"""Process-level registry of tool descriptors.

Mirrors the free-function, module-level-dict shape of
:mod:`squadron.providers.registry`, with one deliberate difference: registering a duplicate
name raises instead of silently overwriting. A tool name is a security-relevant surface, so
two definitions of it is a defect that must fail fast rather than resolve by import order.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from squadron.tools.errors import ToolNotRegisteredError
from squadron.tools.models import ToolDescriptor, ToolExecutor

# Module-level registry: tool name -> descriptor
_REGISTRY: dict[str, ToolDescriptor] = {}


def register(descriptor: ToolDescriptor) -> None:
    """Register *descriptor* under its own name.

    Raises:
        ValueError: If a tool is already registered under that name.
    """
    if descriptor.name in _REGISTRY:
        raise ValueError(f"Tool '{descriptor.name}' is already registered.")
    _REGISTRY[descriptor.name] = descriptor


def lookup(name: str) -> ToolDescriptor | None:
    """Return the descriptor registered under *name*, or None if there is none."""
    return _REGISTRY.get(name)


def list_tools() -> list[str]:
    """Return the names of all currently registered tools."""
    return list(_REGISTRY.keys())


def materialize(names: Sequence[str], cwd: str | Path) -> dict[str, ToolExecutor]:
    """Bind the named tools to *cwd* and return their executors.

    ``cwd`` is resolved exactly once here; every executor receives the same resolved path,
    which is the jail root the file tools enforce and the working directory ``bash`` runs in.

    Raises:
        ToolNotRegisteredError: If any name in *names* is not registered.
    """
    resolved = Path(cwd).resolve()

    executors: dict[str, ToolExecutor] = {}
    for name in names:
        descriptor = lookup(name)
        if descriptor is None:
            registered = list(_REGISTRY.keys())
            raise ToolNotRegisteredError(
                f"Tool '{name}' is not registered. Available tools: {registered}"
            )
        executors[name] = descriptor.factory(resolved)
    return executors
