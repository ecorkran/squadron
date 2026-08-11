"""Events package: user-definable actions on supported events.

The set of events is closed — adding a new ``EventType`` member is a
squadron change, never a user change (design D2). Users bind callables to
these events via an ``events.yaml`` manifest; they do not invent new events.
"""

from __future__ import annotations

import inspect
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from squadron.events.protocol import EventAction

__all__ = [
    "EventType",
    "bootstrap_event_actions",
    "get_event_action",
    "list_event_actions",
    "register_event_action",
]


class EventType(StrEnum):
    """Canonical, closed set of events a user action may bind to."""

    COMMIT = "commit"
    POST_ACTION = "post-action"


# Module-level registry: namespaced action name -> EventAction instance
_REGISTRY: dict[str, EventAction] = {}

#: Modules under this prefix may register names starting with "squadron.".
_BUILTIN_MODULE_PREFIX = "squadron.events.builtin"


def register_event_action(action: EventAction) -> None:
    """Register an EventAction under its namespaced ``name``.

    Raises:
        ValueError: If the name has no dot, is already registered, or
            starts with the reserved ``squadron.`` prefix while the calling
            module is not under ``squadron.events.builtin``.
    """
    name = action.name

    if "." not in name:
        raise ValueError(f"Event action name '{name}' must be namespaced as '{{namespace}}.{{name}}'")

    if name in _REGISTRY:
        raise ValueError(f"Event action '{name}' is already registered")

    if name.startswith("squadron."):
        caller_frame = inspect.stack()[1]
        caller_module = caller_frame.frame.f_globals.get("__name__", "")
        if not caller_module.startswith(_BUILTIN_MODULE_PREFIX):
            raise ValueError(
                f"Event action '{name}' uses the reserved 'squadron.' prefix but is "
                f"registered from '{caller_module}', not {_BUILTIN_MODULE_PREFIX}.*"
            )

    _REGISTRY[name] = action


def get_event_action(name: str) -> EventAction:
    """Look up a registered EventAction by namespaced name.

    Raises:
        KeyError: If no action is registered under *name*.
    """
    if name not in _REGISTRY:
        registered = list(_REGISTRY.keys())
        raise KeyError(f"Event action '{name}' is not registered. Available actions: {registered}")
    return _REGISTRY[name]


def list_event_actions() -> list[str]:
    """Return the list of registered event action names."""
    return list(_REGISTRY.keys())


_bootstrapped = False


def bootstrap_event_actions() -> None:
    """Import every built-in event action module so it self-registers.

    Idempotent: repeat calls are cheap no-ops. Mirrors
    ``squadron.pipeline.steps.bootstrap_step_types``.
    """
    global _bootstrapped
    if _bootstrapped:
        return

    import squadron.events.builtin.dispatch_artifact as _b_dispatch_artifact
    import squadron.events.builtin.frontmatter_gate as _b_frontmatter_gate
    import squadron.events.builtin.revision_stamp as _b_revision_stamp

    _ = (_b_dispatch_artifact, _b_frontmatter_gate, _b_revision_stamp)

    _bootstrapped = True
