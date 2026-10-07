"""Waiting on a run until it leaves ``running`` (slice 199 D13).

Backs ``sq runs wait``. Reads run state only. Each poll that sees ``running``
assesses liveness (slice 174 D8): an orphaned run ends the wait; a stale one is
only suspect, so it is logged once and the wait goes on to ``--timeout``.
"""

from __future__ import annotations

import logging
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.run_liveness import (
    LivenessAssessment,
    ProcessCheck,
    RunLiveness,
    assess_liveness,
    process_alive,
)
from squadron.pipeline.state import RUNNING_STATUS, STATE_READ_ERRORS, RunState, StateManager

_logger = logging.getLogger(__name__)

WAIT_POLL_INTERVAL_SECONDS = 2.0


class WaitOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    TIMED_OUT = "timed_out"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    UNKNOWN_STATUS = "unknown_status"
    ORPHANED = "orphaned"


# The single definition of `sq runs wait` exit codes. 2 is left to Typer usage errors.
WAIT_EXIT_CODES: dict[WaitOutcome, int] = {
    WaitOutcome.COMPLETED: 0,
    WaitOutcome.FAILED: 1,
    WaitOutcome.PAUSED: 3,
    WaitOutcome.TIMED_OUT: 4,
    WaitOutcome.NOT_FOUND: 5,
    WaitOutcome.UNREADABLE: 6,
    WaitOutcome.UNKNOWN_STATUS: 7,
    WaitOutcome.ORPHANED: 8,
}

_TERMINAL_OUTCOMES: dict[str, WaitOutcome] = {
    ExecutionStatus.COMPLETED.value: WaitOutcome.COMPLETED,
    ExecutionStatus.FAILED.value: WaitOutcome.FAILED,
    ExecutionStatus.PAUSED.value: WaitOutcome.PAUSED,
}


@dataclass(frozen=True)
class WaitResult:
    outcome: WaitOutcome
    state: RunState | None  # the last state read; None when it could not be read


def wait_for_run(
    state_manager: StateManager,
    run_id: str,
    *,
    timeout: float | None,
    poll_interval: float = WAIT_POLL_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
    hostname: str | None = None,
    process_alive: ProcessCheck = process_alive,
) -> WaitResult:
    """Re-read *run_id*'s state every *poll_interval* until it leaves ``running``.

    ``timeout=None`` waits indefinitely; a caller that needs a bound passes one.
    An orphaned run ends the wait; *hostname* defaults to this host's name.
    """
    host = socket.gethostname() if hostname is None else hostname
    watch = _LivenessWatch(run_id)
    deadline = None if timeout is None else clock() + timeout
    while True:
        outcome, state = _poll(state_manager, run_id)
        if outcome is None and state is not None:
            assessment = assess_liveness(state, now=now(), hostname=host, process_alive=process_alive)
            outcome = watch.observe(assessment)
        if outcome is None and deadline is not None and clock() >= deadline:
            outcome = WaitOutcome.TIMED_OUT
        if outcome is not None:
            if outcome is not WaitOutcome.COMPLETED:
                _logger.warning("wait on run %s ended: %s", run_id, outcome)
            return WaitResult(outcome, state)
        # The last sleep before a deadline is cut short so the timeout is not overshot.
        sleep(poll_interval if deadline is None else min(poll_interval, deadline - clock()))


def _poll(state_manager: StateManager, run_id: str) -> tuple[WaitOutcome | None, RunState | None]:
    """The run's outcome (``None`` while it is still running) and the state read."""
    try:
        state = state_manager.load(run_id)
    except FileNotFoundError:
        return WaitOutcome.NOT_FOUND, None
    except STATE_READ_ERRORS as exc:
        # Files are replaced atomically, so a failed read is a real fault, not a race.
        _logger.warning("run %s state unreadable: %s", run_id, exc)
        return WaitOutcome.UNREADABLE, None
    if state.status == RUNNING_STATUS:
        return None, state
    return _TERMINAL_OUTCOMES.get(state.status, WaitOutcome.UNKNOWN_STATUS), state


@dataclass
class _LivenessWatch:
    """Applies D8's policy across polls: orphaned ends the wait; stale is logged once."""

    run_id: str
    stale: bool = field(default=False)

    def observe(self, assessment: LivenessAssessment | None) -> WaitOutcome | None:
        if assessment is None:
            return None
        match assessment.liveness:
            case RunLiveness.ORPHANED:
                return WaitOutcome.ORPHANED
            case RunLiveness.STALE if not self.stale:
                self.stale = True
                _logger.warning(
                    "run %s heartbeat overdue by %s; still waiting",
                    self.run_id,
                    assessment.heartbeat_age,
                )
            case RunLiveness.LIVE if self.stale:
                self.stale = False
                _logger.info("run %s heartbeat resumed", self.run_id)
            case _:
                pass  # unowned, live, or still stale: keep waiting as before
        return None


def orphaned_message(run_id: str, state: RunState | None) -> str:
    """The stderr line for an orphaned wait: names the process that is gone."""
    pid = "unknown" if state is None or state.owner is None else str(state.owner.pid)
    return f"sq runs wait: run {run_id} orphaned (process {pid} gone)"
