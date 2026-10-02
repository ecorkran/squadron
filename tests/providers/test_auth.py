"""Tests for AuthStrategy protocol and ApiKeyStrategy."""

from __future__ import annotations

import pytest

from squadron.providers.auth import ApiKeyStrategy, AuthStrategy
from squadron.providers.errors import ProviderAuthError


def test_explicit_key_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setenv("CUSTOM_KEY", "custom-env-key")
    strategy = ApiKeyStrategy(
        explicit_key="explicit-key",
        env_var="CUSTOM_KEY",
        fallback_env_var="OPENAI_API_KEY",
    )
    result = pytest.importorskip("asyncio").run(strategy.get_credentials())
    assert result == {"api_key": "explicit-key"}


def test_env_var_from_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("CUSTOM_KEY", "profile-key")
    strategy = ApiKeyStrategy(env_var="CUSTOM_KEY")
    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "profile-key"}


def test_env_var_precedence_over_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CUSTOM_KEY", "custom-val")
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-val")
    strategy = ApiKeyStrategy(env_var="CUSTOM_KEY", fallback_env_var="OPENAI_API_KEY")
    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "custom-val"}


def test_fallback_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CUSTOM_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fallback-key")
    strategy = ApiKeyStrategy(env_var="CUSTOM_KEY")
    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "fallback-key"}


def test_localhost_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy(base_url="http://localhost:11434/v1")
    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "not-needed"}


def test_127_0_0_1_placeholder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy(base_url="http://127.0.0.1:8080/v1")
    import asyncio

    result = asyncio.run(strategy.get_credentials())
    assert result == {"api_key": "not-needed"}


def test_no_key_remote_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy(base_url="https://api.example.com")
    import asyncio

    with pytest.raises(ProviderAuthError):
        asyncio.run(strategy.get_credentials())


def test_no_key_no_url_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy()
    import asyncio

    with pytest.raises(ProviderAuthError):
        asyncio.run(strategy.get_credentials())


def test_is_valid_with_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "some-key")
    strategy = ApiKeyStrategy()
    assert strategy.is_valid() is True


def test_is_valid_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy(base_url="https://api.example.com")
    assert strategy.is_valid() is False


def test_is_valid_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    strategy = ApiKeyStrategy(base_url="http://localhost:11434/v1")
    assert strategy.is_valid() is True


def test_refresh_is_noop() -> None:
    import asyncio

    strategy = ApiKeyStrategy(explicit_key="sk-test")
    # Should complete without error
    asyncio.run(strategy.refresh_if_needed())


def test_isinstance_auth_strategy() -> None:
    strategy = ApiKeyStrategy(explicit_key="sk-test")
    assert isinstance(strategy, AuthStrategy)


class _StubInteractive:
    async def login(self, *, device_code: bool, timeout_s: float, notify: object) -> None:
        return None

    async def logout(self) -> None:
        return None

    async def account_summary(self) -> str | None:
        return None


def test_stub_with_all_three_methods_is_interactive_login() -> None:
    from squadron.providers.auth import InteractiveLogin

    assert isinstance(_StubInteractive(), InteractiveLogin)


def test_api_key_strategy_is_not_interactive_login() -> None:
    from squadron.providers.auth import InteractiveLogin

    assert not isinstance(ApiKeyStrategy(), InteractiveLogin)
