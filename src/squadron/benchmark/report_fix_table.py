"""The fix-case table: objective grade, paired comparison, checks and snapshot (slice 425 D13).

Sections 1-3 for the included cases of kind ``fix``. Registered for ``CaseKind.FIX`` when this
module is imported; ``bench_report`` imports it, and 426 registers its own kind the same way.
"""

from __future__ import annotations

import itertools
from collections import Counter

from squadron.benchmark.grade_matrix import RowKey
from squadron.benchmark.pair_row import PairRow, verdict_text
from squadron.benchmark.paired_stats import (
    compare_pair,
    pair_seed,
    paired_differences,
)
from squadron.benchmark.report_models import (
    CheckRow,
    FixTableData,
    ObjectiveRow,
    ReferenceLine,
    TableSection,
)
from squadron.benchmark.report_rows import (
    NO_VALUE,
    case_fractions,
    config_identity,
    config_text,
    fmt_counts,
    fmt_fraction,
    fmt_signed,
    graded_cells,
    mean_or_none,
    name_width,
    reference_of,
    sorted_rows,
    total_suppressions,
)
from squadron.benchmark.report_tables import ReportInputs, register_case_table
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.grade_models import PairVerdict
from squadron.metrology.grade_records import ReferenceGrade


def objective_row(inputs: ReportInputs, row: RowKey, cases: tuple[str, ...]) -> ObjectiveRow:
    matrix = inputs.matrix
    fractions = case_fractions(matrix, row, cases)
    results = [cell.grade.result for cell in graded_cells(matrix, row, cases) if cell.grade]
    absences = Counter(
        cell.config_absence
        for case in cases
        for cell in matrix.cells.get(row, {}).get(case, ())
        if cell.config_absence
    )
    return ObjectiveRow(
        config=config_identity(matrix, row),
        n_cases=len(fractions),
        samples=matrix.samples,
        mean_pass_fraction=mean_or_none(list(fractions.values())),
        hidden_passed=sum(r.hidden_passed for r in results if r),
        hidden_total=sum(r.hidden_total for r in results if r),
        regressions=sum(r.regression_failure_count for r in results if r),
        producer_new_passed=sum(r.producer_new_passed for r in results if r),
        producer_new_failed=sum(r.producer_new_failed for r in results if r),
        config_absences=dict(absences),
    )


def case_reference(inputs: ReportInputs, case: str) -> ReferenceGrade | None:
    """The case's reference grade, read for the environment of its first replay that has one."""
    return next(
        (
            found
            for row in sorted_rows(inputs.matrix)
            for cell in inputs.matrix.cells.get(row, {}).get(case, ())
            if (found := reference_of(inputs.reference_for, case, cell)) is not None
        ),
        None,
    )


def reference_line(inputs: ReportInputs, cases: tuple[str, ...]) -> ReferenceLine | None:
    """The reference's grade on each included case, read for its replays' environment."""
    passed = total = regressions = counted = 0
    for case in cases:
        reference = case_reference(inputs, case)
        if reference is None or reference.result is None:
            continue
        counted += 1
        passed += reference.result.hidden_passed
        total += reference.result.hidden_total
        regressions += reference.result.regression_failure_count
    return (
        ReferenceLine(
            n_cases=counted, hidden_passed=passed, hidden_total=total, regressions=regressions
        )
        if counted
        else None
    )


def pair_rows(inputs: ReportInputs, cases: tuple[str, ...]) -> tuple[PairRow, ...]:
    matrix = inputs.matrix
    rows = sorted(matrix.comparable_rows, key=lambda r: r.identity_text)
    out: list[PairRow] = []
    for a, b in itertools.combinations(rows, 2):
        fractions_a = case_fractions(matrix, a, cases)
        fractions_b = case_fractions(matrix, b, cases)
        shared = fractions_a.keys() & fractions_b.keys()
        differences = paired_differences(
            {c: fractions_a[c] for c in shared}, {c: fractions_b[c] for c in shared}
        )
        seed = pair_seed(inputs.run.benchmark_id, a.identity_text, b.identity_text)
        result = compare_pair(differences, seed)
        out.append(
            PairRow(
                label_a=matrix.labels[a],
                label_b=matrix.labels[b],
                n_cases=result.n,
                mean_difference=result.mean,
                low=result.low,
                high=result.high,
                verdict=result.verdict,
            )
        )
    return tuple(out)


def check_row(inputs: ReportInputs, row: RowKey, cases: tuple[str, ...]) -> CheckRow:
    matrix = inputs.matrix
    lint: list[float] = []
    types: list[float] = []
    config_edits = test_edits = suppressions = reinstalls = 0
    for case in cases:
        for cell in matrix.cells.get(row, {}).get(case, ()):
            grade = cell.grade
            if grade is None or grade.result is None:
                continue
            result = grade.result
            reference = reference_of(inputs.reference_for, case, cell)
            if reference is not None:
                if result.lint_total is not None and reference.baseline_lint_total is not None:
                    lint.append(result.lint_total - reference.baseline_lint_total)
                if result.type_total is not None and reference.baseline_type_total is not None:
                    types.append(result.type_total - reference.baseline_type_total)
            config_edits += result.config_edit_count
            test_edits += result.test_edit_count
            suppressions += total_suppressions(grade)
            reinstalls += int(result.reinstalled)
    return CheckRow(
        config=config_identity(matrix, row),
        mean_lint_delta=mean_or_none(lint),
        mean_type_delta=mean_or_none(types),
        config_edits=config_edits,
        test_edits=test_edits,
        suppressions=suppressions,
        reinstalls=reinstalls,
    )


def fix_table_data(inputs: ReportInputs) -> FixTableData:
    cases = inputs.included_of(CaseKind.FIX)
    rows = sorted_rows(inputs.matrix)
    return FixTableData(
        objective=tuple(objective_row(inputs, row, cases) for row in rows),
        reference=reference_line(inputs, cases),
        paired=pair_rows(inputs, cases),
        checks=tuple(check_row(inputs, row, cases) for row in rows),
    )


def pair_text(pair: PairRow) -> str:
    head = f"  {pair.label_a} − {pair.label_b}"
    if pair.verdict is PairVerdict.TOO_FEW_CASES:
        return f"{head}  {pair.mean_difference:+.2f}  too few cases ({pair.n_cases})"
    interval = f"[{pair.low:+.2f}, {pair.high:+.2f}]"
    return f"{head}  {pair.mean_difference:+.2f}  {interval}  {verdict_text(pair)}"


REFERENCE_LABEL = "reference (never ranked)"


def render_fix_table(data: FixTableData) -> list[str]:
    width = name_width([row.config for row in data.objective], [REFERENCE_LABEL])
    lines = [
        f"{'objective grade':<{width + 2}}    n   k  pass frac  hidden   regr  "
        "new tests  config absences"
    ]
    for row in data.objective:
        lines.append(
            f"  {config_text(row.config):<{width}}  {row.n_cases:>3} {row.samples:>3}  "
            f"{fmt_fraction(row.mean_pass_fraction):>9}  {row.hidden_passed}/{row.hidden_total}  "
            f"{row.regressions:>5}  {row.producer_new_passed}/"
            f"{row.producer_new_passed + row.producer_new_failed}  "
            f"{fmt_counts(row.config_absences)}"
        )
    if data.reference is not None:
        ref = data.reference
        lines.append(
            f"  {REFERENCE_LABEL:<{width}}  {ref.n_cases:>3}   {NO_VALUE}  "
            f"{'':>9}  {ref.hidden_passed}/{ref.hidden_total}  {ref.regressions:>5}"
        )
    lines += ["", "paired (95% bootstrap over cases)"]
    lines += [pair_text(pair) for pair in data.paired] or [f"  {NO_VALUE} (fewer than two configs)"]
    check_width = name_width([check.config for check in data.checks])
    lines += [
        "",
        f"{'checks vs baseline':<{check_width + 2}}  lint Δ  types Δ  config edits  test edits  "
        "suppressions  reinstalls",
    ]
    for check in data.checks:
        lines.append(
            f"  {config_text(check.config):<{check_width}}  {fmt_signed(check.mean_lint_delta):>6}  "
            f"{fmt_signed(check.mean_type_delta):>12}  {check.config_edits:>12}  "
            f"{check.test_edits:>10}  {check.suppressions:>12}  {check.reinstalls:>10}"
        )
    return lines


class FixCaseTable:
    kind = CaseKind.FIX

    def build(self, inputs: ReportInputs) -> TableSection:
        data = fix_table_data(inputs)
        return TableSection(
            kind=CaseKind.FIX,
            lines=tuple(render_fix_table(data)),
            data=data.model_dump(mode="json"),
        )


register_case_table(FixCaseTable())
