"""Parse the judge's per-finding status lines.

The judge is instructed to emit ``<finding-id>: <status>`` and nothing else,
but real model output arrives with prose around it, bullet markers, and case
variation. Parsing anchors on the shape rather than the layout: a regex that
silently fails on valid output would show up as a fabricated ``disputed``,
which is a fail-closed but noisy lie.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from squadron.pipeline.actions.findings_addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
)

_logger = logging.getLogger(__name__)

#: ``<finding-id>: <status>[ successor=<fresh-finding-id>]`` anywhere on a
#: line, tolerating list markers, surrounding prose, and mixed case.
_STATUS_LINE = re.compile(
    r"(?P<id>[A-Za-z][\w.\-]*)\s*[:=]\s*(?P<status>[A-Za-z_-]+)"
    r"(?:\s*[,;]?\s*successor\s*[:=]\s*(?P<successor>[A-Za-z][\w.\-]*))?",
)


@dataclass(frozen=True)
class JudgeStatus:
    """One status the judge claimed, before any verification."""

    finding_id: str
    status: FindingStatus
    successor_id: str | None = None


def parse_status_lines(raw_output: str) -> dict[str, JudgeStatus]:
    """Read every recognizable status line out of *raw_output*.

    A line naming a status outside the closed set is kept as ``DISPUTED``
    rather than dropped: the judge said something about that finding, and what
    it said was not defensible. Lines that match no finding id the caller cares
    about are filtered later, by the caller.
    """
    statuses: dict[str, JudgeStatus] = {}
    for line in raw_output.splitlines():
        match = _STATUS_LINE.search(line)
        if match is None:
            continue
        token = match.group("status").strip().lower()
        try:
            status = FindingStatus(token)
        except ValueError:
            _logger.warning(
                "findings-addressed: judge emitted unknown status %r for %r; treating as disputed",
                token,
                match.group("id"),
            )
            status = FindingStatus.DISPUTED
        statuses[match.group("id")] = JudgeStatus(
            finding_id=match.group("id"),
            status=status,
            successor_id=match.group("successor"),
        )
    return statuses


def is_parse_failure(residue: list[FindingRecord], statuses: dict[str, JudgeStatus]) -> bool:
    """True when the judge's response yielded nothing usable at all.

    Distinct from a judge that answered about some findings and not others:
    that is per-finding uncertainty (``DISPUTED``), while this is a response
    that could not be read, which fails the leg closed as UNKNOWN.
    """
    return bool(residue) and not any(record.finding_id in statuses for record in residue)


def statuses_to_outcomes(
    residue: list[FindingRecord],
    statuses: dict[str, JudgeStatus],
) -> list[FindingOutcome]:
    """Map the judge's claims onto the residue, one outcome per finding.

    A residue finding the judge said nothing about is ``DISPUTED`` — never
    dropped, and never defaulted to addressed.
    """
    outcomes: list[FindingOutcome] = []
    for record in residue:
        claimed = statuses.get(record.finding_id)
        if claimed is None:
            _logger.warning(
                "findings-addressed: judge returned no status for %r; treating as disputed",
                record.finding_id,
            )
            outcomes.append(
                FindingOutcome(
                    finding_id=record.finding_id,
                    status=FindingStatus.DISPUTED,
                    screen=SettlingScreen.JUDGE,
                    note="judge returned no status for this finding",
                )
            )
            continue
        outcomes.append(
            FindingOutcome(
                finding_id=record.finding_id,
                status=claimed.status,
                screen=SettlingScreen.JUDGE,
                successor_id=claimed.successor_id,
            )
        )
    return outcomes
