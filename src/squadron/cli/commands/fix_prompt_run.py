"""[hidden] Print the assembled fix prompt (slice 423 D9).

The prompt-only counterpart of the ``fix-context`` action: the harness runs this where
the SDK executor would run ``FixContextAction``. It runs that same action, so both modes
refuse the same states and print the same prompt.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import typer

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions.fix_context import PROMPT_KEY, FixContextAction
from squadron.pipeline.control_params import RUN_IO_DIR
from squadron.pipeline.fix_keys import (
    COMMIT_TO_PARAM,
    COMMIT_TO_VALUES,
    ISSUE_FILE_PARAM,
    ISSUE_PARAM,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolver

_logger = logging.getLogger(__name__)


def fix_prompt_run(
    issue: str = typer.Option(..., "--issue", help="Issue number, 301 or #301."),
    issue_file: str = typer.Option("", "--issue-file", help="Frozen issue text; empty fetches."),
    io_dir: str | None = typer.Option(
        None, "--io-dir", help="Directory --issue-file resolves against."
    ),
    commit_to: str = typer.Option(
        ..., "--commit-to", help=f"Where the fix commits: {'|'.join(COMMIT_TO_VALUES)}."
    ),
) -> None:
    """[hidden] Check a fix may start and print its prompt."""
    params: dict[str, object] = {
        ISSUE_PARAM: issue,
        ISSUE_FILE_PARAM: issue_file,
        COMMIT_TO_PARAM: commit_to,
    }
    if io_dir is not None:
        params[RUN_IO_DIR] = io_dir
    context = ActionContext(
        pipeline_name="_fix-prompt",
        run_id="",
        params=params,
        step_name="_fix-prompt",
        step_index=0,
        prior_outputs={},
        resolver=ModelResolver(),
        cf_client=ContextForgeClient(),
        cwd=os.getcwd(),
    )
    try:
        result = asyncio.run(FixContextAction().execute(context))
    except (GitEnvironmentError, ContextForgeError) as exc:
        # CLI process boundary: an environment failure ends the run, with the same text
        # the SDK executor would raise.
        _logger.exception("_fix-prompt: environment failure")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        raise typer.Exit(code=1)
    print(result.outputs[PROMPT_KEY])
