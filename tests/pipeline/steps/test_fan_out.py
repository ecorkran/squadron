"""Unit and integration tests for FanOutStepType and _execute_fan_out_step."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import squadron.pipeline.steps.fan_out  # noqa: F401 — trigger registration
from squadron.pipeline.executor import (
    ExecutionStatus,
    StepResult,
    _execute_fan_out_step,
)
from squadron.pipeline.models import ActionResult, StepConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _step(config: dict[str, object]) -> StepConfig:
    return StepConfig(step_type="fan_out", name="test-fan-out", config=config)


def _make() -> squadron.pipeline.steps.fan_out.FanOutStepType:
    return squadron.pipeline.steps.fan_out.FanOutStepType()


def _fields(errors: list) -> list[str]:
    return [e.field for e in errors]


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


def _make_branch_result(
    step_name: str = "branch",
    status: ExecutionStatus = ExecutionStatus.COMPLETED,
    action_results: list[ActionResult] | None = None,
) -> StepResult:
    return StepResult(
        step_name=step_name,
        step_type="dispatch",
        status=status,
        action_results=action_results or [_make_action_result()],
    )


def _mock_resolver(model_id: str = "opus") -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, None)
    return resolver


def _mock_action(result: ActionResult) -> MagicMock:
    action = MagicMock()
    action.execute = AsyncMock(return_value=result)
    return action


def _dispatch_step_type() -> MagicMock:
    st = MagicMock()
    st.expand.return_value = [("dispatch", {"prompt": "hi"})]
    return st


def _make_fan_out_step(config: dict[str, object] | None = None) -> StepConfig:
    return StepConfig(
        step_type="fan_out",
        name="fan-step",
        config=config
        or {
            "models": ["opus", "sonnet"],
            "inner": {"dispatch": {"prompt": "hi"}},
        },
    )


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


# ---------------------------------------------------------------------------
# Task 13 — Executor integration tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_model_list_collect_result_completed() -> None:
    """Two models → both branches execute, collect reducer, COMPLETED."""
    dispatch_result = _make_action_result(success=True)
    action = _mock_action(dispatch_result)
    step = _make_fan_out_step(
        {
            "models": ["opus", "sonnet"],
            "inner": {"dispatch": {"prompt": "hi"}},
            "fan_in": "collect",
        }
    )

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.action_results) == 1
    branches = result.action_results[0].outputs.get("branches")
    assert isinstance(branches, list)
    assert len(branches) == 2  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_fan_in_omitted_uses_collect_reducer() -> None:
    """fan_in omitted → collect reducer used by default."""
    dispatch_result = _make_action_result(success=True)
    action = _mock_action(dispatch_result)
    step = _make_fan_out_step({"models": ["opus"], "inner": {"dispatch": {}}})

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert "branches" in result.action_results[0].outputs


@pytest.mark.asyncio
async def test_branch_returns_failed_step_result_is_failed() -> None:
    """Branch action returning success=False causes StepResult.FAILED."""
    fail_result = _make_action_result(success=False)
    action = _mock_action(fail_result)
    step = _make_fan_out_step({"models": ["opus", "sonnet"], "inner": {"dispatch": {}}})

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert result.status == ExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_branch_coroutine_raises_step_result_is_failed() -> None:
    """Branch coroutine raising an exception → asyncio.gather propagates, FAILED."""
    action = MagicMock()
    action.execute = AsyncMock(side_effect=RuntimeError("branch exploded"))
    step = _make_fan_out_step({"models": ["opus"], "inner": {"dispatch": {}}})

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert result.status == ExecutionStatus.FAILED


@pytest.mark.asyncio
async def test_first_pass_with_pass_branch_returns_pass_result() -> None:
    """fan_in=first_pass with one PASS branch → action result reflects PASS."""
    pass_result = _make_action_result(
        success=True, verdict="PASS", outputs={"answer": "yes"}
    )
    action = _mock_action(pass_result)
    step = _make_fan_out_step(
        {"models": ["opus"], "inner": {"dispatch": {}}, "fan_in": "first_pass"}
    )

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert result.action_results[0].verdict == "PASS"


@pytest.mark.asyncio
async def test_sdk_session_returns_failed_with_guard_message() -> None:
    """sdk_session not None → FAILED with exact guard message."""
    step = _make_fan_out_step()

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=_mock_resolver(),
        cf_client=MagicMock(),
        sdk_session=MagicMock(),  # non-None triggers guard
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: MagicMock(),
    )

    assert result.status == ExecutionStatus.FAILED
    assert result.error == (
        "fan_out is not supported inside an SDK session step; "
        "use profile-based dispatch"
    )


@pytest.mark.asyncio
async def test_pool_reference_calls_resolver_n_times() -> None:
    """models=pool:review, n=2 → resolver called twice; two branches execute."""
    dispatch_result = _make_action_result(success=True)
    action = _mock_action(dispatch_result)
    resolver = _mock_resolver("haiku")
    step = _make_fan_out_step(
        {"models": "pool:review", "n": 2, "inner": {"dispatch": {}}}
    )

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=resolver,
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: action,
    )

    assert resolver.resolve.call_count == 2
    assert result.status == ExecutionStatus.COMPLETED
    branches = result.action_results[0].outputs["branches"]
    assert len(branches) == 2  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_pool_reference_resolver_raises_model_pool_not_implemented() -> None:
    """Pool resolver raising ModelPoolNotImplemented → step returns FAILED."""
    from squadron.pipeline.resolver import ModelPoolNotImplemented

    resolver = MagicMock()
    resolver.resolve.side_effect = ModelPoolNotImplemented("no pool backend")

    step = _make_fan_out_step(
        {"models": "pool:review", "n": 2, "inner": {"dispatch": {}}}
    )

    result = await _execute_fan_out_step(
        step=step,
        resolved_config=step.config,
        step_index=0,
        merged_params={},
        prior_outputs={},
        pipeline_name="test",
        run_id="run1",
        cwd="/tmp",
        resolver=resolver,
        cf_client=MagicMock(),
        sdk_session=None,
        get_step_type_fn=lambda _: _dispatch_step_type(),
        get_action_fn=lambda _: MagicMock(),
    )

    assert result.status == ExecutionStatus.FAILED
    assert "no pool backend" in (result.error or "")
