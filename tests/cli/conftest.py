"""Shared fixtures for CLI tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from typer.testing import CliRunner

from squadron.core.models import AgentInfo, AgentState, Message


@pytest.fixture(autouse=True)
def _isolated_model_registry(tmp_path: Path) -> Iterator[Path]:
    """Redirect the alias registry to an empty temp file.

    ``resolve_model_alias``/``get_all_aliases`` read the developer's real
    ``~/.config/squadron/models.toml`` (no caching), so without this the
    unknown-alias guard tests depend on a name like ``llama-3-70b`` happening
    not to be defined locally — a machine that defines it fails the suite.
    Mirrors ``_isolated_user_config`` in ``tests/review/conftest.py``.
    """
    registry = tmp_path / "model-registry" / "models.toml"
    registry.parent.mkdir(parents=True, exist_ok=True)
    registry.write_text("", encoding="utf-8")
    with patch("squadron.models.aliases.models_toml_path", return_value=registry):
        yield registry


@pytest.fixture(autouse=True)
def _isolated_user_templates(tmp_path: Path) -> Iterator[Path]:
    """Redirect user template overrides to an empty temp dir.

    ``load_all_templates`` merges ``~/.config/squadron/templates``; a developer
    override that sets ``profile:`` on a template would legitimately suppress
    the unknown-alias guard and fail these tests for the wrong reason.
    """
    templates = tmp_path / "user-templates"
    templates.mkdir(parents=True, exist_ok=True)
    with patch("squadron.review.templates._USER_TEMPLATES_DIR", templates):
        yield templates


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
