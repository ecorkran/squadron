"""EachStepType — iterates a collection of items and runs inner steps for each."""

from __future__ import annotations

import re
from typing import cast

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type
from squadron.pipeline.steps.utils import unpack_inner_steps

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
                            f"'source' must match pattern namespace.function(...), got: {source!r}"
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

    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw: object = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        raw_list = cast(list[object], raw)
        return unpack_inner_steps([cast(dict[str, object], s) for s in raw_list if isinstance(s, dict)])

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Return empty list — executor handles each execution directly."""
        return []


register_step_type(StepTypeName.EACH, EachStepType())
