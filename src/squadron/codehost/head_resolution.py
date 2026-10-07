"""Resolving a pull request head when ``refs/pull/N/head`` disagrees with the host API (#186).

Host-agnostic: the caller names any host-specific fallback refspecs. Only the exact
API head sha is ever reviewed; this module changes where that sha is fetched from.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from squadron.codehost.errors import (
    RENDERED_BY_CALLER,
    HostCommandTimeoutError,
    PullRequestHeadUnavailableError,
    RefNotFetchableError,
)
from squadron.codehost.git_refs import (
    GIT_FETCH_TIMEOUT_SECONDS,
    GIT_QUERY_TIMEOUT_SECONDS,
    REF_NAMESPACE,
    is_ancestor,
    moved_since_resolution,
    read_ref,
    rev_parse,
)
from squadron.codehost.models import RefAdjustment, RefRole
from squadron.core.process_runner import ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)


def api_head_ref(remote_name: str, number: int) -> str:
    """Where the host API's head commit lands when the pull-request ref lags it."""
    return f"{REF_NAMESPACE}/{remote_name}/{number}/api-head"


#: What ``ensure_api_head`` reports for a commit that needed no fetch.
HEAD_PRESENT_LOCALLY = "present locally"


#: The label for the host-neutral attempt: fetch the commit by its sha.
HEAD_FETCHED_BY_SHA = "fetched by sha"


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

    ``api_local`` is left in place afterwards, like the base and head refs: it is
    namespaced under ``refs/squadron/pr/``, force-updated by the next fetch of the
    same pull request, and never a branch, so it is harmless to leave.

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
        fetched = rev_parse(runner, cwd=cwd, ref=api_local)
    except ProcessTimedOutError as exc:
        return f"timed out after {exc.timeout:g}s"
    if fetched == api_sha:
        return None
    return f"fetched {fetched or 'nothing'}, not the API head {api_sha}"


class _HeadRelation(StrEnum):
    """How the pull-request ref's sha relates to the API head."""

    LAGS = "lags"  # the PR ref is an ancestor of the API head
    MOVED = "moved"  # the PR ref descends from the API head: pushed after resolution
    UNRELATED = "unrelated"  # a force-push or rewrite


def _head_relation(runner: ProcessRunner, *, cwd: str, pr_ref_sha: str, api_sha: str) -> _HeadRelation:
    """Classify ``pr_ref_sha`` against ``api_sha``; both commits must be local."""
    if is_ancestor(runner, cwd=cwd, ancestor=pr_ref_sha, descendant=api_sha):
        return _HeadRelation.LAGS
    if is_ancestor(runner, cwd=cwd, ancestor=api_sha, descendant=pr_ref_sha):
        return _HeadRelation.MOVED
    return _HeadRelation.UNRELATED


def resolve_head(
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
    commit that is absent, and ``is_ancestor`` fails closed on one. A ref that
    merely lags is repointed at the API head; a ref that moved or was rewritten is
    an error. Only the exact API head sha is ever reviewed.
    """
    actual = read_ref(runner, cwd=cwd, ref=head_local, role=RefRole.HEAD)
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
        raise moved_since_resolution(RefRole.HEAD, expected, actual, head_source)
    _point_ref_at(runner, cwd=cwd, ref=head_local, sha=expected)
    # Tagged: the command prints the matching adjustment line.
    _logger.warning(
        "%s lags the host API head: reviewing %s (%s) instead of %s",
        head_source,
        expected,
        how,
        actual,
        extra={RENDERED_BY_CALLER: True},
    )
    return expected, RefAdjustment(
        role=RefRole.HEAD,
        reported_sha=actual,
        used_sha=expected,
        source=_how_obtained(how),
        reason=f"{head_source} lags",
    )


def _how_obtained(how: str) -> str:
    """``ensure_api_head``'s label as a phrase: a fallback source reads ``fetched from <it>``."""
    if how in (HEAD_PRESENT_LOCALLY, HEAD_FETCHED_BY_SHA):
        return how
    return f"fetched from {how}"


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
