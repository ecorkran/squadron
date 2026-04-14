"""PoolBackend protocol and DefaultPoolBackend implementation.

``PoolBackend`` — the interface ``ModelResolver`` uses to select models from
a pool and inspect/reset pool configuration.

``DefaultPoolBackend`` — delegates to the module-level functions in
``loader.py``; no logic is duplicated.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from squadron.pipeline.intelligence.pools.loader import (
    clear_pool_state,
    get_all_pools,
    get_pool,
    select_from_pool,
)
from squadron.pipeline.intelligence.pools.models import ModelPool, SelectionContext


@runtime_checkable
class PoolBackend(Protocol):
    """Interface for pool-based model selection.

    ``ModelResolver`` depends on this protocol; ``DefaultPoolBackend``
    provides the production implementation.  Tests may supply stubs.
    """

    def select(self, pool_name: str, context: SelectionContext) -> str:
        """Resolve *pool_name* to an alias name.

        Raises:
            PoolNotFoundError: if no pool with that name exists.
        """
        ...

    def get_pool(self, pool_name: str) -> ModelPool:
        """Return the named pool definition.

        Raises:
            PoolNotFoundError: if no pool with that name exists.
        """
        ...

    def list_pools(self) -> dict[str, ModelPool]:
        """Return all available pools (built-in + user overrides)."""
        ...

    def reset_pool_state(self, pool_name: str) -> None:
        """Clear the round-robin state for *pool_name*.

        No-op if the pool has no persisted state.
        """
        ...


class DefaultPoolBackend:
    """Production PoolBackend that delegates to loader.py functions."""

    def select(self, pool_name: str, context: SelectionContext) -> str:  # noqa: ARG002
        """Select an alias from the named pool using the pool's strategy."""
        pool = get_pool(pool_name)
        return select_from_pool(pool)

    def get_pool(self, pool_name: str) -> ModelPool:
        return get_pool(pool_name)

    def list_pools(self) -> dict[str, ModelPool]:
        return get_all_pools()

    def reset_pool_state(self, pool_name: str) -> None:
        clear_pool_state(pool_name)
