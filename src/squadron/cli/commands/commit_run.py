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

from squadron.cli.commands.commit_run_fix import (
    FixCommitFlags,
    FixFlagsError,
    check_fix_flags,
    fix_prior_outputs,
)
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
from squadron.pipeline.fix_keys import COMMIT_TO_VALUES
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
    issue: str | None = typer.Option(None, "--issue", help="Fix only: the issue number."),
    commit_to: str | None = typer.Option(
        None, "--commit-to", help=f"Fix only: {'|'.join(COMMIT_TO_VALUES)}."
    ),
    start_head: str | None = typer.Option(None, "--start-head", help="Fix only: HEAD at start."),
    start_branch: str | None = typer.Option(None, "--start-branch", help="Fix only: branch at start."),
    report_file: str | None = typer.Option(
        None, "--report-file", help="Fix only: file holding the agent's final reply."
    ),
) -> None:
    """[hidden] Stage and commit the files a pipeline step produced."""
    flags = FixCommitFlags(issue, commit_to, start_head, start_branch, report_file)
    try:
        check_fix_flags(
            subject,
            flags,
            {
                "--slice": slice_index,
                "--plan": plan,
                "--template": template,
                "--round": round_number,
                "--path": paths,
                "--message": message,
            },
        )
        prior_outputs = fix_prior_outputs(flags) if subject is CommitSubject.FIX else {}
    except FixFlagsError as exc:
        # CLI process boundary: bad flags or an unreadable report end the command.
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None
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
        prior_outputs=prior_outputs,
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
