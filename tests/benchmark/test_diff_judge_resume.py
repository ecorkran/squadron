"""Lock, resume and over-size records (slice 426, Task 34)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.diff_judge_plan import JudgeHalted, JudgeRefusal
from squadron.benchmark.diff_judge_runner import JUDGE_LOCK_SUFFIX, judge_lock_path
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.slice_case_models import DiffJudgment, OverSizeCase
from tests.benchmark.diff_judge_run_support import (
    ScriptedDispatcher,
    World,
    case_named,
    make_world,
    plan_of,
    run_plan,
)
from tests.benchmark.diff_judge_support import diff_text

SMALL_LIMIT = 4000


def _world(tmp_path: Path) -> World:
    return make_world(tmp_path, cases={"a": {"opus": 1, "sol": 1}, "b": {"opus": 1, "sol": 1}})


def test_a_rerun_skips_judged_pairs_and_judges_the_rest(tmp_path: Path) -> None:
    world = _world(tmp_path)
    plan = plan_of(world, max_cost=0.10)
    first = ScriptedDispatcher()
    result, _ = run_plan(world, plan, first, lock_root=tmp_path / "locks")
    assert result.summary.judged == 1  # the cap stopped it after one pair
    recorded = len(world.store.diff_judgments_for(world.run.benchmark_id))

    second = ScriptedDispatcher()
    rest, _ = run_plan(world, plan_of(world, max_cost=8.0), second, lock_root=tmp_path / "locks")

    assert rest.summary.judged == 5  # six pairs in all, one already recorded
    assert len(second.prompts) == 10
    assert len(world.store.diff_judgments_for(world.run.benchmark_id)) == recorded + 5


def test_a_held_lock_refuses_naming_the_lock_file_and_logs_a_warning(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = _world(tmp_path)
    locks = tmp_path / "locks"
    held = BenchmarkLock.acquire(
        locks, f"{world.run.benchmark_id}{JUDGE_LOCK_SUFFIX}", SubprocessRunner()
    )
    try:
        with caplog.at_level(logging.WARNING), pytest.raises(JudgeRefusal) as refused:
            run_plan(world, plan_of(world), ScriptedDispatcher(), lock_root=locks)
    finally:
        held.release()

    lock_file = judge_lock_path(locks, world.run.benchmark_id)
    assert str(lock_file) in str(refused.value)
    assert any(
        r.levelno >= logging.WARNING and str(lock_file) in r.getMessage() for r in caplog.records
    )
    assert not lock_file.exists()  # released by its owner, never left by the refused run


def test_the_lock_is_released_when_the_run_ends(tmp_path: Path) -> None:
    world = _world(tmp_path)
    locks = tmp_path / "locks"

    run_plan(world, plan_of(world), ScriptedDispatcher(), lock_root=locks)

    assert not judge_lock_path(locks, world.run.benchmark_id).exists()


def test_an_over_size_record_is_replaced_when_the_limit_changes(tmp_path: Path) -> None:
    world = _world(tmp_path)
    world.reference_diffs[case_named(world, 0).case_id] = b"".join(
        diff_text(f"big{n}") for n in range(200)
    )

    run_plan(world, plan_of(world, limit=SMALL_LIMIT), ScriptedDispatcher(), lock_root=tmp_path / "l")
    run_plan(
        world, plan_of(world, limit=SMALL_LIMIT + 7), ScriptedDispatcher(), lock_root=tmp_path / "l"
    )

    (record,) = world.store.over_size_cases_for(world.run.benchmark_id)
    assert record.max_prompt_chars == SMALL_LIMIT + 7
    assert record.case_id == case_named(world, 0).case_id


def test_a_case_that_fits_after_the_limit_rises_is_judged_on_the_rerun(tmp_path: Path) -> None:
    world = _world(tmp_path)
    big = case_named(world, 0)
    world.reference_diffs[big.case_id] = b"".join(diff_text(f"big{n}") for n in range(200))
    run_plan(world, plan_of(world, limit=SMALL_LIMIT), ScriptedDispatcher(), lock_root=tmp_path / "l")
    assert not [
        j for j in world.store.diff_judgments_for(world.run.benchmark_id) if j.case_id == big.case_id
    ]

    run_plan(world, plan_of(world), ScriptedDispatcher(), lock_root=tmp_path / "l")

    judged = [
        j for j in world.store.diff_judgments_for(world.run.benchmark_id) if j.case_id == big.case_id
    ]
    assert judged  # the stale over-size record stays; the report's rule counts it as judged


class _FailingStore:
    """A store whose writes fail: judgments after ``allow`` of them, over-size at once."""

    def __init__(self, allow: int = 0, over_size: bool = False) -> None:
        self.written: list[DiffJudgment] = []
        self._allow = allow
        self._over_size = over_size

    def write_diff_judgment(self, judgment: DiffJudgment) -> str:
        if len(self.written) >= self._allow:
            raise MetrologyStoreError("disk full")
        self.written.append(judgment)
        return judgment.record_id

    def write_over_size_case(self, over_size: OverSizeCase) -> str:
        if self._over_size:
            raise MetrologyStoreError("disk full")
        return over_size.record_id


def test_a_judgment_write_failure_stops_the_run_with_an_error_log(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = _world(tmp_path)
    store = _FailingStore(allow=1)
    dispatcher = ScriptedDispatcher()

    with caplog.at_level(logging.ERROR), pytest.raises(JudgeHalted, match="disk full"):
        run_plan(world, plan_of(world), dispatcher, lock_root=tmp_path / "l", store=store)

    assert len(store.written) == 1
    assert len(dispatcher.prompts) == 4  # the second pair was judged, then its write failed
    assert any(r.levelno == logging.ERROR for r in caplog.records)
    assert not judge_lock_path(tmp_path / "l", world.run.benchmark_id).exists()


def test_an_over_size_write_failure_halts_before_any_call(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    world = _world(tmp_path)
    world.reference_diffs[case_named(world, 0).case_id] = b"".join(
        diff_text(f"big{n}") for n in range(200)
    )
    dispatcher = ScriptedDispatcher()

    with caplog.at_level(logging.ERROR), pytest.raises(JudgeHalted, match="over-size"):
        run_plan(
            world,
            plan_of(world, limit=SMALL_LIMIT),
            dispatcher,
            lock_root=tmp_path / "l",
            store=_FailingStore(allow=99, over_size=True),
        )

    assert dispatcher.prompts == []
    assert any(r.levelno == logging.ERROR for r in caplog.records)
