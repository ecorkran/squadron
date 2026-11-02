"""The no-tools guard for dispatch steps declaring ``allowed_tools: []`` (slice 949 D6)."""

from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.actions.tool_support import (
    DispatchRoute,
    declares_no_tools,
    tool_isolation_error,
)
from squadron.pipeline.failure_kind import FAILURE_KIND_KEY, FailureKind, pauses_run
from squadron.pipeline.models import ActionContext, StepConfig
from squadron.pipeline.resolver import ResolvedModel
from squadron.pipeline.steps.review import ReviewStepType
from squadron.providers.base import ProfileName, ProviderCapabilities
from tests.pipeline.actions.dispatch_helpers import DISPATCH_MODULE as _P
from tests.pipeline.actions.dispatch_helpers import make_agent_mock, make_context, make_registry
from tests.pipeline.actions.dispatch_helpers import openrouter_profile as _openrouter_profile
from tests.pipeline.actions.dispatch_helpers import sdk_profile as _sdk_profile

_MODEL_ID = "claude-sonnet-4-20250514"


def _provider_stub(*, can_read_files: bool) -> SimpleNamespace:
    """A provider whose capabilities are the only thing the guard may look at."""
    return SimpleNamespace(capabilities=ProviderCapabilities(can_read_files=can_read_files))


def _context(profile: str | None, *, session: object = None, **params: object) -> ActionContext:
    resolver = MagicMock()
    resolver.resolve.return_value = (_MODEL_ID, profile)
    resolver.resolve_full.return_value = ResolvedModel(_MODEL_ID, profile)
    all_params: dict[str, object] = {"prompt": "test", **params}
    return make_context(params=all_params, resolver=resolver, sdk_session=session)


# --- declares_no_tools ---


@pytest.mark.parametrize(
    ("params", "expected"),
    [
        ({"allowed_tools": []}, True),
        ({"allowed_tools": ["read_file"]}, False),
        ({}, False),
        ({"allowed_tools": None}, False),
    ],
)
def test_declares_no_tools(params: dict[str, object], expected: bool) -> None:
    assert declares_no_tools(make_context(params={"prompt": "x", **params})) is expected


# --- tool_isolation_error ---


def _error(route: DispatchRoute, *, can_read_files: bool) -> str | None:
    return tool_isolation_error(
        step_name="extract",
        model="some-model",
        provider="some-provider",
        route=route,
        can_read_files=can_read_files,
    )


@pytest.mark.parametrize("can_read_files", [True, False])
def test_session_route_always_errors(can_read_files: bool) -> None:
    assert _error(DispatchRoute.SESSION, can_read_files=can_read_files) is not None


def test_agent_route_errors_when_the_provider_reads_files() -> None:
    assert _error(DispatchRoute.AGENT, can_read_files=True) is not None


def test_agent_route_is_clear_when_the_provider_reads_no_files() -> None:
    assert _error(DispatchRoute.AGENT, can_read_files=False) is None


def test_error_names_step_model_and_provider() -> None:
    message = _error(DispatchRoute.AGENT, can_read_files=True)
    assert message is not None
    assert "extract" in message
    assert "some-model" in message
    assert "some-provider" in message
    assert "openrouter" in message


def test_tool_isolation_does_not_pause_the_run() -> None:
    assert not pauses_run({FAILURE_KIND_KEY: FailureKind.TOOL_ISOLATION.value})


# --- the guard inside DispatchAction ---


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


@pytest.mark.asyncio
async def test_session_route_fails_before_any_model_call(
    action: DispatchAction, caplog: pytest.LogCaptureFixture
) -> None:
    session = AsyncMock()
    ctx = _context(ProfileName.SDK, session=session, allowed_tools=[])
    with (
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_P}.get_provider", return_value=_provider_stub(can_read_files=True)),
        caplog.at_level(logging.WARNING, logger=_P),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == "tool_isolation"
    session.set_model.assert_not_called()
    session.dispatch.assert_not_called()
    assert any("allowed_tools" in r.message and r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_file_reading_one_shot_route_fails_before_any_model_call(
    action: DispatchAction, caplog: pytest.LogCaptureFixture
) -> None:
    """The SDK one-shot and Codex routes both land here: the provider reads files."""
    ctx = _context(None, allowed_tools=[])  # no alias profile: the SDK one-shot default
    registry = make_registry(make_agent_mock("never used"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_P}.get_provider", return_value=_provider_stub(can_read_files=True)),
        caplog.at_level(logging.WARNING, logger=_P),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.TOOL_ISOLATION.value
    registry.spawn.assert_not_called()
    assert "generate" in (result.error or "")  # the step name make_context gives
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_provider_without_file_access_runs_with_no_tools_offered(action: DispatchAction) -> None:
    ctx = _context("openrouter", allowed_tools=[])
    registry = make_registry(make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_openrouter_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=SimpleNamespace(
                capabilities=ProviderCapabilities(can_read_files=False, runs_squadron_tools=True)
            ),
        ),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    config = registry.spawn.call_args[0][0]
    assert not config.allowed_tools


@pytest.mark.asyncio
async def test_absent_allowed_tools_is_not_guarded(action: DispatchAction) -> None:
    ctx = _context(None)
    registry = make_registry(make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True


def test_review_step_with_empty_allowed_tools_is_unchanged() -> None:
    """Excluded in the design: only dispatch steps are guarded."""
    step = StepConfig(step_type="review", name="r", config={"template": "code", "allowed_tools": []})
    assert ReviewStepType().validate(step) == []
