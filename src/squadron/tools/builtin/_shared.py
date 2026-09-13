"""Shared helpers for the built-in tools: the path jail, error results, and argument
coercion.

Split out of the former single-module ``builtin.py`` (slice 266, T23). Pure move — no
logic changed."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Iterator
from pathlib import Path

from squadron.tools import limits
from squadron.tools.models import JailSpec, ToolResult

# Canonical tool names. Defined once here and referenced everywhere else.
READ_FILE_NAME = "read_file"
WRITE_FILE_NAME = "write_file"
BASH_NAME = "bash"
LIST_FILES_NAME = "list_files"
GREP_NAME = "grep"

_logger = logging.getLogger(__name__)


def _excluding(spec: JailSpec, candidate: Path) -> Path | None:
    """Return the exclusion *candidate* falls inside, or None if it falls inside none.

    Matched with ``is_relative_to`` for the same reason containment is: a string prefix is
    wrong across path-component boundaries, so a sibling named ``reviews-archive`` would be
    swept up by an exclusion of ``reviews``.
    """
    for excluded in spec.excluded:
        if candidate.is_relative_to(excluded):
            return excluded
    return None


def resolve_in_jail(spec: JailSpec, path: str) -> Path | None:
    """Resolve model-supplied *path* against *spec*, or return None if it is not admitted.

    ``root / path`` covers relative inputs, absolute inputs (``Path.__truediv__`` with an
    absolute right-hand operand yields that absolute path), and ``..`` traversal in one
    expression. ``resolve()`` follows symlinks first, so a link whose target lies outside the
    jail is rejected too.

    A candidate inside ``spec.excluded`` returns None by the **same return** as a
    containment failure: every caller already handles None, so no tool contract or
    model-visible behavior distinguishes the two.

    Neither refusal is logged here. Every caller turns the None into a result through
    :func:`jail_violation`, which is the single place a refusal is both worded and logged —
    so a refusal produces exactly one WARNING, and the two kinds cannot drift into
    contradicting each other.

    String prefix comparison is deliberately not used: it is wrong across path-component
    boundaries (``/tmp/jail_evil`` starts with ``/tmp/jail`` but is not inside it). The same
    trap applies to exclusion matching.
    """
    candidate = (spec.root / path).resolve(strict=False)
    if not candidate.is_relative_to(spec.root):
        return None
    if _excluding(spec, candidate) is not None:
        return None
    return candidate


def contained_in_jail(spec: JailSpec, entry: Path, *, tool: str) -> bool:
    """Return whether *entry* is admitted by *spec*, logging refusals.

    A walk yields entries that were never checked against the jail: ``Path.is_file()``
    follows symlinks, so a link inside the jail pointing outside it looks like an ordinary
    file, and on Python <= 3.12 ``rglob`` also recurses *into* symlinked directories.
    Re-resolving each candidate closes both routes at the point candidates are produced.
    The same re-resolution is what lets an exclusion be enforced here rather than relying on
    the walk never reaching an excluded subtree.

    The refusal is silent to the model (design D6) — a skipped entry is indistinguishable
    from one that did not match, whereas "you were denied" invites probing for the jail
    boundary. That rationale covers exclusions too, and more sharply: an excluded review
    artifact is named after the document under review, so leaking the *name* leaks the fact.
    Both are logged at WARNING, worded distinguishably, so a refusal is observable to an
    operator.
    """
    resolved = entry.resolve(strict=False)
    if not resolved.is_relative_to(spec.root):
        _logger.warning(
            "%s: refusing jail escape via %s -> %s (outside %s)", tool, entry, resolved, spec.root
        )
        return False
    excluded = _excluding(spec, resolved)
    if excluded is not None:
        _logger.warning("%s: refusing excluded path %s (inside excluded %s)", tool, resolved, excluded)
        return False
    return True


def walk_tree(root: Path, *, recursive: bool = True) -> Iterator[Path]:
    """Yield entries under *root*, pruning ``limits.SKIP_DIRECTORIES`` as it descends.

    ``Path.rglob`` cannot prune: it yields every entry, so a caller filtering afterwards has
    already paid to stat everything under ``.venv`` or ``node_modules``. That cost, not
    regex backtracking, is what exhausted the ``grep`` budget in practice (issue #79).

    Pruning is by exact directory name at any depth, and applies to *descent* only — a
    caller that explicitly asks for ``.venv`` as its root still gets it, since the skip set
    is consulted for children rather than for *root* itself.

    Lazy across directories, eager within one: each level's listing is read and sorted
    before its first entry is yielded, so output order is deterministic and the cost of
    stopping early is bounded by the widest single directory rather than by the tree.
    Descent into a child happens only when the caller pulls past it, which is what lets
    the budget and entry caps upstream stop the walk.
    """
    skip = limits.SKIP_DIRECTORIES
    try:
        entries = sorted(root.iterdir())
    except OSError:  # PermissionError is an OSError subclass; both are covered
        # An unreadable directory inside the tree is normal input for a whole-tree walk;
        # the remaining entries are still worth yielding.
        return
    for entry in entries:
        yield entry
        if not recursive:
            continue
        if entry.name in skip:
            _logger.debug("walk: pruning %s", entry)
            continue
        # is_dir() follows symlinks; descending through one is how a walk leaves the jail,
        # so links are yielded above (the caller's containment check sees them) but never
        # descended into.
        if entry.is_dir() and not entry.is_symlink():
            yield from walk_tree(entry, recursive=True)


def reject_special_file(tool: str, target: Path) -> ToolResult | None:
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
        return error(tool, f"path is not a regular file: {target.name}")
    return None


def jail_violation(tool: str, spec: JailSpec, path: str) -> ToolResult:
    """Build the error result for a path :func:`resolve_in_jail` refused, and log it once.

    The single wording-and-logging site for both refusals, which is what keeps one refusal
    to one WARNING. It re-resolves to classify, which costs nothing in practice: this runs
    only on the refusal path.

    The two are logged distinguishably — an escape means someone reached for the trust
    boundary, an exclusion means a legitimate path was deliberately withheld — and an
    operator has to be able to tell them apart.

    What the **model** sees does not distinguish them, and for an exclusion it deliberately
    does not mention the exclusion at all: it gets the same "not found" a path that was never
    there would get (design D6). Naming the refusal would both invite probing for the
    boundary and, since review artifacts are named after the document under review, confirm
    that the document's own predecessors exist.
    """
    candidate = (spec.root / path).resolve(strict=False)
    if candidate.is_relative_to(spec.root) and (excluded := _excluding(spec, candidate)) is not None:
        _logger.warning("%s: refusing excluded path %s (inside excluded %s)", tool, candidate, excluded)
        # Built directly rather than via error(), which would add a second (INFO) record
        # for a refusal specified to log exactly once. The text reproduces exactly what
        # error() emits for a genuine FileNotFoundError — that message carries
        # ``exc.filename``, the *resolved* path, so the resolved candidate is used here
        # rather than the model's spelling. Any divergence is a distinguisher.
        return ToolResult(content=f"Error: file not found: {candidate}", is_error=True)
    _logger.warning("%s: rejected path outside working directory: %s", tool, path)
    return ToolResult(
        content=f"Error: path '{path}' resolves outside the working directory and was rejected.",
        is_error=True,
    )


def error(tool: str, message: str) -> ToolResult:
    """Build a routine error result and log it at INFO.

    These are outcomes the model probes for and reacts to — a missing file, a permission
    denial, a non-zero exit. Elevating them to WARNING would train operators to ignore
    warnings.
    """
    _logger.info("%s: %s", tool, message)
    return ToolResult(content=f"Error: {message}", is_error=True)


async def guarded(tool: str, run: Callable[[], Awaitable[ToolResult]]) -> ToolResult:
    """Run *run*, converting expected failures into error results.

    Every executor routes through this wrapper. From slice 262 onward the caller is a model
    loop, so an unexpected tool bug must surface as an observable error result rather than
    crash the run — hence the catch-all, which is a process-boundary handler.
    """
    try:
        return await run()
    except FileNotFoundError as exc:
        return error(tool, f"file not found: {exc.filename or exc}")
    except IsADirectoryError as exc:
        return error(tool, f"path is a directory: {exc.filename or exc}")
    except NotADirectoryError as exc:
        return error(tool, f"path component is not a directory: {exc.filename or exc}")
    except PermissionError as exc:
        return error(tool, f"permission denied: {exc.filename or exc}")
    except UnicodeDecodeError as exc:
        return error(tool, f"could not decode content: {exc}")
    except TimeoutError as exc:
        return error(tool, f"operation timed out: {exc}")
    except Exception as exc:  # noqa: BLE001
        _logger.exception("%s: unexpected failure", tool)
        return ToolResult(content=f"Error: unexpected failure in {tool}: {exc}", is_error=True)


def require_str(args: dict[str, object], key: str) -> str:
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


def truncate(data: bytes, limit: int, label: str) -> str:
    """Decode *data*, truncating to *limit* bytes with a visible trailing marker.

    Truncation is never silent: the model has to know it did not see everything. Decoding
    after the byte-level cut with ``errors="replace"`` also absorbs a split codepoint at the
    boundary.
    """
    if len(data) <= limit:
        return data.decode(errors="replace")
    kept = data[:limit].decode(errors="replace")
    return f"{kept}\n[truncated: {label} is {len(data)} bytes, showing first {limit}]"


def optional_str(args: dict[str, object], key: str, default: str) -> str:
    """Return ``args[key]`` as a string, falling back to *default* when absent or null.

    Same boundary-narrowing rationale as ``require_str``: model-supplied arguments are
    untyped, and an optional argument that arrives with the wrong type is a caller error the
    model can correct, not something to coerce silently.
    """
    value = args.get(key)
    if value is None:
        return default
    if not isinstance(value, str):
        raise ValueError(f"argument '{key}' must be a string, got {type(value).__name__}")
    return value


def optional_bool(args: dict[str, object], key: str, default: bool) -> bool:
    """Return ``args[key]`` as a bool, falling back to *default* when absent or null."""
    value = args.get(key)
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ValueError(f"argument '{key}' must be a boolean, got {type(value).__name__}")
    return value


def format_entry(entry: Path, root: Path) -> str:
    """Render *entry* relative to jail root *root*, marking directories with a trailing slash."""
    rendered = str(entry.relative_to(root))
    return f"{rendered}/" if entry.is_dir() else rendered


def optional_int(args: dict[str, object], key: str) -> int | None:
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
