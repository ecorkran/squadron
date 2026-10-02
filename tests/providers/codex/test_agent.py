"""Tests for CodexAgent — official Codex Python SDK (faked at the import boundary)."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND
from squadron.providers.errors import ProviderError
from tests.providers.codex.conftest import (
    PATH_RUNTIME,
    ApprovalMode,
    FakeSdk,
    Sandbox,
    TurnResult,
    TurnStatus,
)

_CONFIG = "squadron.providers.codex.agent.get_typed_config"


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


def _send(agent: CodexAgent, *contents: str) -> list[Message]:
    """Send each content as a message; return every yielded Message."""

    async def run() -> list[Message]:
        msgs: list[Message] = []
        for content in contents:
            async for msg in agent.handle_message(_make_message(content)):
                msgs.append(msg)
        return msgs

    return asyncio.run(run())


class TestInitialState:
    def test_starts_idle(self, agent: CodexAgent) -> None:
        assert agent.state == AgentState.idle

    def test_name(self, agent: CodexAgent) -> None:
        assert agent.name == "test-codex"

    def test_agent_type(self, agent: CodexAgent) -> None:
        from squadron.providers.base import ProviderType

        assert agent.agent_type == ProviderType.OPENAI_OAUTH


class TestClientLifecycle:
    def test_starts_client_once_and_reuses_it(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        msgs = _send(agent, "first", "second")
        assert [m.content for m in msgs] == ["Codex response", "Codex response"]
        fake_sdk.async_codex.assert_called_once()
        fake_sdk.client.__aenter__.assert_awaited_once()
        fake_sdk.client.thread_start.assert_awaited_once()
        assert fake_sdk.turn.run.await_count == 2

    def test_bundled_runtime_passes_no_binary(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        (config,) = fake_sdk.async_codex.call_args.args
        assert config.codex_bin is None

    def test_path_runtime_passes_its_binary(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        with patch("squadron.providers.codex.agent.resolve_codex_runtime", return_value=PATH_RUNTIME):
            _send(agent, "hi")
        (config,) = fake_sdk.async_codex.call_args.args
        assert config.codex_bin == "/usr/local/bin/codex"

    def test_thread_start_denies_approvals(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        kwargs = fake_sdk.client.thread_start.call_args.kwargs
        assert kwargs["approval_mode"] is ApprovalMode.deny_all
        assert kwargs["model"] == "gpt-5.3-codex"
        assert kwargs["cwd"] == "/tmp/test-project"

    def test_base_instructions_absent_when_unset(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        assert fake_sdk.client.thread_start.call_args.kwargs["base_instructions"] is None

    def test_base_instructions_passed_when_set(
        self, agent_config: AgentConfig, fake_sdk: FakeSdk
    ) -> None:
        config = agent_config.model_copy(update={"instructions": "Review carefully."})
        _send(CodexAgent(name="test-codex", config=config), "hi")
        kwargs = fake_sdk.client.thread_start.call_args.kwargs
        assert kwargs["base_instructions"] == "Review carefully."

    def test_package_missing_raises_install_hint(self, agent: CodexAgent) -> None:
        with patch("squadron.providers.codex.runtime._module_available", return_value=False):
            with pytest.raises(ProviderError) as exc_info:
                _send(agent, "hi")
        assert CODEX_INSTALL_COMMAND in str(exc_info.value)

    def test_missing_model_raises(self, fake_sdk: FakeSdk) -> None:
        config = AgentConfig(
            name="no-model", agent_type="openai-oauth", provider="openai-oauth", model=None
        )
        with pytest.raises(ProviderError, match="model is required"):
            _send(CodexAgent(name="no-model", config=config), "hi")
        fake_sdk.async_codex.assert_not_called()


class TestSandbox:
    def test_defaults_to_read_only(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        assert fake_sdk.client.thread_start.call_args.kwargs["sandbox"] is Sandbox.read_only

    def test_valid_value_passed_through(self, agent_config: AgentConfig, fake_sdk: FakeSdk) -> None:
        config = agent_config.model_copy(update={"credentials": {"sandbox": "workspace-write"}})
        _send(CodexAgent(name="test-codex", config=config), "hi")
        assert fake_sdk.client.thread_start.call_args.kwargs["sandbox"] is Sandbox.workspace_write

    def test_invalid_value_names_valid_values(
        self, agent_config: AgentConfig, fake_sdk: FakeSdk
    ) -> None:
        config = agent_config.model_copy(update={"credentials": {"sandbox": "wide-open"}})
        with pytest.raises(ProviderError) as exc_info:
            _send(CodexAgent(name="test-codex", config=config), "hi")
        message = str(exc_info.value)
        assert "wide-open" in message
        for member in Sandbox:
            assert member.value in message
        fake_sdk.client.thread_start.assert_not_called()


class TestTurnResultChecks:
    """One test per Failure Modes row that applies to a turn (D7, D8)."""

    def test_timeout_interrupts_turn_and_shutdown_still_runs(
        self, agent: CodexAgent, fake_sdk: FakeSdk
    ) -> None:
        async def hang() -> TurnResult:
            await asyncio.sleep(10)
            raise AssertionError("turn should have timed out")

        fake_sdk.turn.run.side_effect = hang

        async def run() -> None:
            try:
                async for _ in agent.handle_message(_make_message()):
                    pass
            finally:
                await agent.shutdown()

        with patch(_CONFIG, return_value=0):
            with pytest.raises(ProviderError, match="Codex turn timed out after 0 s"):
                asyncio.run(run())
        fake_sdk.turn.interrupt.assert_awaited_once()
        fake_sdk.client.__aexit__.assert_awaited_once()
        assert agent.state == AgentState.terminated

    def test_failed_turn_carries_sdk_message(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        sdk_error = RuntimeError("unexpected status 401 Unauthorized")
        fake_sdk.turn.run.side_effect = sdk_error
        with pytest.raises(ProviderError, match="401 Unauthorized") as exc_info:
            _send(agent, "hi")
        assert exc_info.value.__cause__ is sdk_error

    def test_interrupted_turn_raises(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        fake_sdk.turn.run.return_value = TurnResult(status=TurnStatus.interrupted)
        with pytest.raises(ProviderError, match="Codex turn interrupted"):
            _send(agent, "hi")

    @pytest.mark.parametrize("response", [None, "", "  \n "])
    def test_empty_or_blank_response_raises(
        self, agent: CodexAgent, fake_sdk: FakeSdk, response: str | None
    ) -> None:
        fake_sdk.turn.run.return_value = TurnResult(final_response=response)
        with pytest.raises(ProviderError, match="Codex turn completed with no response text"):
            _send(agent, "hi")


class TestHandleMessage:
    def test_state_transitions(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        observed_states: list[AgentState] = []
        original_run = agent._run_prompt

        async def spy_run(prompt: str) -> str:
            observed_states.append(agent.state)
            return await original_run(prompt)

        agent._run_prompt = spy_run  # type: ignore[assignment]
        _send(agent, "hi")
        assert AgentState.processing in observed_states
        assert agent.state == AgentState.idle

    def test_yields_message_with_correct_fields(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        fake_sdk.turn.run.return_value = TurnResult(final_response="detailed output")
        (msg,) = _send(agent, "hi")
        assert msg.sender == "test-codex"
        assert msg.content == "detailed output"
        assert msg.message_type == MessageType.chat


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


class TestOutputBudgetWarning:
    """Slice 924 B2: Codex cannot apply a budget, and says so."""

    def test_budget_logs_one_warning(
        self, agent_config: AgentConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = agent_config.model_copy(update={"max_output_tokens": 4096})
        with caplog.at_level("WARNING", logger="squadron.providers.codex.agent"):
            CodexAgent(name="test-codex", config=config)
        hits = [r for r in caplog.records if "cannot apply max_output_tokens=4096" in r.getMessage()]
        assert len(hits) == 1

    def test_no_budget_logs_nothing(
        self, agent_config: AgentConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="squadron.providers.codex.agent"):
            CodexAgent(name="test-codex", config=agent_config)
        assert not [r for r in caplog.records if "max_output_tokens" in r.getMessage()]

    def test_effort_logs_one_warning(
        self, agent_config: AgentConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Slice 931 D4: Codex cannot apply effort, and says so."""
        from squadron.core.models import Effort

        config = agent_config.model_copy(update={"effort": Effort.low})
        with caplog.at_level("WARNING", logger="squadron.providers.codex.agent"):
            CodexAgent(name="test-codex", config=config)
        messages = [r.getMessage() for r in caplog.records]
        assert messages.count("Codex agent cannot apply effort=low; the backend default applies") == 1

    def test_no_effort_logs_nothing(
        self, agent_config: AgentConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("WARNING", logger="squadron.providers.codex.agent"):
            CodexAgent(name="test-codex", config=agent_config)
        assert not [r for r in caplog.records if "effort" in r.getMessage()]
