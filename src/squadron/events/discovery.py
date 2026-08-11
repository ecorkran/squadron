"""Plugin discovery — imports declared plugin modules (design D7).

Declared imports only, no scanning: a plugin module registers itself via
``register_event_action`` at module foot, the same idiom as every built-in
action module. ``cwd`` is prepended to ``sys.path`` for the import step so
an in-repo plugin (e.g. ``tools.squadron_rules``) resolves without packaging
ceremony, then removed — success or failure.
"""

from __future__ import annotations

import importlib
import logging
import sys

_logger = logging.getLogger(__name__)


class PluginLoadError(Exception):
    """Raised when a declared plugin module fails to import.

    Carries the module path and the manifest file it was declared in, so
    callers can attribute the failure without re-deriving it from the
    exception chain.
    """

    def __init__(self, module: str, manifest_source: str) -> None:
        super().__init__(f"failed to import plugin '{module}' declared in {manifest_source}")
        self.module = module
        self.manifest_source = manifest_source


def discover_plugins(plugins: tuple[str, ...], *, manifest_source: str, cwd: str) -> None:
    """Import each declared plugin module, once per process.

    Raises:
        PluginLoadError: If any plugin raises on import. Never skips a
            failing plugin — a gate whose plugin didn't load must not pass.
    """
    if not plugins:
        return

    sys.path.insert(0, cwd)
    try:
        for module in plugins:
            try:
                importlib.import_module(module)
            except Exception:
                _logger.exception(
                    "plugin '%s' declared in %s failed to import", module, manifest_source
                )
                raise PluginLoadError(module, manifest_source) from None
    finally:
        sys.path.remove(cwd)
