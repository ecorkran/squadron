"""Unit tests for DispatchStepType (T8 — slice 191)."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.dispatch import DispatchStepType


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="dispatch", name="test-dispatch", config=config)


def _make() -> DispatchStepType:
    return DispatchStepType()


def test_step_type_name() -> None:
    assert _make().step_type == "dispatch"


def test_expand_with_prompt_and_model() -> None:
    actions = _make().expand(_step({"prompt": "Do something.", "model": "haiku"}))
    assert actions == [("dispatch", {"prompt": "Do something.", "model": "haiku"})]


def test_expand_prompt_only() -> None:
    actions = _make().expand(_step({"prompt": "Do something."}))
    assert actions == [("dispatch", {"prompt": "Do something."})]
    # model key should be absent — not injected as None
    assert "model" not in actions[0][1]


def test_expand_empty_config() -> None:
    actions = _make().expand(_step({}))
    assert actions == [("dispatch", {})]


def test_validate_prompt_non_string() -> None:
    errors = _make().validate(_step({"prompt": 42}))
    assert len(errors) == 1
    assert errors[0].field == "prompt"


def test_validate_model_non_string() -> None:
    errors = _make().validate(_step({"model": 99}))
    assert len(errors) == 1
    assert errors[0].field == "model"


def test_validate_valid_config() -> None:
    errors = _make().validate(_step({"prompt": "Go.", "model": "haiku"}))
    assert errors == []


def test_validate_empty_config() -> None:
    errors = _make().validate(_step({}))
    assert errors == []
