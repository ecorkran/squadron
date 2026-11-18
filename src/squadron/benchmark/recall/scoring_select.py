"""Which stored entries a recipe stage uses (slice 430 D4 entry selection). Pure.

A live entry matches a recipe stage when its identity, (``config_key``, ``effort_sent``),
equals what the injected resolver gives for the stage's alias. An imported entry matches
when its ``alias`` equals the recipe's alias. Comb chains are walked stage by stage, so a
two-stage chain matches only under its matching first stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from squadron.core.models import Effort
from squadron.metrology.recall_run_models import (
    COMB_KEY_SEPARATOR,
    RecallRun,
    StageEntry,
    StageKind,
    chain_key,
)


@dataclass(frozen=True)
class StageIdentity:
    """D4's report identity of a stage: ``config_key`` and the effort actually sent."""

    config_key: str
    effort_sent: Effort | None


class StageIdentityResolver(Protocol):
    """The live identity an alias resolves to now; ``None`` when no live identity is known."""

    def resolve(self, alias: str, stage_kind: StageKind) -> StageIdentity | None: ...


class ImportOnlyResolver:
    """Knows no live aliases, so only imported entries match (by alias)."""

    def resolve(self, alias: str, stage_kind: StageKind) -> StageIdentity | None:
        return None


def identity_of(entry: StageEntry) -> StageIdentity:
    return StageIdentity(entry.config.config_key, entry.effort_sent)


def entry_matches(
    entry: StageEntry, alias: str, kind: StageKind, resolver: StageIdentityResolver
) -> bool:
    if not entry.is_live:
        return entry.alias == alias
    wanted = resolver.resolve(alias, kind)
    return wanted is not None and identity_of(entry) == wanted


def matching_reviews(
    run: RecallRun, alias: str, resolver: StageIdentityResolver
) -> list[tuple[str, StageEntry]]:
    """(entry key, entry) of every review in *run* that serves the recipe's *alias*."""
    return [
        (key, entry)
        for key, entry in sorted(run.reviews.items())
        if entry_matches(entry, alias, StageKind.REVIEW, resolver)
    ]


def matching_chains(
    run: RecallRun, review_key: str, aliases: tuple[str, ...], resolver: StageIdentityResolver
) -> list[tuple[StageEntry, ...]]:
    """Every stored comb chain under *review_key* whose stages serve *aliases*, in order."""
    chains: list[tuple[tuple[str, ...], tuple[StageEntry, ...]]] = [((), ())]
    for alias in aliases:
        extended: list[tuple[tuple[str, ...], tuple[StageEntry, ...]]] = []
        for keys, entries in chains:
            for slot, entry in sorted(run.combs.items()):
                expected = f"{review_key}{COMB_KEY_SEPARATOR}{chain_key([*keys, entry.entry_key])}"
                if slot == expected and entry_matches(entry, alias, StageKind.COMB, resolver):
                    extended.append(((*keys, entry.entry_key), (*entries, entry)))
        chains = extended
    return [entries for _, entries in chains]
