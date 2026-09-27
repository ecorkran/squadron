"""Tests for the model alias registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.models.aliases import (
    get_all_aliases,
    load_builtin_aliases,
    load_user_aliases,
    model_max_output_tokens,
    resolve_model_alias,
)

# ---------------------------------------------------------------------------
# resolve_model_alias — built-in aliases
# ---------------------------------------------------------------------------


def test_resolve_opus() -> None:
    """opus resolves to claude-opus-5-5 on sdk profile."""
    model, profile = resolve_model_alias("opus")
    assert model == "claude-opus-5-5"
    assert profile == "sdk"


def test_resolve_gpt54_nano() -> None:
    """gpt54-nano resolves to gpt-5.4-nano on openai profile."""
    model, profile = resolve_model_alias("gpt54-nano")
    assert model == "gpt-5.4-nano"
    assert profile == "openai"


def test_resolve_unknown_passthrough() -> None:
    """Unknown model name passes through unchanged with None profile."""
    model, profile = resolve_model_alias("unknown-model")
    assert model == "unknown-model"
    assert profile is None


def test_resolve_sonnet() -> None:
    """sonnet resolves to claude-sonnet-5 on sdk profile."""
    model, profile = resolve_model_alias("sonnet")
    assert model == "claude-sonnet-5"
    assert profile == "sdk"


def test_resolve_codex() -> None:
    """codex resolves to gpt-5.3-codex on openai profile (unchanged)."""
    model, profile = resolve_model_alias("codex")
    assert model == "gpt-5.3-codex"
    assert profile == "openai"


def test_resolve_codex_agent() -> None:
    """codex-agent resolves to gpt-5.3-codex on openai-oauth profile."""
    model, profile = resolve_model_alias("codex-agent")
    assert model == "gpt-5.3-codex"
    assert profile == "openai-oauth"


def test_resolve_codex_spark() -> None:
    """codex-spark resolves to gpt-5.3-codex-spark on openai-oauth profile."""
    model, profile = resolve_model_alias("codex-spark")
    assert model == "gpt-5.3-codex-spark"
    assert profile == "openai-oauth"


# ---------------------------------------------------------------------------
# User alias overrides
# ---------------------------------------------------------------------------


def test_user_alias_overrides_builtin(tmp_path: Path) -> None:
    """User alias overrides a built-in alias by name."""
    toml_content = """
[aliases]
opus = { profile = "openrouter", model = "anthropic/claude-opus-custom" }
"""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(toml_content)

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        model, profile = resolve_model_alias("opus")
        assert model == "anthropic/claude-opus-custom"
        assert profile == "openrouter"


def test_user_alias_adds_new_entry(tmp_path: Path) -> None:
    """User alias adds a new entry not in built-ins."""
    toml_content = """
[aliases]
kimi-custom = { profile = "openrouter", model = "moonshotai/kimi-k2.7-code" }
"""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(toml_content)

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        model, profile = resolve_model_alias("kimi-custom")
        assert model == "moonshotai/kimi-k2.7-code"
        assert profile == "openrouter"


# ---------------------------------------------------------------------------
# load_user_aliases — edge cases
# ---------------------------------------------------------------------------


def test_missing_models_toml_returns_empty() -> None:
    """Missing models.toml returns empty dict without error."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=Path("/nonexistent/models.toml"),
    ):
        aliases = load_user_aliases()
        assert aliases == {}


def test_malformed_toml_raises_error(tmp_path: Path) -> None:
    """Malformed TOML file raises ValueError with helpful message."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text("this is not valid toml [[[")

    with (
        patch("squadron.models.aliases.models_toml_path", return_value=toml_file),
        pytest.raises(ValueError, match="Invalid TOML"),
    ):
        load_user_aliases()


def test_toml_without_aliases_section(tmp_path: Path) -> None:
    """TOML file without [aliases] section returns empty dict."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text("[settings]\nfoo = 'bar'\n")

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = load_user_aliases()
        assert aliases == {}


# ---------------------------------------------------------------------------
# get_all_aliases — merged view
# ---------------------------------------------------------------------------


def test_get_all_aliases_includes_builtins(tmp_path: Path) -> None:
    """get_all_aliases returns all built-in aliases when no user file."""
    with patch(
        "squadron.models.aliases.models_toml_path",
        return_value=tmp_path / "models.toml",
    ):
        aliases = get_all_aliases()
        assert "opus" in aliases
        assert "sonnet" in aliases
        assert "gpt54-nano" in aliases
        assert len(aliases) >= len(load_builtin_aliases())


def test_get_all_aliases_merges_user(tmp_path: Path) -> None:
    """get_all_aliases merges user aliases with built-ins."""
    toml_content = """
[aliases]
kimi-custom = { profile = "openrouter", model = "moonshotai/kimi-k2.7-code" }
"""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(toml_content)

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = get_all_aliases()
        assert "kimi-custom" in aliases
        assert "opus" in aliases  # built-in still present
        assert aliases["kimi-custom"]["model"] == "moonshotai/kimi-k2.7-code"


# ---------------------------------------------------------------------------
# load_builtin_aliases — data/ TOML source
# ---------------------------------------------------------------------------


def testload_builtin_aliases_nonempty() -> None:
    """load_builtin_aliases returns a non-empty dict."""
    aliases = load_builtin_aliases()
    assert len(aliases) > 0


def testload_builtin_aliases_contains_claude() -> None:
    """load_builtin_aliases contains opus, sonnet, haiku."""
    aliases = load_builtin_aliases()
    assert "opus" in aliases
    assert "sonnet" in aliases
    assert "haiku" in aliases


# ---------------------------------------------------------------------------
# max_output_tokens (slice 924 D4)
# ---------------------------------------------------------------------------


def _user_aliases(tmp_path: Path, body: str) -> Path:
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(f'[aliases.budgeted]\nprofile = "openrouter"\nmodel = "x/y"\n{body}\n')
    return toml_file


def test_max_output_tokens_is_read_back(tmp_path: Path) -> None:
    toml_file = _user_aliases(tmp_path, "max_output_tokens = 4096")

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        assert model_max_output_tokens("budgeted") == 4096


@pytest.mark.parametrize("raw", ["0", "-1", '"4096"', "4096.0", "true"])
def test_invalid_max_output_tokens_is_rejected(
    tmp_path: Path, raw: str, caplog: pytest.LogCaptureFixture
) -> None:
    toml_file = _user_aliases(tmp_path, f"max_output_tokens = {raw}")

    with (
        patch("squadron.models.aliases.models_toml_path", return_value=toml_file),
        caplog.at_level("WARNING", logger="squadron.models.aliases"),
    ):
        assert model_max_output_tokens("budgeted") is None
    assert any(
        "Skipping max_output_tokens for alias 'budgeted'" in r.getMessage() for r in caplog.records
    )


def test_max_output_tokens_is_none_when_unset(tmp_path: Path) -> None:
    toml_file = _user_aliases(tmp_path, "")

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        assert model_max_output_tokens("budgeted") is None
        assert model_max_output_tokens("no-such-alias") is None
        assert model_max_output_tokens(None) is None


def test_shipped_models_toml_loads_with_budgets() -> None:
    """Slice 924 B5: the built-in file parses and carries OpenRouter budgets."""
    builtin = load_builtin_aliases()

    budgets = [alias.get("max_output_tokens") for alias in builtin.values()]
    assert any(budget is not None for budget in budgets)
    assert all(budget is None or budget >= 1 for budget in budgets)
