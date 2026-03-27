"""Codex Agent Provider — agentic tasks via Codex MCP server."""

from __future__ import annotations

from squadron.providers.base import ProviderType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.provider import CodexProvider
from squadron.providers.registry import register_provider

# Auto-register on import.
_provider = CodexProvider()
register_provider(ProviderType.OPENAI_OAUTH, _provider)

__all__ = ["CodexProvider", "CodexAgent"]
