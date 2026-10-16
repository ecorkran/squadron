"""Payload models for producer replays and pairwise judgments (slice 177 D9).

Two record types behind the 320 store envelope: a replay outcome and a judgment are
different facts with different lifetimes, and a "score" is derived from them. The
``RECORD_TYPE_*`` constants and the envelope's sibling fields stay in ``models.py``.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel

from squadron.core.usage import UsageRecord
from squadron.metrology.project_id import ProjectId

#: A pairwise contestant reference is a replay record id, or this prefix plus the
#: commit sha that first added the original artifact.
ORIGINAL_CONTESTANT_PREFIX = "original:"


class ReplayPhase(StrEnum):
    """The phases a replay regenerates."""

    DESIGN = "design"
    TASKS = "tasks"


class ReplayOutcome(StrEnum):
    """How one replayed config's run ended (D4 outcome table)."""

    ACCEPTED = "accepted"
    EXHAUSTED = "exhausted"
    FAILED = "failed"


class JudgePick(StrEnum):
    """One judge call's verdict, read from the ``WINNER:`` line; ``INVALID`` when absent."""

    A = "A"
    B = "B"
    TIE = "TIE"
    INVALID = "INVALID"


class PairOutcome(StrEnum):
    """A pair's outcome after both orders (D5). Inconsistent picks are not wins."""

    A = "A"
    B = "B"
    TIE = "TIE"
    INCONSISTENT = "INCONSISTENT"
    INVALID = "INVALID"


class ModelRef(BaseModel):
    """A model by alias and the concrete model id it resolved to."""

    alias: str
    model: str


class ProducerConfigRef(BaseModel):
    """A producer config (D1): an alias, its model and profile, and the effort sent."""

    alias: str
    model: str
    profile: str | None
    effort_sent: str | None


class JudgeRef(BaseModel):
    """Judge identity: alias, model, and the hash of the packaged judge prompt."""

    alias: str
    model: str
    prompt_hash: str


class PromptIdentity(BaseModel):
    """The ``metadata["prompt"]`` value a dispatch records (D8)."""

    sha256: str
    source: str
    squadron_version: str
    cf_version: str | None
    guide_version: str | None


class JudgeCall(BaseModel):
    """One judge call: its pick and the tail of its raw output."""

    pick: JudgePick
    raw_tail: str


class ProducerReplay(BaseModel):
    """One config's regeneration of one artifact — a ``producer_replay`` payload."""

    # sha256 of (project_id, phase, slice_index, start_sha, reviewer alias, max_revisions)
    replay_set: str
    project_id: ProjectId
    phase: ReplayPhase
    slice_index: int
    slice_name: str
    original_sha: str
    start_sha: str
    config: ProducerConfigRef
    reviewer: ModelRef
    max_revisions: int
    run_id: str
    outcome: ReplayOutcome
    failure_class: str | None
    rounds: int | None
    first_verdict: str | None
    cost_usd: float | None
    priced: tuple[int, int]
    wall_seconds: float
    prompt: PromptIdentity | None
    task_prompt: str | None  # build_context stdout, for the judge
    first_draft: str | None
    final_text: str | None
    squadron_version: str
    created_at: datetime


class PairwiseJudgment(BaseModel):
    """One pair judged in both orders — a ``pairwise_judgment`` payload."""

    replay_set: str
    project_id: ProjectId  # the store filters judgments by project, as it does replays
    phase: ReplayPhase
    judge: JudgeRef
    a: str  # a replay record id or ORIGINAL_CONTESTANT_PREFIX + sha
    b: str
    first_call: JudgeCall
    second_call: JudgeCall
    outcome: PairOutcome
    first_usage: UsageRecord | None
    second_usage: UsageRecord | None
    created_at: datetime
