"""The recipe review flow both entry points share (slice 434, D5, D8).

Run the recipe, merge, save the review file, then write the record. The CLI and the
pipeline action differ only in the save callable, the sink and the run linkage they pass.

- A save that raises: the record is written with ``review_file: null``, then the save
  error propagates.
- A record write that fails (``MetrologyStoreError``, ``OSError``): logged at ERROR, the
  review still returns its result, with no record id.
- An unexpected exception in a stage or the merge: the aborted record (finished stages,
  ``complete: false``, UNKNOWN) is written, no review file, the error propagates.
- Cancellation: the same aborted record, written synchronously, then the cancellation
  propagates.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.identity import derive_project_id, template_behavior_hash
from squadron.metrology.recall_run_models import StageConfig
from squadron.metrology.recipe_review_models import new_recipe_review_id
from squadron.recipes.comb_call import call_comb
from squadron.recipes.recipe import Recipe
from squadron.recipes.recipe_merge import merge_recipe
from squadron.recipes.recipe_outcome import RecipeOutcome, RecipeProgress, RecipeStageResult
from squadron.recipes.recipe_record import (
    RecipeRecordContext,
    RecipeRecordFacts,
    RecipeRecordSink,
    build_recipe_record,
)
from squadron.recipes.recipe_runner import RecipeReviewCall, run_recipe
from squadron.recipes.stage_config import plan_recipe
from squadron.review.models import ReviewResult, Verdict
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import ReviewTemplate

_logger = logging.getLogger(__name__)

#: Saves the merged review; returns the file written, or ``None`` when nothing is saved.
SaveReview = Callable[[ReviewResult], Awaitable[Path | None]]
CANCELLED_REASON = "cancelled"
#: What the CLI and the action report when the record could not be written (D8).
RECORD_NOT_WRITTEN = "recipe record: not written"
#: The review inputs that name what was reviewed, recorded as the merged result's input files.
INPUT_FILE_KEYS = ("input", "against", "diff", "files")


@dataclass(frozen=True)
class RecipeReviewRequest:
    """One recipe review: the recipe, the review it stands in for, and where it runs."""

    recipe: Recipe
    call: RecipeReviewCall
    changed_files: Sequence[str]
    cwd: Path
    input_files: dict[str, str]
    slow_after_s: float


def recipe_review_request(
    recipe: Recipe,
    *,
    template: ReviewTemplate,
    inputs: dict[str, str],
    options: dict[str, object],
    changed_files: Sequence[str],
    cwd: Path,
    slow_after_s: float,
) -> RecipeReviewRequest:
    """The request both entry points build: stages call ``run_review_with_profile``, combs
    ``call_comb``. *options* are the caller's own review-call options (rules, tools, ...)."""
    call = RecipeReviewCall(
        template=template,
        inputs=inputs,
        options=options,
        review_call=run_review_with_profile,
        comb_call=call_comb,
    )
    return RecipeReviewRequest(
        recipe=recipe,
        call=call,
        changed_files=changed_files,
        cwd=cwd,
        input_files={k: inputs[k] for k in INPUT_FILE_KEYS if k in inputs},
        slow_after_s=slow_after_s,
    )


def record_context(
    cwd: str,
    *,
    run_id: str | None = None,
    step_name: str | None = None,
    iteration: int | None = None,
) -> RecipeRecordContext:
    """The production record context: the project of *cwd*, UTC now, the run linkage."""
    return RecipeRecordContext(
        project_id=lambda: derive_project_id(cwd),
        clock=lambda: datetime.now(UTC),
        run_id=run_id,
        step_name=step_name,
        iteration=iteration,
    )


@dataclass(frozen=True)
class RecipeReviewOutput:
    result: ReviewResult
    #: ``None`` when the record could not be written.
    record_id: str | None
    outcome: RecipeOutcome


@dataclass(frozen=True)
class _Writer:
    request: RecipeReviewRequest
    sink: RecipeRecordSink
    context: RecipeRecordContext
    record_id: str
    planned: Sequence[StageConfig]

    def facts(
        self,
        stages: Sequence[RecipeStageResult],
        verdict: Verdict,
        complete: bool,
        *,
        review_file: str | None = None,
        aborted: str | None = None,
    ) -> RecipeRecordFacts:
        template = self.request.call.template
        return RecipeRecordFacts(
            record_id=self.record_id,
            recipe=self.request.recipe,
            template_name=template.name,
            template_hash=template_behavior_hash(template),
            planned=self.planned,
            stages=stages,
            verdict=verdict,
            complete=complete,
            review_file=review_file,
            aborted=aborted,
        )

    def write(self, facts: RecipeRecordFacts) -> bool:
        try:
            record, raw_outputs = build_recipe_record(facts, self.context)
            self.sink.write(record, raw_outputs)
        except (MetrologyStoreError, MetrologyIdentityError, OSError) as exc:
            # D8: the review has already produced its result, which is the primary output;
            # a lost record must not fail it, the same boundary the review-file save has.
            # A project with no stable identity cannot key a record: the same case.
            _logger.error("recipe review record %s not written: %s", self.record_id, exc)
            return False
        return True

    def aborted(self, progress: RecipeProgress, reason: str) -> RecipeRecordFacts:
        return self.facts(list(progress.stages), Verdict.UNKNOWN, False, aborted=reason)


async def run_recipe_review(
    request: RecipeReviewRequest,
    *,
    save: SaveReview,
    sink: RecipeRecordSink,
    context: RecipeRecordContext,
    progress: RecipeProgress | None = None,
) -> RecipeReviewOutput:
    """Run, merge, save, record. Returns the merged result and the record id (or ``None``).

    Pass *progress* to keep the finished stages when this raises (their spend, D9).
    """
    template = request.call.template
    # Off the loop: the plan reads and parses template and alias files.
    plan = await asyncio.to_thread(plan_recipe, request.recipe, template)
    writer = _Writer(
        request=request,
        sink=sink,
        context=context,
        record_id=new_recipe_review_id(context.clock),
        planned=plan.planned,
    )
    progress = progress if progress is not None else RecipeProgress()
    try:
        outcome = await run_recipe(
            request.recipe,
            call=request.call,
            plan=plan,
            changed_files=request.changed_files,
            cwd=request.cwd,
            slow_after_s=request.slow_after_s,
            progress=progress,
        )
        result = merge_recipe(outcome, request.recipe.name, template.name, request.input_files)
    except asyncio.CancelledError:
        _logger.warning("recipe %s: cancelled; writing the aborted record", request.recipe.name)
        writer.write(writer.aborted(progress, CANCELLED_REASON))
        raise
    except Exception as exc:
        _logger.exception("recipe %s: aborted by an unexpected error", request.recipe.name)
        await asyncio.to_thread(writer.write, writer.aborted(progress, str(exc)))
        raise
    review_file = await _save_then_record(writer, result, outcome, save)
    written = await asyncio.to_thread(
        writer.write,
        writer.facts(outcome.stages, result.verdict, outcome.complete, review_file=review_file),
    )
    return RecipeReviewOutput(
        result=result, record_id=writer.record_id if written else None, outcome=outcome
    )


async def _save_then_record(
    writer: _Writer, result: ReviewResult, outcome: RecipeOutcome, save: SaveReview
) -> str | None:
    """Save the review; when the save raises, record with no file and re-raise."""
    try:
        path = await save(result)
    except Exception:
        _logger.exception("recipe review %s: saving the review file failed", writer.record_id)
        facts = writer.facts(outcome.stages, result.verdict, outcome.complete)
        await asyncio.to_thread(writer.write, facts)
        raise
    return None if path is None else str(path)
