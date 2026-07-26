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


class AuditBlockMissingError(MetrologyError):
    """The audit output carried no machine-readable findings block.

    Distinct from ``AuditBlockMalformedError`` because the two mean
    different things about the run: *missing* says the model never emitted
    the block (it ignored the contract, or the run was truncated before
    reaching it), while *malformed* says it tried and produced something
    unparseable. The harness logs them differently so a systematic contract
    failure is distinguishable from sporadic YAML damage.
    """


class AuditBlockMalformedError(MetrologyError):
    """The findings block was present but could not be parsed.

    Raised for unparseable YAML, a non-mapping document, or a missing
    ``findings`` list. Fails loudly at the boundary rather than
    half-parsing — a partially-read block would under-count findings and
    silently bias the measurement.
    """
