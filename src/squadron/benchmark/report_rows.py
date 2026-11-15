"""Row helpers shared by the report's tables and sections (slice 425 D13)."""

from __future__ import annotations

import json
import statistics
from collections.abc import Mapping, Sequence

from squadron.benchmark.grade_matrix import Cell, GradeMatrix, ReferenceLookup, RowKey
from squadron.benchmark.paired_stats import case_pass_fraction
from squadron.benchmark.report_models import ConfigIdentity
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade

NOT_MEASURED = "not measured"
NO_VALUE = "–"
EFFORT_NOT_SENT = "effort not sent"


def config_identity(matrix: GradeMatrix, row: RowKey) -> ConfigIdentity:
    """The report's view of a row; its label is the alias the first replay named."""
    return ConfigIdentity(
        label=matrix.labels[row],
        model=row.model,
        profile=row.profile,
        effort_sent=row.effort_sent,
        tool_use=row.tool_use,
        max_output_tokens=row.max_output_tokens,
        prompt=row.prompt,
        identity=row.identity_text,
    )


def config_text(config: ConfigIdentity) -> str:
    """``label  (profile, effort high)``: how a row is named in the text report."""
    suffix = "" if config.prompt is None else f", prompt {config.prompt[:8]}"
    return f"{config.label} ({_profile_and_effort(config.profile, config.effort_sent)}{suffix})"


def _profile_and_effort(profile: str | None, effort_sent: str | None) -> str:
    """``profile, effort high``: the part of a config's name that is not its label."""
    effort = EFFORT_NOT_SENT if effort_sent is None else f"effort {effort_sent}"
    return f"{profile or 'no profile'}, {effort}"


def sorted_rows(matrix: GradeMatrix) -> list[RowKey]:
    """Every row, split ones included, in a fixed order."""
    return sorted(matrix.cells, key=lambda row: row.identity_text)


def case_fractions(matrix: GradeMatrix, row: RowKey, cases: Sequence[str]) -> dict[str, float]:
    """The pass fraction of each case the row has samples for (a config absence is a fail)."""
    by_case = matrix.cells.get(row, {})
    return {
        case: case_pass_fraction([cell.passed for cell in by_case[case]])
        for case in cases
        if by_case.get(case)
    }


def graded_cells(matrix: GradeMatrix, row: RowKey, cases: Sequence[str]) -> list[Cell]:
    """The row's cells on *cases* that carry a grade result."""
    by_case = matrix.cells.get(row, {})
    return [
        cell
        for case in cases
        for cell in by_case.get(case, ())
        if cell.grade is not None and cell.grade.result is not None
    ]


def environment_digest(cell: Cell) -> str | None:
    replay = cell.replay
    return None if replay is None or replay.environment is None else replay.environment.identity_digest


def reference_of(reference_for: ReferenceLookup, case_id: str, cell: Cell) -> ReferenceGrade | None:
    digest = environment_digest(cell)
    return None if digest is None else reference_for(case_id, digest)


def mean_or_none(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def total_suppressions(grade: ImplementationGrade) -> int:
    result = grade.result
    if result is None:
        return 0
    s = result.suppressions
    return s.noqa_source + s.noqa_test + s.type_ignore_source + s.type_ignore_test


def fmt_fraction(value: float | None) -> str:
    return NO_VALUE if value is None else f"{value:.2f}"


def fmt_signed(value: float | None, missing: str = NOT_MEASURED) -> str:
    return missing if value is None else f"{value:+.2f}"


def fmt_usd(value: float | None) -> str:
    return NO_VALUE if value is None else f"${value:.2f}"


def fmt_counts(counts: Mapping[str, int]) -> str:
    return ", ".join(f"{kind} {n}" for kind, n in sorted(counts.items())) or NO_VALUE


def name_width(configs: Sequence[ConfigIdentity], extra: Sequence[str] = ()) -> int:
    """The width that lines up a table's name column."""
    return max([len(config_text(c)) for c in configs] + [len(s) for s in extra], default=0)


def identity_label(identity_text: str) -> str:
    """A short name for a config from its canonical identity text (``RowKey.identity_text``)."""
    model, profile, effort, *_ = json.loads(identity_text)
    return f"{model} ({_profile_and_effort(profile, effort)})"
