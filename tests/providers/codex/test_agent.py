"""Tests for CodexAgent — MCP transport path."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.errors import ProviderError


@pytest.fixture()
def agent_config() -> AgentConfig:
    return AgentConfig(
        name="test-codex",
        agent_type="codex",
        provider="codex",
        model="gpt-5.3-codex",
        cwd="/tmp/test-project",
    )


@pytest.fixture()
def agent(agent_config: AgentConfig) -> CodexAgent:
    return CodexAgent(name="test-codex", config=agent_config)


def _make_message(content: str = "hello") -> Message:
    return Message(
        sender="user",
        recipients=["test-codex"],
        content=content,
        message_type=MessageType.chat,
    )


def _mock_call_tool_result(
    text: str = "Codex response",
    *,
    is_error: bool = False,
    thread_id: str | None = "thread-abc-123",
) -> MagicMock:
    text_content = MagicMock()
    text_content.text = text
    result = MagicMock()
    result.isError = is_error
    result.content = [text_content]
    result.structuredContent = {"threadId": thread_id} if thread_id else None
    result._meta = None
    return result


class TestInitialState:
    def test_starts_idle(self, agent: CodexAgent) -> None:
        assert agent.state == AgentState.idle

    def test_name(self, agent: CodexAgent) -> None:
        assert agent.name == "test-codex"

    def test_agent_type(self, agent: CodexAgent) -> None:
        from squadron.providers.base import ProviderType

        assert agent.agent_type == ProviderType.OPENAI_OAUTH


class TestHandleMessage:
    def test_first_message_initializes_client(self, agent: CodexAgent) -> None:
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())
        mock_session.initialize = AsyncMock()

        with patch.object(
            agent, "_start_client", new_callable=AsyncMock
        ) as mock_start:
            agent._session = None

            async def run() -> list[Message]:
                async def fake_start() -> None:
                    agent._session = mock_session

                mock_start.side_effect = fake_start
                msgs: list[Message] = []
                async for msg in agent.handle_message(_make_message()):
                    msgs.append(msg)
                return msgs

            msgs = asyncio.run(run())
            mock_start.assert_awaited_once()
            assert len(msgs) == 1
            assert msgs[0].content == "Codex response"

    def test_subsequent_message_reuses_thread(self, agent: CodexAgent) -> None:
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())

        agent._session = mock_session
        agent._thread_id = "existing-thread"

        async def run() -> list[Message]:
            msgs: list[Message] = []
            async for msg in agent.handle_message(_make_message("follow up")):
                msgs.append(msg)
            return msgs

        msgs = asyncio.run(run())
        mock_session.call_tool.assert_awaited_once_with(
            "codex-reply",
            {"prompt": "follow up", "threadId": "existing-thread"},
        )
        assert msgs[0].content == "Codex response"

    def test_state_transitions(self, agent: CodexAgent) -> None:
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(return_value=_mock_call_tool_result())
        agent._session = mock_session
        agent._thread_id = "thread-1"

        observed_states: list[AgentState] = []
        original_codex_reply = agent._codex_reply

        async def spy_reply(prompt: str) -> Message:
            observed_states.append(agent.state)
            return await original_codex_reply(prompt)

        agent._codex_reply = spy_reply  # type: ignore[assignment]

        async def run() -> None:
            async for _ in agent.handle_message(_make_message()):
                pass

        asyncio.run(run())
        assert AgentState.processing in observed_states
        assert agent.state == AgentState.idle

    def test_yields_message_with_correct_fields(self, agent: CodexAgent) -> None:
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_mock_call_tool_result(text="detailed output")
        )
        agent._session = mock_session
        agent._thread_id = None

        async def run() -> Message:
            async for msg in agent.handle_message(_make_message()):
                return msg
            raise AssertionError("no message yielded")

        msg = asyncio.run(run())
        assert msg.sender == "test-codex"
        assert msg.content == "detailed output"
        assert msg.message_type == MessageType.chat

    def test_tool_error_raises_provider_error(self, agent: CodexAgent) -> None:
        mock_session = AsyncMock()
        mock_session.call_tool = AsyncMock(
            return_value=_mock_call_tool_result(
                text="something went wrong", is_error=True
            )
        )
        agent._session = mock_session
        agent._thread_id = None

        async def run() -> None:
            async for _ in agent.handle_message(_make_message()):
                pass

        with pytest.raises(ProviderError, match="Codex tool error"):
            asyncio.run(run())

    def test_missing_model_raises(self) -> None:
        config = AgentConfig(
            name="no-model",
            agent_type="codex",
            provider="codex",
            model=None,
        )
        agent = CodexAgent(name="no-model", config=config)
        mock_session = AsyncMock()
        agent._session = mock_session

        async def run() -> None:
            async for _ in agent.handle_message(_make_message()):
                pass

        with pytest.raises(ProviderError, match="model is required"):
            asyncio.run(run())


class TestShutdown:
    def test_sets_terminated(self, agent: CodexAgent) -> None:
        asyncio.run(agent.shutdown())
        assert agent.state == AgentState.terminated

    def test_cleans_up_exit_stack(self, agent: CodexAgent) -> None:
        mock_stack = AsyncMock()
        agent._exit_stack = mock_stack
        agent._session = MagicMock()
        agent._thread_id = "thread-1"

        asyncio.run(agent.shutdown())

        mock_stack.aclose.assert_awaited_once()
        assert agent._session is None
        assert agent._thread_id is None
        assert agent._exit_stack is None


class TestResolveCodexCommand:
    def test_not_found_raises(self, agent: CodexAgent) -> None:
        with patch("shutil.which", return_value=None):
            with pytest.raises(ProviderError, match="Codex CLI not found"):
                agent._resolve_codex_command()

    def test_found_returns_path(self, agent: CodexAgent) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/codex"):
            assert agent._resolve_codex_command() == "/usr/local/bin/codex"
