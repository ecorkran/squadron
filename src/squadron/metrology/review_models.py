"""The ``code_review`` record: one ingested code-review file, findings inline (slice 402).

A record is a derived copy of a review file, keyed on project and path (D5). It sits
behind the metrology envelope as an optional sibling payload, so ``schema_version`` does
not move. Severity is the review scale (``review.models.Severity``) and is never mapped
to the audit's scale.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.project_id import ProjectId
from squadron.review.models import Severity, Verdict


class CodeReviewFinding(BaseModel):
    """One finding of an ingested code review."""

    finding_id: str
    severity: Severity
    #: None means the finding had no category (uncategorized), never ``other``.
    category: ReviewCategory | None
    #: The string the model (or an older review) used, when it differs from ``category``.
    raw_category: str | None = None
    location: str | None
    summary: str


class CodeReviewRecord(BaseModel):
    """One code-review file as the metrology store holds it."""

    record_id: str
    project_id: ProjectId
    #: Relative to the repo root when inside it, else absolute.
    review_path: str
    #: None when the file has no ``reviewedSha``; that is the only reason one is absent.
    commit_sha: str | None
    #: None for PR reviews and anything whose ``sourceDocument`` names no slice or tasks file.
    slice_index: int | None
    verdict: Verdict
    #: True when the categories came from the historical alias table, not from the prompt.
    read_side_mapped: bool
    reviewed_at: date
    ingested_at: datetime
    findings: list[CodeReviewFinding]
    #: Findings dropped because their severity isn't on the review scale.
    unnormalized_count: int = 0

    @model_validator(mode="after")
    def _verdict_is_known(self) -> CodeReviewRecord:
        """An unparsed review with no findings would read as a clean one (D6)."""
        if self.verdict is Verdict.UNKNOWN:
            raise ValueError("a code review with an UNKNOWN verdict is not recorded")
        return self
