"""The commit a loop round makes (slice 196 D1).

A round's subject comes from its last review action: the review's template names
what the round revised. The executor and the prompt renderer both build the
commit's params here, so a round commits the same thing in either mode.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.pipeline.actions import ActionType
from squadron.pipeline.commit_plan import (
    PLAN_PARAM,
    REVIEW_TEMPLATE_PARAM,
    SLICE_PARAM,
    SUBJECT_PARAM,
    CommitSubject,
    subject_for_template,
)
from squadron.pipeline.models import StepConfig
from squadron.pipeline.steps import bootstrap_step_types, get_step_type


class CommitScopeUnknownError(ValueError):
    """A loop round has no review, or its review names no slice or plan to commit."""


def round_commit_params(
    inner_steps: Sequence[StepConfig], params: dict[str, object], round_number: int
) -> dict[str, object]:
    """The commit action params for loop round ``round_number``.

    ``params`` are the loop's merged params, used to resolve placeholders in the
    review action's config and as the fallback source of the slice or plan.

    Raises:
        CommitScopeUnknownError: no review in the round, or it names no target.
        UnmappedTemplateError: the review's template has no commit subject.
    """
    from squadron.pipeline.executor import resolve_placeholders

    review_config = _last_review_config(inner_steps)
    if review_config is None:
        raise CommitScopeUnknownError(f"commit scope unknown: no review in round {round_number}")

    resolved = resolve_placeholders(review_config, params)
    template = str(resolved["template"])
    subject = subject_for_template(template)
    # An architecture round is initiative-scoped; every other subject is per slice.
    key = PLAN_PARAM if subject is CommitSubject.ARCHITECTURE else SLICE_PARAM
    target = resolved.get(key) or params.get(key)
    if not isinstance(target, str | int) or target == "":
        raise CommitScopeUnknownError(
            f"commit scope unknown: the review in round {round_number} names no {key}"
        )
    return {SUBJECT_PARAM: subject, REVIEW_TEMPLATE_PARAM: template, key: target}


def _last_review_config(inner_steps: Sequence[StepConfig]) -> dict[str, object] | None:
    """The config of the last review action the round's steps expand to."""
    bootstrap_step_types()  # idempotent; the renderer can reach here before the executor ran
    last: dict[str, object] | None = None
    for inner in inner_steps:
        for action_type, action_config in get_step_type(inner.step_type).expand(inner):
            if action_type == ActionType.REVIEW:
                last = action_config
    return last
