"""CodexAgent — agentic provider via Codex Python SDK."""

from __future__ import annotations

import os
import shutil
from collections.abc import AsyncIterator

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.logging import get_logger
from squadron.providers.base import ProviderType
from squadron.providers.errors import ProviderError

_log = get_logger("squadron.providers.codex.agent")

_DEFAULT_SANDBOX = "read-only"

# The Codex Python SDK is installed from the openai/codex GitHub repo.
# It requires the Codex CLI binary on PATH (installed via npm).
_SDK_INSTALL_URL = "https://github.com/openai/codex/tree/main/sdk/python"
_CLI_INSTALL_CMD = "npm i -g @openai/codex"


def _resolve_codex_binary() -> str | None:
    """Find the Codex CLI binary on PATH (installed via npm)."""
    return shutil.which("codex")


class CodexAgent:
    """Agentic provider backed by the Codex Python SDK.

    Requires:
    - ``codex-app-server-sdk`` Python package (from openai/codex GitHub repo)
    - ``codex`` CLI binary on PATH (``npm i -g @openai/codex``)

    The SDK client is started lazily on first ``handle_message()`` call.
    Subsequent messages continue the same thread.
    """

    def __init__(self, name: str, config: AgentConfig) -> None:
        self._name = name
        self._config = config
        self._state = AgentState.idle
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
        if self._codex is not None:
            try:
                await self._codex.__aexit__(None, None, None)  # type: ignore[union-attr]
            except Exception:
                pass
        self._codex = None
        self._thread = None
        self._state = AgentState.terminated

    async def _run_prompt(self, prompt: str) -> str:
        """Send prompt via SDK and return response text."""
        try:
            from codex_app_server import AsyncCodex
            from codex_app_server.client import AppServerConfig
        except ImportError as exc:
            raise ProviderError(
                "Codex Python SDK (codex_app_server) not installed. "
                "Install the official OpenAI SDK from GitHub:\n"
                "  pip install 'codex-app-server-sdk @ "
                "git+https://github.com/openai/codex.git"
                "#subdirectory=sdk/python'\n"
                "Note: do NOT install the similarly-named PyPI package."
            ) from exc

        if self._config.model is None:
            raise ProviderError(
                "model is required for Codex agents. "
                "Specify --model or use a model alias (e.g. codex-agent)."
            )

        if self._codex is None:
            codex_bin = _resolve_codex_binary()
            if codex_bin is None:
                raise ProviderError(
                    f"Codex CLI not found on PATH. Install with: {_CLI_INSTALL_CMD}"
                )

            config = AppServerConfig(codex_bin=codex_bin)
            self._codex = await AsyncCodex(config=config).__aenter__()
            sandbox = self._config.credentials.get("sandbox", _DEFAULT_SANDBOX)
            cwd = self._config.cwd or os.getcwd()

            thread_kwargs: dict[str, object] = {
                "model": self._config.model,
                "sandbox": sandbox,
                "cwd": cwd,
                "approval_policy": "never",
            }
            if self._config.instructions:
                thread_kwargs["base_instructions"] = self._config.instructions

            self._thread = await self._codex.thread_start(  # type: ignore[union-attr]
                **thread_kwargs,
            )
            _log.debug(
                "Codex SDK session started: model=%s, bin=%s",
                self._config.model,
                codex_bin,
            )

        result = await self._thread.run(prompt)  # type: ignore[union-attr]
        return result.final_response or ""
