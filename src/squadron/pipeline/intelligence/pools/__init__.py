"""Public API for model pool infrastructure.

All symbols importable directly from ``squadron.pipeline.intelligence.pools``.
"""

from squadron.pipeline.intelligence.pools.loader import (
    clear_pool_state,
    get_all_pools,
    get_pool,
    load_builtin_pools,
    load_pool_state,
    load_user_pools,
    save_pool_state,
    select_from_pool,
)
from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    PoolState,
    PoolValidationError,
    SelectionContext,
    StrategyNotFoundError,
)
from squadron.pipeline.intelligence.pools.protocol import PoolStrategy
from squadron.pipeline.intelligence.pools.strategies import (
    get_strategy,
    register_strategy,
)

__all__ = [
    # Data model
    "ModelPool",
    "SelectionContext",
    "PoolState",
    "PoolStrategy",
    # Errors
    "PoolValidationError",
    "PoolNotFoundError",
    "StrategyNotFoundError",
    # Loader
    "load_builtin_pools",
    "load_user_pools",
    "get_all_pools",
    "get_pool",
    # Selection
    "select_from_pool",
    # Strategy registry
    "register_strategy",
    "get_strategy",
    # State management
    "load_pool_state",
    "save_pool_state",
    "clear_pool_state",
]
