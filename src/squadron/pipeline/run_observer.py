"""The executor's progress interface (slice 174 D12).

``execute_pipeline`` reports step starts, ``each`` item starts and step
completions to one ``RunObserver``. ``RunStateRecorder`` is the
``StateManager``-backed implementation that records them in the run's state
file. This is internal bookkeeping, separate from the user-bindable events
dispatcher (``squadron.events``): it always runs, is synchronous, and never
fails a step through a progress write.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from squadron.pipeline.executor import StepResult
    from squadron.pipeline.state import ActiveItem, StateManager


class RunObserver(Protocol):
    """Receives the executor's progress notifications, on the event-loop thread."""

    def step_started(self, step_name: str) -> None: ...

    def item_started(self, step_name: str, item: ActiveItem) -> None: ...

    def step_completed(self, result: StepResult) -> None: ...


class RunStateRecorder:
    """Records a run's progress in its state file through ``StateManager``."""

    def __init__(self, state_mgr: StateManager, run_id: str) -> None:
        self._state_mgr = state_mgr
        self._run_id = run_id

    def step_started(self, step_name: str) -> None:
        """No-op until progress fields exist."""

    def item_started(self, step_name: str, item: ActiveItem) -> None:
        """No-op until progress fields exist."""

    def step_completed(self, result: StepResult) -> None:
        """Append the step and record any compact summaries it produced."""
        self._state_mgr.record_step_completed(self._run_id, result)
