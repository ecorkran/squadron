"""Tests for ReviewStepType."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.review import ReviewStepType


def _make_config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="review", name="test-step", config=config)


def test_step_type() -> None:
    assert ReviewStepType().step_type == "review"


# --- validate() ---


def test_validate_missing_template() -> None:
    errors = ReviewStepType().validate(_make_config({}))
    assert len(errors) == 1
    assert errors[0].field == "template"
    assert "required" in errors[0].message


def test_validate_valid_full_config() -> None:
    errors = ReviewStepType().validate(
        _make_config({"template": "code", "model": "opus", "checkpoint": "on-fail"})
    )
    assert errors == []


def test_validate_invalid_checkpoint() -> None:
    errors = ReviewStepType().validate(
        _make_config({"template": "code", "checkpoint": "invalid"})
    )
    assert len(errors) == 1
    assert errors[0].field == "checkpoint"


def test_validate_invalid_model() -> None:
    errors = ReviewStepType().validate(_make_config({"template": "code", "model": 123}))
    assert len(errors) == 1
    assert errors[0].field == "model"


# --- expand() ---


def test_expand_with_checkpoint() -> None:
    """Template + model + checkpoint produces 2-action sequence."""
    actions = ReviewStepType().expand(
        _make_config(
            {"template": "code", "model": "minimax2.7", "checkpoint": "on-fail"}
        )
    )

    assert len(actions) == 2
    assert actions[0] == ("review", {"template": "code", "model": "minimax2.7"})
    assert actions[1] == ("checkpoint", {"trigger": "on-fail"})


def test_expand_no_checkpoint() -> None:
    """Template only (no checkpoint) produces 1-action sequence."""
    actions = ReviewStepType().expand(_make_config({"template": "code"}))

    assert len(actions) == 1
    assert actions[0] == ("review", {"template": "code", "model": None})


def test_expand_model_none_when_not_in_config() -> None:
    actions = ReviewStepType().expand(_make_config({"template": "slice"}))
    review = actions[0]
    assert review[1]["model"] is None
