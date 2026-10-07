"""Rich views of pipelines and runs, shared by the run, pipelines and runs commands.

Command modules import their views from here so that no command module imports
another (slice 199).
"""

from __future__ import annotations

from rich import print as rprint
from rich.markup import escape
from rich.panel import Panel
from rich.table import Table

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loader import LISTING_ORDER, PipelineInfo, PipelineSource
from squadron.pipeline.run_listing import ResumeKind, ResumeProblem, RunSummary
from squadron.pipeline.state import RunState

# Keyed by ExecutionStatus values; a status not listed renders UNKNOWN_STATUS_COLOR.
STATUS_COLORS: dict[str, str] = {
    ExecutionStatus.COMPLETED.value: "bright_green",
    ExecutionStatus.FAILED.value: "red",
    ExecutionStatus.PAUSED.value: "yellow",
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
_UNFOLDED_COLUMNS = frozenset({"Run ID", "Status", "Resume at"})
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
        f"[bold]Run:[/bold]      {state.run_id}",
        f"[bold]Pipeline:[/bold] {state.pipeline}",
        f"[bold]Params:[/bold]   {state.params}",
        f"[bold]Status:[/bold]   [{color}]{state.status}[/{color}]",
        f"[bold]Mode:[/bold]     {state.execution_mode.value}",
        f"[bold]Started:[/bold]  {state.started_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Updated:[/bold]  {state.updated_at:%Y-%m-%d %H:%M:%S}",
        f"[bold]Steps:[/bold]    {len(state.completed_steps)} completed",
    ]
    if state.checkpoint is not None:
        lines.append(
            f"[bold]Checkpoint:[/bold] paused at '{state.checkpoint.step}' — {state.checkpoint.reason}"
        )

    rprint(Panel("\n".join(lines), title="Run Status"))


def render_pipeline_listing(pipelines: list[PipelineInfo]) -> None:
    """Print one table per non-empty source group, in LISTING_ORDER, names sorted."""
    if not pipelines:
        rprint("No pipelines found.")
        return
    for source in LISTING_ORDER:
        group = sorted((p for p in pipelines if p.source is source), key=lambda p: p.name)
        if not group:
            continue
        table = Table(title=f"{_SOURCE_TITLES[source]} ({len(group)})", title_justify="left")
        table.add_column("Name", style="bold")
        table.add_column("Description")
        for info in group:
            table.add_row(info.name, info.description)
        rprint(table)


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


def _run_row(summary: RunSummary) -> tuple[str, str, str, str, str]:
    """The plain-text cells before Started, in column order."""
    return (
        summary.run_id,
        summary.pipeline,
        target_cell(summary.params),
        summary.status,
        resume_cell(summary),
    )


def render_run_listing(summaries: list[RunSummary], *, include_all: bool) -> None:
    """Print the run table and the resume hints (``sq runs list``)."""
    if not summaries:
        hint = "" if include_all else " Use --all to include completed runs."
        rprint(f"No resumable runs.{hint}")
        return
    rows = [_run_row(summary) for summary in summaries]
    table = Table(box=None)
    # Run ID (copied into --resume), status and resume point never fold; the rest may.
    for position, column in enumerate(("Run ID", "Pipeline", "Target", "Status", "Resume at")):
        if column in _UNFOLDED_COLUMNS:
            longest = max(len(row[position]) for row in rows)
            table.add_column(column, no_wrap=True, min_width=longest)
        else:
            table.add_column(column, overflow="fold")
    table.add_column("Started", overflow="fold")
    for summary, row in zip(summaries, rows, strict=True):
        color = status_color(summary.status)
        run_id, pipeline, target, status, resume = (escape(cell) for cell in row)
        started = f"{summary.started_at:{_STARTED_FORMAT}}"
        table.add_row(run_id, pipeline, target, f"[{color}]{status}[/{color}]", resume, started)
    rprint(table)
    rprint()
    for hint in _RESUME_HINTS:
        rprint(escape(hint))
