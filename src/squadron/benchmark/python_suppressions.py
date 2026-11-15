"""Counting suppressions a producer's diff added (slice 425 D6)."""

from __future__ import annotations

import re

from squadron.benchmark.python_fairness import PythonFixCaseAdapter
from squadron.metrology.grade_models import SuppressionCounts

# Lenient about spacing, case and any rule list after the marker: it is the marker that counts.
_NOQA = re.compile(r"#\s*noqa\b", re.IGNORECASE)
_TYPE_IGNORE = re.compile(r"#\s*(?:type|pyright)\s*:\s*ignore\b", re.IGNORECASE)
_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@")
_NEW_FILE_HEADER = "+++ "
_NO_FILE = "/dev/null"
_DIFF_START = "diff --git "


def _new_path(header: str) -> str | None:
    """The path of a ``+++ b/<path>`` header, ``None`` for a deleted file."""
    path = header.removeprefix(_NEW_FILE_HEADER).split("\t")[0].strip().strip('"')
    if path == _NO_FILE:
        return None
    return path.removeprefix("b/")


def count_suppressions(diff: bytes) -> SuppressionCounts:
    """Suppressions added by *diff*, by file side (D6).

    Only added lines inside a hunk count, so header lines (a path that happens to contain
    ``# noqa``), context lines and removed lines never do. ``# pyright: ignore`` counts as a
    type ignore. A file is test-side by 422's default rules (the diff carries no pyproject).
    """
    classifier = PythonFixCaseAdapter()
    counts = {
        "noqa_source": 0,
        "noqa_test": 0,
        "type_ignore_source": 0,
        "type_ignore_test": 0,
    }
    path: str | None = None
    old_left = new_left = 0
    for line in diff.decode("utf-8", errors="replace").split("\n"):
        if old_left > 0 or new_left > 0:
            marker = line[:1]
            if marker == "+":
                new_left -= 1
                if path is not None:
                    side = "test" if classifier.is_test_side(None, path) else "source"
                    counts[f"noqa_{side}"] += bool(_NOQA.search(line))
                    counts[f"type_ignore_{side}"] += bool(_TYPE_IGNORE.search(line))
            elif marker == "-":
                old_left -= 1
            elif marker == " " or line == "":
                old_left -= 1
                new_left -= 1
            continue
        if line.startswith(_DIFF_START):
            path = None
        elif line.startswith(_NEW_FILE_HEADER):
            path = _new_path(line)
        elif hunk := _HUNK_HEADER.match(line):
            old_left = int(hunk.group(1)) if hunk.group(1) is not None else 1
            new_left = int(hunk.group(2)) if hunk.group(2) is not None else 1
    return SuppressionCounts(**counts)
