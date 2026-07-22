"""metrology subcommand — blind human-sample capture and store inspection.

A thin Typer shell over ``squadron.metrology`` (the ``config`` sub-app
pattern): all logic lives in the core, so the future MCP surface wraps the
same functions with zero duplication.
"""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich import print as rprint

from squadron.config.manager import get_config
from squadron.metrology.capture import (
    build_capture_payload,
    record_sample,
    resolve_target,
    reveal,
)
from squadron.metrology.errors import (
    MetrologyIdentityError,
    MetrologyStoreError,
    MetrologyTargetError,
)
from squadron.metrology.models import JudgeConfigId
from squadron.metrology.store import MetrologyStore, resolve_store_dir
from squadron.review.models import Verdict

metrology_app = typer.Typer(
    name="metrology",
    help="Capture and inspect blind human calibration samples.",
    no_args_is_help=True,
)

_VERDICT_CHOICES = "/".join(v.value for v in (Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL))


def _resolve_cwd(cwd: str | None) -> str:
    """Resolve the project root the metrology commands operate against.

    Defaults to the process working directory (``.``), **not** the ``cwd``
    config key: that key scopes the review models' document-content lookups
    (it points inside ``project-documents/user``), whereas reviews are
    persisted by ``save_review_result`` relative to the process working
    directory. Identity derivation and target resolution both need the repo
    root, which is the process dir. An explicit ``--cwd`` overrides.
    """
    return cwd if cwd is not None else "."


def _parse_verdict(raw: str) -> Verdict | None:
    """Parse a verdict string case-insensitively; None if unrecognized."""
    try:
        return Verdict(raw.strip().upper())
    except ValueError:
        return None


def _build_store(cwd: str) -> MetrologyStore:
    return MetrologyStore(store_dir=resolve_store_dir(cwd=cwd))


def _sample_budget() -> int:
    value = get_config("metrology.sample_budget")
    return value if isinstance(value, int) else 0


@metrology_app.command("sample")
def sample(
    target: str = typer.Argument(help="Review-file path, or a bare slice index with --type"),
    review_type: str | None = typer.Option(
        None, "--type", help="Review type when target is a bare index (e.g. slice, code)"
    ),
    verdict: str | None = typer.Option(
        None, "--verdict", help=f"Non-interactive verdict ({_VERDICT_CHOICES})"
    ),
    note: str | None = typer.Option(None, "--note", help="Optional one-line note"),
    skip: bool = typer.Option(False, "--skip", help="Skip: record nothing, exit 0"),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Blind-capture a human verdict for one persisted judge result."""
    if skip:
        rprint("[dim]sample skipped[/dim]")
        return

    resolved_cwd = _resolve_cwd(cwd)

    try:
        review_file = resolve_target(target, review_type, resolved_cwd)
        payload = build_capture_payload(review_file, resolved_cwd)
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    # Blind presentation: artifact + ground truth only, never judge output.
    rprint(f"[bold]Artifact:[/bold] {payload.artifact_path or '(unknown)'}")
    if payload.ground_truth_text is not None:
        rprint("[bold]Ground truth:[/bold]")
        rprint(payload.ground_truth_text)
    else:
        rprint("[yellow](ground-truth source not found on disk)[/yellow]")

    chosen = _collect_verdict(verdict)
    if chosen is None:
        return  # skip / interrupt / empty — records nothing, exit 0

    try:
        outcome = record_sample(
            payload,
            chosen,
            note,
            store=_build_store(resolved_cwd),
            cwd=resolved_cwd,
            sample_budget=_sample_budget(),
        )
    except MetrologyIdentityError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyTargetError as exc:
        rprint(f"[red]Error: {exc}[/red]")
        raise typer.Exit(code=1) from exc
    except MetrologyStoreError as exc:
        rprint(f"[red]Store error: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if outcome.budget_reached:
        rprint(
            f"[yellow]Sample budget reached for this project "
            f"(limit {outcome.budget_limit}). Nothing recorded.[/yellow]"
        )
        return  # a ceiling, not an error — exit 0

    rprint(f"[green]Recorded[/green] {outcome.sample_id}")
    _offer_reveal(review_file)


def _collect_verdict(verdict_flag: str | None) -> Verdict | None:
    """Resolve the human verdict, honoring non-interactive and skip rules.

    Returns the chosen ``Verdict``, or ``None`` when the human declined to
    record (empty / interrupt / skip). Raises ``typer.Exit(1)`` for the hard
    errors: a non-TTY without ``--verdict``, and an invalid ``--verdict``.
    """
    if verdict_flag is not None:
        parsed = _parse_verdict(verdict_flag)
        if parsed is None:
            rprint(
                f"[red]Error: invalid --verdict {verdict_flag!r} "
                f"(expected one of {_VERDICT_CHOICES}).[/red]"
            )
            raise typer.Exit(code=1)
        return parsed

    if not sys.stdin.isatty():
        rprint(
            "[red]Error: non-interactive stdin — pass --verdict "
            f"({_VERDICT_CHOICES}) to record a sample.[/red]"
        )
        raise typer.Exit(code=1)

    # Interactive: re-prompt on invalid input; interrupt/EOF/empty = skip.
    while True:
        try:
            raw = typer.prompt(f"Your verdict [{_VERDICT_CHOICES}]", default="", show_default=False)
        except (KeyboardInterrupt, EOFError, typer.Abort):
            rprint("[dim]sample skipped[/dim]")
            return None
        if not raw.strip():
            rprint("[dim]sample skipped[/dim]")
            return None
        parsed = _parse_verdict(raw)
        if parsed is not None:
            return parsed
        rprint(f"[yellow]Not a verdict. Choose one of {_VERDICT_CHOICES}.[/yellow]")


def _offer_reveal(review_file: Path) -> None:
    """Post-commit only: optionally show the judge output (never affects record)."""
    if not sys.stdin.isatty():
        return
    try:
        show = typer.confirm("Reveal the judge's output now?", default=False)
    except (KeyboardInterrupt, EOFError, typer.Abort):
        return
    if not show:
        return
    judge = reveal(review_file)
    rprint("[bold]Judge output (post-commit):[/bold]")
    for key, value in judge.items():
        rprint(f"  {key}: {value}")


@metrology_app.command("list")
def list_samples(
    project: str | None = typer.Option(None, "--project", help="Filter by project id"),
    judge_config: str | None = typer.Option(
        None, "--judge-config", help="Filter by 'template_name|model'"
    ),
    cwd: str | None = typer.Option(None, "--cwd", help="Working directory"),
) -> None:
    """Print raw stored samples (inspection aid — not the 321 report)."""
    resolved_cwd = _resolve_cwd(cwd)
    config_filter: JudgeConfigId | None = None
    if judge_config is not None:
        if "|" not in judge_config:
            rprint("[red]Error: --judge-config must be 'template_name|model'.[/red]")
            raise typer.Exit(code=1)
        template_name, _, model = judge_config.partition("|")
        config_filter = JudgeConfigId(template_name=template_name, model=model)

    store = _build_store(resolved_cwd)
    samples = store.list_samples(project_id=project, judge_config=config_filter)
    if not samples:
        rprint("[dim]No samples recorded.[/dim]")
        return
    for sample_record in samples:
        rprint(
            f"{sample_record.sample_id}  {sample_record.project_id.value}  "
            f"{sample_record.human_verdict.value}  "
            f"{sample_record.judge_config.template_name}/{sample_record.judge_config.model}  "
            f"-> {sample_record.result_ref.relative_review_path}"
        )
