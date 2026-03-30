"""Tests for sq models command."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from squadron.cli.app import app
from squadron.models.aliases import (
    load_builtin_aliases,
    estimate_cost,
    load_user_aliases,
)

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


def test_builtin_aliases_have_metadata() -> None:
    """All built-in aliases have private and cost_tier keys."""
    for name, alias in load_builtin_aliases().items():
        assert "private" in alias, f"{name} missing 'private'"
        assert "cost_tier" in alias, f"{name} missing 'cost_tier'"


def test_builtin_sdk_aliases_have_no_pricing() -> None:
    """SDK aliases (opus, sonnet, haiku) do NOT have pricing."""
    builtin = load_builtin_aliases()
    for name in _SDK_ALIASES:
        assert name in builtin
        assert "pricing" not in builtin[name], f"{name} should not have pricing"


def test_builtin_api_aliases_have_pricing() -> None:
    """API aliases have pricing with input and output fields."""
    builtin = load_builtin_aliases()
    api_aliases_with_pricing = {
        name for name, alias in builtin.items() if "pricing" in alias
    }
    for name in api_aliases_with_pricing:
        alias = builtin[name]
        assert "pricing" in alias, f"{name} missing 'pricing'"
        pricing = alias["pricing"]
        assert "input" in pricing, f"{name} pricing missing 'input'"
        assert "output" in pricing, f"{name} pricing missing 'output'"


# --- T6: TOML metadata and pricing parsing tests ---


def test_user_alias_with_metadata(tmp_path: Path) -> None:
    """Full table syntax with private, cost_tier, notes loads all fields."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases.mymodel]\n"
        'profile = "openrouter"\n'
        'model = "test/test-model"\n'
        "private = true\n"
        'cost_tier = "cheap"\n'
        'notes = "Test model"\n'
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    alias = aliases["mymodel"]
    assert alias["profile"] == "openrouter"
    assert alias["model"] == "test/test-model"
    assert alias["private"] is True
    assert alias["cost_tier"] == "cheap"
    assert alias["notes"] == "Test model"


def test_user_alias_with_pricing_full_table(tmp_path: Path) -> None:
    """[aliases.name.pricing] sub-table loads all four pricing fields."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases.mymodel]\n"
        'profile = "openai"\n'
        'model = "test-model"\n'
        "\n"
        "[aliases.mymodel.pricing]\n"
        "input = 5.0\n"
        "output = 25.0\n"
        "cache_read = 0.5\n"
        "cache_write = 6.25\n"
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    pricing = aliases["mymodel"]["pricing"]
    assert pricing["input"] == 5.0
    assert pricing["output"] == 25.0
    assert pricing["cache_read"] == 0.5
    assert pricing["cache_write"] == 6.25


def test_user_alias_with_pricing_inline(tmp_path: Path) -> None:
    """Inline pricing = { input, output } loads correctly."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases]\n"
        'mymodel = { profile = "openai",'
        ' model = "test-model",'
        " pricing = { input = 1.0, output = 2.0 } }\n"
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    pricing = aliases["mymodel"]["pricing"]
    assert pricing["input"] == 1.0
    assert pricing["output"] == 2.0


def test_user_alias_with_partial_pricing(tmp_path: Path) -> None:
    """Pricing with only input/output — cache fields absent, not defaulted."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases.mymodel]\n"
        'profile = "openai"\n'
        'model = "test-model"\n'
        "\n"
        "[aliases.mymodel.pricing]\n"
        "input = 3.0\n"
        "output = 15.0\n"
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    pricing = aliases["mymodel"]["pricing"]
    assert pricing["input"] == 3.0
    assert pricing["output"] == 15.0
    assert "cache_read" not in pricing
    assert "cache_write" not in pricing


def test_user_alias_without_metadata(tmp_path: Path) -> None:
    """Minimal { profile, model } alias has no metadata keys."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        '[aliases]\nsimple = { profile = "openai", model = "test-model" }\n'
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    alias = aliases["simple"]
    assert alias["profile"] == "openai"
    assert alias["model"] == "test-model"
    assert "private" not in alias
    assert "cost_tier" not in alias
    assert "notes" not in alias
    assert "pricing" not in alias


def test_existing_toml_backward_compat(tmp_path: Path) -> None:
    """Old-format models.toml with no metadata returns only profile/model."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        "[aliases]\n"
        'old = { profile = "sdk", model = "claude-opus-4-6" }\n'
        'also_old = { profile = "openai", model = "gpt-5.4" }\n'
    )
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=toml_file,
    ):
        aliases = load_user_aliases()
    for name in ("old", "also_old"):
        alias = aliases[name]
        assert set(alias.keys()) == {"profile", "model"}


# --- T8: estimate_cost() tests ---


def test_estimate_cost_full_pricing() -> None:
    """Known alias with pricing returns correct USD result."""
    pricing = load_builtin_aliases()["kimi25"]["pricing"]
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost("kimi25", input_tokens=1000, output_tokens=500)
    assert result is not None
    expected = 1000 / 1_000_000 * pricing["input"] + 500 / 1_000_000 * pricing["output"]
    assert result == pytest.approx(expected)


def test_estimate_cost_with_cache() -> None:
    """Cache cost is included when cached_tokens > 0 and cache_read present."""
    pricing = load_builtin_aliases()["kimi25"]["pricing"]
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost(
            "kimi25",
            input_tokens=1000,
            output_tokens=500,
            cached_tokens=2000,
        )
    assert result is not None
    expected = (
        1000 / 1_000_000 * pricing["input"]
        + 500 / 1_000_000 * pricing["output"]
        + 2000 / 1_000_000 * pricing["cache_read"]
    )
    assert result == pytest.approx(expected)


def test_estimate_cost_no_pricing() -> None:
    """Subscription model (opus) with no pricing returns None."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost("opus", input_tokens=1000, output_tokens=500)
    assert result is None


def test_estimate_cost_unknown_alias() -> None:
    """Unknown alias returns None."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost("nonexistent", input_tokens=1000, output_tokens=500)
    assert result is None


def test_estimate_cost_zero_tokens() -> None:
    """Zero tokens with pricing returns 0.0, not None."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost("kimi25", input_tokens=0, output_tokens=0)
    assert result == 0.0


def test_estimate_cost_known_model() -> None:
    """Known model with pricing returns a positive float."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        result = estimate_cost("gpt54", input_tokens=1_000_000, output_tokens=1_000_000)
    assert result is not None
    assert result > 0.0


# --- T10: Verbose display and compact default tests ---

_NO_USER_TOML = patch(
    "squadron.models.aliases.models_toml_path",
    return_value=Path("/nonexistent/models.toml"),
)


def test_models_default_compact() -> None:
    """sq models (no flags) does NOT show metadata column headers."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models"])
    assert result.exit_code == 0
    # Compact mode should not contain pricing or metadata indicators
    assert "$2.50" not in result.output
    assert "yes" not in result.output
    assert "sub" not in result.output


def test_models_verbose_shows_metadata_columns() -> None:
    """sq models -v shows metadata column headers (may be truncated by Rich)."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models", "-v"])
    assert result.exit_code == 0
    # Rich may truncate headers; check for partial matches
    assert "Priva" in result.output
    assert "Cost" in result.output
    assert "$/1M" in result.output
    assert "Note" in result.output


def test_models_verbose_shows_pricing_values() -> None:
    """sq models -v shows formatted pricing values."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models", "-v"])
    assert result.exit_code == 0
    # At least one $ price should appear for API models
    assert "$" in result.output
    assert "$2.50" in result.output


def test_models_verbose_shows_subscription_cost_tier() -> None:
    """sq models -v shows 'sub' for SDK aliases."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models", "-v"])
    assert result.exit_code == 0
    assert "sub" in result.output


def test_models_verbose_private_yes() -> None:
    """sq models -v shows 'yes' for built-in aliases (all private=True)."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models", "-v"])
    assert result.exit_code == 0
    assert "yes" in result.output


def test_models_list_verbose() -> None:
    """sq models list -v shows metadata columns (parity with bare)."""
    with _NO_USER_TOML:
        result = runner.invoke(app, ["models", "list", "-v"])
    assert result.exit_code == 0
    assert "Priva" in result.output
    assert "Cost" in result.output
