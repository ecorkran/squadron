"""PoolStrategy protocol — the interface all selection strategies must satisfy."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from squadron.pipeline.intelligence.pools.models import ModelPool, SelectionContext


@runtime_checkable
class PoolStrategy(Protocol):
    """Selects one model alias from a pool.

    All built-in strategies and any user-registered strategies must
    implement this interface.  The return value is an alias name from
    ``pool.models`` — not a raw model ID.
    """

    def select(self, pool: ModelPool, context: SelectionContext) -> str:
        """Return the alias name of the selected model."""
        ...
