"""Validation: an ``implement`` step needs a ``branch: {op: enter}`` before it (slice 196 D4).

Without the enter, an implement would run on whatever branch is checked out, and its
commit would then refuse to stage (D3), but only after the dispatch had already run.
Failing at load time is cheaper.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from squadron.pipeline.models import StepConfig, ValidationError
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.branch import BranchOp
from squadron.pipeline.steps.utils import unpack_inner_steps

# Step types whose ``steps:`` body is a nested list this rule descends into.
_CONTAINER_STEP_TYPES = frozenset({StepTypeName.LOOP, StepTypeName.EACH})


def implement_branch_errors(steps: Sequence[StepConfig]) -> list[ValidationError]:
    """One error per ``implement`` step with no preceding ``branch: {op: enter}``."""
    errors: list[ValidationError] = []
    _walk(steps, entered=False, errors=errors)
    return errors


def _walk(steps: Sequence[StepConfig], *, entered: bool, errors: list[ValidationError]) -> None:
    """Walk one step list in order.

    ``entered`` is whether an enter already precedes this list's position: an enter earlier
    in this list, or earlier in an enclosing list than the container holding it. An enter
    inside a sibling container does not count, so a container's result is never carried
    back out.
    """
    for step in steps:
        if step.step_type == StepTypeName.BRANCH and step.config.get("op") == BranchOp.ENTER:
            entered = True
        elif step.step_type == StepTypeName.IMPLEMENT and not entered:
            errors.append(
                ValidationError(
                    field="steps",
                    message=(
                        f"implement step {step.name} needs a preceding branch: {{op: enter}}. "
                        "Add '- branch: {op: enter}' before it, and '- branch: {op: merge}' "
                        "after its review."
                    ),
                    action_type=step.step_type,
                )
            )
        elif step.step_type in _CONTAINER_STEP_TYPES:
            _walk(_inner_steps(step), entered=entered, errors=errors)


def _inner_steps(step: StepConfig) -> list[StepConfig]:
    raw = step.config.get("steps")
    if not isinstance(raw, list):
        return []
    return unpack_inner_steps(
        [cast(dict[str, object], s) for s in cast(list[object], raw) if isinstance(s, dict)]
    )
