"""Resolve a planning loop's final review notes inside the loop (issue #287).

A review loop that completes with findings left on its last review (a PASS with notes, or
an accepted CONCERNS) runs one resolve dispatch before it collapses. The dispatch applies
the notes and records each finding's disposition in the review file, so the resolution
lands in the loop's single document commit instead of a hand-made second one.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from squadron.pipeline.actions import ActionType
from squadron.pipeline.actions.dispatch import DispatchFeedback
from squadron.pipeline.actions.review_outputs import review_file
from squadron.pipeline.models import ActionResult, StepConfig
from squadron.pipeline.steps import StepTypeName

#: The loop key that turns resolving on; its value is a dispatch step config.
RESOLVE_KEY = "resolve"
#: The name the resolve dispatch runs under.
RESOLVE_STEP_NAME = "resolve"
#: The section the resolve dispatch appends to the review file.
RESOLUTION_HEADING = "## Resolution"

RESOLVE_PROMPT = (
    "The review of this artifact completed, but left the findings below. Resolve them now: "
    "apply each one that improves the artifact, editing the reviewed files in place. Then "
    "append a `{heading}` section to the end of the review file `{review_file}` with one "
    "line per finding saying what you changed, or that you deferred or rejected it and why. "
    "List every finding; drop none. Do not start another review."
)


class ResolveError(ValueError):
    """The loop's final review has notes but cannot be resolved as configured."""


def _latest_review(results: Sequence[ActionResult]) -> ActionResult | None:
    for result in reversed(results):
        if result.action_type == ActionType.REVIEW:
            return result
    return None


def final_review(
    round_results: Sequence[ActionResult],
    prior_outputs: Mapping[str, ActionResult],
    *,
    rounds_run: bool,
) -> ActionResult | None:
    """The review that completed the loop.

    A loop that ran rounds completed on its last round's review. One that ran none
    (``skip_if_met``) completed on the review already in scope before it.
    """
    if rounds_run:
        return _latest_review(round_results)
    return _latest_review(list(prior_outputs.values()))


def has_notes(review: ActionResult) -> bool:
    """Whether ``review`` left findings to resolve."""
    return any(isinstance(finding, dict) for finding in review.findings)


def resolve_step(resolve_config: Mapping[str, object], review: ActionResult) -> StepConfig:
    """The dispatch step that resolves ``review``'s notes.

    Raises:
        ResolveError: the review was not saved, so there is no file to record the
            resolution in.
    """
    path = review_file(review)
    if path is None:
        raise ResolveError(
            "the loop's final review left findings but was not saved to a file, "
            f"so there is nowhere to write its {RESOLUTION_HEADING} section"
        )
    config: dict[str, object] = dict(resolve_config)
    config["prompt"] = RESOLVE_PROMPT.format(heading=RESOLUTION_HEADING, review_file=path)
    config["feedback"] = DispatchFeedback.REVIEW.value
    return StepConfig(step_type=StepTypeName.DISPATCH, name=RESOLVE_STEP_NAME, config=config)
