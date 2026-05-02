"""[hidden] Execute a one-shot dispatch via a non-SDK provider profile.

Used by prompt-only pipeline rendering when a dispatch step is configured
with a non-SDK model alias. The harness invokes this command to perform
the actual dispatch call and print the result to stdout.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import typer

from squadron.pipeline.actions.dispatch import one_shot_dispatch


def dispatch_run(
    prompt_file: Path = typer.Option(
        ..., "--prompt-file", help="Path to prompt text file."
    ),
    model: str = typer.Option(..., "--model", help="Resolved model ID."),
    profile: str | None = typer.Option(
        None, "--profile", help="Provider profile name."
    ),
    param: list[str] = typer.Option(
        [],
        "--param",
        "-p",
        help="key=value pipeline parameters (repeatable).",
    ),
    system_prompt: str | None = typer.Option(
        None, "--system-prompt", help="System prompt text."
    ),
) -> None:
    """[hidden] Run a one-shot dispatch via a non-SDK provider profile."""
    if not prompt_file.exists():
        print(f"Error: prompt file not found — {prompt_file}", file=sys.stderr)
        raise typer.Exit(code=1)

    try:
        prompt_text = prompt_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"Error: could not read prompt file — {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

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

    resolved_profile = profile
    model_id = model

    if resolved_profile is None:
        from squadron.pipeline.resolver import ModelResolver

        resolver = ModelResolver()
        try:
            model_id, resolved_profile_or_none = resolver.resolve(model)
            resolved_profile = resolved_profile_or_none or "sdk"
        except Exception as exc:
            print(f"Error: model resolution failed — {exc}", file=sys.stderr)
            raise typer.Exit(code=1)

    try:
        result = asyncio.run(
            one_shot_dispatch(
                prompt=prompt_text,
                model_id=model_id,
                profile_name=resolved_profile,
                system_prompt=system_prompt or "",
            )
        )
    except KeyError as exc:
        print(f"Error: unknown profile — {exc}", file=sys.stderr)
        raise typer.Exit(code=1)
    except Exception as exc:
        print(f"Error: provider failure — {exc}", file=sys.stderr)
        raise typer.Exit(code=1)

    print(result)
