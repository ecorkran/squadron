"""The table for ``sq stats runs`` (slice 176 D7): one row per run, one total.

Formats the values ``RunsUsageReport.to_json_dict()`` serializes. The total row uses 175's
``$X (k of m priced)`` form, so an unpriced action is never counted as $0.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.cli.run_views import STARTED_FORMAT, print_lines
from squadron.cli.stats_views import UNREPORTED, count_cell
from squadron.core.usage import format_usd
from squadron.stats.usage_report import PARTIAL_LOOP_NOTE, RunsUsageReport, RunTotalsRow, UsageTotals

NO_MATCHING_RUNS = "no matching runs"

_COLUMNS = [
    Column("Run ID", shrinkable=False),
    Column("Pipeline", shrinkable=True),
    Column("Slice", shrinkable=False),
    Column("Status", shrinkable=False),
    Column("Started", shrinkable=True),
    Column("Recorded", shrinkable=False),
    Column("Prompt", shrinkable=False),
    Column("Cached", shrinkable=False),
    Column("Compl.", shrinkable=False),
    Column("Cost", shrinkable=True),
]


def render_runs_report(report: RunsUsageReport, console: Console) -> None:
    if not report.rows:
        console.print(Text(NO_MATCHING_RUNS))
        _print_unreadable(report, console)
        return
    rows = [[Text(cell) for cell in _run_cells(row)] for row in report.rows]
    rows.append([Text(cell) for cell in _total_cells(report)])
    print_lines(render_rows(_COLUMNS, rows, available=available_width(console)), console)
    partial = sum(row.partial_loop for row in report.rows)
    if partial:
        console.print(Text(f"{partial} run(s): {PARTIAL_LOOP_NOTE}"))
    _print_unreadable(report, console)


def _print_unreadable(report: RunsUsageReport, console: Console) -> None:
    if report.unreadable_runs:
        console.print(Text(f"{report.unreadable_runs} run file(s) unreadable"))


def _run_cells(row: RunTotalsRow) -> list[str]:
    usage = row.totals.usage
    return [
        row.run_id,
        row.pipeline,
        row.slice or UNREPORTED,
        row.status,
        f"{row.started_at:{STARTED_FORMAT}}",
        f"{row.recorded}/{row.llm_actions}",
        count_cell(usage.prompt),
        count_cell(usage.cached),
        count_cell(usage.completion),
        UNREPORTED if row.totals.cost_usd is None else format_usd(row.totals.cost_usd),
    ]


def _total_cells(report: RunsUsageReport) -> list[str]:
    totals: UsageTotals = report.totals
    recorded = sum(row.recorded for row in report.rows)
    cost = (
        UNREPORTED
        if totals.cost_usd is None
        else f"{format_usd(totals.cost_usd)} ({totals.priced} of {report.llm_actions} priced)"
    )
    return [
        "Total",
        "",
        "",
        "",
        "",
        f"{recorded}/{report.llm_actions}",
        count_cell(totals.usage.prompt),
        count_cell(totals.usage.cached),
        count_cell(totals.usage.completion),
        cost,
    ]
