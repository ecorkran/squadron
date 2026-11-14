"""Strict validation reports config keys a step type does not read (slice 949 D7, D8)."""

from __future__ import annotations

import pytest

import squadron.cli.commands.run  # noqa: F401  # registers step and action types
from squadron.pipeline.loader import validate_pipeline
from squadron.pipeline.models import PipelineDefinition, StepConfig

_UNKNOWN = {"colour": "red"}

# A minimal valid config for each step type (the body steps keep the containers valid).
_DISPATCH_BODY = {"dispatch": {"name": "inner", "prompt": "hello"}}
_VALID_CONFIGS: dict[str, dict[str, object]] = {
    "design": {"phase": 4},
    "tasks": {"phase": 5},
    "implement": {"phase": 6},
    "dispatch": {"prompt": "hello"},
    "review": {"template": "code"},
    "gate": {"policy": "most-severe", "judge_from": "j", "review_from": "r"},
    "summary": {"template": "minimal-sdk"},
    "compact": {},
    "devlog": {"mode": "auto"},
    "branch": {"op": "enter"},
    "fix": {"issue": "301", "commit-to": "target"},
    "loop": {"max": 2, "steps": [_DISPATCH_BODY]},
    "each": {"source": "cf.slices()", "as": "s", "steps": [_DISPATCH_BODY]},
    "fan_out": {"models": ["sonnet"], "inner": {"dispatch": {"prompt": "hello"}}},
}


def _definition(*steps: StepConfig) -> PipelineDefinition:
    return PipelineDefinition(name="t", description="t", params={}, steps=list(steps))


def _steps_for(step_type: str, config: dict[str, object]) -> list[StepConfig]:
    """The step under test, preceded by the steps a gate refers to."""
    prefix = [
        StepConfig(step_type="dispatch", name="j", config={"prompt": "x"}),
        StepConfig(step_type="dispatch", name="r", config={"prompt": "x"}),
    ]
    step = StepConfig(step_type=step_type, name="under-test", config=config)
    if step_type == "implement":  # branch rules: an implement step sits between enter and merge
        enter = StepConfig(step_type="branch", name="enter", config={"op": "enter"})
        merge = StepConfig(step_type="branch", name="merge", config={"op": "merge"})
        return [*prefix, enter, step, merge]
    return [*prefix, step]


def _unknown_key_fields(step_type: str, config: dict[str, object], *, strict: bool) -> list[str]:
    errors = validate_pipeline(_definition(*_steps_for(step_type, config)), strict=strict)
    return [e.field for e in errors if e.field.endswith(".colour")]


@pytest.mark.parametrize("step_type", sorted(_VALID_CONFIGS))
def test_valid_config_passes_strict(step_type: str) -> None:
    steps = _steps_for(step_type, _VALID_CONFIGS[step_type])
    assert validate_pipeline(_definition(*steps), strict=True) == []


@pytest.mark.parametrize("step_type", sorted(_VALID_CONFIGS))
def test_unknown_key_is_one_error_naming_the_step(step_type: str) -> None:
    config = {**_VALID_CONFIGS[step_type], **_UNKNOWN}
    assert _unknown_key_fields(step_type, config, strict=True) == ["steps[under-test].colour"]


def test_executor_keys_are_accepted_on_any_step() -> None:
    config = {"prompt": "hello", "step_model": "sonnet", "loop": {"max": 2}}
    steps = _steps_for("dispatch", config)
    assert validate_pipeline(_definition(*steps), strict=True) == []


@pytest.mark.parametrize("container", ["loop", "each"])
def test_unknown_key_in_a_container_body_names_the_nested_step(container: str) -> None:
    body = {"dispatch": {"name": "nested", "prompt": "hello", **_UNKNOWN}}
    config = {**_VALID_CONFIGS[container], "steps": [body]}
    assert _unknown_key_fields(container, config, strict=True) == ["steps[nested].colour"]


@pytest.mark.parametrize("step_type", sorted(_VALID_CONFIGS))
def test_plain_validation_ignores_unknown_keys(step_type: str) -> None:
    config = {**_VALID_CONFIGS[step_type], **_UNKNOWN}
    assert _unknown_key_fields(step_type, config, strict=False) == []


def test_unknown_key_in_a_fan_out_branch_step_names_the_nested_step() -> None:
    inner = {"dispatch": {"name": "branch-step", "prompt": "hello", **_UNKNOWN}}
    config = {**_VALID_CONFIGS["fan_out"], "inner": inner}
    assert _unknown_key_fields("fan_out", config, strict=True) == ["steps[branch-step].colour"]
