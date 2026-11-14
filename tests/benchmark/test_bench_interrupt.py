"""A benchmark killed by a real signal is reported interrupted and resumes (slice 424 Task 31)."""

from __future__ import annotations

import logging
import subprocess
import sys
import time
from pathlib import Path

import pytest

from squadron.benchmark.bench_plan import BenchConfig, build_plan
from squadron.benchmark.bench_runner import begin_benchmark, run_benchmark
from squadron.benchmark.sandbox import sweep_benchmark_orphans
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import BenchmarkStatus
from squadron.metrology.benchmark_replay_models import CaseDrop, ImplementationReplay
from tests.benchmark.interrupt_support import (
    CAPS,
    CHILD_SANDBOX,
    CONFIG,
    CONFIG_REF,
    NOW,
    record_for,
    scenario,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
READY_TIMEOUT_S = 120
CHILD_CODE = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "from tests.benchmark.interrupt_support import child_main; child_main(sys.argv[2:])"
)


def _wait_until(path: Path, child: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + READY_TIMEOUT_S
    while not path.exists():
        if child.poll() is not None:
            raise AssertionError(f"the child exited ({child.returncode}) before blocking")
        if time.monotonic() > deadline:
            raise AssertionError(f"the child did not block within {READY_TIMEOUT_S}s")
        time.sleep(0.05)


def test_a_killed_benchmark_is_reported_interrupted_and_resumes_with_the_remaining_replays(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    store_dir, root, ready = tmp_path / "store", tmp_path / "root", tmp_path / "ready"
    root.mkdir()
    child = subprocess.Popen(
        [sys.executable, "-I", "-c", CHILD_CODE, str(REPO_ROOT), str(store_dir), str(root), str(ready)]
    )
    try:
        _wait_until(ready, child)
        child.kill()  # SIGKILL: the child cannot clean anything up
        child.wait(timeout=30)
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=30)

    world = scenario(store_dir)
    stored = world.store.get_run(world.plan.benchmark_id)
    assert stored is not None and stored.status == BenchmarkStatus.RUNNING
    assert (root / CHILD_SANDBOX).is_dir()
    assert len(world.store.replays_for(world.plan.benchmark_id)) == 1

    reports: list[str] = []
    runner = SubprocessRunner()
    with caplog.at_level(logging.WARNING):
        started = begin_benchmark(
            plan=world.plan, config_refs=[CONFIG_REF], caps=CAPS, store=world.store, root=root,
            process_runner=runner, sweep=sweep_benchmark_orphans, report=reports.append,
            print_bound=lambda: None, clock=lambda: NOW,
        )  # fmt: skip
    assert started.was_interrupted
    assert any("interrupted" in message for message in reports)
    assert started.swept_sandboxes == 1
    assert "swept 1 orphaned sandbox" in reports
    assert not (root / CHILD_SANDBOX).exists()
    assert not (root / f"{CHILD_SANDBOX}.home").exists()

    # What the CLI does on the rerun: plan again, with the records the killed run left.
    pending_plan = build_plan(
        set_name="fixes", set_version=1, case_ids=list(world.cases), configs=[CONFIG], samples=1,
        existing_record_ids=[rid for rid, _ in world.store.replays_for(world.plan.benchmark_id)],
    )  # fmt: skip
    assert len(pending_plan.pending) == 2
    calls: list[str] = []

    def replay(
        case: BenchmarkCase, config: BenchConfig, sample: int
    ) -> ImplementationReplay | CaseDrop:
        calls.append(case.case_id)
        record_id = record_for(world.plan, world.store, case)
        stored_replay = world.store.get_replay(record_id)
        assert stored_replay is not None
        return stored_replay

    final = run_benchmark(
        started, pending_plan, world.cases, replay, world.store, lambda: NOW, lambda p, r: None
    )
    started.lock.release()
    assert calls == [r.case_id for r in world.plan.replays[1:]]
    assert final.status == BenchmarkStatus.COMPLETE
    assert len(world.store.replays_for(world.plan.benchmark_id)) == 3
    assert child.returncode is not None
    assert sorted(p.name for p in root.iterdir()) == []
