"""Builders for producer-replay and pairwise-judgment records (slice 177)."""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.core.usage import CostBasis, TokenUsage, UsageRecord
from squadron.metrology.project_id import ProjectId, ProjectIdSource
from squadron.metrology.replay_models import (
    JudgeCall,
    JudgePick,
    JudgeRef,
    ModelRef,
    PairOutcome,
    PairwiseJudgment,
    ProducerConfigRef,
    ProducerReplay,
    PromptIdentity,
    ReplayOutcome,
    ReplayPhase,
)

PROJECT = "github.com/manta/example-repo"


def make_replay(
    *,
    project_value: str = PROJECT,
    phase: ReplayPhase = ReplayPhase.DESIGN,
    replay_set: str = "set-1",
    alias: str = "opus",
    outcome: ReplayOutcome = ReplayOutcome.ACCEPTED,
    created_at: datetime | None = None,
    first_draft: str | None = "# Draft",
    task_prompt: str | None = "Create a slice design.",
    original_sha: str = "a" * 40,
    model: str = "claude-opus-5-5",
    slice_index: int = 176,
    rounds: int | None = 1,
    cost_usd: float | None = 1.25,
    priced: tuple[int, int] = (3, 3),
    wall_seconds: float = 42.5,
    reviewer_alias: str = "sonnet",
    guide_version: str | None = None,
) -> ProducerReplay:
    return ProducerReplay(
        replay_set=replay_set,
        project_id=ProjectId(value=project_value, source=ProjectIdSource.REMOTE),
        phase=phase,
        slice_index=slice_index,
        slice_name="effort-calibration",
        original_sha=original_sha,
        start_sha="b" * 40,
        config=ProducerConfigRef(alias=alias, model=model, profile="sdk", effort_sent="high"),
        reviewer=ModelRef(alias=reviewer_alias, model=f"model-{reviewer_alias}"),
        max_revisions=2,
        run_id="run-1",
        outcome=outcome,
        failure_class=None,
        rounds=rounds,
        first_verdict="CONCERNS",
        cost_usd=cost_usd,
        priced=priced,
        wall_seconds=wall_seconds,
        prompt=PromptIdentity(
            sha256="c" * 64,
            source="build_context",
            squadron_version="0.0.0",
            cf_version="0.19.13",
            guide_version=guide_version,
        ),
        task_prompt=task_prompt,
        first_draft=first_draft,
        final_text="# Final",
        squadron_version="0.0.0",
        created_at=created_at or datetime(2026, 11, 1, tzinfo=UTC),
    )


def make_judge(prompt_hash: str = "d" * 64) -> JudgeRef:
    return JudgeRef(alias="opus", model="claude-opus-5-5", prompt_hash=prompt_hash)


def _usage() -> UsageRecord:
    return UsageRecord(
        model="claude-opus-5-5",
        alias="opus",
        profile="sdk",
        effort=None,
        turns=1,
        duration_seconds=2.0,
        usage=TokenUsage(prompt=100, completion=10),
        cost_usd=0.05,
        cost_basis=CostBasis.PROVIDER,
    )


def make_judgment(
    *,
    project_value: str = PROJECT,
    phase: ReplayPhase = ReplayPhase.DESIGN,
    judge: JudgeRef | None = None,
    created_at: datetime | None = None,
    replay_set: str = "set-1",
    a: str = "replay-20261101-aaaaaaaa",
    b: str = "original:" + "a" * 40,
    outcome: PairOutcome = PairOutcome.A,
) -> PairwiseJudgment:
    return PairwiseJudgment(
        replay_set=replay_set,
        project_id=ProjectId(value=project_value, source=ProjectIdSource.REMOTE),
        phase=phase,
        judge=judge or make_judge(),
        a=a,
        b=b,
        first_call=JudgeCall(pick=JudgePick.A, raw_tail="WINNER: A"),
        second_call=JudgeCall(pick=JudgePick.B, raw_tail="WINNER: B"),
        outcome=outcome,
        first_usage=_usage(),
        second_usage=_usage(),
        created_at=created_at or datetime(2026, 11, 1, tzinfo=UTC),
    )
