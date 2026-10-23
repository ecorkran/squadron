"""The default adapter registry: Python and TypeScript.

The only non-test module that imports concrete adapters. The CLI and 404 pass this
to ``take_snapshot``; tests pass their own.
"""

from __future__ import annotations

from squadron.metrology.snapshot.contract import AdapterRegistry, LanguageAdapter
from squadron.metrology.snapshot.python_adapter import PythonAdapter
from squadron.metrology.snapshot.typescript_adapter import TypeScriptAdapter


def default_registry() -> AdapterRegistry:
    """Language to adapter for every language squadron can measure."""
    adapters: tuple[LanguageAdapter, ...] = (PythonAdapter(), TypeScriptAdapter())
    return {adapter.language: adapter for adapter in adapters}
