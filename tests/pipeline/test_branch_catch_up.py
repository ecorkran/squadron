"""Tests for ``branch enter`` catching an existing slice branch up to the target (slice 197 D5)."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.branch_ops import BranchFailure, MergeFailedError, enter_slice_branch
from squadron.pipeline.git_ops import GitStateUnknownError, branch_work_count
from squadron.review.git_utils import resolve_slice_diff_range
from tests.conftest import run_test_git

SLICE = 105
DESIGN_FILE = "project-documents/user/slices/105-slice.batch-foo.md"
BRANCH = "105-slice.batch-foo"


def _cf() -> MagicMock:
    client = MagicMock()
    client.list_slices.return_value = [
        SliceEntry(index=SLICE, name="Batch Foo", design_file=DESIGN_FILE, status="in_progress")
    ]
    client.list_tasks.return_value = [TaskEntry(index=SLICE, files=[])]
    client.get_project.return_value = ProjectInfo(
        arch_file="a.md", slice_plan="p", phase="Phase 6", slice=str(SLICE), name="squadron"
    )
    client.get_config.return_value = ""
    client.list_worktrees.return_value = []
    return client


def _commit_file(repo: Path, name: str, text: str = "content\n") -> None:
    (repo / name).write_text(text)
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")


def _branch(repo: Path) -> str:
    return run_test_git(repo, "branch", "--show-current").strip()


def _subjects(repo: Path, ref: str) -> list[str]:
    return run_test_git(repo, "log", ref, "--format=%s").splitlines()


def _enter(repo: Path):  # type: ignore[no-untyped-def]
    return enter_slice_branch(SLICE, str(repo), _cf())


@pytest.fixture
def behind_with_work(temp_git_repo: Path) -> Path:
    """The slice branch has one commit of its own; main moved on after the fork."""
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)
    _commit_file(temp_git_repo, "feature.py")
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    _commit_file(temp_git_repo, "main-only.txt")
    return temp_git_repo


def test_behind_with_work_merges_the_target_in(behind_with_work: Path) -> None:
    _enter(behind_with_work)

    assert _branch(behind_with_work) == BRANCH
    assert _subjects(behind_with_work, BRANCH)[0] == f"merge: main into slice {SLICE}"
    assert "add feature.py" in _subjects(behind_with_work, BRANCH)
    assert (behind_with_work / "main-only.txt").exists()


def test_behind_with_no_work_fast_forwards(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", BRANCH)
    _commit_file(temp_git_repo, "main-only.txt")

    _enter(temp_git_repo)

    tip = run_test_git(temp_git_repo, "rev-parse", BRANCH).strip()
    assert tip == run_test_git(temp_git_repo, "rev-parse", "main").strip()
    assert not any(s.startswith("merge:") for s in _subjects(temp_git_repo, BRANCH))
    assert branch_work_count(BRANCH, "main", cwd=str(temp_git_repo)) == 0


def test_not_behind_attempts_no_merge(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)
    _commit_file(temp_git_repo, "feature.py")
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    before = run_test_git(temp_git_repo, "rev-parse", BRANCH)

    with patch("squadron.pipeline.branch_ops.run_git", wraps=_real_run_git()) as spy:
        _enter(temp_git_repo)

    assert run_test_git(temp_git_repo, "rev-parse", BRANCH) == before
    assert not any(call.args[0][0] == "merge" for call in spy.call_args_list)


def test_review_diff_range_after_catch_up_excludes_target_only_commits(
    behind_with_work: Path,
) -> None:
    _enter(behind_with_work)

    diff_range = resolve_slice_diff_range(SLICE, str(behind_with_work), base="main")
    changed = run_test_git(behind_with_work, "diff", "--name-only", diff_range).split()
    assert changed == ["feature.py"]


# ---------------------------------------------------------------------------
# Conflict, refusal and an unverifiable state
# ---------------------------------------------------------------------------


@pytest.fixture
def conflicting(behind_with_work: Path) -> Path:
    """Both the slice branch and main changed README.md differently."""
    run_test_git(behind_with_work, "checkout", "-q", BRANCH)
    _commit_file(behind_with_work, "README.md", "slice version\n")
    run_test_git(behind_with_work, "checkout", "-q", "main")
    _commit_file(behind_with_work, "README.md", "main version\n")
    return behind_with_work


def test_conflict_aborts_onto_the_clean_slice_branch(conflicting: Path) -> None:
    before = run_test_git(conflicting, "rev-parse", BRANCH)

    with pytest.raises(MergeFailedError) as excinfo:
        _enter(conflicting)

    message = str(excinfo.value)
    assert message.startswith(f"catch-up merge of main into {BRANCH} failed: ")
    assert "CONFLICT" in message
    assert "(conflicted: README.md)" in message
    assert message.endswith("resolve on the branch and retry")
    assert excinfo.value.failure is BranchFailure.CONFLICT
    assert _branch(conflicting) == BRANCH
    assert not (conflicting / ".git" / "MERGE_HEAD").exists()
    assert run_test_git(conflicting, "status", "--porcelain", "-uall") == ""
    assert run_test_git(conflicting, "rev-parse", BRANCH) == before


@pytest.mark.asyncio
async def test_conflict_flags_the_item_with_a_warning(
    conflicting: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """D12 row 3: the item is flagged, with the conflicted path in the WARNING."""
    from squadron.pipeline.actions.branch import BranchAction
    from squadron.pipeline.batch_report import ItemOutcome
    from squadron.pipeline.executor import execute_pipeline
    from squadron.pipeline.models import PipelineDefinition, StepConfig
    from squadron.pipeline.sources import SOURCE_REGISTRY

    async def source(*_: object, **__: object) -> list[dict[str, object]]:
        return [{"index": str(SLICE), "name": "Batch Foo"}]

    monkeypatch.setitem(SOURCE_REGISTRY, ("test", "slices"), source)
    definition = PipelineDefinition(
        name="catch-up",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="each",
                name="slices",
                config={
                    "source": "test.slices()",
                    "as": "slice",
                    "on_item_failure": "continue",
                    "steps": [{"branch": {"op": "enter", "slice": "{slice.index}"}}],
                },
            )
        ],
    )
    caplog.set_level(logging.WARNING)

    result = await execute_pipeline(
        definition,
        {"_project": "test"},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(conflicting),
        runs_dir=tmp_path / "runs",
        _action_registry={"branch": BranchAction()},
    )

    report = result.step_results[0].batch_report
    assert report is not None
    assert report.records[0].outcome is ItemOutcome.FLAGGED
    assert any(
        r.levelno == logging.WARNING
        and f"item {SLICE} FLAGGED: catch-up merge of main into {BRANCH}" in r.getMessage()
        and "conflicted: README.md" in r.getMessage()
        for r in caplog.records
    )


def _real_run_git() -> Callable[..., subprocess.CompletedProcess[str] | None]:
    from squadron.review.git_utils import run_git

    return run_git


def _failing_merge(
    answer: subprocess.CompletedProcess[str] | None,
) -> Callable[..., subprocess.CompletedProcess[str] | None]:
    """A ``run_git`` that answers like git, except the catch-up merge returns ``answer``."""
    real = _real_run_git()

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[:2] == ["merge", "--no-ff"]:
            return answer
        return real(args, cwd=cwd)

    return fake


@pytest.mark.parametrize(
    "answer",
    [
        subprocess.CompletedProcess([], 1, stdout="", stderr="error: refusing to merge"),
        None,  # timeout
    ],
)
def test_refusal_with_a_settled_state_is_an_other_item_failure(
    behind_with_work: Path, answer: subprocess.CompletedProcess[str] | None
) -> None:
    with patch("squadron.pipeline.branch_ops.run_git", side_effect=_failing_merge(answer)):
        with pytest.raises(MergeFailedError) as excinfo:
            _enter(behind_with_work)

    assert excinfo.value.failure is BranchFailure.OTHER
    assert _branch(behind_with_work) == BRANCH


def test_refusal_with_an_unverifiable_state_raises_and_logs_error(
    behind_with_work: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """D12 row 4: a failed state check after a refused catch-up ends the run."""
    real = _real_run_git()

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[:2] == ["merge", "--no-ff"]:
            # Leave the tree dirty so verify_git_state cannot pass.
            (behind_with_work / "README.md").write_text("half-merged\n")
            return None
        return real(args, cwd=cwd)

    with (
        patch("squadron.pipeline.branch_ops.run_git", side_effect=fake),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
    ):
        with pytest.raises(GitStateUnknownError, match="tracked changes: README.md"):
            _enter(behind_with_work)

    assert any(
        r.levelno == logging.ERROR and "git state unverified" in r.getMessage() for r in caplog.records
    )
