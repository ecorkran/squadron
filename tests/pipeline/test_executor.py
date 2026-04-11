"""Tests for squadron.pipeline.executor — result types, resolve_placeholders,
evaluate_condition, retry loops, and core executor logic.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig

# ---------------------------------------------------------------------------
# T1 — Test infrastructure helpers
# ---------------------------------------------------------------------------


def make_action_result(
    success: bool,
    action_type: str,
    verdict: str | None = None,
) -> ActionResult:
    """Build a minimal ActionResult for test use."""
    return ActionResult(
        success=success,
        action_type=action_type,
        outputs={},
        verdict=verdict,
    )


def make_step_config(
    step_type: str,
    name: str,
    config: dict[str, object],
) -> StepConfig:
    """Build a StepConfig for test use."""
    return StepConfig(step_type=step_type, name=name, config=config)


def make_pipeline(
    steps: list[StepConfig],
    params: dict[str, object] | None = None,
) -> PipelineDefinition:
    """Build a minimal PipelineDefinition for test use."""
    return PipelineDefinition(
        name="test-pipeline",
        description="test",
        params=params or {},
        steps=steps,
    )


def mock_action(results: list[ActionResult]) -> MagicMock:
    """Return an async mock Action whose execute() returns each result in turn."""
    action = MagicMock()
    # execute is async — use side_effect to yield results sequentially
    action.execute = AsyncMock(side_effect=results)
    return action


def mock_step_type(
    actions: list[tuple[str, dict[str, object]]],
) -> MagicMock:
    """Return a StepType mock whose expand() returns the given action pairs."""
    step = MagicMock()
    step.expand.return_value = actions
    return step


# ---------------------------------------------------------------------------
# T2 — Result types and ExecutionStatus
# ---------------------------------------------------------------------------


class TestExecutionStatus:
    def test_values(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus

        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.PAUSED.value == "paused"
        assert ExecutionStatus.SKIPPED.value == "skipped"


class TestStepResult:
    def test_minimal_construction(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, StepResult

        result = StepResult(
            step_name="my-step",
            step_type="design",
            status=ExecutionStatus.COMPLETED,
            action_results=[],
        )
        assert result.step_name == "my-step"
        assert result.iteration == 0
        assert result.error is None

    def test_with_iteration(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, StepResult

        result = StepResult(
            step_name="s",
            step_type="review",
            status=ExecutionStatus.COMPLETED,
            action_results=[],
            iteration=3,
        )
        assert result.iteration == 3


class TestPipelineResult:
    def test_paused_at_defaults_none(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, PipelineResult

        result = PipelineResult(
            pipeline_name="test",
            status=ExecutionStatus.COMPLETED,
            step_results=[],
        )
        assert result.paused_at is None
        assert result.error is None


# ---------------------------------------------------------------------------
# T3 — resolve_placeholders
# ---------------------------------------------------------------------------


class TestResolvePlaceholders:
    def test_simple_replacement(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders({"key": "{slice}"}, {"slice": "191"})
        assert result["key"] == "191"

    def test_missing_param_left_as_is(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders({"key": "{missing}"}, {})
        assert result["key"] == "{missing}"

    def test_dotted_path(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders(
            {"key": "{slice.index}"},
            {"slice": {"index": "191"}},
        )
        assert result["key"] == "191"

    def test_non_string_value_untouched(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders({"phase": 4}, {"phase": "ignored"})
        assert result["phase"] == 4

    def test_nested_dict_resolved_recursively(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        config: dict[str, object] = {"outer": {"inner": "{val}"}}
        result = resolve_placeholders(config, {"val": "X"})
        outer = result["outer"]
        assert isinstance(outer, dict)
        assert outer["inner"] == "X"

    def test_multiple_placeholders_in_one_string(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders(
            {"key": "{a}-{b}"},
            {"a": "hello", "b": "world"},
        )
        assert result["key"] == "hello-world"

    def test_list_elements_resolved(self) -> None:
        from squadron.pipeline.executor import resolve_placeholders

        result = resolve_placeholders({"items": ["{x}", 42]}, {"x": "foo"})
        assert result["items"] == ["foo", 42]


# ---------------------------------------------------------------------------
# T4 — LoopCondition and evaluate_condition
# ---------------------------------------------------------------------------


class TestEvaluateCondition:
    def test_review_pass_with_pass_verdict(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [make_action_result(True, "review", verdict="PASS")]
        assert evaluate_condition(LoopCondition.REVIEW_PASS, results) is True

    def test_review_pass_with_fail_verdict(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [make_action_result(True, "review", verdict="FAIL")]
        assert evaluate_condition(LoopCondition.REVIEW_PASS, results) is False

    def test_review_concerns_or_better_with_concerns(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [make_action_result(True, "review", verdict="CONCERNS")]
        assert (
            evaluate_condition(LoopCondition.REVIEW_CONCERNS_OR_BETTER, results) is True
        )

    def test_review_concerns_or_better_with_fail(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [make_action_result(True, "review", verdict="FAIL")]
        assert (
            evaluate_condition(LoopCondition.REVIEW_CONCERNS_OR_BETTER, results)
            is False
        )

    def test_action_success_all_pass(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [
            make_action_result(True, "dispatch"),
            make_action_result(True, "commit"),
        ]
        assert evaluate_condition(LoopCondition.ACTION_SUCCESS, results) is True

    def test_action_success_one_failure(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [
            make_action_result(True, "dispatch"),
            make_action_result(False, "commit"),
        ]
        assert evaluate_condition(LoopCondition.ACTION_SUCCESS, results) is False

    def test_review_pass_no_review_actions(self) -> None:
        from squadron.pipeline.executor import LoopCondition, evaluate_condition

        results = [make_action_result(True, "dispatch")]
        assert evaluate_condition(LoopCondition.REVIEW_PASS, results) is False


# ---------------------------------------------------------------------------
# T5a — Core executor: happy path
# ---------------------------------------------------------------------------


class TestExecutePipelineHappyPath:
    @pytest.mark.asyncio
    async def test_single_step_single_action_success(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        action_result = make_action_result(True, "dispatch")
        action = mock_action([action_result])
        step = mock_step_type([("dispatch", {})])

        register_step_type("_test_single", step)

        action_registry: dict[str, object] = {"dispatch": action}
        step_config = make_step_config("_test_single", "step-1", {})
        pipeline = make_pipeline([step_config])

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 1
        assert result.step_results[0].status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_two_steps_both_completed(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        action1 = mock_action([make_action_result(True, "dispatch")])
        action2 = mock_action([make_action_result(True, "commit")])
        step1 = mock_step_type([("dispatch", {})])
        step2 = mock_step_type([("commit", {})])

        register_step_type("_test_two_a", step1)
        register_step_type("_test_two_b", step2)

        pipeline = make_pipeline(
            [
                make_step_config("_test_two_a", "step-a", {}),
                make_step_config("_test_two_b", "step-b", {}),
            ]
        )
        action_registry: dict[str, object] = {"dispatch": action1, "commit": action2}

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(result.step_results) == 2
        assert result.step_results[0].step_name == "step-a"
        assert result.step_results[1].step_name == "step-b"

    @pytest.mark.asyncio
    async def test_prior_outputs_available_in_step2(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_contexts: list[object] = []

        async def action1_execute(ctx: object) -> ActionResult:
            return make_action_result(True, "dispatch")

        async def action2_execute(ctx: object) -> ActionResult:
            captured_contexts.append(ctx)
            return make_action_result(True, "commit")

        action1 = MagicMock()
        action1.execute = action1_execute
        action2 = MagicMock()
        action2.execute = action2_execute

        step1 = mock_step_type([("dispatch", {})])
        step2 = mock_step_type([("commit", {})])

        register_step_type("_test_prior_a", step1)
        register_step_type("_test_prior_b", step2)

        pipeline = make_pipeline(
            [
                make_step_config("_test_prior_a", "step-a", {}),
                make_step_config("_test_prior_b", "step-b", {}),
            ]
        )
        action_registry: dict[str, object] = {"dispatch": action1, "commit": action2}

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(captured_contexts) == 1
        from squadron.pipeline.models import ActionContext

        ctx = captured_contexts[0]
        assert isinstance(ctx, ActionContext)
        # Prior output from step 1 should be keyed as "dispatch-0"
        assert "dispatch-0" in ctx.prior_outputs

    @pytest.mark.asyncio
    async def test_on_step_complete_called_per_step(self) -> None:
        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        calls: list[object] = []

        action = mock_action([make_action_result(True, "dispatch")])
        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_callback", step)

        pipeline = make_pipeline([make_step_config("_test_callback", "step-1", {})])

        await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            on_step_complete=calls.append,
            _action_registry={"dispatch": action},
        )

        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_missing_required_param_raises(self) -> None:
        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        step = mock_step_type([])
        register_step_type("_test_req", step)

        pipeline = make_pipeline(
            [make_step_config("_test_req", "step-1", {})],
            params={"slice": "required"},
        )

        with pytest.raises(ValueError, match="slice"):
            await execute_pipeline(
                pipeline,
                {},  # missing "slice"
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={},
            )


# ---------------------------------------------------------------------------
# T5b — Core executor: error handling and skip logic
# ---------------------------------------------------------------------------


class TestExecutePipelineErrorHandling:
    @pytest.mark.asyncio
    async def test_start_from_skips_earlier_steps(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        executed: list[str] = []

        async def make_exec(name: str) -> ActionResult:
            executed.append(name)
            return make_action_result(True, "dispatch")

        action_a = MagicMock()
        action_a.execute = lambda ctx: make_exec("a")
        action_b = MagicMock()
        action_b.execute = lambda ctx: make_exec("b")

        step_a = mock_step_type([("dispatch", {})])
        step_b = mock_step_type([("dispatch", {})])
        register_step_type("_test_skip_a", step_a)
        register_step_type("_test_skip_b", step_b)

        pipeline = make_pipeline(
            [
                make_step_config("_test_skip_a", "step-a", {}),
                make_step_config("_test_skip_b", "step-b", {}),
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            start_from="step-b",
            _action_registry={"dispatch": action_b},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert "a" not in executed
        assert "b" in executed

    @pytest.mark.asyncio
    async def test_start_from_unknown_step_raises(self) -> None:
        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        step = mock_step_type([])
        register_step_type("_test_unk", step)

        pipeline = make_pipeline([make_step_config("_test_unk", "step-1", {})])

        with pytest.raises(ValueError, match="nonexistent"):
            await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                start_from="nonexistent",
                _action_registry={},
            )

    @pytest.mark.asyncio
    async def test_action_failure_stops_pipeline(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        executed: list[str] = []

        async def fail_exec(ctx: object) -> ActionResult:
            executed.append("step-a")
            return make_action_result(False, "dispatch")

        async def ok_exec(ctx: object) -> ActionResult:
            executed.append("step-b")
            return make_action_result(True, "commit")

        action_fail = MagicMock()
        action_fail.execute = fail_exec
        action_ok = MagicMock()
        action_ok.execute = ok_exec

        step_a = mock_step_type([("dispatch", {})])
        step_b = mock_step_type([("commit", {})])
        register_step_type("_test_fail_a", step_a)
        register_step_type("_test_fail_b", step_b)

        pipeline = make_pipeline(
            [
                make_step_config("_test_fail_a", "step-a", {}),
                make_step_config("_test_fail_b", "step-b", {}),
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"dispatch": action_fail, "commit": action_ok},
        )

        assert result.status == ExecutionStatus.FAILED
        assert "step-b" not in executed

    @pytest.mark.asyncio
    async def test_checkpoint_pause(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        async def pause_exec(ctx: object) -> ActionResult:
            return ActionResult(
                success=True,
                action_type="checkpoint",
                outputs={"checkpoint": "paused"},
            )

        action = MagicMock()
        action.execute = pause_exec

        step = mock_step_type([("checkpoint", {})])
        register_step_type("_test_pause", step)

        pipeline = make_pipeline([make_step_config("_test_pause", "step-pause", {})])

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"checkpoint": action},
        )

        assert result.status == ExecutionStatus.PAUSED
        assert result.paused_at == "step-pause"


# ---------------------------------------------------------------------------
# T6 — Retry loop execution
# ---------------------------------------------------------------------------


class TestRetryLoop:
    @pytest.mark.asyncio
    async def test_loop_runs_once_condition_met(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        action_result = make_action_result(True, "review", verdict="PASS")
        action = mock_action([action_result])
        step = mock_step_type([("review", {})])
        register_step_type("_test_loop1", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_loop1",
                    "step-loop",
                    {"loop": {"max": 3, "until": "review.pass"}},
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": action},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.step_results[0].iteration == 1

    @pytest.mark.asyncio
    async def test_loop_runs_until_condition_met_on_third(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        results = [
            make_action_result(True, "review", verdict="FAIL"),
            make_action_result(True, "review", verdict="FAIL"),
            make_action_result(True, "review", verdict="PASS"),
        ]
        action = mock_action(results)
        step = mock_step_type([("review", {})])
        register_step_type("_test_loop3", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_loop3",
                    "step-loop",
                    {"loop": {"max": 5, "until": "review.pass"}},
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": action},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.step_results[0].iteration == 3

    @pytest.mark.asyncio
    async def test_loop_exhaust_fail(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        results = [make_action_result(True, "review", verdict="FAIL")] * 3
        action = mock_action(results)
        step = mock_step_type([("review", {})])
        register_step_type("_test_exhaust_fail", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_exhaust_fail",
                    "step-loop",
                    {"loop": {"max": 3, "until": "review.pass", "on_exhaust": "fail"}},
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": action},
        )

        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_loop_exhaust_checkpoint(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        results = [make_action_result(True, "review", verdict="FAIL")] * 2
        action = mock_action(results)
        step = mock_step_type([("review", {})])
        register_step_type("_test_exhaust_ckpt", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_exhaust_ckpt",
                    "step-loop",
                    {
                        "loop": {
                            "max": 2,
                            "until": "review.pass",
                            "on_exhaust": "checkpoint",
                        }
                    },
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": action},
        )

        assert result.status == ExecutionStatus.PAUSED
        assert result.paused_at == "step-loop"

    @pytest.mark.asyncio
    async def test_loop_exhaust_skip_continues(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        review_results = [make_action_result(True, "review", verdict="FAIL")] * 2
        review_action = mock_action(review_results)
        ok_action = mock_action([make_action_result(True, "commit")])

        loop_step = mock_step_type([("review", {})])
        next_step = mock_step_type([("commit", {})])
        register_step_type("_test_skip_step", loop_step)
        register_step_type("_test_skip_next", next_step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_skip_step",
                    "step-loop",
                    {
                        "loop": {
                            "max": 2,
                            "until": "review.pass",
                            "on_exhaust": "skip",
                        }
                    },
                ),
                make_step_config("_test_skip_next", "step-next", {}),
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"review": review_action, "commit": ok_action},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert result.step_results[0].status == ExecutionStatus.SKIPPED
        assert result.step_results[1].status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_checkpoint_in_loop_stops_immediately(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        async def pause_exec(ctx: object) -> ActionResult:
            return ActionResult(
                success=True,
                action_type="checkpoint",
                outputs={"checkpoint": "paused"},
            )

        action = MagicMock()
        action.execute = pause_exec

        step = mock_step_type([("checkpoint", {})])
        register_step_type("_test_loop_pause", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_loop_pause",
                    "step-loop",
                    {"loop": {"max": 5, "until": "review.pass"}},
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry={"checkpoint": action},
        )

        assert result.status == ExecutionStatus.PAUSED
        assert result.paused_at == "step-loop"

    @pytest.mark.asyncio
    async def test_loop_strategy_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        action_result = make_action_result(True, "dispatch")
        action = mock_action([action_result])
        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_strategy", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_strategy",
                    "step-1",
                    {"loop": {"max": 1, "strategy": "convergence"}},
                )
            ]
        )

        with caplog.at_level(logging.WARNING):
            result = await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={"dispatch": action},
            )

        assert result.status == ExecutionStatus.COMPLETED
        assert any("convergence" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_invalid_on_exhaust_raises(self) -> None:
        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_inv_exhaust", step)

        pipeline = make_pipeline(
            [
                make_step_config(
                    "_test_inv_exhaust",
                    "step-1",
                    {"loop": {"max": 1, "on_exhaust": "invalid-value"}},
                )
            ]
        )

        with pytest.raises(ValueError, match="on_exhaust"):
            await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={"dispatch": MagicMock()},
            )


# ---------------------------------------------------------------------------
# T7 — EachStepType
# ---------------------------------------------------------------------------


class TestEachStepType:
    def _make_valid_config(self) -> StepConfig:
        return make_step_config(
            "each",
            "each-step",
            {
                "source": 'cf.unfinished_slices("{plan}")',
                "as": "slice",
                "steps": [{"design": {"phase": 4}}],
            },
        )

    def test_validate_valid_config(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        errors = impl.validate(self._make_valid_config())
        assert errors == []

    def test_validate_missing_source(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        cfg = make_step_config(
            "each", "s", {"as": "slice", "steps": [{"design": {"phase": 4}}]}
        )
        errors = impl.validate(cfg)
        assert any(e.field == "source" for e in errors)

    def test_validate_missing_as(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        cfg = make_step_config(
            "each",
            "s",
            {"source": "cf.unfinished_slices()", "steps": [{"design": {"phase": 4}}]},
        )
        errors = impl.validate(cfg)
        assert any(e.field == "as" for e in errors)

    def test_validate_missing_steps(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        cfg = make_step_config(
            "each", "s", {"source": "cf.unfinished_slices()", "as": "slice"}
        )
        errors = impl.validate(cfg)
        assert any(e.field == "steps" for e in errors)

    def test_validate_malformed_source(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        cfg = make_step_config(
            "each",
            "s",
            {"source": "not-valid-source", "as": "slice", "steps": [{"design": {}}]},
        )
        errors = impl.validate(cfg)
        assert any(e.field == "source" for e in errors)

    def test_validate_empty_steps_list(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        cfg = make_step_config(
            "each",
            "s",
            {"source": "cf.unfinished_slices()", "as": "slice", "steps": []},
        )
        errors = impl.validate(cfg)
        assert any(e.field == "steps" for e in errors)

    def test_expand_returns_empty_list(self) -> None:
        from squadron.pipeline.steps.collection import EachStepType

        impl = EachStepType()
        assert impl.expand(self._make_valid_config()) == []

    def test_registered_under_each(self) -> None:
        import squadron.pipeline.steps.collection  # noqa: F401
        from squadron.pipeline.steps import get_step_type

        impl = get_step_type("each")
        assert impl.step_type == "each"


# ---------------------------------------------------------------------------
# T8 — Source registry and `each` execution
# ---------------------------------------------------------------------------


class TestCfUnfinishedSlices:
    @pytest.mark.asyncio
    async def test_filters_complete_slices(self) -> None:
        from squadron.integrations.context_forge import SliceEntry
        from squadron.pipeline.executor import _cf_unfinished_slices

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(index=1, name="slice-a", design_file=None, status="complete"),
            SliceEntry(
                index=2, name="slice-b", design_file="f.md", status="in_progress"
            ),
            SliceEntry(index=3, name="slice-c", design_file=None, status="not_started"),
        ]

        result = await _cf_unfinished_slices([], cf_client, {})
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "slice-a" not in names
        assert "slice-b" in names
        assert "slice-c" in names


class TestParseSource:
    def test_valid_source(self) -> None:
        from squadron.pipeline.executor import _parse_source

        ns, fn, args = _parse_source('cf.unfinished_slices("myplan")')
        assert ns == "cf"
        assert fn == "unfinished_slices"
        assert args == ["myplan"]

    def test_unrecognized_source_raises(self) -> None:
        from squadron.pipeline.executor import _parse_source

        with pytest.raises(ValueError, match="Unknown source"):
            _parse_source("cf.nonexistent_fn()")

    def test_malformed_source_raises(self) -> None:
        from squadron.pipeline.executor import _parse_source

        with pytest.raises(ValueError):
            _parse_source("not-a-source")


class TestEachExecution:
    @pytest.mark.asyncio
    async def test_two_slices_inner_steps_run_twice(self) -> None:
        from squadron.integrations.context_forge import SliceEntry
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        call_count = 0

        async def dispatch_exec(ctx: object) -> ActionResult:
            nonlocal call_count
            call_count += 1
            return make_action_result(True, "dispatch")

        dispatch_action = MagicMock()
        dispatch_action.execute = dispatch_exec

        inner_step_type = mock_step_type([("dispatch", {})])
        register_step_type("_test_each_inner", inner_step_type)

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(index=1, name="slice-a", design_file=None, status="not_started"),
            SliceEntry(index=2, name="slice-b", design_file=None, status="in_progress"),
        ]

        pipeline = make_pipeline(
            [
                make_step_config(
                    "each",
                    "each-step",
                    {
                        "source": "cf.unfinished_slices()",
                        "as": "slice",
                        "steps": [{"_test_each_inner": {}}],
                    },
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=cf_client,
            _action_registry={"dispatch": dispatch_action},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_zero_slices_completes(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        inner_step_type = mock_step_type([("dispatch", {})])
        register_step_type("_test_each_zero", inner_step_type)

        cf_client = MagicMock()
        cf_client.list_slices.return_value = []

        pipeline = make_pipeline(
            [
                make_step_config(
                    "each",
                    "each-step",
                    {
                        "source": "cf.unfinished_slices()",
                        "as": "slice",
                        "steps": [{"_test_each_zero": {}}],
                    },
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=cf_client,
            _action_registry={},
        )

        assert result.status == ExecutionStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_slice_index_resolves_in_inner_step(self) -> None:
        from squadron.integrations.context_forge import SliceEntry
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        received_params: list[dict[str, object]] = []

        async def dispatch_exec(ctx: object) -> ActionResult:
            from squadron.pipeline.models import ActionContext

            assert isinstance(ctx, ActionContext)
            received_params.append(dict(ctx.params))
            return make_action_result(True, "dispatch")

        dispatch_action = MagicMock()
        dispatch_action.execute = dispatch_exec

        inner_step_type = mock_step_type([("dispatch", {"slice_id": "{slice.index}"})])
        register_step_type("_test_each_resolve", inner_step_type)

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(
                index=42, name="my-slice", design_file=None, status="not_started"
            ),
        ]

        pipeline = make_pipeline(
            [
                make_step_config(
                    "each",
                    "each-step",
                    {
                        "source": "cf.unfinished_slices()",
                        "as": "slice",
                        "steps": [
                            {"_test_each_resolve": {"slice_id": "{slice.index}"}}
                        ],
                    },
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=cf_client,
            _action_registry={"dispatch": dispatch_action},
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(received_params) == 1
        assert received_params[0].get("slice_id") == "42"

    @pytest.mark.asyncio
    async def test_inner_step_failure_propagates(self) -> None:
        from squadron.integrations.context_forge import SliceEntry
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        async def fail_exec(ctx: object) -> ActionResult:
            return make_action_result(False, "dispatch")

        fail_action = MagicMock()
        fail_action.execute = fail_exec

        inner_step_type = mock_step_type([("dispatch", {})])
        register_step_type("_test_each_fail", inner_step_type)

        cf_client = MagicMock()
        cf_client.list_slices.return_value = [
            SliceEntry(index=1, name="a", design_file=None, status="not_started"),
            SliceEntry(index=2, name="b", design_file=None, status="not_started"),
        ]

        pipeline = make_pipeline(
            [
                make_step_config(
                    "each",
                    "each-step",
                    {
                        "source": "cf.unfinished_slices()",
                        "as": "slice",
                        "steps": [{"_test_each_fail": {}}],
                    },
                )
            ]
        )

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=cf_client,
            _action_registry={"dispatch": fail_action},
        )

        assert result.status == ExecutionStatus.FAILED

    @pytest.mark.asyncio
    async def test_unrecognized_source_raises(self) -> None:
        from squadron.pipeline.executor import execute_pipeline

        pipeline = make_pipeline(
            [
                make_step_config(
                    "each",
                    "each-step",
                    {
                        "source": "cf.no_such_function()",
                        "as": "slice",
                        "steps": [{"design": {}}],
                    },
                )
            ]
        )

        with pytest.raises(ValueError, match="Unknown source"):
            await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={},
            )


# ---------------------------------------------------------------------------
# T6 — _project param injection
# ---------------------------------------------------------------------------


class TestProjectParamInjection:
    @pytest.mark.asyncio
    async def test_project_injected_from_cf(self, tmp_path: object) -> None:
        """_project is set in ActionContext.params from gather_cf_params."""
        from pathlib import Path
        from unittest.mock import patch

        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        assert isinstance(tmp_path, Path)

        captured_ctx: list[object] = []

        async def capture_ctx(ctx: object) -> ActionResult:
            captured_ctx.append(ctx)
            return make_action_result(True, "dispatch")

        action = MagicMock()
        action.execute = capture_ctx
        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_project_inject", step)

        pipeline = make_pipeline([make_step_config("_test_project_inject", "s", {})])

        with patch(
            "squadron.pipeline.executor.gather_cf_params",
            return_value={"project": "myproject"},
        ):
            await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                cwd=str(tmp_path),
                _action_registry={"dispatch": action},
            )

        assert len(captured_ctx) == 1
        from squadron.pipeline.models import ActionContext

        ctx = captured_ctx[0]
        assert isinstance(ctx, ActionContext)
        assert ctx.params["_project"] == "myproject"

    @pytest.mark.asyncio
    async def test_project_falls_back_to_unknown_when_cf_unavailable(
        self, tmp_path: object
    ) -> None:
        """CF unavailable → _project is 'unknown', no exception."""
        from pathlib import Path
        from unittest.mock import patch

        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        assert isinstance(tmp_path, Path)

        captured_ctx: list[object] = []

        async def capture_ctx(ctx: object) -> ActionResult:
            captured_ctx.append(ctx)
            return make_action_result(True, "dispatch")

        action = MagicMock()
        action.execute = capture_ctx
        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_project_fallback", step)

        pipeline = make_pipeline([make_step_config("_test_project_fallback", "s", {})])

        with patch(
            "squadron.pipeline.executor.gather_cf_params",
            return_value={},
        ):
            await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                cwd=str(tmp_path),
                _action_registry={"dispatch": action},
            )

        assert len(captured_ctx) == 1
        from squadron.pipeline.models import ActionContext

        ctx = captured_ctx[0]
        assert isinstance(ctx, ActionContext)
        assert ctx.params["_project"] == "unknown"

    @pytest.mark.asyncio
    async def test_explicit_project_param_not_overwritten(
        self, tmp_path: object
    ) -> None:
        """Caller-supplied _project in params takes precedence over CF."""
        from pathlib import Path
        from unittest.mock import patch

        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        assert isinstance(tmp_path, Path)

        captured_ctx: list[object] = []

        async def capture_ctx(ctx: object) -> ActionResult:
            captured_ctx.append(ctx)
            return make_action_result(True, "dispatch")

        action = MagicMock()
        action.execute = capture_ctx
        step = mock_step_type([("dispatch", {})])
        register_step_type("_test_project_override", step)

        pipeline = make_pipeline([make_step_config("_test_project_override", "s", {})])

        with patch(
            "squadron.pipeline.executor.gather_cf_params",
            return_value={"project": "cf-project"},
        ):
            await execute_pipeline(
                pipeline,
                {"_project": "explicit-override"},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                cwd=str(tmp_path),
                _action_registry={"dispatch": action},
            )

        from squadron.pipeline.models import ActionContext

        ctx = captured_ctx[0]
        assert isinstance(ctx, ActionContext)
        assert ctx.params["_project"] == "explicit-override"


# ---------------------------------------------------------------------------
# T160-1 — CheckpointResolution, CheckpointDecision, _is_interactive
# ---------------------------------------------------------------------------


class TestCheckpointResolution:
    def test_values(self) -> None:
        from squadron.pipeline.executor import CheckpointResolution

        assert CheckpointResolution.ACCEPT.value == "accept"
        assert CheckpointResolution.OVERRIDE.value == "override"
        assert CheckpointResolution.EXIT.value == "exit"

    def test_importable_from_all(self) -> None:
        from squadron.pipeline import executor

        assert "CheckpointResolution" in executor.__all__
        assert "CheckpointDecision" in executor.__all__


class TestCheckpointDecision:
    def test_exit_construction(self) -> None:
        from squadron.pipeline.executor import CheckpointDecision, CheckpointResolution

        decision = CheckpointDecision(CheckpointResolution.EXIT, None)
        assert decision.resolution == CheckpointResolution.EXIT
        assert decision.override_instructions is None

    def test_accept_construction(self) -> None:
        from squadron.pipeline.executor import CheckpointDecision, CheckpointResolution

        decision = CheckpointDecision(CheckpointResolution.ACCEPT, "fix error handling")
        assert decision.resolution == CheckpointResolution.ACCEPT
        assert decision.override_instructions == "fix error handling"


class TestIsInteractive:
    def test_no_interactive_env_var_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from squadron.pipeline.executor import _is_interactive

        monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")
        assert _is_interactive() is False

    def test_non_tty_stdin(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from squadron.pipeline.executor import _is_interactive

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: False))
        assert _is_interactive() is False

    def test_tty_and_no_env_var(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from squadron.pipeline.executor import _is_interactive

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        assert _is_interactive() is True


# ---------------------------------------------------------------------------
# T160-2 — _prompt_checkpoint_interactive
# ---------------------------------------------------------------------------


class TestPromptCheckpointInteractive:
    """Tests for _prompt_checkpoint_interactive using stdin/stdout monkeypatching."""

    def _make_findings(self, count: int) -> list[dict[str, object]]:
        return [
            {
                "severity": "concern",
                "summary": f"Finding {i}",
                "location": f"file.py:{i}",
            }
            for i in range(1, count + 1)
        ]

    def test_non_interactive_env_var_returns_exit(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from squadron.pipeline.executor import (
            CheckpointResolution,
            _prompt_checkpoint_interactive,
        )

        monkeypatch.setenv("SQUADRON_NO_INTERACTIVE", "1")
        decision = _prompt_checkpoint_interactive(
            verdict="CONCERNS",
            findings=[],
            run_id="run-abc",
            step_name="design",
        )
        assert decision.resolution == CheckpointResolution.EXIT
        assert decision.override_instructions is None

    def test_accept_returns_formatted_findings(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import sys

        from squadron.pipeline.executor import (
            CheckpointResolution,
            _prompt_checkpoint_interactive,
        )

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))

        findings = [
            {
                "severity": "concern",
                "summary": "Bad error handling",
                "location": "src/foo.py:10",
            },
            {
                "severity": "note",
                "summary": "Variable name unclear",
                "location": "src/bar.py:5",
            },
        ]
        inputs = iter(["a"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        decision = _prompt_checkpoint_interactive(
            verdict="CONCERNS",
            findings=findings,
            run_id="run-abc",
            step_name="design",
        )
        assert decision.resolution == CheckpointResolution.ACCEPT
        assert (
            "[concern] Bad error handling — src/foo.py:10"
            in decision.override_instructions
        )
        assert (
            "[note] Variable name unclear — src/bar.py:5"
            in decision.override_instructions
        )

    def test_override_returns_user_text(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from squadron.pipeline.executor import (
            CheckpointResolution,
            _prompt_checkpoint_interactive,
        )

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))

        inputs = iter(["o", "keep it under 50 lines"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        decision = _prompt_checkpoint_interactive(
            verdict="CONCERNS",
            findings=[],
            run_id="run-abc",
            step_name="design",
        )
        assert decision.resolution == CheckpointResolution.OVERRIDE
        assert decision.override_instructions == "keep it under 50 lines"

    def test_exit_returns_exit_decision(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from squadron.pipeline.executor import (
            CheckpointResolution,
            _prompt_checkpoint_interactive,
        )

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "e")

        decision = _prompt_checkpoint_interactive(
            verdict=None,
            findings=[],
            run_id="run-abc",
            step_name="review",
        )
        assert decision.resolution == CheckpointResolution.EXIT
        assert decision.override_instructions is None

    def test_invalid_input_then_accept(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import sys

        from squadron.pipeline.executor import (
            CheckpointResolution,
            _prompt_checkpoint_interactive,
        )

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))

        inputs = iter(["x", "a"])
        monkeypatch.setattr("builtins.input", lambda _: next(inputs))

        decision = _prompt_checkpoint_interactive(
            verdict="CONCERNS",
            findings=[],
            run_id="run-abc",
            step_name="design",
        )
        assert decision.resolution == CheckpointResolution.ACCEPT

    def test_finding_truncation(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        import sys

        from squadron.pipeline.executor import _prompt_checkpoint_interactive

        monkeypatch.delenv("SQUADRON_NO_INTERACTIVE", raising=False)
        monkeypatch.setattr(sys, "stdin", MagicMock(isatty=lambda: True))
        monkeypatch.setattr("builtins.input", lambda _: "e")

        findings = self._make_findings(12)
        _prompt_checkpoint_interactive(
            verdict="CONCERNS",
            findings=findings,
            run_id="run-abc",
            step_name="design",
        )
        captured = capsys.readouterr()
        assert "… and 2 more (see review file)" in captured.out


# ---------------------------------------------------------------------------
# T160-3 — Checkpoint detection in _execute_step_once (via execute_pipeline)
# ---------------------------------------------------------------------------


class TestCheckpointDetection:
    """Tests for the modified checkpoint detection block in _execute_step_once."""

    async def _run_checkpoint_pipeline(
        self,
        decision: object,
        extra_actions: list[tuple[str, object]] | None = None,
    ) -> tuple[object, dict[str, object]]:
        """Helper: run a pipeline with a checkpoint action and a mocked decision.

        Returns (pipeline_result, merged_params_snapshot).
        The pipeline has: [review, checkpoint] then optionally extra_actions.
        """
        from unittest.mock import patch

        from squadron.pipeline.executor import execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_params: dict[str, object] = {}

        async def checkpoint_exec(ctx: object) -> ActionResult:
            return ActionResult(
                success=True,
                action_type="checkpoint",
                outputs={"checkpoint": "paused"},
            )

        async def post_exec(ctx: object) -> ActionResult:
            # Capture merged params at the point after checkpoint decision

            captured_params.update(ctx.params)  # type: ignore[union-attr]
            return ActionResult(success=True, action_type="commit", outputs={})

        actions: list[tuple[str, dict[str, object]]] = [("checkpoint", {})]
        action_registry: dict[str, object] = {}

        checkpoint_action = MagicMock()
        checkpoint_action.execute = checkpoint_exec
        action_registry["checkpoint"] = checkpoint_action

        if extra_actions:
            for act_type, _ in extra_actions:
                post_action = MagicMock()
                post_action.execute = post_exec
                action_registry[act_type] = post_action
                actions.append((act_type, {}))

        step_name = "_test_ckpt_detect"
        step = mock_step_type(actions)
        register_step_type(step_name, step)

        pipeline = make_pipeline([make_step_config(step_name, "step-ckpt", {})])

        with patch(
            "squadron.pipeline.executor._prompt_checkpoint_interactive",
            return_value=decision,
        ):
            result = await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry=action_registry,
            )
        return result, captured_params

    @pytest.mark.asyncio
    async def test_exit_returns_paused(self) -> None:
        from squadron.pipeline.executor import (
            CheckpointDecision,
            CheckpointResolution,
            ExecutionStatus,
        )

        decision = CheckpointDecision(CheckpointResolution.EXIT, None)
        result, _ = await self._run_checkpoint_pipeline(decision)
        assert result.status == ExecutionStatus.PAUSED

    @pytest.mark.asyncio
    async def test_accept_continues_and_injects_instructions(self) -> None:
        from squadron.pipeline.executor import (
            CheckpointDecision,
            CheckpointResolution,
            ExecutionStatus,
        )

        decision = CheckpointDecision(CheckpointResolution.ACCEPT, "fix error handling")
        result, captured = await self._run_checkpoint_pipeline(
            decision, extra_actions=[("commit", {})]
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert captured.get("override_instructions") == "fix error handling"

    @pytest.mark.asyncio
    async def test_override_continues_and_injects_instructions(self) -> None:
        from squadron.pipeline.executor import (
            CheckpointDecision,
            CheckpointResolution,
            ExecutionStatus,
        )

        decision = CheckpointDecision(
            CheckpointResolution.OVERRIDE, "keep under 50 lines"
        )
        result, captured = await self._run_checkpoint_pipeline(
            decision, extra_actions=[("commit", {})]
        )
        assert result.status == ExecutionStatus.COMPLETED
        assert captured.get("override_instructions") == "keep under 50 lines"

    @pytest.mark.asyncio
    async def test_second_checkpoint_replaces_instructions(self) -> None:
        """Second checkpoint decision replaces override_instructions from the first."""
        from unittest.mock import patch

        from squadron.pipeline.executor import (
            CheckpointDecision,
            CheckpointResolution,
            ExecutionStatus,
            execute_pipeline,
        )
        from squadron.pipeline.steps import register_step_type

        captured_params: list[dict[str, object]] = []
        call_count = 0

        decisions = [
            CheckpointDecision(CheckpointResolution.ACCEPT, "fix A"),
            CheckpointDecision(CheckpointResolution.OVERRIDE, "fix B"),
        ]

        async def checkpoint_exec(ctx: object) -> ActionResult:
            return ActionResult(
                success=True,
                action_type="checkpoint",
                outputs={"checkpoint": "paused"},
            )

        async def commit_exec(ctx: object) -> ActionResult:
            captured_params.append(dict(ctx.params))  # type: ignore[union-attr]
            return ActionResult(success=True, action_type="commit", outputs={})

        step_name = "_test_ckpt_replace"
        # One step with: checkpoint, commit, checkpoint, commit
        step = mock_step_type(
            [("checkpoint", {}), ("commit", {}), ("checkpoint", {}), ("commit2", {})]
        )
        register_step_type(step_name, step)

        ck_action = MagicMock()
        ck_action.execute = checkpoint_exec
        cm_action = MagicMock()
        cm_action.execute = commit_exec
        cm2_action = MagicMock()
        cm2_action.execute = commit_exec

        def decision_side_effect(*args: object, **kwargs: object) -> object:
            nonlocal call_count
            d = decisions[call_count]
            call_count += 1
            return d

        pipeline = make_pipeline([make_step_config(step_name, "step-replace", {})])

        with patch(
            "squadron.pipeline.executor._prompt_checkpoint_interactive",
            side_effect=decision_side_effect,
        ):
            result = await execute_pipeline(
                pipeline,
                {},
                resolver=MagicMock(),
                cf_client=MagicMock(),
                _action_registry={
                    "checkpoint": ck_action,
                    "commit": cm_action,
                    "commit2": cm2_action,
                },
            )

        assert result.status == ExecutionStatus.COMPLETED
        # Second commit should see "fix B"
        assert len(captured_params) == 2
        assert captured_params[0].get("override_instructions") == "fix A"
        assert captured_params[1].get("override_instructions") == "fix B"
