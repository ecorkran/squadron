"""Tests for squadron.pipeline.loader.validate_pipeline — semantic validation."""

from __future__ import annotations

from pathlib import Path

from squadron.pipeline.loader import load_pipeline, validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig


def _make_definition(
    *,
    name: str = "test",
    steps: list[StepConfig] | None = None,
    params: dict[str, object] | None = None,
    model: str | None = None,
) -> PipelineDefinition:
    """Build a PipelineDefinition for testing."""
    return PipelineDefinition(
        name=name,
        description="",
        params=params or {},
        steps=steps or [],
        model=model,
    )


class TestValidateBuiltIns:
    """Built-in pipelines should validate cleanly."""

    def test_slice_lifecycle_valid(self) -> None:
        defn = load_pipeline(
            "slice",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        errors = validate_pipeline(defn)
        assert errors == []

    def test_review_only_valid(self) -> None:
        defn = load_pipeline(
            "review",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        errors = validate_pipeline(defn)
        assert errors == []

    def test_implementation_only_valid(self) -> None:
        defn = load_pipeline(
            "implement",
            project_dir=Path("/nonexistent"),
            user_dir=Path("/nonexistent"),
        )
        errors = validate_pipeline(defn)
        assert errors == []


class TestUnknownStepType:
    """Unknown step types produce validation errors."""

    def test_unknown_step_type(self) -> None:
        defn = _make_definition(
            steps=[StepConfig(step_type="nonexistent", name="s0", config={})],
        )
        errors = validate_pipeline(defn)
        step_type_errors = [e for e in errors if e.field == "step_type"]
        assert len(step_type_errors) == 1
        assert "nonexistent" in step_type_errors[0].message


class TestModelAliasValidation:
    """Model alias resolution validation."""

    def test_invalid_model_alias(self) -> None:
        defn = _make_definition(model="not-a-real-alias-xyz")
        errors = validate_pipeline(defn)
        model_errors = [e for e in errors if e.field == "model"]
        assert len(model_errors) == 1
        assert "not-a-real-alias-xyz" in model_errors[0].message

    def test_valid_model_alias_no_error(self) -> None:
        defn = _make_definition(model="opus")
        errors = validate_pipeline(defn)
        model_errors = [e for e in errors if e.field == "model"]
        assert len(model_errors) == 0


class TestReviewTemplateValidation:
    """Review template reference validation."""

    def test_missing_review_template(self) -> None:
        """A step with a review template ref that doesn't exist produces error."""
        defn = _make_definition(
            steps=[
                StepConfig(
                    step_type="design",
                    name="d0",
                    config={"review": "nonexistent-template-xyz"},
                ),
            ],
        )
        errors = validate_pipeline(defn)
        template_errors = [e for e in errors if "template" in e.field]
        assert len(template_errors) >= 1
        assert "nonexistent-template-xyz" in template_errors[0].message


class TestParamPlaceholderValidation:
    """Param placeholder reference validation."""

    def test_undeclared_param_produces_error(self) -> None:
        defn = _make_definition(
            steps=[
                StepConfig(
                    step_type="design",
                    name="d0",
                    config={"template": "{undeclared}"},
                ),
            ],
        )
        errors = validate_pipeline(defn)
        param_errors = [e for e in errors if "undeclared" in e.message]
        assert len(param_errors) >= 1

    def test_declared_param_no_error(self) -> None:
        defn = _make_definition(
            params={"slice": "required"},
            steps=[
                StepConfig(
                    step_type="design",
                    name="d0",
                    config={"target": "{slice}"},
                ),
            ],
        )
        errors = validate_pipeline(defn)
        param_errors = [e for e in errors if "placeholder" in e.message]
        assert len(param_errors) == 0
