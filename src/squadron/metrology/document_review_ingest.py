"""Build ``document_review`` records from slice, tasks and arch review files (#374, part 2)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.document_review_models import (
    BlobRef,
    DocumentReviewFinding,
    DocumentReviewRecord,
)
from squadron.metrology.project_id import ProjectId
from squadron.metrology.review_category_map import UNCATEGORIZED
from squadron.metrology.review_ingest_fields import (
    FileProblem,
    FindingFields,
    parse_findings,
    reviewed_at,
    slice_index,
    text_or_none,
)
from squadron.metrology.store import document_review_record_id
from squadron.review.document_stamp import (
    DOCUMENT_BLOB_CURRENT_KEY,
    DOCUMENT_BLOB_KEY,
    PARENT_BLOB_CURRENT_KEY,
    PARENT_BLOB_KEY,
)
from squadron.review.models import Verdict

#: The ``reviewType`` values ingested as document reviews.
DOCUMENT_REVIEW_TYPES = frozenset({"slice", "tasks", "arch"})


def _category(raw: object) -> str | None:
    """The written category; the ``uncategorized`` marker means none, as for code reviews."""
    return None if raw is None or str(raw) == UNCATEGORIZED else str(raw)


def _finding(fields: FindingFields) -> DocumentReviewFinding:
    return DocumentReviewFinding(
        finding_id=fields.finding_id(),
        severity=fields.severity,
        category=_category(fields.fields.get("category")),
        location=fields.location(),
        summary=fields.summary(),
    )


def _blob_ref(frontmatter: dict[str, object], blob_key: str, current_key: str) -> BlobRef | None:
    """The stamp under *blob_key*, or None when the review carries none.

    A blob without a boolean ``current`` is a malformed stamp and fails the file.
    """
    blob = frontmatter.get(blob_key)
    if blob is None:
        return None
    current = frontmatter.get(current_key)
    if not isinstance(current, bool):
        raise FileProblem(f"has {blob_key} but {current_key} is {current!r}, not true or false")
    return BlobRef(blob=str(blob), current=current)


def build_document_record(
    frontmatter: dict[str, object],
    review_type: str,
    verdict: Verdict,
    path: Path,
    review_path: str,
    project_id: ProjectId,
) -> DocumentReviewRecord:
    findings, unnormalized = parse_findings(frontmatter, path, _finding)
    source = text_or_none(frontmatter.get("sourceDocument"))
    return DocumentReviewRecord(
        record_id=document_review_record_id(project_id, review_path),
        project_id=project_id,
        review_path=review_path,
        review_type=review_type,
        source_document=source,
        slice_index=slice_index(source),
        reviewed_blob=_blob_ref(frontmatter, DOCUMENT_BLOB_KEY, DOCUMENT_BLOB_CURRENT_KEY),
        parent_blob=_blob_ref(frontmatter, PARENT_BLOB_KEY, PARENT_BLOB_CURRENT_KEY),
        verdict=verdict,
        reviewed_at=reviewed_at(frontmatter.get("dateCreated")),
        ingested_at=datetime.now(UTC),
        findings=findings,
        unnormalized_count=unnormalized,
    )
