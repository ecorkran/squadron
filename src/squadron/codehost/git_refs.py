"""Git reads on fetched pull-request refs, shared by ``refs`` and ``head_resolution``.

Host-agnostic, over the injected runner. Each read is bounded; a failure either
answers "no" with a logged WARNING (``is_ancestor`` fails closed) or raises a code
host error the command renders.
"""

from __future__ import annotations

import logging

from squadron.codehost.errors import (
    RENDERED_BY_CALLER,
    HostCommandTimeoutError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
)
from squadron.codehost.models import RefRole
from squadron.core.process_runner import ProcessRunner, ProcessTimedOutError

_logger = logging.getLogger(__name__)

#: Wall-clock bound on the git queries here — rev-parse, merge-base, diff.
GIT_QUERY_TIMEOUT_SECONDS = 30


#: Fetch moves data over the network; the query bound is far too tight for it.
GIT_FETCH_TIMEOUT_SECONDS = 300


#: Where fetched pull-request endpoints land. Namespacing by remote keeps PR 12
#: on ``origin`` distinct from PR 12 on ``upstream``.
REF_NAMESPACE = "refs/squadron/pr"


def read_ref(runner: ProcessRunner, *, cwd: str, ref: str, role: RefRole) -> str:
    """Resolve a fetched ref to its sha; a ref that is missing after a fetch is an error."""
    actual = rev_parse(runner, cwd=cwd, ref=ref)
    if actual is None:
        _logger.warning(
            "%s ref %s is missing after fetch", role.value, ref, extra={RENDERED_BY_CALLER: True}
        )
        raise RefNotFetchableError(role, f"{role.value} ref {ref} is missing after fetch")
    return actual


def moved_since_resolution(
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


def is_ancestor(runner: ProcessRunner, *, cwd: str, ancestor: str, descendant: str) -> bool:
    """Is ``ancestor`` reachable from ``descendant``?

    ``merge-base --is-ancestor`` exits 0 for yes and 1 for no. Anything else
    (e.g. ``ancestor`` absent locally) is logged and answered no, so the caller
    fails closed.

    Deliberately not ``pipeline.git_ops._is_ancestor``, which raises on an unexpected
    exit. Here a wrong "no" ends in a rendered "head moved" error the operator can
    rerun; there a wrong "no" would reopen a merged slice and reimplement it.
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


def rev_parse(runner: ProcessRunner, *, cwd: str, ref: str) -> str | None:
    """Resolve a ref to its sha, or ``None`` when it does not exist."""
    result = runner.run(
        ["git", "rev-parse", "--verify", f"{ref}^{{commit}}"],
        cwd=cwd,
        timeout=GIT_QUERY_TIMEOUT_SECONDS,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None
