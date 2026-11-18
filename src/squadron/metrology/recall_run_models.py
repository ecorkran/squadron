"""Recall run records: one per (case, run index), holding every stage entry (slice 430 D4-D8).

Keys are deterministic: ``config_key`` hashes the stage identity fields, ``entry_key`` adds
the configured effort (so ``run`` can tell distinct pending calls apart), and a comb entry
lives under ``"<entry_key>|<chain_key>"`` because a tuple cannot be a JSON object key.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict

from squadron.core.finding_categories import ReviewCategory
from squadron.core.models import Effort
from squadron.core.usage import CostBasis
from squadron.metrology.benchmark_replay_enums import LeakVerdict

#: The one marker for a field whose value the source did not record (D10).
UNKNOWN_MARKER = "unknown"
CHAIN_SEPARATOR = ">"
COMB_KEY_SEPARATOR = "|"
RECALL_RUN_ID_PREFIX = "rbrun-"
_ID_HEX_DIGITS = 12
_WHITESPACE = re.compile(r"\s+")

Unknown = Literal["unknown"]


class StageKind(StrEnum):
    REVIEW = "review"
    COMB = "comb"


class CombVerdict(StrEnum):
    KEEP = "KEEP"
    DROP = "DROP"
    UNDECIDED = "UNDECIDED"


class StageOutcome(StrEnum):
    """D8: ``config_failure`` is a miss for the config; ``harness_failure`` drops the pair."""

    OK = "ok"
    CONFIG_FAILURE = "config_failure"
    HARNESS_FAILURE = "harness_failure"


class RecallLeakVerdict(StrEnum):
    """424's scan verdicts (values taken from ``LeakVerdict``) plus recall's two (D6)."""

    LEAKED = LeakVerdict.LEAKED.value
    NO_LEAK_DETECTED = LeakVerdict.NO_LEAK_DETECTED.value
    SCAN_UNAVAILABLE = LeakVerdict.SCAN_UNAVAILABLE.value
    CONFINED = "confined"
    NOT_SCANNED = "not_scanned"


#: Verdicts that drop an entry's (case, run) from every recipe, like a harness failure.
DROPPED_LEAK_VERDICTS = frozenset({RecallLeakVerdict.LEAKED, RecallLeakVerdict.SCAN_UNAVAILABLE})


def _sha256_json(value: object) -> str:
    canonical = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class StageConfig(BaseModel):
    """Stage identity fields (D4); ``None`` = unset by the alias, ``unknown`` = not recorded."""

    model_config = ConfigDict(frozen=True)

    model: str | None
    profile: str | None
    template_hash: str | None
    tool_use: bool | Unknown | None
    max_output_tokens: int | Unknown | None

    @property
    def config_key(self) -> str:
        """sha256 of the five identity fields; alias and configured effort never enter."""
        return _sha256_json(
            [self.model, self.profile, self.template_hash, self.tool_use, self.max_output_tokens]
        )


class StageUsage(BaseModel):
    model_config = ConfigDict(frozen=True)

    cost_usd: float | None = None
    cost_basis: CostBasis | None = None
    duration_s: float | None = None
    turns: int | None = None
    tool_calls: int | None = None


class RecallFinding(BaseModel):
    """A review finding with its full text, which combing and labelling need (D4)."""

    model_config = ConfigDict(frozen=True)

    finding_id: str
    content_key: str
    severity: str
    category: ReviewCategory | None
    raw_category: str | None = None
    location: str | None
    title: str
    description: str


class CombDecision(BaseModel):
    model_config = ConfigDict(frozen=True)

    verdict: CombVerdict
    reason: str | None = None


class StageEntry(BaseModel):
    """One stage call's result: a review (findings) or a comb (decisions)."""

    model_config = ConfigDict(frozen=True)

    kind: StageKind
    config: StageConfig
    effort_configured: Effort | None
    effort_sent: Effort | None
    findings: tuple[RecallFinding, ...] = ()
    decisions: dict[str, CombDecision] = {}
    usage: StageUsage = StageUsage()
    outcome: StageOutcome
    outcome_reason: str | None = None
    leak: RecallLeakVerdict
    source: str
    case_set: str
    raw_ref: str | None = None
    alias: str
    created: datetime
    duplicate_decisions: int = 0
    unknown_ids: int = 0

    @property
    def entry_key(self) -> str:
        return entry_key(self.config, self.effort_configured)

    @property
    def is_live(self) -> bool:
        return self.source == LIVE_SOURCE


#: ``source`` of an entry ``run`` produced; imported entries carry ``import:<folder>``.
LIVE_SOURCE = "live"
IMPORT_SOURCE_PREFIX = "import:"


class RecallRun(BaseModel):
    """Every reviewer's review and combs for one (case, run index) (D4)."""

    case_id: str
    run_index: int
    reviews: dict[str, StageEntry] = {}
    combs: dict[str, StageEntry] = {}
    superseded: list[StageEntry] = []

    @property
    def record_id(self) -> str:
        return run_record_id(self.case_id, self.run_index)


def entry_key(config: StageConfig, effort_configured: Effort | None) -> str:
    """sha256 of (``config_key``, configured effort); used only for pending-call matching."""
    effort = None if effort_configured is None else effort_configured.value
    return _sha256_json([config.config_key, effort])


def chain_key(comb_entry_keys: list[str] | tuple[str, ...]) -> str:
    """The ordered comb entry keys joined with ``>``."""
    if not comb_entry_keys:
        raise ValueError("a comb chain needs at least one comb entry key")
    return CHAIN_SEPARATOR.join(comb_entry_keys)


def parent_chain_key(chain: str) -> str | None:
    """The chain one stage shorter; ``None`` for a one-stage chain (its input is the review)."""
    parts = chain.split(CHAIN_SEPARATOR)
    return None if len(parts) == 1 else CHAIN_SEPARATOR.join(parts[:-1])


def comb_slot(review_entry_key: str, chain: str) -> str:
    """The ``RecallRun.combs`` key: ``"<entry_key>|<chain_key>"``."""
    return f"{review_entry_key}{COMB_KEY_SEPARATOR}{chain}"


def content_key(location: str | None, title: str, description: str) -> str:
    """sha256 of normalized (location, title, description), whitespace collapsed (D3)."""

    def norm(text: str | None) -> str:
        return _WHITESPACE.sub(" ", text or "").strip()

    return _sha256_json([norm(location), norm(title), norm(description)])


def run_record_id(case_id: str, run_index: int) -> str:
    """``rbrun-<sha12>`` of (case_id, run_index)."""
    return f"{RECALL_RUN_ID_PREFIX}{_sha256_json([case_id, run_index])[:_ID_HEX_DIGITS]}"
