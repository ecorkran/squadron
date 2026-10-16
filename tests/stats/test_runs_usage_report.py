"""The cross-run usage report (slice 176 D7; 175 D9 totals rules)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.pipeline.state import RunState, StateManager
from squadron.stats.usage_report import RunsUsageReport, runs_usage_report
from tests.stats.producer_support import action, producer_actions, run, step, usage


def _write(runs_dir: Path, *states: RunState) -> StateManager:
    for state in states:
        (runs_dir / f"{state.run_id}.json").write_text(state.model_dump_json())
    return StateManager(runs_dir=runs_dir)


def _day(day: int) -> datetime:
    return datetime(2026, 11, day, 9, tzinfo=UTC)


def _report(
    manager: StateManager, *, slice_index: int | None = None, pipeline: str | None = None
) -> RunsUsageReport:
    return runs_usage_report(slice_index=slice_index, pipeline=pipeline, state_manager=manager)


@pytest.fixture
def runs_dir(tmp_path: Path) -> Path:
    directory = tmp_path / "runs"
    directory.mkdir()
    return directory


@pytest.fixture
def manager(runs_dir: Path) -> StateManager:
    """p4 on slice 1 ($1 dispatch), p5 on slice 1 with a loop ($1 + $0.5 + $0.25), p4 on slice 2."""
    simple = run(
        "p4-s1",
        [step("design-0", "design", producer_actions(cost=1.0))],
        slice_index=1,
        started_at=_day(1),
    )
    looped = run(
        "p5-s1",
        [
            step("tasks-0", "tasks", producer_actions(cost=1.0)),
            step(
                "loop-1",
                "loop",
                [action("dispatch", usage_record=usage(cost=0.25))],
                iteration=2,
                prior_rounds=[[action("dispatch", usage_record=usage(cost=0.5))]],
            ),
        ],
        pipeline="p5",
        slice_index=1,
        started_at=_day(2),
    )
    other = run(
        "p4-s2",
        [step("design-0", "design", producer_actions(cost=3.0))],
        slice_index=2,
        started_at=_day(3),
    )
    return _write(runs_dir, simple, looped, other)


def test_each_filter_and_both_together_and_none(manager: StateManager) -> None:
    assert len(_report(manager).rows) == 3
    assert [r.run_id for r in _report(manager, slice_index=1).rows] == ["p5-s1", "p4-s1"]
    assert [r.run_id for r in _report(manager, pipeline="p4").rows] == ["p4-s2", "p4-s1"]
    both = _report(manager, slice_index=1, pipeline="p4")
    assert [r.run_id for r in both.rows] == ["p4-s1"]
    assert _report(manager, slice_index=99).rows == ()


def test_rows_are_newest_first_and_carry_run_identity(manager: StateManager) -> None:
    report = _report(manager)

    assert [r.run_id for r in report.rows] == ["p4-s2", "p5-s1", "p4-s1"]
    first = report.rows[0]
    assert (first.pipeline, first.slice, first.status) == ("p4", "2", "completed")
    assert first.started_at == _day(3)


def test_totals_equal_the_sum_of_per_run_totals_including_loop_rounds(
    manager: StateManager,
) -> None:
    report = _report(manager)

    per_run = {r.run_id: r.totals.cost_usd for r in report.rows}
    assert per_run == {"p4-s1": 1.0, "p5-s1": pytest.approx(1.75), "p4-s2": 3.0}
    assert report.totals.cost_usd == pytest.approx(5.75)
    assert report.totals.priced == 5  # 1 + (1, 0.5, 0.25) + 1
    assert report.totals.usage.prompt == sum(r.totals.usage.prompt or 0 for r in report.rows)
    looped = next(r for r in report.rows if r.run_id == "p5-s1")
    assert (looped.llm_actions, looped.recorded) == (4, 3)  # dispatch, review, 2 loop dispatches


def test_a_pre_175_run_counts_as_unpriced_not_zero(runs_dir: Path) -> None:
    old = run(
        "old", [step("design-0", "design", [action("dispatch"), action("review")])], started_at=_day(1)
    )
    priced = run("new", [step("design-0", "design", producer_actions(cost=2.0))], started_at=_day(2))
    report = _report(_write(runs_dir, old, priced))

    old_row = next(r for r in report.rows if r.run_id == "old")
    assert old_row.totals.cost_usd is None and old_row.totals.priced == 0
    assert (old_row.llm_actions, old_row.recorded) == (2, 0)
    assert report.totals.cost_usd == 2.0  # the priced run only
    assert (report.totals.priced, report.llm_actions) == (1, 4)  # "1 of 4 priced"


def test_only_unpriced_runs_have_no_total_cost_at_all(runs_dir: Path) -> None:
    old = run("old", [step("design-0", "design", [action("dispatch")])])

    report = _report(_write(runs_dir, old))

    assert report.totals.cost_usd is None


def test_an_unreadable_run_file_is_counted(manager: StateManager, runs_dir: Path) -> None:
    (runs_dir / "run-corrupt.json").write_text("{not json")

    report = _report(manager)

    assert report.unreadable_runs == 1 and len(report.rows) == 3


def test_a_partial_loop_run_is_flagged(runs_dir: Path) -> None:
    stuck = run(
        "stuck",
        [step("design-0", "design", producer_actions()), step("loop-1", "loop", status="failed")],
        status="failed",
        current_step="loop-1",
    )

    report = _report(_write(runs_dir, stuck))

    assert report.rows[0].partial_loop is True


def test_json_values_equal_the_report_values(manager: StateManager) -> None:
    report = _report(manager, slice_index=1)

    data = report.to_json_dict()

    assert data["slice_index"] == 1 and data["pipeline"] is None
    rows = data["rows"]
    assert isinstance(rows, list) and [r["run_id"] for r in rows] == ["p5-s1", "p4-s1"]
    assert rows[0]["totals"]["cost_usd"] == pytest.approx(1.75)
    assert data["totals"]["cost_usd"] == pytest.approx(2.75)  # type: ignore[index]
