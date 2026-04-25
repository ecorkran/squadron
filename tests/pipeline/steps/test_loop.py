"""Unit tests for LoopStepType — validation, expand, and registration."""

from __future__ import annotations

import squadron.pipeline.steps.loop  # noqa: F401 — trigger registration
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps import get_step_type
from squadron.pipeline.steps.loop import LoopStepType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="loop", name="test-loop", config=config)


def _make() -> LoopStepType:
    return LoopStepType()


def _fields(errors: list) -> list[str]:
    return [e.field for e in errors]


def _messages(errors: list) -> list[str]:
    return [e.message for e in errors]


# ---------------------------------------------------------------------------
# Task 5 — Validation rules
# ---------------------------------------------------------------------------


def test_missing_max_produces_error() -> None:
    errors = _make().validate(_step({"steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_not_int_produces_error() -> None:
    errors = _make().validate(_step({"max": "3", "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_zero_produces_error() -> None:
    errors = _make().validate(_step({"max": 0, "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_max_negative_produces_error() -> None:
    errors = _make().validate(_step({"max": -1, "steps": [{"review": {}}]}))
    assert "max" in _fields(errors)


def test_invalid_until_value_produces_error() -> None:
    errors = _make().validate(
        _step({"max": 3, "until": "never", "steps": [{"review": {}}]})
    )
    assert "until" in _fields(errors)
    assert any("never" in m for m in _messages(errors))


def test_invalid_on_exhaust_value_produces_error() -> None:
    errors = _make().validate(
        _step({"max": 3, "on_exhaust": "retry", "steps": [{"review": {}}]})
    )
    assert "on_exhaust" in _fields(errors)


def test_strategy_not_string_produces_error() -> None:
    errors = _make().validate(
        _step({"max": 3, "strategy": 42, "steps": [{"review": {}}]})
    )
    assert "strategy" in _fields(errors)


def test_missing_steps_produces_error() -> None:
    errors = _make().validate(_step({"max": 3}))
    assert "steps" in _fields(errors)


def test_steps_not_list_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "steps": "bad"}))
    assert "steps" in _fields(errors)


def test_steps_empty_list_produces_error() -> None:
    errors = _make().validate(_step({"max": 3, "steps": []}))
    assert "steps" in _fields(errors)


def test_inner_step_with_loop_subfield_produces_nested_loop_error() -> None:
    """Ban (a): inner step config carries a loop: sub-field."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "steps": [{"review": {"loop": {"max": 2}}}],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("loop:" in m and "sub-field" in m for m in _messages(errors))


def test_inner_step_with_loop_type_produces_nested_loop_error() -> None:
    """Ban (b): inner step type is loop."""
    errors = _make().validate(
        _step(
            {
                "max": 3,
                "steps": [{"loop": {"max": 2, "steps": [{"review": {}}]}}],
            }
        )
    )
    assert "steps" in _fields(errors)
    assert any("type 'loop'" in m for m in _messages(errors))


def test_valid_config_no_errors() -> None:
    """Minimal valid config — max, steps, no optional fields."""
    errors = _make().validate(_step({"max": 3, "steps": [{"review": {}}]}))
    assert errors == []


def test_valid_config_with_all_options_no_errors() -> None:
    """All optional fields with valid values produce zero errors."""
    errors = _make().validate(
        _step(
            {
                "max": 5,
                "until": "review.pass",
                "on_exhaust": "checkpoint",
                "strategy": "weighted-decay",
                "steps": [{"dispatch": {}}, {"review": {}}],
            }
        )
    )
    assert errors == []


# ---------------------------------------------------------------------------
# Task 6 — expand() and registration
# ---------------------------------------------------------------------------


def test_expand_returns_empty_list() -> None:
    result = _make().expand(_step({"max": 3, "steps": [{"review": {}}]}))
    assert result == []


def test_get_step_type_returns_loop_step_type_instance() -> None:
    impl = get_step_type("loop")
    assert isinstance(impl, LoopStepType)
