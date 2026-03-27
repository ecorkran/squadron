"""Tests for CodexProvider."""

from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.provider import CodexProvider
from squadron.providers.errors import ProviderAuthError


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


class TestProviderType:
    def test_returns_openai_oauth(self, provider: CodexProvider) -> None:
        from squadron.providers.base import ProviderType

        assert provider.provider_type == ProviderType.OPENAI_OAUTH


class TestCapabilities:
    def test_can_read_files(self, provider: CodexProvider) -> None:
        assert provider.capabilities.can_read_files is True

    def test_no_system_prompt(self, provider: CodexProvider) -> None:
        assert provider.capabilities.supports_system_prompt is False

    def test_no_streaming(self, provider: CodexProvider) -> None:
        assert provider.capabilities.supports_streaming is False


class TestCreateAgent:
    def test_returns_codex_agent(
        self,
        provider: CodexProvider,
        agent_config: AgentConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        agent = asyncio.run(provider.create_agent(agent_config))
        assert isinstance(agent, CodexAgent)
        assert agent.name == "test-codex"

    def test_raises_when_no_credentials(
        self,
        provider: CodexProvider,
        agent_config: AgentConfig,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with patch(
            "squadron.providers.codex.auth._CODEX_AUTH_FILE",
            tmp_path / "nonexistent" / "auth.json",  # type: ignore[operator]
        ):
            with pytest.raises(ProviderAuthError, match="No Codex credentials"):
                asyncio.run(provider.create_agent(agent_config))


class TestValidateCredentials:
    def test_true_when_sdk_importable_and_creds(
        self,
        provider: CodexProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert asyncio.run(provider.validate_credentials()) is True

    def test_false_when_sdk_not_importable(
        self,
        provider: CodexProvider,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        with patch("builtins.__import__", side_effect=ImportError):
            assert asyncio.run(provider.validate_credentials()) is False
