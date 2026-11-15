"""Grade one subject, a reference or a replay, in a fresh sandbox (slice 425 D1, D16).

``grade_one`` opens the sandbox, runs the grade steps in the fixed order of D1, and writes one
record. A step that cannot continue raises ``GradeAbsent`` and the record carries the absence
and its class; nothing falls back to a partial grade. ``GradeCapReached`` and
``MissingReferenceGrade`` are not absences: they propagate and no record is written.
"""

from __future__ import annotations

from datetime import datetime

from squadron.benchmark.adapter import EnvironmentResolutionError
from squadron.benchmark.grade_checks import (
    count_added_suppressions,
    restore_tests,
    run_hidden,
    run_producer_new,
    run_regression,
    take_snapshot,
)
from squadron.benchmark.grade_deps import (
    GradeAbsent,
    GradeDeps,
    GradeTarget,
    absent,
)
from squadron.benchmark.grade_prepare import prepare_tree
from squadron.benchmark.grade_result import (
    build_result,
    failed_reference_detail,
    implementation_record,
    reference_record,
)
from squadron.benchmark.grade_run import GradeRun
from squadron.benchmark.tree_reader import TreeReadError
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.grade_models import (
    GRADE_ABSENCE_CLASS,
    GradeAbsence,
    GradeSubject,
)
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade
from squadron.replay.history_free_sandbox import SandboxError

GradeRecord = ReferenceGrade | ImplementationGrade


def _absent_record(
    case: BenchmarkCase,
    target: GradeTarget,
    deps: GradeDeps,
    failure: GradeAbsent,
    *,
    environment_digest: str | None,
    cost_usd: float | None,
    began: datetime,
    run: GradeRun | None = None,
) -> GradeRecord:
    now = deps.clock()
    wall_seconds = (now - began).total_seconds()
    if target.subject is GradeSubject.REFERENCE:
        # What the reference had measured before it stopped is kept beside the absence.
        return ReferenceGrade(
            case_id=case.case_id,
            grader=deps.grader,
            environment_digest=target.environment_digest,
            result=None,
            absence=failure.absence,
            detail=failure.detail,
            baseline_nodes=None if run is None else run.baseline_nodes_sha,
            baseline_snapshot=None if run is None else run.baseline_snapshot,
            baseline_lint_total=None if run is None else run.baseline_lint_total,
            baseline_type_total=None if run is None else run.baseline_type_total,
            review_floor=None if run is None else run.review_floor,
            grading_cost_usd=cost_usd,
            wall_seconds=wall_seconds,
            created_at=now,
        )
    if target.replay_id is None or target.benchmark_id is None:
        raise ValueError("a replay target carries its replay id and benchmark id")
    return ImplementationGrade(
        replay_id=target.replay_id,
        benchmark_id=target.benchmark_id,
        case_id=case.case_id,
        grader=deps.grader,
        environment_digest=environment_digest,
        result=None,
        absence=failure.absence,
        absence_class=GRADE_ABSENCE_CLASS[failure.absence],
        detail=failure.detail,
        grading_cost_usd=cost_usd,
        wall_seconds=wall_seconds,
        created_at=now,
    )


def _write(deps: GradeDeps, record: GradeRecord) -> GradeRecord:
    if isinstance(record, ReferenceGrade):
        deps.store.write_reference_grade(record)
    else:
        deps.store.write_grade(record)
    return record


def _as_absence(problem: GradeAbsent | TreeReadError) -> GradeAbsent:
    """A tree-read failure is a commit unreadable in the user's checkout, a harness absence."""
    if isinstance(problem, GradeAbsent):
        return problem
    return absent(GradeAbsence.REFERENCE_UNREADABLE, problem.detail)


def _grade_steps(run: GradeRun) -> None:
    """The steps of D1, in order; each raises ``GradeAbsent`` when it cannot continue."""
    prepare_tree(run)
    run_producer_new(run)
    take_snapshot(run)
    restore_tests(run)
    run_regression(run)
    run_hidden(run)
    count_added_suppressions(run)
    if run.target.subject is GradeSubject.REFERENCE:
        detail = failed_reference_detail(build_result(run))
        if detail is not None:
            raise absent(GradeAbsence.REFERENCE_FAILED_GRADE, detail)


def grade_one(case: BenchmarkCase, target: GradeTarget, deps: GradeDeps) -> GradeRecord:
    """Grade *target* for *case* and write its record, which is also returned."""
    began = deps.clock()
    digest: str | None = None
    try:
        with deps.sandbox_factory(case) as sandbox:
            digest = sandbox.identity.identity_digest
            run = GradeRun(
                case=case,
                target=target,
                deps=deps,
                sandbox=sandbox,
                adapter=deps.grading_adapter_for(case),
                start=deps.tree_reader_for(case, case.start_sha),
                reference=deps.tree_reader_for(case, case.reference_sha),
            )
            try:
                _grade_steps(run)
            except (GradeAbsent, TreeReadError) as problem:
                failure = _as_absence(problem)
                record = _absent_record(
                    case,
                    target,
                    deps,
                    failure,
                    environment_digest=digest,
                    cost_usd=run.grading_cost_usd(),
                    began=began,
                    run=run,
                )
                if deps.keep:
                    sandbox.keep()
                return _write(deps, record)
            now = deps.clock()
            if target.subject is GradeSubject.REFERENCE:
                record: GradeRecord = reference_record(run, began, now)
            else:
                record = implementation_record(run, began, now)
            if deps.keep:
                sandbox.keep()
            return _write(deps, record)
    except (EnvironmentResolutionError, SandboxError) as exc:
        failure = absent(GradeAbsence.ENVIRONMENT_FAILED, str(exc))
        record = _absent_record(
            case, target, deps, failure, environment_digest=None, cost_usd=None, began=began
        )
        return _write(deps, record)
