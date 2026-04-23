"""Tests for CompactStepType (slice 169: compact action dispatch)."""

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


def test_validate_model_as_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": "haiku"}))
    assert errors == []


def test_validate_model_as_non_string() -> None:
    errors = CompactStepType().validate(_make_config({"model": 42}))
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_validate_instructions_as_string() -> None:
    errors = CompactStepType().validate(
        _make_config({"instructions": "keep recent work"})
    )
    assert errors == []


def test_validate_instructions_as_non_string() -> None:
    errors = CompactStepType().validate(_make_config({"instructions": 42}))
    assert len(errors) == 1
    assert errors[0].field == "instructions"


# --- expand() ---


def test_expand_empty_config_emits_compact() -> None:
    """expand() returns a compact action."""
    actions = CompactStepType().expand(_make_config({}))
    assert len(actions) == 1
    action_type, config = actions[0]
    assert action_type == "compact"
    assert config == {}


def test_expand_does_not_emit_summary_or_rotate() -> None:
    """compact step no longer delegates to summary with emit=[rotate]."""
    actions = CompactStepType().expand(_make_config({}))
    action_type, config = actions[0]
    assert action_type != "summary"
    assert "emit" not in config


def test_expand_passes_model() -> None:
    actions = CompactStepType().expand(_make_config({"model": "haiku"}))
    action_type, config = actions[0]
    assert action_type == "compact"
    assert config["model"] == "haiku"


def test_expand_passes_instructions() -> None:
    actions = CompactStepType().expand(
        _make_config({"instructions": "keep design section"})
    )
    action_type, config = actions[0]
    assert action_type == "compact"
    assert config["instructions"] == "keep design section"


def test_expand_passes_both_model_and_instructions() -> None:
    actions = CompactStepType().expand(
        _make_config({"model": "haiku", "instructions": "keep recent work verbatim"})
    )
    action_type, config = actions[0]
    assert action_type == "compact"
    assert config["model"] == "haiku"
    assert config["instructions"] == "keep recent work verbatim"


def test_expand_omits_unknown_keys() -> None:
    """Legacy fields (keep, summarize, template) are not forwarded."""
    actions = CompactStepType().expand(
        _make_config(
            {"model": "haiku", "keep": ["design"], "summarize": True, "template": "x"}
        )
    )
    _, config = actions[0]
    assert "keep" not in config
    assert "summarize" not in config
    assert "template" not in config
