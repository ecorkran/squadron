"""``sq squash``: collapse the newest planning commit run into one commit (slice 948).

The pipeline ``squash`` step renders this command in prompt-only mode and calls the
same two functions in the SDK executor, so both modes find and rewrite the same run.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
from squadron.pipeline.commit_plan import CommitTarget
from squadron.pipeline.git_ops import GitEnvironmentError, read_integration_target
from squadron.pipeline.squash import (
    SquashPlan,
    SquashRewriteError,
    apply_squash,
    check_squash_scope,
    plan_squash,
)

_logger = logging.getLogger(__name__)
_SHORT = 8


def squash_run(
    subject: str = typer.Argument(..., help="design, tasks or architecture."),
    slice_index: int | None = typer.Option(None, "--slice", help="Slice index (design, tasks)."),
    plan: int | None = typer.Option(None, "--plan", help="Initiative index (architecture)."),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the run and the backup tag; rewrite nothing."
    ),
) -> None:
    """Collapse the newest commit run of one planning artifact into a single commit."""
    try:
        parsed = check_squash_scope(subject, slice_index is not None, plan is not None)
        target = CommitTarget(parsed, slice_index, None if plan is None else str(plan), None, 0)
        cwd = Path.cwd()
        cf_client = ContextForgeClient()
        squash = plan_squash(target, read_integration_target(cf_client), cwd, cf_client)
        if squash is None:
            print("nothing to squash")
            return
        if dry_run:
            _print_dry_run(squash)
            return
        new_sha = apply_squash(squash, cwd)
    except (ValueError, SquashRewriteError) as exc:
        # Refusals, bad scope and failed rewrites are already logged where they happen.
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None
    except (GitEnvironmentError, ContextForgeError) as exc:
        # CLI process boundary: an environment failure ends the command.
        _logger.exception("squash: environment failure")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    print(f"squashed {len(squash.commits)} commits into {new_sha[:_SHORT]}")
    print(f"backup tag: {squash.backup_tag}")
    print(f"remove it later with: git tag -d {squash.backup_tag}")


def _print_dry_run(squash: SquashPlan) -> None:
    print(f"run of {len(squash.commits)} commits (oldest first):")
    for commit in squash.commits:
        print(f"  {commit.sha[:_SHORT]} {commit.subject}")
    print(f"surviving message: {squash.commits[0].subject}")
    print(f"backup tag: {squash.backup_tag}")
    print("dry run: nothing rewritten")
