"""``sq review resolve`` — did the work address a prior review's findings?

This path asks the findings-addressed question outside the gate loop, against
a review file already on disk. It reads that file, measures what changed since
it was authored, consults the judge over what the deterministic screens cannot
settle, and writes a separate resolution artifact. It never touches the review
file: the review's ``verdict:`` is the reviewer's record, and a derived
resolution is evidence about it, not an amendment to it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from squadron.review.addressed.judge import JudgeLegResult, judge_residue_core
from squadron.review.addressed.models import (
    FindingOutcome,
    FindingRecord,
    FindingStatus,
    SettlingScreen,
    concern_plus,
)
from squadron.review.addressed.screens import RoundDiff
from squadron.review.addressed.verification import (
    derive_addressed_verdict,
    verify_outcomes,
)
from squadron.review.models import Verdict
from squadron.review.resolution_artifact import (
    ResolutionRecord,
    render_resolution,
    save_resolution,
    today_stamp,
)
from squadron.review.resolution_evidence import (
    INJECTION_CAP_KEY,
    DiffBaseSource,
    LoadedReview,
    compute_review_diff,
    injection_cap_if_exceeded,
    load_review,
    locate_review,
    resolve_review_diff_base,
    review_type_of,
    screen_review_diff,
)

_logger = logging.getLogger(__name__)


class Resolution(StrEnum):
    """What the resolve path concluded about a review's CONCERN+ findings.

    Deliberately not ``Verdict``: this is a statement *about* a review, not a
    second review verdict, and naming it ``verdict:`` anywhere would invite a
    reader to treat it as one.
    """

    ADDRESSED = "ADDRESSED"
    UNADDRESSED = "UNADDRESSED"
    UNKNOWN = "UNKNOWN"


#: The addressed-leg verdict the shared derivation returns, in this path's
#: vocabulary. Defined once so the mapping cannot drift between call sites.
_LEG_VERDICT_TO_RESOLUTION: dict[str, Resolution] = {
    Verdict.PASS: Resolution.ADDRESSED,
    Verdict.FAIL: Resolution.UNADDRESSED,
    Verdict.UNKNOWN: Resolution.UNKNOWN,
}


def screen_verdict_consistency(
    review: LoadedReview, accountable: list[FindingRecord]
) -> Resolution | None:
    """Settle the leg when there is nothing to hold the work accountable for.

    Zero CONCERN+ findings only means "addressed" if the review itself says
    nothing was wrong. Against a failing verdict it means the opposite: the
    evidence disagrees with itself. The review parser is known to drop findings
    while still recording a verdict (issue #28), so a ``FAIL`` review with an
    empty findings list is far more likely a parse loss than a clean slate —
    and reading it as a pass would launder that bug into an approval.

    Runs before any diff work: inconsistent evidence needs no measurement to
    justify UNKNOWN, and a review with no findings has nothing to measure
    against.
    """
    if accountable:
        return None

    if review.verdict == Verdict.PASS:
        _logger.info(
            "review-resolve: %s raised no CONCERN+ findings and its verdict is %s; "
            "resolution %s by annotation",
            review.path.name,
            Verdict.PASS,
            Resolution.ADDRESSED,
        )
        return Resolution.ADDRESSED

    _logger.warning(
        "review-resolve: %s has verdict %s but 0 CONCERN+ findings were parsed — "
        "treating as inconsistent evidence, not a pass (the review parser is known "
        "to drop findings while recording a verdict, issue #28); resolution %s",
        review.path.name,
        review.verdict,
        Resolution.UNKNOWN,
    )
    return Resolution.UNKNOWN


async def _run_judge_leg(
    accountable: list[FindingRecord],
    diff: RoundDiff,
    *,
    base: str | None,
    model_id: str | None,
    profile: str,
    cwd: str,
    no_judge: bool,
) -> JudgeLegResult:
    """Consult the judge over the residue, or record why it was not consulted.

    Two conditions skip the call, and both are reported as a judge failure
    rather than as an answer: the caller asked for no judge, and a change set
    too large to inject. Skipping fails closed by construction — the residue
    stays unsettled, which the derivation reads as UNKNOWN.

    The residue is the *entire* CONCERN+ set. 305's exact-match screen cannot
    narrow it here: that screen needs a fresh review to compare against, and
    this path has none (Decision 3).
    """
    if no_judge:
        _logger.warning(
            "review-resolve: --no-judge was given; %d CONCERN+ finding(s) left unsettled, "
            "resolution %s",
            len(accountable),
            Resolution.UNKNOWN,
        )
        return JudgeLegResult(failed=True)

    cap = injection_cap_if_exceeded(diff, cwd=cwd)
    if cap is not None:
        _logger.warning(
            "review-resolve: the change set since %s exceeds the %s cap of %d bytes; "
            "not consulting the judge, resolution %s",
            base,
            INJECTION_CAP_KEY,
            cap,
            Resolution.UNKNOWN,
        )
        return JudgeLegResult(failed=True)

    return await judge_residue_core(
        residue=accountable,
        # No fresh review exists on this path, so there is no finding set to
        # compare successors against. verify_outcomes will therefore downgrade
        # every MOVED claim to disputed — the documented consequence of
        # Decision 3, not a defect.
        fresh_findings=[],
        diff=diff,
        model_id=model_id,
        profile=profile,
        cwd=cwd,
    )


#: What an unsettled finding's record says. A finding the judge never spoke
#: about is disputed by the same rule as one it spoke about indefensibly:
#: uncertainty, recorded as uncertainty.
UNSETTLED_NOTE = "the judge did not settle this finding"


def _with_unsettled_recorded(
    outcomes: list[FindingOutcome], accountable: list[FindingRecord]
) -> list[FindingOutcome]:
    """Append a DISPUTED outcome for every accountable finding with no outcome.

    A skipped or failed judge leg returns no outcomes at all, which would leave
    the artifact silent about findings it was supposed to account for — and the
    artifact exists precisely so a reader can see which findings are unsettled
    and why. The derivation already reads this state as UNKNOWN, so recording
    it changes the record rather than the answer.
    """
    settled = {outcome.finding_id for outcome in outcomes}
    return outcomes + [
        FindingOutcome(
            finding_id=record.finding_id,
            status=FindingStatus.DISPUTED,
            screen=SettlingScreen.JUDGE,
            note=UNSETTLED_NOTE,
        )
        for record in accountable
        if record.finding_id not in settled
    ]


@dataclass(frozen=True)
class SettledFindings:
    """What the resolve path concluded, and the evidence it concluded it from."""

    resolution: Resolution
    outcomes: list[FindingOutcome]
    diff: RoundDiff
    #: Both None when the leg was settled before any diff base was needed —
    #: the verdict-consistency screen never measures anything.
    base: str | None
    base_source: DiffBaseSource | None
    judge_model: str | None = None


async def settle_findings(
    review: LoadedReview,
    *,
    model_id: str | None,
    profile: str,
    cwd: str,
    since: str | None = None,
    no_judge: bool = False,
) -> SettledFindings:
    """Decide each CONCERN+ finding's fate, cheapest evidence first.

    Order is the design's Data Flow, and it is load-bearing: the deterministic
    screens settle what they can before any model is consulted, so a run with
    nothing to weigh costs zero judge tokens.

    There is no fresh review on this path, so 305's exact-match screen cannot
    run and ``fresh_findings`` is empty everywhere below — see Decision 3.
    """
    accountable = concern_plus(review.findings)

    consistency = screen_verdict_consistency(review, accountable)
    if consistency is not None:
        return SettledFindings(
            resolution=consistency,
            outcomes=[],
            diff=RoundDiff(changed_paths=frozenset(), is_empty=True, prior_sha=None),
            base=None,
            base_source=None,
        )

    base, base_source = resolve_review_diff_base(review.frontmatter, review.path, since=since, cwd=cwd)
    diff = compute_review_diff(base, review.path, cwd=cwd)

    screened = screen_review_diff(accountable, diff)
    if screened is not None and screened.leg_verdict is not None:
        return SettledFindings(
            resolution=_LEG_VERDICT_TO_RESOLUTION[screened.leg_verdict],
            outcomes=screened.outcomes,
            diff=diff,
            base=base,
            base_source=base_source,
        )

    leg = await _run_judge_leg(
        accountable,
        diff,
        base=base,
        model_id=model_id,
        profile=profile,
        cwd=cwd,
        no_judge=no_judge,
    )
    verified = _with_unsettled_recorded(
        verify_outcomes(
            leg.outcomes,
            residue=accountable,
            fresh_findings=[],
            diff=diff,
        ),
        accountable,
    )
    return SettledFindings(
        resolution=_LEG_VERDICT_TO_RESOLUTION[
            derive_addressed_verdict(verified, judge_failed=leg.failed)
        ],
        outcomes=verified,
        diff=diff,
        base=base,
        base_source=base_source,
        judge_model=leg.model,
    )


@dataclass(frozen=True)
class ResolutionResult:
    """What a ``sq review resolve`` run produced, for a caller to report on."""

    resolution: Resolution
    review_path: Path
    artifact_path: Path
    outcomes: list[FindingOutcome]
    base: str | None
    base_source: DiffBaseSource | None


def _frontmatter_str(frontmatter: dict[str, object], key: str, fallback: str) -> str:
    """A string field from frontmatter, or *fallback* when it is absent or not one."""
    value = frontmatter.get(key)
    return value if isinstance(value, str) and value else fallback


async def resolve_review(
    index: int,
    review_type: str | None = None,
    *,
    model_id: str | None,
    profile: str,
    no_judge: bool = False,
    since: str | None = None,
    cwd: str,
) -> ResolutionResult:
    """Answer "were this review's findings addressed?" and record the answer.

    Sequences the design's Data Flow: locate → load → verdict-consistency
    screen → diff-base resolve → diff compute → empty/git-failure screen →
    judge leg → verify → derive → render → save. The review file is read and
    never written.

    ``model_id`` and ``profile`` arrive already resolved. The flag → config →
    template cascade lives at the CLI boundary that owns those flags, so it is
    not restated here in a second, drifting copy.

    Every WARNING and ERROR the steps above emit propagates as-is: nothing here
    catches, downgrades, or summarizes a log record another function chose to
    write.

    Raises:
        ResolutionError: If the review cannot be located or read.
        FileExistsError: If the resolution artifact's path is already taken.
    """
    review_path = locate_review(index, review_type, cwd)
    resolved_type = review_type or review_type_of(review_path)
    review = load_review(review_path)

    settled = await settle_findings(
        review,
        model_id=model_id,
        profile=profile,
        cwd=cwd,
        since=since,
        no_judge=no_judge,
    )

    record = ResolutionRecord(
        index=index,
        review_file=review_path.name,
        review_type=resolved_type,
        slice_name=_frontmatter_str(review.frontmatter, "slice", str(index)),
        project=_frontmatter_str(review.frontmatter, "project", "unknown"),
        review_verdict=review.verdict,
        resolution=settled.resolution,
        date_created=today_stamp(),
        reviewed_sha=_frontmatter_str(review.frontmatter, "reviewedSha", "") or None,
        resolved_sha=settled.base,
        sha_source=settled.base_source,
        judge_model=settled.judge_model,
        outcomes=settled.outcomes,
    )
    artifact_path = save_resolution(
        render_resolution(record),
        index=index,
        review_type=resolved_type,
        slice_name=record.slice_name,
        cwd=cwd,
    )
    _logger.info(
        "review-resolve: %s resolved %s; recorded in %s",
        review_path.name,
        settled.resolution,
        artifact_path.name,
    )
    return ResolutionResult(
        resolution=settled.resolution,
        review_path=review_path,
        artifact_path=artifact_path,
        outcomes=settled.outcomes,
        base=settled.base,
        base_source=settled.base_source,
    )
