"""Git utilities for scoped slice diff resolution."""

from __future__ import annotations

import subprocess


class DiffRangeUnresolvedError(Exception):
    """Raised when a slice's diff range cannot be resolved from git structure.

    No local branch and no merge commit means there is no reliable,
    structural way to know which commits belong to this slice — a
    commit-message grep was tried previously but matches unrelated commits
    that merely mention the slice number in prose (e.g. "docs: reconcile
    124 initiative status"), which silently pulled prior slices' merged
    code into the reviewed diff (issue #14). Failing loudly here is safer
    than guessing.
    """


def _find_slice_branch(slice_number: int, cwd: str) -> str | None:
    """Find a local branch matching '{slice_number}-slice.*'.

    Returns the branch name or None if not found.
    """
    try:
        result = subprocess.run(
            ["git", "branch", "--list", f"{slice_number}-slice.*"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode != 0:
            return None
        for line in result.stdout.splitlines():
            branch = line.strip().lstrip("* ")
            if branch:
                return branch
    except (FileNotFoundError, OSError):
        return None
    return None


def _find_merge_commit(slice_number: int, cwd: str) -> str | None:
    """Find the merge commit for a slice branch on main.

    Returns the commit hash or None if not found.
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--merges",
                "--oneline",
                f"--grep={slice_number}-slice",
                "main",
                "-1",
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        # First word is the commit hash
        return result.stdout.strip().split()[0]
    except (FileNotFoundError, OSError):
        return None


def find_git_root(cwd: str) -> str | None:
    """Return the root of the git repository containing ``cwd``.

    Returns the absolute path string, or ``None`` if ``cwd`` is not inside
    a git repository or git is unavailable.
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    return None


def _resolve_rev(ref: str, cwd: str) -> str | None:
    """Resolve a git ref to its full SHA. Returns None on failure."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", ref],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, OSError):
        pass
    return None


def resolve_slice_diff_range(slice_number: int, cwd: str) -> str:
    """Resolve the git diff range for a slice's commits.

    Precedence:
    1. Local branch exists → merge-base three-dot diff
    2. Merge commit found on main → parent diff of merge

    Raises ``DiffRangeUnresolvedError`` if neither resolves. A prior
    commit-message-grep fallback (path 3) was removed (issue #14): it
    matched any commit whose message contained the slice number as a
    bare token, including unrelated commits (e.g. "docs: reconcile 124
    initiative status") that could be older than the slice's actual
    work — silently pulling a wider, wrong range into what the review
    model was told was "this slice's diff." No text heuristic over
    commit messages can safely distinguish real slice-work commits from
    incidental mentions, so failing loudly beats guessing.

    Returns a diff range string suitable for ``git diff <range>``.
    """
    branch = _find_slice_branch(slice_number, cwd)
    if branch is not None:
        # Compute merge-base for three-dot diff
        try:
            mb_result = subprocess.run(
                ["git", "merge-base", "main", branch],
                capture_output=True,
                text=True,
                cwd=cwd,
                check=False,
            )
            if mb_result.returncode == 0 and mb_result.stdout.strip():
                merge_base = mb_result.stdout.strip()
                # Check if branch tip equals merge-base — if so,
                # branch is fully merged and three-dot diff will be
                # empty. Fall through to merge commit path instead.
                branch_tip = _resolve_rev(branch, cwd)
                if branch_tip is None or merge_base != branch_tip:
                    return f"{merge_base}...{branch}"
        except (FileNotFoundError, OSError):
            pass
        # merge-base failed or branch is merged — fall through

    merge_commit = _find_merge_commit(slice_number, cwd)
    if merge_commit is not None:
        return f"{merge_commit}^1..{merge_commit}^2"

    raise DiffRangeUnresolvedError(
        f"Could not resolve diff range for slice {slice_number}: no local "
        f"branch matching '{slice_number}-slice.*' and no merge commit "
        f"found on main. Pass --diff explicitly to review a specific range."
    )
