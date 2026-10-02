"""CodexAgent — agentic provider via the official Codex Python SDK (``openai_codex``)."""

from __future__ import annotations

import asyncio
import os
import time
from collections.abc import AsyncIterator

from squadron.config.manager import get_typed_config
from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.logging import get_logger
from squadron.providers.base import ProviderType
from squadron.providers.codex.auth import OAuthFileStrategy
from squadron.providers.codex.runtime import resolve_codex_runtime
from squadron.providers.errors import ProviderError

_log = get_logger("squadron.providers.codex.agent")

_SANDBOX_KEY = "sandbox"
_TURN_TIMEOUT_KEY = "codex.turn_timeout_s"
_RPC_TIMEOUT_KEY = "codex.account_timeout_s"


class CodexAgent:
    """Agentic provider backed by the official Codex Python SDK.

    Requires the ``codex`` extra (``openai-codex``), which bundles the Codex
    runtime binary; a ``codex`` on PATH is the fallback (see ``runtime.py``).

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
        self._codex: object | None = None
        self._thread: object | None = None

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
            response_text = await self._run_prompt(message.content)
            yield Message(
                sender=self._name,
                recipients=[],
                content=response_text,
                message_type=MessageType.chat,
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
                await self._codex.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:  # noqa: BLE001
                # Teardown boundary: __aexit__ closes the Codex SDK's
                # subprocess/transport, whose failure modes are internal to
                # the SDK and not enumerable here. A cleanup failure at
                # shutdown must not block finishing teardown — logged for
                # diagnosability, never re-raised.
                _log.exception("CodexAgent: ignoring error during SDK teardown")
        self._codex = None
        self._thread = None

    async def _run_prompt(self, prompt: str) -> str:
        """Send prompt via SDK and return response text."""
        if self._config.model is None:
            raise ProviderError(
                "model is required for Codex agents. "
                "Specify --model or use a model alias (e.g. codex-agent)."
            )
        if self._thread is None:
            await self._start_thread(self._config.model)
        result = await self._run_turn_translating_errors(prompt)
        return self._checked_response(result)

    async def _run_turn_translating_errors(self, prompt: str) -> object:
        """Run a turn, mapping SDK errors to ``ProviderError`` (Failure Modes)."""
        from openai_codex import (  # pyright: ignore[reportMissingImports]
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

    async def _run_turn(self, prompt: str) -> object:
        """Run one turn under ``codex.turn_timeout_s``; interrupt it on expiry."""
        timeout_s = get_typed_config(_TURN_TIMEOUT_KEY, int)
        turn: object | None = None
        try:
            async with asyncio.timeout(timeout_s):
                turn = await self._thread.turn(prompt, **self._turn_options())  # type: ignore[union-attr]
                return await turn.run()  # type: ignore[union-attr]
        except TimeoutError as exc:
            if turn is not None:
                await self._interrupt(turn)
            raise ProviderError(f"Codex turn timed out after {timeout_s} s") from exc
        except RuntimeError as exc:
            # The SDK reports a failed turn (and a missing completion event)
            # as a bare RuntimeError carrying the runtime's error message.
            raise ProviderError(f"Codex turn failed: {exc}") from exc

    def _turn_options(self) -> dict[str, object]:
        """Per-turn SDK options: effort maps by name to ``ReasoningEffort`` (D5)."""
        if self._config.effort is None:
            return {}
        from openai_codex.types import ReasoningEffort  # pyright: ignore[reportMissingImports]

        return {"effort": ReasoningEffort(self._config.effort.value)}

    async def _interrupt(self, turn: object) -> None:
        """Best-effort interrupt of a timed-out turn, bounded so a hung runtime cannot block."""
        from openai_codex import CodexError  # pyright: ignore[reportMissingImports]

        try:
            async with asyncio.timeout(get_typed_config(_RPC_TIMEOUT_KEY, int)):
                await turn.interrupt()  # type: ignore[attr-defined]
        except (TimeoutError, CodexError):
            # The turn already failed with a timeout, which is what gets raised;
            # shutdown() tears down the runtime either way.
            _log.warning("Codex turn interrupt after timeout did not complete", exc_info=True)

    @staticmethod
    def _checked_response(result: object) -> str:
        """Return the turn's response text, or raise for an interrupted or empty turn."""
        from openai_codex.types import TurnStatus  # pyright: ignore[reportMissingImports]

        if result.status == TurnStatus.interrupted:  # type: ignore[attr-defined]
            raise ProviderError("Codex turn interrupted")
        text = result.final_response  # type: ignore[attr-defined]
        if text is None or not text.strip():
            raise ProviderError("Codex turn completed with no response text")
        return text

    async def _start_thread(self, model: str) -> None:
        """Start the SDK client and open a thread (first message only)."""
        runtime = resolve_codex_runtime()
        from openai_codex import (  # pyright: ignore[reportMissingImports]
            ApprovalMode,
            AsyncCodex,
            CodexConfig,
            CodexError,
            Sandbox,
        )

        sandbox = self._resolve_sandbox(Sandbox)

        started = time.monotonic()
        codex = AsyncCodex(CodexConfig(codex_bin=runtime.path))
        try:
            # Spawn + initialize: CodexError from the protocol, OSError when the
            # binary cannot run, RuntimeError from initialize-metadata checks.
            self._codex = await codex.__aenter__()
        except (CodexError, OSError, RuntimeError) as exc:
            raise ProviderError(f"Codex runtime failed to start: {exc}") from exc
        _log.debug(
            "Codex runtime started in %.2fs (%s, bin=%s)",
            time.monotonic() - started,
            runtime.source,
            runtime.path,
        )
        try:
            self._thread = await self._codex.thread_start(  # type: ignore[union-attr]
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

    def _resolve_sandbox(self, sandbox_enum: type) -> object:
        """Validate ``credentials["sandbox"]`` against the SDK enum (default read-only)."""
        raw = self._config.credentials.get(_SANDBOX_KEY)
        if raw is None:
            return sandbox_enum.read_only  # type: ignore[attr-defined]
        try:
            return sandbox_enum(raw)
        except ValueError as exc:
            valid = ", ".join(member.value for member in sandbox_enum)  # type: ignore[attr-defined]
            raise ProviderError(f"Invalid Codex sandbox {raw!r}; valid values: {valid}") from exc
