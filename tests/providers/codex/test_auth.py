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

    def test_api_key_alone_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        # The Codex runtime ignores OPENAI_API_KEY (slice 129 Task 1).
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        strategy = OAuthFileStrategy(auth_file=missing)
        with pytest.raises(ProviderAuthError, match="No credentials found"):
            asyncio.run(strategy.get_credentials())

    @pytest.mark.usefixtures("_no_api_key")
    def test_no_credentials_raises(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        strategy = OAuthFileStrategy(auth_file=missing)
        with pytest.raises(ProviderAuthError, match="No credentials found"):
            asyncio.run(strategy.get_credentials())

    def test_auth_file_used_when_api_key_also_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-ignored")
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

    def test_invalid_with_api_key_only(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).is_valid() is False

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
        strategy = OAuthFileStrategy(auth_file=auth_file)
        assert strategy.active_source == "~/.codex/auth.json"

    def test_api_key_is_not_a_source(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).active_source is None

    @pytest.mark.usefixtures("_no_api_key")
    def test_no_source(self, tmp_path: pytest.TempPathFactory) -> None:
        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        assert OAuthFileStrategy(auth_file=missing).active_source is None

    def test_auth_file_source_when_api_key_also_set(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: pytest.TempPathFactory,
    ) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text("{}")
        strategy = OAuthFileStrategy(auth_file=auth_file)
        assert strategy.active_source == "~/.codex/auth.json"


class TestSetupHint:
    def test_returns_actionable_message(self) -> None:
        strategy = OAuthFileStrategy()
        assert "sq auth login openai-oauth" in strategy.setup_hint
        assert "OPENAI_API_KEY" not in strategy.setup_hint


class TestRefreshIfNeeded:
    def test_is_noop(self) -> None:
        asyncio.run(OAuthFileStrategy().refresh_if_needed())


class TestInteractiveLogin:
    def test_is_interactive_login(self) -> None:
        from squadron.providers.auth import InteractiveLogin

        assert isinstance(OAuthFileStrategy(), InteractiveLogin)

    def test_login_delegates(self) -> None:
        from unittest.mock import AsyncMock, patch

        notify: list[str] = []
        with patch("squadron.providers.codex.login.login", new=AsyncMock()) as delegate:
            asyncio.run(OAuthFileStrategy().login(device_code=True, timeout_s=12, notify=notify.append))
        delegate.assert_awaited_once_with(device_code=True, timeout_s=12, notify=notify.append)

    def test_logout_delegates(self) -> None:
        from unittest.mock import AsyncMock, patch

        with patch("squadron.providers.codex.login.logout", new=AsyncMock()) as delegate:
            asyncio.run(OAuthFileStrategy().logout())
        delegate.assert_awaited_once()

    def test_account_summary_delegates_when_valid(self, tmp_path: pytest.TempPathFactory) -> None:
        from unittest.mock import AsyncMock, patch

        auth_file = tmp_path / "auth.json"  # type: ignore[operator]
        auth_file.write_text("{}")
        with patch(
            "squadron.providers.codex.login.account_summary",
            new=AsyncMock(return_value="you@example.com, plus"),
        ):
            summary = asyncio.run(OAuthFileStrategy(auth_file=auth_file).account_summary())
        assert summary == "you@example.com, plus"

    def test_invalid_strategy_skips_the_runtime(self, tmp_path: pytest.TempPathFactory) -> None:
        from unittest.mock import AsyncMock, patch

        missing = tmp_path / "nonexistent" / "auth.json"  # type: ignore[operator]
        with patch("squadron.providers.codex.login.account_summary", new=AsyncMock()) as delegate:
            assert asyncio.run(OAuthFileStrategy(auth_file=missing).account_summary()) is None
        delegate.assert_not_awaited()
