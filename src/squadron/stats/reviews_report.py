"""The ``sq stats reviews`` report: one row per standalone review artifact (D8).

Reads only frontmatter: one parse per artifact, never the body. An artifact stamped with
``runId`` came from a pipeline run and is counted there (``sq stats run``), so it is
excluded here and each review's spend appears in exactly one view.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from squadron.core.usage import UsageRecord
from squadron.documents.frontmatter import read_frontmatter
from squadron.review.frontmatter_usage import frontmatter_text, record_from_frontmatter
from squadron.stats.usage_report import UsageTotals, usage_totals

_logger = logging.getLogger(__name__)

#: A review artifact's file name starts with its slice index (``175-review.slice...``).
_INDEX_PREFIX = re.compile(r"^(\d+)-")


@dataclass(frozen=True)
class ReviewUsageRow:
    path: Path
    date: str | None
    slice: str | None
    review_type: str | None
    model: str | None
    verdict: str | None
    record: UsageRecord


@dataclass(frozen=True)
class ReviewsUsageReport:
    reviews_dir: Path
    rows: list[ReviewUsageRow] = field(default_factory=list[ReviewUsageRow])
    totals: UsageTotals = field(default_factory=lambda: usage_totals([]))
    excluded_run_ids: list[str] = field(default_factory=list[str])  # pipeline reviews
    skipped: int = 0  # unreadable frontmatter
    missing_dir: bool = False


def reviews_usage_report(reviews_dir: Path, slice_filter: str | None) -> ReviewsUsageReport:
    """Report the standalone review artifacts in ``reviews_dir``, optionally for one slice.

    ``slice_filter`` matches the frontmatter ``slice`` value or the file name's leading
    slice index, since artifacts name the slice in frontmatter and index it in the name.
    """
    if not reviews_dir.is_dir():
        return ReviewsUsageReport(reviews_dir=reviews_dir, missing_dir=True)
    rows: list[ReviewUsageRow] = []
    excluded: list[str] = []
    skipped = 0
    for path in sorted(reviews_dir.glob("*.md")):
        front = read_frontmatter(path)
        if front is None:
            _logger.warning("skipping review artifact with no readable frontmatter: %s", path)
            skipped += 1
            continue
        if slice_filter is not None and not _slice_matches(
            path, frontmatter_text(front, "slice"), slice_filter
        ):
            continue
        run_id = front.get("runId")
        if run_id is not None:
            excluded.append(str(run_id))
            continue
        rows.append(_row(path, front))
    return ReviewsUsageReport(
        reviews_dir=reviews_dir,
        rows=rows,
        totals=usage_totals(row.record for row in rows),
        excluded_run_ids=excluded,
        skipped=skipped,
    )


def _slice_matches(path: Path, slice_value: str | None, slice_filter: str) -> bool:
    if slice_value == slice_filter:
        return True
    match = _INDEX_PREFIX.match(path.name)
    return match is not None and match.group(1) == slice_filter


def row_matches_slice(row: ReviewUsageRow, slice_filter: str) -> bool:
    """The ``--slice`` rule applied to an already-read row, so a caller reads the dir once."""
    return _slice_matches(row.path, row.slice, slice_filter)


def _row(path: Path, front: Mapping[str, object]) -> ReviewUsageRow:
    return ReviewUsageRow(
        path=path,
        date=frontmatter_text(front, "dateCreated"),
        slice=frontmatter_text(front, "slice"),
        review_type=frontmatter_text(front, "reviewType"),
        model=frontmatter_text(front, "aiModel"),
        verdict=frontmatter_text(front, "verdict"),
        record=record_from_frontmatter(path, front),
    )
