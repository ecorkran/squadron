"""Tests for CompactAction."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.compact import CompactAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext


@pytest.fixture
def action() -> CompactAction:
    return CompactAction()


@pytest.fixture
def mock_context() -> ActionContext:
    resolver = MagicMock()
    cf_client = MagicMock()
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params={},
        step_name="compact-step",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=cf_client,
        cwd="/tmp/test",
    )


# --- action_type ---


def test_action_type(action: CompactAction) -> None:
    assert action.action_type == "compact"


def test_protocol_compliance(action: CompactAction) -> None:
    assert isinstance(action, Action)


# --- validate() ---


def test_validate_empty_config(action: CompactAction) -> None:
    errors = action.validate({})
    assert errors == []


def test_validate_keep_as_list_of_strings(action: CompactAction) -> None:
    errors = action.validate({"keep": ["design", "tasks"]})
    assert errors == []


def test_validate_keep_as_non_list(action: CompactAction) -> None:
    errors = action.validate({"keep": "design"})
    assert len(errors) == 1
    assert errors[0].field == "keep"
    assert "list of strings" in errors[0].message


def test_validate_keep_as_list_with_non_strings(action: CompactAction) -> None:
    errors = action.validate({"keep": [1, 2]})
    assert len(errors) == 1
    assert errors[0].field == "keep"


def test_validate_summarize_as_bool(action: CompactAction) -> None:
    errors = action.validate({"summarize": True})
    assert errors == []


def test_validate_summarize_as_non_bool(action: CompactAction) -> None:
    errors = action.validate({"summarize": "yes"})
    assert len(errors) == 1
    assert errors[0].field == "summarize"
    assert "boolean" in errors[0].message


def test_validate_template_as_string(action: CompactAction) -> None:
    errors = action.validate({"template": "custom"})
    assert errors == []


def test_validate_template_as_non_string(action: CompactAction) -> None:
    errors = action.validate({"template": 42})
    assert len(errors) == 1
    assert errors[0].field == "template"
    assert "string" in errors[0].message


# --- execute() ---


@pytest.mark.asyncio
async def test_execute_happy_path(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"keep": ["design", "tasks"], "summarize": True}
    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    assert result.success is True
    assert result.action_type == "compact"
    assert "stdout" in result.outputs
    assert "instructions" in result.outputs
    assert "summarize_stdout" in result.outputs
    # Should have called _run twice: compact + summarize
    assert mock_context.cf_client._run.call_count == 2  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_execute_template_rendering_includes_keep(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"keep": ["design", "tasks"]}
    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    instructions = str(result.outputs["instructions"])
    assert "design" in instructions
    assert "tasks" in instructions


@pytest.mark.asyncio
async def test_execute_cf_error(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {}
    mock_context.cf_client._run = MagicMock(  # type: ignore[union-attr]
        side_effect=ContextForgeError("compact failed")
    )

    result = await action.execute(mock_context)

    assert result.success is False
    assert result.error == "compact failed"


@pytest.mark.asyncio
async def test_execute_summarize_triggers_cf_summarize(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"summarize": True}
    mock_context.cf_client._run = MagicMock(return_value="done")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    assert result.success is True
    calls = mock_context.cf_client._run.call_args_list  # type: ignore[union-attr]
    # Second call should be summarize
    assert calls[1][0][0] == ["summarize"]


@pytest.mark.asyncio
async def test_execute_no_keep_no_summarize(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {}
    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    assert result.success is True
    # Only one call (compact), no summarize
    assert mock_context.cf_client._run.call_count == 1  # type: ignore[union-attr]
    assert "summarize_stdout" not in result.outputs


@pytest.mark.asyncio
async def test_execute_custom_template(
    action: CompactAction,
    mock_context: ActionContext,
    tmp_path: Path,
) -> None:
    # Create a custom template
    custom_dir = tmp_path / "compaction"
    custom_dir.mkdir()
    (custom_dir / "custom.yaml").write_text(
        "name: custom\n"
        "description: Custom template\n"
        "instructions: |\n"
        "  Custom instructions\n"
        "  {keep_section}\n"
        "  {summarize_section}\n"
    )

    mock_context.params = {"template": "custom"}
    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]

    # Patch the user dir to use our tmp_path (constant now lives in compaction_templates)
    import squadron.pipeline.compaction_templates as ct_mod

    original_dir = ct_mod._USER_COMPACTION_DIR
    ct_mod._USER_COMPACTION_DIR = custom_dir
    try:
        result = await action.execute(mock_context)
    finally:
        ct_mod._USER_COMPACTION_DIR = original_dir

    assert result.success is True
    instructions = str(result.outputs["instructions"])
    assert "Custom instructions" in instructions


@pytest.mark.asyncio
async def test_execute_missing_template(
    action: CompactAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"template": "nonexistent"}

    result = await action.execute(mock_context)

    assert result.success is False
    assert "not found" in str(result.error)


# ---------------------------------------------------------------------------
# T13 (slice 164) — compact-via-summary inheritance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_compact_non_sdk_profile_non_rotate_emit_succeeds(
    action: CompactAction,
    mock_context: ActionContext,
) -> None:
    """Compact with SDK session + non-SDK model + non-rotate emit delegates to
    _execute_summary which uses the non-SDK provider path — no compact-specific
    code is needed."""
    from unittest.mock import AsyncMock, patch

    from squadron.pipeline.models import ActionResult

    mock_context.sdk_session = MagicMock()  # type: ignore[attr-defined]
    mock_context.params = {"model": "minimax"}

    fake_result = ActionResult(
        success=True,
        action_type="compact",
        outputs={"summary": "COMPACT SUMMARY"},
    )

    # compact imports _execute_summary from summary at call time — patch there
    with patch(
        "squadron.pipeline.actions.summary._execute_summary",
        new=AsyncMock(return_value=fake_result),
    ) as mock_execute:
        result = await action.execute(mock_context)

    assert result.success is True
    mock_execute.assert_called_once()
    # Confirm compact passes action_type="compact" (not "summary")
    call_kwargs = mock_execute.call_args.kwargs
    assert call_kwargs["action_type"] == "compact"


@pytest.mark.asyncio
async def test_compact_non_sdk_profile_with_rotate_fails(
    action: CompactAction,
    mock_context: ActionContext,
) -> None:
    """_execute_summary validation: non-SDK profile + ROTATE fails with 'rotate' error.

    Compact always passes EmitKind.ROTATE to _execute_summary.  This test
    calls _execute_summary directly (the shared helper) to verify the error
    message shape when a non-SDK profile is paired with ROTATE.
    """
    from unittest.mock import AsyncMock, patch

    from squadron.pipeline.actions.summary import _execute_summary
    from squadron.pipeline.emit import EmitDestination, EmitKind

    ctx = MagicMock()
    ctx.sdk_session = MagicMock()
    ctx.resolver = MagicMock()
    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")
    ctx.step_index = 0
    ctx.step_name = "compact-step"

    with patch(
        "squadron.pipeline.actions.summary.capture_summary_via_profile",
        new=AsyncMock(return_value="SHOULD NOT REACH"),
    ) as mock_oneshot:
        result = await _execute_summary(
            context=ctx,
            instructions="summarize",
            summary_model_alias="minimax",
            emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
            action_type="compact",
        )

    assert result.success is False
    assert result.error is not None
    assert "rotate" in result.error.lower()
    mock_oneshot.assert_not_called()
