"""Assemble the recall report from stored records (slice 430). Reads through the store only."""

from __future__ import annotations

from collections import defaultdict

from squadron.benchmark.recall.label_precedence import resolve_labels
from squadron.benchmark.recall.recall_store import RecallRecordStore, RecallStoreError
from squadron.benchmark.recall.report_render import ReportData, ReportRow
from squadron.benchmark.recall.scoring import recipe_outputs, unfiltered
from squadron.benchmark.recall.scoring_metrics import LabelsByCase, row_metrics
from squadron.benchmark.recall.scoring_paired import paired_lines
from squadron.benchmark.recall.scoring_select import StageIdentityResolver
from squadron.metrology.recall_case_models import RealBugCase, RecallCaseSet
from squadron.metrology.recall_label_models import RecallLabels
from squadron.metrology.recall_run_models import RecallRun
from squadron.recipes.recipe import Recipe


def set_label(case_set: RecallCaseSet) -> str:
    """``<name>@v<version>``: the entry ``case_set`` value and the pair-seed benchmark id."""
    return f"{case_set.name}@v{case_set.version}"


def build_report(
    store: RecallRecordStore,
    recipes: list[Recipe],
    case_set: RecallCaseSet,
    run_indexes: list[int],
    resolver: StageIdentityResolver,
) -> ReportData:
    cases = _cases(store, case_set)
    case_ids = [case.case_id for case in cases]
    runs = {(run.case_id, run.run_index): run for run in store.list_runs(case_ids)}
    labels = resolved_labels(store.list_labels(case_ids))
    label = set_label(case_set)
    rows = [
        row
        for recipe in recipes
        for row in _recipe_rows(recipe, cases, runs, run_indexes, resolver, labels, label)
    ]
    return ReportData(
        case_set=case_set,
        known_bugs=sum(len(case.bugs) for case in cases),
        run_indexes=run_indexes,
        rows=rows,
        paired=paired_lines([row.outputs for row in rows], labels, run_indexes, label),
    )


def _recipe_rows(
    recipe: Recipe,
    cases: list[RealBugCase],
    runs: dict[tuple[str, int], RecallRun],
    run_indexes: list[int],
    resolver: StageIdentityResolver,
    labels: LabelsByCase,
    label: str,
) -> list[ReportRow]:
    """A recipe's rows; with a filter each also carries the row scored without it (437 D8)."""
    rows = recipe_outputs(recipe, cases, runs, run_indexes, resolver)
    if recipe.keep_categories is None:
        return [ReportRow(outputs=row, metrics=row_metrics(row, labels, label)) for row in rows]
    # Identities do not depend on the filter, so the unfiltered pass has the same rows.
    before = {
        row.identity: row
        for row in recipe_outputs(unfiltered(recipe), cases, runs, run_indexes, resolver)
    }
    return [
        ReportRow(
            outputs=row,
            metrics=row_metrics(row, labels, label),
            unfiltered=row_metrics(before[row.identity], labels, label),
        )
        for row in rows
    ]


def resolved_labels(records: list[RecallLabels]) -> LabelsByCase:
    by_case: dict[str, list[RecallLabels]] = defaultdict(list)
    for record in records:
        by_case[record.case_id].append(record)
    return {case_id: resolve_labels(found) for case_id, found in by_case.items()}


def _cases(store: RecallRecordStore, case_set: RecallCaseSet) -> list[RealBugCase]:
    cases: list[RealBugCase] = []
    for case_id in case_set.case_ids:
        case = store.get_case(case_id)
        if case is None:
            raise RecallStoreError(f"Case set {set_label(case_set)} names missing case {case_id}")
        cases.append(case)
    return cases
