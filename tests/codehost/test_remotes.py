"""Tests for remote enumeration and target-to-remote selection.

Selection runs against the fake process runner, so no git repository is
required and every argv the implementation issues is asserted rather than
assumed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

import pytest

from squadron.codehost.errors import (
    AmbiguousHostRemoteError,
    ForeignRepositoryError,
    NoHostRemoteError,
)
from squadron.codehost.models import LocalRemote
from squadron.codehost.remotes import list_remotes, parse_remote_url, select_remote
from squadron.codehost.targets import parse_target
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
ENTERPRISE = "ghe.corp.example"


def _result(argv: list[str], stdout: str) -> ProcessResult:
    return ProcessResult(argv=tuple(argv), returncode=0, stdout=stdout, stderr="")


def _serves(*hosts: str) -> Callable[[str], bool]:
    """A ``serves_host`` callable accepting exactly the named hosts."""
    allowed = set(hosts)

    def _predicate(hostname: str) -> bool:
        return hostname in allowed

    return _predicate


def _remote(name: str, host: str | None, owner: str | None, repository: str | None) -> LocalRemote:
    url = f"https://{host}/{owner}/{repository}.git" if host else "weird::url"
    return LocalRemote(name=name, host=host, owner=owner, repository=repository, url=url)


# --- URL parsing -----------------------------------------------------------


@pytest.mark.parametrize("host", [GITHUB, ENTERPRISE])
@pytest.mark.parametrize("suffix", ["", ".git"])
@pytest.mark.parametrize(
    "template",
    [
        "https://{host}/{owner}/{repo}{suffix}",
        "ssh://git@{host}/{owner}/{repo}{suffix}",
        "git@{host}:{owner}/{repo}{suffix}",
    ],
)
def test_parses_all_three_url_shapes(host: str, suffix: str, template: str) -> None:
    url = template.format(host=host, owner="ecorkran", repo="squadron", suffix=suffix)
    remote = parse_remote_url("origin", url)
    assert remote.host == host
    assert remote.owner == "ecorkran"
    assert remote.repository == "squadron"


def test_unparseable_url_yields_host_none_but_is_retained() -> None:
    remote = parse_remote_url("weird", "some-local-thing")
    assert remote.host is None
    assert remote.owner is None
    assert remote.repository is None
    assert remote.url == "some-local-thing"


# --- Enumeration -----------------------------------------------------------


def test_list_remotes_preserves_git_order_and_bounds_every_call() -> None:
    runner = FakeProcessRunner(
        [
            (["git", "remote"], _result(["git", "remote"], "origin\nupstream\n")),
            (
                ["git", "remote", "get-url", "origin"],
                _result([], f"https://{GITHUB}/ecorkran/squadron.git\n"),
            ),
            (
                ["git", "remote", "get-url", "upstream"],
                _result([], f"https://{GITHUB}/upstream-org/squadron.git\n"),
            ),
        ]
    )
    remotes = list_remotes(runner, cwd="/repo")
    assert [r.name for r in remotes] == ["origin", "upstream"]
    assert [r.owner for r in remotes] == ["ecorkran", "upstream-org"]
    assert all(call.timeout > 0 for call in runner.calls)


# --- Selection: explicit forms --------------------------------------------


def test_explicit_form_matches_owner_and_repository_case_insensitively() -> None:
    remotes = [_remote("origin", GITHUB, "EcorKran", "Squadron")]
    locator = select_remote(parse_target("ecorkran/squadron#7"), remotes, _serves(GITHUB))
    assert locator.remote_name == "origin"


def test_explicit_form_with_no_matching_remote_names_both_sides() -> None:
    remotes = [_remote("origin", GITHUB, "someone", "other-repo")]
    with pytest.raises(ForeignRepositoryError) as excinfo:
        select_remote(parse_target("ecorkran/squadron#7"), remotes, _serves(GITHUB))
    message = str(excinfo.value)
    assert "squadron" in message
    assert "other-repo" in message


def test_two_remotes_for_one_repository_take_git_order_and_log_at_info(
    caplog: pytest.LogCaptureFixture,
) -> None:
    remotes = [
        _remote("origin", GITHUB, "ecorkran", "squadron"),
        _remote("mirror", GITHUB, "ecorkran", "squadron"),
    ]
    with caplog.at_level(logging.INFO, logger="squadron.codehost.remotes"):
        locator = select_remote(parse_target("ecorkran/squadron#7"), remotes, _serves(GITHUB))
    assert locator.remote_name == "origin"
    assert any(record.levelno == logging.INFO for record in caplog.records)


# --- Selection: repository-name form --------------------------------------


def test_repo_number_ignores_owner_and_resolves_on_served_host() -> None:
    remotes = [_remote("origin", GITHUB, "ecorkran", "squadron")]
    locator = select_remote(parse_target("squadron#7"), remotes, _serves(GITHUB))
    assert locator.owner == "ecorkran"


def test_repo_number_under_two_owners_is_ambiguous_and_lists_both() -> None:
    remotes = [
        _remote("origin", GITHUB, "ecorkran", "squadron"),
        _remote("upstream", GITHUB, "other-org", "squadron"),
    ]
    with pytest.raises(AmbiguousHostRemoteError) as excinfo:
        select_remote(parse_target("squadron#7"), remotes, _serves(GITHUB))
    message = str(excinfo.value)
    assert "ecorkran/squadron" in message
    assert "other-org/squadron" in message


def test_repo_number_matching_nothing_raises_foreign_repository() -> None:
    remotes = [_remote("origin", GITHUB, "ecorkran", "squadron")]
    with pytest.raises(ForeignRepositoryError):
        select_remote(parse_target("nonexistent#7"), remotes, _serves(GITHUB))


# --- Selection: bare forms -------------------------------------------------


def test_fork_layout_bare_form_is_ambiguous_and_names_both_remotes() -> None:
    """origin (fork) + upstream (canonical), both on the same host."""
    remotes = [
        _remote("origin", GITHUB, "ecorkran", "squadron"),
        _remote("upstream", GITHUB, "upstream-org", "squadron"),
    ]
    with pytest.raises(AmbiguousHostRemoteError) as excinfo:
        select_remote(parse_target("7"), remotes, _serves(GITHUB))
    message = str(excinfo.value)
    assert "origin" in message
    assert "upstream" in message


def test_fork_layout_explicit_form_still_resolves() -> None:
    remotes = [
        _remote("origin", GITHUB, "ecorkran", "squadron"),
        _remote("upstream", GITHUB, "upstream-org", "squadron"),
    ]
    locator = select_remote(parse_target("upstream-org/squadron#7"), remotes, _serves(GITHUB))
    assert locator.remote_name == "upstream"


def test_github_plus_non_github_mirror_resolves_bare_forms() -> None:
    """The case a naive "exactly one remote" rule gets wrong."""
    remotes = [
        _remote("origin", GITHUB, "ecorkran", "squadron"),
        _remote("gitlab", "gitlab.com", "ecorkran", "squadron"),
    ]
    locator = select_remote(parse_target("7"), remotes, _serves(GITHUB))
    assert locator.remote_name == "origin"


def test_no_remote_on_a_served_host_raises_no_host_remote() -> None:
    remotes = [_remote("gitlab", "gitlab.com", "ecorkran", "squadron")]
    with pytest.raises(NoHostRemoteError):
        select_remote(parse_target("7"), remotes, _serves(GITHUB))


def test_unparseable_remote_is_skipped_but_named_in_the_message() -> None:
    remotes = [
        LocalRemote(name="weird", host=None, owner=None, repository=None, url="some-local-thing")
    ]
    with pytest.raises(NoHostRemoteError) as excinfo:
        select_remote(parse_target("7"), remotes, _serves(GITHUB))
    message = str(excinfo.value)
    assert "weird" in message
    assert "some-local-thing" in message


def test_enterprise_host_resolves_when_served() -> None:
    remotes = [_remote("origin", ENTERPRISE, "acme", "widgets")]
    locator = select_remote(parse_target("7"), remotes, _serves(ENTERPRISE))
    assert locator.host == ENTERPRISE
