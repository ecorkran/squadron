"""Tests for OAuthFileStrategy credential resolution."""

from __future__ import annotations

import asyncio
import json

import pytest

from squadron.providers.codex.auth import OAuthFileStrategy
from squadron.providers.errors import ProviderAuthError


@pytest.fixture()
def _no_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure OPENAI_API_KEY is not set."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)


class TestGetCredentials:
    @pytest.mark.usefixtures("_no_api_key")
    def test_auth_file_returns_path(self, tmp_path: pytest.TempPathFactory) -> None:
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text(json.dumps({"token": "tok-abc"}))
        strategy = OAuthFileStrategy(auth_file=auth_file)
        result = asyncio.run(strategy.get_credentials())
        assert result == {"auth_file": str(auth_file)}

    @pytest.mark.usefixtures("_no_api_key")
    def test_api_key_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        strategy = OAuthFileStrategy(auth_file=missing)
        result = asyncio.run(strategy.get_credentials())
        assert result == {"api_key": "sk-test-key"}

    @pytest.mark.usefixtures("_no_api_key")
    def test_no_credentials_raises(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        strategy = OAuthFileStrategy(auth_file=missing)
        with pytest.raises(ProviderAuthError, match="No credentials found"):
            asyncio.run(strategy.get_credentials())

    def test_auth_file_preferred_over_api_key(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-should-not-use")
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text(json.dumps({"token": "tok-abc"}))
        strategy = OAuthFileStrategy(auth_file=auth_file)
        result = asyncio.run(strategy.get_credentials())
        assert result == {"auth_file": str(auth_file)}


class TestIsValid:
    @pytest.mark.usefixtures("_no_api_key")
    def test_valid_with_auth_file(self, tmp_path: pytest.TempPathFactory) -> None:
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text("{}")
        assert OAuthFileStrategy(auth_file=auth_file).is_valid() is True

    def test_valid_with_api_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert OAuthFileStrategy().is_valid() is True

    @pytest.mark.usefixtures("_no_api_key")
    def test_invalid_no_sources(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).is_valid() is False


class TestFromConfig:
    def test_returns_working_strategy(self) -> None:
        from squadron.core.models import AgentConfig

        config = AgentConfig(name="test", agent_type="codex", provider="codex")
        strategy = OAuthFileStrategy.from_config(config)
        assert isinstance(strategy, OAuthFileStrategy)


class TestActiveSource:
    @pytest.mark.usefixtures("_no_api_key")
    def test_auth_file_source(self, tmp_path: pytest.TempPathFactory) -> None:
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text("{}")
        assert OAuthFileStrategy(auth_file=auth_file).active_source == "~/.codex/auth.json"

    @pytest.mark.usefixtures("_no_api_key")
    def test_api_key_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).active_source == "OPENAI_API_KEY"

    @pytest.mark.usefixtures("_no_api_key")
    def test_no_source(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).active_source is None

    def test_auth_file_preferred_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text("{}")
        assert OAuthFileStrategy(auth_file=auth_file).active_source == "~/.codex/auth.json"


class TestSetupHint:
    def test_returns_actionable_message(self) -> None:
        strategy = OAuthFileStrategy()
        assert "codex" in strategy.setup_hint.lower()
        assert "OPENAI_API_KEY" in strategy.setup_hint


class TestRefreshIfNeeded:
    def test_is_noop(self) -> None:
        asyncio.run(OAuthFileStrategy().refresh_if_needed())
