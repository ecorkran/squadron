"""Frozen issue text for a case (slice 422 D2).

``render_issue`` turns an ``IssueSnapshot`` into the markdown a producer is given as its
task. With a cutoff (a fix commit's committer date) it keeps only what existed before
the cutoff; ``freeze_issue`` additionally refuses an issue whose title, body or kept
comments were edited after the cutoff, because the text as it stood then cannot be
recovered and today's version may describe the fix.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from squadron.codehost.models import IssueComment, IssueSnapshot
from squadron.metrology.benchmark_models import CandidateRejection

_HEADING_TIME_FORMAT = "%Y-%m-%d %H:%M UTC"


@dataclass(frozen=True)
class FrozenIssue:
    task_text: str


def _require_aware(value: datetime, what: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError(f"{what} is a naive timestamp; issue times must be timezone-aware")
    return value


def _included_comments(snapshot: IssueSnapshot, cutoff: datetime | None) -> list[IssueComment]:
    if cutoff is None:
        return list(snapshot.comments)
    return [
        comment
        for comment in snapshot.comments
        if _require_aware(comment.created_at, "comment created_at") < cutoff
    ]


def _comment_heading(comment: IssueComment) -> str:
    when = comment.created_at.astimezone(UTC).strftime(_HEADING_TIME_FORMAT)
    return f"## Comment by {comment.author_login} on {when}"


def render_issue(snapshot: IssueSnapshot, cutoff: datetime | None) -> str:
    """Title, body and each comment in order, those created at or after ``cutoff`` omitted."""
    if cutoff is not None:
        _require_aware(cutoff, "cutoff")
    parts = [f"# {snapshot.title}", snapshot.body]
    for comment in _included_comments(snapshot, cutoff):
        parts.extend([_comment_heading(comment), comment.body])
    return "\n\n".join(parts) + "\n"


def _edited_after(edited: datetime | None, cutoff: datetime, what: str) -> bool:
    return edited is not None and _require_aware(edited, what) > cutoff


def _edited_after_cutoff(snapshot: IssueSnapshot, cutoff: datetime) -> bool:
    """Whether the title, the body or an included comment changed after ``cutoff``."""
    if any(
        _require_aware(renamed, "title rename time") >= cutoff for renamed in snapshot.title_renamed_at
    ):
        return True
    if _edited_after(snapshot.last_edited_at, cutoff, "issue last_edited_at"):
        return True
    return any(
        _edited_after(comment.last_edited_at, cutoff, "comment last_edited_at")
        for comment in _included_comments(snapshot, cutoff)
    )


def freeze_issue(snapshot: IssueSnapshot, cutoff: datetime | None) -> FrozenIssue | CandidateRejection:
    """The frozen text, or ``issue_edited_after_fix`` when it cannot be reconstructed.

    With no cutoff nothing is filtered and the edited-after check does not apply.
    """
    if cutoff is not None:
        _require_aware(cutoff, "cutoff")
        if _edited_after_cutoff(snapshot, cutoff):
            return CandidateRejection.ISSUE_EDITED_AFTER_FIX
    return FrozenIssue(task_text=render_issue(snapshot, cutoff))
