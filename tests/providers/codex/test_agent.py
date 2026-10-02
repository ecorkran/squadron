"""Tests for CodexAgent — official Codex Python SDK (faked at the import boundary)."""

from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import AgentConfig, AgentState, Effort, Message, MessageType
from squadron.core.usage import TokenUsage
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.errors import ProviderError
from tests.providers.codex.fake_sdk import (
    ApprovalMode,
    CodexError,
    CodexRpcError,
    FakeSdk,
    ReasoningEffort,
    RetryLimitExceededError,
    Sandbox,
    ServerBusyError,
    ThreadTokenUsage,
    TransportClosedError,
    TurnResult,
    TurnStatus,
    Usage,
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

    def test_uses_bundled_runtime(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        (config,) = fake_sdk.async_codex.call_args.args
        assert config.codex_bin is None

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
        fake_sdk.client.close.assert_awaited_once()
        assert agent.state == AgentState.terminated

    def test_timeout_still_reported_when_interrupt_raises_runtime_error(
        self, agent: CodexAgent, fake_sdk: FakeSdk, caplog: pytest.LogCaptureFixture
    ) -> None:
        async def hang() -> TurnResult:
            await asyncio.sleep(10)
            raise AssertionError("turn should have timed out")

        fake_sdk.turn.run.side_effect = hang
        fake_sdk.turn.interrupt.side_effect = RuntimeError("runtime gone")
        with patch(_CONFIG, return_value=0), caplog.at_level(logging.WARNING):
            with pytest.raises(ProviderError, match="Codex turn timed out after 0 s"):
                _send(agent, "hi")
        assert "interrupt after timeout did not complete" in caplog.text

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


class TestSdkErrors:
    """One test per SDK-error Failure Modes row; each chains the original."""

    def test_startup_failure(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        sdk_error = CodexError("initialize failed")
        fake_sdk.client.__aenter__.side_effect = sdk_error
        with pytest.raises(ProviderError, match="Codex runtime failed to start") as exc_info:
            _send(agent, "hi")
        assert exc_info.value.__cause__ is sdk_error
        assert agent._codex is None

    def test_thread_start_failure_closes_client(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        fake_sdk.client.thread_start.side_effect = CodexError("bad thread")
        with pytest.raises(ProviderError, match="Codex thread start failed"):
            _send(agent, "hi")
        fake_sdk.client.close.assert_awaited_once()
        assert agent._codex is None
        assert agent.state == AgentState.idle

    def test_transport_closed_resets_and_next_message_starts_new_client(
        self, agent: CodexAgent, fake_sdk: FakeSdk
    ) -> None:
        sdk_error = TransportClosedError("Codex process is not running")
        fake_sdk.turn.run.side_effect = [sdk_error, TurnResult()]
        with pytest.raises(ProviderError, match="connection closed") as exc_info:
            _send(agent, "first")
        assert exc_info.value.__cause__ is sdk_error
        assert agent._codex is None
        assert agent._thread is None
        (msg,) = _send(agent, "second")
        assert msg.content == "Codex response"
        assert fake_sdk.async_codex.call_count == 2

    @pytest.mark.parametrize("error_type", [ServerBusyError, RetryLimitExceededError])
    def test_server_busy_not_retried(
        self, agent: CodexAgent, fake_sdk: FakeSdk, error_type: type[Exception]
    ) -> None:
        sdk_error = error_type("server overloaded")
        fake_sdk.turn.run.side_effect = sdk_error
        with pytest.raises(ProviderError, match="server overloaded") as exc_info:
            _send(agent, "hi")
        assert exc_info.value.__cause__ is sdk_error
        assert fake_sdk.turn.run.await_count == 1

    def test_rpc_error_points_to_login(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        sdk_error = CodexRpcError("not logged in")
        fake_sdk.turn.run.side_effect = sdk_error
        with pytest.raises(ProviderError, match="sq auth login openai-oauth") as exc_info:
            _send(agent, "hi")
        assert exc_info.value.__cause__ is sdk_error

    def test_teardown_error_logged_not_raised(
        self, agent: CodexAgent, fake_sdk: FakeSdk, caplog: pytest.LogCaptureFixture
    ) -> None:
        _send(agent, "hi")
        fake_sdk.client.close.side_effect = CodexError("close failed")
        with caplog.at_level("ERROR", logger="squadron.providers.codex.agent"):
            asyncio.run(agent.shutdown())
        assert any("ignoring error during SDK teardown" in r.getMessage() for r in caplog.records)
        assert agent.state == AgentState.terminated


class TestUsage:
    """Slice 129 D6: per-turn usage rides the Message as the OpenAI agent stamps it."""

    def test_full_mapping(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        fake_sdk.turn.run.return_value = TurnResult(
            usage=ThreadTokenUsage(
                last=Usage(
                    input_tokens=1200,
                    cached_input_tokens=300,
                    output_tokens=450,
                    reasoning_output_tokens=90,
                )
            )
        )
        (msg,) = _send(agent, "hi")
        assert msg.metadata["usage"] == TokenUsage(
            prompt=1200, cached=300, completion=450, reasoning=90
        )
        assert msg.metadata["turns"] == 1

    def test_omitted_field_stays_none(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        last = SimpleNamespace(input_tokens=10, cached_input_tokens=0, output_tokens=5)
        fake_sdk.turn.run.return_value = TurnResult(usage=SimpleNamespace(last=last))  # type: ignore[arg-type]
        (msg,) = _send(agent, "hi")
        assert msg.metadata["usage"] == TokenUsage(prompt=10, cached=0, completion=5)
        assert msg.metadata["usage"].reasoning is None

    def test_no_usage_is_not_reported(
        self, agent: CodexAgent, fake_sdk: FakeSdk, caplog: pytest.LogCaptureFixture
    ) -> None:
        with caplog.at_level("DEBUG", logger="squadron.providers.codex.agent"):
            (msg,) = _send(agent, "hi")
        usage = msg.metadata["usage"]
        assert usage == TokenUsage()
        assert not usage.reported
        assert any("reported no token usage" in r.getMessage() for r in caplog.records)


class TestHandleMessage:
    def test_state_transitions(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        observed_states: list[AgentState] = []
        original_run = agent._run_prompt

        async def spy_run(prompt: str) -> tuple[str, TokenUsage]:
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

        mock_codex.close.assert_awaited_once()
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


class TestEffort:
    """Slice 129 D5: squadron Effort reaches the turn as the same-named ReasoningEffort."""

    @pytest.mark.parametrize("effort", list(Effort))
    def test_effort_maps_by_name(
        self, agent_config: AgentConfig, fake_sdk: FakeSdk, effort: Effort
    ) -> None:
        config = agent_config.model_copy(update={"effort": effort})
        _send(CodexAgent(name="test-codex", config=config), "hi")
        sent = fake_sdk.thread.turn.call_args.kwargs["effort"]
        assert sent is ReasoningEffort(effort.value)

    def test_no_effort_sends_none(self, agent: CodexAgent, fake_sdk: FakeSdk) -> None:
        _send(agent, "hi")
        assert "effort" not in fake_sdk.thread.turn.call_args.kwargs

    def test_effort_logs_no_warning(
        self, agent_config: AgentConfig, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = agent_config.model_copy(update={"effort": Effort.high})
        with caplog.at_level("WARNING", logger="squadron.providers.codex.agent"):
            CodexAgent(name="test-codex", config=config)
        assert not [r for r in caplog.records if "effort" in r.getMessage()]
