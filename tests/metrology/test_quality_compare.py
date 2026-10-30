"""``compare_snapshots``: per-measurement comparability with named breaks (slice 403, D7)."""

from __future__ import annotations

import pytest

from squadron.metrology.quality_report.compare import compare_snapshots
from squadron.metrology.quality_report.models import ComparabilityBreak, MetricComparison
from squadron.metrology.snapshot_models import LengthLimits, SnapshotMetric
from tests.metrology.snapshot.builders import make_measured_snapshot

BEFORE_SHA = "1" * 40
AFTER_SHA = "2" * 40


def row(rows: list[MetricComparison], metric: SnapshotMetric) -> MetricComparison:
    return next(r for r in rows if r.metric is metric)


def kinds(comparison: MetricComparison) -> set[ComparabilityBreak]:
    return {b.kind for b in comparison.breaks}


def test_identical_identity_gives_a_delta_with_sample_sizes() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA, file_total=100, lint_total=4)
    after = make_measured_snapshot(commit_sha=AFTER_SHA, file_total=120, lint_total=6)

    rows = compare_snapshots(before, after)

    lint = row(rows, SnapshotMetric.LINT_COUNT)
    assert (lint.before.total, lint.after.total, lint.delta) == (4, 6, 2)  # pyright: ignore[reportOptionalMemberAccess]
    assert lint.breaks == []
    length = row(rows, SnapshotMetric.FILE_LENGTH)
    assert length.delta == 20
    assert (length.after.n, length.after.n_unit) == (4, "files")  # pyright: ignore[reportOptionalMemberAccess]
    assert row(rows, SnapshotMetric.FUNCTION_LENGTH).after.n_unit == "functions"  # pyright: ignore[reportOptionalMemberAccess]


@pytest.mark.parametrize(
    ("changed", "expected", "metric"),
    [
        ({"lint_version": "0.16.0"}, ComparabilityBreak.TOOL_CHANGED, SnapshotMetric.LINT_COUNT),
        ({"lint_rules_hash": "f" * 64}, ComparabilityBreak.RULE_SET_CHANGED, SnapshotMetric.LINT_COUNT),
        (
            {"lockfile_hash": "e" * 64},
            ComparabilityBreak.ENVIRONMENT_CHANGED,
            SnapshotMetric.TYPE_ERRORS,
        ),
        ({"interpreter": "3.13.0"}, ComparabilityBreak.ENVIRONMENT_CHANGED, SnapshotMetric.TYPE_ERRORS),
    ],
)
def test_a_changed_identity_names_its_break_and_gives_no_delta(
    changed: dict[str, str], expected: ComparabilityBreak, metric: SnapshotMetric
) -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA)
    after = make_measured_snapshot(commit_sha=AFTER_SHA, **changed)

    comparison = row(compare_snapshots(before, after), metric)

    assert kinds(comparison) == {expected}
    assert comparison.delta is None
    assert comparison.breaks[0].detail


def test_a_tool_change_shows_the_remeasure_fix_naming_both_commits() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA)
    after = make_measured_snapshot(commit_sha=AFTER_SHA, lint_version="0.16.0")

    [tool_break] = row(compare_snapshots(before, after), SnapshotMetric.LINT_COUNT).breaks

    assert tool_break.fix is not None
    assert "sq metrology snapshot --commit" in tool_break.fix
    assert BEFORE_SHA[:12] in tool_break.fix
    assert AFTER_SHA[:12] in tool_break.fix


def test_absent_after_and_absent_before_carry_the_absence_reason() -> None:
    measured = make_measured_snapshot(commit_sha=BEFORE_SHA)
    unresolved = make_measured_snapshot(commit_sha=AFTER_SHA, types_resolved=False)

    went_absent = row(compare_snapshots(measured, unresolved), SnapshotMetric.TYPE_ERRORS)
    came_back = row(compare_snapshots(unresolved, measured), SnapshotMetric.TYPE_ERRORS)

    assert kinds(went_absent) == {ComparabilityBreak.ABSENT_AFTER}
    assert "environment_unresolved" in went_absent.breaks[0].detail
    assert kinds(came_back) == {ComparabilityBreak.ABSENT_BEFORE}
    assert went_absent.delta is None
    assert came_back.delta is None


def test_absent_on_both_sides_carries_both_breaks() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA, types_resolved=False)
    after = make_measured_snapshot(commit_sha=AFTER_SHA, types_resolved=False)

    comparison = row(compare_snapshots(before, after), SnapshotMetric.TYPE_ERRORS)

    assert kinds(comparison) == {ComparabilityBreak.ABSENT_BEFORE, ComparabilityBreak.ABSENT_AFTER}


def test_different_limits_mark_every_row_naming_the_limits() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA)
    after = make_measured_snapshot(
        commit_sha=AFTER_SHA,
        limits=LengthLimits(max_file_lines=300, max_function_lines=50, limits_declared=True),
    )

    rows = compare_snapshots(before, after)

    assert rows
    for comparison in rows:
        settings = [b for b in comparison.breaks if b.kind is ComparabilityBreak.SETTINGS_CHANGED]
        assert len(settings) == 1
        assert "limits" in settings[0].detail
        assert "file 300" in settings[0].detail
        assert comparison.delta is None


def test_different_exclusions_mark_every_row_naming_the_exclusions() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA)
    after = make_measured_snapshot(commit_sha=AFTER_SHA, exclusions=["vendor/**"])

    rows = compare_snapshots(before, after)

    for comparison in rows:
        settings = [b for b in comparison.breaks if b.kind is ComparabilityBreak.SETTINGS_CHANGED]
        assert len(settings) == 1
        assert "exclusions" in settings[0].detail
        assert "vendor/**" in settings[0].detail
        assert comparison.delta is None


def test_a_language_in_only_one_snapshot_is_absent_on_the_other_side() -> None:
    before = make_measured_snapshot(commit_sha=BEFORE_SHA)
    after = make_measured_snapshot(commit_sha=AFTER_SHA).model_copy(update={"languages": []})

    comparison = row(compare_snapshots(before, after), SnapshotMetric.LINT_COUNT)

    assert kinds(comparison) == {ComparabilityBreak.ABSENT_AFTER}
    assert "no python files" in comparison.breaks[0].detail
