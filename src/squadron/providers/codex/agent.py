"""CodexAgent — agentic provider via Codex MCP server (stdio transport)."""

from __future__ import annotations

import io
import logging
import os
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession, StdioServerParameters, stdio_client

from squadron.core.models import AgentConfig, AgentState, Message, MessageType
from squadron.logging import get_logger
from squadron.providers.base import ProviderType
from squadron.providers.errors import ProviderError

_log = get_logger("squadron.providers.codex.agent")

# Suppress MCP library validation warnings for Codex custom notifications
# (codex/event). These are non-standard MCP notifications that the library
# doesn't recognize but are harmless.
logging.getLogger("mcp").setLevel(logging.ERROR)

_DEFAULT_SANDBOX = "read-only"


class CodexAgent:
    """Agentic provider backed by Codex MCP server (``codex mcp-server``).

    The MCP client is started lazily on first ``handle_message()`` call
    to avoid spawning a subprocess for agents that may never be used.
    """

    def __init__(self, name: str, config: AgentConfig) -> None:
        self._name = name
        self._config = config
        self._state = AgentState.idle
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None
        self._thread_id: str | None = None

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
            if self._session is None:
                await self._start_client()

            if self._thread_id is None:
                response = await self._codex_start(message.content)
            else:
                response = await self._codex_reply(message.content)

            yield response
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"Codex agent error: {exc}") from exc
        finally:
            self._state = AgentState.idle

    async def shutdown(self) -> None:
        """Tear down the MCP client and subprocess."""
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
            self._exit_stack = None
        self._session = None
        self._thread_id = None
        self._state = AgentState.terminated

    async def _start_client(self) -> None:
        """Spawn ``codex mcp-server`` and initialize MCP session."""
        codex_cmd = self._resolve_codex_command()
        server_params = StdioServerParameters(
            command=codex_cmd,
            args=["mcp-server"],
        )

        self._exit_stack = AsyncExitStack()
        try:
            # Suppress MCP stderr output (codex/event validation warnings)
            devnull = io.StringIO()
            transport = await self._exit_stack.enter_async_context(
                stdio_client(server_params, errlog=devnull)
            )
            read_stream, write_stream = transport
            session = await self._exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            await session.initialize()
            self._session = session
            _log.debug("Codex MCP session initialized for agent %r", self._name)
        except Exception:
            await self._exit_stack.aclose()
            self._exit_stack = None
            raise

    def _resolve_codex_command(self) -> str:
        """Find the ``codex`` CLI binary on PATH."""
        import shutil

        cmd = shutil.which("codex")
        if cmd is None:
            raise ProviderError(
                "Codex CLI not found on PATH. Install it with: npm i -g @openai/codex"
            )
        return cmd

    async def _codex_start(self, prompt: str) -> Message:
        """Start a new Codex session via the ``codex`` MCP tool."""
        assert self._session is not None  # noqa: S101
        if self._config.model is None:
            raise ProviderError(
                "model is required for Codex agents. "
                "Specify --model or use a model alias (e.g. codex-agent)."
            )
        model = self._config.model
        sandbox = self._config.credentials.get("sandbox", _DEFAULT_SANDBOX)
        cwd = self._config.cwd or os.getcwd()

        arguments: dict[str, Any] = {
            "prompt": prompt,
            "model": model,
            "approval-policy": "never",
            "sandbox": sandbox,
            "cwd": cwd,
        }
        _log.debug("Calling codex tool: model=%s, sandbox=%s", model, sandbox)
        result = await self._session.call_tool("codex", arguments)

        response_text = self._extract_text(result)
        thread_id = self._extract_thread_id(result)
        if thread_id:
            self._thread_id = thread_id

        return Message(
            sender=self._name,
            recipients=[],
            content=response_text,
            message_type=MessageType.chat,
        )

    async def _codex_reply(self, prompt: str) -> Message:
        """Continue an existing Codex session via ``codex-reply`` MCP tool."""
        assert self._session is not None  # noqa: S101
        assert self._thread_id is not None  # noqa: S101

        arguments: dict[str, Any] = {
            "prompt": prompt,
            "threadId": self._thread_id,
        }
        _log.debug("Calling codex-reply: threadId=%s", self._thread_id)
        result = await self._session.call_tool("codex-reply", arguments)
        response_text = self._extract_text(result)
        return Message(
            sender=self._name,
            recipients=[],
            content=response_text,
            message_type=MessageType.chat,
        )

    def _extract_text(self, result: Any) -> str:
        """Extract text content from an MCP CallToolResult."""
        if result.isError:
            parts = [c.text for c in result.content if hasattr(c, "text")]
            raise ProviderError(f"Codex tool error: {' '.join(parts)}")

        parts = [c.text for c in result.content if hasattr(c, "text")]
        return "\n".join(parts) if parts else ""

    def _extract_thread_id(self, result: Any) -> str | None:
        """Extract thread ID from structured content if present."""
        if result.structuredContent and "threadId" in result.structuredContent:
            return str(result.structuredContent["threadId"])
        if result._meta and "threadId" in result._meta:
            return str(result._meta["threadId"])
        return None
