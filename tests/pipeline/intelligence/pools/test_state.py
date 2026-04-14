"""Tests for round-robin pool state persistence (load/save/clear)."""

from __future__ import annotations

from pathlib import Path

from squadron.pipeline.intelligence.pools.loader import (
    clear_pool_state,
    load_pool_state,
    save_pool_state,
)
from squadron.pipeline.intelligence.pools.models import PoolState


class TestLoadPoolState:
    def test_missing_file_returns_default(self, tmp_state_file: Path) -> None:
        assert not tmp_state_file.exists()
        state = load_pool_state("review")
        assert state.last_index == 0

    def test_missing_pool_entry_returns_default(self, tmp_state_file: Path) -> None:
        # Save for "other" pool, load for "review" (absent)
        save_pool_state("other", PoolState(last_index=5))
        state = load_pool_state("review")
        assert state.last_index == 0

    def test_roundtrip_preserves_last_index(self, tmp_state_file: Path) -> None:
        save_pool_state("review", PoolState(last_index=3))
        state = load_pool_state("review")
        assert state.last_index == 3


class TestSavePoolState:
    def test_save_updates_without_destroying_other_pools(
        self, tmp_state_file: Path
    ) -> None:
        save_pool_state("review", PoolState(last_index=2))
        save_pool_state("high", PoolState(last_index=7))

        review_state = load_pool_state("review")
        high_state = load_pool_state("high")

        assert review_state.last_index == 2
        assert high_state.last_index == 7

    def test_save_creates_file_and_dirs(self, tmp_state_file: Path) -> None:
        assert not tmp_state_file.exists()
        save_pool_state("review", PoolState(last_index=1))
        assert tmp_state_file.exists()

    def test_wrap_around_across_calls(self, tmp_state_file: Path) -> None:
        # Simulate: last_index goes 0 → 1 → 2 → 0 (for a 3-member pool)
        save_pool_state("review", PoolState(last_index=0))
        save_pool_state("review", PoolState(last_index=1))
        save_pool_state("review", PoolState(last_index=2))
        save_pool_state("review", PoolState(last_index=0))
        state = load_pool_state("review")
        assert state.last_index == 0


class TestClearPoolState:
    def test_clear_removes_entry(self, tmp_state_file: Path) -> None:
        save_pool_state("review", PoolState(last_index=3))
        clear_pool_state("review")
        state = load_pool_state("review")
        assert state.last_index == 0

    def test_clear_absent_entry_is_noop(self, tmp_state_file: Path) -> None:
        # No exception when pool entry is missing
        clear_pool_state("nonexistent")

    def test_clear_absent_file_is_noop(self, tmp_state_file: Path) -> None:
        assert not tmp_state_file.exists()
        clear_pool_state("review")  # must not raise

    def test_clear_preserves_other_pools(self, tmp_state_file: Path) -> None:
        save_pool_state("review", PoolState(last_index=2))
        save_pool_state("high", PoolState(last_index=5))
        clear_pool_state("review")
        assert load_pool_state("review").last_index == 0
        assert load_pool_state("high").last_index == 5
