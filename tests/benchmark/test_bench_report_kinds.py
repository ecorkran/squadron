"""The report grouped by case kind (slice 426, Task 36)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from squadron.benchmark.bench_report_render import render_json, render_text
from squadron.metrology.benchmark_models import CaseKind
from tests.benchmark.pairwise_support import slice_world
from tests.benchmark.report_support import fixture_world, make_world

GOLDEN = Path(__file__).parent / "fixtures" / "report_golden.txt"
_GRADER_DIGEST = re.compile(r"grader [0-9a-f]{8}")


def _normalized(text: str) -> str:
    """The grader digest moved on main (#336) without the golden; the rest must match."""
    return _GRADER_DIGEST.sub("grader XXXXXXXX", text)


def test_a_fix_only_benchmark_is_byte_identical_to_425s_golden(tmp_path: Path) -> None:
    report = fixture_world(tmp_path).build()

    text = render_text(report)

    assert _normalized(text + "\n") == _normalized(GOLDEN.read_text(encoding="utf-8"))
    assert [section.kind for section in report.tables] == [CaseKind.FIX]
    assert "slice cases" not in text
    assert "pairwise" not in text
    assert "pairwise" not in json.loads(render_json(report))


def test_a_slice_only_benchmark_shows_one_slice_table_with_the_renamed_column(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    slice_world(world, cases=3, samples=2)

    report = world.build()
    text = render_text(report)

    assert [section.kind for section in report.tables] == [CaseKind.SLICE]
    header = next(line for line in text.splitlines() if line.startswith("slice cases"))
    assert "no regressions" in header
    assert "hidden" not in header and "pass frac" not in header
    assert "objective grade" not in text
    assert text.count("slice cases") == 1


def test_the_slice_table_has_paired_and_checks_sections_and_a_reference_line(
    tmp_path: Path,
) -> None:
    world = make_world(tmp_path)
    slice_world(world, cases=3, samples=2)

    text = render_text(world.build())

    assert "paired (95% bootstrap over cases)" in text
    assert "checks vs baseline" in text
    reference = next(line for line in text.splitlines() if "reference (never ranked)" in line)
    assert "1.00" in reference  # every reference passes, so every case has no regressions


def test_a_mixed_benchmark_shows_both_kinds_fix_first(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    slice_world(world, cases=2, samples=2, kind_fix=2)

    report = world.build()
    text = render_text(report)

    assert [section.kind for section in report.tables] == [CaseKind.FIX, CaseKind.SLICE]
    assert text.index("objective grade") < text.index("slice cases")
    assert "hidden" in text.split("slice cases")[0]  # the fix table keeps its hidden column
    assert [t["kind"] for t in json.loads(render_json(report))["tables"]] == ["fix", "slice"]


def test_the_slice_table_data_counts_only_slice_cases(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    slice_world(world, cases=2, samples=2, kind_fix=1)

    report = world.build()
    slice_data = next(t for t in report.tables if t.kind is CaseKind.SLICE).data
    fix_data = next(t for t in report.tables if t.kind is CaseKind.FIX).data

    assert {row["n_cases"] for row in slice_data["objective"]} == {2}
    assert {row["n_cases"] for row in fix_data["objective"]} == {1}
    assert slice_data["reference"]["n_cases"] == 2
