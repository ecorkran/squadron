"""``GitHubCli.get_issue``: real captured responses, paging and failure mapping (slice 422 D2).

The fixtures in ``fixtures/gh/issue-*.json`` came off the wire (see the README there);
the paging cases derive their pages from one of them rather than inventing a payload.
"""

from __future__ import annotations

import copy
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from squadron.codehost.errors import (
    HostCommandTimeoutError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    IssueNotFoundError,
    IssueTooLargeError,
    ReferenceIsPullRequestError,
)
from squadron.codehost.github_cli import MAX_DISCUSSION_PAGES, GitHubCli
from squadron.codehost.github_parse import DELETED_AUTHOR_LOGIN
from squadron.codehost.models import RepositoryLocator
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
GH_GRAPHQL = ["gh", "api", "graphql"]
_FIXTURES = Path(__file__).parent / "fixtures" / "gh"
LOCATOR = RepositoryLocator(host=GITHUB, owner="ecorkran", repository="squadron", remote_name="origin")


def fixture_text(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name: str) -> dict[str, Any]:
    return json.loads(fixture_text(name))


def ok(stdout: str) -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def failed(returncode: int, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr=stderr)


def host_with(
    script: list[tuple[list[str], ProcessResult | Exception]],
) -> tuple[GitHubCli, FakeProcessRunner]:
    runner = FakeProcessRunner(script)
    return GitHubCli(runner, frozenset({GITHUB})), runner


def issue_node(payload: dict[str, Any]) -> dict[str, Any]:
    return payload["data"]["repository"]["issueOrPullRequest"]


def paged_copy(
    name: str,
    *,
    comment_slice: slice,
    comments_next: str | None,
    renames_next: str | None = None,
) -> str:
    """A page of a real fixture: only ``comment_slice`` of its comments, with a next cursor."""
    payload = copy.deepcopy(fixture_json(name))
    node = issue_node(payload)
    node["comments"]["nodes"] = node["comments"]["nodes"][comment_slice]
    node["comments"]["pageInfo"] = {
        "hasNextPage": comments_next is not None,
        "endCursor": comments_next,
    }
    node["timelineItems"]["pageInfo"]["hasNextPage"] = renames_next is not None
    if renames_next is not None:
        node["timelineItems"]["pageInfo"]["endCursor"] = renames_next
    return json.dumps(payload)


def test_edited_comment_fixture_maps_to_a_snapshot() -> None:
    cli, _ = host_with([(GH_GRAPHQL, ok(fixture_text("issue-edited-comment.json")))])
    snapshot = cli.get_issue(LOCATOR, 126)

    assert snapshot.number == 126
    assert snapshot.locator == LOCATOR
    assert snapshot.created_at == datetime(2026, 9, 22, 14, 10, 57, tzinfo=UTC)
    assert snapshot.last_edited_at is None
    assert len(snapshot.comments) == 2
    assert snapshot.comments[0].last_edited_at == datetime(2026, 9, 24, 13, 41, 26, tzinfo=UTC)
    assert snapshot.comments[1].last_edited_at is None
    assert snapshot.comments[0].created_at < snapshot.comments[1].created_at
    assert snapshot.title_renamed_at == ()


def test_a_comment_from_a_deleted_account_carries_the_placeholder_login() -> None:
    payload = fixture_json("issue-edited-comment.json")
    issue_node(payload)["comments"]["nodes"][0]["author"] = None
    cli, _ = host_with([(GH_GRAPHQL, ok(json.dumps(payload)))])
    comments = cli.get_issue(LOCATOR, 126).comments
    assert comments[0].author_login == DELETED_AUTHOR_LOGIN
    assert comments[1].author_login not in ("", DELETED_AUTHOR_LOGIN)


def test_never_edited_fixture_has_no_edit_timestamps() -> None:
    cli, _ = host_with([(GH_GRAPHQL, ok(fixture_text("issue-never-edited.json")))])
    snapshot = cli.get_issue(LOCATOR, 304)

    assert snapshot.last_edited_at is None
    assert [comment.last_edited_at for comment in snapshot.comments] == [None, None]
    assert snapshot.title_renamed_at == ()
    assert snapshot.title
    assert snapshot.comments[0].author_login == "ecorkran"


def test_title_rename_fixture_carries_the_rename_time() -> None:
    cli, _ = host_with([(GH_GRAPHQL, ok(fixture_text("issue-title-renamed.json")))])
    snapshot = cli.get_issue(LOCATOR, 257)

    assert snapshot.title_renamed_at == (datetime(2026, 11, 1, 14, 7, 40, tzinfo=UTC),)


def test_a_pull_request_number_raises_reference_is_pull_request() -> None:
    cli, _ = host_with([(GH_GRAPHQL, ok(fixture_text("issue-is-pull-request.json")))])
    with pytest.raises(ReferenceIsPullRequestError, match="ecorkran/squadron#83"):
        cli.get_issue(LOCATOR, 83)


def test_a_nonexistent_number_raises_issue_not_found() -> None:
    # gh exits 1 and writes the GraphQL NOT_FOUND body to stdout.
    cli, _ = host_with([(GH_GRAPHQL, failed(1, stdout=fixture_text("issue-not-found.json")))])
    with pytest.raises(IssueNotFoundError, match="ecorkran/squadron#99999"):
        cli.get_issue(LOCATOR, 99999)


def test_a_null_node_without_errors_is_not_found() -> None:
    body = json.dumps({"data": {"repository": {"issueOrPullRequest": None}}})
    cli, _ = host_with([(GH_GRAPHQL, ok(body))])
    with pytest.raises(IssueNotFoundError):
        cli.get_issue(LOCATOR, 5)


def test_first_call_argv_sends_null_cursors_and_the_hostname() -> None:
    cli, runner = host_with([(GH_GRAPHQL, ok(fixture_text("issue-never-edited.json")))])
    cli.get_issue(LOCATOR, 304)

    argv = runner.calls[0].argv
    assert "commentsCursor=null" in argv
    assert "renamesCursor=null" in argv
    assert "number=304" in argv
    assert argv[-2:] == ("--hostname", GITHUB)


def test_a_multi_page_comment_list_is_joined_in_order() -> None:
    page_one = paged_copy("issue-never-edited.json", comment_slice=slice(0, 1), comments_next="CUR1")
    page_two = paged_copy("issue-never-edited.json", comment_slice=slice(1, 2), comments_next=None)
    cli, runner = host_with([(GH_GRAPHQL, ok(page_one)), (GH_GRAPHQL, ok(page_two))])
    snapshot = cli.get_issue(LOCATOR, 304)

    whole = fixture_json("issue-never-edited.json")
    expected = [node["createdAt"] for node in issue_node(whole)["comments"]["nodes"]]
    assert [comment.created_at.isoformat() for comment in snapshot.comments] == [
        value.replace("Z", "+00:00") for value in expected
    ]
    assert "commentsCursor=CUR1" in runner.calls[1].argv


def test_renames_page_independently_of_comments() -> None:
    page_one = paged_copy(
        "issue-title-renamed.json",
        comment_slice=slice(0, 2),
        comments_next=None,
        renames_next="REN1",
    )
    page_two = paged_copy("issue-title-renamed.json", comment_slice=slice(0, 0), comments_next=None)
    cli, runner = host_with([(GH_GRAPHQL, ok(page_one)), (GH_GRAPHQL, ok(page_two))])
    snapshot = cli.get_issue(LOCATOR, 257)

    # Comments finished on page one: page two's (here empty) comments are not read again.
    assert len(snapshot.comments) == 2
    assert len(snapshot.title_renamed_at) == 2
    assert "renamesCursor=REN1" in runner.calls[1].argv


def test_page_bound_raises_and_never_truncates() -> None:
    endless = paged_copy("issue-never-edited.json", comment_slice=slice(0, 1), comments_next="CUR")
    cli, runner = host_with([(GH_GRAPHQL, ok(endless)) for _ in range(MAX_DISCUSSION_PAGES)])
    with pytest.raises(IssueTooLargeError, match=str(MAX_DISCUSSION_PAGES)):
        cli.get_issue(LOCATOR, 304)
    assert len(runner.calls) == MAX_DISCUSSION_PAGES


def test_timeout_surfaces_unchanged() -> None:
    cli, _ = host_with([(GH_GRAPHQL, ProcessTimedOutError(GH_GRAPHQL, 30.0))])
    with pytest.raises(HostCommandTimeoutError):
        cli.get_issue(LOCATOR, 304)


def test_unauthenticated_surfaces_unchanged() -> None:
    cli, _ = host_with([(GH_GRAPHQL, failed(4, stderr="auth required"))])
    with pytest.raises(HostUnauthenticatedError):
        cli.get_issue(LOCATOR, 304)


def test_a_timestamp_without_a_timezone_is_reported_as_drift() -> None:
    payload = fixture_json("issue-never-edited.json")
    issue_node(payload)["createdAt"] = "2026-11-07T04:17:42"
    cli, _ = host_with([(GH_GRAPHQL, ok(json.dumps(payload)))])
    with pytest.raises(HostResponseMalformedError, match="timezone"):
        cli.get_issue(LOCATOR, 304)


@pytest.mark.parametrize("field", ["title", "body"])
def test_a_missing_title_or_body_is_reported_as_drift(field: str) -> None:
    payload = fixture_json("issue-never-edited.json")
    issue_node(payload)[field] = None
    cli, _ = host_with([(GH_GRAPHQL, ok(json.dumps(payload)))])
    with pytest.raises(HostResponseMalformedError, match=field):
        cli.get_issue(LOCATOR, 304)


def test_a_next_page_without_a_cursor_is_reported_as_drift() -> None:
    page = paged_copy("issue-never-edited.json", comment_slice=slice(0, 1), comments_next="X")
    payload = json.loads(page)
    issue_node(payload)["comments"]["pageInfo"]["endCursor"] = None
    cli, _ = host_with([(GH_GRAPHQL, ok(json.dumps(payload)))])
    with pytest.raises(HostResponseMalformedError, match="endCursor"):
        cli.get_issue(LOCATOR, 304)
