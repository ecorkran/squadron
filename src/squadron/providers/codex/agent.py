"""CodexAgent — agentic provider via the official Codex Python SDK (``openai_codex``)."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from squadron.config.manager import get_typed_config
from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.core.usage import TokenUsage
from squadron.logging import get_logger
from squadron.providers.base import ProviderType
from squadron.providers.codex.auth import OAuthFileStrategy
from squadron.providers.errors import ProviderError

if TYPE_CHECKING:
    from openai_codex import AsyncCodex, AsyncThread, AsyncTurnHandle, Sandbox, TurnResult

_log = get_logger("squadron.providers.codex.agent")

_SANDBOX_KEY = "sandbox"
_TURN_TIMEOUT_KEY = "codex.turn_timeout_s"
_RPC_TIMEOUT_KEY = "codex.account_timeout_s"


class CodexAgent:
    """Agentic provider backed by the official Codex Python SDK.

    ``openai-codex`` bundles the Codex runtime binary; the SDK locates it itself.

    The SDK client is started lazily on first ``handle_message()`` call and
    reused; subsequent messages continue the same thread.
    """

    def __init__(self, name: str, config: AgentConfig) -> None:
        self._name = name
        self._config = config
        self._state = AgentState.idle
        # Slice 924 B2: Codex sends no per-request budget; say so rather than drop it.
        if config.max_output_tokens is not None:
            _log.warning(
                "Codex agent cannot apply max_output_tokens=%d; the backend default applies",
                config.max_output_tokens,
            )
        self._codex: AsyncCodex | None = None
        self._thread: AsyncThread | None = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return ProviderType.OPENAI_OAUTH

    @property
    def state(self) -> AgentState:
        return self._state

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Send a message to the Codex agent and yield response Messages."""
        self._state = AgentState.processing
        try:
            response_text, usage = await self._run_prompt(message.content)
            # Same telemetry keys the OpenAI agent stamps, read by review's collect_turn.
            yield Message(
                sender=self._name,
                recipients=[],
                content=response_text,
                message_type=MessageType.chat,
                metadata={"turns": 1, "usage": usage},
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Codex agent error: {exc}") from exc
        finally:
            self._state = AgentState.idle

    async def shutdown(self) -> None:
        """Tear down the SDK client."""
        await self._close_client()
        self._state = AgentState.terminated

    async def _close_client(self) -> None:
        """Close the SDK client (if any) and forget it and its thread."""
        if self._codex is not None:
            try:
                await self._codex.close()
            except Exception:  # noqa: BLE001
                # Teardown boundary: __aexit__ closes the Codex SDK's
                # subprocess/transport, whose failure modes are internal to
                # the SDK and not enumerable here. A cleanup failure at
                # shutdown must not block finishing teardown — logged for
                # diagnosability, never re-raised.
                _log.exception("CodexAgent: ignoring error during SDK teardown")
        self._codex = None
        self._thread = None

    async def _run_prompt(self, prompt: str) -> tuple[str, TokenUsage]:
        """Send prompt via SDK and return the response text and the turn's usage."""
        if self._config.model is None:
            raise ProviderError(
                "model is required for Codex agents. "
                "Specify --model or use a model alias (e.g. codex-agent)."
            )
        if self._thread is None:
            await self._start_thread(self._config.model)
        result = await self._run_turn_translating_errors(prompt)
        return self._checked_response(result), _turn_usage(result)

    async def _run_turn_translating_errors(self, prompt: str) -> TurnResult:
        """Run a turn, mapping SDK errors to ``ProviderError`` (Failure Modes)."""
        from openai_codex import (
            CodexRpcError,
            ServerBusyError,
            TransportClosedError,
        )

        try:
            return await self._run_turn(prompt)
        except TransportClosedError as exc:
            # The runtime is gone; drop it so the next message starts a new one.
            self._codex = None
            self._thread = None
            raise ProviderError(f"Codex runtime connection closed: {exc}") from exc
        except ServerBusyError as exc:  # includes RetryLimitExceededError
            raise ProviderError(f"Codex server busy: {exc}") from exc
        except CodexRpcError as exc:
            raise ProviderError(
                f"Codex rejected the request: {exc}. {OAuthFileStrategy().setup_hint}."
            ) from exc

    async def _run_turn(self, prompt: str) -> TurnResult:
        """Run one turn under ``codex.turn_timeout_s``; interrupt it on expiry."""
        timeout_s = get_typed_config(_TURN_TIMEOUT_KEY, int)
        if self._thread is None:
            raise ProviderError("Codex turn requested before the thread started")
        turn: AsyncTurnHandle | None = None
        try:
            async with asyncio.timeout(timeout_s):
                turn = await self._thread.turn(prompt, **self._turn_options())
                return await turn.run()
        except TimeoutError as exc:
            if turn is not None:
                await self._interrupt(turn)
            raise ProviderError(f"Codex turn timed out after {timeout_s} s") from exc
        except RuntimeError as exc:
            # The SDK reports a failed turn (and a missing completion event)
            # as a bare RuntimeError carrying the runtime's error message.
            raise ProviderError(f"Codex turn failed: {exc}") from exc

    def _turn_options(self) -> dict[str, Any]:
        """Per-turn SDK options: effort maps by name to ``ReasoningEffort`` (D5)."""
        if self._config.effort is None:
            return {}
        from openai_codex.types import ReasoningEffort

        return {"effort": ReasoningEffort(self._config.effort.value)}

    async def _interrupt(self, turn: AsyncTurnHandle) -> None:
        """Best-effort interrupt of a timed-out turn, bounded so a hung runtime cannot block."""
        from openai_codex import CodexError

        try:
            async with asyncio.timeout(get_typed_config(_RPC_TIMEOUT_KEY, int)):
                await turn.interrupt()
        except (TimeoutError, CodexError):
            # The turn already failed with a timeout, which is what gets raised;
            # shutdown() tears down the runtime either way.
            _log.warning("Codex turn interrupt after timeout did not complete", exc_info=True)

    @staticmethod
    def _checked_response(result: TurnResult) -> str:
        """Return the turn's response text, or raise for an interrupted or empty turn."""
        from openai_codex.types import TurnStatus

        if result.status == TurnStatus.interrupted:
            raise ProviderError("Codex turn interrupted")
        text = result.final_response
        if text is None or not text.strip():
            raise ProviderError("Codex turn completed with no response text")
        return text

    async def _start_thread(self, model: str) -> None:
        """Start the SDK client and open a thread (first message only)."""
        from openai_codex import (
            ApprovalMode,
            AsyncCodex,
            CodexConfig,
            CodexError,
        )

        sandbox = self._resolve_sandbox()

        started = time.monotonic()
        codex = AsyncCodex(CodexConfig())
        try:
            # Spawn + initialize: CodexError from the protocol, OSError when the
            # binary cannot run, RuntimeError from initialize-metadata checks.
            self._codex = await codex.__aenter__()
        except (CodexError, OSError, RuntimeError) as exc:
            raise ProviderError(f"Codex runtime failed to start: {exc}") from exc
        _log.debug("Codex runtime started in %.2fs", time.monotonic() - started)
        try:
            self._thread = await self._codex.thread_start(
                model=model,
                sandbox=sandbox,
                cwd=self._config.cwd or os.getcwd(),
                approval_mode=ApprovalMode.deny_all,
                base_instructions=self._config.instructions or None,
            )
        except CodexError as exc:
            await self._close_client()
            raise ProviderError(f"Codex thread start failed: {exc}") from exc
        _log.debug("Codex thread started: model=%s", model)

    def _resolve_sandbox(self) -> Sandbox:
        """Validate ``credentials["sandbox"]`` against the SDK enum (default read-only)."""
        from openai_codex import Sandbox

        raw = self._config.credentials.get(_SANDBOX_KEY)
        if raw is None:
            return Sandbox.read_only
        try:
            return Sandbox(raw)
        except ValueError as exc:
            valid = ", ".join(member.value for member in Sandbox)
            raise ProviderError(f"Invalid Codex sandbox {raw!r}; valid values: {valid}") from exc


def _turn_usage(result: object) -> TokenUsage:
    """Map ``TurnResult.usage.last`` to ``TokenUsage`` (D6); unreported fields stay ``None``."""
    usage = getattr(result, "usage", None)
    if usage is None:
        _log.debug("Codex turn reported no token usage")
        return TokenUsage()
    last = usage.last
    return TokenUsage(
        prompt=getattr(last, "input_tokens", None),
        cached=getattr(last, "cached_input_tokens", None),
        completion=getattr(last, "output_tokens", None),
        reasoning=getattr(last, "reasoning_output_tokens", None),
    )
