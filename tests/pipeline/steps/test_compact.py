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


def test_validate_model_as_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": "haiku"}))
    assert errors == []


def test_validate_model_as_non_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": 42}))
    assert len(errors) == 1
    assert errors[0].field == "model"


# --- expand() ---


def test_compact_step_expands_to_summary_with_rotate() -> None:
    """expand() returns a summary action with emit=["rotate"]."""
    actions = CompactStepType().expand(_make_config({}))
    assert len(actions) == 1
    tup = actions[0]
    assert tup[0] == "summary"
    assert tup[1]["emit"] == ["rotate"]


def test_compact_step_passes_through_template_model_keep_summarize() -> None:
    """All four config fields pass through unchanged into the action config."""
    actions = CompactStepType().expand(
        _make_config(
            {
                "template": "custom",
                "model": "haiku",
                "keep": ["design", "tasks"],
                "summarize": True,
            }
        )
    )
    assert len(actions) == 1
    _, config = actions[0]
    assert config["template"] == "custom"
    assert config["model"] == "haiku"
    assert config["keep"] == ["design", "tasks"]
    assert config["summarize"] is True
    assert config["emit"] == ["rotate"]


def test_compact_step_with_no_model_emits_none() -> None:
    """When no model is specified, expanded config has model: None."""
    actions = CompactStepType().expand(_make_config({}))
    _, config = actions[0]
    assert config["model"] is None


def test_expand_with_keep_and_summarize() -> None:
    actions = CompactStepType().expand(
        _make_config({"keep": ["design", "tasks"], "summarize": True})
    )
    assert len(actions) == 1
    action_type, config = actions[0]
    assert action_type == "summary"
    assert config["keep"] == ["design", "tasks"]
    assert config["summarize"] is True
    assert config["model"] is None
    assert config["emit"] == ["rotate"]


def test_expand_empty_config() -> None:
    actions = CompactStepType().expand(_make_config({}))
    assert len(actions) == 1
    action_type, config = actions[0]
    assert action_type == "summary"
    assert config == {"model": None, "emit": ["rotate"]}


def test_expand_with_template() -> None:
    actions = CompactStepType().expand(_make_config({"template": "custom"}))
    assert len(actions) == 1
    action_type, config = actions[0]
    assert action_type == "summary"
    assert config["template"] == "custom"
    assert config["model"] is None
    assert config["emit"] == ["rotate"]


def test_expand_with_model() -> None:
    actions = CompactStepType().expand(_make_config({"model": "haiku"}))
    action_type, config = actions[0]
    assert action_type == "summary"
    assert config["model"] == "haiku"
    assert config["emit"] == ["rotate"]
