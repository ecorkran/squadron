"""Why an action failed, as a value rather than error text (slice 177 D4).

Stamped in ``ActionResult.metadata`` where the failure is decided, so a reader of run
state (the replay outcome reader) classifies failures without matching error messages.
An action that fails for any other reason carries no kind.
"""

from __future__ import annotations

from enum import StrEnum

#: ``ActionResult.metadata`` key holding a ``FailureKind`` value.
FAILURE_KIND_KEY = "failure_kind"


class FailureKind(StrEnum):
    PROVIDER_ERROR = "provider_error"  # a dispatch's provider raised
    STALL = "stall"  # a dispatch produced no output within the stall bound (slice 174)
    ARTIFACT_MISSING = "artifact_missing"  # a phase dispatch wrote no artifact (slice 909/945)
