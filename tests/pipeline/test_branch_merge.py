"""Tests for ``branch merge`` (slice 196 D6): merge, already merged, abort-to-clean."""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
from squadron.pipeline.actions.branch import BranchAction
from squadron.pipeline.branch_ops import MergeFailedError, MergeOutcome, merge_slice_branch
from squadron.pipeline.git_ops import GitEnvironmentError, GitStateUnknownError
from squadron.pipeline.models import ActionContext
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
    return client


def _commit_file(repo: Path, name: str, text: str = "content\n") -> None:
    (repo / name).write_text(text)
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")


@pytest.fixture
def slice_repo(temp_git_repo: Path) -> Path:
    """A repo on its slice branch, one commit ahead of main."""
    run_test_git(temp_git_repo, "checkout", "-q", "-b", BRANCH)
    _commit_file(temp_git_repo, "feature.py")
    return temp_git_repo


def _branch(repo: Path) -> str:
    return run_test_git(repo, "branch", "--show-current").strip()


def _merge(repo: Path):  # type: ignore[no-untyped-def]
    return merge_slice_branch(SLICE, str(repo), _cf())


def _snapshot(repo: Path) -> tuple[str, str, str]:
    return (
        _branch(repo),
        run_test_git(repo, "status", "--porcelain", "-uall"),
        run_test_git(repo, "rev-parse", "main"),
    )


# ---------------------------------------------------------------------------
# Happy path and already merged
# ---------------------------------------------------------------------------


def test_clean_merge_ends_on_the_target_with_a_merge_commit(slice_repo: Path) -> None:
    result = _merge(slice_repo)

    assert result.outcome is MergeOutcome.MERGED
    assert _branch(slice_repo) == "main"
    assert (slice_repo / "feature.py").exists()
    assert run_test_git(slice_repo, "log", "-1", "--format=%s").strip() == (
        "merge: slice 105 — Batch Foo"
    )
    parents = run_test_git(slice_repo, "log", "-1", "--format=%p").split()
    assert len(parents) == 2  # --no-ff: a real merge commit
    assert run_test_git(slice_repo, "branch", "--list", BRANCH).strip() == BRANCH


def test_already_merged_succeeds_without_a_new_commit(slice_repo: Path) -> None:
    run_test_git(slice_repo, "checkout", "-q", "main")
    run_test_git(slice_repo, "merge", "-q", "--no-ff", "-m", "merged by the agent", BRANCH)
    head = run_test_git(slice_repo, "rev-parse", "HEAD")

    result = _merge(slice_repo)

    assert result.outcome is MergeOutcome.ALREADY
    assert run_test_git(slice_repo, "rev-parse", "HEAD") == head


@pytest.mark.asyncio
async def test_action_reports_branch_target_and_outcome(slice_repo: Path) -> None:
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "merge", "slice": str(SLICE)},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(slice_repo),
    )

    result = await BranchAction().execute(context)

    assert result.success is True
    assert result.outputs == {"branch": BRANCH, "target": "main", "merged": "merged"}


# ---------------------------------------------------------------------------
# Guards
# ---------------------------------------------------------------------------


def test_wrong_branch_raises_and_changes_nothing(slice_repo: Path) -> None:
    run_test_git(slice_repo, "checkout", "-q", "main")
    before = _snapshot(slice_repo)

    with pytest.raises(GitEnvironmentError, match=f"on main, expected {BRANCH} to merge it"):
        _merge(slice_repo)

    assert _snapshot(slice_repo) == before


def test_dirty_tree_raises_and_changes_nothing(slice_repo: Path) -> None:
    (slice_repo / "feature.py").write_text("edited\n")
    before = _snapshot(slice_repo)

    with pytest.raises(GitEnvironmentError, match="working tree not clean before merging"):
        _merge(slice_repo)

    assert _snapshot(slice_repo) == before


def test_target_checked_out_in_another_worktree_raises(slice_repo: Path, tmp_path: Path) -> None:
    # main stays checked out in the primary checkout; the slice branch moves to a worktree.
    run_test_git(slice_repo, "checkout", "-q", "main")
    holder = tmp_path / "holder"
    run_test_git(slice_repo, "worktree", "add", "-q", str(holder), BRANCH)

    with pytest.raises(GitEnvironmentError, match="already"):
        _merge(holder)

    assert _branch(holder) == BRANCH


# ---------------------------------------------------------------------------
# Failure and abort
# ---------------------------------------------------------------------------


@pytest.fixture
def conflicting_repo(slice_repo: Path) -> Path:
    """The slice branch and main both changed README.md differently."""
    _commit_file(slice_repo, "README.md", "slice version\n")
    run_test_git(slice_repo, "checkout", "-q", "main")
    _commit_file(slice_repo, "README.md", "main version\n")
    run_test_git(slice_repo, "checkout", "-q", BRANCH)
    return slice_repo


def test_conflict_is_aborted_back_to_a_clean_target(conflicting_repo: Path) -> None:
    with pytest.raises(MergeFailedError) as excinfo:
        _merge(conflicting_repo)

    message = str(excinfo.value)
    assert message.startswith("merge failed: ")
    assert "README.md" in message
    assert f"slice branch {BRANCH} left unmerged" in message
    assert _branch(conflicting_repo) == "main"
    assert run_test_git(conflicting_repo, "status", "--porcelain", "-uall") == ""
    assert not (conflicting_repo / ".git" / "MERGE_HEAD").exists()
    unmerged = subprocess.run(
        ["git", "merge-base", "--is-ancestor", BRANCH, "main"], cwd=conflicting_repo, check=False
    )
    assert unmerged.returncode == 1


@pytest.mark.asyncio
async def test_action_turns_a_failed_merge_into_an_item_failure(conflicting_repo: Path) -> None:
    context = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"op": "merge", "slice": str(SLICE)},
        step_name="s",
        step_index=0,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=_cf(),
        cwd=str(conflicting_repo),
    )

    result = await BranchAction().execute(context)

    assert result.success is False
    assert "merge failed" in (result.error or "")


def _fake_git(
    **overrides: subprocess.CompletedProcess[str] | None,
) -> Callable[..., subprocess.CompletedProcess[str] | None]:
    """A ``run_git`` that answers like git except for the commands named in ``overrides``."""
    from squadron.review.git_utils import run_git as real_run_git

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        key = args[0] if args[0] != "merge" else " ".join(args[:2])
        if key in overrides:
            return overrides[key]
        return real_run_git(args, cwd=cwd)

    return fake


def test_a_refusal_without_a_conflict_is_an_item_failure_with_gits_text(slice_repo: Path) -> None:
    refusal = subprocess.CompletedProcess(
        [], 1, stdout="", stderr="error: untracked working tree files would be overwritten"
    )

    with patch(
        "squadron.pipeline.branch_ops.run_git", side_effect=_fake_git(**{"merge --no-ff": refusal})
    ):
        with pytest.raises(MergeFailedError, match="untracked working tree files"):
            _merge(slice_repo)

    assert _branch(slice_repo) == "main"


def test_a_failing_abort_raises_state_unknown_and_logs_error(
    conflicting_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    abort_fails = subprocess.CompletedProcess([], 1, stdout="", stderr="boom")

    with (
        patch(
            "squadron.pipeline.branch_ops.run_git",
            side_effect=_fake_git(**{"merge --abort": abort_fails}),
        ),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.branch_ops"),
    ):
        with pytest.raises(GitStateUnknownError, match="MERGE_HEAD present, abort failed: boom"):
            _merge(conflicting_repo)

    assert any(r.levelno == logging.ERROR for r in caplog.records)


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------


def test_checkout_timeout_with_a_settled_repo_is_an_environment_error(slice_repo: Path) -> None:
    with patch("squadron.pipeline.branch_ops.run_git", side_effect=_fake_git(checkout=None)):
        with pytest.raises(GitEnvironmentError, match="git timed out") as excinfo:
            _merge(slice_repo)

    assert not isinstance(excinfo.value, GitStateUnknownError)


def test_checkout_timeout_with_an_unverifiable_state_raises_state_unknown(
    slice_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def status_hangs(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "status" else real_run_git(args, cwd=cwd)

    with (
        patch("squadron.pipeline.branch_ops.run_git", side_effect=_fake_git(checkout=None)),
        patch("squadron.pipeline.git_ops.run_git", side_effect=status_hangs),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
    ):
        with pytest.raises(GitStateUnknownError):
            _merge(slice_repo)

    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_merge_timeout_with_a_clean_target_is_an_item_failure(slice_repo: Path) -> None:
    with patch(
        "squadron.pipeline.branch_ops.run_git", side_effect=_fake_git(**{"merge --no-ff": None})
    ):
        with pytest.raises(MergeFailedError, match="git timed out"):
            _merge(slice_repo)


def test_merge_timeout_with_an_unverifiable_state_raises_state_unknown(
    slice_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    from squadron.review.git_utils import run_git as real_run_git

    def status_hangs(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        return None if args[0] == "status" else real_run_git(args, cwd=cwd)

    with (
        patch("squadron.pipeline.branch_ops.run_git", side_effect=_fake_git(**{"merge --no-ff": None})),
        patch("squadron.pipeline.git_ops.run_git", side_effect=status_hangs),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
    ):
        with pytest.raises(GitStateUnknownError):
            _merge(slice_repo)

    assert any(r.levelno == logging.ERROR for r in caplog.records)
