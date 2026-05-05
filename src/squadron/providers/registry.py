"""Provider registry — maps provider type names to AgentProvider instances."""

from __future__ import annotations

from squadron.providers.base import AgentProvider

# Module-level registry: provider type name -> AgentProvider instance
_REGISTRY: dict[str, AgentProvider] = {}


def register_provider(name: str, provider: AgentProvider) -> None:
    """Register an AgentProvider instance under the given provider type name."""
    _REGISTRY[name] = provider


def get_provider(name: str) -> AgentProvider:
    """Look up a registered AgentProvider by type name.

    Raises:
        KeyError: If no provider is registered under *name*.
    """
    if name not in _REGISTRY:
        registered = list(_REGISTRY.keys())
        raise KeyError(f"Provider '{name}' is not registered. Available providers: {registered}")
    return _REGISTRY[name]


def list_providers() -> list[str]:
    """Return the type names of all currently registered providers."""
    return list(_REGISTRY.keys())
