"""A stored benchmark of slice cases and the plumbing to plan and run a judge over it
(slice 426, Tasks 31-35)."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.diff_judge_plan import JudgePlan, ResolvedJudge, plan_judge
from squadron.benchmark.diff_judge_runner import JudgeRunResult, run_judging
from squadron.benchmark.diff_pairs import ReplayInput
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.slice_case_models import diff_judgment_id
from squadron.metrology.slice_case_store import SliceCaseRecordStore
from squadron.metrology.store import MetrologyStore
from squadron.replay.judging import JudgeCallError, JudgeReply
from tests.benchmark.diff_judge_support import diff_reader, diff_text, replay_input
from tests.benchmark.slice_case_support import PROJECT, judge_ref, usage
from tests.benchmark.slice_runner_support import slice_case
from tests.benchmark.test_grade_plan import make_run

NOW = datetime(2026, 11, 15, tzinfo=UTC)
LIMIT = 400000
JUDGE = ResolvedJudge(judge_ref(), "openai-oauth")
PER_CALL = 0.04


class ScriptedDispatcher:
    """Answers ``WINNER: A`` to every prompt at ``cost`` per call; scripted calls fail or hang."""

    def __init__(
        self,
        cost: float | None = PER_CALL,
        fail_calls: Collection[int] = (),
        hang_calls: Collection[int] = (),
        delay_s: float = 0.0,
    ) -> None:
        self.prompts: list[str] = []
        self.events: list[str] = []
        self._cost = cost
        self._fail = set(fail_calls)
        self._hang = set(hang_calls)
        self._delay_s = delay_s
        self.in_flight = 0
        self.max_in_flight = 0

    async def __call__(self, prompt: str) -> JudgeReply:
        self.prompts.append(prompt)
        self.events.append("call")
        number = len(self.prompts)
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        try:
            if number in self._hang:
                await asyncio.sleep(60)
            if self._delay_s:
                await asyncio.sleep(self._delay_s)
            if number in self._fail:
                raise JudgeCallError("provider down")
            return JudgeReply("Fine.\nWINNER: A", None if self._cost is None else usage(self._cost))
        finally:
            self.in_flight -= 1


class MemorySidecars:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}

    def put(self, data: bytes) -> str:
        digest = hashlib.sha256(data).hexdigest()
        self.files[digest] = data
        return digest


@dataclass
class World:
    run: BenchmarkRun
    cases: dict[str, BenchmarkCase]
    inputs: list[ReplayInput]
    store: SliceCaseRecordStore
    sidecars: MemorySidecars = field(default_factory=MemorySidecars)
    reference_diffs: dict[str, bytes] = field(default_factory=lambda: {})

    @property
    def replays(self) -> list[tuple[str, object]]:
        return [(item.record_id, item.replay) for item in self.inputs]


def make_world(
    tmp_path: Path,
    *,
    cases: Mapping[str, Mapping[str, int]],
    absent: Mapping[str, Mapping[str, ProducerOutcome]] | None = None,
) -> World:
    """``cases`` maps a case label to ``{alias: k}``; ``absent`` maps it to ``{alias: outcome}``
    for one extra absent sample each."""
    run = make_run("bench-3f9c0a1b2c3d4e5f")
    built: dict[str, BenchmarkCase] = {}
    inputs: list[ReplayInput] = []
    for label, aliases in cases.items():
        case = slice_case(task=f"## File: design for {label}\n")
        built[case.case_id] = case
        for alias, k in aliases.items():
            inputs += [replay_input(case, alias, sample) for sample in range(1, k + 1)]
        for alias, outcome in (absent or {}).get(label, {}).items():
            inputs.append(replay_input(case, alias, 1, outcome=outcome))
    store = SliceCaseRecordStore(BenchmarkRecordStore(MetrologyStore(store_dir=tmp_path / "store")))
    return World(run, built, inputs, store)


def case_named(world: World, index: int = 0) -> BenchmarkCase:
    return list(world.cases.values())[index]


def plan_of(world: World, **overrides: object) -> JudgePlan:
    """Plan the world's judge, with every input a default a test may override."""
    recorded = {
        j.record_id for j in world.store.diff_judgments_for(world.run.benchmark_id, JUDGE.ref.alias)
    }
    options: dict[str, object] = {
        "run": world.run,
        "cases": world.cases,
        "replays": world.replays,
        "judge": JUDGE,
        "limit": LIMIT,
        "max_cost": 8.0,
        "judge_cost": PER_CALL,
        "observed_cost": None,
        "recorded_ids": recorded,
        "repo_projects": {PROJECT.value},
        "reference_diff_for": lambda case: world.reference_diffs.get(
            case.case_id, diff_text("reference")
        ),
        "diff_of": diff_reader(world.inputs),
    }
    options.update(overrides)
    return plan_judge(**options)  # type: ignore[arg-type]


def run_plan(
    world: World,
    plan: JudgePlan,
    dispatcher: ScriptedDispatcher,
    *,
    lock_root: Path,
    timeout_s: float = 5.0,
    store: object | None = None,
) -> tuple[JudgeRunResult, list[str]]:
    lines: list[str] = []
    result = run_judging(
        plan,
        store=store or world.store,  # type: ignore[arg-type]
        sidecars=world.sidecars,
        dispatcher=dispatcher,
        timeout_s=timeout_s,
        lock_root=lock_root,
        process_runner=SubprocessRunner(),
        print_line=lines.append,
        clock=lambda: NOW,
    )
    return result, lines


def pair_ids(world: World, plan: JudgePlan) -> list[str]:
    return [
        diff_judgment_id(world.run.benchmark_id, cp.case.case_id, (p.a.ref, p.b.ref), plan.judge.ref)
        for cp in plan.cases
        for p in cp.pairs
    ]
