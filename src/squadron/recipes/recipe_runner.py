"""Run a recipe's stages in order, one call at a time (slice 434, D3-D5).

Per reviewer, in recipe order: its review stage (the step's own template, inputs and
rules, the reviewer's own ``reviewer_options`` (tools, rules file; 437) and its alias), then
its comb chain. A ``ProviderError`` or an
unusable answer fails the stage (D5's first table); anything else propagates, with the
finished stages already in the caller's ``RecipeProgress``. The runner runs no ``git``
of its own: ``changed_files`` comes from the caller's scope check.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, TypeVar

from squadron.core.usage import TokenUsage
from squadron.metrology.recall_run_models import (
    RecallFinding,
    StageConfig,
    StageKind,
    StageOutcome,
    StageUsage,
)
from squadron.providers.errors import ProviderError
from squadron.recipes.comb_call import CombCall, ReviewCall, StageModel
from squadron.recipes.kept_findings import (
    CombStep,
    apply_comb,
    chain_result,
    comb_input,
    decisions_by_finding,
    pass_through,
    split_by_category,
)
from squadron.recipes.recipe import Recipe, RequiredStage, required_stages
from squadron.recipes.recipe_outcome import (
    RecipeOutcome,
    RecipeProgress,
    RecipeStageResult,
    ReviewerOutcome,
    failure_usage,
    recall_findings,
    stage_usage,
)
from squadron.recipes.reviewer_options import reviewer_call_options
from squadron.recipes.stage_config import RecipePlan
from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import ReviewTemplate

_logger = logging.getLogger(__name__)
_T = TypeVar("_T")


@dataclass(frozen=True)
class RecipeReviewCall:
    """The review the step would run: template, inputs and the caller's own call options
    (rules, allowed tools, pricing set). Per-alias settings are added per stage."""

    template: ReviewTemplate
    inputs: Mapping[str, str]
    options: Mapping[str, Any]
    review_call: ReviewCall
    comb_call: CombCall


@dataclass(frozen=True)
class _Run:
    recipe: Recipe
    call: RecipeReviewCall
    comb_template: ReviewTemplate
    models: dict[str, StageModel]
    configs: dict[RequiredStage, StageConfig]
    changed: str
    cwd: Path
    slow_after_s: float
    progress: RecipeProgress

    async def timed(self, label: str, alias: str, awaitable: Awaitable[_T]) -> _T:
        """Await one stage call; past ``slow_after_s`` log one WARNING, never stop it."""
        started = time.monotonic()
        _logger.info("recipe %s: stage %s (%s) started", self.recipe.name, label, alias)
        handle = asyncio.get_running_loop().call_later(
            self.slow_after_s, self._warn_slow, label, alias, started
        )
        try:
            return await awaitable
        finally:
            handle.cancel()
            _logger.info("recipe %s: stage %s (%s) finished", self.recipe.name, label, alias)

    def _warn_slow(self, label: str, alias: str, started: float) -> None:
        _logger.warning(
            "recipe %s: stage %s (%s) still running after %.0fs",
            self.recipe.name,
            label,
            alias,
            time.monotonic() - started,
        )

    def record(self, stage: RecipeStageResult) -> None:
        if stage.outcome is not StageOutcome.OK:
            _logger.warning(
                "recipe %s: stage %s failed (%s): %s",
                self.recipe.name,
                stage.label,
                stage.outcome.value,
                stage.reason,
            )
        self.progress.stages.append(stage)


async def run_recipe(
    recipe: Recipe,
    *,
    call: RecipeReviewCall,
    plan: RecipePlan,
    changed_files: Sequence[str],
    cwd: Path,
    slow_after_s: float,
    progress: RecipeProgress,
) -> RecipeOutcome:
    """Run every stage of *recipe* to *plan*, resolved by the caller before the first call."""
    run = _Run(
        recipe=recipe,
        call=call,
        comb_template=plan.comb_template,
        models=plan.models,
        configs=dict(zip(required_stages(recipe), plan.planned, strict=True)),
        changed="\n".join(changed_files),
        cwd=cwd,
        slow_after_s=slow_after_s,
        progress=progress,
    )
    reviewers = [await _run_reviewer(run, reviewer) for reviewer in recipe.reviewers]
    return RecipeOutcome(
        stages=tuple(progress.stages),
        reviewers=tuple(reviewers),
        complete=progress.complete,
        planned=plan.planned,
    )


def _stage(
    run: _Run,
    required: RequiredStage,
    *,
    outcome: StageOutcome,
    result: ReviewResult | None = None,
    error: ProviderError | None = None,
    **fields: Any,
) -> RecipeStageResult:
    alias = required.chain[-1] if required.chain else required.reviewer
    defaults: dict[str, Any] = {
        "findings": (),
        "decisions": {},
        "duplicate_decisions": 0,
        "unknown_ids": 0,
        "reason": None,
        "raw_output": result.raw_output if result is not None else "",
    }
    defaults.update(fields)
    usage, tokens = StageUsage(), TokenUsage()
    if result is not None:
        usage, tokens = stage_usage(result), result.usage
    elif error is not None:
        usage, tokens = failure_usage(error)
    return RecipeStageResult(
        kind=required.kind,
        reviewer=required.reviewer,
        alias=alias,
        chain=required.chain,
        config=run.configs[required],
        effort_sent=result.effort if result is not None else None,
        usage=usage,
        outcome=outcome,
        result=result,
        tokens=tokens,
        **defaults,
    )


def _no_findings(reviewer: str) -> ReviewerOutcome:
    return ReviewerOutcome(reviewer=reviewer, kept=(), uncombed=(), source={}, not_combed={})


async def _run_reviewer(run: _Run, reviewer: str) -> ReviewerOutcome:
    required = RequiredStage(StageKind.REVIEW, reviewer, ())
    model = run.models[reviewer]
    call = run.call
    review = call.review_call(
        call.template,
        dict(call.inputs),
        **reviewer_call_options(call.options, run.recipe.reviewer_options.get(reviewer)),
        profile=model.profile,
        model=model.model,
        model_allows_tools=model.allows_tools,
        max_output_tokens=model.max_output_tokens,
        effort=model.effort,
        alias=reviewer,
    )
    try:
        result = await run.timed(f"review {reviewer}", reviewer, review)
    except ProviderError as exc:
        run.record(
            _stage(run, required, outcome=StageOutcome.HARNESS_FAILURE, error=exc, reason=str(exc))
        )
        return _no_findings(reviewer)
    findings = recall_findings(result.findings)
    if result.verdict is Verdict.UNKNOWN:
        reason = "the review's verdict is UNKNOWN; its findings are not used"
        run.record(
            _stage(
                run,
                required,
                outcome=StageOutcome.CONFIG_FAILURE,
                result=result,
                findings=findings,
                reason=reason,
            )
        )
        return _no_findings(reviewer)
    run.record(_stage(run, required, outcome=StageOutcome.OK, result=result, findings=findings))
    return await _run_chain(run, reviewer, findings, result)


async def _run_chain(
    run: _Run, reviewer: str, findings: tuple[RecallFinding, ...], result: ReviewResult
) -> ReviewerOutcome:
    split = comb_input(findings)
    gating, not_gating = split_by_category(split.scored, run.recipe.keep_categories)
    chain_in: tuple[RecallFinding, ...] = gating
    steps: list[CombStep] = []
    not_combed: dict[str, str] = {}
    combs = run.recipe.combs
    for depth in range(1, len(combs) + 1):
        step = await _run_comb(run, RequiredStage(StageKind.COMB, reviewer, combs[:depth]), chain_in)
        stage = run.progress.stages[-1]
        not_combed.update(dict.fromkeys(stage.not_combed, stage.alias))
        steps.append(step)
        chain_in = step.kept
    source = {f.finding_id: original for f, original in zip(findings, result.findings, strict=True)}
    return ReviewerOutcome(
        reviewer=reviewer,
        kept=chain_result(gating, steps),
        uncombed=split.unscored,
        source=source,
        not_combed=not_combed,
        not_gating=not_gating,
    )


async def _run_comb(
    run: _Run, required: RequiredStage, findings: tuple[RecallFinding, ...]
) -> CombStep:
    if not findings:
        run.record(_stage(run, required, outcome=StageOutcome.OK))
        return CombStep(kept=(), dropped=(), undecided=())
    alias = required.chain[-1]
    passed = tuple(f.finding_id for f in findings)
    call = run.call.comb_call(
        template=run.comb_template,
        findings=list(findings),
        changed=run.changed,
        cwd=run.cwd,
        model=run.models[alias],
        review_call=run.call.review_call,
    )
    label = " > ".join((f"comb {required.reviewer}", *required.chain))
    try:
        answer = await run.timed(label, alias, call)
    except ProviderError as exc:
        failed = _stage(
            run,
            required,
            outcome=StageOutcome.HARNESS_FAILURE,
            error=exc,
            findings=findings,
            reason=str(exc),
            not_combed=passed,
        )
        run.record(failed)
        return pass_through(findings)
    if answer.parsed.is_empty:
        reason = "the comb's output has no parseable decision line"
        failed = _stage(
            run,
            required,
            outcome=StageOutcome.CONFIG_FAILURE,
            result=answer.result,
            findings=findings,
            reason=reason,
            not_combed=passed,
        )
        run.record(failed)
        return pass_through(findings)
    decisions = decisions_by_finding(findings, answer.parsed.decisions)
    _warn_counts(run, label, answer.parsed.duplicate_decisions, answer.parsed.unknown_ids)
    run.record(
        _stage(
            run,
            required,
            outcome=StageOutcome.OK,
            result=answer.result,
            findings=findings,
            decisions=decisions,
            duplicate_decisions=answer.parsed.duplicate_decisions,
            unknown_ids=answer.parsed.unknown_ids,
        )
    )
    return apply_comb(findings, decisions)


def _warn_counts(run: _Run, label: str, duplicates: int, unknown: int) -> None:
    if duplicates or unknown:
        _logger.warning(
            "recipe %s: stage %s repeated %d decision(s) and named %d unknown id(s); "
            "the first decision per id was used",
            run.recipe.name,
            label,
            duplicates,
            unknown,
        )
