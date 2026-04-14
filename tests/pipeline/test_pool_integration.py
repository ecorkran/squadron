"""Integration tests for pool-based model resolution through execute_pipeline.

Uses real PoolBackend/DefaultPoolBackend and real alias registry, with a
minimal in-memory PipelineDefinition.  Actions are mocked to avoid real API
calls.  State files are isolated to tmp_path.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.intelligence.pools import (
    DefaultPoolBackend,
    PoolBackend,
    PoolNotFoundError,
    PoolSelection,
)
from squadron.pipeline.intelligence.pools.models import SelectionContext
from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolver
from squadron.pipeline.state import StateManager

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_state_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Isolate pool-state.toml writes so tests don't touch ~/.config/squadron/."""
    config_dir = tmp_path / "squadron"
    config_dir.mkdir()
    import squadron.pipeline.intelligence.pools.loader as loader_mod

    monkeypatch.setattr(loader_mod, "_config_dir", lambda: config_dir)
    return config_dir / "pool-state.toml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_POOL_MEMBERS = ["minimax", "glm5", "kimi25", "grok-fast"]  # from review pool


def _stub_action_fn() -> MagicMock:
    result = ActionResult(success=True, action_type="mock", outputs={}, verdict=None)
    action = MagicMock()
    action.execute = AsyncMock(return_value=result)
    return action


def _minimal_pipeline(model: str | None = None) -> PipelineDefinition:
    """One-step pipeline with an action-type that maps to a stub registry entry."""
    return PipelineDefinition(
        name="pool-integration-test",
        description="integration test pipeline",
        params={},
        steps=[StepConfig(step_type="dispatch", name="step-0", config={})],
        model=model,
    )


def _registry() -> dict[str, object]:
    return {"dispatch": _stub_action_fn()}


def _resolver_with_backend(
    cli_override: str | None = None,
    pipeline_model: str | None = None,
    backend: PoolBackend | None = None,
    selections: list[PoolSelection] | None = None,
) -> ModelResolver:
    if backend is None:
        backend = DefaultPoolBackend()
    on_sel = selections.append if selections is not None else None
    return ModelResolver(
        cli_override=cli_override,
        pipeline_model=pipeline_model,
        pool_backend=backend,
        on_pool_selection=on_sel,
    )


# ---------------------------------------------------------------------------
# Pool resolution through execute_pipeline
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cli_pool_override_resolves_and_logs(
    tmp_path: Path, tmp_state_file: Path
) -> None:
    """CLI pool: override resolves; resolver callback fires and state is logged."""
    selections: list[PoolSelection] = []
    state_mgr = StateManager(runs_dir=tmp_path)
    run_id = state_mgr.init_run("pool-integration-test", {})

    resolver = _resolver_with_backend(
        cli_override="pool:review",
        selections=selections,
        backend=DefaultPoolBackend(),
    )

    # Call resolve() directly — this is what real action handlers do.
    model_id, _profile = resolver.resolve()
    assert model_id  # resolves to a real model ID
    assert len(selections) == 1
    sel = selections[0]
    assert sel.pool_name == "review"
    assert sel.selected_alias in _POOL_MEMBERS

    # Log to state and verify persistence
    state_mgr.log_pool_selection(run_id, sel)
    state = state_mgr.load(run_id)
    assert len(state.pool_selections) == 1
    assert state.pool_selections[0]["pool_name"] == "review"
    assert state.pool_selections[0]["selected_alias"] in _POOL_MEMBERS

    # Also verify execute_pipeline runs to completion with this resolver
    result = await execute_pipeline(
        _minimal_pipeline(),
        {},
        resolver=resolver,
        cf_client=MagicMock(),
        run_id=run_id,
        on_step_complete=state_mgr.make_step_callback(run_id),
        _action_registry=_registry(),
    )
    assert result.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_pipeline_level_pool_resolves(
    tmp_path: Path, tmp_state_file: Path
) -> None:
    """pool: at pipeline level resolves via backend; callback fires on resolve()."""
    selections: list[PoolSelection] = []
    resolver = _resolver_with_backend(
        pipeline_model="pool:review",
        selections=selections,
    )

    # Direct resolve call (what dispatch/review actions do)
    model_id, _profile = resolver.resolve()
    assert model_id
    assert len(selections) == 1
    assert selections[0].selected_alias in _POOL_MEMBERS

    # execute_pipeline completes without error
    result = await execute_pipeline(
        _minimal_pipeline(model="pool:review"),
        {},
        resolver=resolver,
        cf_client=MagicMock(),
        _action_registry=_registry(),
    )
    assert result.status == ExecutionStatus.COMPLETED


@pytest.mark.asyncio
async def test_action_alias_overrides_pipeline_pool(
    tmp_path: Path, tmp_state_file: Path
) -> None:
    """Explicit alias at action level bypasses pipeline-level pool — cascade intact."""
    selections: list[PoolSelection] = []

    # Pipeline model is a pool but the action has a hard alias; since our stub
    # action doesn't invoke the resolver, we verify via resolver directly.
    resolver = _resolver_with_backend(
        pipeline_model="pool:review",
        selections=selections,
    )
    # Action-level alias wins — no pool callback
    model_id, _ = resolver.resolve(action_model="sonnet")
    assert "sonnet" in model_id.lower()
    assert len(selections) == 0


@pytest.mark.asyncio
async def test_round_robin_advances_across_two_runs(tmp_state_file: Path) -> None:
    """Round-robin pool state advances across successive selections."""
    pool = DefaultPoolBackend().get_pool("review")
    members = pool.models

    ctx = SelectionContext(pool_name="review", action_type="dispatch")
    b = DefaultPoolBackend()
    first = b.select("review", ctx)
    second = b.select("review", ctx)
    # With round-robin the second call should advance or wrap
    assert first in members
    assert second in members
    # They may be equal only if the pool has exactly one member
    if len(members) > 1:
        assert first != second


@pytest.mark.asyncio
async def test_unknown_pool_raises_pool_not_found(tmp_state_file: Path) -> None:
    resolver = _resolver_with_backend(cli_override="pool:no-such-pool")
    with pytest.raises(PoolNotFoundError):
        resolver.resolve()


@pytest.mark.asyncio
async def test_pool_prefix_without_backend_raises_not_implemented() -> None:
    resolver = ModelResolver(pipeline_model="pool:review")  # no backend
    with pytest.raises(ModelPoolNotImplemented):
        resolver.resolve()
