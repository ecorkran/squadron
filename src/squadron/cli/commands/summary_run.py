"""[hidden] Execute a one-shot summary via a non-SDK provider profile.

Used by prompt-only pipeline rendering when a summary step is configured
with a non-SDK model alias.  The harness invokes this command to perform
the actual summary call and print the result to stdout.
"""

from __future__ import annotations

import asyncio
import sys

import typer

from squadron.pipeline.compaction_templates import (
    load_compaction_template,
    render_instructions,
)
from squadron.pipeline.summary_oneshot import capture_summary_via_profile


def summary_run(
    template: str = typer.Option(..., "--template", help="Compaction template name."),
    profile: str = typer.Option(..., "--profile", help="Provider profile name."),
    model: str = typer.Option(..., "--model", help="Resolved model ID."),
    param: list[str] = typer.Option(
        [],
        "--param",
        "-p",
        help="key=value pipeline parameters (repeatable).",
    ),
) -> None:
    """[hidden] Run a one-shot summary via a non-SDK provider profile."""
    # Parse --param flags into a dict.
    params: dict[str, object] = {}
    for entry in param:
        if "=" not in entry:
            print(
                f"Error: --param value {entry!r} is missing '=' (expected key=value).",
                file=sys.stderr,
            )
            raise typer.Exit(code=1)
        key, _, value = entry.partition("=")
        params[key] = value

    # Load and render the compaction template.
    try:
        tmpl = load_compaction_template(template)
    except FileNotFoundError:
        print(f"Error: template {template!r} not found.", file=sys.stderr)
        raise typer.Exit(code=1)

    instructions = render_instructions(tmpl, pipeline_params=params)

    # Execute the one-shot summary.
    try:
        result = asyncio.run(
            capture_summary_via_profile(
                instructions=instructions,
                model_id=model,
                profile=profile,
            )
        )
    except KeyError as exc:
        print(f"Error: unknown profile — {exc}", file=sys.stderr)
        raise typer.Exit(code=1)
    except Exception as exc:
        print(f"Error: provider failure — {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(result)
