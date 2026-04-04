"""Tests for SDK executor wiring — executor propagation and CLI session lifecycle."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.executor import execute_pipeline
from squadron.pipeline.models import (
    ActionContext,
    ActionResult,
    PipelineDefinition,
    StepConfig,
)
from squadron.pipeline.sdk_session import SDKExecutionSession
from squadron.pipeline.steps import register_step_type

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pipeline(step_type: str = "_test_wiring") -> PipelineDefinition:
    return PipelineDefinition(
        name="test-pipeline",
        description="test",
        params={},
        steps=[StepConfig(step_type=step_type, name="step-0", config={})],
    )


def _make_capturing_action() -> tuple[MagicMock, list[ActionContext]]:
    """Return a mock action + capture list for verifying ActionContext fields."""
    captured: list[ActionContext] = []

    mock_action = MagicMock()
    mock_action.action_type = "dispatch"
    mock_action.validate = MagicMock(return_value=[])

    async def _capture(ctx: ActionContext) -> ActionResult:
        captured.append(ctx)
        return ActionResult(success=True, action_type="dispatch", outputs={})

    mock_action.execute = _capture
    return mock_action, captured


def _make_step_type_mock(action_type: str = "dispatch") -> MagicMock:
    step = MagicMock()
    step.expand.return_value = [(action_type, {})]
    return step


def _make_session() -> AsyncMock:
    session = AsyncMock(spec=SDKExecutionSession)
    session.connect = AsyncMock()
    session.disconnect = AsyncMock()
    return session


# ---------------------------------------------------------------------------
# Executor propagation tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_execute_pipeline_propagates_sdk_session() -> None:
    """execute_pipeline with sdk_session passes it into ActionContext."""
    mock_action, captured = _make_capturing_action()
    session = _make_session()
    pipeline = _make_pipeline("_test_wiring_session")

    step = _make_step_type_mock("dispatch")
    register_step_type("_test_wiring_session", step)

    await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry={"dispatch": mock_action},
    )

    assert len(captured) == 1
    assert captured[0].sdk_session is session


@pytest.mark.asyncio
async def test_execute_pipeline_session_none_propagates_none() -> None:
    """execute_pipeline with sdk_session=None passes None to ActionContext."""
    mock_action, captured = _make_capturing_action()
    pipeline = _make_pipeline("_test_wiring_none")

    step = _make_step_type_mock("dispatch")
    register_step_type("_test_wiring_none", step)

    await execute_pipeline(
        pipeline,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        sdk_session=None,
        _action_registry={"dispatch": mock_action},
    )

    assert len(captured) == 1
    assert captured[0].sdk_session is None


# ---------------------------------------------------------------------------
# CLI session lifecycle tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_pipeline_sdk_connects_and_disconnects_on_success() -> None:
    """_run_pipeline_sdk connects before run and disconnects after success."""
    from squadron.cli.commands.run import _run_pipeline_sdk
    from squadron.pipeline.executor import ExecutionStatus, PipelineResult

    success_result = PipelineResult(
        pipeline_name="test", status=ExecutionStatus.COMPLETED, step_results=[]
    )

    mock_session = AsyncMock(spec=SDKExecutionSession)
    mock_session.connect = AsyncMock()
    mock_session.disconnect = AsyncMock()

    with (
        patch("squadron.cli.commands.run._resolve_execution_mode"),
        patch(
            "squadron.cli.commands.run._run_pipeline",
            new_callable=AsyncMock,
            return_value=success_result,
        ),
        patch("claude_agent_sdk.ClaudeSDKClient"),
        patch("claude_agent_sdk.ClaudeAgentOptions"),
        patch(
            "squadron.cli.commands.run.SDKExecutionSession",
            return_value=mock_session,
        ),
    ):
        result = await _run_pipeline_sdk("test-pipeline", {})

    assert result is success_result
    mock_session.connect.assert_called_once()
    mock_session.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_run_pipeline_sdk_disconnects_on_failure() -> None:
    """_run_pipeline_sdk disconnects even when _run_pipeline raises."""
    from squadron.cli.commands.run import _run_pipeline_sdk

    mock_session = AsyncMock(spec=SDKExecutionSession)
    mock_session.connect = AsyncMock()
    mock_session.disconnect = AsyncMock()

    with (
        patch("squadron.cli.commands.run._resolve_execution_mode"),
        patch(
            "squadron.cli.commands.run._run_pipeline",
            new_callable=AsyncMock,
            side_effect=RuntimeError("pipeline crashed"),
        ),
        patch("claude_agent_sdk.ClaudeSDKClient"),
        patch("claude_agent_sdk.ClaudeAgentOptions"),
        patch(
            "squadron.cli.commands.run.SDKExecutionSession",
            return_value=mock_session,
        ),
    ):
        with pytest.raises(RuntimeError, match="pipeline crashed"):
            await _run_pipeline_sdk("test-pipeline", {})

    mock_session.connect.assert_called_once()
    mock_session.disconnect.assert_called_once()
