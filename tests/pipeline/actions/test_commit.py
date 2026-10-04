"""Tests for CommitAction (slice 196 D1-D3, D6, D8)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.git_ops import GitEnvironmentError, GitStateUnknownError
from squadron.pipeline.models import ActionContext
from tests.conftest import run_test_git

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
TASKS_FILE = "project-documents/user/tasks/105-tasks.batch-foo.md"
ARCH_FILE = "project-documents/user/architecture/100-arch.plan-name.md"
DESIGN_REVIEW = "project-documents/user/reviews/105-review.slice.batch-foo.md"
SLICE_BRANCH = "105-slice.batch-foo"


@pytest.fixture
def action() -> CommitAction:
    return CommitAction()


def _cf(integration_branch: str = "") -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=DESIGN_FILE, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=["105-tasks.batch-foo.md"])]
    client.get_project.return_value = ProjectInfo(
        arch_file=ARCH_FILE,
        slice_plan="100-slices.plan-name",
        phase="Phase 4",
        slice=str(SLICE),
        name="squadron",
    )
    client.get_config.return_value = integration_branch
    return client


def _context(
    repo: Path,
    cf_client: MagicMock | None = None,
    *,
    iteration: int = 0,
    params: dict[str, object] | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params=dict(params or {}),
        step_name="commit-step",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=cf_client or _cf(),
        cwd=str(repo),
        iteration=iteration,
    )


def _write(repo: Path, relative: str, text: str = "content\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _porcelain(repo: Path) -> str:
    return run_test_git(repo, "status", "--porcelain", "-uall")


def _design_params(**extra: object) -> dict[str, object]:
    return {"commit_subject": "design", "slice": str(SLICE), "review_template": "slice", **extra}


def test_action_type(action: CommitAction) -> None:
    assert action.action_type == "commit"


def test_protocol_compliance(action: CommitAction) -> None:
    assert isinstance(action, Action)


# ---------------------------------------------------------------------------
# Scoped staging and messages (D1, D2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commits_planned_paths_and_leaves_a_stray_file_modified(
    action: CommitAction, temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(temp_git_repo, DESIGN_FILE)
    _write(temp_git_repo, DESIGN_REVIEW, "---\nverdict: CONCERNS\n---\n")
    _write(temp_git_repo, "stray.txt")

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.actions.commit"):
        result = await action.execute(_context(temp_git_repo, params=_design_params()))

    assert result.success is True
    assert result.outputs["committed"] is True
    assert result.outputs["message"] == "docs: add slice 105 design (review: CONCERNS)"
    assert len(str(result.outputs["sha"])) == 40
    assert _porcelain(temp_git_repo) == "?? stray.txt\n"
    assert any("stray.txt" in r.message for r in caplog.records)


@pytest.mark.asyncio
async def test_nothing_staged_returns_committed_false_and_warns(
    action: CommitAction, temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    _write(temp_git_repo, "stray.txt")

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.actions.commit"):
        result = await action.execute(_context(temp_git_repo, params=_design_params()))

    assert result.success is True
    assert result.outputs["committed"] is False
    assert any("step commit-step produced no changes to commit" in r.message for r in caplog.records)
    assert _porcelain(temp_git_repo) == "?? stray.txt\n"


@pytest.mark.asyncio
async def test_explicit_message_is_used_verbatim(action: CommitAction, temp_git_repo: Path) -> None:
    _write(temp_git_repo, DESIGN_FILE)

    result = await action.execute(
        _context(temp_git_repo, params=_design_params(message="feat: my own words"), iteration=2)
    )

    assert result.outputs["message"] == "feat: my own words"


@pytest.mark.asyncio
async def test_loop_round_message_carries_the_round(action: CommitAction, temp_git_repo: Path) -> None:
    _write(temp_git_repo, DESIGN_FILE, "v1\n")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "design v1")
    _write(temp_git_repo, DESIGN_FILE, "v2\n")
    _write(temp_git_repo, DESIGN_REVIEW, "---\nverdict: PASS\n---\n")

    result = await action.execute(_context(temp_git_repo, params=_design_params(), iteration=2))

    assert result.outputs["message"] == "docs: revise slice 105 design, round 2 (review: PASS)"


@pytest.mark.asyncio
async def test_content_already_in_the_index_is_not_swept_into_the_commit(
    action: CommitAction, temp_git_repo: Path
) -> None:
    _write(temp_git_repo, DESIGN_FILE)
    _write(temp_git_repo, "pre_staged.txt")
    run_test_git(temp_git_repo, "add", "pre_staged.txt")

    await action.execute(_context(temp_git_repo, params=_design_params()))

    assert _porcelain(temp_git_repo) == "A  pre_staged.txt\n"


@pytest.mark.asyncio
async def test_hook_rejection_is_an_ordinary_failure_carrying_stderr(
    action: CommitAction, temp_git_repo: Path
) -> None:
    hook = temp_git_repo / ".git" / "hooks" / "pre-commit"
    hook.write_text("#!/bin/sh\necho 'hook says no' >&2\nexit 1\n")
    hook.chmod(0o755)
    _write(temp_git_repo, DESIGN_FILE)

    result = await action.execute(_context(temp_git_repo, params=_design_params()))

    assert result.success is False
    assert "hook says no" in (result.error or "")


@pytest.mark.asyncio
async def test_no_subject_and_no_paths_never_stages_everything(
    action: CommitAction, temp_git_repo: Path
) -> None:
    _write(temp_git_repo, "file.txt")

    result = await action.execute(_context(temp_git_repo, params={"message": "feat: x"}))

    assert result.success is False
    assert "refusing to stage everything" in (result.error or "")
    assert _porcelain(temp_git_repo) == "?? file.txt\n"


@pytest.mark.asyncio
async def test_explicit_paths_scope_staging(action: CommitAction, temp_git_repo: Path) -> None:
    _write(temp_git_repo, "include.txt")
    _write(temp_git_repo, "exclude.txt")

    result = await action.execute(
        _context(temp_git_repo, params={"paths": ["include.txt"], "message": "feat: scoped"})
    )

    assert result.outputs["committed"] is True
    assert _porcelain(temp_git_repo) == "?? exclude.txt\n"


@pytest.mark.asyncio
async def test_explicit_paths_need_a_message(action: CommitAction, temp_git_repo: Path) -> None:
    _write(temp_git_repo, "include.txt")

    result = await action.execute(_context(temp_git_repo, params={"paths": ["include.txt"]}))

    assert result.success is False
    assert "needs a 'message'" in (result.error or "")


@pytest.mark.asyncio
async def test_not_a_git_repository_raises(action: CommitAction, tmp_path: Path) -> None:
    with pytest.raises(GitEnvironmentError):
        await action.execute(_context(tmp_path, params=_design_params()))


# ---------------------------------------------------------------------------
# Placement guards (D3, D8)
# ---------------------------------------------------------------------------


def _code_params(**extra: object) -> dict[str, object]:
    return {"commit_subject": "code", "slice": str(SLICE), "review_template": "code", **extra}


@pytest.mark.asyncio
async def test_code_on_its_slice_branch_stages_everything(
    action: CommitAction, temp_git_repo: Path
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", SLICE_BRANCH)
    _write(temp_git_repo, "src/feature.py")
    _write(temp_git_repo, "anything/else.txt")

    result = await action.execute(_context(temp_git_repo, params=_code_params()))

    assert result.outputs["committed"] is True
    assert result.outputs["message"] == "feat: implement slice 105"
    assert _porcelain(temp_git_repo) == ""


@pytest.mark.asyncio
@pytest.mark.parametrize("branch", ["main", "106-slice.other"])
async def test_code_off_its_slice_branch_is_refused(
    action: CommitAction, temp_git_repo: Path, branch: str
) -> None:
    if branch != "main":
        run_test_git(temp_git_repo, "checkout", "-q", "-b", branch)
    _write(temp_git_repo, "src/feature.py")

    result = await action.execute(_context(temp_git_repo, params=_code_params()))

    assert result.success is False
    assert f"refusing to stage all changes off the slice branch (on {branch})" in (result.error or "")
    assert "src/feature.py" in _porcelain(temp_git_repo)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "scope"),
    [
        (_design_params(), "slice 105"),
        ({"commit_subject": "tasks", "slice": str(SLICE), "review_template": "tasks"}, "slice 105"),
        (
            {"commit_subject": "architecture", "plan": "100", "review_template": "arch"},
            "initiative 100",
        ),
    ],
)
async def test_planning_commit_off_the_target_raises(
    action: CommitAction, temp_git_repo: Path, params: dict[str, object], scope: str
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "scratch")
    _write(temp_git_repo, DESIGN_FILE)

    with pytest.raises(
        GitEnvironmentError, match=f"planning commit for {scope} on scratch; expected main"
    ):
        await action.execute(_context(temp_git_repo, params=params))


@pytest.mark.asyncio
async def test_planning_commit_honors_a_configured_integration_branch(
    action: CommitAction, temp_git_repo: Path
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "dev/erik")
    _write(temp_git_repo, DESIGN_FILE)

    result = await action.execute(
        _context(temp_git_repo, _cf(integration_branch="dev/erik"), params=_design_params())
    )

    assert result.outputs["committed"] is True


@pytest.mark.asyncio
async def test_devlog_on_its_own_slice_branch_succeeds(
    action: CommitAction, temp_git_repo: Path
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", SLICE_BRANCH)
    _write(temp_git_repo, "DEVLOG.md")
    _write(temp_git_repo, "src/in_progress.py")

    result = await action.execute(
        _context(temp_git_repo, params={"commit_subject": "devlog", "slice": str(SLICE)})
    )

    assert result.outputs["message"] == "docs: add DEVLOG entry for slice 105"
    # Only the entry is committed; the slice's code in progress stays in the tree.
    assert _porcelain(temp_git_repo) == "?? src/in_progress.py\n"


@pytest.mark.asyncio
async def test_devlog_on_another_slices_branch_raises(
    action: CommitAction, temp_git_repo: Path
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "106-slice.other")
    _write(temp_git_repo, "DEVLOG.md")

    with pytest.raises(GitEnvironmentError, match="planning commit for slice 105 on 106-slice.other"):
        await action.execute(
            _context(temp_git_repo, params={"commit_subject": "devlog", "slice": str(SLICE)})
        )


# ---------------------------------------------------------------------------
# Timeouts (D6)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("hung_command", ["add", "commit"])
async def test_a_git_timeout_raises_state_unknown_and_logs_error(
    action: CommitAction,
    temp_git_repo: Path,
    hung_command: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def fake_run_git(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        if args[0] == hung_command:
            return None
        return real_run_git(args, cwd=cwd)

    _write(temp_git_repo, DESIGN_FILE)
    with (
        patch("squadron.pipeline.actions.commit.run_git", side_effect=fake_run_git),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.actions.commit"),
    ):
        with pytest.raises(GitStateUnknownError, match=f"git {hung_command} timed out"):
            await action.execute(_context(temp_git_repo, params=_design_params()))

    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.asyncio
async def test_code_without_a_slice_is_refused_by_the_placement_guard(
    action: CommitAction, temp_git_repo: Path
) -> None:
    _write(temp_git_repo, "src/feature.py")

    result = await action.execute(_context(temp_git_repo, params={"commit_subject": "code"}))

    assert result.success is False
    assert result.error == "a code commit needs a slice index"
    assert "src/feature.py" in _porcelain(temp_git_repo)


@pytest.mark.asyncio
async def test_an_unreadable_sha_after_a_commit_is_logged(
    action: CommitAction, temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def fake_run_git(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        if args[0] == "rev-parse" and args[-1] == "HEAD":
            return None
        return real_run_git(args, cwd=cwd)

    _write(temp_git_repo, DESIGN_FILE)
    with (
        patch("squadron.pipeline.actions.commit.run_git", side_effect=fake_run_git),
        caplog.at_level(logging.WARNING, logger="squadron.pipeline.actions.commit"),
    ):
        result = await action.execute(_context(temp_git_repo, params=_design_params()))

    assert result.outputs["committed"] is True
    assert result.outputs["sha"] == "unknown"
    assert "cannot read the new HEAD sha" in caplog.text


@pytest.mark.asyncio
async def test_a_deleted_review_is_committed_without_a_verdict(
    action: CommitAction, temp_git_repo: Path
) -> None:
    _write(temp_git_repo, DESIGN_FILE)
    _write(temp_git_repo, DESIGN_REVIEW, "---\nverdict: PASS\n---\n")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "seed")
    (temp_git_repo / DESIGN_REVIEW).unlink()

    result = await action.execute(_context(temp_git_repo, params=_design_params()))

    assert result.success is True, result.error
    assert result.outputs["committed"] is True
    assert _porcelain(temp_git_repo) == ""
