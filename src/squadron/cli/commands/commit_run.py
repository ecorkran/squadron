"""[hidden] Make a scoped pipeline commit (slice 196 D1).

Used by prompt-only pipeline rendering: the harness runs this where the SDK
executor would run ``CommitAction``. The action's own logic does the work, so
both modes stage the same paths, write the same message, and refuse the same
misplaced commits.
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys

import typer

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.actions.commit import CommitAction
from squadron.pipeline.commit_plan import (
    MESSAGE_PARAM,
    PATHS_PARAM,
    PLAN_PARAM,
    REVIEW_TEMPLATE_PARAM,
    SLICE_PARAM,
    SUBJECT_PARAM,
    CommitSubject,
)
from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolver

_logger = logging.getLogger(__name__)


def commit_run(
    subject: CommitSubject | None = typer.Option(
        None, "--subject", help="What the commit is about (a scoped commit)."
    ),
    slice_index: int | None = typer.Option(None, "--slice", help="Slice index."),
    plan: str | None = typer.Option(None, "--plan", help="Initiative (plan) index."),
    template: str | None = typer.Option(
        None, "--template", help="Review template whose file the commit reports a verdict for."
    ),
    round_number: int = typer.Option(
        0, "--round", help="Loop round number; 0 for a step's own commit."
    ),
    paths: list[str] | None = typer.Option(
        None, "--path", help="Explicit path to commit (repeatable); used without --subject."
    ),
    message: str | None = typer.Option(None, "--message", help="Commit message, used verbatim."),
) -> None:
    """[hidden] Stage and commit the files a pipeline step produced."""
    params: dict[str, object] = {}
    if subject is not None:
        params[SUBJECT_PARAM] = subject.value
    if paths:
        params[PATHS_PARAM] = list(paths)
    if message is not None:
        params[MESSAGE_PARAM] = message
    if slice_index is not None:
        params[SLICE_PARAM] = str(slice_index)
    if plan is not None:
        params[PLAN_PARAM] = plan
    if template is not None:
        params[REVIEW_TEMPLATE_PARAM] = template

    context = ActionContext(
        pipeline_name="_commit",
        run_id="",
        params=params,
        step_name="_commit",
        step_index=0,
        prior_outputs={},
        resolver=ModelResolver(),
        cf_client=ContextForgeClient(),
        cwd=os.getcwd(),
        iteration=round_number,
    )
    try:
        result = asyncio.run(CommitAction().execute(context))
    except (GitEnvironmentError, ContextForgeError) as exc:
        # CLI process boundary: an environment failure ends the run, with the same
        # text the SDK executor would raise.
        _logger.exception("_commit: environment failure")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    if not result.success:
        print(f"Error: {result.error}", file=sys.stderr)
        raise typer.Exit(code=1)
    if result.outputs.get("committed") is True:
        print(f"committed {result.outputs['sha']} {result.outputs['message']}")
    else:
        print("nothing to commit")
