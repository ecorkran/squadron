"""Cap a truncated or unread PASS to CONCERNS (slice 927 D4, slice 196 D12)."""

from __future__ import annotations

from dataclasses import dataclass

from squadron.config.manager import get_typed_config
from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict, VerdictSource

COVERAGE_CATEGORY = "review-coverage"
COVERAGE_TITLE = "Too little of the diff was examined to support PASS"
OUTPUT_COVERAGE_TITLE = "Output cut off at the model's output budget"
OUTPUT_COVERAGE_DESCRIPTION = (
    "Output cut off at the model's output budget; findings after the cutoff are lost. "
    "The model's own verdict was PASS."
)


@dataclass(frozen=True)
class CoverageLimits:
    """The thresholds below which a stated PASS is not trusted (#309, #311).

    ``max_unseen_fraction``: more than this share of the diff never reaching the model
    caps a PASS whatever tool calls were made. ``large_diff_chars`` and
    ``min_tool_calls_large_diff``: a diff at least that large, reviewed by a model that
    was offered tools, needs at least that many successful calls.
    """

    max_unseen_fraction: float
    large_diff_chars: int
    min_tool_calls_large_diff: int


def load_coverage_limits(cwd: str) -> CoverageLimits:
    """Read the limits from config (defaults live in ``config.keys``)."""
    return CoverageLimits(
        max_unseen_fraction=get_typed_config("review.max_unseen_diff_fraction", float, cwd=cwd),
        large_diff_chars=get_typed_config("review.large_diff_chars", int, cwd=cwd),
        min_tool_calls_large_diff=get_typed_config("review.min_tool_calls_large_diff", int, cwd=cwd),
    )


def _coverage_gap(result: ReviewResult, limits: CoverageLimits) -> str | None:
    """Why a stated PASS rests on too little of the diff, or None when it does not."""
    injection = result.diff_injection
    if injection is None:
        return None
    total, injected = injection.total_chars, injection.injected_chars
    successful = result.successful_tool_calls
    if injection.truncated:
        cut_paths = ", ".join(f.path for f in injection.cut_files)
        cut_note = f" (cut or omitted: {cut_paths})" if cut_paths else ""
        limit_note = (
            "(review.max_file_size_bytes caps each file, review.max_total_injection_bytes the whole)"
        )
        if successful <= 0:
            return (
                f"The diff was {total} characters; {injected} reached the model "
                f"{limit_note}. The model made no successful tool calls, so the remaining "
                f"{total - injected} characters were not reviewed{cut_note}. The model's own "
                f"verdict was PASS. Raise the limits, narrow the diff, or use a tool-enabled model."
            )
        if (total - injected) / total > limits.max_unseen_fraction:
            return (
                f"The diff was {total} characters; {injected} reached the model "
                f"{limit_note}, more than review.max_unseen_diff_fraction "
                f"({limits.max_unseen_fraction}) of it unseen{cut_note}. The model made "
                f"{successful} successful tool call(s), which cannot stand in for the rest "
                f"of the diff. The model's own verdict was PASS. Raise the limits or "
                f"narrow the diff."
            )
    if (
        result.tools_given
        and total >= limits.large_diff_chars
        and successful < limits.min_tool_calls_large_diff
    ):
        return (
            f"The diff was {total} characters (review.large_diff_chars is "
            f"{limits.large_diff_chars}) and the model made {successful} successful tool "
            f"call(s); review.min_tool_calls_large_diff is {limits.min_tool_calls_large_diff}. "
            f"The verdict rests mostly on the diff text, not on the code behind it. "
            f"The model's own verdict was PASS."
        )
    return None


def impose_diff_coverage(result: ReviewResult, limits: CoverageLimits) -> None:
    """Cap a stated PASS to CONCERNS when too little of the diff was examined.

    Three causes (see ``_coverage_gap``): a truncated diff and no successful tool
    call (slice 927 D4); a mostly-unseen diff whatever tools were used (#309); a
    large diff reviewed with fewer successful tool calls than the floor (#311).
    No tools offered counts as zero successful calls.

    Mutates ``result`` in place: sets verdict to CONCERNS, verdict_source to
    IMPOSED, and prepends a synthetic CONCERN finding. Otherwise a no-op.
    """
    if result.verdict is not Verdict.PASS:
        return
    description = _coverage_gap(result, limits)
    if description is None:
        return
    finding = ReviewFinding(
        severity=Severity.CONCERN,
        title=COVERAGE_TITLE,
        description=description,
        category=COVERAGE_CATEGORY,
        location=None,
    )
    result.findings = [finding, *result.findings]
    result.verdict = Verdict.CONCERNS
    result.verdict_source = VerdictSource.IMPOSED


def impose_output_coverage(result: ReviewResult) -> None:
    """Cap a stated PASS to CONCERNS when the output budget was exhausted (#152).

    Truncation loses findings however much the model read, so unlike
    ``impose_diff_coverage`` the tool-call count is ignored.

    Mutates ``result`` in place: sets verdict to CONCERNS, verdict_source to
    IMPOSED, and prepends a synthetic CONCERN finding. Otherwise a no-op.
    """
    if not result.output_budget_exhausted:
        return
    if result.verdict is not Verdict.PASS:
        return

    finding = ReviewFinding(
        severity=Severity.CONCERN,
        title=OUTPUT_COVERAGE_TITLE,
        description=OUTPUT_COVERAGE_DESCRIPTION,
        category=COVERAGE_CATEGORY,
        location=None,
    )
    result.findings = [finding, *result.findings]
    result.verdict = Verdict.CONCERNS
    result.verdict_source = VerdictSource.IMPOSED
