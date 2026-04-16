"""Unit tests for FanInReducer protocol and built-in reducers."""

from __future__ import annotations

import pytest

from squadron.pipeline.executor import ExecutionStatus, StepResult
from squadron.pipeline.intelligence.fan_in.protocol import FanInReducer
from squadron.pipeline.intelligence.fan_in.reducers import (
    CollectReducer,
    FirstPassReducer,
    get_reducer,
)
from squadron.pipeline.models import ActionResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_step_result(
    step_name: str = "branch",
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    action_results: list[ActionResult] | None = None,
) -> StepResult:
    return StepResult(
        step_name=step_name,
        step_type="dispatch",
        status=status,
        action_results=action_results or [],
    )


def _make_action_result(
    success: bool = True,
    verdict: str | None = None,
    outputs: dict[str, object] | None = None,
) -> ActionResult:
    return ActionResult(
        success=success,
        action_type="dispatch",
        outputs=outputs or {},
        verdict=verdict,
    )


# ---------------------------------------------------------------------------
# Task 4 — Protocol conformance
# ---------------------------------------------------------------------------


class _ConformingReducer:
    def reduce(self, branch_results, config):  # type: ignore[override]
        return None  # type: ignore[return-value]


class _NonConformingReducer:
    pass


def test_conforming_reducer_satisfies_protocol() -> None:
    assert isinstance(_ConformingReducer(), FanInReducer)


def test_non_conforming_reducer_fails_protocol() -> None:
    assert not isinstance(_NonConformingReducer(), FanInReducer)


# ---------------------------------------------------------------------------
# Task 6 — collect reducer
# ---------------------------------------------------------------------------


def test_collect_all_succeed_returns_success() -> None:
    results = [
        _make_step_result("b0", ExecutionStatus.COMPLETED, [_make_action_result(True)]),
        _make_step_result("b1", ExecutionStatus.COMPLETED, [_make_action_result(True)]),
    ]
    out = CollectReducer().reduce(results, {})
    assert out.success is True


def test_collect_one_fail_returns_failure() -> None:
    results = [
        _make_step_result("b0", ExecutionStatus.COMPLETED, [_make_action_result(True)]),
        _make_step_result("b1", ExecutionStatus.FAILED, [_make_action_result(False)]),
    ]
    out = CollectReducer().reduce(results, {})
    assert out.success is False


def test_collect_branches_count() -> None:
    results = [
        _make_step_result("b0", action_results=[_make_action_result()]),
        _make_step_result("b1", action_results=[_make_action_result()]),
        _make_step_result("b2", action_results=[_make_action_result()]),
    ]
    out = CollectReducer().reduce(results, {})
    assert len(out.outputs["branches"]) == 3  # type: ignore[arg-type]


def test_collect_branches_contain_expected_keys() -> None:
    results = [
        _make_step_result(
            "my-branch", action_results=[_make_action_result(verdict="PASS")]
        )
    ]
    out = CollectReducer().reduce(results, {})
    branch = out.outputs["branches"][0]  # type: ignore[index]
    assert "step_name" in branch  # type: ignore[operator]
    assert "status" in branch  # type: ignore[operator]
    assert "action_results" in branch  # type: ignore[operator]
    assert branch["step_name"] == "my-branch"  # type: ignore[index]


def test_collect_action_type_is_fan_out() -> None:
    out = CollectReducer().reduce([], {})
    assert out.action_type == "fan_out"


def test_get_reducer_collect_returns_collect_reducer() -> None:
    assert isinstance(get_reducer("collect"), CollectReducer)


def test_get_reducer_nonexistent_raises_key_error() -> None:
    with pytest.raises(KeyError):
        get_reducer("nonexistent")


# ---------------------------------------------------------------------------
# Task 8 — first_pass reducer
# ---------------------------------------------------------------------------


def test_first_pass_first_branch_pass_returned() -> None:
    results = [
        _make_step_result(
            "b0", action_results=[_make_action_result(verdict="PASS", outputs={"x": 1})]
        ),
        _make_step_result(
            "b1", action_results=[_make_action_result(verdict="FAIL", outputs={"x": 2})]
        ),
    ]
    out = FirstPassReducer().reduce(results, {})
    assert out.verdict == "PASS"
    assert out.outputs == {"x": 1}


def test_first_pass_second_branch_pass_returned() -> None:
    results = [
        _make_step_result(
            "b0", action_results=[_make_action_result(verdict="FAIL", outputs={"x": 1})]
        ),
        _make_step_result(
            "b1", action_results=[_make_action_result(verdict="PASS", outputs={"x": 2})]
        ),
    ]
    out = FirstPassReducer().reduce(results, {})
    assert out.verdict == "PASS"
    assert out.outputs == {"x": 2}


def test_first_pass_no_pass_returns_last_branch() -> None:
    results = [
        _make_step_result(
            "b0", action_results=[_make_action_result(verdict="FAIL", outputs={"x": 1})]
        ),
        _make_step_result(
            "b1", action_results=[_make_action_result(verdict="FAIL", outputs={"x": 2})]
        ),
    ]
    out = FirstPassReducer().reduce(results, {})
    assert out.outputs == {"x": 2}


def test_first_pass_success_always_true() -> None:
    results = [
        _make_step_result("b0", action_results=[_make_action_result(verdict="FAIL")]),
    ]
    out = FirstPassReducer().reduce(results, {})
    assert out.success is True


def test_get_reducer_first_pass_returns_instance() -> None:
    assert isinstance(get_reducer("first_pass"), FirstPassReducer)
