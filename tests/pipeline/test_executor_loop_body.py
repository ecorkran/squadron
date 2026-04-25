"""Integration tests for _execute_loop_body — multi-step loop: step type."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.steps import register_step_type

# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _action_result(
    success: bool,
    action_type: str,
    verdict: str | None = None,
    paused: bool = False,
) -> ActionResult:
    outputs: dict[str, object] = {}
    if paused:
        outputs["checkpoint"] = "paused"
    return ActionResult(
        success=success,
        action_type=action_type,
        outputs=outputs,
        verdict=verdict,
    )


def _mock_action(results: list[ActionResult]) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(side_effect=results)
    return action


def _mock_step_type(
    action_pairs: list[tuple[str, dict[str, object]]],
) -> MagicMock:
    st = MagicMock()
    st.expand.return_value = action_pairs
    return st


def _loop_step(name: str, config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="loop", name=name, config=config)


def _pipeline(steps: list[StepConfig]) -> PipelineDefinition:
    return PipelineDefinition(
        name="test-loop-body",
        description="test",
        params={},
        steps=steps,
    )


# ---------------------------------------------------------------------------
# Task 10 — passes after iteration 1
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_body_completes_on_iteration_1() -> None:
    """Body containing one inner step; PASS review exits on iteration 1."""
    pass_result = _action_result(True, "review", verdict="PASS")
    review_action = _mock_action([pass_result])

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_inner_t10", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "my-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [{"_lb_inner_t10": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    step_result = result.step_results[0]
    assert step_result.iteration == 1
    assert any(ar.verdict == "PASS" for ar in step_result.action_results)


# ---------------------------------------------------------------------------
# Task 11 — retries to PASS on iteration N
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_body_retries_to_pass_on_iteration_3() -> None:
    """Body retries until PASS on iteration 3; earlier iterations return CONCERNS."""
    results = [
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="PASS"),
    ]
    review_action = _mock_action(results)

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_inner_t11", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "my-loop",
                {
                    "max": 5,
                    "until": "review.pass",
                    "steps": [{"_lb_inner_t11": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    step_result = result.step_results[0]
    assert step_result.iteration == 3
    # Final iteration's results only
    assert any(ar.verdict == "PASS" for ar in step_result.action_results)


# ---------------------------------------------------------------------------
# Task 12 — exhaustion modes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_loop_body_exhaustion_fail() -> None:
    """Never reaches PASS with max=2 and on_exhaust=fail → FAILED."""
    results = [
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="CONCERNS"),
    ]
    review_action = _mock_action(results)

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_inner_t12_fail", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "exhaust-fail",
                {
                    "max": 2,
                    "until": "review.pass",
                    "on_exhaust": "fail",
                    "steps": [{"_lb_inner_t12_fail": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action},
    )

    assert result.status == ExecutionStatus.FAILED
    assert result.step_results[0].iteration == 2


@pytest.mark.asyncio
async def test_loop_body_exhaustion_checkpoint() -> None:
    """Never reaches PASS with max=2 and on_exhaust=checkpoint → PAUSED."""
    results = [
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="CONCERNS"),
    ]
    review_action = _mock_action(results)

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_inner_t12_ckpt", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "exhaust-ckpt",
                {
                    "max": 2,
                    "until": "review.pass",
                    "on_exhaust": "checkpoint",
                    "steps": [{"_lb_inner_t12_ckpt": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action},
    )

    assert result.status == ExecutionStatus.PAUSED
    assert result.step_results[0].iteration == 2


@pytest.mark.asyncio
async def test_loop_body_exhaustion_skip() -> None:
    """Never reaches PASS with max=2 and on_exhaust=skip → SKIPPED."""
    results = [
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="CONCERNS"),
    ]
    review_action = _mock_action(results)

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_inner_t12_skip", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "exhaust-skip",
                {
                    "max": 2,
                    "until": "review.pass",
                    "on_exhaust": "skip",
                    "steps": [{"_lb_inner_t12_skip": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action},
    )

    # SKIPPED steps do not abort the pipeline — pipeline result is COMPLETED
    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[0].status == ExecutionStatus.SKIPPED
    assert result.step_results[0].iteration == 2


# ---------------------------------------------------------------------------
# Task 13 — inner failure is transient
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inner_failure_is_transient_second_step_still_runs() -> None:
    """First inner step fails on iteration 1; second still runs and produces PASS.

    FAILED status on an inner step does not abort the iteration — execution
    continues to the next inner step so the until condition can be evaluated.
    """
    fail_result = _action_result(False, "dispatch")
    pass_result = _action_result(True, "review", verdict="PASS")

    dispatch_action = _mock_action([fail_result])
    review_action = _mock_action([pass_result])

    failing_inner = _mock_step_type([("dispatch", {})])
    passing_inner = _mock_step_type([("review", {})])

    register_step_type("_lb_failing_inner_t13", failing_inner)
    register_step_type("_lb_passing_inner_t13", passing_inner)

    pipeline = _pipeline(
        [
            _loop_step(
                "transient-fail",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_failing_inner_t13": {}},
                        {"_lb_passing_inner_t13": {}},
                    ],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={
            "dispatch": dispatch_action,
            "review": review_action,
        },
    )

    assert result.status == ExecutionStatus.COMPLETED
    step_result = result.step_results[0]
    assert step_result.iteration == 1
    # Both inner action results captured
    assert len(step_result.action_results) == 2


# ---------------------------------------------------------------------------
# Task 14 — checkpoint pause short-circuits the loop
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_checkpoint_pause_stops_loop_body() -> None:
    """An inner step that pauses on a checkpoint stops the loop immediately."""
    ckpt_result = _action_result(True, "checkpoint", paused=True)
    ckpt_action = _mock_action([ckpt_result])

    inner_st = _mock_step_type([("checkpoint", {})])
    register_step_type("_lb_ckpt_inner_t14", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "pause-loop",
                {
                    "max": 5,
                    "steps": [{"_lb_ckpt_inner_t14": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"checkpoint": ckpt_action},
    )

    assert result.status == ExecutionStatus.PAUSED
    step_result = result.step_results[0]
    assert step_result.iteration == 1
