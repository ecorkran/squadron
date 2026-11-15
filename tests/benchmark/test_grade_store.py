"""``GradeRecordStore``: grade and estimate records (slice 425 Task 10)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path

import pytest

from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.grade_models import GradeAbsence
from squadron.metrology.grade_records import (
    CasesNeeded,
    PairEstimate,
    SampleSizeEstimate,
)
from squadron.metrology.grade_store import (
    GradeRecordStore,
    implementation_grade_id,
    reference_grade_id,
)
from squadron.metrology.store import MetrologyStore
from tests.benchmark.test_grade_identity import make_identity, make_reviewer
from tests.benchmark.test_grade_models import make_result
from tests.benchmark.test_grade_records import (
    make_heavy_reference,
    make_implementation,
    make_reference,
)
from tests.metrology.test_benchmark_store import make_case

REPLAY_A = "implreplay-aaaaaaaaaaaa-bbbbbbbbbbbb-cccccccc-s1"
REPLAY_B = "implreplay-aaaaaaaaaaaa-bbbbbbbbbbbb-dddddddd-s1"


@pytest.fixture
def raw(tmp_path: Path) -> MetrologyStore:
    return MetrologyStore(store_dir=tmp_path)


@pytest.fixture
def records(raw: MetrologyStore) -> BenchmarkRecordStore:
    return BenchmarkRecordStore(raw)


@pytest.fixture
def grades(records: BenchmarkRecordStore) -> GradeRecordStore:
    return GradeRecordStore(records)


def make_estimate(benchmark_id: str, case_set: str, day: int) -> SampleSizeEstimate:
    return SampleSizeEstimate(
        benchmark_id=benchmark_id,
        case_set=case_set,
        case_set_version=1,
        grader_digest="a" * 64,
        n_cases=10,
        samples=3,
        pairs=(
            PairEstimate(
                config_a="a",
                config_b="b",
                within_case_variance=0.1,
                between_case_variance=0.0,
                mdd_now=0.2,
                cases_needed=(CasesNeeded(samples=3, cases=12),),
            ),
        ),
        created_at=datetime(2026, 11, day, tzinfo=UTC),
    )


class TestReferenceGrades:
    def test_round_trip_and_lookup_by_case_grader_and_environment(
        self, grades: GradeRecordStore
    ) -> None:
        case_id = make_case().case_id
        reference = make_reference(case_id=case_id)
        record_id = grades.write_reference_grade(reference)
        assert record_id == reference_grade_id(
            case_id, reference.grader.digest, reference.environment_digest
        )
        found = grades.get_reference_grade(
            case_id, reference.grader.digest, reference.environment_digest
        )
        assert found == reference

    def test_a_different_environment_digest_finds_nothing(self, grades: GradeRecordStore) -> None:
        case_id = make_case().case_id
        reference = make_reference(case_id=case_id)
        grades.write_reference_grade(reference)
        assert grades.get_reference_grade(case_id, reference.grader.digest, "9" * 64) is None

    def test_a_different_grader_finds_nothing(self, grades: GradeRecordStore) -> None:
        case_id = make_case().case_id
        reference = make_reference(case_id=case_id)
        grades.write_reference_grade(reference)
        other = make_identity(reviewer=make_reviewer(model="another"))
        assert grades.get_reference_grade(case_id, other.digest, reference.environment_digest) is None

    def test_the_same_grade_written_twice_is_a_no_op(self, grades: GradeRecordStore) -> None:
        reference = make_reference(case_id=make_case().case_id)
        first = grades.write_reference_grade(reference)
        assert grades.write_reference_grade(reference) == first

    def test_different_content_under_the_same_id_raises(
        self, grades: GradeRecordStore, caplog: pytest.LogCaptureFixture
    ) -> None:
        case_id = make_case().case_id
        grades.write_reference_grade(make_reference(case_id=case_id))
        changed = make_reference(case_id=case_id, wall_seconds=99.0)
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="differs"):
            grades.write_reference_grade(changed)
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    def test_the_typical_heavy_record_is_accepted(self, grades: GradeRecordStore) -> None:
        heavy = make_heavy_reference()
        grades.write_reference_grade(heavy)
        found = grades.get_reference_grade(heavy.case_id, heavy.grader.digest, heavy.environment_digest)
        assert found == heavy


class TestImplementationGrades:
    def test_round_trip(self, grades: GradeRecordStore) -> None:
        grade = make_implementation(replay_id=REPLAY_A)
        record_id = grades.write_grade(grade)
        assert record_id == implementation_grade_id(REPLAY_A, grade.grader.digest)
        assert grades.get_grade(record_id) == grade

    def test_grades_for_returns_only_that_benchmarks_implementation_grades(
        self, grades: GradeRecordStore
    ) -> None:
        mine = make_implementation(replay_id=REPLAY_A, benchmark_id="bench-1")
        theirs = make_implementation(replay_id=REPLAY_B, benchmark_id="bench-2")
        grades.write_grade(mine)
        grades.write_grade(theirs)
        grades.write_reference_grade(make_reference(case_id=make_case().case_id))
        found = grades.grades_for("bench-1")
        assert [grade for _, grade in found] == [mine]

    def test_an_absent_grade_is_stored_like_any_other(self, grades: GradeRecordStore) -> None:
        grade = make_implementation(
            replay_id=REPLAY_A,
            result=None,
            absence=GradeAbsence.REVIEW_FAILED,
            absence_class="harness",
        )
        record_id = grades.write_grade(grade)
        stored = grades.get_grade(record_id)
        assert stored is not None
        assert stored.absence is GradeAbsence.REVIEW_FAILED


class TestDelete:
    def test_removes_only_the_named_ids_reference_or_implementation(
        self, grades: GradeRecordStore
    ) -> None:
        reference = make_reference(case_id=make_case().case_id)
        keep = make_implementation(replay_id=REPLAY_A)
        drop = make_implementation(replay_id=REPLAY_B)
        reference_id = grades.write_reference_grade(reference)
        grades.write_grade(keep)
        drop_id = grades.write_grade(drop)

        removed = grades.delete_grades([reference_id, drop_id, "implgrade-missing"])

        assert removed == 2
        assert grades.get_grade(drop_id) is None
        assert (
            grades.get_reference_grade(
                reference.case_id, reference.grader.digest, reference.environment_digest
            )
            is None
        )
        assert [g for _, g in grades.grades_for(keep.benchmark_id)] == [keep]

    def test_a_record_of_another_type_under_a_named_id_raises(
        self, grades: GradeRecordStore, records: BenchmarkRecordStore
    ) -> None:
        case_id = records.write_case(make_case())
        with pytest.raises(MetrologyStoreError, match="not a grade"):
            grades.delete_grades([case_id])
        assert records.get_case(case_id) is not None


class TestEstimates:
    def test_writing_twice_leaves_one_record(
        self, grades: GradeRecordStore, raw: MetrologyStore
    ) -> None:
        grades.write_estimate(make_estimate("bench-1", "fixes", 1))
        grades.write_estimate(make_estimate("bench-1", "fixes", 2))
        stored = [r for _, r in raw.iter_records() if r.sample_size_estimate is not None]
        assert len(stored) == 1
        assert stored[0].sample_size_estimate is not None
        assert stored[0].sample_size_estimate.created_at.day == 2

    def test_latest_estimate_picks_the_newest_for_the_case_set(self, grades: GradeRecordStore) -> None:
        grades.write_estimate(make_estimate("bench-1", "fixes", 1))
        newest = make_estimate("bench-2", "fixes", 5)
        grades.write_estimate(newest)
        grades.write_estimate(make_estimate("bench-3", "other", 9))
        assert grades.latest_estimate("fixes") == newest

    def test_estimate_for_is_this_benchmarks_own_even_when_a_newer_one_shares_the_case_set(
        self, grades: GradeRecordStore
    ) -> None:
        older = make_estimate("bench-1", "fixes", 1)
        grades.write_estimate(older)
        grades.write_estimate(make_estimate("bench-2", "fixes", 5))
        assert grades.estimate_for("bench-1") == older
        assert grades.estimate_for("bench-9") is None

    def test_no_estimate_is_none(self, grades: GradeRecordStore) -> None:
        assert grades.latest_estimate("fixes") is None


class TestWriteFailures:
    def test_a_failing_write_logs_error_and_raises(
        self,
        grades: GradeRecordStore,
        raw: MetrologyStore,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        def boom(record_id: str, record: object) -> None:
            raise MetrologyStoreError("disk full")

        monkeypatch.setattr(raw, "write_record", boom)
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="disk full"):
            grades.write_grade(make_implementation(replay_id=REPLAY_A))
        assert any("Failed to write grade record" in r.getMessage() for r in caplog.records)

    def test_an_oversized_record_is_refused_naming_its_largest_field_and_writes_nothing(
        self,
        grades: GradeRecordStore,
        raw: MetrologyStore,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        bloated = make_result(
            regression_failures=tuple("x" * 1000 for _ in range(50)),
            regression_failure_count=50,
        )
        grade = make_implementation(replay_id=REPLAY_A, result=bloated)
        record_id = implementation_grade_id(REPLAY_A, grade.grader.digest)
        with caplog.at_level(logging.ERROR), pytest.raises(MetrologyStoreError, match="bound"):
            grades.write_grade(grade)
        messages = [r.getMessage() for r in caplog.records if r.levelno == logging.ERROR]
        assert any(record_id in m and "result.regression_failures" in m for m in messages)
        assert not raw.record_location(record_id).exists()


class TestLargestReviewCost:
    def _graded(self, cost: float | None, reviewer_model: str = "gpt-x", replay: str = REPLAY_A):
        from squadron.metrology.grade_models import ReviewSummary
        from tests.benchmark.test_grade_identity import HASH

        summary = ReviewSummary(
            severity_counts={},
            total=0,
            unnormalized_count=0,
            cost_usd=cost,
            rules_hash=None,
            findings_sha256=HASH,
        )
        grader = make_identity(reviewer=make_reviewer(model=reviewer_model))
        return make_implementation(
            replay_id=replay, grader=grader, result=make_result(reviews=(summary,))
        )

    def test_none_when_nothing_is_stored(self, grades: GradeRecordStore) -> None:
        assert grades.largest_review_cost(make_reviewer().reviewer_key) is None

    def test_the_largest_priced_cost_of_that_reviewer_only(self, grades: GradeRecordStore) -> None:
        grades.write_grade(self._graded(0.10, replay=REPLAY_A))
        grades.write_grade(self._graded(0.30, replay=REPLAY_B))
        grades.write_grade(self._graded(9.99, reviewer_model="another-model", replay=REPLAY_B))
        grades.write_grade(
            self._graded(None, replay="implreplay-zzzzzzzzzzzz-bbbbbbbbbbbb-cccccccc-s9")
        )
        assert grades.largest_review_cost(make_reviewer().reviewer_key) == pytest.approx(0.30)
