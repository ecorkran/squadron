"""Tests for sq models command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.models.aliases import BUILT_IN_ALIASES

runner = CliRunner()


def test_models_contains_builtins() -> None:
    """sq models shows built-in aliases."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "opus" in result.output
    assert "sonnet" in result.output
    assert "gpt54-nano" in result.output


def test_models_list_is_alias_for_bare() -> None:
    """sq models list produces the same output as sq models."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        bare = runner.invoke(app, ["models"])
        listed = runner.invoke(app, ["models", "list"])
    assert bare.exit_code == 0
    assert listed.exit_code == 0
    assert "opus" in listed.output
    assert "Alias" in listed.output


def test_models_shows_user_tag(tmp_path: Path) -> None:
    """User alias shows (user) tag in output."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases]\n"
        'deepseek = { profile = "openrouter",'
        ' model = "deepseek/deepseek-r2" }\n'
    )

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "deepseek" in result.output
    assert "(user)" in result.output


def test_models_shows_user_override(tmp_path: Path) -> None:
    """User alias that overrides built-in shows (user override)."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        '[aliases]\nopus = { profile = "openrouter",'
        ' model = "anthropic/claude-opus" }\n'
    )

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "(user override)" in result.output


def test_models_output_is_tabular() -> None:
    """Output is formatted as a table with columns."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    assert "Alias" in result.output
    assert "Profile" in result.output
    assert "Model ID" in result.output


def test_models_profile_requires_base_url() -> None:
    """--profile with no base_url configured shows error."""
    result = runner.invoke(app, ["models", "--profile", "nonexistent"])
    assert result.exit_code != 0


# --- T4: Built-in metadata tests ---

_SDK_ALIASES = {"opus", "sonnet", "haiku"}
_API_ALIASES_WITH_PRICING = {
    "gpt54",
    "gpt54-mini",
    "gpt54-nano",
    "codex",
    "gemini",
    "flash3",
    "kimi25",
    "minimax",
    "glm5",
}


def test_builtin_aliases_have_metadata() -> None:
    """All built-in aliases have private and cost_tier keys."""
    for name, alias in BUILT_IN_ALIASES.items():
        assert "private" in alias, f"{name} missing 'private'"
        assert "cost_tier" in alias, f"{name} missing 'cost_tier'"


def test_builtin_sdk_aliases_have_no_pricing() -> None:
    """SDK aliases (opus, sonnet, haiku) do NOT have pricing."""
    for name in _SDK_ALIASES:
        assert name in BUILT_IN_ALIASES
        assert "pricing" not in BUILT_IN_ALIASES[name], (
            f"{name} should not have pricing"
        )


def test_builtin_api_aliases_have_pricing() -> None:
    """API aliases have pricing with input and output fields."""
    for name in _API_ALIASES_WITH_PRICING:
        alias = BUILT_IN_ALIASES[name]
        assert "pricing" in alias, f"{name} missing 'pricing'"
        pricing = alias["pricing"]
        assert "input" in pricing, f"{name} pricing missing 'input'"
        assert "output" in pricing, f"{name} pricing missing 'output'"
