"""Pure data types for the tool protocol.

A tool is described by a :class:`ToolDescriptor` and executed through a
:class:`ToolExecutor` closure that a :class:`ToolFactory` binds to a resolved
:class:`JailSpec`. There is deliberately no ``Protocol`` here (design decision D2): every
tool has the same shape, so a protocol with a single implementer would be unjustified
indirection.
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


@dataclass(frozen=True)
class JailSpec:
    """The path boundary a tool executor is bound to: one root, zero or more exclusions.

    Both fields are **already resolved** — resolution happens once at bind time
    (:func:`squadron.tools.registry.materialize`), never inside a predicate. This continues
    the contract that a factory receives a resolved working directory rather than a string
    to interpret; a predicate that re-resolved per call would both cost per invocation and
    admit divergence between what was vetted and what is used.

    Attributes:
        root: The jail root. Every admitted path lies inside it, and it is the working
            directory ``bash`` runs in.
        excluded: Resolved paths inside *root* that are nonetheless refused. Carries no
            policy — who excludes what is decided by the caller (a review template), not
            here. Empty for every caller that wants plain jail behavior.
    """

    root: Path
    excluded: tuple[Path, ...] = ()

    @classmethod
    def rooted_at(cls, root: str | Path) -> JailSpec:
        """Build an exclusion-free spec, resolving *root* — the plain-jail convenience.

        Every non-review caller wants this, and it keeps constructing a spec as cheap as
        passing a ``Path`` was before the spec existed.
        """
        return cls(root=Path(root).resolve())


# An executor receives the model-supplied arguments and returns a result. It is bound to a
# jail specification by its factory, so ``cwd`` never appears in the argument dict.
ToolExecutor = Callable[[dict[str, object]], Awaitable[ToolResult]]

# A factory receives an already-resolved :class:`JailSpec` and returns a closure-bound
# executor.
ToolFactory = Callable[[JailSpec], ToolExecutor]


@dataclass(frozen=True)
class ToolDescriptor:
    """Static definition of a tool: what it is called, what it does, and how to build it.

    Attributes:
        name: Registry key and the name the model calls. Part of the canonical squadron tool
            vocabulary.
        description: Natural-language description handed to the model.
        parameters: JSON Schema object matching OpenAI's ``tools[].function.parameters``
            shape. ``cwd`` never appears here — the model cannot supply a working directory.
        factory: Called with an **already-resolved** :class:`JailSpec` and returns a
            closure-bound :data:`ToolExecutor`.
    """

    name: str
    description: str
    parameters: dict[str, object]
    factory: ToolFactory
