"""Implementation-replay and benchmark-run records (slice 424, Database / Storage Schema).

An ``ImplementationReplay`` is one config's producer-only run of one benchmark case; a
``BenchmarkRun`` is the resumable envelope over all of a benchmark's replays. The enums
(``ProducerOutcome`` and friends) live in ``benchmark_replay_enums`` and are defined once there.

Bounds on the leak scan's output are enforced by validators that raise: an oversized
excerpt or hit list is a caller bug and must never be truncated silently here.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import CandidateRejection
from squadron.metrology.benchmark_replay_enums import (
    AbsenceClass,
    BenchmarkStatus,
    LeakRule,
    LeakVerdict,
    ProducerOutcome,
)
from squadron.metrology.replay_models import ProducerConfigRef, PromptIdentity

MAX_LEAK_HITS = 20
MAX_LEAK_EXCERPT_CHARS = 300


class LeakHit(BaseModel):
    model_config = ConfigDict(frozen=True)

    rule: LeakRule
    tool: str
    excerpt: str

    @field_validator("excerpt")
    @classmethod
    def _excerpt_bounded(cls, value: str) -> str:
        if len(value) > MAX_LEAK_EXCERPT_CHARS:
            raise ValueError(
                f"leak excerpt is {len(value)} chars; the limit is {MAX_LEAK_EXCERPT_CHARS}"
            )
        return value


class LeakScanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: LeakVerdict
    rules_version: int
    tool_calls_seen: int
    hits: tuple[LeakHit, ...]
    #: Reason when the verdict is ``scan_unavailable``; empty otherwise.
    detail: str

    @field_validator("hits")
    @classmethod
    def _hits_bounded(cls, value: tuple[LeakHit, ...]) -> tuple[LeakHit, ...]:
        if len(value) > MAX_LEAK_HITS:
            raise ValueError(f"{len(value)} leak hits; the limit is {MAX_LEAK_HITS}")
        return value


class DiffRef(BaseModel):
    """A content-addressed pointer to a stored diff sidecar (D11)."""

    model_config = ConfigDict(frozen=True)

    sha256: str
    bytes: int
    files_changed: int


class ImplementationReplay(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_id: str
    case_set: str
    case_set_version: int
    sample: int
    config: ProducerConfigRef
    pipeline: str
    producer_step: str
    run_id: str
    outcome: ProducerOutcome
    absence: AbsenceClass | None
    failure_detail: str | None
    #: ``None`` only when the producer never ran.
    leak: LeakScanResult | None
    diff: DiffRef | None
    commit_sha: str | None
    environment: EnvironmentIdentity | None
    prompt: PromptIdentity | None
    #: ``(relative path, sha256)`` of each instruction file in the tree at the start commit; the
    #: hash is a marker (``outside-tree``, ``unreadable``) for a file that could not be hashed.
    instruction_files: tuple[tuple[str, str], ...]
    cost_usd: float | None
    turns: int | None
    wall_seconds: float
    squadron_version: str
    created_at: datetime


class CaseDrop(BaseModel):
    """A case whose re-qualification failed: reported, never a replay outcome (D10)."""

    model_config = ConfigDict(frozen=True)

    case_id: str
    reason: CandidateRejection | str
    environment_digest: str


class BenchmarkRun(BaseModel):
    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_set: str
    case_set_version: int
    configs: tuple[ProducerConfigRef, ...]
    samples: int
    status: BenchmarkStatus
    #: The latest invocation's caps.
    run_cap_usd: float
    per_replay_cap_usd: float
    #: Known spend across invocations.
    spent_usd: float
    unpriced_replays: int
    case_drops: tuple[CaseDrop, ...]
    started_at: datetime
    updated_at: datetime
