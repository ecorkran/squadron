"""Tests for BranchStepType (slice 196 D4)."""

from __future__ import annotations

import pytest

from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps.branch import BranchOp, BranchStepType


def _config(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="branch", name="branch-0", config=config)


def test_step_type() -> None:
    assert BranchStepType().step_type == "branch"


@pytest.mark.parametrize("op", ["enter", "merge"])
def test_valid_ops_pass_validation(op: str) -> None:
    assert BranchStepType().validate(_config({"op": op})) == []


def test_slice_is_accepted() -> None:
    assert BranchStepType().validate(_config({"op": "enter", "slice": "{slice.index}"})) == []


def test_missing_op_is_an_error() -> None:
    errors = BranchStepType().validate(_config({}))
    assert [e.field for e in errors] == ["op"]
    assert "'op' is required" in errors[0].message


def test_bad_op_value_is_an_error() -> None:
    errors = BranchStepType().validate(_config({"op": "rebase"}))
    assert [e.field for e in errors] == ["op"]
    assert "'rebase' is not a valid branch op" in errors[0].message


def test_unknown_keys_are_rejected() -> None:
    errors = BranchStepType().validate(_config({"op": "enter", "force": True, "mode": "x"}))
    assert [e.field for e in errors] == ["force", "mode"]


@pytest.mark.parametrize(
    ("config", "expected_slice"),
    [({"op": "enter"}, "{slice}"), ({"op": "merge", "slice": "{slice.index}"}, "{slice.index}")],
)
def test_expands_to_one_branch_action(config: dict[str, object], expected_slice: str) -> None:
    actions = BranchStepType().expand(_config(config))
    assert actions == [("branch", {"op": BranchOp(str(config["op"])), "slice": expected_slice})]
