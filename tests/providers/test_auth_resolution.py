"""Tests for resolve_auth_strategy factory function."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from squadron.core.models import AgentConfig
from squadron.providers.auth import (
    ApiKeyStrategy,
    resolve_auth_strategy,
    resolve_auth_strategy_for_profile,
)
from squadron.providers.errors import ProviderAuthError
from squadron.providers.profiles import get_profile


def _make_config(**kwargs: object) -> AgentConfig:
    defaults: dict[str, object] = {
        "name": "test-agent",
        "agent_type": "api",
        "provider": "openai",
    }
    defaults.update(kwargs)
    return AgentConfig(**defaults)  # type: ignore[arg-type]


def test_resolve_api_key_strategy_default() -> None:
    """No profile → returns ApiKeyStrategy."""
    config = _make_config()
    strategy = resolve_auth_strategy(config, profile=None)
    assert isinstance(strategy, ApiKeyStrategy)


def test_resolve_api_key_strategy_with_profile() -> None:
    """Profile with auth_type='api_key' → ApiKeyStrategy using profile's api_key_env."""
    config = _make_config()
    profile = SimpleNamespace(auth_type="api_key", api_key_env="MY_PROFILE_KEY")
    strategy = resolve_auth_strategy(config, profile=profile)  # type: ignore[arg-type]
    assert isinstance(strategy, ApiKeyStrategy)
    # Verify the env_var was taken from the profile
    assert strategy._env_var == "MY_PROFILE_KEY"


def test_resolve_unknown_auth_type_raises() -> None:
    """Profile with auth_type='unknown' → ProviderAuthError with descriptive message."""
    config = _make_config()
    profile = SimpleNamespace(auth_type="unknown", api_key_env=None)
    with pytest.raises(ProviderAuthError, match="Unknown auth_type 'unknown'"):
        resolve_auth_strategy(config, profile=profile)  # type: ignore[arg-type]


def test_resolve_no_profile_uses_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """Config with credentials api_key_env and no profile → strategy uses that env var."""  # noqa: E501
    monkeypatch.setenv("MY_KEY", "resolved-from-credentials")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = _make_config(credentials={"api_key_env": "MY_KEY"})
    strategy = resolve_auth_strategy(config, profile=None)
    assert isinstance(strategy, ApiKeyStrategy)
    assert strategy._env_var == "MY_KEY"

    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "resolved-from-credentials"}


# ---------------------------------------------------------------------------
# from_config classmethod tests
# ---------------------------------------------------------------------------


class TestFromConfig:
    def test_from_config_with_profile_env_var(self) -> None:
        config = _make_config()
        profile = SimpleNamespace(
            auth_type="api_key", api_key_env="CUSTOM_KEY", base_url=None
        )
        strategy = ApiKeyStrategy.from_config(config, profile=profile)  # type: ignore[arg-type]
        assert isinstance(strategy, ApiKeyStrategy)
        assert strategy._env_var == "CUSTOM_KEY"

    def test_from_config_with_explicit_key(self) -> None:
        config = _make_config(api_key="sk-explicit")
        strategy = ApiKeyStrategy.from_config(config, profile=None)
        assert strategy._explicit_key == "sk-explicit"

    def test_from_config_with_localhost(self) -> None:
        config = _make_config(base_url="http://localhost:11434/v1")
        strategy = ApiKeyStrategy.from_config(config, profile=None)
        assert strategy._is_localhost() is True


# ---------------------------------------------------------------------------
# active_source and setup_hint tests
# ---------------------------------------------------------------------------


class TestActiveSource:
    def test_returns_env_var_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        strategy = ApiKeyStrategy(env_var="OPENROUTER_API_KEY")
        assert strategy.active_source == "OPENROUTER_API_KEY"

    def test_returns_fallback_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        strategy = ApiKeyStrategy()
        assert strategy.active_source == "OPENAI_API_KEY"

    def test_returns_explicit(self) -> None:
        strategy = ApiKeyStrategy(explicit_key="sk-explicit")
        assert strategy.active_source == "explicit"

    def test_returns_localhost(self) -> None:
        strategy = ApiKeyStrategy(base_url="http://localhost:8080")
        assert strategy.active_source == "localhost"

    def test_returns_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        strategy = ApiKeyStrategy()
        assert strategy.active_source is None


class TestSetupHint:
    def test_returns_actionable_message(self) -> None:
        strategy = ApiKeyStrategy(env_var="OPENROUTER_API_KEY")
        assert "OPENROUTER_API_KEY" in strategy.setup_hint

    def test_uses_fallback_when_no_env_var(self) -> None:
        strategy = ApiKeyStrategy()
        assert "OPENAI_API_KEY" in strategy.setup_hint


# ---------------------------------------------------------------------------
# resolve_auth_strategy_for_profile tests
# ---------------------------------------------------------------------------


class TestResolveForProfile:
    def test_openai_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        profile = get_profile("openai")
        strategy = resolve_auth_strategy_for_profile(profile)
        assert strategy.is_valid() is True

    def test_sdk_profile(self) -> None:
        profile = get_profile("sdk")
        strategy = resolve_auth_strategy_for_profile(profile)
        assert strategy.is_valid() is True
