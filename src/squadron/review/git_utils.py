"""Git utilities for scoped slice diff resolution."""

from __future__ import annotations

import logging
import subprocess

_logger = logging.getLogger(__name__)

#: The diff base used when no integration branch is configured. Slice branches
#: fork from and merge into this ref by default.
DEFAULT_DIFF_BASE = "main"

#: CF config key naming an optional long-lived integration branch that work
#: branches fork from and merge into instead of ``main``.
INTEGRATION_BRANCH_KEY = "git.integration_branch"


def run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
    """Run a git command, returning the CompletedProcess or None on OSError.

    ``None`` means git could not be invoked at all (missing binary, bad cwd);
    a non-zero ``returncode`` on the returned process means git ran and
    refused. Callers must distinguish the two — they are different failures.
    """
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            cwd=cwd,
        )
    except OSError:
        return None


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


class EmptyDiffError(Exception):
    """Raised when a diff-based review resolves to no changed files.

    The range resolved fine — it simply contains nothing. Running the review
    anyway produces a review *about the missing diff* (every finding tagged
    ``category: tooling``, locations ``unverified``) which is then persisted
    as a genuine verdict and overwrites the existing review of the same SHA.
    Because the archive is single-slot, a second such run destroys the
    surviving copy permanently — so this refuses before the model is called
    (issue #73).
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


def _resolve_fork_point(branch: str, cwd: str) -> str | None:
    """Resolve where *branch* was created, from the branch's own reflog.

    ``git reflog show <branch>`` ends with the entry that created the ref
    ("branch: Created from ..."), whose commit is the fork point. That entry
    survives a fast-forward merge, which is what makes it usable where plain
    merge-base has collapsed to the branch tip (issue #54).

    ``merge-base --fork-point base branch`` is *not* usable here: after a
    fast-forward, base's reflog records the merge, so it resolves to the
    merged tip rather than the fork.

    Returns None when the reflog cannot answer — a fresh clone, or after
    ``git gc`` has expired the entries — so the caller falls through and
    fails loudly rather than guessing.
    """
    try:
        result = subprocess.run(
            ["git", "reflog", "show", "--format=%H %gs", branch],
            capture_output=True,
            text=True,
            cwd=cwd,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        sha, _, subject = line.partition(" ")
        # The creating entry is "branch: Created from <rev>"; git also writes
        # "branch: Reset to <rev>" and checkout entries, which are not forks.
        if subject.startswith("branch: Created from") and sha.strip():
            return sha.strip()
    return None


def _search_merge_commit(slice_number: int, cwd: str, ref: str) -> str | None:
    """Search ``ref`` for the newest merge commit naming this slice.

    Matches merge commit messages regardless of word order around the
    slice number — e.g. both "Merge slice 303: ..." (message prose,
    the actual convention real merge commits use on this project) and
    "303-slice..." (branch-name convention). POSIX ERE has no word-boundary
    escape, so number boundaries are anchored explicitly with
    (^|[^0-9]) / ([^0-9]|$) to avoid slice 303 matching a commit about
    slice 3033.

    Returns the commit hash or None if not found.
    """
    try:
        grep_pattern = (
            rf"slice[^0-9]{slice_number}([^0-9]|$)"
            rf"|(^|[^0-9]){slice_number}-slice"
        )
        result = subprocess.run(
            [
                "git",
                "log",
                "--merges",
                "--oneline",
                "--extended-regexp",
                f"--grep={grep_pattern}",
                ref,
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


def _find_merge_commit(slice_number: int, cwd: str, base: str = DEFAULT_DIFF_BASE) -> str | None:
    """Find the merge commit for a slice branch, preferring ``base``.

    Searches ``base`` first. Because an integration branch is downstream of
    ``main``, a slice merged to ``main`` before the integration branch was
    adopted is still reachable from ``base``, so that search normally
    succeeds and the fallback never fires.

    The fallback to ``main`` covers the one case reachability does not: an
    integration branch that forked before the slice's merge and has not been
    synced since. That path can return a merge whose parent diff spans a
    batch promotion rather than this slice alone, so it logs at WARNING —
    a silently over-broad diff is the defect this base plumbing exists to
    fix (issue #32), and it should be visible if it recurs.

    Returns the commit hash or None if not found on either ref.
    """
    found = _search_merge_commit(slice_number, cwd, base)
    if found is not None:
        return found

    if base == DEFAULT_DIFF_BASE:
        return None

    found = _search_merge_commit(slice_number, cwd, DEFAULT_DIFF_BASE)
    if found is not None:
        _logger.warning(
            "slice %d: no merge commit on %r; fell back to %r (commit %s). "
            "If %r is behind %r, this diff may span a batch promotion rather "
            "than slice %d alone — verify the range or pass --diff explicitly.",
            slice_number,
            base,
            DEFAULT_DIFF_BASE,
            found,
            base,
            DEFAULT_DIFF_BASE,
            slice_number,
        )
    return found


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


def resolve_diff_base(cwd: str, cf_client: object | None = None) -> str:
    """Return the ref that slice branches fork from and merge into.

    Reads ``git.integration_branch`` from CF config; falls back to
    ``DEFAULT_DIFF_BASE`` when the key is unset, when ``cf`` is unavailable,
    or when reading it fails. A missing integration branch is the common
    case, not an error — and ``sq review --diff`` must keep working on
    machines with no ``cf`` installed, so this never raises.

    ``cf_client`` is injectable for testing; production callers pass None
    and get a ``ContextForgeClient``.
    """
    from squadron.integrations.context_forge import (
        ContextForgeClient,
        ContextForgeError,
        ContextForgeNotAvailable,
    )

    if cf_client is None:
        cf_client = ContextForgeClient()

    getter = getattr(cf_client, "get_config", None)
    if getter is None:
        return DEFAULT_DIFF_BASE

    try:
        value = str(getter(INTEGRATION_BRANCH_KEY)).strip()
    except (ContextForgeNotAvailable, ContextForgeError) as exc:
        # cf absent, key unknown, non-zero exit, or non-JSON output all mean
        # "no integration branch configured here" — degrade to the default
        # base rather than blocking a review. DEBUG, not WARNING: an absent
        # cf is the normal case for someone running `sq review --diff`.
        _logger.debug(
            "resolve_diff_base: CF config read failed (%s); using %s",
            exc,
            DEFAULT_DIFF_BASE,
        )
        return DEFAULT_DIFF_BASE

    if not value:
        return DEFAULT_DIFF_BASE

    _logger.info("resolve_diff_base: using integration branch %r as diff base", value)
    return value


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


def resolve_slice_diff_range(slice_number: int, cwd: str, base: str | None = None) -> str:
    """Resolve the git diff range for a slice's commits.

    ``base`` is the ref the slice branch forked from — ``main``, or the
    configured ``git.integration_branch`` when one is set. Pass None to
    resolve it from CF config. Taking it as a parameter keeps this module
    free of config I/O; callers that already know the base can supply it.

    Precedence:
    1. Local branch exists → merge-base three-dot diff against ``base``
    2. Merge commit found on ``base`` (or ``main``) → parent diff of merge

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
    if base is None:
        base = resolve_diff_base(cwd)

    branch = _find_slice_branch(slice_number, cwd)
    if branch is not None:
        # Compute merge-base for three-dot diff. Using `base` rather than a
        # hardcoded "main" is the fix for issue #32: on a repo with an
        # integration branch, or where earlier band work was already
        # promoted, merge-base against main returns the whole accumulated
        # band instead of this slice's own diff.
        try:
            mb_result = subprocess.run(
                ["git", "merge-base", base, branch],
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
                    _logger.debug(
                        "slice %d: diff range from merge-base(%s, %s)",
                        slice_number,
                        base,
                        branch,
                    )
                    return f"{merge_base}...{branch}"
                # branch_tip == merge_base: the branch is fully contained in
                # base. A --no-ff merge leaves a merge commit for the path
                # below, but a fast-forward merge leaves none (issue #54), and
                # fast-forward is git's default when base has not diverged.
                # The reflog still records where the branch forked, which is
                # exact — unlike a commit-message search over base, which
                # issue #14 removed for silently widening the range.
                fork_point = _resolve_fork_point(branch, cwd)
                if fork_point is not None and fork_point != branch_tip:
                    _logger.debug(
                        "slice %d: diff range from fork-point(%s, %s)",
                        slice_number,
                        base,
                        branch,
                    )
                    return f"{fork_point}..{branch_tip}"
        except (FileNotFoundError, OSError):
            pass
        # merge-base failed or branch is merged — fall through

    merge_commit = _find_merge_commit(slice_number, cwd, base)
    if merge_commit is not None:
        return f"{merge_commit}^1..{merge_commit}^2"

    searched = base if base == DEFAULT_DIFF_BASE else f"{base} or {DEFAULT_DIFF_BASE}"
    raise DiffRangeUnresolvedError(
        f"Could not resolve diff range for slice {slice_number}: no local "
        f"branch matching '{slice_number}-slice.*' and no merge commit "
        f"found on {searched}. Pass --diff explicitly to review a specific range."
    )
