"""A pid + process-start-time lock, and the check for whether its owner is still alive.

Shared by the scratch PR-review worktree (slice 382) and the producer-replay sandbox
(slice 177). A lock records the owning *process's start time*, not when the lock was
written, so a pid the OS has since recycled for an unrelated process never reads as the
owner. A missing, unreadable, malformed or incomplete lock reads as an orphan, never as
an exception: a parse error here must not fail every later run.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import cast

from squadron.core.process_runner import ProcessRunner

_logger = logging.getLogger(__name__)

#: Wall-clock bound on a ``ps`` query.
PS_QUERY_TIMEOUT_SECONDS = 30

#: ``ps`` truncates to whole seconds, so a lock written and re-read within the same second
#: is identical; any real cross-process comparison stays well outside this window unless
#: the pid was actually recycled.
_START_TIME_TOLERANCE_SECONDS = 2.0


class ProcessIdentityUnresolvable(Exception):
    """This process's own start time could not be determined via ``ps``.

    Raised before anything is created: a lock written without a resolvable start time
    could never be matched on readback, silently defeating the orphan sweep.
    """

    def __init__(self, pid: int) -> None:
        super().__init__(f"could not determine this process's own start time via 'ps' (pid {pid})")
        self.pid = pid


@dataclass(frozen=True)
class ProcessLock:
    """The owner recorded in a lock file: a pid and that process's start time."""

    pid: int
    started_at: float

    def to_json(self) -> str:
        return json.dumps({"pid": self.pid, "started_at": self.started_at})


def process_start_time(runner: ProcessRunner, pid: int) -> float | None:
    """The start time of *pid*, as epoch seconds, or ``None`` if it is not running.

    No stdlib call returns this portably (Linux has ``/proc``, macOS does not), so this
    shells out to ``ps -o lstart=``, whose format both BSD (macOS) and GNU (Linux) ``ps``
    accept. Parsed as local time, matching the host clock the same ``ps`` reads: a lock is
    only ever read back by a process on the machine that wrote it.
    """
    result = runner.run(
        ["ps", "-o", "lstart=", "-p", str(pid)],
        cwd=None,
        timeout=PS_QUERY_TIMEOUT_SECONDS,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return datetime.strptime(result.stdout.strip(), "%a %b %d %H:%M:%S %Y").timestamp()
    except ValueError:
        # A ps output format this parser does not recognize is not evidence the process
        # is dead — treat as "cannot determine", the same as a missing pid, so a live
        # owner is never mistaken for an orphan due to a parsing gap.
        _logger.warning("Could not parse 'ps' start-time output for pid %d: %r", pid, result.stdout)
        return None


def current_process_lock(runner: ProcessRunner) -> ProcessLock:
    """A lock owned by the current process.

    Unlike :func:`process_start_time` on another pid, where "gone" is an expected outcome,
    the current process is always running: failing to resolve its own start time means
    ``ps`` itself is broken or missing, an environment fault surfaced loudly rather than by
    writing a lock that can never match on readback.

    Raises:
        ProcessIdentityUnresolvable: ``ps`` cannot report this process's start time.
    """
    pid = os.getpid()
    start_time = process_start_time(runner, pid)
    if start_time is None:
        raise ProcessIdentityUnresolvable(pid)
    return ProcessLock(pid=pid, started_at=start_time)


def read_lock(lock_path: Path) -> ProcessLock | None:
    """Parse *lock_path*, or ``None`` for any of: missing, unreadable, malformed, incomplete.

    Each of these is one treat-as-orphan path; this function never raises.
    """
    try:
        raw = lock_path.read_text()
    except OSError:
        return None
    try:
        parsed: object = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    data = cast(dict[str, object], parsed)
    if "pid" not in data or "started_at" not in data:
        return None
    raw_pid = data["pid"]
    raw_started_at = data["started_at"]
    if not isinstance(raw_pid, int) or not isinstance(raw_started_at, (int, float)):
        return None
    return ProcessLock(pid=raw_pid, started_at=float(raw_started_at))


def is_orphan(runner: ProcessRunner, lock: ProcessLock | None) -> bool:
    """Whether the owner recorded by *lock* is gone, or a different process entirely."""
    if lock is None:
        return True
    live_start = process_start_time(runner, lock.pid)
    if live_start is None:
        return True
    return abs(live_start - lock.started_at) > _START_TIME_TOLERANCE_SECONDS
