"""Integration tests for the full SDK pipeline executor cycle.

Uses a real test-pipeline definition with mocked action implementations
to verify the execution flow end-to-end without real LLM calls.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionContext, ActionResult
from squadron.pipeline.sdk_session import SDKExecutionSession

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_session() -> AsyncMock:
    session = AsyncMock(spec=SDKExecutionSession)
    session.set_model = AsyncMock()
    session.dispatch = AsyncMock(return_value="mock response")
    session.configure_compaction = MagicMock()
    session.connect = AsyncMock()
    session.disconnect = AsyncMock()
    return session


def _make_resolver(model_id: str = "claude-haiku-4-5-20251001") -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, None)
    return resolver


def _success(action_type: str, **extra_outputs: object) -> ActionResult:
    return ActionResult(
        success=True,
        action_type=action_type,
        outputs=dict(extra_outputs),
    )


def _paused_checkpoint() -> ActionResult:
    return ActionResult(
        success=True,
        action_type="checkpoint",
        outputs={"checkpoint": "paused"},
    )


def _pass_review() -> ActionResult:
    return ActionResult(
        success=True,
        action_type="review",
        outputs={"verdict": "PASS"},
        verdict="PASS",
    )


def _make_full_registry(
    *,
    dispatch_fn: AsyncMock | None = None,
    review_fn: AsyncMock | None = None,
    compact_fn: AsyncMock | None = None,
    checkpoint_fn: AsyncMock | None = None,
) -> dict[str, object]:
    """Build a complete action registry with optional overrides."""

    def _make(action_type: str, result: ActionResult) -> MagicMock:
        m = MagicMock()
        m.action_type = action_type
        m.validate = MagicMock(return_value=[])
        m.execute = AsyncMock(return_value=result)
        return m

    def _make_with_fn(action_type: str, fn: AsyncMock) -> MagicMock:
        m = MagicMock()
        m.action_type = action_type
        m.validate = MagicMock(return_value=[])
        m.execute = fn
        return m

    registry: dict[str, object] = {
        "cf-op": _make("cf-op", _success("cf-op")),
        "commit": _make("commit", _success("commit")),
    }

    if dispatch_fn is not None:
        registry["dispatch"] = _make_with_fn("dispatch", dispatch_fn)
    else:
        registry["dispatch"] = _make(
            "dispatch",
            ActionResult(
                success=True,
                action_type="dispatch",
                outputs={"response": "design output"},
                metadata={
                    "model": "claude-haiku-4-5-20251001",
                    "profile": "sdk-session",
                },
            ),
        )

    if review_fn is not None:
        registry["review"] = _make_with_fn("review", review_fn)
    else:
        registry["review"] = _make("review", _pass_review())

    if compact_fn is not None:
        registry["compact"] = _make_with_fn("compact", compact_fn)
    else:
        registry["compact"] = _make(
            "compact",
            ActionResult(
                success=True,
                action_type="compact",
                outputs={"compaction_configured": True, "instructions": "Keep things"},
            ),
        )

    if checkpoint_fn is not None:
        registry["checkpoint"] = _make_with_fn("checkpoint", checkpoint_fn)
    else:
        registry["checkpoint"] = _make("checkpoint", _success("checkpoint"))

    return registry


# ---------------------------------------------------------------------------
# T18: Full pipeline cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_full_pipeline_cycle_completes() -> None:
    """Full pipeline runs to completion with mock session."""
    session = _make_mock_session()
    definition = load_pipeline("test-pipeline")

    result = await execute_pipeline(
        definition,
        {"slice": "154"},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry=_make_full_registry(),
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.step_results) == 3


@pytest.mark.asyncio
async def test_sdk_session_propagated_to_all_dispatch_contexts() -> None:
    """Session is in ActionContext for all dispatch actions."""
    session = _make_mock_session()
    definition = load_pipeline("test-pipeline")

    captured: list[ActionContext] = []

    async def _capture(ctx: ActionContext) -> ActionResult:
        captured.append(ctx)
        return ActionResult(
            success=True,
            action_type="dispatch",
            outputs={"response": "output"},
            metadata={"model": "claude-haiku-4-5-20251001", "profile": "sdk-session"},
        )

    result = await execute_pipeline(
        definition,
        {"slice": "154"},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry=_make_full_registry(dispatch_fn=_capture),
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(captured) >= 2  # design + tasks dispatch steps
    for ctx in captured:
        assert ctx.sdk_session is session


@pytest.mark.asyncio
async def test_compact_step_receives_session() -> None:
    """Compact action context has the SDK session."""
    session = _make_mock_session()
    definition = load_pipeline("test-pipeline")

    captured_compact: list[ActionContext] = []

    async def _capture_compact(ctx: ActionContext) -> ActionResult:
        captured_compact.append(ctx)
        return ActionResult(
            success=True,
            action_type="compact",
            outputs={"compaction_configured": True, "instructions": "Keep things"},
        )

    result = await execute_pipeline(
        definition,
        {"slice": "154"},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry=_make_full_registry(compact_fn=_capture_compact),
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(captured_compact) == 1
    assert captured_compact[0].sdk_session is session


@pytest.mark.asyncio
async def test_checkpoint_pauses_returns_paused_status() -> None:
    """When checkpoint fires, pipeline returns PAUSED status."""
    session = _make_mock_session()
    definition = load_pipeline("test-pipeline")

    result = await execute_pipeline(
        definition,
        {"slice": "154"},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry=_make_full_registry(
            checkpoint_fn=AsyncMock(return_value=_paused_checkpoint())
        ),
    )

    assert result.status == ExecutionStatus.PAUSED
    assert result.paused_at is not None


@pytest.mark.asyncio
async def test_review_actions_context_has_session_but_review_does_not_call_it() -> None:
    """Review actions have session in context but don't call session methods.

    The real ReviewAction uses subprocess dispatch (existing review system),
    not the SDK session. This test simulates that behavior.
    """
    session = _make_mock_session()
    definition = load_pipeline("test-pipeline")

    review_contexts: list[ActionContext] = []

    async def _capture_review(ctx: ActionContext) -> ActionResult:
        # Simulate review action: receives session in context but doesn't use it
        review_contexts.append(ctx)
        return _pass_review()

    result = await execute_pipeline(
        definition,
        {"slice": "154"},
        resolver=_make_resolver(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry=_make_full_registry(review_fn=_capture_review),
    )

    assert result.status == ExecutionStatus.COMPLETED
    # Reviews were called with session in context
    assert len(review_contexts) >= 1
    for ctx in review_contexts:
        assert ctx.sdk_session is session

    # The mock review fn never called session methods (simulating real behavior)
    session.set_model.assert_not_called()
    session.dispatch.assert_not_called()
