"""The ``grep`` search tool.

Split out of the former single-module ``builtin.py`` (slice 266, T23). Pure move — no
logic changed."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Iterator
from pathlib import Path

import regex

from squadron.tools import limits
from squadron.tools.builtin._shared import (
    GREP_NAME,
    contained_in_jail,
    error,
    guarded,
    jail_violation,
    optional_int,
    optional_str,
    require_str,
    resolve_in_jail,
    truncate,
    walk_tree,
)
from squadron.tools.models import JailSpec, ToolDescriptor, ToolExecutor, ToolResult
from squadron.tools.registry import register

_logger = logging.getLogger(__name__)


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


def _globbed(target: Path, glob: str | None) -> Iterator[Path]:
    """Yield entries under *target*, pruned, honoring *glob* when one is given.

    ``walk_tree`` does the pruning; the glob is applied to the yielded names rather than
    handed to ``rglob``, because ``rglob`` cannot prune as it descends.
    """
    for entry in walk_tree(target, recursive=True):
        if glob is None or entry.match(glob):
            yield entry


def _grep_candidates(spec: JailSpec, target: Path, glob: str | None) -> Iterator[Path]:
    """Yield the files *target* expands to, filtered by *glob* when it is a directory.

    Lazy across directories: ``walk_tree`` sorts one level at a time and descends only as
    the caller pulls, so the deadline check between files can stop the walk without the
    whole tree having been listed first.

    Every candidate is re-checked against *spec*: this is the single point all
    candidates pass through, so both symlink escape routes close here.

    Dependency and VCS directories are pruned during descent (``limits.SKIP_DIRECTORIES``).
    Reading them is what actually exhausted the budget in practice — they are the bulk of a
    real tree and never the code a model is asking about (issue #79).
    """
    if target.is_file():
        if contained_in_jail(spec, target, tool=GREP_NAME):
            yield target
        return
    for entry in _globbed(target, glob):
        # Containment is checked before is_file(): on Python 3.13+ rglob yields a symlinked
        # directory without descending into it, and is_file() is False for that entry — so
        # testing is_file() first would skip the escape silently instead of logging it.
        if not contained_in_jail(spec, entry, tool=GREP_NAME):
            continue
        if entry.is_file():
            yield entry


def _grep_factory(spec: JailSpec) -> ToolExecutor:
    async def execute(args: dict[str, object]) -> ToolResult:
        async def run() -> ToolResult:
            pattern = require_str(args, "pattern")
            path = optional_str(args, "path", ".")
            glob = args.get("glob")
            if glob is not None and not isinstance(glob, str):
                raise ValueError(f"argument 'glob' must be a string, got {type(glob).__name__}")
            max_results = optional_int(args, "max_results")

            # The whole walk — resolve, directory expansion, every file read, and all regex
            # matching — runs in one worker thread. Matching is CPU-bound by construction (the
            # timeout exists precisely because a model-supplied pattern can backtrack
            # catastrophically), so it must never run on the event loop.
            def _search() -> ToolResult:
                target = resolve_in_jail(spec, path)
                if target is None:
                    return jail_violation(GREP_NAME, spec, path)
                if not target.exists():
                    return error(GREP_NAME, f"path does not exist: {path}")

                # Checked before compile(), not after: an unbounded pattern must never
                # reach the engine at all. Returned rather than raised, matching the
                # invalid-regex branch below — the model supplied it and must correct it.
                if len(pattern) > limits.MAX_PATTERN_CHARS:
                    return _oversized_pattern(pattern)

                try:
                    compiled = regex.compile(pattern)
                except regex.error as exc:
                    # Returned, never raised: the model supplied the pattern and is the one
                    # that has to correct it.
                    return error(GREP_NAME, f"invalid regular expression {pattern!r}: {exc}")

                # Read the limit at call time (module attribute), never captured at import.
                budget = limits.GREP_TIMEOUT_S
                deadline = time.monotonic() + budget

                matches: list[str] = []
                scanned = 0
                # Files whose search covered only the first MAX_READ_BYTES. A match past
                # that point is invisible to the scan, so reporting "no match" without
                # saying so would be a silent failure.
                truncated_files: list[str] = []
                for candidate in _grep_candidates(spec, target, glob):
                    # Checked per candidate as well as per line: traversal of a large tree and
                    # the reads themselves consume wall time the per-line check never sees.
                    if time.monotonic() >= deadline:
                        return _grep_walk_timeout(budget, matches, scanned)
                    scanned += 1
                    try:
                        # Bounded like read_file: an enormous file must not consume the whole
                        # budget (or the process's memory) inside a single unbounded read.
                        with candidate.open("rb") as handle:
                            raw = handle.read(limits.MAX_READ_BYTES)
                            # One extra byte distinguishes "exactly at the cap" from
                            # "there is more" without a second stat or a full read.
                            truncated = handle.read(1) != b""
                        text = raw.decode(errors="replace")
                    except (OSError, UnicodeDecodeError):
                        # An unreadable or undecodable file inside the tree is normal input for
                        # a whole-directory search; skipping it is correct, and the remaining
                        # files still produce results.
                        continue

                    relative = candidate.relative_to(spec.root)
                    if truncated:
                        truncated_files.append(str(relative))
                    for number, line in enumerate(text.splitlines(), start=1):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            return _grep_walk_timeout(budget, matches, scanned)
                        try:
                            # The per-call timeout is scoped to what is left of the whole-walk
                            # budget, so the sum across every line of every file cannot exceed
                            # GREP_TIMEOUT_S for the call.
                            found = compiled.search(line, timeout=remaining)
                        except TimeoutError:
                            return _grep_pattern_timeout(pattern, budget)
                        if found is None:
                            continue
                        matches.append(f"{relative}:{number}:{line}")
                        if max_results is not None and len(matches) >= max_results:
                            break
                    if max_results is not None and len(matches) >= max_results:
                        break

                lines = list(matches)
                # Named per file so the model can narrow its own search rather than
                # concluding the pattern is absent from a file it only partly saw.
                lines.extend(
                    f"[searched only the first {limits.MAX_READ_BYTES} bytes of {name}; "
                    "a match beyond that was not seen]"
                    for name in truncated_files
                )
                body = "\n".join(lines)
                return ToolResult(content=truncate(body.encode(), limits.MAX_OUTPUT_BYTES, "matches"))

            return await asyncio.to_thread(_search)

        return await guarded(GREP_NAME, run)

    return execute


#: Above this, an argument is not a long pattern — it is a malfunction. The agentic loop
#: has already seen a model emit a ~400KB tool argument from a degenerate repetition loop
#: (see ``_execute_tool_call``); that case produced malformed JSON, but the same runaway can
#: parse cleanly and land in a string field. Telling such a model to "shorten it" invites a
#: retry of the same broken output, so the advice differs past this point.
_RUNAWAY_PATTERN_CHARS = 10_000


def _oversized_pattern(pattern: str) -> ToolResult:
    """Reject a pattern over the cap, distinguishing "too long" from "malfunctioning".

    A genuinely long pattern is the model's to shorten. An argument of hundreds of
    kilobytes is not a pattern at all, and the useful instruction is to re-issue the call
    with a real one — logged at WARNING, because a runaway argument is an operator-visible
    event rather than the routine error that ``error()`` reports at INFO.
    """
    size = len(pattern)
    if size < _RUNAWAY_PATTERN_CHARS:
        return error(
            GREP_NAME,
            f"pattern is {size} characters, over the "
            f"{limits.MAX_PATTERN_CHARS}-character limit; shorten it.",
        )

    _logger.warning(
        "%s: rejected a %d-character 'pattern' — this is a runaway tool argument, "
        "not a search pattern (first 200 chars: %.200r)",
        GREP_NAME,
        size,
        pattern,
    )
    return ToolResult(
        content=(
            f"Error: the 'pattern' argument was {size} characters. That is not a search "
            "pattern — it looks like generated content placed in the wrong argument. "
            "Re-issue the call with a short regular expression in 'pattern', and use "
            "'path' or 'glob' to narrow the search."
        ),
        is_error=True,
    )


def _grep_pattern_timeout(pattern: str, budget: float) -> ToolResult:
    """The regex engine itself ran out of budget — the pattern is the problem.

    Only raised from ``compiled.search(..., timeout=...)``, i.e. genuine catastrophic
    backtracking. Telling the model to simplify its pattern is correct advice *here* and
    nowhere else; see :func:`_grep_walk_timeout` for the other cause.
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


def _grep_walk_timeout(budget: float, matches: list[str], scanned: int) -> ToolResult:
    """The tree was too large to finish — the pattern is *not* the problem.

    Reporting this as a pattern failure is what made issue #79 costly: a model told to
    simplify an already-trivial pattern retries a change that cannot help. The fix the model
    can act on is narrowing the search, so that is what this says.

    Whatever matched before the budget ran out is returned rather than discarded: a partial
    answer beats none, and the notice says it is partial.
    """
    _logger.warning(
        "%s: search of %d files exceeded the %ss budget and was abandoned", GREP_NAME, scanned, budget
    )
    notice = (
        f"[search abandoned: scanned {scanned} files before exceeding the {budget}s budget. "
        "The tree is too large, not the pattern — narrow it with 'path' or 'glob'.]"
    )
    if not matches:
        return ToolResult(content=f"Error: {notice}", is_error=True)
    # Partial results are a successful, incomplete answer — not an error.
    return ToolResult(content="\n".join([*matches, notice]))


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
