"""Console output for audit runs, shared by ``audit run``, ``audit variance`` and ``baseline``."""

from __future__ import annotations

from collections.abc import Callable

import typer
from rich import print as rprint

from squadron.metrology.audit import AuditProgress, AuditRunResult
from squadron.metrology.models import AuditNoiseFloor


def make_progress_reporter(label: str) -> Callable[[AuditProgress], None]:
    """Return a callback that keeps a live audit visibly alive.

    A full audit takes 5-20 minutes and emits no prose until it finishes, so
    without this the command looks hung — and an operator cannot tell a
    working run from a stalled one. Writes to stderr on a single rewritten
    line so ``--json`` on stdout stays machine-readable.
    """

    def _report(progress: AuditProgress) -> None:
        typer.echo(
            f"\r  {label} working… {progress.tool_events} tool calls, "
            f"{progress.bytes_received:,} bytes",
            err=True,
            nl=False,
        )

    return _report


def report_run_outcome(outcome: AuditRunResult, *, prefix: str = "") -> None:
    """Print one run's result. A 12-audit campaign must not look hung."""
    # Clear the in-place progress line before printing the durable result.
    typer.echo("\r" + " " * 78 + "\r", err=True, nl=False)
    if outcome.succeeded and outcome.run is not None:
        run = outcome.run
        rprint(
            f"{prefix}[green]ok[/green] {run.project_id.value} "
            f"@{run.commit_sha[:8]}  {len(run.findings)} findings"
            + (
                f" ([yellow]{run.unnormalized_count} unnormalized[/yellow])"
                if run.unnormalized_count
                else ""
            )
        )
        if outcome.rate_limit_summary:
            rprint(f"{prefix}[dim]{outcome.rate_limit_summary}[/dim]")
        return
    rprint(
        f"{prefix}[red]failed[/red] {outcome.project_path}  "
        f"{outcome.failure.value if outcome.failure else 'unknown'}: {outcome.detail or ''}"
    )
    if outcome.rate_limit_summary:
        rprint(f"{prefix}[dim]{outcome.rate_limit_summary}[/dim]")


def campaign_summary(succeeded: int, failed: int, floors_written: int | None = None) -> None:
    """Report the campaign honestly — a failed run is never hidden."""
    parts = [f"{succeeded} succeeded", f"{failed} failed"]
    if floors_written is not None:
        parts.append(f"{floors_written} floor(s) written")
    style = "yellow" if failed else "dim"
    rprint(f"[{style}]Campaign: {', '.join(parts)}.[/{style}]")


def print_floor(floor: AuditNoiseFloor) -> None:
    """Print the one-line noise floor a series produced."""
    rprint(
        f"[green]floor[/green] {floor.project_id.value} @{floor.commit_sha[:8]}  "
        f"total {floor.total.min}-{floor.total.max} "
        f"(mean {floor.total.mean:.1f}, sd {floor.total.stddev:.2f}, n={floor.n_runs})"
    )


class SeriesPrinter:
    """Prints a series' cooldown, run and live-progress lines (an ``AuditSeriesObserver``)."""

    def __init__(self, label: str, n_runs: int) -> None:
        self._label = label
        self._n_runs = n_runs

    def on_run_start(self, run_number: int) -> None:
        """Nothing is printed at run start; the progress line shows it."""

    def on_cooldown(self, run_number: int, cooldown_s: int) -> None:
        rprint(f"  [dim]cooling down {cooldown_s}s before run {run_number}[/dim]")

    def on_outcome(self, run_number: int, outcome: AuditRunResult) -> None:
        report_run_outcome(outcome, prefix=f"  run {run_number}/{self._n_runs}  ")

    def progress_callback(self, run_number: int) -> Callable[[AuditProgress], None] | None:
        return make_progress_reporter(f"{self._label} run {run_number}/{self._n_runs}")
