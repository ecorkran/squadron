"""The history rollup report (slice 403)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.quality_report.history_report import build_history_report
from squadron.metrology.quality_report.models import ComparabilityBreak
from squadron.metrology.store import MetrologyStore
from tests.metrology.snapshot.builders import make_measured_snapshot, make_project_id

PROJECT = make_project_id()
FIRST, SECOND, THIRD, OFF_LINE = "1" * 40, "2" * 40, "3" * 40, "9" * 40


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "history-store")


def write(
    store: MetrologyStore,
    sha: str,
    day: int,
    *,
    lint_version: str = "0.15.1",
    types_resolved: bool = True,
) -> None:
    store.write_snapshot(
        make_measured_snapshot(
            commit_sha=sha,
            measured_at=datetime(2026, 10, day, tzinfo=UTC),
            lint_version=lint_version,
            types_resolved=types_resolved,
        )
    )


def test_order_follows_the_passed_list_not_measured_at(store: MetrologyStore) -> None:
    write(store, FIRST, day=20)  # measured last
    write(store, SECOND, day=10)  # measured first
    write(store, THIRD, day=15)

    report = build_history_report(store, PROJECT, [FIRST, SECOND, THIRD])

    assert [row.commit_sha for row in report.rows] == [FIRST, SECOND, THIRD]


def test_a_tool_change_between_rows_inserts_a_break_on_the_later_row(store: MetrologyStore) -> None:
    write(store, FIRST, day=1)
    write(store, SECOND, day=2, lint_version="0.16.0")
    write(store, THIRD, day=3, lint_version="0.16.0")

    report = build_history_report(store, PROJECT, [FIRST, SECOND, THIRD])

    first, second, third = report.rows
    assert first.breaks_from_previous == []
    assert [b.kind for b in second.breaks_from_previous] == [ComparabilityBreak.TOOL_CHANGED]
    assert "python lint_count" in second.breaks_from_previous[0].detail
    assert third.breaks_from_previous == []


def test_snapshots_off_the_line_are_counted_not_listed(store: MetrologyStore) -> None:
    write(store, FIRST, day=1)
    write(store, OFF_LINE, day=2)

    report = build_history_report(store, PROJECT, [FIRST, SECOND])

    assert [row.commit_sha for row in report.rows] == [FIRST]
    assert report.off_line_snapshots == 1


def test_commits_on_the_line_without_a_snapshot_have_no_row(store: MetrologyStore) -> None:
    write(store, SECOND, day=2)

    report = build_history_report(store, PROJECT, [FIRST, SECOND, THIRD])

    assert [row.commit_sha for row in report.rows] == [SECOND]
    assert report.off_line_snapshots == 0


def test_each_row_carries_its_summaries(store: MetrologyStore) -> None:
    write(store, FIRST, day=1)

    [row] = build_history_report(store, PROJECT, [FIRST]).rows

    assert row.summaries
    assert row.measured_at == datetime(2026, 10, 1, tzinfo=UTC)


def test_metrics_never_measured_at_either_commit_are_not_a_break(store: MetrologyStore) -> None:
    write(store, FIRST, day=1)
    write(store, SECOND, day=2)

    report = build_history_report(store, PROJECT, [FIRST, SECOND])

    assert report.rows[1].breaks_from_previous == []


def test_a_metric_that_stops_being_measured_is_a_break(store: MetrologyStore) -> None:
    write(store, FIRST, day=1)
    write(store, SECOND, day=2, types_resolved=False)

    report = build_history_report(store, PROJECT, [FIRST, SECOND])

    [only] = report.rows[1].breaks_from_previous
    assert only.kind is ComparabilityBreak.ABSENT_AFTER
    assert "python type_errors" in only.detail
