"""Shared fixtures for server tests: mock agent/provider and engine/app/client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Generator
from typing import Any

import httpx
import pytest

from squadron.core.models import (
    AgentConfig,
    AgentState,
    Message,
    MessageType,
)
from squadron.providers import registry as reg_module
from squadron.providers.base import Agent
from squadron.server.app import create_app
from squadron.server.engine import SquadronEngine


class MockAgent:
    """Test double satisfying the Agent Protocol with controllable responses."""

    def __init__(self, name: str) -> None:
        self._name = name
        self._state = AgentState.idle
        self._responses: list[Message] = [
            Message(
                sender=name,
                recipients=["human"],
                content="mock response",
                message_type=MessageType.chat,
            )
        ]
        self._shutdown_called = False

    @property
    def name(self) -> str:
        return self._name

    @property
    def agent_type(self) -> str:
        return "api"

    @property
    def state(self) -> AgentState:
        return self._state

    async def handle_message(self, message: Message) -> AsyncIterator[Message]:
        self._state = AgentState.processing
        try:
            for msg in self._responses:
                yield msg
        finally:
            self._state = AgentState.idle

    async def shutdown(self) -> None:
        self._shutdown_called = True
        self._state = AgentState.terminated


class MockProvider:
    """Test double satisfying the AgentProvider Protocol."""

    def __init__(self) -> None:
        self._agents: dict[str, MockAgent] = {}

    @property
    def provider_type(self) -> str:
        return "mock"

    async def create_agent(self, config: AgentConfig) -> Agent:
        agent = MockAgent(config.name)
        self._agents[config.name] = agent
        return agent

    async def validate_credentials(self) -> bool:
        return True


@pytest.fixture(autouse=True)
def _clean_provider_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Save and restore provider registry state so tests are isolated."""
    original = dict(reg_module._REGISTRY)  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    yield
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.update(original)  # pyright: ignore[reportPrivateUsage]


@pytest.fixture
def mock_provider() -> MockProvider:
    """A fresh MockProvider instance."""
    return MockProvider()


@pytest.fixture
def engine(mock_provider: MockProvider) -> SquadronEngine:
    """SquadronEngine with mock provider registered."""
    eng = SquadronEngine()
    reg_module.register_provider("mock", mock_provider)
    return eng


@pytest.fixture
def app(engine: SquadronEngine) -> Any:
    """FastAPI test app backed by the engine fixture."""
    return create_app(engine)


@pytest.fixture
async def async_client(app: Any) -> AsyncIterator[httpx.AsyncClient]:
    """httpx AsyncClient using ASGITransport for in-process route testing."""
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        yield client
