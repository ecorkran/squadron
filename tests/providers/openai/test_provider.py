"""Tests for providers/openai/provider.py."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.config.manager import set_config
from squadron.core.models import AgentConfig
from squadron.providers.base import ProfileName
from squadron.providers.errors import ProviderAuthError, ProviderError
from squadron.providers.openai.provider import OpenAICompatibleProvider
from squadron.providers.profiles import BUILT_IN_PROFILES, profile_credentials

_BASE_CONFIG = dict(name="agent", agent_type="api", provider="openai", model="gpt-4o-mini")


@pytest.fixture
def provider() -> OpenAICompatibleProvider:
    return OpenAICompatibleProvider()


class TestProviderType:
    def test_provider_type(self, provider: OpenAICompatibleProvider) -> None:
        assert provider.provider_type == "openai"


class TestCreateAgent:
    @pytest.mark.asyncio
    async def test_uses_config_api_key(self, provider: OpenAICompatibleProvider) -> None:
        config = AgentConfig(**{**_BASE_CONFIG, "api_key": "sk-config"})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        mock_cls.assert_called_once()
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-config"

    @pytest.mark.asyncio
    async def test_falls_back_to_env_var(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**{**_BASE_CONFIG, "api_key": None})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-env"

    @pytest.mark.asyncio
    async def test_raises_auth_error_no_key(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = AgentConfig(**{**_BASE_CONFIG, "api_key": None})
        with pytest.raises(ProviderAuthError):
            await provider.create_agent(config)

    @pytest.mark.asyncio
    async def test_raises_error_model_none(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**{**_BASE_CONFIG, "model": None})
        with pytest.raises(ProviderError):
            await provider.create_agent(config)

    @pytest.mark.asyncio
    async def test_passes_base_url(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**{**_BASE_CONFIG, "base_url": "http://localhost:11434/v1"})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["base_url"] == "http://localhost:11434/v1"

    @pytest.mark.asyncio
    async def test_threads_allowed_tools_and_cwd_into_agent(
        self,
        provider: OpenAICompatibleProvider,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        # Review F002: create_agent's tools-configured path was previously exercised
        # only via an unmodified no-tools test suite plus a manual diff read. Assert
        # on the *returned agent object* so a future edit that silently drops the
        # threading is caught.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(
            **{
                **_BASE_CONFIG,
                "allowed_tools": ["read_file"],
                "cwd": str(tmp_path),
            }
        )
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent = await provider.create_agent(config)
        assert "read_file" in agent._tool_executors  # pyright: ignore[reportPrivateUsage]
        assert agent._cwd == config.cwd  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_threads_output_budget_into_agent(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**{**_BASE_CONFIG, "max_output_tokens": 4096})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent = await provider.create_agent(config)
        assert agent._max_output_tokens == 4096  # pyright: ignore[reportPrivateUsage]

    @pytest.mark.asyncio
    async def test_resolves_loop_bounds_from_config_into_agent(
        self,
        provider: OpenAICompatibleProvider,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        patch_config_paths: dict[str, Path],
    ) -> None:
        # Loop bounds are resolved here, at the composition boundary, so the agent
        # never does blocking config file I/O from inside an async turn.
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        set_config("agent.max_tool_iterations", "7")
        set_config("agent.max_history_chars", "1234")
        config = AgentConfig(**{**_BASE_CONFIG, "cwd": str(tmp_path)})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            agent = await provider.create_agent(config)
        assert agent._max_tool_iterations == 7  # pyright: ignore[reportPrivateUsage]
        assert agent._max_history_chars == 1234  # pyright: ignore[reportPrivateUsage]


class TestEnhancedCredentialResolution:
    @pytest.mark.asyncio
    async def test_api_key_from_credentials_env_var(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_CUSTOM_KEY", "sk-custom")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        creds = {"api_key_env": "MY_CUSTOM_KEY"}
        config = AgentConfig(**{**_BASE_CONFIG, "credentials": creds})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-custom"

    @pytest.mark.asyncio
    async def test_credentials_env_var_takes_precedence_over_default(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MY_CUSTOM_KEY", "sk-custom")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-default")
        creds = {"api_key_env": "MY_CUSTOM_KEY"}
        config = AgentConfig(**{**_BASE_CONFIG, "credentials": creds})
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "sk-custom"

    @pytest.mark.asyncio
    async def test_localhost_placeholder_key(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = AgentConfig(
            **{**_BASE_CONFIG, "api_key": None, "base_url": "http://localhost:11434/v1"}
        )
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "not-needed"

    @pytest.mark.asyncio
    async def test_127_0_0_1_placeholder_key(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = AgentConfig(
            **{**_BASE_CONFIG, "api_key": None, "base_url": "http://127.0.0.1:8080/v1"}
        )
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["api_key"] == "not-needed"

    @pytest.mark.asyncio
    async def test_remote_url_still_raises_without_key(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = AgentConfig(**{**_BASE_CONFIG, "api_key": None, "base_url": "https://api.example.com"})
        with pytest.raises(ProviderAuthError):
            await provider.create_agent(config)

    @pytest.mark.asyncio
    async def test_default_headers_passed_to_client(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(
            **{**_BASE_CONFIG, "credentials": {"default_headers": {"X-Custom": "val"}}}
        )
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["default_headers"] == {"X-Custom": "val"}

    @pytest.mark.asyncio
    async def test_no_default_headers_passes_none(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**_BASE_CONFIG)
        with patch("squadron.providers.openai.provider.AsyncOpenAI") as mock_cls:
            mock_cls.return_value = MagicMock()
            await provider.create_agent(config)
        _, kwargs = mock_cls.call_args
        assert kwargs["default_headers"] is None


class TestValidateCredentials:
    @pytest.mark.asyncio
    async def test_returns_true_when_key_set(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-present")
        result = await provider.validate_credentials()
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_no_env(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        result = await provider.validate_credentials()
        assert result is False

    @pytest.mark.asyncio
    async def test_never_raises(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        # Should not raise even when openai is importable but key is absent
        result = await provider.validate_credentials()
        assert isinstance(result, bool)


class TestStreamOptions:
    """Slice 931: stream_options goes out unless a profile opts out."""

    @staticmethod
    async def _create_kwargs(
        provider: OpenAICompatibleProvider, credentials: dict[str, object]
    ) -> dict[str, object]:
        from openai import omit

        from squadron.core.models import Message, MessageType

        from .conftest import text_chunk

        async def _stream() -> AsyncIterator[object]:
            yield text_chunk("hi")

        client = MagicMock()
        client.chat.completions.create = AsyncMock(return_value=_stream())
        config = AgentConfig(**{**_BASE_CONFIG, "credentials": credentials})
        with patch("squadron.providers.openai.provider.AsyncOpenAI", return_value=client):
            agent = await provider.create_agent(config)
        message = Message(sender="u", recipients=["agent"], content="q", message_type=MessageType.chat)
        async for _ in agent.handle_message(message):
            pass
        kwargs: dict[str, object] = client.chat.completions.create.call_args.kwargs
        return {k: v for k, v in kwargs.items() if v is not omit}

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("profile_name", "sends"),
        [(ProfileName.GEMINI, False), (ProfileName.OPENROUTER, True)],
    )
    async def test_profile_decides_stream_options(
        self,
        provider: OpenAICompatibleProvider,
        monkeypatch: pytest.MonkeyPatch,
        profile_name: str,
        sends: bool,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        credentials = profile_credentials(BUILT_IN_PROFILES[profile_name])
        credentials["api_key_env"] = "OPENAI_API_KEY"

        kwargs = await self._create_kwargs(provider, credentials)

        if sends:
            assert kwargs["stream_options"] == {"include_usage": True}
        else:
            assert "stream_options" not in kwargs

    @pytest.mark.asyncio
    async def test_agent_without_profile_sends_stream_options(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The daemon's request-body agents carry no profile keys at all."""
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")

        kwargs = await self._create_kwargs(provider, {})

        assert kwargs["stream_options"] == {"include_usage": True}
        # Apart from stream_options, the request is today's.
        assert set(kwargs) == {"model", "messages", "stream", "extra_body", "stream_options"}

    @pytest.mark.asyncio
    async def test_non_bool_flag_rejected(
        self, provider: OpenAICompatibleProvider, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
        config = AgentConfig(**{**_BASE_CONFIG, "credentials": {"sends_stream_usage": "no"}})
        with (
            patch("squadron.providers.openai.provider.AsyncOpenAI"),
            pytest.raises(ProviderError, match="sends_stream_usage must be a bool"),
        ):
            await provider.create_agent(config)
