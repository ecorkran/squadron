"""``begin_benchmark``: the lock, interruption, sweep and the order of bound and record."""

from __future__ import annotations

import hashlib
import logging
import os
import shutil
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.bench_lock import GUARD_SUFFIX, BenchmarkLock
from squadron.benchmark.bench_plan import (
    BenchConfig,
    BenchmarkPlan,
    BenchmarkRefusal,
    Caps,
    build_plan,
    format_bound,
)
from squadron.benchmark.bench_runner import begin_benchmark
from squadron.core.process_runner import SubprocessRunner
from squadron.metrology.benchmark_replay_enums import BenchmarkStatus
from squadron.metrology.benchmark_replay_models import BenchmarkRun
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.replay_models import ProducerConfigRef
from squadron.metrology.store import MetrologyStore

NOW = datetime(2026, 11, 14, 12, tzinfo=UTC)
CAPS = Caps(run_cap_usd=40.0, per_replay_cap_usd=1.5, per_replay_source="--max-cost-per-replay")
OPUS = BenchConfig("opus", "claude-opus-5-5", "sdk", "high")
OPUS_REF = ProducerConfigRef(alias="opus", model="claude-opus-5-5", profile="sdk", effort_sent=None)


def _plan() -> BenchmarkPlan:
    case_ids = [f"case-{hashlib.sha256(str(n).encode()).hexdigest()[:16]}" for n in range(2)]
    return build_plan(
        set_name="fixes",
        set_version=1,
        case_ids=case_ids,
        configs=[OPUS],
        samples=2,
        existing_record_ids=(),
    )


class Events:
    """An ordered log shared by the doubles."""

    def __init__(self) -> None:
        self.log: list[str] = []

    def add(self, event: str) -> None:
        self.log.append(event)


class SpyStore(BenchmarkRecordStore):
    def __init__(self, store: MetrologyStore, events: Events) -> None:
        super().__init__(store)
        self._events = events

    def write_run(self, run: BenchmarkRun) -> str:
        self._events.add(f"write_run:{run.status.value}")
        return super().write_run(run)


class Env:
    def __init__(self, tmp_path: Path) -> None:
        self.root = tmp_path / "bench-root"
        self.events = Events()
        self.store = SpyStore(MetrologyStore(store_dir=tmp_path / "store"), self.events)
        self.reports: list[str] = []
        self.runner = SubprocessRunner()
        self.plan = _plan()
        self.swept_dirs: list[str] = []
        self.bound_seen_status: BenchmarkStatus | None = None

    def sweep(self, runner: Any, root: Path) -> None:
        self.events.add("sweep")
        for name in self.swept_dirs:
            shutil.rmtree(root / name, ignore_errors=True)
            shutil.rmtree(root / f"{name}.home", ignore_errors=True)

    def report(self, message: str) -> None:
        self.reports.append(message)
        self.events.add(f"report:{message}")

    def print_bound(self) -> None:
        stored = self.store.get_run(self.plan.benchmark_id)
        self.bound_seen_status = None if stored is None else stored.status
        self.events.add("bound")

    def begin(self, plan: BenchmarkPlan | None = None, caps: Caps = CAPS) -> Any:
        return begin_benchmark(
            plan=plan or self.plan,
            config_refs=[OPUS_REF],
            caps=caps,
            store=self.store,
            root=self.root,
            process_runner=self.runner,
            sweep=self.sweep,
            report=self.report,
            print_bound=self.print_bound,
            clock=lambda: NOW,
        )

    def stored_run(self, status: BenchmarkStatus, **updates: Any) -> BenchmarkRun:
        run = BenchmarkRun(
            benchmark_id=self.plan.benchmark_id,
            case_set="fixes",
            case_set_version=1,
            configs=(OPUS_REF,),
            samples=2,
            status=status,
            run_cap_usd=10.0,
            per_replay_cap_usd=1.0,
            spent_usd=7.25,
            unpriced_replays=2,
            case_drops=(),
            started_at=NOW - timedelta(days=1),
            updated_at=NOW - timedelta(days=1),
        )
        run = run.model_copy(update=updates)
        self.store.write_run(run)
        self.events.log.clear()
        return run

    def lock_file(self) -> Path:
        return self.root / f"{self.plan.benchmark_id}.lock"


@pytest.fixture
def env(tmp_path: Path) -> Env:
    return Env(tmp_path)


class TestLock:
    def test_second_invocation_while_the_lock_is_held_refuses_and_the_first_is_unaffected(
        self, env: Env
    ) -> None:
        first = env.begin()
        owner_before = env.lock_file().read_text()
        with pytest.raises(BenchmarkRefusal) as raised:
            env.begin()
        assert env.plan.benchmark_id in str(raised.value)
        assert str(first.lock.owner.pid) in str(raised.value)
        assert env.lock_file().read_text() == owner_before
        stored = env.store.get_run(env.plan.benchmark_id)
        assert stored is not None and stored.status == BenchmarkStatus.RUNNING
        first.lock.release()
        assert not env.lock_file().exists()

    def test_a_lock_whose_owner_is_gone_is_taken_over(
        self, env: Env, caplog: pytest.LogCaptureFixture
    ) -> None:
        env.root.mkdir(parents=True)
        env.lock_file().write_text('{"pid": 999999999, "started_at": 1.0}')
        with caplog.at_level(logging.WARNING):
            started = env.begin()
        assert started.lock.owner.pid != 999999999
        assert any("no longer running" in record.message for record in caplog.records)
        started.lock.release()

    def test_an_unreadable_lock_is_taken_over(self, env: Env) -> None:
        env.root.mkdir(parents=True)
        env.lock_file().write_text("not json")
        env.begin().lock.release()

    def test_the_lock_never_exists_without_its_owner(
        self, env: Env, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # A process reading the lock mid-create must not see an empty file and take it over.
        real_link = os.link
        seen: list[str] = []

        def checking_link(source: Any, target: Any) -> None:
            seen.append(f"before:{Path(target).exists()}:{Path(source).read_text() != ''}")
            real_link(source, target)
            seen.append(f"after:{Path(target).read_text() != ''}")

        monkeypatch.setattr("squadron.benchmark.bench_lock.os.link", checking_link)
        env.begin().lock.release()
        assert seen == ["before:False:True", "after:True"]
        assert not list(env.root.glob("*.tmp"))

    def test_taking_over_a_stale_lock_is_serialized_across_acquirers(self, env: Env) -> None:
        # Many acquirers race for one stale lock: exactly one may end up holding it.
        env.root.mkdir(parents=True)
        env.lock_file().write_text('{"pid": 999999999, "started_at": 1.0}')
        held: list[BenchmarkLock] = []
        refused: list[BenchmarkRefusal] = []
        barrier = threading.Barrier(8)

        def contend() -> None:
            barrier.wait()
            try:
                held.append(BenchmarkLock.acquire(env.root, env.plan.benchmark_id, env.runner))
            except BenchmarkRefusal as exc:
                refused.append(exc)

        threads = [threading.Thread(target=contend) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)
        assert (len(held), len(refused)) == (1, 7)
        held[0].release()

    def test_an_acquirer_waits_while_another_holds_the_acquisition_guard(self, env: Env) -> None:
        import fcntl

        env.root.mkdir(parents=True)
        guard_path = env.root / f"{env.plan.benchmark_id}.lock{GUARD_SUFFIX}"
        done = threading.Event()
        taken: list[BenchmarkLock] = []

        def acquire() -> None:
            taken.append(BenchmarkLock.acquire(env.root, env.plan.benchmark_id, env.runner))
            done.set()

        with guard_path.open("a") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX)
            thread = threading.Thread(target=acquire)
            thread.start()
            assert not done.wait(timeout=0.5)  # blocked on the guard
        assert done.wait(timeout=30)
        thread.join(timeout=30)
        taken[0].release()

    def test_the_lock_is_a_context_manager(self, env: Env) -> None:
        with BenchmarkLock.acquire(env.root, "bench-x", env.runner):
            assert (env.root / "bench-x.lock").exists()
        assert not (env.root / "bench-x.lock").exists()

    def test_a_refused_start_does_not_touch_a_running_record_with_a_live_owner(self, env: Env) -> None:
        holder = BenchmarkLock.acquire(env.root, env.plan.benchmark_id, env.runner)
        env.stored_run(BenchmarkStatus.RUNNING)
        with pytest.raises(BenchmarkRefusal):
            env.begin()
        stored = env.store.get_run(env.plan.benchmark_id)
        assert stored is not None and stored.status == BenchmarkStatus.RUNNING
        assert env.events.log == []
        holder.release()

    def test_the_lock_is_released_when_the_start_fails_after_taking_it(self, env: Env) -> None:
        def boom() -> None:
            raise RuntimeError("printer failed")

        with pytest.raises(RuntimeError, match="printer failed"):
            begin_benchmark(
                plan=env.plan, config_refs=[OPUS_REF], caps=CAPS, store=env.store, root=env.root,
                process_runner=env.runner, sweep=env.sweep, report=env.report,
                print_bound=boom, clock=lambda: NOW,
            )  # fmt: skip
        assert not env.lock_file().exists()
        assert env.store.get_run(env.plan.benchmark_id) is None


class TestInterruption:
    def test_a_running_record_with_a_free_lock_becomes_interrupted_then_running(self, env: Env) -> None:
        env.stored_run(BenchmarkStatus.RUNNING)
        started = env.begin()
        assert started.was_interrupted
        assert any("interrupted" in report for report in env.reports)
        assert env.events.log.index("write_run:interrupted") < env.events.log.index("bound")
        assert env.bound_seen_status == BenchmarkStatus.INTERRUPTED
        assert env.events.log[-1] == "write_run:running"
        started.lock.release()

    @pytest.mark.parametrize(
        "status", [BenchmarkStatus.COMPLETE, BenchmarkStatus.PARTIAL, BenchmarkStatus.INTERRUPTED]
    )
    def test_other_stored_statuses_are_not_reported_as_interrupted(
        self, env: Env, status: BenchmarkStatus
    ) -> None:
        env.stored_run(status)
        started = env.begin()
        assert not started.was_interrupted
        assert "write_run:interrupted" not in env.events.log
        started.lock.release()

    def test_a_first_run_has_no_interruption(self, env: Env) -> None:
        started = env.begin()
        assert not started.was_interrupted
        started.lock.release()


class TestRunningRecord:
    def test_new_caps_are_recorded_and_earlier_spend_is_carried(self, env: Env) -> None:
        previous = env.stored_run(BenchmarkStatus.PARTIAL)
        caps = Caps(run_cap_usd=99.0, per_replay_cap_usd=3.0, per_replay_source="--max-cost-per-replay")
        started = env.begin(caps=caps)
        run = started.run
        assert (run.run_cap_usd, run.per_replay_cap_usd) == (99.0, 3.0)
        assert (run.spent_usd, run.unpriced_replays) == (7.25, 2)
        assert run.started_at == previous.started_at
        assert run.updated_at == NOW
        assert run.status == BenchmarkStatus.RUNNING
        assert env.store.get_run(env.plan.benchmark_id) == run
        started.lock.release()

    def test_a_first_run_starts_at_zero_spend(self, env: Env) -> None:
        started = env.begin()
        assert (started.run.spent_usd, started.run.unpriced_replays) == (0.0, 0)
        assert started.run.started_at == NOW
        started.lock.release()

    def test_case_drops_do_not_carry_over(self, env: Env) -> None:
        from squadron.metrology.benchmark_replay_models import CaseDrop

        drop = CaseDrop(case_id="case-aaaaaaaaaaaaaaaa", reason="x", environment_digest="d")
        env.stored_run(BenchmarkStatus.PARTIAL, case_drops=(drop,))
        started = env.begin()
        assert started.run.case_drops == ()
        started.lock.release()


class TestSweep:
    def test_the_count_of_removed_sandboxes_is_reported(self, env: Env) -> None:
        for name in ("sandbox-a", "sandbox-b", "sandbox-c"):
            (env.root / name).mkdir(parents=True)
            (env.root / f"{name}.home").mkdir()
            (env.root / f"{name}.out").mkdir()
        env.swept_dirs = ["sandbox-a", "sandbox-b"]
        started = env.begin()
        assert started.swept_sandboxes == 2
        assert "swept 2 orphaned sandboxes" in env.reports
        started.lock.release()

    def test_nothing_to_sweep_is_reported_as_zero(self, env: Env) -> None:
        started = env.begin()
        assert started.swept_sandboxes == 0
        assert "swept 0 orphaned sandboxes" in env.reports
        started.lock.release()

    def test_one_removal_reads_in_the_singular(self, env: Env) -> None:
        (env.root / "sandbox-a").mkdir(parents=True)
        env.swept_dirs = ["sandbox-a"]
        env.begin().lock.release()
        assert "swept 1 orphaned sandbox" in env.reports


class TestOrder:
    def test_the_bound_is_printed_before_running_is_written_and_before_any_invoker_call(
        self, env: Env
    ) -> None:
        started = env.begin()
        env.events.add("invoker call")
        log = env.events.log
        assert log.index("sweep") < log.index("bound") < log.index("write_run:running")
        assert log.index("write_run:running") < log.index("invoker call")
        assert env.bound_seen_status is None  # no run record existed when the bound printed
        started.lock.release()

    def test_the_real_bound_text_can_be_printed_from_the_callback(self, env: Env) -> None:
        printed: list[str] = []
        started = begin_benchmark(
            plan=env.plan, config_refs=[OPUS_REF], caps=CAPS, store=env.store, root=env.root,
            process_runner=env.runner, sweep=env.sweep, report=env.report,
            print_bound=lambda: printed.append(format_bound(env.plan, CAPS, ("sdk",), frozenset())),
            clock=lambda: NOW,
        )  # fmt: skip
        assert "pending 4 of 4 replays" in printed[0]
        started.lock.release()
