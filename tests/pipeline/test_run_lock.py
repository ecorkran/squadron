"""The per-checkout run lock (slice 197 D11; D12 lock rows)."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.run_lock import RunLockError, RunLockHeldError, project_run_lock
from tests.conftest import run_test_git


def _errors(caplog: pytest.LogCaptureFixture, text: str) -> bool:
    return any(r.levelno == logging.ERROR and text in r.getMessage() for r in caplog.records)


def test_the_lock_lives_in_the_git_dir(temp_git_repo: Path) -> None:
    with project_run_lock(str(temp_git_repo)) as path:
        assert path == (temp_git_repo / ".git" / "squadron-run.flock").resolve()


def test_a_second_holder_is_refused_with_the_message(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)
    with project_run_lock(str(temp_git_repo)):
        with pytest.raises(RunLockHeldError, match="another squadron run holds the project lock"):
            with project_run_lock(str(temp_git_repo)):
                pass

    assert _errors(caplog, "one mutating run per project at a time")
    with project_run_lock(str(temp_git_repo)):  # released when the holder exits
        pass


def test_a_killed_holder_releases_the_lock(temp_git_repo: Path) -> None:
    holder = subprocess.Popen(
        [
            sys.executable,
            "-c",
            "import sys, time\n"
            "from squadron.pipeline.run_lock import project_run_lock\n"
            "with project_run_lock(sys.argv[1]):\n"
            "    print('held', flush=True)\n"
            "    time.sleep(60)\n",
            str(temp_git_repo),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert holder.stdout is not None
        assert holder.stdout.readline().strip() == "held"
        with pytest.raises(RunLockHeldError):
            with project_run_lock(str(temp_git_repo)):
                pass
    finally:
        holder.kill()
        holder.wait()

    deadline = time.monotonic() + 5
    while True:
        try:
            with project_run_lock(str(temp_git_repo)):
                break
        except RunLockHeldError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.05)


def test_separate_worktrees_lock_independently(temp_git_repo: Path, tmp_path: Path) -> None:
    linked = tmp_path / "linked"
    run_test_git(temp_git_repo, "worktree", "add", "-q", "-b", "other", str(linked))

    with project_run_lock(str(temp_git_repo)), project_run_lock(str(linked)):
        pass


@pytest.mark.parametrize("timeout", [True, False])
def test_a_failed_git_dir_read_is_an_environment_error(
    tmp_path: Path, timeout: bool, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.ERROR)
    with patch("squadron.pipeline.run_lock.run_git", return_value=None) if timeout else nullcontext():
        # Not a repo when git answers; no answer at all when it times out.
        with pytest.raises(GitEnvironmentError, match="cannot find the git dir"):
            with project_run_lock(str(tmp_path)):
                pass

    assert _errors(caplog, "cannot find the git dir for the project run lock")


def test_an_open_failure_names_the_path(temp_git_repo: Path, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.ERROR)
    with patch.object(Path, "open", side_effect=PermissionError(13, "Permission denied")):
        with pytest.raises(RunLockError, match="squadron-run.flock: cannot open: Permission denied"):
            with project_run_lock(str(temp_git_repo)):
                pass

    assert _errors(caplog, "squadron-run.flock: cannot open")
