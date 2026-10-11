"""Read task files and run the merge-step gate over them (slice 933).

The one entry point the CLI and pipeline tasks reviews share, so the two paths
cannot drift. Reads are small, local and synchronous by design: task files are a
few hundred lines, well inside the sync budget, like the ``missing_input_files``
stat check they sit beside.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from squadron.review.models import ReviewResult
from squadron.review.task_gate import INPUT_KEY, merge_gate_results, scan_merge_steps


class TaskFileReadError(Exception):
    """A task file could not be read or decoded; the gate never skips a file."""


def _read_task_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise TaskFileReadError(f"Cannot read task file {path} for the merge-step gate: {exc}") from exc


def gate_task_files(part_inputs: Sequence[Mapping[str, str]]) -> dict[str, ReviewResult]:
    """Scan every part's task file; return FAIL results for the offending parts.

    Empty when every part is clean.

    Raises:
        TaskFileReadError: a part's file could not be read or decoded.
    """
    scans = [(inputs, scan_merge_steps(_read_task_file(inputs[INPUT_KEY]))) for inputs in part_inputs]
    return merge_gate_results(scans)
