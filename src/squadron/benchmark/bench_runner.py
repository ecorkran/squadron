"""The benchmark runner (slice 424 D4, D8): begin, schedule, spend cap, resume.

``begin_benchmark`` takes the lock, reports an interrupted earlier invocation, sweeps orphaned
sandboxes, prints the stated bound, and only then records the benchmark as running. Nothing is
dispatched before the bound has been printed. ``run_benchmark`` then replays what has no
record yet, case-major, stopping before a replay when this invocation's known spend has
reached the run cap.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from squadron.benchmark.bench_lock import BenchmarkLock
from squadron.benchmark.bench_plan import BenchConfig, BenchmarkPlan, Caps, PlannedReplay
from squadron.benchmark.sandbox import HOME_SUFFIX, OUT_SUFFIX
from squadron.core.process_runner import ProcessRunner
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, BenchmarkStatus, ProducerOutcome
from squadron.metrology.benchmark_replay_models import BenchmarkRun, CaseDrop, ImplementationReplay
from squadron.metrology.benchmark_store import BenchmarkRecordStore
from squadron.metrology.replay_models import ProducerConfigRef

_logger = logging.getLogger(__name__)
_SIBLING_SUFFIXES = (HOME_SUFFIX, OUT_SUFFIX)

#: Removes sandboxes whose owner is gone (421's ``sweep_benchmark_orphans``).
OrphanSweep = Callable[[ProcessRunner, Path], None]


@dataclass(frozen=True)
class StartedBenchmark:
    """A benchmark that holds its lock and is recorded as running."""

    run: BenchmarkRun
    lock: BenchmarkLock
    #: Whether an earlier invocation was found still ``running`` with no live owner.
    was_interrupted: bool
    swept_sandboxes: int


def _sandbox_directories(root: Path) -> int:
    """Sandbox trees under *root*; the ``.home`` and ``.out`` siblings go with their tree."""
    if not root.is_dir():
        return 0
    return sum(
        1 for entry in root.iterdir() if entry.is_dir() and not entry.name.endswith(_SIBLING_SUFFIXES)
    )


def _sweep_and_count(sweep: OrphanSweep, runner: ProcessRunner, root: Path) -> int:
    before = _sandbox_directories(root)
    sweep(runner, root)
    return max(before - _sandbox_directories(root), 0)


def _interrupted_earlier(
    store: BenchmarkRecordStore, plan: BenchmarkPlan, now: datetime
) -> tuple[BenchmarkRun | None, bool]:
    """The stored run, marked ``interrupted`` when it says ``running`` but we hold the lock."""
    previous = store.get_run(plan.benchmark_id)
    if previous is None or previous.status is not BenchmarkStatus.RUNNING:
        return previous, False
    marked = previous.model_copy(update={"status": BenchmarkStatus.INTERRUPTED, "updated_at": now})
    store.write_run(marked)
    return marked, True


def _running_record(
    plan: BenchmarkPlan,
    configs: Sequence[ProducerConfigRef],
    caps: Caps,
    previous: BenchmarkRun | None,
    now: datetime,
) -> BenchmarkRun:
    """The run record for this invocation: the new caps, spend carried from earlier ones."""
    return BenchmarkRun(
        benchmark_id=plan.benchmark_id,
        case_set=plan.set_name,
        case_set_version=plan.set_version,
        configs=tuple(configs),
        samples=plan.samples,
        status=BenchmarkStatus.RUNNING,
        run_cap_usd=caps.run_cap_usd,
        per_replay_cap_usd=caps.per_replay_cap_usd,
        spent_usd=0.0 if previous is None else previous.spent_usd,
        unpriced_replays=0 if previous is None else previous.unpriced_replays,
        case_drops=(),
        started_at=now if previous is None else previous.started_at,
        updated_at=now,
    )


def begin_benchmark(
    *,
    plan: BenchmarkPlan,
    config_refs: Sequence[ProducerConfigRef],
    caps: Caps,
    store: BenchmarkRecordStore,
    root: Path,
    process_runner: ProcessRunner,
    sweep: OrphanSweep,
    report: Callable[[str], None],
    print_bound: Callable[[], None],
    clock: Callable[[], datetime],
) -> StartedBenchmark:
    """Lock, report an interruption, sweep, print the bound, then write ``running``.

    Raises ``BenchmarkRefusal`` while another live invocation holds the benchmark. The lock is
    released if anything after it fails, so a refused or failed start never leaves it behind.
    """
    lock = BenchmarkLock.acquire(root, plan.benchmark_id, process_runner)
    started = False
    try:
        previous, interrupted = _interrupted_earlier(store, plan, clock())
        if interrupted:
            report(
                f"benchmark {plan.benchmark_id} was left running by an earlier "
                f"invocation; it is now marked interrupted"
            )
        swept = _sweep_and_count(sweep, process_runner, root)
        report(f"swept {swept} orphaned sandbox{'' if swept == 1 else 'es'}")
        print_bound()
        run = _running_record(plan, config_refs, caps, previous, clock())
        store.write_run(run)
        started = True
    finally:
        if not started:
            lock.release()
    return StartedBenchmark(run=run, lock=lock, was_interrupted=interrupted, swept_sandboxes=swept)


#: Replays one (case, config, sample) of the plan: ``replay_one`` with its deps bound.
ReplayFunction = Callable[[BenchmarkCase, BenchConfig, int], ImplementationReplay | CaseDrop]
#: Told of each finished replay or dropped case, to print one line for it.
ReplayListener = Callable[[PlannedReplay, ImplementationReplay | CaseDrop], None]


@dataclass
class _Tally:
    """What this invocation has spent and seen so far."""

    spent_usd: float = 0.0

    def add(self, replay: ImplementationReplay) -> None:
        if replay.cost_usd is not None:
            self.spent_usd += replay.cost_usd


def _is_unpriced(replay: ImplementationReplay) -> bool:
    # A replay that never reached a producer spent nothing; it is not "unpriced".
    return replay.cost_usd is None and replay.outcome is not ProducerOutcome.ENVIRONMENT_FAILED


def _unpriced_in_store(store: BenchmarkRecordStore, benchmark_id: str) -> int:
    """Stored replays of the benchmark that reported no cost.

    Counted from the records, not carried from earlier invocations: ``--retry-harness``
    deletes records, and an invocation killed before it stored its totals would otherwise
    leave the count wrong.
    """
    return sum(_is_unpriced(replay) for _, replay in store.replays_for(benchmark_id))


def run_benchmark(
    started: StartedBenchmark,
    plan: BenchmarkPlan,
    cases: Mapping[str, BenchmarkCase],
    replay: ReplayFunction,
    store: BenchmarkRecordStore,
    clock: Callable[[], datetime],
    on_result: ReplayListener,
) -> BenchmarkRun:
    """Replay every pending (case, sample, config); return and store the final run record.

    Before each replay the run stops, ``partial``, once this invocation's known spend is at or
    over the run cap, so one replay can overshoot by up to a per-replay cap. A case whose
    re-qualification fails is dropped once: none of its remaining replays is attempted and the
    drop is recorded on the run. Unpriced replays add nothing to the spend; they are counted
    from the stored records.
    The run record's spend is rewritten after each replay. A ``ReplayStoreError`` from *replay*
    propagates: the stored status stays ``running``, with the spend so far.
    """
    tally = _Tally()
    drops: dict[str, CaseDrop] = {}
    cap = started.run.run_cap_usd
    stopped_at_cap = False
    for planned in plan.pending:
        if planned.case_id in drops:
            continue
        if tally.spent_usd >= cap:
            stopped_at_cap = True
            break
        result = replay(cases[planned.case_id], planned.config, planned.sample)
        on_result(planned, result)
        if isinstance(result, CaseDrop):
            drops[planned.case_id] = result
        else:
            tally.add(result)
            # Persist after every replay: a killed invocation or a store failure keeps
            # the spend of the replays that finished.
            store.write_run(
                started.run.model_copy(
                    update={
                        "spent_usd": started.run.spent_usd + tally.spent_usd,
                        "updated_at": clock(),
                    }
                )
            )
    status = BenchmarkStatus.PARTIAL if stopped_at_cap else BenchmarkStatus.COMPLETE
    final = started.run.model_copy(
        update={
            "status": status,
            "spent_usd": started.run.spent_usd + tally.spent_usd,
            "unpriced_replays": _unpriced_in_store(store, started.run.benchmark_id),
            "case_drops": tuple(drops.values()),
            "updated_at": clock(),
        }
    )
    store.write_run(final)
    return final


#: ``sq benchmark run`` exit codes: complete, a harness stop or refusal, the run cap reached.
EXIT_COMPLETE = 0
EXIT_STOPPED = 1
EXIT_PARTIAL = 2


def exit_code_for(run: BenchmarkRun) -> int:
    """The exit code for a finished invocation; a stop or refusal never reaches this."""
    return EXIT_PARTIAL if run.status is BenchmarkStatus.PARTIAL else EXIT_COMPLETE


def delete_harness_replays(store: BenchmarkRecordStore, benchmark_id: str) -> int:
    """``--retry-harness``: delete every replay of the benchmark whose absence is the
    harness's, so the next plan runs them again. Returns how many were deleted."""
    harness = [
        record_id
        for record_id, replay in store.replays_for(benchmark_id)
        if replay.absence is AbsenceClass.HARNESS
    ]
    deleted = store.delete_replays(harness)
    if deleted:
        _logger.info("deleted %d harness-absent replays of %s", deleted, benchmark_id)
    return deleted
