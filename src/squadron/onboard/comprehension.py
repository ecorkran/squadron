"""Finding the codebase-comprehension document (slice 440 D3).

The analysis skill writes ``{index}-analysis.codebase-comprehension.md``; onboard
treats the highest index as the current one and stores no other state.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from squadron.integrations.context_forge import DOCS_ROOT

#: Where the analysis skill writes, relative to the project root.
ANALYSIS_DIR = f"{DOCS_ROOT}/user/analysis"
#: What follows the index in the comprehension document's file name.
COMPREHENSION_SUFFIX = "-analysis.codebase-comprehension.md"

_INDEX_PATTERN = re.compile(r"^(\d+)")
_logger = logging.getLogger(__name__)


def newest_comprehension(root: Path) -> Path | None:
    """The comprehension doc under *root* with the highest leading integer index.

    Files without a leading integer are skipped with a WARNING naming them.
    Returns ``None`` when there is no analysis directory or no matching file.
    """
    analysis_dir = root / ANALYSIS_DIR
    if not analysis_dir.is_dir():
        return None
    best: tuple[int, Path] | None = None
    for candidate in analysis_dir.glob(f"*{COMPREHENSION_SUFFIX}"):
        match = _INDEX_PATTERN.match(candidate.name)
        if match is None:
            _logger.warning("Skipping comprehension doc with no leading index: %s", candidate)
            continue
        index = int(match.group(1))
        if best is None or index > best[0]:
            best = (index, candidate)
    return None if best is None else best[1]
