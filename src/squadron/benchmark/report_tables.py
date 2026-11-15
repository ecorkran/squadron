"""Case-kind tables of the benchmark report: the protocol and its registry (slice 425 D13).

Sections 1-3 of the report (objective grade, paired comparison, checks against the baseline)
are built per case kind by a registered table. 426 registers its slice-case table here without
editing ``bench_report.py`` or the grade runner. A kind with no registered table raises a named
error: it is never silently left out of the report.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from squadron.benchmark.grade_matrix import GradeMatrix, ReferenceLookup
from squadron.benchmark.report_models import TableSection
from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.metrology.benchmark_replay_models import BenchmarkRun
from squadron.metrology.grade_models import GraderIdentity

_logger = logging.getLogger(__name__)


class UnregisteredCaseKind(Exception):
    """An included case has a kind no table is registered for."""

    def __init__(self, kind: CaseKind) -> None:
        super().__init__(f"no report table is registered for case kind '{kind.value}'")
        self.kind = kind


@dataclass(frozen=True)
class ReportInputs:
    """What a table reads: the run, the comparable cases and the matrix of their outcomes."""

    run: BenchmarkRun
    cases: Mapping[str, BenchmarkCase]
    grader: GraderIdentity
    matrix: GradeMatrix
    reference_for: ReferenceLookup

    def included_of(self, kind: CaseKind) -> tuple[str, ...]:
        """The compared cases of one kind, in case-id order."""
        return tuple(c for c in self.matrix.included_cases if self.cases[c].kind is kind)


class CaseKindTable(Protocol):
    """Builds and renders sections 1-3 for the included cases of one kind."""

    kind: CaseKind

    def build(self, inputs: ReportInputs) -> TableSection: ...


_TABLES: dict[CaseKind, CaseKindTable] = {}


def register_case_table(table: CaseKindTable) -> None:
    """Register *table* for its kind, replacing any earlier one."""
    _TABLES[table.kind] = table


def table_for(kind: CaseKind) -> CaseKindTable:
    table = _TABLES.get(kind)
    if table is None:
        _logger.error("no report table is registered for case kind '%s'", kind.value)
        raise UnregisteredCaseKind(kind)
    return table


def kinds_present(inputs: ReportInputs) -> Sequence[CaseKind]:
    """The case kinds among the compared cases, in kind order."""
    return sorted({inputs.cases[c].kind for c in inputs.matrix.included_cases}, key=lambda k: k.value)


def build_tables(inputs: ReportInputs) -> tuple[TableSection, ...]:
    """One table per kind present among the included cases, from the registry."""
    return tuple(table_for(kind).build(inputs) for kind in kinds_present(inputs))


__all__ = [
    "CaseKindTable",
    "ReportInputs",
    "UnregisteredCaseKind",
    "build_tables",
    "register_case_table",
    "table_for",
]
