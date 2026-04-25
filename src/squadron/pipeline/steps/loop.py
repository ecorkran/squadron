"""LoopStepType — multi-step loop body with configurable retry semantics.

expand() returns [] — the executor handles iteration directly via
_execute_loop_body, mirroring the each and fan_out step patterns.
"""

from __future__ import annotations

from typing import cast

from squadron.pipeline.executor import ExhaustBehavior, LoopCondition
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, register_step_type


class LoopStepType:
    """Step type for multi-step loop bodies with retry semantics.

    The ``steps`` body is executed per iteration; the ``until`` condition is
    evaluated against the aggregated action results of each iteration.
    Nested loop: steps are banned at validation time.
    """

    @property
    def step_type(self) -> str:
        return StepTypeName.LOOP

    def validate(self, config: StepConfig) -> list[ValidationError]:  # noqa: C901
        errors: list[ValidationError] = []
        cfg = config.config
        step_type = self.step_type

        # max: required positive integer (bool is a subclass of int — reject it)
        max_val = cfg.get("max")
        if isinstance(max_val, bool) or not isinstance(max_val, int) or max_val < 1:
            errors.append(
                ValidationError(
                    field="max",
                    message="'max' is required and must be a positive integer",
                    action_type=step_type,
                )
            )

        # until: optional, must be a valid LoopCondition value
        until_val = cfg.get("until")
        if until_val is not None:
            valid_until = [c.value for c in LoopCondition]
            if until_val not in valid_until:
                errors.append(
                    ValidationError(
                        field="until",
                        message=(
                            f"'until' must be one of {valid_until}, got: {until_val!r}"
                        ),
                        action_type=step_type,
                    )
                )

        # on_exhaust: optional, must be a valid ExhaustBehavior value
        on_exhaust_val = cfg.get("on_exhaust")
        if on_exhaust_val is not None:
            valid_exhaust = [b.value for b in ExhaustBehavior]
            if on_exhaust_val not in valid_exhaust:
                errors.append(
                    ValidationError(
                        field="on_exhaust",
                        message=(
                            f"'on_exhaust' must be one of {valid_exhaust}, "
                            f"got: {on_exhaust_val!r}"
                        ),
                        action_type=step_type,
                    )
                )

        # strategy: optional, must be a string (strategies implemented in slice 184)
        strategy_val = cfg.get("strategy")
        if strategy_val is not None and not isinstance(strategy_val, str):
            errors.append(
                ValidationError(
                    field="strategy",
                    message="'strategy' must be a string",
                    action_type=step_type,
                )
            )

        # steps: required, non-empty list
        steps_val = cfg.get("steps")
        if steps_val is None:
            errors.append(
                ValidationError(
                    field="steps",
                    message="'steps' is required",
                    action_type=step_type,
                )
            )
        elif not isinstance(steps_val, list):
            errors.append(
                ValidationError(
                    field="steps",
                    message="'steps' must be a list",
                    action_type=step_type,
                )
            )
        elif not steps_val:
            errors.append(
                ValidationError(
                    field="steps",
                    message="'steps' must be a non-empty list",
                    action_type=step_type,
                )
            )
        else:
            errors.extend(
                self._validate_inner_steps(cast(list[object], steps_val), step_type)
            )

        return errors

    def _validate_inner_steps(
        self,
        steps: list[object],
        step_type: str,
    ) -> list[ValidationError]:
        """Check nested-loop ban on each inner step."""
        errors: list[ValidationError] = []
        for idx, raw_inner in enumerate(steps):
            if not isinstance(raw_inner, dict) or len(raw_inner) != 1:  # type: ignore[arg-type]
                continue
            inner_step = cast(dict[str, object], raw_inner)
            inner_type = str(next(iter(inner_step)))
            inner_cfg = inner_step[inner_type]
            if isinstance(inner_cfg, dict):
                inner_cfg_typed = cast(dict[str, object], inner_cfg)
                inner_name = str(inner_cfg_typed.get("name", f"{inner_type}-{idx}"))
            else:
                inner_name = f"{inner_type}-{idx}"
            # Ban (a): inner step config carries a loop: sub-field
            if isinstance(inner_cfg, dict) and "loop" in cast(
                dict[str, object], inner_cfg
            ):
                errors.append(
                    ValidationError(
                        field="steps",
                        message=(
                            f"inner step '{inner_name}' may not carry a 'loop:' "
                            f"sub-field; nested loops are not supported in v1"
                        ),
                        action_type=step_type,
                    )
                )
            # Ban (b): inner step type is loop
            if inner_type == StepTypeName.LOOP:
                errors.append(
                    ValidationError(
                        field="steps",
                        message=(
                            f"inner step '{inner_name}' may not be of type 'loop'; "
                            f"nested loops are not supported in v1"
                        ),
                        action_type=step_type,
                    )
                )
        return errors

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Return empty — executor handles iteration via _execute_loop_body."""
        return []


register_step_type(StepTypeName.LOOP, LoopStepType())
