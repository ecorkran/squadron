"""Grade planning, refusals and the stated bound (slice 425 Task 34, D9)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from squadron.benchmark.grade_plan import (
    GradePlan,
    GradeRefusal,
    plan_grading,
    render_bound,
)
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.grade_models import GradeAbsence, ReviewSummary
from squadron.metrology.grade_store import GradeRecordStore, implementation_grade_id
from squadron.metrology.store import MetrologyStore
from tests.benchmark.test_grade_identity import HASH, make_identity, make_reviewer
from tests.benchmark.test_grade_models import make_result
from tests.benchmark.test_grade_records import make_implementation, make_reference
from tests.metrology.test_benchmark_replay_models import (  # pyright: ignore[reportPrivateUsage]
    _environment,
    _replay,
    _run,
)
from tests.metrology.test_benchmark_store import make_case

PROJECT = "proj"
REVIEWER = make_reviewer()
FLOOR_RUNS = 3
OTHER_ENVIRONMENT: EnvironmentIdentity = _environment().model_copy(
    update={"interpreter_version": "3.13.9"}
)


@pytest.fixture
def store(tmp_path: Path) -> GradeRecordStore:
    return GradeRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path)))


def make_run(benchmark_id: str = "bench-3f9c") -> BenchmarkRun:
    return _run().model_copy(update={"benchmark_id": benchmark_id})


def make_replay(case: BenchmarkCase, sample: int, **update: object) -> tuple[str, ImplementationReplay]:
    record_id = f"implreplay-aaaaaaaaaaaa-{case.case_id[5:17]}-cccccccc-s{sample}"
    replay = _replay().model_copy(
        update={"case_id": case.case_id, "sample": sample, "run_id": record_id, **update}
    )
    return record_id, replay


def plan(
    store: GradeRecordStore,
    cases: list[BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    **kwargs: object,
) -> GradePlan:
    options: dict[str, object] = {
        "run": make_run(),
        "cases": {case.case_id: case for case in cases},
        "replays": replays,
        "store": store,
        "reviewer": REVIEWER,
        "review_floor_runs": FLOOR_RUNS,
        "review_timeout_s": 120.0,
        "max_cost": 15.0,
        "review_cost": 0.25,
        "repo_project_ids": {PROJECT},
    }
    options.update(kwargs)
    return plan_grading(**options)  # type: ignore[arg-type]


def graded_summary(cost: float | None) -> ReviewSummary:
    return ReviewSummary(
        severity_counts={},
        total=0,
        unnormalized_count=0,
        cost_usd=cost,
        rules_hash=None,
        findings_sha256=HASH,
    )


def store_observed_cost(
    store: GradeRecordStore, cost: float, replay_id: str = "implreplay-x-s0"
) -> None:
    grade = make_implementation(
        replay_id=replay_id,
        grader=make_identity(reviewer=REVIEWER),
        result=make_result(reviews=(graded_summary(cost),)),
    )
    store.write_grade(grade)


class TestRefusals:
    def test_no_run_cap_names_the_flag(self, store: GradeRecordStore) -> None:
        with pytest.raises(GradeRefusal, match="--max-cost"):
            plan(store, [], [], max_cost=None)

    def test_no_reviewer_names_the_flag_and_the_config_key(self, store: GradeRecordStore) -> None:
        with pytest.raises(GradeRefusal, match=r"--review-model.*benchmark\.grading_review_model"):
            plan(store, [], [], reviewer=None)

    def test_an_unset_review_timeout_names_the_key(self, store: GradeRecordStore) -> None:
        with pytest.raises(GradeRefusal, match=r"benchmark\.review_timeout_s"):
            plan(store, [], [], review_timeout_s=None)

    def test_a_case_project_with_no_matching_repo_names_the_project(
        self, store: GradeRecordStore
    ) -> None:
        case = make_case(project_value="elsewhere")
        with pytest.raises(GradeRefusal, match="elsewhere"):
            plan(store, [case], [make_replay(case, 0)], repo_project_ids={PROJECT})

    def test_no_per_review_figure_names_the_flag(self, store: GradeRecordStore) -> None:
        with pytest.raises(GradeRefusal, match="--review-cost"):
            plan(store, [], [], review_cost=None)

    def test_a_non_positive_cap_or_figure_is_refused(self, store: GradeRecordStore) -> None:
        with pytest.raises(GradeRefusal, match="positive"):
            plan(store, [], [], max_cost=0)
        with pytest.raises(GradeRefusal, match="positive"):
            plan(store, [], [], review_cost=-1.0)


class TestFigure:
    def test_the_stores_largest_observed_cost_wins_over_the_flag(self, store: GradeRecordStore) -> None:
        store_observed_cost(store, 0.18)
        result = plan(store, [], [], review_cost=0.99)
        assert result.per_review_usd == pytest.approx(0.18)
        assert result.figure_source.value == "max observed"

    def test_the_flag_is_used_when_the_store_has_none(self, store: GradeRecordStore) -> None:
        result = plan(store, [], [], review_cost=0.25)
        assert result.per_review_usd == pytest.approx(0.25)
        assert result.figure_source.value == "--review-cost"


class TestPlanning:
    def test_reviews_are_references_times_floor_runs_plus_replays(
        self, store: GradeRecordStore
    ) -> None:
        cases = [make_case(task=f"t{i}") for i in range(2)]
        replays = [make_replay(case, s) for case in cases for s in range(2)]
        result = plan(store, cases, replays)
        assert (len(result.references), len(result.replays)) == (2, 4)
        assert result.review_count == 2 * FLOOR_RUNS + 4

    def test_two_replays_of_one_case_with_different_environments_plan_two_references(
        self, store: GradeRecordStore
    ) -> None:
        case = make_case()
        replays = [
            make_replay(case, 0),
            make_replay(case, 1, environment=OTHER_ENVIRONMENT),
        ]
        result = plan(store, [case], replays)
        assert len(result.references) == 2
        digests = {ref.environment_digest for ref in result.references}
        assert digests == {_environment().identity_digest, OTHER_ENVIRONMENT.identity_digest}
        assert result.review_count == 2 * FLOOR_RUNS + 2

    def test_a_graded_replay_is_excluded_and_so_is_a_reference_nobody_needs(
        self, store: GradeRecordStore
    ) -> None:
        case = make_case()
        record_id, replay = make_replay(case, 0)
        grader = plan(store, [case], []).grader
        store.write_grade(make_implementation(replay_id=record_id, grader=grader))
        result = plan(store, [case], [(record_id, replay)])
        assert result.replays == ()
        assert result.references == ()  # a case with no gradable replay needs none

    def test_an_existing_reference_is_not_planned_again(self, store: GradeRecordStore) -> None:
        case = make_case()
        grader = plan(store, [case], []).grader
        store.write_reference_grade(
            make_reference(
                case_id=case.case_id,
                grader=grader,
                environment_digest=_environment().identity_digest,
            )
        )
        result = plan(store, [case], [make_replay(case, 0)])
        assert result.references == ()
        assert len(result.replays) == 1

    def test_replays_that_cannot_be_graded_are_left_out(self, store: GradeRecordStore) -> None:
        case = make_case()
        replays = [
            make_replay(case, 0, outcome=ProducerOutcome.NO_COMMIT),
            make_replay(case, 1, absence=AbsenceClass.HARNESS),
            make_replay(case, 2, environment=None),
            make_replay(case, 3),
        ]
        result = plan(store, [case], replays)
        assert [r.replay.sample for r in result.replays] == [3]

    def test_the_case_filter_limits_the_plan(self, store: GradeRecordStore) -> None:
        cases = [make_case(task=f"t{i}") for i in range(2)]
        replays = [make_replay(case, 0) for case in cases]
        result = plan(store, cases, replays, only_cases={cases[1].case_id})
        assert [r.case.case_id for r in result.replays] == [cases[1].case_id]

    def test_retry_harness_replans_harness_absent_grades_and_names_the_stale_records(
        self, store: GradeRecordStore
    ) -> None:
        case = make_case()
        record_id, replay = make_replay(case, 0)
        grader = plan(store, [case], []).grader
        store.write_grade(
            make_implementation(
                replay_id=record_id,
                grader=grader,
                result=None,
                absence=GradeAbsence.REVIEW_FAILED,
                absence_class=AbsenceClass.HARNESS,
            )
        )
        without = plan(store, [case], [(record_id, replay)])
        assert without.replays == ()
        with_retry = plan(store, [case], [(record_id, replay)], retry_harness=True)
        assert len(with_retry.replays) == 1
        assert with_retry.stale_record_ids == (implementation_grade_id(record_id, grader.digest),)

    def test_retry_harness_leaves_a_config_absence_alone(self, store: GradeRecordStore) -> None:
        case = make_case()
        record_id, replay = make_replay(case, 0)
        grader = plan(store, [case], []).grader
        store.write_grade(
            make_implementation(
                replay_id=record_id,
                grader=grader,
                result=None,
                absence=GradeAbsence.PRODUCER_ENV_UNRESOLVABLE,
                absence_class=AbsenceClass.CONFIG,
            )
        )
        result = plan(store, [case], [(record_id, replay)], retry_harness=True)
        assert result.replays == ()
        assert result.stale_record_ids == ()


class TestBound:
    def test_the_text_matches_the_designs_example(self, store: GradeRecordStore) -> None:
        store_observed_cost(store, 0.18)
        cases = [make_case(task=f"t{i}") for i in range(10)]
        replays = [
            make_replay(case, sample)
            for index, case in enumerate(cases)
            for sample in range(6 if index < 4 else 5)
        ]
        assert len(replays) == 54
        result = plan(store, cases, replays, max_cost=15.0)
        assert render_bound(result).splitlines() == [
            "grade bench-3f9c  reviewer gpt-review (openai-oauth)  floor runs 3",
            "references 10 × 3 reviews + replays 54 × 1 review = 84 reviews",
            "bound: 84 × $0.18 (max observed) = $15.12, capped at run cap $15.00",
            "       + one review of overshoot $0.18 → at most $15.18",
            "       no per-review cap: a review can cost more than its figure",
        ]

    def test_a_bound_under_the_cap_says_so(self, store: GradeRecordStore) -> None:
        case = make_case()
        result = plan(store, [case], [make_replay(case, 0)], max_cost=50.0, review_cost=0.25)
        lines = render_bound(result).splitlines()
        assert lines[2] == "bound: 4 × $0.25 (--review-cost) = $1.00, under run cap $50.00"

    def test_nothing_to_grade_says_so(self, store: GradeRecordStore) -> None:
        assert render_bound(plan(store, [], [])).splitlines()[-1] == "nothing to grade"
