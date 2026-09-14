"""Typed records for code-host entities.

Field names are the architecture's — they are the contract slices 382, 384, and
385 import, so they are not renamed here.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PullRequestState(StrEnum):
    """Lifecycle state of a pull request.

    GraphQL returns these uppercase; mapping is explicit at the parse boundary
    rather than relying on case coincidence.
    """

    OPEN = "OPEN"
    CLOSED = "CLOSED"
    MERGED = "MERGED"


class RefRole(StrEnum):
    """Which end of a pull request range a ref represents."""

    BASE = "base"
    HEAD = "head"


@dataclass(frozen=True)
class PullRequestRecord:
    """Identity of a pull request, produced once and passed around after."""

    host: str
    owner: str
    repository: str
    number: int
    base_ref: str
    head_ref: str
    head_sha: str
    url: str

    @property
    def key(self) -> str:
        """Stable, filesystem-safe identifier.

        383 uses this as a filename prefix, so it must not acquire characters
        that a path cannot carry.
        """
        return f"{self.host}/{self.owner}/{self.repository}#{self.number}"


@dataclass(frozen=True)
class ResolvedPullRequest:
    """A record plus the content fields a review needs."""

    record: PullRequestRecord
    title: str
    body: str
    state: PullRequestState
    author_login: str
    base_sha: str
    is_cross_repository: bool
    head_repository: str
    linked_issue_numbers: tuple[int, ...]


@dataclass(frozen=True)
class RepositoryLocator:
    """The repository a target resolved to, and the remote it came from."""

    host: str
    owner: str
    repository: str
    remote_name: str


@dataclass(frozen=True)
class LocalRemote:
    """A git remote and the repository coordinates parsed out of its URL.

    ``host`` is ``None`` when the URL matches no known shape. Such a remote is
    never a candidate for selection, but it is retained so ambiguity messages
    can name it — dropping it silently is the failure mode that guards against.
    """

    name: str
    host: str | None
    owner: str | None
    repository: str | None
    url: str


@dataclass(frozen=True)
class FetchedRange:
    """The result of fetching a pull request's base and head."""

    base_ref: str
    head_ref: str
    base_sha: str
    head_sha: str
    merge_base: str
    diff_range: str
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class ReviewDiscussion:
    """One review comment thread anchored at a file and line."""

    path: str
    line: int
    author_login: str
    body: str
    url: str


@dataclass(frozen=True)
class HostComment:
    """A top-level comment on a pull request."""

    id: str
    author_login: str
    body: str
    url: str


@dataclass(frozen=True)
class OperatorIdentity:
    """Who the operator is authenticated as on a given host."""

    host: str
    login: str
