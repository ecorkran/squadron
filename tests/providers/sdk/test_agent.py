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
    async def test_json_decode_error(self, query_agent: ClaudeSDKAgent, input_message: Message) -> None:
        gen = _make_error_gen(CLIJSONDecodeError("bad json", ValueError("oops")))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed

    @pytest.mark.asyncio
    async def test_base_sdk_error(self, query_agent: ClaudeSDKAgent, input_message: Message) -> None:
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
    async def test_shutdown_without_client_is_safe(self, client_agent: ClaudeSDKAgent) -> None:
        await client_agent.shutdown()
        assert client_agent.state == AgentState.terminated


# ---------------------------------------------------------------------------
# Unparseable-message tolerance
# ---------------------------------------------------------------------------


class TestUnparseableMessages:
    """The bundled CLI may emit message types the installed SDK cannot parse.

    The SDK's parser raises on any unrecognized type, which previously
    killed a working run — an audit was lost to a message that carried no
    failure at all. Note that ``rate_limit_event`` is deliberately NOT
    skipped: it means real throttling and must reach the backoff path.

    Skipping in place matters more than it looks: both handlers retry the
    *whole query*, so treating this as retryable would discard every tool
    call already made rather than continuing past a notice.
    """

    @pytest.mark.asyncio
    async def test_unparseable_message_does_not_kill_the_stream(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        from claude_agent_sdk._errors import MessageParseError

        async def gen(*, prompt: str, options: object = None) -> AsyncIterator[object]:
            yield AssistantMessage(content=[TextBlock(text="before")], model="claude")
            # An unknown *informational* type. Not a rate-limit notice: those
            # deliberately reach the backoff path instead of being skipped.
            raise MessageParseError("Unknown message type: telemetry_ping", {"type": "telemetry_ping"})

        with patch(_QUERY, side_effect=gen):
            messages = await _collect(query_agent.handle_message(input_message))

        # The prose emitted before the unparseable message survives, and the
        # run completes normally rather than raising.
        assert any("before" in msg.content for msg in messages)
        assert query_agent.state == AgentState.idle

    @pytest.mark.asyncio
    async def test_content_after_an_unparseable_message_still_arrives(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """The stream continues past the notice — this is the whole point."""
        from claude_agent_sdk._errors import MessageParseError

        class _Flaky:
            def __init__(self) -> None:
                self._step = 0

            def __aiter__(self) -> _Flaky:
                return self

            async def __anext__(self) -> object:
                self._step += 1
                if self._step == 1:
                    return AssistantMessage(content=[TextBlock(text="before")], model="claude")
                if self._step == 2:
                    raise MessageParseError("Unknown message type: telemetry_ping", {})
                if self._step == 3:
                    return AssistantMessage(content=[TextBlock(text="after")], model="claude")
                raise StopAsyncIteration

        def gen(*, prompt: str, options: object = None) -> _Flaky:
            return _Flaky()

        with patch(_QUERY, side_effect=gen):
            messages = await _collect(query_agent.handle_message(input_message))

        text = " ".join(msg.content for msg in messages)
        assert "before" in text
        assert "after" in text, "work after the unparseable notice must not be lost"

    @pytest.mark.asyncio
    async def test_real_errors_still_propagate(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """Only parse failures are swallowed; genuine failures still raise."""
        gen = _make_error_gen(CLIConnectionError("connection lost"))
        with patch(_QUERY, side_effect=gen):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))
            assert query_agent.state == AgentState.failed


class TestRateLimitBackoff:
    """Rate-limit retries must wait, not hammer.

    The retry loops previously carried a comment claiming "the CLI handles
    the backoff delay" and slept for nothing — measured at 11 attempts in
    0.1ms. That does not survive a rate limit; it *causes* one.
    """

    def test_backoff_grows_exponentially_and_is_capped(self) -> None:
        from squadron.providers.sdk.rate_limit import (
            RATE_LIMIT_MAX_BACKOFF_S,
            rate_limit_backoff_s,
        )

        assert rate_limit_backoff_s(1) == 2.0
        assert rate_limit_backoff_s(2) == 4.0
        assert rate_limit_backoff_s(3) == 8.0
        assert rate_limit_backoff_s(20) == RATE_LIMIT_MAX_BACKOFF_S
        # An explicit cap overrides the default for heavier workloads.
        assert rate_limit_backoff_s(20, 120.0) == 120.0

    @pytest.mark.asyncio
    async def test_retries_actually_sleep(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """Each retry awaits a delay — asserted on the calls, not wall-clock."""
        from claude_agent_sdk import ClaudeSDKError

        slept: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        gen = _make_error_gen(ClaudeSDKError("rate_limit_event: slow down"))
        with (
            patch(_QUERY, side_effect=gen),
            patch("squadron.providers.sdk.agent.asyncio.sleep", fake_sleep),
        ):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))

        assert len(slept) == 10, "every retry must wait before re-issuing"
        assert slept[0] < slept[-1], "the delay must grow"
        assert sum(slept) > 60, "cumulative backoff must be meaningful, not token"

    @pytest.mark.asyncio
    async def test_budget_resets_when_work_comes_through(
        self, client_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """The budget bounds *consecutive* throttles, not throttles per run.

        Observed on a real audit: attempts climbed 1..8 of 10 across a single
        run while tool calls kept accumulating between them. The counter was
        initialised outside the loop and never reset, so a long run exhausted
        its budget while still making progress and lost completed work.

        Here every attempt delivers a message before throttling, so the run
        survives far more than ``max_rate_limit_retries`` throttles.
        """
        from claude_agent_sdk import ClaudeSDKError

        throttles = 0
        max_throttles = 25  # > the budget of 3 below

        async def receive_response() -> AsyncIterator[AssistantMessage]:
            nonlocal throttles
            yield AssistantMessage(content=[TextBlock(text="progress")], model="m")
            if throttles < max_throttles:
                throttles += 1
                raise ClaudeSDKError("rate_limit_event: slow down")

        async def no_sleep(seconds: float) -> None:
            return None

        class _FakeClient:
            async def connect(self) -> None:
                return None

            async def query(self, prompt: str) -> None:
                return None

            def receive_response(self) -> AsyncIterator[AssistantMessage]:
                return receive_response()

        client_agent._max_rate_limit_retries = 3  # pyright: ignore[reportPrivateUsage]

        with (
            patch(_CLIENT, return_value=_FakeClient()),
            patch("squadron.providers.sdk.agent.asyncio.sleep", no_sleep),
        ):
            messages = await _collect(client_agent.handle_message(input_message))

        assert throttles == max_throttles, "run must survive throttles beyond the budget"
        assert len(messages) == max_throttles + 1, "each attempt's work must reach the caller"
        assert client_agent.state == AgentState.idle

    def test_stats_summarize_cost_not_just_occurrence(self) -> None:
        """Per-event warnings say throttling happened, not what it cost."""
        from squadron.providers.sdk.rate_limit import RateLimitStats

        stats = RateLimitStats()
        assert stats.summary() == "", "a clean run reports nothing"

        stats.record(2.0)
        stats.record(60.0)
        assert stats.throttles == 2
        assert stats.waited_s == 62.0
        assert "2 rate-limit pauses" in stats.summary()
        assert "62s" in stats.summary()

    @pytest.mark.asyncio
    async def test_stats_accumulate_across_retries(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        from claude_agent_sdk import ClaudeSDKError

        async def no_sleep(seconds: float) -> None:
            return None

        gen = _make_error_gen(ClaudeSDKError("rate_limit_event: slow down"))
        with (
            patch(_QUERY, side_effect=gen),
            patch("squadron.providers.sdk.agent.asyncio.sleep", no_sleep),
        ):
            with pytest.raises(ProviderError):
                await _collect(query_agent.handle_message(input_message))

        assert query_agent.rate_limit_stats.throttles == 10
        assert query_agent.rate_limit_stats.waited_s > 60

    @pytest.mark.asyncio
    async def test_exhausted_rate_limit_raises_a_distinct_error(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """Callers must be able to tell throttling from a malformed run.

        A campaign should pause on this rather than burn its remaining work
        on requests that will fail the same way.
        """
        from claude_agent_sdk import ClaudeSDKError

        from squadron.providers.errors import ProviderRateLimitError

        async def no_sleep(seconds: float) -> None:
            return None

        gen = _make_error_gen(ClaudeSDKError("rate_limit_event: quota"))
        with (
            patch(_QUERY, side_effect=gen),
            patch("squadron.providers.sdk.agent.asyncio.sleep", no_sleep),
        ):
            with pytest.raises(ProviderRateLimitError):
                await _collect(query_agent.handle_message(input_message))

    @pytest.mark.asyncio
    async def test_a_rate_limit_notice_reaches_the_backoff_not_the_skip(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """Regression: the skip must not swallow the signal backoff needs.

        A rate_limit_event arrives as MessageParseError only because this
        SDK version lacks a case for it. Skipping it silently disabled the
        backoff entirely — the run continued into a stream that had stopped
        producing work, ended with ~70 bytes, and never waited once.
        """
        from claude_agent_sdk._errors import MessageParseError

        slept: list[float] = []

        async def fake_sleep(seconds: float) -> None:
            slept.append(seconds)

        async def gen(*, prompt: str, options: object = None) -> AsyncIterator[object]:
            raise MessageParseError("Unknown message type: rate_limit_event", {})
            yield  # pragma: no cover - unreachable, defines the generator

        with (
            patch(_QUERY, side_effect=gen),
            patch("squadron.providers.sdk.agent.asyncio.sleep", fake_sleep),
        ):
            from squadron.providers.errors import ProviderRateLimitError

            with pytest.raises(ProviderRateLimitError):
                await _collect(query_agent.handle_message(input_message))

        assert slept, "a rate-limit notice must trigger backoff, not be skipped"
        assert len(slept) == 10

    @pytest.mark.asyncio
    async def test_other_unknown_messages_are_still_skipped(
        self, query_agent: ClaudeSDKAgent, input_message: Message
    ) -> None:
        """The narrow skip still applies to genuinely uninteresting types."""
        from claude_agent_sdk._errors import MessageParseError

        class _Flaky:
            def __init__(self) -> None:
                self._step = 0

            def __aiter__(self) -> _Flaky:
                return self

            async def __anext__(self) -> object:
                self._step += 1
                if self._step == 1:
                    raise MessageParseError("Unknown message type: telemetry_ping", {})
                if self._step == 2:
                    return AssistantMessage(content=[TextBlock(text="work")], model="claude")
                raise StopAsyncIteration

        with patch(_QUERY, side_effect=lambda **_: _Flaky()):
            messages = await _collect(query_agent.handle_message(input_message))

        assert any("work" in msg.content for msg in messages)
