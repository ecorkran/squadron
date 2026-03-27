"""Tests for ClaudeSDKProvider — options mapping, defaults, and credentials."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.sdk.provider import ClaudeSDKProvider

# Patch target: the deferred import inside create_agent resolves from this module.
_AGENT_PATCH = "squadron.providers.sdk.agent.ClaudeSDKAgent"


@pytest.fixture
def provider() -> ClaudeSDKProvider:
    return ClaudeSDKProvider()


# ---------------------------------------------------------------------------
# provider_type
# ---------------------------------------------------------------------------


def test_provider_type(provider: ClaudeSDKProvider) -> None:
    assert provider.provider_type == "sdk"


# ---------------------------------------------------------------------------
# create_agent — option mapping
# ---------------------------------------------------------------------------


class TestCreateAgent:
    @pytest.mark.asyncio
    async def test_minimal_config(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(name="basic", agent_type="sdk", provider="sdk")
        with patch(
            _AGENT_PATCH,
            create=True,
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            mock_cls.assert_called_once()
            _, kwargs = mock_cls.call_args
            assert kwargs["name"] == "basic"
            assert kwargs["mode"] == "query"
            # Options should have default permission_mode only
            opts = kwargs["options"]
            assert opts.permission_mode == "acceptEdits"

    @pytest.mark.asyncio
    async def test_full_sdk_config(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(
            name="full",
            agent_type="sdk",
            provider="sdk",
            instructions="You are a code reviewer.",
            model="claude-opus-4-20250514",
            allowed_tools=["read_file", "bash"],
            cwd="/workspace",
            setting_sources=["project"],
            permission_mode="bypassPermissions",
        )
        with patch(
            _AGENT_PATCH,
            create=True,
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            opts = mock_cls.call_args.kwargs["options"]
            assert opts.system_prompt == "You are a code reviewer."
            assert opts.model == "claude-opus-4-20250514"
            assert opts.allowed_tools == ["read_file", "bash"]
            assert opts.cwd == "/workspace"
            assert opts.setting_sources == ["project"]
            assert opts.permission_mode == "bypassPermissions"

    @pytest.mark.asyncio
    async def test_default_permission_mode(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(name="noperm", agent_type="sdk", provider="sdk")
        with patch(
            _AGENT_PATCH,
            create=True,
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            opts = mock_cls.call_args.kwargs["options"]
            assert opts.permission_mode == "acceptEdits"

    @pytest.mark.asyncio
    async def test_mode_from_credentials(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(
            name="client-mode",
            agent_type="sdk",
            provider="sdk",
            credentials={"mode": "client"},
        )
        with patch(
            _AGENT_PATCH,
            create=True,
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            assert mock_cls.call_args.kwargs["mode"] == "client"

    @pytest.mark.asyncio
    async def test_api_only_fields_ignored(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(
            name="api-fields",
            agent_type="sdk",
            provider="sdk",
            api_key="sk-12345",
            auth_token="tok-abc",
            base_url="https://api.example.com",
        )
        with patch(
            _AGENT_PATCH,
            create=True,
        ) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            # Should succeed without error — API fields silently ignored
            mock_cls.assert_called_once()


# ---------------------------------------------------------------------------
# validate_credentials
# ---------------------------------------------------------------------------


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_returns_true_when_importable(
        self, provider: ClaudeSDKProvider
    ) -> None:
        result = await provider.validate_credentials()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_import_fails(
        self, provider: ClaudeSDKProvider
    ) -> None:
        with patch.dict("sys.modules", {"claude_agent_sdk": None}):
            # When the module entry is None, Python raises ImportError
            result = await provider.validate_credentials()
            assert result is False
