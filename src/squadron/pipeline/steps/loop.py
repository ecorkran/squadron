"""LoopStepType — multi-step loop body with configurable retry semantics.

expand() returns [] — the executor handles iteration directly via
_execute_loop_body, mirroring the each and fan_out step patterns.
"""

from __future__ import annotations

from typing import cast

from squadron.pipeline.executor import ExhaustBehavior, LoopCondition
from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName, get_step_type, register_step_type
from squadron.pipeline.steps.utils import unpack_inner_steps

_VERDICT_BEARING_ACTION_TYPES = frozenset({"review", "gate"})
_COMMIT_ACTION_TYPE = "commit"


class LoopStepType:
    """Step type for multi-step loop bodies with retry semantics.

    The ``steps`` body is executed per iteration; the ``until`` condition is
    evaluated against the aggregated action results of each iteration.
    Nested loop: steps are banned at validation time.
    """

    @property
    def step_type(self) -> str:
        """Return the registered step-type name (``"loop"``)."""
        return StepTypeName.LOOP

    def validate(self, config: StepConfig) -> list[ValidationError]:  # noqa: C901
        """Validate the loop step config and return any errors found."""
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
                        message=(f"'until' must be one of {valid_until}, got: {until_val!r}"),
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
                            f"'on_exhaust' must be one of {valid_exhaust}, got: {on_exhaust_val!r}"
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

        # commit_each_iteration: optional, must be a bool (0/1 rejected —
        # bool is a subclass of int, but that is not what's accepted here)
        commit_each_iteration_val = cfg.get("commit_each_iteration")
        if commit_each_iteration_val is not None and not isinstance(commit_each_iteration_val, bool):
            errors.append(
                ValidationError(
                    field="commit_each_iteration",
                    message="'commit_each_iteration' must be a boolean",
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
            errors.extend(self._validate_inner_steps(cast(list[object], steps_val), step_type))
            if until_val is not None:
                errors.extend(self._validate_verdict_count(cast(list[object], steps_val), step_type))
            if commit_each_iteration_val is True:
                errors.extend(
                    self._validate_commit_each_iteration(cast(list[object], steps_val), step_type)
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
            if isinstance(inner_cfg, dict) and "loop" in cast(dict[str, object], inner_cfg):
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

    def _walk_valid_inner_action_types(
        self,
        steps: list[object],
    ) -> list[tuple[StepConfig, list[str]]]:
        """Return ``(inner_step, action_types)`` for each inner step that
        passes its own ``validate()``.

        Shared by ``_validate_verdict_count`` and
        ``_validate_commit_each_iteration``. An inner step that fails its own
        validate() may not have the fields expand() requires (e.g. review:
        with no template:) — ``_validate_inner_steps`` already reports shape
        errors for it, so it is skipped here rather than letting expand()
        raise on an incomplete config it was never guaranteed to receive.
        """
        raw_dicts = [cast(dict[str, object], s) for s in steps if isinstance(s, dict)]
        inner_configs = unpack_inner_steps(raw_dicts)

        results: list[tuple[StepConfig, list[str]]] = []
        for inner in inner_configs:
            step_impl = get_step_type(inner.step_type)
            if step_impl.validate(inner):
                continue
            action_types = [action_type for action_type, _action_config in step_impl.expand(inner)]
            results.append((inner, action_types))
        return results

    def _validate_verdict_count(
        self,
        steps: list[object],
        step_type: str,
    ) -> list[ValidationError]:
        """Reject a loop body with more than one verdict-bearing action.

        A verdict-bearing action ("review" or "gate") gates ``until:`` via
        ``_last_with_verdict``, which only looks at the last such action in
        the body. Two or more makes that gating ambiguous, so this is
        rejected at validation time rather than resolved at runtime.
        """
        offending_names: list[str] = []
        verdict_count = 0
        for inner, action_types in self._walk_valid_inner_action_types(steps):
            inner_verdict_count = sum(1 for a in action_types if a in _VERDICT_BEARING_ACTION_TYPES)
            if inner_verdict_count:
                verdict_count += inner_verdict_count
                offending_names.append(inner.name)

        if verdict_count > 1:
            return [
                ValidationError(
                    field="steps",
                    message=(
                        f"loop body has {verdict_count} verdict-bearing actions "
                        f"({', '.join(offending_names)}) with 'until:' set — this "
                        f"makes 'until:' ambiguous, since only the last "
                        f"verdict-bearing action gates the loop. Split into "
                        f"sequential loops, one review/gate per loop body."
                    ),
                    action_type=step_type,
                )
            ]
        return []

    def _validate_commit_each_iteration(
        self,
        steps: list[object],
        step_type: str,
    ) -> list[ValidationError]:
        """Reject ``commit_each_iteration: true`` when the body already
        commits (a phase-shaped inner step commits on every iteration
        unconditionally), which would otherwise commit twice per round.
        """
        offending_names = [
            inner.name
            for inner, action_types in self._walk_valid_inner_action_types(steps)
            if _COMMIT_ACTION_TYPE in action_types
        ]
        if offending_names:
            return [
                ValidationError(
                    field="commit_each_iteration",
                    message=(
                        f"loop body already commits via {', '.join(offending_names)} "
                        f"(phase steps commit each iteration automatically) — "
                        f"remove 'commit_each_iteration' from the loop config"
                    ),
                    action_type=step_type,
                )
            ]
        return []

    def inner_steps(self, config: StepConfig) -> list[StepConfig]:
        raw: object = config.config.get("steps", [])
        if not isinstance(raw, list):
            return []
        raw_list = cast(list[object], raw)
        return unpack_inner_steps([cast(dict[str, object], s) for s in raw_list if isinstance(s, dict)])

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        """Return empty — executor handles iteration via _execute_loop_body."""
        return []


register_step_type(StepTypeName.LOOP, LoopStepType())
