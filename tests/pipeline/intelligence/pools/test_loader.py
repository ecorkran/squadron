"""Tests for pool loader, validation, alias checking, and select_from_pool."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from squadron.pipeline.intelligence.pools.loader import (
    _parse_pools_from_toml,
    get_all_pools,
    get_pool,
    load_builtin_pools,
    load_user_pools,
    select_from_pool,
)
from squadron.pipeline.intelligence.pools.models import (
    PoolNotFoundError,
    PoolValidationError,
)

# ---------------------------------------------------------------------------
# Built-in pool loading
# ---------------------------------------------------------------------------


class TestLoadBuiltinPools:
    def test_loads_all_three_default_pools(self) -> None:
        pools = load_builtin_pools()
        assert "review" in pools
        assert "high" in pools
        assert "cheap" in pools

    def test_review_pool_strategy_and_members(self) -> None:
        pools = load_builtin_pools()
        review = pools["review"]
        assert review.strategy == "round-robin"
        assert len(review.models) >= 3

    def test_high_pool_strategy_and_members(self) -> None:
        pools = load_builtin_pools()
        high = pools["high"]
        assert high.strategy == "random"
        assert len(high.models) >= 2

    def test_cheap_pool_strategy_and_members(self) -> None:
        pools = load_builtin_pools()
        cheap = pools["cheap"]
        assert cheap.strategy == "cheapest"
        assert len(cheap.models) >= 3

    def test_builtin_pools_toml_fixture_matches_loader(
        self, builtin_pools_toml: str
    ) -> None:
        """Confirm fixture reads same file the loader uses — parser parity."""
        from squadron.data import data_dir

        actual_text = (data_dir() / "pools.toml").read_text()
        assert actual_text == builtin_pools_toml


# ---------------------------------------------------------------------------
# User pool loading
# ---------------------------------------------------------------------------


class TestLoadUserPools:
    def test_absent_file_returns_empty(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import squadron.pipeline.intelligence.pools.loader as loader_mod

        monkeypatch.setattr(loader_mod, "_config_dir", lambda: tmp_path / "squadron")
        result = load_user_pools()
        assert result == {}

    def test_user_pool_overrides_builtin(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import squadron.pipeline.intelligence.pools.loader as loader_mod

        cfg_dir = tmp_path / "squadron"
        cfg_dir.mkdir()
        monkeypatch.setattr(loader_mod, "_config_dir", lambda: cfg_dir)

        user_toml = """
[pools.high]
description = "User override"
strategy = "random"
models = ["opus", "gpt54"]
"""
        (cfg_dir / "pools.toml").write_text(user_toml)

        # Patch alias validation to accept our test aliases
        known = {"opus": {}, "gpt54": {}}
        with patch(
            "squadron.models.aliases.get_all_aliases",
            return_value=known,
        ):
            user_pools = load_user_pools()
        assert "high" in user_pools
        assert user_pools["high"].description == "User override"


class TestGetAllPools:
    def test_user_wins_on_name_collision(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import squadron.pipeline.intelligence.pools.loader as loader_mod

        cfg_dir = tmp_path / "squadron"
        cfg_dir.mkdir()
        monkeypatch.setattr(loader_mod, "_config_dir", lambda: cfg_dir)

        (cfg_dir / "pools.toml").write_text(
            "[pools.review]\n"
            'description = "custom"\n'
            'strategy = "random"\n'
            'models = ["opus"]\n'
        )
        known = {
            "opus": {},
            "gpt54": {},
            "gemini": {},
            "minimax": {},
            "glm5": {},
            "kimi25": {},
            "grok-fast": {},
            "flash3": {},
            "gemma4": {},
            "qwen36-free": {},
        }
        with patch(
            "squadron.models.aliases.get_all_aliases",
            return_value=known,
        ):
            pools = get_all_pools()
        assert pools["review"].description == "custom"


class TestGetPool:
    def test_unknown_pool_raises(self) -> None:
        with pytest.raises(PoolNotFoundError, match="no-such-pool"):
            get_pool("no-such-pool")

    def test_known_pool_returns_model_pool(self) -> None:
        pool = get_pool("review")
        assert pool.name == "review"


# ---------------------------------------------------------------------------
# Validation — strategy
# ---------------------------------------------------------------------------


class TestPoolValidation:
    def _parse(self, toml_text: str) -> Any:
        """Helper: parse TOML using a dummy path."""
        return _parse_pools_from_toml(Path("/fake/pools.toml"), toml_text)

    def test_unknown_strategy_raises(self) -> None:
        toml = (
            "[pools.test]\n"
            'description = "x"\n'
            'strategy = "no-such-strategy"\n'
            'models = ["minimax"]\n'
        )
        with pytest.raises(PoolValidationError, match="no-such-strategy"):
            self._parse(toml)

    def test_empty_models_raises(self) -> None:
        toml = '[pools.test]\ndescription = "x"\nstrategy = "random"\nmodels = []\n'
        with pytest.raises(PoolValidationError, match="models"):
            self._parse(toml)

    def test_weights_keys_not_in_models_raises(self) -> None:
        toml = (
            "[pools.test]\n"
            'description = "x"\n'
            'strategy = "weighted-random"\n'
            'models = ["minimax"]\n'
            "\n[pools.test.weights]\n"
            "nonmember = 2.0\n"
        )
        with pytest.raises(PoolValidationError, match="nonmember"):
            self._parse(toml)

    def test_valid_pool_parses_ok(self) -> None:
        toml = (
            "[pools.test]\n"
            'description = "x"\n'
            'strategy = "random"\n'
            'models = ["minimax", "glm5"]\n'
        )
        pools = self._parse(toml)
        assert "test" in pools


# ---------------------------------------------------------------------------
# Alias validation
# ---------------------------------------------------------------------------


class TestAliasValidation:
    def test_unknown_alias_raises(self) -> None:
        known = {"minimax": {}, "glm5": {}}
        from squadron.pipeline.intelligence.pools.loader import _validate_pool_aliases
        from squadron.pipeline.intelligence.pools.models import ModelPool

        pool = ModelPool(
            name="bad",
            description="",
            models=["nonexistent-alias"],
            strategy="random",
        )
        with pytest.raises(PoolValidationError, match="nonexistent-alias"):
            _validate_pool_aliases("bad", pool, known)

    def test_valid_alias_no_error(self) -> None:
        known = {"minimax": {}, "glm5": {}}
        from squadron.pipeline.intelligence.pools.loader import _validate_pool_aliases
        from squadron.pipeline.intelligence.pools.models import ModelPool

        pool = ModelPool(
            name="ok",
            description="",
            models=["minimax"],
            strategy="random",
        )
        _validate_pool_aliases("ok", pool, known)  # must not raise


# ---------------------------------------------------------------------------
# select_from_pool
# ---------------------------------------------------------------------------

_KNOWN_ALIASES_PATCH = "squadron.models.aliases.get_all_aliases"


class TestSelectFromPool:
    def test_random_pool_returns_member(
        self, tmp_state_file: Path, sample_aliases: dict
    ) -> None:
        with patch(_KNOWN_ALIASES_PATCH, return_value=sample_aliases):
            pool = get_pool("high")
            result = select_from_pool(pool)
        assert result in pool.models

    def test_cheapest_pool_returns_member(
        self, tmp_state_file: Path, sample_aliases: dict
    ) -> None:
        with patch(_KNOWN_ALIASES_PATCH, return_value=sample_aliases):
            pool = get_pool("cheap")
            result = select_from_pool(pool)
        assert result in pool.models

    def test_round_robin_pool_advances_state(
        self, tmp_state_file: Path, sample_aliases: dict
    ) -> None:
        with patch(_KNOWN_ALIASES_PATCH, return_value=sample_aliases):
            pool = get_pool("review")
            r1 = select_from_pool(pool)
            r2 = select_from_pool(pool)
        # Two consecutive calls must differ (pool has ≥4 members)
        assert r1 != r2

    def test_round_robin_state_file_updated(
        self, tmp_state_file: Path, sample_aliases: dict
    ) -> None:
        with patch(_KNOWN_ALIASES_PATCH, return_value=sample_aliases):
            pool = get_pool("review")
            select_from_pool(pool)
        assert tmp_state_file.exists()
