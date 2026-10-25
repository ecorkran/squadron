"""The ``code_review`` record models (slice 402, D6)."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from squadron.core.finding_categories import ReviewCategory
from squadron.metrology.review_models import CodeReviewFinding, CodeReviewRecord
from squadron.review.models import Severity, Verdict
from tests.metrology.snapshot.builders import make_project_id


def make_finding(category: ReviewCategory | None = ReviewCategory.TEST_DEBT) -> CodeReviewFinding:
    return CodeReviewFinding(
        finding_id="F001",
        severity=Severity.CONCERN,
        category=category,
        raw_category="Test Debt" if category is not None else None,
        location="src/a.py:1",
        summary="No test",
    )


def make_record(
    verdict: Verdict = Verdict.CONCERNS, findings: list[CodeReviewFinding] | None = None
) -> CodeReviewRecord:
    return CodeReviewRecord(
        record_id="codereview-x-y",
        project_id=make_project_id(),
        review_path="project-documents/user/reviews/947-review.code.x.md",
        commit_sha="c" * 40,
        slice_index=947,
        verdict=verdict,
        read_side_mapped=False,
        reviewed_at=date(2026, 10, 18),
        ingested_at=datetime(2026, 10, 25, tzinfo=UTC),
        findings=findings if findings is not None else [make_finding()],
    )


def test_a_valid_record_round_trips_through_json() -> None:
    record = make_record()

    assert CodeReviewRecord.model_validate_json(record.model_dump_json()) == record


@pytest.mark.parametrize("verdict", [Verdict.PASS, Verdict.CONCERNS, Verdict.FAIL])
def test_known_verdicts_are_accepted(verdict: Verdict) -> None:
    assert make_record(verdict).verdict is verdict


def test_unknown_verdict_is_rejected() -> None:
    with pytest.raises(ValidationError, match="UNKNOWN"):
        make_record(Verdict.UNKNOWN)


def test_a_missing_category_serializes_as_null_never_other() -> None:
    record = make_record(findings=[make_finding(category=None)])

    dumped = json.loads(record.model_dump_json())

    assert dumped["findings"][0]["category"] is None
    assert dumped["findings"][0]["raw_category"] is None
