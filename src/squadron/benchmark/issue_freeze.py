"""Frozen issue text for a case (slice 422 D2).

``render_issue`` turns an ``IssueSnapshot`` into the markdown a producer is given as its
task. With a cutoff (a fix commit's committer date) it keeps only what existed before
the cutoff; ``freeze_issue`` additionally refuses an issue whose title, body or kept
comments were edited after the cutoff, because the text as it stood then cannot be
recovered and today's version may describe the fix.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from squadron.codehost.issue_text import included_comments, render_issue, require_aware
from squadron.codehost.models import IssueSnapshot
from squadron.metrology.benchmark_models import CandidateRejection


@dataclass(frozen=True)
class FrozenIssue:
    task_text: str


def _edited_at_or_after(edited: datetime | None, cutoff: datetime, what: str) -> bool:
    """The same boundary as comment omission: a change at the cutoff instant is too late."""
    return edited is not None and require_aware(edited, what) >= cutoff


def _edited_after_cutoff(snapshot: IssueSnapshot, cutoff: datetime) -> bool:
    """Whether the title, the body or an included comment changed at or after ``cutoff``."""
    if any(
        _edited_at_or_after(renamed, cutoff, "title rename time")
        for renamed in snapshot.title_renamed_at
    ):
        return True
    if _edited_at_or_after(snapshot.last_edited_at, cutoff, "issue last_edited_at"):
        return True
    return any(
        _edited_at_or_after(comment.last_edited_at, cutoff, "comment last_edited_at")
        for comment in included_comments(snapshot, cutoff)
    )


def freeze_issue(snapshot: IssueSnapshot, cutoff: datetime | None) -> FrozenIssue | CandidateRejection:
    """The frozen text, or ``issue_edited_after_fix`` when it cannot be reconstructed.

    With no cutoff nothing is filtered and the edited-after check does not apply.
    """
    if cutoff is not None:
        require_aware(cutoff, "cutoff")
        if _edited_after_cutoff(snapshot, cutoff):
            return CandidateRejection.ISSUE_EDITED_AFTER_FIX
    return FrozenIssue(task_text=render_issue(snapshot, cutoff))
