"""``sq metrology baseline`` (slice 404).

One command to start measuring an existing project: checks every setting up
front, prints the scope, takes a code snapshot of the clean HEAD, then runs the
audit variance series at that commit and writes its noise floor. A thin shell
over ``prepare_baseline``, ``take_snapshot`` and ``run_audit_series``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
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
from squadron.metrology.audit import (
    AuditPreflightError,
    AuditRunResult,
    AuditSkillError,
    find_audit_file,
    run_audit,
)
from squadron.metrology.audit_series import (
    AuditSeriesRequest,
    AuditSeriesResult,
    NoFloorReason,
    run_audit_series,
)
from squadron.metrology.audit_variance import MIN_USABLE_RUNS
from squadron.metrology.baseline import BaselinePlan, prepare_baseline
from squadron.metrology.errors import BaselinePreflightError, MetrologyStoreError
from squadron.metrology.preview import abbrev
from squadron.metrology.snapshot.contract import AdapterRegistry
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.render import render_summary
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot.take import take_snapshot
from squadron.metrology.snapshot_models import CodeSnapshot
from squadron.metrology.store import MetrologyStore, resolve_store_dir

_logger = logging.getLogger(__name__)

#: Failures that stop the command before anything is written or spent.
PREFLIGHT_FAILURES = (*SNAPSHOT_FAILURES, BaselinePreflightError, AuditPreflightError, AuditSkillError)


INTERRUPTED_EXIT_CODE = 130  # the shell convention for SIGINT


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


class _CountingPrinter(SeriesPrinter):
    """The series printer, plus a count of the runs that completed this session."""

    def __init__(self, label: str, n_runs: int) -> None:
        super().__init__(label, n_runs)
        self.completed = 0

    def on_outcome(self, run_number: int, outcome: AuditRunResult) -> None:
        super().on_outcome(run_number, outcome)
        if outcome.succeeded:
            self.completed += 1


@dataclass
class _Session:
    """What one command invocation has done so far; the failure reports read it."""

    plan: BaselinePlan
    registry: AdapterRegistry
    store: MetrologyStore
    store_dir: Path
    started: float
    printer: _CountingPrinter
    snapshot: CodeSnapshot | None = None


def _take_snapshot(session: _Session) -> CodeSnapshot:
    try:
        snapshot = take_snapshot(
            session.plan.project_path, session.registry, SubprocessToolRunner(), session.store
        )
    except SNAPSHOT_FAILURES as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    session.snapshot = snapshot
    typer.echo("Snapshot")
    for line in render_summary(snapshot, session.store.record_location(snapshot.snapshot_id)):
        typer.echo(f"  {line}")
    return snapshot


def _run_series(session: _Session, snapshot: CodeSnapshot) -> AuditSeriesResult:
    plan = session.plan
    typer.echo("Audit")
    request = AuditSeriesRequest(
        project_path=plan.project_path,
        runs=plan.runs,
        cooldown_s=plan.cooldown_s,
        profile=plan.profile,
        model=plan.model,
        expected_sha=snapshot.commit_sha,
        config_cwd=str(plan.project_path),
    )
    return run_audit_series(request, store=session.store, observer=session.printer, audit=run_audit)


def _print_analysis_file(session: _Session) -> None:
    """Name the file the audit wrote: it makes the next snapshot refuse a dirty tree."""
    written = find_audit_file(session.plan.project_path, newer_than=session.started)
    if written is None:
        return
    relative = written.relative_to(session.plan.project_path)
    typer.echo(f"The audit wrote {relative}. Remove or commit it before the next snapshot.")


def _report_result(session: _Session, result: AuditSeriesResult) -> int:
    plan = session.plan
    if result.floor is None:
        _print_no_floor(plan, result)
        _print_analysis_file(session)
        return 1
    print_floor(result.floor)
    campaign_summary(len(result.runs), result.failed, 1)
    _print_analysis_file(session)
    typer.echo(f"Next: sq metrology report baseline --project {plan.project_id.value}")
    return 0


def _report_interrupt(session: _Session) -> int:
    if session.snapshot is None:
        typer.echo("Interrupted before the snapshot finished. Nothing was recorded or spent.")
        return INTERRUPTED_EXIT_CODE
    typer.echo(
        f"Interrupted. Snapshot {session.snapshot.snapshot_id} is kept; "
        f"{session.printer.completed} run(s) completed."
    )
    typer.echo(f"Run a fresh series: {_recovery_command(session.plan.project_path)}")
    _print_analysis_file(session)
    return INTERRUPTED_EXIT_CODE


def _report_store_error(session: _Session, exc: MetrologyStoreError) -> int:
    typer.echo(f"Store error: {exc}", err=True)
    typer.echo(
        f"Store: {session.store_dir}; {session.printer.completed} run(s) persisted this session."
    )
    typer.echo(f"Run a fresh series: {_recovery_command(session.plan.project_path)}")
    _print_analysis_file(session)
    return 1


def _execute(session: _Session) -> int:
    """Snapshot, then the series; returns the exit code."""
    try:
        result = _run_series(session, _take_snapshot(session))
    except KeyboardInterrupt:
        # Process boundary: the one place Ctrl-C is caught. The interrupted run
        # persisted nothing; everything completed is already in the store.
        return _report_interrupt(session)
    except MetrologyStoreError as exc:
        _logger.exception("Baseline could not write to the metrology store %s", session.store_dir)
        return _report_store_error(session, exc)
    return _report_result(session, result)


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
        without a floor, keeping the snapshot and the runs that completed; exits
        130 when interrupted.

        The audit skill writes an analysis file into the project; remove or
        commit it before the next snapshot.

        Security: baselining a repository runs executables and config taken from
        that repository: its .venv/bin/ruff, .venv/bin/pyright and .venv/bin/python,
        node_modules/.bin/eslint and its JavaScript config. That executes the
        repository's code, with your full environment (including any secrets in it)
        inherited. Only baseline repositories you trust.
        """
        started = time.time()
        project_path = Path(path).expanduser().resolve()
        registry = default_registry()
        try:
            plan = prepare_baseline(project_path, registry, profile=profile, model=model)
        except PREFLIGHT_FAILURES as exc:
            typer.echo(f"Error: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        _print_scope(plan)
        store_dir = resolve_store_dir(cwd=str(project_path))
        session = _Session(
            plan=plan,
            registry=registry,
            store=MetrologyStore(store_dir=store_dir),
            store_dir=store_dir,
            started=started,
            printer=_CountingPrinter(project_path.name, plan.runs),
        )
        exit_code = _execute(session)
        if exit_code != 0:
            raise typer.Exit(code=exit_code)
