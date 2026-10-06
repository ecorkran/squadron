"""Tests for the git_ops state and target readers (slice 196 D5, D6)."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pipeline.git_ops import (
    GitEnvironmentError,
    GitStateUnknownError,
    NoDesignFileError,
    branch_behind_count,
    branch_work_count,
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
