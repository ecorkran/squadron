"""What a dispatch's tool telemetry says happened (slice 945 D3).

A pure function over the telemetry providers already stamp. It decides whether a step
that reports ``completed`` did any work; the caller logs and builds the result.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import cast

from squadron.providers.base import (
    FAILED_TOOL_CALLS_KEY,
    FIRST_TOOL_ERROR_KEY,
    TOOL_CALLS_MADE_KEY,
    TOOLS_GIVEN_KEY,
)
from squadron.tools.builtin import WRITE_TOOL_NAMES


@dataclass(frozen=True)
class ToolOutcome:
    """``fail_reason`` set means the step failed; ``warnings`` are logged either way."""

    fail_reason: str | None = None
    warnings: list[str] = field(default_factory=list[str])


def _count(telemetry: Mapping[str, object], key: str) -> int:
    value = telemetry.get(key, 0)
    if not isinstance(value, int):
        raise TypeError(f"tool telemetry {key!r} must be an int, got {value!r}")
    return value


def assess_tool_outcome(requires_writes: bool, telemetry: Mapping[str, object]) -> ToolOutcome:
    """Apply the D3 rows, in order, to one dispatch's telemetry.

    Telemetry without ``tool_calls_made`` means no tools were given, so there is nothing
    to assess: a bare dispatch is never failed on prose (design, Excluded).
    """
    if TOOL_CALLS_MADE_KEY not in telemetry:
        return ToolOutcome()
    made = _count(telemetry, TOOL_CALLS_MADE_KEY)
    failed = _count(telemetry, FAILED_TOOL_CALLS_KEY)

    if requires_writes and made == 0:
        return ToolOutcome(fail_reason="step must write files but made no tool calls")

    given = telemetry.get(TOOLS_GIVEN_KEY)
    given_names = [str(name) for name in cast(list[object], given)] if isinstance(given, list) else []
    has_write_tool = not WRITE_TOOL_NAMES.isdisjoint(given_names)
    if made > 0 and failed == made and (requires_writes or has_write_tool):
        reason = "every tool call failed"
        first_error = telemetry.get(FIRST_TOOL_ERROR_KEY)
        if first_error:
            reason = f"{reason}; first error: {first_error}"
        return ToolOutcome(fail_reason=reason)

    if failed > 0:
        return ToolOutcome(warnings=[f"{failed} of {made} tool calls failed"])
    return ToolOutcome()
