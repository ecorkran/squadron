"""CodexProvider — creates Codex agents via the official Codex Python SDK."""

from __future__ import annotations

from squadron.core.models import AgentConfig
from squadron.logging import get_logger
from squadron.providers.base import ProviderCapabilities, ProviderType
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.auth import OAuthFileStrategy
from squadron.providers.codex.runtime import resolve_codex_runtime
from squadron.providers.errors import ProviderAuthError, ProviderError

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
        )

    async def create_agent(self, config: AgentConfig) -> CodexAgent:
        """Validate credentials and runtime, then return a ``CodexAgent``.

        Checks importability and file presence only; the runtime is spawned
        lazily by the agent on its first message.
        """
        strategy = OAuthFileStrategy()
        if not strategy.is_valid():
            raise ProviderAuthError(f"No Codex credentials found. {strategy.setup_hint}.")
        resolve_codex_runtime()  # raises ProviderError with the install hint
        _log.debug("Creating Codex agent %r (model=%s)", config.name, config.model)
        return CodexAgent(name=config.name, config=config)

    async def validate_credentials(self) -> bool:
        """Return True if the Codex runtime resolves and credentials exist."""
        try:
            resolve_codex_runtime()
        except ProviderError:
            # A missing extra or binary is the "not usable" answer this
            # boolean check exists to give, not a failure of the check.
            return False
        return OAuthFileStrategy().is_valid()
