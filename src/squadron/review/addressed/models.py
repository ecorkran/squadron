"""Vocabulary of the findings-addressed gate policy.

The status set, the settling-screen names, and how a finding is read out of a
review's ``ActionResult`` are defined here, once, and referenced everywhere
else in the policy.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from squadron.review.models import Severity

if TYPE_CHECKING:
    # Annotation only. Importing ``ActionResult`` at runtime would make the
    # review package depend on the pipeline package, inverting the established
    # direction (pipeline consumes review) this module was moved here to keep.
    from squadron.pipeline.models import ActionResult

_logger = logging.getLogger(__name__)

# CONCERN+ — the severities this policy holds a round accountable for.
CONCERN_PLUS_SEVERITIES: frozenset[str] = frozenset({Severity.CONCERN, Severity.FAIL})


class FindingStatus(StrEnum):
    """What became of one prior finding. Closed set — defined once, here.

    ``DISPUTED`` exists so a judge under uncertainty has an honest answer:
    guessing between addressed and unaddressed is the failure mode it prevents.
    """

    ADDRESSED = "addressed"
    UNADDRESSED = "unaddressed"
    MOVED = "moved"
    DISPUTED = "disputed"


class SettlingScreen(StrEnum):
    """Which layer settled a finding — the audit field on gate metadata."""

    NO_PRIOR_ROUND = "no_prior_round"
    BYTE_IDENTICAL = "byte_identical"
    EXACT_MATCH = "exact_match"
    JUDGE = "judge"


@dataclass(frozen=True)
class FindingRecord:
    """One finding as it arrives from a review ActionResult.

    ``malformed`` marks a finding whose dict was missing fields this policy
    needs. Such a finding is never dropped and never settled mechanically — it
    is unsettleable residue, which fails closed.
    """

    finding_id: str
    severity: str
    category: str
    location: str
    summary: str
    malformed: bool = False


@dataclass(frozen=True)
class FindingOutcome:
    """The disposition of one prior finding, and which screen settled it."""

    finding_id: str
    status: FindingStatus
    screen: SettlingScreen
    successor_id: str | None = None
    note: str | None = None


def _as_str(value: object) -> str | None:
    """Return *value* as a non-empty string, or None if it is neither."""
    if isinstance(value, str) and value:
        return value
    return None


def _as_severity(value: object) -> str | None:
    """Return *value* normalized to the case ``Severity`` uses.

    ``ReviewResult.structured_findings`` lowercases severities on the way out
    (``f.severity.value.lower()``) while ``Severity`` itself is uppercase.
    Normalizing here, at the boundary, keeps ``CONCERN_PLUS_SEVERITIES`` tied
    to the enum: lowercasing the constant instead would let it drift silently
    the next time a producer changes case.
    """
    severity = _as_str(value)
    return severity.upper() if severity is not None else None


def read_findings(result: ActionResult | None) -> list[FindingRecord]:
    """Read every finding out of *result* as a FindingRecord.

    Findings arrive as plain dicts (``[sf.__dict__ for sf in ...]`` in the
    review action), so every field is read defensively. A finding missing a
    field this policy needs is logged at WARNING and returned ``malformed``
    rather than dropped — a silently discarded finding is a silently passed
    round.
    """
    if result is None:
        return []

    records: list[FindingRecord] = []
    for index, raw in enumerate(result.findings):
        if not isinstance(raw, dict):
            _logger.warning(
                "findings-addressed: finding %d is %s, not a mapping; treating as residue",
                index,
                type(raw).__name__,
            )
            records.append(
                FindingRecord(
                    finding_id=f"finding-{index}",
                    severity="",
                    category="",
                    location="",
                    summary="",
                    malformed=True,
                )
            )
            continue

        finding: dict[str, object] = {str(key): value for key, value in raw.items()}  # pyright: ignore[reportUnknownVariableType, reportUnknownArgumentType]
        finding_id = _as_str(finding.get("id"))
        severity = _as_severity(finding.get("severity"))
        category = _as_str(finding.get("category"))
        location = _as_str(finding.get("location"))
        summary = _as_str(finding.get("summary"))

        missing = [
            name
            for name, value in (
                ("id", finding_id),
                ("severity", severity),
                ("category", category),
                ("location", location),
            )
            if value is None
        ]
        if missing:
            _logger.warning(
                "findings-addressed: finding %r is missing %s; treating as residue",
                finding_id or f"finding-{index}",
                ", ".join(missing),
            )

        records.append(
            FindingRecord(
                finding_id=finding_id or f"finding-{index}",
                severity=severity or "",
                category=category or "",
                location=location or "",
                summary=summary or "",
                malformed=bool(missing),
            )
        )
    return records


def concern_plus(records: list[FindingRecord]) -> list[FindingRecord]:
    """Return the CONCERN+ subset — the findings a round is accountable for.

    A malformed record is kept regardless of its severity: its severity is
    exactly what could not be read, so excluding it would be a silent pass.
    """
    return [
        record for record in records if record.malformed or record.severity in CONCERN_PLUS_SEVERITIES
    ]
