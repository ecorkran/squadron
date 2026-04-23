"""Tests for CompactAction — true-CLI rotate and prompt-only /compact dispatch."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.compact import CompactAction
from squadron.pipeline.models import ActionContext

_MOD = "squadron.pipeline.actions.compact"
_SDK = "claude_agent_sdk"


@pytest.fixture
def action() -> CompactAction:
    return CompactAction()


def _make_context(
    sdk_session: object = None,
    params: dict[str, object] | None = None,
) -> ActionContext:
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-abc123",
        params=params or {},
        step_name="compact-step",
        step_index=1,
        prior_outputs={},
        resolver=MagicMock(),
        cf_client=MagicMock(),
        cwd="/tmp",
        sdk_session=sdk_session,
    )


# ---------------------------------------------------------------------------
# action_type and validate
# ---------------------------------------------------------------------------


def test_action_type(action: CompactAction) -> None:
    assert action.action_type == "compact"


def test_validate_no_params(action: CompactAction) -> None:
    assert action.validate({}) == []


def test_validate_instructions_string(action: CompactAction) -> None:
    assert action.validate({"instructions": "keep recent work verbatim"}) == []


def test_validate_instructions_non_string(action: CompactAction) -> None:
    errors = action.validate({"instructions": 42})
    assert len(errors) == 1
    assert errors[0].field == "instructions"


def test_validate_model_string(action: CompactAction) -> None:
    assert action.validate({"model": "sonnet"}) == []


def test_validate_model_non_string(action: CompactAction) -> None:
    errors = action.validate({"model": 99})
    assert len(errors) == 1
    assert errors[0].field == "model"


# ---------------------------------------------------------------------------
# T5 — True CLI rotate branch
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_true_cli_calls_sdk_compact(action: CompactAction) -> None:
    session = MagicMock()
    session.current_model = "claude-sonnet-4-20250514"
    session.compact = AsyncMock(return_value="summary text")
    ctx = _make_context(sdk_session=session)

    result = await action.execute(ctx)

    assert result.success is True
    session.compact.assert_awaited_once()


@pytest.mark.asyncio
async def test_true_cli_forwards_instructions(action: CompactAction) -> None:
    session = MagicMock()
    session.current_model = None
    session.compact = AsyncMock(return_value="summary")
    ctx = _make_context(
        sdk_session=session, params={"instructions": "keep recent work"}
    )

    await action.execute(ctx)

    call_kwargs = session.compact.call_args
    assert call_kwargs.kwargs.get("instructions") == "keep recent work"


@pytest.mark.asyncio
async def test_true_cli_forwards_model(action: CompactAction) -> None:
    session = MagicMock()
    session.current_model = "claude-opus-4"
    session.compact = AsyncMock(return_value="summary")
    ctx = _make_context(sdk_session=session, params={"model": "haiku"})

    await action.execute(ctx)

    call_kwargs = session.compact.call_args
    assert call_kwargs.kwargs.get("summary_model") == "haiku"


@pytest.mark.asyncio
async def test_true_cli_passes_restore_model(action: CompactAction) -> None:
    session = MagicMock()
    session.current_model = "claude-sonnet-4"
    session.compact = AsyncMock(return_value="summary")
    ctx = _make_context(sdk_session=session)

    await action.execute(ctx)

    call_kwargs = session.compact.call_args
    assert call_kwargs.kwargs.get("restore_model") == "claude-sonnet-4"


@pytest.mark.asyncio
async def test_true_cli_returns_failed_on_exception(action: CompactAction) -> None:
    session = MagicMock()
    session.current_model = None
    session.compact = AsyncMock(side_effect=RuntimeError("sdk blew up"))
    ctx = _make_context(sdk_session=session)

    result = await action.execute(ctx)

    assert result.success is False
    assert "sdk blew up" in (result.error or "")


# ---------------------------------------------------------------------------
# T6 — Prompt-only /compact dispatch branch
# ---------------------------------------------------------------------------


def _make_compact_boundary_message() -> object:
    """Build a synthetic SystemMessage(subtype='compact_boundary')."""
    from claude_agent_sdk import SystemMessage

    return SystemMessage(
        subtype="compact_boundary",
        data={"compact_metadata": {"pre_tokens": 5000, "trigger": "manual"}},
    )


@pytest.mark.asyncio
async def test_prompt_only_dispatches_compact(action: CompactAction) -> None:
    ctx = _make_context(sdk_session=None)

    async def _gen(*a: object, **kw: object) -> AsyncIterator[object]:
        yield _make_compact_boundary_message()

    with patch(f"{_SDK}.query", side_effect=_gen):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["pre_tokens"] == 5000
    assert result.outputs["trigger"] == "manual"
    assert "compacted_at" in result.outputs


@pytest.mark.asyncio
async def test_prompt_only_includes_instructions_in_prompt(
    action: CompactAction,
) -> None:
    ctx = _make_context(
        sdk_session=None, params={"instructions": "keep recent context"}
    )
    captured_prompt: list[str] = []

    async def _gen(prompt: str, **kw: object) -> AsyncIterator[object]:
        captured_prompt.append(prompt)
        yield _make_compact_boundary_message()

    with patch(f"{_SDK}.query", side_effect=_gen):
        await action.execute(ctx)

    assert len(captured_prompt) == 1
    assert captured_prompt[0].startswith("/compact")
    assert "keep recent context" in captured_prompt[0]


@pytest.mark.asyncio
async def test_prompt_only_no_instructions_sends_bare_compact(
    action: CompactAction,
) -> None:
    ctx = _make_context(sdk_session=None)
    captured_prompt: list[str] = []

    async def _gen(prompt: str, **kw: object) -> AsyncIterator[object]:
        captured_prompt.append(prompt)
        yield _make_compact_boundary_message()

    with patch(f"{_SDK}.query", side_effect=_gen):
        await action.execute(ctx)

    assert captured_prompt[0] == "/compact"


@pytest.mark.asyncio
async def test_prompt_only_waits_for_boundary_after_other_messages(
    action: CompactAction,
) -> None:
    """Action must not return until compact_boundary arrives."""
    from claude_agent_sdk import AssistantMessage, SystemMessage, TextBlock

    ctx = _make_context(sdk_session=None)

    async def _gen(*a: object, **kw: object) -> AsyncIterator[object]:
        yield AssistantMessage(
            content=[TextBlock(text="compacting...")], model="claude-sonnet-4"
        )
        yield SystemMessage(subtype="other_event", data={})
        yield _make_compact_boundary_message()

    with patch(f"{_SDK}.query", side_effect=_gen):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["pre_tokens"] == 5000


@pytest.mark.asyncio
async def test_prompt_only_timeout_raises(action: CompactAction) -> None:
    """TimeoutError raised when compact_boundary never arrives."""
    ctx = _make_context(sdk_session=None, params={"_compact_timeout_s": 0.05})

    async def _gen(*a: object, **kw: object) -> AsyncIterator[object]:
        await asyncio.sleep(10)  # never delivers boundary
        yield  # unreachable

    with patch(f"{_SDK}.query", side_effect=_gen):
        with pytest.raises(TimeoutError):
            await action.execute(ctx)
