"""Tests for squadron.pipeline.summary_oneshot."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.core.models import SDK_RESULT_TYPE, Message
from squadron.pipeline.summary_oneshot import (
    capture_summary_via_profile,
    is_sdk_profile,
)
from squadron.providers.base import AgentProvider, ProviderCapabilities

# ---------------------------------------------------------------------------
# T3 — is_sdk_profile predicate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "profile,expected",
    [
        (None, True),
        ("sdk", True),
        ("openrouter", False),
        ("openai", False),
        ("gemini", False),
        ("local", False),
        ("openai-oauth", False),
        ("unknown-future", False),
    ],
)
def test_is_sdk_profile(profile: str | None, expected: bool) -> None:
    assert is_sdk_profile(profile) is expected


# ---------------------------------------------------------------------------
# T5 — capture_summary_via_profile with stub provider
# ---------------------------------------------------------------------------

_FAKE_PROFILE = "fake-oneshot"
_FAKE_PROVIDER_TYPE = "fake-oneshot-provider"


def _make_fake_message(content: str, sdk_type: str | None = None) -> Message:
    msg = MagicMock(spec=Message)
    msg.content = content
    msg.metadata = {"sdk_type": sdk_type} if sdk_type else {}
    return msg


def _make_fake_agent(
    messages: list[Message], *, raises: Exception | None = None
) -> MagicMock:
    """Return a fake Agent that yields *messages* from handle_message()."""

    async def _handle(message: Message) -> AsyncIterator[Message]:
        if raises is not None:
            raise raises
        for m in messages:
            yield m

    agent = MagicMock()
    agent.handle_message = _handle
    agent.shutdown = AsyncMock()
    return agent


def _make_fake_provider(agent: MagicMock) -> AgentProvider:
    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = _FAKE_PROVIDER_TYPE
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(return_value=agent)
    return provider


@pytest.fixture()
def fake_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register a fake profile and provider for the duration of the test."""
    from squadron.providers import profiles as profiles_mod
    from squadron.providers import registry as registry_mod
    from squadron.providers.profiles import ProviderProfile

    fake_profile = ProviderProfile(
        name=_FAKE_PROFILE,
        provider=_FAKE_PROVIDER_TYPE,
        api_key_env=None,
        description="Fake profile for unit tests",
    )

    original_get_all = profiles_mod.get_all_profiles
    monkeypatch.setattr(
        profiles_mod,
        "get_all_profiles",
        lambda: {**original_get_all(), _FAKE_PROFILE: fake_profile},
    )

    original_registry = dict(registry_mod._REGISTRY)

    def _restore() -> None:
        registry_mod._REGISTRY.clear()
        registry_mod._REGISTRY.update(original_registry)

    monkeypatch.setattr(
        registry_mod,
        "ensure_provider_loaded",
        lambda name: None,  # type: ignore[attr-defined]
        raising=False,
    )

    yield  # type: ignore[misc]
    _restore()


@pytest.mark.asyncio
async def test_capture_summary_happy_path(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("SUMMARY OUTPUT")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await capture_summary_via_profile(
        instructions="summarize this",
        model_id="model-x",
        profile=_FAKE_PROFILE,
    )

    assert result == "SUMMARY OUTPUT"
    agent.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_capture_summary_multi_chunk(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    msgs = [_make_fake_message("Part A"), _make_fake_message(" Part B")]
    agent = _make_fake_agent(msgs)
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await capture_summary_via_profile(
        instructions="summarize",
        model_id=None,
        profile=_FAKE_PROFILE,
    )

    assert result == "Part A Part B"
    agent.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_capture_summary_filters_sdk_result_type(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    msgs = [
        _make_fake_message("REAL CONTENT"),
        _make_fake_message("REAL CONTENT", sdk_type=SDK_RESULT_TYPE),
    ]
    agent = _make_fake_agent(msgs)
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await capture_summary_via_profile(
        instructions="summarize",
        model_id=None,
        profile=_FAKE_PROFILE,
    )

    # Duplicate ResultMessage must be filtered — content appears only once
    assert result == "REAL CONTENT"
    agent.shutdown.assert_called_once()


@pytest.mark.asyncio
async def test_capture_summary_shutdown_called_on_exception(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([], raises=RuntimeError("provider exploded"))
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    with pytest.raises(RuntimeError, match="provider exploded"):
        await capture_summary_via_profile(
            instructions="summarize",
            model_id=None,
            profile=_FAKE_PROFILE,
        )

    agent.shutdown.assert_called_once()
