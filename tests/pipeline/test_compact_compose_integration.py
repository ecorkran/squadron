"""Integration tests for slice 169: compact-compose pipeline (T10).

Tests the summarize → compact → summarize(restore) compose pattern in both
prompt-only (no sdk_session) and true-CLI (sdk_session present) paths.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import ActionResult

_SDK = "claude_agent_sdk"


def _no_project_pipeline(name: str) -> object:
    return load_pipeline(
        name,
        project_dir=Path("/nonexistent"),
        user_dir=Path("/nonexistent"),
    )


def _make_compact_boundary_message() -> object:
    from claude_agent_sdk import SystemMessage

    return SystemMessage(
        subtype="compact_boundary",
        data={"compact_metadata": {"pre_tokens": 8000, "trigger": "manual"}},
    )


# ---------------------------------------------------------------------------
# Prompt-only compose: sdk_session is None, /compact dispatched via query()
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compact_compose_prompt_only_steps_use_real_compact_action() -> None:
    """Prompt-only: real CompactAction dispatches /compact, all 5 steps complete."""
    definition = _no_project_pipeline("test-compact-compose")

    async def _compact_boundary_gen(*a: object, **kw: object):  # type: ignore[no-untyped-def]
        yield _make_compact_boundary_message()

    dispatch_result = ActionResult(
        success=True, action_type="dispatch", outputs={"response": "async facts"}
    )
    summarize_result = ActionResult(
        success=True,
        action_type="summary",
        outputs={
            "summary": "the summarized content",
            "instructions": "summarize",
            "emit_results": [],
        },
    )

    call_count: list[int] = [0]

    async def _summary_execute(ctx: object) -> ActionResult:
        call_count[0] += 1
        if call_count[0] == 1:
            return summarize_result
        # restore mode — real action would pull from prior_outputs, but mock it
        return ActionResult(
            success=True,
            action_type="summary",
            outputs={"summary": "the summarized content", "restored": True},
        )

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(return_value=dispatch_result)

    summary_action = MagicMock()
    summary_action.execute = AsyncMock(side_effect=_summary_execute)

    # Import real CompactAction, patch query inside it
    from squadron.pipeline.actions.compact import CompactAction

    compact_action = CompactAction()

    with patch(f"{_SDK}.query", side_effect=_compact_boundary_gen):
        result = await execute_pipeline(
            definition,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            sdk_session=None,
            _action_registry={
                "dispatch": dispatch_action,
                "summary": summary_action,
                "compact": compact_action,
            },
        )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.step_results) == 5
    assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)

    # Confirm compact step outputs contain boundary metadata
    compact_step = result.step_results[2]
    assert compact_step.step_name == "compact-2"
    compact_ar = compact_step.action_results[0]
    assert compact_ar.outputs.get("pre_tokens") == 8000
    assert compact_ar.outputs.get("trigger") == "manual"


@pytest.mark.asyncio
async def test_compact_compose_no_dead_slash_command_text() -> None:
    """Regression: prompt-only compact must not return literal '/compact' as response text."""
    definition = _no_project_pipeline("test-compact-compose")
    from squadron.pipeline.actions.compact import CompactAction

    compact_action = CompactAction()

    dispatch_result = ActionResult(
        success=True, action_type="dispatch", outputs={"response": "some text"}
    )
    summarize_result = ActionResult(
        success=True,
        action_type="summary",
        outputs={"summary": "summary", "instructions": "x", "emit_results": []},
    )

    async def _compact_boundary_gen(*a: object, **kw: object):  # type: ignore[no-untyped-def]
        yield _make_compact_boundary_message()

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(return_value=dispatch_result)

    call_count: list[int] = [0]

    async def _summary_execute(ctx: object) -> ActionResult:
        call_count[0] += 1
        if call_count[0] == 1:
            return summarize_result
        return ActionResult(
            success=True,
            action_type="summary",
            outputs={"summary": "summary", "restored": True},
        )

    summary_action = MagicMock()
    summary_action.execute = AsyncMock(side_effect=_summary_execute)

    with patch(f"{_SDK}.query", side_effect=_compact_boundary_gen):
        result = await execute_pipeline(
            definition,
            {},
            resolver=MagicMock(),
            cf_client=MagicMock(),
            sdk_session=None,
            _action_registry={
                "dispatch": dispatch_action,
                "summary": summary_action,
                "compact": compact_action,
            },
        )

    assert result.status == ExecutionStatus.COMPLETED
    # Compact action outputs must not contain "/compact" as plain text
    compact_step = result.step_results[2]
    compact_ar = compact_step.action_results[0]
    response_text = str(compact_ar.outputs.get("response", ""))
    assert "/compact" not in response_text


# ---------------------------------------------------------------------------
# True CLI compose: sdk_session present, compact() rotate flow
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compact_compose_true_cli_all_steps_complete() -> None:
    """True CLI: CompactAction delegates to sdk_session.compact(), all 5 steps complete."""
    definition = _no_project_pipeline("test-compact-compose")
    from squadron.pipeline.actions.compact import CompactAction

    compact_action = CompactAction()

    session = MagicMock()
    session.current_model = "claude-sonnet-4"
    session.compact = AsyncMock(return_value="captured summary for rotation")
    session.seed_context = AsyncMock()

    dispatch_result = ActionResult(
        success=True, action_type="dispatch", outputs={"response": "async facts"}
    )
    summarize_result = ActionResult(
        success=True,
        action_type="summary",
        outputs={
            "summary": "summarized text",
            "instructions": "summarize",
            "emit_results": [],
        },
    )

    call_count: list[int] = [0]

    async def _summary_execute(ctx: object) -> ActionResult:
        call_count[0] += 1
        if call_count[0] == 1:
            return summarize_result
        return ActionResult(
            success=True,
            action_type="summary",
            outputs={"summary": "summarized text", "restored": True},
        )

    dispatch_action = MagicMock()
    dispatch_action.execute = AsyncMock(return_value=dispatch_result)

    summary_action = MagicMock()
    summary_action.execute = AsyncMock(side_effect=_summary_execute)

    result = await execute_pipeline(
        definition,
        {},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        sdk_session=session,
        _action_registry={
            "dispatch": dispatch_action,
            "summary": summary_action,
            "compact": compact_action,
        },
    )

    assert result.status == ExecutionStatus.COMPLETED
    assert len(result.step_results) == 5
    assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)

    # Confirm sdk_session.compact() was called (true-CLI rotate flow)
    session.compact.assert_awaited_once()
