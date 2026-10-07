"""Waiting on a run until it leaves ``running`` (slice 199 D13).

Backs ``sq runs wait``. Reads run state only; a crashed run stays ``running`` forever
and cannot be told from a live one (#190), so callers bound the wait with a timeout.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum

from pydantic import ValidationError

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.state import RUNNING_STATUS, RunState, SchemaVersionError, StateManager

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


# The single definition of `sq runs wait` exit codes. 2 is left to Typer usage errors.
WAIT_EXIT_CODES: dict[WaitOutcome, int] = {
    WaitOutcome.COMPLETED: 0,
    WaitOutcome.FAILED: 1,
    WaitOutcome.PAUSED: 3,
    WaitOutcome.TIMED_OUT: 4,
    WaitOutcome.NOT_FOUND: 5,
    WaitOutcome.UNREADABLE: 6,
    WaitOutcome.UNKNOWN_STATUS: 7,
}

_TERMINAL_OUTCOMES: dict[str, WaitOutcome] = {
    ExecutionStatus.COMPLETED.value: WaitOutcome.COMPLETED,
    ExecutionStatus.FAILED.value: WaitOutcome.FAILED,
    ExecutionStatus.PAUSED.value: WaitOutcome.PAUSED,
}

# _load_raw's raisable set for a present file (as in StateManager.list_runs). A state
# file is replaced atomically, so a failed read is a real fault, not a race.
_STATE_READ_ERRORS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    SchemaVersionError,
    ValidationError,
)


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
) -> WaitResult:
    """Re-read *run_id*'s state every *poll_interval* until it leaves ``running``.

    ``timeout=None`` waits indefinitely; a caller that needs a bound passes one.
    """
    deadline = None if timeout is None else clock() + timeout
    while True:
        outcome, state = _poll(state_manager, run_id)
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
    except _STATE_READ_ERRORS as exc:
        _logger.warning("run %s state unreadable: %s", run_id, exc)
        return WaitOutcome.UNREADABLE, None
    if state.status == RUNNING_STATUS:
        return None, state
    return _TERMINAL_OUTCOMES.get(state.status, WaitOutcome.UNKNOWN_STATUS), state
