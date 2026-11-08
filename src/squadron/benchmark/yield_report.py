"""The fix-case yield report: counts per project, by reason, and separability (slice 422 D12).

A candidate is one ``(project, commit_sha)``, represented by its latest ``FixQualification`` by
``created_at`` whatever its environment digest or rule version; earlier records for the commit
are ignored. Counts group by enum value, never by message text.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from squadron.benchmark.separability import ASSUMPTION, SeparabilityAssessment, assess
from squadron.metrology.benchmark_models import (
    CandidateRejection,
    CaseSet,
    FixQualification,
    QualificationOutcome,
    TestRejection,
)

POOLED_LABEL = "pooled"
_NO_RECORDS = "no fix qualification records"


@dataclass(frozen=True)
class YieldRow:
    project: str
    candidates: int
    qualified: int
    rejected: Mapping[CandidateRejection, int]
    harness_errors: int
    #: One count per hidden-test verdict of the ``no_qualifying_hidden_test`` candidates.
    test_rejections: Mapping[TestRejection, int]
    separability: SeparabilityAssessment


@dataclass(frozen=True)
class CaseSetRef:
    name: str
    version: int


@dataclass(frozen=True)
class YieldReport:
    rows: tuple[YieldRow, ...]
    #: ``None`` when there are no records at all.
    pooled: YieldRow | None
    #: Every stored case set (name, version) holding a qualified case of these projects.
    case_sets: tuple[CaseSetRef, ...]


def _latest_per_candidate(records: Iterable[FixQualification]) -> list[FixQualification]:
    latest: dict[tuple[str, str], FixQualification] = {}
    for record in records:
        key = (record.project_id.value, record.commit_sha)
        held = latest.get(key)
        if held is None or record.created_at >= held.created_at:
            latest[key] = record
    return list(latest.values())


def _row(
    project: str,
    records: Sequence[FixQualification],
    planned_samples: int,
    target_difference: float,
) -> YieldRow:
    rejected = Counter(
        r.rejection for r in records if r.outcome is QualificationOutcome.REJECTED and r.rejection
    )
    test_rejections = Counter(
        verdict.rejection
        for r in records
        if r.rejection is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST
        for verdict in r.hidden_verdicts
        if verdict.rejection is not None
    )
    qualified = sum(1 for r in records if r.outcome is QualificationOutcome.QUALIFIED)
    return YieldRow(
        project=project,
        candidates=len(records),
        qualified=qualified,
        rejected=dict(rejected),
        harness_errors=sum(1 for r in records if r.outcome is QualificationOutcome.HARNESS_ERROR),
        test_rejections=dict(test_rejections),
        separability=assess(qualified, planned_samples, target_difference),
    )


def _pooled(rows: Sequence[YieldRow], planned_samples: int, target_difference: float) -> YieldRow:
    rejected: Counter[CandidateRejection] = Counter()
    test_rejections: Counter[TestRejection] = Counter()
    for row in rows:
        rejected.update(row.rejected)
        test_rejections.update(row.test_rejections)
    qualified = sum(row.qualified for row in rows)
    return YieldRow(
        project=POOLED_LABEL,
        candidates=sum(row.candidates for row in rows),
        qualified=qualified,
        rejected=dict(rejected),
        harness_errors=sum(row.harness_errors for row in rows),
        test_rejections=dict(test_rejections),
        separability=assess(qualified, planned_samples, target_difference),
    )


def build_yield(
    records: Iterable[FixQualification],
    case_sets: Iterable[CaseSet],
    planned_samples: int,
    target_difference: float,
) -> YieldReport:
    """Aggregate ``records`` into one row per project, a pooled row and the case sets involved."""
    latest = _latest_per_candidate(records)
    by_project: dict[str, list[FixQualification]] = {}
    for record in latest:
        by_project.setdefault(record.project_id.value, []).append(record)
    rows = tuple(
        _row(project, by_project[project], planned_samples, target_difference)
        for project in sorted(by_project)
    )
    qualified_ids = {r.case_id for r in latest if r.case_id is not None}
    involved = sorted(
        (CaseSetRef(s.name, s.version) for s in case_sets if qualified_ids & set(s.case_ids)),
        key=lambda ref: (ref.name, ref.version),
    )
    pooled = _pooled(rows, planned_samples, target_difference) if rows else None
    return YieldReport(rows=rows, pooled=pooled, case_sets=tuple(involved))


def _rejection_summary(row: YieldRow) -> str:
    """Reasons by descending count: ``name N`` with the test-level breakdown for the hidden-test one."""
    parts: list[tuple[int, str]] = []
    for reason, count in row.rejected.items():
        text = f"{reason.value} {count}"
        if reason is CandidateRejection.NO_QUALIFYING_HIDDEN_TEST and row.test_rejections:
            ordered = sorted(row.test_rejections.items(), key=lambda item: (-item[1], item[0].value))
            text += " (" + ", ".join(f"{test.value} {n}" for test, n in ordered) + ")"
        parts.append((count, text))
    if row.harness_errors:
        parts.append((row.harness_errors, f"harness_error {row.harness_errors}"))
    return ", ".join(text for _, text in sorted(parts, key=lambda part: (-part[0], part[1])))


def _separability_line(row: YieldRow) -> str:
    sep = row.separability
    head = (
        f"separability {row.project} (k={sep.samples_per_case} samples, "
        f"target {sep.target_difference:.2f}): "
    )
    if sep.no_qualified_cases:
        return f"{head}no qualified cases (need >= {sep.cases_needed} cases)"
    verdict = "enough cases" if sep.enough else f"not enough (need >= {sep.cases_needed} cases)"
    return f"{head}n={sep.qualified_cases} qualified -> MDD {sep.minimum_difference:.2f} -> {verdict}"


def render_text(report: YieldReport) -> str:
    """The table, one separability line per row, and the assumption sentence once."""
    if not report.rows:
        return _NO_RECORDS + "\n"
    rows = [*report.rows, *([report.pooled] if report.pooled else [])]
    width = max(len("project"), *(len(row.project) for row in rows))
    lines = [f"{'project':<{width}}  candidates  qualified  top rejections"]
    for row in rows:
        cells = f"{row.project:<{width}}  {row.candidates:<10}  {row.qualified:<9}  "
        lines.append((cells + _rejection_summary(row)).rstrip())
    lines.append("")
    lines.extend(_separability_line(row) for row in rows)
    lines.append(ASSUMPTION)
    return "\n".join(lines) + "\n"


def _row_json(row: YieldRow) -> dict[str, object]:
    sep = row.separability
    return {
        "project": row.project,
        "candidates": row.candidates,
        "qualified": row.qualified,
        "rejected": {reason.value: count for reason, count in row.rejected.items()},
        "harness_error": row.harness_errors,
        "test_rejections": {test.value: count for test, count in row.test_rejections.items()},
        "separability": {
            "qualified_cases": sep.qualified_cases,
            "samples_per_case": sep.samples_per_case,
            "target_difference": sep.target_difference,
            "minimum_difference": sep.minimum_difference,
            "enough": sep.enough,
            "cases_needed": sep.cases_needed,
            "no_qualified_cases": sep.no_qualified_cases,
        },
    }


def render_json(report: YieldReport) -> str:
    """The report as JSON, with the case sets (name and version) holding qualified cases."""
    payload = {
        "rows": [_row_json(row) for row in report.rows],
        "pooled": _row_json(report.pooled) if report.pooled else None,
        "case_sets": [{"name": ref.name, "version": ref.version} for ref in report.case_sets],
        "assumption": ASSUMPTION,
    }
    return json.dumps(payload, indent=2)
