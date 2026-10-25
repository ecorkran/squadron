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
        {"kind": "slice"},
        {"kind": "tasks", "index": "{slice.index}"},
        {"kind": "arch", "index": "100"},
        {"kind": "plan", "index": "{plan}"},
    ],
)
def test_valid_configs_pass(config: dict[str, object]) -> None:
    assert SquashStepType().validate(_config(config)) == []


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"kind": "code"},
        {"kind": "arch"},
        {"kind": "plan"},
        {"kind": "slice", "colour": "blue"},
    ],
)
def test_invalid_configs_give_one_error(config: dict[str, object]) -> None:
    assert len(SquashStepType().validate(_config(config))) == 1


def test_slice_expands_to_one_action_with_the_default_index() -> None:
    actions = SquashStepType().expand(_config({"kind": "slice"}))
    assert actions == [(ActionType.SQUASH, {"kind": "slice", "index": "{slice}"})]


def test_arch_gets_no_default_index() -> None:
    actions = SquashStepType().expand(_config({"kind": "arch", "index": "100"}))
    assert actions == [(ActionType.SQUASH, {"kind": "arch", "index": "100"})]
