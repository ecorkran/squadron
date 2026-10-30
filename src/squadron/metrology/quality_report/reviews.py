"""Review figures for the rollup reports (slice 403, D8, D9).

Counts per ``ReviewCategory`` over ingested code reviews. Severity stays on the review
scale. A finding with no category is counted as uncategorized, never as ``other``, and
findings mapped at read time are counted apart from those categorized at write time.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.quality_report.models import CategoryCount, ReviewSection
from squadron.metrology.review_models import CodeReviewFinding, CodeReviewRecord
from squadron.review.models import Severity


def _category_count(category: ReviewCategory, findings: Sequence[CodeReviewFinding]) -> CategoryCount:
    severities: dict[Severity, int] = {}
    for finding in findings:
        severities[finding.severity] = severities.get(finding.severity, 0) + 1
    # Only ``other`` keeps the reviewers' own words: they show how well the vocabulary fits.
    raw = (
        sorted({f.raw_category for f in findings if f.raw_category is not None})
        if category is ReviewCategory.OTHER
        else []
    )
    return CategoryCount(
        category=category, count=len(findings), severities=severities, raw_categories=raw
    )


def review_section(reviews: Sequence[CodeReviewRecord]) -> ReviewSection:
    """Counts over *reviews*: per category, plus the write-time and read-side-mapped totals."""
    findings = [finding for review in reviews for finding in review.findings]
    write_time = [f for review in reviews if not review.read_side_mapped for f in review.findings]
    mapped_total = len(findings) - len(write_time)
    categories = [
        _category_count(category, matching)
        for category in ReviewCategory
        if (matching := [f for f in findings if f.category is category])
    ]
    write_time_other = sum(1 for f in write_time if f.category is ReviewCategory.OTHER)
    return ReviewSection(
        n_files=len(reviews),
        n_findings=len(findings),
        write_time_findings=len(write_time),
        read_side_mapped_findings=mapped_total,
        categories=categories,
        uncategorized=sum(1 for f in findings if f.category is None),
        other_share=write_time_other / len(write_time) if write_time else None,
    )


def split_by_attribution(
    reviews: Sequence[CodeReviewRecord], resolved_indices: Collection[int]
) -> tuple[list[CodeReviewRecord], list[CodeReviewRecord]]:
    """Split into ``(slice_attributed, project_only)``.

    A review is attributed to a slice only when its ``slice_index`` has a resolved landing
    (D9). A review with no ``slice_index``, or whose slice never resolved, is project-only.
    """
    attributed: list[CodeReviewRecord] = []
    project_only: list[CodeReviewRecord] = []
    for review in reviews:
        resolved = review.slice_index is not None and review.slice_index in resolved_indices
        (attributed if resolved else project_only).append(review)
    return attributed, project_only
