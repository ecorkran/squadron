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

    # Patch the user dir to use our tmp_path
    import squadron.pipeline.actions.compact as compact_mod

    original_dir = compact_mod._USER_COMPACTION_DIR
    compact_mod._USER_COMPACTION_DIR = custom_dir
    try:
        result = await action.execute(mock_context)
    finally:
        compact_mod._USER_COMPACTION_DIR = original_dir

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
