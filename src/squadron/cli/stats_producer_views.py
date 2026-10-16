"""The table for ``sq stats producers`` (slice 176 D8).

Formats the values ``ProducerReport.to_json_dict()`` serializes. Every row carries its n;
a row below the evidence floor says so instead of showing a cost ratio.
"""

from __future__ import annotations

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.cli.run_views import print_lines
from squadron.cli.stats_views import UNREADABLE_RUNS_TEXT, UNREPORTED
from squadron.core.usage import format_usd
from squadron.stats.producer_report import FirstRound, PhaseSection, ProducerReport, ProducerRow
from squadron.stats.usage_report import PARTIAL_LOOP_NOTE

NO_PHASE_RUNS = "no phase runs"
BELOW_FLOOR = "below floor"
OBSERVATIONAL_FOOTER = (
    "Observational: configs saw different slices, so slice difficulty is a confound. "
    "Prompt-template revisions are pooled. Runs from before slice 175 have no cost, and "
    "runs from before slice 176 have no per-round data."
)

_COLUMNS = [
    Column("Model / effort", shrinkable=True),
    Column("Profile", shrinkable=True),
    Column("Reviewer", shrinkable=True),
    Column("n", shrinkable=False),
    Column("First PASS/CONC/FAIL", shrinkable=False),
    Column("Rev. rounds", shrinkable=False),
    Column("Accepted", shrinkable=False),
    Column("Failed", shrinkable=False),
    Column("$/accepted", shrinkable=True),
]


def render_producers_report(report: ProducerReport, console: Console) -> None:
    if not report.phases:
        console.print(Text(NO_PHASE_RUNS))
        return
    for section in report.phases:
        _render_section(section, report.min_n, console)
    console.print(Text(OBSERVATIONAL_FOOTER))
    for line in _count_footers(report):
        console.print(Text(line))


def _render_section(section: PhaseSection, min_n: int, console: Console) -> None:
    console.print(Text(f"Phase {section.phase}   min n {min_n}   pipeline runs {section.runs}"))
    console.print()
    rows = [[Text(cell) for cell in _cells(row)] for row in section.rows]
    print_lines(render_rows(_COLUMNS, rows, available=available_width(console)), console)
    console.print()


def _cells(row: ProducerRow) -> list[str]:
    return [
        f"{row.alias or row.model or UNREPORTED} / {row.effort or UNREPORTED}",
        row.profile or UNREPORTED,
        row.reviewer or UNREPORTED,
        str(row.n),
        _first_round(row),
        f"{row.median_revise_rounds:g}",
        f"{row.accepted}/{row.n}",
        f"{row.failed}/{row.n}",
        _cost(row),
    ]


def _first_round(row: ProducerRow) -> str:
    counts = row.first_round
    cell = " / ".join(
        str(counts[bucket.value]) for bucket in (FirstRound.PASS, FirstRound.CONCERNS, FirstRound.FAIL)
    )
    none = counts[FirstRound.NONE.value]
    return f"{cell} (+{none} none)" if none else cell


def _cost(row: ProducerRow) -> str:
    if row.below_floor:
        return BELOW_FLOOR
    if row.cost_per_accepted is None:
        return UNREPORTED
    return f"{format_usd(row.cost_per_accepted)} ({row.priced} of {row.llm_actions} priced)"


def _count_footers(report: ProducerReport) -> list[str]:
    excluded = report.excluded
    candidates = [
        (excluded.orphan_loops, "loop(s) with no phase step before them"),
        (excluded.each_steps, "each step(s): phase work inside them is not counted"),
        (excluded.partial_loop_runs, f"run(s): {PARTIAL_LOOP_NOTE}"),
        (excluded.without_dispatch, "phase step(s) without a dispatch"),
        (excluded.paused, "phase step(s) paused"),
        (report.unreadable_runs, UNREADABLE_RUNS_TEXT),
        (report.rounds_unrecorded, "run(s) with loop rounds that were not recorded"),
        (report.unpriced_runs, "run(s) with no recorded cost"),
    ]
    return [f"{count} {text}" for count, text in candidates if count]
