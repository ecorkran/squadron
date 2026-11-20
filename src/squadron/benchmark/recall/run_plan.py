"""The stages ``run`` still has to call for recipes over a case set (slice 430 D2, D4, D9).

Each recipe expands, per case and run index, to one review stage per reviewer and one comb
stage per chain prefix, keyed by live ``entry_key``s. A stage is already stored only when a
live entry sits at that key; imported entries never count. With ``--retry-harness`` a live
harness failure or a dropped-leak entry is pending again, and the entry it replaces is
carried so the loop can move it to ``superseded``.
"""

from __future__ import annotations

import dataclasses
import hashlib
from collections.abc import Callable
from dataclasses import dataclass

from squadron.core.models import Effort
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import (
    DROPPED_LEAK_VERDICTS,
    RecallRun,
    StageConfig,
    StageEntry,
    StageKind,
    StageOutcome,
    chain_key,
    comb_slot,
    entry_key,
    run_record_id,
)
from squadron.recipes.recipe import Recipe

ConfigFor = Callable[[str, StageKind], tuple[StageConfig, Effort | None]]


@dataclass(frozen=True)
class PendingStage:
    case: RealBugCase
    run_index: int
    reviewer: str
    kind: StageKind
    #: The stage's own alias: the reviewer for a review, the last comb for a comb.
    alias: str
    config: StageConfig
    effort_configured: Effort | None
    review_key: str
    #: Comb entry keys of the chain, this stage last; empty for a review.
    chain: tuple[str, ...]
    #: The live entry a ``--retry-harness`` call replaces.
    replaces: StageEntry | None = None

    @property
    def record_id(self) -> str:
        return run_record_id(self.case.case_id, self.run_index)

    @property
    def slot(self) -> str:
        """Where the entry goes: ``reviews[slot]`` or ``combs[slot]``."""
        return (
            self.review_key
            if self.kind is StageKind.REVIEW
            else comb_slot(self.review_key, chain_key(self.chain))
        )

    @property
    def parent_slot(self) -> str | None:
        """The comb slot this comb reads; ``None`` when its input is the review."""
        if self.kind is StageKind.REVIEW or len(self.chain) == 1:
            return None
        return comb_slot(self.review_key, chain_key(self.chain[:-1]))

    @property
    def input_slot(self) -> str | None:
        """The slot this stage reads: the review for a first comb; ``None`` for a review."""
        if self.kind is StageKind.REVIEW:
            return None
        return self.parent_slot or self.review_key

    @property
    def file_key(self) -> str:
        """A filename-safe stage key for ``recall-out/<record id>/<file key>.json``."""
        if self.kind is StageKind.REVIEW:
            return self.review_key
        return hashlib.sha256(self.slot.encode("utf-8")).hexdigest()


def expand_pending(
    recipes: list[Recipe],
    cases: list[RealBugCase],
    run_indexes: list[int],
    runs: dict[tuple[str, int], RecallRun],
    config_for: ConfigFor,
    retry_harness: bool = False,
) -> list[PendingStage]:
    """Every stage the recipes need that has no current live entry, in dispatch order.

    A comb whose parent stage is pending is pending too: its stored entry was built from
    the parent's old output, so it is replaced (and moved to ``superseded``) after the rerun.
    """
    pending: list[PendingStage] = []
    pending_slots: set[tuple[str, str]] = set()
    seen: set[tuple[str, str]] = set()
    for case in cases:
        for run_index in run_indexes:
            run = runs.get((case.case_id, run_index))
            for recipe in recipes:
                for stage in _recipe_stages(recipe, case, run_index, config_for):
                    if (stage.record_id, stage.slot) in seen:
                        continue
                    seen.add((stage.record_id, stage.slot))
                    stale = (stage.record_id, stage.input_slot) in pending_slots
                    found = _pending_form(stage, run, retry_harness, stale)
                    if found is not None:
                        pending.append(found)
                        pending_slots.add((stage.record_id, stage.slot))
    return pending


def _recipe_stages(
    recipe: Recipe, case: RealBugCase, run_index: int, config_for: ConfigFor
) -> list[PendingStage]:
    """Per reviewer: its review, then one comb stage per chain prefix."""
    stages: list[PendingStage] = []
    for reviewer in recipe.reviewers:
        config, effort = config_for(reviewer, StageKind.REVIEW)
        review = PendingStage(
            case=case,
            run_index=run_index,
            reviewer=reviewer,
            kind=StageKind.REVIEW,
            alias=reviewer,
            config=config,
            effort_configured=effort,
            review_key=entry_key(config, effort),
            chain=(),
        )
        stages.append(review)
        chain: tuple[str, ...] = ()
        for comb in recipe.combs:
            comb_config, comb_effort = config_for(comb, StageKind.COMB)
            chain = (*chain, entry_key(comb_config, comb_effort))
            stages.append(
                dataclasses.replace(
                    review,
                    kind=StageKind.COMB,
                    alias=comb,
                    config=comb_config,
                    effort_configured=comb_effort,
                    chain=chain,
                )
            )
    return stages


def _pending_form(
    stage: PendingStage, run: RecallRun | None, retry_harness: bool, stale: bool
) -> PendingStage | None:
    """``None`` when a current live entry is stored; else the stage, with what it replaces."""
    if run is None:
        return stage
    stored = (run.reviews if stage.kind is StageKind.REVIEW else run.combs).get(stage.slot)
    if stored is None or not stored.is_live:
        return stage
    if stale or (retry_harness and is_retryable(stored)):
        return dataclasses.replace(stage, replaces=stored)
    return None


def is_retryable(entry: StageEntry) -> bool:
    """D8: harness failures and dropped-leak entries rerun under ``--retry-harness``."""
    return entry.outcome is StageOutcome.HARNESS_FAILURE or entry.leak in DROPPED_LEAK_VERDICTS
