"""Tests for the D3 tool-outcome rules (slice 945)."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions.dispatch_outcome import ToolOutcome, assess_tool_outcome
from squadron.providers.base import (
    FAILED_TOOL_CALLS_KEY,
    FIRST_TOOL_ERROR_KEY,
    TOOL_CALLS_MADE_KEY,
    TOOLS_GIVEN_KEY,
)


def _telemetry(
    given: list[str], made: int, failed: int, first_error: str | None = None
) -> dict[str, object]:
    telemetry: dict[str, object] = {
        TOOLS_GIVEN_KEY: given,
        TOOL_CALLS_MADE_KEY: made,
        FAILED_TOOL_CALLS_KEY: failed,
    }
    if first_error is not None:
        telemetry[FIRST_TOOL_ERROR_KEY] = first_error
    return telemetry


def test_row1_write_required_with_no_calls_fails() -> None:
    outcome = assess_tool_outcome(True, _telemetry(["write_file"], made=0, failed=0))

    assert outcome.fail_reason == "step must write files but made no tool calls"


def test_row2_all_calls_failed_fails_and_includes_first_error() -> None:
    outcome = assess_tool_outcome(
        True, _telemetry(["write_file"], made=2, failed=2, first_error="path escapes jail")
    )

    assert outcome.fail_reason is not None
    assert outcome.fail_reason.startswith("every tool call failed")
    assert "path escapes jail" in outcome.fail_reason


def test_row2_without_first_error_has_no_error_detail() -> None:
    outcome = assess_tool_outcome(False, _telemetry(["bash"], made=1, failed=1))

    assert outcome.fail_reason == "every tool call failed"


def test_row2_not_triggered_for_read_only_step_with_only_read_tools_warns() -> None:
    outcome = assess_tool_outcome(False, _telemetry(["read_file", "grep"], made=2, failed=2))

    assert outcome.fail_reason is None
    assert outcome.warnings == ["2 of 2 tool calls failed"]


def test_row3_partial_failure_warns_without_failing() -> None:
    outcome = assess_tool_outcome(True, _telemetry(["write_file"], made=3, failed=1))

    assert outcome.fail_reason is None
    assert outcome.warnings == ["1 of 3 tool calls failed"]


@pytest.mark.parametrize("requires_writes", [True, False])
def test_no_telemetry_is_an_empty_outcome(requires_writes: bool) -> None:
    assert assess_tool_outcome(requires_writes, {}) == ToolOutcome()


def test_clean_run_is_an_empty_outcome() -> None:
    assert assess_tool_outcome(True, _telemetry(["write_file"], made=2, failed=0)) == ToolOutcome()


def test_non_integer_count_raises() -> None:
    with pytest.raises(TypeError):
        assess_tool_outcome(True, {TOOL_CALLS_MADE_KEY: "2"})
