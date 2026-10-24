"""Action protocol — defines the interface all pipeline actions must satisfy."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Protocol, runtime_checkable

from squadron.pipeline.models import ActionContext, ActionResult, ValidationError


@runtime_checkable
class Action(Protocol):
    """Interface for all pipeline action implementations.

    Every action must expose its type name, execute asynchronously against
    an ActionContext, and validate its configuration section.
    """

    @property
    def action_type(self) -> str:
        """Canonical action type identifier (matches ActionType enum value)."""
        ...

    async def execute(self, context: ActionContext) -> ActionResult:
        """Execute this action and return its result."""
        ...

    def validate(self, config: dict[str, object]) -> list[ValidationError]:
        """Validate the action's configuration section.

        Returns an empty list if the configuration is valid.
        """
        ...


@runtime_checkable
class RunPreflight(Protocol):
    """An action that can refuse a fresh run at its start, before any step spends (#256)."""

    def preflight(self, params: Mapping[str, object], cwd: str) -> None:
        """Raise ValueError when this action would fail on the run's starting state."""
        ...
