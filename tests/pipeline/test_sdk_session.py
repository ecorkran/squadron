"""Tests for SDKExecutionSession."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from claude_agent_sdk import ClaudeAgentOptions

from squadron.pipeline.sdk_session import SDKExecutionSession

_MOD = "squadron.pipeline.sdk_session"


def _make_client() -> AsyncMock:
    """Build a minimal AsyncMock for ClaudeSDKClient."""
    client = AsyncMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.set_model = AsyncMock()
    client.query = AsyncMock()
    client.receive_response = MagicMock()
    return client


def _make_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(cwd=".", permission_mode="bypassPermissions")


def _make_session(client: AsyncMock | None = None) -> SDKExecutionSession:
    return SDKExecutionSession(client=client or _make_client(), options=_make_options())


# ---------------------------------------------------------------------------
# connect / disconnect
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_calls_client_connect() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.connect()
    client.connect.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_calls_client_disconnect() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.disconnect()
    client.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_disconnect_handles_exception_gracefully() -> None:
    client = _make_client()
    client.disconnect.side_effect = RuntimeError("conn already closed")
    session = _make_session(client)
    # Should not raise
    await session.disconnect()


# ---------------------------------------------------------------------------
# set_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_model_calls_client_when_model_differs() -> None:
    client = _make_client()
    session = _make_session(client)
    await session.set_model("claude-haiku-4-5-20251001")
    client.set_model.assert_called_once_with("claude-haiku-4-5-20251001")
    assert session.current_model == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_set_model_skips_call_when_model_matches() -> None:
    client = _make_client()
    session = SDKExecutionSession(
        client=client,
        options=_make_options(),
        current_model="claude-haiku-4-5-20251001",
    )
    await session.set_model("claude-haiku-4-5-20251001")
    client.set_model.assert_not_called()


@pytest.mark.asyncio
async def test_set_model_updates_current_model() -> None:
    client = _make_client()
    session = SDKExecutionSession(
        client=client,
        options=_make_options(),
        current_model="claude-haiku-4-5-20251001",
    )
    await session.set_model("claude-sonnet-4-6")
    assert session.current_model == "claude-sonnet-4-6"
    client.set_model.assert_called_once_with("claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# dispatch
# ---------------------------------------------------------------------------


def _sdk_text_messages(*texts: str) -> AsyncMock:
    """Async generator that yields fake SDK messages converted via translate."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        for text in texts:
            msg = MagicMock(spec=AssistantMessage)
            block = MagicMock(spec=TextBlock)
            block.text = text
            msg.content = [block]
            yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


@pytest.mark.asyncio
async def test_dispatch_sends_query_and_collects_response() -> None:
    client = _make_client()
    session = _make_session(client)

    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        block = MagicMock(spec=TextBlock)
        block.text = "Hello world"
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("do something")

    client.query.assert_called_once_with("do something")
    assert "Hello world" in result


@pytest.mark.asyncio
async def test_dispatch_retries_on_rate_limit() -> None:
    from claude_agent_sdk import AssistantMessage, ClaudeSDKError, TextBlock

    client = _make_client()
    session = _make_session(client)

    call_count = 0

    async def _gen():  # type: ignore[return]
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise ClaudeSDKError("rate_limit_event")
        # Third call succeeds
        msg = MagicMock(spec=AssistantMessage)
        block = MagicMock(spec=TextBlock)
        block.text = "done"
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    client.receive_response.return_value = gen_mock

    result = await session.dispatch("test")
    assert "done" in result
    assert call_count == 3


@pytest.mark.asyncio
async def test_dispatch_raises_provider_auth_on_cli_not_found() -> None:
    from claude_agent_sdk import CLINotFoundError

    from squadron.providers.errors import ProviderAuthError

    client = _make_client()
    client.query.side_effect = CLINotFoundError("claude not found")
    session = _make_session(client)

    with pytest.raises(ProviderAuthError):
        await session.dispatch("test")


@pytest.mark.asyncio
async def test_dispatch_raises_provider_api_on_process_error() -> None:
    from claude_agent_sdk import ProcessError

    from squadron.providers.errors import ProviderAPIError

    client = _make_client()
    client.query.side_effect = ProcessError("process failed", exit_code=1)
    session = _make_session(client)

    with pytest.raises(ProviderAPIError):
        await session.dispatch("test")


# ---------------------------------------------------------------------------
# session_id capture
# ---------------------------------------------------------------------------


def _assistant_gen(text: str) -> MagicMock:
    """Yield only an AssistantMessage with the given text."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    async def _gen():  # type: ignore[return]
        msg = MagicMock(spec=AssistantMessage)
        block = MagicMock(spec=TextBlock)
        block.text = text
        msg.content = [block]
        yield msg

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


def _result_message_gen(text: str, session_id: str | None = "sess-1") -> MagicMock:
    """Yield only a ResultMessage so metadata (session_id) is captured
    without duplicating content from an AssistantMessage."""
    from claude_agent_sdk import ResultMessage

    async def _gen():  # type: ignore[return]
        result = ResultMessage(
            subtype="success",
            result=text,
            duration_ms=1,
            duration_api_ms=1,
            is_error=False,
            num_turns=1,
            session_id=session_id or "sess-1",
        )
        yield result

    gen_mock = MagicMock()
    gen_mock.__aiter__ = lambda self: _gen()
    return gen_mock


@pytest.mark.asyncio
async def test_dispatch_captures_session_id() -> None:
    client = _make_client()
    client.receive_response.return_value = _result_message_gen(
        "hi", session_id="sess-abc"
    )
    session = _make_session(client)
    await session.dispatch("hi")
    assert session.session_id == "sess-abc"


@pytest.mark.asyncio
async def test_dispatch_session_id_latest_wins() -> None:
    client = _make_client()
    client.receive_response.return_value = _result_message_gen(
        "one", session_id="sess-1"
    )
    session = _make_session(client)
    await session.dispatch("one")
    assert session.session_id == "sess-1"

    client.receive_response.return_value = _result_message_gen(
        "two", session_id="sess-2"
    )
    await session.dispatch("two")
    assert session.session_id == "sess-2"


# ---------------------------------------------------------------------------
# compact (session rotate)
# ---------------------------------------------------------------------------


class TestCompactSessionRotate:
    @pytest.mark.asyncio
    async def test_compact_without_summary_model_skips_initial_set_model(
        self,
    ) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new) as client_ctor:
            result = await session.compact(instructions="Keep X")

        assert result == "SUMMARY"
        old.set_model.assert_not_called()
        client_ctor.assert_called_once_with(options=session.options)
        old.disconnect.assert_called_once()
        new.connect.assert_called_once()
        assert session.client is new

    @pytest.mark.asyncio
    async def test_compact_with_summary_model_switches_first(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            await session.compact(instructions="Keep X", summary_model="haiku-id")

        old.set_model.assert_any_call("haiku-id")

    @pytest.mark.asyncio
    async def test_compact_restores_model_at_end(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            await session.compact(
                instructions="Keep X",
                summary_model="haiku-id",
                restore_model="sonnet-id",
            )

        new.set_model.assert_called_once_with("sonnet-id")
        assert session.current_model == "sonnet-id"

    @pytest.mark.asyncio
    async def test_compact_dispatches_instructions_then_summary(self) -> None:
        old = _make_client()
        old.receive_response.return_value = _result_message_gen("SUMMARY TEXT")
        new = _make_client()
        new.receive_response.return_value = _result_message_gen("ack")
        session = _make_session(old)

        with patch(f"{_MOD}.ClaudeSDKClient", return_value=new):
            result = await session.compact(instructions="Keep X")

        assert result == "SUMMARY TEXT"
        old.query.assert_called_once_with("Keep X")
        new.query.assert_called_once_with("SUMMARY TEXT")


# ---------------------------------------------------------------------------
# seed_context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seed_context_calls_dispatch_once() -> None:
    client = _make_client()
    client.receive_response.return_value = _result_message_gen("ack")
    session = _make_session(client)
    result = await session.seed_context("prior summary")
    assert result is None
    client.query.assert_called_once_with("prior summary")
