"""Tests for all four built-in pool selection strategies and the registry."""

from __future__ import annotations

from collections import Counter

import pytest

from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolState,
    SelectionContext,
    StrategyNotFoundError,
)
from squadron.pipeline.intelligence.pools.strategies import (
    COST_TIER_RANK,
    CheapestStrategy,
    RandomStrategy,
    RoundRobinStrategy,
    WeightedRandomStrategy,
    get_strategy,
    register_strategy,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pool(
    models: list[str],
    strategy: str = "random",
    weights: dict[str, float] | None = None,
) -> ModelPool:
    return ModelPool(
        name="test",
        description="test pool",
        models=models,
        strategy=strategy,
        weights=weights,
    )


def _make_ctx(
    pool_state: PoolState | None = None,
    aliases: dict | None = None,
) -> SelectionContext:
    return SelectionContext(
        pool_name="test",
        action_type="test",
        pool_state=pool_state,
        aliases=aliases,
    )


# ---------------------------------------------------------------------------
# COST_TIER_RANK constant
# ---------------------------------------------------------------------------


class TestCostTierRank:
    def test_free_is_zero(self) -> None:
        assert COST_TIER_RANK["free"] == 0

    def test_expensive_is_three(self) -> None:
        assert COST_TIER_RANK["expensive"] == 3

    def test_ordering(self) -> None:
        assert COST_TIER_RANK["free"] < COST_TIER_RANK["cheap"]
        assert COST_TIER_RANK["cheap"] < COST_TIER_RANK["moderate"]
        assert COST_TIER_RANK["moderate"] < COST_TIER_RANK["expensive"]
        assert COST_TIER_RANK["expensive"] < COST_TIER_RANK["subscription"]


# ---------------------------------------------------------------------------
# RandomStrategy
# ---------------------------------------------------------------------------


class TestRandomStrategy:
    def test_single_member_always_returns_it(self) -> None:
        pool = _make_pool(["minimax"])
        strategy = RandomStrategy()
        ctx = _make_ctx()
        for _ in range(20):
            assert strategy.select(pool, ctx) == "minimax"

    def test_uniform_distribution(self) -> None:
        models = ["minimax", "glm5", "kimi25"]
        pool = _make_pool(models)
        strategy = RandomStrategy()
        ctx = _make_ctx()
        counts = Counter(strategy.select(pool, ctx) for _ in range(200))
        for model in models:
            assert counts[model] > 30, f"{model} appeared only {counts[model]} times"

    def test_returns_member_of_pool(self) -> None:
        models = ["minimax", "glm5"]
        pool = _make_pool(models)
        strategy = RandomStrategy()
        ctx = _make_ctx()
        for _ in range(50):
            assert strategy.select(pool, ctx) in models


# ---------------------------------------------------------------------------
# RoundRobinStrategy
# ---------------------------------------------------------------------------


class TestRoundRobinStrategy:
    def test_rotates_through_all_members(self) -> None:
        models = ["minimax", "glm5", "kimi25"]
        pool = _make_pool(models)
        strategy = RoundRobinStrategy()
        state = PoolState(last_index=0)
        ctx = _make_ctx(pool_state=state)

        # With last_index=0, first call advances to index 1
        r1 = strategy.select(pool, ctx)
        r2 = strategy.select(pool, ctx)
        r3 = strategy.select(pool, ctx)
        assert r1 == "glm5"
        assert r2 == "kimi25"
        assert r3 == "minimax"

    def test_wrap_around(self) -> None:
        models = ["minimax", "glm5", "kimi25"]
        pool = _make_pool(models)
        strategy = RoundRobinStrategy()
        state = PoolState(last_index=0)
        ctx = _make_ctx(pool_state=state)

        # Exhaust one full cycle
        for _ in range(3):
            strategy.select(pool, ctx)
        # Fourth call wraps back to index 1 (second element)
        assert strategy.select(pool, ctx) == "glm5"

    def test_single_member_pool(self) -> None:
        pool = _make_pool(["minimax"])
        strategy = RoundRobinStrategy()
        state = PoolState(last_index=0)
        ctx = _make_ctx(pool_state=state)
        for _ in range(5):
            assert strategy.select(pool, ctx) == "minimax"

    def test_none_pool_state_treated_as_zero(self) -> None:
        models = ["minimax", "glm5", "kimi25"]
        pool = _make_pool(models)
        strategy = RoundRobinStrategy()
        ctx = _make_ctx(pool_state=None)
        result = strategy.select(pool, ctx)
        # last_index=0 → advances to 1 → "glm5"
        assert result == "glm5"
        assert ctx.pool_state is not None
        assert ctx.pool_state.last_index == 1

    def test_mutates_state(self) -> None:
        pool = _make_pool(["a", "b", "c"])
        strategy = RoundRobinStrategy()
        state = PoolState(last_index=0)
        ctx = _make_ctx(pool_state=state)
        strategy.select(pool, ctx)
        assert state.last_index == 1


# ---------------------------------------------------------------------------
# CheapestStrategy
# ---------------------------------------------------------------------------


class TestCheapestStrategy:
    def test_free_tier_wins(self, sample_aliases: dict) -> None:
        # qwen36-free is free tier, others are cheap
        pool = _make_pool(["minimax", "glm5", "qwen36-free"])
        strategy = CheapestStrategy()
        ctx = _make_ctx(aliases=sample_aliases)
        assert strategy.select(pool, ctx) == "qwen36-free"

    def test_same_tier_broken_by_price(self, sample_aliases: dict) -> None:
        # All cheap: minimax(0.30), glm5(0.72), grok-fast(0.20)
        pool = _make_pool(["minimax", "glm5", "grok-fast"])
        strategy = CheapestStrategy()
        ctx = _make_ctx(aliases=sample_aliases)
        # grok-fast has lowest input price among cheap tier
        assert strategy.select(pool, ctx) == "grok-fast"

    def test_unknown_member_ranked_worst(self, sample_aliases: dict) -> None:
        # "unknown-model" not in aliases → worst rank
        pool = _make_pool(["unknown-model", "qwen36-free"])
        strategy = CheapestStrategy()
        ctx = _make_ctx(aliases=sample_aliases)
        assert strategy.select(pool, ctx) == "qwen36-free"

    def test_single_member_pool(self, sample_aliases: dict) -> None:
        pool = _make_pool(["opus"])
        strategy = CheapestStrategy()
        ctx = _make_ctx(aliases=sample_aliases)
        assert strategy.select(pool, ctx) == "opus"

    def test_none_aliases_all_ranked_worst(self) -> None:
        pool = _make_pool(["minimax", "glm5"])
        strategy = CheapestStrategy()
        ctx = _make_ctx(aliases=None)
        # Both ranked worst — result is deterministic only in that it's one of the two
        result = strategy.select(pool, ctx)
        assert result in ["minimax", "glm5"]


# ---------------------------------------------------------------------------
# WeightedRandomStrategy
# ---------------------------------------------------------------------------


class TestWeightedRandomStrategy:
    def test_relative_frequency_matches_weights(self) -> None:
        # member "a" has weight 2.0, "b" has weight 1.0 → ~2:1 ratio
        pool = _make_pool(["a", "b"], weights={"a": 2.0, "b": 1.0})
        strategy = WeightedRandomStrategy()
        ctx = _make_ctx()
        counts = Counter(strategy.select(pool, ctx) for _ in range(1000))
        ratio = counts["a"] / counts["b"]
        assert 1.0 < ratio < 4.0, f"Expected ~2:1 ratio, got {ratio:.2f}"

    def test_absent_weights_uniform(self) -> None:
        models = ["minimax", "glm5", "kimi25"]
        pool = _make_pool(models, weights=None)
        strategy = WeightedRandomStrategy()
        ctx = _make_ctx()
        counts = Counter(strategy.select(pool, ctx) for _ in range(600))
        for m in models:
            assert counts[m] > 100, f"{m} underrepresented: {counts[m]}"

    def test_single_member_pool(self) -> None:
        pool = _make_pool(["minimax"], weights={"minimax": 5.0})
        strategy = WeightedRandomStrategy()
        ctx = _make_ctx()
        for _ in range(20):
            assert strategy.select(pool, ctx) == "minimax"


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------


class TestStrategyRegistry:
    def test_all_builtins_retrievable(self) -> None:
        for name in ("random", "round-robin", "cheapest", "weighted-random"):
            strategy = get_strategy(name)
            assert strategy is not None

    def test_random_is_random_strategy(self) -> None:
        assert isinstance(get_strategy("random"), RandomStrategy)

    def test_round_robin_is_rr_strategy(self) -> None:
        assert isinstance(get_strategy("round-robin"), RoundRobinStrategy)

    def test_cheapest_is_cheapest_strategy(self) -> None:
        assert isinstance(get_strategy("cheapest"), CheapestStrategy)

    def test_weighted_random_is_wr_strategy(self) -> None:
        assert isinstance(get_strategy("weighted-random"), WeightedRandomStrategy)

    def test_unknown_name_raises(self) -> None:
        with pytest.raises(StrategyNotFoundError, match="nope"):
            get_strategy("nope")

    def test_register_custom_strategy(self) -> None:
        class MyStrategy:
            def select(self, pool: ModelPool, context: SelectionContext) -> str:
                return pool.models[0]

        register_strategy("my-custom", MyStrategy())
        retrieved = get_strategy("my-custom")
        assert isinstance(retrieved, MyStrategy)
