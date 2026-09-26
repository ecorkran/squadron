"""Cap a truncated, unread PASS to CONCERNS (slice 927 D4)."""

from __future__ import annotations

from squadron.review.models import ReviewFinding, ReviewResult, Severity, Verdict, VerdictSource

COVERAGE_CATEGORY = "review-coverage"
COVERAGE_TITLE = "Diff truncated; the omitted part was never read"


def impose_diff_coverage(result: ReviewResult) -> None:
    """Cap a stated PASS to CONCERNS when the diff was truncated and unread.

    Applies only when the diff was truncated, the verdict is PASS, and no
    tool call succeeded — ``(tool_calls_made or 0) - (failed_tool_calls or
    0) <= 0``. The ``or 0`` is deliberate (D4): no tools offered counts as
    zero successful calls, the same as every call failing. Do not change
    this to ``is None`` checks.

    Mutates ``result`` in place: sets verdict to CONCERNS, verdict_source to
    IMPOSED, and prepends a synthetic CONCERN finding. Otherwise a no-op.
    """
    if result.diff_injection is None or not result.diff_injection.truncated:
        return
    if result.verdict is not Verdict.PASS:
        return

    successful_calls = (result.tool_calls_made or 0) - (result.failed_tool_calls or 0)
    if successful_calls > 0:
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
