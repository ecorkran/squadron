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

import subprocess
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.codehost.github_cli import HOST_COMMAND_TIMEOUT_SECONDS, GitHubCli
from squadron.codehost.remotes import GIT_QUERY_TIMEOUT_SECONDS
from squadron.core.models import Message
from squadron.core.process_runner import ProcessResult, ProcessTimedOutError
from squadron.integrations.context_forge import ContextForgeNotAvailable
from squadron.providers.base import AgentProvider, ProviderCapabilities
from tests.codehost.fake_runner import FakeProcessRunner

GITHUB = "github.com"
_FIXTURES = Path(__file__).parent.parent / "codehost" / "fixtures" / "gh"
_FAKE_PROFILE = "sdk"
_FAKE_PROVIDER_TYPE = "fake-pr-create-failures-provider"


def _fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _ok(stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=0, stdout=stdout, stderr="")


def _fail(returncode: int, stdout: str = "") -> ProcessResult:
    return ProcessResult(argv=(), returncode=returncode, stdout=stdout, stderr="")


@pytest.fixture(autouse=True)
def _isolated_cf(monkeypatch: pytest.MonkeyPatch) -> None:
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
    script_holder: dict[str, list[tuple[list[str], ProcessResult | Exception]]] = {"script": []}
    captured: dict[str, object] = {}

    def _build(_runner: object) -> GitHubCli:
        fake = FakeProcessRunner(script_holder["script"])
        captured["runner"] = fake
        return GitHubCli(fake, frozenset({GITHUB}))

    with patch("squadron.cli.commands.pr.build_github_host", _build):
        yield {"script_holder": script_holder, "runner": captured}


def _arm(
    patched_host: dict[str, object], script: list[tuple[list[str], ProcessResult | Exception]]
) -> None:
    holder = patched_host["script_holder"]
    holder["script"] = script  # type: ignore[index]


def _runner_of(patched_host: dict[str, object]) -> FakeProcessRunner:
    captured = patched_host["runner"]
    runner = captured["runner"]  # type: ignore[index]
    assert isinstance(runner, FakeProcessRunner)
    return runner


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
    from squadron.providers import loader as loader_mod
    from squadron.providers import profiles as profiles_mod
    from squadron.providers import registry as registry_mod
    from squadron.providers.profiles import ProviderProfile

    fake_profile = ProviderProfile(
        name=_FAKE_PROFILE,
        provider=_FAKE_PROVIDER_TYPE,
        api_key_env=None,
        description="Fake profile for pr-create failure tests",
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


#: Scripted calls preceding each failure site's own call — the reads that
#: must succeed on the way to that site. Each site's failing call itself is
#: appended by the test.
def _prefix_for(site: str, *, local_sha: str) -> list[tuple[list[str], ProcessResult | Exception]]:
    remote_discovery = [
        (["git", "remote"], _ok("origin\n")),
        (["git", "remote", "get-url"], _ok(f"https://{GITHUB}/ecorkran/squadron.git\n")),
        (["git", "rev-parse", "--abbrev-ref", "HEAD"], _ok("scratch-branch\n")),
    ]
    if site == "identify_operator":
        return remote_discovery
    identity = [(["gh", "api", "user"], _ok(_fixture("user.json")))]
    if site == "branch_exists":
        return [*remote_discovery, *identity, (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n"))]
    branch_exists = [
        (
            ["gh", "api", "repos/ecorkran/squadron/branches/scratch-branch"],
            _ok(_fixture("repo.json")),
        )
    ]
    if site == "ls_remote":
        return [
            *remote_discovery,
            *identity,
            (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n")),
            *branch_exists,
        ]
    ls_remote = [
        (
            ["git", "ls-remote", "origin", "refs/heads/scratch-branch"],
            _ok(f"{local_sha}\trefs/heads/scratch-branch\n"),
        )
    ]
    if site == "default_branch":
        return [
            *remote_discovery,
            *identity,
            (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n")),
            *branch_exists,
            *ls_remote,
        ]
    default_branch = [(["gh", "api", "repos/ecorkran/squadron"], _ok(_fixture("repo.json")))]
    if site == "open_pull_request":
        return [
            *remote_discovery,
            *identity,
            (["git", "rev-parse", "HEAD"], _ok(f"{local_sha}\n")),
            *branch_exists,
            *ls_remote,
            *default_branch,
        ]
    raise ValueError(f"unknown site: {site}")


_SITE_FAILING_CALL: dict[str, list[str]] = {
    "identify_operator": ["gh", "api", "user"],
    "branch_exists": ["gh", "api", "repos/ecorkran/squadron/branches/scratch-branch"],
    "ls_remote": ["git", "ls-remote", "origin", "refs/heads/scratch-branch"],
    "default_branch": ["gh", "api", "repos/ecorkran/squadron"],
    "open_pull_request": ["gh", "api", "-X", "POST"],
}

#: The four `gh` calls carry HOST_COMMAND_TIMEOUT_SECONDS; the one git query
#: (ls-remote) carries GIT_QUERY_TIMEOUT_SECONDS (D2, F007).
_SITE_TIMEOUT: dict[str, float] = {
    "identify_operator": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "branch_exists": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "ls_remote": float(GIT_QUERY_TIMEOUT_SECONDS),
    "default_branch": float(HOST_COMMAND_TIMEOUT_SECONDS),
    "open_pull_request": float(HOST_COMMAND_TIMEOUT_SECONDS),
}


@pytest.mark.parametrize(
    "site", ["identify_operator", "branch_exists", "ls_remote", "default_branch", "open_pull_request"]
)
def test_transport_failure_at_each_site_exits_one_with_no_effective_write(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path, site: str
) -> None:
    local_sha = _local_head_sha(repo)
    prefix = _prefix_for(site, local_sha=local_sha)
    failing_call = _SITE_FAILING_CALL[site]
    _arm(patched_host, [*prefix, (failing_call, _fail(1, '{"status":"500","message":"boom"}'))])

    result = cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo)])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    writes = runner.write_calls()
    if site == "open_pull_request":
        assert len(writes) == 1, "expected exactly one write attempt, not a retry or duplicate"
    else:
        assert writes == []


@pytest.mark.parametrize(
    "site", ["identify_operator", "branch_exists", "ls_remote", "default_branch", "open_pull_request"]
)
def test_scripted_timeout_at_each_site_exits_one_with_no_effective_write(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path, site: str
) -> None:
    local_sha = _local_head_sha(repo)
    prefix = _prefix_for(site, local_sha=local_sha)
    failing_call = _SITE_FAILING_CALL[site]
    timeout = _SITE_TIMEOUT[site]
    _arm(patched_host, [*prefix, (failing_call, ProcessTimedOutError(failing_call, timeout))])

    result = cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo)])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    writes = runner.write_calls()
    if site == "open_pull_request":
        assert len(writes) == 1
    else:
        assert writes == []


def test_the_four_gh_calls_carry_host_timeout_and_ls_remote_carries_git_query_timeout(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    local_sha = _local_head_sha(repo)
    script = _prefix_for("open_pull_request", local_sha=local_sha) + [
        (
            ["gh", "api", "-X", "POST"],
            _ok('{"number":99,"html_url":"https://github.com/ecorkran/squadron/pull/99"}'),
        )
    ]
    _arm(patched_host, script)

    result = cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo)])

    assert result.exit_code == 0, result.output
    runner = _runner_of(patched_host)
    gh_calls = [call for call in runner.calls if call.argv[0] == "gh"]
    ls_remote_calls = [call for call in runner.calls if call.argv[:2] == ("git", "ls-remote")]

    assert gh_calls, "expected at least one gh call"
    for call in gh_calls:
        assert call.timeout == HOST_COMMAND_TIMEOUT_SECONDS

    assert ls_remote_calls, "expected the ls-remote call"
    for call in ls_remote_calls:
        assert call.timeout == GIT_QUERY_TIMEOUT_SECONDS


def test_pull_request_creation_rejected_is_reported_and_not_retried(
    cli_runner: CliRunner, patched_host: dict[str, object], repo: Path
) -> None:
    local_sha = _local_head_sha(repo)
    script = _prefix_for("open_pull_request", local_sha=local_sha) + [
        (["gh", "api", "-X", "POST"], _fail(1, _fixture("rest-422.json")))
    ]
    _arm(patched_host, script)

    result = cli_runner.invoke(app, ["pr", "create", "--cwd", str(repo)])

    assert result.exit_code == 1, result.output
    runner = _runner_of(patched_host)
    writes = runner.write_calls()
    assert len(writes) == 1, "a rejected create must not be retried"
