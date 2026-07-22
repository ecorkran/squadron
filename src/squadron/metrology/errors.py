"""Typed exceptions for the metrology data layer.

Three concrete errors under a common ``MetrologyError`` base let callers —
and the future MCP surface — distinguish "your input was wrong"
(identity / target) from "the store is broken" (store write). Each message
is actionable: it names the fix or the offending path, never a bare label.
"""

from __future__ import annotations


class MetrologyError(Exception):
    """Base class for all metrology-layer failures."""


class MetrologyIdentityError(MetrologyError):
    """No stable project identity is derivable.

    Raised when a repo has neither a git remote nor a recorded
    ``metrology.project_id``. The message names the one-line fix. Identity is
    never derived from a filesystem path.
    """


class MetrologyTargetError(MetrologyError):
    """A capture target could not be resolved to exactly one judge result.

    Covers a missing target file, a malformed / unparseable review file
    missing required judge fields, and target resolution that yields zero or
    multiple matches. The message names the resolved path or the candidate
    types.
    """


class MetrologyStoreError(MetrologyError):
    """The metrology store could not be written.

    Wraps the underlying ``OSError`` (dir not creatable, path not writable,
    rename failure). Distinct from identity/target errors so callers can tell
    a broken store from bad input.
    """
