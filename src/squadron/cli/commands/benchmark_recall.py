"""``sq benchmark recall``: reviewer recall on real escaped bugs (slice 430).

Each ``make_*`` takes the one seam, ``services_factory``: production passes
``build_production_recall_services``; tests pass doubles. Commands hold no recall logic.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.recall.case_intake import expand_case_paths, validate_case_files
from squadron.benchmark.recall.recall_services import (
    RecallRefusal,
    RecallServices,
    RecallServicesFactory,
    build_production_recall_services,
    recall_lock,
)
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.cli.commands.benchmark_recall_common import REFUSED_ERRORS, open_services
from squadron.cli.commands.benchmark_recall_import import make_import_command
from squadron.cli.commands.benchmark_recall_label import make_label_command
from squadron.cli.commands.benchmark_recall_render import render_cases
from squadron.cli.commands.benchmark_recall_report import make_report_command
from squadron.cli.commands.benchmark_recall_run import make_run_command
from squadron.cli.commands.benchmark_recall_stage import STAGE_COMMAND, stage_command


def _cases_add(services: RecallServices, paths: list[Path], set_name: str) -> int:
    files = expand_case_paths(paths)
    if not files:
        raise RecallRefusal(f"no case files found in {', '.join(str(p) for p in paths)}")
    result = validate_case_files(files, services.kind_context())
    if result.failures:
        for failure in result.failures:
            typer.echo(f"refused: {failure.path}: {failure.reason}", err=True)
        typer.echo(f"Error: {len(result.failures)} case file(s) refused; nothing written", err=True)
        return 1
    with recall_lock(services):
        written = sum(services.store.write_case(case) for case in result.cases)
        case_set = services.store.write_case_set(set_name, [case.case_id for case in result.cases])
    typer.echo(
        f"{len(result.cases)} cases ({written} new); set {case_set.name} v{case_set.version} "
        f"with {len(case_set.case_ids)} cases"
    )
    return 0


def make_cases_add_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def cases_add_command(
        paths: Annotated[list[Path], typer.Argument(help="Case files or folders of *.yaml files.")],
        set_name: Annotated[str, typer.Option("--set", help="Case set to write a version of.")],
    ) -> None:
        """Validate case files, write the cases and a new case-set version if membership changed."""
        try:
            code = _cases_add(open_services(services_factory), paths, set_name)
        except REFUSED_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        if code:
            raise typer.Exit(code)

    return cases_add_command


def make_cases_list_command(services_factory: RecallServicesFactory) -> Callable[..., None]:
    def cases_list_command(
        set_ref: Annotated[
            str | None, typer.Option("--set", help="Only this set (NAME or NAME@VERSION).")
        ] = None,
    ) -> None:
        """List case sets with versions, and each case's bugs, locations and repo status."""
        try:
            services = open_services(services_factory)
            sets = services.store.list_case_sets()
            if set_ref is None:
                cases = services.store.list_cases()
            else:
                chosen = services.store.resolve_set(set_ref)
                sets = [s for s in sets if s.name == chosen.name]
                found = [services.store.get_case(cid) for cid in chosen.case_ids]
                cases = [case for case in found if case is not None]
        except REFUSED_ERRORS as exc:
            raise stderr_exit(f"Error: {exc}") from exc
        typer.echo(render_cases(sets, cases))

    return cases_list_command


def build_recall_app(factory: RecallServicesFactory) -> typer.Typer:
    """The ``recall`` command group, every command bound to *factory*."""
    app = typer.Typer(
        name="recall",
        help="Code-review recall on real escaped bugs: cases, import, run, label, report.",
        no_args_is_help=True,
    )
    cases = typer.Typer(name="cases", help="Recall case files and case sets.", no_args_is_help=True)
    cases.command("add")(make_cases_add_command(factory))
    cases.command("list")(make_cases_list_command(factory))
    app.add_typer(cases, name="cases")
    app.command("import")(make_import_command(factory))
    app.command("run")(make_run_command(factory))
    app.command("label")(make_label_command(factory))
    app.command("report")(make_report_command(factory))
    app.command(STAGE_COMMAND, hidden=True)(stage_command)
    return app


recall_app = build_recall_app(build_production_recall_services)
