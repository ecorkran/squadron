"""Undecided hit candidates, and recording a person's hit label (slice 430 D3).

A candidate is a (finding, bug) pair the location gate cannot decide and no label covers.
With recipes, the findings are those the recipes keep (upper bound: a finding a comb left
undecided can still be a hit). Without, every scored finding of the set's stored reviews.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from squadron.benchmark.recall.hit_rule import HitOutcome, resolve
from squadron.benchmark.recall.label_precedence import ResolvedLabels
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.recipe import Recipe
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.benchmark.recall.report_build import resolved_labels
from squadron.benchmark.recall.scoring import SCORED_SEVERITIES, recipe_outputs
from squadron.benchmark.recall.scoring_select import StageIdentityResolver
from squadron.metrology.recall_case_models import KnownBug, RealBugCase
from squadron.metrology.recall_label_models import HitVerdict, LabelerKind, RecallLabels, labeler_name
from squadron.metrology.recall_run_models import RecallFinding, RecallRun

ALL_STORED = "(stored reviews)"


@dataclass
class Candidate:
    case: RealBugCase
    bug: KnownBug
    finding: RecallFinding
    #: (recipe or ALL_STORED, run index) pairs the finding appears in.
    seen_in: set[tuple[str, int]] = field(default_factory=set[tuple[str, int]])


def undecided_candidates(
    store: RecallRecordStore,
    cases: list[RealBugCase],
    recipes: list[Recipe],
    run_indexes: list[int],
    resolver: StageIdentityResolver,
) -> list[Candidate]:
    case_ids = [case.case_id for case in cases]
    runs = {(run.case_id, run.run_index): run for run in store.list_runs(case_ids)}
    labels = resolved_labels(store.list_labels(case_ids))
    found: dict[tuple[str, str, str], Candidate] = {}
    for case, run_index, source, finding in _findings(cases, runs, recipes, run_indexes, resolver):
        case_labels = labels.get(case.case_id, ResolvedLabels())
        for bug in case.bugs:
            if resolve(finding, bug, case_labels) is not HitOutcome.UNDECIDED:
                continue
            key = (case.case_id, finding.content_key, bug.id)
            candidate = found.setdefault(key, Candidate(case, bug, finding))
            candidate.seen_in.add((source, run_index))
    return sorted(found.values(), key=lambda c: (c.case.name, c.bug.id, c.finding.content_key))


def _findings(
    cases: list[RealBugCase],
    runs: dict[tuple[str, int], RecallRun],
    recipes: list[Recipe],
    run_indexes: list[int],
    resolver: StageIdentityResolver,
) -> list[tuple[RealBugCase, int, str, RecallFinding]]:
    if not recipes:
        by_id = {case.case_id: case for case in cases}
        return [
            (by_id[run.case_id], run.run_index, ALL_STORED, finding)
            for run in runs.values()
            for entry in run.reviews.values()
            for finding in entry.findings
            if finding.severity in SCORED_SEVERITIES
        ]
    return [
        (pair.case, pair.run_index, row.label, finding)
        for recipe in recipes
        for row in recipe_outputs(recipe, cases, runs, run_indexes, resolver)
        for pair in row.pairs
        for reviewer in pair.reviewers
        for finding in reviewer.upper
    ]


def record_person_hit(
    store: RecallRecordStore,
    cases: list[RealBugCase],
    content_key: str,
    bug_id: str,
    verdict: HitVerdict,
    person: str,
    clock: Callable[[], datetime],
) -> RecallLabels:
    """Write (or rewrite) ``person:<person>``'s label record for the finding's case."""
    case = _case_of(store, cases, content_key)
    if bug_id not in {bug.id for bug in case.bugs}:
        raise RecallRefusal(f"case {case.name} has no bug {bug_id!r}")
    labeler = labeler_name(LabelerKind.PERSON, person)
    existing = store.get_labels(case.case_id, labeler)
    hits = {key: dict(bugs) for key, bugs in (existing.hits if existing else {}).items()}
    hits.setdefault(content_key, {})[bug_id] = verdict
    record = RecallLabels(
        case_id=case.case_id,
        labeler=labeler,
        labeler_kind=LabelerKind.PERSON,
        hits=hits,
        grades=dict(existing.grades) if existing else {},
        updated=clock(),
        notes=existing.notes if existing else None,
    )
    store.put_labels(record)
    return record


def _case_of(store: RecallRecordStore, cases: list[RealBugCase], content_key: str) -> RealBugCase:
    by_id = {case.case_id: case for case in cases}
    owners = {
        run.case_id
        for run in store.list_runs(list(by_id))
        for entry in run.reviews.values()
        if any(finding.content_key == content_key for finding in entry.findings)
    }
    if not owners:
        raise RecallRefusal(f"no stored finding has content key {content_key!r} in this set")
    if len(owners) > 1:
        raise RecallRefusal(f"content key {content_key!r} appears in several cases; pass --case")
    return by_id[owners.pop()]
