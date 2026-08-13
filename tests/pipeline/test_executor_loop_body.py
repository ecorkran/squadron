"""Integration tests for _execute_loop_body — multi-step loop: step type."""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.state import StateManager
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
async def test_two_inner_steps_same_action_type_do_not_collide_within_iteration() -> None:
    """Two different inner steps producing the same action_type in one
    iteration must not overwrite each other in running_prior.

    Body is dispatch -> dispatch -> review. Both dispatch inner steps
    produce an action_type="dispatch" result with action_index 0 (each
    inner step's own action list restarts its index at 0), so a key scheme
    that ignores which inner step produced the result would let the second
    dispatch's result silently overwrite the first's before review even
    runs. Both inner steps resolve to the same "dispatch" entry in
    _action_registry (lookup is by action_type only), so a single mock
    returns each result in call order — first inner step's call gets
    first_dispatch_result, second inner step's call gets
    second_dispatch_result. Asserts review's ActionContext.prior_outputs
    contains both, distinguishable by their outputs.
    """
    captured_review_ctx: list[ActionContext] = []

    first_dispatch_result = ActionResult(
        success=True, action_type="dispatch", outputs={"response": "first"}
    )
    second_dispatch_result = ActionResult(
        success=True, action_type="dispatch", outputs={"response": "second"}
    )
    dispatch_action = _mock_action([first_dispatch_result, second_dispatch_result])

    async def _review_side_effect(ctx: ActionContext) -> ActionResult:
        captured_review_ctx.append(ctx)
        return ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")

    review_action = MagicMock()
    review_action.execute = AsyncMock(side_effect=_review_side_effect)

    first_dispatch_inner = _mock_step_type([("dispatch", {})])
    second_dispatch_inner = _mock_step_type([("dispatch", {})])
    review_inner = _mock_step_type([("review", {})])
    register_step_type("_lb_first_dispatch_t_collision", first_dispatch_inner)
    register_step_type("_lb_second_dispatch_t_collision", second_dispatch_inner)
    register_step_type("_lb_review_t_collision", review_inner)

    pipeline = _pipeline(
        [
            _loop_step(
                "no-collision-loop",
                {
                    "max": 1,
                    "steps": [
                        {"_lb_first_dispatch_t_collision": {}},
                        {"_lb_second_dispatch_t_collision": {}},
                        {"_lb_review_t_collision": {}},
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
    assert len(captured_review_ctx) == 1

    dispatch_results_seen = [
        r for r in captured_review_ctx[0].prior_outputs.values() if r.action_type == "dispatch"
    ]
    responses_seen = {r.outputs.get("response") for r in dispatch_results_seen}
    assert responses_seen == {"first", "second"}, (
        f"expected both dispatch results to survive without collision, got: {responses_seen}"
    )


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


@pytest.mark.asyncio
async def test_action_context_carries_loop_iteration_number() -> None:
    """ActionContext.iteration inside a loop body matches the 1-based round;
    the same step type executed outside a loop receives the 0 sentinel.
    """
    captured_contexts: list[ActionContext] = []

    async def _capture(ctx: ActionContext) -> ActionResult:
        captured_contexts.append(ctx)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(side_effect=_capture)

    review_results = [
        ActionResult(success=True, action_type="review", outputs={}, verdict="FAIL"),
        ActionResult(success=True, action_type="review", outputs={}, verdict="PASS"),
    ]
    review_action = _mock_action(review_results)

    dispatch_inner = _mock_step_type([("dispatch", {})])
    review_inner = _mock_step_type([("review", {})])
    register_step_type("_lb_dispatch_inner_ctx", dispatch_inner)
    register_step_type("_lb_review_inner_ctx", review_inner)

    pipeline = _pipeline(
        [
            _loop_step(
                "ctx-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_dispatch_inner_ctx": {}},
                        {"_lb_review_inner_ctx": {}},
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
    assert [ctx.iteration for ctx in captured_contexts] == [1, 2]

    # The same step type executed outside a loop receives the 0 sentinel.
    outside_contexts: list[ActionContext] = []

    async def _capture_outside(ctx: ActionContext) -> ActionResult:
        outside_contexts.append(ctx)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    outside_dispatch_action = MagicMock()
    outside_dispatch_action.execute = AsyncMock(side_effect=_capture_outside)
    outside_dispatch_inner = _mock_step_type([("dispatch", {})])
    register_step_type("_top_level_dispatch_ctx", outside_dispatch_inner)

    outside_pipeline = _pipeline(
        [StepConfig(step_type="_top_level_dispatch_ctx", name="plain-step", config={})]
    )

    outside_result = await execute_pipeline(
        outside_pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"dispatch": outside_dispatch_action},
    )

    assert outside_result.status == ExecutionStatus.COMPLETED
    assert [ctx.iteration for ctx in outside_contexts] == [0]


# ---------------------------------------------------------------------------
# commit_each_iteration (slice 911 Part A2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_commit_each_iteration_invokes_commit_per_round() -> None:
    """commit_each_iteration: true appends one commit action per iteration,
    each carrying that iteration's number, for a dispatch-bodied loop."""
    review_results = [
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="CONCERNS"),
        _action_result(True, "review", verdict="PASS"),
    ]
    review_action = _mock_action(review_results)

    captured_contexts: list[ActionContext] = []

    async def _commit_side_effect(ctx: ActionContext) -> ActionResult:
        captured_contexts.append(ctx)
        return ActionResult(success=True, action_type="commit", outputs={"committed": True})

    commit_action = MagicMock()
    commit_action.execute = AsyncMock(side_effect=_commit_side_effect)

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_commit_each_t15", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "commit-loop",
                {
                    "max": 5,
                    "until": "review.pass",
                    "commit_each_iteration": True,
                    "steps": [{"_lb_commit_each_t15": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action, "commit": commit_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[0].iteration == 3
    assert commit_action.execute.call_count == 3
    assert [ctx.iteration for ctx in captured_contexts] == [1, 2, 3]
    # The final iteration's commit result is present in action_results.
    assert any(ar.action_type == "commit" for ar in result.step_results[0].action_results)


# ---------------------------------------------------------------------------
# Slice 305 Part A — loop-body evidence plumbing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_inner_step_verdict_lands_in_step_outputs_every_iteration() -> None:
    """An inner review step named `fresh-review` publishes its verdict-bearing
    result into step_outputs under that name, on every iteration.

    step_outputs is a gate's only mechanism for resolving review_from /
    judge_from, and the top-level walk never sees inner steps — without this
    a gate inside a loop resolves nothing and emits UNKNOWN every round.
    """
    seen_step_outputs: list[dict[str, ActionResult]] = []

    review_results = [
        ActionResult(success=True, action_type="review", outputs={}, verdict="CONCERNS"),
        ActionResult(success=True, action_type="review", outputs={}, verdict="PASS"),
    ]
    review_action = _mock_action(review_results)

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_step_outputs.append(dict(ctx.step_outputs))
        return ActionResult(success=True, action_type="emit", outputs={})

    capture_action = MagicMock()
    capture_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_lb_so_review", _mock_step_type([("review", {})]))
    register_step_type("_lb_so_capture", _mock_step_type([("emit", {})]))

    pipeline = _pipeline(
        [
            _loop_step(
                "step-outputs-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_so_review": {"name": "fresh-review"}},
                        {"_lb_so_capture": {"name": "observer"}},
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
        _action_registry={"review": review_action, "emit": capture_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(seen_step_outputs) == 2
    assert [so["fresh-review"].verdict for so in seen_step_outputs] == ["CONCERNS", "PASS"]


@pytest.mark.asyncio
async def test_inner_step_without_verdict_creates_no_step_outputs_entry() -> None:
    """An inner step whose results carry no verdict is not published into
    step_outputs — the entry is absent, not present-and-empty."""
    seen_step_outputs: list[dict[str, ActionResult]] = []

    dispatch_action = _mock_action([ActionResult(success=True, action_type="dispatch", outputs={})])

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_step_outputs.append(dict(ctx.step_outputs))
        return ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")

    review_action = MagicMock()
    review_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_lb_so_noverdict_dispatch", _mock_step_type([("dispatch", {})]))
    register_step_type("_lb_so_noverdict_review", _mock_step_type([("review", {})]))

    pipeline = _pipeline(
        [
            _loop_step(
                "no-verdict-loop",
                {
                    "max": 2,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_so_noverdict_dispatch": {"name": "implement"}},
                        {"_lb_so_noverdict_review": {"name": "fresh-review"}},
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
    assert len(seen_step_outputs) == 1
    assert "implement" not in seen_step_outputs[0]


@pytest.mark.asyncio
async def test_inner_step_output_does_not_survive_into_the_next_iteration() -> None:
    """Round N's view of an inner step is round N's own, or absent.

    If round N's review emits no verdict, round N-1's result must not still be
    standing under that name: a gate reading it as this round's evidence would
    compare the prior round against itself with no way to tell.
    """
    seen_step_outputs: list[dict[str, ActionResult]] = []

    review_results = [
        ActionResult(success=True, action_type="review", outputs={}, verdict="CONCERNS"),
        ActionResult(success=True, action_type="review", outputs={}),  # no verdict
    ]
    review_action = _mock_action(review_results)

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_step_outputs.append(dict(ctx.step_outputs))
        return ActionResult(success=True, action_type="emit", outputs={})

    capture_action = MagicMock()
    capture_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_lb_stale_review", _mock_step_type([("review", {})]))
    register_step_type("_lb_stale_capture", _mock_step_type([("emit", {})]))

    pipeline = _pipeline(
        [
            _loop_step(
                "stale-loop",
                {
                    "max": 2,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_stale_review": {"name": "fresh-review"}},
                        {"_lb_stale_capture": {"name": "observer"}},
                    ],
                },
            )
        ]
    )

    await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action, "emit": capture_action},
    )

    assert len(seen_step_outputs) == 2
    assert seen_step_outputs[0]["fresh-review"].verdict == "CONCERNS"
    assert "fresh-review" not in seen_step_outputs[1]


@pytest.mark.asyncio
async def test_inner_step_names_do_not_leak_past_the_loop() -> None:
    """A step after the loop cannot resolve a body step's name.

    The loader rejects such a reference at load time; leaving the entry in the
    run-wide dict would make it resolvable at runtime to the final iteration's
    value, which no configuration ever asked for.
    """
    seen_step_outputs: list[dict[str, ActionResult]] = []

    review_action = _mock_action(
        [ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")]
    )

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_step_outputs.append(dict(ctx.step_outputs))
        return ActionResult(success=True, action_type="emit", outputs={})

    capture_action = MagicMock()
    capture_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_lb_leak_review", _mock_step_type([("review", {})]))
    register_step_type("_lb_leak_capture", _mock_step_type([("emit", {})]))

    pipeline = _pipeline(
        [
            _loop_step(
                "leak-loop",
                {
                    "max": 2,
                    "until": "review.pass",
                    "steps": [{"_lb_leak_review": {"name": "fresh-review"}}],
                },
            ),
            StepConfig(step_type="_lb_leak_capture", name="after", config={}),
        ]
    )

    await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action, "emit": capture_action},
    )

    assert len(seen_step_outputs) == 1
    assert "fresh-review" not in seen_step_outputs[0]


@pytest.mark.asyncio
async def test_prior_iteration_step_outputs_carries_the_previous_round() -> None:
    """Iteration 1 sees an empty prior_iteration_step_outputs; iteration 2 sees
    iteration 1's entries with iteration 1's findings — not its own round's.

    The gate sits late in the body, where running_prior's positional keys have
    already been overwritten by the current round, so this is the only view of
    the prior round available to it.
    """
    seen_prior: list[dict[str, ActionResult]] = []

    review_results = [
        ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="CONCERNS",
            findings=[{"id": "F001", "severity": "CONCERN", "summary": "round-1 finding"}],
        ),
        ActionResult(
            success=True,
            action_type="review",
            outputs={},
            verdict="PASS",
            findings=[{"id": "F002", "severity": "NOTE", "summary": "round-2 finding"}],
        ),
    ]
    review_action = _mock_action(review_results)

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_prior.append(dict(ctx.prior_iteration_step_outputs))
        return ActionResult(success=True, action_type="gate", outputs={})

    gate_action = MagicMock()
    gate_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_lb_prior_review", _mock_step_type([("review", {})]))
    register_step_type("_lb_prior_gate", _mock_step_type([("gate", {})]))

    pipeline = _pipeline(
        [
            _loop_step(
                "prior-iteration-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [
                        {"_lb_prior_review": {"name": "fresh-review"}},
                        {"_lb_prior_gate": {"name": "settled"}},
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
        _action_registry={"review": review_action, "gate": gate_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(seen_prior) == 2

    iteration_1_prior, iteration_2_prior = seen_prior
    assert iteration_1_prior == {}

    round_1_review = iteration_2_prior["fresh-review"]
    assert round_1_review.verdict == "CONCERNS"
    round_1_finding = cast(dict[str, object], round_1_review.findings[0])
    assert round_1_finding["summary"] == "round-1 finding"


@pytest.mark.asyncio
async def test_step_outside_a_loop_sees_empty_prior_iteration_step_outputs() -> None:
    """The empty dict is the no-prior-iteration sentinel outside loops too."""
    seen_prior: list[dict[str, ActionResult]] = []

    async def _capture(ctx: ActionContext) -> ActionResult:
        seen_prior.append(dict(ctx.prior_iteration_step_outputs))
        return ActionResult(success=True, action_type="gate", outputs={})

    gate_action = MagicMock()
    gate_action.execute = AsyncMock(side_effect=_capture)

    register_step_type("_top_level_gate_prior", _mock_step_type([("gate", {})]))

    pipeline = _pipeline([StepConfig(step_type="_top_level_gate_prior", name="settled", config={})])

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"gate": gate_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert seen_prior == [{}]


@pytest.mark.asyncio
async def test_commit_each_iteration_absent_never_invokes_commit() -> None:
    """Absent commit_each_iteration — existing loops are unaffected; commit
    is never invoked even when registered in the action registry."""
    review_action = _mock_action([_action_result(True, "review", verdict="PASS")])
    commit_action = MagicMock()
    commit_action.execute = AsyncMock(
        return_value=ActionResult(success=True, action_type="commit", outputs={})
    )

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_no_commit_t15", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "no-commit-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [{"_lb_no_commit_t15": {}}],
                },
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        _action_registry={"review": review_action, "commit": commit_action},
    )

    assert result.status == ExecutionStatus.COMPLETED


# ---------------------------------------------------------------------------
# Slice 915 Part C (#48) — WARNING when a loop abandons rounds on pause
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_step_body_pause_emits_warning_with_rounds_not_run(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Multi-step body pauses at round 1 of max: 3 -> one WARNING naming the
    step, the paused round (1), and 2 rounds not run."""
    ckpt_result = _action_result(True, "checkpoint", paused=True)
    ckpt_action = _mock_action([ckpt_result])

    inner_st = _mock_step_type([("checkpoint", {})])
    register_step_type("_lb_warn_multi_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "pause-loop",
                {
                    "max": 3,
                    "steps": [{"_lb_warn_multi_t915": {}}],
                },
            )
        ]
    )

    with caplog.at_level("WARNING", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"checkpoint": ckpt_action},
        )

    assert result.status == ExecutionStatus.PAUSED
    abandon_warnings = [r.getMessage() for r in caplog.records if "paused at round" in r.getMessage()]
    assert len(abandon_warnings) == 1
    message = abandon_warnings[0]
    assert "pause-loop" in message
    assert "1" in message  # paused round
    assert "2" in message  # rounds not run (max 3 - round 1)


@pytest.mark.asyncio
async def test_single_step_body_pause_emits_same_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The single-step loop path (_execute_loop_step, driven by an inline
    `loop:` key rather than step_type: loop) emits the identical WARNING."""
    ckpt_result = _action_result(True, "checkpoint", paused=True)
    ckpt_action = _mock_action([ckpt_result])

    inner_st = _mock_step_type([("checkpoint", {})])
    register_step_type("_ls_warn_t915", inner_st)

    pipeline = _pipeline(
        [
            StepConfig(
                step_type="_ls_warn_t915",
                name="single-pause-loop",
                config={"loop": {"max": 4}},
            )
        ]
    )

    with caplog.at_level("WARNING", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"checkpoint": ckpt_action},
        )

    assert result.status == ExecutionStatus.PAUSED
    abandon_warnings = [r.getMessage() for r in caplog.records if "paused at round" in r.getMessage()]
    assert len(abandon_warnings) == 1
    message = abandon_warnings[0]
    assert "single-pause-loop" in message
    assert "1" in message  # paused round
    assert "3" in message  # rounds not run (max 4 - round 1)


@pytest.mark.asyncio
async def test_converging_loop_emits_no_pause_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A loop that converges normally (no inner pause) emits no abandonment
    WARNING at all."""
    pass_result = _action_result(True, "review", verdict="PASS")
    review_action = _mock_action([pass_result])

    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_no_warn_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "converging-loop",
                {
                    "max": 3,
                    "until": "review.pass",
                    "steps": [{"_lb_no_warn_t915": {}}],
                },
            )
        ]
    )

    with caplog.at_level("WARNING", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": review_action},
        )

    assert result.status == ExecutionStatus.COMPLETED
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings == []


# ---------------------------------------------------------------------------
# Slice 915 Part B (#48) — start_iteration range, both loop paths (Task 3.2)
# ---------------------------------------------------------------------------


def _never_pass_review(n: int) -> MagicMock:
    """A review action that returns CONCERNS every call — never converges,
    so the loop always runs to `max` and every round is observable."""
    return _mock_action([_action_result(True, "review", verdict="CONCERNS") for _ in range(n)])


@pytest.mark.asyncio
async def test_multi_step_body_start_iteration_2_runs_rounds_2_and_3() -> None:
    review_action = _never_pass_review(2)
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_si2_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "resume-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_si2_t915": {}}]},
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        start_from="resume-loop",
        start_from_iteration=2,
        _action_registry={"review": review_action},
    )

    assert review_action.execute.call_count == 2
    assert result.step_results[0].iteration == 3


@pytest.mark.asyncio
async def test_multi_step_body_start_iteration_1_unchanged() -> None:
    """Default start_from_iteration=0 (no resume round) behaves exactly as
    a plain run: round 1 executes, same as pre-Part-B behavior."""
    pass_result = _action_result(True, "review", verdict="PASS")
    review_action = _mock_action([pass_result])
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_si1_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "unresumed-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_si1_t915": {}}]},
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
    assert result.step_results[0].iteration == 1


@pytest.mark.asyncio
async def test_multi_step_body_start_iteration_equals_max_runs_one_round() -> None:
    review_action = _never_pass_review(1)
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_si_eq_max_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "last-round-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_si_eq_max_t915": {}}]},
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        start_from="last-round-loop",
        start_from_iteration=3,
        _action_registry={"review": review_action},
    )

    assert review_action.execute.call_count == 1
    assert result.step_results[0].iteration == 3


@pytest.mark.asyncio
async def test_multi_step_body_start_iteration_above_max_fails_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A resume request above the loop's max: (only reachable from malformed
    resume state) fails with a WARNING rather than silently reporting
    COMPLETED for zero rounds run (design Success Criteria)."""
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_si_above_max_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "over-max-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_si_above_max_t915": {}}]},
            )
        ]
    )

    with caplog.at_level("WARNING", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="over-max-loop",
            start_from_iteration=5,
            _action_registry={"review": _mock_action([])},
        )

    assert result.status == ExecutionStatus.FAILED
    degenerate_warnings = [r.getMessage() for r in caplog.records if "above max" in r.getMessage()]
    assert len(degenerate_warnings) == 1
    message = degenerate_warnings[0]
    assert "over-max-loop" in message
    assert "5" in message
    assert "3" in message


@pytest.mark.asyncio
async def test_single_step_loop_start_iteration_2_runs_rounds_2_and_3() -> None:
    """The single-step loop path (_execute_loop_step) honors start_iteration
    identically to the multi-step body path."""
    review_action = _never_pass_review(2)
    step_type = _mock_step_type([("review", {})])
    register_step_type("_ls_si2_t915", step_type)

    pipeline = _pipeline(
        [
            StepConfig(
                step_type="_ls_si2_t915",
                name="single-resume-loop",
                config={"loop": {"max": 3, "until": "review.pass"}},
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        start_from="single-resume-loop",
        start_from_iteration=2,
        _action_registry={"review": review_action},
    )

    assert review_action.execute.call_count == 2
    assert result.step_results[0].iteration == 3


@pytest.mark.asyncio
async def test_single_step_loop_start_iteration_above_max_fails_loudly(
    caplog: pytest.LogCaptureFixture,
) -> None:
    step_type = _mock_step_type([("review", {})])
    register_step_type("_ls_si_above_max_t915", step_type)

    pipeline = _pipeline(
        [
            StepConfig(
                step_type="_ls_si_above_max_t915",
                name="single-over-max-loop",
                config={"loop": {"max": 2, "until": "review.pass"}},
            )
        ]
    )

    with caplog.at_level("WARNING", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="single-over-max-loop",
            start_from_iteration=4,
            _action_registry={"review": _mock_action([])},
        )

    assert result.status == ExecutionStatus.FAILED
    degenerate_warnings = [r.getMessage() for r in caplog.records if "above max" in r.getMessage()]
    assert len(degenerate_warnings) == 1


# ---------------------------------------------------------------------------
# Slice 915 Part B (#48) — execute_pipeline iteration threading (Task 3.4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_start_from_loop_step_emits_reentry_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """start_from a loop step with start_from_iteration=2 -> rounds 2+ run
    and an INFO naming the step and round is emitted (design D4 signal 2)."""
    review_action = _never_pass_review(2)
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_reentry_info_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "reentry-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_reentry_info_t915": {}}]},
            )
        ]
    )

    with caplog.at_level("INFO", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="reentry-loop",
            start_from_iteration=2,
            _action_registry={"review": review_action},
        )

    assert result.step_results[0].iteration == 3
    reentry_info = [r.getMessage() for r in caplog.records if "re-entering at round" in r.getMessage()]
    assert len(reentry_info) == 1
    assert "reentry-loop" in reentry_info[0]
    assert "2" in reentry_info[0]


@pytest.mark.asyncio
async def test_start_from_non_loop_step_ignores_iteration_with_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """start_from a non-loop step with a non-zero start_from_iteration behaves
    identically to start_from_iteration=0, and logs a DEBUG "ignored" line
    (design D3: a non-loop step has no rounds to re-enter)."""
    action = _mock_action([_action_result(True, "cf-op")])
    step_type = _mock_step_type([("cf-op", {})])
    register_step_type("_plain_step_t915", step_type)

    pipeline = _pipeline(
        [
            StepConfig(step_type="_plain_step_t915", name="plain-step", config={}),
        ]
    )

    with caplog.at_level("DEBUG", logger="squadron.pipeline.executor"):
        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="plain-step",
            start_from_iteration=2,
            _action_registry={"cf-op": action},
        )

    assert result.status == ExecutionStatus.COMPLETED
    ignored_debug = [r.getMessage() for r in caplog.records if "ignored" in r.getMessage()]
    assert len(ignored_debug) == 1
    assert "plain-step" in ignored_debug[0]


@pytest.mark.asyncio
async def test_start_from_iteration_zero_on_loop_clamps_to_round_1() -> None:
    pass_result = _action_result(True, "review", verdict="PASS")
    review_action = _mock_action([pass_result])
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_clamp0_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "clamp-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_clamp0_t915": {}}]},
            )
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        start_from="clamp-loop",
        start_from_iteration=0,
        _action_registry={"review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.step_results[0].iteration == 1


@pytest.mark.asyncio
async def test_start_from_skips_earlier_steps_with_iteration_set() -> None:
    """Steps before start_from are still skipped, unchanged, even when
    start_from_iteration is set."""
    earlier_action = _mock_action([_action_result(True, "cf-op")])
    earlier_step_type = _mock_step_type([("cf-op", {})])
    register_step_type("_earlier_step_t915", earlier_step_type)

    pass_result = _action_result(True, "review", verdict="PASS")
    review_action = _mock_action([pass_result])
    inner_st = _mock_step_type([("review", {})])
    register_step_type("_lb_skip_earlier_t915", inner_st)

    pipeline = _pipeline(
        [
            StepConfig(step_type="_earlier_step_t915", name="earlier-step", config={}),
            _loop_step(
                "target-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_lb_skip_earlier_t915": {}}]},
            ),
        ]
    )

    result = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        start_from="target-loop",
        start_from_iteration=1,
        _action_registry={"cf-op": earlier_action, "review": review_action},
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.step_results) == 1
    assert result.step_results[0].step_name == "target-loop"
    earlier_action.execute.assert_not_called()


# ---------------------------------------------------------------------------
# Slice 915 Part B (#48) — end-to-end CLI resume contract (Task 3.6)
# ---------------------------------------------------------------------------


def _e2e_loop_pipeline(max_rounds: int) -> PipelineDefinition:
    """A [dispatch, review] loop body with checkpoint: on-concerns, matching
    the design's Verification Walkthrough fixture shape."""
    return _pipeline(
        [
            _loop_step(
                "review-loop",
                {
                    "max": max_rounds,
                    "until": "review.pass",
                    "steps": [{"_e2e_inner_t915": {}}],
                },
            )
        ]
    )


def _e2e_registry(review_results: list[ActionResult]) -> dict[str, object]:
    dispatch_action = _mock_action([_action_result(True, "dispatch")] * len(review_results))
    review_action = _mock_action(review_results)
    checkpoint_action = MagicMock()

    async def _checkpoint_execute(ctx: ActionContext) -> ActionResult:
        # on-concerns: pause whenever the loop's review verdict was CONCERNS.
        last_review = next(
            (r for r in reversed(list(ctx.prior_outputs.values())) if r.verdict is not None),
            None,
        )
        if last_review is not None and last_review.verdict == "CONCERNS":
            return _action_result(True, "checkpoint", paused=True)
        return ActionResult(success=True, action_type="checkpoint", outputs={})

    checkpoint_action.execute = _checkpoint_execute
    return {"dispatch": dispatch_action, "review": review_action, "checkpoint": checkpoint_action}


@pytest.mark.asyncio
async def test_e2e_pause_and_resume_reenters_loop_at_recorded_round(tmp_path: Path) -> None:
    """Design Verification Walkthrough steps 1-5, driven the way run.py's
    resume paths actually drive it: first_unfinished_step + resume_iteration_for
    feeding execute_pipeline(start_from=..., start_from_iteration=...)."""
    inner_st = _mock_step_type([("dispatch", {}), ("review", {}), ("checkpoint", {})])
    register_step_type("_e2e_inner_t915", inner_st)

    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run("e2e-loop-pipe", {"slice": "915"})
    definition = _e2e_loop_pipeline(max_rounds=3)

    # Round 1: review returns CONCERNS -> checkpoint pauses.
    result1 = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        runs_dir=tmp_path,
        on_step_complete=mgr.make_step_callback(run_id),
        _action_registry=_e2e_registry([_action_result(True, "review", verdict="CONCERNS")]),
    )
    assert result1.status == ExecutionStatus.PAUSED

    state = mgr.load(run_id)
    assert state.status == "paused"
    paused_step = state.completed_steps[-1]
    assert paused_step.step_name == "review-loop"
    assert paused_step.status == "paused"
    assert paused_step.iteration == 1

    # Resume: exactly what run.py's --resume / implicit paths do.
    resume_from = mgr.first_unfinished_step(run_id, definition)
    assert resume_from == "review-loop"  # re-enters the loop, not the next step
    resume_iteration = mgr.resume_iteration_for(run_id, resume_from)
    assert resume_iteration == 1

    # Round 2 (via the resumed loop, which restarts its own internal counter
    # at start_iteration=1 but this is round "2" of the logical sequence —
    # covered by the next test's mid-loop pause instead) — here round 1's
    # resume simply retries round 1 and converges with PASS.
    result2 = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        runs_dir=tmp_path,
        start_from=resume_from,
        start_from_iteration=resume_iteration,
        on_step_complete=mgr.make_step_callback(run_id),
        _action_registry=_e2e_registry([_action_result(True, "review", verdict="PASS")]),
    )
    mgr.finalize(run_id, result2)
    assert result2.status == ExecutionStatus.COMPLETED

    final = mgr.load(run_id)
    assert final.status == "completed"

    # Clean-run regression: a fully completed run reports nothing to resume.
    assert mgr.first_unfinished_step(run_id, definition) is None


@pytest.mark.asyncio
async def test_e2e_paused_at_round_2_of_3_resumes_at_round_2_not_round_1(
    tmp_path: Path,
) -> None:
    """max: counting rule (design Success Criteria): a loop paused at round 2
    of 3 resumes at round 2 and runs at most rounds 2-3 — resume neither
    restarts the count nor grants extra rounds."""
    inner_st = _mock_step_type([("dispatch", {}), ("review", {}), ("checkpoint", {})])
    register_step_type("_e2e_inner_r2_t915", inner_st)

    pipeline = _pipeline(
        [
            _loop_step(
                "review-loop",
                {"max": 3, "until": "review.pass", "steps": [{"_e2e_inner_r2_t915": {}}]},
            )
        ]
    )

    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run("e2e-loop-pipe-r2", {"slice": "915"})

    # Round 1 CONCERNS (no pause — checkpoint only fires when explicitly
    # driven to pause below), round 2 CONCERNS with pause.
    dispatch_action = _mock_action([_action_result(True, "dispatch")] * 2)
    review_action = _mock_action(
        [
            _action_result(True, "review", verdict="CONCERNS"),
            _action_result(True, "review", verdict="CONCERNS"),
        ]
    )
    pause_on_round = [0]

    async def _checkpoint_execute(ctx: ActionContext) -> ActionResult:
        pause_on_round[0] += 1
        if pause_on_round[0] >= 2:
            return _action_result(True, "checkpoint", paused=True)
        return ActionResult(success=True, action_type="checkpoint", outputs={})

    checkpoint_action = MagicMock()
    checkpoint_action.execute = _checkpoint_execute

    result1 = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        runs_dir=tmp_path,
        on_step_complete=mgr.make_step_callback(run_id),
        _action_registry={
            "dispatch": dispatch_action,
            "review": review_action,
            "checkpoint": checkpoint_action,
        },
    )
    assert result1.status == ExecutionStatus.PAUSED

    state = mgr.load(run_id)
    paused_step = state.completed_steps[-1]
    assert paused_step.iteration == 2  # paused at round 2, not round 1

    resume_from = mgr.first_unfinished_step(run_id, pipeline)
    resume_iteration = mgr.resume_iteration_for(run_id, resume_from or "")
    assert resume_iteration == 2  # resumes at round 2, not round 1

    # Resuming runs at most rounds 2-3: converge immediately on re-entry.
    result2 = await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        run_id=run_id,
        runs_dir=tmp_path,
        start_from=resume_from,
        start_from_iteration=resume_iteration,
        on_step_complete=mgr.make_step_callback(run_id),
        _action_registry=_e2e_registry([_action_result(True, "review", verdict="PASS")]),
    )
    assert result2.status == ExecutionStatus.COMPLETED
    # Converged on the first round after resume, i.e. round 2 — not round 1
    # (would be impossible if the count restarted) and not round 4+ (would
    # be impossible if extra rounds were granted beyond max: 3).
    assert result2.step_results[0].iteration == 2
