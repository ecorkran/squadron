"""Frozen issue text and the edited-after-fix rejection (slice 422 D2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from squadron.benchmark.issue_freeze import FrozenIssue, freeze_issue, render_issue
from squadron.codehost.models import IssueComment, IssueSnapshot, RepositoryLocator
from squadron.metrology.benchmark_models import CandidateRejection

LOCATOR = RepositoryLocator(host="github.com", owner="o", repository="r", remote_name="origin")
CUTOFF = datetime(2026, 10, 10, 12, 0, tzinfo=UTC)
BEFORE = CUTOFF - timedelta(days=1)
AFTER = CUTOFF + timedelta(days=1)


def comment(
    created: datetime, body: str = "a comment", edited: datetime | None = None, author: str = "ann"
) -> IssueComment:
    return IssueComment(author_login=author, body=body, created_at=created, last_edited_at=edited)


def snapshot(
    comments: tuple[IssueComment, ...] = (),
    *,
    edited: datetime | None = None,
    renamed: tuple[datetime, ...] = (),
) -> IssueSnapshot:
    return IssueSnapshot(
        locator=LOCATOR,
        number=7,
        title="Crash on empty input",
        body="It crashes.",
        created_at=BEFORE - timedelta(days=5),
        last_edited_at=edited,
        comments=comments,
        title_renamed_at=renamed,
    )


def frozen_text(issue: IssueSnapshot, cutoff: datetime | None = CUTOFF) -> str:
    result = freeze_issue(issue, cutoff)
    assert isinstance(result, FrozenIssue)
    return result.task_text


def test_heading_and_layout_are_pinned() -> None:
    issue = snapshot(
        (
            comment(datetime(2026, 10, 8, 9, 30, tzinfo=UTC), "first", author="ann"),
            comment(datetime(2026, 10, 9, 18, 5, tzinfo=UTC), "second", author="bob"),
        )
    )
    assert render_issue(issue, CUTOFF) == (
        "# Crash on empty input\n\n"
        "It crashes.\n\n"
        "## Comment by ann on 2026-10-08 09:30 UTC\n\n"
        "first\n\n"
        "## Comment by bob on 2026-10-09 18:05 UTC\n\n"
        "second\n"
    )


def test_a_late_comment_does_not_change_the_rendered_text() -> None:
    early = comment(BEFORE, "early")
    without = snapshot((early,))
    with_late = snapshot((early, comment(AFTER, "late")))
    assert frozen_text(with_late) == frozen_text(without)
    assert "late" not in frozen_text(with_late)


def test_a_comment_created_exactly_at_the_cutoff_is_omitted() -> None:
    assert "at the cutoff" not in frozen_text(snapshot((comment(CUTOFF, "at the cutoff"),)))


def test_a_late_comments_edit_does_not_reject() -> None:
    late_edited = comment(AFTER, "late", edited=AFTER + timedelta(hours=1))
    assert isinstance(freeze_issue(snapshot((late_edited,)), CUTOFF), FrozenIssue)


def test_an_edited_body_rejects() -> None:
    assert freeze_issue(snapshot(edited=AFTER), CUTOFF) is CandidateRejection.ISSUE_EDITED_AFTER_FIX


def test_a_body_edited_before_the_cutoff_is_fine() -> None:
    assert isinstance(freeze_issue(snapshot(edited=BEFORE), CUTOFF), FrozenIssue)


def test_an_included_comment_edited_after_the_cutoff_rejects() -> None:
    edited_later = comment(BEFORE, "early", edited=AFTER)
    assert freeze_issue(snapshot((edited_later,)), CUTOFF) is CandidateRejection.ISSUE_EDITED_AFTER_FIX


def test_a_title_rename_after_the_cutoff_rejects_and_one_before_does_not() -> None:
    assert freeze_issue(snapshot(renamed=(AFTER,)), CUTOFF) is CandidateRejection.ISSUE_EDITED_AFTER_FIX
    assert (
        freeze_issue(snapshot(renamed=(CUTOFF,)), CUTOFF) is CandidateRejection.ISSUE_EDITED_AFTER_FIX
    )
    assert isinstance(freeze_issue(snapshot(renamed=(BEFORE,)), CUTOFF), FrozenIssue)


@pytest.mark.parametrize(
    "at_cutoff",
    [
        snapshot(edited=CUTOFF),
        snapshot((comment(BEFORE, edited=CUTOFF),)),
        snapshot(renamed=(CUTOFF,)),
    ],
    ids=["body", "comment", "title"],
)
def test_a_change_exactly_at_the_cutoff_rejects_for_every_kind(at_cutoff: IssueSnapshot) -> None:
    assert freeze_issue(at_cutoff, CUTOFF) is CandidateRejection.ISSUE_EDITED_AFTER_FIX


def test_no_cutoff_renders_every_comment_and_never_rejects() -> None:
    issue = snapshot(
        (comment(BEFORE, "early", edited=AFTER), comment(AFTER, "late")),
        edited=AFTER,
        renamed=(AFTER,),
    )
    text = frozen_text(issue, None)
    assert "early" in text
    assert "late" in text


@pytest.mark.parametrize(
    "issue",
    [
        snapshot((comment(datetime(2026, 10, 1)),)),
        snapshot(edited=datetime(2026, 10, 11)),
        snapshot(renamed=(datetime(2026, 10, 11),)),
    ],
    ids=["comment created", "body edited", "title renamed"],
)
def test_a_naive_snapshot_timestamp_raises(issue: IssueSnapshot) -> None:
    with pytest.raises(ValueError, match="naive"):
        freeze_issue(issue, CUTOFF)


def test_a_naive_cutoff_raises() -> None:
    with pytest.raises(ValueError, match="cutoff"):
        freeze_issue(snapshot(), datetime(2026, 10, 10))
    with pytest.raises(ValueError, match="cutoff"):
        render_issue(snapshot(), datetime(2026, 10, 10))
