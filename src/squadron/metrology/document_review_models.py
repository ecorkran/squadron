"""The ``document_review`` record: one ingested slice, tasks or arch review (#374, part 2).

A sibling of ``CodeReviewRecord``, not a variant of it: document review templates set
their own finding categories, so ``category`` is the string the review wrote rather than
a ``ReviewCategory``. Severity and verdict are the review scale. What was reviewed is
named by the blob stamps of part 1, not by a commit.
"""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, model_validator

from squadron.metrology.project_id import ProjectId
from squadron.review.models import Severity, Verdict


class DocumentReviewFinding(BaseModel):
    """One finding of an ingested document review."""

    finding_id: str
    severity: Severity
    #: The category as the review wrote it; None when the finding had none.
    category: str | None
    location: str | None
    summary: str


class BlobRef(BaseModel):
    """A document's blob at review time, and whether it equalled the blob at HEAD."""

    blob: str
    current: bool


class DocumentReviewRecord(BaseModel):
    """One slice, tasks or arch review file as the metrology store holds it."""

    record_id: str
    project_id: ProjectId
    #: Relative to the repo root when inside it, else absolute.
    review_path: str
    #: The frontmatter ``reviewType``: slice, tasks or arch.
    review_type: str
    source_document: str | None
    #: None when ``sourceDocument`` names no slice or tasks file (arch reviews included).
    slice_index: int | None
    #: None when the review predates blob stamps (#374 part 1) or the stamp was unresolved.
    reviewed_blob: BlobRef | None
    parent_blob: BlobRef | None
    verdict: Verdict
    reviewed_at: date
    ingested_at: datetime
    findings: list[DocumentReviewFinding]
    #: Findings dropped because their severity isn't on the review scale.
    unnormalized_count: int = 0

    @model_validator(mode="after")
    def _verdict_is_known(self) -> DocumentReviewRecord:
        """An unparsed review with no findings would read as a clean one."""
        if self.verdict is Verdict.UNKNOWN:
            raise ValueError("a document review with an UNKNOWN verdict is not recorded")
        return self
