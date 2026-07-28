"""Compare a fresh audit run to a stored baseline, relative to the floor.

Pure computation — no I/O, no agent, no store access — mirroring
``audit_variance.py``'s discipline, so the arithmetic is testable on
fixtures without spending a token.

The interpretation this module applies is deliberately weak, and that is
the point. A delta is judged against the measured floor's **observed
spread** (``max - min``), not against a derived confidence interval: at the
default n=3 the sample standard deviation is too coarse to support a
significance claim, and dressing it up as one would be exactly the
overclaiming initiative 320 exists to prevent.

Three states, never two:

- ``within_floor=True``  — the change is smaller than run-to-run noise
- ``within_floor=False`` — the change is at least as large as observed noise
- ``within_floor=None``  — **no floor was measured**, so no interpretation
  is available in either direction

The third is why this is not a boolean. A category with no floor is not
"not significant" and is certainly not "significant" — it is unmeasured,
and it reports as such rather than borrowing another category's number.
"""

from __future__ import annotations

from squadron.metrology.audit_models import (
    DELTA_DISCLAIMER,
    AuditCategory,
    AuditRun,
    DeltaCell,
    DeltaReport,
    FloorStat,
    ProjectBaseline,
)

__all__ = ["compute_delta", "is_within_floor"]


def is_within_floor(delta: int, floor: FloorStat | None) -> bool | None:
    """Judge a delta against a floor's observed spread.

    Returns ``None`` when no floor was measured — never ``False``, which
    would read as "measured, and significant" for a quantity that was never
    measured at all.
    """
    if floor is None:
        return None
    return abs(delta) < (floor.max - floor.min)


def compute_delta(baseline: ProjectBaseline, new_run: AuditRun) -> DeltaReport:
    """Compare ``new_run``'s finding counts to ``baseline``'s, per category.

    Per-category counts zero-fill in both directions: a category present in
    the baseline but absent from the new run counts 0 for the new run (and
    vice versa), matching ``audit_variance.reduce_noise_floor``'s precedent.
    Skipping such a category would hide the largest deltas there are — a
    class of issue appearing or disappearing entirely.
    """
    baseline_counts = {cell.category: cell.count for cell in baseline.cells}
    baseline_floors = {cell.category: cell.floor for cell in baseline.cells}

    new_counts: dict[AuditCategory, int] = {}
    for finding in new_run.findings:
        new_counts[finding.category] = new_counts.get(finding.category, 0) + 1

    cells: list[DeltaCell] = []
    for category in AuditCategory:
        baseline_count = baseline_counts.get(category, 0)
        new_count = new_counts.get(category, 0)
        # A category absent from both sides was never an issue class for
        # this project; emitting a 0 -> 0 row would bury the real ones.
        if category not in baseline_counts and category not in new_counts:
            continue
        delta = new_count - baseline_count
        floor = baseline_floors.get(category)
        cells.append(
            DeltaCell(
                category=category,
                baseline_count=baseline_count,
                new_count=new_count,
                delta=delta,
                floor=floor,
                within_floor=is_within_floor(delta, floor),
            )
        )

    new_total = len(new_run.findings)
    total_delta = new_total - baseline.total_findings

    return DeltaReport(
        project_id=baseline.project_id,
        baseline_commit_sha=baseline.commit_sha,
        new_commit_sha=new_run.commit_sha,
        baseline_total=baseline.total_findings,
        new_total=new_total,
        total_delta=total_delta,
        total_within_floor=is_within_floor(total_delta, baseline.total_floor),
        cells=cells,
        disclaimer=DELTA_DISCLAIMER,
    )
