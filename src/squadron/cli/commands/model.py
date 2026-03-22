"""model subcommand — model alias management."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from squadron.models.aliases import BUILT_IN_ALIASES, get_all_aliases

model_app = typer.Typer(
    name="model",
    help="Model alias management.",
    no_args_is_help=True,
)


@model_app.command("list")
def model_list() -> None:
    """List available model aliases."""
    all_aliases = get_all_aliases()
    if not all_aliases:
        typer.echo("No model aliases configured.")
        return

    console = Console()
    table = Table(show_header=True, header_style="bold")
    table.add_column("Alias", style="cyan")
    table.add_column("Profile")
    table.add_column("Model ID")
    table.add_column("Source", style="dim")

    for name, alias in sorted(all_aliases.items()):
        source = "(user)" if name not in BUILT_IN_ALIASES else ""
        if name in BUILT_IN_ALIASES and alias != BUILT_IN_ALIASES[name]:
            source = "(user override)"
        table.add_row(name, alias["profile"], alias["model"], source)

    console.print(table)
