"""Tests for the one-shot composer's wiring (D3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.core.models import Message
from squadron.pr.body import CompositionError, compose_one_shot
from squadron.providers.base import AgentProvider, ProviderCapabilities

_FAKE_PROFILE = "fake-pr-body"
_FAKE_PROVIDER_TYPE = "fake-pr-body-provider"


def _make_fake_message(content: str) -> Message:
    msg = MagicMock(spec=Message)
    msg.content = content
    msg.metadata = {}
    return msg


def _make_fake_agent(messages: list[Message], *, raises: Exception | None = None) -> MagicMock:
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


@pytest.fixture
def fake_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register a fake profile and provider for the duration of the test."""
    from squadron.providers import loader as loader_mod
    from squadron.providers import profiles as profiles_mod
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
    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)


@pytest.mark.asyncio
async def test_composer_resolves_profile_through_the_registry(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await compose_one_shot("write a PR body", model="model-x", profile=_FAKE_PROFILE)

    assert result == "the body"
    provider.create_agent.assert_awaited_once()
    config = provider.create_agent.await_args.args[0]
    assert config.provider == _FAKE_PROVIDER_TYPE
    assert config.model == "model-x"


@pytest.mark.asyncio
async def test_model_none_is_passed_through_not_defaulted(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    config = provider.create_agent.await_args.args[0]
    assert config.model is None


@pytest.mark.asyncio
async def test_no_tools_are_requested(monkeypatch: pytest.MonkeyPatch, fake_provider_env: None) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    config = provider.create_agent.await_args.args[0]
    assert config.allowed_tools == []


@pytest.mark.asyncio
async def test_response_text_is_returned_unmodified(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("Part A"), _make_fake_message("Part B")])
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    result = await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    assert result == "Part A\nPart B"


@pytest.mark.asyncio
async def test_sdk_profile_resolves_and_dispatches_without_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The design's D3 claim, checked rather than asserted.

    ``ensure_provider_loaded`` is patched to a no-op: unpatched, it imports
    the real SDK provider module, which re-registers the genuine provider
    over the fake this test installs.
    """
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = MagicMock(spec=AgentProvider)
    provider.provider_type = "sdk"
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(return_value=agent)

    from squadron.providers import loader as loader_mod

    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)
    original = registry_mod._REGISTRY.get("sdk")
    registry_mod._REGISTRY["sdk"] = provider
    try:
        result = await compose_one_shot("write a PR body", model=None, profile="sdk")
    finally:
        if original is not None:
            registry_mod._REGISTRY["sdk"] = original
        else:
            registry_mod._REGISTRY.pop("sdk", None)

    assert result == "the body"
    provider.create_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_raising_exits_via_composition_error(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([], raises=RuntimeError("provider exploded"))
    provider = _make_fake_provider(agent)
    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider

    with pytest.raises(CompositionError):
        await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    agent.shutdown.assert_called_once()
