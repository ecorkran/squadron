"""events subcommand — sq events fire / sq events list (design D8)."""

from __future__ import annotations

import asyncio

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.events import EventType
from squadron.events.contexts import CommitContext
from squadron.events.discovery import PluginLoadError
from squadron.events.dispatcher import OutcomeErrorKind, run_event
from squadron.events.manifest import ManifestError, load_manifest

events_app = typer.Typer(
    name="events",
    help="Run and inspect user-definable actions on supported events.",
    no_args_is_help=True,
)


@events_app.command("fire")
def events_fire(
    event: str = typer.Argument(help="Event to fire: 'commit'"),
    paths: list[str] | None = typer.Argument(default=None, help="Staged paths (commit event only)"),
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Fire all bound actions for *event* and exit 0/1/2 per D8."""
    if event == EventType.POST_ACTION.value:
        rprint(
            "[red]Error: 'post-action' has no meaning outside a pipeline run — "
            "it cannot be fired from the CLI.[/red]"
        )
        raise typer.Exit(code=2)

    try:
        event_type = EventType(event)
    except ValueError:
        valid = [member.value for member in EventType]
        rprint(
            f"[red]Error: unknown event '{escape(str(event))}'. "
            f"Valid events: {escape(str(valid))}[/red]"
        )
        raise typer.Exit(code=2) from None

    context = CommitContext(event=event_type, cwd=cwd, params={}, staged_paths=tuple(paths or []))

    try:
        outcomes = asyncio.run(run_event(context))
    except (PluginLoadError, ManifestError) as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]")
        raise typer.Exit(code=2) from exc

    any_failed = False
    for outcome in outcomes:
        if outcome.error_kind is OutcomeErrorKind.TIMEOUT:
            rprint(f"[red]{escape(str(outcome.action_name))}: timed out[/red]")
            any_failed = True
        elif outcome.error_kind is OutcomeErrorKind.RAISED:
            rprint(f"[red]{escape(str(outcome.action_name))}: raised an exception[/red]")
            any_failed = True
        elif outcome.result is not None and not outcome.result.success:
            rprint(
                f"[red]{escape(str(outcome.action_name))}: {escape(str(outcome.result.error))}[/red]"
            )
            any_failed = True
        else:
            rprint(f"[green]{escape(str(outcome.action_name))}: ok[/green]")

    raise typer.Exit(code=1 if any_failed else 0)


@events_app.command("list")
def events_list(
    cwd: str = typer.Option(".", "--cwd", help="Working directory"),
) -> None:
    """Show every binding grouped by event, with its source."""
    try:
        manifest = load_manifest(cwd=cwd)
    except ManifestError as exc:
        rprint(f"[red]Error: {escape(str(exc))}[/red]")
        raise typer.Exit(code=2) from exc

    for member in EventType:
        rprint(f"[bold]{escape(str(member.value))}[/bold]")
        bindings = [b for b in manifest.bindings if b.event is member]
        if not bindings:
            rprint("  (no bindings)")
        for binding in bindings:
            rprint(f"  {escape(str(binding.action))}  ({escape(str(binding.source))})")

    if manifest.disabled:
        rprint("[bold]disabled[/bold]")
        for name in sorted(manifest.disabled):
            rprint(f"  {escape(str(name))}  (disabled)")
