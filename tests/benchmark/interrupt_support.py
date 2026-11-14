"""Shared scenario and child entry point for the killed-benchmark test (slice 424 Task 31).

The child process runs ``child_main`` under ``python -I`` (so nothing from the test process's
environment leaks in); the parent builds the same scenario with ``scenario`` and checks what
the killed child left behind. Fake replays write real records into the real store, so what
survives the kill is exactly what a real interrupted benchmark would leave.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from squadron.benchmark.bench_plan import (
    BenchConfig,
    BenchmarkPlan,
    Caps,
    build_plan,
    config_key,
    replay_record_id,
)
from squadron.benchmark.bench_runner import begin_benchmark, run_benchmark
from squadron.core.process_lock import current_process_lock
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_models import CaseDrop, ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.metrology.store import MetrologyStore

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
CONFIG = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
CONFIG_REF = ProducerConfigRef(alias="opus", model="claude-opus-5-5", profile="sdk", effort_sent=None)
CAPS = Caps(run_cap_usd=100.0, per_replay_cap_usd=1.5, per_replay_source="--max-cost-per-replay")
CASE_COUNT = 3
#: The replay (0-based) during which the child blocks and is killed.
BLOCKING_REPLAY_INDEX = 1
CHILD_SANDBOX = "sandbox-child"


@dataclass(frozen=True)
class Scenario:
    plan: BenchmarkPlan
    cases: dict[str, BenchmarkCase]
    store: BenchmarkRecordStore


def scenario(store_dir: Path) -> Scenario:
    from tests.benchmark.test_fix_case_runner import fix_case

    cases = {c.case_id: c for c in (fix_case(task=f"issue {n}") for n in range(CASE_COUNT))}
    plan = build_plan(
        set_name="fixes", set_version=1, case_ids=list(cases), configs=[CONFIG], samples=1,
        existing_record_ids=[],
    )  # fmt: skip
    return Scenario(plan, cases, BenchmarkRecordStore(MetrologyStore(store_dir=store_dir)))


def record_for(plan: BenchmarkPlan, store: BenchmarkRecordStore, case: BenchmarkCase) -> str:
    """Write a committed replay of *case* and return its record id."""
    from tests.metrology.test_benchmark_replay_models import _replay as make_replay

    record_id = replay_record_id(plan.benchmark_id, case.case_id, config_key(CONFIG), 0)
    replay: ImplementationReplay = make_replay().model_copy(
        update={
            "benchmark_id": plan.benchmark_id,
            "case_id": case.case_id,
            "sample": 0,
            "run_id": record_id,
            "cost_usd": 0.5,
        }
    )
    store.write_replay(record_id, replay)
    return record_id


def child_main(arguments: list[str]) -> None:
    """Begin the benchmark and run it, blocking forever inside the second replay."""
    store_dir, root, ready_file = (Path(argument) for argument in arguments)
    world = scenario(store_dir)
    runner = SubprocessRunner()
    calls: list[str] = []

    def replay(
        case: BenchmarkCase, config: BenchConfig, sample: int
    ) -> ImplementationReplay | CaseDrop:
        if len(calls) == BLOCKING_REPLAY_INDEX:
            # What a real replay holds while it runs: a sandbox tree with its own lock.
            (root / CHILD_SANDBOX).mkdir()
            (root / f"{CHILD_SANDBOX}.home").mkdir()
            (root / f"{CHILD_SANDBOX}.lock").write_text(current_process_lock(runner).to_json())
            ready_file.write_text("blocked")
            time.sleep(3600)
        calls.append(case.case_id)
        record_for(world.plan, world.store, case)
        return world.store.get_replay(
            replay_record_id(world.plan.benchmark_id, case.case_id, config_key(config), sample)
        )  # type: ignore[return-value]

    started = begin_benchmark(
        plan=world.plan, config_refs=[CONFIG_REF], caps=CAPS, store=world.store, root=root,
        process_runner=runner, sweep=lambda r, p: None, report=lambda message: None,
        print_bound=lambda: None, clock=lambda: NOW,
    )  # fmt: skip
    run_benchmark(
        started, world.plan, world.cases, replay, world.store, lambda: NOW, lambda p, r: None
    )  # fmt: skip
