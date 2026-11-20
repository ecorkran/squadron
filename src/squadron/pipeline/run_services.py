"""The run-scoped services one pipeline invocation shares across every step."""

from __future__ import annotations

from dataclasses import dataclass

from squadron.pipeline.run_spend import RunSpend
from squadron.pipeline.usage_capture import UsageCapture
from squadron.recipes.recipe_record import RecipeRecordSink


@dataclass(frozen=True)
class RunServices:
    """One per invocation, shared by every step including fan_out branches.

    ``usage_capture`` builds usage records (slice 175); ``spend`` tallies them against the
    cost cap (slice 947); ``recipe_sink`` takes recipe review records (slice 434 D8).
    """

    usage_capture: UsageCapture
    spend: RunSpend
    recipe_sink: RecipeRecordSink


def capture_of(services: RunServices | None) -> UsageCapture | None:
    """The run's usage capture, or ``None`` for a context with no run (standalone tests)."""
    return services.usage_capture if services is not None else None


def sink_of(services: RunServices | None) -> RecipeRecordSink | None:
    """The run's recipe record sink, or ``None`` for a context with no run."""
    return services.recipe_sink if services is not None else None
