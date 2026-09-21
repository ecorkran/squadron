"""D8: transport failure and timeout across all five host calls on the
``sq pr create`` path.

Kept separate from ``test_pr_create.py``'s decision table: this is one
assertion shape (exit 1, no effective write) applied across five call
sites, following ``test_review_pr_post_failures.py``'s precedent from 384.

The five call sites are ``identify_operator``, ``branch_exists``,
``default_branch``, the ``ls-remote`` sha read, and ``open_pull_request``.
The first four are reads and precede the model call; ``open_pull_request``
is the only write.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost.github_cli import HOST_COMMAND_TIMEOUT_SECONDS
from squadron.codehost.remotes import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import ProcessTimedOutError
from tests.cli.pr_create_support import (
    CREATE_CALL,
    HostHarness,
    fail,
    failing_call_of,
    gh_fixture,
    local_head_sha,
    script_before,
    script_through,
)

pytestmark = pytest.mark.usefixtures("isolated_cf", "fake_composer")

_FAILURE_SITES = [
    "identify_operator",
    "branch_exists",
    "ls_remote",
    "default_branch",
    "open_pull_request",
]

#: The four `gh` calls carry HOST_COMMAND_TIMEOUT_SECONDS; the one git query
#: (ls-remote) carries GIT_QUERY_TIMEOUT_SECONDS (D2, F007).
_SITE_TIMEOUT: dict[str, float] = {
    "identify_operator": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "branch_exists": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "ls_remote": float(GIT_QUERY_TIMEOUT_SECONDS),
    "default_branch": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "open_pull_request": float(HOST_COMMAND_TIMEOUT_SECONDS),
}


def _expected_writes(site: str) -> int:
    """Only a failure at the create itself leaves a write attempt behind."""
    return 1 if site == "open_pull_request" else 0


def _invoke(cli_runner: CliRunner, repo: Path) -> Result:
    return cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo)])


@pytest.mark.parametrize("site", _FAILURE_SITES)
def test_transport_failure_at_each_site_exits_one_with_no_effective_write(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path, site: str
) -> None:
    prefix = script_before(site, local_sha=local_head_sha(pr_create_repo))
    failure = fail(1, '{"status":"500","message":"boom"}')
    pr_create_host.script = [*prefix, (failing_call_of(site), failure)]

    result = _invoke(cli_runner, pr_create_repo)

    assert result.exit_code == 1, result.output
    # One attempt at most: a failed create is not retried or duplicated.
    assert len(pr_create_host.runner.write_calls()) == _expected_writes(site)


@pytest.mark.parametrize("site", _FAILURE_SITES)
def test_scripted_timeout_at_each_site_exits_one_with_no_effective_write(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path, site: str
) -> None:
    prefix = script_before(site, local_sha=local_head_sha(pr_create_repo))
    failing_call = failing_call_of(site)
    timed_out = ProcessTimedOutError(failing_call, _SITE_TIMEOUT[site])
    pr_create_host.script = [*prefix, (failing_call, timed_out)]

    result = _invoke(cli_runner, pr_create_repo)

    assert result.exit_code == 1, result.output
    assert len(pr_create_host.runner.write_calls()) == _expected_writes(site)


def test_the_four_gh_calls_carry_host_timeout_and_ls_remote_carries_git_query_timeout(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    pr_create_host.script = script_through(
        "open_pull_request", local_sha=local_head_sha(pr_create_repo)
    )

    result = _invoke(cli_runner, pr_create_repo)

    assert result.exit_code == 0, result.output
    calls = pr_create_host.runner.calls
    gh_calls = [call for call in calls if call.argv[0] == "gh"]
    ls_remote_calls = [call for call in calls if call.argv[:2] == ("git", "ls-remote")]

    assert len(gh_calls) == 4
    for call in gh_calls:
        assert call.timeout == HOST_COMMAND_TIMEOUT_SECONDS

    assert ls_remote_calls, "expected the ls-remote call"
    for call in ls_remote_calls:
        assert call.timeout == GIT_QUERY_TIMEOUT_SECONDS


def test_pull_request_creation_rejected_is_reported_and_not_retried(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    prefix = script_before("open_pull_request", local_sha=local_head_sha(pr_create_repo))
    pr_create_host.script = [*prefix, (CREATE_CALL, fail(1, gh_fixture("rest-422.json")))]

    result = _invoke(cli_runner, pr_create_repo)

    assert result.exit_code == 1, result.output
    assert len(pr_create_host.runner.write_calls()) == 1, "a rejected create must not be retried"
