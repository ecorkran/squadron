"""Load test: the diff judge over a 200-pair plan (slice 426, Task 33).

Required by the load-test tier: the judge's calls are a network path. A long plan must run
its calls one at a time with a slow dispatcher, stop at the run cap keeping every record, and
cut a hung call at ``timeout_s`` so the run still finishes.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pytest

from squadron.benchmark.diff_judge_runner import JudgeStatus
from tests.benchmark.diff_judge_run_support import (
    PER_CALL,
    ScriptedDispatcher,
    World,
    make_world,
    plan_of,
    run_plan,
)

ALIASES = {name: 20 for name in ("a", "b", "c", "d")}  # 20·C(4,2) + 20·4 = 200 pairs
CALL_DELAY_S = 0.002
BOUND_S = 60.0


def _world(tmp_path: Path) -> World:
    return make_world(tmp_path, cases={"big": ALIASES})


def test_a_200_pair_plan_runs_its_calls_one_at_a_time(tmp_path: Path) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=1000.0)
    assert plan.pairs == 200 and plan.calls == 400
    dispatcher = ScriptedDispatcher(delay_s=CALL_DELAY_S)

    started = time.monotonic()
    result, _ = run_plan(world, plan, dispatcher, lock_root=tmp_path / "locks")
    elapsed = time.monotonic() - started

    assert result.status is JudgeStatus.COMPLETE
    assert result.summary.judged == 200
    assert dispatcher.max_in_flight == 1
    assert elapsed < BOUND_S
    assert len(world.store.diff_judgments_for(world.run.benchmark_id)) == 200


def test_the_cap_stops_a_long_plan_and_keeps_every_record(tmp_path: Path) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=0.78)  # the 20th call, at $0.04, crosses it
    dispatcher = ScriptedDispatcher(delay_s=CALL_DELAY_S)

    result, _ = run_plan(world, plan, dispatcher, lock_root=tmp_path / "locks")

    assert result.status is JudgeStatus.CAP_REACHED
    assert len(dispatcher.prompts) == 20  # the call that crossed the cap was the last
    assert result.spent_usd == pytest.approx(20 * PER_CALL)
    assert result.summary.judged == 10
    assert len(world.store.diff_judgments_for(world.run.benchmark_id)) == 10


def test_a_hung_call_is_cut_at_the_timeout_and_the_run_finishes(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = make_world(tmp_path, cases={"small": {"a": 2, "b": 2}})
    plan = plan_of(world, max_cost=1000.0)
    dispatcher = ScriptedDispatcher(hang_calls={3})  # the first call of the second pair hangs

    started = time.monotonic()
    with caplog.at_level(logging.ERROR):
        result, _ = run_plan(world, plan, dispatcher, lock_root=tmp_path / "locks", timeout_s=0.2)

    assert time.monotonic() - started < 10.0
    assert result.status is JudgeStatus.COMPLETE
    assert (result.summary.failed, result.summary.judged) == (1, plan.pairs - 1)
    assert len(world.store.diff_judgments_for(world.run.benchmark_id)) == plan.pairs - 1
    assert any(r.levelno == logging.ERROR and "exceeded" in r.getMessage() for r in caplog.records)
