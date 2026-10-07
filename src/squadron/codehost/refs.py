"""Fetching a pull request's endpoints and describing the range between them.

Host-agnostic git over the injected runner: the caller supplies the refspec
sources, because a refspec is the *host's* convention, and nothing here names a
host. No git argv on this path carries a hostname.

Everything is read-only against the working tree. Refs land under
``refs/squadron/`` — a namespace, not branches — so ``git branch``,
``git status``, and the checkout itself are untouched. That is what lets
``sq pr show`` run against a dirty tree.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from squadron.codehost.errors import (
    RENDERED_BY_CALLER,
    HostCommandTimeoutError,
    NoMergeBaseError,
    PullRequestHeadUnavailableError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
)
from squadron.codehost.models import FetchedRange, RefAdjustment, RefRole
from squadron.core.process_runner import ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)

#: Wall-clock bound on the git queries here — rev-parse, merge-base, diff.
GIT_QUERY_TIMEOUT_SECONDS = 30

#: Fetch moves data over the network; the query bound is far too tight for it.
GIT_FETCH_TIMEOUT_SECONDS = 300

#: Where fetched pull-request endpoints land. Namespacing by remote keeps PR 12
#: on ``origin`` distinct from PR 12 on ``upstream``.
_REF_NAMESPACE = "refs/squadron/pr"


def local_ref(remote_name: str, number: int, role: RefRole) -> str:
    """The local ref a fetched endpoint lands on."""
    return f"{_REF_NAMESPACE}/{remote_name}/{number}/{role.value}"


def api_head_ref(remote_name: str, number: int) -> str:
    """Where the host API's head commit lands when the pull-request ref lags it."""
    return f"{_REF_NAMESPACE}/{remote_name}/{number}/api-head"


#: What ``ensure_api_head`` reports for a commit that needed no fetch.
HEAD_PRESENT_LOCALLY = "present locally"

#: The label for the host-neutral attempt: fetch the commit by its sha.
HEAD_FETCHED_BY_SHA = "fetched by sha"


def fetch_and_range(
    runner: ProcessRunner,
    *,
    cwd: str,
    remote_name: str,
    namespace: int,
    base_refspec_source: str,
    head_refspec_source: str,
    expected_base_sha: str,
    expected_head_sha: str,
    head_fallback_sources: tuple[str, ...] = (),
) -> FetchedRange:
    """Fetch base and head, verify they are what the host reported, describe the range.

    ``namespace`` is the pull-request number the local refs are filed under.
    ``head_fallback_sources`` are host-supplied refspec sources to try, after
    fetching by sha, when the pull-request ref and the API disagree about the
    head (a host's convention, so the caller names them).
    """
    base_local = local_ref(remote_name, namespace, RefRole.BASE)
    head_local = local_ref(remote_name, namespace, RefRole.HEAD)

    _fetch(
        runner,
        cwd=cwd,
        remote_name=remote_name,
        specs=(
            (base_refspec_source, base_local),
            (head_refspec_source, head_local),
        ),
    )

    base_sha, base_adjustment = _verify(
        runner,
        cwd=cwd,
        ref=base_local,
        role=RefRole.BASE,
        expected=expected_base_sha,
        source=base_refspec_source,
    )
    head_sha, head_adjustment = _resolve_head(
        runner,
        cwd=cwd,
        remote_name=remote_name,
        namespace=namespace,
        head_local=head_local,
        head_source=head_refspec_source,
        expected=expected_head_sha,
        head_fallback_sources=head_fallback_sources,
    )

    merge_base = _merge_base(runner, cwd=cwd, base=base_local, head=head_local)
    # The three-dot form: everything head gained since it forked from base.
    # Built here rather than imported from squadron.review — codehost must not
    # depend on review — but it is the same form that path already accepts.
    diff_range = f"{base_local}...{head_local}"

    return FetchedRange(
        base_ref=base_local,
        head_ref=head_local,
        base_sha=base_sha,
        head_sha=head_sha,
        merge_base=merge_base,
        diff_range=diff_range,
        changed_paths=_changed_paths(runner, cwd=cwd, diff_range=diff_range),
        adjustments=tuple(a for a in (base_adjustment, head_adjustment) if a is not None),
    )


def _fetch(
    runner: ProcessRunner,
    *,
    cwd: str,
    remote_name: str,
    specs: tuple[tuple[str, str], ...],
) -> None:
    """Fetch every endpoint in one call.

    The ``+`` prefix force-updates, so re-resolving the same pull request after
    its head moves overwrites rather than failing.
    """
    argv = ["git", "fetch", "--no-tags", remote_name]
    argv += [f"+{source}:{destination}" for source, destination in specs]
    try:
        result = runner.run(argv, cwd=cwd, timeout=GIT_FETCH_TIMEOUT_SECONDS)
    except ProcessTimedOutError as exc:
        # Rendered by the command as a code host error, never a traceback.
        _logger.warning(
            "git fetch from %s exceeded %ss",
            remote_name,
            exc.timeout,
            extra={RENDERED_BY_CALLER: True},
        )
        raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc
    if result.returncode == 0:
        return

    # Which endpoint actually failed? Ask, rather than guess from the message:
    # a fetch that could not reach one of two refspecs fails the whole call.
    for (_, destination), role in zip(specs, (RefRole.BASE, RefRole.HEAD), strict=True):
        if _rev_parse(runner, cwd=cwd, ref=destination) is None:
            _logger.warning(
                "fetch of %s from %s failed: %s",
                role.value,
                remote_name,
                result.stderr.strip(),
                extra={RENDERED_BY_CALLER: True},
            )
            raise RefNotFetchableError(
                role,
                f"could not fetch {role.value} from {remote_name}: "
                f"{result.stderr.strip() or '(no stderr)'}",
                fix_hint="Check the remote is reachable and the pull request still exists.",
            )

    # Both refs are present despite the non-zero exit; treat it as a base-side
    # failure rather than continuing with an unexplained error.
    _logger.warning(
        "git fetch exited %s: %s",
        result.returncode,
        result.stderr.strip(),
        extra={RENDERED_BY_CALLER: True},
    )
    raise RefNotFetchableError(
        RefRole.BASE,
        f"git fetch failed: {result.stderr.strip() or '(no stderr)'}",
    )


def ensure_api_head(
    runner: ProcessRunner,
    *,
    cwd: str,
    remote_name: str,
    api_sha: str,
    api_local: str,
    pr_ref: str,
    pr_ref_sha: str,
    head_fallback_sources: tuple[str, ...],
) -> str:
    """Make the host API's head commit present locally; say how it got there.

    Tries, in order: the commit already being present, ``fetch <remote> +<sha>``
    (host-neutral), then each ``head_fallback_sources`` entry, each into
    ``api_local``. After every fetch ``api_local`` must resolve to ``api_sha``: a
    fork PR's same-named base branch is a different commit and is rejected, so the
    stale pull-request ref's sha is never reviewed. Returns ``HEAD_PRESENT_LOCALLY``,
    ``HEAD_FETCHED_BY_SHA`` or the fallback source that worked.

    Raises:
        HostCommandTimeoutError: the presence check timed out.
        PullRequestHeadUnavailableError: no source yielded the commit; it names
            each source with its reason. ``pr_ref`` and ``pr_ref_sha`` describe
            the lagging ref for that message.
    """
    if _commit_is_present(runner, cwd=cwd, sha=api_sha):
        return HEAD_PRESENT_LOCALLY

    attempts: list[tuple[str, str]] = []
    sources = ((HEAD_FETCHED_BY_SHA, api_sha), *((entry, entry) for entry in head_fallback_sources))
    for label, source in sources:
        reason = _fetch_api_head(
            runner,
            cwd=cwd,
            remote_name=remote_name,
            source=source,
            api_local=api_local,
            api_sha=api_sha,
        )
        if reason is None:
            return label
        _logger.debug("api head %s: %s: %s", api_sha, label, reason)
        attempts.append((label, reason))

    _logger.warning(
        "api head %s could not be fetched from %s: %s",
        api_sha,
        remote_name,
        "; ".join(f"{label}: {reason}" for label, reason in attempts),
        extra={RENDERED_BY_CALLER: True},
    )
    raise PullRequestHeadUnavailableError(api_sha, pr_ref, pr_ref_sha, remote_name, attempts)


def _commit_is_present(runner: ProcessRunner, *, cwd: str, sha: str) -> bool:
    """``cat-file -e``: exit 0 is present; non-zero is simply absent."""
    argv = ["git", "cat-file", "-e", f"{sha}^{{commit}}"]
    try:
        result = runner.run(argv, cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    except ProcessTimedOutError as exc:
        _logger.warning("git cat-file exceeded %ss", exc.timeout, extra={RENDERED_BY_CALLER: True})
        raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc
    _logger.debug("commit %s present locally: %s", sha, result.returncode == 0)
    return result.returncode == 0


def _fetch_api_head(
    runner: ProcessRunner,
    *,
    cwd: str,
    remote_name: str,
    source: str,
    api_local: str,
    api_sha: str,
) -> str | None:
    """One fetch attempt into ``api_local``; ``None`` on success, else the reason."""
    argv = ["git", "fetch", "--no-tags", remote_name, f"+{source}:{api_local}"]
    try:
        result = runner.run(argv, cwd=cwd, timeout=GIT_FETCH_TIMEOUT_SECONDS)
        if result.returncode != 0:
            return result.stderr.strip() or "(no stderr)"
        fetched = _rev_parse(runner, cwd=cwd, ref=api_local)
    except ProcessTimedOutError as exc:
        return f"timed out after {exc.timeout:g}s"
    if fetched == api_sha:
        return None
    return f"fetched {fetched or 'nothing'}, not the API head {api_sha}"


def _read_ref(runner: ProcessRunner, *, cwd: str, ref: str, role: RefRole) -> str:
    """Resolve a fetched ref to its sha; a ref that is missing after a fetch is an error."""
    actual = _rev_parse(runner, cwd=cwd, ref=ref)
    if actual is None:
        _logger.warning(
            "%s ref %s is missing after fetch", role.value, ref, extra={RENDERED_BY_CALLER: True}
        )
        raise RefNotFetchableError(role, f"{role.value} ref {ref} is missing after fetch")
    return actual


def _moved_since_resolution(
    role: RefRole, expected: str, actual: str, source: str
) -> RefMovedSinceResolutionError:
    """Log (tagged: the command renders it) and build the error for a ref that moved."""
    _logger.warning(
        "%s moved since resolution: expected %s, found %s",
        role.value,
        expected,
        actual,
        extra={RENDERED_BY_CALLER: True},
    )
    return RefMovedSinceResolutionError(
        role, expected, actual, expected_source="host API", actual_source=source
    )


def _verify(
    runner: ProcessRunner,
    *,
    cwd: str,
    ref: str,
    role: RefRole,
    expected: str,
    source: str,
) -> tuple[str, RefAdjustment | None]:
    """Resolve the base ref and confirm it is the sha the host reported.

    Returns the sha to use and, when it differs from the reported one, the
    ``RefAdjustment`` that says so.

    A fetched sha that descends from ``expected`` passes and is returned in its
    place. GitHub's ``baseRefOid`` can trail the base branch's real tip after a
    merge, while ``git fetch`` already serves the new tip (#131). A base that only
    moved forward still yields the same three-dot range, so the fetched tip is the
    right one to review against. Any other movement (rewind, force-push) fails.
    """
    actual = _read_ref(runner, cwd=cwd, ref=ref, role=role)
    if actual == expected:
        return actual, None
    if _is_ancestor(runner, cwd=cwd, ancestor=expected, descendant=actual):
        _logger.warning(
            "%s advanced since resolution: host reported %s, fetched %s (a descendant); "
            "using the fetched tip",
            role.value,
            expected,
            actual,
        )
        adjustment = RefAdjustment(
            role=role,
            reported_sha=expected,
            used_sha=actual,
            source=source,
            reason=f"{role.value} advanced since resolution",
        )
        return actual, adjustment
    raise _moved_since_resolution(role, expected, actual, source)


class _HeadRelation(StrEnum):
    """How the pull-request ref's sha relates to the API head."""

    LAGS = "lags"  # the PR ref is an ancestor of the API head
    MOVED = "moved"  # the PR ref descends from the API head: pushed after resolution
    UNRELATED = "unrelated"  # a force-push or rewrite


def _head_relation(runner: ProcessRunner, *, cwd: str, pr_ref_sha: str, api_sha: str) -> _HeadRelation:
    """Classify ``pr_ref_sha`` against ``api_sha``; both commits must be local."""
    if _is_ancestor(runner, cwd=cwd, ancestor=pr_ref_sha, descendant=api_sha):
        return _HeadRelation.LAGS
    if _is_ancestor(runner, cwd=cwd, ancestor=api_sha, descendant=pr_ref_sha):
        return _HeadRelation.MOVED
    return _HeadRelation.UNRELATED


def _resolve_head(
    runner: ProcessRunner,
    *,
    cwd: str,
    remote_name: str,
    namespace: int,
    head_local: str,
    head_source: str,
    expected: str,
    head_fallback_sources: tuple[str, ...],
) -> tuple[str, RefAdjustment | None]:
    """The head sha to review and, when it is not the PR ref's, the adjustment saying so.

    When the fetched pull-request ref differs from the API head, the API head is
    made local first (``ensure_api_head``): ancestry cannot be answered for a
    commit that is absent, and ``_is_ancestor`` fails closed on one. A ref that
    merely lags is repointed at the API head; a ref that moved or was rewritten is
    an error. Only the exact API head sha is ever reviewed.
    """
    actual = _read_ref(runner, cwd=cwd, ref=head_local, role=RefRole.HEAD)
    if actual == expected:
        return actual, None
    how = ensure_api_head(
        runner,
        cwd=cwd,
        remote_name=remote_name,
        api_sha=expected,
        api_local=api_head_ref(remote_name, namespace),
        pr_ref=head_source,
        pr_ref_sha=actual,
        head_fallback_sources=head_fallback_sources,
    )
    relation = _head_relation(runner, cwd=cwd, pr_ref_sha=actual, api_sha=expected)
    if relation is not _HeadRelation.LAGS:
        raise _moved_since_resolution(RefRole.HEAD, expected, actual, head_source)
    _point_ref_at(runner, cwd=cwd, ref=head_local, sha=expected)
    _logger.warning(
        "%s lags the host API head: reviewing %s (%s) instead of %s",
        head_source,
        expected,
        how,
        actual,
    )
    return expected, RefAdjustment(
        role=RefRole.HEAD,
        reported_sha=actual,
        used_sha=expected,
        source=how,
        reason=f"{head_source} lags",
    )


def _point_ref_at(runner: ProcessRunner, *, cwd: str, ref: str, sha: str) -> None:
    """``update-ref``: failure or timeout is rendered, never silent."""
    argv = ["git", "update-ref", ref, sha]
    try:
        result = runner.run(argv, cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    except ProcessTimedOutError as exc:
        _logger.warning("git update-ref exceeded %ss", exc.timeout, extra={RENDERED_BY_CALLER: True})
        raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc
    if result.returncode != 0:
        _logger.warning(
            "could not point %s at %s: %s",
            ref,
            sha,
            result.stderr.strip(),
            extra={RENDERED_BY_CALLER: True},
        )
        raise RefNotFetchableError(
            RefRole.HEAD,
            f"could not point {ref} at the API head {sha}: {result.stderr.strip() or '(no stderr)'}",
        )


def _is_ancestor(runner: ProcessRunner, *, cwd: str, ancestor: str, descendant: str) -> bool:
    """Is ``ancestor`` reachable from ``descendant``?

    ``merge-base --is-ancestor`` exits 0 for yes and 1 for no. Anything else
    (e.g. ``ancestor`` absent locally) is logged and answered no, so the caller
    fails closed.
    """
    argv = ["git", "merge-base", "--is-ancestor", ancestor, descendant]
    try:
        result = runner.run(argv, cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    except ProcessTimedOutError as exc:
        _logger.warning(
            "git merge-base --is-ancestor exceeded %ss", exc.timeout, extra={RENDERED_BY_CALLER: True}
        )
        raise HostCommandTimeoutError(exc.argv, exc.timeout) from exc
    if result.returncode not in (0, 1):
        _logger.warning(
            "could not test ancestry of %s in %s: %s", ancestor, descendant, result.stderr.strip()
        )
    return result.returncode == 0


def _rev_parse(runner: ProcessRunner, *, cwd: str, ref: str) -> str | None:
    """Resolve a ref to its sha, or ``None`` when it does not exist."""
    result = runner.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=cwd,
        timeout=GIT_QUERY_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def _merge_base(runner: ProcessRunner, *, cwd: str, base: str, head: str) -> str:
    """The commit base and head diverged from."""
    result = runner.run(["git", "merge-base", base, head], cwd=cwd, timeout=GIT_QUERY_TIMEOUT_SECONDS)
    merge_base = result.stdout.strip()
    if result.returncode != 0 or not merge_base:
        _logger.warning(
            "no merge base between %s and %s: %s",
            base,
            head,
            result.stderr.strip(),
            extra={RENDERED_BY_CALLER: True},
        )
        raise NoMergeBaseError(
            f"{base} and {head} share no common ancestor, so there is no range to review"
        )
    return merge_base


def _changed_paths(runner: ProcessRunner, *, cwd: str, diff_range: str) -> tuple[str, ...]:
    """Every path touched across the range.

    No exclusion patterns: 382 applies the review template's patterns through
    the existing scope assertion, so filtering here would apply them twice.
    """
    result = runner.run(
        ["git", "diff", "--name-only", diff_range],
        cwd=cwd,
        timeout=GIT_QUERY_TIMEOUT_SECONDS,
    )
    return tuple(line for line in result.stdout.splitlines() if line.strip())
