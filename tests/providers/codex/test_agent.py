"""Tests for CodexAgent — Python SDK transport."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.errors import ProviderError


@pytest.fixture()
def agent_config() -> AgentConfig:
    return AgentConfig(
        name="test-codex",
        agent_type="openai-oauth",
        provider="openai-oauth",
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


@dataclass
class _MockRunResult:
    final_response: str | None = "Codex response"
    items: list[object] | None = None
    usage: object | None = None

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []


class TestInitialState:
    def test_starts_idle(self, agent: CodexAgent) -> None:
        assert agent.state == AgentState.idle

    def test_name(self, agent: CodexAgent) -> None:
        assert agent.name == "test-codex"

    def test_agent_type(self, agent: CodexAgent) -> None:
        from squadron.providers.base import ProviderType

        assert agent.agent_type == ProviderType.OPENAI_OAUTH


class TestHandleMessage:
    def test_first_message_initializes_sdk(self, agent: CodexAgent) -> None:
        mock_thread = AsyncMock()
        mock_thread.run = AsyncMock(return_value=_MockRunResult())

        mock_codex = AsyncMock()
        mock_codex.thread_start = AsyncMock(return_value=mock_thread)

        with patch(
            "codex_app_server.AsyncCodex",
            return_value=MagicMock(__aenter__=AsyncMock(return_value=mock_codex)),
        ):

            async def run() -> list[Message]:
                msgs: list[Message] = []
                async for msg in agent.handle_message(_make_message()):
                    msgs.append(msg)
                return msgs

            msgs = asyncio.run(run())
            assert len(msgs) == 1
            assert msgs[0].content == "Codex response"
            mock_codex.thread_start.assert_awaited_once()

    def test_subsequent_message_reuses_thread(self, agent: CodexAgent) -> None:
        mock_thread = AsyncMock()
        mock_thread.run = AsyncMock(return_value=_MockRunResult())

        # Pre-set the SDK state
        agent._codex = MagicMock()
        agent._thread = mock_thread

        async def run() -> list[Message]:
            msgs: list[Message] = []
            async for msg in agent.handle_message(_make_message("follow up")):
                msgs.append(msg)
            return msgs

        msgs = asyncio.run(run())
        mock_thread.run.assert_awaited_once_with("follow up")
        assert msgs[0].content == "Codex response"

    def test_state_transitions(self, agent: CodexAgent) -> None:
        mock_thread = AsyncMock()
        mock_thread.run = AsyncMock(return_value=_MockRunResult())
        agent._codex = MagicMock()
        agent._thread = mock_thread

        observed_states: list[AgentState] = []

        original_run = agent._run_prompt

        async def spy_run(prompt: str) -> str:
            observed_states.append(agent.state)
            return await original_run(prompt)

        agent._run_prompt = spy_run  # type: ignore[assignment]

        async def run() -> None:
            async for _ in agent.handle_message(_make_message()):
                pass

        asyncio.run(run())
        assert AgentState.processing in observed_states
        assert agent.state == AgentState.idle

    def test_yields_message_with_correct_fields(self, agent: CodexAgent) -> None:
        mock_thread = AsyncMock()
        mock_thread.run = AsyncMock(
            return_value=_MockRunResult(final_response="detailed output")
        )
        agent._codex = MagicMock()
        agent._thread = mock_thread

        async def run() -> Message:
            async for msg in agent.handle_message(_make_message()):
                return msg
            raise AssertionError("no message yielded")

        msg = asyncio.run(run())
        assert msg.sender == "test-codex"
        assert msg.content == "detailed output"
        assert msg.message_type == MessageType.chat

    def test_none_response_yields_empty(self, agent: CodexAgent) -> None:
        mock_thread = AsyncMock()
        mock_thread.run = AsyncMock(return_value=_MockRunResult(final_response=None))
        agent._codex = MagicMock()
        agent._thread = mock_thread

        async def run() -> Message:
            async for msg in agent.handle_message(_make_message()):
                return msg
            raise AssertionError("no message yielded")

        msg = asyncio.run(run())
        assert msg.content == ""

    def test_missing_model_raises(self) -> None:
        config = AgentConfig(
            name="no-model",
            agent_type="openai-oauth",
            provider="openai-oauth",
            model=None,
        )
        agent = CodexAgent(name="no-model", config=config)
        agent._codex = MagicMock()

        async def run() -> None:
            async for _ in agent.handle_message(_make_message()):
                pass

        with pytest.raises(ProviderError, match="model is required"):
            asyncio.run(run())

    def test_sdk_import_error_raises(self, agent: CodexAgent) -> None:
        with patch.dict("sys.modules", {"codex_app_server": None}):
            with patch(
                "builtins.__import__",
                side_effect=ImportError("no module"),
            ):

                async def run() -> None:
                    async for _ in agent.handle_message(_make_message()):
                        pass

                with pytest.raises(ProviderError, match="SDK not installed"):
                    asyncio.run(run())


class TestShutdown:
    def test_sets_terminated(self, agent: CodexAgent) -> None:
        asyncio.run(agent.shutdown())
        assert agent.state == AgentState.terminated

    def test_cleans_up_sdk(self, agent: CodexAgent) -> None:
        mock_codex = AsyncMock()
        agent._codex = mock_codex
        agent._thread = MagicMock()

        asyncio.run(agent.shutdown())

        mock_codex.__aexit__.assert_awaited_once()
        assert agent._codex is None
        assert agent._thread is None
