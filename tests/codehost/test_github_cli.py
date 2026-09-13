"""Tests for the GitHub adapter: argv pinning, reads, and failure classification.

The argv assertions are the contract 384 and 385 build on, and the only defense
against the ``HostUnreachableError`` residual bucket quietly absorbing a
squadron-side argv bug. Host-dependent cases run over ``github.com`` and an
enterprise hostname: no live GHE is available, so this parametrization is the
whole of the Enterprise evidence.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest

from squadron.codehost.errors import (
    AmbiguousBranchPullRequestsError,
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostRequestRejectedError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    HostUnreachableError,
    NoOpenPullRequestForBranchError,
    OperatorUnidentifiedError,
)
from squadron.codehost.github_cli import (
    HOST_COMMAND_TIMEOUT_SECONDS,
    MAX_DISCUSSION_PAGES,
    GitHubCli,
)
from squadron.codehost.models import (
    PullRequestRecord,
    PullRequestState,
    RepositoryLocator,
)
from squadron.codehost.targets import parse_target
from squadron.core.process_runner import (
    ProcessNotFoundError,
    ProcessResult,
    ProcessTimedOutError,
)
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
ENTERPRISE = "ghe.corp.example"
HOSTS = frozenset({GITHUB, ENTERPRISE})

_FIXTURES = Path(__file__).parent / "fixtures" / "gh"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str) -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int, stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr=stderr)


def _locator(host: str = GITHUB) -> RepositoryLocator:
    return RepositoryLocator(host=host, owner="ecorkran", repository="squadron", remote_name="origin")


def _record(host: str = GITHUB) -> PullRequestRecord:
    return PullRequestRecord(
        host=host,
        owner="ecorkran",
        repository="squadron",
        number=83,
        base_ref="main",
        head_ref="feat",
        head_sha="b67cf55",
        url=f"https://{host}/ecorkran/squadron/pull/83",
    )


def _host(
    script: list[tuple[list[str], ProcessResult | Exception]],
) -> tuple[GitHubCli, FakeProcessRunner]:
    runner = FakeProcessRunner(script)
    return GitHubCli(runner, HOSTS), runner


# --- Every gh call carries --hostname and the three env vars ---------------


@pytest.mark.parametrize("host", [GITHUB, ENTERPRISE])
def test_every_gh_argv_carries_hostname_and_env(host: str) -> None:
    cli, runner = _host([(["gh", "api"], _ok(_fixture("repo.json")))])
    cli.default_branch(_locator(host))

    call = runner.calls[0]
    assert call.argv[0] == "gh"
    assert "--hostname" in call.argv
    assert call.argv[call.argv.index("--hostname") + 1] == host
    assert call.env is not None
    assert call.env["GH_PROMPT_DISABLED"] == "1"
    assert call.env["GH_NO_UPDATE_NOTIFIER"] == "1"
    assert call.env["NO_COLOR"] == "1"
    assert call.timeout == HOST_COMMAND_TIMEOUT_SECONDS


# --- Read operations, argv pinned -----------------------------------------


@pytest.mark.parametrize("host", [GITHUB, ENTERPRISE])
def test_default_branch_argv_and_value(host: str) -> None:
    cli, runner = _host([(["gh", "api"], _ok(_fixture("repo.json")))])
    assert cli.default_branch(_locator(host)) == "main"
    assert runner.calls[0].argv == (
        "gh",
        "api",
        "repos/ecorkran/squadron",
        "--hostname",
        host,
    )


@pytest.mark.parametrize("host", [GITHUB, ENTERPRISE])
def test_resolve_by_number_argv_and_record(host: str) -> None:
    cli, runner = _host([(["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json")))])
    resolved = cli.resolve_pull_request(_locator(host), parse_target("83"))

    assert resolved.record.number == 83
    assert resolved.record.host == host
    assert resolved.state is PullRequestState.MERGED
    assert resolved.is_cross_repository is True
    assert resolved.base_sha == "4edf5f1709489da9494906b2178e27dea6a9ae10"
    assert resolved.linked_issue_numbers == (82,)

    argv = runner.calls[0].argv
    assert argv[:3] == ("gh", "api", "graphql")
    assert "-F" in argv and "number=83" in argv
    assert argv[-2:] == ("--hostname", host)


def test_identify_operator_argv_and_login() -> None:
    cli, runner = _host([(["gh", "api"], _ok(_fixture("user.json")))])
    identity = cli.identify_operator(GITHUB)
    assert identity.login == "ecorkran"
    assert identity.host == GITHUB
    assert runner.calls[0].argv == ("gh", "api", "user", "--hostname", GITHUB)


def test_identify_operator_without_login_raises() -> None:
    cli, _ = _host([(["gh", "api"], _ok(json.dumps({"name": "nobody"})))])
    with pytest.raises(OperatorUnidentifiedError):
        cli.identify_operator(GITHUB)


# --- branch_exists: a missing branch is an answer --------------------------


def test_branch_exists_true_on_success() -> None:
    cli, runner = _host([(["gh", "api"], _ok(json.dumps({"name": "main"})))])
    assert cli.branch_exists(_locator(), "main") is True
    assert runner.calls[0].argv[2] == "repos/ecorkran/squadron/branches/main"


def test_branch_exists_false_on_404_and_does_not_raise() -> None:
    cli, _ = _host([(["gh", "api"], _fail(1, stdout=_fixture("branch-404.json")))])
    assert cli.branch_exists(_locator(), "no-such-branch") is False


def test_branch_exists_raises_on_500() -> None:
    body = json.dumps({"message": "server error", "status": "500"})
    cli, _ = _host([(["gh", "api"], _fail(1, stdout=body))])
    with pytest.raises(HostRequestRejectedError) as excinfo:
        cli.branch_exists(_locator(), "main")
    assert excinfo.value.status == 500


# --- Branch resolution: zero, one, two -------------------------------------


def _branch_payload(numbers: list[int]) -> str:
    return json.dumps(
        {"data": {"repository": {"pullRequests": {"nodes": [{"number": n} for n in numbers]}}}}
    )


def test_branch_with_no_open_pr_raises() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _ok(_branch_payload([])))])
    with pytest.raises(NoOpenPullRequestForBranchError):
        cli.resolve_pull_request(_locator(), parse_target("some-branch"))


def test_branch_with_two_open_prs_is_ambiguous_and_names_them() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _ok(_branch_payload([7, 9])))])
    with pytest.raises(AmbiguousBranchPullRequestsError) as excinfo:
        cli.resolve_pull_request(_locator(), parse_target("some-branch"))
    message = str(excinfo.value)
    assert "7" in message and "9" in message


def test_branch_with_one_open_pr_resolves_through_to_the_record() -> None:
    cli, runner = _host(
        [
            (["gh", "api", "graphql"], _ok(_branch_payload([83]))),
            (["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json"))),
        ]
    )
    resolved = cli.resolve_pull_request(_locator(), parse_target("some-branch"))
    assert resolved.record.number == 83
    assert len(runner.calls) == 2


# --- Classification: structural signals only -------------------------------


def test_exit_four_is_unauthenticated_with_login_hint() -> None:
    cli, _ = _host([(["gh", "api"], _fail(4, stderr="auth required"))])
    with pytest.raises(HostUnauthenticatedError) as excinfo:
        cli.default_branch(_locator())
    assert excinfo.value.fix_hint is not None
    assert "gh auth login" in excinfo.value.fix_hint


def test_rest_401_is_unauthenticated() -> None:
    body = json.dumps({"message": "Bad credentials", "status": "401"})
    cli, _ = _host([(["gh", "api"], _fail(1, stdout=body))])
    with pytest.raises(HostUnauthenticatedError):
        cli.default_branch(_locator())


def test_rest_404_is_rejected_with_status() -> None:
    cli, _ = _host([(["gh", "api"], _fail(1, stdout=_fixture("branch-404.json")))])
    with pytest.raises(HostRequestRejectedError) as excinfo:
        cli.default_branch(_locator())
    assert excinfo.value.status == 404


def test_rest_422_is_rejected_with_status() -> None:
    cli, _ = _host([(["gh", "api"], _fail(1, stdout=_fixture("rest-422.json")))])
    with pytest.raises(HostRequestRejectedError) as excinfo:
        cli.default_branch(_locator())
    assert excinfo.value.status == 422


def test_graphql_not_found_is_rejected_as_404() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _fail(1, stdout=_fixture("graphql-notfound.json")))])
    with pytest.raises(HostRequestRejectedError) as excinfo:
        cli.resolve_pull_request(_locator(), parse_target("83"))
    assert excinfo.value.status == 404


def test_graphql_other_error_type_is_rejected() -> None:
    body = json.dumps({"errors": [{"type": "RATE_LIMITED", "message": "slow down"}]})
    cli, _ = _host([(["gh", "api", "graphql"], _fail(1, stdout=body))])
    with pytest.raises(HostRequestRejectedError):
        cli.resolve_pull_request(_locator(), parse_target("83"))


def test_no_json_no_http_is_unreachable_carrying_stderr_verbatim() -> None:
    """The residual bucket. The verbatim stderr is what names the real cause."""
    cli, _ = _host([(["gh", "api"], _fail(1, stdout="not json at all", stderr="dial tcp: no route"))])
    with pytest.raises(HostUnreachableError) as excinfo:
        cli.default_branch(_locator())
    assert "dial tcp: no route" in str(excinfo.value)


def test_missing_gh_becomes_cli_missing_error() -> None:
    cli, _ = _host([(["gh", "api"], ProcessNotFoundError("gh"))])
    with pytest.raises(GitHubCliMissingError) as excinfo:
        cli.default_branch(_locator())
    assert excinfo.value.fix_hint is not None


def test_timeout_becomes_host_timeout_naming_the_bound() -> None:
    cli, _ = _host([(["gh", "api"], ProcessTimedOutError(["gh", "api"], 30.0))])
    with pytest.raises(HostCommandTimeoutError) as excinfo:
        cli.default_branch(_locator())
    assert excinfo.value.seconds == 30.0


def test_malformed_json_on_success_is_reported_as_drift() -> None:
    cli, _ = _host([(["gh", "api"], _ok("{not json"))])
    with pytest.raises(HostResponseMalformedError):
        cli.default_branch(_locator())


def test_missing_required_field_is_reported_as_drift() -> None:
    cli, _ = _host([(["gh", "api"], _ok(json.dumps({"name": "squadron"})))])
    with pytest.raises(HostResponseMalformedError) as excinfo:
        cli.default_branch(_locator())
    assert "default_branch" in str(excinfo.value)


# --- Discussion paging -----------------------------------------------------


def _threads_page(*, resolved: bool = False, has_next: bool = False, cursor: str = "c1") -> str:
    return json.dumps(
        {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "pageInfo": {"hasNextPage": has_next, "endCursor": cursor},
                            "nodes": [
                                {
                                    "isResolved": resolved,
                                    "comments": {
                                        "nodes": [
                                            {
                                                "path": "src/x.py",
                                                "line": 12,
                                                "author": {"login": "someone"},
                                                "body": "a comment",
                                                "url": "https://example/1",
                                            }
                                        ]
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        }
    )


def test_discussions_single_page() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _ok(_threads_page()))])
    discussions = cli.list_unresolved_discussions(_record())
    assert len(discussions) == 1
    assert discussions[0].path == "src/x.py"
    assert discussions[0].line == 12


def test_resolved_threads_are_excluded() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _ok(_threads_page(resolved=True)))])
    assert cli.list_unresolved_discussions(_record()) == []


def test_empty_page_from_the_real_fixture() -> None:
    cli, _ = _host([(["gh", "api", "graphql"], _ok(_fixture("pr83-reviewthreads.json")))])
    assert cli.list_unresolved_discussions(_record()) == []


def test_paging_stops_at_the_cap_and_warns_with_the_count(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A silently truncated list is a review that quietly misses comments."""
    script: list[tuple[list[str], Any]] = [
        (["gh", "api", "graphql"], _ok(_threads_page(has_next=True)))
        for _ in range(MAX_DISCUSSION_PAGES)
    ]
    cli, runner = _host(script)
    with caplog.at_level(logging.WARNING, logger="squadron.codehost.github_cli"):
        discussions = cli.list_unresolved_discussions(_record())

    assert len(runner.calls) == MAX_DISCUSSION_PAGES
    assert len(discussions) == MAX_DISCUSSION_PAGES
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "hitting the page cap must be observable"
    assert str(MAX_DISCUSSION_PAGES) in warnings[0].getMessage()
