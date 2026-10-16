"""The ``sq replay report`` tables (slice 177 D7).

Formats the values ``ReplayReport`` carries; every figure is computed in the report core, so
the table and ``--json`` cannot disagree.
"""

from __future__ import annotations

from datetime import timedelta

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.cli.run_views import print_lines
from squadron.cli.stats_views import UNREPORTED
from squadron.core.usage import format_usd
from squadron.pipeline.run_liveness import format_duration
from squadron.replay.report_models import ConfigRow, ReplayReport, ReplayTable

NO_REPLAYS = "No replays recorded; run `sq replay run` first."
BELOW_FLOOR = "below floor"
_COLUMNS = [
    Column("config", shrinkable=True),
    Column("n", shrinkable=False),
    Column("failed", shrinkable=False),
    Column("accepted", shrinkable=False),
    Column("rounds", shrinkable=False),
    Column("cost (priced)", shrinkable=True),
    Column("time", shrinkable=False),
    Column("BT", shrinkable=False),
    Column("W-L-T", shrinkable=False),
    Column("pairs", shrinkable=True),
    Column("", shrinkable=False),
]


def render_replay_report(report: ReplayReport, console: Console) -> None:
    if not report.tables:
        console.print(Text(NO_REPLAYS))
        return
    for table in report.tables:
        _render_table(table, console)


def _render_table(table: ReplayTable, console: Console) -> None:
    judge = (
        "none yet"
        if table.judge is None
        else f"{table.judge.alias} (prompt {table.judge.prompt_hash[:6]})"
    )
    console.print(
        Text(
            f"Producer replay - {table.phase.value}   reviewer: {table.reviewer.alias}   judge: {judge}"
        )
    )
    rows = [[Text(cell) for cell in _cells(row)] for row in table.rows]
    print_lines(render_rows(_COLUMNS, rows, available=available_width(console)), console)
    for row in table.rows:
        if row.strength is None and row.strength_reason is not None:
            console.print(Text(f"{row.label}: no strength - {row.strength_reason}"))
    for line in _footer(table):
        console.print(Text(line))
    console.print()


def _cells(row: ConfigRow) -> list[str]:
    is_original = row.config is None
    return [
        row.label,
        UNREPORTED if is_original else str(row.n),
        UNREPORTED if is_original else f"{row.failed}/{row.n}",
        UNREPORTED if is_original or not row.accepted_of else f"{row.accepted}/{row.accepted_of}",
        UNREPORTED if row.median_rounds is None else f"{row.median_rounds:g}",
        _cost(row),
        UNREPORTED
        if row.median_wall_seconds is None
        else format_duration(timedelta(seconds=row.median_wall_seconds)),
        UNREPORTED if row.strength is None else f"{row.strength:.2f}",
        f"{row.wins}-{row.losses}-{row.ties}",
        _pairs(row),
        BELOW_FLOOR if row.below_floor else "",
    ]


def _cost(row: ConfigRow) -> str:
    if row.median_cost_usd is None:
        return UNREPORTED
    return f"{format_usd(row.median_cost_usd)} ({row.priced} of {row.llm_actions} priced)"


def _pairs(row: ConfigRow) -> str:
    notes = [f"{row.invalid} invalid"] if row.invalid else []
    notes += [f"{row.inconsistent} inconsistent"] if row.inconsistent else []
    return f"{row.pairs} ({', '.join(notes)})" if notes else str(row.pairs)


def _footer(table: ReplayTable) -> list[str]:
    consistency = (
        "no judged pairs"
        if not table.verdict_pairs
        else f"position consistency {100 * table.consistent_pairs // table.verdict_pairs}% "
        f"({table.consistent_pairs} of {table.verdict_pairs})"
    )
    slices = ", ".join(str(index) for index in table.slices)
    identities = "; ".join(table.prompt_identities) or "none recorded"
    lines = [f"slices: {slices} · {consistency} · prompt identity: {identities}"]
    if table.self_preference and table.judge is not None:
        lines.append(f"warning: the judge's model ({table.judge.model}) is also a contestant's model")
    if not table.strengths_converged:
        lines.append("note: the Bradley-Terry fit stopped at its iteration cap before converging")
    if table.strength_components > 1:
        lines.append(
            f"note: the comparisons form {table.strength_components} disconnected groups, "
            "each fitted separately; strengths are comparable only within a group"
        )
    return lines
