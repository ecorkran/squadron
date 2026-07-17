"""Tests for the gate action's reduction core: severity table and reduce_verdicts."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.gate import reduce_verdicts
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig

_VERDICTS = ["PASS", "CONCERNS", "FAIL", "UNKNOWN"]

_MOST_SEVERE = {"PASS": 0, "CONCERNS": 1, "FAIL": 2, "UNKNOWN": 3}


def _expected(a: str, b: str) -> str:
    return a if _MOST_SEVERE[a] >= _MOST_SEVERE[b] else b


class TestReduceVerdictsCrossProduct:
    """Full 4x4 cross-product of {PASS, CONCERNS, FAIL, UNKNOWN}, incl. diagonal ties."""

    @pytest.mark.parametrize(
        ("a", "b"),
        [(a, b) for a in _VERDICTS for b in _VERDICTS],
    )
    def test_most_severe_wins(self, a: str, b: str) -> None:
        assert reduce_verdicts(a, b) == _expected(a, b)

    @pytest.mark.parametrize("verdict", _VERDICTS)
    def test_diagonal_ties_are_idempotent(self, verdict: str) -> None:
        assert reduce_verdicts(verdict, verdict) == verdict


class TestReduceVerdictsNoneNormalization:
    """A None leg normalizes to UNKNOWN before ranking (F001, fail-closed)."""

    def test_none_and_pass_yields_unknown(self) -> None:
        assert reduce_verdicts(None, "PASS") == "UNKNOWN"

    def test_pass_and_none_yields_unknown(self) -> None:
        assert reduce_verdicts("PASS", None) == "UNKNOWN"

    def test_none_and_none_yields_unknown(self) -> None:
        assert reduce_verdicts(None, None) == "UNKNOWN"

    @pytest.mark.parametrize("verdict", _VERDICTS)
    def test_none_dominates_every_verdict(self, verdict: str) -> None:
        assert reduce_verdicts(None, verdict) == "UNKNOWN"
        assert reduce_verdicts(verdict, None) == "UNKNOWN"


# ---------------------------------------------------------------------------
# T4 — Executor step-keyed read surface (ActionContext.step_outputs)
# ---------------------------------------------------------------------------


def _make_step_config(step_type: str, name: str, config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type=step_type, name=name, config=config)


def _make_pipeline(steps: list[StepConfig]) -> PipelineDefinition:
    return PipelineDefinition(name="test-pipeline", description="test", params={}, steps=steps)


class TestStepOutputsReadSurface:
    """Prove step_outputs recovers both source results by step name, bypassing
    the review-0 collision in the lossy action-keyed prior_outputs."""

    @pytest.mark.asyncio
    async def test_later_step_sees_both_named_review_results(self) -> None:
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_contexts: list[ActionContext] = []

        async def review_execute(ctx: ActionContext) -> ActionResult:
            verdict = "PASS" if ctx.step_name == "judge-slice" else "CONCERNS"
            return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

        async def gate_execute(ctx: ActionContext) -> ActionResult:
            captured_contexts.append(ctx)
            return ActionResult(success=True, action_type="gate", outputs={})

        review_action = MagicMock()
        review_action.execute = review_execute
        gate_action = MagicMock()
        gate_action.execute = gate_execute

        review_step = MagicMock()
        review_step.expand.return_value = [("review", {})]
        gate_step = MagicMock()
        gate_step.expand.return_value = [("gate", {})]

        register_step_type("_test_step_outputs_review", review_step)
        register_step_type("_test_step_outputs_gate", gate_step)

        pipeline = _make_pipeline(
            [
                _make_step_config("_test_step_outputs_review", "judge-slice", {}),
                _make_step_config("_test_step_outputs_review", "review-slice", {}),
                _make_step_config("_test_step_outputs_gate", "compose-gate", {}),
            ]
        )
        action_registry: dict[str, object] = {"review": review_action, "gate": gate_action}

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        assert len(captured_contexts) == 1
        ctx = captured_contexts[0]

        # Both source results are recoverable by step name, despite both
        # having written the same "review-0" key in prior_outputs.
        assert ctx.step_outputs["judge-slice"].verdict == "PASS"
        assert ctx.step_outputs["review-slice"].verdict == "CONCERNS"


class TestStepOutputsRegression:
    """The read surface is purely additive: prior_outputs and
    _find_review_verdict behavior are unchanged."""

    @pytest.mark.asyncio
    async def test_prior_outputs_collision_unchanged(self) -> None:
        """Two review steps still collide under 'review-0' in prior_outputs —
        step_outputs does not alter this existing (lossy) behavior."""
        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
        from squadron.pipeline.steps import register_step_type

        captured_contexts: list[ActionContext] = []

        async def review_execute(ctx: ActionContext) -> ActionResult:
            verdict = "PASS" if ctx.step_name == "judge-slice" else "CONCERNS"
            return ActionResult(success=True, action_type="review", outputs={}, verdict=verdict)

        async def checkpoint_execute(ctx: ActionContext) -> ActionResult:
            captured_contexts.append(ctx)
            return ActionResult(success=True, action_type="checkpoint", outputs={})

        review_action = MagicMock()
        review_action.execute = review_execute
        checkpoint_action = MagicMock()
        checkpoint_action.execute = checkpoint_execute

        review_step = MagicMock()
        review_step.expand.return_value = [("review", {})]
        checkpoint_step = MagicMock()
        checkpoint_step.expand.return_value = [("checkpoint", {})]

        register_step_type("_test_regression_review", review_step)
        register_step_type("_test_regression_checkpoint", checkpoint_step)

        pipeline = _make_pipeline(
            [
                _make_step_config("_test_regression_review", "judge-slice", {}),
                _make_step_config("_test_regression_review", "review-slice", {}),
                _make_step_config("_test_regression_checkpoint", "gate-check", {}),
            ]
        )
        action_registry: dict[str, object] = {
            "review": review_action,
            "checkpoint": checkpoint_action,
        }

        result = await execute_pipeline(
            pipeline,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            _action_registry=action_registry,
        )

        assert result.status == ExecutionStatus.COMPLETED
        ctx = captured_contexts[0]

        # Only one "review-0" key survives — the second review step's result
        # overwrote the first's, exactly as before this slice.
        assert list(ctx.prior_outputs.keys()).count("review-0") == 1
        assert ctx.prior_outputs["review-0"].verdict == "CONCERNS"
