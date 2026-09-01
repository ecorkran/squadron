"""Tool-use observability: the -v log line and RunState persistence (slice 265, task 25).

Before this slice nothing recorded that a step was given tools or called them — a review that
ran tool-less was indistinguishable in every artifact from one that read a dozen files
(issue #68). SC8 requires the zero-calls case to read distinctly from the no-tools case, and
SC9 requires the same facts to survive into persisted run state.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, _log_action_result, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager

# ---------------------------------------------------------------------------
# The -v log line
# ---------------------------------------------------------------------------


def _capture_log(result: ActionResult, caplog: pytest.LogCaptureFixture) -> str:
    with caplog.at_level(logging.INFO, logger="squadron.pipeline.executor"):
        _log_action_result("dispatch", result)
    return "\n".join(record.getMessage() for record in caplog.records)


def _result(**metadata: object) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="dispatch",
        outputs={},
        metadata={"model": "gpt-4o-mini", **metadata},
    )


def test_log_line_shows_tools_given_and_calls_made(caplog: pytest.LogCaptureFixture) -> None:
    line = _capture_log(_result(tools_given=["read_file", "grep"], tool_calls_made=3), caplog)

    assert "tools=2/3 calls" in line


def test_log_line_shows_zero_calls_distinctly_from_no_tools(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """SC8's literal distinguishing case."""
    offered = _capture_log(
        _result(tools_given=["read_file", "list_files", "grep"], tool_calls_made=0), caplog
    )
    caplog.clear()
    never = _capture_log(_result(), caplog)

    assert "tools=3/0 calls" in offered
    assert "tools=" not in never
    assert offered != never


def test_log_line_omits_tools_segment_when_no_tools_configured(
    caplog: pytest.LogCaptureFixture,
) -> None:
    line = _capture_log(_result(), caplog)

    assert "tools=" not in line
    # The existing segments are untouched.
    assert "model=gpt-4o-mini" in line


def test_log_line_defaults_missing_call_count_to_zero(
    caplog: pytest.LogCaptureFixture,
) -> None:
    line = _capture_log(_result(tools_given=["read_file"]), caplog)

    assert "tools=1/0 calls" in line


# ---------------------------------------------------------------------------
# RunState.action_results persistence (SC9)
# ---------------------------------------------------------------------------


def _tool_bearing_action() -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(
        return_value=ActionResult(
            success=True,
            action_type="dispatch",
            outputs={"response": "done"},
            metadata={
                "model": "gpt-4o-mini",
                "tools_given": ["read_file", "grep"],
                "tool_calls_made": 4,
            },
        )
    )
    return action


@pytest.mark.asyncio
async def test_run_state_action_results_contains_tools_metadata(tmp_path: Path) -> None:
    """Design D8's "no schema change needed" claim, asserted rather than assumed.

    Runs a one-step pipeline end to end through the executor with a mocked action (no model
    call), then reads the persisted run JSON off disk.
    """
    definition = PipelineDefinition(
        name="telemetry-test",
        description="single dispatch step",
        params={},
        steps=[
            StepConfig(
                step_type="dispatch",
                name="write-something",
                config={"prompt": "do the thing", "allowed_tools": ["read_file", "grep"]},
            )
        ],
    )
    # The executor records into a run the caller initialized, so create it first — the same
    # sequence `sq run` follows.
    state_manager = StateManager(runs_dir=tmp_path)
    run_id = state_manager.init_run("telemetry-test", {}, run_id="run-telemetry-1")

    result = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(tmp_path),
        run_id=run_id,
        runs_dir=tmp_path,
        # The same persistence seam `sq run` wires up, so this asserts the real path.
        on_step_complete=state_manager.make_step_callback(run_id),
        _action_registry={"dispatch": _tool_bearing_action()},
    )

    assert result.status == ExecutionStatus.COMPLETED

    persisted = json.loads((tmp_path / f"{run_id}.json").read_text(encoding="utf-8"))
    action_results = persisted["completed_steps"][0]["action_results"]
    assert len(action_results) == 1
    metadata = action_results[0]["metadata"]
    assert metadata["tools_given"] == ["read_file", "grep"]
    assert metadata["tool_calls_made"] == 4
