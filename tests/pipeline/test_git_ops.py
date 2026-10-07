"""Tests for the git_ops state and target readers (slice 196 D5, D6)."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import (
    ContextForgeError,
    ContextForgeNotAvailable,
    SliceEntry,
)
from squadron.pipeline.git_ops import (
    GitEnvironmentError,
    GitStateUnknownError,
    NoDesignFileError,
    branch_behind_count,
    branch_work_count,
    merged_slice_branches,
    read_integration_target,
    slice_branch_name,
    verify_git_state,
)
from tests.conftest import run_test_git

# ---------------------------------------------------------------------------
# read_integration_target
# ---------------------------------------------------------------------------


def _cf(value: str | None = None, error: Exception | None = None) -> MagicMock:
    client = MagicMock()
    if error is not None:
        client.get_config.side_effect = error
    else:
        client.get_config.return_value = value
    return client


def test_unset_target_is_main() -> None:
    assert read_integration_target(_cf("")) == "main"


def test_set_target_is_returned() -> None:
    assert read_integration_target(_cf(" dev/erik ")) == "dev/erik"


@pytest.mark.parametrize("error", [ContextForgeNotAvailable("no cf"), ContextForgeError("bad")])
def test_cf_failure_raises_and_never_degrades_to_main(
    error: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"):
        with pytest.raises(GitEnvironmentError, match="Refusing to guess"):
            read_integration_target(_cf(error=error))
    assert any(r.levelno == logging.ERROR for r in caplog.records)


# ---------------------------------------------------------------------------
# slice_branch_name
# ---------------------------------------------------------------------------


def test_branch_name_strips_the_design_prefix() -> None:
    design = "project-documents/user/slices/105-slice.pipeline-batch-foo.md"
    assert slice_branch_name(105, design) == "105-slice.pipeline-batch-foo"


@pytest.mark.parametrize("design_file", [None, ""])
def test_branch_name_without_a_design_file_raises(design_file: str | None) -> None:
    with pytest.raises(NoDesignFileError, match="slice 105 has no design file"):
        slice_branch_name(105, design_file)


# ---------------------------------------------------------------------------
# verify_git_state
# ---------------------------------------------------------------------------


def test_clean_repo_on_expected_branch_passes(temp_git_repo: Path) -> None:
    verify_git_state("main", cwd=str(temp_git_repo))


def test_untracked_files_do_not_fail_the_check(temp_git_repo: Path) -> None:
    (temp_git_repo / "scratch.txt").write_text("x")
    verify_git_state("main", cwd=str(temp_git_repo))


def test_wrong_branch_raises_and_logs_error(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "other")
    with caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"):
        with pytest.raises(GitStateUnknownError, match="on other, expected main"):
            verify_git_state("main", cwd=str(temp_git_repo))
    assert any(r.levelno == logging.ERROR for r in caplog.records)


def test_tracked_changes_raise(temp_git_repo: Path) -> None:
    (temp_git_repo / "README.md").write_text("changed\n")
    with pytest.raises(GitStateUnknownError, match="tracked changes: README.md"):
        verify_git_state("main", cwd=str(temp_git_repo))


def test_merge_head_present_raises(temp_git_repo: Path) -> None:
    head = run_test_git(temp_git_repo, "rev-parse", "HEAD").strip()
    (temp_git_repo / ".git" / "MERGE_HEAD").write_text(f"{head}\n")
    with pytest.raises(GitStateUnknownError, match="MERGE_HEAD present"):
        verify_git_state("main", cwd=str(temp_git_repo))


def test_detached_head_raises(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "--detach")
    with pytest.raises(GitStateUnknownError, match="detached HEAD"):
        verify_git_state("main", cwd=str(temp_git_repo))


@pytest.mark.parametrize("failing_read", ["MERGE_HEAD", "branch", "status"])
def test_a_git_read_that_cannot_answer_raises(
    temp_git_repo: Path, failing_read: str, caplog: pytest.LogCaptureFixture
) -> None:
    """``run_git`` returning None (timeout, no git) is an unknown state, never a pass."""
    from squadron.review.git_utils import run_git as real_run_git

    def fake_run_git(args: list[str], *, cwd: str):  # type: ignore[no-untyped-def]
        if failing_read in " ".join(args):
            return None
        return real_run_git(args, cwd=cwd)

    with (
        patch("squadron.pipeline.git_ops.run_git", side_effect=fake_run_git),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
    ):
        with pytest.raises(GitStateUnknownError, match="read failed"):
            verify_git_state("main", cwd=str(temp_git_repo))
    assert any(r.levelno == logging.ERROR for r in caplog.records)


# ---------------------------------------------------------------------------
# branch_work_count / branch_behind_count (slice 197 D4, D5)
# ---------------------------------------------------------------------------


def _commit(repo: Path, name: str) -> None:
    (repo / name).write_text(f"{name}\n")
    run_test_git(repo, "add", name)
    run_test_git(repo, "commit", "-q", "-m", f"add {name}")


def test_work_count_counts_commits_ahead(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "slice")
    _commit(temp_git_repo, "a.txt")
    _commit(temp_git_repo, "b.txt")
    assert branch_work_count("slice", "main", cwd=str(temp_git_repo)) == 2


def test_work_count_is_zero_when_not_ahead(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", "slice")
    assert branch_work_count("slice", "main", cwd=str(temp_git_repo)) == 0


def test_work_count_ignores_merge_commits(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", "slice")
    _commit(temp_git_repo, "main-only.txt")
    run_test_git(temp_git_repo, "checkout", "-q", "slice")
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge: main", "main")
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    run_test_git(temp_git_repo, "commit", "-q", "--allow-empty", "-m", "later")
    # slice holds only its merge commit beyond main's history
    assert branch_work_count("slice", "main", cwd=str(temp_git_repo)) == 0


def test_behind_count_counts_target_commits(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", "slice")
    _commit(temp_git_repo, "a.txt")
    _commit(temp_git_repo, "b.txt")
    assert branch_behind_count("slice", "main", cwd=str(temp_git_repo)) == 2


@pytest.mark.parametrize(
    ("count", "message"),
    [
        (branch_work_count, "cannot count work on slice: "),
        (branch_behind_count, "cannot compare slice with main: "),
    ],
)
@pytest.mark.parametrize("timeout", [True, False])
def test_count_failure_raises_and_logs_error(
    temp_git_repo: Path,
    count: object,
    message: str,
    timeout: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A failed or timed-out count is never 0 (D12 rows 1 and 2)."""
    assert callable(count)
    cwd = str(temp_git_repo)
    with caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"):
        if timeout:
            with patch("squadron.pipeline.git_ops.run_git", return_value=None):
                with pytest.raises(GitStateUnknownError, match=message):
                    count("slice", "main", cwd=cwd)
        else:  # "slice" does not exist, so rev-list exits non-zero
            with pytest.raises(GitStateUnknownError, match=message):
                count("slice", "main", cwd=cwd)
    assert any(r.levelno == logging.ERROR and message in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# merged_slice_branches (slice 934 D1, D10)
# ---------------------------------------------------------------------------

_DESIGN = "105-slice.batch-foo.md"
_BRANCH = "105-slice.batch-foo"
_ENTRY = SliceEntry(index=105, name="Batch Foo", design_file=_DESIGN, status="in_progress")


def _commit(repo: Path, filename: str) -> None:
    (repo / filename).write_text(f"{filename}\n")
    run_test_git(repo, "add", filename)
    run_test_git(repo, "commit", "-q", "-m", f"add {filename}")


def _slice_branch_with_work(repo: Path) -> None:
    """Create the slice branch with one commit of its own, then return to main."""
    run_test_git(repo, "checkout", "-q", "-b", _BRANCH)
    _commit(repo, "feature.py")
    run_test_git(repo, "checkout", "-q", "main")


def test_no_ff_merged_branch_is_merged(temp_git_repo: Path) -> None:
    _slice_branch_with_work(temp_git_repo)
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge slice", _BRANCH)
    assert merged_slice_branches([_ENTRY], "main", cwd=str(temp_git_repo)) == {105}


def test_fast_forward_merged_branch_is_not_merged(temp_git_repo: Path) -> None:
    _slice_branch_with_work(temp_git_repo)
    run_test_git(temp_git_repo, "merge", "-q", "--ff-only", _BRANCH)
    assert merged_slice_branches([_ENTRY], "main", cwd=str(temp_git_repo)) == set()


def test_branch_entered_with_no_commits_is_not_merged(temp_git_repo: Path) -> None:
    run_test_git(temp_git_repo, "branch", _BRANCH)
    assert merged_slice_branches([_ENTRY], "main", cwd=str(temp_git_repo)) == set()


def test_unmerged_branch_with_work_is_not_merged(temp_git_repo: Path) -> None:
    _slice_branch_with_work(temp_git_repo)
    assert merged_slice_branches([_ENTRY], "main", cwd=str(temp_git_repo)) == set()


def test_missing_branch_is_not_merged_and_logs_nothing(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG, logger="squadron.pipeline.git_ops"):
        assert merged_slice_branches([_ENTRY], "main", cwd=str(temp_git_repo)) == set()
    assert caplog.records == []


def test_slice_without_a_design_file_is_not_merged(temp_git_repo: Path) -> None:
    entry = SliceEntry(index=106, name="No Design", design_file=None, status="not_started")
    assert merged_slice_branches([entry], "main", cwd=str(temp_git_repo)) == set()


def test_mixed_set_returns_only_the_merged_slices(temp_git_repo: Path) -> None:
    _slice_branch_with_work(temp_git_repo)
    run_test_git(temp_git_repo, "merge", "-q", "--no-ff", "-m", "merge slice", _BRANCH)
    other = SliceEntry(index=107, name="Open", design_file="107-slice.open.md", status="x")
    run_test_git(temp_git_repo, "checkout", "-q", "-b", "107-slice.open")
    _commit(temp_git_repo, "open.py")
    run_test_git(temp_git_repo, "checkout", "-q", "main")
    entries = [_ENTRY, other]
    assert merged_slice_branches(entries, "main", cwd=str(temp_git_repo)) == {105}


# D10: each of the three git calls, timing out and exiting non-zero.

_OK = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
_TIP = f"{_BRANCH} {'a' * 40}\n"


def _git_stub(failing: str, outcome: subprocess.CompletedProcess[str] | None):  # type: ignore[no-untyped-def]
    """A ``run_git`` fake that answers every call sanely except the ``failing`` one."""

    def fake(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
        if args[0] == failing or (failing == "merge-base" and args[0] == "merge-base"):
            return outcome
        if args[0] == "for-each-ref":
            return subprocess.CompletedProcess(args, 0, stdout=_TIP, stderr="")
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    return fake


@pytest.mark.parametrize("command", ["for-each-ref", "rev-list", "merge-base"])
@pytest.mark.parametrize(
    "outcome",
    [None, subprocess.CompletedProcess(args=[], returncode=128, stdout="", stderr="fatal: boom")],
    ids=["timeout", "non-zero"],
)
def test_git_failure_raises_and_logs_error(
    command: str,
    outcome: subprocess.CompletedProcess[str] | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    with (
        patch("squadron.pipeline.git_ops.run_git", _git_stub(command, outcome)),
        caplog.at_level(logging.ERROR, logger="squadron.pipeline.git_ops"),
        pytest.raises(GitStateUnknownError),
    ):
        merged_slice_branches([_ENTRY], "main", cwd="/unused")
    errors = [r for r in caplog.records if r.levelno == logging.ERROR]
    assert len(errors) == 1
    assert command in errors[0].getMessage()


def test_missing_target_raises_from_rev_list(temp_git_repo: Path) -> None:
    with pytest.raises(GitStateUnknownError, match="rev-list"):
        merged_slice_branches([_ENTRY], "no-such-target", cwd=str(temp_git_repo))
