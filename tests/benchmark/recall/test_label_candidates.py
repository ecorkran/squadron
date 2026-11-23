"""Label candidates for a recipe with a category filter (slice 437 D8)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.recall.label_candidates import undecided_candidates
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.scoring_select import ImportOnlyResolver
from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import RecallRun
from squadron.metrology.store import MetrologyStore
from squadron.recipes.recipe import Recipe
from tests.benchmark.recall.scoring_support import finding, make_case, make_run, review

NOW = datetime(2026, 11, 23, 12, 0, tzinfo=UTC)


def _store(tmp_path: Path, case: RealBugCase, run: RecallRun) -> RecallRecordStore:
    store = RecallRecordStore(MetrologyStore(tmp_path / "store"), clock=lambda: NOW)
    store.write_case(case)
    store.put_run(run)
    return store


def test_candidates_include_a_not_gating_finding(tmp_path: Path) -> None:
    case = make_case(bug_files=("src/a.py", "src/b.py"))
    gate = finding(1, "src/a.py", category=ReviewCategory.CORRECTNESS)
    debt = finding(2, "src/b.py", category=ReviewCategory.TEST_DEBT)
    run = make_run(case, 1, review("a", (gate, debt)))
    store = _store(tmp_path, case, run)
    recipe = Recipe(name="r", reviewers=("a",), keep_categories=(ReviewCategory.CORRECTNESS,))
    found = undecided_candidates(store, [case], [recipe], [1], ImportOnlyResolver())
    assert {c.finding.finding_id for c in found} == {"F1", "F2"}
