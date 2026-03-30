"""Pipeline steps package.

Exports the StepType protocol, StepTypeName enum, and the step-type registry.
"""

from __future__ import annotations

from enum import StrEnum

from squadron.pipeline.steps.protocol import StepType

__all__ = [
    "StepType",
    "StepTypeName",
    "get_step_type",
    "list_step_types",
    "register_step_type",
]


class StepTypeName(StrEnum):
    """Canonical step type identifiers."""

    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENT = "implement"
    COMPACT = "compact"
    REVIEW = "review"
    EACH = "each"
    DEVLOG = "devlog"


# Module-level registry: step type name -> StepType instance
_REGISTRY: dict[str, StepType] = {}


def register_step_type(step_type: str, impl: StepType) -> None:
    """Register a StepType implementation under the given type name."""
    _REGISTRY[step_type] = impl


def get_step_type(step_type: str) -> StepType:
    """Look up a registered StepType by type name.

    Raises:
        KeyError: If no step type is registered under *step_type*.
    """
    if step_type not in _REGISTRY:
        registered = list(_REGISTRY.keys())
        raise KeyError(
            f"Step type '{step_type}' is not registered. "
            f"Available step types: {registered}"
        )
    return _REGISTRY[step_type]


def list_step_types() -> list[str]:
    """Return the list of registered step type names."""
    return list(_REGISTRY.keys())
