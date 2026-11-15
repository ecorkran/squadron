"""Slice-case records (slice 426, Database / Storage Schema).

A ``SliceQualification`` is one slice candidate's qualification result; a ``DiffJudgment`` is
one pair of implementation diffs judged in both orders (or forfeited); an ``OverSizeCase``
says a case's longest judge prompt exceeded the limit, so it was not judged. These live
beside ``benchmark_models`` (already past 300 lines) and import its shared enums.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from squadron.core.usage import UsageRecord
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import QualificationOutcome, TestRejection
from squadron.metrology.project_id import ProjectId
from squadron.metrology.replay_models import JudgeCall, JudgeRef, PairOutcome

SLICE_QUALIFICATION_ID_PREFIX = "slicequal-"
DIFF_JUDGMENT_ID_PREFIX = "diffjudge-"
OVER_SIZE_CASE_ID_PREFIX = "oversize-"
SLICE_QUALIFICATION_NO_ENVIRONMENT = "pre"
_PROJECT_DIGITS = 12
_SHA_DIGITS = 12
_ENVIRONMENT_DIGITS = 12
_BENCHMARK_SEGMENT = slice(6, 18)  # after "bench-"
_CASE_SEGMENT = slice(5, 17)  # after "case-"
_PAIR_DIGITS = 12
_OVER_SIZE_DIGITS = 8
#: The outcomes a forfeited pair can have: the other side wins, or both sides were absent.
FORFEIT_OUTCOMES = (PairOutcome.A, PairOutcome.B, PairOutcome.TIE)


class SliceCandidateRejection(StrEnum):
    """Why a slice candidate is not a case (slice 426, Patterns and Conventions)."""

    MULTIPLE_LANDINGS = "multiple_landings"
    BRANCH_CONTAINS_MERGES = "branch_contains_merges"
    NO_DESIGN_AT_FORK = "no_design_at_fork"
    NO_TASKS_AT_FORK = "no_tasks_at_fork"
    NO_SLICE_PLAN_AT_FORK = "no_slice_plan_at_fork"
    NO_CODE_CHANGE = "no_code_change"
    NO_REGRESSION_SIGNAL = "no_regression_signal"


class SliceQualification(BaseModel):
    """One qualification result for a slice landing (D6)."""

    model_config = ConfigDict(frozen=True)

    project_id: ProjectId
    slice_index: int
    slice_name: str
    landing_after_sha: str
    fork_sha: str
    tip_sha: str
    rule_version: int
    start_environment: EnvironmentIdentity | None  # None when rejected before any sandbox
    reference_environment: EnvironmentIdentity | None
    repeats: int
    outcome: QualificationOutcome
    case_id: str | None
    rejection: SliceCandidateRejection | None
    detail: str
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...]
    created_at: datetime

    @model_validator(mode="after")
    def _outcome_matches_fields(self) -> Self:
        qualified = self.outcome is QualificationOutcome.QUALIFIED
        rejected = self.outcome is QualificationOutcome.REJECTED
        if qualified != (self.case_id is not None):
            raise ValueError("case_id is set exactly when the outcome is qualified")
        if rejected != (self.rejection is not None):
            raise ValueError("rejection is set exactly when the outcome is rejected")
        return self

    @property
    def record_id(self) -> str:
        digest = None if self.start_environment is None else self.start_environment.identity_digest
        return slice_qualification_id(self.project_id, self.slice_index, self.landing_after_sha, digest)


class DiffJudgment(BaseModel):
    """One pair of implementation diffs judged in both orders, or forfeited (D12, D15)."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_id: str
    judge: JudgeRef  # prompt_hash of pairwise-diff-judge.md
    a: str  # replay record id or "reference:<sha>"
    b: str
    a_diff: str | None  # normalized diff sidecar sha256; None for an absent side
    b_diff: str | None
    forfeit: bool
    first_call: JudgeCall | None  # None on a forfeit
    second_call: JudgeCall | None
    outcome: PairOutcome | None
    first_usage: UsageRecord | None
    second_usage: UsageRecord | None
    max_prompt_chars: int  # the limit in effect
    created_at: datetime

    @model_validator(mode="after")
    def _forfeit_matches_fields(self) -> Self:
        if self.forfeit:
            self._check_forfeit()
        else:
            self._check_judged()
        return self

    def _check_forfeit(self) -> None:
        if self.first_call is not None or self.second_call is not None:
            raise ValueError("a forfeit makes no judge call")
        if self.first_usage is not None or self.second_usage is not None:
            raise ValueError("a forfeit has no usage")
        if self.outcome not in FORFEIT_OUTCOMES:
            raise ValueError("a forfeit's outcome is A, B or TIE")

    def _check_judged(self) -> None:
        if self.first_call is None or self.second_call is None:
            raise ValueError("a judged pair needs both calls")
        if self.outcome is None:
            raise ValueError("a judged pair needs an outcome")

    @property
    def record_id(self) -> str:
        return diff_judgment_id(self.benchmark_id, self.case_id, (self.a, self.b), self.judge)


class OverSizeCase(BaseModel):
    """A case not judged because its longest pair prompt exceeded the limit (D14)."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    case_id: str
    judge: JudgeRef
    longest_prompt_chars: int
    longest_contestant: str
    max_prompt_chars: int  # the limit in effect
    created_at: datetime

    @property
    def record_id(self) -> str:
        return over_size_case_id(self.benchmark_id, self.case_id, self.judge)


def _sha256_hex(*parts: object) -> str:
    """sha256 of the canonical JSON of *parts*; never ``hash()``, which varies per process."""
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode("utf-8")).hexdigest()


def slice_qualification_id(
    project_id: ProjectId, slice_index: int, landing_after_sha: str, env_digest: str | None
) -> str:
    """``slicequal-<sha256(project_id)[:12]>-<index>-<after sha[:12]>-<env digest[:12] or "pre">``."""
    project_hash = hashlib.sha256(project_id.value.encode("utf-8")).hexdigest()
    environment = (
        SLICE_QUALIFICATION_NO_ENVIRONMENT if env_digest is None else env_digest[:_ENVIRONMENT_DIGITS]
    )
    return (
        f"{SLICE_QUALIFICATION_ID_PREFIX}{project_hash[:_PROJECT_DIGITS]}"
        f"-{slice_index}-{landing_after_sha[:_SHA_DIGITS]}-{environment}"
    )


def diff_judgment_id(benchmark_id: str, case_id: str, refs: tuple[str, str], judge: JudgeRef) -> str:
    """``diffjudge-<benchmark[6:18]>-<case[5:17]>-<sha256(sorted refs, prompt hash, alias)[:12]>``."""
    pair = _sha256_hex(sorted(refs), judge.prompt_hash, judge.alias)[:_PAIR_DIGITS]
    return (
        f"{DIFF_JUDGMENT_ID_PREFIX}{benchmark_id[_BENCHMARK_SEGMENT]}-{case_id[_CASE_SEGMENT]}-{pair}"
    )


def over_size_case_id(benchmark_id: str, case_id: str, judge: JudgeRef) -> str:
    """``oversize-<benchmark[6:18]>-<case[5:17]>-<sha256(prompt hash, alias)[:8]>``."""
    judge_hash = _sha256_hex(judge.prompt_hash, judge.alias)[:_OVER_SIZE_DIGITS]
    return (
        f"{OVER_SIZE_CASE_ID_PREFIX}{benchmark_id[_BENCHMARK_SEGMENT]}"
        f"-{case_id[_CASE_SEGMENT]}-{judge_hash}"
    )
