"""A graded benchmark of slice cases with diff judgments, for the pairwise tests
(slice 426, Tasks 36-39)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta

from squadron.metrology.benchmark_models import BenchmarkCase, CaseKind
from squadron.metrology.replay_models import JudgeCall, JudgePick, JudgeRef, PairOutcome
from squadron.metrology.slice_case_models import DiffJudgment, OverSizeCase
from tests.benchmark.report_support import ReportWorld, config
from tests.benchmark.slice_case_support import BENCHMARK_ID, judge_ref, usage

OPUS = config("opus")
SOL = config("sol", profile="openai-oauth", effort_sent="medium")
T0 = datetime(2026, 11, 15, 12, 0, tzinfo=UTC)


def as_slice(world: ReportWorld, case: BenchmarkCase) -> BenchmarkCase:
    """The case with its kind set to ``slice`` (the id check is bypassed, as 425's tests do)."""
    converted = case.model_copy(update={"kind": CaseKind.SLICE})
    world.cases[case.case_id] = converted
    return converted


class Samples:
    """The replay record ids of each (case, alias, sample) a world holds."""

    def __init__(self) -> None:
        self.ids: dict[tuple[str, str, int], str] = {}

    def add(self, case: BenchmarkCase, alias: str, sample: int, record_id: str) -> None:
        self.ids[(case.case_id, alias, sample)] = record_id

    def of(self, case: BenchmarkCase, alias: str, sample: int) -> str:
        return self.ids[(case.case_id, alias, sample)]


def slice_world(
    world: ReportWorld, cases: int, *, samples: int = 1, passes: bool = True, kind_fix: int = 0
) -> tuple[list[BenchmarkCase], Samples]:
    """``cases`` slice cases graded for opus and sol at ``samples`` samples each (plus
    ``kind_fix`` fix cases)."""
    found: list[BenchmarkCase] = []
    ids = Samples()
    for index in range(cases):
        case = as_slice(world, world.add_case(f"slice-{index}"))
        found.append(case)
        for sample in range(samples):
            ids.add(case, "opus", sample, world.add_sample(case, OPUS, sample, passed=passes))
            ids.add(case, "sol", sample, world.add_sample(case, SOL, sample, passed=passes))
    for index in range(kind_fix):
        case = world.add_case(f"fix-{index}")
        for sample in range(samples):
            world.add_sample(case, OPUS, sample)
            world.add_sample(case, SOL, sample)
    return found, ids


def verdict_judgment(
    case: BenchmarkCase,
    a: str,
    b: str,
    outcome: PairOutcome,
    *,
    judge: JudgeRef | None = None,
    forfeit: bool = False,
    at: int = 0,
) -> DiffJudgment:
    """One judgment of ``a`` against ``b`` (replay record ids, or ``reference:<sha>``)."""
    pick = JudgePick.A if outcome is PairOutcome.A else JudgePick.B
    call = None if forfeit else JudgeCall(pick=pick, raw_tail="ok")
    return DiffJudgment(
        benchmark_id=BENCHMARK_ID,
        case_id=case.case_id,
        judge=judge or judge_ref(),
        a=a,
        b=b,
        a_diff=None if forfeit else "c" * 64,
        b_diff="d" * 64,
        forfeit=forfeit,
        first_call=call,
        second_call=call,
        outcome=outcome,
        first_usage=None if forfeit else usage(),
        second_usage=None if forfeit else usage(),
        max_prompt_chars=400000,
        created_at=T0 + timedelta(minutes=at),
    )


def over_size_record(
    case: BenchmarkCase, *, limit: int = 1000, judge: JudgeRef | None = None, at: int = 0
) -> OverSizeCase:
    return OverSizeCase(
        benchmark_id=BENCHMARK_ID,
        case_id=case.case_id,
        judge=judge or judge_ref(),
        longest_prompt_chars=limit + 1,
        longest_contestant="reference:" + "a" * 40,
        max_prompt_chars=limit,
        created_at=T0 + timedelta(minutes=at),
    )


def reference_ref(case: BenchmarkCase) -> str:
    return f"reference:{case.reference_sha}"


def cross(
    case: BenchmarkCase, ids: Samples, outcomes: Sequence[PairOutcome], **kwargs: object
) -> list[DiffJudgment]:
    """One opus-vs-sol judgment per sample, with the given outcomes in sample order."""
    return [
        verdict_judgment(case, ids.of(case, "opus", s), ids.of(case, "sol", s), outcome, **kwargs)  # type: ignore[arg-type]
        for s, outcome in enumerate(outcomes)
    ]
