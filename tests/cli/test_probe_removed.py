"""``sq probe`` was replaced by ``sq onboard`` (slice 440)."""

from __future__ import annotations

from typing import cast

import click
from typer.main import get_command

from squadron.cli.app import app


def test_probe_is_not_a_registered_command() -> None:
    root = cast("click.Group", get_command(app))
    assert "probe" not in root.commands
