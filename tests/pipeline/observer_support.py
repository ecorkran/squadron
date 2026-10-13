"""A recording ``RunObserver`` for executor tests (slice 174 D12)."""

from __future__ import annotations

from dataclasses import dataclass, field

from squadron.pipeline.executor import StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.state import ActiveItem


@dataclass
class RecordingObserver:
    """Records every notification in order; ``completed`` holds the step results."""

    events: list[tuple[str, str, ActiveItem | None]] = field(default_factory=list)
    completed: list[StepResult] = field(default_factory=list)
    rounds: list[tuple[str, int, list[ActionResult]]] = field(default_factory=list)

    def step_started(self, step_name: str) -> None:
        self.events.append(("step_started", step_name, None))

    def item_started(self, step_name: str, item: ActiveItem) -> None:
        self.events.append(("item_started", step_name, item))

    def step_completed(self, result: StepResult) -> None:
        self.events.append(("step_completed", result.step_name, None))
        self.completed.append(result)

    def round_completed(self, step_name: str, iteration: int, results: list[ActionResult]) -> None:
        self.events.append(("round_completed", step_name, None))
        self.rounds.append((step_name, iteration, results))
