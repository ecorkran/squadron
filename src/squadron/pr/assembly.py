"""Deterministic assembly: the exact parts, built without a model.

Every fact is copied from an input. Nothing is derived, inferred, or
defaulted — initiative 360's traceability rule as code: assert nothing an
input does not support.
"""

from __future__ import annotations

from dataclasses import dataclass

from squadron.pr.inputs import PrInputs, ReviewProvenance
from squadron.review.git_utils import CommitRecord
from squadron.review.models import Verdict


@dataclass(frozen=True)
class PrFacts:
    """The exact parts of a PR body, each present or explicitly absent."""

    commits: tuple[CommitRecord, ...]
    slice_design_file: str | None
    checked_items: tuple[str, ...]
    unchecked_items: tuple[str, ...]
    review_path: str | None
    review_verdict: Verdict | None
    reviewed_sha: str | None


def assemble_facts(inputs: PrInputs, review: ReviewProvenance | None) -> PrFacts:
    """Copy every input's exact parts into a ``PrFacts``.

    ``review`` comes from ``find_latest_in_range_review``, gathered
    separately from ``PrInputs`` — assembly's job is to copy, not to gather.
    """
    slice_inputs = inputs.slice
    task_items = slice_inputs.task_items

    return PrFacts(
        commits=inputs.commits,
        slice_design_file=slice_inputs.design_file,
        checked_items=task_items.checked if task_items is not None else (),
        unchecked_items=task_items.unchecked if task_items is not None else (),
        review_path=str(review.path) if review is not None else None,
        review_verdict=review.verdict if review is not None else None,
        reviewed_sha=review.reviewed_sha if review is not None else None,
    )
