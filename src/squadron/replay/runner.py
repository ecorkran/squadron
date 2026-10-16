"""Run a set of producer configs against one slice's start point (slice 177 D4).

Per config: build a history-free sandbox, run ``sq run P4|P5`` there under a fixed
reviewer, read what the run left, write a ``producer_replay`` record, then remove the
sandbox. A failed config is data and does not stop the set; a store write failure does,
and keeps the sandbox for inspection.

Every collaborator is injected (sandbox, ``sq`` invoker, store, run state, drafts), so the
tests run no git, cf or model.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
import time
from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

import squadron
from squadron.core.process_runner import (
    ProcessCwdNotFoundError,
    ProcessNotFoundError,
    ProcessResult,
    ProcessRunner,
    ProcessTimedOutError,
)
from squadron.core.subprocess_text import TEXT_DECODING
from squadron.metrology.errors import MetrologyStoreError
from squadron.metrology.project_id import ProjectId
from squadron.metrology.replay_models import (
    ModelRef,
    ProducerConfigRef,
    ProducerReplay,
    ReplayPhase,
)
from squadron.pipeline.state import STATE_READ_ERRORS, RunState
from squadron.pipeline.text_tail import tail_text
from squadron.replay.drafts import Drafts
from squadron.replay.outcome import OutcomeReading, no_run_state_reading, read_outcome
from squadron.replay.sandbox import SandboxError, sweep_orphans
from squadron.replay.start_point import StartPoint

_logger = logging.getLogger(__name__)

#: The pipeline each phase is regenerated with; defined once.
PIPELINE_OF_PHASE: dict[ReplayPhase, str] = {
    ReplayPhase.DESIGN: "P4",
    ReplayPhase.TASKS: "P5",
}
_RESOLUTION_TIMEOUT_SECONDS = 120
_SQ_NOT_FOUND_EXIT = 127


class SandboxHandle(Protocol):
    @property
    def path(self) -> Path: ...

    def keep(self) -> None: ...


#: Builds the sandbox for one replay id; start commit, slice and repo are bound by the caller.
SandboxFactory = Callable[[str], AbstractContextManager[SandboxHandle]]
#: Runs ``sq`` to completion in a directory, with no wall-clock bound (174's stall bounds end a hang).
SqRunInvoker = Callable[[Sequence[str], Path], ProcessResult]
DraftsReader = Callable[[Path], Drafts]


class ReplayStore(Protocol):
    def write_replay(self, replay: ProducerReplay) -> str: ...


class RunStateReader(Protocol):
    def load(self, run_id: str) -> RunState: ...


def run_sq_subprocess(argv: Sequence[str], cwd: Path) -> ProcessResult:
    """The production invoker: captured output, no timeout."""
    try:
        done = subprocess.run(
            list(argv), cwd=cwd, capture_output=True, text=True, **TEXT_DECODING, check=False
        )
    except FileNotFoundError as exc:
        return ProcessResult(
            argv=tuple(argv), returncode=_SQ_NOT_FOUND_EXIT, stdout="", stderr=str(exc)
        )
    return ProcessResult(
        argv=tuple(argv), returncode=done.returncode, stdout=done.stdout, stderr=done.stderr
    )


@dataclass(frozen=True)
class ReplayRequest:
    project_id: ProjectId
    phase: ReplayPhase
    configs: Sequence[ProducerConfigRef]
    reviewer: ModelRef
    max_revisions: int


@dataclass(frozen=True)
class ReplayPlan:
    """What a replay set will do, shown for confirmation before any sandbox exists."""

    phase: ReplayPhase
    slice_index: int
    slice_name: str
    start_sha: str
    configs: tuple[ProducerConfigRef, ...]
    reviewer: ModelRef
    max_revisions: int
    llm_call_bound: int  # configs x 2 x (1 + cap): a dispatch and a review per round


@dataclass(frozen=True)
class ReplayDeps:
    store: ReplayStore
    run_states: RunStateReader
    sandbox_factory: SandboxFactory
    invoker: SqRunInvoker
    process_runner: ProcessRunner
    read_drafts: DraftsReader
    sq_executable: str
    now: Callable[[], datetime] = lambda: datetime.now(UTC)


@dataclass
class ReplaySetSummary:
    declined: bool = False
    records: list[tuple[str, ProducerReplay]] = field(default_factory=list[tuple[str, ProducerReplay]])
    skipped: list[tuple[str, str]] = field(default_factory=list[tuple[str, str]])  # (alias, why)
    stopped: str | None = None  # why the set ended early, with nothing further run


def replay_set_id(request: ReplayRequest, start: StartPoint) -> str:
    """Identity of one comparison: configs replayed under it share the same conditions (D9)."""
    parts = [
        request.project_id.value,
        request.phase.value,
        start.slice_index,
        start.start_sha,
        request.reviewer.alias,
        request.max_revisions,
    ]
    return hashlib.sha256(json.dumps(parts).encode("utf-8")).hexdigest()


def build_plan(request: ReplayRequest, start: StartPoint) -> ReplayPlan:
    return ReplayPlan(
        phase=request.phase,
        slice_index=start.slice_index,
        slice_name=start.slice_name,
        start_sha=start.start_sha,
        configs=tuple(request.configs),
        reviewer=request.reviewer,
        max_revisions=request.max_revisions,
        llm_call_bound=len(request.configs) * 2 * (1 + request.max_revisions),
    )


def run_replay_set(
    request: ReplayRequest,
    start: StartPoint,
    deps: ReplayDeps,
    *,
    confirm: Callable[[ReplayPlan], bool],
    new_replay_id: Callable[[], str],
    on_record: Callable[[str, ProducerReplay], None] | None = None,
    on_skip: Callable[[str, str], None] | None = None,
) -> ReplaySetSummary:
    """Sweep stale sandboxes, confirm the plan, then replay each config in order."""
    summary = ReplaySetSummary()
    sweep_orphans(deps.process_runner)
    if not confirm(build_plan(request, start)):
        summary.declined = True
        return summary
    replay_set = replay_set_id(request, start)
    for position, config in enumerate(request.configs):
        replay_id = new_replay_id()
        try:
            with deps.sandbox_factory(replay_id) as sandbox:
                if position == 0 and (why := _unresolved(deps, start, sandbox.path)) is not None:
                    summary.stopped = why  # nothing has been dispatched
                    return summary
                record = _replay_config(request, start, deps, config, sandbox, replay_id, replay_set)
                try:
                    record_id = deps.store.write_replay(record)
                except MetrologyStoreError as exc:
                    sandbox.keep()
                    summary.stopped = (
                        f"could not write the replay record: {exc}; sandbox kept at {sandbox.path}"
                    )
                    _logger.error(summary.stopped)
                    return summary
        except SandboxError as exc:
            _logger.error("replay of %s skipped: %s", config.alias, exc)
            summary.skipped.append((config.alias, str(exc)))
            if on_skip is not None:
                on_skip(config.alias, str(exc))
            continue
        summary.records.append((record_id, record))
        if on_record is not None:
            on_record(record_id, record)
    return summary


def _unresolved(deps: ReplayDeps, start: StartPoint, sandbox: Path) -> str | None:
    """Why the slice does not resolve in the first sandbox, or ``None`` when it does.

    ``cf set slice`` is the cheapest dispatch-free step of the run that can fail on a start
    point whose plan entry does not yet list the slice (D2); the runner never edits the plan.
    """
    argv = ["cf", "set", "slice", str(start.slice_index)]
    try:
        result = deps.process_runner.run(argv, cwd=str(sandbox), timeout=_RESOLUTION_TIMEOUT_SECONDS)
    except (ProcessNotFoundError, ProcessCwdNotFoundError, ProcessTimedOutError) as exc:
        return (
            f"slice {start.slice_index} could not be resolved at start commit {start.start_sha}: {exc}"
        )
    if result.returncode == 0:
        return None
    return (
        f"slice {start.slice_index} does not resolve at start commit {start.start_sha}: "
        f"{result.stderr.strip()}"
    )


def _replay_config(
    request: ReplayRequest,
    start: StartPoint,
    deps: ReplayDeps,
    config: ProducerConfigRef,
    sandbox: SandboxHandle,
    replay_id: str,
    replay_set: str,
) -> ProducerReplay:
    argv = [
        deps.sq_executable,
        "run",
        PIPELINE_OF_PHASE[request.phase],
        str(start.slice_index),
        "-m",
        config.alias,
        "-p",
        f"review-model={request.reviewer.alias}",
        "-p",
        f"max-revisions={request.max_revisions}",
        "--run-id",
        replay_id,
    ]
    began = time.monotonic()
    result = deps.invoker(argv, sandbox.path)
    wall_seconds = time.monotonic() - began
    reading = _read_run(deps, replay_id, result)
    drafts = deps.read_drafts(sandbox.path)
    return _record(request, start, deps, config, replay_id, replay_set, reading, drafts, wall_seconds)


def _read_run(deps: ReplayDeps, run_id: str, result: ProcessResult) -> OutcomeReading:
    """The outcome from run state; a run that left no readable state is ``no_run_state``."""
    try:
        return read_outcome(deps.run_states.load(run_id))
    except FileNotFoundError:
        why = f"no run state for {run_id}"
    except STATE_READ_ERRORS as exc:
        why = f"unreadable run state for {run_id}: {exc}"
    detail = f"{why}; exit {result.returncode}; stderr: {tail_text(result.stderr)}"
    _logger.warning("replay run %s: %s", run_id, detail)
    return no_run_state_reading(detail)


def _record(
    request: ReplayRequest,
    start: StartPoint,
    deps: ReplayDeps,
    config: ProducerConfigRef,
    replay_id: str,
    replay_set: str,
    reading: OutcomeReading,
    drafts: Drafts,
    wall_seconds: float,
) -> ProducerReplay:
    return ProducerReplay(
        replay_set=replay_set,
        project_id=request.project_id,
        phase=request.phase,
        slice_index=start.slice_index,
        slice_name=start.slice_name,
        original_sha=start.original_sha,
        start_sha=start.start_sha,
        config=config.model_copy(update={"effort_sent": reading.effort_sent}),
        reviewer=request.reviewer,
        max_revisions=request.max_revisions,
        run_id=replay_id,
        outcome=reading.outcome,
        failure_class=None if reading.failure_class is None else reading.failure_class.value,
        failure_detail=reading.failure_detail,
        rounds=reading.rounds,
        first_verdict=reading.first_verdict,
        cost_usd=reading.cost_usd,
        priced=reading.priced,
        wall_seconds=wall_seconds,
        prompt=reading.prompt,
        task_prompt=reading.task_prompt,
        first_draft=drafts.first,
        final_text=drafts.final,
        squadron_version=squadron.__version__,
        created_at=deps.now(),
    )
