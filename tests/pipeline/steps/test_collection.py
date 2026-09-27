"""Unit tests for EachStepType validation (slice 195 D3, D5)."""

from __future__ import annotations

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import bootstrap_step_types
from squadron.pipeline.steps.collection import EachStepType

bootstrap_step_types()


def _each(steps: list[object], **extra: object) -> StepConfig:
    return StepConfig(
        step_type="each",
        name="slices",
        config={"source": 'cf.undesigned_slices("900")', "as": "slice", "steps": steps, **extra},
    )


def _validate(config: StepConfig) -> list[ValidationError]:
    return EachStepType().validate(config)


def test_valid_body_has_no_errors() -> None:
    body: list[object] = [
        {"design": {"phase": 4, "plan": "{plan}", "slice": "{slice.index}"}},
        {"loop": {"max": 2, "until": "review.pass", "steps": [{"review": {"template": "slice"}}]}},
    ]
    assert _validate(_each(body, on_item_failure="continue")) == []


def test_nested_each_is_rejected() -> None:
    inner = {
        "each": {"source": "cf.unfinished_slices()", "as": "x", "steps": [{"design": {"phase": 4}}]}
    }
    errors = _validate(_each([inner]))
    assert any("type 'each'" in e.message for e in errors)


def test_inner_step_errors_surface() -> None:
    # A design step without phase fails PhaseStepType.validate; each reports it.
    errors = _validate(_each([{"design": {"model": "opus"}}]))
    assert [e.field for e in errors] == ["phase"]


def test_unknown_inner_step_type_is_reported() -> None:
    errors = _validate(_each([{"no_such_step": {}}]))
    assert any("no_such_step" in e.message for e in errors)


def test_bad_on_item_failure_is_rejected() -> None:
    errors = _validate(_each([{"design": {"phase": 4}}], on_item_failure="skip"))
    assert [e.field for e in errors] == ["on_item_failure"]
