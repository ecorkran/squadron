"""Grade record ids (slice 425 Task 10, D10)."""

from __future__ import annotations

import pytest

from squadron.metrology.grade_models import GraderIdentity
from squadron.metrology.grade_store import (
    estimate_id,
    implementation_grade_id,
    reference_grade_id,
)
from tests.benchmark.test_grade_identity import make_identity, make_reviewer

CASE_ID = "case-0123456789abcdef"
ENVIRONMENT = "e1" * 32
REPLAY_ID = "implreplay-aaaaaaaaaaaa-bbbbbbbbbbbb-cccccccc-s2"


def test_reference_id_has_the_designed_shape() -> None:
    grader = make_identity()
    expected = f"refgrade-0123456789ab-{grader.digest[:12]}-{ENVIRONMENT[:8]}"
    assert reference_grade_id(CASE_ID, grader.digest, ENVIRONMENT) == expected


def test_implementation_id_has_the_designed_shape() -> None:
    grader = make_identity()
    expected = f"implgrade-aaaaaaaaaaaa-bbbbbbbbbbbb-cccccccc-s2-{grader.digest[:8]}"
    assert implementation_grade_id(REPLAY_ID, grader.digest) == expected


def test_ids_are_deterministic() -> None:
    grader = make_identity()
    assert reference_grade_id(CASE_ID, grader.digest, ENVIRONMENT) == reference_grade_id(
        CASE_ID, make_identity().digest, ENVIRONMENT
    )
    assert implementation_grade_id(REPLAY_ID, grader.digest) == implementation_grade_id(
        REPLAY_ID, make_identity().digest
    )


@pytest.mark.parametrize(
    "other",
    [
        make_identity(reviewer=make_reviewer(model="another-model")),
        make_identity(grader_version=2),
    ],
    ids=["new reviewer", "bumped grader version"],
)
def test_a_new_grader_identity_gives_new_ids(other: GraderIdentity) -> None:
    base = make_identity()
    assert other != base
    assert reference_grade_id(CASE_ID, other.digest, ENVIRONMENT) != reference_grade_id(
        CASE_ID, base.digest, ENVIRONMENT
    )
    assert implementation_grade_id(REPLAY_ID, other.digest) != implementation_grade_id(
        REPLAY_ID, base.digest
    )


def test_a_different_environment_digest_gives_a_new_reference_id() -> None:
    grader = make_identity()
    assert reference_grade_id(CASE_ID, grader.digest, ENVIRONMENT) != reference_grade_id(
        CASE_ID, grader.digest, "f2" * 32
    )


def test_the_replay_prefix_is_removed_exactly_once() -> None:
    grader = make_identity()
    doubled = implementation_grade_id("implreplay-implreplay-x-s1", grader.digest)
    assert doubled == f"implgrade-implreplay-x-s1-{grader.digest[:8]}"


def test_ids_reject_a_foreign_prefix() -> None:
    grader = make_identity()
    with pytest.raises(ValueError, match="case id"):
        reference_grade_id("replay-0123456789abcdef", grader.digest, ENVIRONMENT)
    with pytest.raises(ValueError, match="replay id"):
        implementation_grade_id("case-0123456789abcdef", grader.digest)


def test_estimate_id_is_per_benchmark() -> None:
    assert estimate_id("bench-1") != estimate_id("bench-2")
    assert estimate_id("bench-1") == estimate_id("bench-1")
