"""Text and JSON renderings of the benchmark report (slice 425 D13, API Contracts).

The text follows D13's section order: objective grade, paired comparison, checks and snapshot
(the case-kind tables), review findings, cost and time, absences and exclusions, sample count.
"""

from __future__ import annotations

from squadron.benchmark.report_models import BenchmarkReport, CostRow, ReviewPair
from squadron.benchmark.report_rows import (
    NO_VALUE,
    config_text,
    fmt_counts,
    fmt_usd,
    identity_label,
    name_width,
)
from squadron.metrology.grade_records import SampleSizeEstimate

DIGEST_CHARS = 8


def _header(report: BenchmarkReport) -> list[str]:
    excluded = ", ".join(f"{reason} {n}" for reason, n in sorted(report.exclusions.items()))
    cases = (
        f"cases: {report.cases_in_set} in set · {report.cases_compared} compared · "
        f"{report.dropped_cases} dropped"
    )
    if excluded:
        cases += f" · not compared: {excluded}"
    lines = [
        f"benchmark {report.benchmark_id}  set {report.case_set} v{report.case_set_version}  "
        f"grader {report.grader_digest[:DIGEST_CHARS]} ({report.reviewer_alias}, "
        f"floor runs {report.review_floor_runs})",
        cases,
    ]
    if report.older_identity_grades:
        lines.append(f"{report.older_identity_grades} grades under older grader identities not shown")
    lines += [f"warning: {warning}" for warning in report.warnings]
    return lines


def _findings(report: BenchmarkReport) -> list[str]:
    lines = ["", f"review findings ({report.review_flag})"]
    width = name_width([row.config for row in report.findings])
    for row in report.findings:
        severities = ", ".join(
            f"{sev} {mean:.2f}" for sev, mean in sorted(row.mean_by_severity.items())
        )
        total = NO_VALUE if row.mean_total is None else f"{row.mean_total:.2f}"
        lines.append(
            f"  {config_text(row.config):<{width}}  per replay: {total} total"
            f"{f' ({severities})' if severities else ''}  over {row.replays} replays"
        )
    for pair in report.review_pairs:
        lines.append(_review_pair_text(pair))
    return lines


def _review_pair_text(pair: ReviewPair) -> str:
    beyond = pair.a_more + pair.b_more
    return (
        f"  {pair.label_a} vs {pair.label_b}: beyond floor on {beyond} cases "
        f"({pair.label_a} more {pair.a_more}, {pair.label_b} more {pair.b_more}), "
        f"within {pair.within}, no floor {pair.no_floor}"
    )


def _cost(report: BenchmarkReport) -> list[str]:
    lines = [
        "",
        "cost / turns / time               producer $ (mean/total)  grading $ (mean/total)  "
        "turns  wall s (mean/total)",
    ]
    width = name_width([row.config for row in report.costs])
    for row in report.costs:
        lines.append(_cost_text(row, width))
    return lines


def _cost_text(row: CostRow, width: int) -> str:
    producer = f"{fmt_usd(row.producer_cost_mean)}/{fmt_usd(row.producer_cost_total)}"
    grading = f"{fmt_usd(row.grading_cost_mean)}/{fmt_usd(row.grading_cost_total)}"
    turns = NO_VALUE if row.turns_mean is None else f"{row.turns_mean:.1f}"
    wall = NO_VALUE if row.wall_seconds_mean is None else f"{row.wall_seconds_mean:.0f}"
    unpriced = ""
    if row.unpriced_producer or row.unpriced_grading:
        unpriced = f"  unpriced: {row.unpriced_producer} producer, {row.unpriced_grading} grading"
    return (
        f"  {config_text(row.config):<{width}}  {producer}  {grading}  {turns}  "
        f"{wall}/{row.wall_seconds_total:.0f}{unpriced}"
    )


def _absences(report: BenchmarkReport) -> list[str]:
    lines = ["", "absences and exclusions"]
    by_class: dict[str, dict[str, int]] = {}
    for item in report.absences:
        by_class.setdefault(item.absence_class, {})[item.kind] = item.count
    for absence_class, kinds in sorted(by_class.items()):
        lines.append(f"  {absence_class}: {fmt_counts(kinds)}")
    if not by_class:
        lines.append(f"  absences: {NO_VALUE}")
    lines.append(f"  cases dropped: {report.dropped_cases}")
    lines.append(f"  cases not compared: {fmt_counts(report.exclusions)}")
    if report.unstamped_replays:
        lines.append(
            f"  failed replays with no effort stamp (no row): {fmt_counts(report.unstamped_replays)}"
        )
    lines.append(f"  replays scanned under an older leak-rule version: {report.stale_leak_scans}")
    return lines


def _sample_count(report: BenchmarkReport) -> list[str]:
    estimate = report.estimate
    if estimate is None:
        return []
    labels = {row.config.identity: row.config.label for row in report.costs}
    return ["", *_estimate_lines(estimate, labels)]


def _estimate_lines(estimate: SampleSizeEstimate, labels: dict[str, str]) -> list[str]:
    head = f"sample count (measured, k={estimate.samples}, n={estimate.n_cases}):"
    lines: list[str] = []
    for pair in estimate.pairs:
        a = labels.get(pair.config_a) or identity_label(pair.config_a)
        b = labels.get(pair.config_b) or identity_label(pair.config_b)
        needed = ", ".join(f"{item.cases} at k={item.samples}" for item in pair.cases_needed)
        lines.append(
            f"{head} {a} vs {b}  MDD {pair.mdd_now:.2f} at n={estimate.n_cases} · need {needed}"
        )
    return lines


def render_text(report: BenchmarkReport) -> str:
    lines = _header(report)
    for table in report.tables:
        lines += ["", *table.lines]
    lines += _findings(report)
    lines += _cost(report)
    lines += _absences(report)
    lines += _sample_count(report)
    return "\n".join(lines)


def render_json(report: BenchmarkReport) -> str:
    """The ``BenchmarkReport`` model as JSON; it loads back into the model."""
    return report.model_dump_json(indent=2)
