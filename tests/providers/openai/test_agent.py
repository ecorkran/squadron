"""Tests for providers/openai/agent.py."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import openai
import pytest
from openai import omit

from squadron.core.models import AgentState, Message, MessageType
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.openai.agent import OpenAICompatibleAgent
from squadron.tools.guidance import TOOL_USE_HEADING

from .conftest import text_chunk, tool_chunk

_MODEL = "gpt-4o-mini"


def _make_agent(
    name: str = "bot",
    model: str = _MODEL,
    system_prompt: str | None = None,
    client: Any = None,
) -> OpenAICompatibleAgent:
    if client is None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        client.close = AsyncMock()
    return OpenAICompatibleAgent(name=name, client=client, model=model, system_prompt=system_prompt)


def _async_stream(*chunks: Any) -> AsyncMock:
    """Return an AsyncMock whose __aiter__ yields the given chunks."""

    async def _gen() -> Any:
        for chunk in chunks:
            yield chunk

    mock = AsyncMock()
    mock.__aiter__ = lambda _: _gen()
    return mock


async def _collect(agent: OpenAICompatibleAgent, msg: Message) -> list[Message]:
    return [m async for m in agent.handle_message(msg)]


_USER_MSG = Message(sender="human", recipients=["bot"], content="hello")


class TestInitialState:
    def test_initial_state_is_idle(self) -> None:
        agent = _make_agent()
        assert agent.state == AgentState.idle

    def test_system_prompt_prepended_to_history(self) -> None:
        agent = _make_agent(system_prompt="Be helpful.")
        assert agent._history[0]["role"] == "system"  # pyright: ignore[reportPrivateUsage]
        assert agent._history[0]["content"] == "Be helpful."  # pyright: ignore[reportPrivateUsage]

    def test_no_system_prompt_history_empty(self) -> None:
        agent = _make_agent()
        assert agent._history == []  # pyright: ignore[reportPrivateUsage]


class TestHandleMessage:
    @pytest.mark.asyncio
    async def test_handle_message_appends_user_entry(self) -> None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("hi")))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        await _collect(agent, _USER_MSG)
        history = agent._history  # pyright: ignore[reportPrivateUsage]
        user_entries = [e for e in history if e["role"] == "user"]
        assert len(user_entries) == 1
        assert user_entries[0]["content"] == "hello"

    @pytest.mark.asyncio
    async def test_handle_message_appends_assistant_entry(self) -> None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("I'm fine")))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        await _collect(agent, _USER_MSG)
        history = agent._history  # pyright: ignore[reportPrivateUsage]
        asst_entries = [e for e in history if e["role"] == "assistant"]
        assert len(asst_entries) == 1
        assert "fine" in asst_entries[0]["content"]

    @pytest.mark.asyncio
    async def test_handle_message_yields_chat_message(self) -> None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("Hello!")))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        msgs = await _collect(agent, _USER_MSG)
        assert len(msgs) == 1
        assert msgs[0].message_type == MessageType.chat
        assert msgs[0].content == "Hello!"

    @pytest.mark.asyncio
    async def test_handle_message_multi_turn_history_grows(self) -> None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("resp")))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        await _collect(agent, _USER_MSG)
        await _collect(agent, _USER_MSG)
        history = agent._history  # pyright: ignore[reportPrivateUsage]
        assert len([e for e in history if e["role"] == "user"]) == 2
        assert len([e for e in history if e["role"] == "assistant"]) == 2

    @pytest.mark.asyncio
    async def test_handle_message_yields_system_for_tool_call(self) -> None:
        chunk = tool_chunk(0, "call_1", "search", '{"q": "hi"}')
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(chunk))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        msgs = await _collect(agent, _USER_MSG)
        assert len(msgs) == 1
        assert msgs[0].message_type == MessageType.system
        assert msgs[0].metadata["tool_name"] == "search"

    @pytest.mark.asyncio
    async def test_state_is_idle_after_success(self) -> None:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_async_stream(text_chunk("ok")))
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        await _collect(agent, _USER_MSG)
        assert agent.state == AgentState.idle


# ---------------------------------------------------------------------------
# Error mapping helpers
# ---------------------------------------------------------------------------


def _mock_response(status_code: int = 401) -> httpx.Response:
    return httpx.Response(status_code=status_code, request=httpx.Request("GET", "http://test"))


class TestErrorMapping:
    @pytest.mark.asyncio
    async def test_error_auth(self) -> None:
        exc = openai.AuthenticationError("bad key", response=_mock_response(401), body=None)
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=exc)
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        with pytest.raises(ProviderAuthError):
            await _collect(agent, _USER_MSG)
        assert agent.state == AgentState.idle

    @pytest.mark.asyncio
    async def test_error_rate_limit(self) -> None:
        exc = openai.RateLimitError("rate limited", response=_mock_response(429), body=None)
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=exc)
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        with pytest.raises(ProviderAPIError) as exc_info:
            await _collect(agent, _USER_MSG)
        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("error_cls", "status"),
        [(openai.BadRequestError, 400), (openai.InternalServerError, 503)],
        ids=["400-rejects-request", "503"],
    )
    async def test_error_api_status(self, error_cls: type[openai.APIStatusError], status: int) -> None:
        # 400 is D12's "backend rejects stream_options" row (slice 931): the request that
        # failed carried stream_options, and the rejection surfaces as ProviderAPIError.
        exc = error_cls("rejected", response=_mock_response(status), body=None)
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=exc)
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        with pytest.raises(ProviderAPIError) as exc_info:
            await _collect(agent, _USER_MSG)
        assert exc_info.value.status_code == status
        assert client.chat.completions.create.call_args.kwargs["stream_options"] == {
            "include_usage": True
        }
        assert exc_info.value.telemetry is not None

    @pytest.mark.asyncio
    async def test_error_connection(self) -> None:
        exc = openai.APIConnectionError(request=httpx.Request("GET", "http://test"))
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=exc)
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        with pytest.raises(ProviderError):
            await _collect(agent, _USER_MSG)

    @pytest.mark.asyncio
    async def test_error_timeout(self) -> None:
        exc = openai.APITimeoutError(request=httpx.Request("GET", "http://test"))
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=exc)
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        with pytest.raises(ProviderTimeoutError):
            await _collect(agent, _USER_MSG)


class TestShutdown:
    @pytest.mark.asyncio
    async def test_shutdown_closes_client_and_sets_terminated(self) -> None:
        client = MagicMock()
        client.close = AsyncMock()
        agent = _make_agent(client=client)
        await agent.shutdown()
        client.close.assert_called_once()
        assert agent.state == AgentState.terminated


class TestUnknownToolNamePolicy:
    """Slice 265 / design D3: an unknown tool name raises rather than being dropped.

    Before this, a template declaring Claude vocabulary (``Read``, ``Glob``, ``Grep``) had
    every name dropped by the registry lookup and the review ran tool-less while still
    reporting a verdict — issue #68. A raise makes the misconfiguration impossible to miss.
    """

    def _agent_with_tools(self, tools: list[str], cwd: str) -> OpenAICompatibleAgent:
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        client.close = AsyncMock()
        return OpenAICompatibleAgent(
            name="bot",
            client=client,
            model=_MODEL,
            system_prompt=None,
            allowed_tools=tools,
            cwd=cwd,
        )

    def test_unknown_tool_name_raises_provider_error(self, tmp_path: Any) -> None:
        with pytest.raises(ProviderError) as excinfo:
            self._agent_with_tools(["Read"], str(tmp_path))

        message = str(excinfo.value)
        assert "Read" in message
        # The registered-tool list travels with the error so the fix needs no second lookup.
        assert "read_file" in message

    def test_two_unknown_names_both_named_in_error(self, tmp_path: Any) -> None:
        with pytest.raises(ProviderError) as excinfo:
            self._agent_with_tools(["Glob", "read_file", "Grep"], str(tmp_path))

        message = str(excinfo.value)
        assert "Glob" in message
        assert "Grep" in message

    def test_known_tool_names_construct_successfully(self, tmp_path: Any) -> None:
        agent = self._agent_with_tools(["read_file", "list_files", "grep"], str(tmp_path))

        executors = agent._tool_executors  # pyright: ignore[reportPrivateUsage]
        assert sorted(executors) == ["grep", "list_files", "read_file"]


class TestToolUseGuidanceComposition:
    """Slice 267 SC1/SC2: the guidance block is composed once, at the agent.

    Composing here rather than at the four call sites (design D1) means no caller that
    passes tools can ship an agent without the discipline block.
    """

    def _agent(
        self,
        *,
        system_prompt: str | None,
        allowed_tools: list[str] | None,
        cwd: str | None = None,
        tools_suppressed_reason: str | None = None,
    ) -> OpenAICompatibleAgent:
        client = MagicMock()
        client.chat.completions.create = AsyncMock()
        client.close = AsyncMock()
        return OpenAICompatibleAgent(
            name="bot",
            client=client,
            model=_MODEL,
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            tools_suppressed_reason=tools_suppressed_reason,
            cwd=cwd,
        )

    def test_tools_append_block_after_instructions(self, tmp_path: Any) -> None:
        agent = self._agent(
            system_prompt="Be helpful.",
            allowed_tools=["read_file", "grep"],
            cwd=str(tmp_path),
        )

        content = agent._history[0]["content"]  # pyright: ignore[reportPrivateUsage]
        assert agent._history[0]["role"] == "system"  # pyright: ignore[reportPrivateUsage]
        assert content.startswith("Be helpful.")
        assert content.index("Be helpful.") < content.index(TOOL_USE_HEADING)
        assert "read_file" in content
        assert "grep" in content

    def test_suppressed_tools_leave_instructions_alone(self, tmp_path: Any) -> None:
        # A suppressed run reaches the agent with an empty allowed_tools plus a reason;
        # the block must not claim tools the agent does not hold.
        agent = self._agent(
            system_prompt="Be helpful.",
            allowed_tools=[],
            cwd=str(tmp_path),
            tools_suppressed_reason="run-suppressed",
        )

        content = agent._history[0]["content"]  # pyright: ignore[reportPrivateUsage]
        assert content == "Be helpful."

    def test_no_instructions_no_tools_leaves_history_empty(self) -> None:
        agent = self._agent(system_prompt=None, allowed_tools=None)

        assert agent._history == []  # pyright: ignore[reportPrivateUsage]

    def test_tools_without_instructions_make_the_block_the_whole_prompt(self, tmp_path: Any) -> None:
        agent = self._agent(system_prompt=None, allowed_tools=["read_file"], cwd=str(tmp_path))

        content = agent._history[0]["content"]  # pyright: ignore[reportPrivateUsage]
        assert content.startswith(TOOL_USE_HEADING)

    @pytest.mark.asyncio
    async def test_composition_survives_the_provider_plumbing(self, tmp_path: Any) -> None:
        """Through create_agent, not the constructor: the provider must pass tools too."""
        from squadron.core.models import AgentConfig
        from squadron.providers.openai.provider import OpenAICompatibleProvider

        config = AgentConfig(
            name="agent",
            agent_type="api",
            provider="openai",
            model=_MODEL,
            api_key="sk-config",
            instructions="Review the diff.",
            allowed_tools=["read_file"],
            cwd=str(tmp_path),
        )
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent = await OpenAICompatibleProvider().create_agent(config)

        content = agent._history[0]["content"]  # pyright: ignore[reportPrivateUsage]
        assert content.startswith("Review the diff.")
        assert TOOL_USE_HEADING in content
        assert "read_file" in content


class TestOutputBudget:
    """Slice 924 D4, D5: a configured budget rides every request; none sends omit."""

    @staticmethod
    def _client(*streams: AsyncMock) -> MagicMock:
        client = MagicMock()
        client.chat.completions.create = AsyncMock(side_effect=list(streams))
        client.close = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_budget_is_sent_on_every_turn_of_the_agentic_loop(self, tmp_path: Any) -> None:
        (tmp_path / "a.txt").write_text("A")
        client = self._client(
            _async_stream(tool_chunk(0, "c1", "read_file", '{"path": "a.txt"}')),
            _async_stream(text_chunk("done")),
        )
        agent = OpenAICompatibleAgent(
            name="bot",
            client=client,
            model=_MODEL,
            system_prompt=None,
            allowed_tools=["read_file"],
            cwd=str(tmp_path),
            max_output_tokens=4096,
        )

        await _collect(agent, _USER_MSG)

        calls = client.chat.completions.create.call_args_list
        assert len(calls) == 2
        assert all(call.kwargs["max_completion_tokens"] == 4096 for call in calls)
        assert all("max_tokens" not in call.kwargs for call in calls)

    @pytest.mark.asyncio
    async def test_no_budget_sends_omit(self) -> None:
        client = self._client(_async_stream(text_chunk("hi")))
        agent = _make_agent(client=client)

        await _collect(agent, _USER_MSG)

        assert client.chat.completions.create.call_args.kwargs["max_completion_tokens"] is omit
