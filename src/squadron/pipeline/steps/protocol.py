"""StepType protocol — defines the interface all pipeline step types must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from squadron.pipeline.models import StepConfig, ValidationError


@runtime_checkable
class StepType(Protocol):
    """Interface for all pipeline step-type implementations.

    A step type knows how to expand a StepConfig into a sequence of
    (action_type, config) pairs and validate its configuration.
    """

    @property
    def step_type(self) -> str:
        """Canonical step type identifier (matches StepTypeName enum value)."""
        ...

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Expand this step into a list of (action_type, action_config) pairs."""
        ...

    def validate(self, config: StepConfig) -> list[ValidationError]:
        """Validate the step's configuration section.

        Returns an empty list if the configuration is valid.
        """
        ...
