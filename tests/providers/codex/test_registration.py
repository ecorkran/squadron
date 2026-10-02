"""Integration tests for Codex (openai-oauth) provider auto-registration."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

from squadron.providers import registry as reg_module
from squadron.providers.base import ProviderType
from squadron.providers.registry import get_provider, list_providers


@pytest.fixture(autouse=True)
def _clean_registry() -> Generator[None]:  # pyright: ignore[reportUnusedFunction]
    """Save and restore registry state so tests are isolated."""
    original = dict(reg_module._REGISTRY)  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    yield
    reg_module._REGISTRY.clear()  # pyright: ignore[reportPrivateUsage]
    reg_module._REGISTRY.update(original)  # pyright: ignore[reportPrivateUsage]


def _import_codex_package() -> None:
    """Force the Codex package import and its auto-registration side effect."""
    import importlib

    import squadron.providers.codex  # noqa: F401

    importlib.reload(squadron.providers.codex)


class TestAutoRegistration:
    def test_openai_oauth_in_list_after_import(self) -> None:
        _import_codex_package()
        assert ProviderType.OPENAI_OAUTH in list_providers()

    def test_get_provider_returns_codex_provider(self) -> None:
        _import_codex_package()
        from squadron.providers.codex.provider import CodexProvider

        assert isinstance(get_provider(ProviderType.OPENAI_OAUTH), CodexProvider)

    def test_provider_type_is_openai_oauth(self) -> None:
        _import_codex_package()
        provider = get_provider(ProviderType.OPENAI_OAUTH)
        assert provider.provider_type == ProviderType.OPENAI_OAUTH

    def test_registers_without_the_sdk_and_raises_install_hint(self) -> None:
        """With the extra absent the provider still registers; using it gives the hint."""
        import asyncio
        from unittest.mock import patch

        from squadron.core.models import AgentConfig
        from squadron.providers.codex.runtime import CODEX_INSTALL_COMMAND
        from squadron.providers.errors import ProviderError

        auth_file = Path.home() / ".codex" / "auth.json"
        auth_file.parent.mkdir(parents=True, exist_ok=True)
        auth_file.write_text("{}")
        with patch("squadron.providers.codex.runtime._module_available", return_value=False):
            _import_codex_package()
            provider = get_provider(ProviderType.OPENAI_OAUTH)
            config = AgentConfig(
                name="c", agent_type="openai-oauth", provider="openai-oauth", model="m"
            )
            with pytest.raises(ProviderError) as exc_info:
                asyncio.run(provider.create_agent(config))
        assert CODEX_INSTALL_COMMAND in str(exc_info.value)
