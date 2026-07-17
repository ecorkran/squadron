"""Tests for the gate action's reduction core: severity table and reduce_verdicts."""

from __future__ import annotations

import logging
from unittest.mock import MagicMock

import pytest

from squadron.pipeline.actions.gate import GateAction, reduce_verdicts
from squadron.pipeline.actions.judge import Provenance
from squadron.pipeline.actions.protocol import Action
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


# ---------------------------------------------------------------------------
# T5/T6 — GateAction
# ---------------------------------------------------------------------------


def _make_gate_context(
    step_outputs: dict[str, ActionResult] | None = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    """Build an ActionContext with configurable step_outputs and params."""
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params=params or {},
        step_name="compose-gate",
        step_index=2,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp/test",
        step_outputs=step_outputs or {},
    )


def _named_result(
    verdict: str | None,
    score: float | None = None,
    criteria: dict[str, float] | None = None,
) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={},
        verdict=verdict,
        score=score,
        criteria=criteria,
    )


class TestGateActionBasics:
    def test_action_type(self) -> None:
        assert GateAction().action_type == "gate"

    def test_protocol_compliance(self) -> None:
        assert isinstance(GateAction(), Action)


class TestGateActionValidation:
    def test_valid_config(self) -> None:
        errors = GateAction().validate({"judge_from": "judge-slice", "review_from": "review-slice"})
        assert errors == []

    def test_missing_judge_from(self) -> None:
        errors = GateAction().validate({"review_from": "review-slice"})
        assert len(errors) == 1
        assert errors[0].field == "judge_from"

    def test_missing_review_from(self) -> None:
        errors = GateAction().validate({"judge_from": "judge-slice"})
        assert len(errors) == 1
        assert errors[0].field == "review_from"

    def test_missing_both(self) -> None:
        errors = GateAction().validate({})
        assert {e.field for e in errors} == {"judge_from", "review_from"}


class TestGateActionExecute:
    @pytest.mark.asyncio
    async def test_judge_pass_review_concerns_reduces_to_concerns(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS", score=90.0),
                "review-slice": _named_result("CONCERNS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "CONCERNS"
        assert result.provenance == Provenance.COMPOSED
        assert result.metadata["judge_verdict"] == "PASS"
        assert result.metadata["review_verdict"] == "CONCERNS"

    @pytest.mark.asyncio
    async def test_judge_unknown_review_pass_reduces_to_unknown(self) -> None:
        """No-silent-pass under a broken judge leg."""
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("UNKNOWN"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"

    @pytest.mark.asyncio
    async def test_none_leg_verdict_reduces_to_unknown_and_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result(None),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        with caplog.at_level(logging.WARNING):
            result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_unresolvable_judge_from_yields_unknown_and_warns(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        ctx = _make_gate_context(
            step_outputs={"review-slice": _named_result("PASS")},
            params={"judge_from": "does-not-exist", "review_from": "review-slice"},
        )
        with caplog.at_level(logging.WARNING):
            result = await GateAction().execute(ctx)
        assert result.verdict == "UNKNOWN"
        assert any(r.levelno >= logging.WARNING for r in caplog.records)

    @pytest.mark.asyncio
    async def test_both_pass_reduces_to_pass(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.verdict == "PASS"

    @pytest.mark.asyncio
    async def test_success_is_true(self) -> None:
        ctx = _make_gate_context(
            step_outputs={
                "judge-slice": _named_result("PASS"),
                "review-slice": _named_result("PASS"),
            },
            params={"judge_from": "judge-slice", "review_from": "review-slice"},
        )
        result = await GateAction().execute(ctx)
        assert result.success is True


# ---------------------------------------------------------------------------
# T7/T8 — GateStepType: expansion and own-config validation
# ---------------------------------------------------------------------------


def _gate_step_config(config: dict[str, object], name: str = "compose-gate") -> StepConfig:
    return StepConfig(step_type="gate", name=name, config=config)


class TestGateStepTypeBasics:
    def test_step_type(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        assert GateStepType().step_type == "gate"


class TestGateStepTypeExpand:
    def test_expand_without_checkpoint(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"judge_from": "judge-slice", "review_from": "review-slice"})
        actions = GateStepType().expand(step)
        assert actions == [
            ("gate", {"judge_from": "judge-slice", "review_from": "review-slice"}),
        ]

    def test_expand_with_checkpoint(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "checkpoint": "on-concerns",
            }
        )
        actions = GateStepType().expand(step)
        assert actions == [
            ("gate", {"judge_from": "judge-slice", "review_from": "review-slice"}),
            ("checkpoint", {"trigger": "on-concerns"}),
        ]


class TestGateStepTypeValidateOwnConfig:
    """Own-config validation only: presence/type. Cross-step existence is the
    loader's job (see TestValidatePipelineGateReferences)."""

    def test_valid_config(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"judge_from": "judge-slice", "review_from": "review-slice"})
        assert GateStepType().validate(step) == []

    def test_missing_judge_from(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"review_from": "review-slice"})
        errors = GateStepType().validate(step)
        assert any(e.field == "judge_from" for e in errors)

    def test_missing_review_from(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"judge_from": "judge-slice"})
        errors = GateStepType().validate(step)
        assert any(e.field == "review_from" for e in errors)

    def test_non_string_judge_from(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"judge_from": 123, "review_from": "review-slice"})
        errors = GateStepType().validate(step)
        assert any(e.field == "judge_from" for e in errors)

    def test_invalid_policy(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "policy": "bogus",
            }
        )
        errors = GateStepType().validate(step)
        assert any(e.field == "policy" for e in errors)

    def test_valid_policy(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "policy": "most-severe",
            }
        )
        assert GateStepType().validate(step) == []

    def test_invalid_checkpoint_trigger(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "checkpoint": "bogus",
            }
        )
        errors = GateStepType().validate(step)
        assert any(e.field == "checkpoint" for e in errors)


# ---------------------------------------------------------------------------
# T7b/T8 — loader cross-step validation of judge_from/review_from (F005)
# ---------------------------------------------------------------------------


class TestValidatePipelineGateReferences:
    """validate_pipeline() catches a gate naming a nonexistent or later step
    at load time — distinct from GateAction's execute-time UNKNOWN fallback."""

    def _make_pipeline(
        self, steps: list[StepConfig], params: dict[str, object] | None = None
    ) -> PipelineDefinition:
        return PipelineDefinition(name="test", description="test", params=params or {}, steps=steps)

    def test_nonexistent_source_step_fails(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="gate",
                    name="compose-gate",
                    config={"judge_from": "does-not-exist", "review_from": "also-missing"},
                ),
            ]
        )
        errors = validate_pipeline(defn)
        fields = [e.field for e in errors]
        assert "steps[compose-gate].judge_from" in fields
        assert "steps[compose-gate].review_from" in fields

    def test_later_step_reference_fails(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="gate",
                    name="compose-gate",
                    config={"judge_from": "judge-slice", "review_from": "review-slice"},
                ),
                StepConfig(
                    step_type="review",
                    name="judge-slice",
                    config={"template": "judge.slice-vs-arch"},
                ),
                StepConfig(
                    step_type="review",
                    name="review-slice",
                    config={"template": "design"},
                ),
            ]
        )
        errors = validate_pipeline(defn)
        fields = [e.field for e in errors]
        # Both names exist in the pipeline but run AFTER the gate — still invalid.
        assert "steps[compose-gate].judge_from" in fields
        assert "steps[compose-gate].review_from" in fields

    def test_two_real_prior_steps_validates_clean(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="review",
                    name="judge-slice",
                    config={"template": "judge.slice-vs-arch"},
                ),
                StepConfig(
                    step_type="review",
                    name="review-slice",
                    config={"template": "design"},
                ),
                StepConfig(
                    step_type="gate",
                    name="compose-gate",
                    config={"judge_from": "judge-slice", "review_from": "review-slice"},
                ),
            ]
        )
        errors = validate_pipeline(defn)
        gate_errors = [e for e in errors if "compose-gate" in e.field]
        assert gate_errors == []

    def test_param_placeholder_source_skipped(self) -> None:
        """A {param} placeholder in judge_from/review_from is skipped at
        validation time, mirroring _validate_model_alias's placeholder skip."""
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="gate",
                    name="compose-gate",
                    config={"judge_from": "{judge_step}", "review_from": "{review_step}"},
                ),
            ],
            params={"judge_step": "judge-slice", "review_step": "review-slice"},
        )
        errors = validate_pipeline(defn)
        gate_errors = [e for e in errors if "compose-gate" in e.field]
        assert gate_errors == []
