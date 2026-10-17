"""A replay's first draft and final text, read from its sandbox (slice 177 D4).

The first draft is the artifact as the sandbox commit that first added it holds it; the
final text is the working-tree file after the revise loop. Either is ``None`` when the
sandbox has no such artifact: a failed run, or a producer that never committed it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from squadron.metrology.replay_models import ReplayPhase
from squadron.replay.start_point import StartPointError, artifact_files, resolve_start_point
from squadron.review.git_utils import run_git
from squadron.stats.git_history import GitHistory, GitHistoryError

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Drafts:
    first: str | None
    final: str | None


def read_drafts(sandbox: Path, phase: ReplayPhase, index: int) -> Drafts:
    """Both texts of slice ``index``'s artifact in ``sandbox``; a missing one is ``None``."""
    return Drafts(first=_first_draft(sandbox, phase, index), final=_final_text(sandbox, phase, index))


def _first_draft(sandbox: Path, phase: ReplayPhase, index: int) -> str | None:
    history = GitHistory(sandbox, run=run_git)
    try:
        history.load()
        return resolve_start_point(phase, index, history).original_first_draft
    except (StartPointError, GitHistoryError) as exc:
        _logger.warning("no first draft for slice %d %s in %s: %s", index, phase.value, sandbox, exc)
        return None


def _final_text(sandbox: Path, phase: ReplayPhase, index: int) -> str | None:
    files = artifact_files(phase, index, sandbox)
    if not files:
        return None
    try:
        return "\n".join(path.read_text(encoding="utf-8") for path in files)
    except (OSError, UnicodeDecodeError) as exc:
        # A replay whose final text is unreadable is recorded without it; the set goes on.
        _logger.warning(
            "final text unreadable for slice %d %s in %s: %s", index, phase.value, sandbox, exc
        )
        return None
