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
