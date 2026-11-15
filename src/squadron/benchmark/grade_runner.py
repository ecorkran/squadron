"""Run a grade plan: bound, lock, order, cap (slice 425 D8, D9).

The bound prints before anything is graded. References are graded before the replays that
read their baseline, a case whose reference failed is dropped with its replays, and replays
run sample-major then by config. One ``ReviewBudget`` is shared by every ``grade_one`` call,
and ``GradeCapReached`` ends the run with every record already written kept.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.bench_plan import BenchmarkRefusal
from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps, GradeTarget
from squadron.benchmark.grade_estimate import EstimateInputs, write_estimate
from squadron.benchmark.grade_one import GradeRecord, grade_one
from squadron.benchmark.grade_plan import (
    GradePlan,
    GradeRefusal,
    PlannedReference,
    PlannedReplayGrade,
    render_bound,
)
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.grade_models import GradeAbsence, GradeSubject
from squadron.metrology.grade_records import ReferenceGrade

_logger = logging.getLogger(__name__)

#: Beside the run lock of 424, but separate: grading can follow a partial run (D9).
GRADE_LOCK_SUFFIX = ".grade"

GradeFunction = Callable[..., GradeRecord]
LineSink = Callable[[str], None]


class GradeStatus(StrEnum):
    COMPLETE = "complete"
    CAP_REACHED = "cap_reached"


@dataclass
class GradeSummary:
    """What one grade invocation did."""

    status: GradeStatus
    spent_usd: float
    unpriced_reviews: int
    references_graded: int = 0
    replays_graded: int = 0
    passed: int = 0
    failed: int = 0
    absences: Counter[GradeAbsence] = field(default_factory=Counter[GradeAbsence])
    dropped_cases: tuple[str, ...] = ()
    #: Harness-absent grade records ``--retry-harness`` deleted before grading again.
    deleted_stale: int = 0
    estimate_note: str | None = None


def _result_text(record: GradeRecord) -> str:
    """``pass``, ``fail (…)`` or ``absent <kind>`` for one finished grade."""
    if record.absence is not None:
        return f"absent {record.absence.value}"
    result = record.result
    if result is None:
        raise ValueError("a grade has a result or an absence")
    if result.passed:
        return "pass"
    parts: list[str] = []
    if result.hidden_passed != result.hidden_total:
        parts.append(f"{result.hidden_total - result.hidden_passed} hidden")
    if result.regression_failure_count:
        parts.append(f"{result.regression_failure_count} regressions")
    return f"fail ({', '.join(parts)})"


def _is_failed_reference(reference: ReferenceGrade | None) -> bool:
    return reference is not None and (reference.result is None or not reference.result.passed)


def _tally(summary: GradeSummary, record: GradeRecord) -> None:
    if isinstance(record, ReferenceGrade):
        summary.references_graded += 1
    else:
        summary.replays_graded += 1
    if record.absence is not None:
        summary.absences[record.absence] += 1
    elif record.result is not None and record.result.passed:
        summary.passed += 1
    else:
        summary.failed += 1


def _replay_order(replay: PlannedReplayGrade) -> tuple[int, str, str]:
    """Sample-major, then config; the record id breaks any remaining tie."""
    return (replay.replay.sample, replay.replay.config.alias, replay.replay_id)


def _reference_target(reference: PlannedReference) -> GradeTarget:
    return GradeTarget(subject=GradeSubject.REFERENCE, environment_digest=reference.environment_digest)


def _replay_target(plan: GradePlan, replay: PlannedReplayGrade) -> GradeTarget:
    if replay.replay.environment is None or replay.replay.diff is None:
        raise ValueError("a planned replay has an environment and a stored diff")
    return GradeTarget(
        subject=GradeSubject.REPLAY,
        environment_digest=replay.replay.environment.identity_digest,
        replay_id=replay.replay_id,
        benchmark_id=plan.benchmark_id,
        diff_sha256=replay.replay.diff.sha256,
    )


def _case_ids(plan: GradePlan) -> list[str]:
    ids = {r.case.case_id for r in plan.references} | {r.case.case_id for r in plan.replays}
    return sorted(ids)


def _grade_case(
    case_id: str,
    plan: GradePlan,
    deps: GradeDeps,
    grade: GradeFunction,
    summary: GradeSummary,
    print_line: LineSink,
) -> bool:
    """Grade one case's references, then its replays. ``False`` when the case was dropped."""
    for reference in (r for r in plan.references if r.case.case_id == case_id):
        record = grade(reference.case, _reference_target(reference), deps)
        _tally(summary, record)
        print_line(f"reference {case_id} {_result_text(record)}")
    replays = sorted((r for r in plan.replays if r.case.case_id == case_id), key=_replay_order)
    for digest in sorted(
        {r.replay.environment.identity_digest for r in replays if r.replay.environment}
    ):
        stored = deps.store.get_reference_grade(case_id, deps.grader.digest, digest)
        if _is_failed_reference(stored):
            _logger.warning("case %s dropped: its reference did not grade cleanly", case_id)
            print_line(f"case {case_id} dropped: its reference did not grade cleanly")
            return False
    for planned in replays:
        record = grade(planned.case, _replay_target(plan, planned), deps)
        _tally(summary, record)
        print_line(
            f"{case_id} {planned.replay.config.alias} s{planned.replay.sample} {_result_text(record)}"
        )
    return True


def run_grading(
    plan: GradePlan,
    make_deps: Callable[[ReviewBudget], GradeDeps],
    *,
    lock_root: Path,
    process_runner: ProcessRunner,
    print_line: LineSink,
    grade: GradeFunction = grade_one,
    estimate: EstimateInputs | None = None,
) -> GradeSummary:
    """Grade everything *plan* names; the bound is printed first, and the lock is held throughout.

    Raises ``GradeRefusal`` while another invocation grades the same benchmark. A run that
    reaches its cap stops, keeps every record already written and returns ``cap_reached``.
    """
    try:
        lock = BenchmarkLock.acquire(
            lock_root, f"{plan.benchmark_id}{GRADE_LOCK_SUFFIX}", process_runner
        )
    except BenchmarkRefusal as exc:
        raise GradeRefusal(str(exc)) from exc
    with lock:
        print_line(render_bound(plan))
        budget = ReviewBudget(plan.run_cap_usd, plan.per_review_usd)
        deps = make_deps(budget)
        summary = GradeSummary(GradeStatus.COMPLETE, 0.0, 0)
        if plan.stale_record_ids:
            summary.deleted_stale = deps.store.delete_grades(plan.stale_record_ids)
            print_line(f"retry-harness: removed {summary.deleted_stale} harness-absent grade records")
        dropped: list[str] = []
        try:
            for case_id in _case_ids(plan):
                if not _grade_case(case_id, plan, deps, grade, summary, print_line):
                    dropped.append(case_id)
        except GradeCapReached as reached:
            print_line(f"stopped: {reached}")
            summary.status = GradeStatus.CAP_REACHED
        summary.dropped_cases = tuple(dropped)
        if estimate is not None:
            summary.estimate_note = write_estimate(estimate, deps, deps.clock())
            print_line(summary.estimate_note)
        summary.spent_usd = budget.spent
        summary.unpriced_reviews = budget.unpriced
        return summary
