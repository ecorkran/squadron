"""Paired intervals per recipe pair (slice 430 D12)."""

from __future__ import annotations

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.scoring import RowOutputs, recipe_outputs
from squadron.benchmark.recall.scoring_paired import (
    MIN_RECALL_PAIRED_CASES,
    PairedLine,
    PairedMetric,
    paired_lines,
)
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.metrology.grade_models import PairVerdict
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import HitVerdict
from squadron.metrology.recall_run_models import RecallRun
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import finding, make_case, make_run, review

BENCH = "s@v1"


def _setup(
    case_count: int, a_hits: int, undecided_cases: int = 0
) -> tuple[list[RowOutputs], dict[str, ResolvedLabels]]:
    """Reviewer a hits B1 on the first *a_hits* cases; b never hits. Some cases get an open finding."""
    cases: list[RealBugCase] = [make_case(f"case-{i}") for i in range(case_count)]
    runs: dict[tuple[str, int], RecallRun] = {}
    labels: dict[str, ResolvedLabels] = {}
    for i, case in enumerate(cases):
        hit = finding(1, "src/a.py", text=case.name)
        a_findings = (hit,) if i < a_hits else ()
        b_findings = (finding(2, None, text=case.name),) if i < undecided_cases else ()
        runs[(case.case_id, 1)] = make_run(case, 1, review("a", a_findings), review("b", b_findings))
        labels[case.case_id] = ResolvedLabels(
            hits={hit.content_key: {"B1": HitVerdict.HIT, "B2": HitVerdict.MISS}}
        )
    rows = [
        recipe_outputs(Recipe(name=name, reviewers=(name,)), cases, runs, [1], ImportOnlyResolver())[0]
        for name in ("a", "b")
    ]
    return rows, labels


def _recall_line(lines: list[PairedLine]) -> PairedLine:
    return next(line for line in lines if line.metric is PairedMetric.RECALL)


def test_interval_is_deterministic_for_a_fixed_set() -> None:
    rows, labels = _setup(10, a_hits=10)
    first = _recall_line(paired_lines(rows, labels, [1], BENCH))
    second = _recall_line(paired_lines(rows, labels, [1], BENCH))
    assert first == second
    assert first.comparison.n == 10
    assert first.comparison.verdict is PairVerdict.A_AHEAD


def test_interval_spanning_zero_is_not_distinguishable() -> None:
    rows, labels = _setup(10, a_hits=1)
    line = _recall_line(paired_lines(rows, labels, [1], BENCH))
    assert line.comparison.verdict is PairVerdict.NOT_DISTINGUISHABLE


def test_too_few_cases_below_the_floor() -> None:
    rows, labels = _setup(MIN_RECALL_PAIRED_CASES - 1, a_hits=7)
    line = _recall_line(paired_lines(rows, labels, [1], BENCH))
    assert line.comparison.verdict is PairVerdict.TOO_FEW_CASES
    assert line.comparison.low is None


def test_undecided_cases_are_left_out_and_counted() -> None:
    rows, labels = _setup(10, a_hits=10, undecided_cases=3)
    line = _recall_line(paired_lines(rows, labels, [1], BENCH))
    assert line.left_out_undecided == 3
    assert line.comparison.n == 7
    assert line.comparison.verdict is PairVerdict.TOO_FEW_CASES
