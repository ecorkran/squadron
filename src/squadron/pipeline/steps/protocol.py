"""StepType protocol — defines the interface all pipeline step types must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from squadron.pipeline.models import StepConfig, ValidationError

#: Keys the executor reads on any step, whatever its type: ``loop`` (a per-step retry
#: block, executor.py ``_execute_step``) and ``step_model`` (the model cascade level,
#: executor.py ``_step_resolves_to_sdk``). Not part of any step type's own keys.
EXECUTOR_STEP_KEYS = frozenset({"loop", "step_model"})


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

    @property
    def known_keys(self) -> frozenset[str]:
        """Every config key this step type's validate or expand reads.

        ``sq run --validate --strict`` reports any other key (slice 949 D7).
        """
        ...

    def needs_context_forge(self, config: StepConfig) -> bool:
        """Whether running this step calls Context Forge (#288).

        Every step type declares it. ``sq run`` checks that cf can see a project only
        when some step in the pipeline answers True.
        """
        ...

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Expand this step into a list of (action_type, action_config) pairs."""
        ...

    def validate(self, config: StepConfig) -> list[ValidationError]:
        """Validate the step's configuration section.

        Returns an empty list if the configuration is valid.
        """
        ...
