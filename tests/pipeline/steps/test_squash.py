"""Tests for SquashStepType (slice 948 D6)."""

from __future__ import annotations

import pytest

from squadron.pipeline.actions import ActionType
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.squash import SquashStepType


def _config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="squash", name="squash-0", config=config)


@pytest.mark.parametrize(
    "config",
    [
        {"subject": "design"},
        {"subject": "tasks", "slice": "{slice.index}"},
        {"subject": "architecture", "plan": "100"},
    ],
)
def test_valid_configs_pass(config: dict[str, object]) -> None:
    assert SquashStepType().validate(_config(config)) == []


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"subject": "code"},
        {"subject": "architecture"},
        {"subject": "design", "plan": "100"},
        {"subject": "design", "colour": "blue"},
    ],
)
def test_invalid_configs_give_one_error(config: dict[str, object]) -> None:
    assert len(SquashStepType().validate(_config(config))) == 1


def test_design_expands_to_one_action_with_the_default_slice() -> None:
    actions = SquashStepType().expand(_config({"subject": "design"}))
    assert actions == [(ActionType.SQUASH, {"subject": "design", "slice": "{slice}"})]


def test_architecture_gets_no_slice() -> None:
    actions = SquashStepType().expand(_config({"subject": "architecture", "plan": "100"}))
    assert actions == [(ActionType.SQUASH, {"subject": "architecture", "plan": "100"})]
