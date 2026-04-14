"""Built-in pool selection strategies and strategy registry.

Provides four strategies:
  - ``random``: uniform random selection
  - ``round-robin``: deterministic rotation with persistent state
  - ``cheapest``: cost-tier ordering (breaks ties by pricing.input)
  - ``weighted-random``: weighted random selection

All strategies conform to the ``PoolStrategy`` protocol.
The module-level registry maps strategy name strings to singleton instances.
"""

from __future__ import annotations

import random as _random
from typing import Protocol, runtime_checkable

from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolState,
    SelectionContext,
    StrategyNotFoundError,
)


@runtime_checkable
class PoolStrategy(Protocol):
    """Protocol for pool selection strategies."""

    def select(self, pool: ModelPool, context: SelectionContext) -> str: ...


# Single source of truth for cost tier ordering.  Lower rank = cheaper.
COST_TIER_RANK: dict[str, int] = {
    "free": 0,
    "cheap": 1,
    "moderate": 2,
    "expensive": 3,
    "subscription": 4,
}

# Sentinel rank for tiers not present in COST_TIER_RANK.
_UNKNOWN_TIER_RANK: int = len(COST_TIER_RANK)


class RandomStrategy:
    """Uniform random selection from pool members."""

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        return _random.choice(pool.models)


class RoundRobinStrategy:
    """Deterministic rotation through pool members in order.

    Reads ``context.pool_state.last_index``, advances by one (mod pool
    size), updates the state in place, and returns the member at the new
    index.  The caller is responsible for persisting the updated state.

    If ``context.pool_state`` is ``None``, treats ``last_index`` as 0.
    """

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        if context.pool_state is None:
            context.pool_state = PoolState(last_index=0)

        state = context.pool_state
        next_index = (state.last_index + 1) % len(pool.models)
        state.last_index = next_index
        return pool.models[next_index]


class CheapestStrategy:
    """Select the cheapest member by cost tier.

    Tier ordering is defined by ``COST_TIER_RANK``.  Ties within the
    same tier are broken by ``pricing.input`` (lowest wins).  If pricing
    is unavailable for a tied member, ties are broken randomly.  Members
    absent from ``context.aliases`` receive the worst possible rank.
    """

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        aliases = context.aliases or {}

        def sort_key(member: str) -> tuple[int, float]:
            alias = aliases.get(member)
            if alias is None:
                return (_UNKNOWN_TIER_RANK, _random.random())

            tier = alias.get("cost_tier", "")
            rank = COST_TIER_RANK.get(tier, _UNKNOWN_TIER_RANK)

            pricing = alias.get("pricing")
            if pricing is not None:
                input_price = pricing.get("input")
                if input_price is not None:
                    return (rank, float(input_price))

            # Pricing unavailable — break ties randomly within tier.
            return (rank, _random.random())

        return min(pool.models, key=sort_key)


class WeightedRandomStrategy:
    """Weighted random selection from pool members.

    Per-member weights come from ``pool.weights``.  Members absent from
    ``pool.weights`` default to 1.0.  Weights are normalised to
    probabilities at selection time.
    """

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        weights_map = pool.weights or {}
        weights = [weights_map.get(m, 1.0) for m in pool.models]
        return _random.choices(pool.models, weights=weights, k=1)[0]


# ---------------------------------------------------------------------------
# Strategy registry
# ---------------------------------------------------------------------------

_STRATEGY_REGISTRY: dict[str, PoolStrategy] = {
    "random": RandomStrategy(),
    "round-robin": RoundRobinStrategy(),
    "cheapest": CheapestStrategy(),
    "weighted-random": WeightedRandomStrategy(),
}


def register_strategy(name: str, strategy: PoolStrategy) -> None:
    """Register a named strategy in the module-level registry.

    Allows callers to add custom strategies beyond the four built-ins.
    """
    _STRATEGY_REGISTRY[name] = strategy


def get_strategy(name: str) -> PoolStrategy:
    """Return the strategy registered under ``name``.

    Raises:
        StrategyNotFoundError: if ``name`` is not in the registry.
    """
    strategy = _STRATEGY_REGISTRY.get(name)
    if strategy is None:
        registered = sorted(_STRATEGY_REGISTRY)
        raise StrategyNotFoundError(
            f"Unknown pool strategy {name!r}. Registered strategies: {registered}"
        )
    return strategy
