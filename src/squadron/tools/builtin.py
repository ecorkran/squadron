"""Built-in tool implementations: ``read_file``, ``write_file``, ``bash``, ``list_files``, ``grep``.

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
import time
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

import regex

from squadron.tools import limits
from squadron.tools.models import ToolDescriptor, ToolExecutor, ToolResult
from squadron.tools.registry import register

# Canonical tool names. Defined once here and referenced everywhere else.
READ_FILE_NAME = "read_file"
WRITE_FILE_NAME = "write_file"
BASH_NAME = "bash"
LIST_FILES_NAME = "list_files"
GREP_NAME = "grep"

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


def _reject_special_file(tool: str, target: Path) -> ToolResult | None:
    """Return an error result if *target* exists and is not a regular file, else None.

    A read or write against a FIFO, device node, or socket blocks in the thread pool with no
    way to cancel it — unlike ``bash``, which can kill its subprocess. ``asyncio.to_thread``
    workers are not interruptible, so a caller-side ``wait_for`` does not rescue the process
    either: the interpreter joins the stuck thread at shutdown and hangs anyway. The jail
    admits any path under the working directory, so a special file inside it is realistic
    input, not a hypothetical. The only reliable defense is to refuse before opening.

    Directories are deliberately not rejected here — the file tools report those with their own
    specific messages.
    """
    if not target.exists() or target.is_dir():
        return None
    if not target.is_file():
        return _error(tool, f"path is not a regular file: {target.name}")
    return None


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

            # Every blocking syscall — the resolve/stat walk, the special-file check, and the
            # read itself — runs in one worker thread. Resolving on the event loop would
            # stall it on a slow or network filesystem (rules/python.md: synchronous work
            # inside an async def must complete in under 1ms).
            def _read() -> ToolResult:
                target = _resolve_in_jail(cwd, path)
                if target is None:
                    return _jail_violation(READ_FILE_NAME, path)
                rejection = _reject_special_file(READ_FILE_NAME, target)
                if rejection is not None:
                    return rejection
                data = target.read_bytes()
                return ToolResult(content=_truncate(data, limits.MAX_READ_BYTES, str(target)))

            return await asyncio.to_thread(_read)

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

            payload = content.encode()

            # As in read_file, every blocking syscall runs in one worker thread rather than on
            # the event loop. No separate jail check on target.parent: resolve() de-symlinks
            # every existing component, so a target inside the jail always has a parent inside
            # the jail — a second check cannot reject anything the first accepted, and nothing
            # is created before that check runs.
            def _write() -> ToolResult:
                target = _resolve_in_jail(cwd, path)
                if target is None:
                    return _jail_violation(WRITE_FILE_NAME, path)
                if target.is_dir():
                    return _error(WRITE_FILE_NAME, f"path is an existing directory: {path}")
                rejection = _reject_special_file(WRITE_FILE_NAME, target)
                if rejection is not None:
                    return rejection

                existed = target.exists()
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(payload)

                verb = "Overwrote" if existed else "Created"
                return ToolResult(content=f"{verb} {path} ({len(payload)} bytes).")

            return await asyncio.to_thread(_write)

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


def _optional_str(args: dict[str, object], key: str, default: str) -> str:
    """Return ``args[key]`` as a string, falling back to *default* when absent or null.

    Same boundary-narrowing rationale as ``_require_str``: model-supplied arguments are
    untyped, and an optional argument that arrives with the wrong type is a caller error the
    model can correct, not something to coerce silently.
    """
    value = args.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"argument '{key}' must be a string, got {type(value).__name__}")
    return value


def _optional_bool(args: dict[str, object], key: str, default: bool) -> bool:
    """Return ``args[key]`` as a bool, falling back to *default* when absent or null."""
    value = args.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"argument '{key}' must be a boolean, got {type(value).__name__}")
    return value


def _format_entry(entry: Path, root: Path) -> str:
    """Render *entry* relative to jail root *root*, marking directories with a trailing slash."""
    rendered = str(entry.relative_to(root))
    return f"{rendered}/" if entry.is_dir() else rendered


def _list_files_factory(cwd: Path) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            path = _optional_str(args, "path", ".")
            pattern = _optional_str(args, "pattern", "*")
            recursive = _optional_bool(args, "recursive", False)

            # As in read_file, the whole blocking walk — resolve, stat, iterate — runs in one
            # worker thread rather than on the event loop.
            def _walk() -> ToolResult:
                target = _resolve_in_jail(cwd, path)
                if target is None:
                    return _jail_violation(LIST_FILES_NAME, path)
                if not target.exists():
                    return _error(LIST_FILES_NAME, f"path does not exist: {path}")
                if not target.is_dir():
                    return _error(LIST_FILES_NAME, f"path is not a directory: {path}")

                matches = target.rglob(pattern) if recursive else target.glob(pattern)
                lines = sorted(_format_entry(entry, cwd) for entry in matches)
                body = "\n".join(lines)
                # Read the limit at call time (module attribute), never captured at import.
                return ToolResult(content=_truncate(body.encode(), limits.MAX_OUTPUT_BYTES, "listing"))

            return await asyncio.to_thread(_walk)

        return await _guarded(LIST_FILES_NAME, run)

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


GREP_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {
        "pattern": {
            "type": "string",
            "description": "Regular expression matched against each line.",
        },
        "path": {
            "type": "string",
            "description": (
                "File or directory to search, relative to the working directory. Defaults to '.'."
            ),
        },
        "glob": {
            "type": "string",
            "description": "Optional filename filter applied when path is a directory, e.g. '*.py'.",
        },
        "max_results": {
            "type": "integer",
            "description": "Stop after this many matches.",
        },
    },
    "required": ["pattern"],
}


def _optional_int(args: dict[str, object], key: str) -> int | None:
    """Return ``args[key]`` as an int, or None when absent or null.

    ``bool`` is rejected explicitly: it is a subclass of ``int``, so a model passing ``true``
    would otherwise silently become a cap of 1.
    """
    value = args.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"argument '{key}' must be an integer, got {type(value).__name__}")
    return value


def _grep_candidates(target: Path, glob: str | None) -> Iterator[Path]:
    """Yield the files *target* expands to, filtered by *glob* when it is a directory.

    Deliberately lazy and unsorted: a sorted list would walk and materialize the entire tree
    before the caller's first deadline check, so a large enough tree could blow the whole-walk
    budget during traversal alone — before a single line was ever matched.
    """
    if target.is_file():
        yield target
        return
    for entry in target.rglob(glob or "*"):
        if entry.is_file():
            yield entry


def _grep_factory(cwd: Path) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            pattern = _require_str(args, "pattern")
            path = _optional_str(args, "path", ".")
            glob = args.get("glob")
            if glob is not None and not isinstance(glob, str):
                raise ValueError(f"argument 'glob' must be a string, got {type(glob).__name__}")
            max_results = _optional_int(args, "max_results")

            # The whole walk — resolve, directory expansion, every file read, and all regex
            # matching — runs in one worker thread. Matching is CPU-bound by construction (the
            # timeout exists precisely because a model-supplied pattern can backtrack
            # catastrophically), so it must never run on the event loop.
            def _search() -> ToolResult:
                target = _resolve_in_jail(cwd, path)
                if target is None:
                    return _jail_violation(GREP_NAME, path)
                if not target.exists():
                    return _error(GREP_NAME, f"path does not exist: {path}")

                try:
                    compiled = regex.compile(pattern)
                except regex.error as exc:
                    # Returned, never raised: the model supplied the pattern and is the one
                    # that has to correct it.
                    return _error(GREP_NAME, f"invalid regular expression {pattern!r}: {exc}")

                # Read the limit at call time (module attribute), never captured at import.
                budget = limits.GREP_TIMEOUT_S
                deadline = time.monotonic() + budget

                matches: list[str] = []
                for candidate in _grep_candidates(target, glob):
                    # Checked per candidate as well as per line: traversal of a large tree and
                    # the reads themselves consume wall time the per-line check never sees.
                    if time.monotonic() >= deadline:
                        return _grep_timeout(pattern, budget)
                    try:
                        # Bounded like read_file: an enormous file must not consume the whole
                        # budget (or the process's memory) inside a single unbounded read.
                        with candidate.open("rb") as handle:
                            raw = handle.read(limits.MAX_READ_BYTES)
                        text = raw.decode(errors="replace")
                    except (OSError, UnicodeDecodeError):
                        # An unreadable or undecodable file inside the tree is normal input for
                        # a whole-directory search; skipping it is correct, and the remaining
                        # files still produce results.
                        continue

                    relative = candidate.relative_to(cwd)
                    for number, line in enumerate(text.splitlines(), start=1):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return _grep_timeout(pattern, budget)
                        try:
                            # The per-call timeout is scoped to what is left of the whole-walk
                            # budget, so the sum across every line of every file cannot exceed
                            # GREP_TIMEOUT_S for the call.
                            found = compiled.search(line, timeout=remaining)
                        except TimeoutError:
                            return _grep_timeout(pattern, budget)
                        if found is None:
                            continue
                        matches.append(f"{relative}:{number}:{line}")
                        if max_results is not None and len(matches) >= max_results:
                            break
                    if max_results is not None and len(matches) >= max_results:
                        break

                body = "\n".join(matches)
                return ToolResult(content=_truncate(body.encode(), limits.MAX_OUTPUT_BYTES, "matches"))

            return await asyncio.to_thread(_search)

        return await _guarded(GREP_NAME, run)

    return execute


def _grep_timeout(pattern: str, budget: float) -> ToolResult:
    """Build the error result for an exhausted grep budget and log it at WARNING.

    Mirrors the bash timeout path: an abandoned search is an operator-visible event, and the
    model needs to know its pattern — not the tree — was the problem.
    """
    _logger.warning(
        "%s: pattern exceeded the %ss budget and was abandoned: %s", GREP_NAME, budget, pattern
    )
    return ToolResult(
        content=(
            f"Error: pattern {pattern!r} exceeded the {budget}s search budget and was abandoned. "
            "Use a simpler or more anchored pattern."
        ),
        is_error=True,
    )


GREP = ToolDescriptor(
    name=GREP_NAME,
    description=(
        "Search files under the working directory for lines matching a regular expression. "
        "Returns 'path:line:text' matches; long output is truncated with a visible marker and "
        "expensive patterns are abandoned against a wall-clock budget."
    ),
    parameters=GREP_PARAMETERS,
    factory=_grep_factory,
)

register(GREP)
