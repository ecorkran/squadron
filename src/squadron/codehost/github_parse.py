"""Turning ``gh`` responses into typed records.

Split out of ``github_cli.py``: shaping a response is a different job from
issuing one, and it changes when GitHub's payloads change rather than when the
transport does. Nothing here runs a process.

A field that should be present and is not is ``gh`` drift, reported as
``HostResponseMalformedError`` rather than escaping as a ``KeyError`` or a
``ValueError`` from the middle of a parse.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

from squadron.codehost.errors import HostResponseMalformedError
from squadron.codehost.models import (
    PullRequestRecord,
    PullRequestState,
    RepositoryLocator,
    ResolvedPullRequest,
    ReviewDiscussion,
)


def dig(payload: Mapping[str, Any], path: Sequence[str]) -> Any:
    """Walk a nested mapping, returning ``None`` at the first missing step."""
    current: Mapping[str, Any] = payload
    for key in path:
        value: Any = current.get(key)
        if isinstance(value, dict):
            current = cast(Mapping[str, Any], value)
            continue
        # A leaf, or a missing key: either way the walk ends here. Remaining
        # path segments mean the caller asked for something absent.
        return value if key == path[-1] else None
    return current


def dig_list(payload: Mapping[str, Any], path: Sequence[str]) -> list[dict[str, Any]]:
    """Walk to a list of objects, treating anything else as absent."""
    found = dig(payload, path)
    if not isinstance(found, list):
        return []
    items = cast(list[Any], found)
    return [item for item in items if isinstance(item, dict)]


def require(payload: Mapping[str, Any], key: str, argv: Sequence[str]) -> Any:
    """Read a field that must be present."""
    if key not in payload or payload[key] is None:
        raise HostResponseMalformedError(tuple(argv), f"missing field {key!r}")
    return payload[key]


def require_str(payload: Mapping[str, Any], key: str, argv: Sequence[str]) -> str:
    """Read a required field as text."""
    return str(require(payload, key, argv))


def require_int(payload: Mapping[str, Any], key: str, argv: Sequence[str]) -> int:
    """Read a required field as an integer.

    A field that should be numeric and is not is drift, not a ``ValueError``
    escaping from the middle of a parse.
    """
    value = require(payload, key, argv)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise HostResponseMalformedError(
            tuple(argv), f"field {key!r} is not an integer: {value!r}"
        ) from exc


def _nested_str(node: Mapping[str, Any], key: str, inner: str) -> str:
    """Read ``node[key][inner]`` as text, tolerating either being absent."""
    value = node.get(key)
    if not isinstance(value, dict):
        return ""
    return str(cast(Mapping[str, Any], value).get(inner, ""))


def to_resolved(node: Mapping[str, Any], locator: RepositoryLocator) -> ResolvedPullRequest:
    """Build a resolved pull request from a GraphQL node."""
    argv = ("gh", "graphql")
    record = PullRequestRecord(
        host=locator.host,
        owner=locator.owner,
        repository=locator.repository,
        number=require_int(node, "number", argv),
        base_ref=require_str(node, "baseRefName", argv),
        head_ref=require_str(node, "headRefName", argv),
        head_sha=require_str(node, "headRefOid", argv),
        url=require_str(node, "url", argv),
    )

    raw_state = require_str(node, "state", argv)
    try:
        # GraphQL returns these uppercase; map explicitly rather than trusting
        # a case coincidence to hold.
        state = PullRequestState(raw_state)
    except ValueError as exc:
        raise HostResponseMalformedError(argv, f"unknown state {raw_state!r}") from exc

    linked = dig_list(node, ("closingIssuesReferences", "nodes"))
    return ResolvedPullRequest(
        record=record,
        title=str(node.get("title") or ""),
        body=str(node.get("body") or ""),
        state=state,
        author_login=_nested_str(node, "author", "login"),
        base_sha=require_str(node, "baseRefOid", argv),
        is_cross_repository=bool(node.get("isCrossRepository")),
        head_repository=_nested_str(node, "headRepository", "nameWithOwner"),
        linked_issue_numbers=tuple(int(item["number"]) for item in linked if "number" in item),
    )


def to_discussions(threads: Mapping[str, Any]) -> list[ReviewDiscussion]:
    """Extract unresolved threads from one page of review threads."""
    discussions: list[ReviewDiscussion] = []
    for thread in dig_list(threads, ("nodes",)):
        if thread.get("isResolved"):
            continue
        for comment in dig_list(thread, ("comments", "nodes")):
            discussions.append(
                ReviewDiscussion(
                    path=str(comment.get("path") or ""),
                    line=int(comment.get("line") or 0),
                    author_login=_nested_str(comment, "author", "login"),
                    body=str(comment.get("body") or ""),
                    url=str(comment.get("url") or ""),
                )
            )
    return discussions
