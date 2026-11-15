"""Report sections 1-3 on a hand-computed fixture (slice 425 Task 39, D13).

Fixture: opus (high) and sol (medium) on six cases at k = 2. Pass patterns per case,
opus [TT, TT, TF, FF, TT, TF] and sol [TF, FF, FF, FF, TF, FF], give per-case fractions
[1, 1, .5, 0, 1, .5] and [.5, 0, 0, 0, .5, 0]: means 2/3 and 1/6, paired differences
[.5, 1, .5, 0, .5, .5] with mean 0.5. A passing cell has 3 of 3 hidden tests and a failing one
2 of 3: opus has 8 passing and 4 failing cells (8*3 + 4*2 = 32 of 36), sol 2 and 10 (26 of 36).
Opus's case 3 sample 0 has two regressions. Lint is 4 for opus (baseline 3, so +1) and 6 for sol
(+3); types 2 for opus (baseline 2, so 0) and not measured for sol.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from squadron.benchmark.bench_report_render import render_text
from squadron.benchmark.report_models import FixTableData
from squadron.benchmark.report_tables import ReportInputs, table_for
from squadron.metrology.benchmark_models import CaseKind
from squadron.metrology.grade_models import PairVerdict
from tests.benchmark.report_support import ReportWorld, config, fixture_world, make_world


def fix_data(world: ReportWorld) -> FixTableData:
    report = world.build()
    return FixTableData.model_validate(report.tables[0].data)


def test_the_objective_rows_match_the_hand_computed_values(tmp_path: Path) -> None:
    data = fix_data(fixture_world(tmp_path))
    opus, sol = data.objective
    assert (opus.config.label, sol.config.label) == ("opus", "sol")
    assert (opus.n_cases, opus.samples, sol.n_cases) == (6, 2, 6)
    assert opus.mean_pass_fraction == pytest.approx(2 / 3)
    assert sol.mean_pass_fraction == pytest.approx(1 / 6)
    assert (opus.hidden_passed, opus.hidden_total) == (32, 36)
    assert (sol.hidden_passed, sol.hidden_total) == (26, 36)
    assert (opus.regressions, sol.regressions) == (2, 0)
    assert (opus.producer_new_passed, opus.producer_new_failed) == (0, 0)


def test_the_reference_line_is_read_per_case_and_never_ranked(tmp_path: Path) -> None:
    data = fix_data(fixture_world(tmp_path))
    assert data.reference is not None
    assert (data.reference.n_cases, data.reference.hidden_passed, data.reference.hidden_total) == (
        6,
        18,
        18,
    )
    assert data.reference.regressions == 0


def test_a_clear_pair_is_ahead_with_an_interval_above_zero(tmp_path: Path) -> None:
    (pair,) = fix_data(fixture_world(tmp_path)).paired
    assert (pair.label_a, pair.label_b) == ("opus", "sol")
    assert pair.mean_difference == pytest.approx(0.5)
    assert pair.low is not None and pair.low > 0
    assert pair.high is not None and pair.high <= 1.0
    assert pair.verdict is PairVerdict.A_AHEAD


def test_a_null_pair_is_not_distinguishable(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    for index in range(6):
        case = world.add_case(f"case-{index}")
        for sample in range(2):
            world.add_sample(case, config("opus"), sample, passed=index % 2 == 0)
            world.add_sample(case, config("sol", effort_sent="medium"), sample, passed=index % 2 == 0)
    (pair,) = fix_data(world).paired
    assert pair.mean_difference == 0.0
    assert pair.verdict is PairVerdict.NOT_DISTINGUISHABLE


def test_a_missing_lint_or_type_total_is_not_measured_not_zero(tmp_path: Path) -> None:
    world = fixture_world(tmp_path)
    opus, sol = fix_data(world).checks
    assert opus.mean_lint_delta == pytest.approx(1.0)
    assert opus.mean_type_delta == pytest.approx(0.0)
    assert sol.mean_lint_delta == pytest.approx(3.0)
    assert sol.mean_type_delta is None
    text = render_text(world.build())
    sol_line = next(line for line in text.splitlines() if line.startswith("  sol") and "+3.00" in line)
    assert "not measured" in sol_line
    opus_line = next(
        line for line in text.splitlines() if line.startswith("  opus") and "+1.00" in line
    )
    assert "not measured" not in opus_line


def test_the_checks_count_edits_suppressions_and_reinstalls(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    cfg = config("opus")
    for index in range(6):
        case = world.add_case(f"case-{index}")
        for sample in range(2):
            world.add_sample(
                case,
                cfg,
                sample,
                config_edits=("tool.ruff",),
                config_edit_count=1,
                test_edits=("tests/a.py", "tests/b.py"),
                test_edit_count=2,
                reinstalled=sample == 0,
            )
    (check,) = fix_data(world).checks
    assert (check.config_edits, check.test_edits, check.reinstalls) == (12, 24, 6)
    assert check.suppressions == 0


def test_fewer_than_five_cases_show_too_few_cases_with_the_count(tmp_path: Path) -> None:
    world = make_world(tmp_path)
    for index in range(4):
        case = world.add_case(f"case-{index}")
        for sample in range(2):
            world.add_sample(case, config("opus"), sample, passed=True)
            world.add_sample(case, config("sol", effort_sent="medium"), sample, passed=False)
    (pair,) = fix_data(world).paired
    assert pair.verdict is PairVerdict.TOO_FEW_CASES
    assert (pair.low, pair.high) == (None, None)
    assert "too few cases (4)" in render_text(world.build())


def test_the_section_comes_from_the_table_registered_for_the_fix_kind(tmp_path: Path) -> None:
    report = fixture_world(tmp_path).build()
    (section,) = report.tables
    assert section.kind is CaseKind.FIX
    assert section.lines == tuple(
        table_for(CaseKind.FIX).build(_inputs(fixture_world(tmp_path / "again"))).lines
    )


def _inputs(world: ReportWorld) -> ReportInputs:
    from squadron.benchmark.grade_matrix import build_matrix

    matrix = build_matrix(
        case_ids=list(world.cases),
        samples=world.run.samples,
        replays=world.replays,
        grades=world.grades,
        grader_digest=world.grader.digest,
        reference_for=lambda c, d: world.store.get_reference_grade(c, world.grader.digest, d),
    )
    return ReportInputs(
        run=world.run,
        cases=world.cases,
        grader=world.grader,
        matrix=matrix,
        reference_for=lambda c, d: world.store.get_reference_grade(c, world.grader.digest, d),
    )
