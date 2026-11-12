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
_TS = "squadron.pipeline.actions.tool_support"


def _capabilities(*, can_read_files: bool, honors_empty_tools: bool = False) -> ProviderCapabilities:
    return ProviderCapabilities(can_read_files=can_read_files, honors_empty_tools=honors_empty_tools)


def _provider_stub(*, can_read_files: bool, honors_empty_tools: bool = False) -> SimpleNamespace:
    """A provider whose capabilities are the only thing the guard may look at."""
    return SimpleNamespace(
        capabilities=_capabilities(can_read_files=can_read_files, honors_empty_tools=honors_empty_tools)
    )


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


def _error(route: DispatchRoute, capabilities: ProviderCapabilities) -> str | None:
    return tool_isolation_error(
        step_name="extract",
        model="some-model",
        provider="some-provider",
        route=route,
        capabilities=capabilities,
    )


@pytest.mark.parametrize("honors_empty_tools", [True, False])
def test_session_route_always_errors(honors_empty_tools: bool) -> None:
    caps = _capabilities(can_read_files=True, honors_empty_tools=honors_empty_tools)
    message = _error(DispatchRoute.SESSION, caps)
    assert message is not None
    assert "persistent session" in message


def test_agent_route_errors_when_the_provider_brings_tools_it_cannot_drop() -> None:
    message = _error(DispatchRoute.AGENT, _capabilities(can_read_files=True))
    assert message is not None
    assert "cannot run with none" in message


def test_agent_route_is_clear_when_the_provider_honors_an_empty_tool_list() -> None:
    assert (
        _error(DispatchRoute.AGENT, _capabilities(can_read_files=True, honors_empty_tools=True)) is None
    )


def test_agent_route_is_clear_when_the_provider_reads_no_files() -> None:
    assert _error(DispatchRoute.AGENT, _capabilities(can_read_files=False)) is None


def test_error_names_step_model_and_provider() -> None:
    message = _error(DispatchRoute.AGENT, _capabilities(can_read_files=True))
    assert message is not None
    assert "extract" in message
    assert "some-model" in message
    assert "some-provider" in message


def test_tool_isolation_does_not_pause_the_run() -> None:
    assert not pauses_run({FAILURE_KIND_KEY: FailureKind.TOOL_ISOLATION.value})


# --- the guard inside DispatchAction ---


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


@pytest.mark.asyncio
async def test_no_tools_step_skips_the_persistent_session(action: DispatchAction) -> None:
    """The session carries earlier conversation and bypassPermissions; the step runs one-shot (#299)."""
    session = AsyncMock()
    ctx = _context(ProfileName.SDK, session=session, allowed_tools=[])
    registry = make_registry(make_agent_mock("from the prompt alone"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=_provider_stub(can_read_files=True, honors_empty_tools=True),
        ),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    session.set_model.assert_not_called()
    session.dispatch.assert_not_called()
    registry.spawn.assert_called_once()


@pytest.mark.asyncio
async def test_no_tools_sdk_step_without_a_session_runs_one_shot(action: DispatchAction) -> None:
    """An explicit sdk profile with no session used to fail the 'needs a session' guard."""
    ctx = _context(ProfileName.SDK, allowed_tools=[])
    registry = make_registry(make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=_provider_stub(can_read_files=True, honors_empty_tools=True),
        ),
    ):
        result = await action.execute(ctx)

    assert result.success is True


@pytest.mark.asyncio
async def test_no_tools_sdk_step_is_isolated_in_the_spawned_config(action: DispatchAction) -> None:
    ctx = _context(ProfileName.SDK, allowed_tools=[], system_prompt="be brief")
    registry = make_registry(make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=_provider_stub(can_read_files=True, honors_empty_tools=True),
        ),
    ):
        await action.execute(ctx)

    config = registry.spawn.call_args[0][0]
    assert config.allowed_tools == []
    assert config.setting_sources == []
    assert config.auto_memory is False
    assert config.use_default_system_prompt is False
    assert config.instructions == "be brief"


@pytest.mark.asyncio
async def test_tooled_sdk_step_keeps_the_preset_and_settings(action: DispatchAction) -> None:
    """The isolation applies only to allowed_tools == []."""
    ctx = _context(None, allowed_tools=["read_file"])
    registry = make_registry(make_agent_mock("ok"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    config = registry.spawn.call_args[0][0]
    assert config.use_default_system_prompt is True
    assert config.setting_sources


@pytest.mark.asyncio
async def test_provider_that_cannot_drop_its_tools_fails_before_any_model_call(
    action: DispatchAction, caplog: pytest.LogCaptureFixture
) -> None:
    """Codex-like: reads files itself and does not honor an empty tool list."""
    ctx = _context(None, allowed_tools=[])
    registry = make_registry(make_agent_mock("never used"))
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(f"{_TS}.get_provider", return_value=_provider_stub(can_read_files=True)),
        caplog.at_level(logging.WARNING, logger=_TS),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.TOOL_ISOLATION.value
    registry.spawn.assert_not_called()
    assert "generate" in (result.error or "")  # the step name make_context gives
    assert "cannot run with none" in (result.error or "")
    assert any(r.levelno == logging.WARNING for r in caplog.records)


@pytest.mark.asyncio
async def test_tool_use_in_a_no_tools_step_fails_the_step(
    action: DispatchAction, caplog: pytest.LogCaptureFixture
) -> None:
    """The reply is the check: the options withhold tools, this does not trust them (#299)."""
    ctx = _context(None, allowed_tools=[])
    leaked = make_agent_mock(
        "I read the file",
        metadata={"tools_given": [], "tool_calls_made": 2, "failed_tool_calls": 0},
    )
    registry = make_registry(leaked)
    with (
        patch(f"{_P}.get_registry", return_value=registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=_provider_stub(can_read_files=True, honors_empty_tools=True),
        ),
        caplog.at_level(logging.ERROR, logger=_P),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert result.metadata[FAILURE_KIND_KEY] == FailureKind.TOOL_ISOLATION.value
    assert "2 tool call" in (result.error or "")
    assert result.outputs == {}
    assert any(r.levelno == logging.ERROR for r in caplog.records)


@pytest.mark.asyncio
async def test_no_tools_step_that_used_none_succeeds(action: DispatchAction) -> None:
    ctx = _context(None, allowed_tools=[])
    clean = make_agent_mock(
        "answer", metadata={"tools_given": [], "tool_calls_made": 0, "failed_tool_calls": 0}
    )
    with (
        patch(f"{_P}.get_registry", return_value=make_registry(clean)),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
        patch(
            f"{_P}.get_provider",
            return_value=_provider_stub(can_read_files=True, honors_empty_tools=True),
        ),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["response"] == "answer"


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
    """Load-time validation stays dispatch-only; review and summary are guarded at run time (#306)."""
    step = StepConfig(step_type="review", name="r", config={"template": "code", "allowed_tools": []})
    assert ReviewStepType().validate(step) == []
