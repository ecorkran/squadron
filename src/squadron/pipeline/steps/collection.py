"""EachStepType — iterates a collection of items and runs inner steps for each."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import cast

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, get_step_type, register_step_type
from squadron.pipeline.steps.utils import unpack_inner_steps

_SOURCE_PATTERN = re.compile(r"(\w+)\.(\w+)\([^)]*\)")


class ItemFailurePolicy(StrEnum):
    """What ``each`` does when an item's body fails (slice 195 D5)."""

    STOP = "stop"
    CONTINUE = "continue"


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
        else:
            errors.extend(self._validate_inner_steps(config))

        policy = cfg.get("on_item_failure")
        if policy is not None and policy not in ItemFailurePolicy.__members__.values():
            valid = [p.value for p in ItemFailurePolicy]
            errors.append(
                ValidationError(
                    field="on_item_failure",
                    message=f"'on_item_failure' must be one of {valid}, got: {policy!r}",
                    action_type=StepTypeName.EACH,
                )
            )

        return errors

    def _validate_inner_steps(self, config: StepConfig) -> list[ValidationError]:
        """Validate each body step with its own step type (D3); ban nested each."""
        errors: list[ValidationError] = []
        for inner in self.inner_steps(config):
            if inner.step_type == StepTypeName.EACH:
                errors.append(
                    ValidationError(
                        field="steps",
                        message=f"inner step '{inner.name}' may not be of type 'each'; "
                        "nested each is not supported",
                        action_type=StepTypeName.EACH,
                    )
                )
                continue
            try:
                inner_impl = get_step_type(inner.step_type)
            except KeyError as exc:
                errors.append(
                    ValidationError(field="steps", message=str(exc), action_type=StepTypeName.EACH)
                )
                continue
            errors.extend(inner_impl.validate(inner))
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
