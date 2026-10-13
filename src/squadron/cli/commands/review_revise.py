"""``sq review <kind> --max N``: one review, then revise-and-review rounds (slice 941).

``RoundPrinter`` is the ``RunObserver`` that prints progress as the composed
pipeline runs; ``run_review_revise`` drives that pipeline.
"""

from __future__ import annotations

from collections.abc import Callable

import typer

from squadron.pipeline.actions.review_outputs import ReviewOutputKey
from squadron.pipeline.executor import StepResult
from squadron.pipeline.models import ActionResult
from squadron.pipeline.review_revise import REVIEW_STEP_NAME
from squadron.pipeline.state import ActiveItem

_SHORT_SHA_LENGTH = 7
_LABEL_WIDTH = 10
_VERDICT_WIDTH = 14


def _single(results: list[ActionResult], action_type: str) -> ActionResult | None:
    return next((r for r in results if r.action_type == action_type), None)


class RoundPrinter:
    """Prints the review line, one line per round, and nothing else (D7).

    Raises ``ValueError`` when a round has no review result or no commit result:
    both are guaranteed by the loop shape the builder checks, so their absence is
    a bug to surface, not a line to print around.
    """

    def __init__(self, write: Callable[[str], None] = typer.echo) -> None:
        self._write = write

    def header(self, kind: str, slice_index: str, reviewer: str, reviser: str, max_rounds: int) -> None:
        self._write(
            f"review-revise {kind} {slice_index}  reviewer={reviewer}  "
            f"reviser={reviser}  max={max_rounds}"
        )

    def step_started(self, step_name: str) -> None:
        """Nothing to print: lines appear when work finishes."""

    def item_started(self, step_name: str, item: ActiveItem) -> None:
        """No ``each`` step exists in the composed pipeline."""

    def step_completed(self, result: StepResult) -> None:
        """Print the leading review's line; the loop's rounds print via ``round_completed``."""
        if result.step_name != REVIEW_STEP_NAME:
            return
        review = _single(result.action_results, "review")
        if review is None:
            raise ValueError("review-revise: the leading review step produced no review result")
        file_name = review.outputs.get(ReviewOutputKey.REVIEW_FILE, "")
        self._write(f"  {'review':<{_LABEL_WIDTH}}{self._verdict_cell(review)}{file_name}".rstrip())

    def round_completed(self, step_name: str, iteration: int, results: list[ActionResult]) -> None:
        review = _single(results, "review")
        if review is None:
            raise ValueError(f"review-revise: round {iteration} of '{step_name}' has no review result")
        commit = _single(results, "commit")
        if commit is None:
            raise ValueError(f"review-revise: round {iteration} of '{step_name}' has no commit result")
        label = f"round {iteration}"
        self._write(
            f"  {label:<{_LABEL_WIDTH}}{self._verdict_cell(review)}{self._commit_text(commit)}".rstrip()
        )

    @staticmethod
    def _verdict_cell(review: ActionResult) -> str:
        if review.verdict is None:
            raise ValueError("review-revise: a review result carries no verdict")
        text = f"{review.verdict} ({len(review.findings)})" if review.findings else review.verdict
        return f"{text:<{_VERDICT_WIDTH}}"

    @staticmethod
    def _commit_text(commit: ActionResult) -> str:
        if not commit.success:
            return "commit failed"
        if commit.outputs.get("committed") is False:
            return "no changes"
        return f"committed {str(commit.outputs['sha'])[:_SHORT_SHA_LENGTH]}"
