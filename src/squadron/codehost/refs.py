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
    RENDERED_BY_CALLER,
    HostCommandTimeoutError,
    NoMergeBaseError,
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
from squadron.codehost.head_resolution import resolve_head
from squadron.codehost.models import FetchedRange, RefAdjustment, RefRole
from squadron.core.process_runner import ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)


def local_ref(remote_name: str, number: int, role: RefRole) -> str:
    """The local ref a fetched endpoint lands on."""
    return f"{REF_NAMESPACE}/{remote_name}/{number}/{role.value}"


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
    head_sha, head_adjustment = resolve_head(
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
        if rev_parse(runner, cwd=cwd, ref=destination) is None:
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
    actual = read_ref(runner, cwd=cwd, ref=ref, role=role)
    if actual == expected:
        return actual, None
    if is_ancestor(runner, cwd=cwd, ancestor=expected, descendant=actual):
        # Tagged: the command prints the matching adjustment line.
        _logger.warning(
            "%s advanced since resolution: host reported %s, fetched %s (a descendant); "
            "using the fetched tip",
            role.value,
            expected,
            actual,
            extra={RENDERED_BY_CALLER: True},
        )
        adjustment = RefAdjustment(
            role=role,
            reported_sha=expected,
            used_sha=actual,
            source=f"fetched from {source}",
            reason="advanced since resolution",
        )
        return actual, adjustment
    raise moved_since_resolution(role, expected, actual, source)


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
