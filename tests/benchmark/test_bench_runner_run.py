"""``run_benchmark``: order, the spend cap, resume and what each outcome adds (slice 424)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from squadron.benchmark.bench_plan import (
    BenchConfig,
    BenchmarkPlan,
    Caps,
    PlannedReplay,
    build_plan,
    config_key,
    replay_record_id,
)
from squadron.benchmark.bench_runner import StartedBenchmark, begin_benchmark, run_benchmark
from squadron.metrology.benchmark_models import CandidateRejection
from squadron.metrology.benchmark_replay_enums import AbsenceClass, BenchmarkStatus, ProducerOutcome
from squadron.metrology.benchmark_replay_models import CaseDrop, ImplementationReplay
from tests.benchmark.test_bench_runner_begin import NOW, OPUS, OPUS_REF, Env
from tests.benchmark.test_fix_case_runner import fix_case
from tests.metrology.test_benchmark_replay_models import _replay as make_replay

SOL = BenchConfig("sol", "sol-model", "openai-oauth", None)
SOL_REF = OPUS_REF.model_copy(update={"alias": "sol", "profile": "openai-oauth"})


def caps(run_cap: float, per_replay: float = 1.5) -> Caps:
    return Caps(run_cap, per_replay, "--max-cost-per-replay")


class Scenario(Env):
    """An ``Env`` with real cases, a scripted replay function and a call log."""

    def __init__(self, tmp_path: Path, configs: list[BenchConfig], samples: int = 2) -> None:
        super().__init__(tmp_path)
        self.cases = {case.case_id: case for case in (fix_case(task=f"issue {n}") for n in range(2))}
        self.case_ids = list(self.cases)
        self.configs = configs
        self.samples = samples
        self.costs: dict[tuple[int, int, str], float | None] = {}
        self.default_cost: float | None = 1.0
        self.outcome = ProducerOutcome.COMMITTED
        self.drop_cases: set[str] = set()
        self.calls: list[tuple[str, int, str]] = []
        self.results: list[tuple[PlannedReplay, Any]] = []
        self.plan = self.make_plan()

    def make_plan(self) -> BenchmarkPlan:
        existing = [record_id for record_id, _ in self.store.replays_for(self._benchmark_id())]
        return build_plan(
            set_name="fixes",
            set_version=1,
            case_ids=self.case_ids,
            configs=self.configs,
            samples=self.samples,
            existing_record_ids=existing,
        )

    def _benchmark_id(self) -> str:
        return build_plan(
            set_name="fixes", set_version=1, case_ids=[], configs=self.configs,
            samples=self.samples, existing_record_ids=(),
        ).benchmark_id  # fmt: skip

    def replay(self, case: Any, config: BenchConfig, sample: int) -> ImplementationReplay | CaseDrop:
        self.calls.append((case.case_id, sample, config.alias))
        self.events.add(f"replay:{config.alias}:{sample}")
        if case.case_id in self.drop_cases:
            return CaseDrop(
                case_id=case.case_id,
                reason=CandidateRejection.NO_TEST_CHANGE,
                environment_digest="digest",
            )
        index = self.case_ids.index(case.case_id)
        cost = self.costs.get((index, sample, config.alias), self.default_cost)
        record_id = replay_record_id(self.plan.benchmark_id, case.case_id, config_key(config), sample)
        record = make_replay().model_copy(
            update={
                "benchmark_id": self.plan.benchmark_id,
                "case_id": case.case_id,
                "sample": sample,
                "run_id": record_id,
                "outcome": self.outcome,
                "absence": None if self.outcome is ProducerOutcome.COMMITTED else AbsenceClass.CONFIG,
                "cost_usd": cost,
            }
        )
        self.store.write_replay(record_id, record)
        return record

    def start(self, run_cap: float) -> StartedBenchmark:
        self.plan = self.make_plan()
        return begin_benchmark(
            plan=self.plan,
            config_refs=[OPUS_REF, SOL_REF][: len(self.configs)],
            caps=caps(run_cap),
            store=self.store,
            root=self.root,
            process_runner=self.runner,
            sweep=self.sweep,
            report=self.report,
            print_bound=self.print_bound,
            clock=lambda: NOW,
        )

    def run(self, run_cap: float):  # type: ignore[no-untyped-def]
        started = self.start(run_cap)
        try:
            return run_benchmark(
                started, self.plan, self.cases, self.replay, self.store, lambda: NOW,
                lambda planned, result: self.results.append((planned, result)),
            )  # fmt: skip
        finally:
            started.lock.release()


@pytest.fixture
def scenario(tmp_path: Path) -> Scenario:
    return Scenario(tmp_path, [OPUS, SOL])


class TestSpendIsPersistedAsItGoes:
    def test_the_stored_spend_is_current_before_the_next_replay_starts(
        self, scenario: Scenario
    ) -> None:
        stored_at_start: list[float] = []
        original = scenario.replay

        def observing(case: Any, config: BenchConfig, sample: int) -> Any:
            run = scenario.store.get_run(scenario.plan.benchmark_id)
            assert run is not None
            stored_at_start.append(run.spent_usd)
            return original(case, config, sample)

        started = scenario.start(run_cap=100)
        try:
            run_benchmark(
                started, scenario.plan, scenario.cases, observing, scenario.store,
                lambda: NOW, lambda planned, result: None,
            )  # fmt: skip
        finally:
            started.lock.release()
        assert stored_at_start[:4] == [0.0, 1.0, 2.0, 3.0]

    def test_a_failure_mid_run_keeps_the_spend_so_far(self, scenario: Scenario) -> None:
        calls = 0
        original = scenario.replay

        def failing(case: Any, config: BenchConfig, sample: int) -> Any:
            nonlocal calls
            calls += 1
            if calls == 3:
                raise RuntimeError("store failed")
            return original(case, config, sample)

        started = scenario.start(run_cap=100)
        try:
            with pytest.raises(RuntimeError):
                run_benchmark(
                    started, scenario.plan, scenario.cases, failing, scenario.store,
                    lambda: NOW, lambda planned, result: None,
                )  # fmt: skip
        finally:
            started.lock.release()
        run = scenario.store.get_run(scenario.plan.benchmark_id)
        assert run is not None
        assert (run.status, run.spent_usd) == (BenchmarkStatus.RUNNING, 2.0)


class TestOrder:
    def test_replays_run_case_major_then_sample_then_config(self, scenario: Scenario) -> None:
        first, second = scenario.case_ids
        scenario.run(run_cap=100)
        assert scenario.calls == [
            (first, 0, "opus"), (first, 0, "sol"), (first, 1, "opus"), (first, 1, "sol"),
            (second, 0, "opus"), (second, 0, "sol"), (second, 1, "opus"), (second, 1, "sol"),
        ]  # fmt: skip

    def test_a_complete_run_is_recorded_complete(self, scenario: Scenario) -> None:
        final = scenario.run(run_cap=100)
        assert final.status == BenchmarkStatus.COMPLETE
        assert scenario.store.get_run(final.benchmark_id) == final
        assert len(scenario.results) == 8


class TestSpendCap:
    def test_cap_reached_after_the_first_replay_stops_dispatching_and_keeps_records(
        self, scenario: Scenario
    ) -> None:
        scenario.default_cost = 1.0
        final = scenario.run(run_cap=1.0)
        assert len(scenario.calls) == 1
        assert final.status == BenchmarkStatus.PARTIAL
        assert final.spent_usd == pytest.approx(1.0)
        assert len(scenario.store.replays_for(final.benchmark_id)) == 1

    def test_a_replay_may_overshoot_and_the_next_is_not_started(self, scenario: Scenario) -> None:
        first = scenario.case_ids[0]
        scenario.costs = {(0, 0, "opus"): 0.9, (0, 0, "sol"): 1.5}
        final = scenario.run(run_cap=1.0)
        assert scenario.calls == [(first, 0, "opus"), (first, 0, "sol")]
        assert final.status == BenchmarkStatus.PARTIAL
        assert final.spent_usd == pytest.approx(2.4)

    def test_spend_below_the_cap_keeps_going(self, scenario: Scenario) -> None:
        scenario.default_cost = 0.1
        assert scenario.run(run_cap=100).status == BenchmarkStatus.COMPLETE

    def test_cap_reached_exactly_by_the_last_replay_is_still_complete(self, tmp_path: Path) -> None:
        scenario = Scenario(tmp_path, [OPUS], samples=1)
        scenario.default_cost = 1.0
        final = scenario.run(run_cap=2.0)
        assert len(scenario.calls) == 2
        assert final.status == BenchmarkStatus.COMPLETE

    def test_rerun_with_a_higher_cap_skips_recorded_replays_and_continues(
        self, scenario: Scenario
    ) -> None:
        first_run = scenario.run(run_cap=2.0)
        assert first_run.status == BenchmarkStatus.PARTIAL
        done = len(scenario.calls)
        scenario.calls.clear()
        scenario.default_cost = 0.5
        second = scenario.run(run_cap=100)
        assert second.status == BenchmarkStatus.COMPLETE
        assert len(scenario.calls) == 8 - done
        assert len(scenario.store.replays_for(second.benchmark_id)) == 8
        assert second.run_cap_usd == 100


class TestResume:
    @pytest.mark.parametrize(
        "outcome",
        [ProducerOutcome.COMMITTED, ProducerOutcome.NO_COMMIT, ProducerOutcome.ENVIRONMENT_FAILED],
    )
    def test_a_replay_with_a_record_is_skipped_whatever_its_outcome(
        self, scenario: Scenario, outcome: ProducerOutcome
    ) -> None:
        scenario.outcome = outcome
        scenario.run(run_cap=100)
        scenario.calls.clear()
        scenario.run(run_cap=100)
        assert scenario.calls == []

    def test_a_harness_absent_record_is_skipped_too(self, scenario: Scenario) -> None:
        scenario.outcome = ProducerOutcome.NO_RUN_STATE
        scenario.run(run_cap=100)
        scenario.calls.clear()
        final = scenario.run(run_cap=100)
        assert scenario.calls == [] and final.status == BenchmarkStatus.COMPLETE


class TestUnpriced:
    def test_unpriced_replays_are_counted_and_add_no_spend(self, scenario: Scenario) -> None:
        scenario.costs = {(0, 0, "sol"): None, (0, 1, "sol"): None}
        final = scenario.run(run_cap=100)
        assert final.unpriced_replays == 2
        assert final.spent_usd == pytest.approx(6.0)

    def test_unpriced_replays_never_trip_the_cap(self, scenario: Scenario) -> None:
        scenario.default_cost = None
        final = scenario.run(run_cap=0.01)
        assert final.status == BenchmarkStatus.COMPLETE
        assert len(scenario.calls) == 8 and final.spent_usd == 0.0

    def test_a_replay_that_never_ran_a_producer_is_not_unpriced(self, scenario: Scenario) -> None:
        scenario.outcome = ProducerOutcome.ENVIRONMENT_FAILED
        scenario.default_cost = None
        assert scenario.run(run_cap=100).unpriced_replays == 0


class TestAcrossInvocations:
    def test_spent_usd_adds_up_across_two_invocations(self, scenario: Scenario) -> None:
        scenario.default_cost = 1.0
        first = scenario.run(run_cap=2.0)
        second = scenario.run(run_cap=100)
        assert first.spent_usd == pytest.approx(2.0)
        assert second.spent_usd == pytest.approx(8.0)

    def test_the_run_cap_applies_to_each_invocation_not_the_total(self, scenario: Scenario) -> None:
        scenario.default_cost = 1.0
        scenario.run(run_cap=3.0)
        scenario.calls.clear()
        scenario.run(run_cap=3.0)
        assert len(scenario.calls) == 3

    def test_unpriced_count_follows_the_stored_records_after_a_harness_retry(
        self, scenario: Scenario
    ) -> None:
        scenario.default_cost = None
        scenario.outcome = ProducerOutcome.NO_RUN_STATE
        first = scenario.run(run_cap=100)
        assert first.unpriced_replays == 8
        harness_ids = [
            record_id
            for record_id, replay in scenario.store.replays_for(first.benchmark_id)
            if replay.outcome is ProducerOutcome.NO_RUN_STATE
        ]
        scenario.store.delete_replays(harness_ids)
        scenario.default_cost = 1.0
        scenario.outcome = ProducerOutcome.COMMITTED
        second = scenario.run(run_cap=100)
        # The deleted records no longer count; the new ones report a cost.
        assert second.unpriced_replays == 0

    def test_unpriced_counts_add_up_across_invocations(self, scenario: Scenario) -> None:
        # First invocation: opus is unpriced, then 1.0 + 1.0 reaches the cap of 2.0 after three replays.
        scenario.costs = {(0, 0, "opus"): None, (0, 0, "sol"): 1.0, (0, 1, "opus"): 1.0}
        first = scenario.run(run_cap=2.0)
        assert (len(scenario.calls), first.unpriced_replays) == (3, 1)
        # Second invocation: the five remaining replays are all unpriced.
        scenario.costs = {}
        scenario.default_cost = None
        second = scenario.run(run_cap=100)
        assert second.unpriced_replays == 6
        assert second.spent_usd == pytest.approx(first.spent_usd)


class TestCaseFilter:
    def test_case_filter_limits_the_plan_without_changing_the_benchmark_id(
        self, scenario: Scenario
    ) -> None:
        first = scenario.case_ids[0]
        full = scenario.plan
        limited = build_plan(
            set_name="fixes", set_version=1, case_ids=scenario.case_ids, configs=scenario.configs,
            samples=scenario.samples, existing_record_ids=(), only_cases=[first],
        )  # fmt: skip
        assert limited.benchmark_id == full.benchmark_id
        assert {r.case_id for r in limited.replays} == {first}
        assert len(limited.replays) == 4

    def test_records_made_under_a_filter_count_toward_the_full_benchmark(
        self, scenario: Scenario
    ) -> None:
        first = scenario.case_ids[0]
        scenario.plan = build_plan(
            set_name="fixes", set_version=1, case_ids=scenario.case_ids, configs=scenario.configs,
            samples=scenario.samples, existing_record_ids=(), only_cases=[first],
        )  # fmt: skip
        started = begin_benchmark(
            plan=scenario.plan, config_refs=[OPUS_REF, SOL_REF], caps=caps(100), store=scenario.store,
            root=scenario.root, process_runner=scenario.runner, sweep=scenario.sweep,
            report=scenario.report, print_bound=scenario.print_bound, clock=lambda: NOW,
        )  # fmt: skip
        run_benchmark(
            started, scenario.plan, scenario.cases, scenario.replay, scenario.store, lambda: NOW,
            lambda planned, result: None,
        )  # fmt: skip
        started.lock.release()
        full = scenario.make_plan()
        assert (len(full.replays), full.recorded, len(full.pending)) == (8, 4, 4)

    def test_an_unknown_case_is_refused(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_plan import BenchmarkRefusal

        with pytest.raises(BenchmarkRefusal, match="case-nope"):
            build_plan(
                set_name="fixes", set_version=1, case_ids=scenario.case_ids,
                configs=scenario.configs, samples=1, existing_record_ids=(),
                only_cases=["case-nope"],
            )  # fmt: skip


class TestSampleFilter:
    def test_sample_filter_limits_the_plan_without_changing_the_benchmark_id(
        self, scenario: Scenario
    ) -> None:
        full = scenario.plan
        limited = build_plan(
            set_name="fixes", set_version=1, case_ids=scenario.case_ids, configs=scenario.configs,
            samples=scenario.samples, existing_record_ids=(), only_samples=[0],
        )  # fmt: skip
        assert limited.benchmark_id == full.benchmark_id
        assert {r.sample for r in limited.replays} == {0}
        assert {r.record_id for r in limited.replays} < {r.record_id for r in full.replays}
        assert len(limited.replays) == 4

    def test_a_sample_outside_the_benchmark_is_refused(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_plan import BenchmarkRefusal

        with pytest.raises(BenchmarkRefusal, match="--sample"):
            build_plan(
                set_name="fixes", set_version=1, case_ids=scenario.case_ids,
                configs=scenario.configs, samples=2, existing_record_ids=(), only_samples=[2],
            )  # fmt: skip


class TestCaseDrops:
    def test_a_dropped_case_is_reported_once_and_none_of_its_replays_run(
        self, scenario: Scenario
    ) -> None:
        dropped, kept = scenario.case_ids
        scenario.drop_cases = {dropped}
        final = scenario.run(run_cap=100)
        assert {case_id for case_id, _, _ in scenario.calls if case_id == dropped} == {dropped}
        assert sum(1 for case_id, _, _ in scenario.calls if case_id == dropped) == 1
        assert {case_id for case_id, _, _ in scenario.calls} == {dropped, kept}
        reported_drops = [r for _, r in scenario.results if isinstance(r, CaseDrop)]
        assert [drop.case_id for drop in reported_drops] == [dropped]
        assert [drop.case_id for drop in final.case_drops] == [dropped]
        assert final.status == BenchmarkStatus.COMPLETE
        assert len(scenario.store.replays_for(final.benchmark_id)) == 4

    def test_drops_cost_nothing_and_are_not_unpriced(self, scenario: Scenario) -> None:
        scenario.drop_cases = set(scenario.case_ids)
        final = scenario.run(run_cap=100)
        assert (final.spent_usd, final.unpriced_replays) == (0.0, 0)
        assert len(final.case_drops) == 2


class TestRetryHarness:
    def test_only_harness_absent_records_are_deleted_and_counted(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_runner import delete_harness_replays

        outcomes = [
            (ProducerOutcome.COMMITTED, None),
            (ProducerOutcome.NO_COMMIT, AbsenceClass.CONFIG),
            (ProducerOutcome.ENVIRONMENT_FAILED, AbsenceClass.HARNESS),
            (ProducerOutcome.NO_RUN_STATE, AbsenceClass.HARNESS),
        ]
        plan = scenario.plan
        for planned, (outcome, absence) in zip(plan.replays, outcomes, strict=False):
            record = make_replay().model_copy(
                update={"benchmark_id": plan.benchmark_id, "outcome": outcome, "absence": absence}
            )
            scenario.store.write_replay(planned.record_id, record)
        assert delete_harness_replays(scenario.store, plan) == 2
        left = {record.outcome for _, record in scenario.store.replays_for(plan.benchmark_id)}
        assert left == {ProducerOutcome.COMMITTED, ProducerOutcome.NO_COMMIT}
        assert len(scenario.make_plan().pending) == 6

    def test_nothing_to_retry_deletes_nothing(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_runner import delete_harness_replays

        assert delete_harness_replays(scenario.store, scenario.plan) == 0

    def test_harness_records_outside_a_filtered_plan_are_kept(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_runner import delete_harness_replays

        full = scenario.plan
        for planned in full.replays:
            record = make_replay().model_copy(
                update={
                    "benchmark_id": full.benchmark_id,
                    "outcome": ProducerOutcome.NO_RUN_STATE,
                    "absence": AbsenceClass.HARNESS,
                }
            )
            scenario.store.write_replay(planned.record_id, record)
        limited = build_plan(
            set_name="fixes", set_version=1, case_ids=scenario.case_ids, configs=scenario.configs,
            samples=scenario.samples, existing_record_ids=(),
            only_cases=[scenario.case_ids[0]], only_samples=[0],
        )  # fmt: skip
        assert delete_harness_replays(scenario.store, limited) == 2
        assert len(scenario.store.replays_for(full.benchmark_id)) == 6


class TestStoreFailure:
    def test_a_record_write_failure_stops_the_run_and_leaves_running_with_the_sandbox_kept(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        import logging

        from squadron.benchmark.replay_one import ReplayStoreError, replay_one
        from squadron.core.process_runner import SubprocessRunner
        from squadron.metrology.errors import MetrologyStoreError
        from tests.benchmark.test_replay_one import CONFIG, World

        world = World(tmp_path)
        case = fix_case()
        plan = build_plan(
            set_name="fixes", set_version=1, case_ids=[case.case_id], configs=[CONFIG], samples=2,
            existing_record_ids=(),
        )  # fmt: skip

        def boom(record_id: str, replay: Any) -> str:
            raise MetrologyStoreError("read-only store")

        monkeypatch.setattr(world.store, "write_replay", boom)
        reports: list[str] = []

        def begin() -> StartedBenchmark:
            return begin_benchmark(
                plan=plan, config_refs=[OPUS_REF], caps=caps(100), store=world.store,
                root=tmp_path / "lockroot", process_runner=SubprocessRunner(),
                sweep=lambda runner, root: None, report=reports.append, print_bound=lambda: None,
                clock=lambda: NOW,
            )  # fmt: skip

        started = begin()
        with caplog.at_level(logging.ERROR), pytest.raises(ReplayStoreError):
            run_benchmark(
                started, plan, {case.case_id: case},
                lambda c, cfg, sample: replay_one(c, cfg, sample, world.deps()),
                world.store, lambda: NOW, lambda planned, result: None,
            )  # fmt: skip
        started.lock.release()
        assert any(
            r.levelno == logging.ERROR and "read-only store" in r.message for r in caplog.records
        )
        stored = world.store.get_run(plan.benchmark_id)
        assert stored is not None and stored.status == BenchmarkStatus.RUNNING
        kept = world.factory.sandboxes[0]
        assert kept.kept and kept.tree.exists()
        assert len(world.factory.sandboxes) == 1  # the second replay was never started
        # The next invocation sees a running record with a free lock.
        second = begin()
        assert second.was_interrupted
        assert any("interrupted" in message for message in reports)
        second.lock.release()


class TestExitCodes:
    def test_exit_codes_follow_the_run_status(self, scenario: Scenario) -> None:
        from squadron.benchmark.bench_runner import (
            EXIT_COMPLETE,
            EXIT_PARTIAL,
            EXIT_STOPPED,
            exit_code_for,
        )

        scenario.default_cost = 1.0
        partial = scenario.run(run_cap=1.0)
        complete = scenario.run(run_cap=100)
        assert exit_code_for(partial) == EXIT_PARTIAL == 2
        assert exit_code_for(complete) == EXIT_COMPLETE == 0
        assert EXIT_STOPPED == 1
