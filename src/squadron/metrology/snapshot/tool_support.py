"""Helpers shared by the tool-backed adapters (ruff, pyright, ESLint).

An unmeasurable metric is data, not an exception: these build the absent
``Measurement`` and log the failure at WARNING with the tool, command and stderr head,
so every absence is observable.
"""

from __future__ import annotations

import logging
from pathlib import Path

from squadron.metrology.snapshot.runner import stderr_head
from squadron.metrology.snapshot_models import (
    AbsenceReason,
    Measurement,
    SnapshotMetric,
    SourceLanguage,
)

_logger = logging.getLogger(__name__)


def absent(
    language: SourceLanguage, metric: SnapshotMetric, reason: AbsenceReason, detail: str
) -> Measurement:
    """An absent measurement with its reason and detail."""
    return Measurement(metric=metric, language=language, absent=reason, absent_detail=detail)


def tool_missing(
    language: SourceLanguage, metric: SnapshotMetric, tool: str, looked_in: str
) -> Measurement:
    """The tool isn't installed where it's allowed to come from."""
    detail = f"{tool} not found in {looked_in}"
    _logger.warning("%s: %s", metric.value, detail)
    return absent(language, metric, AbsenceReason.TOOL_MISSING, detail)


def tool_failed(
    language: SourceLanguage,
    metric: SnapshotMetric,
    detail: str,
    *,
    command: str,
    stderr: str = "",
) -> Measurement:
    """The tool ran (or was meant to) and gave no usable answer. Logged at WARNING."""
    _logger.warning(
        "%s: %s (command: %s; stderr: %s)", metric.value, detail, command, stderr_head(stderr)
    )
    return absent(language, metric, AbsenceReason.TOOL_FAILED, detail)


def repo_relative(filename: str, repo_root: Path) -> str | None:
    """A tool-reported path as a repo-relative POSIX path; None when outside the repo."""
    path = Path(filename)
    for root in (repo_root, repo_root.resolve()):
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            continue
    return None
