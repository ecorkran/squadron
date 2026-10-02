"""Tests for CLI auth commands (auth login, auth status)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_auth_login_valid_key(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """When env var is set, output shows ✓ and source."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abcdef1234567890")
    result = runner.invoke(app, ["auth", "login", "openai"])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert "authenticated" in result.output
    assert "OPENAI_API_KEY" in result.output


def test_auth_login_missing_key(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """When env var is not set, output shows ✗ and setup hint."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = runner.invoke(app, ["auth", "login", "openai"])
    assert result.exit_code == 0
    assert "✗" in result.output
    assert "not authenticated" in result.output
    assert "OPENAI_API_KEY" in result.output  # setup hint


def test_auth_login_sdk_session(runner: CliRunner) -> None:
    """SDK profile uses session strategy — always valid."""
    result = runner.invoke(app, ["auth", "login", "sdk"])
    assert result.exit_code == 0
    assert "✓" in result.output
    assert "authenticated" in result.output


def test_auth_login_unknown_profile(runner: CliRunner) -> None:
    """Unknown profile produces error message and exit code 1."""
    result = runner.invoke(app, ["auth", "login", "nonexistent-profile"])
    assert result.exit_code == 1
    assert "nonexistent-profile" in result.output or "Error" in result.output


def test_auth_status_shows_all_profiles(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status output contains all built-in profile names."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "openai" in result.output
    assert "openrouter" in result.output
    assert "local" in result.output
    assert "gemini" in result.output
    assert "openai-oauth" in result.output
    assert "sdk" in result.output


def test_auth_status_valid_and_missing(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Status shows ✓ for set keys and ✗ for missing keys."""
    monkeypatch.setenv("OPENAI_API_KEY", "sk-testkey")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "✓" in result.output  # at least one valid
    assert "authenticated" in result.output


def test_auth_status_no_string_dispatch(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    """Auth status output includes openai-oauth profile correctly."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    result = runner.invoke(app, ["auth", "status"])
    assert result.exit_code == 0
    assert "openai-oauth" in result.output
    assert "oauth" in result.output


# --- slice 129: interactive login ---

_LOGIN = "squadron.providers.codex.login"


def _write_codex_auth_file() -> None:
    from pathlib import Path

    auth_file = Path.home() / ".codex" / "auth.json"
    auth_file.parent.mkdir(parents=True, exist_ok=True)
    auth_file.write_text("{}")


def test_interactive_login_success_prints_account(runner: CliRunner) -> None:
    from unittest.mock import AsyncMock, patch

    async def fake_login(*, device_code: bool, timeout_s: float, notify: object) -> None:
        notify("Sign in at: https://auth.example/x")  # type: ignore[operator]
        _write_codex_auth_file()

    with (
        patch(f"{_LOGIN}.login", side_effect=fake_login),
        patch(f"{_LOGIN}.account_summary", new=AsyncMock(return_value="you@example.com, plus")),
    ):
        result = runner.invoke(app, ["auth", "login", "openai-oauth"])
    assert result.exit_code == 0, result.output
    assert "Sign in at: https://auth.example/x" in result.output
    assert "✓ openai-oauth: authenticated (you@example.com, plus)" in result.output


def test_interactive_login_passes_device_code_and_default_timeout(runner: CliRunner) -> None:
    from unittest.mock import AsyncMock, patch

    with (
        patch(f"{_LOGIN}.login", new=AsyncMock()) as login,
        patch(f"{_LOGIN}.account_summary", new=AsyncMock(return_value=None)),
    ):
        result = runner.invoke(app, ["auth", "login", "openai-oauth", "--device-code"])
    assert result.exit_code == 0, result.output
    kwargs = login.await_args.kwargs
    assert kwargs["device_code"] is True
    assert kwargs["timeout_s"] == 300  # codex.login_timeout_s default


def test_interactive_login_timeout_override(runner: CliRunner) -> None:
    from unittest.mock import AsyncMock, patch

    with (
        patch(f"{_LOGIN}.login", new=AsyncMock()) as login,
        patch(f"{_LOGIN}.account_summary", new=AsyncMock(return_value=None)),
    ):
        result = runner.invoke(app, ["auth", "login", "openai-oauth", "--timeout", "42"])
    assert result.exit_code == 0, result.output
    assert login.await_args.kwargs["timeout_s"] == 42


@pytest.mark.parametrize(
    "message", ["Codex login failed: access denied", "Codex login timed out after 300 s"]
)
def test_interactive_login_failure_exits_nonzero(runner: CliRunner, message: str) -> None:
    from unittest.mock import AsyncMock, patch

    from squadron.providers.errors import ProviderError

    with patch(f"{_LOGIN}.login", new=AsyncMock(side_effect=ProviderError(message))):
        result = runner.invoke(app, ["auth", "login", "openai-oauth"])
    assert result.exit_code == 1
    assert message in result.output


def test_login_success_without_account_details_still_succeeds(runner: CliRunner) -> None:
    from unittest.mock import AsyncMock, patch

    async def fake_login(**_kwargs: object) -> None:
        _write_codex_auth_file()

    with (
        patch(f"{_LOGIN}.login", side_effect=fake_login),
        patch(f"{_LOGIN}.account_summary", new=AsyncMock(return_value=None)),
    ):
        result = runner.invoke(app, ["auth", "login", "openai-oauth"])
    assert result.exit_code == 0, result.output
    assert "✓ openai-oauth: authenticated (~/.codex/auth.json)" in result.output


def test_device_code_on_non_interactive_profile_errors(runner: CliRunner) -> None:
    result = runner.invoke(app, ["auth", "login", "sdk", "--device-code"])
    assert result.exit_code == 1
    assert "does not support interactive login" in result.output


def test_non_interactive_profile_output_unchanged(
    runner: CliRunner, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-abcdef1234567890")
    result = runner.invoke(app, ["auth", "login", "openai"])
    assert result.exit_code == 0
    assert result.output == "✓ openai: authenticated (OPENAI_API_KEY)\n"


def test_interactive_login_extra_absent_prints_install_command(runner: CliRunner) -> None:
    from unittest.mock import patch

    from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND

    with patch("squadron.providers.codex.runtime._module_available", return_value=False):
        result = runner.invoke(app, ["auth", "login", "openai-oauth"])
    assert result.exit_code == 1
    assert CODEX_INSTALL_COMMAND in result.output
    assert "Traceback" not in result.output
