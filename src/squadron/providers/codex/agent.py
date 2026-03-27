"""CodexAgent — agentic provider via Codex Python SDK."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.logging import get_logger
from squadron.providers.base import ProviderType
from squadron.providers.errors import ProviderError

_log = get_logger("squadron.providers.codex.agent")

_DEFAULT_SANDBOX = "read-only"


class CodexAgent:
    """Agentic provider backed by the Codex Python SDK.

    The SDK client is started lazily on first ``handle_message()`` call.
    Subsequent messages continue the same thread.
    """

    def __init__(self, name: str, config: AgentConfig) -> None:
        self._name = name
        self._config = config
        self._state = AgentState.idle
        self._codex: object | None = None  # AsyncCodex instance
        self._thread: object | None = None  # AsyncThread instance

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
        if self._codex is not None:
            try:
                await self._codex.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass  # Best-effort cleanup
        self._codex = None
        self._thread = None
        self._state = AgentState.terminated

    async def _run_prompt(self, prompt: str) -> str:
        """Send prompt via SDK and return response text."""
        try:
            from codex_app_server import AsyncCodex
        except ImportError as exc:
            raise ProviderError(
                "Codex Python SDK not installed. "
                "Install from: https://github.com/openai/codex/tree/main/sdk/python"
            ) from exc

        if self._config.model is None:
            raise ProviderError(
                "model is required for Codex agents. "
                "Specify --model or use a model alias (e.g. codex-agent)."
            )

        # Lazy initialization
        if self._codex is None:
            self._codex = await AsyncCodex().__aenter__()
            sandbox = self._config.credentials.get("sandbox", _DEFAULT_SANDBOX)
            cwd = self._config.cwd or os.getcwd()
            self._thread = await self._codex.thread_start(  # type: ignore[union-attr]
                model=self._config.model,
                sandbox=sandbox,
                cwd=cwd,
                approval_policy="never",
            )
            _log.debug(
                "Codex SDK session started: model=%s, sandbox=%s",
                self._config.model,
                sandbox,
            )

        result = await self._thread.run(prompt)  # type: ignore[union-attr]
        response = result.final_response
        if response is None:
            return ""
        return response
