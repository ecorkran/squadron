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
# Slice 305 Part B — per-policy config surface
# ---------------------------------------------------------------------------


class TestFindingsAddressedConfigSurface:
    """findings-addressed declares review_from only; judge_from belongs to a
    policy with two verdict legs and is rejected here."""

    def test_review_from_only_validates(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"review_from": "fresh-review", "policy": "findings-addressed"})
        assert GateStepType().validate(step) == []

    def test_judge_from_is_rejected_naming_policy_and_field(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "judge_from": "judge-slice",
                "policy": "findings-addressed",
            }
        )
        errors = GateStepType().validate(step)
        judge_errors = [e for e in errors if e.field == "judge_from"]
        assert len(judge_errors) == 1
        assert "findings-addressed" in judge_errors[0].message

    def test_missing_review_from_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"policy": "findings-addressed"})
        errors = GateStepType().validate(step)
        assert any(e.field == "review_from" for e in errors)

    def test_most_severe_missing_judge_from_still_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"review_from": "review-slice", "policy": "most-severe"})
        errors = GateStepType().validate(step)
        assert any(e.field == "judge_from" for e in errors)


class TestGateJudgeBlock:
    def test_well_formed_judge_block_passes(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "policy": "findings-addressed",
                "judge": {"model": "sonnet"},
            }
        )
        assert GateStepType().validate(step) == []

    def test_non_mapping_judge_block_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "policy": "findings-addressed",
                "judge": "sonnet",
            }
        )
        errors = GateStepType().validate(step)
        assert any(e.field == "judge" for e in errors)

    def test_unknown_judge_key_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "policy": "findings-addressed",
                "judge": {"model": "sonnet", "temperature": "0.2"},
            }
        )
        errors = GateStepType().validate(step)
        assert any(e.field == "judge.temperature" for e in errors)

    def test_non_string_model_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "policy": "findings-addressed",
                "judge": {"model": 42},
            }
        )
        errors = GateStepType().validate(step)
        assert any(e.field == "judge.model" for e in errors)

    def test_judge_block_on_most_severe_errors(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "judge_from": "judge-slice",
                "review_from": "review-slice",
                "policy": "most-severe",
                "judge": {"model": "sonnet"},
            }
        )
        errors = GateStepType().validate(step)
        judge_errors = [e for e in errors if e.field == "judge"]
        assert len(judge_errors) == 1
        assert "most-severe" in judge_errors[0].message


class TestGateExpandPerPolicy:
    def test_findings_addressed_expands_without_judge_from(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"review_from": "fresh-review", "policy": "findings-addressed"})
        actions = GateStepType().expand(step)
        assert actions == [
            ("gate", {"review_from": "fresh-review", "policy": "findings-addressed"}),
        ]

    def test_findings_addressed_passes_judge_block_through(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config(
            {
                "review_from": "fresh-review",
                "policy": "findings-addressed",
                "judge": {"model": "sonnet"},
                "checkpoint": "on-concerns",
            }
        )
        actions = GateStepType().expand(step)
        assert actions == [
            (
                "gate",
                {
                    "review_from": "fresh-review",
                    "policy": "findings-addressed",
                    "judge": {"model": "sonnet"},
                },
            ),
            ("checkpoint", {"trigger": "on-concerns"}),
        ]

    def test_most_severe_expansion_unchanged(self) -> None:
        from squadron.pipeline.steps.gate import GateStepType

        step = _gate_step_config({"judge_from": "judge-slice", "review_from": "review-slice"})
        assert GateStepType().expand(step) == [
            ("gate", {"judge_from": "judge-slice", "review_from": "review-slice"}),
        ]


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

    def test_findings_addressed_review_from_is_checked(self) -> None:
        """A findings-addressed gate's review_from is resolved per its policy
        contract — not silently unchecked because judge_from is absent."""
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="review",
                    name="fresh-review",
                    config={"template": "design"},
                ),
                StepConfig(
                    step_type="gate",
                    name="settled",
                    config={"review_from": "frsh-review", "policy": "findings-addressed"},
                ),
            ]
        )
        errors = validate_pipeline(defn)
        assert "steps[settled].review_from" in [e.field for e in errors]

    def test_findings_addressed_prior_review_validates_clean(self) -> None:
        from squadron.pipeline.loader import validate_pipeline

        defn = self._make_pipeline(
            [
                StepConfig(
                    step_type="review",
                    name="fresh-review",
                    config={"template": "design"},
                ),
                StepConfig(
                    step_type="gate",
                    name="settled",
                    config={"review_from": "fresh-review", "policy": "findings-addressed"},
                ),
            ]
        )
        errors = validate_pipeline(defn)
        assert [e for e in errors if "settled" in e.field] == []

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
