"""Tests for CompactAction — SDK session rotate compaction path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.compact import CompactAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.sdk_session import SDKExecutionSession

_COMPACT_MOD = "squadron.pipeline.actions.compact"


def _make_resolver(resolved: str = "claude-haiku-4-5-20251001") -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (resolved, None)
    return resolver


def _make_session(
    current_model: str | None = "claude-sonnet-4-6",
    compact_return: str = "summary-text",
) -> MagicMock:
    session = MagicMock(spec=SDKExecutionSession)
    session.current_model = current_model
    session.compact = AsyncMock(return_value=compact_return)
    return session


def _make_context(
    session: MagicMock | None = None,
    params: dict[str, object] | None = None,
    resolver: MagicMock | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-abcdef12",
        params=params or {},
        step_name="compact",
        step_index=2,
        prior_outputs={},
        resolver=resolver or _make_resolver(),
        cf_client=MagicMock(),
        cwd="/tmp/test",
        sdk_session=session,
    )


@pytest.fixture
def action() -> CompactAction:
    return CompactAction()


def _patch_template() -> object:
    mock_load = patch(f"{_COMPACT_MOD}.load_compaction_template")
    m = mock_load.start()
    m.return_value = MagicMock(
        name="default",
        description="test",
        instructions="Keep design for slice {slice}",
    )
    return mock_load


@pytest.mark.asyncio
async def test_sdk_with_model_resolves_and_passes_summary_model(
    action: CompactAction,
) -> None:
    session = _make_session(current_model="claude-sonnet-4-6")
    resolver = _make_resolver(resolved="haiku-id-xyz")
    ctx = _make_context(
        session=session, params={"slice": "154", "model": "haiku"}, resolver=resolver
    )
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    resolver.resolve.assert_called_once_with(action_model="haiku", step_model=None)
    session.compact.assert_awaited_once()
    kwargs = session.compact.await_args.kwargs
    assert kwargs["summary_model"] == "haiku-id-xyz"
    assert kwargs["restore_model"] == "claude-sonnet-4-6"
    assert result.success is True
    assert result.outputs["summary"] == "summary-text"
    assert result.outputs["source_step_index"] == 2
    assert result.outputs["source_step_name"] == "compact"
    assert result.outputs["summary_model"] == "haiku-id-xyz"
    assert "instructions" in result.outputs


@pytest.mark.asyncio
async def test_sdk_without_model_passes_none(action: CompactAction) -> None:
    session = _make_session(current_model="claude-sonnet-4-6")
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    kwargs = session.compact.await_args.kwargs
    assert kwargs["summary_model"] is None
    assert kwargs["restore_model"] == "claude-sonnet-4-6"
    assert result.success is True


@pytest.mark.asyncio
async def test_sdk_compact_exception_returns_failure(action: CompactAction) -> None:
    session = _make_session()
    session.compact = AsyncMock(side_effect=RuntimeError("boom"))
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    assert result.success is False
    assert result.error == "boom"


@pytest.mark.asyncio
async def test_non_sdk_path_uses_cf_compaction(action: CompactAction) -> None:
    """When sdk_session is None, CF compaction is used as before."""
    ctx = _make_context(session=None, params={"slice": "154"})
    mock_cf = MagicMock()
    mock_cf._run.return_value = "compact output"
    ctx.cf_client = mock_cf
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    mock_cf._run.assert_called()
    assert result.success is True
    assert "stdout" in result.outputs
