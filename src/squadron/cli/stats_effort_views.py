"""Tables for ``sq stats slice`` and ``sq stats slices`` (slice 176 D7).

The tables format the same report values ``to_json_dict()`` serializes, so ``--json`` and the
table cannot disagree. No aggregation happens here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.cli.run_views import print_lines
from squadron.cli.stats_views import UNREADABLE_RUNS_TEXT, UNREPORTED
from squadron.core.usage import format_usd
from squadron.pipeline.run_liveness import format_duration
from squadron.stats.artifacts_report import ArtifactsUsageReport
from squadron.stats.effort_report import (
    CODE_REVIEW_TYPE,
    DESIGN_REVIEW_TYPE,
    NO_TASK_FILE_NOTE,
    TASKS_REVIEW_TYPE,
    GroupRow,
    ReviewTypeRounds,
    SliceEffortReport,
)
from squadron.stats.effort_rollup import LevelRow, Measure, MeasureStat, SlicesEffortReport
from squadron.stats.slice_spend import SliceSpend
from squadron.stats.task_attribution import GroupStatus
from squadron.stats.usage_report import PARTIAL_LOOP_NOTE

UNPLANNED_LABEL = "unplanned"
SPAN_FOOTER = "span is wall-clock time between commits and includes idle time"
SPEND_FOOTER = (
    "recorded spend counts pipeline runs and standalone reviews; "
    "interactive Claude Code sessions are not recorded"
)
LOWER_BOUND_FOOTER = (
    "review round counts are a lower bound: the earliest round predates per-round commits"
)
ORDINAL_FOOTER = "planned effort is an ordinal rank: levels are compared by distribution, not ratio"
_REVIEW_LABELS = (
    (DESIGN_REVIEW_TYPE, "slice"),
    (TASKS_REVIEW_TYPE, "tasks"),
    (CODE_REVIEW_TYPE, "code"),
)
_SHORT_SHA_LENGTH = 8
_NOT_ACCEPTED = "not accepted"

_GROUP_COLUMNS = [
    Column("Group", shrinkable=False),
    Column("Tasks", shrinkable=False),
    Column("Effort", shrinkable=False),
    Column("Done", shrinkable=False),
    Column("Marker", shrinkable=True),
    Column("Extra", shrinkable=False),
    Column("Span", shrinkable=False),
]
_LEVEL_COLUMNS = [
    Column("Planned", shrinkable=False),
    Column("n", shrinkable=False),
    *[
        Column(header, shrinkable=True)
        for header in (
            "Span",
            "Impl commits",
            "Fix-ups",
            "Design rounds",
            "Tasks rounds",
            "Recorded spend",
        )
    ],
]


def _span_value(value: float) -> str:
    return format_duration(timedelta(seconds=value))


def _count_value(value: float) -> str:
    return f"{value:g}"


_LEVEL_MEASURES: tuple[tuple[Measure, Callable[[float], str]], ...] = (
    (Measure.SPAN, _span_value),
    (Measure.IMPLEMENTATION_COMMITS, _count_value),
    (Measure.FIXUPS, _count_value),
    (Measure.DESIGN_ROUNDS, _count_value),
    (Measure.TASKS_ROUNDS, _count_value),
    (Measure.RECORDED_SPEND, format_usd),
)


def render_slice_report(report: SliceEffortReport, console: Console) -> None:
    planned = UNREPORTED if report.planned_effort is None else f"{report.planned_effort}/5"
    console.print(
        Text(
            f"Slice {report.index}  {report.title}  planned effort {planned}  "
            f"window: {report.window_source.value}"
        )
    )
    console.print(
        Text(
            f"span {_duration(report.span)}  impl commits {_count(report.implementation_commits)}  "
            f"fix-ups {_count(report.fixups)}  rounds: {_rounds(report.reviews)}"
        )
    )
    console.print(Text(f"recorded spend {_spend(report.spend)}"))
    if report.artifact_usage is not None and report.artifact_usage.by_kind:
        console.print(Text(_artifact_spend(report.artifact_usage)))
    if report.task_file_missing:
        console.print(Text(NO_TASK_FILE_NOTE))
    else:
        console.print()
        rows = [_group_cells(number, group) for number, group in enumerate(report.groups, start=1)]
        print_lines(render_rows(_GROUP_COLUMNS, rows, available=available_width(console)), console)
    _print_slice_footer(report, console)


def render_slices_report(report: SlicesEffortReport, console: Console) -> None:
    if report.empty_reason is not None:
        console.print(Text(report.empty_reason))
        return
    since = "" if report.since is None else f"  since {report.since}"
    console.print(Text(f"Completed slices {report.slices}{since}"))
    console.print()
    rows = [_level_cells(level) for level in report.levels]
    print_lines(render_rows(_LEVEL_COLUMNS, rows, available=available_width(console)), console)
    footers = [ORDINAL_FOOTER, SPAN_FOOTER, SPEND_FOOTER]
    if report.lower_bound_slices:
        footers.append(f"{report.lower_bound_slices} slice(s): {LOWER_BOUND_FOOTER}")
    footers += _count_footers(report.markers_not_found, report.rounds_skipped, report.unreadable_runs)
    _print_all(footers, console)


def _print_slice_footer(report: SliceEffortReport, console: Console) -> None:
    footers = [SPAN_FOOTER, SPEND_FOOTER]
    if report.lower_bound:
        footers.append(LOWER_BOUND_FOOTER)
    if report.spend.partial_loop_runs:
        footers.append(f"{report.spend.partial_loop_runs} run(s): {PARTIAL_LOOP_NOTE}")
    footers += _count_footers(report.markers_not_found, report.rounds_skipped, report.unreadable_runs)
    _print_all(footers, console)


def _count_footers(markers_not_found: int, rounds_skipped: int, unreadable_runs: int) -> list[str]:
    footers: list[str] = []
    if markers_not_found:
        footers.append(f"{markers_not_found} task group(s): {GroupStatus.MARKER_NOT_FOUND.value}")
    if rounds_skipped:
        footers.append(f"{rounds_skipped} review round(s) skipped (unreadable)")
    if unreadable_runs:
        footers.append(f"{unreadable_runs} {UNREADABLE_RUNS_TEXT}")
    return footers


def _print_all(lines: list[str], console: Console) -> None:
    console.print()
    for line in lines:
        console.print(Text(line))


def _group_cells(number: int, group: GroupRow) -> list[Text]:
    tasks = (
        str(group.first_task)
        if group.first_task == group.last_task
        else f"{group.first_task}–{group.last_task}"
    )
    marker = (
        group.marker_sha[:_SHORT_SHA_LENGTH] if group.marker_sha is not None else group.status.value
    )
    cells = [
        str(number),
        tasks,
        UNREPORTED if group.planned_effort is None else str(group.planned_effort),
        f"{group.checked}/{group.total}",
        marker,
        _count(group.extra),
        _duration(group.span),
    ]
    return [Text(cell) for cell in cells]


def _level_cells(level: LevelRow) -> list[Text]:
    label = UNPLANNED_LABEL if level.level is None else f"{level.level}/5"
    cells = [label, str(level.n)]
    cells += [_stat_cell(level.measures[measure.value], fmt) for measure, fmt in _LEVEL_MEASURES]
    return [Text(cell) for cell in cells]


def _stat_cell(stat: MeasureStat, fmt: Callable[[float], str]) -> str:
    if stat.median is None or stat.minimum is None or stat.maximum is None:
        return UNREPORTED
    median, low, high = (fmt(v) for v in (stat.median, stat.minimum, stat.maximum))
    return f"{median} ({low}–{high}) n={stat.n}"


def _rounds(reviews: tuple[ReviewTypeRounds, ...]) -> str:
    by_type = {review.review_type: review for review in reviews}
    parts: list[str] = []
    for review_type, label in _REVIEW_LABELS:
        review = by_type[review_type]
        if review.rounds == 0:
            value = UNREPORTED
        elif review.to_accept is None:
            value = f"{review.rounds} ({_NOT_ACCEPTED})"
        else:
            value = str(review.to_accept)
        parts.append(f"{label} {value}")
    return " · ".join(parts)


def _spend(spend: SliceSpend) -> str:
    cost = spend.totals.cost_usd
    if cost is None:
        return UNREPORTED
    return f"{format_usd(cost)} ({spend.totals.priced} of {spend.llm_actions} priced)"


def _artifact_spend(usage: ArtifactsUsageReport) -> str:
    """Stamped production cost per artifact kind; a floor, and never added to recorded spend."""
    parts: list[str] = []
    for item in usage.by_kind:
        cost = UNREPORTED if item.cost_usd is None else format_usd(item.cost_usd)
        parts.append(f"{item.kind.value} {cost} ({item.priced_rounds} of {item.rounds} rounds)")
    line = f"artifact spend: {' · '.join(parts)} (floor)"
    return f"{line}\n{_model_spend(usage)}" if usage.by_model else line


def _model_spend(usage: ArtifactsUsageReport) -> str:
    """Stamped production cost per model; rounds stamped before the split are unattributed."""
    parts = [
        f"{item.model} {UNREPORTED if item.cost_usd is None else format_usd(item.cost_usd)} "
        f"({item.rounds} rounds)"
        for item in usage.by_model
    ]
    if usage.unattributed_rounds:
        parts.append(f"no model recorded ({usage.unattributed_rounds} rounds)")
    return f"by model: {' · '.join(parts)}"


def _duration(value: timedelta | None) -> str:
    return UNREPORTED if value is None else format_duration(value)


def _count(value: int | None) -> str:
    return UNREPORTED if value is None else str(value)
