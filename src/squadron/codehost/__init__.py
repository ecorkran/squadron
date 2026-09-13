"""Code-host adapter: typed PR records, a host protocol, and a GitHub implementation.

This module re-exports the package's public surface — the contract slices 382,
384, and 385 import. Deep-path imports into the submodules are not the
interface; each name below is added as its part lands.
"""

from __future__ import annotations

from squadron.codehost.errors import (
    AmbiguousBranchPullRequestsError,
    AmbiguousHostRemoteError,
    CodeHostError,
    ForeignRepositoryError,
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostRequestRejectedError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    HostUnreachableError,
    NoHostRemoteError,
    NoMergeBaseError,
    NoOpenPullRequestForBranchError,
    OperatorUnidentifiedError,
    PullRequestCreationRejectedError,
    PullRequestNotFoundError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
    TargetSyntaxError,
    TargetUnresolvableError,
)
from squadron.codehost.models import (
    FetchedRange,
    HostComment,
    LocalRemote,
    OperatorIdentity,
    PullRequestRecord,
    PullRequestState,
    RefRole,
    RepositoryLocator,
    ResolvedPullRequest,
    ReviewDiscussion,
)
from squadron.codehost.protocol import CodeHost
from squadron.codehost.remotes import list_remotes, parse_remote_url, select_remote
from squadron.codehost.targets import PullRequestTarget, TargetForm, parse_target

__all__ = [
    "AmbiguousBranchPullRequestsError",
    "AmbiguousHostRemoteError",
    "CodeHost",
    "CodeHostError",
    "FetchedRange",
    "ForeignRepositoryError",
    "GitHubCliMissingError",
    "HostComment",
    "HostCommandTimeoutError",
    "HostRequestRejectedError",
    "HostResponseMalformedError",
    "HostUnauthenticatedError",
    "HostUnreachableError",
    "LocalRemote",
    "NoHostRemoteError",
    "NoMergeBaseError",
    "NoOpenPullRequestForBranchError",
    "OperatorIdentity",
    "OperatorUnidentifiedError",
    "PullRequestCreationRejectedError",
    "PullRequestNotFoundError",
    "PullRequestRecord",
    "PullRequestState",
    "PullRequestTarget",
    "RefMovedSinceResolutionError",
    "RefNotFetchableError",
    "RefRole",
    "RepositoryLocator",
    "ResolvedPullRequest",
    "ReviewDiscussion",
    "TargetForm",
    "TargetSyntaxError",
    "TargetUnresolvableError",
    # Sorted uppercase-first above; the functions trail by convention.
    "list_remotes",
    "parse_remote_url",
    "parse_target",
    "select_remote",
]
