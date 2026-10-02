"""Integration tests for Codex (openai-oauth) provider auto-registration."""

from __future__ import annotations

from collections.abc import Generator

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
