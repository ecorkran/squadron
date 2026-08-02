"""Deterministic screens for the findings-addressed gate policy.

Screens run before any model call and cost zero tokens. Each one settles the
findings it can prove something about; whatever it cannot settle becomes
residue for the judge. No screen ever settles a finding as ``addressed`` —
that direction fails open, and the screens are the fail-closed layer.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from squadron.pipeline.actions.findings_addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
)
from squadron.review.git_utils import run_git
from squadron.review.models import Verdict
from squadron.review.parsers import UNVERIFIED_LOCATION

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Round diff — the deterministic evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundDiff:
    """What this round changed, measured at gate time.

    The gate runs *before* the iteration's commit (``commit_each_iteration``
    appends its commit after all inner steps), so round N is uncommitted and
    ``HEAD`` is the prior round's commit. The round's changes are therefore the
    working tree against ``HEAD`` — no round-N SHA exists to diff against, and
    none is attempted.
    """

    changed_paths: frozenset[str]
    is_empty: bool
    #: The prior round's commit — ``HEAD`` at gate time. Round N's own SHA is
    #: not recordable here: this evidence is written before the commit that
    #: contains it, so it cannot carry that commit's identity. The audit pair
    #: is prior SHA + revision_number; round N's commit is discoverable from
    #: git afterwards as the commit containing the artifact.
    prior_sha: str | None
    #: The git command that failed, verbatim. Not None means the evidence could
    #: not be computed at all — the one git condition that earns UNKNOWN.
    failed_command: str | None = None


def _git_output(args: list[str], *, cwd: str) -> tuple[str | None, str | None]:
    """Run a git command, returning ``(stdout, failed_command)``.

    Exactly one element is ever non-None: git could not be invoked or refused
    (failed command), or it produced output (possibly empty).
    """
    command = " ".join(["git", *args])
    completed = run_git(args, cwd=cwd)
    if completed is None:
        return None, command
    if completed.returncode != 0:
        return None, command
    return completed.stdout, None


def compute_round_diff(*, cwd: str, paths: Sequence[str] = ()) -> RoundDiff:
    """Measure round N's changes as the working tree against ``HEAD``.

    ``paths`` scopes the measurement to the loop's artifact paths when the gate
    supplies them; empty means the whole tree. Untracked files are picked up
    via ``git status --porcelain``, which ``git diff`` alone would miss — a
    round whose only output is a brand-new file is not a byte-identical round.
    """
    path_args = ["--", *paths] if paths else []

    diff_out, failed = _git_output(["diff", "HEAD", "--name-only", *path_args], cwd=cwd)
    if failed is not None:
        return RoundDiff(
            changed_paths=frozenset(), is_empty=False, prior_sha=None, failed_command=failed
        )

    status_out, failed = _git_output(["status", "--porcelain", *path_args], cwd=cwd)
    if failed is not None:
        return RoundDiff(
            changed_paths=frozenset(), is_empty=False, prior_sha=None, failed_command=failed
        )

    sha_out, failed = _git_output(["rev-parse", "HEAD"], cwd=cwd)
    if failed is not None:
        return RoundDiff(
            changed_paths=frozenset(), is_empty=False, prior_sha=None, failed_command=failed
        )

    changed = {line.strip() for line in (diff_out or "").splitlines() if line.strip()}
    # Porcelain lines are "XY path"; the status codes are irrelevant here —
    # only whether anything is there, and which paths.
    status_lines = [line for line in (status_out or "").splitlines() if line.strip()]
    changed.update(line[3:].strip() for line in status_lines if len(line) > 3)

    prior_sha = (sha_out or "").strip() or None
    return RoundDiff(
        changed_paths=frozenset(changed),
        is_empty=not changed,
        prior_sha=prior_sha,
    )


# ---------------------------------------------------------------------------
# Deterministic screens
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ScreenResult:
    """What the deterministic layer settled, and what it could not.

    ``leg_verdict`` is set only when a screen decided the addressed leg
    outright (screens 0 and 1, or a git failure). Otherwise it is None and the
    residue goes to the judge.

    ``deciding_screen`` names which screen did that, so the gate's metadata
    reports it from the enum rather than from a reconstructed free string. It
    is None when no screen decided the leg, including the git-failure path —
    nothing was settled there.
    """

    outcomes: list[FindingOutcome]
    residue: list[FindingRecord]
    leg_verdict: str | None = None
    deciding_screen: SettlingScreen | None = None


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


def screen_byte_identical(prior_findings: list[FindingRecord]) -> ScreenResult:
    """Screen 1 — the round produced nothing, so nothing was addressed.

    Zero judge tokens: there is no evidence to weigh. This is issue #42's
    symptom made load-bearing.
    """
    _logger.warning(
        "findings-addressed: round produced no changes; %d prior finding(s) unaddressed",
        len(prior_findings),
    )
    return ScreenResult(
        outcomes=[
            FindingOutcome(
                finding_id=record.finding_id,
                status=FindingStatus.UNADDRESSED,
                screen=SettlingScreen.BYTE_IDENTICAL,
                note="round produced no changes",
            )
            for record in prior_findings
        ],
        residue=[],
        leg_verdict=Verdict.FAIL,
        deciding_screen=SettlingScreen.BYTE_IDENTICAL,
    )


def screen_git_failure(diff: RoundDiff) -> ScreenResult:
    """The round diff could not be computed — the check could not run.

    The only git condition that earns UNKNOWN. A missing round-N commit is not
    this: that is a known state (Screen 1), with a known right answer.
    """
    _logger.warning(
        "findings-addressed: round diff unavailable, '%s' failed; addressed leg UNKNOWN",
        diff.failed_command,
    )
    return ScreenResult(outcomes=[], residue=[], leg_verdict=Verdict.UNKNOWN)


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
        return screen_byte_identical(prior_findings)

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
