"""``commands/sq/benchmark.md`` lists ``grade``, ``report``, ``judge`` and ``slice-cases build`` with
their real options (slices 425, 426)."""

from __future__ import annotations

from pathlib import Path

import click
import pytest
import typer.main

from squadron.cli.commands.benchmark import benchmark_app

COMMAND_FILE = Path(__file__).resolve().parents[2] / "commands" / "sq" / "benchmark.md"


def _flags(name: str) -> set[str]:
    """The ``--flags`` of a benchmark subcommand; ``slice-cases build`` is a nested one."""
    group = typer.main.get_command(benchmark_app)
    assert isinstance(group, click.Group)
    command = group
    for part in name.split():
        assert isinstance(command, click.Group)
        command = command.commands[part]
    return {
        opt for param in command.params for opt in getattr(param, "opts", []) if opt.startswith("--")
    }


@pytest.mark.parametrize(
    "name",
    [
        "grade",
        "report",
        "judge",
        "slice-cases build",
        "recall cases add",
        "recall cases list",
        "recall import",
        "recall run",
        "recall label",
        "recall report",
    ],
)
def test_every_option_of_the_typer_command_is_listed(name: str) -> None:
    text = COMMAND_FILE.read_text(encoding="utf-8")
    signature = next(part for part in text.split("`") if part.startswith(f"{name} "))
    flags = _flags(name)
    assert flags, name
    for flag in flags:
        assert flag in signature, f"{flag} missing from the {name} signature in benchmark.md"


def test_the_file_still_just_runs_the_command_with_the_arguments() -> None:
    text = COMMAND_FILE.read_text(encoding="utf-8")
    assert text.startswith("Run the following command and display the results:")
    assert "`sq benchmark $ARGUMENTS`" in text
