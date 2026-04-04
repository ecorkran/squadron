"""Tests for CfOpAction."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from squadron.integrations.context_forge import ContextForgeError
from squadron.pipeline.actions.cf_op import CfOpAction, CfOperation
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext, ActionResult


@pytest.fixture
def action() -> CfOpAction:
    return CfOpAction()


@pytest.fixture
def mock_context() -> ActionContext:
    resolver = MagicMock()
    cf_client = MagicMock()
    return ActionContext(
        pipeline_name="test-pipeline",
        run_id="run-001",
        params={},
        step_name="cf-step",
        step_index=0,
        prior_outputs={},
        resolver=resolver,
        cf_client=cf_client,
        cwd="/tmp/test",
    )


def test_action_type(action: CfOpAction) -> None:
    assert action.action_type == "cf-op"


def test_protocol_compliance(action: CfOpAction) -> None:
    assert isinstance(action, Action)


# --- validate() ---


def test_validate_missing_operation(action: CfOpAction) -> None:
    errors = action.validate({})
    assert len(errors) == 1
    assert errors[0].field == "operation"
    assert "required" in errors[0].message


def test_validate_invalid_operation(action: CfOpAction) -> None:
    errors = action.validate({"operation": "nonexistent"})
    assert len(errors) == 1
    assert errors[0].field == "operation"
    assert "not a valid" in errors[0].message


def test_validate_set_phase_without_phase(action: CfOpAction) -> None:
    errors = action.validate({"operation": CfOperation.SET_PHASE})
    assert len(errors) == 1
    assert errors[0].field == "phase"


def test_validate_valid_set_phase(action: CfOpAction) -> None:
    errors = action.validate(
        {
            "operation": CfOperation.SET_PHASE,
            "phase": 4,
        }
    )
    assert errors == []


def test_validate_valid_build_context(action: CfOpAction) -> None:
    errors = action.validate({"operation": CfOperation.BUILD_CONTEXT})
    assert errors == []


def test_validate_valid_summarize(action: CfOpAction) -> None:
    errors = action.validate({"operation": CfOperation.SUMMARIZE})
    assert errors == []


# --- execute() ---


@pytest.mark.asyncio
async def test_execute_set_phase(
    action: CfOpAction, mock_context: ActionContext
) -> None:
    mock_context.params = {
        "operation": CfOperation.SET_PHASE,
        "phase": "4",
    }
    mock_context.cf_client._run = MagicMock(return_value="Phase set to 4")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    mock_context.cf_client._run.assert_called_once_with(["set", "phase", "4"])  # type: ignore[union-attr]
    assert result.success is True
    assert result.outputs["stdout"] == "Phase set to 4"
    assert result.outputs["operation"] == "set_phase"


@pytest.mark.asyncio
async def test_execute_build_context(
    action: CfOpAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
    mock_context.cf_client._run_json = MagicMock(  # type: ignore[union-attr]
        return_value={"context": "Context built"},
    )

    result = await action.execute(mock_context)

    mock_context.cf_client._run_json.assert_called_once_with(["build", "--json"])  # type: ignore[union-attr]
    assert result.success is True
    assert result.outputs["stdout"] == "Context built"
    assert result.outputs["operation"] == "build_context"


@pytest.mark.asyncio
async def test_execute_summarize(
    action: CfOpAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"operation": CfOperation.SUMMARIZE}
    mock_context.cf_client._run = MagicMock(return_value="Summary done")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    mock_context.cf_client._run.assert_called_once_with(["summarize"])  # type: ignore[union-attr]
    assert result.success is True
    assert result.outputs["stdout"] == "Summary done"


@pytest.mark.asyncio
async def test_execute_success_outputs(
    action: CfOpAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]

    result = await action.execute(mock_context)

    assert isinstance(result, ActionResult)
    assert result.success is True
    assert "stdout" in result.outputs
    assert result.action_type == "cf-op"


@pytest.mark.asyncio
async def test_execute_cf_error(
    action: CfOpAction, mock_context: ActionContext
) -> None:
    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
    mock_context.cf_client._run_json = MagicMock(  # type: ignore[union-attr]
        side_effect=ContextForgeError("cf build failed")
    )

    result = await action.execute(mock_context)

    assert result.success is False
    assert result.error == "cf build failed"
    assert result.action_type == "cf-op"
