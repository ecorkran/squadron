"""Tests for ModelResolver pool integration (PoolBackend wiring)."""

from __future__ import annotations

from datetime import datetime

import pytest

from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    PoolSelection,
    SelectionContext,
)
from squadron.pipeline.resolver import (
    ModelPoolNotImplemented,
    ModelResolver,
)

# ---------------------------------------------------------------------------
# Stub backend
# ---------------------------------------------------------------------------

_REVIEW_POOL = ModelPool(
    name="review",
    description="test pool",
    models=["minimax", "glm5"],
    strategy="round-robin",
)
_HIGH_POOL = ModelPool(
    name="high",
    description="high pool",
    models=["opus"],
    strategy="random",
)


class StubPoolBackend:
    """Minimal PoolBackend stub for resolver tests.

    Always returns the first member of the requested pool.
    """

    def __init__(self, pools: dict[str, ModelPool] | None = None) -> None:
        self._pools = pools or {"review": _REVIEW_POOL, "high": _HIGH_POOL}

    def select(self, pool_name: str, context: SelectionContext) -> str:
        if pool_name not in self._pools:
            raise PoolNotFoundError(f"No pool: {pool_name!r}")
        return self._pools[pool_name].models[0]

    def get_pool(self, pool_name: str) -> ModelPool:
        if pool_name not in self._pools:
            raise PoolNotFoundError(f"No pool: {pool_name!r}")
        return self._pools[pool_name]

    def list_pools(self) -> dict[str, ModelPool]:
        return dict(self._pools)

    def reset_pool_state(self, pool_name: str) -> None:
        pass


# ---------------------------------------------------------------------------
# No backend → ModelPoolNotImplemented (preserves existing behaviour)
# ---------------------------------------------------------------------------


def test_pool_prefix_no_backend_raises() -> None:
    resolver = ModelResolver(pipeline_model="pool:review")
    with pytest.raises(ModelPoolNotImplemented):
        resolver.resolve()


def test_pool_prefix_action_level_no_backend_raises() -> None:
    resolver = ModelResolver(config_default="sonnet")
    with pytest.raises(ModelPoolNotImplemented):
        resolver.resolve(action_model="pool:review")


# ---------------------------------------------------------------------------
# Pool resolution with backend
# ---------------------------------------------------------------------------


def test_cli_pool_resolves_via_backend() -> None:
    """CLI override pool: resolves through backend → alias → model_id."""
    backend = StubPoolBackend()
    resolver = ModelResolver(cli_override="pool:review", pool_backend=backend)
    model_id, _profile = resolver.resolve()
    # minimax is the first member; verify it resolves to a real model id
    assert model_id  # non-empty
    assert "minimax" in model_id.lower() or model_id == "minimax"


def test_pipeline_level_pool_resolves_via_backend() -> None:
    backend = StubPoolBackend()
    resolver = ModelResolver(pipeline_model="pool:high", pool_backend=backend)
    model_id, _profile = resolver.resolve()
    # 'opus' is the only member
    assert model_id  # non-empty


def test_action_model_alias_beats_pipeline_pool() -> None:
    """Explicit alias at action level wins over pipeline-level pool:."""
    backend = StubPoolBackend()
    resolver = ModelResolver(pipeline_model="pool:high", pool_backend=backend)
    model_id, _profile = resolver.resolve(action_model="sonnet")
    assert "sonnet" in model_id.lower()


def test_pool_not_found_propagates() -> None:
    backend = StubPoolBackend()
    resolver = ModelResolver(cli_override="pool:no-such-pool", pool_backend=backend)
    with pytest.raises(PoolNotFoundError):
        resolver.resolve()


# ---------------------------------------------------------------------------
# on_pool_selection callback
# ---------------------------------------------------------------------------


def test_callback_fires_once_per_resolution() -> None:
    selections: list[PoolSelection] = []
    backend = StubPoolBackend()
    resolver = ModelResolver(
        pipeline_model="pool:review",
        pool_backend=backend,
        on_pool_selection=selections.append,
    )
    resolver.resolve()

    assert len(selections) == 1
    sel = selections[0]
    assert sel.pool_name == "review"
    assert sel.selected_alias == "minimax"
    assert sel.strategy == "round-robin"
    assert isinstance(sel.timestamp, datetime)


def test_callback_not_fired_when_no_pool() -> None:
    selections: list[PoolSelection] = []
    resolver = ModelResolver(
        pipeline_model="sonnet",
        on_pool_selection=selections.append,
    )
    resolver.resolve()
    assert len(selections) == 0


def test_no_callback_does_not_raise() -> None:
    """on_pool_selection=None must not raise."""
    backend = StubPoolBackend()
    resolver = ModelResolver(
        pipeline_model="pool:review",
        pool_backend=backend,
        on_pool_selection=None,
    )
    model_id, _ = resolver.resolve()
    assert model_id  # just verify it completed
