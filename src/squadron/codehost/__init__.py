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
from squadron.codehost.github_cli import GitHubCli, build_github_host
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
from squadron.codehost.worktree import (
    ProcessIdentityUnresolvableError,
    ScratchWorktree,
    SubmoduleTimeoutError,
    SubmoduleUnfetchableError,
    WorktreeCreationError,
    WorktreeError,
    WorktreeLock,
    sweep_orphans,
)

__all__ = [
    "AmbiguousBranchPullRequestsError",
    "AmbiguousHostRemoteError",
    "CodeHost",
    "CodeHostError",
    "FetchedRange",
    "ForeignRepositoryError",
    "GitHubCli",
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
    "ProcessIdentityUnresolvableError",
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
    "ScratchWorktree",
    "SubmoduleTimeoutError",
    "SubmoduleUnfetchableError",
    "TargetForm",
    "TargetSyntaxError",
    "TargetUnresolvableError",
    "WorktreeCreationError",
    "WorktreeError",
    "WorktreeLock",
    # Sorted uppercase-first above; the functions trail by convention.
    "build_github_host",
    "list_remotes",
    "parse_remote_url",
    "parse_target",
    "select_remote",
    "sweep_orphans",
]
