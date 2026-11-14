"""A fake code host and issue snapshot for the fix pipeline's fetched-issue tests (slice 423)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from squadron.codehost.models import IssueComment, IssueSnapshot, RepositoryLocator
from squadron.codehost.protocol import CodeHost
from squadron.core.process_runner import SubprocessRunner
from squadron.pipeline.fix_issue import IssueTextLoader
from tests.conftest import run_test_git

LOCATOR = RepositoryLocator(host="github.com", owner="o", repository="r", remote_name="origin")


def snapshot() -> IssueSnapshot:
    return IssueSnapshot(
        locator=LOCATOR,
        number=301,
        title="Parser drops the last row",
        body="It drops it.",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        last_edited_at=datetime(2026, 3, 1, tzinfo=UTC),  # edited later; no cutoff applies
        comments=(
            IssueComment(
                author_login="ann",
                body="early",
                created_at=datetime(2026, 1, 2, tzinfo=UTC),
                last_edited_at=None,
            ),
            IssueComment(
                author_login="bob",
                body="late",
                created_at=datetime(2030, 1, 2, tzinfo=UTC),
                last_edited_at=None,
            ),
        ),
        title_renamed_at=(),
    )


class FakeHost:
    """The three CodeHost members the loader uses; ``get_issue`` raises ``error`` when set."""

    def __init__(self, error: Exception | None = None) -> None:
        self.runner = SubprocessRunner()
        self.error = error
        self.fetched: list[tuple[RepositoryLocator, int]] = []

    def serves_host(self, hostname: str) -> bool:
        return hostname == "github.com"

    def get_issue(self, locator: RepositoryLocator, number: int) -> IssueSnapshot:
        self.fetched.append((locator, number))
        if self.error is not None:
            raise self.error
        return snapshot()


def loader_for(host: FakeHost) -> IssueTextLoader:
    return IssueTextLoader(lambda: cast(CodeHost, host))


def add_github_remote(repo: Path) -> None:
    """Give ``repo`` the origin remote ``LOCATOR`` names, so a bare ``#n`` resolves to it."""
    run_test_git(repo, "remote", "add", LOCATOR.remote_name, "https://github.com/o/r.git")
