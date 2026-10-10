"""CLI helpers shared by the commands that install into a target runtime.

``install-commands``/``uninstall-commands`` and ``sq skills`` take the same
``--ide`` option and remove files through the same receipt routine; both parse
and report through here rather than one command module importing another.
"""

from __future__ import annotations

import typer
from rich import print as rprint
from rich.markup import escape

from squadron.skills.receipts import RemovalResult
from squadron.skills.targets import CommandTarget, normalize_target


def parse_ide_option(ide: str) -> CommandTarget:
    """Resolve the ``--ide`` value, or exit 2 naming the accepted spellings."""
    try:
        return normalize_target(ide)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from None


def report_skipped_entries(result: RemovalResult) -> None:
    """Print the receipt entries ``remove_receipt_files`` refused to follow."""
    for relative in result.skipped_outside:
        rprint(
            f"[yellow]Skipping receipt entry outside the install destination: "
            f"{escape(repr(relative))}[/yellow]"
        )
