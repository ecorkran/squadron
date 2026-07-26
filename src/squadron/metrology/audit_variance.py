"""Reduce a variance series to a measured noise floor.

Pure reduction — no I/O, no agent, no store access — so the expensive
I/O-bound step (running audits) and the cheap arithmetic are independently
testable. A floor can be recomputed from persisted runs at zero token cost,
including after more runs are added to a series.

What this module mostly does is **refuse**. A noise floor is a claim about
the audit's run-to-run spread on *unchanged code under one instrument*, so
a series that does not meet that precondition is rejected rather than
averaged into a number that looks authoritative and means nothing. The
refusals are the feature.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime

from squadron.metrology.errors import MetrologyError
from squadron.metrology.models import (
    AuditCategory,
    AuditNoiseFloor,
    AuditRun,
    FloorStat,
)

#: A spread needs at least two points. One run is a measurement, not a
#: variance measurement, and emitting a zero-width floor from it would
#: understate the error bar — the exact overclaiming this slice exists to
#: prevent.
MIN_USABLE_RUNS = 2


class AuditVarianceError(MetrologyError):
    """A run series cannot be reduced to a noise floor.

    Raised for a series spanning differing commits or instruments, or one
    with too few usable runs. Never a silent fallback: a floor that does not
    describe what it claims to describe is worse than no floor, because 324
    reads it as the error bar on every later delta.
    """


def _require_uniform(runs: list[AuditRun], field: str, label: str) -> str:
    """Return the shared value of ``field``, or raise naming the mismatch."""
    values = {getattr(run, field) for run in runs}
    if len(values) > 1:
        shown = ", ".join(sorted(str(value)[:12] for value in values))
        raise AuditVarianceError(
            f"Refusing to reduce a variance series spanning differing {label} "
            f"values ({shown}). A floor measured across a change in {label} is "
            "not a floor — reduce each group separately."
        )
    return str(values.pop())


def _stat(counts: list[int]) -> FloorStat:
    """Summarize one quantity's spread across the series.

    ``stdev`` is the *sample* standard deviation. At the default n=3 it is a
    coarse figure and every surface that presents it says so — it bounds
    interpretation of a delta, it does not support a significance claim.
    """
    return FloorStat(
        min=min(counts),
        max=max(counts),
        mean=statistics.fmean(counts),
        stddev=statistics.stdev(counts),
    )


def reduce_noise_floor(runs: list[AuditRun]) -> AuditNoiseFloor:
    """Reduce a series of audit runs to one ``AuditNoiseFloor``.

    The series must share ``(project_id, commit_sha, audit_prompt_hash)`` —
    unchanged code, one project, one instrument. Anything else raises.

    ``n_runs`` records the number of runs **actually** reduced, which may be
    fewer than a campaign requested when runs failed. That is honest by
    construction: failed runs persist nothing, so they cannot be counted
    here, and the floor states the evidence it really rests on.

    Raises:
        AuditVarianceError: fewer than two runs, or a non-uniform series.
    """
    if len(runs) < MIN_USABLE_RUNS:
        raise AuditVarianceError(
            f"Refusing to reduce a noise floor from {len(runs)} run(s): at least "
            f"{MIN_USABLE_RUNS} usable runs are required for a spread. Runs that "
            "failed persist nothing, so a short series means the campaign lost runs."
        )

    project_values = {run.project_id.value for run in runs}
    if len(project_values) > 1:
        raise AuditVarianceError(
            f"Refusing to reduce a variance series spanning multiple projects "
            f"({', '.join(sorted(project_values))}). The floor is per-project."
        )

    commit_sha = _require_uniform(runs, "commit_sha", "commit_sha")
    prompt_hash = _require_uniform(runs, "audit_prompt_hash", "audit_prompt_hash")

    totals = [len(run.findings) for run in runs]

    # Per-category counts zero-fill across the whole series: a category
    # absent from one run counts as 0 for that run, not as missing. Dropping
    # it instead would compute the spread over a smaller denominator and
    # understate the very variance being measured.
    per_category: dict[AuditCategory, FloorStat] = {}
    for category in AuditCategory:
        counts = [sum(1 for f in run.findings if f.category is category) for run in runs]
        if not any(counts):
            continue
        per_category[category] = _stat(counts)

    return AuditNoiseFloor(
        project_id=runs[0].project_id,
        commit_sha=commit_sha,
        audit_prompt_hash=prompt_hash,
        n_runs=len(runs),
        total=_stat(totals),
        per_category=per_category,
        measured_at=datetime.now(UTC),
    )
