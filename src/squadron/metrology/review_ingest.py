"""Ingest review files into the metrology store (slice 402, D5, D6, D7; #374 part 2).

One ``code_review`` record per code-review file and one ``document_review`` record per
slice, tasks or arch review file, findings inline. The review files stay the source; a
record is a derived copy keyed on project and path, so ingest always writes and
re-running replaces in place. Everything that can't be counted honestly is skipped with a
reason or listed as failed, never defaulted.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squadron.core.finding_categories import ReviewCategory
from squadron.documents.frontmatter import parse_frontmatter
from squadron.metrology.document_review_ingest import DOCUMENT_REVIEW_TYPES, build_document_record
from squadron.metrology.document_review_models import DocumentReviewRecord
from squadron.metrology.errors import ReviewIngestInputError
from squadron.metrology.project_id import ProjectId
from squadron.metrology.review_category_map import UNCATEGORIZED, map_historical_category
from squadron.metrology.review_ingest_fields import (
    FileProblem,
    FindingFields,
    parse_findings,
    reviewed_at,
    slice_index,
    text_or_none,
)
from squadron.metrology.review_models import CodeReviewFinding, CodeReviewRecord
from squadron.metrology.store import MetrologyStore, code_review_record_id
from squadron.review.models import Verdict
from squadron.review.reviews_dir import resolve_reviews_dir

_logger = logging.getLogger(__name__)

CODE_REVIEW_TYPE = "code"
_REVIEW_FILE_GLOB = "*.md"


@dataclass
class IngestResult:
    """What an ingest run did. The caller passes it in so the counts survive an abort."""

    #: Records written, code and document reviews together.
    ingested: int = 0
    #: How many of ``ingested`` were document (slice, tasks, arch) reviews.
    documents: int = 0
    replaced: int = 0
    #: Files whose ``reviewType`` is neither code nor a document review type.
    skipped_other_type: int = 0
    skipped_unknown_verdict: int = 0
    #: Findings dropped for a severity outside the review scale, across all ingested files.
    dropped_findings: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list[tuple[Path, str]])


def default_reviews_dir(project_id: ProjectId, cwd: Path) -> Path:
    """The reviews directory for *cwd*, by the same rules ``sq review`` writes with."""
    parts = project_id.value.split("/")
    if len(parts) < 3:  # noqa: PLR2004 - host/owner/repository is the identity shape
        raise ReviewIngestInputError(
            f"Can't resolve the default reviews directory: project id {project_id.value!r} "
            "isn't host/owner/repository. Pass the review files or directory as PATHS."
        )
    directory, _rule = resolve_reviews_dir(
        flag=None,
        cwd=str(cwd),
        host=parts[0],
        owner="/".join(parts[1:-1]),
        repository=parts[-1],
    )
    if not directory.is_dir():
        raise ReviewIngestInputError(
            f"The reviews directory {directory} doesn't exist. "
            "Pass the review files or directory as PATHS."
        )
    return directory


def resolve_review_files(
    paths: Sequence[Path], project_id: ProjectId, cwd: Path
) -> tuple[list[Path], list[Path]]:
    """The review files to ingest and the directories searched for them.

    Each path is a file or a directory (its ``*.md``). A nonexistent path raises before
    anything is written. With no paths, the default reviews directory is searched.
    """
    roots = list(paths) if paths else [default_reviews_dir(project_id, cwd)]
    files: list[Path] = []
    directories: list[Path] = []
    for root in roots:
        if root.is_dir():
            directories.append(root)
            files.extend(sorted(root.glob(_REVIEW_FILE_GLOB)))
        elif root.is_file():
            files.append(root)
        else:
            raise ReviewIngestInputError(f"{root} doesn't exist. Check the PATHS argument.")
    # Overlapping PATHS name the same file more than once; count each file once.
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path.resolve() not in seen:
            seen.add(path.resolve())
            unique.append(path)
    return unique, directories


def _read_frontmatter(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise FileProblem(f"can't be read: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise FileProblem(f"isn't valid UTF-8: {exc}") from exc
    frontmatter = parse_frontmatter(text)
    if frontmatter is None:
        raise FileProblem("has no readable frontmatter")
    return frontmatter


def _review_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _stored_category(raw: object, raw_category: object) -> tuple[ReviewCategory | None, str | None]:
    """A write-time file's stored category, which must already be a ``ReviewCategory``."""
    if raw is None or str(raw) == UNCATEGORIZED:
        return None, None
    try:
        return ReviewCategory(str(raw)), text_or_none(raw_category)
    except ValueError as exc:
        raise FileProblem(f"stores category {raw!r}, which isn't a ReviewCategory value") from exc


def _code_finding(fields: FindingFields, *, read_side: bool) -> CodeReviewFinding:
    raw = fields.fields.get("category")
    if read_side:
        mapped = map_historical_category(None if raw is None else str(raw))
        category, raw_category = mapped.category, mapped.raw_category
    else:
        category, raw_category = _stored_category(raw, fields.fields.get("rawCategory"))
    return CodeReviewFinding(
        finding_id=fields.finding_id(),
        severity=fields.severity,
        category=category,
        raw_category=raw_category,
        location=fields.location(),
        summary=fields.summary(),
    )


def _build_code_record(
    frontmatter: dict[str, object],
    verdict: Verdict,
    path: Path,
    review_path: str,
    project_id: ProjectId,
) -> CodeReviewRecord:
    read_side = frontmatter.get("categoriesNormalized") is not True
    findings, unnormalized = parse_findings(
        frontmatter, path, lambda fields: _code_finding(fields, read_side=read_side)
    )
    return CodeReviewRecord(
        record_id=code_review_record_id(project_id, review_path),
        project_id=project_id,
        review_path=review_path,
        commit_sha=text_or_none(frontmatter.get("reviewedSha")),
        slice_index=slice_index(frontmatter.get("sourceDocument")),
        verdict=verdict,
        read_side_mapped=read_side,
        reviewed_at=reviewed_at(frontmatter.get("dateCreated")),
        ingested_at=datetime.now(UTC),
        findings=findings,
        unnormalized_count=unnormalized,
    )


def _review_type(frontmatter: dict[str, object]) -> str:
    review_type = frontmatter.get("reviewType")
    if review_type is None:
        raise FileProblem("is missing reviewType")
    return str(review_type)


def _verdict(frontmatter: dict[str, object]) -> Verdict:
    """The review's verdict; a missing or unrecognized one is a failure."""
    raw = frontmatter.get("verdict")
    if raw is None:
        raise FileProblem("is missing verdict")
    try:
        return Verdict(str(raw))
    except ValueError as exc:
        raise FileProblem(f"has an unrecognized verdict {raw!r}") from exc


def _write(store: MetrologyStore, record: CodeReviewRecord | DocumentReviewRecord) -> None:
    if isinstance(record, DocumentReviewRecord):
        store.write_document_review(record)
    else:
        store.write_code_review(record)


def ingest_reviews(
    project_id: ProjectId,
    repo_root: Path,
    files: Sequence[Path],
    store: MetrologyStore,
    result: IngestResult,
) -> None:
    """Ingest *files*, updating *result* as each is processed.

    A file that can't be ingested is listed under ``result.failed`` with a WARNING and the
    run continues. ``MetrologyStoreError`` from a write propagates; *result* then shows
    what was written before it.
    """
    known_ids = {review.record_id for review in store.list_code_reviews(project_id)}
    known_ids |= {review.record_id for review in store.list_document_reviews(project_id)}
    for path in files:
        try:
            frontmatter = _read_frontmatter(path)
            review_type = _review_type(frontmatter)
            if review_type != CODE_REVIEW_TYPE and review_type not in DOCUMENT_REVIEW_TYPES:
                result.skipped_other_type += 1
                continue
            verdict = _verdict(frontmatter)
            if verdict is Verdict.UNKNOWN:
                result.skipped_unknown_verdict += 1
                continue
            review_path = _review_path(path, repo_root)
            record = (
                _build_code_record(frontmatter, verdict, path, review_path, project_id)
                if review_type == CODE_REVIEW_TYPE
                else build_document_record(
                    frontmatter, review_type, verdict, path, review_path, project_id
                )
            )
        except FileProblem as exc:
            _logger.warning("Can't ingest %s: it %s", path, exc)
            result.failed.append((path, str(exc)))
            continue
        _write(store, record)
        result.ingested += 1
        result.documents += isinstance(record, DocumentReviewRecord)
        result.dropped_findings += record.unnormalized_count
        if record.record_id in known_ids:
            result.replaced += 1
        known_ids.add(record.record_id)
