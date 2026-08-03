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


def _unreadable_record(index: int) -> FindingRecord:
    """A record standing in for an entry that was not a mapping at all."""
    return FindingRecord(
        finding_id=f"finding-{index}",
        severity="",
        category="",
        location="",
        summary="",
        malformed=True,
    )


def _record_from_mapping(raw: dict[object, object], index: int) -> FindingRecord:
    """Read one finding mapping into a FindingRecord, defensively.

    Every field is read through ``_as_str``/``_as_severity`` so both producer
    shapes normalize identically. A finding missing a field this policy needs
    is logged at WARNING and returned ``malformed`` rather than dropped — a
    silently discarded finding is a silently passed round.
    """
    finding: dict[str, object] = {str(key): value for key, value in raw.items()}
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

    return FindingRecord(
        finding_id=finding_id or f"finding-{index}",
        severity=severity or "",
        category=category or "",
        location=location or "",
        summary=summary or "",
        malformed=bool(missing),
    )


def read_findings(result: ActionResult | None) -> list[FindingRecord]:
    """Read every finding out of *result* as a FindingRecord.

    Findings arrive as plain dicts (``[sf.__dict__ for sf in ...]`` in the
    review action), so every field is read defensively.
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
            records.append(_unreadable_record(index))
            continue
        records.append(_record_from_mapping(raw, index))  # pyright: ignore[reportUnknownArgumentType]
    return records


def records_from_frontmatter(findings: list[object]) -> list[FindingRecord]:
    """Read findings out of a *review file's* YAML frontmatter.

    This is a second reader, not a variant of :func:`read_findings`. The two
    consume different producer shapes: ``read_findings`` reads
    ``ActionResult.findings`` (``ReviewResult.structured_findings`` dicts,
    whose ``severity`` is already lowercased on the way out), while this one
    reads the ``findings:`` block ``format_review_markdown`` writes into the
    review file (``id``, ``severity``, ``category``, ``summary``, and
    ``location`` only when the finding carries one).

    The shapes are close but not identical, and 305's F002 lesson — a parser
    must be exercised against the shape its real producer emits — is the
    reason both readers exist rather than one lenient reader spanning both.
    Normalization is shared: both route through ``_as_severity``, so
    ``CONCERN_PLUS_SEVERITIES`` stays tied to the ``Severity`` enum for either
    source.

    A finding missing a required field is kept as malformed residue, never
    dropped — the same rule ``read_findings`` applies, not a new one.
    """
    records: list[FindingRecord] = []
    for index, raw in enumerate(findings):
        if not isinstance(raw, dict):
            _logger.warning(
                "findings-addressed: frontmatter finding %d is %s, not a mapping; treating as residue",
                index,
                type(raw).__name__,
            )
            records.append(_unreadable_record(index))
            continue
        records.append(_record_from_mapping(raw, index))  # pyright: ignore[reportUnknownArgumentType]
    return records


def concern_plus(records: list[FindingRecord]) -> list[FindingRecord]:
    """Return the CONCERN+ subset — the findings a round is accountable for.

    A malformed record is kept regardless of its severity: its severity is
    exactly what could not be read, so excluding it would be a silent pass.
    """
    return [
        record for record in records if record.malformed or record.severity in CONCERN_PLUS_SEVERITIES
    ]
