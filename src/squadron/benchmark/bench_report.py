"""The benchmark report, assembled from stored records (slice 425 D13).

Scope is one benchmark and its latest grader identity. Sections 1-3 come from the case-kind
tables registered in ``report_tables`` (the fix table registers on import below); sections 4-7
(review findings, cost and time, absences and exclusions, the sample count) are built here.
No function in this module combines two signals into one number.
"""

from __future__ import annotations

import itertools
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence

from squadron.benchmark.grade_matrix import (
    AbsenceStage,
    GradeMatrix,
    ReferenceLookup,
    RowKey,
    absence_label,
    build_matrix,
)
from squadron.benchmark.leak_scan import LEAK_RULES_VERSION
from squadron.benchmark.report_fix_table import FixCaseTable as FixCaseTable  # registers on import
from squadron.benchmark.report_models import (
    AbsenceCount,
    BenchmarkReport,
    CostRow,
    FindingsRow,
    ReviewPair,
)
from squadron.benchmark.report_rows import (
    config_identity,
    graded_cells,
    mean_or_none,
    reference_of,
    sorted_rows,
)
from squadron.benchmark.report_tables import ReportInputs, build_tables
from squadron.metrology.audit_delta import is_within_floor
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.grade_models import GRADE_ABSENCE_CLASS, GraderIdentity, ReviewerRef
from squadron.metrology.grade_records import ImplementationGrade, SampleSizeEstimate


def review_flag(reviewer: ReviewerRef) -> str:
    """The heading text of the review section; 427 changes this function alone.

    Until recall data exists for the grading reviewer, its findings are flagged unmeasured.
    """
    return f"unmeasured reviewer: no recall data for {reviewer.alias}"


def latest_grader(grades: Sequence[ImplementationGrade]) -> GraderIdentity | None:
    """The grader identity of the newest grade, ``None`` when nothing is graded."""
    if not grades:
        return None
    return max(grades, key=lambda grade: grade.created_at).grader


def _findings_rows(matrix: GradeMatrix, cases: Sequence[str]) -> tuple[FindingsRow, ...]:
    rows: list[FindingsRow] = []
    for row in sorted_rows(matrix):
        summaries = [
            cell.grade.result.reviews[0]
            for cell in graded_cells(matrix, row, cases)
            if cell.grade and cell.grade.result and cell.grade.result.reviews
        ]
        severities = sorted({sev for s in summaries for sev in s.severity_counts})
        rows.append(
            FindingsRow(
                config=config_identity(matrix, row),
                replays=len(summaries),
                mean_by_severity={
                    sev: statistics.fmean(s.severity_counts.get(sev, 0) for s in summaries)
                    for sev in severities
                },
                mean_total=mean_or_none([float(s.total) for s in summaries]),
            )
        )
    return tuple(rows)


def _mean_findings_by_case(matrix: GradeMatrix, row: RowKey, cases: Sequence[str]) -> dict[str, float]:
    by_case = matrix.cells.get(row, {})
    out: dict[str, float] = {}
    for case in cases:
        totals = [
            float(cell.grade.result.reviews[0].total)
            for cell in by_case.get(case, ())
            if cell.grade and cell.grade.result and cell.grade.result.reviews
        ]
        if totals:
            out[case] = statistics.fmean(totals)
    return out


def _review_pairs(inputs: ReportInputs, cases: Sequence[str]) -> tuple[ReviewPair, ...]:
    matrix = inputs.matrix
    rows = sorted(matrix.comparable_rows, key=lambda r: r.identity_text)
    pairs: list[ReviewPair] = []
    for a, b in itertools.combinations(rows, 2):
        means_a = _mean_findings_by_case(matrix, a, cases)
        means_b = _mean_findings_by_case(matrix, b, cases)
        a_more = b_more = within = no_floor = 0
        for case in sorted(means_a.keys() & means_b.keys()):
            cell = next(iter(matrix.cells[a].get(case, ())), None)
            reference = None if cell is None else reference_of(inputs.reference_for, case, cell)
            floor = None if reference is None else reference.review_floor
            delta = means_a[case] - means_b[case]
            judged = is_within_floor(delta, floor)
            if judged is None:
                no_floor += 1
            elif judged:
                within += 1
            elif delta > 0:
                a_more += 1
            else:
                b_more += 1
        pairs.append(
            ReviewPair(
                label_a=matrix.labels[a],
                label_b=matrix.labels[b],
                a_more=a_more,
                b_more=b_more,
                within=within,
                no_floor=no_floor,
            )
        )
    return tuple(pairs)


def _cost_rows(matrix: GradeMatrix, cases: Sequence[str]) -> tuple[CostRow, ...]:
    rows: list[CostRow] = []
    for row in sorted_rows(matrix):
        cells = [c for case in cases for c in matrix.cells.get(row, {}).get(case, ())]
        replays = [c.replay for c in cells if c.replay is not None]
        grades = [c.grade for c in cells if c.grade is not None]
        producer = [r.cost_usd for r in replays if r.cost_usd is not None]
        grading = [g.grading_cost_usd for g in grades if g.grading_cost_usd is not None]
        turns = [float(r.turns) for r in replays if r.turns is not None]
        walls = [r.wall_seconds for r in replays]
        rows.append(
            CostRow(
                config=config_identity(matrix, row),
                producer_cost_mean=mean_or_none(producer),
                producer_cost_total=sum(producer) if producer else None,
                grading_cost_mean=mean_or_none(grading),
                grading_cost_total=sum(grading) if grading else None,
                turns_mean=mean_or_none(turns),
                wall_seconds_mean=mean_or_none(walls),
                wall_seconds_total=sum(walls),
                unpriced_producer=len(replays) - len(producer),
                unpriced_grading=len(grades) - len(grading),
            )
        )
    return tuple(rows)


def _absence_counts(
    replays: Sequence[tuple[str, ImplementationReplay]], grades: Sequence[ImplementationGrade]
) -> tuple[AbsenceCount, ...]:
    counts: Counter[tuple[str, str]] = Counter()
    for _, replay in replays:
        if replay.absence is not None:
            counts[
                (replay.absence.value, absence_label(AbsenceStage.REPLAY, replay.outcome.value))
            ] += 1
    for grade in grades:
        if grade.absence is not None:
            counts[
                (
                    GRADE_ABSENCE_CLASS[grade.absence].value,
                    absence_label(AbsenceStage.GRADE, grade.absence.value),
                )
            ] += 1
    return tuple(
        AbsenceCount(absence_class=cls, kind=kind, count=n) for (cls, kind), n in sorted(counts.items())
    )


def build_report(
    *,
    run: BenchmarkRun,
    cases: Mapping[str, BenchmarkCase],
    case_ids: Sequence[str],
    replays: Sequence[tuple[str, ImplementationReplay]],
    grades: Sequence[ImplementationGrade],
    grader: GraderIdentity,
    reference_for: ReferenceLookup,
    estimate: SampleSizeEstimate | None,
) -> BenchmarkReport:
    """Assemble the report of one benchmark under *grader* from its stored records."""
    matrix = build_matrix(
        case_ids=case_ids,
        samples=run.samples,
        replays=replays,
        grades=grades,
        grader_digest=grader.digest,
        reference_for=reference_for,
    )
    inputs = ReportInputs(
        run=run, cases=cases, grader=grader, matrix=matrix, reference_for=reference_for
    )
    included = matrix.included_cases
    latest = [g for g in grades if g.grader.digest == grader.digest]
    return BenchmarkReport(
        benchmark_id=run.benchmark_id,
        case_set=run.case_set,
        case_set_version=run.case_set_version,
        grader_digest=grader.digest,
        reviewer_alias=grader.reviewer.alias,
        review_floor_runs=grader.review_floor_runs,
        cases_in_set=len(case_ids),
        cases_compared=len(included),
        exclusions=dict(Counter(reason.value for reason in matrix.excluded.values())),
        dropped_cases=len(run.case_drops),
        warnings=matrix.warnings,
        older_identity_grades=matrix.older_identity_grades,
        tables=build_tables(inputs),
        review_flag=review_flag(grader.reviewer),
        findings=_findings_rows(matrix, included),
        review_pairs=_review_pairs(inputs, included),
        costs=_cost_rows(matrix, included),
        absences=_absence_counts(replays, latest),
        stale_leak_scans=sum(
            1
            for _, replay in replays
            if replay.leak is not None and replay.leak.rules_version < LEAK_RULES_VERSION
        ),
        unstamped_replays=dict(matrix.unstamped),
        # One estimate is stored per benchmark; one made under another grader is out of date.
        estimate=estimate if estimate is not None and estimate.grader_digest == grader.digest else None,
    )
