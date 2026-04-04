"""Tests for DispatchAction."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from squadron.core.models import Message
from squadron.pipeline.actions.dispatch import DispatchAction
from squadron.pipeline.actions.protocol import Action
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ModelResolutionError
from squadron.providers.base import ProfileName
from squadron.providers.profiles import ProviderProfile

_P = "squadron.pipeline.actions.dispatch"


@pytest.fixture
def action() -> DispatchAction:
    return DispatchAction()


def _make_context(**overrides: object) -> ActionContext:
    """Build an ActionContext with sensible defaults."""
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    defaults: dict[str, object] = {
        "pipeline_name": "test-pipeline",
        "run_id": "run-12345678",
        "params": {"prompt": "Hello world"},
        "step_name": "generate",
        "step_index": 0,
        "prior_outputs": {},
        "resolver": resolver,
        "cf_client": MagicMock(),
        "cwd": "/tmp/test",
    }
    defaults.update(overrides)
    return ActionContext(**defaults)  # type: ignore[arg-type]


def _sdk_profile() -> ProviderProfile:
    return ProviderProfile(
        name=ProfileName.SDK,
        provider="sdk",
        api_key_env=None,
        description="test",
    )


def _openrouter_profile() -> ProviderProfile:
    return ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        description="test",
    )


def _make_agent_mock(
    *contents: str,
    metadata: dict[str, object] | None = None,
) -> AsyncMock:
    """Build a mock agent whose handle_message yields given contents."""

    async def _handle(_msg: object) -> AsyncIterator[Message]:
        for content in contents:
            msg = MagicMock(spec=Message)
            msg.content = content
            msg.metadata = metadata or {}
            yield msg

    mock_agent = AsyncMock()
    mock_agent.handle_message = _handle
    return mock_agent


def _make_registry(agent: AsyncMock) -> MagicMock:
    """Build a mock registry that spawns the given agent."""
    mock_registry = MagicMock()
    mock_registry.spawn = AsyncMock(return_value=agent)
    mock_registry.shutdown_agent = AsyncMock()
    return mock_registry


# --- Protocol ---


def test_action_type(action: DispatchAction) -> None:
    assert action.action_type == "dispatch"


def test_protocol_compliance(action: DispatchAction) -> None:
    assert isinstance(action, Action)


# --- validate() ---


def test_validate_always_passes(action: DispatchAction) -> None:
    """Dispatch validates at runtime — prompt resolved from prior outputs."""
    assert action.validate({}) == []
    assert action.validate({"prompt": "hello"}) == []


# --- execute() ---


@pytest.mark.asyncio
async def test_execute_happy_path(action: DispatchAction) -> None:
    """Prompt dispatched, response captured in outputs."""
    ctx = _make_context()
    mock_agent = _make_agent_mock("Hello ", "world")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is True
    assert result.outputs["response"] == "Hello world"
    assert result.metadata["model"] == "claude-sonnet-4-20250514"
    assert result.metadata["profile"] == ProfileName.SDK


@pytest.mark.asyncio
async def test_execute_model_resolution(action: DispatchAction) -> None:
    """Resolver called with action_model and step_model from params."""
    ctx = _make_context(
        params={"prompt": "test", "model": "opus", "step_model": "sonnet"},
    )
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    ctx.resolver.resolve.assert_called_once_with("opus", "sonnet")


@pytest.mark.asyncio
async def test_execute_profile_from_alias(action: DispatchAction) -> None:
    """When resolver returns alias profile, that profile is used."""
    ctx = _make_context()
    ctx.resolver.resolve.return_value = ("model-x", "openrouter")
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(
            f"{_P}.get_profile", return_value=_openrouter_profile()
        ) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with("openrouter")
    assert result.metadata["profile"] == "openrouter"


@pytest.mark.asyncio
async def test_execute_profile_override(action: DispatchAction) -> None:
    """Explicit profile in params takes precedence over alias profile."""
    ctx = _make_context(params={"prompt": "test", "profile": "openai"})
    ctx.resolver.resolve.return_value = ("model-x", "openrouter")
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with("openai")
    assert result.metadata["profile"] == "openai"


@pytest.mark.asyncio
async def test_execute_default_profile(action: DispatchAction) -> None:
    """When no alias profile and no explicit profile, defaults to SDK."""
    ctx = _make_context()
    ctx.resolver.resolve.return_value = ("model-x", None)
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()) as mock_get_profile,
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    mock_get_profile.assert_called_once_with(ProfileName.SDK)
    assert result.metadata["profile"] == ProfileName.SDK


@pytest.mark.asyncio
async def test_execute_system_prompt(action: DispatchAction) -> None:
    """System prompt passed as instructions in AgentConfig."""
    ctx = _make_context(
        params={"prompt": "test", "system_prompt": "You are helpful."},
    )
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        await action.execute(ctx)

    spawn_config = mock_registry.spawn.call_args[0][0]
    assert spawn_config.instructions == "You are helpful."


@pytest.mark.asyncio
async def test_execute_sdk_dedup(action: DispatchAction) -> None:
    """Messages with sdk_type='result' are filtered out."""
    ctx = _make_context()

    async def _responses(_msg: object) -> AsyncIterator[Message]:
        normal = MagicMock(spec=Message)
        normal.content = "real response"
        normal.metadata = {}
        yield normal

        dupe = MagicMock(spec=Message)
        dupe.content = "real response"
        dupe.metadata = {"sdk_type": "result"}
        yield dupe

    mock_agent = AsyncMock()
    mock_agent.handle_message = _responses
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.outputs["response"] == "real response"


@pytest.mark.asyncio
async def test_execute_token_metadata(action: DispatchAction) -> None:
    """Token counts extracted from response metadata."""
    ctx = _make_context()
    token_meta = {
        "prompt_tokens": 10,
        "completion_tokens": 20,
        "total_tokens": 30,
    }
    mock_agent = _make_agent_mock("ok", metadata=token_meta)
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.metadata["prompt_tokens"] == 10
    assert result.metadata["completion_tokens"] == 20
    assert result.metadata["total_tokens"] == 30


@pytest.mark.asyncio
async def test_execute_token_metadata_absent(action: DispatchAction) -> None:
    """When no token metadata, result still has model and profile."""
    ctx = _make_context()
    mock_agent = _make_agent_mock("ok")
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert "model" in result.metadata
    assert "profile" in result.metadata
    assert "prompt_tokens" not in result.metadata


@pytest.mark.asyncio
async def test_execute_agent_shutdown_always_called(
    action: DispatchAction,
) -> None:
    """Agent shutdown called even on error during handle_message."""
    ctx = _make_context()

    async def _explode(_msg: object) -> AsyncIterator[Message]:
        raise RuntimeError("boom")
        yield  # type: ignore[misc]  # make it an async generator

    mock_agent = AsyncMock()
    mock_agent.handle_message = _explode
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "boom" in (result.error or "")
    mock_registry.shutdown_agent.assert_called_once()


@pytest.mark.asyncio
async def test_execute_model_resolution_error(
    action: DispatchAction,
) -> None:
    """ModelResolutionError returns success=False."""
    ctx = _make_context()
    ctx.resolver.resolve.side_effect = ModelResolutionError("no model")

    with (
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "no model" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_profile_not_found(action: DispatchAction) -> None:
    """KeyError from get_profile returns success=False."""
    ctx = _make_context()

    with patch(
        f"{_P}.get_profile",
        side_effect=KeyError("Profile 'bad' not found"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    assert "bad" in (result.error or "")


@pytest.mark.asyncio
async def test_execute_handle_message_error_still_shuts_down(
    action: DispatchAction,
) -> None:
    """Agent handle_message exception: success=False, agent still shut down."""
    ctx = _make_context()

    async def _fail(_msg: object) -> AsyncIterator[Message]:
        raise ConnectionError("API unavailable")
        yield  # type: ignore[misc]

    mock_agent = AsyncMock()
    mock_agent.handle_message = _fail
    mock_registry = _make_registry(mock_agent)

    with (
        patch(f"{_P}.get_registry", return_value=mock_registry),
        patch(f"{_P}.get_profile", return_value=_sdk_profile()),
        patch(f"{_P}.ensure_provider_loaded"),
    ):
        result = await action.execute(ctx)

    assert result.success is False
    mock_registry.shutdown_agent.assert_called_once()
