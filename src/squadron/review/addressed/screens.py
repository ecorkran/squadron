"""Deterministic evidence and the screens that read it, free of loop context.

What lives here is what both entry points need: the measurement of what
changed (``RoundDiff``), and the two screens that decide from that measurement
alone — a diff that could not be computed, and a diff that is empty. Neither
needs a fresh review, an iteration number, or anything else the gate loop
supplies, so neither belongs in the pipeline package.

The screens that *do* need loop context — screen 0 (no prior round) and
screen 2 (the reviewer re-found it) — stay in
``pipeline/actions/findings_addressed/screens.py`` and import from here, in the
established pipeline-consumes-review direction (design review F002).

No screen ever settles a finding as ``addressed``: that direction fails open,
and the screens are the fail-closed layer.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass

from squadron.review.addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
)
from squadron.review.git_utils import run_git
from squadron.review.models import Verdict

_logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Round diff — the deterministic evidence
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoundDiff:
    """What changed between a base commit and now.

    The gate loop measures a *round*: it runs before the iteration's commit
    (``commit_each_iteration`` appends its commit after all inner steps), so
    round N is uncommitted, ``HEAD`` is the prior round's commit, and the
    base is ``HEAD``. The resolve path measures *since a review was authored*,
    so its base is the review's ``reviewedSha`` (or a fallback). Both are the
    same measurement against a different base.
    """

    changed_paths: frozenset[str]
    is_empty: bool
    #: The commit the change set was measured against. For the gate loop this
    #: is the prior round's commit — round N's own SHA is not recordable there:
    #: the evidence is written before the commit that contains it, so it cannot
    #: carry that commit's identity. The audit pair is prior SHA +
    #: revision_number; round N's commit is discoverable from git afterwards as
    #: the commit containing the artifact.
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


def _failed(command: str) -> RoundDiff:
    return RoundDiff(changed_paths=frozenset(), is_empty=False, prior_sha=None, failed_command=command)


def compute_diff_since(base_ref: str, *, cwd: str, paths: Sequence[str] = ()) -> RoundDiff:
    """Measure everything that changed since *base_ref*, committed or not.

    Two sources are unioned. ``git diff <base>`` — one commit argument, not a
    range — spans the base all the way to the working tree, so it catches both
    what has been committed since and what is merely edited. ``git status
    --porcelain`` adds what that misses: untracked files. A round whose only
    output is a brand-new file is not an empty round.

    ``paths`` scopes the measurement when the caller supplies them; empty means
    the whole tree. A base of ``HEAD`` measures the working tree alone, which
    is exactly what the gate loop needs.
    """
    path_args = ["--", *paths] if paths else []

    diff_out, failed = _git_output(["diff", base_ref, "--name-only", *path_args], cwd=cwd)
    if failed is not None:
        return _failed(failed)

    status_out, failed = _git_output(["status", "--porcelain", *path_args], cwd=cwd)
    if failed is not None:
        return _failed(failed)

    sha_out, failed = _git_output(["rev-parse", base_ref], cwd=cwd)
    if failed is not None:
        return _failed(failed)

    changed = {line.strip() for line in (diff_out or "").splitlines() if line.strip()}
    # Porcelain lines are "XY path"; the status codes are irrelevant here —
    # only whether anything is there, and which paths.
    status_lines = [line for line in (status_out or "").splitlines() if line.strip()]
    changed.update(line[3:].strip() for line in status_lines if len(line) > 3)

    return RoundDiff(
        changed_paths=frozenset(changed),
        is_empty=not changed,
        prior_sha=(sha_out or "").strip() or None,
    )


# ---------------------------------------------------------------------------
# Context-free screens
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


#: What an empty diff means, said in the caller's own terms. The gate loop
#: measures a round; the resolve path measures everything since a review was
#: authored. The screen is the same; only the sentence a reader sees differs,
#: so it is passed in rather than branched on inside.
EMPTY_ROUND_NOTE = "round produced no changes"
EMPTY_SINCE_REVIEW_NOTE = "nothing changed since the review was authored"


def screen_byte_identical(prior_findings: list[FindingRecord], *, note: str) -> ScreenResult:
    """Screen 1 — nothing changed, so nothing was addressed.

    Zero judge tokens: there is no evidence to weigh. This is issue #42's
    symptom made load-bearing.
    """
    _logger.warning(
        "findings-addressed: %s; %d prior finding(s) unaddressed",
        note,
        len(prior_findings),
    )
    return ScreenResult(
        outcomes=[
            FindingOutcome(
                finding_id=record.finding_id,
                status=FindingStatus.UNADDRESSED,
                screen=SettlingScreen.BYTE_IDENTICAL,
                note=note,
            )
            for record in prior_findings
        ],
        residue=[],
        leg_verdict=Verdict.FAIL,
        deciding_screen=SettlingScreen.BYTE_IDENTICAL,
    )


def screen_git_failure(diff: RoundDiff) -> ScreenResult:
    """The diff could not be computed — the check could not run.

    The only git condition that earns UNKNOWN. A missing round-N commit is not
    this: that is a known state (Screen 1), with a known right answer.
    """
    _logger.warning(
        "findings-addressed: round diff unavailable, '%s' failed; addressed leg UNKNOWN",
        diff.failed_command,
    )
    return ScreenResult(outcomes=[], residue=[], leg_verdict=Verdict.UNKNOWN)
