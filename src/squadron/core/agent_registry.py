"""Agent registry: spawn, track, and manage agent lifecycle."""

from __future__ import annotations

from squadron.core.models import AgentConfig, AgentInfo, AgentState, ShutdownReport
from squadron.logging import get_logger
from squadron.providers.base import Agent
from squadron.providers.registry import get_provider


class AgentRegistryError(Exception):
    """Base for registry-specific errors."""


class AgentNotFoundError(AgentRegistryError):
    """Raised when referencing a non-existent agent name."""


class AgentAlreadyExistsError(AgentRegistryError):
    """Raised when spawning with a duplicate name."""


logger = get_logger(__name__)


class AgentRegistry:
    """Central coordination point for agent lifecycle management.

    Spawns agents by provider configuration, tracks them by unique name,
    provides lookup/enumeration, and manages graceful shutdown.
    """

    def __init__(self) -> None:
        self._agents: dict[str, Agent] = {}
        self._configs: dict[str, AgentConfig] = {}

    async def spawn(self, config: AgentConfig) -> Agent:
        """Create an agent from *config* and track it by name.

        Raises:
            AgentAlreadyExistsError: If *config.name* is already registered.
            KeyError: If *config.provider* is not registered.
            ProviderError: If the provider fails to create the agent.
        """
        if config.name in self._agents:
            raise AgentAlreadyExistsError(f"Agent '{config.name}' already exists in the registry")

        provider = get_provider(config.provider)
        agent = await provider.create_agent(config)

        self._agents[config.name] = agent
        self._configs[config.name] = config

        logger.info(
            "agent.spawned: name=%s agent_type=%s provider=%s",
            config.name,
            config.agent_type,
            config.provider,
        )
        return agent

    def has(self, name: str) -> bool:
        """Return True if an agent with *name* is tracked."""
        return name in self._agents

    def get(self, name: str) -> Agent:
        """Return the Agent instance registered under *name*.

        Raises:
            AgentNotFoundError: If no agent with *name* exists.
        """
        if name not in self._agents:
            raise AgentNotFoundError(f"Agent '{name}' not found in the registry")
        return self._agents[name]

    def list_agents(
        self,
        state: AgentState | None = None,
        provider: str | None = None,
    ) -> list[AgentInfo]:
        """Return AgentInfo summaries for tracked agents, optionally filtered.

        Args:
            state: If given, include only agents in this state.
            provider: If given, include only agents from this provider.
        """
        result: list[AgentInfo] = []
        for name, agent in self._agents.items():
            agent_provider = self._configs[name].provider
            if state is not None and agent.state != state:
                continue
            if provider is not None and agent_provider != provider:
                continue
            result.append(
                AgentInfo(
                    name=agent.name,
                    agent_type=agent.agent_type,
                    provider=agent_provider,
                    state=agent.state,
                )
            )
        return result

    async def shutdown_agent(self, name: str) -> None:
        """Shut down the agent registered under *name* and remove it.

        The agent is always removed, even if ``agent.shutdown()`` raises —
        an agent in an indeterminate state should not remain tracked.

        Raises:
            AgentNotFoundError: If no agent with *name* exists.
        """
        if name not in self._agents:
            raise AgentNotFoundError(f"Agent '{name}' not found in the registry")

        agent = self._agents[name]
        try:
            await agent.shutdown()
        except Exception:
            logger.warning(
                "agent.shutdown_failed: name=%s error=%s",
                name,
                str(agent),
                exc_info=True,
            )
            raise
        finally:
            del self._agents[name]
            del self._configs[name]

        logger.info("agent.shutdown: name=%s", name)

    async def shutdown_all(self) -> ShutdownReport:
        """Shut down every registered agent and clear the registry.

        Each agent's ``shutdown()`` is called individually. Failures are
        collected rather than aborting — best-effort for clean teardown.
        """
        report = ShutdownReport()
        names = list(self._agents.keys())

        for name in names:
            agent = self._agents[name]
            try:
                await agent.shutdown()
                report.succeeded.append(name)
            except Exception as exc:
                report.failed[name] = str(exc)

        self._agents.clear()
        self._configs.clear()

        logger.info(
            "registry.shutdown_all: count=%d succeeded=%d failed=%d",
            len(names),
            len(report.succeeded),
            len(report.failed),
        )
        return report


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Return the shared AgentRegistry singleton, creating on first call."""
    global _registry  # noqa: PLW0603
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def reset_registry() -> None:
    """Reset the singleton. Intended for test cleanup only."""
    global _registry  # noqa: PLW0603
    _registry = None
