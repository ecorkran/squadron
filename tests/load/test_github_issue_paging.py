"""Load test: ``GitHubCli.get_issue`` on an issue that fills every allowed page (slice 422).

Required by the load-test tier: ``get_issue`` is a network path that makes up to
``MAX_DISCUSSION_PAGES`` sequential GraphQL calls per issue, and fix-case qualification makes
one such fetch per candidate. The calls here are scripted (no network), so the test pins what
the code controls: the call count, nothing dropped or reordered across pages, and a latency
bound on the parsing and joining of a realistically large comment list.
"""

from __future__ import annotations

import copy
import json
import time

from squadron.codehost.github_cli import MAX_DISCUSSION_PAGES
from tests.codehost.test_github_issue import (
    GH_GRAPHQL,
    LOCATOR,
    fixture_json,
    host_with,
    issue_node,
    ok,
)

COMMENTS_PER_PAGE = 100  # the page size ``github_queries`` asks for
LATENCY_BUDGET_S = 5.0


def _page(first_index: int, *, has_next: bool) -> str:
    payload = copy.deepcopy(fixture_json("issue-never-edited.json"))
    node = issue_node(payload)
    template = node["comments"]["nodes"][0]
    nodes = []
    for index in range(first_index, first_index + COMMENTS_PER_PAGE):
        comment = copy.deepcopy(template)
        comment["body"] = f"comment {index}"
        nodes.append(comment)
    node["comments"]["nodes"] = nodes
    node["comments"]["pageInfo"] = {"hasNextPage": has_next, "endCursor": f"CUR{first_index}"}
    node["timelineItems"]["pageInfo"]["hasNextPage"] = False
    return json.dumps(payload)


def test_an_issue_filling_every_allowed_page_is_fetched_whole_within_budget() -> None:
    pages = [
        _page(page * COMMENTS_PER_PAGE, has_next=page < MAX_DISCUSSION_PAGES - 1)
        for page in range(MAX_DISCUSSION_PAGES)
    ]
    cli, runner = host_with([(GH_GRAPHQL, ok(page)) for page in pages])

    started = time.monotonic()
    snapshot = cli.get_issue(LOCATOR, 304)
    elapsed = time.monotonic() - started

    total = MAX_DISCUSSION_PAGES * COMMENTS_PER_PAGE
    assert len(runner.calls) == MAX_DISCUSSION_PAGES, "one GraphQL call per page, no retries"
    assert [comment.body for comment in snapshot.comments] == [
        f"comment {index}" for index in range(total)
    ]
    assert elapsed < LATENCY_BUDGET_S
