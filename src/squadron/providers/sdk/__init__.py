"""Claude SDK Agent Provider using claude-agent-sdk."""

from __future__ import annotations

from squadron.providers.base import ProviderType
from squadron.providers.registry import register_provider
from squadron.providers.sdk.agent import ClaudeSDKAgent
from squadron.providers.sdk.provider import ClaudeSDKProvider

# Auto-register on import.
_provider = ClaudeSDKProvider()
register_provider(ProviderType.SDK, _provider)

__all__ = ["ClaudeSDKProvider", "ClaudeSDKAgent"]
