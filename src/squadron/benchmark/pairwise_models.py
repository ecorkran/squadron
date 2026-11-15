"""The pairwise section's models (slice 426 D17).

Every number is a measured signal: strengths from the pairwise fit, a paired interval per pair
of configs, and the counts of what was and was not judged. No field combines these with the
objective grade into one score, and a test reads this module's fields to keep it so.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from squadron.benchmark.pair_row import PairRow


class PairwiseConfigRow(BaseModel):
    """One config's strength and tallies over the judged pairs."""

    model_config = ConfigDict(frozen=True)

    label: str
    #: Canonical text of the config identity, which a pair's seed is derived from.
    identity: str
    #: ``None`` when the fit gives no finite value; ``reason`` then says why.
    strength: float | None
    reason: str | None
    wins: int
    losses: int
    ties: int
    inconsistent: int
    invalid: int
    forfeits: int
    pairs: int


class PairwiseReference(BaseModel):
    """The reference's strength: shown as a line, never ranked."""

    model_config = ConfigDict(frozen=True)

    strength: float | None
    reason: str | None


class PairwiseCounts(BaseModel):
    """What was and was not judged: cases judged, over size (with the limit), harness-absent,
    and pairs of judged cases with no record yet."""

    model_config = ConfigDict(frozen=True)

    judged: int
    over_size: int
    over_size_limit: int | None
    harness_absent: int
    pending: int


class OtherJudge(BaseModel):
    model_config = ConfigDict(frozen=True)

    alias: str
    prompt_hash: str
    judgments: int


class PairwiseSection(BaseModel):
    """The pairwise section for the latest judge, with the other judges listed."""

    model_config = ConfigDict(frozen=True)

    judge_alias: str
    prompt_hash: str
    configs: tuple[PairwiseConfigRow, ...]
    reference: PairwiseReference | None
    pairs: tuple[PairRow, ...]
    counts: PairwiseCounts
    others: tuple[OtherJudge, ...]
