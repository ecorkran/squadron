"""Tests for CodexProvider."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.provider import CodexProvider
from squadron.providers.errors import ProviderAuthError, ProviderError


@pytest.fixture()
def provider() -> CodexProvider:
    return CodexProvider()


@pytest.fixture()
def agent_config() -> AgentConfig:
    return AgentConfig(
        name="test-codex",
        agent_type="codex",
        provider="codex",
        model="gpt-5.3-codex",
    )


@pytest.fixture()
def _codex_logged_in() -> None:
    """Write ~/.codex/auth.json in the per-test home."""
    auth_file = Path.home() / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text("{}")


class TestProviderType:
    def test_returns_openai_oauth(self, provider: CodexProvider) -> None:
        from squadron.providers.base import ProviderType

        assert provider.provider_type == ProviderType.OPENAI_OAUTH


class TestCapabilities:
    def test_can_read_files(self, provider: CodexProvider) -> None:
        assert provider.capabilities.can_read_files is True

    def test_supports_system_prompt(self, provider: CodexProvider) -> None:
        assert provider.capabilities.supports_system_prompt is True

    def test_no_streaming(self, provider: CodexProvider) -> None:
        assert provider.capabilities.supports_streaming is False


class TestCreateAgent:
    @pytest.mark.usefixtures("_codex_logged_in")
    def test_returns_codex_agent(
        self,
        provider: CodexProvider,
        agent_config: AgentConfig,
    ) -> None:
        with patch(
            "squadron.providers.codex.agent.resolve_codex_binary",
            return_value="/usr/local/bin/codex",
        ):
            agent = asyncio.run(provider.create_agent(agent_config))
        assert isinstance(agent, CodexAgent)
        assert agent.name == "test-codex"

    @pytest.mark.usefixtures("_codex_logged_in")
    def test_raises_when_binary_absent(
        self,
        provider: CodexProvider,
        agent_config: AgentConfig,
    ) -> None:
        with patch(
            "squadron.providers.codex.agent.resolve_codex_binary",
            return_value=None,
        ):
            with pytest.raises(ProviderError, match="npm i -g @openai/codex"):
                asyncio.run(provider.create_agent(agent_config))

    def test_raises_when_no_credentials(
        self,
        provider: CodexProvider,
        agent_config: AgentConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The per-test home has no ~/.codex/auth.json.
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(ProviderAuthError, match="No Codex credentials"):
            asyncio.run(provider.create_agent(agent_config))


class TestValidateCredentials:
    @pytest.mark.usefixtures("_codex_logged_in")
    def test_true_when_sdk_importable_and_creds(self, provider: CodexProvider) -> None:
        # Mock the SDK as importable
        with patch.dict("sys.modules", {"codex_app_server": MagicMock()}):
            with patch(
                "squadron.providers.codex.agent.resolve_codex_binary",
                return_value="/usr/local/bin/codex",
            ):
                assert asyncio.run(provider.validate_credentials()) is True

    def test_false_when_sdk_not_importable(
        self,
        provider: CodexProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with patch("builtins.__import__", side_effect=ImportError):
            assert asyncio.run(provider.validate_credentials()) is False
