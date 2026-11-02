"""Tests for squadron.pipeline.models."""

import dataclasses

from squadron.pipeline.models import (
    ActionResult,
    PipelineDefinition,
    StepConfig,
    ValidationError,
    prior_output_key,
    results_for_step,
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


def test_action_result_score_fields_default_none() -> None:
    result = ActionResult(success=True, action_type="review", outputs={})
    assert result.score is None
    assert result.criteria is None
    assert result.provenance is None


def test_action_result_score_fields_round_trip() -> None:
    result = ActionResult(
        success=True,
        action_type="review",
        outputs={},
        score=87.5,
        criteria={"alignment": 90.0},
        provenance="judge",
    )
    assert result.score == 87.5
    assert result.criteria == {"alignment": 90.0}
    assert result.provenance == "judge"


def test_action_result_asdict_includes_score_fields() -> None:
    result = ActionResult(success=True, action_type="review", outputs={})
    d = dataclasses.asdict(result)
    assert {"score", "criteria", "provenance"} <= d.keys()


def _result(action_type: str, response: str) -> ActionResult:
    return ActionResult(success=True, action_type=action_type, outputs={"response": response})


def test_results_for_step_returns_the_steps_results_in_action_order() -> None:
    prior_outputs = {
        prior_output_key("ask", "dispatch", 1): _result("dispatch", "second"),
        prior_output_key("other", "dispatch", 0): _result("dispatch", "other"),
        prior_output_key("ask", "cf-op", 0): _result("cf-op", "first"),
    }
    found = results_for_step(prior_outputs, "ask")
    assert [r.outputs["response"] for r in found] == ["first", "second"]


def test_results_for_step_is_empty_for_an_unknown_step() -> None:
    prior_outputs = {prior_output_key("ask", "dispatch", 0): _result("dispatch", "x")}
    assert results_for_step(prior_outputs, "missing") == []


def test_results_for_step_does_not_match_a_longer_step_name() -> None:
    prior_outputs = {prior_output_key("ask-more", "dispatch", 0): _result("dispatch", "x")}
    assert results_for_step(prior_outputs, "ask") == []
