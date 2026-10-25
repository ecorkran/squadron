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
from squadron.pipeline.git_ops import GitEnvironmentError, read_integration_target
from squadron.pipeline.squash import (
    SHORT_SHA_LENGTH,
    SquashKind,
    SquashPlan,
    SquashRefusedError,
    SquashRewriteError,
    SquashTarget,
    apply_squash,
    plan_squash,
)

_logger = logging.getLogger(__name__)


def squash_run(
    kind: SquashKind = typer.Argument(
        ..., help="slice (design), tasks, arch (architecture) or plan (slice plan)."
    ),
    index: int = typer.Argument(
        ..., help="Slice index for slice/tasks; initiative index for arch/plan."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the run and the backup tag; rewrite nothing."
    ),
) -> None:
    """Collapse the newest commit run of one planning artifact into a single commit."""
    try:
        cwd = Path.cwd()
        cf_client = ContextForgeClient()
        target = SquashTarget(kind, index)
        squash = plan_squash(target, read_integration_target(cf_client), cwd, cf_client)
        if squash is None:
            print("nothing to squash")
            return
        if dry_run:
            _print_dry_run(squash)
            return
        new_sha = apply_squash(squash, cwd)
    except (SquashRefusedError, SquashRewriteError) as exc:
        # Already logged where they happen (WARNING for a refusal, ERROR for a failed rewrite).
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None
    except (ValueError, FileNotFoundError) as exc:
        # The slice is not in cf's plan, or the initiative has no such document.
        _logger.warning("squash: cannot resolve %s %d: %s", kind, index, exc)
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None
    except (GitEnvironmentError, ContextForgeError) as exc:
        # CLI process boundary: an environment failure ends the command.
        _logger.exception("squash: environment failure")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None

    print(f"squashed {len(squash.commits)} commits into {new_sha[:SHORT_SHA_LENGTH]}")
    if squash.later:
        print(f"recreated {squash.later} later commits on top (content unchanged)")
    print(f"backup tag: {squash.backup_tag}")
    print(f"remove it later with: git tag -d {squash.backup_tag}")


def _print_dry_run(squash: SquashPlan) -> None:
    print(f"run of {len(squash.commits)} commits (oldest first):")
    for commit in squash.commits:
        print(f"  {commit.sha[:SHORT_SHA_LENGTH]} {commit.subject}")
    print(f"surviving message: {squash.commits[0].subject}")
    if squash.later:
        print(f"later commits recreated on top (content unchanged): {squash.later}")
    print(f"backup tag: {squash.backup_tag}")
    print("dry run: nothing rewritten")
