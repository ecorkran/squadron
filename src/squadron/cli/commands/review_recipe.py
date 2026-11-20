"""``sq review``'s recipe path (slice 434, D2, D5, D8).

A recipe name runs the shared ``run_recipe_review`` flow with the metrology-store sink and
no run linkage. The review file is saved inside the flow, through the subcommand's own
save step (``CliPersist``), so the record that follows can name the file.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer
from rich import print as rprint
from rich.console import Console
from rich.markup import escape

from squadron.config.keys import REVIEW_RECIPE_STAGE_SLOW_KEY
from squadron.config.manager import get_positive_int_config
from squadron.metrology.recall_run_models import StageOutcome
from squadron.recipes.model_ref import RecipeRef
from squadron.recipes.recipe_record import metrology_recipe_sink
from squadron.recipes.recipe_review import (
    RECORD_NOT_WRITTEN,
    RecipeReviewRequest,
    recipe_review_request,
    record_context,
    run_recipe_review,
)
from squadron.review.models import ReviewResult, Verdict
from squadron.review.templates import ReviewTemplate

_logger = logging.getLogger(__name__)


@dataclass
class CliPersist[OutcomeT]:
    """A subcommand's save step, run at most once.

    The recipe flow runs it before writing the record; a single-model review runs it
    after the review returns, as before. Either way the subcommand reads the outcome
    from ``run``.
    """

    #: Saves *result*, appends the path written (if any), returns the save outcome.
    save: Callable[[ReviewResult, list[Path]], OutcomeT]
    outcome: OutcomeT | None = None
    paths: list[Path] = field(default_factory=list[Path])

    def run(self, result: ReviewResult) -> OutcomeT:
        if self.outcome is None:
            self.outcome = self.save(result, self.paths)
        return self.outcome


@dataclass(frozen=True)
class CliRecipeReview:
    """What ``sq review`` hands the recipe path besides the recipe itself."""

    template: ReviewTemplate
    inputs: dict[str, str]
    rules_content: str | None
    verbosity: int
    no_tools: bool
    language_rules: list[str]
    persist: CliPersist[Any]
    #: The files the subcommand's diff scope check returned; empty without a diff.
    changed_files: list[str]


def _request(ref: RecipeRef, review: CliRecipeReview, cwd: str) -> RecipeReviewRequest:
    return recipe_review_request(
        ref.recipe,
        template=review.template,
        inputs=review.inputs,
        options={
            "rules_content": review.rules_content,
            "verbosity": review.verbosity,
            "no_tools": review.no_tools,
        },
        changed_files=review.changed_files,
        cwd=Path(cwd),
        slow_after_s=get_positive_int_config(REVIEW_RECIPE_STAGE_SLOW_KEY, cwd),
    )


def run_recipe_cli(ref: RecipeRef, review: CliRecipeReview, *, json_stdout: bool) -> ReviewResult:
    """Run the recipe, save through the subcommand, write the record; exit 1 on UNKNOWN."""
    cwd = review.inputs.get("cwd") or "."

    async def save(result: ReviewResult) -> Path | None:
        result.project_rules = list(review.language_rules)
        review.persist.run(result)
        return review.persist.paths[0] if review.persist.paths else None

    context = record_context(cwd)
    try:
        output = asyncio.run(
            run_recipe_review(
                _request(ref, review, cwd),
                save=save,
                sink=metrology_recipe_sink(cwd),
                context=context,
            )
        )
    except Exception as exc:
        # Process boundary: run_recipe_review logged it with its traceback and wrote the
        # aborted record; the command reports it and exits 1.
        rprint(f"[red]Error: recipe review failed — {escape(str(exc))}[/red]")
        raise typer.Exit(code=1) from exc
    report = Console(stderr=True) if json_stdout else Console()
    if output.record_id is None:
        report.print(f"[yellow]{RECORD_NOT_WRITTEN}[/yellow]")
    result = output.result
    if result.verdict is Verdict.UNKNOWN:
        failed = [s for s in output.outcome.stages if s.outcome is not StageOutcome.OK]
        report.print(f"[red]Recipe {escape(ref.recipe.name)} is incomplete with nothing kept.[/red]")
        for stage in failed:
            report.print(
                f"[red]  failed stage {escape(stage.label)}: {escape(str(stage.reason))}[/red]"
            )
    return result
