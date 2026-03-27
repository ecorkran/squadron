"""SquadronEngine — central coordination for agents and conversation history."""

from __future__ import annotations

import importlib

from squadron.core.agent_registry import AgentRegistry
from squadron.core.models import (
    AgentConfig,
    AgentInfo,
    AgentState,
    Message,
    MessageType,
    ShutdownReport,
)
from squadron.logging import get_logger
from squadron.providers.base import Agent

logger = get_logger(__name__)


# Provider type → module name mapping. Module names are implementation
# details; provider type strings are the public identifiers.
_PROVIDER_MODULES: dict[str, str] = {
    "openai": "openai",
    "sdk": "sdk",
    "openai-oauth": "codex",
}


def _load_provider(name: str) -> None:
    """Import the provider module to trigger its auto-registration side effect."""
    module_name = _PROVIDER_MODULES.get(name, name)
    try:
        importlib.import_module(f"squadron.providers.{module_name}")
    except ImportError:
        pass  # Unknown name; let get_provider raise KeyError naturally


class SquadronEngine:
    """Composes AgentRegistry with conversation history tracking.

    The engine is the single coordination point for agent lifecycle and
    messaging within the daemon process. It owns its own registry instance
    (not the module-level singleton) and maintains per-agent conversation
    histories at the squadron level.
    """

    def __init__(self) -> None:
        self._registry = AgentRegistry()
        self._histories: dict[str, list[Message]] = {}

    @property
    def registry(self) -> AgentRegistry:
        """Expose registry for direct access when needed (e.g., route layer)."""
        return self._registry

    async def spawn_agent(self, config: AgentConfig) -> AgentInfo:
        """Spawn an agent and initialize its conversation history.

        Calls _load_provider to auto-register the provider module before
        delegating to the registry.
        """
        _load_provider(config.provider)
        agent = await self._registry.spawn(config)
        self._histories[config.name] = []

        logger.info("engine.spawn: name=%s provider=%s", config.name, config.provider)
        return AgentInfo(
            name=agent.name,
            agent_type=agent.agent_type,
            provider=config.provider,
            state=agent.state,
        )

    def list_agents(
        self,
        state: str | None = None,
        provider: str | None = None,
    ) -> list[AgentInfo]:
        """List agents, optionally filtered by state or provider."""
        agent_state = AgentState(state) if state else None
        return self._registry.list_agents(state=agent_state, provider=provider)

    def get_agent(self, name: str) -> Agent:
        """Get an agent by name. Raises AgentNotFoundError if not found."""
        return self._registry.get(name)

    async def send_message(self, agent_name: str, content: str) -> list[Message]:
        """Send a message to an agent and record the conversation.

        Creates a human Message, records it, calls the agent's handle_message,
        collects and records response messages, and returns them.
        """
        agent = self._registry.get(agent_name)

        human_msg = Message(
            sender="human",
            recipients=[agent_name],
            content=content,
            message_type=MessageType.chat,
        )
        self._histories[agent_name].append(human_msg)

        responses: list[Message] = []
        async for msg in agent.handle_message(human_msg):
            responses.append(msg)

        self._histories[agent_name].extend(responses)
        return responses

    def get_history(self, agent_name: str) -> list[Message]:
        """Return conversation history for an agent.

        Returns empty list for unknown agents — supports querying history
        after agent shutdown or for agents that never existed.
        """
        return self._histories.get(agent_name, [])

    async def shutdown_agent(self, name: str) -> None:
        """Shut down a single agent. History is retained (per design)."""
        await self._registry.shutdown_agent(name)
        logger.info("engine.shutdown: name=%s", name)

    async def shutdown_all(self) -> ShutdownReport:
        """Shut down all agents. Returns ShutdownReport."""
        report = await self._registry.shutdown_all()
        logger.info(
            "engine.shutdown_all: succeeded=%d failed=%d",
            len(report.succeeded),
            len(report.failed),
        )
        return report
