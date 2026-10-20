"""Non-interactive resume of a run paused at an exhausted loop: a pinned contract.

External launchers base their "retry" resolution on this: resuming a loop that
exhausted with ``on_exhaust: checkpoint`` reruns the final round once, then
continues past the loop or pauses again. It never accepts or skips the loop.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
from squadron.pipeline.executor import ExecutionStatus, PipelineResult, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager
from squadron.pipeline.steps import register_step_type

_MAX_ROUNDS = 2


def _review(verdict: str) -> ActionResult:
    return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)


def _after() -> ActionResult:
    return ActionResult(success=True, action_type="after", outputs={})


def _mock_action(results: list[ActionResult]) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=results)
    return action


def _register(name: str, action_type: str) -> None:
    step_type = MagicMock()
    step_type.expand.return_value = [(action_type, {})]
    register_step_type(name, step_type)


def _pipeline() -> PipelineDefinition:
    _register("_rc_review", "review")
    _register("_rc_after", "after")
    loop = StepConfig(
        step_type="loop",
        name="revise",
        config={
            "max": _MAX_ROUNDS,
            "until": "review.pass",
            "on_exhaust": "checkpoint",
            "skip_if_met": True,
            "steps": [{"_rc_review": {}}],
        },
    )
    after = StepConfig(step_type="_rc_after", name="after-loop", config={})
    return PipelineDefinition(name="contract", description="t", params={}, steps=[loop, after])


async def _execute(
    sm: StateManager,
    run_id: str,
    definition: PipelineDefinition,
    registry: dict[str, object],
    *,
    resume: bool,
) -> PipelineResult:
    start_from = sm.first_unfinished_step(run_id, definition) if resume else None
    start_iteration = sm.resume_iteration_for(run_id, start_from) if start_from else 0
    result = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        start_from=start_from,
        start_from_iteration=start_iteration,
        observer=sm.observer(run_id),
        _action_registry=registry,
    )
    sm.finalize(run_id, result)
    return result


async def _paused_run(tmp_path: Path) -> tuple[StateManager, str, PipelineDefinition]:
    sm = StateManager(runs_dir=tmp_path / "runs")
    run_id = sm.init_run("contract", {})
    definition = _pipeline()
    registry: dict[str, object] = {
        "review": _mock_action([_review("FAIL")] * _MAX_ROUNDS),
        "after": _mock_action([]),
    }
    first = await _execute(sm, run_id, definition, registry, resume=False)
    assert first.status == ExecutionStatus.PAUSED
    assert first.paused_at == "revise"
    return sm, run_id, definition


@pytest.mark.asyncio
async def test_resume_reruns_the_final_round_once_and_continues_on_pass(tmp_path: Path) -> None:
    sm, run_id, definition = await _paused_run(tmp_path)
    review = _mock_action([_review("PASS")])
    after = _mock_action([_after()])

    result = await _execute(sm, run_id, definition, {"review": review, "after": after}, resume=True)

    assert review.execute.call_count == 1
    assert after.execute.call_count == 1
    assert result.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_resume_pauses_again_when_the_final_round_still_fails(tmp_path: Path) -> None:
    sm, run_id, definition = await _paused_run(tmp_path)
    review = _mock_action([_review("FAIL")])
    after = _mock_action([])

    result = await _execute(sm, run_id, definition, {"review": review, "after": after}, resume=True)

    assert review.execute.call_count == 1  # one paid retry, never an accept or a skip
    assert after.execute.call_count == 0
    assert result.status == ExecutionStatus.PAUSED
    assert result.paused_at == "revise"
