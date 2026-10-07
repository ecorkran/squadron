"""Run listing — which runs can be resumed, and where (slice 199).

Builds typed row data from run state and batch reports for ``sq runs list``. Read-only
and lock-free: a live run is read as a snapshot, and its liveness is assessed, never
written (slice 174 D4). Rendering lives in ``cli/run_views``.
Every status comparison goes through ``RESUMABLE_STATUSES``, ``RUNNING_STATUS`` or
``ExecutionStatus``; this module adds no status literals (D10).
"""

from __future__ import annotations

import logging
import socket
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
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
from squadron.pipeline.run_liveness import (
    LivenessAssessment,
    ProcessCheck,
    assess_liveness,
    process_alive,
)
from squadron.pipeline.state import (
    RESUMABLE_STATUSES,
    RUNNING_STATUS,
    ActiveItem,
    RunState,
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
    # Set only for running runs (slice 174 D3).
    liveness: LivenessAssessment | None = None
    active_step: str | None = None
    active_item: ActiveItem | None = None


@dataclass(frozen=True)
class RunListing:
    """The listing's rows, and why each unavailable pipeline could not be loaded (D10)."""

    rows: list[RunSummary]
    unavailable: dict[str, str]  # pipeline -> loader message

    @property
    def unavailable_runs(self) -> int:
        """Rows whose pipeline could not be loaded."""
        return sum(1 for row in self.rows if row.problem is ResumeProblem.PIPELINE_UNAVAILABLE)


_Resolution = tuple[ResumePoint | None, ResumeProblem | None]
_NOTHING_TO_RESUME: _Resolution = (None, None)


class _Definitions:
    """Loads each pipeline at most once per listing call (D12); failures are remembered."""

    def __init__(self, load_definition: DefinitionLoader) -> None:
        self._load = load_definition
        self._definitions: dict[str, PipelineDefinition] = {}
        self._failures: dict[str, str] = {}  # pipeline -> why it could not be loaded

    @property
    def failures(self) -> dict[str, str]:
        return dict(self._failures)

    def get(self, state: RunState) -> PipelineDefinition | None:
        """The run's definition, or ``None`` when it cannot be loaded.

        A failure is logged once per pipeline at DEBUG; the CLI reports it in one
        summary line rather than per run (174 D10).
        """
        name = state.pipeline
        if name not in self._definitions and name not in self._failures:
            try:
                self._definitions[name] = self._load(name)
            except _DEFINITION_ERRORS as exc:
                # Renamed, deleted or broken pipeline: the row shows a marker (D7).
                self._failures[name] = str(exc)
                _logger.debug("pipeline %s unavailable: %s", name, exc)
        return self._definitions.get(name)


def list_run_summaries(
    state_manager: StateManager,
    *,
    pipeline: str | None,
    include_all: bool,
    load_definition: DefinitionLoader = load_pipeline,
    load_report: ReportLoader = BatchReport.load,
    now: datetime | None = None,
    hostname: str | None = None,
    process_alive: ProcessCheck = process_alive,
) -> RunListing:
    """One summary per run, newest first.

    Unless *include_all*, only running runs and runs with a resume point or a
    problem are kept: a problem means resumability could not be determined, which
    is never hidden, and a running run is the one a user most wants to check on.
    """
    definitions = _Definitions(load_definition)
    runs = state_manager.list_runs(pipeline=pipeline.lower() if pipeline else None)
    assessed_at = datetime.now(UTC) if now is None else now
    host = socket.gethostname() if hostname is None else hostname
    summaries: list[RunSummary] = []
    for state in runs:
        if state.status == RUNNING_STATUS:
            liveness = assess_liveness(
                state, now=assessed_at, hostname=host, process_alive=process_alive
            )
            summaries.append(_summary(state, None, None, liveness))
            continue
        resume, problem = _resolve(state, state_manager.runs_dir, definitions, load_report)
        if include_all or resume is not None or problem is not None:
            summaries.append(_summary(state, resume, problem, None))
    return RunListing(summaries, definitions.failures)


def _summary(
    state: RunState,
    resume: ResumePoint | None,
    problem: ResumeProblem | None,
    liveness: LivenessAssessment | None,
) -> RunSummary:
    running = liveness is not None
    return RunSummary(
        run_id=state.run_id,
        pipeline=state.pipeline,
        params=dict(state.params),
        status=state.status,
        resume=resume,
        problem=problem,
        started_at=state.started_at,
        liveness=liveness,
        active_step=state.active_step if running else None,
        active_item=state.active_item if running else None,
    )


def _resolve(
    state: RunState, runs_dir: Path, definitions: _Definitions, load_report: ReportLoader
) -> _Resolution:
    if state.status in RESUMABLE_STATUSES:
        return _resolve_step(state, definitions)
    if state.status == ExecutionStatus.COMPLETED.value:
        return _resolve_items(state, runs_dir, definitions, load_report)
    return _NOTHING_TO_RESUME  # an unknown status has no resume point


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
