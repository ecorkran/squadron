"""Shared provider loading.

Lazily import provider modules to trigger auto-registration.
"""

from __future__ import annotations

import importlib

# Provider type -> module name mapping.
_PROVIDER_MODULES: dict[str, str] = {
    "openai": "openai",
    "sdk": "sdk",
    "openai-oauth": "codex",
}


def ensure_provider_loaded(provider_type: str) -> None:
    """Import the provider module to trigger auto-registration if needed."""
    module_name = _PROVIDER_MODULES.get(provider_type, provider_type)
    try:
        importlib.import_module(f"squadron.providers.{module_name}")
    except ImportError:
        pass  # Let get_provider raise KeyError with available providers


def missing_extra_hint(provider_type: str) -> str | None:
    """The provider's install hint if it needs a missing extra, else ``None`` (slice 129 D9).

    Raises:
        KeyError: no provider is registered under ``provider_type``.
    """
    from squadron.providers.base import ExtraRequirement
    from squadron.providers.registry import get_provider

    ensure_provider_loaded(provider_type)
    provider = get_provider(provider_type)
    if isinstance(provider, ExtraRequirement):
        return provider.missing_extra_hint()
    return None
