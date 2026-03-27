"""Agent and AgentProvider Protocols — contracts for all provider implementations."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable

from squadron.core.models import AgentConfig, AgentState, Message


class ProviderType(StrEnum):
    """Registered provider type identifiers."""

    OPENAI = "openai"
    SDK = "sdk"
    OPENAI_OAUTH = "openai-oauth"


class ProfileName(StrEnum):
    """Built-in profile identifiers."""

    OPENAI = "openai"
    OPENROUTER = "openrouter"
    LOCAL = "local"
    GEMINI = "gemini"
    SDK = "sdk"
    OPENAI_OAUTH = "openai-oauth"


class AuthType(StrEnum):
    """Authentication strategy identifiers."""

    API_KEY = "api_key"
    SESSION = "session"
    OAUTH = "oauth"


@dataclass(frozen=True)
class ProviderCapabilities:
    """Declared capabilities of a provider.

    Callers adapt based on capabilities, not provider identity.
    """

    can_read_files: bool = False
    """Agent can read project files directly (e.g. SDK, Codex sandbox)."""

    supports_system_prompt: bool = True
    """Agent accepts a system prompt via config."""

    supports_streaming: bool = False
    """Agent yields incremental response chunks."""


@runtime_checkable
class Agent(Protocol):
    """A participant that can receive and produce messages."""

    @property
    def name(self) -> str:
        """Agent display name."""
        ...

    @property
    def agent_type(self) -> str:
        """Execution model identifier."""
        ...

    @property
    def state(self) -> AgentState:
        """Current lifecycle state."""
        ...

    def handle_message(self, message: Message) -> AsyncIterator[Message]:
        """Process an incoming message and yield response messages."""
        ...

    async def shutdown(self) -> None:
        """Gracefully shut down the agent."""
        ...


@runtime_checkable
class AgentProvider(Protocol):
    """Creates and manages agents of a specific type."""

    @property
    def provider_type(self) -> str:
        """Provider identifier."""
        ...

    @property
    def capabilities(self) -> ProviderCapabilities:
        """Declared capabilities of this provider."""
        ...

    async def create_agent(self, config: AgentConfig) -> Agent:
        """Create an agent from configuration."""
        ...

    async def validate_credentials(self) -> bool:
        """Check that credentials are valid and the provider is reachable."""
        ...
