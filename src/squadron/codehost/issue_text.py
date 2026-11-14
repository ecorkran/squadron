"""The text of an issue snapshot, as a producer reads it (slice 422 D2, slice 423 D3).

Kept beside the code-host models so both the benchmark's frozen cases and the fix
pipeline's fetched issues render the same markdown without one importing the other.
"""

from __future__ import annotations

from datetime import UTC, datetime

from squadron.codehost.models import IssueComment, IssueSnapshot

_HEADING_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"


def require_aware(value: datetime, what: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{what} is a naive timestamp; issue times must be timezone-aware")
    return value


def included_comments(snapshot: IssueSnapshot, cutoff: datetime | None) -> list[IssueComment]:
    if cutoff is None:
        return list(snapshot.comments)
    return [
        comment
        for comment in snapshot.comments
        if require_aware(comment.created_at, "comment created_at") < cutoff
    ]


def _comment_heading(comment: IssueComment) -> str:
    when = comment.created_at.astimezone(UTC).strftime(_HEADING_TIME_FORMAT)
    return f"## Comment by {comment.author_login} on {when}"


def render_issue(snapshot: IssueSnapshot, cutoff: datetime | None) -> str:
    """Title, body and each comment in order, those created at or after ``cutoff`` omitted."""
    if cutoff is not None:
        require_aware(cutoff, "cutoff")
    parts = [f"# {snapshot.title}", snapshot.body]
    for comment in included_comments(snapshot, cutoff):
        parts.extend([_comment_heading(comment), comment.body])
    return "\n\n".join(parts) + "\n"
