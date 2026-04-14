"""Tests for ModelPool, SelectionContext, and PoolState data models."""

from __future__ import annotations

import dataclasses

import pytest

from squadron.pipeline.intelligence.pools.models import (
    ModelPool,
    PoolNotFoundError,
    PoolState,
    PoolValidationError,
    SelectionContext,
    StrategyNotFoundError,
)


class TestModelPool:
    def test_instantiation_without_weights(self) -> None:
        pool = ModelPool(
            name="test",
            description="A test pool",
            models=["minimax", "glm5"],
            strategy="random",
        )
        assert pool.name == "test"
        assert pool.models == ["minimax", "glm5"]
        assert pool.weights is None

    def test_instantiation_with_weights(self) -> None:
        pool = ModelPool(
            name="test",
            description="Weighted pool",
            models=["minimax", "glm5"],
            strategy="weighted-random",
            weights={"minimax": 2.0, "glm5": 1.0},
        )
        assert pool.weights == {"minimax": 2.0, "glm5": 1.0}

    def test_frozen_raises_on_assignment(self) -> None:
        pool = ModelPool(
            name="test",
            description="desc",
            models=["minimax"],
            strategy="random",
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            pool.name = "other"  # type: ignore[misc]


class TestSelectionContext:
    def test_required_fields_only(self) -> None:
        ctx = SelectionContext(pool_name="review", action_type="review")
        assert ctx.pool_name == "review"
        assert ctx.action_type == "review"
        assert ctx.run_id is None
        assert ctx.aliases is None
        assert ctx.pool_state is None
        assert ctx.task_description is None

    def test_all_fields(self) -> None:
        state = PoolState(last_index=2)
        ctx = SelectionContext(
            pool_name="review",
            action_type="dispatch",
            run_id="run-001",
            aliases={},
            pool_state=state,
            task_description="summarize code",
        )
        assert ctx.run_id == "run-001"
        assert ctx.pool_state is state
        assert ctx.task_description == "summarize code"


class TestPoolState:
    def test_default_last_index_is_zero(self) -> None:
        state = PoolState()
        assert state.last_index == 0

    def test_custom_last_index(self) -> None:
        state = PoolState(last_index=5)
        assert state.last_index == 5

    def test_mutable(self) -> None:
        state = PoolState(last_index=0)
        state.last_index = 3
        assert state.last_index == 3


class TestExceptions:
    def test_pool_validation_error_is_exception(self) -> None:
        assert issubclass(PoolValidationError, Exception)
        exc = PoolValidationError("bad pool")
        assert str(exc) == "bad pool"

    def test_pool_not_found_error_is_exception(self) -> None:
        assert issubclass(PoolNotFoundError, Exception)

    def test_strategy_not_found_error_is_exception(self) -> None:
        assert issubclass(StrategyNotFoundError, Exception)
