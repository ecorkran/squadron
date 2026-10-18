"""Usage records on dispatch steps (slice 175 D4–D7, #151, #154)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import Effort, Message
from squadron.core.usage import CostBasis, RunTelemetry, TokenUsage, UsageRecord
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.sdk_session import DispatchStalledError, SDKExecutionSession
from squadron.pipeline.sdk_turns import SessionReply
from squadron.pipeline.state import StateManager
from squadron.pipeline.usage_capture import UsageCapture
from squadron.providers.base import COST_USD_KEY, TURNS_KEY, USAGE_KEY
from squadron.providers.errors import ProviderAPIError
from tests.pipeline.actions.dispatch_helpers import make_agent_mock, make_context, make_registry
from tests.pipeline.actions.dispatch_helpers import openrouter_profile as _openrouter_profile

_P = "squadron.pipeline.actions.dispatch"
_USAGE_MOD = "squadron.pipeline.usage_capture"


def _one_shot_context(effort: Effort | None = Effort.low) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("gpt-x", "openrouter")
    resolver.resolve_full.return_value = ResolvedModel(
        "gpt-x", "openrouter", max_output_tokens=4096, effort=effort
    )
    return make_context(resolver=resolver, params={"prompt": "go", "profile": "openrouter"})


async def _run_one_shot(agent: AsyncMock, ctx: ActionContext) -> tuple[ActionResult, MagicMock]:
    registry = make_registry(agent)
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        return await DispatchAction().execute(ctx), registry


def _usage(result: ActionResult) -> UsageRecord:
    raw = result.metadata[USAGE_KEY]
    assert isinstance(raw, dict)
    return UsageRecord.from_dict(raw)  # pyright: ignore[reportUnknownArgumentType]


@pytest.mark.asyncio
async def test_one_shot_success_records_usage_and_sends_budget() -> None:
    metadata: dict[str, object] = {
        TURNS_KEY: 2,
        USAGE_KEY: TokenUsage(prompt=100, completion=10),
        COST_USD_KEY: 0.25,
    }

    result, registry = await _run_one_shot(
        make_agent_mock("done", metadata=metadata), _one_shot_context()
    )

    assert result.success
    record = _usage(result)
    assert (record.turns, record.cost_usd, record.cost_basis) == (2, 0.25, CostBasis.PROVIDER)
    assert record.usage == TokenUsage(prompt=100, completion=10)
    assert record.effort == "low"  # the openai provider applies effort
    assert record.duration_seconds is not None
    assert registry.spawn.call_args.args[0].max_output_tokens == 4096


@pytest.mark.asyncio
async def test_one_shot_provider_error_records_its_telemetry() -> None:
    raised = ProviderAPIError("boom", status_code=500)
    raised.telemetry = RunTelemetry(turns=1, usage=TokenUsage(prompt=40, completion=4))

    async def _handle(_msg: object) -> AsyncIterator[Message]:
        raise raised
        yield  # pragma: no cover - makes this an async generator

    agent = AsyncMock()
    agent.handle_message = _handle

    result, _ = await _run_one_shot(agent, _one_shot_context())

    assert result.success is False
    record = _usage(result)
    assert record.usage == TokenUsage(prompt=40, completion=4)
    assert record.duration_seconds is not None


@pytest.mark.asyncio
async def test_cancellation_propagates_and_writes_no_record() -> None:
    async def _handle(_msg: object) -> AsyncIterator[Message]:
        raise asyncio.CancelledError
        yield  # pragma: no cover - makes this an async generator

    agent = AsyncMock()
    agent.handle_message = _handle

    with pytest.raises(asyncio.CancelledError):
        await _run_one_shot(agent, _one_shot_context())


@pytest.mark.asyncio
async def test_capture_adds_no_state_saves() -> None:
    metadata: dict[str, object] = {TURNS_KEY: 1, USAGE_KEY: TokenUsage(prompt=1, completion=1)}

    with patch.object(StateManager, "_write_atomic") as write:
        result, _ = await _run_one_shot(make_agent_mock("done", metadata=metadata), _one_shot_context())

    assert USAGE_KEY in result.metadata
    write.assert_not_called()


def _session(reply: SessionReply | None = None) -> AsyncMock:
    session = AsyncMock(spec=SDKExecutionSession)
    session.current_model = None
    session.background_tasks_waited = 0
    session.background_tasks_stopped = 0
    session.background_shells_running = 0
    session.seeded = False
    session.setting_sources = None
    session.auto_memory = False
    if reply is not None:
        session.dispatch.return_value = reply
    return session


def _session_context(
    session: AsyncMock, *, effort: Effort | None = None, capture: UsageCapture | None = None
) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-x", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-x", None, effort=effort)
    overrides: dict[str, object] = {"resolver": resolver, "sdk_session": session}
    if capture is not None:
        overrides["usage_capture"] = capture
    return make_context(**overrides)


@pytest.mark.asyncio
async def test_session_success_records_reply_telemetry() -> None:
    telemetry = RunTelemetry(turns=5, usage=TokenUsage(prompt=500, completion=20), cost_usd=0.3)
    session = _session(SessionReply(text="done", telemetry=telemetry))

    result = await DispatchAction().execute(_session_context(session))

    record = _usage(result)
    assert (record.turns, record.cost_usd) == (5, 0.3)
    assert record.effort is None


@pytest.mark.asyncio
async def test_stall_with_failed_drain_records_partial(caplog: pytest.LogCaptureFixture) -> None:
    stalled = DispatchStalledError(1800, session_usable=False)
    stalled.telemetry = RunTelemetry(turns=1, usage=TokenUsage(prompt=10, completion=1))
    session = _session()
    session.dispatch.side_effect = stalled

    with caplog.at_level(logging.WARNING, logger=_USAGE_MOD):
        result = await DispatchAction().execute(_session_context(session))

    assert result.success is False
    assert result.metadata["stalled"] is True
    assert result.metadata[USAGE_KEY]["partial"] is True  # type: ignore[index]
    assert _usage(result).duration_seconds is not None
    assert any("interrupt drained no result" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_session_alias_effort_recorded_as_unsent_and_logged_once(
    caplog: pytest.LogCaptureFixture,
) -> None:
    capture = UsageCapture(set())
    reply = SessionReply(text="ok", telemetry=RunTelemetry(turns=1, usage=TokenUsage(prompt=1)))

    with caplog.at_level(logging.DEBUG, logger=_USAGE_MOD):
        results = [
            await DispatchAction().execute(
                _session_context(_session(reply), effort=Effort.high, capture=capture)
            )
            for _ in range(2)
        ]

    assert all(_usage(r).effort is None for r in results)
    assert len([r for r in caplog.records if "#216" in r.getMessage()]) == 1


@pytest.mark.asyncio
async def test_missing_capture_is_a_clear_error() -> None:
    session = _session(SessionReply(text="ok", telemetry=RunTelemetry()))
    ctx = _session_context(session)
    ctx.usage_capture = None

    result = await DispatchAction().execute(ctx)

    assert result.success is False
    assert result.error is not None and "usage capture" in result.error
