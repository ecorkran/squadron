"""Single home for tool execution limits.

Every limit enforced by a built-in tool is defined here and nowhere else. Tool
implementations reference these constants by module attribute (``limits.MAX_READ_BYTES``)
rather than importing the values, so tests can monkeypatch them and the executor sees the
patched value at call time.

Slice 266 considered making these configurable and decided against it (design D4): they
stay module attributes with no config keys until someone actually needs to tune one. A
config surface for values nobody has had to change would be plumbing maintained for its
own sake, and it would split each limit's definition across two places.

The decision is settled, not deferred. If a limit does need tuning, the constraints any
config surface must preserve are recorded in
https://github.com/ecorkran/squadron/issues/76 — chiefly that a constant must resolve
*from* config rather than sit beside it, or this module stops being one home for a value.
"""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)

# Maximum number of bytes ``read_file`` returns before truncating with a visible marker.
MAX_READ_BYTES = 256_000

# Maximum number of bytes of each captured stream (stdout, stderr) ``bash`` returns.
MAX_OUTPUT_BYTES = 64_000

# Wall-clock seconds a ``bash`` command may run before its process group is killed.
BASH_TIMEOUT_S = 120.0

# Directory names the walking tools prune by default. These hold dependencies, VCS
# internals, and build output — not the code a model is asked about — and they dominate a
# real tree: in this repo ``.venv`` alone is 21,402 of 29,373 entries, and reading it
# exhausts the whole ``grep`` budget before any project file is reached (issue #79).
#
# Pruned at the directory level during the walk, so their contents are never stat-ed or
# opened. Matched by exact directory name at any depth. A caller that genuinely wants to
# search inside one names it in ``path`` — the prune applies to descent, not to an
# explicitly requested root.
SKIP_DIRECTORIES = frozenset(
    {
        ".bzr",
        ".git",
        ".hg",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".svn",
        ".tox",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "node_modules",
        "venv",
    }
)

# Maximum directory entries ``list_files`` will walk. Bounds the *work*: without it a wide
# tree is fully materialized by ``sorted()`` before the byte-level output cap ever applies,
# so a large enough tree costs the full walk no matter how little is returned. Distinct from
# MAX_OUTPUT_BYTES, which bounds the rendered listing; both apply.
MAX_LIST_ENTRIES = 10_000

# Headroom the per-result cap keeps above the largest result a well-behaved tool can
# return. Every built-in tool bounds its own output and appends a marker saying so, so the
# agent-side cap is a backstop for a tool that does not — it must sit *above* those bounds.
#
# Two rounds of live failures came from getting this wrong. A cap of 20_000 (5% of the old
# history budget) cut grep's 64_000 output mid-line, replacing its "showing first N" marker;
# a review went from 45 tool calls to 1 and returned UNKNOWN. Raising the floor to
# MAX_OUTPUT_BYTES * 1.5 fixed grep but ignored read_file, which returns up to
# MAX_READ_BYTES — so a 167_573-character read was still re-truncated at 96_000. The floor
# is therefore derived from *every* tool bound, not whichever one prompted the last fix.
TOOL_RESULT_HEADROOM = 1.5


def min_tool_result_chars() -> int:
    """Return the smallest per-result cap that cannot re-truncate a tool's own output.

    Derived from the largest bound any built-in tool applies to its own result, so adding a
    tool with a larger bound raises this automatically rather than silently under-sizing the
    cap. Read at call time so tests can monkeypatch either input.
    """
    return int(max(MAX_READ_BYTES, MAX_OUTPUT_BYTES) * TOOL_RESULT_HEADROOM)


def resolve_tool_result_cap(configured: int) -> int:
    """Clamp a configured per-result cap up to the floor that keeps it a backstop.

    ``agent.max_tool_result_chars`` is operator-tunable (its default is derived from the
    floor), but a value below what a tool can itself return would mangle correct results
    rather than bound runaway ones, so it is raised rather than honored.
    """
    floor = min_tool_result_chars()
    if configured < floor:
        _logger.warning(
            "agent.max_tool_result_chars is %d, below the %d a tool can itself return; "
            "using %d so correctly-truncated results are not re-truncated",
            configured,
            floor,
            floor,
        )
        return floor
    return configured


# Maximum length of a model-supplied ``grep`` pattern. Checked before compilation: the
# point is to never hand an unbounded pattern to the regex engine at all, since compilation
# itself is where a pathological pattern does its damage.
MAX_PATTERN_CHARS = 1_000

# Wall-clock seconds the ``grep`` tool's regex matching may consume across an entire
# walk before the search is abandoned. Bounds catastrophic backtracking on
# model-supplied patterns; the ``regex`` package enforces it at the engine level.
GREP_TIMEOUT_S = 5.0

# Wall-clock seconds ``squadron.frontmatter-gate`` waits for ``cf validate frontmatter``
# before killing its process group (slice 919 Part 3, #98, D14). Set well below
# BASH_TIMEOUT_S: validating a handful of staged files is fast, and a gate blocking a
# commit is more disruptive than a long-running interactive command, so it gets a much
# tighter bound rather than inheriting the general-purpose one.
FRONTMATTER_GATE_TIMEOUT_S = 20.0
