"""One test node's result (slice 421 D6), shared with the grade records (slice 425 D2).

Lives in ``metrology`` because stored grade records embed ``NodeResult`` and the metrology
package must not import from ``squadron.benchmark``. ``benchmark.adapter`` re-exports all
three names, so existing ``from squadron.benchmark.adapter import NodeResult`` imports keep
working.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class FailureKind(StrEnum):
    COLLECTION_ERROR = "collection_error"
    MISSING_SYMBOL = "missing_symbol"
    ASSERTION_FAILURE = "assertion_failure"
    PROJECT_EXCEPTION = "project_exception"
    OTHER_EXCEPTION = "other_exception"


class NodeOutcome(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    SKIPPED = "skipped"
    XFAILED = "xfailed"
    XPASSED = "xpassed"
    NOT_RUN = "not_run"


@dataclass(frozen=True)
class NodeResult:
    node_id: str
    outcome: NodeOutcome
    failure_kind: FailureKind | None = None
    phase: str | None = None
    exception_type: str | None = None
