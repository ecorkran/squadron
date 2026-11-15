"""Grade enums, grader identity and review models (slice 425 Task 7)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.grade_models import (
    GRADE_ABSENCE_CLASS,
    GRADER_VERSION,
    GradeAbsence,
    GraderIdentity,
    ReviewerRef,
    ReviewOutcome,
    ReviewSummary,
)
from squadron.metrology.review_models import CodeReviewFinding
from squadron.review.models import Severity

HASH = "a" * 64


def make_reviewer(**override: Any) -> ReviewerRef:
    fields: dict[str, Any] = {
        "alias": "gpt-review",
        "model": "gpt-x",
        "profile": "openai-oauth",
        "effort": "high",
        "template_hash": HASH,
        **override,
    }
    return ReviewerRef.build(**fields)


def make_identity(**override: Any) -> GraderIdentity:
    fields: dict[str, Any] = {
        "grader_version": GRADER_VERSION,
        "reviewer": make_reviewer(),
        "review_floor_runs": 3,
        **override,
    }
    return GraderIdentity.build(**fields)


def finding(severity: Severity, index: int = 0) -> CodeReviewFinding:
    return CodeReviewFinding(
        finding_id=f"f{index}",
        severity=severity,
        category=None,
        location=None,
        summary="s",
    )


def test_every_absence_has_a_class_and_only_one_is_config() -> None:
    assert set(GRADE_ABSENCE_CLASS) == set(GradeAbsence)
    assert len(GradeAbsence) == 11
    config = [a for a, c in GRADE_ABSENCE_CLASS.items() if c is AbsenceClass.CONFIG]
    assert config == [GradeAbsence.PRODUCER_ENV_UNRESOLVABLE]


class TestGraderIdentity:
    def test_digest_is_stable_across_construction_order(self) -> None:
        reviewer = make_reviewer()
        first = GraderIdentity.build(grader_version=1, reviewer=reviewer, review_floor_runs=3)
        second = GraderIdentity.build(review_floor_runs=3, reviewer=reviewer, grader_version=1)
        assert first.digest == second.digest

    @pytest.mark.parametrize(
        "override",
        [
            {"reviewer": make_reviewer(model="other-model")},
            {"reviewer": make_reviewer(effort="low")},
            {"reviewer": make_reviewer(template_hash="b" * 64)},
            {"grader_version": GRADER_VERSION + 1},
            {"review_floor_runs": 4},
        ],
    )
    def test_digest_changes_with_reviewer_version_and_floor_runs(
        self, override: dict[str, Any]
    ) -> None:
        assert make_identity(**override).digest != make_identity().digest

    def test_a_tampered_digest_fails_validation(self) -> None:
        identity = make_identity()
        data = identity.model_dump(mode="json")
        data["digest"] = "0" * 64
        with pytest.raises(ValidationError, match="digest"):
            GraderIdentity.model_validate(data)

    def test_round_trips_through_json(self) -> None:
        identity = make_identity()
        assert GraderIdentity.model_validate_json(identity.model_dump_json()) == identity


class TestReviewerRef:
    def test_reviewer_key_ignores_alias(self) -> None:
        assert make_reviewer(alias="one").reviewer_key == make_reviewer(alias="two").reviewer_key

    def test_alias_change_keeps_the_grader_digest(self) -> None:
        one = make_identity(reviewer=make_reviewer(alias="one"))
        two = make_identity(reviewer=make_reviewer(alias="two"))
        assert one.digest == two.digest

    def test_has_no_rules_hash_field(self) -> None:
        assert "rules_hash" not in ReviewerRef.model_fields

    def test_a_tampered_key_fails_validation(self) -> None:
        data = make_reviewer().model_dump(mode="json")
        data["reviewer_key"] = "0" * 64
        with pytest.raises(ValidationError, match="reviewer_key"):
            ReviewerRef.model_validate(data)


def test_review_summary_matches_its_outcome() -> None:
    outcome = ReviewOutcome(
        findings=(
            finding(Severity.FAIL, 0),
            finding(Severity.CONCERN, 1),
            finding(Severity.CONCERN, 2),
        ),
        unnormalized_count=1,
        cost_usd=0.12,
        rules_hash=HASH,
    )
    summary = ReviewSummary.from_outcome(outcome, findings_sha256="c" * 64)
    assert summary.total == len(outcome.findings) == 3
    assert summary.severity_counts == {"FAIL": 1, "CONCERN": 2}
    assert (summary.unnormalized_count, summary.cost_usd, summary.rules_hash) == (1, 0.12, HASH)
    assert summary.findings_sha256 == "c" * 64
