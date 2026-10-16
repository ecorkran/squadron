"""Values of the ``sq replay report`` core (slice 177 D7)."""

from __future__ import annotations

from dataclasses import dataclass

from squadron.metrology.replay_models import JudgeRef, ModelRef, ProducerConfigRef, ReplayPhase
from squadron.stats.json_support import to_json_dict

#: The pairwise contestant that is not a producer config: the artifact as first written.
ORIGINAL_LABEL = "original"


@dataclass(frozen=True)
class ConfigRow:
    """One config (D1: alias, model, profile, effort sent) in one table; or the original."""

    label: str
    config: ProducerConfigRef | None  # None for the original
    n: int  # replays of this config
    failed: int
    accepted: int
    accepted_of: int  # n - failed
    median_rounds: float | None  # accepted replays only
    median_cost_usd: float | None
    priced: int  # priced records over all replays
    llm_actions: int
    median_wall_seconds: float | None
    strength: float | None  # Bradley-Terry
    strength_reason: str | None  # why strength is None, when it is
    wins: int
    losses: int
    ties: int
    pairs: int  # recorded pairs involving this contestant
    invalid: int
    inconsistent: int
    below_floor: bool
    rank: int | None  # by strength among configs at or above the floor


@dataclass(frozen=True)
class ReplayTable:
    """One table per (phase, reviewer, judge)."""

    phase: ReplayPhase
    reviewer: ModelRef
    judge: JudgeRef | None  # None when no pair has been judged yet
    rows: tuple[ConfigRow, ...]
    slices: tuple[int, ...]
    consistent_pairs: int  # pairs whose two orders agreed
    verdict_pairs: int  # pairs with a verdict in both orders
    prompt_identities: tuple[str, ...]
    strengths_converged: bool
    strength_components: int
    self_preference: bool  # the judge's model is also a contestant's model


@dataclass(frozen=True)
class ReplayReport:
    min_n: int
    tables: tuple[ReplayTable, ...]

    def to_json_dict(self) -> dict[str, object]:
        return to_json_dict(self)
