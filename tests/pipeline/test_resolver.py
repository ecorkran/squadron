"""Tests for ModelResolver 5-level cascade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.pipeline.resolver import (
    ModelPoolNotImplemented,
    ModelResolutionError,
    ModelResolver,
)


def test_cli_override_wins() -> None:
    resolver = ModelResolver(
        cli_override="sonnet",
        pipeline_model="opus",
        config_default="haiku",
    )
    model_id, _ = resolver.resolve(action_model="gpt4o", step_model="opus")
    # CLI override resolves "sonnet" alias
    assert "sonnet" in model_id.lower()


def test_action_model_over_step() -> None:
    resolver = ModelResolver(pipeline_model="opus", config_default="haiku")
    model_id, _ = resolver.resolve(action_model="sonnet", step_model="opus")
    assert "sonnet" in model_id.lower()


def test_step_model_over_pipeline() -> None:
    resolver = ModelResolver(pipeline_model="opus", config_default="haiku")
    model_id, _ = resolver.resolve(step_model="sonnet")
    assert "sonnet" in model_id.lower()


def test_pipeline_model_over_config() -> None:
    resolver = ModelResolver(pipeline_model="sonnet", config_default="haiku")
    model_id, _ = resolver.resolve()
    assert "sonnet" in model_id.lower()


def test_config_default_fallback() -> None:
    resolver = ModelResolver(config_default="sonnet")
    model_id, _ = resolver.resolve()
    assert "sonnet" in model_id.lower()


def test_all_none_raises_resolution_error() -> None:
    resolver = ModelResolver()
    with pytest.raises(ModelResolutionError):
        resolver.resolve()


def test_pool_prefix_raises_not_implemented() -> None:
    resolver = ModelResolver(pipeline_model="pool:high")
    with pytest.raises(ModelPoolNotImplemented):
        resolver.resolve()


def test_pool_prefix_at_action_level() -> None:
    resolver = ModelResolver(config_default="sonnet")
    with pytest.raises(ModelPoolNotImplemented):
        resolver.resolve(action_model="pool:review")


def test_resolves_known_alias() -> None:
    resolver = ModelResolver(pipeline_model="sonnet")
    model_id, profile = resolver.resolve()
    assert model_id == "claude-sonnet-5"
    assert profile == "sdk"


def test_resolves_unknown_alias_as_literal() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model")
    model_id, profile = resolver.resolve()
    assert model_id == "my-custom-model"
    assert profile is None


def test_resolve_full_carries_the_alias_output_budget(tmp_path: Path) -> None:
    """Slice 924 D4: read while the alias name is still known."""
    toml_file = tmp_path / "models.toml"
    toml_file.write_text(
        '[aliases.budgeted]\nprofile = "openrouter"\nmodel = "x/y"\nmax_output_tokens = 4096\n'
    )
    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        resolved = ModelResolver(cli_override="budgeted").resolve_full()
    assert resolved.max_output_tokens == 4096


def test_resolve_full_has_no_budget_for_an_alias_without_one(tmp_path: Path) -> None:
    with patch("squadron.models.aliases.models_toml_path", return_value=tmp_path / "none.toml"):
        resolved = ModelResolver(cli_override="opus").resolve_full()
    assert resolved.max_output_tokens is None
