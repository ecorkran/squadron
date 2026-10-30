"""``sq metrology baseline`` (slice 404).

One command to start measuring an existing project: checks every setting up
front, prints the scope, takes a code snapshot of the clean HEAD, then runs the
audit variance series at that commit and writes its noise floor. A thin shell
over ``prepare_baseline``, ``take_snapshot`` and ``run_audit_series``.
"""

from __future__ import annotations

import logging
from pathlib import Path

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.cli.commands.metrology_audit_output import (
    SeriesPrinter,
    campaign_summary,
    print_floor,
)
from squadron.cli.commands.metrology_snapshot import SNAPSHOT_FAILURES
from squadron.metrology.audit import AuditPreflightError, AuditSkillError, run_audit
from squadron.metrology.audit_series import (
    AuditSeriesRequest,
    AuditSeriesResult,
    NoFloorReason,
    run_audit_series,
)
from squadron.metrology.audit_variance import MIN_USABLE_RUNS
from squadron.metrology.baseline import BaselinePlan, prepare_baseline
from squadron.metrology.errors import BaselinePreflightError
from squadron.metrology.preview import abbrev
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.render import render_summary
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot.take import take_snapshot
from squadron.metrology.store import MetrologyStore, resolve_store_dir

_logger = logging.getLogger(__name__)

#: Failures that stop the command before anything is written or spent.
PREFLIGHT_FAILURES = (*SNAPSHOT_FAILURES, BaselinePreflightError, AuditPreflightError, AuditSkillError)


def _recovery_command(project_path: Path) -> str:
    return f"sq metrology audit variance {project_path}"


def _print_scope(plan: BaselinePlan) -> None:
    """Informational only: no prompt, no wall-clock estimate (D5)."""
    typer.echo(f"Baseline for {plan.project_id.value} @{abbrev(plan.head_sha)}")
    typer.echo(
        f"  Scope: {plan.file_count:,} files, {plan.byte_count:,} bytes after exclusions "
        f"({len(plan.exclusions)} excluded patterns)"
    )
    typer.echo("         The audit agent reads the repository itself; exclusions don't limit it.")
    typer.echo(
        f"  Audit: {plan.runs} runs, profile {plan.profile}, model {plan.model}, "
        f"{plan.cooldown_s}s between runs"
    )


def _print_no_floor(plan: BaselinePlan, result: AuditSeriesResult) -> None:
    """Say why there is no floor, and how to get one."""
    if result.stop_error is not None:
        rprint(f"[red]Error: {escape(result.stop_error)}[/red]")
    if result.rate_limited:
        rprint("[yellow]Stopping: the provider is rate limiting.[/yellow]")
    if result.no_floor_reason is NoFloorReason.UNREDUCIBLE:
        rprint(f"[yellow]No floor: {escape(result.reduce_error or '')}[/yellow]")
    else:
        rprint(
            f"[yellow]No floor: {len(result.runs)} usable run(s); "
            f"{MIN_USABLE_RUNS} are required.[/yellow]"
        )
    typer.echo(
        f"The snapshot and completed runs are kept. Run a fresh series: "
        f"{_recovery_command(plan.project_path)}"
    )


def _run_series(plan: BaselinePlan, snapshot_sha: str, store: MetrologyStore) -> AuditSeriesResult:
    typer.echo("Audit")
    request = AuditSeriesRequest(
        project_path=plan.project_path,
        runs=plan.runs,
        cooldown_s=plan.cooldown_s,
        profile=plan.profile,
        model=plan.model,
        expected_sha=snapshot_sha,
        config_cwd=str(plan.project_path),
    )
    return run_audit_series(
        request,
        store=store,
        observer=SeriesPrinter(plan.project_path.name, plan.runs),
        audit=run_audit,
    )


def register_baseline_command(metrology_app: typer.Typer) -> None:
    """Mount ``baseline`` onto the parent module's existing metrology app."""

    @metrology_app.command("baseline")
    def baseline(  # pyright: ignore[reportUnusedFunction]
        path: str = typer.Argument(".", help="Project directory to baseline (default: current)"),
        profile: str | None = typer.Option(None, "--profile", help="Provider profile override"),
        model: str | None = typer.Option(None, "--model", help="Model override"),
    ) -> None:
        """Snapshot a project's clean HEAD, then measure its audit noise floor there.

        Checks every setting before anything runs (a pinned audit model is
        required), prints the scope, takes one code snapshot, then runs the
        audit variance series at that commit and writes the noise floor. Exits 1
        without a floor, keeping the snapshot and the runs that completed.

        The audit skill writes an analysis file into the project; remove or
        commit it before the next snapshot.

        Security: baselining a repository runs executables and config taken from
        that repository: its .venv/bin/ruff, .venv/bin/pyright and .venv/bin/python,
        node_modules/.bin/eslint and its JavaScript config. That executes the
        repository's code, with your full environment (including any secrets in it)
        inherited. Only baseline repositories you trust.
        """
        project_path = Path(path).expanduser().resolve()
        registry = default_registry()
        try:
            plan = prepare_baseline(project_path, registry, profile=profile, model=model)
        except PREFLIGHT_FAILURES as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        _print_scope(plan)
        store = MetrologyStore(store_dir=resolve_store_dir(cwd=str(project_path)))
        try:
            snapshot = take_snapshot(project_path, registry, SubprocessToolRunner(), store)
        except SNAPSHOT_FAILURES as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc
        typer.echo("Snapshot")
        for line in render_summary(snapshot, store.record_location(snapshot.snapshot_id)):
            typer.echo(f"  {line}")

        result = _run_series(plan, snapshot.commit_sha, store)
        if result.floor is None:
            _print_no_floor(plan, result)
            raise typer.Exit(code=1)
        print_floor(result.floor)
        campaign_summary(len(result.runs), result.failed, 1)
        typer.echo(f"Next: sq metrology report baseline --project {plan.project_id.value}")
