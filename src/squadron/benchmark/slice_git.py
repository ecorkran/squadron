"""One git query in the user's checkout for slice-case building (slice 426 D6).

A failed, timed-out or missing ``git`` is the harness's problem, never the slice's: it
raises ``SliceHarnessError`` after an ERROR log, and the caller records ``harness_error``
instead of a rejection that would blame the slice.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)

_logger = logging.getLogger(__name__)

_GIT_FAILURES = (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError)


class SliceHarnessError(Exception):
    """A git query (or a sandbox, or a suite run) failed; the message says which and why."""


def git_result(
    runner: ProcessRunner, repo: Path, args: Sequence[str], timeout_s: float
) -> ProcessResult:
    """The finished ``git <args>`` in *repo*, whatever its exit code.

    A git that is missing, times out or has no such directory is logged at ERROR and raised
    as ``SliceHarnessError``; a non-zero exit is the caller's to judge.
    """
    argv = ["git", *args]
    try:
        return runner.run(argv, cwd=str(repo), timeout=timeout_s)
    except _GIT_FAILURES as exc:
        command = " ".join(argv)
        _logger.exception("%s failed in %s", command, repo)
        raise SliceHarnessError(f"{command}: {exc}") from exc


def run_git(runner: ProcessRunner, repo: Path, args: Sequence[str], timeout_s: float) -> str:
    """The stdout of ``git <args>`` in *repo*; a failure is logged at ERROR and raised."""
    command = " ".join(["git", *args])
    result = git_result(runner, repo, args, timeout_s)
    if result.returncode != 0:
        message = f"{command} exited {result.returncode} in {repo}: {result.stderr.strip()}"
        _logger.error(message)
        raise SliceHarnessError(message)
    return result.stdout
