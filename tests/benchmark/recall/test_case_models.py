"""Recall case model identity and validation (slice 430 D1)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.recall_case_models import (
    BugLocation,
    KnownBug,
    OriginalReview,
    RealBugCase,
    case_id_for,
    case_set_id,
)
from tests.benchmark.recall.support import case_fields, make_bug


def test_case_id_stable_across_bug_order_and_repo_parent() -> None:
    first = RealBugCase.build(**case_fields())
    reordered = RealBugCase.build(
        **case_fields(bugs=(make_bug("B2", "src/b.py"), make_bug("B1")), repo="/other/parent/demo")
    )
    assert first.case_id == reordered.case_id
    assert first.case_id.startswith("rbcase-")
    assert len(first.case_id) == len("rbcase-") + 12


def test_case_id_ignores_displaycase_fields() -> None:
    first = RealBugCase.build(**case_fields())
    renamed = RealBugCase.build(**case_fields(name="other", notes="n", hand_run_id="9"))
    assert first.case_id == renamed.case_id


@pytest.mark.parametrize(
    "change",
    [
        {"bugs": (make_bug("B1", "src/changed.py"), make_bug("B2", "src/b.py"))},
        {"bugs": (make_bug("B1"),)},
        {"head": "c" * 40},
        {"host_repo": "owner/other"},
    ],
)
def test_case_id_changes_with_identity(change: dict[str, Any]) -> None:
    assert (
        RealBugCase.build(**case_fields()).case_id != RealBugCase.build(**case_fields(**change)).case_id
    )


def test_extra_location_reason_changes_id() -> None:
    def with_extra(reason: str) -> KnownBug:
        extra = BugLocation(file="src/x.py", reason=reason)
        return make_bug().model_copy(update={"extra_locations": (extra,)})

    one = RealBugCase.build(**case_fields(bugs=(with_extra("r1"),)))
    two = RealBugCase.build(**case_fields(bugs=(with_extra("r2"),)))
    assert one.case_id != two.case_id


def test_extra_location_without_reason_rejected() -> None:
    with pytest.raises(ValidationError, match="without a reason"):
        KnownBug(
            id="B1",
            description="d",
            proof=("#5",),
            original_review=OriginalReview.REPORTED,
            locations=(),
            extra_locations=(BugLocation(file="src/x.py"),),
        )


def test_tampered_case_id_rejected() -> None:
    case = RealBugCase.build(**case_fields())
    data = case.model_dump(mode="json")
    data["case_id"] = "rbcase-000000000000"
    with pytest.raises(ValidationError, match="does not match"):
        RealBugCase.model_validate(data)


def test_round_trip_json() -> None:
    case = RealBugCase.build(**case_fields())
    restored = RealBugCase.model_validate_json(case.model_dump_json())
    assert restored == case
    assert case_id_for(restored) == case.case_id


def test_case_set_id() -> None:
    assert case_set_id("real-bugs", 2) == "rbset-real-bugs-v2"
