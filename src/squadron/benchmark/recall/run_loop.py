"""Serial dispatch of pending stages: sandboxes, caps, resume, orphans, retry (D7, D8, D9).

One sandbox per case per invocation, reused for that case's stages and removed after.
Stages run one at a time. The dollar cap is checked before every call and the plan-call cap
before every plan-billed call; either stops the loop with every record kept. Each entry is
stored as soon as it exists. On resume, an output file with no entry is ingested (its leak
scan runs while its scrubbed home is still present), otherwise the call is repeated.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager, ExitStack
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Protocol

from squadron.benchmark.grade_budget import GradeCapReached, ReviewBudget
from squadron.benchmark.recall.kinds import KindContext, get_kind
from squadron.benchmark.recall.recall_store import RecallRecordStore
from squadron.benchmark.recall.run_bound import RunBound
from squadron.benchmark.recall.run_plan import PendingStage
from squadron.benchmark.recall.stage_ingest import IngestContext, failure_entry, stage_label
from squadron.benchmark.recall.stage_runner import (
    StageDeps,
    ingest_orphan,
    remove_home,
    run_stage,
    stage_paths,
)
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.recall_case_models import RealBugCase
from squadron.metrology.recall_run_models import (
    CHAIN_SEPARATOR,
    COMB_KEY_SEPARATOR,
    RecallRun,
    StageEntry,
    StageKind,
    StageOutcome,
)
from squadron.replay.history_free_sandbox import SandboxError

_logger = logging.getLogger(__name__)


class SandboxFactory(Protocol):
    def open(self, case: RealBugCase) -> AbstractContextManager[Path]: ...


StageCall = Callable[[PendingStage, RecallRun, Path], StageEntry]
OrphanIngest = Callable[[PendingStage, Path], StageEntry | None]
HasOutput = Callable[[PendingStage], bool]


class LoopStatus(StrEnum):
    COMPLETE = "complete"
    CAPPED = "capped"
    ERROR = "error"


@dataclass
class LoopResult:
    status: LoopStatus = LoopStatus.COMPLETE
    stored: int = 0
    remaining: list[PendingStage] = field(default_factory=list[PendingStage])
    reason: str | None = None


@dataclass(frozen=True)
class LoopDeps:
    store: RecallRecordStore
    sandboxes: SandboxFactory
    call: StageCall
    has_output: HasOutput
    ingest_orphan: OrphanIngest
    remove_home: Callable[[PendingStage], None]
    ingest: IngestContext
    budget: ReviewBudget | None


class _Stop(Exception):
    """Ends the loop: a cap was reached or a record could not be written."""

    def __init__(self, status: LoopStatus, reason: str) -> None:
        super().__init__(reason)
        self.status = status
        self.reason = reason


@dataclass
class _Counters:
    plan_calls: int = 0
    stored: int = 0


def run_pending(bound: RunBound, deps: LoopDeps) -> LoopResult:
    """Dispatch every pending stage of *bound* in order, case by case."""
    counters = _Counters()
    done: set[int] = set()
    try:
        for case, stages in _by_case(bound.pending):
            _run_case(case, stages, bound, deps, counters, done)
    except _Stop as stop:
        remaining = [s for i, s in enumerate(bound.pending) if i not in done]
        return LoopResult(stop.status, counters.stored, remaining, stop.reason)
    return LoopResult(LoopStatus.COMPLETE, counters.stored)


def _by_case(pending: list[PendingStage]) -> list[tuple[RealBugCase, list[tuple[int, PendingStage]]]]:
    groups: dict[str, tuple[RealBugCase, list[tuple[int, PendingStage]]]] = {}
    for index, stage in enumerate(pending):
        groups.setdefault(stage.case.case_id, (stage.case, []))[1].append((index, stage))
    return list(groups.values())


def _run_case(
    case: RealBugCase,
    stages: list[tuple[int, PendingStage]],
    bound: RunBound,
    deps: LoopDeps,
    counters: _Counters,
    done: set[int],
) -> None:
    with ExitStack() as stack:
        try:
            sandbox = stack.enter_context(deps.sandboxes.open(case))
        except SandboxError as exc:
            for index, stage in stages:
                entry = failure_entry(
                    stage, StageOutcome.HARNESS_FAILURE, f"sandbox: {exc}", deps.ingest
                )
                _store(stage, entry, deps, counters)
                done.add(index)
            return
        for index, stage in stages:
            _run_one(stage, sandbox, bound, deps, counters)
            done.add(index)


def _run_one(
    stage: PendingStage, sandbox: Path, bound: RunBound, deps: LoopDeps, counters: _Counters
) -> None:
    run = deps.store.get_run(stage.case.case_id, stage.run_index) or RecallRun(
        case_id=stage.case.case_id, run_index=stage.run_index
    )
    if stage.replaces is None and deps.has_output(stage):
        orphan = deps.ingest_orphan(stage, sandbox)
        if orphan is not None:
            _logger.warning("recall %s: ingested an output file with no entry", stage_label(stage))
            _store(stage, orphan, deps, counters, run)
            return
        _logger.warning(
            "recall %s: output file with no entry and no scrubbed home; repeating the call, "
            "the earlier call's cost was spent without a record",
            stage_label(stage),
        )
    plan_billed = bound.is_plan_billed(stage)
    _check_caps(plan_billed, bound, deps, counters)
    entry = deps.call(stage, run, sandbox)
    if plan_billed:
        counters.plan_calls += 1
    elif deps.budget is not None:
        deps.budget.after_review(entry.usage.cost_usd)
    _store(stage, entry, deps, counters, run)


def _check_caps(plan_billed: bool, bound: RunBound, deps: LoopDeps, counters: _Counters) -> None:
    if deps.budget is not None:
        try:
            deps.budget.before_review()
        except GradeCapReached as exc:
            raise _Stop(LoopStatus.CAPPED, str(exc)) from exc
    cap = bound.max_plan_calls
    if plan_billed and cap is not None and counters.plan_calls >= cap:
        _logger.warning("recall plan-call cap reached: %d of %d", counters.plan_calls, cap)
        raise _Stop(LoopStatus.CAPPED, f"plan-billed call cap {cap} reached")


def descendant_prefix(stage: PendingStage) -> str:
    """The ``combs`` slot prefix of every comb that reads *stage*'s output."""
    if stage.kind is StageKind.REVIEW:
        return f"{stage.review_key}{COMB_KEY_SEPARATOR}"
    return f"{stage.slot}{CHAIN_SEPARATOR}"


def _store(
    stage: PendingStage,
    entry: StageEntry,
    deps: LoopDeps,
    counters: _Counters,
    run: RecallRun | None = None,
) -> None:
    """Put *entry* in its run record now; a write failure stops the loop (output file kept)."""
    run = (
        run
        or deps.store.get_run(stage.case.case_id, stage.run_index)
        or RecallRun(case_id=stage.case.case_id, run_index=stage.run_index)
    )
    slots = run.reviews if stage.kind is StageKind.REVIEW else run.combs
    previous = slots.get(stage.slot)
    if previous is not None:
        # A replacement (--retry-harness or a stale comb): the old entry is kept, and every
        # comb built on it is stale, so it leaves the record with it in the same write. A
        # run stopped before those combs rerun then finds them missing, hence pending.
        run.superseded.append(previous)
        prefix = descendant_prefix(stage)
        for slot in [slot for slot in run.combs if slot.startswith(prefix)]:
            run.superseded.append(run.combs.pop(slot))
    slots[stage.slot] = entry
    try:
        deps.store.put_run(run)
    except MetrologyStoreError as exc:
        _logger.error(
            "recall %s: run record not written; output file kept: %s", stage_label(stage), exc
        )
        raise _Stop(LoopStatus.ERROR, f"write_record failed for {run.record_id}: {exc}") from exc
    counters.stored += 1
    deps.remove_home(stage)


@dataclass(frozen=True)
class KindSandboxFactory:
    """Opens each case's sandbox through its kind (D14); the id is unique per invocation."""

    context: KindContext
    root: Path
    invocation: str

    def open(self, case: RealBugCase) -> AbstractContextManager[Path]:
        sandbox_id = f"recall-{self.invocation}-{case.case_id}"
        return get_kind(case.kind).open_sandbox(case, self.context, self.root, sandbox_id)


def live_loop_deps(
    store: RecallRecordStore,
    sandboxes: SandboxFactory,
    stage_deps: StageDeps,
    budget: ReviewBudget | None,
) -> LoopDeps:
    """``LoopDeps`` over the real stage runner, orphan ingest and home removal."""
    root = stage_deps.bench_root
    return LoopDeps(
        store=store,
        sandboxes=sandboxes,
        call=lambda stage, run, sandbox: run_stage(stage, run, sandbox, stage_deps),
        has_output=lambda stage: stage_paths(stage, root).output.is_file(),
        ingest_orphan=lambda stage, _current_sandbox: ingest_orphan(stage, stage_deps),
        remove_home=lambda stage: remove_home(stage, root),
        ingest=stage_deps.ingest,
        budget=budget,
    )
