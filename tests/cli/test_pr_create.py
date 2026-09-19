"""Tests for ``sq pr create``.

Two process paths meet here: remote discovery, identity, branch existence,
``ls-remote``, and the create call all go through the adapter's
``host.runner`` (D2, D8) and are scripted against the fake runner, following
``test_pr_show.py``'s injection seam. Commit listing and the review scan are
plain local git queries outside the adapter (``review.git_utils``), so they
run against a real git repository on disk, like ``tests/pr/test_inputs.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result
from typer.testing import CliRunner

from squadron.cli.app import app
from tests.cli.pr_create_support import (
    HEAD_BRANCH,
    HostHarness,
    Script,
    fail,
    git,
    local_head_sha,
    ok,
    script_before,
    script_through,
)

pytestmark = pytest.mark.usefixtures("isolated_cf", "fake_composer")


def _run(cli_runner: CliRunner, host: HostHarness, script: Script, repo: Path, *flags: str) -> Result:
    host.script = script
    return cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo), *flags])


def _dry_run_script(repo: Path) -> Script:
    """Everything a happy path calls except the create itself."""
    return script_through("default_branch", local_sha=local_head_sha(repo))


def _full_script(repo: Path) -> Script:
    return script_through("open_pull_request", local_sha=local_head_sha(repo))


def test_happy_path_makes_exactly_one_write(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    result = _run(cli_runner, pr_create_host, _full_script(pr_create_repo), pr_create_repo)

    assert result.exit_code == 0, result.output
    assert "https://github.com/ecorkran/squadron/pull/99" in result.output
    assert len(pr_create_host.runner.write_calls()) == 1


def test_dry_run_makes_zero_writes_and_prints_body_to_stdout(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    result = _run(
        cli_runner, pr_create_host, _dry_run_script(pr_create_repo), pr_create_repo, "--dry-run"
    )

    assert result.exit_code == 0, result.output
    assert "## What changed" in result.stdout
    assert pr_create_host.runner.write_calls() == []


def test_dry_run_title_and_body_equal_what_the_next_real_run_sends(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    dry_result = _run(
        cli_runner, pr_create_host, _dry_run_script(pr_create_repo), pr_create_repo, "--dry-run"
    )
    assert dry_result.exit_code == 0, dry_result.output
    dry_title, _, dry_body = dry_result.stdout.partition("\n")

    real_result = _run(cli_runner, pr_create_host, _full_script(pr_create_repo), pr_create_repo)
    assert real_result.exit_code == 0, real_result.output

    (write,) = pr_create_host.runner.write_calls()
    assert write.stdin is not None
    sent = json.loads(write.stdin)
    assert sent["title"] == dry_title
    # ``print`` ends the dry-run body with one newline the payload does not carry.
    assert sent["body"] + "\n" == dry_body


def test_base_flag_is_honored(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    git(pr_create_repo, "branch", "release", "main")
    # --base bypasses host confirmation entirely: the default-branch lookup is
    # unscripted, so making it would surface as an unscripted-call failure.
    script = script_through(
        "open_pull_request", local_sha=local_head_sha(pr_create_repo), skip=("default_branch",)
    )

    result = _run(cli_runner, pr_create_host, script, pr_create_repo, "--base", "release")

    assert result.exit_code == 0, result.output
    (write,) = pr_create_host.runner.write_calls()
    assert write.stdin is not None
    assert json.loads(write.stdin)["base"] == "release"


def test_title_flag_overrides(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    result = _run(
        cli_runner,
        pr_create_host,
        _dry_run_script(pr_create_repo),
        pr_create_repo,
        "--dry-run",
        "--title",
        "My Custom Title",
    )

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == "My Custom Title"


def test_detached_head_is_refused_with_no_host_call(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    script = script_through("remote_discovery", local_sha="")[:-1]
    script.append((["git", "rev-parse", "--abbrev-ref", "HEAD"], ok("HEAD\n")))

    result = _run(cli_runner, pr_create_host, script, pr_create_repo)

    assert result.exit_code == 1
    assert "detached" in result.output
    assert all(call.argv[0] == "git" for call in pr_create_host.runner.calls)


def test_identity_refusal_exits_1_with_no_write(
    cli_runner: CliRunner, pr_create_host: HostHarness, pr_create_repo: Path
) -> None:
    script = [
        *script_before("identify_operator", local_sha=""),
        (["gh", "api", "user"], fail(stdout='{"message":"Bad credentials","status":"401"}')),
    ]

    result = _run(cli_runner, pr_create_host, script, pr_create_repo)

    assert result.exit_code == 1
    assert pr_create_host.runner.write_calls() == []


def test_failed_presence_check_exits_1_with_no_write(
    cli_runner: CliRunner,
    pr_create_host: HostHarness,
    pr_create_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _empty_body(*args: object, **kwargs: object) -> str:
        return ""

    monkeypatch.setattr("squadron.cli.commands.pr.compose_body", _empty_body)

    result = _run(cli_runner, pr_create_host, _dry_run_script(pr_create_repo), pr_create_repo)

    assert result.exit_code == 1
    assert pr_create_host.runner.write_calls() == []


@pytest.fixture
def composer_calls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Replace the composer with one that records every prompt it is given."""
    prompts: list[str] = []

    async def _recording_compose(prompt: str, *, model: str | None, profile: str) -> str:
        prompts.append(prompt)
        return "should not happen"

    monkeypatch.setattr("squadron.cli.commands.pr.compose_one_shot", _recording_compose)
    return prompts


def test_precondition_failure_means_composer_never_called(
    cli_runner: CliRunner,
    pr_create_host: HostHarness,
    pr_create_repo: Path,
    composer_calls: list[str],
) -> None:
    local_sha = local_head_sha(pr_create_repo)
    script = [
        *script_before("ls_remote", local_sha=local_sha),
        (["git", "ls-remote", "origin", f"refs/heads/{HEAD_BRANCH}"], fail()),
    ]

    result = _run(cli_runner, pr_create_host, script, pr_create_repo)

    assert result.exit_code == 1
    assert composer_calls == []


def test_base_absent_from_the_local_clone_is_a_rendered_refusal(
    cli_runner: CliRunner,
    pr_create_host: HostHarness,
    pr_create_repo: Path,
    composer_calls: list[str],
) -> None:
    """``--base`` is taken verbatim, so the local range is where a typo surfaces."""
    script = script_through(
        "ls_remote", local_sha=local_head_sha(pr_create_repo), skip=("default_branch",)
    )

    result = _run(cli_runner, pr_create_host, script, pr_create_repo, "--base", "no-such-base")

    assert result.exit_code == 1
    assert isinstance(result.exception, SystemExit), "a refusal, not a traceback"
    assert "no-such-base" in result.output
    assert composer_calls == []
    assert pr_create_host.runner.write_calls() == []


def test_empty_commit_range_is_refused_before_composition(
    cli_runner: CliRunner,
    pr_create_host: HostHarness,
    pr_create_repo: Path,
    composer_calls: list[str],
) -> None:
    """A head pushed at the base's own commit passes every precondition."""
    git(pr_create_repo, "branch", "same-as-head", HEAD_BRANCH)
    script = script_through(
        "ls_remote", local_sha=local_head_sha(pr_create_repo), skip=("default_branch",)
    )

    result = _run(cli_runner, pr_create_host, script, pr_create_repo, "--base", "same-as-head")

    assert result.exit_code == 1
    assert "no commits" in result.output
    assert composer_calls == []
    assert pr_create_host.runner.write_calls() == []
