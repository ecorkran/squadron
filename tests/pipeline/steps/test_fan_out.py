"""Unit and integration tests for FanOutStepType and _execute_fan_out_step."""

from __future__ import annotations

import squadron.pipeline.steps.fan_out  # noqa: F401 — trigger registration
from squadron.pipeline.models import StepConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="fan_out", name="test-fan-out", config=config)


def _make() -> squadron.pipeline.steps.fan_out.FanOutStepType:
    return squadron.pipeline.steps.fan_out.FanOutStepType()


def _fields(errors: list) -> list[str]:
    return [e.field for e in errors]


# ---------------------------------------------------------------------------
# Task 10 — FanOutStepType validation
# ---------------------------------------------------------------------------


def test_missing_models_produces_error() -> None:
    errors = _make().validate(_step({"inner": {"dispatch": {"prompt": "hi"}}}))
    assert "models" in _fields(errors)


def test_missing_inner_produces_error() -> None:
    errors = _make().validate(_step({"models": ["opus", "sonnet"]}))
    assert "inner" in _fields(errors)


def test_nested_fan_out_inner_produces_error() -> None:
    cfg = {
        "models": ["opus", "sonnet"],
        "inner": {"fan_out": {"models": ["haiku"], "inner": {"dispatch": {}}}},
    }
    errors = _make().validate(_step(cfg))
    assert "inner" in _fields(errors)


def test_pool_ref_without_n_produces_error() -> None:
    cfg = {
        "models": "pool:review",
        "inner": {"dispatch": {"prompt": "hi"}},
    }
    errors = _make().validate(_step(cfg))
    assert "n" in _fields(errors)


def test_pool_ref_with_valid_n_no_error_for_n() -> None:
    cfg = {
        "models": "pool:review",
        "n": 3,
        "inner": {"dispatch": {"prompt": "hi"}},
    }
    errors = _make().validate(_step(cfg))
    assert "n" not in _fields(errors)


def test_unregistered_fan_in_produces_error() -> None:
    cfg = {
        "models": ["opus"],
        "inner": {"dispatch": {"prompt": "hi"}},
        "fan_in": "no_such_reducer",
    }
    errors = _make().validate(_step(cfg))
    assert "fan_in" in _fields(errors)


def test_valid_explicit_list_no_errors() -> None:
    cfg = {
        "models": ["opus", "sonnet"],
        "inner": {"dispatch": {"prompt": "hi"}},
    }
    errors = _make().validate(_step(cfg))
    assert errors == []
