"""Typer CLI application definition for the squadron framework."""

from __future__ import annotations

import importlib.metadata

import typer

from squadron.cli.commands.auth import auth_app
from squadron.cli.commands.config import config_app
from squadron.cli.commands.history import history
from squadron.cli.commands.install import install_commands, uninstall_commands
from squadron.cli.commands.list import list_agents
from squadron.cli.commands.message import message
from squadron.cli.commands.model import model_app
from squadron.cli.commands.models import models
from squadron.cli.commands.review import review_app
from squadron.cli.commands.serve import serve
from squadron.cli.commands.shutdown import shutdown
from squadron.cli.commands.spawn import spawn
from squadron.cli.commands.task import task

app = typer.Typer(
    name="squadron",
    help="Multi-agent squadron CLI",
    no_args_is_help=True,
)

app.command("serve")(serve)
app.command("spawn")(spawn)
app.command("list")(list_agents)
app.command("task")(task)
app.command("message")(message)
app.command("models")(models)
app.command("history")(history)
app.command("shutdown")(shutdown)
app.add_typer(review_app, name="review")
app.add_typer(model_app, name="model")
app.add_typer(config_app, name="config")
app.add_typer(auth_app, name="auth")
app.command("install-commands")(install_commands)
app.command("uninstall-commands")(uninstall_commands)


def version_callback(value: bool) -> None:
    if value:
        print(f"squadron {importlib.metadata.version('squadron-ai')}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Multi-agent squadron CLI."""
