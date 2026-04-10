"""Emit destination registry and types for the summary pipeline action.

Provides the ``EmitKind`` enum, ``EmitDestination`` / ``EmitResult`` dataclasses,
the ``EmitFn`` callable type, and the module-level registry used by
``_execute_summary`` to dispatch summary text to one or more destinations.

Built-in destinations (stdout, file, clipboard, rotate) are registered when
this module is first imported.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from squadron.pipeline.models import ActionContext

_logger = logging.getLogger(__name__)

# Default directory for pipeline summary files written without an explicit path.
# Convention: ~/.config/squadron/runs/summaries/{project}-{pipeline}.md
_DEFAULT_SUMMARIES_DIR = Path.home() / ".config" / "squadron" / "runs" / "summaries"

__all__ = [
    "EmitKind",
    "EmitDestination",
    "EmitResult",
    "EmitFn",
    "register_emit",
    "get_emit",
    "parse_emit_entry",
    "parse_emit_list",
]


class EmitKind(StrEnum):
    """Canonical emit destination identifiers (match YAML grammar)."""

    STDOUT = "stdout"
    FILE = "file"
    CLIPBOARD = "clipboard"
    ROTATE = "rotate"


@dataclass(frozen=True)
class EmitDestination:
    """A single resolved emit destination."""

    kind: EmitKind
    arg: str | None = None  # path for FILE; unused otherwise

    def display(self) -> str:
        """Human-readable form: 'stdout', 'file:/tmp/x.md', 'file:(default)', etc."""
        if self.kind is EmitKind.FILE:
            return f"file:{self.arg}" if self.arg is not None else "file:(default)"
        return self.kind.value


@dataclass(frozen=True)
class EmitResult:
    """Outcome of a single emit operation."""

    destination: str  # human-readable, from EmitDestination.display()
    ok: bool
    detail: str


# EmitFn: async callable that writes summary text to one destination.
EmitFn = Callable[
    [str, EmitDestination, "ActionContext"],
    Awaitable[EmitResult],
]

_REGISTRY: dict[EmitKind, EmitFn] = {}


def register_emit(kind: EmitKind, fn: EmitFn) -> None:
    """Register an emit function for the given kind."""
    _REGISTRY[kind] = fn


def get_emit(kind: EmitKind) -> EmitFn:
    """Return the registered emit function for *kind*.

    Raises:
        KeyError: If no function is registered for *kind*.
    """
    return _REGISTRY[kind]


# ---------------------------------------------------------------------------
# Built-in emit destination implementations
# ---------------------------------------------------------------------------


async def _emit_stdout(
    text: str, dest: EmitDestination, ctx: ActionContext
) -> EmitResult:
    print(text)  # noqa: T201 — intentional user-facing output
    return EmitResult(destination=dest.display(), ok=True, detail="")


async def _emit_file(
    text: str, dest: EmitDestination, ctx: ActionContext
) -> EmitResult:
    if dest.arg is not None:
        path = Path(dest.arg)
        if not path.is_absolute():
            path = Path(ctx.cwd) / path
    else:
        # No explicit path — write to the conventional summaries location.
        project = str(ctx.params.get("_project") or "unknown")
        pipeline = ctx.pipeline_name or "unknown"
        _DEFAULT_SUMMARIES_DIR.mkdir(parents=True, exist_ok=True)
        path = _DEFAULT_SUMMARIES_DIR / f"{project}-{pipeline}.md"

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        encoded = text.encode("utf-8")
        path.write_bytes(encoded)
        return EmitResult(
            destination=dest.display(),
            ok=True,
            detail=f"wrote {len(encoded)} bytes",
        )
    except OSError as exc:
        _logger.warning("emit file failed: %s", exc)
        return EmitResult(destination=dest.display(), ok=False, detail=str(exc))


async def _emit_clipboard(
    text: str, dest: EmitDestination, ctx: ActionContext
) -> EmitResult:
    import pyperclip  # lazy import — platform probe can fail on headless systems

    try:
        await asyncio.to_thread(pyperclip.copy, text)
        return EmitResult(destination=dest.display(), ok=True, detail="")
    except pyperclip.PyperclipException as exc:
        return EmitResult(destination=dest.display(), ok=False, detail=str(exc))


async def _emit_rotate(
    text: str, dest: EmitDestination, ctx: ActionContext
) -> EmitResult:
    if ctx.sdk_session is None:
        return EmitResult(
            destination=dest.display(),
            ok=False,
            detail="rotate emit requires SDK execution mode",
        )
    try:
        await ctx.sdk_session.compact(
            instructions="",
            summary=text,
            restore_model=ctx.sdk_session.current_model,
        )
        return EmitResult(destination=dest.display(), ok=True, detail="session rotated")
    except Exception as exc:
        return EmitResult(destination=dest.display(), ok=False, detail=str(exc))


# Register all built-in destinations at import time.
register_emit(EmitKind.STDOUT, _emit_stdout)
register_emit(EmitKind.FILE, _emit_file)
register_emit(EmitKind.CLIPBOARD, _emit_clipboard)
register_emit(EmitKind.ROTATE, _emit_rotate)


# ---------------------------------------------------------------------------
# YAML parse helpers
# ---------------------------------------------------------------------------


def parse_emit_entry(entry: object) -> EmitDestination:
    """Parse a single YAML emit entry into an EmitDestination.

    Accepted forms:
      - ``"stdout"`` / ``"clipboard"`` / ``"rotate"`` — bare strings
      - ``{"file": "<path>"}`` — one-key dict with a non-empty string path

    Raises:
        ValueError: On any other shape or unknown kind.
    """
    if isinstance(entry, str):
        try:
            kind = EmitKind(entry)
        except ValueError:
            raise ValueError(f"unknown emit destination: {entry!r}")
        # Bare "file" string → default path (no explicit arg).
        return EmitDestination(kind=kind)

    if isinstance(entry, dict):
        d: dict[object, object] = cast(dict[object, object], entry)
        keys = list(d.keys())
        if keys != ["file"]:
            raise ValueError(
                f"emit dict must have exactly one key 'file', got: {keys!r}"
            )
        arg = d["file"]
        if not isinstance(arg, str) or not arg:
            raise ValueError(
                f"'file' emit path must be a non-empty string, got: {arg!r}"
            )
        return EmitDestination(kind=EmitKind.FILE, arg=arg)

    raise ValueError(
        f"emit entry must be a string or dict, got: {type(entry).__name__}"
    )


def parse_emit_list(raw: object) -> list[EmitDestination]:
    """Parse a YAML emit value into a list of EmitDestination.

    - ``None`` or missing → ``[EmitDestination(EmitKind.STDOUT)]``
    - ``list[...]`` → each entry parsed via ``parse_emit_entry``
    - anything else → ``ValueError``

    Raises:
        ValueError: On unknown kinds, empty list, or wrong shape.
    """
    if raw is None:
        return [EmitDestination(kind=EmitKind.STDOUT)]

    if not isinstance(raw, list):
        raise ValueError(f"emit must be a list or null, got: {type(raw).__name__}")

    entries = cast(list[object], raw)
    if len(entries) == 0:
        raise ValueError("emit list cannot be empty")

    return [parse_emit_entry(entry) for entry in entries]
