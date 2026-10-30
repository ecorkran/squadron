"""Text rendering of the rollup reports (slice 403)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.quality_report.history_report import build_history_report
from squadron.metrology.quality_report.models import SliceReport
from squadron.metrology.quality_report.project_report import build_project_report
from squadron.metrology.quality_report.render import (
    comparison_lines,
    render_history_report,
    render_project_report,
    render_slice_report,
)
from squadron.metrology.quality_report.slice_report import build_slice_report
from squadron.metrology.slice_range import RecordedLanding, SliceRangeResult
from squadron.metrology.slice_range_models import RangeUnresolvedReason
from squadron.metrology.snapshot_models import CodeSnapshot, LengthLimits, SnapshotMetric
from squadron.metrology.store import MetrologyStore, code_review_record_id
from tests.metrology.snapshot.builders import make_measured_snapshot, make_project_id
from tests.metrology.test_quality_slice_report import landing
from tests.metrology.test_review_models import make_record

PROJECT = make_project_id()
FIRST_BEFORE, FIRST_AFTER = "1" * 40, "2" * 40
SECOND_BEFORE, SECOND_AFTER = "3" * 40, "4" * 40
LIMITS = LengthLimits(max_file_lines=300, max_function_lines=50, limits_declared=True)


@pytest.fixture
def store(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path / "render-store")


def snapshot_for(commit: str) -> CodeSnapshot:
    """The second landing's after commit was measured with a newer ruff."""
    return make_measured_snapshot(
        commit_sha=commit,
        lint_version="0.16.0" if commit == SECOND_AFTER else "0.15.1",
        file_total=120 if commit == FIRST_AFTER else 100,
        limits=LIMITS,
        exclusions=["vendor/**"],
    )


def two_landing_report(store: MetrologyStore) -> SliceReport:
    path = "project-documents/user/reviews/940-review.code.a.md"
    store.write_code_review(
        make_record().model_copy(
            update={
                "slice_index": 940,
                "review_path": path,
                "record_id": code_review_record_id(PROJECT, path),
            }
        )
    )
    result = SliceRangeResult(
        940,
        [
            RecordedLanding(landing(FIRST_BEFORE, FIRST_AFTER), False),
            RecordedLanding(landing(SECOND_BEFORE, SECOND_AFTER), False),
        ],
        None,
    )
    return build_slice_report(940, result, store, PROJECT, lambda sha: True, snapshot_for)


def test_slice_report_key_lines(store: MetrologyStore) -> None:
    text = "\n".join(render_slice_report(two_landing_report(store)))

    assert "Slice 940 — 2 landings on main" in text
    assert "Landing 1  merge " in text
    assert "Landing 2  merge " in text
    assert "measured under 11111111 limits file 300, function 50; 1 exclusions" in text
    assert "total 100 → 120 (+20)" in text
    assert f"audit   no audit run at {'1' * 12}; no audit run at {'2' * 12}" in text
    assert "Reviews (by source document; no floor measured)" in text
    assert "n=1 review files, 1 findings (write-time 1, read-side mapped 0)" in text


def test_a_break_prints_not_compared_with_its_detail_and_fix(store: MetrologyStore) -> None:
    lines = render_slice_report(two_landing_report(store))

    [break_line] = [line for line in lines if "lint_count" in line and "not compared" in line]
    assert "not compared: tool_changed (ruff 0.15.1 -> ruff 0.16.0)" in break_line
    assert any(
        line.strip().startswith("fix: re-measure both with sq metrology snapshot") for line in lines
    )


def test_an_unresolved_slice_prints_its_reason(store: MetrologyStore) -> None:
    unresolved = SliceRangeResult(388, [], RangeUnresolvedReason.REFLOG_UNAVAILABLE)
    report = build_slice_report(388, unresolved, store, PROJECT, lambda sha: True, snapshot_for)

    assert render_slice_report(report) == ["Slice 388 — unresolved: reflog_unavailable"]


def test_a_missing_commit_prints_not_found(store: MetrologyStore) -> None:
    result = SliceRangeResult(940, [RecordedLanding(landing(FIRST_BEFORE, FIRST_AFTER), False)], None)
    report = build_slice_report(940, result, store, PROJECT, lambda sha: False, snapshot_for)

    text = "\n".join(render_slice_report(report))

    assert f"commit {FIRST_BEFORE} not found" in text


def test_project_report_key_lines(store: MetrologyStore) -> None:
    store.write_snapshot(snapshot_for(FIRST_BEFORE))

    lines = render_project_report(build_project_report(store, PROJECT, resolved_indices=set()))

    assert lines[0] == f"Project {PROJECT.value} — latest snapshot 11111111"
    assert any(line.strip().startswith("python.lint_count=4") for line in lines)
    assert "Audit baseline: no audit run recorded" in lines
    assert any(line.startswith("Reviews attributed to the project only") for line in lines)


def test_empty_project_report_says_so(store: MetrologyStore) -> None:
    lines = render_project_report(build_project_report(store, PROJECT, resolved_indices=set()))

    assert lines[0] == f"Project {PROJECT.value} — no snapshot recorded"


def test_history_report_prints_a_break_marker_and_the_off_line_count(
    store: MetrologyStore,
) -> None:
    store.write_snapshot(snapshot_for(FIRST_AFTER))
    store.write_snapshot(
        snapshot_for(SECOND_AFTER).model_copy(
            update={"measured_at": datetime(2026, 10, 25, tzinfo=UTC)}
        )
    )
    store.write_snapshot(snapshot_for("9" * 40))

    lines = render_history_report(build_history_report(store, PROJECT, [FIRST_AFTER, SECOND_AFTER]))

    assert lines[0] == "History — 2 snapshots on the first-parent line"
    assert any(line.strip().startswith("--- not compared: tool_changed") for line in lines)
    assert lines[-1] == "1 snapshots of commits off this line not shown"


def test_a_metric_absent_at_both_commits_for_the_same_reason_prints_one_short_line(
    store: MetrologyStore,
) -> None:
    lines = render_slice_report(two_landing_report(store))

    rows = [line for line in lines if "coverable_lines" in line]

    assert len(rows) == 2  # one per landing
    for line in rows:
        assert "absent at both commits: metric_unsupported: not measured by this fixture" in line
        assert "absent_before" not in line


def test_long_metric_names_keep_a_space_before_the_figures(store: MetrologyStore) -> None:
    result = SliceRangeResult(940, [RecordedLanding(landing(FIRST_BEFORE, FIRST_AFTER), False)], None)
    report = build_slice_report(940, result, store, PROJECT, lambda sha: True, snapshot_for)
    row = (
        report.landings[0]
        .comparisons[0]
        .model_copy(update={"metric": SnapshotMetric.CYCLOMATIC_COMPLEXITY})
    )

    [line] = comparison_lines([row])

    assert "cyclomatic_complexity " in line
