"""[hidden] Emit rendered compaction template instructions to stdout.

Used by the ``/sq:summary`` slash command to obtain deterministic,
template-driven summary instructions for the current Claude Code session.
"""

from __future__ import annotations

import sys

import typer

from squadron.config.manager import get_config
from squadron.pipeline.summary_render import resolve_template_instructions


def summary_instructions(
    template: str = typer.Argument(
        None,
        help="Compaction template name (e.g. 'minimal', 'minimal-sdk').",
    ),
    cwd: str = typer.Option(".", "--cwd", hidden=True),
) -> None:
    """[hidden] Print rendered compaction template instructions."""
    # Template name resolution: explicit arg > config > "minimal"
    if not template:
        config_val = get_config("compact.template", cwd=cwd)
        template = (
            config_val if isinstance(config_val, str) and config_val else "minimal"
        )

    try:
        rendered = resolve_template_instructions(template, cwd=cwd)
    except FileNotFoundError:
        print(f"Error: template '{template}' not found.", file=sys.stderr)
        raise typer.Exit(code=1)

    print(rendered)
