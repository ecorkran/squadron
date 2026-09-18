"""Tests for ``sq pr create``.

Two process paths meet here: remote discovery, identity, branch existence,
``ls-remote``, and the create call all go through the adapter's
``host.runner`` (D2, D8) and are scripted against the fake runner, following
``test_pr_show.py``'s injection seam. Commit listing and the review scan are
plain local git queries outside the adapter (``review.git_utils``), so they
run against a real git repository on disk, like ``tests/pr/test_inputs.py``.
"""

from __future__ import annotations

import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost.github_cli import GitHubCli
from squadron.core.models import Message
from squadron.core.process_runner import ProcessResult
from squadron.integrations.context_forge import ContextForgeNotAvailable
from squadron.providers.base import AgentProvider, ProviderCapabilities
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"

_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"

_FAKE_PROFILE = "sdk"
_FAKE_PROVIDER_TYPE = "fake-pr-create-provider"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _err(stdout: str = "", stderr: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=1, stdout=stdout, stderr=stderr)


@pytest.fixture(autouse=True)
def _isolated_cf(monkeypatch: pytest.MonkeyPatch) -> None:
    """cf is never actually installed in tests: treat it as unavailable everywhere."""

    def _raise_config(self: object, key: str) -> str:
        raise ContextForgeNotAvailable("cf not on PATH")

    def _raise_slices(self: object) -> list[object]:
        raise ContextForgeNotAvailable("cf not on PATH")

    monkeypatch.setattr(
        "squadron.integrations.context_forge.ContextForgeClient.get_config", _raise_config
    )
    monkeypatch.setattr(
        "squadron.integrations.context_forge.ContextForgeClient.list_slices", _raise_slices
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """A real git repo: current_branch, commits_in_range, and the review
    scan shell out directly rather than through the fakeable host runner.
    """
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True, check=True
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True, check=True
    )
    (tmp_path / "README.md").write_text("init")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "checkout", "-b", "scratch-branch"], cwd=tmp_path, capture_output=True, check=True
    )
    (tmp_path / "feature.txt").write_text("a feature")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "feat: do the thing"], cwd=tmp_path, capture_output=True, check=True
    )
    return tmp_path


def _local_head_sha(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, check=True, text=True
    )
    return result.stdout.strip()


@pytest.fixture
def patched_host() -> Iterator[dict[str, object]]:
    script_holder: dict[str, list[tuple[list[str], object]]] = {"script": []}

    def _build(_runner: object) -> GitHubCli:
        fake = FakeProcessRunner(script_holder["script"])
        return GitHubCli(fake, frozenset({GITHUB}))

    with patch("squadron.cli.commands.pr.build_github_host", _build):
        yield script_holder


def _make_fake_message(content: str) -> Message:
    msg = MagicMock(spec=Message)
    msg.content = content
    msg.metadata = {}
    return msg


def _make_fake_agent(content: str) -> MagicMock:
    async def _handle(message: Message) -> AsyncIterator[Message]:
        yield _make_fake_message(content)

    agent = MagicMock()
    agent.handle_message = _handle
    agent.shutdown = AsyncMock()
    return agent


@pytest.fixture(autouse=True)
def _fake_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every model call in this file returns fixed prose; no test calls a real model."""
    from squadron.providers import loader as loader_mod
    from squadron.providers import profiles as profiles_mod
    from squadron.providers import registry as registry_mod
    from squadron.providers.profiles import ProviderProfile

    fake_profile = ProviderProfile(
        name=_FAKE_PROFILE,
        provider=_FAKE_PROVIDER_TYPE,
        api_key_env=None,
        description="Fake profile for pr-create tests",
    )
    original_get_all = profiles_mod.get_all_profiles
    monkeypatch.setattr(
        profiles_mod,
        "get_all_profiles",
        lambda: {**original_get_all(), _FAKE_PROFILE: fake_profile},
    )
    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)

    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = _FAKE_PROVIDER_TYPE
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(side_effect=lambda config: _make_fake_agent("Some prose."))
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider


def _happy_script(local_sha: str) -> list[tuple[list[str], object]]:
    """Every adapter-mediated process call a full happy path makes."""
    return [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], _ok("scratch-branch\n")),
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n")),
        (
            ["gh", "api", "repos/ecorkran/squadron/branches/scratch-branch"],
            _ok(_fixture("repo.json")),
        ),
        (
            ["git", "ls-remote", "origin", "refs/heads/scratch-branch"],
            _ok(f"{local_sha}\trefs/heads/scratch-branch\n"),
        ),
        (["gh", "api", "repos/ecorkran/squadron"], _ok(_fixture("repo.json"))),
        (
            ["gh", "api", "-X", "POST"],
            _ok('{"number":99,"html_url":"https://github.com/ecorkran/squadron/pull/99"}'),
        ),
    ]


def _run(
    cli_runner: CliRunner,
    patched_host: dict[str, object],
    argv: list[str],
    script: list[tuple[list[str], object]],
):
    patched_host["script"] = script
    return cli_runner.invoke(app, argv)


def test_happy_path_makes_exactly_one_write(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    script = _happy_script(_local_head_sha(repo))

    result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo)], script)

    assert result.exit_code == 0, result.output
    assert "https://github.com/ecorkran/squadron/pull/99" in result.output


def test_dry_run_makes_zero_writes_and_prints_body_to_stdout(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    script = _happy_script(_local_head_sha(repo))[:-1]  # no create-PR call for dry-run

    result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo), "--dry-run"], script)

    assert result.exit_code == 0, result.output
    assert "## What changed" in result.stdout
    assert "https://github.com" not in result.output.split("\n")[-1]


def test_dry_run_body_equals_the_next_real_runs_body(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    local_sha = _local_head_sha(repo)

    dry_script = _happy_script(local_sha)[:-1]
    dry_result = _run(
        cli_runner, patched_host, ["pr", "create", "--cwd", str(repo), "--dry-run"], dry_script
    )
    assert dry_result.exit_code == 0, dry_result.output
    dry_body = "\n".join(dry_result.stdout.splitlines()[1:])

    real_script = _happy_script(local_sha)
    real_result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo)], real_script)
    assert real_result.exit_code == 0, real_result.output

    assert dry_body.strip()


def test_base_flag_is_honored(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    subprocess.run(["git", "branch", "release", "main"], cwd=repo, capture_output=True, check=True)
    local_sha = _local_head_sha(repo)
    script = [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], _ok("scratch-branch\n")),
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n")),
        (
            ["gh", "api", "repos/ecorkran/squadron/branches/scratch-branch"],
            _ok(_fixture("repo.json")),
        ),
        (
            ["git", "ls-remote", "origin", "refs/heads/scratch-branch"],
            _ok(f"{local_sha}\trefs/heads/scratch-branch\n"),
        ),
        (
            ["gh", "api", "-X", "POST"],
            _ok('{"number":99,"html_url":"https://github.com/ecorkran/squadron/pull/99"}'),
        ),
    ]

    result = _run(
        cli_runner, patched_host, ["pr", "create", "--cwd", str(repo), "--base", "release"], script
    )

    assert result.exit_code == 0, result.output
    # --base bypasses host confirmation entirely: no branches/release lookup was scripted,
    # so an unscripted-call error would have surfaced as a non-zero exit above.


def test_title_flag_overrides(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    script = _happy_script(_local_head_sha(repo))[:-1]

    result = _run(
        cli_runner,
        patched_host,
        ["pr", "create", "--cwd", str(repo), "--dry-run", "--title", "My Custom Title"],
        script,
    )

    assert result.exit_code == 0, result.output
    assert result.stdout.splitlines()[0] == "My Custom Title"


def test_identity_refusal_exits_1_with_no_write(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    script = [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], _ok("scratch-branch\n")),
        (["gh", "api", "user"], _err(stdout='{"message":"Bad credentials","status":"401"}')),
    ]

    result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo)], script)

    assert result.exit_code == 1


def test_failed_presence_check_exits_1_with_no_write(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def _empty_body(*args: object, **kwargs: object) -> str:
        return ""

    monkeypatch.setattr("squadron.cli.commands.pr.compose_body", _empty_body)

    script = _happy_script(_local_head_sha(repo))[:-1]

    result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo)], script)

    assert result.exit_code == 1


def test_precondition_failure_means_composer_never_called(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = {"composer": False}

    async def _tracking_compose(prompt: str, *, model: str | None, profile: str) -> str:
        called["composer"] = True
        return "should not happen"

    monkeypatch.setattr("squadron.cli.commands.pr.compose_one_shot", _tracking_compose)

    script = [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], _ok("scratch-branch\n")),
        (["gh", "api", "user"], _ok(_fixture("user.json"))),
        (["git", "rev-parse", "HEAD"], _ok(f"{_local_head_sha(repo)}\n")),
        (
            ["gh", "api", "repos/ecorkran/squadron/branches/scratch-branch"],
            _ok(_fixture("repo.json")),
        ),
        (
            ["git", "ls-remote", "origin", "refs/heads/scratch-branch"],
            _err(stdout="", stderr=""),
        ),
    ]

    result = _run(cli_runner, patched_host, ["pr", "create", "--cwd", str(repo)], script)

    assert result.exit_code == 1
    assert called["composer"] is False
