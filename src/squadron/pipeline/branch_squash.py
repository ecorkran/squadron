"""Collapse a slice branch into one commit before it merges.

Phase 6 commits once per implement pass, review fix and devlog entry, so a slice
branch arrives with a stack of commits that say nothing the merge commit does not.
``squash_slice_branch`` replaces them with one commit whose tree is the branch tip's,
parented on the point where the branch left the target. Content never changes.
"""

from __future__ import annotations

import logging

from squadron.pipeline.git_ops import GitEnvironmentError
from squadron.review.git_utils import run_git

_logger = logging.getLogger(__name__)


def squash_slice_branch(slice_index: int, name: str, branch: str, target: str, cwd: str) -> int:
    """Squash ``branch``'s commits since it left ``target`` into one; return how many were replaced.

    The branch must be checked out with a clean tree. Returns 0 when there is nothing to
    do: no commits of its own, or only one. A branch with any commit already in a
    remote-tracking ref is left as it is (and logged at WARNING), because squashing it
    would rewrite pushed history. The old tip stays in the reflog; it is logged here.

    Raises:
        GitEnvironmentError: a git command failed. The branch is untouched until the
            final reset, which only moves to a commit with the same tree.
    """
    base = _git(["merge-base", target, branch], cwd).strip()
    commits = _count(["rev-list", "--count", f"{base}..{branch}"], cwd)
    if commits <= 1:
        return 0
    unpushed = _count(["rev-list", "--count", f"{base}..{branch}", "--not", "--remotes"], cwd)
    if unpushed != commits:
        _logger.warning(
            "slice %d branch %s not squashed: %d of its %d commits are already pushed",
            slice_index,
            branch,
            commits - unpushed,
            commits,
        )
        return 0
    old_tip = _git(["rev-parse", branch], cwd).strip()
    message = f"feat: implement slice {slice_index} — {name}\n\nSquashed from {commits} commits."
    squashed = _git(["commit-tree", f"{branch}^{{tree}}", "-p", base, "-m", message], cwd).strip()
    _git(["reset", "--hard", squashed], cwd)
    _logger.info("squashed %d commits on %s (was %s)", commits, branch, old_tip)
    return commits


def _count(args: list[str], cwd: str) -> int:
    return int(_git(args, cwd).strip())


def _git(args: list[str], cwd: str) -> str:
    result = run_git(args, cwd=cwd)
    if result is None or result.returncode != 0:
        detail = result.stderr.strip() if result is not None else "git timed out"
        raise GitEnvironmentError(f"git {' '.join(args)} failed: {detail}")
    return result.stdout
