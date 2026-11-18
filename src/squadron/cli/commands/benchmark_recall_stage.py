"""``sq benchmark recall _stage``: one comb call, launched by the recall runner (slice 430 D6).

Hidden, in the style of ``_auth-probe``. It runs in a scrubbed home with cwd = the case
sandbox. Any failure exits non-zero without writing the output file, which the runner
reads as "the call never reached the model" (D8).
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer

from squadron.benchmark.auth_check import UnresolvedProfileError, resolve_alias_profile
from squadron.benchmark.recall.stage_command import (
    StageInputError,
    StageModel,
    changed_files,
    read_stage_input,
    run_comb_stage,
    write_stage_output,
)
from squadron.cli.commands.benchmark_common import stderr_exit
from squadron.config.keys import BENCHMARK_RECALL_FETCH_TIMEOUT_KEY
from squadron.config.manager import get_positive_int_config
from squadron.core.process_runner import SubprocessRunner
from squadron.models.aliases import model_allows_tools, model_effort, model_max_output_tokens
from squadron.review.review_client import run_review_with_profile
from squadron.review.templates import get_template, load_all_templates

STAGE_COMMAND = "_stage"


def resolve_stage_model(alias: str) -> StageModel:
    model, profile = resolve_alias_profile(alias)
    return StageModel(
        alias=alias,
        model=model,
        profile=profile.value,
        effort=model_effort(alias),
        max_output_tokens=model_max_output_tokens(alias),
        allows_tools=model_allows_tools(alias),
    )


def stage_command(
    template_name: Annotated[str, typer.Option("--template", help="Built-in template name.")],
    input_path: Annotated[Path, typer.Option("--input", help="JSON list of findings to comb.")],
    output_path: Annotated[Path, typer.Option("--output", help="Where to write the result.")],
    alias: Annotated[str, typer.Option("--model", help="Model alias for the call.")],
    base: Annotated[str, typer.Option("--diff", help="The case's base commit.")],
) -> None:
    """Run one comb call in the current directory (the sandbox)."""
    load_all_templates()
    template = get_template(template_name)
    if template is None:
        raise stderr_exit(f"Error: unknown template {template_name!r}")
    cwd = Path.cwd()
    try:
        findings = read_stage_input(input_path)
        timeout = float(get_positive_int_config(BENCHMARK_RECALL_FETCH_TIMEOUT_KEY, cwd=str(cwd)))
        changed = changed_files(SubprocessRunner(), cwd, base, timeout)
        model = resolve_stage_model(alias)
        document = asyncio.run(
            run_comb_stage(
                template=template,
                findings=findings,
                changed=changed,
                cwd=cwd,
                model=model,
                review_call=run_review_with_profile,
            )
        )
        write_stage_output(output_path, document)
    except (StageInputError, UnresolvedProfileError) as exc:
        raise stderr_exit(f"Error: {exc}") from exc
    except Exception as exc:  # noqa: BLE001 - process boundary: the runner reads the exit
        raise stderr_exit(f"{type(exc).__name__}: {exc}") from exc
