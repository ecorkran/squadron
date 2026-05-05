"""Tests for DispatchAction profile-aware routing (slice 242).

Covers the five routing cases that branch _dispatch based on resolved
profile and sdk_session presence.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext, ActionResult

_P = "squadron.pipeline.actions.dispatch"


def _make_resolver(model_id: str, profile: str | None) -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, profile)
    return resolver


def _make_context(
    *,
    resolver: MagicMock,
    sdk_session: object = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    return ActionContext(  # type: ignore[arg-type]
        pipeline_name="test-pipeline",
        run_id="run-12345678",
        params=params or {"prompt": "test prompt"},
        step_name="dispatch",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd="/tmp/test",
        sdk_session=sdk_session,
    )


def _agent_result(profile: str) -> ActionResult:
    return ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"response": "agent response"},
        metadata={"model": "some-model", "profile": profile},
    )


def _session_result() -> ActionResult:
    return ActionResult(
        success=True,
        action_type="dispatch",
        outputs={"response": "session response"},
        metadata={"model": "claude-id", "profile": "sdk-session"},
    )


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


@pytest.mark.asyncio
async def test_dispatch_routes_to_agent_when_session_present_but_profile_non_sdk(
    action: DispatchAction,
) -> None:
    """T5a: session present but non-SDK profile → agent path."""
    resolver = _make_resolver("minimax-text-01", "openrouter")
    fake_session = MagicMock()
    ctx = _make_context(
        resolver=resolver,
        sdk_session=fake_session,
        params={"prompt": "test", "model": "minimax"},
    )
    expected = _agent_result("openrouter")

    with (
        patch.object(action, "_dispatch_via_agent", new=AsyncMock(return_value=expected)) as mock_agent,
        patch.object(
            action,
            "_dispatch_via_session",
            side_effect=AssertionError("should not be called"),
        ),
    ):
        result = await action._dispatch(ctx)

    mock_agent.assert_awaited_once_with(ctx)
    assert result.metadata["profile"] == "openrouter"


@pytest.mark.asyncio
async def test_dispatch_routes_to_session_when_profile_is_none(
    action: DispatchAction,
) -> None:
    """T5b: session present, resolver returns None profile → session path."""
    resolver = _make_resolver("claude-sonnet-4-20250514", None)
    fake_session = MagicMock()
    ctx = _make_context(resolver=resolver, sdk_session=fake_session)
    expected = _session_result()

    with (
        patch.object(
            action, "_dispatch_via_session", new=AsyncMock(return_value=expected)
        ) as mock_session,
        patch.object(
            action,
            "_dispatch_via_agent",
            side_effect=AssertionError("should not be called"),
        ),
    ):
        result = await action._dispatch(ctx)

    mock_session.assert_awaited_once_with(ctx, fake_session)
    assert result.metadata["profile"] == "sdk-session"


@pytest.mark.asyncio
async def test_dispatch_routes_to_session_for_explicit_sdk_profile(
    action: DispatchAction,
) -> None:
    """T5c: session present, resolver returns explicit 'sdk' profile → session path."""
    resolver = _make_resolver("claude-sonnet-4-20250514", "sdk")
    fake_session = MagicMock()
    ctx = _make_context(resolver=resolver, sdk_session=fake_session)
    expected = _session_result()

    with (
        patch.object(
            action, "_dispatch_via_session", new=AsyncMock(return_value=expected)
        ) as mock_session,
        patch.object(
            action,
            "_dispatch_via_agent",
            side_effect=AssertionError("should not be called"),
        ),
    ):
        result = await action._dispatch(ctx)

    mock_session.assert_awaited_once_with(ctx, fake_session)
    assert result.metadata["profile"] == "sdk-session"


@pytest.mark.asyncio
async def test_dispatch_routes_to_agent_when_no_session(
    action: DispatchAction,
) -> None:
    """T5d: no session present → agent path regardless of profile."""
    resolver = _make_resolver("minimax-text-01", "openrouter")
    ctx = _make_context(
        resolver=resolver,
        sdk_session=None,
        params={"prompt": "test", "model": "minimax"},
    )
    expected = _agent_result("openrouter")

    with (
        patch.object(action, "_dispatch_via_agent", new=AsyncMock(return_value=expected)) as mock_agent,
        patch.object(
            action,
            "_dispatch_via_session",
            side_effect=AssertionError("should not be called"),
        ),
    ):
        result = await action._dispatch(ctx)

    mock_agent.assert_awaited_once_with(ctx)
    assert result.metadata["profile"] == "openrouter"


@pytest.mark.asyncio
async def test_dispatch_mixed_pipeline_routes_per_step(
    action: DispatchAction,
) -> None:
    """T5e: two consecutive dispatches on the same instance route independently."""
    fake_session = MagicMock()

    claude_resolver = _make_resolver("claude-sonnet-4-20250514", None)
    minimax_resolver = _make_resolver("minimax-text-01", "openrouter")

    ctx_claude = _make_context(resolver=claude_resolver, sdk_session=fake_session)
    ctx_minimax = _make_context(
        resolver=minimax_resolver,
        sdk_session=fake_session,
        params={"prompt": "test", "model": "minimax"},
    )

    session_result = _session_result()
    agent_result = _agent_result("openrouter")

    with (
        patch.object(
            action, "_dispatch_via_session", new=AsyncMock(return_value=session_result)
        ) as mock_session,
        patch.object(
            action, "_dispatch_via_agent", new=AsyncMock(return_value=agent_result)
        ) as mock_agent,
    ):
        result_a = await action._dispatch(ctx_claude)
        result_b = await action._dispatch(ctx_minimax)

    mock_session.assert_awaited_once_with(ctx_claude, fake_session)
    mock_agent.assert_awaited_once_with(ctx_minimax)
    assert result_a.metadata["profile"] == "sdk-session"
    assert result_b.metadata["profile"] == "openrouter"
