"""``sq benchmark recall report``: recall per recipe with paired comparisons (slice 430)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated

import typer

from squadron.benchmark.recall.recall_services import RecallServices, RecallServicesFactory
from squadron.benchmark.recall.recipe import RecipeError, load_recipes
from squadron.benchmark.recall.report_build import build_report
from squadron.benchmark.recall.report_json import report_json
from squadron.benchmark.recall.report_render import render_text
from squadron.benchmark.recall.scoring_select import StageIdentityResolver
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services

DEFAULT_RUNS = 1


def run_report(
    services: RecallServices,
    resolver: StageIdentityResolver,
    recipe_refs: list[str],
    set_ref: str,
    runs: int,
    as_json: bool,
) -> str:
    if runs < 1:
        raise ValueError("--runs must be at least 1")
    recipes = load_recipes(recipe_refs, services.repo_root)
    case_set = services.store.resolve_set(set_ref)
    data = build_report(services.store, recipes, case_set, list(range(1, runs + 1)), resolver)
    if as_json:
        return json.dumps(report_json(data).model_dump(mode="json"), indent=2)
    return render_text(data)


def make_report_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def report_command(
        recipe_refs: Annotated[
            list[str], typer.Option("--recipe", help="Recipe name or file (repeatable).")
        ],
        set_ref: Annotated[str, typer.Option("--set", help="Case set, NAME or NAME@VERSION.")],
        runs: Annotated[int, typer.Option("--runs", help="Score run indexes 1..N.")] = DEFAULT_RUNS,
        as_json: Annotated[bool, typer.Option("--json", help="Emit the JSON document.")] = False,
    ) -> None:
        """Recall per recipe and stage identity, with paired intervals between rows."""
        try:
            services = open_services(services_factory)
            output = run_report(services, services.stage_resolver, recipe_refs, set_ref, runs, as_json)
        except (*REFUSED_ERRORS, RecipeError) as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        typer.echo(output)

    return report_command
