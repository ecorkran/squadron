"""Tests for the fix pipeline's issue reference and frozen-file source (slice 423 D2)."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from typing import NoReturn

import pytest

from squadron.codehost.errors import (
    CodeHostError,
    HostCommandTimeoutError,
    HostUnauthenticatedError,
    IssueNotFoundError,
    NoHostRemoteError,
    ReferenceIsPullRequestError,
)
from squadron.codehost.issue_text import render_issue
from squadron.pipeline.fix_issue import (
    IssueTextError,
    IssueTextLoader,
    parse_issue_ref,
)
from squadron.pipeline.fix_keys import IssueSource
from tests.pipeline.fix_fetch_helpers import (
    LOCATOR,
    FakeHost,
    add_github_remote,
    loader_for,
    snapshot,
)


def _factory_that_must_not_run() -> NoReturn:
    raise AssertionError("the code host factory was called")


def _loader() -> IssueTextLoader:
    return IssueTextLoader(_factory_that_must_not_run)


@pytest.mark.parametrize(
    ("value", "expected"), [("301", 301), ("#301", 301), (" #7 ", 7), ("0012", 12)]
)
def test_parse_issue_ref_accepts(value: str, expected: int) -> None:
    assert parse_issue_ref(value) == expected


@pytest.mark.parametrize("value", ["", "0", "-3", "abc", "1.5", "#", "12x", "# 4", "##4", "٣", "²"])
def test_parse_issue_ref_rejects_naming_the_value(value: str) -> None:
    with pytest.raises(ValueError, match="positive integer") as info:
        parse_issue_ref(value)
    assert repr(value) in str(info.value)


def test_file_is_read_verbatim_with_sha256(tmp_path: Path) -> None:
    content = "Titre — résumé\n\nbody with trailing newline\n"
    (tmp_path / "issue.md").write_bytes(content.encode("utf-8"))
    loaded = _loader().load(5, "issue.md", tmp_path, str(tmp_path))
    assert loaded.text == content
    assert loaded.source is IssueSource.FILE
    assert loaded.sha256 == hashlib.sha256(content.encode("utf-8")).hexdigest()


def test_relative_path_resolves_under_the_cwd_argument_without_io_dir(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    checkout = tmp_path / "checkout"
    elsewhere = tmp_path / "elsewhere"
    checkout.mkdir()
    elsewhere.mkdir()
    (checkout / "issue.md").write_text("from the checkout", encoding="utf-8")
    (elsewhere / "issue.md").write_text("from the process cwd", encoding="utf-8")
    monkeypatch.chdir(elsewhere)  # the process cwd is not the checkout
    assert _loader().load(5, "issue.md", None, str(checkout)).text == "from the checkout"


def test_io_dir_wins_over_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    cwd = tmp_path / "cwd"
    io_dir = tmp_path / "io"
    cwd.mkdir()
    io_dir.mkdir()
    (cwd / "issue.md").write_text("from cwd", encoding="utf-8")
    (io_dir / "issue.md").write_text("from io-dir", encoding="utf-8")
    monkeypatch.chdir(cwd)
    assert _loader().load(5, "issue.md", io_dir, str(tmp_path)).text == "from io-dir"


def test_parent_path_is_refused(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "issue.md").write_text("text", encoding="utf-8")
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError, match=r"\.\."):
        _loader().load(5, "../issue.md", tmp_path / "sub", str(tmp_path))
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def _make_directory(root: Path) -> None:
    (root / "issue.md").mkdir()


def _make_empty(root: Path) -> None:
    (root / "issue.md").write_text("", encoding="utf-8")


def _make_whitespace(root: Path) -> None:
    (root / "issue.md").write_text(" \n\t\n", encoding="utf-8")


def _make_nothing(root: Path) -> None:
    del root


@pytest.mark.parametrize(
    ("prepare", "fragment"),
    [
        (_make_nothing, "does not exist"),
        (_make_directory, "not a regular file"),
        (_make_empty, "is empty"),
        (_make_whitespace, "is empty"),
    ],
)
def test_checked_refusals_raise_and_log_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, prepare: Callable[[Path], None], fragment: str
) -> None:
    prepare(tmp_path)
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError, match=fragment) as info:
        _loader().load(5, "issue.md", tmp_path, str(tmp_path))
    assert str(tmp_path / "issue.md") in str(info.value)
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_non_utf8_raises_with_an_error_record(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    (tmp_path / "issue.md").write_bytes(b"\xff\xfe\x00bad")
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError) as info:
        _loader().load(5, "issue.md", tmp_path, str(tmp_path))
    assert isinstance(info.value.__cause__, UnicodeDecodeError)
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    assert caplog.records[0].exc_info is not None


def test_unreadable_file_raises_with_an_error_record(
    tmp_path: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "issue.md").write_text("text", encoding="utf-8")

    def deny(self: Path) -> bytes:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "read_bytes", deny)
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError, match="denied") as info:
        _loader().load(5, "issue.md", tmp_path, str(tmp_path))
    assert isinstance(info.value.__cause__, PermissionError)
    assert [r.levelno for r in caplog.records] == [logging.ERROR]


# --- fetched source (slice 423 D2, D3) ---


@pytest.fixture
def github_repo(temp_git_repo: Path) -> Path:
    add_github_remote(temp_git_repo)
    return temp_git_repo


def test_fetch_renders_title_body_and_every_comment_without_a_cutoff(github_repo: Path) -> None:
    host = FakeHost()

    loaded = loader_for(host).load(301, "", None, str(github_repo))

    assert loaded.text == render_issue(snapshot(), None)
    assert "early" in loaded.text
    assert "late" in loaded.text
    assert loaded.source is IssueSource.GITHUB
    assert loaded.sha256 == hashlib.sha256(loaded.text.encode("utf-8")).hexdigest()
    assert host.fetched == [(LOCATOR, 301)]


@pytest.mark.parametrize(
    "error",
    [
        HostCommandTimeoutError(["gh", "api"], 30.0, fix_hint="check your network"),
        IssueNotFoundError("issue 301 not found in o/r"),
        ReferenceIsPullRequestError("301 is a pull request"),
        HostUnauthenticatedError("gh is not logged in"),
    ],
    ids=lambda error: type(error).__name__,
)
def test_host_errors_become_refusals_with_the_hosts_message(
    github_repo: Path, caplog: pytest.LogCaptureFixture, error: CodeHostError
) -> None:
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError) as info:
        loader_for(FakeHost(error)).load(301, "", None, str(github_repo))

    assert str(error) in str(info.value)
    if error.fix_hint:
        assert error.fix_hint in str(info.value)
    assert info.value.__cause__ is error
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
    assert caplog.records[0].exc_info is not None


def test_a_repository_with_no_served_remote_is_a_refusal(
    temp_git_repo: Path, caplog: pytest.LogCaptureFixture
) -> None:
    host = FakeHost()
    with caplog.at_level(logging.WARNING), pytest.raises(IssueTextError) as info:
        loader_for(host).load(301, "", None, str(temp_git_repo))  # no remotes at all

    assert isinstance(info.value.__cause__, NoHostRemoteError)
    assert host.fetched == []
    # The selection's hints name forms `fix` rejects; its message is kept, they are not.
    assert "no remote belongs to a supported host" in str(info.value)
    assert "owner/repo" not in str(info.value)
    assert "by URL" not in str(info.value)
    assert [record.levelno for record in caplog.records] == [logging.ERROR]
