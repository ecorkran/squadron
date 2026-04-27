"""Pipeline steps package.

Exports the StepType protocol, StepTypeName enum, and the step-type registry.
"""

from __future__ import annotations

from enum import StrEnum

from squadron.pipeline.steps.protocol import StepType

__all__ = [
    "StepType",
    "StepTypeName",
    "bootstrap_step_types",
    "get_step_type",
    "list_step_types",
    "register_step_type",
]


class StepTypeName(StrEnum):
    """Canonical step type identifiers."""

    DESIGN = "design"
    TASKS = "tasks"
    IMPLEMENT = "implement"
    DISPATCH = "dispatch"
    COMPACT = "compact"
    SUMMARY = "summary"
    REVIEW = "review"
    EACH = "each"
    FAN_OUT = "fan_out"
    LOOP = "loop"
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


_bootstrapped = False


def bootstrap_step_types() -> None:
    """Import every step module so its `register_step_type` call runs.

    Single source of truth for step-type registration. Idempotent: repeat
    calls are cheap no-ops. Call sites that need the registry populated
    (executor, loader, prompt_renderer) invoke this instead of maintaining
    their own import lists.
    """
    global _bootstrapped
    if _bootstrapped:
        return
    # Import for side effect: each module calls register_step_type on import.
    import squadron.pipeline.steps.collection  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.compact  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.devlog  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.dispatch  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.fan_out  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.loop  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.phase  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.review  # noqa: F401  # pyright: ignore[reportUnusedImport]
    import squadron.pipeline.steps.summary  # noqa: F401  # pyright: ignore[reportUnusedImport]

    _bootstrapped = True
