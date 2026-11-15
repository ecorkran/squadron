"""Slice-case records: enums, round trips and the validators that keep them honest (slice 426)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from squadron.metrology.benchmark_models import QualificationOutcome
from squadron.metrology.benchmark_replay_models import CaseDrop
from squadron.metrology.replay_models import PairOutcome
from squadron.metrology.slice_case_models import (
    DiffJudgment,
    OverSizeCase,
    SliceCandidateRejection,
    SliceQualification,
)
from squadron.pipeline.text_tail import FINAL_TEXT_TAIL_CHARS
from tests.benchmark.slice_case_support import (
    CASE_ID,
    environment,
    judgment,
    over_size,
    qualification,
)

MAX_JUDGMENT_BYTES = 4096


def test_the_rejection_values_are_the_designs_seven() -> None:
    assert {rejection.value for rejection in SliceCandidateRejection} == {
        "multiple_landings",
        "branch_contains_merges",
        "no_design_at_fork",
        "no_tasks_at_fork",
        "no_slice_plan_at_fork",
        "no_code_change",
        "no_regression_signal",
    }


def test_each_record_round_trips_through_json() -> None:
    records = [
        qualification(start_environment=environment()),
        qualification(QualificationOutcome.REJECTED, rejection=SliceCandidateRejection.NO_CODE_CHANGE),
        judgment(),
        over_size(),
    ]

    for record in records:
        assert type(record).model_validate_json(record.model_dump_json()) == record


def test_a_qualified_outcome_needs_a_case_id_and_no_rejection() -> None:
    with pytest.raises(ValidationError, match="case_id"):
        SliceQualification.model_validate(qualification().model_dump() | {"case_id": None})
    with pytest.raises(ValidationError, match="rejection"):
        SliceQualification.model_validate(
            qualification().model_dump() | {"rejection": SliceCandidateRejection.NO_CODE_CHANGE}
        )


def test_a_rejected_outcome_needs_a_rejection_and_no_case() -> None:
    rejected = qualification(
        QualificationOutcome.REJECTED, rejection=SliceCandidateRejection.NO_REGRESSION_SIGNAL
    )
    assert rejected.case_id is None
    with pytest.raises(ValidationError, match="rejection"):
        qualification(QualificationOutcome.REJECTED)
    with pytest.raises(ValidationError, match="case_id"):
        SliceQualification.model_validate(rejected.model_dump() | {"case_id": CASE_ID})


def test_a_harness_error_has_neither_case_nor_rejection() -> None:
    record = qualification(QualificationOutcome.HARNESS_ERROR)
    assert (record.case_id, record.rejection) == (None, None)
    with pytest.raises(ValidationError, match="rejection"):
        qualification(
            QualificationOutcome.HARNESS_ERROR, rejection=SliceCandidateRejection.NO_CODE_CHANGE
        )


def test_a_forfeit_has_no_calls_and_an_outcome() -> None:
    forfeit = DiffJudgment.model_validate(
        judgment().model_dump()
        | {
            "forfeit": True,
            "first_call": None,
            "second_call": None,
            "first_usage": None,
            "second_usage": None,
            "a_diff": None,
            "outcome": PairOutcome.B,
        }
    )
    assert forfeit.first_call is None and forfeit.outcome is PairOutcome.B
    for broken in (
        {"first_call": judgment().first_call},
        {"first_usage": judgment().first_usage},
        {"outcome": None},
        {"outcome": PairOutcome.INCONSISTENT},
    ):
        with pytest.raises(ValidationError):
            DiffJudgment.model_validate(forfeit.model_dump() | broken)


def test_a_judged_pair_needs_both_calls_and_an_outcome() -> None:
    assert judgment().first_call is not None
    for broken in ({"first_call": None}, {"second_call": None}, {"outcome": None}):
        with pytest.raises(ValidationError):
            DiffJudgment.model_validate(judgment().model_dump() | broken)


def test_a_realistic_judgment_serializes_under_4096_bytes() -> None:
    """Realistic tails are 177's: each call keeps at most FINAL_TEXT_TAIL_CHARS plus a mark
    (the task's "two 2 KB tails" alone would be 4096 bytes, so it cannot be the bound)."""
    record = judgment()

    assert record.first_call is not None
    assert len(record.first_call.raw_tail) == FINAL_TEXT_TAIL_CHARS + 1
    assert len(record.model_dump_json().encode()) < MAX_JUDGMENT_BYTES


def test_over_size_case_is_a_plain_record() -> None:
    record = over_size(limit=1000)
    assert isinstance(record, OverSizeCase)
    assert record.longest_prompt_chars > record.max_prompt_chars


@pytest.mark.parametrize("rejection", list(SliceCandidateRejection))
def test_a_case_drop_accepts_a_slice_rejection_value(rejection: SliceCandidateRejection) -> None:
    drop = CaseDrop(case_id=CASE_ID, reason=rejection, environment_digest="e" * 64)

    assert drop.reason == rejection
    assert CaseDrop.model_validate_json(drop.model_dump_json()) == drop
