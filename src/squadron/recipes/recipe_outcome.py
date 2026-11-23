"""What a recipe run produced: per-stage results and the recipe outcome (slice 434, D3-D5).

``RecipeProgress`` is owned by the caller and filled by the runner as each stage finishes,
so the caller still has the finished stages when the runner raises or is cancelled.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from squadron.core.models import Effort
from squadron.core.usage import TokenUsage, add_optional, add_optional_float
from squadron.metrology.recall_run_models import (
    CombDecision,
    RecallFinding,
    StageConfig,
    StageKind,
    StageOutcome,
    StageUsage,
    content_key,
)
from squadron.metrology.review_category_map import map_historical_category
from squadron.providers.errors import ProviderError
from squadron.recipes.comb_call import finding_id_at
from squadron.review.models import ReviewFinding, ReviewResult


@dataclass(frozen=True)
class RecipeStageResult:
    """One stage that ran (or, for an empty-input comb, was decided with no call)."""

    kind: StageKind
    reviewer: str
    alias: str
    chain: tuple[str, ...]
    config: StageConfig
    effort_sent: Effort | None
    #: Review stages: every finding returned. Comb stages: the findings the comb was given.
    findings: tuple[RecallFinding, ...]
    #: Comb stages: decision per reviewer finding id.
    decisions: dict[str, CombDecision]
    duplicate_decisions: int
    unknown_ids: int
    usage: StageUsage
    outcome: StageOutcome
    reason: str | None
    raw_output: str
    #: Comb stages that failed: the finding ids that passed through uncombed.
    not_combed: tuple[str, ...] = ()
    #: The provider's result, when a call returned (token usage, answering model).
    result: ReviewResult | None = None
    #: Tokens the call reported: from its result, or from a provider error's telemetry.
    tokens: TokenUsage = field(default_factory=TokenUsage)

    @property
    def made_call(self) -> bool:
        """A call reported something: it returned, or the provider error carried spend.
        An empty comb, or a failure that reported nothing, spent nothing."""
        return self.result is not None or self.usage != StageUsage()

    @property
    def label(self) -> str:
        """``review rev-a`` or ``comb rev-a > comb-1 > comb-2``."""
        return " > ".join((f"{self.kind.value} {self.reviewer}", *self.chain))


@dataclass
class RecipeProgress:
    """Caller-owned list of finished stages, appended in execution order."""

    stages: list[RecipeStageResult] = field(default_factory=list[RecipeStageResult])

    @property
    def complete(self) -> bool:
        return all(stage.outcome is StageOutcome.OK for stage in self.stages)


@dataclass(frozen=True)
class ReviewerOutcome:
    """One reviewer's contribution: kept CONCERN/FAIL findings and uncombed NOTE/PASS."""

    reviewer: str
    kept: tuple[RecallFinding, ...]
    uncombed: tuple[RecallFinding, ...]
    #: The reviewer's own findings by finding id, for the merged review.
    source: dict[str, ReviewFinding]
    #: Finding id -> the comb alias that failed while the finding passed through it.
    not_combed: dict[str, str]
    #: CONCERN/FAIL findings the recipe's category filter did not keep (437 D5, D6).
    not_gating: tuple[RecallFinding, ...] = ()


@dataclass(frozen=True)
class RecipeOutcome:
    """Every stage, the kept findings per reviewer, and whether every planned stage was ok."""

    stages: tuple[RecipeStageResult, ...]
    reviewers: tuple[ReviewerOutcome, ...]
    complete: bool
    planned: tuple[StageConfig, ...]


@dataclass(frozen=True)
class StageTotals:
    """Spend summed over stages; each ``None`` when no stage reported it."""

    cost_usd: float | None
    duration_s: float | None
    turns: int | None
    tool_calls: int | None
    tokens: TokenUsage


def stage_totals(stages: Iterable[RecipeStageResult]) -> StageTotals:
    """Sum cost, duration, turns, tool calls and tokens over *stages*."""
    cost: float | None = None
    duration: float | None = None
    turns: int | None = None
    tool_calls: int | None = None
    tokens = TokenUsage()
    for stage in stages:
        cost = add_optional_float(cost, stage.usage.cost_usd)
        duration = add_optional_float(duration, stage.usage.duration_s)
        turns = add_optional(turns, stage.usage.turns)
        tool_calls = add_optional(tool_calls, stage.usage.tool_calls)
        tokens = tokens.plus(stage.tokens)
    return StageTotals(cost, duration, turns, tool_calls, tokens)


def failure_usage(error: ProviderError) -> tuple[StageUsage, TokenUsage]:
    """What a failed call reported before it failed (slice 175 D5, 931 D12)."""
    telemetry = error.telemetry
    cost = error.cost_usd
    if cost is None and telemetry is not None:
        cost = telemetry.cost_usd
    usage = StageUsage(
        cost_usd=cost,
        cost_basis=error.cost_basis if cost is not None else None,
        duration_s=error.duration_seconds,
        turns=telemetry.turns if telemetry is not None else None,
        tool_calls=error.tool_calls_made,
    )
    return usage, telemetry.usage if telemetry is not None else TokenUsage()


def stage_usage(result: ReviewResult) -> StageUsage:
    """Cost, basis, duration, turns and tool calls a stage call reported."""
    return StageUsage(
        cost_usd=result.cost_usd,
        cost_basis=result.cost_basis,
        duration_s=result.duration_seconds,
        turns=result.turns,
        tool_calls=result.tool_calls_made,
    )


def recall_findings(findings: Sequence[ReviewFinding]) -> tuple[RecallFinding, ...]:
    """A review's findings as recall findings, ids positional (``F1`` is index 0)."""
    return tuple(_recall_finding(index, finding) for index, finding in enumerate(findings))


def _recall_finding(index: int, finding: ReviewFinding) -> RecallFinding:
    normalized = map_historical_category(finding.category)
    return RecallFinding(
        finding_id=finding_id_at(index),
        content_key=content_key(finding.location, finding.title, finding.description),
        severity=finding.severity.value,
        category=normalized.category,
        raw_category=finding.raw_category or normalized.raw_category,
        location=finding.location,
        title=finding.title,
        description=finding.description,
    )
