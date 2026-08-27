"""Exceptions raised by the tool registry."""

from __future__ import annotations


class ToolNotRegisteredError(Exception):
    """Raised when :func:`squadron.tools.registry.materialize` is given an unknown tool name.

    This signals a *caller configuration* error — the process asked for a tool that was never
    registered — not a model error. Tool executors never raise to their caller; they return
    ``ToolResult(is_error=True)`` instead.
    """
