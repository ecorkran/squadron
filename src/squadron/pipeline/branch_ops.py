"""Enter and merge a slice's branch (slice 196 D5, D6).

The logic lives here, not in the action, so ``BranchAction`` and the hidden
``sq _branch`` command run the same code. Environment failures raise
``GitEnvironmentError``: they would hit every later item in a batch too, so they
end the run. The only item failure is a slice that has no design file.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from squadron.integrations.context_forge import ContextForgeError, ContextForgeNotAvailable
from squadron.pipeline.git_ops import (
    GitEnvironmentError,
    GitStateUnknownError,
    current_branch,
    read_integration_target,
    slice_branch_name,
    verify_git_state,
)
from squadron.pr.branch import parse_slice_branch
from squadron.review.git_utils import run_git
from squadron.review.persistence import CfClientProtocol, resolve_slice_info

_logger = logging.getLogger(__name__)

# git's wording when a branch is held by another worktree (it changed across versions).
_CHECKED_OUT_ELSEWHERE = ("already checked out", "already used by worktree")


@dataclass(frozen=True)
class EnterResult:
    """Where ``branch enter`` left the checkout."""

    branch: str
    target: str
    created: bool


def enter_slice_branch(slice_index: int, cwd: str, cf_client: CfClientProtocol) -> EnterResult:
    """Put the checkout on slice ``slice_index``'s branch, forked from the target.

    Raises:
        GitEnvironmentError: cf cannot be read, the worktree is unregistered, the checkout
            is on a foreign branch, the tree is dirty, or the branch is held elsewhere.
        GitStateUnknownError: a git write failed and the state cannot be verified.
        NoDesignFileError: the slice has no design file (an item failure).
        ValueError: the slice is not in the current plan (an item failure).
    """
    target = read_integration_target(cf_client)
    _require_registered_worktree(cwd, cf_client)
    branch = _slice_branch(slice_index, cf_client)

    start = current_branch(cwd)
    if start not in (target, branch):
        _leave_other_slice_branch(start, target, branch, cwd)
    _require_clean_tree(cwd, slice_index)
    return _switch_to(branch, target, cwd)


def _slice_branch(slice_index: int, cf_client: CfClientProtocol) -> str:
    try:
        info = resolve_slice_info(cf_client, slice_index)
    except (ContextForgeError, ContextForgeNotAvailable) as exc:
        _logger.exception("cannot resolve slice %d through cf", slice_index)
        raise GitEnvironmentError(f"cannot resolve slice {slice_index} through cf: {exc}") from exc
    return slice_branch_name(slice_index, info["design_file"])


def _require_registered_worktree(cwd: str, cf_client: CfClientProtocol) -> None:
    """A linked worktree must be registered with cf, or its target is the primary checkout's."""
    dirs = _git_stdout(["rev-parse", "--path-format=absolute", "--git-dir", "--git-common-dir"], cwd)
    git_dir, common_dir = dirs.splitlines()
    if Path(git_dir).resolve() == Path(common_dir).resolve():
        return  # the primary checkout
    root = Path(_git_stdout(["rev-parse", "--show-toplevel"], cwd).strip()).resolve()
    try:
        registered = cf_client.list_worktrees()
    except (ContextForgeError, ContextForgeNotAvailable) as exc:
        _logger.exception("cannot list cf worktrees")
        raise GitEnvironmentError(f"cannot list cf worktrees: {exc}") from exc
    if not any(Path(w.worktree_path).resolve() == root for w in registered):
        raise GitEnvironmentError(
            f"unregistered worktree {root}: integration target belongs to the primary checkout"
        )


def _leave_other_slice_branch(start: str, target: str, branch: str, cwd: str) -> None:
    """Return to the target from another slice's unmerged branch, keeping its leftovers.

    An earlier item ended there because its implement, review, devlog or merge failed or
    paused. Its tree was clean when that branch was entered, so whatever is dirty now is
    that slice's own work, which is committed on its branch before leaving.
    """
    other = parse_slice_branch(start)
    if other is None:
        raise GitEnvironmentError(f"on {start}, expected {target} or {branch}")
    if _git_stdout(["status", "--porcelain"], cwd).strip():
        _write_or_unknown(["add", "-A"], cwd, start, "git add")
        _write_or_unknown(
            ["commit", "-m", f"chore: preserve uncommitted work on flagged slice {other}"],
            cwd,
            start,
            "git commit",
        )
    _checkout(["checkout", target], cwd, start)
    _logger.warning("left unmerged slice branch %s for %s", start, target)


def _require_clean_tree(cwd: str, slice_index: int) -> None:
    status = _git_stdout(["status", "--porcelain", "-uall"], cwd)
    if not status.strip():
        return
    paths = ", ".join(line[3:] for line in status.splitlines() if line.strip())
    raise GitEnvironmentError(
        f"working tree not clean: {paths}. Commit or remove them, then rerun phase 6 for "
        f"slice {slice_index}; design and tasks commits from this run are kept."
    )


def _switch_to(branch: str, target: str, cwd: str) -> EnterResult:
    start = current_branch(cwd)
    exists = run_git(["rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"], cwd=cwd)
    if exists is None:
        raise GitStateUnknownError(f"cannot tell whether {branch} exists: git timed out")
    created = exists.returncode != 0
    args = ["checkout", "-b", branch, target] if created else ["checkout", branch]
    _checkout(args, cwd, start)
    return EnterResult(branch=branch, target=target, created=created)


def _checkout(args: list[str], cwd: str, expected_branch: str) -> None:
    """Run a checkout; failure is classified, never forced.

    A branch held by another worktree is an environment fault. Any other failure, or a
    timeout, goes to the state check with the branch we started on, since nobody knows
    whether the checkout took effect.
    """
    result = run_git(args, cwd=cwd)
    if result is not None and result.returncode == 0:
        return
    stderr = result.stderr.strip() if result is not None else "git timed out"
    if result is not None and any(text in stderr for text in _CHECKED_OUT_ELSEWHERE):
        raise GitEnvironmentError(stderr)
    verify_git_state(expected_branch, cwd=cwd)
    raise GitEnvironmentError(f"git {' '.join(args)} failed: {stderr}")


def _write_or_unknown(args: list[str], cwd: str, expected_branch: str, label: str) -> None:
    result = run_git(args, cwd=cwd)
    if result is not None and result.returncode == 0:
        return
    stderr = result.stderr.strip() if result is not None else "git timed out"
    verify_git_state(expected_branch, cwd=cwd)
    raise GitEnvironmentError(f"{label} failed: {stderr}")


def _git_stdout(args: list[str], cwd: str) -> str:
    """stdout of a read-only git command, raising when git cannot answer."""
    result: subprocess.CompletedProcess[str] | None = run_git(args, cwd=cwd)
    if result is None or result.returncode != 0:
        detail = result.stderr.strip() if result is not None else "git timed out or could not run"
        raise GitEnvironmentError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout
