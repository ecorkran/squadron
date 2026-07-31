"""Integration tests for _execute_loop_body — multi-step loop: step type."""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
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


# ---------------------------------------------------------------------------
# Part A (#42) — findings feedback between iterations
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_iteration_2_dispatch_sees_iteration_1_review_in_prior_outputs() -> None:
    """dispatch on iteration 2 receives iteration 1's review ActionResult.

    Body is dispatch -> review, review FAILs on iteration 1 (with a finding)
    and PASSes on iteration 2. Captures the ActionContext passed to each
    dispatch call and asserts the second call's prior_outputs contains the
    iteration-1 review result — proving the loop feeds results forward
    rather than replaying the same prior_outputs every iteration (which the
    existing retries-to-pass-on-iteration-3 test does not, by itself, prove:
    it only shows the loop runs the right number of times).
    """
    captured_contexts: list[ActionContext] = []

    async def _dispatch_side_effect(ctx: ActionContext) -> ActionResult:
        captured_contexts.append(ctx)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(side_effect=_dispatch_side_effect)

    review_results = [
        ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="FAIL",
            findings=[{"severity": "HIGH", "summary": "iteration-1 finding", "location": "x.py"}],
        ),
        ActionResult(success=True, action_type="review", outputs={}, verdict="PASS"),
    ]
    review_action = _mock_action(review_results)

    dispatch_inner = _mock_step_type([("dispatch", {})])
    review_inner = _mock_step_type([("review", {})])
    register_step_type("_lb_dispatch_inner_t6", dispatch_inner)
    register_step_type("_lb_review_inner_t6", review_inner)

    pipeline = _pipeline(
        [
            _loop_step(
                "findings-feedback-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_dispatch_inner_t6": {}},
                        {"_lb_review_inner_t6": {}},
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
        _action_registry={"dispatch": dispatch_action, "review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[0].iteration == 2
    assert len(captured_contexts) == 2

    iteration_1_ctx, iteration_2_ctx = captured_contexts

    # Iteration 1's dispatch has nothing to feed back yet.
    assert not any(r.action_type == "review" for r in iteration_1_ctx.prior_outputs.values())

    # Iteration 2's dispatch sees iteration 1's review result.
    review_results_seen = [
        r for r in iteration_2_ctx.prior_outputs.values() if r.action_type == "review"
    ]
    assert len(review_results_seen) == 1
    assert review_results_seen[0].verdict == "FAIL"
    seen_finding = cast(dict[str, object], review_results_seen[0].findings[0])
    assert seen_finding["summary"] == "iteration-1 finding"


@pytest.mark.asyncio
async def test_iteration_2_dispatch_prompt_contains_iteration_1_finding() -> None:
    """The resolved prompt for iteration 2's dispatch contains the iteration-1
    finding's summary text — closing the gap between "prior_outputs
    contains the result" (previous test) and "the consumer actually turns
    it into the right prompt" (this test), per the slice design's Success
    Criteria and Verification Walkthrough.
    """
    captured_prompts: list[str | None] = []

    async def _dispatch_side_effect(ctx: ActionContext) -> ActionResult:
        # Testing the exact consumer method the slice design names —
        # accessing it directly, not through the full dispatch execute()
        # path (which requires spawning an agent).
        prompt = DispatchAction._resolve_prompt_from_prior_review(ctx)  # pyright: ignore[reportPrivateUsage]
        captured_prompts.append(prompt)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(side_effect=_dispatch_side_effect)

    review_results = [
        ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="FAIL",
            findings=[{"severity": "HIGH", "summary": "fix the frobnicator", "location": "x.py"}],
        ),
        ActionResult(success=True, action_type="review", outputs={}, verdict="PASS"),
    ]
    review_action = _mock_action(review_results)

    dispatch_inner = _mock_step_type([("dispatch", {})])
    review_inner = _mock_step_type([("review", {})])
    register_step_type("_lb_dispatch_inner_t7", dispatch_inner)
    register_step_type("_lb_review_inner_t7", review_inner)

    pipeline = _pipeline(
        [
            _loop_step(
                "findings-feedback-prompt-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_dispatch_inner_t7": {}},
                        {"_lb_review_inner_t7": {}},
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
        _action_registry={"dispatch": dispatch_action, "review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(captured_prompts) == 2

    iteration_1_prompt, iteration_2_prompt = captured_prompts
    assert iteration_1_prompt is None
    assert iteration_2_prompt is not None
    assert "fix the frobnicator" in iteration_2_prompt
