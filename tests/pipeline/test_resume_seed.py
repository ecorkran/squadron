"""A resumed run sees the results of the steps it skips (#219)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import squadron.pipeline.steps.loop  # noqa: F401 — register the loop step type
from squadron.pipeline.executor import ExecutionStatus, StepResult, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager

LOOP = "loop-1"


def _review(verdict: str) -> ActionResult:
    return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)


def _definition() -> PipelineDefinition:
    revise = {"dispatch": {"name": "revise", "model": "m", "feedback": "review"}}
    return PipelineDefinition(
        name="resume-seed",
        description="",
        params={},
        steps=[
            StepConfig(step_type="phase", name="tasks", config={}),
            StepConfig(
                step_type="loop",
                name=LOOP,
                config={"max": 3, "until": "review.pass", "on_exhaust": "fail", "steps": [revise]},
            ),
        ],
    )


def _record(state: StateManager, run_id: str, step: StepResult) -> None:
    state.observer(run_id).step_completed(step)


async def _resume(
    tmp_path: Path, state: StateManager, run_id: str, iteration: int
) -> list[dict[str, ActionResult]]:
    """Resume at the loop; return the prior_outputs each revise dispatch saw."""
    seen: list[dict[str, ActionResult]] = []

    async def revise(ctx: ActionContext) -> ActionResult:
        seen.append(dict(ctx.prior_outputs))
        return ActionResult(success=True, action_type="dispatch", outputs={})

    action = MagicMock()
    action.execute = AsyncMock(side_effect=revise)
    result = await execute_pipeline(
        _definition(),
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd=str(tmp_path),
        run_id=run_id,
        start_from=LOOP,
        start_from_iteration=iteration,
        runs_dir=tmp_path,
        _action_registry={"dispatch": action},
    )
    assert result.status != ExecutionStatus.PAUSED
    return seen


async def test_loop_resumed_at_round_one_sees_the_review_from_a_skipped_step(
    tmp_path: Path,
) -> None:
    state = StateManager(runs_dir=tmp_path)
    run_id = state.init_run("resume-seed", {})
    _record(
        state,
        run_id,
        StepResult("tasks", "phase", ExecutionStatus.COMPLETED, [_review("CONCERNS")]),
    )

    seen = await _resume(tmp_path, state, run_id, iteration=1)

    assert [r.verdict for r in seen[0].values() if r.action_type == "review"] == ["CONCERNS"]


async def test_loop_resumed_above_round_one_also_sees_its_own_earlier_rounds(
    tmp_path: Path,
) -> None:
    state = StateManager(runs_dir=tmp_path)
    run_id = state.init_run("resume-seed", {})
    _record(
        state,
        run_id,
        StepResult("tasks", "phase", ExecutionStatus.COMPLETED, [_review("CONCERNS")]),
    )
    loop = StepResult(
        LOOP,
        "loop",
        ExecutionStatus.PAUSED,
        [_review("FAIL")],
        iteration=2,
        prior_rounds=[[_review("CONCERNS")]],
    )
    _record(state, run_id, loop)

    seen = await _resume(tmp_path, state, run_id, iteration=2)

    verdicts = [r.verdict for r in seen[0].values() if r.action_type == "review"]
    assert verdicts[-1] == "FAIL"


async def test_loop_resumed_at_round_one_ignores_its_own_stale_results(tmp_path: Path) -> None:
    state = StateManager(runs_dir=tmp_path)
    run_id = state.init_run("resume-seed", {})
    _record(
        state,
        run_id,
        StepResult("tasks", "phase", ExecutionStatus.COMPLETED, [_review("CONCERNS")]),
    )
    _record(state, run_id, StepResult(LOOP, "loop", ExecutionStatus.PAUSED, [_review("PASS")]))

    seen = await _resume(tmp_path, state, run_id, iteration=1)

    assert [r.verdict for r in seen[0].values() if r.action_type == "review"] == ["CONCERNS"]
