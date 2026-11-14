"""Building and writing the ``ImplementationReplay`` of one replay (slice 424 D10)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import squadron
from squadron.benchmark.bench_plan import BenchConfig
from squadron.benchmark.case_runners import CaseKindRunner, ReplaySandbox
from squadron.benchmark.replay_deps import ReplayOneDeps, store_failure
from squadron.benchmark.replay_outcome import ProducerClassification
from squadron.metrology.benchmark_environment import EnvironmentIdentity
from squadron.metrology.benchmark_models import BenchmarkCase
from squadron.metrology.benchmark_replay_enums import AbsenceClass, LeakVerdict, ProducerOutcome
from squadron.metrology.benchmark_replay_models import DiffRef, ImplementationReplay, LeakScanResult
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.replay_models import ProducerConfigRef, PromptIdentity

_logger = logging.getLogger(__name__)


def absence_and_detail(
    classification: ProducerClassification, leak: LeakScanResult
) -> tuple[AbsenceClass | None, str | None]:
    """A leak result other than clean makes the replay a harness absence, whatever it produced."""
    if leak.verdict is LeakVerdict.NO_LEAK_DETECTED:
        return classification.absence, classification.failure_detail
    note = f"leak scan {leak.verdict.value}" + (f": {leak.detail}" if leak.detail else "")
    previous = classification.failure_detail
    return AbsenceClass.HARNESS, note if previous is None else f"{previous}; {note}"


@dataclass(frozen=True)
class ReplayFields:
    """What differs between replays; the rest of a record comes from the benchmark and the runner."""

    config: ProducerConfigRef
    outcome: ProducerOutcome
    absence: AbsenceClass | None
    failure_detail: str | None
    leak: LeakScanResult | None
    diff: DiffRef | None
    commit_sha: str | None
    environment: EnvironmentIdentity | None
    prompt: PromptIdentity | None
    instruction_files: tuple[tuple[str, str], ...]
    cost_usd: float | None
    turns: int | None
    wall_seconds: float


def build_record(
    deps: ReplayOneDeps,
    runner: CaseKindRunner,
    case: BenchmarkCase,
    sample: int,
    record_id: str,
    fields: ReplayFields,
) -> ImplementationReplay:
    """The record: the fields every replay shares, the runner's pipeline names, and *fields*."""
    return ImplementationReplay(
        benchmark_id=deps.benchmark_id,
        case_id=case.case_id,
        case_set=deps.case_set,
        case_set_version=deps.case_set_version,
        sample=sample,
        config=fields.config,
        pipeline=runner.pipeline,
        producer_step=runner.producer_step,
        run_id=record_id,
        outcome=fields.outcome,
        absence=fields.absence,
        failure_detail=fields.failure_detail,
        leak=fields.leak,
        diff=fields.diff,
        commit_sha=fields.commit_sha,
        environment=fields.environment,
        prompt=fields.prompt,
        instruction_files=fields.instruction_files,
        cost_usd=fields.cost_usd,
        turns=fields.turns,
        wall_seconds=fields.wall_seconds,
        squadron_version=squadron.__version__,
        created_at=deps.clock(),
    )


def write_record(
    deps: ReplayOneDeps,
    record_id: str,
    record: ImplementationReplay,
    sandbox: ReplaySandbox | None,
) -> None:
    """Store *record*; a failure keeps the sandbox and raises ``ReplayStoreError``."""
    try:
        deps.store.write_replay(record_id, record)
    except MetrologyStoreError as exc:
        raise store_failure(sandbox, f"replay record write failed: {exc}") from exc


def environment_failed_record(
    deps: ReplayOneDeps,
    runner: CaseKindRunner,
    case: BenchmarkCase,
    config: BenchConfig,
    sample: int,
    record_id: str,
    why: str,
) -> ImplementationReplay:
    """Record a replay whose sandbox could not be built; the producer never ran."""
    _logger.error("replay %s: environment failed: %s", record_id, why)
    fields = ReplayFields(
        config=deps.config_ref_for(config),
        outcome=ProducerOutcome.ENVIRONMENT_FAILED,
        absence=AbsenceClass.HARNESS,
        failure_detail=why,
        leak=None,
        diff=None,
        commit_sha=None,
        environment=None,
        prompt=None,
        instruction_files=(),
        cost_usd=None,
        turns=None,
        wall_seconds=0.0,
    )
    record = build_record(deps, runner, case, sample, record_id, fields)
    write_record(deps, record_id, record, None)
    return record
