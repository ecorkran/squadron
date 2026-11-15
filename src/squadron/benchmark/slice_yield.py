"""Slice-case rows of the yield report (slice 426 Technical Scope).

One row per project: slice candidates, how many qualified, and one count per rejection value
and per ``harness_error``. A candidate is one ``(project, slice index)``, represented by its
latest ``SliceQualification`` by ``created_at`` whatever its landing, environment or rule
version. Counts group by enum value, never by message text.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.slice_case_models import SliceCandidateRejection, SliceQualification

HEADING = "slice cases"


@dataclass(frozen=True)
class SliceYieldRow:
    project: str
    candidates: int
    qualified: int
    rejected: Mapping[SliceCandidateRejection, int]
    harness_errors: int


def build_slice_yield(records: Iterable[SliceQualification]) -> tuple[SliceYieldRow, ...]:
    """One row per project that has a slice qualification, sorted by project."""
    latest: dict[tuple[str, int], SliceQualification] = {}
    for record in records:
        key = (record.project_id.value, record.slice_index)
        held = latest.get(key)
        if held is None or record.created_at >= held.created_at:
            latest[key] = record
    by_project: dict[str, list[SliceQualification]] = {}
    for record in latest.values():
        by_project.setdefault(record.project_id.value, []).append(record)
    return tuple(_row(project, by_project[project]) for project in sorted(by_project))


def _row(project: str, records: Sequence[SliceQualification]) -> SliceYieldRow:
    rejected = Counter(
        r.rejection for r in records if r.outcome is QualificationOutcome.REJECTED and r.rejection
    )
    return SliceYieldRow(
        project=project,
        candidates=len(records),
        qualified=sum(1 for r in records if r.outcome is QualificationOutcome.QUALIFIED),
        rejected=dict(rejected),
        harness_errors=sum(1 for r in records if r.outcome is QualificationOutcome.HARNESS_ERROR),
    )


def _rejection_summary(row: SliceYieldRow) -> str:
    """Reasons by descending count, ``harness_error`` among them."""
    parts = [(count, f"{reason.value} {count}") for reason, count in row.rejected.items()]
    if row.harness_errors:
        parts.append((row.harness_errors, f"harness_error {row.harness_errors}"))
    return ", ".join(text for _, text in sorted(parts, key=lambda part: (-part[0], part[1])))


def render_slice_text(rows: Sequence[SliceYieldRow]) -> str:
    """The slice-case table; empty text for no rows."""
    if not rows:
        return ""
    width = max(len(HEADING), *(len(row.project) for row in rows))
    lines = [f"{HEADING:<{width}}  candidates  qualified  top rejections"]
    for row in rows:
        cells = f"{row.project:<{width}}  {row.candidates:<10}  {row.qualified:<9}  "
        lines.append((cells + _rejection_summary(row)).rstrip())
    return "\n".join(lines) + "\n"


def slice_rows_json(rows: Sequence[SliceYieldRow]) -> list[dict[str, object]]:
    return [
        {
            "project": row.project,
            "candidates": row.candidates,
            "qualified": row.qualified,
            "rejected": {reason.value: count for reason, count in row.rejected.items()},
            "harness_error": row.harness_errors,
        }
        for row in rows
    ]
