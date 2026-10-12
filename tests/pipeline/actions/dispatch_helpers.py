"""Shared builders for dispatch action tests (agent, registry, context, profiles)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

from squadron.core.models import Message
from squadron.pipeline.models import ActionContext
from squadron.pipeline.resolver import ResolvedModel
from squadron.providers.base import ProfileName
from squadron.providers.profiles import ProviderProfile

DISPATCH_MODULE = "squadron.pipeline.actions.dispatch"


def make_context(**overrides: object) -> ActionContext:
    """Build an ActionContext with sensible defaults."""
    resolver = MagicMock()
    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
    resolver.resolve_full.return_value = ResolvedModel("claude-sonnet-4-20250514", None)
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


def sdk_profile() -> ProviderProfile:
    return ProviderProfile(
        name=ProfileName.SDK,
        provider="sdk",
        api_key_env=None,
        description="test",
    )


def openrouter_profile() -> ProviderProfile:
    return ProviderProfile(
        name="openrouter",
        provider="openai",
        base_url="https://openrouter.ai/api/v1",
        api_key_env="OPENROUTER_API_KEY",
        description="test",
    )


def make_agent_mock(
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


def make_registry(agent: AsyncMock) -> MagicMock:
    """Build a mock registry that spawns the given agent."""
    mock_registry = MagicMock()
    mock_registry.spawn = AsyncMock(return_value=agent)
    mock_registry.shutdown_agent = AsyncMock()
    return mock_registry
