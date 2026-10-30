"""The rollup report models (slice 403, criterion 9: no model combines sources into a score)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.audit_models import BaselineExclusionSummary, BaselineReport, DeltaReport
from squadron.metrology.quality_report.models import (
    AuditFloorState,
    AuditSection,
    BoundarySettings,
    BreakDetail,
    CategoryCount,
    ComparabilityBreak,
    HistoryReport,
    HistoryRow,
    LandingReport,
    LanguageMetricSummary,
    MetricComparison,
    MetricFigure,
    ProjectReport,
    ReviewSection,
    SliceReport,
)
from squadron.metrology.slice_range_models import RangeUnresolvedReason
from squadron.metrology.snapshot_models import LengthLimits, SnapshotMetric, SourceLanguage
from squadron.review.models import Severity
from tests.metrology.snapshot.builders import make_project_id
from tests.metrology.test_slice_range_models import make_landing

FIGURE = MetricFigure(total=100, n=4, n_unit="files", over_limit=1, limit=300)
BREAK = BreakDetail(
    kind=ComparabilityBreak.TOOL_CHANGED,
    detail="ruff 0.14 -> 0.15",
    fix="re-measure both with sq metrology snapshot --commit <sha>",
)
COMPARISON = MetricComparison(
    language=SourceLanguage.PYTHON,
    metric=SnapshotMetric.FILE_LENGTH,
    before=FIGURE,
    after=FIGURE,
    delta=0,
    source="squadron-python-ast 0.24",
    breaks=[],
)
BROKEN = COMPARISON.model_copy(update={"delta": None, "breaks": [BREAK]})
SUMMARY = LanguageMetricSummary(
    language=SourceLanguage.PYTHON, metric=SnapshotMetric.FILE_LENGTH, figure=FIGURE
)
REVIEWS = ReviewSection(
    n_files=2,
    n_findings=3,
    write_time_findings=2,
    read_side_mapped_findings=1,
    categories=[
        CategoryCount(
            category=ReviewCategory.OTHER,
            count=1,
            severities={Severity.NOTE: 1},
            raw_categories=["style"],
        )
    ],
    uncategorized=0,
    other_share=0.5,
)
SETTINGS = BoundarySettings(
    commit_sha="b" * 40,
    limits=LengthLimits(max_file_lines=300, max_function_lines=50, limits_declared=True),
    exclusions=["vendor/**"],
)
DELTA = DeltaReport(
    project_id=make_project_id(),
    baseline_commit_sha="b" * 40,
    new_commit_sha="a" * 40,
    baseline_total=10,
    new_total=12,
    total_delta=2,
    cells=[],
)


def key_names(value: object) -> list[str]:
    """Every dict key anywhere in a serialized report."""
    if isinstance(value, dict):
        mapping = cast("dict[str, object]", value)
        return [*mapping, *(name for child in mapping.values() for name in key_names(child))]
    if isinstance(value, list):
        return [name for child in cast("list[object]", value) for name in key_names(child)]
    return []


REPORTS = {
    "slice": SliceReport(
        index=403,
        target="main",
        landings=[
            LandingReport(
                landing=make_landing(),
                before=SETTINGS,
                after=SETTINGS,
                comparisons=[COMPARISON, BROKEN],
                audit=AuditSection(
                    delta=DELTA, floor_state=AuditFloorState.NO_FLOOR_MEASURED, floor_n_runs=None
                ),
            )
        ],
        reviews=REVIEWS,
    ),
    "unresolved slice": SliceReport(index=388, reason=RangeUnresolvedReason.REFLOG_UNAVAILABLE),
    "project": ProjectReport(
        project_id=make_project_id(),
        snapshot_commit="a" * 40,
        summaries=[SUMMARY],
        audit=BaselineReport(projects=[], excluded=BaselineExclusionSummary()),
        slice_reviews=REVIEWS,
        project_only_reviews=REVIEWS,
    ),
    "history": HistoryReport(
        project_id=make_project_id(),
        rows=[
            HistoryRow(
                commit_sha="a" * 40,
                measured_at=datetime(2026, 10, 29, tzinfo=UTC),
                summaries=[SUMMARY],
                breaks_from_previous=[BREAK],
            )
        ],
        off_line_snapshots=2,
    ),
}


@pytest.mark.parametrize("name", sorted(REPORTS))
def test_no_serialized_report_has_a_key_containing_score(name: str) -> None:
    serialized = REPORTS[name].model_dump(mode="json")

    assert [key for key in key_names(serialized) if "score" in key.lower()] == []


@pytest.mark.parametrize("name", sorted(REPORTS))
def test_reports_round_trip_through_json(name: str) -> None:
    report = REPORTS[name]

    assert type(report).model_validate_json(report.model_dump_json()) == report


def test_review_section_always_carries_the_no_floor_marker() -> None:
    assert REVIEWS.floor_note == "no floor measured"
