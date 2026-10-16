"""The ``sq stats slices`` report core: completed slices grouped by planned effort (D2, D7).

Planned effort is an ordinal rank, so each level reports the distribution of every actual
measure (n, median, min–max), never a ratio. A measure that is unknown for a slice is left
out of that measure's distribution, and each measure carries its own n.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.pipeline.state import StateManager
from squadron.review.persistence import REVIEWS_DIR
from squadron.stats.effort_report import (
    DESIGN_REVIEW_TYPE,
    TASKS_REVIEW_TYPE,
    SliceEffortReport,
    build_slice_report,
)
from squadron.stats.git_history import GitHistory
from squadron.stats.json_support import to_json_dict
from squadron.stats.planning_docs import read_slice_plans, slice_status
from squadron.stats.slice_spend import SpendSources

#: The report's reason when nothing matched (D9); `since` is appended when it filtered.
NO_COMPLETED_SLICES = "no completed slices"


class Measure(StrEnum):
    SPAN = "span"  # seconds, first to last window commit
    IMPLEMENTATION_COMMITS = "implementation_commits"
    FIXUPS = "fixups"
    DESIGN_ROUNDS = "design_rounds"  # slice-design review rounds to acceptance
    TASKS_ROUNDS = "tasks_rounds"  # task-breakdown review rounds to acceptance
    RECORDED_SPEND = "recorded_spend"  # USD over priced records


@dataclass(frozen=True)
class MeasureStat:
    n: int
    median: float | None
    minimum: float | None
    maximum: float | None


@dataclass(frozen=True)
class LevelRow:
    level: int | None  # planned effort; None is `unplanned`
    n: int
    measures: dict[str, MeasureStat]


@dataclass(frozen=True)
class SlicesEffortReport:
    since: str | None
    levels: tuple[LevelRow, ...]
    slices: int
    empty_reason: str | None
    markers_not_found: int
    rounds_skipped: int
    lower_bound_slices: int
    unreadable_runs: int

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)


def slices_effort_report(
    *, since: str | None, project_root: Path, history: GitHistory, state_manager: StateManager
) -> SlicesEffortReport:
    """Roll up every completed slice (design ``status: complete``, ``dateCreated`` >= ``since``)."""
    sources = SpendSources.load(state_manager, project_root / REVIEWS_DIR)
    reports = [
        (planned.effort, build_slice_report(planned, project_root, history, sources))
        for planned in read_slice_plans(project_root).values()
        if planned.complete and _created_since(planned.index, project_root, since)
    ]
    reports.sort(key=lambda pair: pair[1].index)
    if not reports:
        reason = NO_COMPLETED_SLICES if since is None else f"{NO_COMPLETED_SLICES} since {since}"
        return SlicesEffortReport(since, (), 0, reason, 0, 0, 0, len(sources.scan.unreadable))
    return SlicesEffortReport(
        since=since,
        levels=_levels(reports),
        slices=len(reports),
        empty_reason=None,
        markers_not_found=sum(r.markers_not_found for _, r in reports),
        rounds_skipped=sum(r.rounds_skipped for _, r in reports),
        lower_bound_slices=sum(r.lower_bound for _, r in reports),
        unreadable_runs=len(sources.scan.unreadable),
    )


def _created_since(index: int, project_root: Path, since: str | None) -> bool:
    if since is None:
        return True
    created = slice_status(index, project_root)[1]
    return created is not None and created >= since


def _levels(reports: list[tuple[int | None, SliceEffortReport]]) -> tuple[LevelRow, ...]:
    levels = sorted({level for level, _ in reports if level is not None})
    unplanned = any(planned is None for planned, _ in reports)
    order: list[int | None] = [*levels, None] if unplanned else [*levels]
    rows: list[LevelRow] = []
    for level in order:
        members = [report for planned, report in reports if planned == level]
        measures = {m.value: _stat(_values(members, m)) for m in Measure}
        rows.append(LevelRow(level=level, n=len(members), measures=measures))
    return tuple(rows)


def _values(members: list[SliceEffortReport], measure: Measure) -> list[float]:
    found = (_measure_value(report, measure) for report in members)
    return [value for value in found if value is not None]


def _measure_value(report: SliceEffortReport, measure: Measure) -> float | None:
    rounds = {r.review_type: r.to_accept for r in report.reviews}
    match measure:
        case Measure.SPAN:
            return None if report.span is None else report.span.total_seconds()
        case Measure.IMPLEMENTATION_COMMITS:
            return report.implementation_commits
        case Measure.FIXUPS:
            return report.fixups
        case Measure.DESIGN_ROUNDS:
            return rounds.get(DESIGN_REVIEW_TYPE)
        case Measure.TASKS_ROUNDS:
            return rounds.get(TASKS_REVIEW_TYPE)
        case Measure.RECORDED_SPEND:
            return report.spend.totals.cost_usd


def _stat(values: list[float]) -> MeasureStat:
    if not values:
        return MeasureStat(n=0, median=None, minimum=None, maximum=None)
    return MeasureStat(
        n=len(values),
        median=statistics.median(values),
        minimum=min(values),
        maximum=max(values),
    )
