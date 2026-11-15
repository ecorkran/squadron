"""A graded benchmark in a temp store, for the report tests (slice 425 Tasks 37-41)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from squadron.benchmark.adapter import NodeOutcome, NodeResult
from squadron.benchmark.bench_report import build_report
from squadron.benchmark.report_models import BenchmarkReport
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun, ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.floor_stat import FloorStat
from squadron.metrology.grade_models import GradeAbsence, GradeResult, GraderIdentity, ReviewSummary
from squadron.metrology.grade_records import (
    ImplementationGrade,
    SampleSizeEstimate,
)
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.metrology.store import MetrologyStore
from tests.benchmark.test_grade_identity import HASH, make_identity
from tests.benchmark.test_grade_models import make_result
from tests.benchmark.test_grade_plan import make_replay, make_run
from tests.benchmark.test_grade_records import make_implementation, make_reference
from tests.metrology.test_benchmark_replay_models import (
    _environment,  # pyright: ignore[reportPrivateUsage]
)
from tests.metrology.test_benchmark_store import make_case

ENVIRONMENT_DIGEST = _environment().identity_digest
FIXED_NOW = datetime(2026, 11, 14, tzinfo=UTC)
DEFAULT_FLOOR = FloorStat(min=1, max=3, mean=2.0, stddev=1.0)


def config(alias: str, **update: Any) -> ProducerConfigRef:
    """A config as the replay records it; ``update`` changes one identity field."""
    base: dict[str, Any] = {
        "alias": alias,
        "model": f"{alias}-model",
        "profile": "sdk",
        "effort_sent": "high",
        "tool_use": True,
        "max_output_tokens": None,
    }
    base.update(update)
    return ProducerConfigRef(**base)


def review(
    total: int = 2, cost: float | None = 0.1, severities: dict[str, int] | None = None
) -> ReviewSummary:
    return ReviewSummary(
        severity_counts=severities if severities is not None else {"CONCERN": total},
        total=total,
        unnormalized_count=0,
        cost_usd=cost,
        rules_hash=None,
        findings_sha256=HASH,
    )


def grade_result(passed: bool = True, **kwargs: Any) -> GradeResult:
    """A result that passes or fails (one hidden node not passing); kwargs override fields."""
    if passed:
        fields: dict[str, Any] = {"hidden_total": 3, "hidden_passed": 3}
    else:
        failing = (NodeResult("t.py::x", NodeOutcome.FAILED),)
        fields = {"hidden_total": 3, "hidden_passed": 2, "hidden_failures": failing}
    fields.update(kwargs)
    return make_result(**fields)


@dataclass
class ReportWorld:
    store: GradeRecordStore
    run: BenchmarkRun
    grader: GraderIdentity
    cases: dict[str, BenchmarkCase] = field(default_factory=dict[str, BenchmarkCase])
    replays: list[tuple[str, ImplementationReplay]] = field(
        default_factory=list[tuple[str, ImplementationReplay]]
    )
    grades: list[ImplementationGrade] = field(default_factory=list[ImplementationGrade])

    def add_case(
        self,
        name: str,
        *,
        floor: FloorStat | None = DEFAULT_FLOOR,
        lint: int | None = 3,
        types: int | None = 2,
        reference_passes: bool = True,
        reference: bool = True,
    ) -> BenchmarkCase:
        case = make_case(task=name)
        self.cases[case.case_id] = case
        if reference:
            self.store.write_reference_grade(
                make_reference(
                    case_id=case.case_id,
                    grader=self.grader,
                    environment_digest=ENVIRONMENT_DIGEST,
                    result=grade_result(reference_passes),
                    baseline_lint_total=lint,
                    baseline_type_total=types,
                    review_floor=floor,
                )
            )
        return case

    def add_sample(
        self,
        case: BenchmarkCase,
        cfg: ProducerConfigRef,
        sample: int,
        *,
        passed: bool = True,
        graded: bool = True,
        grader: GraderIdentity | None = None,
        replay: dict[str, Any] | None = None,
        grade_absence: tuple[GradeAbsence, AbsenceClass] | None = None,
        **result_fields: Any,
    ) -> str:
        record_id, base = make_replay(case, sample)
        record_id = f"{record_id}-{cfg.alias}-{cfg.effort_sent}-{cfg.tool_use}-{cfg.max_output_tokens}"
        update: dict[str, Any] = {
            "config": cfg,
            "run_id": record_id,
            "benchmark_id": self.run.benchmark_id,
        }
        update.update(replay or {})
        stored = base.model_copy(update=update)
        self.replays.append((record_id, stored))
        if not graded or stored.outcome is not ProducerOutcome.COMMITTED:
            return record_id
        who = grader or self.grader
        if grade_absence is not None:
            absence, absence_class = grade_absence
            grade = make_implementation(
                replay_id=record_id,
                benchmark_id=self.run.benchmark_id,
                case_id=case.case_id,
                grader=who,
                result=None,
                absence=absence,
                absence_class=absence_class,
                grading_cost_usd=0.1,
            )
        else:
            result_fields.setdefault("reviews", (review(),))
            result_fields.setdefault("lint_total", 4)
            result_fields.setdefault("type_total", 2)
            grade = make_implementation(
                replay_id=record_id,
                benchmark_id=self.run.benchmark_id,
                case_id=case.case_id,
                grader=who,
                result=grade_result(passed, **result_fields),
                grading_cost_usd=0.1,
            )
        self.grades.append(grade)
        return record_id

    def build(self, *, estimate: SampleSizeEstimate | None = None, **overrides: Any) -> BenchmarkReport:
        options: dict[str, Any] = {
            "run": self.run,
            "cases": self.cases,
            "case_ids": list(self.cases),
            "replays": self.replays,
            "grades": self.grades,
            "grader": self.grader,
            "reference_for": lambda case_id, digest: self.store.get_reference_grade(
                case_id, self.grader.digest, digest
            ),
            "estimate": estimate,
        }
        options.update(overrides)
        return build_report(**options)


def make_world(tmp_path: Path, *, samples: int = 2) -> ReportWorld:
    store = GradeRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")))
    run = make_run().model_copy(update={"samples": samples, "case_drops": ()})
    return ReportWorld(store=store, run=run, grader=make_identity())


#: Pass patterns of the hand-computed fixture: two configs, six cases, k = 2.
OPUS_PATTERN: Sequence[Sequence[bool]] = (
    (True, True),
    (True, True),
    (True, False),
    (False, False),
    (True, True),
    (True, False),
)
SOL_PATTERN: Sequence[Sequence[bool]] = (
    (True, False),
    (False, False),
    (False, False),
    (False, False),
    (True, False),
    (False, False),
)


def fixture_world(tmp_path: Path) -> ReportWorld:
    """Opus (high) and sol (medium) on six cases at k = 2, with the patterns above.

    Opus: lint 4 against baseline 3 (+1), types 2 against 2 (0). Sol: lint 6 (+3), no type
    measurement. Cell 3 of opus's case c3 also has two regressions.
    """
    world = make_world(tmp_path)
    opus = config("opus")
    sol = config("sol", profile="openai-oauth", effort_sent="medium")
    for index in range(6):
        case = world.add_case(f"case-{index}")
        for sample in range(2):
            extra = (
                {"regression_failures": ("t::a", "t::b"), "regression_failure_count": 2}
                if (index, sample) == (3, 0)
                else {}
            )
            world.add_sample(case, opus, sample, passed=OPUS_PATTERN[index][sample], **extra)
            world.add_sample(
                case, sol, sample, passed=SOL_PATTERN[index][sample], lint_total=6, type_total=None
            )
    return world
