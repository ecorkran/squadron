"""Tests for ``branch enter`` (slice 196 D5): guards, switch, leftover preservation."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeError,
    ProjectInfo,
    SliceEntry,
    TaskEntry,
    WorktreeEntry,
)
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.branch_ops import enter_slice_branch
from squadron.pipeline.git_ops import GitEnvironmentError, GitStateUnknownError, NoDesignFileError
from squadron.pipeline.models import ActionContext
from tests.conftest import run_test_git

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
BRANCH = "105-slice.batch-foo"


def _cf(
    *,
    design_file: str | None = DESIGN_FILE,
    integration_branch: str = "",
    worktrees: list[WorktreeEntry] | None = None,
) -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=design_file, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=[])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice=str(SLICE), name="squadron"
    )
    client.get_config.return_value = integration_branch
    client.list_worktrees.return_value = worktrees or []
    return client


def _write(repo: Path, relative: str, text: str = "content\n") -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _branch(repo: Path) -> str:
    return run_test_git(repo, "branch", "--show-current").strip()


def _enter(repo: Path, cf: MagicMock | None = None):  # type: ignore[no-untyped-def]
    return enter_slice_branch(SLICE, str(repo), cf or _cf())


# ---------------------------------------------------------------------------
# Switch
# ---------------------------------------------------------------------------


def test_creates_the_slice_branch_from_the_target(temp_git_repo: Path) -> None:
    result = _enter(temp_git_repo)

    assert (result.branch, result.target, result.created) == (BRANCH, "main", True)
    assert _branch(temp_git_repo) == BRANCH
    fork = run_test_git(temp_git_repo, "merge-base", BRANCH, "main").strip()
    assert fork == run_test_git(temp_git_repo, "rev-parse", "main").strip()


def test_checks_out_an_existing_slice_branch(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", BRANCH)

    result = _enter(temp_git_repo)

    assert result.created is False
    assert _branch(temp_git_repo) == BRANCH


def test_already_on_the_slice_branch_is_a_no_op_success(temp_git_repo: Path) -> None:
    _enter(temp_git_repo)
    result = _enter(temp_git_repo)

    assert (result.branch, result.created) == (BRANCH, False)


def test_forks_from_a_configured_integration_branch(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "dev/erik")
    _write(temp_git_repo, "integration.txt")
    run_test_git(temp_git_repo, "add", "-A")
    run_test_git(temp_git_repo, "commit", "-q", "-m", "integration work")

    result = _enter(temp_git_repo, _cf(integration_branch="dev/erik"))

    assert result.target == "dev/erik"
    assert (temp_git_repo / "integration.txt").exists()


# ---------------------------------------------------------------------------
# Another slice's unmerged branch
# ---------------------------------------------------------------------------


def test_leftovers_on_another_slices_branch_are_committed_there(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "106-slice.other")
    _write(temp_git_repo, "README.md", "edited\n")
    _write(temp_git_repo, "leftover.txt")

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.branch_ops"):
        result = _enter(temp_git_repo)

    assert _branch(temp_git_repo) == BRANCH
    assert result.created is True
    subjects = run_test_git(temp_git_repo, "log", "106-slice.other", "--format=%s").splitlines()
    assert subjects[0] == "chore: preserve uncommitted work on flagged slice 106"
    # The new branch forks from the target, so it carries none of the leftovers.
    assert not (temp_git_repo / "leftover.txt").exists()
    assert any(
        "left unmerged slice branch 106-slice.other for main" in r.message for r in caplog.records
    )


def test_clean_other_slice_branch_is_left_without_a_commit(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "106-slice.other")
    before = run_test_git(temp_git_repo, "rev-parse", "106-slice.other").strip()

    with caplog.at_level(logging.WARNING, logger="squadron.pipeline.branch_ops"):
        _enter(temp_git_repo)

    assert run_test_git(temp_git_repo, "rev-parse", "106-slice.other").strip() == before
    assert _branch(temp_git_repo) == BRANCH
    assert any("left unmerged slice branch" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Guards: each leaves branch and status untouched
# ---------------------------------------------------------------------------


def _snapshot(repo: Path) -> tuple[str, str]:
    return _branch(repo), run_test_git(repo, "status", "--porcelain", "-uall")


def test_cf_config_failure_raises_and_changes_nothing(temp_git_repo: Path) -> None:
    cf = _cf()
    cf.get_config.side_effect = ContextForgeError("cf broke")
    before = _snapshot(temp_git_repo)

    with pytest.raises(GitEnvironmentError, match="Refusing to guess"):
        _enter(temp_git_repo, cf)

    assert _snapshot(temp_git_repo) == before


def test_foreign_branch_raises_and_changes_nothing(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "scratch")
    before = _snapshot(temp_git_repo)

    with pytest.raises(GitEnvironmentError, match=f"on scratch, expected main or {BRANCH}"):
        _enter(temp_git_repo)

    assert _snapshot(temp_git_repo) == before


def test_dirty_tree_lists_paths_and_the_recovery(temp_git_repo: Path) -> None:
    _write(temp_git_repo, "unrelated.txt")
    _write(temp_git_repo, "README.md", "edited\n")
    before = _snapshot(temp_git_repo)

    with pytest.raises(GitEnvironmentError) as excinfo:
        _enter(temp_git_repo)

    message = str(excinfo.value)
    assert "working tree not clean: " in message
    assert "unrelated.txt" in message and "README.md" in message
    assert "rerun phase 6 for slice 105; design and tasks commits from this run are kept" in message
    assert _snapshot(temp_git_repo) == before


def test_no_design_file_is_an_item_failure_not_a_halt(temp_git_repo: Path) -> None:
    before = _snapshot(temp_git_repo)

    with pytest.raises(NoDesignFileError, match="slice 105 has no design file"):
        _enter(temp_git_repo, _cf(design_file=None))

    assert _snapshot(temp_git_repo) == before


@pytest.mark.asyncio
async def test_action_turns_the_item_failure_into_a_failed_result(temp_git_repo: Path) -> None:
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "enter", "slice": str(SLICE)},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(design_file=None),
        cwd=str(temp_git_repo),
    )

    result = await BranchAction().execute(context)

    assert result.success is False
    assert "has no design file" in (result.error or "")
    assert result.outputs == {"failure": "other"}


@pytest.mark.asyncio
async def test_action_outputs_branch_target_and_created(temp_git_repo: Path) -> None:
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "enter", "slice": str(SLICE)},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(temp_git_repo),
    )

    result = await BranchAction().execute(context)

    assert result.success is True
    assert result.outputs == {"branch": BRANCH, "target": "main", "created": True}


def _action_context(repo: Path, cf: MagicMock) -> ActionContext:
    return ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "enter", "slice": str(SLICE)},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=cf,
        cwd=str(repo),
    )


@pytest.mark.asyncio
async def test_action_flags_a_slice_missing_from_the_plan(temp_git_repo: Path) -> None:
    cf = _cf()
    cf.list_slices.return_value = []

    result = await BranchAction().execute(_action_context(temp_git_repo, cf))

    assert result.success is False
    assert "No slice with index 105" in (result.error or "")


@pytest.mark.asyncio
async def test_action_lets_an_unrelated_value_error_end_the_run(temp_git_repo: Path) -> None:
    """Only the named item failures become a failed result; an internal fault propagates."""
    with (
        patch(
            "squadron.pipeline.actions.branch.enter_slice_branch",
            side_effect=ValueError("internal fault"),
        ),
        pytest.raises(ValueError, match="internal fault"),
    ):
        await BranchAction().execute(_action_context(temp_git_repo, _cf()))


def test_unexpected_git_dir_output_is_an_environment_error(temp_git_repo: Path) -> None:
    with (
        patch("squadron.pipeline.branch_ops._git_stdout", return_value="only-one-line\n"),
        pytest.raises(GitEnvironmentError, match="unexpected git rev-parse output"),
    ):
        _enter(temp_git_repo)


# ---------------------------------------------------------------------------
# Worktrees
# ---------------------------------------------------------------------------


@pytest.fixture
def linked_worktree(temp_git_repo: Path, tmp_path: Path) -> Path:
    path = tmp_path / "linked"
    run_test_git(temp_git_repo, "worktree", "add", "-q", "-b", "wt-branch", str(path))
    return path


def test_unregistered_linked_worktree_raises(linked_worktree: Path) -> None:
    before = _snapshot(linked_worktree)

    with pytest.raises(GitEnvironmentError, match="unregistered worktree"):
        _enter(linked_worktree, _cf(worktrees=[WorktreeEntry("default", "/somewhere/else")]))

    assert _snapshot(linked_worktree) == before


def test_registered_linked_worktree_passes_the_guard(linked_worktree: Path) -> None:
    registered = _cf(worktrees=[WorktreeEntry("pr", str(linked_worktree))])

    # It then stops at the next guard (the worktree sits on its own branch), which
    # proves the worktree guard let it through.
    with pytest.raises(GitEnvironmentError, match="on wt-branch, expected main"):
        _enter(linked_worktree, registered)


def test_cf_failure_listing_worktrees_raises(linked_worktree: Path) -> None:
    cf = _cf()
    cf.list_worktrees.side_effect = ContextForgeError("no registry")

    with pytest.raises(GitEnvironmentError, match="cannot list cf worktrees"):
        _enter(linked_worktree, cf)


def test_primary_checkout_never_consults_the_worktree_list(temp_git_repo: Path) -> None:
    cf = _cf()
    _enter(temp_git_repo, cf)
    cf.list_worktrees.assert_not_called()


def test_branch_checked_out_in_another_worktree_raises_without_forcing(
    temp_git_repo: Path, tmp_path: Path
) -> None:
    run_test_git(temp_git_repo, "worktree", "add", "-q", "-b", BRANCH, str(tmp_path / "holder"))
    before = _snapshot(temp_git_repo)

    with pytest.raises(GitEnvironmentError, match="already"):
        _enter(temp_git_repo)

    assert _snapshot(temp_git_repo) == before


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------


def test_a_checkout_timeout_with_a_settled_repo_raises_an_environment_error(
    temp_git_repo: Path,
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def fake_run_git(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "checkout" else real_run_git(args, cwd=cwd)

    with patch("squadron.pipeline.branch_ops.run_git", side_effect=fake_run_git):
        with pytest.raises(GitEnvironmentError, match="git timed out") as excinfo:
            _enter(temp_git_repo)

    assert not isinstance(excinfo.value, GitStateUnknownError)


def test_a_checkout_timeout_with_an_unverifiable_state_raises_state_unknown(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def checkout_hangs(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "checkout" else real_run_git(args, cwd=cwd)

    def status_hangs(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "status" else real_run_git(args, cwd=cwd)

    with (
        patch("squadron.pipeline.branch_ops.run_git", side_effect=checkout_hangs),
        patch("squadron.pipeline.git_ops.run_git", side_effect=status_hangs),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
    ):
        with pytest.raises(GitStateUnknownError):
            _enter(temp_git_repo)

    assert any(r.levelno == logging.ERROR for r in caplog.records)
