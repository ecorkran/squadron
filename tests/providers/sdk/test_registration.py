"""Integration tests for SDK provider auto-registration flow."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from squadron.providers import registry as reg_module
from squadron.providers.registry import get_provider, list_providers


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Save and restore registry state so tests are isolated."""
    original = dict(reg_module._REGISTRY)  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    yield
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.update(original)  # pyright: ignore[reportPrivateUsage]


def _import_sdk_package() -> None:
    """Force the SDK package import and its auto-registration side effect."""
    import squadron.providers.sdk  # noqa: F401
    from squadron.providers.registry import register_provider

    # Re-register since the fixture clears the registry before each test.
    from squadron.providers.sdk.provider import ClaudeSDKProvider

    register_provider("sdk", ClaudeSDKProvider())


class TestAutoRegistration:
    def test_sdk_in_list_providers(self) -> None:
        _import_sdk_package()
        assert "sdk" in list_providers()

    def test_get_provider_returns_sdk_provider(self) -> None:
        _import_sdk_package()
        provider = get_provider("sdk")
        from squadron.providers.sdk.provider import ClaudeSDKProvider

        assert isinstance(provider, ClaudeSDKProvider)

    def test_provider_type_is_sdk(self) -> None:
        _import_sdk_package()
        assert get_provider("sdk").provider_type == "sdk"

    @pytest.mark.asyncio
    async def test_full_flow_create_agent(self) -> None:
        _import_sdk_package()
        from squadron.core.models import AgentConfig
        from squadron.providers.sdk.agent import ClaudeSDKAgent

        provider = get_provider("sdk")
        config = AgentConfig(name="integration-test", agent_type="sdk", provider="sdk")
        agent = await provider.create_agent(config)
        assert isinstance(agent, ClaudeSDKAgent)
        assert agent.name == "integration-test"
        assert agent.agent_type == "sdk"
