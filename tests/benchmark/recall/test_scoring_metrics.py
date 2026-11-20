"""Per-row metrics: bounds, matched nothing, pool mean, grades (slice 430 D3, D5)."""

from __future__ import annotations

from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.scoring import RowOutputs, recipe_outputs
from squadron.benchmark.recall.scoring_metrics import Bounds, row_metrics
from squadron.benchmark.recall.scoring_select import (
    ImportOnlyResolver,
    StageIdentityResolver,
    identity_of,
)
from squadron.metrology.recall_label_models import FindingGrade, HitVerdict
from squadron.metrology.recall_run_models import LIVE_SOURCE, RecallRun
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import StubResolver, finding, make_case, make_run, review

CASE = make_case()  # B1 in src/a.py, B2 in src/b.py
SET = "s@v1"


def _row(
    recipe: Recipe, *runs: RecallRun, resolver: StageIdentityResolver | None = None
) -> list[RowOutputs]:
    by_key = {(r.case_id, r.run_index): r for r in runs}
    indexes = sorted({r.run_index for r in runs})
    return recipe_outputs(recipe, [CASE], by_key, indexes, resolver or ImportOnlyResolver())


def _labels(
    hits: dict[str, dict[str, HitVerdict]], grades: dict[str, FindingGrade] | None = None
) -> dict[str, ResolvedLabels]:
    grades = grades or {}
    return {
        CASE.case_id: ResolvedLabels(
            hits=hits,
            grades=grades,
            grade_labeler=dict.fromkeys(grades, "import:grid2/BRIEF.md"),
            import_grades=dict(grades),
        )
    }


def test_bounds_equal_when_nothing_undecided() -> None:
    hit = finding(1, "src/a.py:3")
    miss = finding(2, "src/zzz.py")
    row = _row(Recipe(name="r", reviewers=("a",)), make_run(CASE, 1, review("a", (hit, miss))))[0]
    labels = _labels({hit.content_key: {"B1": HitVerdict.HIT}})
    metrics = row_metrics(row, labels, SET)
    assert metrics.bug_hits == Bounds(1, 1) and metrics.recall.exact
    assert metrics.bug_slots == 2 and metrics.runs_with_hit == Bounds(1, 1)
    assert metrics.matched_nothing == 1  # the src/zzz.py finding: decided miss for both bugs
    assert metrics.findings_per_run == 2


def test_matched_nothing_excludes_undecided_and_bounds_split() -> None:
    open_finding = finding(1, None)  # cites no path: candidate for both bugs, unlabeled
    row = _row(Recipe(name="r", reviewers=("a",)), make_run(CASE, 1, review("a", (open_finding,))))[0]
    metrics = row_metrics(row, _labels({}), SET)
    assert metrics.matched_nothing == 0
    assert metrics.undecided == 2
    assert metrics.bug_hits == Bounds(0, 2) and not metrics.recall.exact


def test_pool_is_the_mean_of_members() -> None:
    hit = finding(1, "src/a.py")
    run = make_run(CASE, 1, review("a", (hit,)), review("b", ()))
    labels = _labels({hit.content_key: {"B1": HitVerdict.HIT, "B2": HitVerdict.MISS}})
    pool = row_metrics(_row(Recipe(name="p", reviewers=("a", "b"), pool=True), run)[0], labels, SET)
    single_a = row_metrics(_row(Recipe(name="a", reviewers=("a",)), run)[0], labels, SET)
    single_b = row_metrics(_row(Recipe(name="b", reviewers=("b",)), run)[0], labels, SET)
    assert pool.bug_hits.low == (single_a.bug_hits.low + single_b.bug_hits.low) / 2
    assert pool.findings_per_run == 0.5
    assert single_a.cost_per_run is not None and single_b.cost_per_run is not None
    assert pool.cost_per_run == (single_a.cost_per_run + single_b.cost_per_run) / 2


def test_live_entries_are_ungraded() -> None:
    graded = finding(1, "src/a.py")
    imported = review("a", (graded,))
    live = review("a", (graded,), model="live", source=LIVE_SOURCE)
    labels = _labels({}, {graded.content_key: FindingGrade.REAL})
    resolver = StubResolver({"a": identity_of(live)})
    rows = _row(
        Recipe(name="r", reviewers=("a",)), make_run(CASE, 1, imported, live), resolver=resolver
    )
    by_tag = {row.source_tag: row_metrics(row, labels, SET) for row in rows}
    assert by_tag["imported"].graded == 1 and by_tag["imported"].real_share == 1.0
    assert by_tag["live"].graded == 0 and by_tag["live"].real_share is None


def test_leaks_and_other_set_entries_counted() -> None:
    run = make_run(CASE, 1, review("a", (), case_set="other@v2"))
    metrics = row_metrics(_row(Recipe(name="r", reviewers=("a",)), run)[0], _labels({}), SET)
    assert metrics.leaks == {"not_scanned": 1}
    assert metrics.other_set_entries == 1
