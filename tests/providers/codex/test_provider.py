"""Tests for CodexProvider."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.codex.agent import CodexAgent
from squadron.providers.codex.provider import CodexProvider
from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND
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


_MODULE_AVAILABLE = "squadron.providers.codex.runtime._module_available"
_WHICH = "squadron.providers.codex.runtime.shutil.which"


def _sdk_installed(name: str) -> bool:
    return name in {"openai_codex", "codex_cli_bin"}


def _sdk_without_bundled_bin(name: str) -> bool:
    return name == "openai_codex"


class TestCreateAgent:
    @pytest.mark.usefixtures("_codex_logged_in")
    def test_returns_codex_agent(self, provider: CodexProvider, agent_config: AgentConfig) -> None:
        with patch(_MODULE_AVAILABLE, side_effect=_sdk_installed):
            agent = asyncio.run(provider.create_agent(agent_config))
        assert isinstance(agent, CodexAgent)
        assert agent.name == "test-codex"

    @pytest.mark.usefixtures("_codex_logged_in")
    def test_package_missing_raises_install_hint(
        self, provider: CodexProvider, agent_config: AgentConfig
    ) -> None:
        with patch(_MODULE_AVAILABLE, return_value=False):
            with pytest.raises(ProviderError) as exc_info:
                asyncio.run(provider.create_agent(agent_config))
        assert CODEX_INSTALL_COMMAND in str(exc_info.value)

    @pytest.mark.usefixtures("_codex_logged_in")
    def test_no_binary_names_both_remedies(
        self, provider: CodexProvider, agent_config: AgentConfig
    ) -> None:
        with (
            patch(_MODULE_AVAILABLE, side_effect=_sdk_without_bundled_bin),
            patch(_WHICH, return_value=None),
        ):
            with pytest.raises(ProviderError) as exc_info:
                asyncio.run(provider.create_agent(agent_config))
        message = str(exc_info.value)
        assert CODEX_INSTALL_COMMAND in message
        assert "PATH" in message

    def test_raises_when_no_credentials(
        self, provider: CodexProvider, agent_config: AgentConfig
    ) -> None:
        # The per-test home has no ~/.codex/auth.json.
        with patch(_MODULE_AVAILABLE, side_effect=_sdk_installed):
            with pytest.raises(ProviderAuthError, match="No Codex credentials"):
                asyncio.run(provider.create_agent(agent_config))


class TestValidateCredentials:
    @pytest.mark.usefixtures("_codex_logged_in")
    def test_true_when_runtime_resolves_and_logged_in(self, provider: CodexProvider) -> None:
        with patch(_MODULE_AVAILABLE, side_effect=_sdk_installed):
            assert asyncio.run(provider.validate_credentials()) is True

    def test_false_when_runtime_resolves_but_not_logged_in(self, provider: CodexProvider) -> None:
        with patch(_MODULE_AVAILABLE, side_effect=_sdk_installed):
            assert asyncio.run(provider.validate_credentials()) is False

    @pytest.mark.usefixtures("_codex_logged_in")
    def test_false_when_package_missing(self, provider: CodexProvider) -> None:
        with patch(_MODULE_AVAILABLE, return_value=False):
            assert asyncio.run(provider.validate_credentials()) is False

    @pytest.mark.usefixtures("_codex_logged_in")
    def test_false_when_no_binary(self, provider: CodexProvider) -> None:
        with (
            patch(_MODULE_AVAILABLE, side_effect=_sdk_without_bundled_bin),
            patch(_WHICH, return_value=None),
        ):
            assert asyncio.run(provider.validate_credentials()) is False
