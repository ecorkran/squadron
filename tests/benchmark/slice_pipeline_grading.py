"""Grade, judge and report the fixture case's replays (slice 426, Task 41).

Real: ``grade_one`` (real suites in real sandboxes), the grade runner, the judge planner and
runner, the stores, ``build_report`` and ``render_text``. Scripted: the grading review (its
``reviewer`` parameter) and the judge's model (a dispatcher that prefers the diff holding the
reference's ``mul``). No model is called.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.bench_report import build_report
from squadron.benchmark.diff_judge_plan import JudgePlan, ResolvedJudge, plan_judge
from squadron.benchmark.diff_judge_reference import ReferenceDiffReader
from squadron.benchmark.diff_judge_runner import JudgeRunResult, run_judging
from squadron.benchmark.diff_prompt import diff_judge_prompt_hash
from squadron.benchmark.grade_budget import ReviewBudget
from squadron.benchmark.grade_deps import GradeDeps, GradeSandbox
from squadron.benchmark.grade_one import grade_one
from squadron.benchmark.grade_plan import GradePlan, plan_grading
from squadron.benchmark.grade_runner import GradeSummary, run_grading
from squadron.benchmark.grade_snapshot import make_snapshot_measurer
from squadron.benchmark.registry import fix_case_adapter_for, grading_adapter_for
from squadron.benchmark.report_models import BenchmarkReport
from squadron.benchmark.tree_reader import GitTreeReader
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import BenchmarkStatus
from squadron.metrology.benchmark_replay_models import BenchmarkRun
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.grade_models import ReviewOutcome
from squadron.metrology.grade_store import GradeRecordStore
from squadron.metrology.replay_models import JudgeRef, ProducerConfigRef
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.snapshot.registry import default_registry
from squadron.metrology.snapshot.runner import SubprocessToolRunner
from squadron.metrology.snapshot_models import SourceLanguage
from squadron.replay.judging import JudgeReply
from tests.benchmark.diff_judge_run_support import MemorySidecars
from tests.benchmark.slice_case_support import usage
from tests.benchmark.slice_pipeline_support import (
    BENCHMARK_ID,
    CONFIGS,
    GIT_TIMEOUT_S,
    PROFILE,
    SliceWorld,
)
from tests.benchmark.test_grade_identity import make_reviewer

LANGUAGE = SourceLanguage.PYTHON
FLOOR_RUNS = 2
RUN_CAP_USD = 5.0
REVIEW_COST_USD = 0.1
JUDGE_CAP_USD = 2.0
JUDGE_CALL_USD = 0.04
JUDGE_LIMIT_CHARS = 400000
JUDGE_TIMEOUT_S = 30.0
NOW = datetime(2026, 11, 15, tzinfo=UTC)
#: The reference's new function: the scripted judge prefers the side whose diff has it.
REFERENCE_MARKER = "+def mul("
IMPLEMENTATION_B_HEADING = "## Implementation B"


class PreferenceDispatcher:
    """A judge that answers by content: the side holding ``REFERENCE_MARKER`` wins, and two
    sides that both hold it (or both lack it) tie. Records every prompt it was given."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def __call__(self, prompt: str) -> JudgeReply:
        self.prompts.append(prompt)
        side_a, side_b = prompt.split(IMPLEMENTATION_B_HEADING, 1)
        a_has, b_has = REFERENCE_MARKER in side_a, REFERENCE_MARKER in side_b
        winner = "A" if a_has and not b_has else "B" if b_has and not a_has else "TIE"
        return JudgeReply(f"Compared.\nWINNER: {winner}", usage(JUDGE_CALL_USD))


@dataclass(frozen=True)
class GradedRun:
    plan: GradePlan
    summary: GradeSummary
    lines: list[str]


@dataclass(frozen=True)
class Judged:
    plan: JudgePlan
    result: JudgeRunResult
    dispatcher: PreferenceDispatcher
    lines: list[str]


def benchmark_run(world: SliceWorld) -> BenchmarkRun:
    """The run record the three replays belong to (one case, one sample each)."""
    return BenchmarkRun(
        benchmark_id=BENCHMARK_ID,
        case_set="e2e-slices",
        case_set_version=1,
        configs=tuple(
            ProducerConfigRef(
                alias=config.alias,
                model=config.model,
                profile=config.profile,
                effort_sent=None,
                tool_use=True,
            )
            for config in CONFIGS
        ),
        samples=1,
        status=BenchmarkStatus.COMPLETE,
        run_cap_usd=20.0,
        per_replay_cap_usd=8.0,
        spent_usd=0.0,
        unpriced_replays=0,
        case_drops=(),
        started_at=NOW,
        updated_at=NOW,
    )


def scripted_review(tree: Path, base: str) -> ReviewOutcome:
    return ReviewOutcome(findings=(), unnormalized_count=0, cost_usd=REVIEW_COST_USD, rules_hash=None)


def collect_node_ids(sandbox: GradeSandbox, case: BenchmarkCase) -> tuple[str, ...]:
    return tuple(fix_case_adapter_for(LANGUAGE).collect(sandbox.context()).digests)


def grade_deps_for(world: SliceWorld, plan: GradePlan) -> Callable[[ReviewBudget], GradeDeps]:
    """The production ``GradeDeps`` of ``grade_services``, over the fixture's own sandboxes."""
    records = world.setup.records
    repo = world.setup.history.repo
    runner = SubprocessRunner()

    def make(budget: ReviewBudget) -> GradeDeps:
        return GradeDeps(
            grader=plan.grader,
            keep=False,
            git_timeout_s=GIT_TIMEOUT_S,
            sandbox_factory=lambda case: world.setup.deps.qualify.sandbox_factory(case.start_sha),
            grading_adapter_for=lambda case: grading_adapter_for(LANGUAGE),
            reviewer=scripted_review,
            budget=budget,
            collect_node_ids=collect_node_ids,
            measure_snapshot=make_snapshot_measurer(default_registry(), SubprocessToolRunner()),
            store=GradeRecordStore(records),
            repo_root_for=lambda case: repo,
            tree_reader_for=lambda case, sha: GitTreeReader(runner, repo, sha),
            process_runner=runner,
            clock=lambda: datetime.now(UTC),
        )

    return make


def grade_all(world: SliceWorld, lock_root: Path) -> tuple[GradePlan, GradeSummary, list[str]]:
    """Plan and run grading of the reference and every gradable replay."""
    records = world.setup.records
    plan = plan_grading(
        run=benchmark_run(world),
        cases={world.case.case_id: world.case},
        replays=records.replays_for(BENCHMARK_ID),
        store=GradeRecordStore(records),
        reviewer=make_reviewer(profile=PROFILE),
        review_floor_runs=FLOOR_RUNS,
        review_timeout_s=60.0,
        max_cost=RUN_CAP_USD,
        review_cost=REVIEW_COST_USD,
        repo_project_ids={world.case.project_id.value},
    )
    lines: list[str] = []
    runner = SubprocessRunner()
    summary = run_grading(
        plan,
        grade_deps_for(world, plan),
        lock_root=lock_root,
        process_runner=runner,
        print_line=lines.append,
        grade=grade_one,
    )
    return plan, summary, lines


def judge_all(world: SliceWorld, lock_root: Path) -> Judged:
    """Plan and run the pairwise judging with the scripted dispatcher."""
    records: BenchmarkRecordStore = world.setup.records
    runner = SubprocessRunner()
    repo_projects = {world.case.project_id.value: world.setup.history.repo}
    judge = ResolvedJudge(
        JudgeRef(
            alias="gpt-judge", model="gpt-x", prompt_hash=diff_judge_prompt_hash(), effort_sent=None
        ),
        PROFILE,
    )
    plan = plan_judge(
        run=benchmark_run(world),
        cases={world.case.case_id: world.case},
        replays=records.replays_for(BENCHMARK_ID),
        judge=judge,
        limit=JUDGE_LIMIT_CHARS,
        max_cost=JUDGE_CAP_USD,
        judge_cost=JUDGE_CALL_USD,
        observed_cost=None,
        recorded_ids=(),
        repo_projects=set(repo_projects),
        reference_diff_for=ReferenceDiffReader(runner, repo_projects, GIT_TIMEOUT_S),
        diff_of=lambda ref: records.diffs.get(ref.sha256),
    )
    dispatcher = PreferenceDispatcher()
    lines: list[str] = []
    result = run_judging(
        plan,
        store=SliceCaseRecordStore(records),
        sidecars=MemorySidecars(),
        dispatcher=dispatcher,
        timeout_s=JUDGE_TIMEOUT_S,
        lock_root=lock_root,
        process_runner=runner,
        print_line=lines.append,
        clock=lambda: NOW,
    )
    return Judged(plan, result, dispatcher, lines)


def report_of(world: SliceWorld) -> BenchmarkReport:
    """The benchmark's report from the stored records, as ``sq benchmark report`` builds it."""
    records = world.setup.records
    grades = GradeRecordStore(records)
    slice_store = SliceCaseRecordStore(records)
    stored = [grade for _, grade in grades.grades_for(BENCHMARK_ID)]
    grader = stored[0].grader
    return build_report(
        run=benchmark_run(world),
        cases={world.case.case_id: world.case},
        case_ids=[world.case.case_id],
        replays=records.replays_for(BENCHMARK_ID),
        grades=stored,
        grader=grader,
        reference_for=lambda case_id, digest: grades.get_reference_grade(
            case_id, grader.digest, digest
        ),
        estimate=None,
        judgments=slice_store.diff_judgments_for(BENCHMARK_ID),
        over_size=slice_store.over_size_cases_for(BENCHMARK_ID),
    )
