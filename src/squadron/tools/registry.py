"""Process-level registry of tool descriptors.

Mirrors the free-function, module-level-dict shape of
:mod:`squadron.providers.registry`, with one deliberate difference: registering a duplicate
name raises instead of silently overwriting. A tool name is a security-relevant surface, so
two definitions of it is a defect that must fail fast rather than resolve by import order.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

from squadron.tools.errors import ToolNotRegisteredError
from squadron.tools.models import JailSpec, ToolDescriptor, ToolExecutor

_logger = logging.getLogger(__name__)

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


def _resolve_exclusions(root: Path, patterns: Sequence[str]) -> tuple[Path, ...]:
    """Resolve *patterns* against jail root *root*, dropping any that fall outside it.

    A pattern resolving outside the jail can never match a candidate — every candidate is
    already inside the root — so keeping it would give a false sense of coverage. It is
    dropped with a WARNING naming the pattern (design D6), because a misconfigured exclusion
    is an operator problem and silence is how it stays one.
    """
    resolved: list[Path] = []
    for pattern in patterns:
        candidate = (root / pattern).resolve(strict=False)
        if not candidate.is_relative_to(root):
            _logger.warning(
                "discarding tool exclusion %r: resolves to %s, outside the jail root %s",
                pattern,
                candidate,
                root,
            )
            continue
        resolved.append(candidate)
    return tuple(resolved)


def materialize(
    names: Sequence[str],
    cwd: str | Path,
    exclude_patterns: Sequence[str] = (),
) -> dict[str, ToolExecutor]:
    """Bind the named tools to a jail spec built from *cwd* and *exclude_patterns*.

    Both ``cwd`` and the exclusions are resolved exactly once here; every executor receives
    the same :class:`JailSpec`, whose root is the jail the file tools enforce and the working
    directory ``bash`` runs in, and whose exclusions are paths inside that jail that are
    nonetheless refused.

    The spec is built per call and passed by value, so two executor sets materialized with
    different exclusions do not interfere. ``exclude_patterns`` defaults to empty, which is
    exactly today's plain-jail behavior for every caller that does not pass it.

    Raises:
        ToolNotRegisteredError: If any name in *names* is not registered.
    """
    root = Path(cwd).resolve()
    spec = JailSpec(root=root, excluded=_resolve_exclusions(root, exclude_patterns))

    executors: dict[str, ToolExecutor] = {}
    for name in names:
        descriptor = lookup(name)
        if descriptor is None:
            registered = list(_REGISTRY.keys())
            raise ToolNotRegisteredError(
                f"Tool '{name}' is not registered. Available tools: {registered}"
            )
        executors[name] = descriptor.factory(spec)
    return executors
