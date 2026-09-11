"""Git utilities for scoped slice diff resolution."""

from __future__ import annotations

import logging
import subprocess
from enum import StrEnum

from squadron.core.subprocess_text import TEXT_DECODING

_logger = logging.getLogger(__name__)

#: The diff base used when no integration branch is configured. Slice branches
#: fork from and merge into this ref by default.
DEFAULT_DIFF_BASE = "main"

#: CF config key naming an optional long-lived integration branch that work
#: branches fork from and merge into instead of ``main``.
INTEGRATION_BRANCH_KEY = "git.integration_branch"

#: Wall-clock bound on any single git invocation. Without it, a command
#: touching an unreachable remote-tracking ref blocks the review forever with
#: no output. Generous enough that a slow local repository never trips it.
GIT_COMMAND_TIMEOUT_SECONDS = 30


def run_git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
    """Run a git command, returning the CompletedProcess or None if it could not answer.

    ``None`` means git could not be invoked at all (missing binary, bad cwd)
    or did not finish within the timeout;
    a non-zero ``returncode`` on the returned process means git ran and
    refused. Callers must distinguish the two — they are different failures.

    Every git call in this module goes through here so the UTF-8 decoding
    pin (issue #63) is applied once, and so every call is bounded by
    ``GIT_COMMAND_TIMEOUT_SECONDS``.
    """
    try:
        return subprocess.run(
            ["git", *args],
            capture_output=True,
            text=True,
            **TEXT_DECODING,
            cwd=cwd,
            check=False,
            timeout=GIT_COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        # Same "git could not answer" signal as OSError for every caller, but
        # a timeout is a distinct operational fault (usually an unreachable
        # remote) and must not vanish into a silent None.
        _logger.warning(
            "git %s timed out after %ds in %r; treating as unavailable",
            " ".join(args),
            GIT_COMMAND_TIMEOUT_SECONDS,
            cwd,
        )
        return None
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


class DiffSpecError(Exception):
    """Base for ``--diff`` specs that cannot be turned into a reviewable range.

    Carries the offending ref so callers can report it without parsing a
    message. The two subclasses are different operator errors with different
    fixes, so consumers branch on type, never on message text.
    """

    def __init__(self, message: str, *, ref: str) -> None:
        super().__init__(message)
        self.ref = ref


class NotAGitRepositoryError(DiffSpecError):
    """Git could not be invoked here at all — wrong cwd, or no git binary.

    Distinct from a ref that simply does not exist: nothing about the spec is
    at fault, so telling the operator to check their ref would send them the
    wrong way.
    """


class RefNotFoundError(DiffSpecError):
    """Git ran and could not resolve the ref. The spec itself is the problem."""


class EmptyScopeCase(StrEnum):
    """Why a diff range yielded nothing to review.

    Two different operator errors with two different fixes. Conflating them is
    how issue #71 stayed unexplained, so callers branch on this field rather
    than on message text.
    """

    #: The range had changed files, but every one matched an exclusion pattern.
    #: The operator likely wants the review omitted, or a different range.
    ALL_EXCLUDED = "all_excluded"
    #: The range itself contains no changed files — wrong base, an
    #: already-merged branch, or a typo.
    NO_CHANGES = "no_changes"


class EmptyScopeError(Exception):
    """Raised when a review's filtered scope contains no files.

    A review of nothing produces findings about the missing diff, which is then
    persisted as a genuine verdict and clears review gates (issue #62). Refusing
    pre-flight costs nothing and says why.

    Carries the case, the matched exclusion patterns and the excluded file count
    as structured fields so consumers never parse the message.
    """

    def __init__(
        self,
        message: str,
        *,
        case: EmptyScopeCase,
        exclude_patterns: list[str] | None = None,
        excluded_count: int = 0,
    ) -> None:
        super().__init__(message)
        self.case = case
        self.exclude_patterns = exclude_patterns or []
        self.excluded_count = excluded_count


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
    result = run_git(["branch", "--list", f"{slice_number}-slice.*"], cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    for line in result.stdout.splitlines():
        branch = line.strip().lstrip("* ")
        if branch:
            return branch
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
    result = run_git(["reflog", "show", "--format=%H %gs", branch], cwd=cwd)
    if result is None or result.returncode != 0:
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
    grep_pattern = rf"slice[^0-9]{slice_number}([^0-9]|$)|(^|[^0-9]){slice_number}-slice"
    result = run_git(
        ["log", "--merges", "--oneline", "--extended-regexp", f"--grep={grep_pattern}", ref, "-1"],
        cwd=cwd,
    )
    if result is None or result.returncode != 0 or not result.stdout.strip():
        return None
    # First word is the commit hash
    return result.stdout.strip().split()[0]


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
    result = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
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
    result = run_git(["rev-parse", ref], cwd=cwd)
    if result is not None and result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return None


#: Git's three-dot range operator: ``a...b`` diffs b against the merge-base of
#: a and b — the change set b introduced, excluding what a gained meanwhile.
THREE_DOT = "..."

#: Git's two-dot range operator: ``a..b`` diffs the two endpoints directly.
TWO_DOT = ".."


def normalize_diff_spec(spec: str, cwd: str) -> str:
    """Return *spec* as an explicit diff range, rewriting a bare ref to merge-base form.

    A bare ``--diff main`` reaches ``git diff`` as a two-dot comparison against
    the current worktree, so every commit the base gained since the branch
    forked is reported as part of the branch's change set (issue #89). The
    merge-base form ``<ref>...HEAD`` is what the operator means.

    Ranges the operator wrote explicitly pass through untouched — including
    ``a..b``, whose two-dot semantics are then deliberate. Endpoints of an
    explicit range are **not** validated here: an unreachable endpoint surfaces
    as an empty scope, which the scope guard reports with better context.

    Raises ``NotAGitRepositoryError`` or ``RefNotFoundError`` when a bare ref
    does not resolve — before any model call is spent on it.
    """
    # Three-dot must be tested first: every three-dot spec contains a two-dot
    # substring, so the reverse order misclassifies explicit merge-base ranges.
    if THREE_DOT in spec or TWO_DOT in spec:
        return spec

    result = run_git(["rev-parse", "--verify", f"{spec}^{{commit}}"], cwd=cwd)
    if result is None:
        raise NotAGitRepositoryError(
            f"Cannot resolve --diff {spec!r}: git could not be run in {cwd!r}. "
            "Check that this is a git repository and that git is installed.",
            ref=spec,
        )
    if result.returncode != 0:
        raise RefNotFoundError(
            f"Cannot resolve --diff {spec!r}: no such ref in this repository. "
            "Check the ref name, or fetch it first.",
            ref=spec,
        )

    return f"{spec}{THREE_DOT}HEAD"


def _changed_paths(diff: str, cwd: str, exclude_patterns: list[str] | None) -> list[str] | None:
    """Return changed paths for *diff*, or None if git could not answer.

    ``None`` is distinct from ``[]``: the former means the range could not be
    computed at all, the latter that it computed to nothing. Collapsing them is
    what let an unreadable range look like an empty one.
    """
    args = ["diff", "--name-only", diff]
    if exclude_patterns:
        args += ["--", ".", *(f":!{pattern}" for pattern in exclude_patterns)]
    result = run_git(args, cwd=cwd)
    if result is None or result.returncode != 0:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def assert_reviewable_scope(
    diff: str,
    cwd: str,
    exclude_patterns: list[str] | None = None,
) -> list[str]:
    """Refuse a review whose filtered scope contains no files. Returns those files.

    Computes the unfiltered and filtered path lists itself rather than reusing
    either caller's ``extract_diff_paths`` call: both are nested under a rules
    directory check, so a guard hung off them would silently not run whenever no
    rules directory resolves — which is the review most in need of the guard.

    Logs at WARNING before raising. A typed exception surfaces at WARNING+ only
    if each entry point's handler happens to log it, and this function exists to
    turn a silent pass into a loud failure, so the level is not left to the
    caller.

    Raises ``EmptyScopeError`` carrying an ``EmptyScopeCase``.
    """
    unfiltered = _changed_paths(diff, cwd, None)
    if unfiltered is None:
        # git could not compute the range at all. Reported as NO_CHANGES: from
        # the operator's side the range is equally unusable, and the remedy —
        # check the range — is the same.
        _logger.warning("Refusing review of %r in %r: git could not compute the range.", diff, cwd)
        raise EmptyScopeError(
            f"Cannot review {diff!r}: git could not compute that range. "
            "Check the range and that this is a git repository.",
            case=EmptyScopeCase.NO_CHANGES,
        )

    if not unfiltered:
        _logger.warning("Refusing review of %r in %r: the range has no changed files.", diff, cwd)
        raise EmptyScopeError(
            f"Cannot review {diff!r}: that range contains no changed files. "
            "The base may be wrong, or the branch may already be merged.",
            case=EmptyScopeCase.NO_CHANGES,
        )

    filtered = _changed_paths(diff, cwd, exclude_patterns)
    if filtered is None:
        # The unfiltered form worked, so the pathspec is what git refused.
        _logger.warning(
            "Refusing review of %r in %r: git rejected the exclusion pathspec %r.",
            diff,
            cwd,
            exclude_patterns,
        )
        raise EmptyScopeError(
            f"Cannot review {diff!r}: git rejected the exclusion patterns {exclude_patterns!r}.",
            case=EmptyScopeCase.ALL_EXCLUDED,
            exclude_patterns=exclude_patterns,
            excluded_count=len(unfiltered),
        )

    if not filtered:
        excluded_count = len(unfiltered)
        _logger.warning(
            "Refusing review of %r in %r: all %d changed file(s) matched the exclusion patterns %r.",
            diff,
            cwd,
            excluded_count,
            exclude_patterns,
        )
        raise EmptyScopeError(
            f"Cannot review {diff!r}: all {excluded_count} changed file(s) matched "
            f"the exclusion patterns {exclude_patterns!r}. Review a range that "
            "contains reviewable code, or omit the review for this change.",
            case=EmptyScopeCase.ALL_EXCLUDED,
            exclude_patterns=exclude_patterns,
            excluded_count=excluded_count,
        )

    return filtered


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
        mb_result = run_git(["merge-base", base, branch], cwd=cwd)
        if mb_result is not None and mb_result.returncode == 0 and mb_result.stdout.strip():
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
