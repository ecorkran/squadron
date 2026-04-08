"""Tests for DispatchAction — SDK session dispatch path."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionContext
from squadron.pipeline.sdk_session import SDKExecutionSession
from squadron.providers.errors import ProviderError


def _make_resolver(model_id: str = "claude-haiku-4-5-20251001") -> MagicMock:
    resolver = MagicMock()
    resolver.resolve.return_value = (model_id, None)
    return resolver


def _make_session(response: str = "session response") -> AsyncMock:
    session = AsyncMock(spec=SDKExecutionSession)
    session.set_model = AsyncMock()
    session.dispatch = AsyncMock(return_value=response)
    return session


def _make_context(
    session: AsyncMock | None = None,
    params: dict[str, object] | None = None,
    model_id: str = "claude-haiku-4-5-20251001",
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-abcdef12",
        params=params or {"prompt": "do the thing"},
        step_name="design",
        step_index=0,
        prior_outputs={},
        resolver=_make_resolver(model_id),
        cf_client=MagicMock(),
        cwd="/tmp/test",
        sdk_session=session,
    )


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_routes_to_session_path_when_session_present(
    action: DispatchAction,
) -> None:
    session = _make_session()
    ctx = _make_context(session=session)
    result = await action.execute(ctx)
    session.dispatch.assert_called_once()
    assert result.success is True


@pytest.mark.asyncio
async def test_routes_to_agent_path_when_session_none(
    action: DispatchAction,
) -> None:
    """When sdk_session is None, the agent path is used (not session)."""
    from unittest.mock import patch

    from squadron.providers.profiles import ProviderProfile
    from tests.pipeline.actions.test_dispatch import _make_agent_mock, _make_registry

    ctx = _make_context(session=None)
    mock_agent = _make_agent_mock("agent response")
    mock_registry = _make_registry(mock_agent)
    sdk_profile = ProviderProfile(
        name="sdk", provider="sdk", api_key_env=None, description="test"
    )

    with (
        patch(
            "squadron.pipeline.actions.dispatch.get_registry",
            return_value=mock_registry,
        ),
        patch(
            "squadron.pipeline.actions.dispatch.get_profile", return_value=sdk_profile
        ),
        patch("squadron.pipeline.actions.dispatch.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["response"] == "agent response"


# ---------------------------------------------------------------------------
# Session path — model resolution and set_model
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_dispatch_calls_set_model_with_resolved_id(
    action: DispatchAction,
) -> None:
    session = _make_session()
    ctx = _make_context(session=session, model_id="claude-haiku-4-5-20251001")
    await action.execute(ctx)
    session.set_model.assert_called_once_with("claude-haiku-4-5-20251001")


@pytest.mark.asyncio
async def test_session_dispatch_calls_dispatch_with_prompt(
    action: DispatchAction,
) -> None:
    session = _make_session()
    ctx = _make_context(session=session, params={"prompt": "design the slice"})
    await action.execute(ctx)
    session.dispatch.assert_called_once_with("design the slice")


@pytest.mark.asyncio
async def test_session_dispatch_returns_action_result_with_response(
    action: DispatchAction,
) -> None:
    session = _make_session(response="the design output")
    ctx = _make_context(session=session)
    result = await action.execute(ctx)
    assert result.success is True
    assert result.outputs["response"] == "the design output"
    assert result.metadata["model"] == "claude-haiku-4-5-20251001"


@pytest.mark.asyncio
async def test_session_dispatch_uses_model_and_step_model_params(
    action: DispatchAction,
) -> None:
    session = _make_session()
    resolver = _make_resolver("claude-opus-4-6")
    ctx = ActionContext(
        pipeline_name="p",
        run_id="r",
        params={"prompt": "go", "model": "opus", "step_model": "haiku"},
        step_name="design",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=MagicMock(),
        cwd="/tmp",
        sdk_session=session,
    )
    await action.execute(ctx)
    resolver.resolve.assert_called_once_with("opus", "haiku")
    session.set_model.assert_called_once_with("claude-opus-4-6")


# ---------------------------------------------------------------------------
# Session path — error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_session_dispatch_failure_returns_action_result_false(
    action: DispatchAction,
) -> None:
    session = _make_session()
    session.dispatch.side_effect = ProviderError("connection dropped")
    ctx = _make_context(session=session)
    result = await action.execute(ctx)
    assert result.success is False
    assert "connection dropped" in (result.error or "")


@pytest.mark.asyncio
async def test_session_dispatch_cli_error_response_returns_failure(
    action: DispatchAction,
) -> None:
    """CLI API errors surfaced as text (e.g. '500 Internal Server Error') must
    not be treated as successful dispatch — executor uses result.success for
    flow control and must not proceed to review/checkpoint on a failed call."""
    error_text = (
        'API Error: 500 {"type":"error","error":{"type":"api_error",'
        '"message":"Internal server error"}}'
    )
    session = _make_session(response=error_text)
    ctx = _make_context(session=session)
    result = await action.execute(ctx)
    assert result.success is False
    assert result.error == error_text
    assert result.outputs["response"] == error_text
