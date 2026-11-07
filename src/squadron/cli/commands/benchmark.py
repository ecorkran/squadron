"""``sq benchmark``: model benchmark harness commands (slice 421)."""

from __future__ import annotations

import asyncio
import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.auth_check import (
    PROBE_PROMPT,
    AuthAnswer,
    AuthCheckResult,
    ProbeStartError,
    UnresolvedProfileError,
    resolve_alias_profile,
    run_auth_check,
)
from squadron.benchmark.scrubbed_env import MissingHarnessHomeError, MissingHarnessToolError
from squadron.cli.commands.benchmark_sandbox import sandbox_command
from squadron.config.keys import BENCHMARK_AUTH_PROBE_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import SubprocessRunner
from squadron.pipeline.actions.dispatch import one_shot_dispatch

benchmark_app = typer.Typer(
    name="benchmark",
    help="Benchmark sandboxes and producer auth checks.",
    no_args_is_help=True,
)

benchmark_app.command("sandbox")(sandbox_command)

ModelOption = Annotated[str, typer.Option("--model", help="Model alias to probe.")]
ModelsOption = Annotated[
    list[str],
    typer.Option("--model", help="Model alias to check (repeatable).", show_default=False),
]


class SqNotFoundError(Exception):
    """``sq`` is not on the harness PATH, so the probe has no binary to run."""


def _stderr_exit(message: str) -> typer.Exit:
    typer.echo(message, err=True)
    return typer.Exit(1)


@benchmark_app.command("_auth-probe", hidden=True)
def auth_probe(model: ModelOption) -> None:
    """Send the probe prompt through the real dispatch path (run in a scrubbed home)."""
    try:
        model_id, profile = resolve_alias_profile(model)
    except UnresolvedProfileError as exc:
        raise _stderr_exit(str(exc)) from exc
    try:
        response = asyncio.run(
            one_shot_dispatch(prompt=PROBE_PROMPT, model_id=model_id, profile_name=profile)
        )
    except Exception as exc:  # noqa: BLE001 - process boundary: any failure is a "no"
        raise _stderr_exit(f"{type(exc).__name__}: {exc}") from exc
    if not response.strip():
        raise _stderr_exit("empty response")
    sys.stdout.write(response)


def _resolve_sq_path() -> str:
    found = shutil.which("sq")
    if found is None:
        raise SqNotFoundError("sq not found on PATH; cannot run the auth probe")
    # Absolute: the probe starts in a throwaway home where a relative path is wrong.
    return str(Path(found).resolve())


def _result_line(row: AuthCheckResult) -> str:
    line = f"{row.profile.value:<14} {row.alias:<20} {row.answer.value}"
    if row.answer is AuthAnswer.NO:
        stderr_lines = row.stderr.strip().splitlines()
        reason = stderr_lines[0] if stderr_lines else f"exit {row.exit_code}"
        line += f"  ({reason})"
    return line


@benchmark_app.command("auth-check")
def auth_check(model: ModelsOption) -> None:
    """Check each profile's login survives the scrubbed producer environment."""
    try:
        sq_path = _resolve_sq_path()
        typer.echo(f"probing with: {sq_path}")
        with tempfile.TemporaryDirectory(prefix="sq-authcheck-") as root:
            rows = run_auth_check(
                model,
                SubprocessRunner(),
                Path(root),
                dict(os.environ),
                sq_path,
                get_positive_int_config(BENCHMARK_AUTH_PROBE_TIMEOUT_KEY),
            )
    except (
        SqNotFoundError,
        UnresolvedProfileError,
        ProbeStartError,
        MissingHarnessToolError,
        MissingHarnessHomeError,
    ) as exc:
        raise _stderr_exit(str(exc)) from exc
    typer.echo(f"{'profile':<14} {'alias':<20} result")
    for row in rows:
        typer.echo(_result_line(row))
        if row.answer is AuthAnswer.YES_CARRYOVER_REPLACED:
            typer.echo(f"  {row.detail}")
    if any(row.answer is not AuthAnswer.YES for row in rows):
        raise typer.Exit(1)
