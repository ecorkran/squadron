"""The code-host error hierarchy.

Twenty classes across the design's fifteen error-table rows — three rows group
more than one class. Every failure path raises one of these, logs once at
WARNING or ERROR with structured fields before raising, and exits 1 through the
CLI. There is no silent path.

Structured values are carried as attributes, not only interpolated into the
message, so tests and callers assert on data rather than on message text.
"""

from __future__ import annotations

from collections.abc import Sequence

from squadron.codehost.models import RefRole

#: ``extra`` key on a log record the command prints itself as a rendered error or
#: adjustment line. The code-host log filter drops tagged records below ``-vv``,
#: so each failure prints once.
RENDERED_BY_CALLER = "rendered_by_caller"

_SHA_DISPLAY_LENGTH = 7


def _short(sha: str) -> str:
    return f"{sha[:_SHA_DISPLAY_LENGTH]}…"


class CodeHostError(Exception):
    """Base for every code-host failure.

    ``fix_hint`` is operator-facing remediation shown alongside the message,
    kept separate from it so the two are formatted independently.
    """

    def __init__(self, message: str, *, fix_hint: str | None = None) -> None:
        super().__init__(message)
        self.fix_hint = fix_hint


# --- Availability and transport -------------------------------------------


class GitHubCliMissingError(CodeHostError):
    """The ``gh`` executable is not on PATH."""


class HostUnauthenticatedError(CodeHostError):
    """The host refused the request for lack of valid credentials."""


class HostUnreachableError(CodeHostError):
    """The host could not be contacted."""


class HostCommandTimeoutError(CodeHostError):
    """A host call exceeded its wall-clock bound.

    Distinct from unreachability: the process started and did not finish.
    """

    def __init__(self, argv: Sequence[str], seconds: float, *, fix_hint: str | None = None) -> None:
        super().__init__(f"host command exceeded {seconds}s: {' '.join(argv)}", fix_hint=fix_hint)
        self.argv = tuple(argv)
        self.seconds = seconds


# --- Pull request resolution ----------------------------------------------


class PullRequestNotFoundError(CodeHostError):
    """No pull request exists for the resolved coordinates."""


class NoOpenPullRequestForBranchError(CodeHostError):
    """The branch resolved, but no open pull request is associated with it."""


class AmbiguousBranchPullRequestsError(CodeHostError):
    """More than one open pull request matches the branch."""


# --- Repository and remote selection --------------------------------------


class ForeignRepositoryError(CodeHostError):
    """The target names a repository none of the local remotes serves."""


class NoHostRemoteError(CodeHostError):
    """No local remote belongs to a host this implementation serves."""


class AmbiguousHostRemoteError(CodeHostError):
    """Several remotes could serve the target and none is preferred."""


# --- Target grammar --------------------------------------------------------


class TargetSyntaxError(CodeHostError):
    """The target string matches none of the accepted forms."""


class TargetUnresolvableError(CodeHostError):
    """The target parsed, but no pull request could be derived from it."""


# --- Refs and ranges -------------------------------------------------------


class RefNotFetchableError(CodeHostError):
    """A required ref could not be fetched from the remote."""

    def __init__(self, role: RefRole, message: str, *, fix_hint: str | None = None) -> None:
        super().__init__(message, fix_hint=fix_hint)
        self.role = role


class RefMovedSinceResolutionError(CodeHostError):
    """A ref changed between resolution and fetch, invalidating the range.

    ``expected_source`` and ``actual_source`` name where each sha came from (for
    example ``host API`` and ``refs/pull/49/head``), so the message says which
    two readings disagree.
    """

    def __init__(
        self,
        role: RefRole,
        expected: str,
        actual: str,
        *,
        expected_source: str,
        actual_source: str,
        fix_hint: str | None = "Rerun to resolve the pull request again.",
    ) -> None:
        super().__init__(
            f"{role.value} moved since resolution: {expected_source} reported {_short(expected)}, "
            f"{actual_source} fetched {_short(actual)}",
            fix_hint=fix_hint,
        )
        self.role = role
        self.expected = expected
        self.actual = actual
        self.expected_source = expected_source
        self.actual_source = actual_source


class PullRequestHeadUnavailableError(CodeHostError):
    """The host's API head commit could not be fetched from any source.

    Raised when the pull-request ref and the API disagree and the API head is
    not obtainable, so whether the ref merely lags is unknown. ``attempts`` pairs
    each source tried with its reason for failing.
    """

    def __init__(
        self,
        api_sha: str,
        pr_ref: str,
        pr_ref_sha: str,
        remote_name: str,
        attempts: Sequence[tuple[str, str]],
    ) -> None:
        tried = "; ".join(f"{source}: {reason}" for source, reason in attempts)
        super().__init__(
            f"pull request head {_short(api_sha)} (host API) could not be fetched; "
            f"{pr_ref} on {remote_name} is {_short(pr_ref_sha)}; {tried}",
            fix_hint=(
                "The host's pull-request ref and its API disagree, and the API head is not "
                "fetchable from origin yet. Rerun later, or push the head branch to a remote "
                "this checkout can fetch."
            ),
        )
        self.role = RefRole.HEAD
        self.api_sha = api_sha
        self.pr_ref_sha = pr_ref_sha
        self.attempts = tuple(attempts)


class NoMergeBaseError(CodeHostError):
    """Base and head share no merge base, so no diff range exists."""


# --- Host responses --------------------------------------------------------


class HostRequestRejectedError(CodeHostError):
    """The host accepted the request and refused it with a status."""

    def __init__(self, status: int, message: str, *, fix_hint: str | None = None) -> None:
        super().__init__(message, fix_hint=fix_hint)
        self.status = status


class PullRequestCreationRejectedError(CodeHostError):
    """The host refused to create the pull request."""


class HostResponseMalformedError(CodeHostError):
    """The host returned output that could not be parsed as expected."""

    def __init__(self, argv: Sequence[str], detail: str, *, fix_hint: str | None = None) -> None:
        super().__init__(f"malformed response from {' '.join(argv)}: {detail}", fix_hint=fix_hint)
        self.argv = tuple(argv)
        self.detail = detail


class OperatorUnidentifiedError(CodeHostError):
    """The operator's identity on the host could not be determined."""
