"""Git utilities for scoped slice diff resolution."""

from __future__ import annotations

import subprocess
import sys


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


def _find_commit_range(slice_number: int, cwd: str) -> str | None:
    """Find a diff range by grepping commit messages for the slice number.

    Runs ``git log --oneline --all --grep=r"\\b{N}\\b"`` and collects all
    matching commit hashes.  Returns:

    - ``"{oldest}^!"``: if exactly one commit matched (single-commit diff)
    - ``"{oldest}^..{newest}"``: if two or more commits matched
    - ``None``: if no commits matched or git failed
    """
    try:
        result = subprocess.run(
            [
                "git",
                "log",
                "--oneline",
                "--all",
                f"--grep=\\b{slice_number}\\b",
            ],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return None
        hashes = [
            line.split()[0] for line in result.stdout.splitlines() if line.strip()
        ]
        if not hashes:
            return None
        if len(hashes) == 1:
            return f"{hashes[0]}^!"
        # git log outputs newest-first; oldest is last
        newest, oldest = hashes[0], hashes[-1]
        return f"{oldest}^..{newest}"
    except (FileNotFoundError, OSError):
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
    3. Commit-message grep → oldest-to-newest range across matched commits
    4. Fallback → 'main' with warning

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

    commit_range = _find_commit_range(slice_number, cwd)
    if commit_range is not None:
        return commit_range

    print(
        f"[WARNING] Could not resolve diff range for slice {slice_number}. "
        "Falling back to --diff main.",
        file=sys.stderr,
    )
    return "main"
