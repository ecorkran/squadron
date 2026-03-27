"""Tests for ClaudeSDKAgent — query mode and client mode."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

import pytest
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKError,
    CLIConnectionError,
    CLIJSONDecodeError,
    CLINotFoundError,
    ProcessError,
    TextBlock,
)

from squadron.core.models import AgentState, Message, MessageType
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
)
from squadron.providers.sdk.agent import ClaudeSDKAgent

# Patch target for the SDK query function.
_QUERY = "squadron.providers.sdk.agent.sdk_query"
_CLIENT = "squadron.providers.sdk.agent.ClaudeSDKClient"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(permission_mode="acceptEdits")


@pytest.fixture
def query_agent(options: ClaudeAgentOptions) -> ClaudeSDKAgent:
    return ClaudeSDKAgent(name="query-bot", options=options, mode="query")


@pytest.fixture
def client_agent(options: ClaudeAgentOptions) -> ClaudeSDKAgent:
    return ClaudeSDKAgent(name="client-bot", options=options, mode="client")


@pytest.fixture
def input_message() -> Message:
    return Message(
        sender="user",
        recipients=["query-bot"],
        content="Review this code.",
    )


def _make_sdk_assistant(text: str) -> AssistantMessage:
    return AssistantMessage(
        content=[TextBlock(text=text)],
        model="claude-sonnet-4-20250514",
    )


async def _collect(ait: AsyncIterator[Message]) -> list[Message]:
    return [msg async for msg in ait]


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestProperties:
    def test_name(self, query_agent: ClaudeSDKAgent) -> None:
        assert query_agent.name == "query-bot"

    def test_agent_type(self, query_agent: ClaudeSDKAgent) -> None:
        assert query_agent.agent_type == "sdk"

    def test_initial_state(self, query_agent: ClaudeSDKAgent) -> None:
        assert query_agent.state == AgentState.idle


# ---------------------------------------------------------------------------
# Query mode — happy path
# ---------------------------------------------------------------------------


class TestQueryModeHappyPath:
    @pytest.mark.asyncio
    async def test_calls_query_with_prompt(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        async def mock_query(  # type: ignore[override]
            *, prompt: str, options: object = None
        ) -> AsyncIterator[AssistantMessage]:
            assert prompt == "Review this code."
            yield _make_sdk_assistant("Looks good.")

        with patch(_QUERY, side_effect=mock_query):
            msgs = await _collect(query_agent.handle_message(input_message))
            assert len(msgs) >= 1

    @pytest.mark.asyncio
    async def test_calls_query_with_options(
        self,
        query_agent: ClaudeSDKAgent,
        input_message: Message,
        options: ClaudeAgentOptions,
    ) -> None:
        captured_options = None

        async def mock_query(  # type: ignore[override]
            *, prompt: str, options: object = None
        ) -> AsyncIterator[AssistantMessage]:
            nonlocal captured_options
            captured_options = options
            yield _make_sdk_assistant("ok")

        with patch(_QUERY, side_effect=mock_query):
            await _collect(query_agent.handle_message(input_message))
            assert captured_options is not None
            assert captured_options.permission_mode == "acceptEdits"

    @pytest.mark.asyncio
    async def test_yields_translated_messages(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        async def mock_query(  # type: ignore[override]
            *, prompt: str, options: object = None
        ) -> AsyncIterator[AssistantMessage]:
            yield _make_sdk_assistant("Hello there.")

        with patch(_QUERY, side_effect=mock_query):
            msgs = await _collect(query_agent.handle_message(input_message))
            assert len(msgs) == 1
            assert msgs[0].sender == "query-bot"
            assert msgs[0].content == "Hello there."
            assert msgs[0].message_type == MessageType.chat

    @pytest.mark.asyncio
    async def test_state_idle_after_success(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        async def mock_query(  # type: ignore[override]
            *, prompt: str, options: object = None
        ) -> AsyncIterator[AssistantMessage]:
            yield _make_sdk_assistant("done")

        with patch(_QUERY, side_effect=mock_query):
            await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.idle

    @pytest.mark.asyncio
    async def test_state_processing_during_execution(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        observed_state: AgentState | None = None

        async def mock_query(  # type: ignore[override]
            *, prompt: str, options: object = None
        ) -> AsyncIterator[AssistantMessage]:
            nonlocal observed_state
            observed_state = query_agent.state
            yield _make_sdk_assistant("mid")

        with patch(_QUERY, side_effect=mock_query):
            await _collect(query_agent.handle_message(input_message))
            assert observed_state == AgentState.processing


# ---------------------------------------------------------------------------
# Query mode — error mapping
# ---------------------------------------------------------------------------


def _make_error_gen(exc: Exception):
    """Return an async generator that raises *exc* immediately."""

    async def gen(  # type: ignore[override]
        *, prompt: str, options: object = None
    ) -> AsyncIterator[AssistantMessage]:
        raise exc
        yield  # make it an async generator  # noqa: F401

    return gen


class TestQueryModeErrors:
    @pytest.mark.asyncio
    async def test_cli_not_found_raises_auth_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        gen = _make_error_gen(CLINotFoundError("not found"))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderAuthError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_process_error_raises_api_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        gen = _make_error_gen(ProcessError("exit failure", exit_code=1))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderAPIError) as exc_info:
                await _collect(query_agent.handle_message(input_message))
            assert exc_info.value.status_code == 1
            assert query_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_cli_connection_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        gen = _make_error_gen(CLIConnectionError("connection failed"))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_json_decode_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        gen = _make_error_gen(CLIJSONDecodeError("bad json", ValueError("oops")))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_base_sdk_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        gen = _make_error_gen(ClaudeSDKError("unknown"))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed


# ---------------------------------------------------------------------------
# Shutdown — query mode
# ---------------------------------------------------------------------------


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_sets_terminated(self, query_agent: ClaudeSDKAgent) -> None:
        await query_agent.shutdown()
        assert query_agent.state == AgentState.terminated

    @pytest.mark.asyncio
    async def test_shutdown_no_client_safe(self, query_agent: ClaudeSDKAgent) -> None:
        await query_agent.shutdown()


# ---------------------------------------------------------------------------
# Client mode — happy path
# ---------------------------------------------------------------------------


class TestClientModeHappyPath:
    @pytest.mark.asyncio
    async def test_first_message_creates_and_connects(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            yield _make_sdk_assistant("connected")

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client):
            msgs = await _collect(client_agent.handle_message(input_message))
            mock_client.connect.assert_awaited_once()
            mock_client.query.assert_awaited_once_with(prompt="Review this code.")
            assert len(msgs) == 1
            assert msgs[0].content == "connected"

    @pytest.mark.asyncio
    async def test_second_message_reuses_client(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            yield _make_sdk_assistant("reply")

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client) as mock_cls:
            await _collect(client_agent.handle_message(input_message))
            assert mock_cls.call_count == 1

            msg2 = Message(
                sender="user",
                recipients=["client-bot"],
                content="Next task",
            )
            await _collect(client_agent.handle_message(msg2))

            # Client was NOT recreated.
            assert mock_cls.call_count == 1
            # connect was only called once.
            assert mock_client.connect.await_count == 1
            # query was called twice (once per message).
            assert mock_client.query.await_count == 2

    @pytest.mark.asyncio
    async def test_yields_translated_messages(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            yield _make_sdk_assistant("Hello from client.")

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client):
            msgs = await _collect(client_agent.handle_message(input_message))
            assert msgs[0].sender == "client-bot"
            assert msgs[0].content == "Hello from client."

    @pytest.mark.asyncio
    async def test_state_idle_after_success(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            yield _make_sdk_assistant("done")

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client):
            await _collect(client_agent.handle_message(input_message))
            assert client_agent.state == AgentState.idle


# ---------------------------------------------------------------------------
# Client mode — error mapping
# ---------------------------------------------------------------------------


class TestClientModeErrors:
    @pytest.mark.asyncio
    async def test_connect_error_maps_correctly(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()
        mock_client.connect.side_effect = CLINotFoundError()

        with patch(_CLIENT, return_value=mock_client):
            with pytest.raises(ProviderAuthError):
                await _collect(client_agent.handle_message(input_message))
            assert client_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_receive_error_maps_correctly(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            raise CLIConnectionError("lost connection")
            yield  # noqa: F401

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client):
            with pytest.raises(ProviderError):
                await _collect(client_agent.handle_message(input_message))
            assert client_agent.state == AgentState.failed


# ---------------------------------------------------------------------------
# Client mode — shutdown
# ---------------------------------------------------------------------------


class TestClientShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_disconnects_client(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        mock_client = AsyncMock()

        async def mock_receive():
            yield _make_sdk_assistant("ok")

        mock_client.receive_response = mock_receive

        with patch(_CLIENT, return_value=mock_client):
            await _collect(client_agent.handle_message(input_message))
            await client_agent.shutdown()
            mock_client.disconnect.assert_awaited_once()
            assert client_agent.state == AgentState.terminated
            assert client_agent._client is None  # noqa: SLF001

    @pytest.mark.asyncio
    async def test_shutdown_without_client_is_safe(
        self, client_agent: ClaudeSDKAgent
    ) -> None:
        await client_agent.shutdown()
        assert client_agent.state == AgentState.terminated
