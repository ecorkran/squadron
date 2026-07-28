"""Floor-relative delta computation (324 T5-T6).

The no-floor case is asserted separately everywhere it can occur: an
unmeasured floor must report ``None``, never ``False``, because ``False``
reads as "measured, and the change exceeds noise".
"""

from __future__ import annotations

import pytest

from squadron.metrology.audit_delta import compute_delta, is_within_floor
from squadron.metrology.audit_models import (
    DELTA_DISCLAIMER,
    AuditCategory,
    AuditRun,
    BaselineCell,
    FloorStat,
    ProjectBaseline,
)
from squadron.metrology.models import ProjectId, ProjectIdSource

from .conftest import make_audit_finding, make_audit_run

_DECAY = AuditCategory.ARCHITECTURAL_DECAY
_TEST_DEBT = AuditCategory.TEST_DEBT
_SECURITY = AuditCategory.SECURITY_HYGIENE


def make_baseline(
    *,
    cells: dict[AuditCategory, tuple[int, FloorStat | None]],
    total_findings: int | None = None,
    total_floor: FloorStat | None = None,
) -> ProjectBaseline:
    """A baseline whose cells are ``{category: (count, floor)}``."""
    return ProjectBaseline(
        project_id=ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE),
        commit_sha="a" * 40,
        audit_prompt_hash="b" * 64,
        run_id="audit-20260726-abcd1234",
        measured_at=make_audit_run().measured_at,
        total_findings=(
            total_findings if total_findings is not None else sum(count for count, _ in cells.values())
        ),
        unnormalized_count=0,
        total_floor=total_floor,
        floor_note=None if total_floor is not None else "no floor measured",
        cells=[
            BaselineCell(
                category=category,
                count=count,
                floor=floor,
                floor_note=None if floor is not None else "no floor measured",
            )
            for category, (count, floor) in cells.items()
        ],
    )


def make_run_with(counts: dict[AuditCategory, int], *, commit_sha: str = "a" * 40) -> AuditRun:
    """An AuditRun carrying ``counts[category]`` findings per category."""
    findings = [
        make_audit_finding(finding_id=f"F{category.value}-{index}", category=category)
        for category, count in counts.items()
        for index in range(count)
    ]
    return make_audit_run(findings=findings, commit_sha=commit_sha)


def test_known_value_per_category_and_total_deltas() -> None:
    baseline = make_baseline(
        cells={_DECAY: (5, None), _TEST_DEBT: (2, None), _SECURITY: (1, None)},
    )
    new_run = make_run_with({_DECAY: 3, _TEST_DEBT: 4, _SECURITY: 1})

    report = compute_delta(baseline, new_run)
    by_category = {cell.category: cell for cell in report.cells}

    assert by_category[_DECAY].delta == -2
    assert by_category[_DECAY].baseline_count == 5
    assert by_category[_DECAY].new_count == 3
    assert by_category[_TEST_DEBT].delta == 2
    assert by_category[_SECURITY].delta == 0

    assert report.baseline_total == 8
    assert report.new_total == 8
    assert report.total_delta == 0


def test_within_floor_when_delta_below_observed_spread() -> None:
    """Spread is max - min = 6; a delta of 2 is indistinguishable from noise."""
    floor = FloorStat(min=3, max=9, mean=6.0, stddev=2.4)
    baseline = make_baseline(cells={_DECAY: (5, floor)}, total_floor=floor)
    new_run = make_run_with({_DECAY: 7})

    report = compute_delta(baseline, new_run)

    assert report.cells[0].delta == 2
    assert report.cells[0].within_floor is True
    assert report.total_within_floor is True


def test_outside_floor_when_delta_meets_spread() -> None:
    """At exactly the spread the delta is not *within* it — boundary is strict."""
    floor = FloorStat(min=4, max=6, mean=5.0, stddev=1.0)
    baseline = make_baseline(cells={_DECAY: (5, floor)}, total_floor=floor)
    new_run = make_run_with({_DECAY: 7})

    report = compute_delta(baseline, new_run)

    assert report.cells[0].delta == 2
    assert report.cells[0].within_floor is False
    assert report.total_within_floor is False


def test_outside_floor_when_delta_exceeds_spread() -> None:
    floor = FloorStat(min=4, max=6, mean=5.0, stddev=1.0)
    baseline = make_baseline(cells={_DECAY: (10, floor)}, total_floor=floor)
    new_run = make_run_with({_DECAY: 1})

    report = compute_delta(baseline, new_run)

    assert report.cells[0].delta == -9
    assert report.cells[0].within_floor is False


def test_no_floor_reports_none_not_false() -> None:
    """An unmeasured floor licenses no claim in either direction."""
    floor = FloorStat(min=3, max=9, mean=6.0, stddev=2.4)
    baseline = make_baseline(
        cells={_DECAY: (5, floor), _TEST_DEBT: (2, None)},
        total_floor=None,
    )
    new_run = make_run_with({_DECAY: 6, _TEST_DEBT: 9})

    report = compute_delta(baseline, new_run)
    by_category = {cell.category: cell for cell in report.cells}

    assert by_category[_DECAY].within_floor is True
    assert by_category[_TEST_DEBT].within_floor is None
    assert by_category[_TEST_DEBT].delta == 7
    assert report.total_within_floor is None


def test_zero_fill_category_absent_from_new_run() -> None:
    """A class disappearing entirely is a real delta, never a skipped row."""
    baseline = make_baseline(cells={_DECAY: (4, None), _TEST_DEBT: (3, None)})
    new_run = make_run_with({_DECAY: 4})

    report = compute_delta(baseline, new_run)
    by_category = {cell.category: cell for cell in report.cells}

    assert by_category[_TEST_DEBT].baseline_count == 3
    assert by_category[_TEST_DEBT].new_count == 0
    assert by_category[_TEST_DEBT].delta == -3


def test_zero_fill_category_absent_from_baseline() -> None:
    """A class appearing for the first time is likewise a real delta."""
    baseline = make_baseline(cells={_DECAY: (4, None)})
    new_run = make_run_with({_DECAY: 4, _SECURITY: 2})

    report = compute_delta(baseline, new_run)
    by_category = {cell.category: cell for cell in report.cells}

    assert by_category[_SECURITY].baseline_count == 0
    assert by_category[_SECURITY].new_count == 2
    assert by_category[_SECURITY].delta == 2


def test_category_absent_from_both_sides_is_omitted() -> None:
    baseline = make_baseline(cells={_DECAY: (4, None)})
    new_run = make_run_with({_DECAY: 4})

    report = compute_delta(baseline, new_run)

    assert [cell.category for cell in report.cells] == [_DECAY]


def test_commit_shas_are_carried_from_both_sides() -> None:
    baseline = make_baseline(cells={_DECAY: (1, None)})
    new_run = make_run_with({_DECAY: 1}, commit_sha="f" * 40)

    report = compute_delta(baseline, new_run)

    assert report.baseline_commit_sha == "a" * 40
    assert report.new_commit_sha == "f" * 40


@pytest.mark.parametrize(
    ("baseline_cells", "new_counts"),
    [
        ({_DECAY: (5, FloorStat(min=3, max=9, mean=6.0, stddev=2.4))}, {_DECAY: 5}),
        ({_DECAY: (5, None)}, {_DECAY: 0}),
        ({}, {}),
    ],
)
def test_disclaimer_present_unconditionally(
    baseline_cells: dict[AuditCategory, tuple[int, FloorStat | None]],
    new_counts: dict[AuditCategory, int],
) -> None:
    """Every report carries it — never gated on having a floor or a delta."""
    report = compute_delta(make_baseline(cells=baseline_cells), make_run_with(new_counts))

    assert report.disclaimer == DELTA_DISCLAIMER


@pytest.mark.parametrize(
    ("delta", "floor", "expected"),
    [
        (0, None, None),
        (99, None, None),
        (0, FloorStat(min=5, max=5, mean=5.0, stddev=0.0), False),
        (1, FloorStat(min=4, max=6, mean=5.0, stddev=1.0), True),
        (-1, FloorStat(min=4, max=6, mean=5.0, stddev=1.0), True),
        (2, FloorStat(min=4, max=6, mean=5.0, stddev=1.0), False),
        (-2, FloorStat(min=4, max=6, mean=5.0, stddev=1.0), False),
    ],
)
def test_is_within_floor_boundaries(delta: int, floor: FloorStat | None, expected: bool | None) -> None:
    """A zero-width floor (min == max) admits no delta as within noise."""
    assert is_within_floor(delta, floor) is expected
