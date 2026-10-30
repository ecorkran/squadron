"""Review counts and slice attribution for the rollup reports (slice 403, D8, D9)."""

from __future__ import annotations

import pytest

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.quality_report.reviews import review_section, split_by_attribution
from squadron.metrology.review_models import CodeReviewFinding, CodeReviewRecord
from squadron.review.models import Severity
from tests.metrology.test_review_models import make_record


def finding(
    category: ReviewCategory | None,
    severity: Severity = Severity.CONCERN,
    raw: str | None = None,
) -> CodeReviewFinding:
    return CodeReviewFinding(
        finding_id="F001",
        severity=severity,
        category=category,
        raw_category=raw,
        location=None,
        summary="s",
    )


def review(
    findings: list[CodeReviewFinding], *, mapped: bool = False, slice_index: int | None = 403
) -> CodeReviewRecord:
    return make_record(findings=findings).model_copy(
        update={"read_side_mapped": mapped, "slice_index": slice_index}
    )


def test_counts_per_category_across_files_with_totals() -> None:
    reviews = [
        review([finding(ReviewCategory.CORRECTNESS), finding(ReviewCategory.TEST_DEBT)]),
        review([finding(ReviewCategory.CORRECTNESS, Severity.NOTE)]),
    ]

    section = review_section(reviews)

    assert (section.n_files, section.n_findings) == (2, 3)
    by_category = {c.category: c for c in section.categories}
    assert by_category[ReviewCategory.CORRECTNESS].count == 2
    assert by_category[ReviewCategory.TEST_DEBT].count == 1
    assert ReviewCategory.SECURITY_HYGIENE not in by_category


def test_write_time_and_read_side_mapped_totals_are_separate() -> None:
    section = review_section(
        [
            review([finding(ReviewCategory.CORRECTNESS)] * 2),
            review([finding(ReviewCategory.TEST_DEBT)] * 3, mapped=True),
        ]
    )

    assert (section.write_time_findings, section.read_side_mapped_findings) == (2, 3)
    assert section.n_findings == 5


def test_severity_counts_use_the_review_scale() -> None:
    section = review_section(
        [
            review(
                [
                    finding(ReviewCategory.CORRECTNESS, Severity.CONCERN),
                    finding(ReviewCategory.CORRECTNESS, Severity.CONCERN),
                    finding(ReviewCategory.CORRECTNESS, Severity.NOTE),
                ]
            )
        ]
    )

    [category] = section.categories
    assert category.severities == {Severity.CONCERN: 2, Severity.NOTE: 1}


def test_other_keeps_the_raw_strings_and_its_share_is_over_write_time_findings() -> None:
    section = review_section(
        [
            review(
                [
                    finding(ReviewCategory.OTHER, raw="style"),
                    finding(ReviewCategory.OTHER, raw="scope"),
                    finding(ReviewCategory.OTHER, raw="style"),
                    finding(ReviewCategory.CORRECTNESS, raw="Correctness"),
                ]
            ),
            review([finding(ReviewCategory.OTHER, raw="mapped")] * 5, mapped=True),
        ]
    )

    other = next(c for c in section.categories if c.category is ReviewCategory.OTHER)
    assert other.raw_categories == ["mapped", "scope", "style"]
    correctness = next(c for c in section.categories if c.category is ReviewCategory.CORRECTNESS)
    assert correctness.raw_categories == []
    assert section.other_share == pytest.approx(3 / 4)


def test_a_finding_with_no_category_is_uncategorized_never_other() -> None:
    section = review_section([review([finding(None), finding(ReviewCategory.CORRECTNESS)])])

    assert section.uncategorized == 1
    assert all(c.category is not ReviewCategory.OTHER for c in section.categories)
    assert section.other_share == 0


def test_no_write_time_findings_means_no_other_share() -> None:
    section = review_section([review([finding(ReviewCategory.OTHER)], mapped=True)])

    assert section.other_share is None


def test_every_review_section_is_marked_unfloored() -> None:
    assert review_section([]).floor_note == "no floor measured"


def test_attribution_splits_on_resolved_slice_indices() -> None:
    resolved = review([finding(ReviewCategory.CORRECTNESS)], slice_index=403)
    unresolved_slice = review([finding(ReviewCategory.CORRECTNESS)], slice_index=388)
    no_slice = review([finding(ReviewCategory.CORRECTNESS)], slice_index=None)

    attributed, project_only = split_by_attribution(
        [resolved, unresolved_slice, no_slice], resolved_indices={403}
    )

    assert attributed == [resolved]
    assert project_only == [unresolved_slice, no_slice]
