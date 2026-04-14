"""Integration smoke tests for model pool infrastructure.

Uses the real alias registry and shipped pools.toml — no mocking.
"""

from __future__ import annotations

from pathlib import Path

from squadron.pipeline.intelligence.pools import (
    get_all_pools,
    get_pool,
    select_from_pool,
)


class TestIntegration:
    def test_all_three_default_pools_present(self) -> None:
        pools = get_all_pools()
        assert "review" in pools
        assert "high" in pools
        assert "cheap" in pools

    def test_review_pool_has_enough_members(self) -> None:
        pools = get_all_pools()
        assert len(pools["review"].models) >= 3

    def test_select_from_review_returns_valid_member(
        self, tmp_state_file: Path
    ) -> None:
        pool = get_pool("review")
        result = select_from_pool(pool)
        assert result in pool.models

    def test_select_from_cheap_returns_valid_member(self, tmp_state_file: Path) -> None:
        pool = get_pool("cheap")
        result = select_from_pool(pool)
        assert result in pool.models
