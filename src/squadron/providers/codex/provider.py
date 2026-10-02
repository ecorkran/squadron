"""CodexProvider — creates Codex agents via the official Codex Python SDK."""

from __future__ import annotations

from squadron.core.models import AgentConfig
from squadron.logging import get_logger
from squadron.providers.base import ProviderCapabilities, ProviderType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.auth import OAuthFileStrategy
from squadron.providers.errors import ProviderAuthError

_log = get_logger("squadron.providers.codex.provider")


class CodexProvider:
    """Creates agentic Codex agents backed by the Codex Python SDK."""

    @property
    def provider_type(self) -> str:
        return ProviderType.OPENAI_OAUTH

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_read_files=True,
            supports_system_prompt=True,
            supports_streaming=False,
            applies_effort=True,
        )

    async def create_agent(self, config: AgentConfig) -> CodexAgent:
        """Validate credentials, then return a ``CodexAgent``.

        Checks file presence only; the runtime is spawned lazily by the agent
        on its first message.
        """
        strategy = OAuthFileStrategy()
        if not strategy.is_valid():
            raise ProviderAuthError(f"No Codex credentials found. {strategy.setup_hint}.")
        _log.debug("Creating Codex agent %r (model=%s)", config.name, config.model)
        return CodexAgent(name=config.name, config=config)

    async def validate_credentials(self) -> bool:
        """Return True if Codex credentials exist."""
        return OAuthFileStrategy().is_valid()
