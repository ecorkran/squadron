"""Tests for squadron.pipeline.models."""

from squadron.pipeline.models import (
    ActionResult,
    PipelineDefinition,
    StepConfig,
    ValidationError,
)


def test_validation_error_fields() -> None:
    err = ValidationError(field="model", message="required", action_type="dispatch")
    assert err.field == "model"
    assert err.message == "required"
    assert err.action_type == "dispatch"


def test_action_result_defaults() -> None:
    result = ActionResult(success=True, action_type="test", outputs={})
    assert result.error is None
    assert result.verdict is None
    assert result.findings == []
    assert result.metadata == {}


def test_action_result_failure() -> None:
    result = ActionResult(
        success=False,
        action_type="dispatch",
        outputs={},
        error="oops",
    )
    assert result.success is False
    assert result.error == "oops"
    assert result.action_type == "dispatch"


def test_step_config_fields() -> None:
    step = StepConfig(
        step_type="phase",
        name="implement",
        config={"model": "sonnet"},
    )
    assert step.step_type == "phase"
    assert step.name == "implement"
    assert step.config == {"model": "sonnet"}


def test_pipeline_definition_model_default() -> None:
    pipeline = PipelineDefinition(
        name="my-pipeline",
        description="test pipeline",
        params={},
        steps=[],
    )
    assert pipeline.model is None


def test_pipeline_definition_with_model() -> None:
    pipeline = PipelineDefinition(
        name="my-pipeline",
        description="test pipeline",
        params={},
        steps=[],
        model="sonnet",
    )
    assert pipeline.model == "sonnet"
