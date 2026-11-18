"""Build the import plan for the hand-run results folder (slice 430 D10).

Part 1 reads the review outputs, part 2 the comb outputs, part 3 the grading passes and the
person overrides. The plan is returned whole; nothing is written to the store here.
"""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from squadron.benchmark.recall.hand_run_combs import plan_combs
from squadron.benchmark.recall.hand_run_labels import plan_labels
from squadron.benchmark.recall.hand_run_overrides import plan_overrides
from squadron.benchmark.recall.hand_run_reviews import plan_reviews
from squadron.benchmark.recall.import_plan import ImportContext, ImportPlan
from squadron.metrology.recall_case_models import RealBugCase


def build_import_plan(
    results_dir: Path,
    cases: Iterable[RealBugCase],
    case_set: str,
    overrides_path: Path | None = None,
) -> ImportPlan:
    """Every record the import of *results_dir* would write, plus what it skipped.

    *overrides_path* is the person overrides file; ``None`` imports no overrides.
    """
    by_hand_id = {case.hand_run_id: case for case in cases if case.hand_run_id is not None}
    context = ImportContext(cases_by_hand_id=by_hand_id, case_set=case_set)
    plan = ImportPlan()
    plan_reviews(results_dir, context, plan)
    plan_combs(results_dir, context, plan)
    pass_labels = plan_labels(results_dir, by_hand_id, plan)
    if overrides_path is not None:
        plan_overrides(overrides_path, by_hand_id, pass_labels, plan)
    return plan
