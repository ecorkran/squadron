"""Rich views of pipelines and runs, shared by the run, pipelines and runs commands.

Command modules import their views from here so that no command module imports
another (slice 199).
"""

from __future__ import annotations

from rich import print as rprint
from rich.panel import Panel
from rich.table import Table

from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.loader import LISTING_ORDER, PipelineInfo, PipelineSource
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
