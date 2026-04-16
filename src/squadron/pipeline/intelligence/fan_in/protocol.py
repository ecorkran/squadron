"""FanInReducer protocol — merges fan-out branch results into a single ActionResult."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from squadron.pipeline.executor import StepResult
    from squadron.pipeline.models import ActionResult


@runtime_checkable
class FanInReducer(Protocol):
    """Merges branch results into a single ActionResult."""

    def reduce(
        self,
        branch_results: list[StepResult],
        config: dict[str, object],
    ) -> ActionResult:
        """Reduce a list of branch StepResults into one ActionResult."""
        ...
