"""The heartbeat that keeps an SDK run's liveness current (slice 174 D6, D13).

``RunHeartbeat`` wraps ``execute_pipeline`` for every SDK run. On enter it
claims a resumed run for this process; while open, an asyncio task rewrites
``heartbeat_at`` every interval. Writes stay on the event-loop thread (D5).
"""

from __future__ import annotations

import asyncio
import logging
import math
from types import TracebackType

from squadron.config.keys import RUN_HEARTBEAT_INTERVAL_KEY
from squadron.config.manager import get_positive_int_config
from squadron.pipeline.state import RunOwner, StateManager

_logger = logging.getLogger(__name__)


def heartbeat_interval_s(cwd: str = ".") -> int:
    """The configured ``pipeline.run_heartbeat_interval_s``; raises if not positive."""
    return get_positive_int_config(RUN_HEARTBEAT_INTERVAL_KEY, cwd=cwd)


class RunHeartbeat:
    """Async context manager: claim (resume only) and heartbeat for one run.

    *claim* is ``True`` only on the resume and item-resume paths; a new run's
    owner was already written by ``init_run(owner=...)`` (D13). The first
    heartbeat follows one *interval* after enter.
    """

    def __init__(self, state_mgr: StateManager, run_id: str, interval: float, *, claim: bool) -> None:
        self._state_mgr = state_mgr
        self._run_id = run_id
        self._interval = interval
        self._claim = claim
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> RunHeartbeat:
        if self._claim:
            # A failed claim is fatal: the run must not start without an owner.
            owner = RunOwner.current(max(1, math.ceil(self._interval)))
            self._state_mgr.claim(self._run_id, owner)
        self._task = asyncio.create_task(self._beat(), name=f"heartbeat:{self._run_id}")
        self._task.add_done_callback(self._report_crash)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._task is None:
            return
        self._task.cancel()
        # wait() neither raises the task's outcome (a crash was logged by _report_crash and
        # must not mask the run's own exit) nor swallows a cancellation of this task.
        await asyncio.wait([self._task])

    async def _beat(self) -> None:
        while True:
            await asyncio.sleep(self._interval)
            # Expected I/O failures are logged inside heartbeat() and do not raise (D6).
            self._state_mgr.heartbeat(self._run_id)

    def _report_crash(self, task: asyncio.Task[None]) -> None:
        if task.cancelled():
            return
        exc = task.exception()
        if exc is not None:
            _logger.error(
                "run %s: heartbeat stopped by an unexpected error; the run will turn stale",
                self._run_id,
                exc_info=exc,
            )
