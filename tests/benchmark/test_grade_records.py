"""Grade and estimate records inside the metrology envelope (slice 425 Task 9)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from squadron.metrology.benchmark_nodes import NodeOutcome, NodeResult
from squadron.metrology.benchmark_replay_enums import AbsenceClass
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import (
    DETAIL_MAX_CHARS,
    GradeAbsence,
    ReviewSummary,
)
from squadron.metrology.grade_records import (
    CasesNeeded,
    ImplementationGrade,
    PairEstimate,
    ReferenceGrade,
    SampleSizeEstimate,
)
from squadron.metrology.models import (
    RECORD_TYPE_IMPLEMENTATION_GRADE,
    RECORD_TYPE_REFERENCE_GRADE,
    RECORD_TYPE_SAMPLE_SIZE_ESTIMATE,
    MetrologyRecord,
)
from tests.benchmark.test_grade_identity import make_identity
from tests.benchmark.test_grade_models import HASH, make_result

NOW = datetime(2026, 11, 14, tzinfo=UTC)
BOUND_BYTES = 16 * 1024


def make_reference(**override: Any) -> ReferenceGrade:
    fields: dict[str, Any] = {
        "case_id": "case-0123456789abcdef",
        "grader": make_identity(),
        "environment_digest": "e" * 64,
        "result": make_result(),
        "absence": None,
        "detail": None,
        "baseline_nodes": HASH,
        "baseline_snapshot": {"sha256": HASH},
        "baseline_lint_total": 4,
        "baseline_type_total": 0,
        "review_floor": FloorStat(min=2, max=4, mean=3.0, stddev=1.0),
        "grading_cost_usd": 0.5,
        "wall_seconds": 12.5,
        "created_at": NOW,
        **override,
    }
    return ReferenceGrade.model_validate(fields)


def make_implementation(**override: Any) -> ImplementationGrade:
    fields: dict[str, Any] = {
        "replay_id": "replay-abc",
        "benchmark_id": "bench-1",
        "case_id": "case-0123456789abcdef",
        "grader": make_identity(),
        "environment_digest": "e" * 64,
        "result": make_result(),
        "absence": None,
        "absence_class": None,
        "detail": None,
        "grading_cost_usd": None,
        "wall_seconds": 3.0,
        "created_at": NOW,
        **override,
    }
    return ImplementationGrade.model_validate(fields)


def test_an_absent_implementation_grade_round_trips_in_the_envelope() -> None:
    grade = make_implementation(
        result=None,
        absence=GradeAbsence.PRODUCER_ENV_UNRESOLVABLE,
        absence_class=AbsenceClass.CONFIG,
        detail="lock is stale",
        environment_digest=None,
    )
    record = MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_IMPLEMENTATION_GRADE, implementation_grade=grade
    )
    loaded = MetrologyRecord.model_validate_json(record.model_dump_json())
    assert loaded.implementation_grade == grade
    assert loaded.implementation_grade is not None
    assert loaded.implementation_grade.result is None


def test_an_absent_reference_grade_round_trips_without_a_baseline() -> None:
    grade = make_reference(
        result=None,
        absence=GradeAbsence.ENVIRONMENT_FAILED,
        baseline_nodes=None,
        baseline_snapshot=None,
        baseline_lint_total=None,
        baseline_type_total=None,
        review_floor=None,
    )
    record = MetrologyRecord(
        schema_version=1, record_type=RECORD_TYPE_REFERENCE_GRADE, reference_grade=grade
    )
    assert MetrologyRecord.model_validate_json(record.model_dump_json()).reference_grade == grade


def test_a_sample_size_estimate_round_trips() -> None:
    estimate = SampleSizeEstimate(
        benchmark_id="bench-1",
        case_set="fixes",
        case_set_version=2,
        grader_digest=HASH,
        n_cases=10,
        samples=3,
        pairs=(
            PairEstimate(
                config_a="a",
                config_b="b",
                within_case_variance=0.1,
                between_case_variance=0.05,
                mdd_now=0.24,
                cases_needed=(CasesNeeded(samples=1, cases=30), CasesNeeded(samples=3, cases=15)),
            ),
        ),
        created_at=NOW,
    )
    record = MetrologyRecord(
        schema_version=1,
        record_type=RECORD_TYPE_SAMPLE_SIZE_ESTIMATE,
        sample_size_estimate=estimate,
    )
    loaded = MetrologyRecord.model_validate_json(record.model_dump_json())
    assert loaded.sample_size_estimate == estimate


def make_heavy_reference() -> ReferenceGrade:
    """50 regression ids of 100 characters, 10 of every other capped list, three reviews."""
    reviews = tuple(
        ReviewSummary(
            severity_counts={"FAIL": 2, "CONCERN": 5, "NOTE": 9},
            total=16,
            unnormalized_count=1,
            cost_usd=0.2,
            rules_hash=HASH,
            findings_sha256=HASH,
        )
        for _ in range(3)
    )
    result = make_result(
        hidden_total=100,
        hidden_passed=90,
        hidden_failures=tuple(
            NodeResult(
                node_id=f"tests/test_module.py::TestClass::test_method_{i}[param-{i}]",
                outcome=NodeOutcome.FAILED,
                phase="call",
                exception_type="AssertionError",
            )
            for i in range(10)
        ),
        regression_selected=900,
        regression_failures=tuple(f"{'t' * 90}::test_{i:03}" for i in range(50)),
        regression_failure_count=50,
        injection_clashes=tuple(f"clash-{'c' * 90}-{i}" for i in range(10)),
        injection_clash_count=10,
        config_edits=tuple(f"tool.{'x' * 90}-{i}" for i in range(10)),
        config_edit_count=10,
        test_edits=tuple(f"tests/{'d' * 90}-{i}.py" for i in range(10)),
        test_edit_count=10,
        reviews=reviews,
    )
    return make_reference(result=result, detail="d" * DETAIL_MAX_CHARS)


def test_a_typical_heavy_reference_grade_stays_under_the_record_bound() -> None:
    record = MetrologyRecord(
        schema_version=1,
        record_type=RECORD_TYPE_REFERENCE_GRADE,
        reference_grade=make_heavy_reference(),
    )
    assert len(record.model_dump_json().encode("utf-8")) < BOUND_BYTES


def test_an_old_record_without_the_new_fields_still_loads() -> None:
    old = json.dumps({"schema_version": 1, "record_type": "sample"})
    loaded = MetrologyRecord.model_validate_json(old)
    assert loaded.reference_grade is None
    assert loaded.implementation_grade is None
    assert loaded.sample_size_estimate is None


class TestValidation:
    def test_a_result_and_an_absence_together_fail(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            make_implementation(absence=GradeAbsence.SUITE_ERROR, absence_class=AbsenceClass.HARNESS)

    def test_neither_a_result_nor_an_absence_fails(self) -> None:
        with pytest.raises(ValidationError, match="exactly one"):
            make_implementation(result=None)

    def test_an_absence_class_that_disagrees_with_the_table_fails(self) -> None:
        with pytest.raises(ValidationError, match="absence_class"):
            make_implementation(
                result=None, absence=GradeAbsence.REVIEW_FAILED, absence_class=AbsenceClass.CONFIG
            )

    def test_a_reference_result_without_its_baseline_fails(self) -> None:
        with pytest.raises(ValidationError, match="baseline"):
            make_reference(baseline_nodes=None)

    def test_a_detail_over_the_cap_fails(self) -> None:
        with pytest.raises(ValidationError, match="detail"):
            make_reference(
                result=None, absence=GradeAbsence.SUITE_ERROR, detail="x" * (DETAIL_MAX_CHARS + 1)
            )
