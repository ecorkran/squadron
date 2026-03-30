"""Pipeline actions package.

Exports the Action protocol, ActionType enum, and the action registry.
"""

from __future__ import annotations

from enum import StrEnum

from squadron.pipeline.actions.protocol import Action

__all__ = [
    "Action",
    "ActionType",
    "get_action",
    "list_actions",
    "register_action",
]


class ActionType(StrEnum):
    """Canonical action type identifiers."""

    DISPATCH = "dispatch"
    REVIEW = "review"
    COMPACT = "compact"
    CHECKPOINT = "checkpoint"
    CF_OP = "cf-op"
    COMMIT = "commit"
    DEVLOG = "devlog"


# Module-level registry: action type name -> Action instance
_REGISTRY: dict[str, Action] = {}


def register_action(action_type: str, action: Action) -> None:
    """Register an Action implementation under the given type name."""
    _REGISTRY[action_type] = action


def get_action(action_type: str) -> Action:
    """Look up a registered Action by type name.

    Raises:
        KeyError: If no action is registered under *action_type*.
    """
    if action_type not in _REGISTRY:
        registered = list(_REGISTRY.keys())
        raise KeyError(
            f"Action '{action_type}' is not registered. Available actions: {registered}"
        )
    return _REGISTRY[action_type]


def list_actions() -> list[str]:
    """Return the list of registered action type names."""
    return list(_REGISTRY.keys())
