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
