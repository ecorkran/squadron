"""Tests for SummaryStepType (T11)."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.summary import SummaryStepType


def _make_config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="summary", name="test-step", config=config)


def _make_step() -> SummaryStepType:
    return SummaryStepType()


# ---------------------------------------------------------------------------
# step_type
# ---------------------------------------------------------------------------


def test_step_type() -> None:
    assert _make_step().step_type == "summary"


# ---------------------------------------------------------------------------
# validate()
# ---------------------------------------------------------------------------


def test_validate_empty_config() -> None:
    errors = _make_step().validate(_make_config({}))
    assert errors == []


def test_validate_valid_template() -> None:
    errors = _make_step().validate(_make_config({"template": "minimal-sdk"}))
    assert errors == []


def test_validate_template_non_string() -> None:
    errors = _make_step().validate(_make_config({"template": 42}))
    assert len(errors) == 1
    assert errors[0].field == "template"


def test_validate_model_non_string() -> None:
    errors = _make_step().validate(_make_config({"model": 42}))
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_validate_emit_unknown_kind() -> None:
    errors = _make_step().validate(_make_config({"emit": ["banana"]}))
    assert len(errors) == 1
    assert errors[0].field == "emit"
    assert "banana" in errors[0].message


def test_validate_checkpoint_always() -> None:
    errors = _make_step().validate(_make_config({"checkpoint": "always"}))
    assert errors == []


def test_validate_checkpoint_on_fail() -> None:
    errors = _make_step().validate(_make_config({"checkpoint": "on-fail"}))
    assert errors == []


def test_validate_checkpoint_invalid() -> None:
    errors = _make_step().validate(_make_config({"checkpoint": "nope"}))
    assert len(errors) == 1
    assert errors[0].field == "checkpoint"
    assert "nope" in errors[0].message


def test_validate_multiple_errors() -> None:
    errors = _make_step().validate(
        _make_config({"template": 42, "model": 99, "checkpoint": "bad"})
    )
    fields = {e.field for e in errors}
    assert fields == {"template", "model", "checkpoint"}


# ---------------------------------------------------------------------------
# expand()
# ---------------------------------------------------------------------------


def test_expand_template_only() -> None:
    actions = _make_step().expand(_make_config({"template": "minimal-sdk"}))
    assert actions == [("summary", {"template": "minimal-sdk"})]


def test_expand_with_model_and_emit() -> None:
    actions = _make_step().expand(
        _make_config(
            {
                "template": "minimal-sdk",
                "model": "haiku",
                "emit": ["stdout", "clipboard"],
            }
        )
    )
    assert len(actions) == 1
    action_type, action_config = actions[0]
    assert action_type == "summary"
    assert action_config["template"] == "minimal-sdk"
    assert action_config["model"] == "haiku"
    assert action_config["emit"] == ["stdout", "clipboard"]


def test_expand_with_checkpoint_always() -> None:
    actions = _make_step().expand(
        _make_config({"template": "minimal-sdk", "checkpoint": "always"})
    )
    assert len(actions) == 2
    assert actions[0][0] == "summary"
    assert actions[1] == ("checkpoint", {"trigger": "always"})


def test_expand_with_checkpoint_on_fail() -> None:
    actions = _make_step().expand(
        _make_config({"template": "minimal-sdk", "checkpoint": "on-fail"})
    )
    assert len(actions) == 2
    assert actions[1] == ("checkpoint", {"trigger": "on-fail"})


def test_expand_without_checkpoint_no_extra_action() -> None:
    actions = _make_step().expand(_make_config({"template": "minimal-sdk"}))
    assert len(actions) == 1
    assert actions[0][0] == "summary"


def test_expand_empty_config() -> None:
    actions = _make_step().expand(_make_config({}))
    assert actions == [("summary", {})]
