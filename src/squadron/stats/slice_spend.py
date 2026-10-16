"""A slice's recorded spend: its pipeline runs plus its standalone review artifacts (D7).

Runs are matched on ``params["slice"]``. Review artifacts stamped with a ``runId`` are
already counted in their run, which ``reviews_usage_report`` excludes. Interactive work in
a Claude Code session is recorded nowhere, so this is a floor, not a total.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from squadron.core.usage import UsageRecord
from squadron.pipeline.state import RunScan
from squadron.stats.reviews_report import reviews_usage_report
from squadron.stats.usage_report import (
    LLM_ACTION_TYPES,
    UsageTotals,
    is_partial_loop,
    report_rows,
    usage_totals,
)


@dataclass(frozen=True)
class SliceSpend:
    totals: UsageTotals
    llm_actions: int  # the "of m" in "k of m priced": run LLM actions plus review artifacts
    run_count: int
    partial_loop_runs: int  # runs whose earlier loop rounds are not recorded


def slice_spend(index: int, scan: RunScan, reviews_dir: Path) -> SliceSpend:
    """Sum the usage records of slice ``index``'s runs and standalone reviews."""
    records: list[UsageRecord] = []
    llm_actions = 0
    run_count = 0
    partial = 0
    for state in scan.states:
        if str(state.params.get("slice")) != str(index):
            continue
        run_count += 1
        partial += is_partial_loop(state)
        for row in report_rows(state):
            llm_actions += row.action_type in LLM_ACTION_TYPES
            if row.record is not None:
                records.append(row.record)
    reviews = reviews_usage_report(reviews_dir, str(index))
    records.extend(row.record for row in reviews.rows)
    return SliceSpend(
        totals=usage_totals(records),
        llm_actions=llm_actions + len(reviews.rows),
        run_count=run_count,
        partial_loop_runs=partial,
    )
