"""Tests for PoolBackend protocol and DefaultPoolBackend implementation."""

from __future__ import annotations

import pytest

from squadron.pipeline.intelligence.pools.backend import DefaultPoolBackend, PoolBackend
from squadron.pipeline.intelligence.pools.loader import load_pool_state
from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    SelectionContext,
)

# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_default_backend_satisfies_protocol() -> None:
    assert isinstance(DefaultPoolBackend(), PoolBackend)


def test_stub_satisfies_protocol() -> None:
    """A minimal hand-written stub must satisfy the runtime-checkable protocol."""

    class StubBackend:
        def select(self, pool_name: str, context: SelectionContext) -> str:
            return "opus"

        def get_pool(self, pool_name: str) -> ModelPool:
            return ModelPool(
                name=pool_name, description="", models=["opus"], strategy="random"
            )

        def list_pools(self) -> dict[str, ModelPool]:
            return {}

        def reset_pool_state(self, pool_name: str) -> None:
            pass

    assert isinstance(StubBackend(), PoolBackend)


# ---------------------------------------------------------------------------
# DefaultPoolBackend.list_pools
# ---------------------------------------------------------------------------


def test_list_pools_contains_builtins() -> None:
    backend = DefaultPoolBackend()
    pools = backend.list_pools()
    assert "review" in pools
    assert "high" in pools
    assert "cheap" in pools


# ---------------------------------------------------------------------------
# DefaultPoolBackend.get_pool
# ---------------------------------------------------------------------------


def test_get_pool_returns_correct_pool() -> None:
    backend = DefaultPoolBackend()
    pool = backend.get_pool("review")
    assert pool.name == "review"
    assert isinstance(pool.models, list)
    assert len(pool.models) > 0


def test_get_pool_unknown_raises() -> None:
    backend = DefaultPoolBackend()
    with pytest.raises(PoolNotFoundError):
        backend.get_pool("does-not-exist")


# ---------------------------------------------------------------------------
# DefaultPoolBackend.select
# ---------------------------------------------------------------------------


def test_select_returns_member_of_pool(tmp_state_file: object) -> None:
    backend = DefaultPoolBackend()
    pool = backend.get_pool("review")
    ctx = SelectionContext(pool_name="review", action_type="dispatch")
    result = backend.select("review", ctx)
    assert result in pool.models


def test_select_unknown_pool_raises(tmp_state_file: object) -> None:
    backend = DefaultPoolBackend()
    ctx = SelectionContext(pool_name="no-such-pool", action_type="dispatch")
    with pytest.raises(PoolNotFoundError):
        backend.select("no-such-pool", ctx)


# ---------------------------------------------------------------------------
# DefaultPoolBackend.reset_pool_state
# ---------------------------------------------------------------------------


def test_reset_clears_round_robin_state(
    tmp_state_file: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Advance round-robin state then reset; load should return last_index=0."""
    from squadron.pipeline.intelligence.pools.loader import save_pool_state
    from squadron.pipeline.intelligence.pools.models import PoolState

    # Seed a non-zero state
    save_pool_state("review", PoolState(last_index=3))
    assert load_pool_state("review").last_index == 3

    backend = DefaultPoolBackend()
    backend.reset_pool_state("review")

    assert load_pool_state("review").last_index == 0
