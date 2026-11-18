"""``sq benchmark recall label``: list undecided hit candidates; record a person's label (D3)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.recall.label_candidates import (
    Candidate,
    record_person_hit,
    undecided_candidates,
)
from squadron.benchmark.recall.recall_services import RecallServices, RecallServicesFactory, recall_lock
from squadron.benchmark.recall.recipe import RecipeError, load_recipe
from squadron.benchmark.recall.refusal import RecallRefusal
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_label_models import HitVerdict


def render_candidate(candidate: Candidate) -> list[str]:
    bug, finding = candidate.bug, candidate.finding
    locations = ", ".join(
        f"{loc.file}#{loc.symbol}" if loc.symbol else loc.file for loc in bug.locations
    )
    seen = ", ".join(f"{source} run {run}" for source, run in sorted(candidate.seen_in))
    return [
        f"{candidate.case.name} {bug.id}: {bug.description}",
        f"  bug files: {locations}",
        f"  finding {finding.content_key}  [{finding.severity}] {finding.location or '(no location)'}",
        f"  title: {finding.title}",
        f"  description: {finding.description}",
        f"  affects: {seen}",
    ]


def _cases(services: RecallServices, set_ref: str, names: list[str]) -> list[RealBugCase]:
    case_set = services.store.resolve_set(set_ref)
    cases = [case for cid in case_set.case_ids if (case := services.store.get_case(cid)) is not None]
    if names:
        unknown = sorted(set(names) - {case.name for case in cases})
        if unknown:
            raise RecallRefusal(f"case(s) not in set {set_ref}: {', '.join(unknown)}")
        cases = [case for case in cases if case.name in names]
    return cases


def run_label(
    services: RecallServices,
    set_ref: str,
    recipe_paths: list[Path],
    case_names: list[str],
    runs: int,
    hit: tuple[str, str, str] | None,
    person: str | None,
) -> None:
    cases = _cases(services, set_ref, case_names)
    if hit is not None:
        key, bug_id, word = hit
        if not person:
            raise RecallRefusal("--hit needs --by NAME")
        try:
            verdict = HitVerdict(word.upper())
        except ValueError as exc:
            raise RecallRefusal(f"verdict must be one of {[v.value for v in HitVerdict]}") from exc
        with recall_lock(services):
            record = record_person_hit(
                services.store, cases, key, bug_id, verdict, person, services.clock
            )
        typer.echo(f"recorded {verdict.value} for {key} {bug_id} as {record.labeler}")
        return
    recipes = [load_recipe(path) for path in recipe_paths]
    found = undecided_candidates(
        services.store, cases, recipes, list(range(1, runs + 1)), services.stage_resolver
    )
    typer.echo(f"{len(found)} undecided candidates")
    for candidate in found:
        for line in render_candidate(candidate):
            typer.echo(line)


def make_label_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def label_command(
        set_ref: Annotated[str, typer.Option("--set", help="Case set, NAME or NAME@VERSION.")],
        recipe_paths: Annotated[
            list[Path] | None, typer.Option("--recipe", help="Only findings these recipes keep.")
        ] = None,
        case_names: Annotated[
            list[str] | None, typer.Option("--case", help="Only this case (repeatable).")
        ] = None,
        runs: Annotated[int, typer.Option("--runs", help="With --recipe: run indexes 1..N.")] = 1,
        hit: Annotated[
            tuple[str, str, str] | None,
            typer.Option("--hit", help="FINDING_KEY BUG HIT|ADJACENT|MISS: record a label."),
        ] = None,
        person: Annotated[str | None, typer.Option("--by", help="Who decides (with --hit).")] = None,
    ) -> None:
        """List undecided hit candidates, or record one person's hit label with --hit."""
        try:
            run_label(
                open_services(services_factory),
                set_ref,
                recipe_paths or [],
                case_names or [],
                runs,
                hit,
                person,
            )
        except (*REFUSED_ERRORS, RecipeError) as exc:
            raise stderr_exit(f"Error: {exc}") from exc

    return label_command
