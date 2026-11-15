"""The slice-case table: objective grade, paired comparison and checks (slice 426 D10, D17).

Sections 1-3 for the included cases of kind ``slice``, registered for ``CaseKind.SLICE`` when
this module is imported (``bench_report`` imports it). A slice case has no hidden tests, so the
hidden column is omitted and the pass column is headed ``no regressions``: a subject passes when
no selected regression node fails. The builders are the fix table's, over the slice cases.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from squadron.benchmark.pair_row import PairRow
from squadron.benchmark.report_fix_table import (
    case_reference,
    check_row,
    objective_row,
    pair_rows,
    pair_text,
)
from squadron.benchmark.report_models import CheckRow, ObjectiveRow, TableSection
from squadron.benchmark.report_rows import (
    NO_VALUE,
    config_text,
    fmt_counts,
    fmt_fraction,
    fmt_signed,
    name_width,
    sorted_rows,
)
from squadron.benchmark.report_tables import ReportInputs, register_case_table
from squadron.metrology.benchmark_models import CaseKind

HEADING = "slice cases"
PAIRED_HEADING = "paired (95% bootstrap over cases)"
REFERENCE_LABEL = "reference (never ranked)"


class SliceReferenceLine(BaseModel):
    """The reference's own grade over the included cases; shown, never ranked."""

    model_config = ConfigDict(frozen=True)

    n_cases: int
    #: Cases whose reference had no failing regression node.
    no_regression_cases: int
    regressions: int


class SliceTableData(BaseModel):
    """Sections 1-3 of the slice-case table."""

    model_config = ConfigDict(frozen=True)

    objective: tuple[ObjectiveRow, ...]
    reference: SliceReferenceLine | None
    paired: tuple[PairRow, ...]
    checks: tuple[CheckRow, ...]


def _reference(inputs: ReportInputs, cases: tuple[str, ...]) -> SliceReferenceLine | None:
    counted = clean = regressions = 0
    for case in cases:
        reference = case_reference(inputs, case)
        if reference is None or reference.result is None:
            continue
        counted += 1
        failures = reference.result.regression_failure_count
        clean += failures == 0
        regressions += failures
    if not counted:
        return None
    return SliceReferenceLine(n_cases=counted, no_regression_cases=clean, regressions=regressions)


def slice_table_data(inputs: ReportInputs) -> SliceTableData:
    cases = inputs.included_of(CaseKind.SLICE)
    rows = sorted_rows(inputs.matrix)
    return SliceTableData(
        objective=tuple(objective_row(inputs, row, cases) for row in rows),
        reference=_reference(inputs, cases),
        paired=pair_rows(inputs, cases),
        checks=tuple(check_row(inputs, row, cases) for row in rows),
    )


def render_slice_table(data: SliceTableData) -> list[str]:
    width = name_width([row.config for row in data.objective], [REFERENCE_LABEL])
    lines = [f"{HEADING:<{width + 2}}    n   k  no regressions  regr  new tests  config absences"]
    for row in data.objective:
        lines.append(
            f"  {config_text(row.config):<{width}}  {row.n_cases:>3} {row.samples:>3}  "
            f"{fmt_fraction(row.mean_pass_fraction):>14}  {row.regressions:>4}  "
            f"{row.producer_new_passed}/{row.producer_new_passed + row.producer_new_failed}  "
            f"{fmt_counts(row.config_absences)}"
        )
    if data.reference is not None:
        ref = data.reference
        fraction = ref.no_regression_cases / ref.n_cases
        lines.append(
            f"  {REFERENCE_LABEL:<{width}}  {ref.n_cases:>3}   {NO_VALUE}  "
            f"{fraction:>14.2f}  {ref.regressions:>4}"
        )
    lines += ["", PAIRED_HEADING]
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


class SliceCaseTable:
    kind = CaseKind.SLICE

    def build(self, inputs: ReportInputs) -> TableSection:
        data = slice_table_data(inputs)
        return TableSection(
            kind=CaseKind.SLICE,
            lines=tuple(render_slice_table(data)),
            data=data.model_dump(mode="json"),
        )


register_case_table(SliceCaseTable())
