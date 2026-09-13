"""File tools: ``read_file``, ``write_file``, ``list_files``.

Split out of the former single-module ``builtin.py`` (slice 266, T23). Pure move — no
logic changed."""

from __future__ import annotations

import asyncio
import logging

from squadron.tools import limits
from squadron.tools.builtin._shared import (
    LIST_FILES_NAME,
    READ_FILE_NAME,
    WRITE_FILE_NAME,
    contained_in_jail,
    error,
    format_entry,
    guarded,
    jail_violation,
    optional_bool,
    optional_str,
    reject_special_file,
    require_str,
    resolve_in_jail,
    truncate,
    walk_tree,
)
from squadron.tools.models import JailSpec, ToolDescriptor, ToolExecutor, ToolResult
from squadron.tools.registry import register

_logger = logging.getLogger(__name__)


READ_FILE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to read, relative to the working directory.",
        }
    },
    "required": ["path"],
}


def _read_file_factory(spec: JailSpec) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = require_str(args, "path")

            # Every blocking syscall — the resolve/stat walk, the special-file check, and the
            # read itself — runs in one worker thread. Resolving on the event loop would
            # stall it on a slow or network filesystem (rules/python.md: synchronous work
            # inside an async def must complete in under 1ms).
            def _read() -> ToolResult:
                target = resolve_in_jail(spec, path)
                if target is None:
                    return jail_violation(READ_FILE_NAME, spec, path)
                rejection = reject_special_file(READ_FILE_NAME, target)
                if rejection is not None:
                    return rejection
                data = target.read_bytes()
                return ToolResult(content=truncate(data, limits.MAX_READ_BYTES, str(target)))

            return await asyncio.to_thread(_read)

        return await guarded(READ_FILE_NAME, run)

    return execute


READ_FILE = ToolDescriptor(
    name=READ_FILE_NAME,
    description=(
        "Read a UTF-8 text file from the working directory. Output beyond the size limit is "
        "truncated with a visible marker."
    ),
    parameters=READ_FILE_PARAMETERS,
    factory=_read_file_factory,
)

register(READ_FILE)

WRITE_FILE_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Path to the file to write, relative to the working directory.",
        },
        "content": {
            "type": "string",
            "description": "Full text content to write. Existing files are overwritten.",
        },
    },
    "required": ["path", "content"],
}


def _write_file_factory(spec: JailSpec) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = require_str(args, "path")
            content = require_str(args, "content")

            payload = content.encode()

            # As in read_file, every blocking syscall runs in one worker thread rather than on
            # the event loop. No separate jail check on target.parent: resolve() de-symlinks
            # every existing component, so a target inside the jail always has a parent inside
            # the jail — a second check cannot reject anything the first accepted, and nothing
            # is created before that check runs.
            def _write() -> ToolResult:
                target = resolve_in_jail(spec, path)
                if target is None:
                    return jail_violation(WRITE_FILE_NAME, spec, path)
                if target.is_dir():
                    return error(WRITE_FILE_NAME, f"path is an existing directory: {path}")
                rejection = reject_special_file(WRITE_FILE_NAME, target)
                if rejection is not None:
                    return rejection

                existed = target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

                verb = "Overwrote" if existed else "Created"
                return ToolResult(content=f"{verb} {path} ({len(payload)} bytes).")

            return await asyncio.to_thread(_write)

        return await guarded(WRITE_FILE_NAME, run)

    return execute


WRITE_FILE = ToolDescriptor(
    name=WRITE_FILE_NAME,
    description=(
        "Write a UTF-8 text file inside the working directory, creating parent directories as "
        "needed. Existing files are overwritten."
    ),
    parameters=WRITE_FILE_PARAMETERS,
    factory=_write_file_factory,
)

register(WRITE_FILE)

LIST_FILES_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "path": {
            "type": "string",
            "description": "Directory to list, relative to the working directory. Defaults to '.'.",
        },
        "pattern": {
            "type": "string",
            "description": "Optional glob filter, e.g. '*.py'. Defaults to every entry.",
        },
        "recursive": {
            "type": "boolean",
            "description": "Descend into subdirectories. Defaults to false.",
        },
    },
    "required": [],
}


def _list_files_factory(spec: JailSpec) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = optional_str(args, "path", ".")
            pattern = optional_str(args, "pattern", "*")
            recursive = optional_bool(args, "recursive", False)

            # As in read_file, the whole blocking walk — resolve, stat, iterate — runs in one
            # worker thread rather than on the event loop.
            def _walk() -> ToolResult:
                target = resolve_in_jail(spec, path)
                if target is None:
                    return jail_violation(LIST_FILES_NAME, spec, path)
                if not target.exists():
                    return error(LIST_FILES_NAME, f"path does not exist: {path}")
                if not target.is_dir():
                    return error(LIST_FILES_NAME, f"path is not a directory: {path}")

                # walk_tree prunes dependency/VCS directories as it descends (issue #79);
                # the pattern is applied to the names it yields, since rglob cannot prune.
                walked = walk_tree(target, recursive=recursive)
                matches = (entry for entry in walked if entry.match(pattern))
                # Consumption stops at the cap, so a wide tree costs a bounded walk rather
                # than a full materialization. sorted() below would otherwise drain the
                # whole iterator before the byte-level cap could apply to anything.
                max_entries = limits.MAX_LIST_ENTRIES
                collected: list[str] = []
                capped = False
                for entry in matches:
                    if len(collected) >= max_entries:
                        capped = True
                        break
                    if contained_in_jail(spec, entry, tool=LIST_FILES_NAME):
                        collected.append(format_entry(entry, spec.root))

                lines = sorted(collected)
                if capped:
                    _logger.warning(
                        "%s: walk stopped at the %d-entry cap under %s",
                        LIST_FILES_NAME,
                        max_entries,
                        path,
                    )
                    # A short listing must stay distinguishable from a truncated one.
                    lines.append(f"[stopped after {max_entries} entries; the listing is partial]")
                body = "\n".join(lines)
                # Read the limit at call time (module attribute), never captured at import.
                return ToolResult(content=truncate(body.encode(), limits.MAX_OUTPUT_BYTES, "listing"))

            return await asyncio.to_thread(_walk)

        return await guarded(LIST_FILES_NAME, run)

    return execute


LIST_FILES = ToolDescriptor(
    name=LIST_FILES_NAME,
    description=(
        "List files and directories inside the working directory, optionally filtered by a "
        "glob pattern and optionally recursive. Directories are marked with a trailing slash; "
        "long listings are truncated with a visible marker."
    ),
    parameters=LIST_FILES_PARAMETERS,
    factory=_list_files_factory,
)

register(LIST_FILES)
