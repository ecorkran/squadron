"""The named failure every project-rules problem raises (slice 935 failure-mode table)."""

from __future__ import annotations


class ProjectRulesError(RuntimeError):
    """An expected project-rules failure: the message says what to fix, so no traceback."""
