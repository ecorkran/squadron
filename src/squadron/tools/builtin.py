"""Built-in tool implementations: ``read_file``, ``write_file``, ``bash``.

These names are the start of the canonical squadron tool vocabulary. Every executor is bound
to a resolved working directory by its factory; the file tools treat that directory as a jail
root and ``bash`` runs inside it.

The working directory is the only boundary at this stage. Network denial, environment
scrubbing, and process isolation are architecture-documented future work, deliberately out of
scope here.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from collections.abc import Awaitable, Callable
from pathlib import Path

from squadron.tools import limits
from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolResult
from squadron.tools.registry import register

# Canonical tool names. Defined once here and referenced everywhere else.
READ_FILE_NAME = "read_file"
WRITE_FILE_NAME = "write_file"
BASH_NAME = "bash"

_logger = logging.getLogger(__name__)


def _resolve_in_jail(cwd: Path, path: str) -> Path | None:
    """Resolve model-supplied *path* against jail root *cwd*, or return None if it escapes.

    ``cwd / path`` covers relative inputs, absolute inputs (``Path.__truediv__`` with an
    absolute right-hand operand yields that absolute path), and ``..`` traversal in one
    expression. ``resolve()`` follows symlinks first, so a link whose target lies outside the
    jail is rejected too.

    String prefix comparison is deliberately not used: it is wrong across path-component
    boundaries (``/tmp/jail_evil`` starts with ``/tmp/jail`` but is not inside it).
    """
    candidate = (cwd / path).resolve(strict=False)
    if not candidate.is_relative_to(cwd):
        return None
    return candidate


def _jail_violation(tool: str, path: str) -> ToolResult:
    """Build the error result for a rejected path and log it at WARNING.

    The working directory is the trust boundary, so an escape attempt must be visible without
    raising verbosity.
    """
    _logger.warning("%s: rejected path outside working directory: %s", tool, path)
    return ToolResult(
        content=f"Error: path '{path}' resolves outside the working directory and was rejected.",
        is_error=True,
    )


def _error(tool: str, message: str) -> ToolResult:
    """Build a routine error result and log it at INFO.

    These are outcomes the model probes for and reacts to — a missing file, a permission
    denial, a non-zero exit. Elevating them to WARNING would train operators to ignore
    warnings.
    """
    _logger.info("%s: %s", tool, message)
    return ToolResult(content=f"Error: {message}", is_error=True)


async def _guarded(tool: str, run: Callable[[], Awaitable[ToolResult]]) -> ToolResult:
    """Run *run*, converting expected failures into error results.

    Every executor routes through this wrapper. From slice 262 onward the caller is a model
    loop, so an unexpected tool bug must surface as an observable error result rather than
    crash the run — hence the catch-all, which is a process-boundary handler.
    """
    try:
        return await run()
    except FileNotFoundError as exc:
        return _error(tool, f"file not found: {exc.filename or exc}")
    except IsADirectoryError as exc:
        return _error(tool, f"path is a directory: {exc.filename or exc}")
    except NotADirectoryError as exc:
        return _error(tool, f"path component is not a directory: {exc.filename or exc}")
    except PermissionError as exc:
        return _error(tool, f"permission denied: {exc.filename or exc}")
    except UnicodeDecodeError as exc:
        return _error(tool, f"could not decode content: {exc}")
    except TimeoutError as exc:
        return _error(tool, f"operation timed out: {exc}")
    except Exception as exc:  # noqa: BLE001
        _logger.exception("%s: unexpected failure", tool)
        return ToolResult(content=f"Error: unexpected failure in {tool}: {exc}", is_error=True)


def _require_str(args: dict[str, object], key: str) -> str:
    """Return ``args[key]`` as a string, or raise ValueError describing what was wrong.

    Arguments arrive from a model and are untyped by construction, so they are narrowed at the
    boundary rather than indexed and passed blind.
    """
    if key not in args:
        raise ValueError(f"missing required argument '{key}'")
    value = args[key]
    if not isinstance(value, str):
        raise ValueError(f"argument '{key}' must be a string, got {type(value).__name__}")
    return value


def _truncate(data: bytes, limit: int, label: str) -> str:
    """Decode *data*, truncating to *limit* bytes with a visible trailing marker.

    Truncation is never silent: the model has to know it did not see everything. Decoding
    after the byte-level cut with ``errors="replace"`` also absorbs a split codepoint at the
    boundary.
    """
    if len(data) <= limit:
        return data.decode(errors="replace")
    kept = data[:limit].decode(errors="replace")
    return f"{kept}\n[truncated: {label} is {len(data)} bytes, showing first {limit}]"


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


def _read_file_factory(cwd: Path) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = _require_str(args, "path")
            target = _resolve_in_jail(cwd, path)
            if target is None:
                return _jail_violation(READ_FILE_NAME, path)

            data = await asyncio.to_thread(target.read_bytes)
            return ToolResult(content=_truncate(data, limits.MAX_READ_BYTES, str(target)))

        return await _guarded(READ_FILE_NAME, run)

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


def _write_file_factory(cwd: Path) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = _require_str(args, "path")
            content = _require_str(args, "content")

            target = _resolve_in_jail(cwd, path)
            if target is None:
                return _jail_violation(WRITE_FILE_NAME, path)
            # The parent is jail-checked before any directory is created, so a rejected path
            # never leaves a directory behind outside the jail.
            if _resolve_in_jail(cwd, str(target.parent)) is None:
                return _jail_violation(WRITE_FILE_NAME, path)
            if target.is_dir():
                return _error(WRITE_FILE_NAME, f"path is an existing directory: {path}")

            existed = target.exists()
            payload = content.encode()

            def _write() -> None:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

            await asyncio.to_thread(_write)

            verb = "Overwrote" if existed else "Created"
            return ToolResult(content=f"{verb} {path} ({len(payload)} bytes).")

        return await _guarded(WRITE_FILE_NAME, run)

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


BASH_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "command": {
            "type": "string",
            "description": "Shell command to run, anchored to the working directory.",
        }
    },
    "required": ["command"],
}


async def _kill_process_group(proc: asyncio.subprocess.Process) -> None:
    """Kill *proc*'s whole process group and reap it, so no zombie or orphan is left."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except ProcessLookupError:
        # The process exited on its own between the timeout firing and this kill. Nothing to
        # signal; the wait below still reaps it.
        pass
    await proc.wait()


def _bash_factory(cwd: Path) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            command = _require_str(args, "command")

            proc = await asyncio.create_subprocess_shell(
                command,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                # Required so the timeout path can kill the whole group, not just the shell.
                start_new_session=True,
            )

            # Read the limit at call time (module attribute), never captured at import, so a
            # lowered limit takes effect for the very next call.
            timeout = limits.BASH_TIMEOUT_S
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                await _kill_process_group(proc)
                _logger.warning(
                    "%s: command timed out after %ss and was killed: %s",
                    BASH_NAME,
                    timeout,
                    command,
                )
                return ToolResult(
                    content=(f"Error: command timed out after {timeout}s and was killed: {command}"),
                    is_error=True,
                )

            limit = limits.MAX_OUTPUT_BYTES
            stdout = _truncate(stdout_bytes, limit, "stdout")
            stderr = _truncate(stderr_bytes, limit, "stderr")
            body = f"stdout:\n{stdout}\nstderr:\n{stderr}"
            exit_code = proc.returncode

            if exit_code != 0:
                # The model needs the captured output to react, so it travels with the error.
                return _error(BASH_NAME, f"command exited with code {exit_code}.\n{body}")
            return ToolResult(content=body)

        return await _guarded(BASH_NAME, run)

    return execute


BASH = ToolDescriptor(
    name=BASH_NAME,
    description=(
        "Run a shell command in the working directory. Returns labeled stdout and stderr; "
        "long output is truncated with a visible marker and long-running commands are killed."
    ),
    parameters=BASH_PARAMETERS,
    factory=_bash_factory,
)

register(BASH)
