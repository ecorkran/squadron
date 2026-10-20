"""probe command — report which brownfield capabilities are available here."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from squadron.probe import build_probe

COMPACT_SEPARATORS = (",", ":")
PRETTY_INDENT = 2


def probe(
    as_json: bool = typer.Option(False, "--json", help="Print one compact JSON line, for programs."),
) -> None:
    """Report installed analysis skills, the understand plugin, and the knowledge graph state.

    Exits 0 whenever the probe can report, including when everything is absent. Fields
    it cannot determine are null, with a warning on stderr. Exits 1 only if the probe
    itself breaks. Field definitions: project-documents/user/reference/capability-probe-contract.md.
    """
    try:
        report = build_probe(Path.cwd())
    except Exception as error:  # noqa: BLE001  # process boundary: any probe failure is exit 1
        typer.echo(f"sq probe failed: {type(error).__name__}: {error}", err=True)
        raise typer.Exit(code=1) from error
    if as_json:
        typer.echo(json.dumps(report, separators=COMPACT_SEPARATORS))
    else:
        typer.echo(json.dumps(report, indent=PRETTY_INDENT))
