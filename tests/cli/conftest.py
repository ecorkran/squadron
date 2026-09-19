"""Shared fixtures for CLI tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.core.models import AgentInfo, AgentState, Message

if TYPE_CHECKING:
    from tests.cli.pr_create_support import HostHarness


@pytest.fixture
def cli_runner() -> CliRunner:
    """Typer CliRunner instance for invoking CLI commands in tests."""
    return CliRunner()


@pytest.fixture
def mock_daemon_client() -> MagicMock:
    """Mock DaemonClient with all async methods as AsyncMock."""
    client = MagicMock()
    client.spawn = AsyncMock()
    client.list_agents = AsyncMock()
    client.send_message = AsyncMock()
    client.get_history = AsyncMock()
    client.shutdown_agent = AsyncMock()
    client.shutdown_all = AsyncMock()
    client.health = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def patch_daemon_client(mock_daemon_client: MagicMock):  # type: ignore[no-untyped-def]
    """Patch DaemonClient() in all command modules to return mock."""
    targets = [
        "squadron.cli.commands.spawn.DaemonClient",
        "squadron.cli.commands.list.DaemonClient",
        "squadron.cli.commands.task.DaemonClient",
        "squadron.cli.commands.shutdown.DaemonClient",
    ]
    patches = []
    for t in targets:
        try:
            p = patch(t, return_value=mock_daemon_client)
            p.start()
            patches.append(p)
        except (ModuleNotFoundError, AttributeError):
            pass  # Module not yet created
    yield mock_daemon_client
    for p in patches:
        p.stop()


def make_agent_info(
    name: str = "test-agent",
    agent_type: str = "sdk",
    provider: str = "sdk",
    state: AgentState = AgentState.idle,
) -> AgentInfo:
    """Factory for AgentInfo test instances."""
    return AgentInfo(
        name=name,
        agent_type=agent_type,
        provider=provider,
        state=state,
    )


def make_agent_dict(
    name: str = "test-agent",
    agent_type: str = "sdk",
    provider: str = "sdk",
    state: str = "idle",
) -> dict:  # type: ignore[type-arg]
    """Factory for agent info dicts (daemon API response format)."""
    return {
        "name": name,
        "agent_type": agent_type,
        "provider": provider,
        "state": state,
    }


def make_message(
    content: str = "Hello from agent",
    sender: str = "test-agent",
) -> Message:
    """Factory for Message test instances."""
    return Message(
        sender=sender,
        recipients=["human"],
        content=content,
    )


def make_message_dict(
    content: str = "Hello from agent",
    sender: str = "test-agent",
) -> dict:  # type: ignore[type-arg]
    """Factory for message dicts (daemon API response format)."""
    return {
        "id": "test-id",
        "sender": sender,
        "content": content,
        "message_type": "chat",
        "timestamp": "2026-02-28T00:00:00",
        "metadata": {},
    }


@pytest.fixture(autouse=True)
def isolate_reviews_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep saved review artifacts out of the working checkout.

    ``REVIEWS_DIR`` is a repo-relative constant, so a CLI test whose save path
    is not mocked writes a real review into ``project-documents/user/reviews/``
    — and archives any prior file of the same name on the way. Two such files
    reached a commit before this fixture existed.

    Scoped to ``tests/cli`` rather than the root conftest: several tests under
    ``tests/review`` build their own reviews directories and pass them
    explicitly, and a blanket override would fight them.
    """
    reviews = tmp_path / "cli-reviews"
    reviews.mkdir()
    monkeypatch.setattr("squadron.review.persistence.REVIEWS_DIR", reviews)


# --- ``sq pr create`` fixtures (opt in with ``pytest.mark.usefixtures``) -----


@pytest.fixture
def isolated_cf(monkeypatch: pytest.MonkeyPatch) -> None:
    """cf is never actually installed in tests: treat it as unavailable everywhere."""
    from squadron.integrations.context_forge import ContextForgeClient, ContextForgeNotAvailable

    def _raise(self: object, *args: object) -> object:
        raise ContextForgeNotAvailable("cf not on PATH")

    monkeypatch.setattr(ContextForgeClient, "get_config", _raise)
    monkeypatch.setattr(ContextForgeClient, "list_slices", _raise)


@pytest.fixture
def pr_create_repo(tmp_path: Path) -> Path:
    """A real git repo, one commit ahead of ``main`` on the head branch.

    ``commits_in_range`` and the review scan shell out directly rather than
    through the fakeable host runner, so they need real history.
    """
    from tests.cli.pr_create_support import HEAD_BRANCH, git

    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.email", "test@test.com")
    git(tmp_path, "config", "user.name", "Test")
    (tmp_path / "README.md").write_text("init")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "init")
    git(tmp_path, "checkout", "-b", HEAD_BRANCH)
    (tmp_path / "feature.txt").write_text("a feature")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-m", "feat: do the thing")
    return tmp_path


@pytest.fixture
def pr_create_host() -> Iterator[HostHarness]:
    """Substitute the host factory; the harness carries the script and runner."""
    from squadron.codehost.github_cli import GitHubCli
    from tests.cli.pr_create_support import GITHUB, HostHarness

    harness = HostHarness()

    def _build(_runner: object) -> GitHubCli:
        return GitHubCli(harness.build_runner(), frozenset({GITHUB}))

    with patch("squadron.cli.commands.pr.build_github_host", _build):
        yield harness


@pytest.fixture
def fake_composer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every model call returns fixed prose; no test calls a real model."""
    from squadron.providers import loader as loader_mod
    from squadron.providers import profiles as profiles_mod
    from squadron.providers import registry as registry_mod
    from squadron.providers.base import AgentProvider, ProviderCapabilities
    from squadron.providers.profiles import ProviderProfile
    from tests.cli.pr_create_support import (
        FAKE_PROFILE,
        FAKE_PROSE,
        FAKE_PROVIDER_TYPE,
        make_fake_agent,
    )

    fake_profile = ProviderProfile(
        name=FAKE_PROFILE,
        provider=FAKE_PROVIDER_TYPE,
        api_key_env=None,
        description="Fake profile for pr-create tests",
    )
    original_get_all = profiles_mod.get_all_profiles
    monkeypatch.setattr(
        profiles_mod,
        "get_all_profiles",
        lambda: {**original_get_all(), FAKE_PROFILE: fake_profile},
    )
    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)

    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = FAKE_PROVIDER_TYPE
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(side_effect=lambda config: make_fake_agent(FAKE_PROSE))
    monkeypatch.setitem(registry_mod._REGISTRY, FAKE_PROVIDER_TYPE, provider)
