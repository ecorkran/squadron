"""Ingest code-review files into the metrology store (slice 402, D5, D6, D7).

One ``code_review`` record per code-review file, findings inline. The review files stay
the source; a record is a derived copy keyed on project and path, so ingest always writes
and re-running replaces in place. Everything that can't be counted honestly is skipped
with a reason or listed as failed, never defaulted.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import cast

from squadron.core.finding_categories import ReviewCategory
from squadron.documents.frontmatter import parse_frontmatter
from squadron.metrology.errors import ReviewIngestInputError
from squadron.metrology.project_id import ProjectId
from squadron.metrology.review_category_map import UNCATEGORIZED, map_historical_category
from squadron.metrology.review_models import CodeReviewFinding, CodeReviewRecord
from squadron.metrology.store import MetrologyStore, code_review_record_id
from squadron.review.models import Severity, Verdict
from squadron.review.reviews_dir import resolve_reviews_dir

_logger = logging.getLogger(__name__)

#: The project's document-naming convention for a review's source: ``{n}-slice.`` or
#: ``{n}-tasks.`` at the start of the ``sourceDocument`` basename (D6).
SLICE_SOURCE_PATTERN = re.compile(r"^(\d+)-(?:slice|tasks)\.")

CODE_REVIEW_TYPE = "code"
_REVIEW_FILE_GLOB = "*.md"
_SEVERITIES = {severity.value.lower(): severity for severity in Severity}
_DATE_FORMAT = "%Y%m%d"


@dataclass
class IngestResult:
    """What an ingest run did. The caller passes it in so the counts survive an abort."""

    ingested: int = 0
    replaced: int = 0
    skipped_not_code: int = 0
    skipped_unknown_verdict: int = 0
    failed: list[tuple[Path, str]] = field(default_factory=list[tuple[Path, str]])


class _FileProblem(Exception):
    """A file can't be ingested; the message is the reason listed under ``failed``."""


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
    return files, directories


def _read_frontmatter(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise _FileProblem(f"can't be read: {exc}") from exc
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _FileProblem(f"isn't valid UTF-8: {exc}") from exc
    frontmatter = parse_frontmatter(text)
    if frontmatter is None:
        raise _FileProblem("has no readable frontmatter")
    return frontmatter


def _slice_index(source_document: object) -> int | None:
    if not isinstance(source_document, str) or not source_document.strip():
        return None
    match = SLICE_SOURCE_PATTERN.match(PurePosixPath(source_document.strip()).name)
    return int(match.group(1)) if match else None


def _reviewed_at(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), _DATE_FORMAT).replace(tzinfo=UTC).date()
    except ValueError as exc:
        raise _FileProblem(f"has an unreadable dateCreated {value!r}") from exc


def _review_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _stored_category(raw: object, raw_category: object) -> tuple[ReviewCategory | None, str | None]:
    """A write-time file's stored category, which must already be a ``ReviewCategory``."""
    if raw is None or str(raw) == UNCATEGORIZED:
        return None, None
    try:
        return ReviewCategory(str(raw)), _text_or_none(raw_category)
    except ValueError as exc:
        raise _FileProblem(f"stores category {raw!r}, which isn't a ReviewCategory value") from exc


def _finding(entry: object, *, read_side: bool) -> CodeReviewFinding | None:
    """One finding, or None when its severity isn't on the review scale."""
    if not isinstance(entry, dict):
        raise _FileProblem("has a finding that isn't a mapping")
    fields = {str(key): value for key, value in cast("dict[object, object]", entry).items()}
    severity = _SEVERITIES.get(str(fields.get("severity", "")).strip().lower())
    if severity is None:
        return None
    if fields.get("id") is None or fields.get("summary") is None:
        raise _FileProblem("has a finding with no id or summary")
    raw = fields.get("category")
    if read_side:
        mapped = map_historical_category(None if raw is None else str(raw))
        category, raw_category = mapped.category, mapped.raw_category
    else:
        category, raw_category = _stored_category(raw, fields.get("rawCategory"))
    return CodeReviewFinding(
        finding_id=str(fields["id"]),
        severity=severity,
        category=category,
        raw_category=raw_category,
        location=_text_or_none(fields.get("location")),
        summary=str(fields["summary"]),
    )


def _findings(
    frontmatter: dict[str, object], *, read_side: bool
) -> tuple[list[CodeReviewFinding], int]:
    entries = frontmatter.get("findings")
    if entries is None:
        return [], 0
    if not isinstance(entries, list):
        raise _FileProblem("has a findings entry that isn't a list")
    kept: list[CodeReviewFinding] = []
    dropped = 0
    for entry in cast("list[object]", entries):
        finding = _finding(entry, read_side=read_side)
        if finding is None:
            dropped += 1
        else:
            kept.append(finding)
    return kept, dropped


def _build_record(
    frontmatter: dict[str, object], verdict: Verdict, review_path: str, project_id: ProjectId
) -> CodeReviewRecord:
    read_side = frontmatter.get("categoriesNormalized") is not True
    findings, unnormalized = _findings(frontmatter, read_side=read_side)
    return CodeReviewRecord(
        record_id=code_review_record_id(project_id, review_path),
        project_id=project_id,
        review_path=review_path,
        commit_sha=_text_or_none(frontmatter.get("reviewedSha")),
        slice_index=_slice_index(frontmatter.get("sourceDocument")),
        verdict=verdict,
        read_side_mapped=read_side,
        reviewed_at=_reviewed_at(frontmatter.get("dateCreated")),
        ingested_at=datetime.now(UTC),
        findings=findings,
        unnormalized_count=unnormalized,
    )


def _verdict(frontmatter: dict[str, object]) -> Verdict:
    """The review's verdict; a missing or unrecognized ``reviewType``/``verdict`` is a failure."""
    if frontmatter.get("reviewType") is None or frontmatter.get("verdict") is None:
        raise _FileProblem("is missing reviewType or verdict")
    try:
        return Verdict(str(frontmatter["verdict"]))
    except ValueError as exc:
        raise _FileProblem(f"has an unrecognized verdict {frontmatter['verdict']!r}") from exc


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
    for path in files:
        try:
            frontmatter = _read_frontmatter(path)
            verdict = _verdict(frontmatter)
            if str(frontmatter["reviewType"]) != CODE_REVIEW_TYPE:
                result.skipped_not_code += 1
                continue
            if verdict is Verdict.UNKNOWN:
                result.skipped_unknown_verdict += 1
                continue
            record = _build_record(frontmatter, verdict, _review_path(path, repo_root), project_id)
        except _FileProblem as exc:
            _logger.warning("Can't ingest %s: it %s", path, exc)
            result.failed.append((path, str(exc)))
            continue
        store.write_code_review(record)
        result.ingested += 1
        if record.record_id in known_ids:
            result.replaced += 1
        known_ids.add(record.record_id)
