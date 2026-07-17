"""Tests for GateStepType (expansion, own-config validation) and the loader's
cross-step validation of judge_from/review_from (F005).
"""

from __future__ import annotations

from squadron.pipeline.models import PipelineDefinition, StepConfig

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
