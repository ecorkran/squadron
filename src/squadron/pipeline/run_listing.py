"""Run listing — which runs can be resumed, and where (slice 199).

Builds typed row data from run state and batch reports for ``sq runs list``. Read-only
and lock-free: a live run is read as a snapshot. Rendering lives in ``cli/run_views``.
Every status comparison goes through ``RESUMABLE_STATUSES``, ``RUNNING_STATUS`` or
``ExecutionStatus``; this module adds no status literals (D10).
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import ValidationError

from squadron.pipeline.batch_report import (
    BatchReport,
    BatchReportLoadError,
    ItemDecision,
    report_json_path,
    report_json_paths,
)
from squadron.pipeline.executor import ExecutionStatus
from squadron.pipeline.item_eligibility import (
    ItemResumeUnsupportedError,
    item_decisions,
    single_each_step,
)
from squadron.pipeline.loader import load_pipeline
from squadron.pipeline.models import PipelineDefinition
from squadron.pipeline.state import (
    RESUMABLE_STATUSES,
    RUNNING_STATUS,
    RunState,
    SchemaVersionError,
    StateManager,
    first_unfinished_step_of,
)

_logger = logging.getLogger(__name__)

DefinitionLoader = Callable[[str], PipelineDefinition]
ReportLoader = Callable[[Path], BatchReport]

# What a definition load may raise for a pipeline that is missing or broken (D7): the
# set discover_pipelines narrows to. Anything else propagates.
_DEFINITION_ERRORS = (OSError, yaml.YAMLError, ValidationError)


class ResumeKind(StrEnum):
    STEP = "step"  # sq run --resume <run-id>
    ITEMS = "items"  # sq run --resume <run-id> --item N --decision ...


class ResumeProblem(StrEnum):
    """Why a run's resumability could not be determined (D7)."""

    PIPELINE_UNAVAILABLE = "pipeline_unavailable"
    NO_UNFINISHED_STEP = "no_unfinished_step"
    ITEM_RESUME_UNSUPPORTED = "item_resume_unsupported"
    REPORT_UNREADABLE = "report_unreadable"


@dataclass(frozen=True)
class ResumePoint:
    kind: ResumeKind
    step_name: str
    open_items: int = 0  # 0 for STEP
    acceptable_items: int = 0  # 0 for STEP


@dataclass(frozen=True)
class RunSummary:
    run_id: str
    pipeline: str
    params: dict[str, object]
    status: str  # RunState.status (D10)
    resume: ResumePoint | None
    problem: ResumeProblem | None  # set only when resume is None
    started_at: datetime


_Resolution = tuple[ResumePoint | None, ResumeProblem | None]
_NOTHING_TO_RESUME: _Resolution = (None, None)


class _Definitions:
    """Loads each pipeline at most once per listing call (D12); failures are remembered."""

    def __init__(self, load_definition: DefinitionLoader) -> None:
        self._load = load_definition
        self._loaded: dict[str, PipelineDefinition | Exception] = {}

    def get(self, state: RunState) -> PipelineDefinition | None:
        """The run's definition, or ``None`` (logged) when it cannot be loaded."""
        if state.pipeline not in self._loaded:
            try:
                self._loaded[state.pipeline] = self._load(state.pipeline)
            except _DEFINITION_ERRORS as exc:
                # Renamed, deleted or broken pipeline: the row shows a marker (D7).
                self._loaded[state.pipeline] = exc
        loaded = self._loaded[state.pipeline]
        if isinstance(loaded, Exception):
            _logger.warning("run %s: pipeline %s unavailable: %s", state.run_id, state.pipeline, loaded)
            return None
        return loaded


def list_run_summaries(
    state_manager: StateManager,
    *,
    pipeline: str | None,
    include_all: bool,
    load_definition: DefinitionLoader = load_pipeline,
    load_report: ReportLoader = BatchReport.load,
) -> list[RunSummary]:
    """One summary per run, newest first.

    Unless *include_all*, only runs with a resume point or a problem are kept: a
    problem means resumability could not be determined, which is never hidden.
    """
    definitions = _Definitions(load_definition)
    runs = state_manager.list_runs(pipeline=pipeline.lower() if pipeline else None)
    summaries: list[RunSummary] = []
    for state in runs:
        resume, problem = _resolve(state, state_manager.runs_dir, definitions, load_report)
        if include_all or resume is not None or problem is not None:
            summaries.append(
                RunSummary(
                    run_id=state.run_id,
                    pipeline=state.pipeline,
                    params=dict(state.params),
                    status=state.status,
                    resume=resume,
                    problem=problem,
                    started_at=state.started_at,
                )
            )
    return summaries


def _resolve(
    state: RunState, runs_dir: Path, definitions: _Definitions, load_report: ReportLoader
) -> _Resolution:
    if state.status in RESUMABLE_STATUSES:
        return _resolve_step(state, definitions)
    if state.status == ExecutionStatus.COMPLETED.value:
        return _resolve_items(state, runs_dir, definitions, load_report)
    return _NOTHING_TO_RESUME  # running: live, or a crash orphan (D7)


def _resolve_step(state: RunState, definitions: _Definitions) -> _Resolution:
    """A paused or failed run resumes at the step ``--resume`` would pick (D4)."""
    definition = definitions.get(state)
    if definition is None:
        return None, ResumeProblem.PIPELINE_UNAVAILABLE
    step_name = first_unfinished_step_of(state, definition)
    if step_name is None:
        _logger.warning("run %s: %s but no unfinished step", state.run_id, state.status)
        return None, ResumeProblem.NO_UNFINISHED_STEP
    return ResumePoint(ResumeKind.STEP, step_name), None


def _resolve_items(
    state: RunState, runs_dir: Path, definitions: _Definitions, load_report: ReportLoader
) -> _Resolution:
    """A completed batch run resumes at its open items (slice 197 item resume)."""
    if not report_json_paths(runs_dir, state.run_id):
        return _NOTHING_TO_RESUME  # never ran an each step; no definition load
    definition = definitions.get(state)
    if definition is None:
        return None, ResumeProblem.PIPELINE_UNAVAILABLE
    try:
        each = single_each_step(definition)
    except ItemResumeUnsupportedError as exc:
        _logger.warning(
            "run %s: pipeline %s has %d each steps; item resume needs exactly one",
            state.run_id,
            exc.pipeline,
            exc.each_count,
        )
        return None, ResumeProblem.ITEM_RESUME_UNSUPPORTED
    path = report_json_path(runs_dir, state.run_id, each.name)
    try:
        report = load_report(path)
    except BatchReportLoadError as exc:
        _logger.warning("run %s: report %s unreadable: %s", state.run_id, path, exc)
        return None, ResumeProblem.REPORT_UNREADABLE
    decisions = [item_decisions(record) for record in report.records]
    open_items = sum(1 for d in decisions if d)
    if open_items == 0:
        return _NOTHING_TO_RESUME
    acceptable = sum(1 for d in decisions if ItemDecision.ACCEPT in d)
    return ResumePoint(ResumeKind.ITEMS, each.name, open_items, acceptable), None


# ---------------------------------------------------------------------------
# Waiting on a run (D13)
# ---------------------------------------------------------------------------

WAIT_POLL_INTERVAL_SECONDS = 2.0


class WaitOutcome(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    TIMED_OUT = "timed_out"
    NOT_FOUND = "not_found"
    UNREADABLE = "unreadable"
    UNKNOWN_STATUS = "unknown_status"


# The single definition of `sq runs wait` exit codes. 2 is left to Typer usage errors.
WAIT_EXIT_CODES: dict[WaitOutcome, int] = {
    WaitOutcome.COMPLETED: 0,
    WaitOutcome.FAILED: 1,
    WaitOutcome.PAUSED: 3,
    WaitOutcome.TIMED_OUT: 4,
    WaitOutcome.NOT_FOUND: 5,
    WaitOutcome.UNREADABLE: 6,
    WaitOutcome.UNKNOWN_STATUS: 7,
}

_TERMINAL_OUTCOMES: dict[str, WaitOutcome] = {
    ExecutionStatus.COMPLETED.value: WaitOutcome.COMPLETED,
    ExecutionStatus.FAILED.value: WaitOutcome.FAILED,
    ExecutionStatus.PAUSED.value: WaitOutcome.PAUSED,
}

# _load_raw's raisable set for a present file (as in StateManager.list_runs). A state
# file is replaced atomically, so a failed read is a real fault, not a race.
_STATE_READ_ERRORS = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    SchemaVersionError,
    ValidationError,
)


def wait_for_run(
    state_manager: StateManager,
    run_id: str,
    *,
    timeout: float | None,
    poll_interval: float = WAIT_POLL_INTERVAL_SECONDS,
    clock: Callable[[], float] = time.monotonic,
    sleep: Callable[[float], None] = time.sleep,
) -> WaitOutcome:
    """Re-read *run_id*'s state every *poll_interval* until it leaves ``running``.

    ``timeout=None`` waits indefinitely: a crashed run stays ``running`` forever and
    cannot be told from a live one (D7, #190), so a caller that needs a bound passes one.
    """
    deadline = None if timeout is None else clock() + timeout
    while True:
        outcome = _poll(state_manager, run_id)
        if outcome is None and deadline is not None and clock() >= deadline:
            outcome = WaitOutcome.TIMED_OUT
        if outcome is not None:
            if outcome is not WaitOutcome.COMPLETED:
                _logger.warning("wait on run %s ended: %s", run_id, outcome)
            return outcome
        sleep(poll_interval)


def _poll(state_manager: StateManager, run_id: str) -> WaitOutcome | None:
    """The run's outcome, or ``None`` while it is still running."""
    try:
        state = state_manager.load(run_id)
    except FileNotFoundError:
        return WaitOutcome.NOT_FOUND
    except _STATE_READ_ERRORS as exc:
        _logger.warning("run %s state unreadable: %s", run_id, exc)
        return WaitOutcome.UNREADABLE
    if state.status == RUNNING_STATUS:
        return None
    return _TERMINAL_OUTCOMES.get(state.status, WaitOutcome.UNKNOWN_STATUS)
