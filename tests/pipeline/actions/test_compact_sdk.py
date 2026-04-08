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
    capture_return: str = "summary-text",
) -> MagicMock:
    session = MagicMock(spec=SDKExecutionSession)
    session.current_model = current_model
    session.capture_summary = AsyncMock(return_value=capture_return)
    session.compact = AsyncMock(return_value=capture_return)
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
async def test_sdk_with_model_resolves_and_captures_summary(
    action: CompactAction,
) -> None:
    """Compact SDK path: resolves model alias, calls capture_summary then compact."""
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
    # capture_summary is called with the resolved model
    session.capture_summary.assert_awaited_once()
    cap_kwargs = session.capture_summary.await_args.kwargs
    assert cap_kwargs["summary_model"] == "haiku-id-xyz"
    # rotate emit calls compact with the captured summary
    session.compact.assert_awaited_once()
    rot_kwargs = session.compact.await_args.kwargs
    assert rot_kwargs["summary"] == "summary-text"
    assert result.success is True
    assert result.outputs["summary"] == "summary-text"
    assert result.outputs["source_step_index"] == 2
    assert result.outputs["source_step_name"] == "compact"
    assert result.outputs["summary_model"] == "haiku-id-xyz"
    assert "instructions" in result.outputs


@pytest.mark.asyncio
async def test_sdk_without_model_passes_none_to_capture(action: CompactAction) -> None:
    session = _make_session(current_model="claude-sonnet-4-6")
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    cap_kwargs = session.capture_summary.await_args.kwargs
    assert cap_kwargs["summary_model"] is None
    assert result.success is True


@pytest.mark.asyncio
async def test_sdk_capture_exception_returns_failure(action: CompactAction) -> None:
    session = _make_session()
    session.capture_summary = AsyncMock(side_effect=RuntimeError("boom"))
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    assert result.success is False
    assert result.error == "boom"


@pytest.mark.asyncio
async def test_sdk_rotate_exception_returns_failure(action: CompactAction) -> None:
    session = _make_session()
    session.compact = AsyncMock(side_effect=RuntimeError("rotate failed"))
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    assert result.success is False
    assert "rotate failed" in (result.error or "")


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


@pytest.mark.asyncio
async def test_sdk_action_type_stays_compact(action: CompactAction) -> None:
    """action_type must remain 'compact' for state-callback persistence."""
    session = _make_session()
    ctx = _make_context(session=session, params={"slice": "154"})
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    assert result.action_type == "compact"


@pytest.mark.asyncio
async def test_sdk_outputs_compatible_with_state_callback(
    action: CompactAction,
) -> None:
    """Outputs include all keys read by _maybe_record_compact_summaries."""
    session = _make_session()
    ctx = _make_context(
        session=session, params={"slice": "154"}, resolver=_make_resolver("model-x")
    )
    p = _patch_template()
    try:
        result = await action.execute(ctx)
    finally:
        p.stop()

    assert result.success is True
    outputs = result.outputs
    assert "summary" in outputs
    assert "source_step_index" in outputs
    assert "source_step_name" in outputs
    assert "summary_model" in outputs
    assert "instructions" in outputs


def test_state_callback_still_records_compact_summary_after_refactor(
    tmp_path: object,
) -> None:
    """Regression: _maybe_record_compact_summaries fires on compact action_type.

    Simulates the full callback path with an ActionResult shaped like what
    the refactored CompactAction produces.
    """
    from pathlib import Path

    from squadron.pipeline.executor import ExecutionStatus, StepResult
    from squadron.pipeline.models import ActionResult
    from squadron.pipeline.state import StateManager

    assert isinstance(tmp_path, Path)
    mgr = StateManager(runs_dir=tmp_path)
    run_id = mgr.init_run("test-pipeline", {"slice": "154"})
    cb = mgr.make_step_callback(run_id)

    ar = ActionResult(
        success=True,
        action_type="compact",  # stays "compact" after refactor
        outputs={
            "summary": "the summary text",
            "instructions": "compact this",
            "source_step_index": 3,
            "source_step_name": "compact-mid",
            "summary_model": "haiku-id",
            "emit_results": [
                {"destination": "rotate", "ok": True, "detail": "session rotated"}
            ],
        },
    )
    step_result = StepResult(
        step_name="compact-mid",
        step_type="compact",
        action_results=[ar],
        status=ExecutionStatus.COMPLETED,
    )
    cb(step_result)

    state = mgr.load(run_id)
    assert "3:compact-mid" in state.compact_summaries
    cs = state.compact_summaries["3:compact-mid"]
    assert cs.text == "the summary text"
    assert cs.summary_model == "haiku-id"
