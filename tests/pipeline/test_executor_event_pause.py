"""A POST_ACTION event can pause a run via ``awaits_human`` (slice 947 D7)."""

from __future__ import annotations

from itertools import count
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.events.dispatcher import EventOutcome, OutcomeErrorKind
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps import register_step_type

_names = count()


def _event_failure(*, awaits_human: bool) -> EventOutcome:
    return EventOutcome(
        action_name="demo.gate",
        result=ActionResult(
            success=False,
            action_type="demo.gate",
            outputs={},
            error="needs the Project Manager",
            awaits_human=awaits_human,
        ),
        error_kind=OutcomeErrorKind.NONE,
    )


async def _run_two_steps(outcome: EventOutcome) -> tuple[PipelineResult, MagicMock]:
    kind = f"_event_pause_{next(_names)}"
    step_type = MagicMock()
    step_type.expand.return_value = [("dispatch", {})]
    register_step_type(kind, step_type)
    action = MagicMock()
    action.execute = AsyncMock(
        side_effect=lambda ctx: ActionResult(success=True, action_type="dispatch", outputs={})
    )
    definition = PipelineDefinition(
        name="pause",
        description="test",
        params={},
        steps=[StepConfig(step_type=kind, name=f"step-{i}", config={}) for i in range(2)],
    )
    with patch("squadron.pipeline.executor.run_event", AsyncMock(return_value=[outcome])):
        result = await execute_pipeline(
            definition,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"dispatch": action},
        )
    return result, action


@pytest.mark.asyncio
async def test_failing_event_with_awaits_human_pauses_the_step_and_the_run() -> None:
    result, action = await _run_two_steps(_event_failure(awaits_human=True))

    assert result.status is ExecutionStatus.PAUSED
    assert result.paused_at == "step-0"
    assert result.step_results[0].status is ExecutionStatus.PAUSED
    assert action.execute.await_count == 1  # step-1 never ran


@pytest.mark.asyncio
async def test_failing_event_without_the_flag_still_fails_the_run() -> None:
    result, action = await _run_two_steps(_event_failure(awaits_human=False))

    assert result.status is ExecutionStatus.FAILED
    assert result.step_results[0].action_results[0].error == "needs the Project Manager"
    assert action.execute.await_count == 1
