"""OpenAICompatibleProvider implementation."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from openai import AsyncOpenAI

from squadron.core.models import AgentConfig
from squadron.logging import get_logger
from squadron.providers.auth import resolve_auth_strategy
from squadron.providers.base import ProviderCapabilities, ProviderType
from squadron.providers.errors import ProviderError

if TYPE_CHECKING:
    from squadron.providers.openai.agent import OpenAICompatibleAgent

_log = get_logger("squadron.providers.openai.provider")


class OpenAICompatibleProvider:
    """Creates API agents backed by the OpenAI Chat Completions API (or compatible)."""

    @property
    def provider_type(self) -> str:
        return ProviderType.OPENAI

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            can_read_files=False,
            supports_system_prompt=True,
            supports_streaming=True,
        )

    async def create_agent(self, config: AgentConfig) -> OpenAICompatibleAgent:
        """Resolve credentials via AuthStrategy, construct AsyncOpenAI client."""
        strategy = resolve_auth_strategy(config, profile=None)
        await strategy.refresh_if_needed()
        credentials = await strategy.get_credentials()
        api_key = credentials["api_key"]

        if config.model is None:
            raise ProviderError("model is required for OpenAI-compatible agents")

        default_headers = config.credentials.get("default_headers")
        client = AsyncOpenAI(
            api_key=api_key,
            base_url=config.base_url,
            default_headers=default_headers,  # type: ignore[arg-type]
        )

        from squadron.providers.openai.agent import OpenAICompatibleAgent

        _log.debug("Creating OpenAI agent %r (model=%s)", config.name, config.model)
        return OpenAICompatibleAgent(
            name=config.name,
            client=client,
            model=config.model,
            system_prompt=config.instructions,
        )

    async def validate_credentials(self) -> bool:
        """Return True if openai is importable and OPENAI_API_KEY is set."""
        try:
            __import__("openai")
        except ImportError:
            return False
        return bool(os.environ.get("OPENAI_API_KEY"))
