"""Tests for CompactStepType."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.compact import CompactStepType


def _make_config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="compact", name="test-step", config=config)


def test_step_type() -> None:
    assert CompactStepType().step_type == "compact"


# --- validate() ---


def test_validate_empty_config() -> None:
    errors = CompactStepType().validate(_make_config({}))
    assert errors == []


def test_validate_keep_as_non_list() -> None:
    errors = CompactStepType().validate(_make_config({"keep": "design"}))
    assert len(errors) == 1
    assert errors[0].field == "keep"


def test_validate_keep_as_list_of_strings() -> None:
    errors = CompactStepType().validate(_make_config({"keep": ["design", "tasks"]}))
    assert errors == []


def test_validate_summarize_as_non_bool() -> None:
    errors = CompactStepType().validate(_make_config({"summarize": "yes"}))
    assert len(errors) == 1
    assert errors[0].field == "summarize"


# --- expand() ---


def test_expand_with_keep_and_summarize() -> None:
    actions = CompactStepType().expand(
        _make_config({"keep": ["design", "tasks"], "summarize": True})
    )
    assert len(actions) == 1
    assert actions[0] == (
        "compact",
        {"keep": ["design", "tasks"], "summarize": True, "model": None},
    )


def test_expand_empty_config() -> None:
    actions = CompactStepType().expand(_make_config({}))
    assert len(actions) == 1
    assert actions[0] == ("compact", {"model": None})


def test_expand_with_template() -> None:
    actions = CompactStepType().expand(_make_config({"template": "custom"}))
    assert len(actions) == 1
    assert actions[0] == ("compact", {"template": "custom", "model": None})


def test_validate_model_as_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": "haiku"}))
    assert errors == []


def test_validate_model_as_non_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": 42}))
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_expand_with_model() -> None:
    actions = CompactStepType().expand(_make_config({"model": "haiku"}))
    assert actions[0] == ("compact", {"model": "haiku"})
