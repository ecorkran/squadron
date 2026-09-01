"""Tool registry, descriptor protocol, and built-in tool implementations.

Importing this package registers the built-in tools and does nothing else — no logging
configuration, no filesystem access, no environment reads.
"""

from __future__ import annotations

# builtin and cf_tools are imported for their side effect: each calls register() at module
# scope. cf_tools registers unconditionally (design D4) so pipeline validation does not depend
# on whether the context-forge MCP server is launchable on this machine.
from squadron.tools import builtin  # noqa: F401  # pyright: ignore[reportUnusedImport]
from squadron.tools import cf_tools  # noqa: F401  # pyright: ignore[reportUnusedImport]
from squadron.tools.errors import ToolNotRegisteredError
from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolFactory, ToolResult
from squadron.tools.registry import list_tools, lookup, materialize, register

__all__ = [
    "ToolDescriptor",
    "ToolExecutor",
    "ToolFactory",
    "ToolNotRegisteredError",
    "ToolResult",
    "list_tools",
    "lookup",
    "materialize",
    "register",
]
