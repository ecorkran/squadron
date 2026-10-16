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
) -> ProducerReplay:
    return ProducerReplay(
        replay_set=replay_set,
        project_id=ProjectId(value=project_value, source=ProjectIdSource.REMOTE),
        phase=phase,
        slice_index=176,
        slice_name="effort-calibration",
        original_sha="a" * 40,
        start_sha="b" * 40,
        config=ProducerConfigRef(
            alias=alias, model="claude-opus-5-5", profile="sdk", effort_sent="high"
        ),
        reviewer=ModelRef(alias="sonnet", model="claude-sonnet-5-5"),
        max_revisions=2,
        run_id="run-1",
        outcome=outcome,
        failure_class=None,
        rounds=1,
        first_verdict="CONCERNS",
        cost_usd=1.25,
        priced=(3, 3),
        wall_seconds=42.5,
        prompt=PromptIdentity(
            sha256="c" * 64,
            source="build_context",
            squadron_version="0.0.0",
            cf_version="0.19.13",
            guide_version=None,
        ),
        task_prompt="Create a slice design.",
        first_draft="# Draft",
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
) -> PairwiseJudgment:
    return PairwiseJudgment(
        replay_set="set-1",
        project_id=ProjectId(value=project_value, source=ProjectIdSource.REMOTE),
        phase=phase,
        judge=judge or make_judge(),
        a="replay-20261101-aaaaaaaa",
        b="original:" + "a" * 40,
        first_call=JudgeCall(pick=JudgePick.A, raw_tail="WINNER: A"),
        second_call=JudgeCall(pick=JudgePick.B, raw_tail="WINNER: B"),
        outcome=PairOutcome.A,
        first_usage=_usage(),
        second_usage=_usage(),
        created_at=created_at or datetime(2026, 11, 1, tzinfo=UTC),
    )
