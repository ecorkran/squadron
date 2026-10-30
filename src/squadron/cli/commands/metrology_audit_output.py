"""Console output for audit runs, shared by ``audit run``, ``audit variance`` and ``baseline``."""

from __future__ import annotations

from collections.abc import Callable

import typer
from rich import print as rprint

from squadron.metrology.audit import AuditProgress, AuditRunResult


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
