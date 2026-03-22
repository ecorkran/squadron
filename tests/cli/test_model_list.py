"""Tests for sq model list command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.app import app

runner = CliRunner()


def test_model_list_contains_builtins() -> None:
    """Output contains built-in aliases."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = runner.invoke(app, ["model", "list"])
    assert result.exit_code == 0
    assert "opus" in result.output
    assert "sonnet" in result.output
    assert "gpt4o" in result.output


def test_model_list_shows_user_tag(tmp_path: Path) -> None:
    """User alias shows (user) tag in output."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        '[aliases]\nkimi25 = { profile = "openrouter",'
        ' model = "moonshotai/kimi-k2" }\n'
    )

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        result = runner.invoke(app, ["model", "list"])
    assert result.exit_code == 0
    assert "kimi25" in result.output
    assert "(user)" in result.output


def test_model_list_shows_user_override(tmp_path: Path) -> None:
    """User alias that overrides built-in shows (user override)."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        '[aliases]\nopus = { profile = "openrouter",'
        ' model = "anthropic/claude-opus" }\n'
    )

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        result = runner.invoke(app, ["model", "list"])
    assert result.exit_code == 0
    assert "(user override)" in result.output


def test_model_list_output_is_tabular() -> None:
    """Output is formatted as a table with columns."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = runner.invoke(app, ["model", "list"])
    assert result.exit_code == 0
    # Table should have header-like content
    assert "Alias" in result.output
    assert "Profile" in result.output
    assert "Model ID" in result.output
