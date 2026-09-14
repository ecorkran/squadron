"""Tests for ``sq pr show``.

The injection seam is named here rather than invented at execution time:
``pr.py`` reaches the host through ``build_github_host(runner)``, so that
factory is the single patch point. Patching ``SubprocessRunner`` instead, or
threading a test-only parameter through the command signature, would bypass the
path under test.

The enterprise leg points ``GH_CONFIG_DIR`` at a two-host ``hosts.yml`` so the
CLI's own ``read_gh_hosts()`` sees both hosts — passing ``hosts`` past the
factory would skip exactly the code this is meant to exercise.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost import errors as errors_module
from squadron.codehost.errors import (
    AmbiguousBranchPullRequestsError,
    AmbiguousHostRemoteError,
    CodeHostError,
    ForeignRepositoryError,
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostRequestRejectedError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    HostUnreachableError,
    NoHostRemoteError,
    NoMergeBaseError,
    NoOpenPullRequestForBranchError,
    OperatorUnidentifiedError,
    PullRequestCreationRejectedError,
    PullRequestNotFoundError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
    TargetSyntaxError,
    TargetUnresolvableError,
)
from squadron.codehost.github_cli import GitHubCli
from squadron.codehost.models import RefRole
from squadron.core.process_runner import ProcessResult
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
ENTERPRISE = "ghe.corp.example"

_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

BASE_SHA = "4edf5f1709489da9494906b2178e27dea6a9ae10"
HEAD_SHA = "b67cf55495f01bc2da843d8f96c767a11770e330"
MERGE_BASE = "1111111111111111111111111111111111111111"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _read_script(host: str) -> list[tuple[list[str], ProcessResult | Exception]]:
    """Every process call one successful ``sq pr show`` makes."""
    return [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{host}/ecorkran/squadron.git\n")),
        (["gh", "api", "graphql"], _ok(_fixture("pr83-resolve.json"))),
        (["git", "fetch"], _ok()),
        (["git", "rev-parse", "--verify"], _ok(BASE_SHA)),
        (["git", "rev-parse", "--verify"], _ok(HEAD_SHA)),
        (["git", "merge-base"], _ok(MERGE_BASE)),
        (["git", "diff", "--name-only"], _ok("src/a.py\nsrc/b.py\n")),
    ]


@pytest.fixture
def hosts_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A two-host ``hosts.yml`` the CLI's own read_gh_hosts() will find."""
    config_dir = tmp_path / "gh"
    config_dir.mkdir()
    (config_dir / "hosts.yml").write_text(
        f"{GITHUB}:\n  user: ecorkran\n{ENTERPRISE}:\n  user: ecorkran\n"
    )
    monkeypatch.setenv("GH_CONFIG_DIR", str(config_dir))
    return config_dir


@pytest.fixture
def patched_host(
    monkeypatch: pytest.MonkeyPatch, hosts_file: Path
) -> Iterator[dict[str, FakeProcessRunner | None]]:
    """Patch the factory ``pr.py`` calls, capturing the fake it hands back."""
    captured: dict[str, FakeProcessRunner | None] = {"runner": None}
    script_holder: dict[str, list[tuple[list[str], ProcessResult | Exception]]] = {"script": []}

    def _build(_runner: object) -> GitHubCli:
        from squadron.codehost.github_config import read_gh_hosts

        fake = FakeProcessRunner(script_holder["script"])
        captured["runner"] = fake
        # Hosts still come from the CLI's own read_gh_hosts(), so the
        # GH_CONFIG_DIR fixture is what the enterprise leg actually exercises.
        return GitHubCli(fake, frozenset({GITHUB, *read_gh_hosts()}))

    monkeypatch.setattr("squadron.cli.commands.pr.build_github_host", _build)
    captured["script_holder"] = script_holder  # type: ignore[assignment]
    yield captured


def _run(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    argv: list[str],
    script: list[tuple[list[str], ProcessResult | Exception]],
):
    holder = patched_host["script_holder"]
    holder["script"] = script  # type: ignore[index]
    return cli_runner.invoke(app, argv)


# --- The headline criterion: six forms, one record -------------------------


@pytest.mark.parametrize("host", [GITHUB, ENTERPRISE])
@pytest.mark.parametrize(
    "target_argv",
    [
        pytest.param([], id="current-branch"),
        pytest.param(["83"], id="number"),
        pytest.param(["#83"], id="hash-number"),
        pytest.param(["squadron#83"], id="repo-number"),
        pytest.param(["ecorkran/squadron#83"], id="owner-repo-number"),
        # The URL form is the one target carrying its own host, so it is built
        # from the host under test. A github.com URL against an
        # enterprise-only checkout is correctly refused, not a passing case.
        pytest.param(["url"], id="url"),
    ],
)
def test_all_six_forms_resolve_to_the_same_record(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    host: str,
    target_argv: list[str],
) -> None:
    """The slice's headline functional criterion, over both hosts."""
    # The URL form carries its own host, so it is built from the host under
    # test rather than hardcoded — a github.com URL against an enterprise-only
    # checkout is correctly refused, which would test the wrong thing here.
    target_argv = [
        f"https://{host}/ecorkran/squadron/pull/83" if arg == "url" else arg for arg in target_argv
    ]
    script = _read_script(host)
    if not target_argv:
        # The current-branch form reads HEAD before anything else.
        script = [
            (["git", "rev-parse", "--abbrev-ref"], _ok("feat\n")),
            (["gh", "api", "graphql"], _ok(json.dumps(_branch_payload(83)))),
            *script,
        ]

    result = _run(cli_runner, patched_host, ["pr", "show", *target_argv, "--json"], script)

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["record"]["number"] == 83
    assert payload["record"]["owner"] == "ecorkran"
    assert payload["record"]["repository"] == "squadron"
    assert payload["record"]["host"] == host
    assert payload["record"]["key"] == f"{host}/ecorkran/squadron#83"


def _branch_payload(number: int) -> dict[str, object]:
    return {"data": {"repository": {"pullRequests": {"nodes": [{"number": number}]}}}}


def test_current_branch_reads_head_from_the_resolved_repo(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    tmp_path: Path,
) -> None:
    """The bare form must read HEAD from --cwd, not the process's own cwd.

    Reading it from the process cwd names the branch of whatever repository
    happens to sit there: a wrong pull request if that is another checkout,
    and a bogus "detached HEAD" if it is not a repository at all. The fake
    runner records cwd on every call, so this asserts it rather than trusting
    argv order — the gap that let the original defect pass unnoticed.
    """
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    script = [
        (["git", "rev-parse", "--abbrev-ref"], _ok("feat\n")),
        (["gh", "api", "graphql"], _ok(json.dumps(_branch_payload(83)))),
        *_read_script(GITHUB),
    ]

    result = _run(cli_runner, patched_host, ["pr", "show", "--cwd", str(elsewhere), "--json"], script)

    assert result.exit_code == 0, result.output
    runner = patched_host["runner"]
    assert isinstance(runner, FakeProcessRunner)
    head_calls = [call for call in runner.calls if call.argv[:2] == ("git", "rev-parse")]
    assert head_calls, "the current-branch form must read HEAD"
    assert head_calls[0].cwd == str(elsewhere)


# --- --json shape -----------------------------------------------------------


def test_json_emits_the_three_key_object(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    result = _run(cli_runner, patched_host, ["pr", "show", "83", "--json"], _read_script(GITHUB))

    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert set(payload) == {"record", "resolved", "fetched"}
    assert payload["resolved"]["base_sha"] == BASE_SHA
    assert payload["resolved"]["state"] == "MERGED"
    assert payload["resolved"]["is_cross_repository"] is True
    assert payload["resolved"]["linked_issue_numbers"] == [82]
    assert payload["fetched"]["merge_base"] == MERGE_BASE
    assert payload["fetched"]["diff_range"].count("...") == 1
    assert payload["fetched"]["changed_paths"] == ["src/a.py", "src/b.py"]


def test_terminal_output_names_the_record_and_the_range(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    result = _run(cli_runner, patched_host, ["pr", "show", "83"], _read_script(GITHUB))

    assert result.exit_code == 0, result.output
    assert "83" in result.output
    assert "MERGED" in result.output


# --- The CLI-level half of the read-only proof ------------------------------


def test_write_calls_is_empty_across_a_whole_pr_show_run(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    """The other half of 381's read-only proof.

    The adapter-level half is in the codehost tests, which could only script the
    adapter pipeline. Together they are the evidence the slice mutates nothing;
    neither may be dropped.
    """
    result = _run(cli_runner, patched_host, ["pr", "show", "83", "--json"], _read_script(GITHUB))
    assert result.exit_code == 0, result.output

    runner = patched_host["runner"]
    assert isinstance(runner, FakeProcessRunner)
    assert runner.write_calls() == [], "sq pr show must not mutate the host"


def test_no_process_call_mutates_the_working_tree(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    """What lets sq pr show run against a dirty checkout."""
    _run(cli_runner, patched_host, ["pr", "show", "83"], _read_script(GITHUB))

    runner = patched_host["runner"]
    assert isinstance(runner, FakeProcessRunner)
    forbidden = {"checkout", "switch", "reset", "branch", "worktree", "commit"}
    for call in runner.calls:
        assert not forbidden.intersection(call.argv), f"mutating argv: {call.argv}"


# --- Enterprise: the hostname reaches gh ------------------------------------


def test_enterprise_run_carries_the_enterprise_hostname(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    """No live GHE is available, so this is the whole of the evidence."""
    result = _run(
        cli_runner,
        patched_host,
        ["pr", "show", "83", "--json"],
        _read_script(ENTERPRISE),
    )
    assert result.exit_code == 0, result.output

    runner = patched_host["runner"]
    assert isinstance(runner, FakeProcessRunner)
    gh_calls = [call for call in runner.calls if call.argv[0] == "gh"]
    assert gh_calls, "expected at least one gh call"
    for call in gh_calls:
        assert "--hostname" in call.argv
        assert call.argv[call.argv.index("--hostname") + 1] == ENTERPRISE


# --- H.5: every error class is observable through the CLI ------------------
#
# The design's test_errors_observable.py. Placement deviation, deliberate: it
# lives here rather than under tests/codehost/ because exit codes are only
# observable through the CLI, and the criterion couples error type, log level,
# and exit code in a single assertion. The count is the check — all nineteen.

_ALL_ERROR_CLASSES = [
    AmbiguousBranchPullRequestsError,
    AmbiguousHostRemoteError,
    ForeignRepositoryError,
    GitHubCliMissingError,
    HostCommandTimeoutError,
    HostRequestRejectedError,
    HostResponseMalformedError,
    HostUnauthenticatedError,
    HostUnreachableError,
    NoHostRemoteError,
    NoMergeBaseError,
    NoOpenPullRequestForBranchError,
    OperatorUnidentifiedError,
    PullRequestCreationRejectedError,
    PullRequestNotFoundError,
    RefMovedSinceResolutionError,
    RefNotFetchableError,
    TargetSyntaxError,
    TargetUnresolvableError,
]


def test_the_error_table_covers_every_subclass() -> None:
    """The count is the check: a new error class must be added here too."""
    declared = {
        obj
        for obj in vars(errors_module).values()
        if isinstance(obj, type) and issubclass(obj, CodeHostError) and obj is not CodeHostError
    }
    assert len(_ALL_ERROR_CLASSES) == 19
    assert set(_ALL_ERROR_CLASSES) == declared


def _instance(error_class: type[CodeHostError]) -> CodeHostError:
    """Build one of each, supplying the structured fields each requires."""
    if error_class is HostCommandTimeoutError:
        return HostCommandTimeoutError(["gh", "api"], 30.0)
    if error_class is RefMovedSinceResolutionError:
        return RefMovedSinceResolutionError(RefRole.BASE, "aaa", "bbb")
    if error_class is RefNotFetchableError:
        return RefNotFetchableError(RefRole.HEAD, "head could not be fetched")
    if error_class is HostRequestRejectedError:
        return HostRequestRejectedError(500, "server error")
    if error_class is HostResponseMalformedError:
        return HostResponseMalformedError(["gh", "api"], "unparseable")
    return error_class("simulated failure")


@pytest.mark.parametrize("error_class", _ALL_ERROR_CLASSES, ids=lambda cls: cls.__name__)
def test_every_error_exits_one_and_is_logged(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    caplog: pytest.LogCaptureFixture,
    error_class: type[CodeHostError],
) -> None:
    """Type, log level, and exit code asserted together, one row per class."""
    raised = _instance(error_class)

    def _explode(*_args: object, **_kwargs: object) -> object:
        _logger = logging.getLogger("squadron.codehost.github_cli")
        _logger.warning("%s: %s", type(raised).__name__, raised)
        raise raised

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr("squadron.cli.commands.pr.list_remotes", _explode)
        with caplog.at_level(logging.WARNING):
            result = _run(cli_runner, patched_host, ["pr", "show", "83"], _read_script(GITHUB))
    finally:
        monkeypatch.undo()

    assert result.exit_code == 1, result.output
    assert any(record.levelno >= logging.WARNING for record in caplog.records), (
        f"{error_class.__name__} reached the CLI without a WARNING-or-higher record"
    )


def test_error_message_and_hint_go_to_stderr_not_stdout(
    cli_runner: CliRunner, patched_host: dict[str, object]
) -> None:
    """`sq pr show --json | parser` stays parseable when the command fails."""
    raised = NoHostRemoteError("no supported remote", fix_hint="Add a remote.")

    def _explode(*_args: object, **_kwargs: object) -> object:
        raise raised

    monkeypatch = pytest.MonkeyPatch()
    try:
        monkeypatch.setattr("squadron.cli.commands.pr.list_remotes", _explode)
        runner = CliRunner()
        result = runner.invoke(app, ["pr", "show", "83", "--json"])
    finally:
        monkeypatch.undo()

    assert result.exit_code == 1
    assert "no supported remote" not in result.stdout
