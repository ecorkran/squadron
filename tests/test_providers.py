"""Tests for provider registry, Agent/AgentProvider Protocols, and error hierarchy."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator

import pytest

from squadron.core.models import AgentConfig, AgentState, Message
from squadron.providers import registry as reg_module
from squadron.providers.base import Agent, AgentProvider, ProviderCapabilities
from squadron.providers.errors import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderError,
    ProviderTimeoutError,
)
from squadron.providers.registry import (
    get_provider,
    list_providers,
    register_provider,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockAgentProvider:
    """Minimal implementation satisfying AgentProvider Protocol."""

    @property
    def provider_type(self) -> str:
        return "mock"

    @property
    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities()

    async def create_agent(self, config: AgentConfig) -> _MockAgent:
        return _MockAgent(config.name, config.agent_type)

    async def validate_credentials(self) -> bool:
        return True


class _MockAgent:
    """Minimal implementation satisfying Agent Protocol."""

    def __init__(self, name: str, agent_type: str) -> None:
        self._name = name
        self._agent_type = agent_type
        self._state = AgentState.idle

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return self._agent_type

    @property
    def state(self) -> AgentState:
        return self._state

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        yield Message(sender=self._name, recipients=[message.sender], content="reply")

    async def shutdown(self) -> None:
        self._state = AgentState.terminated


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Isolate registry state between tests."""
    original = dict(reg_module._REGISTRY)  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    yield
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.update(original)  # pyright: ignore[reportPrivateUsage]


# ---------------------------------------------------------------------------
# Registry tests
# ---------------------------------------------------------------------------


def test_register_provider_stores_instance() -> None:
    provider = _MockAgentProvider()
    register_provider("mock", provider)
    assert "mock" in list_providers()


def test_get_provider_returns_registered_instance() -> None:
    provider = _MockAgentProvider()
    register_provider("mock", provider)
    result = get_provider("mock")
    assert result is provider
    assert result.provider_type == "mock"


def test_get_provider_raises_for_unregistered() -> None:
    with pytest.raises(KeyError, match="unregistered"):
        get_provider("unregistered")


def test_list_providers_returns_registered_names() -> None:
    register_provider("provA", _MockAgentProvider())
    register_provider("provB", _MockAgentProvider())
    names = list_providers()
    assert "provA" in names
    assert "provB" in names


# ---------------------------------------------------------------------------
# Protocol structural tests
# ---------------------------------------------------------------------------


def test_agent_provider_protocol_structural() -> None:
    """_MockAgentProvider satisfies AgentProvider Protocol at runtime."""
    provider = _MockAgentProvider()
    assert isinstance(provider, AgentProvider)


def test_agent_protocol_structural() -> None:
    """_MockAgent satisfies Agent Protocol at runtime."""
    agent = _MockAgent("test", "sdk")
    assert isinstance(agent, Agent)


# ---------------------------------------------------------------------------
# Error hierarchy tests
# ---------------------------------------------------------------------------


def test_provider_auth_error_is_provider_error() -> None:
    assert issubclass(ProviderAuthError, ProviderError)


def test_provider_api_error_is_provider_error() -> None:
    assert issubclass(ProviderAPIError, ProviderError)


def test_provider_timeout_error_is_provider_error() -> None:
    assert issubclass(ProviderTimeoutError, ProviderError)


def test_provider_api_error_status_code() -> None:
    err = ProviderAPIError("rate limited", status_code=429)
    assert str(err) == "rate limited"
    assert err.status_code == 429


def test_provider_api_error_status_code_defaults_none() -> None:
    err = ProviderAPIError("generic error")
    assert err.status_code is None
