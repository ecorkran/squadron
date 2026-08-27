"""Tool registry, descriptor protocol, and built-in tool implementations.

Importing this package registers the built-in tools and does nothing else — no logging
configuration, no filesystem access, no environment reads.
"""

from __future__ import annotations

# builtin is imported for its side effect: it calls register() at module scope.
from squadron.tools import builtin  # noqa: F401  # pyright: ignore[reportUnusedImport]
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
