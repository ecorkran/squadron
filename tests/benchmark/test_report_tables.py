"""The case-kind table registry and ``review_flag`` (slice 425 Task 38, D13)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark import report_tables
from squadron.benchmark.bench_report import review_flag
from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.benchmark.report_fix_table import FixCaseTable
from squadron.benchmark.report_models import TableSection
from squadron.benchmark.report_tables import (
    ReportInputs,
    UnregisteredCaseKind,
    register_case_table,
    table_for,
)
from squadron.metrology.benchmark_models import CaseKind
from tests.benchmark.report_support import ReportWorld, config, make_world
from tests.benchmark.test_grade_identity import make_reviewer

SOURCE = Path(__file__).resolve().parents[2] / "src" / "squadron" / "benchmark"


class StubSliceTable:
    kind = CaseKind.SLICE

    def build(self, inputs: ReportInputs) -> TableSection:
        cases = list(inputs.included_of(CaseKind.SLICE))
        return TableSection(
            kind=CaseKind.SLICE,
            lines=(f"stub slice table over {len(cases)} cases",),
            data={"cases": cases},
        )


def world_with_slice_cases(tmp_path: Path) -> ReportWorld:
    world = make_world(tmp_path)
    for index in range(2):
        case = world.add_case(f"slice-case-{index}")
        world.cases[case.case_id] = case.model_copy(update={"kind": CaseKind.SLICE})
        for sample in range(2):
            world.add_sample(case, config("opus"), sample)
    return world


@pytest.fixture
def isolated_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report_tables, "_TABLES", dict(report_tables._TABLES))  # pyright: ignore[reportPrivateUsage]


def test_a_stub_kind_with_a_stub_table_appears_in_text_and_json_with_no_report_code_change(
    tmp_path: Path, isolated_registry: None
) -> None:
    register_case_table(StubSliceTable())
    report = world_with_slice_cases(tmp_path).build()
    assert [section.kind for section in report.tables] == [CaseKind.SLICE]
    assert "stub slice table over 2 cases" in render_text(report)
    assert '"stub slice table over 2 cases"' in render_json(report)


def test_the_fix_table_is_registered_for_the_fix_kind() -> None:
    assert isinstance(table_for(CaseKind.FIX), FixCaseTable)


def test_an_unregistered_kind_raises_and_logs_error(
    tmp_path: Path, isolated_registry: None, caplog: pytest.LogCaptureFixture
) -> None:
    report_tables._TABLES.pop(CaseKind.SLICE, None)  # pyright: ignore[reportPrivateUsage]
    world = world_with_slice_cases(tmp_path)
    with caplog.at_level(logging.ERROR), pytest.raises(UnregisteredCaseKind, match="slice"):
        world.build()
    assert any(r.levelno == logging.ERROR and "slice" in r.getMessage() for r in caplog.records)


def test_review_flag_text_for_two_aliases() -> None:
    assert review_flag(make_reviewer(alias="gpt-review")) == (
        "unmeasured reviewer: no recall data for gpt-review"
    )
    assert review_flag(make_reviewer(alias="other")) == (
        "unmeasured reviewer: no recall data for other"
    )


def test_the_flag_text_lives_in_exactly_one_source_file() -> None:
    holders = [
        path.name
        for path in SOURCE.glob("*.py")
        if "unmeasured reviewer" in path.read_text(encoding="utf-8")
    ]
    assert holders == ["bench_report.py"]
