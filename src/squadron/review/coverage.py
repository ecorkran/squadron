"""Cap a truncated or unread PASS to CONCERNS (slice 927 D4, slice 196 D12)."""

from __future__ import annotations

from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict, VerdictSource

COVERAGE_CATEGORY = "review-coverage"
COVERAGE_TITLE = "Diff truncated; the omitted part was never read"
OUTPUT_COVERAGE_TITLE = "Output cut off at the model's output budget"
OUTPUT_COVERAGE_DESCRIPTION = (
    "Output cut off at the model's output budget; findings after the cutoff are lost. "
    "The model's own verdict was PASS."
)


def impose_diff_coverage(result: ReviewResult) -> None:
    """Cap a stated PASS to CONCERNS when the diff was truncated and unread.

    Applies only when the diff was truncated, the verdict is PASS, and no
    tool call succeeded (``result.successful_tool_calls <= 0``, D4: no tools
    offered counts as zero successful calls, the same as every call failing).

    Mutates ``result`` in place: sets verdict to CONCERNS, verdict_source to
    IMPOSED, and prepends a synthetic CONCERN finding. Otherwise a no-op.
    """
    if result.diff_injection is None or not result.diff_injection.truncated:
        return
    if result.verdict is not Verdict.PASS:
        return

    if result.successful_tool_calls > 0:
        return

    total = result.diff_injection.total_chars
    injected = result.diff_injection.injected_chars
    omitted = total - injected
    finding = ReviewFinding(
        severity=Severity.CONCERN,
        title=COVERAGE_TITLE,
        description=(
            f"The diff was {total} characters; the first {injected} reached the model "
            f"(review.max_file_size_bytes). The model made no successful tool calls, "
            f"so the remaining {omitted} characters were not reviewed. The model's own "
            f"verdict was PASS. Raise review.max_file_size_bytes, narrow the diff, or "
            f"use a tool-enabled model."
        ),
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
