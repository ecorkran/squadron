"""EachStepType — iterates a collection of items and runs inner steps for each."""

from __future__ import annotations

import re

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type

_SOURCE_PATTERN = re.compile(r"(\w+)\.(\w+)\([^)]*\)")


class EachStepType:
    """Step type that iterates over a source collection.

    ``expand()`` returns an empty list — the executor handles ``each``
    execution directly via its own branch.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.EACH

    def validate(self, config: StepConfig) -> list[ValidationError]:
        errors: list[ValidationError] = []
        cfg = config.config

        source = cfg.get("source")
        if source is None:
            errors.append(
                ValidationError(
                    field="source",
                    message="'source' is required for each step",
                    action_type=StepTypeName.EACH,
                )
            )
        elif isinstance(source, str):
            if not _SOURCE_PATTERN.fullmatch(source.strip()):
                errors.append(
                    ValidationError(
                        field="source",
                        message=(
                            f"'source' must match pattern namespace.function(...), "
                            f"got: {source!r}"
                        ),
                        action_type=StepTypeName.EACH,
                    )
                )

        if cfg.get("as") is None:
            errors.append(
                ValidationError(
                    field="as",
                    message="'as' is required for each step",
                    action_type=StepTypeName.EACH,
                )
            )

        inner_steps = cfg.get("steps")
        if inner_steps is None:
            errors.append(
                ValidationError(
                    field="steps",
                    message="'steps' is required for each step",
                    action_type=StepTypeName.EACH,
                )
            )
        elif isinstance(inner_steps, list) and not inner_steps:
            errors.append(
                ValidationError(
                    field="steps",
                    message="'steps' must be a non-empty list",
                    action_type=StepTypeName.EACH,
                )
            )

        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Return empty list — executor handles each execution directly."""
        return []


register_step_type(StepTypeName.EACH, EachStepType())
