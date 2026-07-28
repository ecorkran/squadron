"""``sq metrology preempt`` and ``sq metrology audit delta`` (324).

A thin Typer shell over ``squadron.metrology.preemption`` and
``squadron.metrology.audit_delta``, kept in its own module because
``metrology.py`` had already reached ~1000 lines. The apps defined here are
mounted onto the existing ``metrology``/``audit`` apps by the parent, so
the command surface is unchanged by the split.

Both commands refuse rather than improvise when a project has no stored
baseline: a fragment generated from nothing, or a delta measured against
nothing, would be a fabricated number wearing a real one's format.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
from rich import print as rprint

from squadron.config.manager import get_config
from squadron.metrology.audit import (
    AuditPreflightError,
    AuditSkillError,
    run_audit,
)
from squadron.metrology.audit_delta import compute_delta
from squadron.metrology.audit_models import DeltaCell, ProjectBaseline
from squadron.metrology.audit_report import baseline_report
from squadron.metrology.errors import (
    MetrologyIdentityError,
    MetrologyStoreError,
)
from squadron.metrology.identity import derive_project_id
from squadron.metrology.preemption import (
    check_freshness,
    fragment_path_for,
    render_fragment,
    write_fragment,
)
from squadron.metrology.store import MetrologyStore

#: Reported per cell when no floor was measured. Stated in full rather than
#: left blank so an uninterpretable delta is never read as a small one.
NO_FLOOR_CELL_NOTE = "no floor — delta not interpretable"

preempt_app = typer.Typer(
    name="preempt",
    help="Generate and check the static pre-emption fragment from a project's baseline.",
    no_args_is_help=True,
)


def _fragment_dir(cwd: str) -> Path:
    """The configured fragment directory, tilde-expanded.

    ``get_typed_config`` validates numerics only, so this follows the
    string-key precedent in ``metrology/audit.py``: read, then reject a
    non-string loudly rather than coercing one into a path.
    """
    value = get_config("metrology.preemption_fragment_dir", cwd=cwd)
    if not isinstance(value, str) or not value.strip():
        raise typer.BadParameter(
            "metrology.preemption_fragment_dir must be a non-empty path string. "
            "Fix it with 'sq config set metrology.preemption_fragment_dir <path>'."
        )
    return Path(value).expanduser()


def _load_baseline(project_path: Path, *, store: MetrologyStore, cwd: str) -> ProjectBaseline:
    """Resolve ``project_path`` to its stored baseline, or exit 1.

    A missing baseline is an error, not an empty result: every 324 surface
    exists to compare against one, and there is nothing to fall back to.
    """
    project_id = derive_project_id(str(project_path))
    report = baseline_report(store, project_filter=project_id.value)

    if not report.projects:
        rprint(
            f"[red]Error: no baseline found for {project_id.value} — run "
            f"'sq metrology audit run {project_path}' first[/red]"
        )
        raise typer.Exit(code=1)

    if len(report.projects) == 1:
        return report.projects[0]

    # baseline_report groups by (project, commit, instrument), so more than
    # one entry means the project was audited at several commits, under
    # several audit prompts, or both.
    instruments = {entry.audit_prompt_hash for entry in report.projects}
    if len(instruments) > 1:
        # Never pick silently across instruments: which audit prompt a
        # fragment or delta rests on is not an implementation detail.
        shown = ", ".join(sorted(value[:12] for value in instruments))
        rprint(
            f"[red]Error: {project_id.value} has baselines under more than one "
            f"audit instrument ({shown}). Re-measure under a single instrument "
            f"before generating a fragment or delta.[/red]"
        )
        raise typer.Exit(code=1)

    # One instrument, several commits: the most recent measurement is the
    # project's current baseline, which is the same rule baseline_report
    # applies within a group.
    return max(report.projects, key=lambda entry: entry.measured_at)


@preempt_app.command("generate")
def preempt_generate(
    project_path: str = typer.Argument(help="Project directory to generate a fragment for"),
    check: bool = typer.Option(
        False, "--check", help="Report whether the existing fragment is current; do not write"
    ),
    as_json: bool = typer.Option(
        False, "--json", help="Emit the PreemptionFragment (or FreshnessResult) verbatim"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Write a project's pre-emption fragment from its stored baseline.

    Regeneration is always explicit. Nothing regenerates a fragment on a
    schedule or as a side effect of an audit: a prompt that changes without
    an operator asking is a prompt nobody can reason about.

    With ``--check``, exits 0 when the fragment matches the current
    baseline and 1 when it is stale or absent, so CI can gate on it.
    """
    resolved_cwd = str(Path(cwd).expanduser()) if cwd else str(Path.cwd())
    resolved_project = Path(project_path).expanduser().resolve()

    try:
        store = MetrologyStore()
        baseline = _load_baseline(resolved_project, store=store, cwd=resolved_cwd)
        directory = _fragment_dir(resolved_cwd)

        if check:
            path = fragment_path_for(baseline.project_id.value, directory=directory)
            result = check_freshness(path, baseline)
            if as_json:
                typer.echo(result.model_dump_json())
            elif result.is_current:
                rprint(f"[green]Current[/green] — {path}")
            else:
                rprint(f"[yellow]{result.note}[/yellow]")
            if not result.is_current:
                raise typer.Exit(code=1)
            return

        fragment = render_fragment(baseline)
        path = write_fragment(fragment, directory=directory)
    except MetrologyIdentityError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if as_json:
        typer.echo(fragment.model_dump_json())
        return

    named = sum(1 for line in fragment.text.splitlines() if line.startswith("- "))
    rprint(f"[green]Wrote[/green] {path}")
    rprint(
        f"[dim]{named} issue class(es) named, from baseline "
        f"{fragment.audit_prompt_hash[:12]} measured {fragment.measured_at.isoformat()}[/dim]"
    )


def _cell_interpretation(cell: DeltaCell) -> str:
    """Render one cell's floor-relative reading, never inventing a verdict."""
    if cell.within_floor is None:
        return f"[yellow]{NO_FLOOR_CELL_NOTE}[/yellow]"
    if cell.within_floor:
        spread = cell.floor.max - cell.floor.min if cell.floor is not None else 0
        return f"[dim]within floor (spread {spread})[/dim]"
    return "[bold]outside floor[/bold]"


def register_delta_command(audit_app: typer.Typer) -> None:
    """Mount ``audit delta`` onto the parent module's existing audit app."""

    @audit_app.command("delta")
    def audit_delta(  # pyright: ignore[reportUnusedFunction]
        project_path: str = typer.Argument(help="Project directory to re-audit and compare"),
        profile: str | None = typer.Option(None, "--profile", help="Provider profile override"),
        as_json: bool = typer.Option(False, "--json", help="Emit the DeltaReport model verbatim"),
        cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
    ) -> None:
        """Run one fresh audit and compare it to the stored baseline.

        One run, not a variance series: the floor this delta is read
        against was already measured by ``audit variance``, and re-measuring
        it here would spend N runs to learn what is already stored.

        The comparison is observational. A delta smaller than the floor's
        observed spread is reported as indistinguishable from noise, and a
        category with no measured floor is reported as uninterpretable
        rather than as evidence of anything.
        """
        resolved_cwd = str(Path(cwd).expanduser()) if cwd else str(Path.cwd())
        resolved_project = Path(project_path).expanduser().resolve()

        try:
            store = MetrologyStore()
            baseline = _load_baseline(resolved_project, store=store, cwd=resolved_cwd)
        except MetrologyIdentityError as exc:
            rprint(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        except MetrologyStoreError as exc:
            rprint(f"[red]Store error: {exc}[/red]")
            raise typer.Exit(code=1) from exc

        if not as_json:
            rprint(f"[dim]Auditing {resolved_project.name}… (5-20 min, no output until done)[/dim]")

        try:
            outcome = asyncio.run(
                run_audit(
                    resolved_project,
                    store=store,
                    profile=profile,
                    model=None,
                    on_progress=None,
                    cwd=resolved_cwd,
                )
            )
        except (AuditPreflightError, AuditSkillError, MetrologyIdentityError) as exc:
            rprint(f"[red]Error: {exc}[/red]")
            raise typer.Exit(code=1) from exc
        except MetrologyStoreError as exc:
            rprint(f"[red]Store error: {exc}[/red]")
            raise typer.Exit(code=1) from exc

        if not outcome.succeeded or outcome.run is None:
            # A failed run persists nothing; reporting a partial delta from
            # it would attach a real format to a number that was never
            # measured.
            rprint(
                f"[red]Error: the audit run failed "
                f"({outcome.failure.value if outcome.failure else 'unknown'}) — "
                f"no delta computed[/red]"
            )
            raise typer.Exit(code=1)

        report = compute_delta(baseline, outcome.run)

        if as_json:
            typer.echo(report.model_dump_json())
            return

        total_reading = (
            NO_FLOOR_CELL_NOTE
            if report.total_within_floor is None
            else ("within floor" if report.total_within_floor else "outside floor")
        )
        rprint(
            f"\n[bold]{report.project_id.value}[/bold]  "
            f"{report.baseline_total} → {report.new_total} findings  "
            f"({report.total_delta:+d}, {total_reading})"
        )
        rprint(
            f"[dim]baseline @{report.baseline_commit_sha[:8]} → "
            f"new @{report.new_commit_sha[:8]}[/dim]\n"
        )
        for cell in report.cells:
            rprint(
                f"  {cell.category.value:<32} {cell.baseline_count:>3} → "
                f"{cell.new_count:>3}  {cell.delta:>+4}  {_cell_interpretation(cell)}"
            )
        rprint(f"\n[dim]{report.disclaimer}[/dim]")
