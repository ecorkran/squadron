"""Rich views of pipelines and runs, shared by the run, pipelines and runs commands.

Command modules import their views from here so that no command module imports
another (slice 199).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from rich import get_console
from rich import print as rprint
from rich.console import Console
from rich.markup import escape
from rich.panel import Panel
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loader import LISTING_ORDER, PipelineInfo, PipelineSource
from squadron.pipeline.run_listing import ResumeKind, ResumeProblem, RunListing, RunSummary
from squadron.pipeline.run_liveness import RunLiveness, format_duration
from squadron.pipeline.run_prune import PruneCandidate, PruneCategory
from squadron.pipeline.state import RUNNING_STATUS, RunState

# Keyed by ExecutionStatus values; a status not listed renders UNKNOWN_STATUS_COLOR.
STATUS_COLORS: dict[str, str] = {
    ExecutionStatus.COMPLETED.value: "bright_green",
    ExecutionStatus.FAILED.value: "red",
    ExecutionStatus.PAUSED.value: "yellow",
    RUNNING_STATUS: "cyan",
}
UNKNOWN_STATUS_COLOR = "dim"

_SOURCE_TITLES: dict[PipelineSource, str] = {
    PipelineSource.BUILT_IN: "Built-in",
    PipelineSource.PROJECT: "Project",
    PipelineSource.USER: "User",
}


# The only definition of the text a user sees for each problem; no logic reads it (D6).
RESUME_PROBLEM_MARKERS: dict[ResumeProblem, str] = {
    ResumeProblem.PIPELINE_UNAVAILABLE: "<pipeline unavailable>",
    ResumeProblem.NO_UNFINISHED_STEP: "<no unfinished step>",
    ResumeProblem.ITEM_RESUME_UNSUPPORTED: "<item resume unsupported>",
    ResumeProblem.REPORT_UNREADABLE: "<report unreadable>",
}

_STARTED_FORMAT = "%Y-%m-%d %H:%M"
_RESUME_HINTS = (
    "Resume a step:  sq run --resume <run-id>",
    "Resume an item: sq run --resume <run-id> --item N --decision retry",
    '                (--decision accept: only items counted as "accept")',
)


def status_color(status: str) -> str:
    """The Rich colour for a run status."""
    return STATUS_COLORS.get(status, UNKNOWN_STATUS_COLOR)


def render_run_status(state: RunState) -> None:
    """Print a Rich panel summarising *state* (``sq run --status``, ``sq runs wait``)."""
    color = status_color(state.status)
    lines: list[str] = [
        f"[bold]Run:[/bold]      {escape(state.run_id)}",
        f"[bold]Pipeline:[/bold] {escape(state.pipeline)}",
        f"[bold]Params:[/bold]   {escape(str(state.params))}",
        f"[bold]Status:[/bold]   [{color}]{escape(state.status)}[/{color}]",
        f"[bold]Mode:[/bold]     {state.execution_mode.value}",
        f"[bold]Started:[/bold]  {state.started_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Updated:[/bold]  {state.updated_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Steps:[/bold]    {len(state.completed_steps)} completed",
    ]
    if state.checkpoint is not None:
        checkpoint = state.checkpoint
        lines.append(
            f"[bold]Checkpoint:[/bold] paused at '{escape(checkpoint.step)}' — "
            f"{escape(checkpoint.reason)}"
        )

    rprint(Panel("\n".join(lines), title="Run Status"))


# Params shown per pipeline under ``sq pipelines list -v``; the rest are counted.
LISTED_PARAMS = 3
_GROUP_LABEL_STYLE = "bold"
_GROUP_COUNT_STYLE = "dim"


def params_cell(params: dict[str, str]) -> str:
    """Up to ``LISTED_PARAMS`` params as ``name=default``, then `` +N`` for the rest."""
    shown = " ".join(f"{name}={default}" for name, default in list(params.items())[:LISTED_PARAMS])
    hidden = len(params) - LISTED_PARAMS
    return f"{shown} +{hidden}" if hidden > 0 else shown


def render_pipeline_listing(
    pipelines: list[PipelineInfo], *, verbose: bool = False, console: Console | None = None
) -> None:
    """Print the pipelines as one aligned list, grouped by source in LISTING_ORDER.

    The Name column is as wide across every group as its longest name, so groups
    line up. ``verbose`` adds a params column.
    """
    target = console or get_console()
    if not pipelines:
        target.print("No pipelines found.")
        return
    groups = [
        (source, sorted((p for p in pipelines if p.source is source), key=lambda p: p.name))
        for source in LISTING_ORDER
    ]
    groups = [(source, group) for source, group in groups if group]
    columns = [Column(None, shrinkable=False), Column(None, shrinkable=True)]
    if verbose:
        columns.append(Column(None, shrinkable=True))
    rows: list[list[Text]] = []
    for _, group in groups:
        for info in group:
            row = [Text(info.name), Text(info.description)]
            if verbose:
                row.append(Text(params_cell(info.params)))
            rows.append(row)
    lines = iter(render_rows(columns, rows, available=available_width(target)))
    for index, (source, group) in enumerate(groups):
        label = Text(_SOURCE_TITLES[source], style=_GROUP_LABEL_STYLE)
        label.append(f" ({len(group)})", style=_GROUP_COUNT_STYLE)
        blank = [Text("")] if index else []  # a blank line between groups
        print_lines([*blank, label, *(next(lines) for _ in group)], target)


def resume_cell(summary: RunSummary) -> str:
    """The "Resume at" text: a step, an item count, a problem marker, or empty."""
    if summary.problem is not None:
        return RESUME_PROBLEM_MARKERS[summary.problem]
    resume = summary.resume
    if resume is None:
        return ""
    match resume.kind:
        case ResumeKind.STEP:
            return resume.step_name
        case ResumeKind.ITEMS:
            text = f"{resume.open_items} items in {resume.step_name}"
            return f"{text} ({resume.acceptable_items} accept)" if resume.acceptable_items else text


def target_cell(params: dict[str, object]) -> str:
    return " ".join(f"{key}={value}" for key, value in params.items())


# Display statuses for running runs whose liveness is in doubt. Derived on every
# read and never persisted (174 D4); live and unowned runs show their stored status.
LIVENESS_STATUSES: dict[RunLiveness, tuple[str, str]] = {
    RunLiveness.ORPHANED: ("orphaned", "red"),
    RunLiveness.STALE: ("stale", "yellow"),
}


def display_status(summary: RunSummary) -> tuple[str, str]:
    """The status text and colour a row shows: a liveness status, else the stored one."""
    if summary.liveness is not None and summary.liveness.liveness in LIVENESS_STATUSES:
        return LIVENESS_STATUSES[summary.liveness.liveness]
    return summary.status, status_color(summary.status)


def at_cell(summary: RunSummary) -> str:
    """Where a run is: the running step and item, or where it resumes (199)."""
    if summary.liveness is None:
        return resume_cell(summary)
    if summary.active_step is None:
        return ""
    item = summary.active_item
    if item is None:
        return summary.active_step
    where = f"item {item.position + 1}/{item.total}"
    if item.index is not None:
        where += f" · {item.index}"
    return f"{summary.active_step} [{where}]"


def activity_cell(summary: RunSummary) -> str:
    """How long a running run has run and when it last moved; empty when unowned."""
    assessment = summary.liveness
    if assessment is None or assessment.elapsed is None:
        return ""
    parts = [format_duration(assessment.elapsed)]
    if assessment.progress_age is not None:
        parts.append(f"{format_duration(assessment.progress_age)} ago")
    if assessment.liveness is RunLiveness.STALE and assessment.heartbeat_age is not None:
        parts.append(f"heartbeat {format_duration(assessment.heartbeat_age)} ago")
    return " · ".join(parts)


def _status_text(summary: RunSummary) -> Text:
    text, color = display_status(summary)
    return Text(text, style=color)


@dataclass(frozen=True)
class _RunColumn:
    """One ``sq runs list`` column: its layout and its cell."""

    column: Column
    cell: Callable[[RunSummary], Text]


# Run ID (copied into --resume) and Status never shrink; the rest may (174 D11).
_RUN_COLUMNS: tuple[_RunColumn, ...] = (
    _RunColumn(Column("Run ID", shrinkable=False), lambda s: Text(s.run_id)),
    _RunColumn(Column("Pipeline", shrinkable=True), lambda s: Text(s.pipeline)),
    _RunColumn(Column("Target", shrinkable=True), lambda s: Text(target_cell(s.params))),
    _RunColumn(Column("Status", shrinkable=False), _status_text),
    _RunColumn(Column("At", shrinkable=True), lambda s: Text(at_cell(s))),
    _RunColumn(Column("Started", shrinkable=True), lambda s: Text(f"{s.started_at:{_STARTED_FORMAT}}")),
    _RunColumn(Column("Activity", shrinkable=True), lambda s: Text(activity_cell(s))),
)


def print_lines(lines: list[Text], console: Console | None = None) -> None:
    """Print pre-fitted lines; never re-wrapped by rich, so piped output stays whole."""
    target = console or get_console()
    for line in lines:
        target.print(line, soft_wrap=True)


def render_run_listing(
    summaries: list[RunSummary], *, include_all: bool, console: Console | None = None
) -> None:
    """Print the run rows and the resume hints (``sq runs list``)."""
    target = console or get_console()
    if not summaries:
        hint = "" if include_all else " Use --all to include completed runs."
        target.print(f"No running or resumable runs.{hint}")
        return
    columns = [run_column.column for run_column in _RUN_COLUMNS]
    rows = [[run_column.cell(summary) for run_column in _RUN_COLUMNS] for summary in summaries]
    print_lines(render_rows(columns, rows, available=available_width(target)), target)
    target.print()
    for hint in _RESUME_HINTS:
        target.print(Text(hint))


def unavailable_summary(listing: RunListing) -> str:
    """The one stderr line naming how many runs reference unavailable pipelines (D10)."""
    return (
        f"{listing.unavailable_runs} runs reference {len(listing.unavailable)} unavailable "
        "pipelines (-v for details; sq runs prune --status unavailable removes them)."
    )


def unavailable_details(listing: RunListing) -> list[str]:
    """One ``  <pipeline>: <message>`` line per unavailable pipeline, for ``-v``."""
    return [f"  {name}: {message}" for name, message in sorted(listing.unavailable.items())]


_NO_VALUE = "—"
_PRUNE_COLUMNS = (
    Column("Run ID", shrinkable=False),
    Column("Pipeline", shrinkable=True),
    Column("Status", shrinkable=False),
    Column("Reason", shrinkable=True),
    Column("Age", shrinkable=False),
)


def render_prune_preview(candidates: list[PruneCandidate], console: Console | None = None) -> None:
    """Print the runs a prune selects: stored status, matched categories and age."""
    target = console or get_console()
    rows = [
        [
            Text(candidate.run_id),
            Text(candidate.pipeline or _NO_VALUE),
            Text(candidate.status or _NO_VALUE),
            Text(", ".join(c.value for c in PruneCategory if c in candidate.categories)),
            Text(_NO_VALUE if candidate.age is None else format_duration(candidate.age)),
        ]
        for candidate in candidates
    ]
    print_lines(render_rows(_PRUNE_COLUMNS, rows, available=available_width(target)), target)
