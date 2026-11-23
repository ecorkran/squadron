"""Recipe outputs per (case, run): comb chains, fan-out and pool composition (D2, D3, D8).

Pure: callers pass the cases, run records and a ``StageIdentityResolver``. Each distinct
combination of stage identities a recipe finds becomes its own row; a recipe with more
than one row is flagged. Only CONCERN and FAIL findings are scored, the set the hand-run
comb, grading and tables used.
"""

from __future__ import annotations

import hashlib
import itertools
from collections import Counter
from dataclasses import dataclass, field

from squadron.benchmark.recall.scoring_select import (
    StageIdentity,
    StageIdentityResolver,
    identity_of,
    matching_chains,
    matching_reviews,
)
from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import (
    DROPPED_LEAK_VERDICTS,
    CombVerdict,
    RecallFinding,
    RecallRun,
    StageEntry,
    StageOutcome,
)
from squadron.recipes.kept_findings import split_by_category
from squadron.recipes.recipe import Recipe
from squadron.review.models import SCORED_SEVERITIES

HARNESS_DROP = "harness"
LEAK_DROP_PREFIX = "leak:"
_ROW_KEY_DIGITS = 8

#: One reviewer's identities: its review, then each comb stage.
ReviewerIdentity = tuple[StageIdentity, ...]


@dataclass(frozen=True)
class ReviewerOutput:
    """One reviewer's final kept findings for one (case, run), lower and upper bound."""

    alias: str
    lower: tuple[RecallFinding, ...]
    upper: tuple[RecallFinding, ...]
    undecided_comb: int
    entries: tuple[StageEntry, ...]
    #: Scored findings the recipe's category filter left out (437 D8); not in lower or upper.
    not_gating: tuple[RecallFinding, ...] = ()


@dataclass(frozen=True)
class PairOutput:
    case: RealBugCase
    run_index: int
    reviewers: tuple[ReviewerOutput, ...]

    @property
    def entries(self) -> tuple[StageEntry, ...]:
        return tuple(entry for reviewer in self.reviewers for entry in reviewer.entries)


@dataclass
class RowOutputs:
    """One report row: a recipe at one combination of stage identities."""

    recipe: Recipe
    identity: tuple[ReviewerIdentity, ...]
    flagged: bool = False
    pairs: list[PairOutput] = field(default_factory=list[PairOutput])
    dropped: Counter[str] = field(default_factory=Counter[str])
    left_out: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])

    @property
    def key(self) -> str:
        digest = hashlib.sha256(repr(self.identity).encode("utf-8")).hexdigest()
        return f"{self.recipe.name}#{digest[:_ROW_KEY_DIGITS]}"

    @property
    def label(self) -> str:
        if not self.flagged:
            return self.recipe.name
        return f"{self.recipe.name} [{self.source_tag} {self.key.rsplit('#', 1)[1]}]"

    @property
    def source_tag(self) -> str:
        sources = {entry.is_live for pair in self.pairs for entry in pair.entries}
        return {frozenset({True}): "live", frozenset({False}): "imported"}.get(
            frozenset(sources), "mixed"
        )


def unfiltered(recipe: Recipe) -> Recipe:
    """*recipe* without its category filter: the pass that gives before-filter numbers."""
    return recipe.model_copy(update={"keep_categories": None})


def recipe_outputs(
    recipe: Recipe,
    cases: list[RealBugCase],
    runs: dict[tuple[str, int], RecallRun],
    run_indexes: list[int],
    resolver: StageIdentityResolver,
) -> list[RowOutputs]:
    """Every row *recipe* yields over *cases* × *run_indexes*, in first-seen order."""
    variants: dict[tuple[str, int], dict[tuple[ReviewerIdentity, ...], PairOutput]] = {}
    rows: dict[tuple[ReviewerIdentity, ...], RowOutputs] = {}
    for case, run_index in itertools.product(cases, run_indexes):
        run = runs.get((case.case_id, run_index))
        found = {} if run is None else _pair_variants(recipe, case, run, resolver)
        variants[(case.case_id, run_index)] = found
        for identity in found:
            rows.setdefault(identity, RowOutputs(recipe=recipe, identity=identity))
    for row in rows.values():
        row.flagged = len(rows) > 1
        for case, run_index in itertools.product(cases, run_indexes):
            pair = variants[(case.case_id, run_index)].get(row.identity)
            if pair is None:
                row.left_out.append((case.name, run_index))
                continue
            reason = drop_reason(pair.entries)
            if reason is not None:
                row.dropped[reason] += 1
                continue
            row.pairs.append(pair)
    if not rows:
        empty = RowOutputs(recipe=recipe, identity=())
        empty.left_out = [(case.name, index) for case, index in itertools.product(cases, run_indexes)]
        return [empty]
    return list(rows.values())


def drop_reason(entries: tuple[StageEntry, ...]) -> str | None:
    """``harness`` or ``leak:<verdict>`` when the pair is dropped from every recipe (D8)."""
    for entry in entries:
        if entry.outcome is StageOutcome.HARNESS_FAILURE:
            return HARNESS_DROP
    for entry in entries:
        if entry.leak in DROPPED_LEAK_VERDICTS:
            return f"{LEAK_DROP_PREFIX}{entry.leak.value}"
    return None


def _pair_variants(
    recipe: Recipe, case: RealBugCase, run: RecallRun, resolver: StageIdentityResolver
) -> dict[tuple[ReviewerIdentity, ...], PairOutput]:
    """Each combination of the reviewers' matching (review, chain) choices."""
    per_reviewer: list[list[ReviewerOutput]] = []
    for alias in recipe.reviewers:
        if alias in recipe.reviewers_with_options():
            # A stored entry carries no record of the options it ran with: a live `haiku`
            # entry ran with tools and an imported one by alias only, so neither can stand
            # in for the reviewer with options. Left out until #393 stores them.
            return {}
        choices = [
            reviewer_output(alias, review, chain, keep=recipe.keep_categories)
            for key, review in matching_reviews(run, alias, resolver)
            for chain in matching_chains(run, key, recipe.combs, resolver)
        ]
        if not choices:
            return {}
        per_reviewer.append(choices)
    found: dict[tuple[ReviewerIdentity, ...], PairOutput] = {}
    for combo in itertools.product(*per_reviewer):
        identity = tuple(tuple(identity_of(entry) for entry in output.entries) for output in combo)
        found.setdefault(identity, PairOutput(case=case, run_index=run.run_index, reviewers=combo))
    return found


def reviewer_output(
    alias: str,
    review: StageEntry,
    chain: tuple[StageEntry, ...],
    *,
    keep: tuple[ReviewCategory, ...] | None = None,
) -> ReviewerOutput:
    """Walk the chain: a stage decides only what the previous stage kept (D3).

    *keep* is the recipe's category filter (437 D8): findings it does not keep are
    ``not_gating`` and enter neither bound. A recipe never has both a filter and combs.
    """
    scored = [f for f in review.findings if f.severity in SCORED_SEVERITIES]
    if review.outcome is not StageOutcome.OK:
        scored = []
    gating, not_gating = split_by_category(scored, keep)
    findings = list(gating)
    state = {finding.finding_id: CombVerdict.KEEP for finding in findings}
    for comb in chain:
        if comb.outcome is not StageOutcome.OK:
            # A failed comb has no output: zero kept from here on.
            state = dict.fromkeys(state, CombVerdict.DROP)
            continue
        for finding_id, verdict in state.items():
            if verdict is CombVerdict.KEEP:
                decision = comb.decisions.get(finding_id)
                state[finding_id] = CombVerdict.UNDECIDED if decision is None else decision.verdict
    lower = tuple(f for f in findings if state[f.finding_id] is CombVerdict.KEEP)
    upper = tuple(f for f in findings if state[f.finding_id] is not CombVerdict.DROP)
    return ReviewerOutput(
        alias=alias,
        lower=lower,
        upper=upper,
        undecided_comb=len(upper) - len(lower),
        entries=(review, *chain),
        not_gating=not_gating,
    )
