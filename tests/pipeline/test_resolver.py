"""Tests for ModelResolver 5-level cascade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.models.aliases import UnknownModelAliasError
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
    assert model_id == "claude-sonnet-5-5"
    assert profile == "sdk"


def test_resolves_unknown_alias_as_literal() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model", profile_source=True)
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


def test_resolve_full_carries_the_alias_effort(tmp_path: Path) -> None:
    """Slice 931 D11: read while the alias name is still known."""
    from squadron.core.models import Effort

    toml_file = tmp_path / "models.toml"
    toml_file.write_text('[aliases.glm-low]\nprofile = "openrouter"\nmodel = "x/y"\neffort = "low"\n')
    with patch("squadron.models.aliases.models_toml_path", return_value=toml_file):
        assert ModelResolver(cli_override="glm-low").resolve_full().effort is Effort.low
        assert ModelResolver(cli_override="opus").resolve_full().effort is None


# ---------------------------------------------------------------------------
# #175 backstop: unknown aliases fail in the resolver
# ---------------------------------------------------------------------------


def test_unknown_model_raises_before_any_request() -> None:
    resolver = ModelResolver(pipeline_model="glm-flash-low.")
    with pytest.raises(UnknownModelAliasError, match="unknown model alias 'glm-flash-low.'"):
        resolver.resolve()


def test_unknown_model_from_the_action_level_raises() -> None:
    resolver = ModelResolver(pipeline_model="sonnet")
    with pytest.raises(UnknownModelAliasError):
        resolver.resolve(action_model="not-an-alias-at-all")


def test_profile_source_lets_a_literal_model_through() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model", profile_source=True)
    model_id, profile = resolver.resolve()
    assert model_id == "my-custom-model"
    assert profile is None


def test_valid_alias_still_resolves_without_profile_source() -> None:
    resolver = ModelResolver(pipeline_model="sonnet")
    model_id, _ = resolver.resolve()
    assert model_id == "claude-sonnet-5-5"


def test_per_call_profile_source_true_accepts_a_literal_id_the_run_rejects() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model", profile_source=False)
    assert resolver.resolve_full(profile_source=True).model_id == "my-custom-model"


def test_per_call_profile_source_false_rejects_a_literal_id_the_run_accepts() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model", profile_source=True)
    with pytest.raises(UnknownModelAliasError):
        resolver.resolve_full(profile_source=False)


def test_per_call_profile_source_none_uses_the_run_value() -> None:
    accepting = ModelResolver(pipeline_model="my-custom-model", profile_source=True)
    assert accepting.resolve_full(profile_source=None).model_id == "my-custom-model"
    rejecting = ModelResolver(pipeline_model="my-custom-model", profile_source=False)
    with pytest.raises(UnknownModelAliasError):
        rejecting.resolve_full(profile_source=None)


def test_resolve_ignores_per_call_override() -> None:
    resolver = ModelResolver(pipeline_model="my-custom-model", profile_source=False)
    with pytest.raises(UnknownModelAliasError):
        resolver.resolve()
