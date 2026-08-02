"""Verify what the judge claimed, then derive the leg verdict from statuses.

The judge is consulted, not obeyed: a claim it cannot support is downgraded to
``DISPUTED`` here, and the verdict is computed from the surviving statuses by
rule. Whatever conclusion the judge stated is never read.
"""

from __future__ import annotations

import logging

from squadron.pipeline.actions.findings_addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
)
from squadron.pipeline.actions.findings_addressed.screens import RoundDiff
from squadron.review.models import Verdict
from squadron.review.parsers import UNVERIFIED_LOCATION

_logger = logging.getLogger(__name__)


def _location_path(location: str) -> str:
    """The path portion of a finding location (``path:line`` → ``path``)."""
    return location.split(":", 1)[0].split("#", 1)[0].strip()


def _diff_touches(location: str, changed_paths: frozenset[str]) -> bool:
    """Whether the round's diff touched the file a finding cites.

    Compared leniently by suffix: git reports repo-relative paths while a
    finding may cite a path relative to a subdirectory. A false "untouched"
    would manufacture a DISPUTED out of honest work.
    """
    path = _location_path(location)
    if not path:
        return False
    return any(
        changed == path or changed.endswith(f"/{path}") or path.endswith(f"/{changed}")
        for changed in changed_paths
    )


def verify_outcomes(
    outcomes: list[FindingOutcome],
    *,
    residue: list[FindingRecord],
    fresh_findings: list[FindingRecord],
    diff: RoundDiff,
) -> list[FindingOutcome]:
    """Downgrade unsupportable judge claims to DISPUTED, recording what was claimed.

    Two checks, both fail-closed:

    - ``MOVED`` must name a successor that exists in the fresh findings. An
      unverifiable relocation claim is uncertainty, not a pass.
    - ``ADDRESSED`` over a file the round never touched contradicts the
      deterministic evidence. A finding located ``unverified`` cannot be
      contradicted this way and is left as the judge reported it.
    """
    fresh_ids = {record.finding_id for record in fresh_findings}
    locations = {record.finding_id: record.location for record in residue}

    verified: list[FindingOutcome] = []
    for outcome in outcomes:
        if outcome.status == FindingStatus.MOVED and (
            outcome.successor_id is None or outcome.successor_id not in fresh_ids
        ):
            _logger.warning(
                "findings-addressed: %r claimed moved to %r, which is not in the fresh "
                "findings; downgrading to disputed",
                outcome.finding_id,
                outcome.successor_id,
            )
            verified.append(
                FindingOutcome(
                    finding_id=outcome.finding_id,
                    status=FindingStatus.DISPUTED,
                    screen=outcome.screen,
                    successor_id=outcome.successor_id,
                    note=f"claimed {FindingStatus.MOVED} with unverifiable successor",
                )
            )
            continue

        location = locations.get(outcome.finding_id, "")
        if (
            outcome.status == FindingStatus.ADDRESSED
            and location
            and location != UNVERIFIED_LOCATION
            and not _diff_touches(location, diff.changed_paths)
        ):
            _logger.warning(
                "findings-addressed: %r claimed addressed but the round did not touch %r; "
                "downgrading to disputed",
                outcome.finding_id,
                location,
            )
            verified.append(
                FindingOutcome(
                    finding_id=outcome.finding_id,
                    status=FindingStatus.DISPUTED,
                    screen=outcome.screen,
                    note=f"claimed {FindingStatus.ADDRESSED} over untouched {location}",
                )
            )
            continue

        verified.append(outcome)
    return verified


def derive_addressed_verdict(
    outcomes: list[FindingOutcome],
    *,
    judge_failed: bool = False,
) -> str:
    """Compute the addressed leg from the per-finding statuses.

    UNKNOWN is evaluated before FAIL so a fail-closed condition dominates: a
    check that could not run must not be reported as a check that ran and
    failed. ``MOVED`` reaching here is successor-verified by construction —
    ``verify_outcomes`` downgrades the rest.
    """
    if judge_failed:
        return Verdict.UNKNOWN
    statuses = {outcome.status for outcome in outcomes}
    if FindingStatus.DISPUTED in statuses:
        return Verdict.UNKNOWN
    if FindingStatus.UNADDRESSED in statuses:
        return Verdict.FAIL
    return Verdict.PASS
