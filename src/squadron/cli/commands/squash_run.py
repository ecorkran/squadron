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
    NothingToSquash,
    SquashKind,
    SquashPlan,
    SquashRefusedError,
    SquashRewriteError,
    SquashTarget,
    apply_squash,
    plan_squash,
)
from squadron.pipeline.squash_backups import backup_tags, drop_backup_tags

_logger = logging.getLogger(__name__)


def squash_run(
    kind: SquashKind | None = typer.Argument(
        None, help="slice (design), tasks, arch (architecture) or plan (slice plan)."
    ),
    index: int | None = typer.Argument(
        None, help="Slice index for slice/tasks; initiative index for arch/plan."
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Show the run and the backup tag; rewrite nothing."
    ),
    drop_backups: bool = typer.Option(
        False,
        "--drop-backups",
        help="Delete every squash backup tag once you are happy with the squashes.",
    ),
) -> None:
    """Collapse the newest commit run of one planning artifact into a single commit."""
    if drop_backups:
        if kind is not None or index is not None:
            raise typer.BadParameter("--drop-backups takes no KIND or INDEX")
        _drop_backups(dry_run)
        return
    if kind is None or index is None:
        raise typer.BadParameter("KIND and INDEX are required (or pass --drop-backups)")
    try:
        cwd = Path.cwd()
        cf_client = ContextForgeClient()
        target = SquashTarget(kind, index)
        squash = plan_squash(target, read_integration_target(cf_client), cwd, cf_client)
        if isinstance(squash, NothingToSquash):
            print(f"nothing to squash: {squash.reason}")
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
    print(f"remove it later with: git tag -d {squash.backup_tag} (or sq squash --drop-backups)")


def _drop_backups(dry_run: bool) -> None:
    """Delete (or with ``dry_run`` list) every squash backup tag."""
    try:
        cwd = Path.cwd()
        tags = backup_tags(cwd) if dry_run else drop_backup_tags(cwd)
    except GitEnvironmentError as exc:
        # CLI process boundary: an environment failure ends the command.
        _logger.exception("squash: could not drop backup tags")
        print(f"Error: {exc}", file=sys.stderr)
        raise typer.Exit(code=1) from None
    if not tags:
        print("no squash backup tags")
        return
    for tag in tags:
        print(f"  {tag}")
    action = "would delete" if dry_run else "deleted"
    print(f"{action} {len(tags)} backup tag(s)")


def _print_dry_run(squash: SquashPlan) -> None:
    print(f"run of {len(squash.commits)} commits (oldest first):")
    for commit in squash.commits:
        print(f"  {commit.sha[:SHORT_SHA_LENGTH]} {commit.subject}")
    print(f"surviving message: {squash.commits[0].subject}")
    if squash.later:
        print(f"later commits recreated on top (content unchanged): {squash.later}")
    print(f"backup tag: {squash.backup_tag}")
    print("dry run: nothing rewritten")
