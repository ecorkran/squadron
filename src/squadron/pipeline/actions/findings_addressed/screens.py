"""Loop-specific screens for the findings-addressed gate policy.

Screens run before any model call and cost zero tokens. Each one settles the
findings it can prove something about; whatever it cannot settle becomes
residue for the judge. No screen ever settles a finding as ``addressed`` —
that direction fails open, and the screens are the fail-closed layer.

What lives here needs the loop's context: an iteration number (screen 0) or a
fresh review to compare against (screen 2). The measurement itself and the
screens that read it alone live in ``review/addressed/screens.py`` — see the
dependency-direction note there (design review F002).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from squadron.review.addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
)
from squadron.review.addressed.screens import (
    EMPTY_ROUND_NOTE,
    RoundDiff,
    ScreenResult,
    compute_diff_since,
    screen_byte_identical,
    screen_git_failure,
)
from squadron.review.models import Verdict
from squadron.review.parsers import UNVERIFIED_LOCATION

_logger = logging.getLogger(__name__)

#: The gate measures round N as the working tree against ``HEAD``: the round is
#: uncommitted at gate time, so ``HEAD`` is the prior round's commit.
_ROUND_DIFF_BASE = "HEAD"


def compute_round_diff(*, cwd: str, paths: Sequence[str] = ()) -> RoundDiff:
    """Measure round N's changes as the working tree against ``HEAD``."""
    return compute_diff_since(_ROUND_DIFF_BASE, cwd=cwd, paths=paths)


def screen_no_prior_round(
    *,
    pipeline_name: str,
    step_name: str,
    iteration: int,
    review_from: str,
) -> ScreenResult:
    """Screen 0 — there is no prior round's review to hold this one accountable to.

    Two states reach here and they are not the same state. Iteration 0 or 1 is
    a legitimate first round: annotated PASS, never UNKNOWN, since UNKNOWN would
    fail every first round closed and silence would hide that the check did not
    run. A *later* iteration with no prior result means the prior round's review
    failed, was skipped, or emitted no verdict — the check could not run, which
    is the module's UNKNOWN condition. Deciding screen is left unset there, as
    on the git-failure path: nothing was settled.
    """
    if iteration > 1:
        _logger.warning(
            "findings-addressed: iteration %d has no prior-round result for '%s' "
            "(pipeline=%s step=%s) — the prior round produced no verdict; "
            "addressed leg UNKNOWN",
            iteration,
            review_from,
            pipeline_name,
            step_name,
        )
        return ScreenResult(outcomes=[], residue=[], leg_verdict=Verdict.UNKNOWN)

    _logger.info(
        "findings-addressed: no prior round for pipeline=%s step=%s iteration=%d; "
        "addressed leg PASS by annotation",
        pipeline_name,
        step_name,
        iteration,
    )
    return ScreenResult(
        outcomes=[],
        residue=[],
        leg_verdict=Verdict.PASS,
        deciding_screen=SettlingScreen.NO_PRIOR_ROUND,
    )


def run_deterministic_screens(
    *,
    prior_findings: list[FindingRecord],
    fresh_findings: list[FindingRecord],
    diff: RoundDiff,
) -> ScreenResult:
    """Run screens 1–2 over the prior round's CONCERN+ findings.

    Screen 0 (no prior round) precedes this: it is decided before any git call,
    by the caller, since there is nothing to measure.
    """
    if not prior_findings:
        _logger.info("findings-addressed: prior round raised no CONCERN+ findings; addressed leg PASS")
        return ScreenResult(outcomes=[], residue=[], leg_verdict=Verdict.PASS)

    if diff.failed_command is not None:
        return screen_git_failure(diff)

    if diff.is_empty:
        return screen_byte_identical(prior_findings, note=EMPTY_ROUND_NOTE)

    return screen_exact_match(prior_findings, fresh_findings)


def _match_key(record: FindingRecord) -> tuple[str, str] | None:
    """The (location, category) key a finding matches on, or None if unmatchable.

    A finding located ``unverified`` has no key. 904 normalizes every unknown
    location to that one token, so two unrelated findings sharing a category
    would exact-match on it — a false ``unaddressed`` that traps the loop until
    exhaustion. Those findings route to the judge instead.
    """
    if record.malformed:
        return None
    if not record.location or record.location == UNVERIFIED_LOCATION:
        return None
    if not record.category:
        return None
    return (record.location, record.category)


def screen_exact_match(
    prior_findings: list[FindingRecord],
    fresh_findings: list[FindingRecord],
) -> ScreenResult:
    """Screen 2 — the reviewer re-found it, so no judgment is needed.

    Exact ``location`` + ``category`` only. 911's clean-regeneration contract
    moves line numbers wholesale between rounds, so fuzzy matching would
    manufacture false resolutions — and a false ``addressed`` fails open.
    Anything unmatched is residue, never ``addressed``.
    """
    fresh_keys = {key for record in fresh_findings if (key := _match_key(record)) is not None}

    outcomes: list[FindingOutcome] = []
    residue: list[FindingRecord] = []
    for record in prior_findings:
        key = _match_key(record)
        if key is not None and key in fresh_keys:
            outcomes.append(
                FindingOutcome(
                    finding_id=record.finding_id,
                    status=FindingStatus.UNADDRESSED,
                    screen=SettlingScreen.EXACT_MATCH,
                    note=f"re-found at {record.location} ({record.category})",
                )
            )
        else:
            residue.append(record)
    return ScreenResult(outcomes=outcomes, residue=residue)
