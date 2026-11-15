"""The grade record a finished grade writes (slice 425 D1, D2, Database Schema)."""

from __future__ import annotations

from datetime import datetime

from squadron.benchmark.grade_run import GradeRun
from squadron.metrology.grade_models import DETAIL_MAX_CHARS, MAX_LISTED_ITEMS, GradeResult
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade


def build_result(run: GradeRun) -> GradeResult:
    """The measurements of a grade that ran to the end; every capped list beside its count."""
    if run.snapshot is None or run.hidden_id_map_sha256 is None:
        raise ValueError("the snapshot and hidden steps run before the result is built")
    config_edits = run.config_edits
    return GradeResult(
        hidden_total=run.hidden_total,
        hidden_passed=run.hidden_passed,
        hidden_failures=run.hidden_failures,
        hidden_id_map_sha256=run.hidden_id_map_sha256,
        injection_clashes=run.injection_clashes,
        injection_clash_count=run.injection_clash_count,
        regression_selected=run.regression_selected,
        regression_failures=run.regression_failures,
        regression_failure_count=run.regression_failure_count,
        producer_new_passed=run.producer_new_passed,
        producer_new_failed=run.producer_new_failed,
        config_edits=config_edits[:MAX_LISTED_ITEMS],
        config_edit_count=len(config_edits),
        test_edits=run.test_edits,
        test_edit_count=run.test_edit_count,
        suppressions=run.suppressions,
        reinstalled=run.reinstalled,
        lockfile_sha256=run.lockfile_sha256,
        snapshot=run.snapshot,
        lint_total=run.lint_total,
        type_total=run.type_total,
        reviews=tuple(run.review_summaries),
    )


def implementation_record(run: GradeRun, began: datetime, now: datetime) -> ImplementationGrade:
    """The replay's grade: its result, the sandbox's environment digest, cost and wall time."""
    target = run.target
    if target.replay_id is None or target.benchmark_id is None:
        raise ValueError("a replay target carries its replay id and benchmark id")
    return ImplementationGrade(
        replay_id=target.replay_id,
        benchmark_id=target.benchmark_id,
        case_id=run.case.case_id,
        grader=run.deps.grader,
        environment_digest=run.sandbox.identity.identity_digest,
        result=build_result(run),
        absence=None,
        absence_class=None,
        detail=None,
        grading_cost_usd=run.grading_cost_usd(),
        wall_seconds=(now - began).total_seconds(),
        created_at=now,
    )


def reference_record(run: GradeRun, began: datetime, now: datetime) -> ReferenceGrade:
    """The case's reference grade: its result, its baseline and its review floor."""
    return ReferenceGrade(
        case_id=run.case.case_id,
        grader=run.deps.grader,
        environment_digest=run.target.environment_digest,
        result=build_result(run),
        absence=None,
        detail=None,
        baseline_nodes=run.baseline_nodes_sha,
        baseline_snapshot=run.baseline_snapshot,
        baseline_lint_total=run.baseline_lint_total,
        baseline_type_total=run.baseline_type_total,
        review_floor=run.review_floor,
        grading_cost_usd=run.grading_cost_usd(),
        wall_seconds=(now - began).total_seconds(),
        created_at=now,
    )


#: How many failing ids a failed-reference detail names; the record holds the rest by count.
DETAIL_NAMED_IDS = 3


def failed_reference_detail(result: GradeResult) -> str | None:
    """Why a reference did not pass its own grade, ``None`` when it did.

    Names the first few failing hidden and regression ids, so a case that no longer grades
    cleanly can be diagnosed from its record.
    """
    if result.passed:
        return None
    named = [
        *(node.node_id for node in result.hidden_failures[:DETAIL_NAMED_IDS]),
        *result.regression_failures[:DETAIL_NAMED_IDS],
    ]
    return (
        f"the reference did not pass its own grade: "
        f"{result.hidden_total - result.hidden_passed} of {result.hidden_total} hidden tests "
        f"not passing, {result.regression_failure_count} regressions; first failing: "
        f"{', '.join(named)}"
    )[:DETAIL_MAX_CHARS]
