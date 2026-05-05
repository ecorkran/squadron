"""Tests for --profile flag on the spawn command."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.cli.commands.spawn import _resolve_profile
from tests.cli.conftest import make_agent_dict


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["spawn", *args])


class TestResolveProfile:
    def test_profile_sets_provider_and_base_url(self) -> None:
        result = _resolve_profile("openrouter", None, None)
        assert result["provider"] == "openai"
        assert result["base_url"] == "https://openrouter.ai/api/v1"

    def test_profile_sets_agent_type_api(self) -> None:
        result = _resolve_profile("openrouter", None, None)
        assert result["agent_type"] == "api"

    def test_profile_includes_credentials(self) -> None:
        result = _resolve_profile("openrouter", None, None)
        creds = result["credentials"]
        assert "api_key_env" in creds
        assert creds["api_key_env"] == "OPENROUTER_API_KEY"
        assert "default_headers" in creds

    def test_cli_provider_overrides_profile(self) -> None:
        result = _resolve_profile("openrouter", "custom-provider", None)
        assert result["provider"] == "custom-provider"

    def test_cli_base_url_overrides_profile(self) -> None:
        result = _resolve_profile("local", None, "http://other:11434/v1")
        assert result["base_url"] == "http://other:11434/v1"

    def test_local_profile_no_api_key_env(self) -> None:
        result = _resolve_profile("local", None, None)
        assert "api_key_env" not in result["credentials"]

    def test_unknown_profile_raises_key_error(self) -> None:
        with pytest.raises(KeyError, match="nonexistent"):
            _resolve_profile("nonexistent", None, None)


class TestSpawnProfileFlag:
    def test_profile_sets_request_data(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.spawn.return_value = make_agent_dict(
            "bot", agent_type="api", provider="openai"
        )
        result = _invoke(cli_runner, "--name", "bot", "--profile", "openrouter", "--model", "x")
        assert result.exit_code == 0, result.output
        call_kwargs = patch_daemon_client.spawn.call_args[0][0]
        assert call_kwargs["provider"] == "openai"
        assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"
        assert call_kwargs["agent_type"] == "api"

    def test_profile_includes_credentials_in_request(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.spawn.return_value = make_agent_dict("bot", agent_type="api")
        result = _invoke(cli_runner, "--name", "bot", "--profile", "openrouter", "--model", "x")
        assert result.exit_code == 0, result.output
        call_kwargs = patch_daemon_client.spawn.call_args[0][0]
        assert "credentials" in call_kwargs
        assert call_kwargs["credentials"]["api_key_env"] == "OPENROUTER_API_KEY"

    def test_profile_cli_base_url_overrides(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        patch_daemon_client.spawn.return_value = make_agent_dict("bot", agent_type="api")
        result = _invoke(
            cli_runner,
            "--name",
            "bot",
            "--profile",
            "local",
            "--base-url",
            "http://other:11434/v1",
            "--model",
            "x",
        )
        assert result.exit_code == 0, result.output
        call_kwargs = patch_daemon_client.spawn.call_args[0][0]
        assert call_kwargs["base_url"] == "http://other:11434/v1"

    def test_profile_unknown_exits_with_error(
        self, cli_runner: CliRunner, patch_daemon_client: MagicMock
    ) -> None:
        result = _invoke(cli_runner, "--name", "bot", "--profile", "nonexistent")
        assert result.exit_code == 1
        assert "nonexistent" in result.output

    def test_no_profile_unchanged(self, cli_runner: CliRunner, patch_daemon_client: MagicMock) -> None:
        patch_daemon_client.spawn.return_value = make_agent_dict("bot")
        result = _invoke(cli_runner, "--name", "bot")
        assert result.exit_code == 0, result.output
        call_kwargs = patch_daemon_client.spawn.call_args[0][0]
        assert call_kwargs["agent_type"] == "sdk"
        assert call_kwargs["provider"] == "sdk"
