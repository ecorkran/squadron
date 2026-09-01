"""Single home for tool execution limits.

Every limit enforced by a built-in tool is defined here and nowhere else. Tool
implementations reference these constants by module attribute (``limits.MAX_READ_BYTES``)
rather than importing the values, so tests can monkeypatch them and the executor sees the
patched value at call time.

Making these configurable is slice 266's job — this module deliberately has no config
plumbing.
"""

from __future__ import annotations

# Maximum number of bytes ``read_file`` returns before truncating with a visible marker.
MAX_READ_BYTES = 256_000

# Maximum number of bytes of each captured stream (stdout, stderr) ``bash`` returns.
MAX_OUTPUT_BYTES = 64_000

# Wall-clock seconds a ``bash`` command may run before its process group is killed.
BASH_TIMEOUT_S = 120.0

# Wall-clock seconds the ``grep`` tool's regex matching may consume across an entire
# walk before the search is abandoned. Bounds catastrophic backtracking on
# model-supplied patterns; the ``regex`` package enforces it at the engine level.
GREP_TIMEOUT_S = 5.0
