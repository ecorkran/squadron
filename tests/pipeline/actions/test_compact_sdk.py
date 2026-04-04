"""Tests for CompactAction — SDK session compaction path."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from squadron.pipeline.actions.compact import CompactAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.sdk_session import SDKExecutionSession

_COMPACT_MOD = "squadron.pipeline.actions.compact"


def _make_resolver() -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-haiku-4-5-20251001", None)
    return resolver


def _make_session() -> MagicMock:
    session = MagicMock(spec=SDKExecutionSession)
    session.configure_compaction = MagicMock()
    return session


def _make_context(
    session: MagicMock | None = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-abcdef12",
        params=params or {},
        step_name="compact",
        step_index=2,
        prior_outputs={},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        cwd="/tmp/test",
        sdk_session=session,
    )


@pytest.fixture
def action() -> CompactAction:
    return CompactAction()


# ---------------------------------------------------------------------------
# SDK path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sdk_path_calls_configure_compaction(action: CompactAction) -> None:
    session = _make_session()
    ctx = _make_context(session=session)

    with patch(f"{_COMPACT_MOD}.load_compaction_template") as mock_load:
        mock_load.return_value = MagicMock(
            name="default",
            description="test",
            instructions="Keep {keep_section}",
        )
        await action.execute(ctx)

    session.configure_compaction.assert_called_once()
    call_kwargs = session.configure_compaction.call_args
    assert call_kwargs.kwargs["trigger_tokens"] == 50_000
    assert call_kwargs.kwargs["pause_after"] is True
    assert isinstance(call_kwargs.kwargs["instructions"], str)


@pytest.mark.asyncio
async def test_sdk_path_returns_success_with_compaction_configured(
    action: CompactAction,
) -> None:
    session = _make_session()
    ctx = _make_context(session=session)

    with patch(f"{_COMPACT_MOD}.load_compaction_template") as mock_load:
        mock_load.return_value = MagicMock(
            name="default",
            description="test",
            instructions="Keep things",
        )
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["compaction_configured"] is True
    assert "instructions" in result.outputs


@pytest.mark.asyncio
async def test_sdk_path_passes_rendered_instructions(action: CompactAction) -> None:
    """Instructions from the compact template are passed to configure_compaction."""
    session = _make_session()
    ctx = _make_context(
        session=session,
        params={"slice": "154"},
    )

    with patch(f"{_COMPACT_MOD}.load_compaction_template") as mock_load:
        mock_load.return_value = MagicMock(
            name="default",
            description="test",
            instructions="Keep design for slice {slice}",
        )
        result = await action.execute(ctx)

    call_instructions = session.configure_compaction.call_args.kwargs["instructions"]
    assert "154" in call_instructions
    assert result.outputs["instructions"] == call_instructions


# ---------------------------------------------------------------------------
# Non-SDK path unchanged
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_non_sdk_path_uses_cf_compaction(action: CompactAction) -> None:
    """When sdk_session is None, CF compaction is used as before."""
    ctx = _make_context(session=None)
    mock_cf = MagicMock()
    mock_cf._run.return_value = "compact output"
    ctx.cf_client = mock_cf

    with patch(f"{_COMPACT_MOD}.load_compaction_template") as mock_load:
        mock_load.return_value = MagicMock(
            name="default",
            description="test",
            instructions="Keep things",
        )
        result = await action.execute(ctx)

    mock_cf._run.assert_called()
    assert result.success is True
    assert "stdout" in result.outputs
