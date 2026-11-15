"""Builders for slice-case records in tests (slice 426)."""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import JudgeCall, JudgePick, JudgeRef, PairOutcome
from squadron.metrology.slice_case_models import (
    DiffJudgment,
    OverSizeCase,
    SliceCandidateRejection,
    SliceQualification,
)
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.pipeline.text_tail import tail_text

PROJECT = ProjectId(value="github.com/manta/example-repo", source=ProjectIdSource.REMOTE)
CREATED = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)
FORK = "f" * 40
TIP = "a" * 40
LANDING = "b" * 40
BENCHMARK_ID = "bench-3f9c0a1b2c3d4e5f"
CASE_ID = "case-0123456789abcdef"
# A judge reply as long as a real one; the call keeps 177's tail of it (400 characters).
LONG_REPLY = "The first implementation covers the task and the second does not. " * 60


def environment(lock_sha: str = "1" * 64) -> EnvironmentIdentity:
    return EnvironmentIdentity(
        language=SourceLanguage.PYTHON,
        lockfile_path="uv.lock",
        lockfile_sha256=lock_sha,
        interpreter_version="Python 3.12.1",
        installer_version="uv 0.5.0",
        platform="darwin-arm64",
        scrub_spec_version=1,
    )


def judge_ref(alias: str = "gpt-judge", prompt_hash: str = "4b1d" * 16) -> JudgeRef:
    return JudgeRef(alias=alias, model="gpt-x", prompt_hash=prompt_hash, effort_sent=None)


def usage(cost: float | None = 0.04) -> UsageRecord:
    return UsageRecord(
        model="gpt-x",
        alias="gpt-judge",
        profile="openai-oauth",
        effort=None,
        turns=1,
        duration_seconds=3.0,
        usage=TokenUsage(prompt=1200, completion=80),
        cost_usd=cost,
        cost_basis=CostBasis.PROVIDER,
    )


def qualification(
    outcome: QualificationOutcome = QualificationOutcome.QUALIFIED,
    *,
    index: int = 403,
    rejection: SliceCandidateRejection | None = None,
    case_id: str | None = CASE_ID,
    start_environment: EnvironmentIdentity | None = None,
    landing_after_sha: str = LANDING,
    rule_version: int = 1,
) -> SliceQualification:
    qualified = outcome is QualificationOutcome.QUALIFIED
    return SliceQualification(
        project_id=PROJECT,
        slice_index=index,
        slice_name="slice-ranges",
        landing_after_sha=landing_after_sha,
        fork_sha=FORK,
        tip_sha=TIP,
        rule_version=rule_version,
        start_environment=start_environment,
        reference_environment=start_environment if qualified else None,
        repeats=3,
        outcome=outcome,
        case_id=case_id if qualified else None,
        rejection=rejection,
        detail="",
        excluded_with_reasons=(),
        created_at=CREATED,
    )


def judgment(
    *,
    a: str = "implreplay-aaaa",
    b: str = "reference:" + TIP,
    judge: JudgeRef | None = None,
    case_id: str = CASE_ID,
    outcome: PairOutcome = PairOutcome.A,
    cost: float | None = 0.04,
) -> DiffJudgment:
    pick = JudgePick(outcome.value) if outcome in (PairOutcome.A, PairOutcome.B) else JudgePick.TIE
    return DiffJudgment(
        benchmark_id=BENCHMARK_ID,
        case_id=case_id,
        judge=judge or judge_ref(),
        a=a,
        b=b,
        a_diff="c" * 64,
        b_diff="d" * 64,
        forfeit=False,
        first_call=JudgeCall(pick=pick, raw_tail=tail_text(LONG_REPLY)),
        second_call=JudgeCall(pick=pick, raw_tail=tail_text(LONG_REPLY)),
        outcome=outcome,
        first_usage=usage(cost),
        second_usage=usage(cost),
        max_prompt_chars=400000,
        created_at=CREATED,
    )


def over_size(*, judge: JudgeRef | None = None, limit: int = 1000) -> OverSizeCase:
    return OverSizeCase(
        benchmark_id=BENCHMARK_ID,
        case_id=CASE_ID,
        judge=judge or judge_ref(),
        longest_prompt_chars=limit + 1,
        longest_contestant="reference:" + TIP,
        max_prompt_chars=limit,
        created_at=CREATED,
    )
