"""Tests for the model alias registry."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.models.aliases import (
    BUILT_IN_ALIASES,
    get_all_aliases,
    load_user_aliases,
    resolve_model_alias,
)

# ---------------------------------------------------------------------------
# resolve_model_alias — built-in aliases
# ---------------------------------------------------------------------------


def test_resolve_opus() -> None:
    """opus resolves to claude-opus-4-6 on sdk profile."""
    model, profile = resolve_model_alias("opus")
    assert model == "claude-opus-4-6"
    assert profile == "sdk"


def test_resolve_gpt4o() -> None:
    """gpt4o resolves to gpt-4o on openai profile."""
    model, profile = resolve_model_alias("gpt4o")
    assert model == "gpt-4o"
    assert profile == "openai"


def test_resolve_unknown_passthrough() -> None:
    """Unknown model name passes through unchanged with None profile."""
    model, profile = resolve_model_alias("unknown-model")
    assert model == "unknown-model"
    assert profile is None


def test_resolve_sonnet() -> None:
    """sonnet resolves to claude-sonnet-4-6 on sdk profile."""
    model, profile = resolve_model_alias("sonnet")
    assert model == "claude-sonnet-4-6"
    assert profile == "sdk"


def test_resolve_o3() -> None:
    """o3 resolves to o3-mini on openai profile."""
    model, profile = resolve_model_alias("o3")
    assert model == "o3-mini"
    assert profile == "openai"


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
kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2" }
"""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(toml_content)

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        model, profile = resolve_model_alias("kimi25")
        assert model == "moonshotai/kimi-k2"
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
        assert "gpt4o" in aliases
        assert len(aliases) >= len(BUILT_IN_ALIASES)


def test_get_all_aliases_merges_user(tmp_path: Path) -> None:
    """get_all_aliases merges user aliases with built-ins."""
    toml_content = """
[aliases]
kimi25 = { profile = "openrouter", model = "moonshotai/kimi-k2" }
"""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(toml_content)

    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        aliases = get_all_aliases()
        assert "kimi25" in aliases
        assert "opus" in aliases  # built-in still present
        assert aliases["kimi25"]["model"] == "moonshotai/kimi-k2"
