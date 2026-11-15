"""``sq benchmark slice-cases build`` (slice 426); ``judge`` is in ``benchmark_judge.py``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.build_errors import BuildHalted
from squadron.benchmark.production_deps import CASE_LANGUAGE
from squadron.benchmark.registry import adapter_for, fix_case_adapter_for
from squadron.benchmark.sandbox import sweep_benchmark_orphans
from squadron.benchmark.slice_case_build import SliceBuildDeps, build_slice_cases
from squadron.benchmark.slice_qualify_types import SliceQualifyDeps
from squadron.benchmark.slice_yield import build_slice_yield, render_slice_text
from squadron.cli.commands.benchmark_common import open_store, repo_root_for, stderr_exit
from squadron.cli.commands.benchmark_fix_cases import RepoOption, make_sandbox_factory
from squadron.codehost.git_refs import GIT_QUERY_TIMEOUT_SECONDS
from squadron.config.keys import (
    BENCHMARK_INSTALL_TIMEOUT_KEY,
    BENCHMARK_QUALIFICATION_REPEATS_KEY,
    BENCHMARK_SUITE_TIMEOUT_KEY,
)
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import ProcessRunner, SubprocessRunner
from squadron.metrology.errors import MetrologyIdentityError, MetrologyStoreError
from squadron.metrology.identity import derive_project_id
from squadron.metrology.slice_case_store import SliceCaseRecordStore

slice_cases_app = typer.Typer(
    name="slice-cases",
    help="Build cases from a project's completed slices.",
    no_args_is_help=True,
)


def build_deps(repo_root: Path, *, keep: bool, runner: ProcessRunner | None = None) -> SliceBuildDeps:
    """The real collaborators of a slice-case build: store, adapters, runner, sandboxes, clock.

    Reads the install, suite and repeat settings for *repo_root*, so a bad setting raises
    ``ValueError`` naming it before anything runs. Runs no process.
    """
    process_runner = runner if runner is not None else SubprocessRunner()
    install_s = get_positive_int_config(BENCHMARK_INSTALL_TIMEOUT_KEY, cwd=str(repo_root))
    suite_s = get_positive_int_config(BENCHMARK_SUITE_TIMEOUT_KEY, cwd=str(repo_root))
    repeats = get_positive_int_config(BENCHMARK_QUALIFICATION_REPEATS_KEY, cwd=str(repo_root))
    records = open_store(repo_root)
    qualify = SliceQualifyDeps(
        project_id=derive_project_id(str(repo_root)),
        repo=repo_root,
        runner=process_runner,
        qualifications=SliceCaseRecordStore(records),
        cases=records,
        sandbox_factory=make_sandbox_factory(
            repo_root, process_runner, keep=False, install_timeout_s=install_s, suite_timeout_s=suite_s
        ),
        adapter=fix_case_adapter_for(CASE_LANGUAGE),
        suite_runner=adapter_for(CASE_LANGUAGE),
        repeats=repeats,
        git_timeout_s=GIT_QUERY_TIMEOUT_SECONDS,
        clock=lambda: datetime.now(UTC),
        keep=keep,
    )
    return SliceBuildDeps(qualify=qualify, ranges=records.metrology_store, case_sets=records)


@slice_cases_app.command("build")
def build_command(
    set_name: Annotated[str, typer.Option("--set", help="Name of the case set to write.")],
    repo: RepoOption = None,
    keep: Annotated[
        bool,
        typer.Option("--keep", help="Leave the fork and tip qualification sandboxes in place."),
    ] = False,
) -> None:
    """Qualify each completed slice as a slice case and write the case set."""
    runner = SubprocessRunner()
    repo_root = repo_root_for(runner, repo)
    sweep_benchmark_orphans(runner)
    try:
        deps = build_deps(repo_root, keep=keep, runner=runner)
    except (ValueError, MetrologyIdentityError) as exc:
        raise stderr_exit(str(exc)) from exc
    try:
        result = build_slice_cases(repo_root, set_name, deps, typer.echo)
    except BuildHalted as exc:
        raise stderr_exit(str(exc)) from exc
    if result.case_set is None:
        typer.echo("no qualified cases: no case set written")
    else:
        typer.echo(f"case set {result.case_set.name} v{result.case_set.version}")
    for path in result.kept_paths:
        typer.echo(f"kept {path}")
    _print_yield(deps)
    if result.stopped_at is not None:
        raise stderr_exit(f"build stopped at slice {result.stopped_at}: a harness failure")


def _print_yield(deps: SliceBuildDeps) -> None:
    """The slice-case yield rows for this project."""
    project = deps.qualify.project_id
    try:
        records = deps.qualify.qualifications.list_slice_qualifications(project)
    except MetrologyStoreError as exc:
        raise stderr_exit(str(exc)) from exc
    typer.echo("")
    typer.echo(render_slice_text(build_slice_yield(records)), nl=False)
