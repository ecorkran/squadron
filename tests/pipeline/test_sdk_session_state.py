"""Dispatch ends on the CLI's idle state (slice 947 D12, issue #239)."""

from __future__ import annotations

import logging
from unittest.mock import AsyncMock, patch

import pytest

from squadron.pipeline.sdk_turns import SESSION_STATE_ENV
from squadron.providers.errors import ProviderError
from tests.pipeline.conftest import (
    ScriptedClient,
    scripted_session,
    sdk_result,
    sdk_session_state,
    sdk_task_notification,
    sdk_task_started,
    sdk_text,
    typed_config,
)

_MOD = "squadron.pipeline.sdk_session"


async def _dispatch(client: ScriptedClient) -> str:
    session = scripted_session(client)
    return (await session.dispatch("p")).text  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_follow_up_turn_with_empty_ledger_is_not_the_end() -> None:
    """#239: both notices arrive before agent 2's follow-up result; agent 3's turn is still owed."""
    client = ScriptedClient(
        [
            sdk_task_started("t2", "local_agent"),
            sdk_task_started("t3", "local_agent"),
            sdk_session_state("running"),
            sdk_text("Spawned both."),
            sdk_result(),
        ],
        [
            sdk_task_notification("t2"),
            sdk_task_notification("t3"),
            sdk_text("Agent 2 done."),
            sdk_result(injected=True),  # ledger is empty here, but the CLI is still running
        ],
        [sdk_text("Agent 3 done."), sdk_result(injected=True)],
        [sdk_session_state("idle")],  # a read ends at each result, so idle opens the next
    )

    assert await _dispatch(client) == "Spawned both.\nAgent 2 done.\nAgent 3 done."
    assert client.receive_calls == 4


@pytest.mark.asyncio
async def test_idle_before_our_result_ends_the_dispatch_at_the_result() -> None:
    client = ScriptedClient(
        [sdk_session_state("running"), sdk_text("hello"), sdk_session_state("idle"), sdk_result()]
    )

    assert await _dispatch(client) == "hello"
    assert client.receive_calls == 1


@pytest.mark.asyncio
async def test_idle_after_our_result_ends_the_dispatch_without_another_result() -> None:
    client = ScriptedClient(
        [sdk_session_state("running"), sdk_text("hello"), sdk_result()],
        [sdk_session_state("idle")],
    )

    assert await _dispatch(client) == "hello"
    assert client.receive_calls == 2


@pytest.mark.asyncio
async def test_state_stuck_running_is_bounded_by_the_background_idle_timeout(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = ScriptedClient(
        [sdk_session_state("running"), sdk_text("hello"), sdk_result()],
        [0.15],  # silent past the idle bound
    )

    with (
        patch(f"{_MOD}.get_typed_config", return_value=0.05),
        caplog.at_level(logging.WARNING, logger=_MOD),
    ):
        text = await _dispatch(client)

    assert text == "hello"
    assert any("no activity" in r.getMessage() for r in caplog.records)


@pytest.mark.asyncio
async def test_stream_end_while_running_raises() -> None:
    client = ScriptedClient(
        [sdk_session_state("running"), sdk_text("hello"), sdk_result()],
        [],  # stream ends: the CLI never reports idle
    )

    with pytest.raises(
        ProviderError,
        match="stream ended after the dispatch's result, before the CLI reported idle.*'running'",
    ):
        await _dispatch(client)


@pytest.mark.asyncio
async def test_unknown_state_warns_once_and_does_not_end_the_dispatch(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = ScriptedClient(
        [
            sdk_session_state("sleeping"),
            sdk_text("hello"),
            sdk_session_state("sleeping"),
            sdk_result(),
        ],
        [sdk_session_state("idle")],
    )

    with caplog.at_level(logging.WARNING):
        text = await _dispatch(client)

    assert text == "hello"
    assert client.receive_calls == 2
    warnings = [r for r in caplog.records if "unknown state" in r.getMessage()]
    assert len(warnings) == 1


@pytest.mark.asyncio
async def test_open_pipeline_session_asks_the_cli_for_state_frames() -> None:
    from squadron.pipeline.sdk_session import open_pipeline_session

    with (
        patch(
            f"{_MOD}.get_typed_config",
            typed_config({"pipeline.auto_memory": False, "pipeline.user_settings": False}),
        ),
        patch(f"{_MOD}.ClaudeSDKClient", return_value=AsyncMock()) as ctor,
    ):
        await open_pipeline_session()

    env = ctor.call_args.kwargs["options"].env
    assert env[SESSION_STATE_ENV] == "1"
    assert env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] == "1"
