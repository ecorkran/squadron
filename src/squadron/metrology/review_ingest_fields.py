"""Frontmatter field parsing shared by code and document review ingest.

Everything that can't be read honestly raises ``FileProblem`` (the file is listed as
failed) or, for a finding whose severity is off the review scale, is dropped with a
WARNING and counted. Nothing is defaulted.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath
from typing import NamedTuple, cast

from squadron.review.models import Severity

_logger = logging.getLogger(__name__)

#: The project's document-naming convention for a review's source: ``{n}-slice.`` or
#: ``{n}-tasks.`` at the start of the ``sourceDocument`` basename (402 D6).
SLICE_SOURCE_PATTERN = re.compile(r"^(\d+)-(?:slice|tasks)\.")

_SEVERITIES = {severity.value.lower(): severity for severity in Severity}
_DATE_FORMAT = "%Y%m%d"


class FileProblem(Exception):
    """A file can't be ingested; the message is the reason listed under ``failed``."""


class FindingFields(NamedTuple):
    """A finding's frontmatter keys, with its severity already on the review scale."""

    fields: dict[str, object]
    severity: Severity

    def finding_id(self) -> str:
        return str(self.fields["id"])

    def summary(self) -> str:
        return str(self.fields["summary"])

    def location(self) -> str | None:
        return text_or_none(self.fields.get("location"))


def slice_index(source_document: object) -> int | None:
    if not isinstance(source_document, str) or not source_document.strip():
        return None
    match = SLICE_SOURCE_PATTERN.match(PurePosixPath(source_document.strip()).name)
    return int(match.group(1)) if match else None


def reviewed_at(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return datetime.strptime(str(value), _DATE_FORMAT).replace(tzinfo=UTC).date()
    except ValueError as exc:
        raise FileProblem(f"has an unreadable dateCreated {value!r}") from exc


def text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


def _finding_fields(entry: object, path: Path) -> FindingFields | None:
    """The finding's keys, or None (with a WARNING) when its severity isn't on the scale."""
    if not isinstance(entry, dict):
        raise FileProblem("has a finding that isn't a mapping")
    fields = {str(key): value for key, value in cast("dict[object, object]", entry).items()}
    severity = _SEVERITIES.get(str(fields.get("severity", "")).strip().lower())
    if severity is None:
        _logger.warning(
            "%s: finding %s has severity %r, which isn't a review severity; dropped",
            path,
            fields.get("id"),
            fields.get("severity"),
        )
        return None
    if fields.get("id") is None or fields.get("summary") is None:
        raise FileProblem("has a finding with no id or summary")
    return FindingFields(fields=fields, severity=severity)


def parse_findings[T](
    frontmatter: dict[str, object], path: Path, build: Callable[[FindingFields], T]
) -> tuple[list[T], int]:
    """The file's findings built by *build*, and the count dropped for an off-scale severity."""
    entries = frontmatter.get("findings")
    if entries is None:
        return [], 0
    if not isinstance(entries, list):
        raise FileProblem("has a findings entry that isn't a list")
    kept: list[T] = []
    dropped = 0
    for entry in cast("list[object]", entries):
        fields = _finding_fields(entry, path)
        if fields is None:
            dropped += 1
        else:
            kept.append(build(fields))
    return kept, dropped
