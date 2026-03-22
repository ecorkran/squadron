"""Tests for the models CLI command."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
from typer.testing import CliRunner

from squadron.cli.app import app

_PATCH_TARGET = "squadron.cli.commands.models.httpx.AsyncClient"


def _invoke(runner: CliRunner, *args: str):  # type: ignore[no-untyped-def]
    return runner.invoke(app, ["models", *args])


def _make_models_response(*model_ids: str) -> dict:  # type: ignore[type-arg]
    return {
        "object": "list",
        "data": [{"id": mid, "object": "model"} for mid in model_ids],
    }


def _mock_client(response: MagicMock) -> AsyncMock:
    client = AsyncMock()
    client.get = AsyncMock(return_value=response)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


class TestModelsCommand:
    def test_models_displays_model_list(self, cli_runner: CliRunner) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = _make_models_response("llama3", "mistral")
        mock_response.raise_for_status = MagicMock()

        with patch(_PATCH_TARGET, return_value=_mock_client(mock_response)):
            result = _invoke(cli_runner, "--base-url", "http://localhost:11434/v1")

        assert result.exit_code == 0, result.output
        assert "llama3" in result.output
        assert "mistral" in result.output

    def test_models_with_profile(self, cli_runner: CliRunner) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = _make_models_response("gemma")
        mock_response.raise_for_status = MagicMock()
        mock_client = _mock_client(mock_response)

        with patch(_PATCH_TARGET, return_value=mock_client):
            result = _invoke(cli_runner, "--profile", "local")

        assert result.exit_code == 0, result.output
        # Verify the correct URL was called (local profile base_url + /models)
        call_args = mock_client.get.call_args[0][0]
        assert "localhost:11434" in call_args
        assert call_args.endswith("/models")

    def test_models_connection_error(self, cli_runner: CliRunner) -> None:
        err_client = AsyncMock()
        err_client.get = AsyncMock(side_effect=httpx.ConnectError("connection refused"))
        err_client.__aenter__ = AsyncMock(return_value=err_client)
        err_client.__aexit__ = AsyncMock(return_value=False)

        with patch(_PATCH_TARGET, return_value=err_client):
            result = _invoke(cli_runner, "--base-url", "http://localhost:11434/v1")

        assert result.exit_code == 1
        assert "connect" in result.output.lower() or "error" in result.output.lower()

    def test_models_bare_shows_aliases(self, cli_runner: CliRunner) -> None:
        """sq models with no flags shows alias table."""
        result = _invoke(cli_runner)
        assert result.exit_code == 0
        assert "Alias" in result.output
        assert "opus" in result.output
