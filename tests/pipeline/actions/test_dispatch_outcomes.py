"""Dispatch wiring of the D3 tool-outcome rules and the write-required contract (slice 945)."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from squadron.core.models import AgentConfig
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.models import ActionResult
from squadron.pipeline.steps import StepTypeName
from squadron.pipeline.steps.phase import RULES_STEP_PARAM
from squadron.providers.base import (
    FAILED_TOOL_CALLS_KEY,
    FIRST_TOOL_ERROR_KEY,
    TOOL_CALLS_MADE_KEY,
    TOOLS_GIVEN_KEY,
    ProviderType,
)
from squadron.tools.builtin import DEFAULT_WRITE_STEP_TOOLS
from tests.pipeline.actions.dispatch_helpers import DISPATCH_MODULE as _P
from tests.pipeline.actions.dispatch_helpers import make_agent_mock as _make_agent_mock
from tests.pipeline.actions.dispatch_helpers import make_context as _make_context
from tests.pipeline.actions.dispatch_helpers import make_registry as _make_registry
from tests.pipeline.actions.dispatch_helpers import openrouter_profile as _openrouter_profile
from tests.providers import agent_config_sites

_STEP = "implement-step"
_WRITE_PARAMS: dict[str, object] = {
    "allowed_tools": ["write_file"],
    RULES_STEP_PARAM: StepTypeName.IMPLEMENT,
}


async def _run(params: dict[str, object], metadata: dict[str, object]) -> ActionResult:
    mock_registry = _make_registry(_make_agent_mock("done", metadata=metadata))
    ctx = _make_context(params={"prompt": "p", **params}, step_name=_STEP)
    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_P}.project_rules_for_dispatch", return_value=("", None)),
    ):
        return await DispatchAction().execute(ctx)


def _telemetry(
    made: int, failed: int, first_error: str | None = None, given: list[str] | None = None
) -> dict[str, object]:
    metadata: dict[str, object] = {
        TOOLS_GIVEN_KEY: given or ["write_file"],
        TOOL_CALLS_MADE_KEY: made,
        FAILED_TOOL_CALLS_KEY: failed,
    }
    if first_error is not None:
        metadata[FIRST_TOOL_ERROR_KEY] = first_error
    return metadata


async def test_write_required_step_with_no_tool_calls_fails(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = await _run(_WRITE_PARAMS, _telemetry(made=0, failed=0))

    assert result.success is False
    assert result.error == "step must write files but made no tool calls"
    assert any(_STEP in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)


async def test_all_calls_failed_fails_with_counts_and_first_error_in_metadata() -> None:
    result = await _run(_WRITE_PARAMS, _telemetry(made=2, failed=2, first_error="outside the jail"))

    assert result.success is False
    assert result.error is not None and "outside the jail" in result.error
    assert result.metadata[FAILED_TOOL_CALLS_KEY] == 2
    assert result.metadata[FIRST_TOOL_ERROR_KEY] == "outside the jail"


async def test_partial_failure_succeeds_with_a_warning(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING):
        result = await _run(_WRITE_PARAMS, _telemetry(made=3, failed=1, first_error="one bad call"))

    assert result.success is True
    assert result.metadata[TOOL_CALLS_MADE_KEY] == 3
    assert result.metadata[FAILED_TOOL_CALLS_KEY] == 1
    assert any("1 of 3 tool calls failed" in r.getMessage() for r in caplog.records)


async def test_sdk_shaped_telemetry_without_first_error_fails_without_detail() -> None:
    """The SDK stamps a failed count but no error text."""
    result = await _run(
        {"allowed_tools": ["write_file"]}, _telemetry(made=1, failed=1, given=["write_file"])
    )

    assert result.success is False
    assert result.error == "every tool call failed"
    assert FIRST_TOOL_ERROR_KEY not in result.metadata


async def test_bare_dispatch_without_tools_is_not_failed() -> None:
    result = await _run({}, {})

    assert result.success is True


# --- requires_writes reaches the provider (D1) ---


async def test_phase_step_param_sets_requires_writes(tmp_path: Path) -> None:
    config = await agent_config_sites.dispatch_action(tmp_path, {RULES_STEP_PARAM: StepTypeName.DESIGN})

    assert config.requires_writes is True


async def test_feedback_param_sets_requires_writes(tmp_path: Path) -> None:
    review = ActionResult(success=True, action_type="review", outputs={}, verdict="CONCERNS")
    config = await agent_config_sites.dispatch_action(
        tmp_path, {"feedback": "review"}, prior_outputs={"0-review-0": review}
    )

    assert config.requires_writes is True


async def test_bare_dispatch_does_not_set_requires_writes(tmp_path: Path) -> None:
    config = await agent_config_sites.dispatch_action(tmp_path, {})

    assert config.requires_writes is False


# --- default tools for a write step that declared none ---

_PHASE_STEP: dict[str, object] = {RULES_STEP_PARAM: StepTypeName.DESIGN}


async def _spawned_config(params: dict[str, object], provider: ProviderType) -> AgentConfig:
    """The AgentConfig the dispatch hands the registry, for a profile of *provider*."""
    mock_registry = _make_registry(_make_agent_mock("done"))
    profile = replace(_openrouter_profile(), provider=provider)
    ctx = _make_context(params={"prompt": "p", **params}, step_name=_STEP)
    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=profile),
        patch(f"{_P}.profile_credentials", return_value={}),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_P}.project_rules_for_dispatch", return_value=("", None)),
    ):
        await DispatchAction().execute(ctx)
    return mock_registry.spawn.call_args.args[0]


async def test_openai_write_step_without_tools_gets_the_default_set() -> None:
    config = await _spawned_config(_PHASE_STEP, ProviderType.OPENAI)

    assert config.allowed_tools == list(DEFAULT_WRITE_STEP_TOOLS)


async def test_declared_tools_are_not_replaced_by_the_default() -> None:
    config = await _spawned_config(
        {**_PHASE_STEP, "allowed_tools": ["write_file"]}, ProviderType.OPENAI
    )

    assert config.allowed_tools == ["write_file"]


@pytest.mark.parametrize(
    ("params", "provider"),
    [
        ({}, ProviderType.OPENAI),
        (_PHASE_STEP, ProviderType.SDK),
        (_PHASE_STEP, ProviderType.OPENAI_OAUTH),
    ],
    ids=["bare-dispatch", "sdk", "codex"],
)
async def test_default_set_not_applied(params: dict[str, object], provider: ProviderType) -> None:
    config = await _spawned_config(params, provider)

    assert config.allowed_tools is None
