"""``sq benchmark recall report``: recall per recipe with paired comparisons (slice 430)."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Annotated

import typer

from squadron.benchmark.recall.real_work import build_rows, render_real_work
from squadron.benchmark.recall.recall_services import RecallServices, RecallServicesFactory
from squadron.benchmark.recall.recipe_dirs import benchmark_recipe_dirs
from squadron.benchmark.recall.report_build import build_report
from squadron.benchmark.recall.report_json import report_json
from squadron.benchmark.recall.report_render import render_text
from squadron.benchmark.recall.scoring_select import StageIdentityResolver
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services
from squadron.recipes.recipe import RecipeError
from squadron.recipes.recipe_search import load_recipes

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
    recipes = load_recipes(recipe_refs, benchmark_recipe_dirs(services.repo_root))
    case_set = services.store.resolve_set(set_ref)
    data = build_report(services.store, recipes, case_set, list(range(1, runs + 1)), resolver)
    if as_json:
        return json.dumps(report_json(data).model_dump(mode="json"), indent=2)
    return render_text(data)


def run_real_work_report(services: RecallServices, recipe_names: list[str]) -> str:
    """The real-work table from this project's ``recipe_review`` records (slice 434 D10)."""
    project = services.project_id()
    records = [r for r in services.store.list_recipe_reviews() if r.project_id == project]
    return render_real_work(build_rows(records, recipe_names))


def make_report_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def report_command(
        recipe_refs: Annotated[
            list[str] | None,
            typer.Option(
                "--recipe", help="Recipe name or file (repeatable); a name filter with --real-work."
            ),
        ] = None,
        set_ref: Annotated[
            str | None,
            typer.Option("--set", help="Case set, NAME or NAME@VERSION; required unless --real-work."),
        ] = None,
        runs: Annotated[int, typer.Option("--runs", help="Score run indexes 1..N.")] = DEFAULT_RUNS,
        as_json: Annotated[bool, typer.Option("--json", help="Emit the JSON document.")] = False,
        real_work: Annotated[
            bool,
            typer.Option("--real-work", help="Counts and cost of recipe reviews of real work."),
        ] = False,
    ) -> None:
        """Recall per recipe and stage identity, with paired intervals between rows."""
        refs = recipe_refs or []
        try:
            services = open_services(services_factory)
            if real_work and as_json:
                raise stderr_exit("Error: --json is not supported with --real-work.")
            if real_work:
                output = run_real_work_report(services, refs)
            elif set_ref is None:
                raise stderr_exit("Error: --set is required unless --real-work is given.")
            elif not refs:
                raise stderr_exit("Error: --recipe is required unless --real-work is given.")
            else:
                output = run_report(services, services.stage_resolver, refs, set_ref, runs, as_json)
        except (*REFUSED_ERRORS, RecipeError) as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        typer.echo(output)

    return report_command
