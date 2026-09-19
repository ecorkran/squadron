"""Tests for the one-shot composer's wiring (D3)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock

import pytest

from squadron.core.models import SDK_RESULT_TYPE, Message
from squadron.pr.composer import CompositionError, compose_one_shot
from squadron.providers.base import AgentProvider, ProfileName, ProviderCapabilities

_FAKE_PROFILE = "fake-pr-body"
_FAKE_PROVIDER_TYPE = "fake-pr-body-provider"


def _make_fake_message(content: str, sdk_type: str | None = None) -> Message:
    msg = MagicMock(spec=Message)
    msg.content = content
    msg.metadata = {"sdk_type": sdk_type} if sdk_type else {}
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
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, provider)

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
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, provider)

    await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    config = provider.create_agent.await_args.args[0]
    assert config.model is None


@pytest.mark.asyncio
async def test_no_tools_are_requested(monkeypatch: pytest.MonkeyPatch, fake_provider_env: None) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([_make_fake_message("the body")])
    provider = _make_fake_provider(agent)
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, provider)

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
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, provider)

    result = await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    assert result == "Part A\nPart B"


@pytest.mark.asyncio
async def test_sdk_duplicate_result_and_tool_messages_are_skipped(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    """The SDK's stream shape: prose, tool narration, then a duplicate result.

    A title composed over this stream must stay one line — the unfiltered
    duplicate made it ``"title\\ntitle"``, which D4a's multi-line rule rejects.
    """
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent(
        [
            _make_fake_message("the title", sdk_type="assistant_text"),
            _make_fake_message("Using tool: Bash", sdk_type="tool_use"),
            _make_fake_message("<bash stdout>", sdk_type="tool_result"),
            _make_fake_message("the title", sdk_type=SDK_RESULT_TYPE),
        ]
    )
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, _make_fake_provider(agent))

    result = await compose_one_shot("write a title", model=None, profile=_FAKE_PROFILE)

    assert result == "the title"


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
    provider.provider_type = ProfileName.SDK
    provider.capabilities = ProviderCapabilities()
    provider.create_agent = AsyncMock(return_value=agent)

    from squadron.providers import loader as loader_mod

    monkeypatch.setattr(loader_mod, "ensure_provider_loaded", lambda name: None)
    monkeypatch.setitem(registry_mod._REGISTRY, ProfileName.SDK, provider)

    result = await compose_one_shot("write a PR body", model=None, profile=ProfileName.SDK)

    assert result == "the body"
    provider.create_agent.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_raising_exits_via_composition_error(
    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
) -> None:
    from squadron.providers import registry as registry_mod

    agent = _make_fake_agent([], raises=RuntimeError("provider exploded"))
    provider = _make_fake_provider(agent)
    monkeypatch.setitem(registry_mod._REGISTRY, _FAKE_PROVIDER_TYPE, provider)

    with pytest.raises(CompositionError):
        await compose_one_shot("write a PR body", model=None, profile=_FAKE_PROFILE)

    agent.shutdown.assert_called_once()
