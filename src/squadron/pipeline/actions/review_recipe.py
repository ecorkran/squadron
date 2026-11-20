"""The review action's recipe path (slice 434, D3, D8, D9).

A step whose review model is a recipe runs every stage once per split part, through the
shared ``run_recipe_review`` flow. The step stamps one usage record: the recipe's summed
spend under the recipe name, which the run's cost cap counts.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from squadron.config.keys import REVIEW_RECIPE_STAGE_SLOW_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.usage import UsageRecord
from squadron.metrology.recall_run_models import StageOutcome
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.usage_capture import stamp
from squadron.recipes.model_ref import RecipeRef
from squadron.recipes.recipe_outcome import RecipeProgress, RecipeStageResult, stage_totals
from squadron.recipes.recipe_review import (
    RECORD_NOT_WRITTEN,
    recipe_review_request,
    record_context,
    run_recipe_review,
)
from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import ReviewTemplate

_logger = logging.getLogger(__name__)

#: ``ActionResult.metadata`` key holding the recipe name, ``complete`` and the record id.
RECIPE_METADATA_KEY = "recipe"

SavePart = Callable[[ReviewResult], Awaitable[str | None]]
ToActionResult = Callable[[ReviewResult, str | None], ActionResult]


class RecipeSinkMissingError(RuntimeError):
    """A recipe review ran in a context the executor gave no record sink."""


class RecipePartAborted(Exception):
    """A recipe part stopped on an unexpected error; carries what its stages spent (D5, D9)."""

    def __init__(self, error: Exception, record: UsageRecord | None) -> None:
        super().__init__(str(error))
        self.error = error
        self.record = record


@dataclass(frozen=True)
class RecipePart:
    """One part of a recipe review step: the recipe and the review it stands in for."""

    ref: RecipeRef
    template: ReviewTemplate
    inputs: dict[str, str]
    rules_content: str | None
    allowed_tools: list[str] | None
    changed_files: Sequence[str]
    #: Every stage the step's earlier parts ran; shared by the parts of one review step, so an
    #: aborted part stamps the spend of all of them (D9).
    spent: list[RecipeStageResult]


def recipe_usage_record(recipe_name: str, stages: Sequence[RecipeStageResult]) -> UsageRecord:
    """The step's usage record: summed spend under the recipe name (D9).

    With an unpriced stage the cost is a floor (the priced stages' sum), and each unpriced
    stage is named in one WARNING; with no priced stage it is ``None``.
    """
    called = [s for s in stages if s.made_call]
    unpriced = [s.label for s in called if s.usage.cost_usd is None]
    if unpriced:
        _logger.warning(
            "recipe %s: unpriced stage(s) %s; the step's cost counts only the priced stages",
            recipe_name,
            ", ".join(unpriced),
        )
    totals = stage_totals(called)
    bases = {s.usage.cost_basis for s in called if s.usage.cost_usd is not None}
    return UsageRecord(
        model=None,
        alias=recipe_name,
        profile=None,
        effort=None,
        turns=totals.turns,
        duration_seconds=totals.duration_s,
        usage=totals.tokens,
        cost_usd=totals.cost_usd,
        cost_basis=bases.pop() if len(bases) == 1 else None,
    )


def _failed_stages(stages: Sequence[RecipeStageResult]) -> str:
    return "; ".join(f"{s.label}: {s.reason}" for s in stages if s.outcome is not StageOutcome.OK)


async def run_recipe_part(
    part: RecipePart,
    context: ActionContext,
    *,
    save: SavePart,
    to_action_result: ToActionResult,
    pricing_warned: set[str],
) -> ActionResult:
    """Run the recipe on one part; map the merged review to the step's ``ActionResult``."""
    sink = context.recipe_sink
    if sink is None:
        raise RecipeSinkMissingError(f"review step {context.step_name} has no recipe record sink")
    recipe = part.ref.recipe
    # Off the loop: the config read opens and parses TOML files.
    slow_after_s = await asyncio.to_thread(
        get_positive_int_config, REVIEW_RECIPE_STAGE_SLOW_KEY, context.cwd
    )
    request = recipe_review_request(
        recipe,
        template=part.template,
        inputs=part.inputs,
        options={
            "rules_content": part.rules_content,
            "allowed_tools": part.allowed_tools,
            "pricing_warned": pricing_warned,
        },
        changed_files=part.changed_files,
        cwd=Path(context.cwd),
        slow_after_s=slow_after_s,
    )
    saved: list[str | None] = []

    async def save_review(result: ReviewResult) -> Path | None:
        result.run_id = context.run_id
        path = await save(result)
        saved.append(path)
        return None if path is None else Path(path)

    progress = RecipeProgress()
    linkage = record_context(
        context.cwd,
        run_id=context.run_id,
        step_name=context.step_name,
        iteration=context.iteration if context.iteration >= 1 else None,
    )
    try:
        output = await run_recipe_review(
            request, save=save_review, sink=sink, context=linkage, progress=progress
        )
    except Exception as exc:
        # Already logged with its traceback by run_recipe_review; the step fails with the
        # spend of this part's finished stages and every earlier part's, as a provider
        # failure's does (D5, D9).
        part.spent.extend(progress.stages)
        raise RecipePartAborted(exc, recipe_usage_record(recipe.name, part.spent)) from exc
    part.spent.extend(output.outcome.stages)
    result = output.result
    action_result = to_action_result(result, saved[0] if saved else None)
    action_result.metadata[RECIPE_METADATA_KEY] = {
        "name": recipe.name,
        "complete": output.outcome.complete,
        "record_id": output.record_id if output.record_id is not None else RECORD_NOT_WRITTEN,
    }
    stamp(action_result.metadata, recipe_usage_record(recipe.name, output.outcome.stages))
    if result.verdict is not Verdict.UNKNOWN:
        return action_result
    error = f"recipe {recipe.name} is incomplete with nothing kept; failed stages: " + _failed_stages(
        output.outcome.stages
    )
    return replace(action_result, success=False, error=error)
