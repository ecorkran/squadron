"""Shared provider loading.

Lazily import provider modules to trigger auto-registration.
"""

from __future__ import annotations

import importlib

from squadron.providers.base import ProviderType

# Provider type -> module under ``squadron.providers``. Module names are
# implementation details; provider type strings are the public identifiers.
PROVIDER_MODULES: dict[str, str] = {
    ProviderType.OPENAI: "openai",
    ProviderType.SDK: "sdk",
    ProviderType.OPENAI_OAUTH: "codex",
}


def ensure_provider_loaded(provider_type: str) -> None:
    """Import the provider module to trigger auto-registration if needed.

    An unknown provider (no such module) is ignored so ``get_provider`` can
    raise its KeyError listing the available providers. Any other import
    failure, such as a provider's own dependency missing, propagates.
    """
    module = f"squadron.providers.{PROVIDER_MODULES.get(provider_type, provider_type)}"
    try:
        importlib.import_module(module)
    except ModuleNotFoundError as exc:
        if exc.name != module:
            raise
