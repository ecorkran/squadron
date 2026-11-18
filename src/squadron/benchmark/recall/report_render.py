"""Text and JSON rendering of the recall report (slice 430 API Contracts).

The text layout follows the design's ``report`` example: header, one table row per recipe
and stage identity, stage efforts, paired lines and a footer. Recall prints as one number,
or ``low–high`` when anything is undecided. An unrecorded ``effort_sent`` prints as "not
recorded", never as the alias's configured effort.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime

from squadron.benchmark.recall.scoring import RowOutputs
from squadron.benchmark.recall.scoring_metrics import Bounds, RowMetrics
from squadron.benchmark.recall.scoring_paired import PairedLine
from squadron.core.models import Effort
from squadron.metrology.grade_models import PairVerdict
from squadron.metrology.recall_case_models import RecallCaseSet

NOT_RECORDED = "not recorded"
RANGE_DASH = "–"
MINUS = "−"
_COLUMNS = (
    "Recipe", "Cases", "Runs", "Bug-hits", "Recall", "Bugs found", "Runs with a hit", "Adjacent",
    "Undecided", "Findings/run", "Matched nothing", "Real share (passes; graded, checked)",
    "Cost/run (basis)", "Leak scan",
)  # fmt: skip
_VERDICT_TEXT = {
    PairVerdict.NOT_DISTINGUISHABLE: "not distinguishable",
    PairVerdict.TOO_FEW_CASES: "too few cases",
}


@dataclass(frozen=True)
class ReportRow:
    outputs: RowOutputs
    metrics: RowMetrics


@dataclass(frozen=True)
class ReportData:
    case_set: RecallCaseSet
    known_bugs: int
    run_indexes: list[int]
    rows: list[ReportRow]
    paired: list[PairedLine]

    @property
    def newest_entry(self) -> datetime | None:
        dates = [e.created for row in self.rows for pair in row.outputs.pairs for e in pair.entries]
        return max(dates) if dates else None


def number(value: float) -> str:
    """An integral value without decimals, else one decimal (pool means are fractional)."""
    return str(int(value)) if float(value).is_integer() else f"{value:.1f}"


def bounds_text(bounds: Bounds) -> str:
    if bounds.exact:
        return number(bounds.low)
    return f"{number(bounds.low)}{RANGE_DASH}{number(bounds.high)}"


def percent_text(bounds: Bounds) -> str:
    low, high = round(bounds.low * 100), round(bounds.high * 100)
    return f"{low}%" if bounds.exact else f"{low}{RANGE_DASH}{high}%"


def render_text(data: ReportData) -> str:
    runs = data.run_indexes
    lines = [
        f"Case set {data.case_set.name} v{data.case_set.version}: {len(data.case_set.case_ids)} cases, "
        f"{data.known_bugs} known bugs, runs {runs[0]}..{runs[-1]}",
        "Hit rule: location gate + labels; recall is shown as low–high when anything is undecided.",
        "",
        "| " + " | ".join(_COLUMNS) + " |",
        "|" + "---|" * len(_COLUMNS),
    ]
    lines += [_table_row(row) for row in data.rows]
    lines += [_stage_line(row.outputs) for row in data.rows]
    lines += [_paired_text(line) for line in data.paired]
    lines.append(_footer(data))
    return "\n".join(lines)


def _table_row(row: ReportRow) -> str:
    m = row.metrics
    cells = [
        row.outputs.label,
        number(m.cases),
        number(m.runs),
        f"{bounds_text(m.bug_hits)}/{m.bug_slots}",
        percent_text(m.recall),
        f"{bounds_text(m.bugs_found)}/{m.bugs_total}",
        f"{bounds_text(m.runs_with_hit)}/{m.pairs}",
        number(m.adjacent),
        number(m.undecided),
        f"{m.findings_per_run:.1f}",
        number(m.matched_nothing),
        _real_share(m),
        _cost(m),
        _leaks(m.leaks),
    ]
    return "| " + " | ".join(cells) + " |"


def _real_share(m: RowMetrics) -> str:
    share = m.real_share
    if share is None:
        return "ungraded"
    checked = number(m.person_checked)
    if m.person_checked:
        checked += f": {number(m.person_agree)} agree"
    return f"{round(share * 100)}% ({', '.join(m.passes)}; {number(m.graded)}, {checked})"


def _cost(m: RowMetrics) -> str:
    bases = ", ".join(m.cost_bases)
    if m.cost_per_run is None:
        return f"not recorded ({bases})" if bases else NOT_RECORDED
    return f"${m.cost_per_run:.2f} {bases}".rstrip()


def _leaks(leaks: Counter[str]) -> str:
    return (
        ", ".join(f"{count} {verdict.replace('_', ' ')}" for verdict, count in sorted(leaks.items()))
        or "-"
    )


def _stage_line(row: RowOutputs) -> str:
    """Each reviewer's stages with the effort actually sent."""
    if not row.pairs:
        return f"Stages {row.label}: none stored"
    parts: list[str] = []
    for reviewer in row.pairs[0].reviewers:
        efforts = [f"{e.alias} effort sent {_effort_text(e.effort_sent)}" for e in reviewer.entries]
        parts.append(" > ".join(efforts))
    return f"Stages {row.label}: " + "; ".join(parts)


def _effort_text(effort: Effort | None) -> str:
    return NOT_RECORDED if effort is None else effort.value


def _paired_text(line: PairedLine) -> str:
    c = line.comparison
    head = (
        f"Paired ({line.metric.value}, {c.n} usable cases, {line.left_out_undecided} left out as "
        f"undecided): {line.label_a} {MINUS} {line.label_b}"
    )
    if c.low is None or c.high is None:
        return f"{head}  {_VERDICT_TEXT[PairVerdict.TOO_FEW_CASES]}"
    verdict = _VERDICT_TEXT.get(c.verdict) or (
        f"{line.label_a} ahead" if c.verdict is PairVerdict.A_AHEAD else f"{line.label_b} ahead"
    )
    return f"{head}  {c.mean:+.2f} [{c.low:+.2f}, {c.high:+.2f}]  {verdict}"


def _footer(data: ReportData) -> str:
    dropped: Counter[str] = Counter()
    left_out: list[str] = []
    for row in data.rows:
        dropped.update(row.outputs.dropped)
        left_out += [f"{row.outputs.label}: {case} run {run}" for case, run in row.outputs.left_out]
    harness = dropped.pop("harness", 0)
    leak = sum(dropped.values())
    by_verdict = ", ".join(f"{reason.split(':', 1)[1]} {n}" for reason, n in sorted(dropped.items()))
    other = sum(row.metrics.other_set_entries for row in data.rows)
    return (
        f"Dropped (harness): {harness}.  Dropped (leak): {leak}{f' ({by_verdict})' if leak else ''}.  "
        f"Left out (incomplete stages): {', '.join(left_out) or 'none'}.  "
        f"Entries from another set version: {other}."
    )
