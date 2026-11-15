"""What a grade invocation will do, and the bound it states first (slice 425 D9, D16).

``plan_grading`` decides which references and replays still need a grade and refuses, naming
what is missing, before anything is spent. ``render_bound`` prints the cost bound that must
appear before the first review: reviews times the per-review figure, capped at the run cap,
plus one review of overshoot, because the cap is checked before each review. No per-review
cap exists, and the bound says so.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol

from squadron.config.keys import BENCHMARK_GRADING_REVIEW_MODEL_KEY, BENCHMARK_REVIEW_TIMEOUT_KEY
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.grade_models import (
    GRADE_ABSENCE_CLASS,
    GRADER_VERSION,
    GraderIdentity,
    ReviewerRef,
)
from squadron.metrology.grade_records import ImplementationGrade, ReferenceGrade
from squadron.metrology.grade_store import implementation_grade_id, reference_grade_id

RUN_CAP_FLAG = "--max-cost"
REVIEW_MODEL_FLAG = "--review-model"
REVIEW_COST_FLAG = "--review-cost"
REPO_FLAG = "--repo"


class GradeRefusal(ValueError):
    """Grading will not start; the message says what is missing and how to supply it."""


class FigureSource(StrEnum):
    """Where the per-review figure came from, as the bound labels it."""

    MAX_OBSERVED = "max observed"
    FLAG = REVIEW_COST_FLAG


class GradePlanStore(Protocol):
    def get_reference_grade(
        self, case_id: str, grader_digest: str, environment_digest: str
    ) -> ReferenceGrade | None: ...

    def get_grade(self, record_id: str) -> ImplementationGrade | None: ...

    def largest_review_cost(self, reviewer_key: str) -> float | None: ...


@dataclass(frozen=True)
class PlannedReference:
    case: BenchmarkCase
    environment_digest: str
    #: The stored record to delete first under ``--retry-harness``, ``None`` when there is none.
    stale_record_id: str | None = None


@dataclass(frozen=True)
class PlannedReplayGrade:
    case: BenchmarkCase
    replay_id: str
    replay: ImplementationReplay
    stale_record_id: str | None = None


@dataclass(frozen=True)
class GradePlan:
    benchmark_id: str
    grader: GraderIdentity
    run_cap_usd: float
    review_timeout_s: float
    per_review_usd: float
    figure_source: FigureSource
    references: tuple[PlannedReference, ...]
    replays: tuple[PlannedReplayGrade, ...]

    @property
    def review_count(self) -> int:
        return len(self.references) * self.grader.review_floor_runs + len(self.replays)

    @property
    def stale_record_ids(self) -> tuple[str, ...]:
        """Harness-absent records ``--retry-harness`` deletes before grading again."""
        ids = [r.stale_record_id for r in (*self.references, *self.replays) if r.stale_record_id]
        return tuple(ids)


def _is_gradable(replay: ImplementationReplay) -> bool:
    """Committed, not a harness absence, with an environment to reproduce."""
    return (
        replay.outcome is ProducerOutcome.COMMITTED
        and replay.absence is not AbsenceClass.HARNESS
        and replay.environment is not None
        and replay.diff is not None
    )


def _replay_state(
    store: GradePlanStore, grader: GraderIdentity, replay_id: str, retry_harness: bool
) -> tuple[bool, str | None]:
    """Whether the replay still needs a grade, and the stale record a retry deletes first."""
    record_id = implementation_grade_id(replay_id, grader.digest)
    grade = store.get_grade(record_id)
    if grade is None:
        return True, None
    if retry_harness and grade.absence_class is AbsenceClass.HARNESS:
        return True, record_id
    return False, None


def _reference_state(
    store: GradePlanStore,
    grader: GraderIdentity,
    case: BenchmarkCase,
    digest: str,
    retry_harness: bool,
) -> tuple[bool, str | None]:
    reference = store.get_reference_grade(case.case_id, grader.digest, digest)
    if reference is None:
        return True, None
    harness = reference.absence is not None and (
        GRADE_ABSENCE_CLASS[reference.absence] is AbsenceClass.HARNESS
    )
    if retry_harness and harness:
        return True, reference_grade_id(case.case_id, grader.digest, digest)
    return False, None


def _check_inputs(
    max_cost: float | None,
    reviewer: ReviewerRef | None,
    review_timeout_s: float | None,
) -> tuple[float, ReviewerRef, float]:
    if max_cost is None:
        raise GradeRefusal(f"no run cap: pass {RUN_CAP_FLAG} USD")
    if max_cost <= 0:
        raise GradeRefusal(f"the run cap must be positive, got {max_cost}")
    if reviewer is None:
        raise GradeRefusal(
            f"no grading reviewer: pass {REVIEW_MODEL_FLAG} ALIAS or set the config key "
            f"{BENCHMARK_GRADING_REVIEW_MODEL_KEY}"
        )
    if review_timeout_s is None:
        raise GradeRefusal(f"no review time limit: set the config key {BENCHMARK_REVIEW_TIMEOUT_KEY}")
    return max_cost, reviewer, review_timeout_s


def _check_projects(cases: Collection[BenchmarkCase], repo_project_ids: Collection[str]) -> None:
    for case in cases:
        if case.project_id.value not in repo_project_ids:
            raise GradeRefusal(
                f"case {case.case_id} belongs to project {case.project_id.value}, which no "
                f"{REPO_FLAG} given matches; pass {REPO_FLAG} PATH for it"
            )


def _per_review_figure(
    store: GradePlanStore, reviewer: ReviewerRef, review_cost: float | None
) -> tuple[float, FigureSource]:
    observed = store.largest_review_cost(reviewer.reviewer_key)
    if observed is not None:
        return observed, FigureSource.MAX_OBSERVED
    if review_cost is None:
        raise GradeRefusal(
            f"no per-review cost figure: no stored grade by reviewer {reviewer.alias} has one; "
            f"pass {REVIEW_COST_FLAG} USD"
        )
    if review_cost <= 0:
        raise GradeRefusal(f"the per-review cost must be positive, got {review_cost}")
    return review_cost, FigureSource.FLAG


def plan_grading(
    *,
    run: BenchmarkRun,
    cases: Mapping[str, BenchmarkCase],
    replays: Sequence[tuple[str, ImplementationReplay]],
    store: GradePlanStore,
    reviewer: ReviewerRef | None,
    review_floor_runs: int,
    review_timeout_s: float | None,
    max_cost: float | None,
    review_cost: float | None,
    repo_project_ids: Collection[str],
    only_cases: Collection[str] | None = None,
    retry_harness: bool = False,
) -> GradePlan:
    """The references and replays that need a grade, or a ``GradeRefusal`` naming what is missing.

    A replay is gradable when committed, not a harness absence and with an environment. A
    reference is planned per case and distinct environment digest among its ungraded replays,
    and each replay is later graded against the reference of its own digest.
    """
    cap, chosen, timeout = _check_inputs(max_cost, reviewer, review_timeout_s)
    selected = [
        (rid, replay)
        for rid, replay in replays
        if replay.case_id in cases and (only_cases is None or replay.case_id in only_cases)
    ]
    involved = {replay.case_id: cases[replay.case_id] for _, replay in selected}
    _check_projects(involved.values(), repo_project_ids)
    figure, source = _per_review_figure(store, chosen, review_cost)
    grader = GraderIdentity.build(
        grader_version=GRADER_VERSION, reviewer=chosen, review_floor_runs=review_floor_runs
    )
    planned_replays: list[PlannedReplayGrade] = []
    planned_refs: dict[tuple[str, str], PlannedReference] = {}
    for record_id, replay in selected:
        if not _is_gradable(replay) or replay.environment is None:
            continue
        needs, stale = _replay_state(store, grader, record_id, retry_harness)
        if not needs:
            continue
        case = cases[replay.case_id]
        planned_replays.append(PlannedReplayGrade(case, record_id, replay, stale))
        key = (case.case_id, replay.environment.identity_digest)
        if key not in planned_refs:
            ref_needed, ref_stale = _reference_state(store, grader, case, key[1], retry_harness)
            if ref_needed:
                planned_refs[key] = PlannedReference(case, key[1], ref_stale)
    return GradePlan(
        benchmark_id=run.benchmark_id,
        grader=grader,
        run_cap_usd=cap,
        review_timeout_s=timeout,
        per_review_usd=figure,
        figure_source=source,
        references=tuple(planned_refs.values()),
        replays=tuple(planned_replays),
    )


def render_bound(plan: GradePlan) -> str:
    """The block printed before the first review (D9)."""
    reviewer = plan.grader.reviewer
    runs = plan.grader.review_floor_runs
    reviews = plan.review_count
    header = (
        f"grade {plan.benchmark_id}  reviewer {reviewer.alias} ({reviewer.profile})  floor runs {runs}"
    )
    counts = (
        f"references {len(plan.references)} × {runs} reviews + replays {len(plan.replays)} × 1 "
        f"review = {reviews} reviews"
    )
    if reviews == 0:
        return f"{header}\n{counts}\nnothing to grade"
    figure = plan.per_review_usd
    total = reviews * figure
    source = f"{figure:.2f} ({plan.figure_source.value})"
    if total > plan.run_cap_usd:
        most = plan.run_cap_usd + figure
        lines = [
            f"bound: {reviews} × ${source} = ${total:.2f}, capped at run cap ${plan.run_cap_usd:.2f}",
            f"       + one review of overshoot ${figure:.2f} → at most ${most:.2f}",
        ]
    else:
        lines = [
            f"bound: {reviews} × ${source} = ${total:.2f}, under run cap ${plan.run_cap_usd:.2f}",
        ]
    lines.append("       no per-review cap: a review can cost more than its figure")
    return "\n".join([header, counts, *lines])
