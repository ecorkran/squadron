"""Tests for check_head_pushed (D2) — missing vs. behind, two different fixes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.codehost.errors import HostCommandTimeoutError
from squadron.codehost.models import RepositoryLocator
from squadron.codehost.remotes import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from squadron.pr.preconditions import (
    HeadBranchBehindError,
    HeadBranchMissingError,
    check_head_pushed,
)
from tests.codehost.fake_runner import FakeProcessRunner

LOCATOR = RepositoryLocator(
    host="github.com", owner="ecorkran", repository="squadron", remote_name="origin"
)
HEAD = "385-slice.create-a-pr-with-a-good-message"
LOCAL_SHA = "a" * 40


def _host(runner: FakeProcessRunner, *, branch_exists: bool) -> MagicMock:
    host = MagicMock()
    host.runner = runner
    host.branch_exists.return_value = branch_exists
    return host


def _ls_remote_ok(sha: str) -> ProcessResult:
    return ProcessResult(
        argv=(), returncode=0, stdout=f"{sha}\trefs/heads/{HEAD}\n", stderr=""
    )


def test_branch_absent_refuses_naming_push_dash_u() -> None:
    runner = FakeProcessRunner([])
    host = _host(runner, branch_exists=False)

    with pytest.raises(HeadBranchMissingError) as exc_info:
        check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")

    assert exc_info.value.fix_hint == f"git push -u origin {HEAD}"


def test_branch_present_and_shas_equal_passes() -> None:
    runner = FakeProcessRunner(
        [(["git", "ls-remote"], _ls_remote_ok(LOCAL_SHA))]
    )
    host = _host(runner, branch_exists=True)

    check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")


def test_branch_present_and_shas_differ_refuses_naming_push_and_both_shas() -> None:
    remote_sha = "b" * 40
    runner = FakeProcessRunner(
        [(["git", "ls-remote"], _ls_remote_ok(remote_sha))]
    )
    host = _host(runner, branch_exists=True)

    with pytest.raises(HeadBranchBehindError) as exc_info:
        check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")

    assert exc_info.value.fix_hint == f"git push origin {HEAD}"
    message = str(exc_info.value)
    assert remote_sha in message
    assert LOCAL_SHA in message


def test_ls_remote_returns_no_matching_ref_is_treated_as_mismatch() -> None:
    runner = FakeProcessRunner(
        [(["git", "ls-remote"], ProcessResult(argv=(), returncode=0, stdout="", stderr=""))]
    )
    host = _host(runner, branch_exists=True)

    with pytest.raises(HeadBranchBehindError):
        check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")


def test_ls_remote_timeout_refuses_rather_than_silently_passing() -> None:
    runner = FakeProcessRunner(
        [
            (
                ["git", "ls-remote"],
                ProcessTimedOutError(["git", "ls-remote"], GIT_QUERY_TIMEOUT_SECONDS),
            )
        ]
    )
    host = _host(runner, branch_exists=True)

    with pytest.raises(HostCommandTimeoutError):
        check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")


def test_ls_remote_call_carries_git_query_timeout_not_gh_constant() -> None:
    runner = FakeProcessRunner(
        [(["git", "ls-remote"], _ls_remote_ok(LOCAL_SHA))]
    )
    host = _host(runner, branch_exists=True)

    check_head_pushed(host, LOCATOR, head=HEAD, local_sha=LOCAL_SHA, cwd=".")

    assert runner.calls[0].timeout == GIT_QUERY_TIMEOUT_SECONDS
