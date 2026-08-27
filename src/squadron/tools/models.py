"""Pure data types for the tool protocol.

A tool is described by a :class:`ToolDescriptor` and executed through a
:class:`ToolExecutor` closure that a :class:`ToolFactory` binds to a resolved working
directory. There is deliberately no ``Protocol`` here (design decision D2): every tool has
the same shape, so a protocol with a single implementer would be unjustified indirection.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ToolResult:
    """The outcome of a single tool invocation.

    Attributes:
        content: Text handed back to the model. On error this carries the reason, because the
            model must be able to react to what went wrong.
        is_error: True when the invocation failed. Errors are values, not exceptions —
            executors never raise to their caller.
    """

    content: str
    is_error: bool = False


# An executor receives the model-supplied arguments and returns a result. It is bound to a
# working directory by its factory, so ``cwd`` never appears in the argument dict.
ToolExecutor = Callable[[dict[str, object]], Awaitable[ToolResult]]

# A factory receives an already-resolved working directory and returns a closure-bound
# executor.
ToolFactory = Callable[[Path], ToolExecutor]


@dataclass(frozen=True)
class ToolDescriptor:
    """Static definition of a tool: what it is called, what it does, and how to build it.

    Attributes:
        name: Registry key and the name the model calls. Part of the canonical squadron tool
            vocabulary.
        description: Natural-language description handed to the model.
        parameters: JSON Schema object matching OpenAI's ``tools[].function.parameters``
            shape. ``cwd`` never appears here — the model cannot supply a working directory.
        factory: Called with an **already-resolved** ``cwd`` and returns a closure-bound
            :data:`ToolExecutor`.
    """

    name: str
    description: str
    parameters: dict[str, object]
    factory: ToolFactory
