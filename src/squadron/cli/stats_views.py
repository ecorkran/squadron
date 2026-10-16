"""Tables and JSON for ``sq stats`` (slice 175 D8, D9).

One serializer per report (``run_report_json`` / ``reviews_report_json``) produces the
row values; the tables format those same values, so ``--json`` and the table cannot
disagree. No aggregation happens here: totals come from the report.
"""

from __future__ import annotations

from datetime import timedelta

from rich.console import Console
from rich.text import Text

from squadron.cli.columns import Column, available_width, render_rows
from squadron.cli.run_views import print_lines
from squadron.core.usage import CostBasis, UsageRecord, format_usd
from squadron.models.aliases import get_all_aliases
from squadron.pipeline.run_liveness import format_duration
from squadron.stats.reviews_report import ReviewsUsageReport
from squadron.stats.usage_report import PARTIAL_LOOP_NOTE, RunUsageReport, UsageTotals

#: The cell for a value nobody reported (D9): never 0.
UNREPORTED = "—"
PARTIAL_MARK = "*"
PARTIAL_FOOTER = "* partial: an interrupted turn's spend is not recorded"
UNREADABLE = "unreadable"
#: The ``cost_tier`` that marks a provider cost as API-rate equivalent, not money (D3).
SUBSCRIPTION_TIER = "subscription"
API_RATE_EQUIV_LABEL = "api-rate equiv."
DEFAULT_EFFORT_LABEL = "default"
_BASIS_LABELS = {CostBasis.PROVIDER: "prov", CostBasis.ALIAS_PRICING: "alias"}

_USAGE_COLUMNS = [
    Column("Turns", shrinkable=False),
    Column("Prompt", shrinkable=False),
    Column("Cached", shrinkable=False),
    Column("Cache wr", shrinkable=False),
    Column("Compl.", shrinkable=False),
    Column("Cost", shrinkable=True),
]
_RUN_COLUMNS = [
    Column("Step", shrinkable=True),
    Column("Action", shrinkable=False),
    Column("Model / effort", shrinkable=True),
    *_USAGE_COLUMNS,
    Column("Time", shrinkable=False),
]
_REVIEW_COLUMNS = [
    Column("Date", shrinkable=False),
    Column("Slice", shrinkable=True),
    Column("Type", shrinkable=True),
    Column("Model", shrinkable=True),
    Column("Verdict", shrinkable=False),
    *_USAGE_COLUMNS,
]


def run_report_json(report: RunUsageReport) -> dict[str, object]:
    """The run report as JSON-ready data: the same rows and totals the table shows."""
    return {
        "run_id": report.run_id,
        "pipeline": report.pipeline,
        "slice": report.slice,
        "status": report.status,
        "started_at": report.started_at.isoformat(),
        "updated_at": report.updated_at.isoformat(),
        "rows": [
            {
                "step": row.step,
                "round": row.round,
                "action": row.action_type,
                "unreadable": row.unreadable,
                "usage": None if row.record is None else row.record.to_dict(),
            }
            for row in report.rows
        ],
        "totals": _totals_json(report.totals),
        "llm_actions": report.llm_actions,
        "unrecorded": report.unrecorded,
        "partial_loop": report.partial_loop,
    }


def reviews_report_json(report: ReviewsUsageReport) -> dict[str, object]:
    """The reviews report as JSON-ready data."""
    return {
        "reviews_dir": str(report.reviews_dir),
        "missing_dir": report.missing_dir,
        "rows": [
            {
                "file": row.path.name,
                "date": row.date,
                "slice": row.slice,
                "review_type": row.review_type,
                "model": row.model,
                "verdict": row.verdict,
                "usage": row.record.to_dict(),
            }
            for row in report.rows
        ],
        "totals": _totals_json(report.totals),
        "excluded_run_ids": report.excluded_run_ids,
        "skipped": report.skipped,
    }


def render_run_report(report: RunUsageReport, console: Console) -> None:
    elapsed = format_duration(report.updated_at - report.started_at)
    slice_part = f"  slice={report.slice}" if report.slice is not None else ""
    console.print(
        Text(f"Run {report.run_id}  {report.pipeline}{slice_part}  {report.status}  {elapsed}")
    )
    console.print()
    rows: list[list[Text]] = []
    for row in report.rows:
        record = row.record
        step = row.step if row.round is None else f"{row.step} r{row.round}"
        if record is not None and record.partial:
            step = f"{step}{PARTIAL_MARK}"
        if record is None:
            blank = UNREADABLE if row.unreadable else UNREPORTED
            cells = [step, row.action_type, blank, *[UNREPORTED] * len(_USAGE_COLUMNS), UNREPORTED]
        else:
            cells = [step, row.action_type, _model_cell(record), *_usage_cells(record), _time(record)]
        rows.append([Text(cell) for cell in cells])
    rows.append(_total_row(report.totals, report.llm_actions, leading=3, trailing=1))
    print_lines(render_rows(_RUN_COLUMNS, rows, available=available_width(console)), console)
    if report.unrecorded:
        console.print(Text(f"{report.unrecorded} LLM action(s) have no usage recorded."))
    if report.any_partial:
        console.print(Text(PARTIAL_FOOTER))
    if report.partial_loop:
        console.print(Text(PARTIAL_LOOP_NOTE))


def render_reviews_report(report: ReviewsUsageReport, console: Console) -> None:
    rows = [
        [
            Text(cell)
            for cell in (
                row.date or UNREPORTED,
                row.slice or UNREPORTED,
                row.review_type or UNREPORTED,
                row.model or UNREPORTED,
                row.verdict or UNREPORTED,
                *_usage_cells(row.record),
            )
        ]
        for row in report.rows
    ]
    rows.append(_total_row(report.totals, len(report.rows), leading=5, trailing=0))
    print_lines(render_rows(_REVIEW_COLUMNS, rows, available=available_width(console)), console)
    excluded = report.excluded_run_ids
    if excluded:
        console.print(
            Text(f"{len(excluded)} pipeline review(s) excluded; see sq stats run {excluded[0]}")
        )
    if report.skipped:
        console.print(Text(f"{report.skipped} artifact(s) skipped"))


def count_cell(count: int | None) -> str:
    """``412.8k``, ``3.12M``; ``—`` when not reported."""
    if count is None:
        return UNREPORTED
    if count < 1_000:
        return str(count)
    if count < 1_000_000:
        return f"{count / 1_000:.1f}k"
    return f"{count / 1_000_000:.2f}M"


def cost_cell(record: UsageRecord) -> str:
    """``$0.41 prov``; ``api-rate equiv.`` for a subscription alias's provider cost (D3)."""
    if record.cost_usd is None or record.cost_basis is None:
        return UNREPORTED
    label = _BASIS_LABELS[record.cost_basis]
    if record.cost_basis is CostBasis.PROVIDER and _is_subscription(record.alias):
        label = API_RATE_EQUIV_LABEL
    return f"{format_usd(record.cost_usd)} {label}"


def _is_subscription(alias: str | None) -> bool:
    if alias is None:
        return False
    entry = get_all_aliases().get(alias)
    return entry is not None and entry.get("cost_tier") == SUBSCRIPTION_TIER


def _usage_cells(record: UsageRecord) -> list[str]:
    usage = record.usage
    return [
        UNREPORTED if record.turns is None else str(record.turns),
        count_cell(usage.prompt),
        count_cell(usage.cached),
        count_cell(usage.cache_write),
        count_cell(usage.completion),
        cost_cell(record),
    ]


def _model_cell(record: UsageRecord) -> str:
    name = record.alias or record.model or UNREPORTED
    return f"{name} / {record.effort or DEFAULT_EFFORT_LABEL}"


def _time(record: UsageRecord) -> str:
    if record.duration_seconds is None:
        return UNREPORTED
    return format_duration(timedelta(seconds=record.duration_seconds))


def _total_row(totals: UsageTotals, actions: int, *, leading: int, trailing: int) -> list[Text]:
    usage = totals.usage
    cost = (
        UNREPORTED
        if totals.cost_usd is None
        else f"{format_usd(totals.cost_usd)} ({totals.priced} of {actions} priced)"
    )
    cells = [
        "Total",
        *[""] * (leading - 1),
        UNREPORTED if totals.turns is None else str(totals.turns),
        count_cell(usage.prompt),
        count_cell(usage.cached),
        count_cell(usage.cache_write),
        count_cell(usage.completion),
        cost,
        *[""] * trailing,
    ]
    return [Text(cell) for cell in cells]


def _totals_json(totals: UsageTotals) -> dict[str, object]:
    usage = totals.usage
    return {
        "turns": totals.turns,
        "tokens": {
            "prompt": usage.prompt,
            "cached": usage.cached,
            "cache_write": usage.cache_write,
            "completion": usage.completion,
            "reasoning": usage.reasoning,
        },
        "cost_usd": totals.cost_usd,
        "priced": totals.priced,
    }
