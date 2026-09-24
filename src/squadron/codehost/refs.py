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

from squadron.codehost.errors import (
    NoMergeBaseError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
)
from squadron.codehost.models import FetchedRange, RefRole
from squadron.core.process_runner import ProcessRunner

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
) -> FetchedRange:
    """Fetch base and head, verify they are what the host reported, describe the range.

    ``namespace`` is the pull-request number the local refs are filed under.
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

    base_sha = _verify(
        runner,
        cwd=cwd,
        ref=base_local,
        role=RefRole.BASE,
        expected=expected_base_sha,
        accept_fast_forward=True,
    )
    head_sha = _verify(
        runner,
        cwd=cwd,
        ref=head_local,
        role=RefRole.HEAD,
        expected=expected_head_sha,
        accept_fast_forward=False,
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
    result = runner.run(argv, cwd=cwd, timeout=GIT_FETCH_TIMEOUT_SECONDS)
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
            )
            raise RefNotFetchableError(
                role,
                f"could not fetch {role.value} from {remote_name}: "
                f"{result.stderr.strip() or '(no stderr)'}",
                fix_hint="Check the remote is reachable and the pull request still exists.",
            )

    # Both refs are present despite the non-zero exit; treat it as a base-side
    # failure rather than continuing with an unexplained error.
    _logger.warning("git fetch exited %s: %s", result.returncode, result.stderr.strip())
    raise RefNotFetchableError(
        RefRole.BASE,
        f"git fetch failed: {result.stderr.strip() or '(no stderr)'}",
    )


def _verify(
    runner: ProcessRunner,
    *,
    cwd: str,
    ref: str,
    role: RefRole,
    expected: str,
    accept_fast_forward: bool,
) -> str:
    """Resolve ``ref`` and confirm it is the sha the host reported.

    With ``accept_fast_forward``, a fetched sha that descends from ``expected``
    passes and is returned in its place. GitHub's ``baseRefOid`` can trail the
    base branch's real tip after a merge, while ``git fetch`` already serves the
    new tip (#131). A base that only moved forward still yields the same
    three-dot range, so the fetched tip is the right one to review against. Any
    other movement (rewind, force-push) still fails.
    """
    actual = _rev_parse(runner, cwd=cwd, ref=ref)
    if actual is None:
        _logger.warning("%s ref %s is missing after fetch", role.value, ref)
        raise RefNotFetchableError(role, f"{role.value} ref {ref} is missing after fetch")
    if actual == expected:
        return actual
    if accept_fast_forward and _is_ancestor(runner, cwd=cwd, ancestor=expected, descendant=actual):
        _logger.warning(
            "%s advanced since resolution: host reported %s, fetched %s (a descendant); "
            "using the fetched tip",
            role.value,
            expected,
            actual,
        )
        return actual
    _logger.warning("%s moved since resolution: expected %s, found %s", role.value, expected, actual)
    raise RefMovedSinceResolutionError(role, expected, actual)


def _is_ancestor(runner: ProcessRunner, *, cwd: str, ancestor: str, descendant: str) -> bool:
    """Is ``ancestor`` reachable from ``descendant``?

    ``merge-base --is-ancestor`` exits 0 for yes and 1 for no. Anything else
    (e.g. ``ancestor`` absent locally) is logged and answered no, so the caller
    fails closed.
    """
    result = runner.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=cwd,
        timeout=GIT_QUERY_TIMEOUT_SECONDS,
    )
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
        _logger.warning("no merge base between %s and %s: %s", base, head, result.stderr.strip())
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
