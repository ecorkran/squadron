"""Tests for ClaudeSDKProvider — options mapping, defaults, and credentials."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.errors import ProviderError
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
            # Canonical names are translated to Claude vocabulary at the config-build edge.
            assert opts.allowed_tools == ["Read", "Bash"]
            assert opts.cwd == "/workspace"
            assert opts.setting_sources == ["project"]
            assert opts.permission_mode == "bypassPermissions"

    @pytest.mark.asyncio
    async def test_default_system_prompt_uses_preset(self, provider: ClaudeSDKProvider) -> None:
        """The preset form is the only way to get the CLI's own system prompt.

        A str (including "") and None both make the SDK emit
        ``--system-prompt ""`` — an *empty* prompt, which strips the tool-use
        discipline the CLI normally supplies. Only the preset makes it omit
        the flag so the CLI falls back to its default.
        """
        config = AgentConfig(
            name="audit",
            agent_type="sdk",
            provider="sdk",
            instructions=None,
            use_default_system_prompt=True,
        )
        with patch(_AGENT_PATCH, create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            opts = mock_cls.call_args.kwargs["options"]
            assert opts.system_prompt == {"type": "preset", "preset": "claude_code"}

    @pytest.mark.asyncio
    async def test_default_system_prompt_wins_over_instructions(
        self, provider: ClaudeSDKProvider
    ) -> None:
        config = AgentConfig(
            name="audit",
            agent_type="sdk",
            provider="sdk",
            instructions="ignored",
            use_default_system_prompt=True,
        )
        with patch(_AGENT_PATCH, create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            opts = mock_cls.call_args.kwargs["options"]
            assert opts.system_prompt == {"type": "preset", "preset": "claude_code"}

    @pytest.mark.asyncio
    async def test_rate_limit_overrides_reach_the_agent(self, provider: ClaudeSDKProvider) -> None:
        config = AgentConfig(
            name="audit",
            agent_type="sdk",
            provider="sdk",
            credentials={"max_rate_limit_retries": 25, "rate_limit_cap_s": 120},
        )
        with patch(_AGENT_PATCH, create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)

            assert mock_cls.call_args.kwargs["max_rate_limit_retries"] == 25
            assert mock_cls.call_args.kwargs["rate_limit_cap_s"] == 120.0

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
    async def test_returns_true_when_importable(self, provider: ClaudeSDKProvider) -> None:
        result = await provider.validate_credentials()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_import_fails(self, provider: ClaudeSDKProvider) -> None:
        with patch.dict("sys.modules", {"claude_agent_sdk": None}):
            # When the module entry is None, Python raises ImportError
            result = await provider.validate_credentials()
            assert result is False


# ---------------------------------------------------------------------------
# create_agent — canonical -> Claude tool name translation
# ---------------------------------------------------------------------------


class TestToolNameTranslation:
    """Canonical squadron names become Claude names on the built ClaudeAgentOptions.

    Every assertion here reads the built config object rather than inferring translation from
    a mock call, because the built object is what the CLI actually receives.
    """

    async def _build_options(self, provider: ClaudeSDKProvider, allowed_tools: list[str] | None):
        config = AgentConfig(
            name="tooled",
            agent_type="sdk",
            provider="sdk",
            allowed_tools=allowed_tools,
        )
        with patch(_AGENT_PATCH, create=True) as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
            return mock_cls.call_args.kwargs["options"]

    @pytest.mark.asyncio
    async def test_canonical_names_translate_to_claude_names(self, provider: ClaudeSDKProvider) -> None:
        opts = await self._build_options(provider, ["read_file", "list_files", "grep"])

        assert opts.allowed_tools == ["Read", "Glob", "Grep"]

    @pytest.mark.asyncio
    async def test_write_and_bash_translate(self, provider: ClaudeSDKProvider) -> None:
        opts = await self._build_options(provider, ["write_file", "bash"])

        assert opts.allowed_tools == ["Write", "Bash"]

    @pytest.mark.asyncio
    async def test_unmapped_canonical_name_raises_provider_error(
        self, provider: ClaudeSDKProvider
    ) -> None:
        with pytest.raises(ProviderError, match="not_a_tool"):
            await self._build_options(provider, ["read_file", "not_a_tool"])

    @pytest.mark.asyncio
    async def test_claude_name_is_not_accepted_as_input(self, provider: ClaudeSDKProvider) -> None:
        """Guards against a half-migrated template quietly passing through."""
        with pytest.raises(ProviderError, match="Read"):
            await self._build_options(provider, ["Read"])

    @pytest.mark.asyncio
    async def test_none_allowed_tools_skips_translation(self, provider: ClaudeSDKProvider) -> None:
        opts = await self._build_options(provider, None)

        assert opts.allowed_tools == []
