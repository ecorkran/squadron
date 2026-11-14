"""In-dispatch cost cap on the SDK path (slice 424, Task 10; design D9)."""

from __future__ import annotations

from itertools import count
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import ResultMessage

from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.control_params import RUN_MAX_COST
from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind, pauses_run
from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.run_spend import CostCap, remaining_budget
from squadron.pipeline.sdk_session import SDK_BUDGET_SUBTYPE, SDKExecutionSession
from squadron.pipeline.steps import register_step_type
from squadron.pipeline.usage_capture import UsageCapture
from squadron.providers.base import USAGE_KEY
from squadron.providers.errors import BudgetExhaustedError, ProviderAPIError
from tests.pipeline.conftest import ScriptedClient, scripted_session, usage_dict

_names = count()


def _result(subtype: str, *, is_error: bool = True) -> ResultMessage:
    return ResultMessage(
        subtype=subtype,
        duration_ms=1,
        duration_api_ms=1,
        is_error=is_error,
        num_turns=1,
        session_id="sess-1",
        result="stopped",
    )


async def _opened_options(**kwargs: object) -> object:
    from squadron.pipeline.sdk_session import open_pipeline_session

    client = MagicMock()
    client.connect = AsyncMock()
    with patch("squadron.pipeline.sdk_session.ClaudeSDKClient", return_value=client) as ctor:
        await open_pipeline_session(**kwargs)  # type: ignore[arg-type]
    return ctor.call_args.kwargs["options"]


@pytest.mark.asyncio
async def test_a_capped_session_carries_the_budget_in_its_options() -> None:
    options = await _opened_options(max_budget_usd=2.5)

    assert options.max_budget_usd == 2.5  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_an_uncapped_session_passes_no_budget() -> None:
    options = await _opened_options()

    assert options.max_budget_usd is None  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_a_budget_stop_result_raises_budget_exhausted() -> None:
    session = scripted_session(ScriptedClient([_result(SDK_BUDGET_SUBTYPE)]))

    with pytest.raises(BudgetExhaustedError, match="run's budget"):
        await session.dispatch("p")  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_another_error_subtype_is_a_plain_provider_error() -> None:
    session = scripted_session(ScriptedClient([_result("error_during_generation")]))

    with pytest.raises(ProviderAPIError, match="is_error=True") as raised:
        await session.dispatch("p")  # type: ignore[attr-defined]

    assert not isinstance(raised.value, BudgetExhaustedError)


def _dispatch_context(session: AsyncMock) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-haiku-4-5-20251001", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-haiku-4-5-20251001", None)
    return ActionContext(
        pipeline_name="p",
        run_id="run-abcdef12",
        params={"prompt": "do it"},
        step_name="implement",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        usage_capture=UsageCapture(set()),
        cwd="/tmp/test",
        sdk_session=session,
    )


@pytest.mark.asyncio
async def test_a_budget_stop_fails_the_dispatch_with_the_cost_cap_kind() -> None:
    session = AsyncMock(spec=SDKExecutionSession)
    session.dispatch = AsyncMock(side_effect=BudgetExhaustedError("stopped at budget"))
    session.effort = None

    result = await DispatchAction().execute(_dispatch_context(session))

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    assert not pauses_run(result.metadata)


@pytest.mark.asyncio
async def test_a_budget_stop_ends_the_run_failed_not_paused(tmp_path: Path) -> None:
    session = AsyncMock(spec=SDKExecutionSession)
    session.dispatch = AsyncMock(side_effect=BudgetExhaustedError("stopped at budget"))
    session.effort = None
    definition = PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[
            StepConfig(
                step_type="dispatch",
                name="work",
                config={"prompt": "do it", "model": "claude-haiku-4-5-20251001"},
            )
        ],
    )
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-haiku-4-5-20251001", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-haiku-4-5-20251001", None)

    result = await execute_pipeline(
        definition,
        {RUN_MAX_COST: 3.0},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd=str(tmp_path),
        sdk_session=session,  # type: ignore[arg-type]
    )

    assert result.status is ExecutionStatus.FAILED
    failed = result.step_results[0].action_results[-1]
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value


def test_remaining_budget_is_the_cap_less_spend() -> None:
    cap = CostCap(5.0, "--max-cost")

    assert remaining_budget(cap, 1.5) == pytest.approx(3.5)
    assert remaining_budget(None, 99.0) is None


@pytest.mark.parametrize("spent", [5.0, 7.25])
def test_no_budget_left_fails_naming_the_cap_and_the_spend(spent: float) -> None:
    with pytest.raises(BudgetExhaustedError) as raised:
        remaining_budget(CostCap(5.0, "--max-cost"), spent)

    message = str(raised.value)
    assert "--max-cost" in message
    assert "$5.00" in message
    assert f"${spent:.2f}" in message


@pytest.mark.asyncio
async def test_a_lazy_session_with_the_cap_spent_is_not_opened_and_fails_cost_cap(
    tmp_path: Path,
) -> None:
    """Spend exactly at the cap passes the after-action check; the next session must not open."""
    kind = f"_budget_step_{next(_names)}"
    step = MagicMock()
    step.expand.return_value = [("dispatch", {})]
    register_step_type(kind, step)

    async def execute(ctx: object) -> ActionResult:
        return ActionResult(
            success=True, action_type="dispatch", outputs={}, metadata={USAGE_KEY: usage_dict(1.0)}
        )

    action = MagicMock()
    action.execute = AsyncMock(side_effect=execute)
    definition = PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[StepConfig(step_type=kind, name=f"step-{i}", config={}) for i in range(2)],
    )
    connect = AsyncMock()
    # The first step is not an SDK step; the second is, so a lazy session would open there.
    candidates = iter([None, "sonnet"])

    with (
        patch(
            "squadron.pipeline.executor._step_sdk_candidate", side_effect=lambda *a: next(candidates)
        ),
        patch("squadron.pipeline.executor._connect_lazy_session", connect),
    ):
        result = await execute_pipeline(
            definition,
            {RUN_MAX_COST: 1.0},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            cwd=str(tmp_path),
            _action_registry={"dispatch": action},
        )

    connect.assert_not_called()
    assert result.status is ExecutionStatus.FAILED
    assert [r.step_name for r in result.step_results] == ["step-0", "step-1"]
    failed = result.step_results[1].action_results[0]
    assert failed.metadata[FAILURE_KIND_KEY] == FailureKind.COST_CAP.value
    assert failed.error is not None and "$1.00" in failed.error


@pytest.mark.asyncio
async def test_a_lazy_session_opens_with_the_remaining_cap(tmp_path: Path) -> None:
    kind = f"_budget_step_{next(_names)}"
    step = MagicMock()
    step.expand.return_value = [("dispatch", {})]
    register_step_type(kind, step)

    async def execute(ctx: object) -> ActionResult:
        return ActionResult(
            success=True, action_type="dispatch", outputs={}, metadata={USAGE_KEY: usage_dict(1.0)}
        )

    action = MagicMock()
    action.execute = AsyncMock(side_effect=execute)
    definition = PipelineDefinition(
        name="cap",
        description="test",
        params={},
        steps=[StepConfig(step_type=kind, name=f"step-{i}", config={}) for i in range(2)],
    )
    session = AsyncMock(spec=SDKExecutionSession)
    connect = AsyncMock(return_value=session)
    candidates = iter([None, "sonnet"])

    with (
        patch(
            "squadron.pipeline.executor._step_sdk_candidate", side_effect=lambda *a: next(candidates)
        ),
        patch("squadron.pipeline.executor._connect_lazy_session", connect),
    ):
        await execute_pipeline(
            definition,
            {RUN_MAX_COST: 4.0},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            cwd=str(tmp_path),
            _action_registry={"dispatch": action},
        )

    assert connect.await_args is not None
    assert connect.await_args.kwargs["max_budget_usd"] == pytest.approx(3.0)
