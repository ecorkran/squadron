"""Pipeline run state persistence.

Provides StateManager, RunState, StepState, CheckpointState, and
SchemaVersionError for storing and resuming pipeline execution state.

State files are written as JSON to ~/.config/squadron/runs/ using atomic
write-then-rename to prevent corruption on interrupted writes.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import socket
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, ValidationError

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult

if TYPE_CHECKING:
    from squadron.pipeline.models import PipelineDefinition
    from squadron.pipeline.run_observer import RunObserver

_logger = logging.getLogger(__name__)

__all__ = [
    "ExecutionMode",
    "StateManager",
    "RunState",
    "StepState",
    "CheckpointState",
    "CompactSummary",
    "SchemaVersionError",
]

_SCHEMA_VERSION = 5
_SUPPORTED_SCHEMA_VERSIONS = {3, 4, 5}

# Statuses that mean "not actually done" despite being recorded in
# completed_steps. FAILED is included because the top-level walk appends the
# step via the same unconditional _append_step before returning on failure
# (see executor.py), so a failed step is recorded complete by the identical
# mechanism a paused step is.
RESUMABLE_STATUSES = frozenset({ExecutionStatus.PAUSED.value, ExecutionStatus.FAILED.value})

# Status init_run writes for a live run. Not an ExecutionStatus member; typing
# RunState.status as an enum that includes it is a schema change (slice 199 D10).
RUNNING_STATUS = "running"


def first_unfinished_step_of(state: RunState, definition: PipelineDefinition) -> str | None:
    """Return name of the first step in *definition* not completed in *state*.

    A step recorded with a status in RESUMABLE_STATUSES (PAUSED, FAILED)
    is not treated as done, so resume returns to that step rather than
    past it.
    """
    completed = {s.step_name for s in state.completed_steps if s.status not in RESUMABLE_STATUSES}
    for step in definition.steps:
        if step.name not in completed:
            return step.name
    return None


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ExecutionMode(StrEnum):
    """Identifies which runner was used to start a pipeline run."""

    SDK = "sdk"
    PROMPT_ONLY = "prompt-only"


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SchemaVersionError(Exception):
    """Raised when a state file has an unsupported schema_version."""

    def __init__(self, version: object) -> None:
        super().__init__(f"Unsupported state file schema_version: {version!r}")
        self.version = version


# What reading a present run-state file can raise (StateManager._load_raw): unreadable
# file, undecodable text, corrupt JSON, unsupported schema version, or a shape that
# fails RunState validation.
STATE_READ_ERRORS: tuple[type[Exception], ...] = (
    OSError,
    UnicodeDecodeError,
    json.JSONDecodeError,
    SchemaVersionError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Pydantic models (external boundary: file I/O)
# ---------------------------------------------------------------------------


class StepState(BaseModel):
    """Persisted record of a single completed pipeline step."""

    step_name: str
    step_type: str
    status: str  # ExecutionStatus string value
    verdict: str | None = None
    # Numeric scoring foundation (slice 300): hoisted from the last non-None
    # action score, mirroring verdict. Default None → older state files load.
    score: float | None = None
    outputs: dict[str, object] = {}
    action_results: list[dict[str, object]] = []
    iteration: int = 0
    completed_at: datetime


class CheckpointState(BaseModel):
    """Metadata captured when a pipeline pauses at a checkpoint."""

    reason: str
    step: str
    verdict: str | None = None
    paused_at: datetime


class CompactSummary(BaseModel):
    """A persisted compact summary captured by a compact step.

    Keyed in ``RunState.compact_summaries`` by a string of the form
    ``"{source_step_index}:{source_step_name}"``. Slice 159 will extend
    this key with a branch suffix for fan-out branches.
    """

    key: str
    text: str
    summary_model: str | None
    source_step_index: int
    source_step_name: str
    created_at: datetime


class RunOwner(BaseModel):
    """The process that owns a running run (slice 174 D2)."""

    pid: int
    hostname: str
    claimed_at: datetime
    heartbeat_interval_s: int  # the writer's interval; readers judge staleness by it

    @classmethod
    def current(cls, heartbeat_interval_s: int) -> RunOwner:
        """An owner record for this process, claimed now."""
        return cls(
            pid=os.getpid(),
            hostname=socket.gethostname(),
            claimed_at=datetime.now(UTC),
            heartbeat_interval_s=heartbeat_interval_s,
        )


class ActiveItem(BaseModel):
    """The ``each`` item a run is working on now (slice 174 D2)."""

    position: int  # 0-based position in the each step's item list
    total: int
    index: str | None  # the item's own "index" field when present (plan slice index)


class RunState(BaseModel):
    """Complete persisted state of a pipeline run."""

    schema_version: int = _SCHEMA_VERSION
    run_id: str
    pipeline: str
    params: dict[str, object]
    execution_mode: ExecutionMode = ExecutionMode.SDK
    started_at: datetime
    updated_at: datetime
    status: str  # ExecutionStatus string value
    current_step: str | None = None
    completed_steps: list[StepState] = []
    checkpoint: CheckpointState | None = None
    compact_summaries: dict[str, CompactSummary] = {}

    pool_selections: list[dict[str, object]] = []

    # Liveness and progress (schema v5, slice 174 D2). None in v3/v4 files.
    owner: RunOwner | None = None
    heartbeat_at: datetime | None = None
    active_step: str | None = None  # the step running now; current_step keeps its meaning
    progress_at: datetime | None = None  # last step start, item start or step completion
    active_item: ActiveItem | None = None

    # Absolute source path when the run started from a pipeline file; None for
    # named runs and for states written before slice 940 (D4).
    pipeline_path: str | None = None

    def active_compact_summary_for_resume(self, resume_step_index: int) -> CompactSummary | None:
        """Return the most recent applicable compact summary for resume.

        Returns the summary whose ``source_step_index`` is the highest value
        strictly less than ``resume_step_index``, or ``None`` if no such
        summary exists.
        """
        applicable = [
            s for s in self.compact_summaries.values() if s.source_step_index < resume_step_index
        ]
        if not applicable:
            return None
        return max(applicable, key=lambda s: s.source_step_index)


@dataclasses.dataclass(frozen=True)
class UnreadableRun:
    """A run-state file that could not be read (slice 174 D9)."""

    path: Path
    mtime: datetime | None  # None when even the file's metadata cannot be read
    reason: str
    # True for a file whose schema version this build does not read: it may be a
    # newer squadron's live run, so it is not junk.
    unsupported_schema: bool = False

    @property
    def run_id(self) -> str:
        return self.path.stem


@dataclasses.dataclass(frozen=True)
class RunScan:
    states: list[RunState]
    unreadable: list[UnreadableRun]


def _unreadable(path: Path, exc: Exception) -> UnreadableRun:
    try:
        mtime: datetime | None = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    except OSError:
        mtime = None  # the file vanished or its directory is unreadable; age is unknown
    return UnreadableRun(
        path,
        mtime,
        f"{type(exc).__name__}: {exc}",
        unsupported_schema=isinstance(exc, SchemaVersionError),
    )


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def state_file_name(run_id: str) -> str:
    """The run-state file name for *run_id*; reports beside it share the prefix."""
    return f"{run_id}.json"


def _default_runs_dir() -> Path:
    return Path.home() / ".config" / "squadron" / "runs"


class StateManager:
    """Manages pipeline run state files on disk."""

    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir if runs_dir is not None else _default_runs_dir()
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def runs_dir(self) -> Path:
        """Where run state files live; per-run artifacts sit beside them."""
        return self._runs_dir

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _state_path(self, run_id: str) -> Path:
        return self._runs_dir / state_file_name(run_id)

    def _write_atomic(self, path: Path, data: str) -> None:
        """Write *data* to *path* atomically via a sibling .tmp file."""
        tmp = path.with_suffix(".tmp")
        tmp.write_text(data, encoding="utf-8")
        tmp.replace(path)

    def _load_raw(self, path: Path) -> RunState:
        """Read, parse, and validate a state file. Raises on version mismatch."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        version = raw.get("schema_version")
        if version not in _SUPPORTED_SCHEMA_VERSIONS:
            raise SchemaVersionError(version)
        return RunState.model_validate(raw)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def init_run(
        self,
        pipeline_name: str,
        params: dict[str, object],
        run_id: str | None = None,
        execution_mode: ExecutionMode = ExecutionMode.SDK,
        *,
        owner: RunOwner | None = None,
        pipeline_path: str | None = None,
    ) -> str:
        """Create an initial state file and return the run_id.

        With *owner*, the write that creates the ``running`` file also records
        the owner, so no v5 ``running`` file is ever ownerless (slice 174 D13).
        With *pipeline_path*, the absolute source file of a path run is kept so
        resume reloads that file rather than a same-named pipeline (slice 940 D4).
        """
        pipeline_name = pipeline_name.lower()
        now = datetime.now(UTC)
        if run_id is None:
            date = now.strftime("%Y%m%d")
            slug = _SLUG_RE.sub("-", pipeline_name).strip("-")
            run_id = f"run-{date}-{slug}-{uuid.uuid4().hex[:8]}"

        state = RunState(
            run_id=run_id,
            pipeline=pipeline_name,
            params=params,
            execution_mode=execution_mode,
            started_at=now,
            updated_at=now,
            status=RUNNING_STATUS,
            owner=owner,
            heartbeat_at=now if owner is not None else None,
            progress_at=now if owner is not None else None,
            pipeline_path=pipeline_path,
        )
        self._save(state)
        self.prune(pipeline_name)
        return run_id

    def observer(self, run_id: str) -> RunObserver:
        """Return the ``RunObserver`` that records *run_id*'s progress (D12)."""
        from squadron.pipeline.run_observer import RunStateRecorder

        return RunStateRecorder(self, run_id)

    def record_step_completed(self, run_id: str, step_result: StepResult) -> None:
        """Append a completed step and record any compact summaries it produced."""
        self._append_step(run_id, step_result)
        self._maybe_record_compact_summaries(run_id, step_result)

    def claim(self, run_id: str, owner: RunOwner) -> None:
        """Mark a resumed run ``running`` under *owner*, in one write (D13).

        Raises ``RuntimeError`` when the run is already ``running`` under a
        live owner. The check and the write are not atomic: two simultaneous
        resumes of one run can both succeed.
        """
        from squadron.pipeline.run_liveness import RunLiveness, assess_liveness

        state = self.load(run_id)
        now = datetime.now(UTC)
        current = assess_liveness(state, now=now, hostname=owner.hostname)
        if state.owner is not None and current is not None and current.liveness is RunLiveness.LIVE:
            raise RuntimeError(
                f"run {run_id} is already running under pid {state.owner.pid} on {state.owner.hostname}"
            )
        state.status = RUNNING_STATUS
        state.owner = owner
        state.heartbeat_at = now
        state.progress_at = now
        state.updated_at = now
        self._save(state)

    def heartbeat(self, run_id: str) -> None:
        """Rewrite ``heartbeat_at`` only; an I/O or read failure logs a WARNING (D6)."""

        def beat(state: RunState, now: datetime) -> None:
            state.heartbeat_at = now

        self._write_progress(run_id, beat, "heartbeat")

    def record_step_started(self, run_id: str, step_name: str) -> None:
        """Record *step_name* as the active step; I/O failure logs a WARNING (D6)."""

        def start(state: RunState, now: datetime) -> None:
            state.active_step = step_name
            state.active_item = None
            state.progress_at = now

        self._write_progress(run_id, start, "step start")

    def record_item_started(self, run_id: str, item: ActiveItem) -> None:
        """Record *item* as the active ``each`` item; I/O failure logs a WARNING (D6)."""

        def start(state: RunState, now: datetime) -> None:
            state.active_item = item
            state.progress_at = now

        self._write_progress(run_id, start, "item start")

    def _write_progress(
        self, run_id: str, change: Callable[[RunState, datetime], None], what: str
    ) -> None:
        """Load, *change* and rewrite the run's state; expected failures are not fatal.

        A run is not killed because its bookkeeping failed: an I/O or read
        error is logged and the run continues, turning stale if it persists
        (D6). Any other exception is a defect and propagates.
        """
        try:
            state = self.load(run_id)
            change(state, datetime.now(UTC))
            self._save(state)
        except STATE_READ_ERRORS as exc:
            _logger.warning("run %s: %s write failed: %s", run_id, what, exc)

    def _save(self, state: RunState) -> None:
        self._write_atomic(
            self._state_path(state.run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )

    def _maybe_record_compact_summaries(self, run_id: str, step_result: StepResult) -> None:
        """Inspect action results for compact summaries and persist them."""
        for ar in step_result.action_results:
            if ar.action_type != "summary" or not ar.success:
                continue
            outputs = ar.outputs
            if "summary" not in outputs or "source_step_index" not in outputs:
                continue
            # Only record when a successful rotate emit is present.
            emit_results = outputs.get("emit_results")
            if not isinstance(emit_results, list):
                continue
            has_rotate = False
            for entry in cast(list[object], emit_results):
                if not isinstance(entry, dict):
                    continue
                entry_dict = cast(dict[str, object], entry)
                if entry_dict.get("destination") == "rotate" and entry_dict.get("ok") is True:
                    has_rotate = True
                    break
            if not has_rotate:
                continue
            key = f"{outputs['source_step_index']}:{outputs['source_step_name']}"
            summary_model = outputs.get("summary_model")
            summary = CompactSummary(
                key=key,
                text=str(outputs["summary"]),
                summary_model=(str(summary_model) if isinstance(summary_model, str) else None),
                source_step_index=int(outputs["source_step_index"]),  # type: ignore[arg-type]
                source_step_name=str(outputs["source_step_name"]),
                created_at=datetime.now(UTC),
            )
            self.record_compact_summary(run_id, summary)

    def _append_step(self, run_id: str, step_result: StepResult) -> None:
        """Append a completed step to the persisted run state."""
        state = self.load(run_id)
        now = datetime.now(UTC)

        # Extract verdict from last non-None action verdict
        verdict: str | None = None
        for ar in reversed(step_result.action_results):
            if ar.verdict is not None:
                verdict = ar.verdict
                break

        # Numeric scoring foundation (slice 300): hoist the last non-None
        # action score, mirroring the verdict hoist above.
        score: float | None = None
        for ar in reversed(step_result.action_results):
            if ar.score is not None:
                score = ar.score
                break

        # Extract outputs from last action
        outputs: dict[str, object] = {}
        if step_result.action_results:
            outputs = step_result.action_results[-1].outputs

        # Serialize action_results as plain dicts
        action_results_dicts = [dataclasses.asdict(ar) for ar in step_result.action_results]

        step_state = StepState(
            step_name=step_result.step_name,
            step_type=step_result.step_type,
            status=step_result.status.value,
            verdict=verdict,
            score=score,
            outputs=outputs,
            action_results=action_results_dicts,
            iteration=step_result.iteration,
            completed_at=now,
        )
        state.completed_steps.append(step_state)
        state.updated_at = now
        state.current_step = step_result.step_name
        state.active_item = None
        state.progress_at = now

        if step_result.status == ExecutionStatus.PAUSED:
            state.status = ExecutionStatus.PAUSED.value
            state.checkpoint = CheckpointState(
                reason=step_result.error or "checkpoint",
                step=step_result.step_name,
                verdict=verdict,
                paused_at=now,
            )

        self._save(state)

    def record_compact_summary(self, run_id: str, summary: CompactSummary) -> None:
        """Add or replace a compact summary in the run state and persist.

        Keyed by ``summary.key``; an existing entry with the same key is
        overwritten.
        """
        state = self.load(run_id)
        state.compact_summaries[summary.key] = summary
        state.updated_at = datetime.now(UTC)
        self._save(state)

    def log_pool_selection(self, run_id: str, selection: object) -> None:
        """Append a pool selection record to the run's state file.

        ``selection`` must be a ``PoolSelection`` dataclass; the type is
        declared as ``object`` to avoid a module-level import of the pools
        package (which would create a circular dependency).
        """
        state = self.load(run_id)
        # PoolSelection is a frozen dataclass — access attrs directly.
        entry: dict[str, object] = {
            "pool_name": selection.pool_name,  # type: ignore[union-attr]
            "selected_alias": selection.selected_alias,  # type: ignore[union-attr]
            "strategy": selection.strategy,  # type: ignore[union-attr]
            "step_name": selection.step_name,  # type: ignore[union-attr]
            "action_type": selection.action_type,  # type: ignore[union-attr]
            "timestamp": selection.timestamp.isoformat(),  # type: ignore[union-attr]
        }
        state.pool_selections.append(entry)
        state.updated_at = datetime.now(UTC)
        self._save(state)

    def finalize(self, run_id: str, result: PipelineResult) -> None:
        """Write terminal status to the run file."""
        state = self.load(run_id)
        state.status = result.status.value
        state.updated_at = datetime.now(UTC)
        # Clear current_step for terminal statuses
        if result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            state.current_step = None
        # The owner record stays as history; liveness is assessed only while running.
        state.active_step = None
        state.active_item = None
        self._save(state)

    def record_step_done(
        self,
        run_id: str,
        step_name: str,
        step_type: str,
        verdict: str | None = None,
    ) -> None:
        """Mark a step as completed in prompt-only mode.

        Constructs a minimal ``StepResult`` and delegates to
        ``_append_step()`` for persistence.

        Raises FileNotFoundError if the run does not exist.
        """
        action_results: list[ActionResult] = []
        if verdict is not None:
            action_results.append(
                ActionResult(
                    success=True,
                    action_type="prompt-only-feedback",
                    outputs={},
                    verdict=verdict,
                )
            )

        step_result = StepResult(
            step_name=step_name,
            step_type=step_type,
            status=ExecutionStatus.COMPLETED,
            action_results=action_results,
        )
        self._append_step(run_id, step_result)

    def load(self, run_id: str) -> RunState:
        """Load and validate a run state file.

        Raises FileNotFoundError if the file does not exist.
        Raises SchemaVersionError if schema_version is not supported.
        """
        path = self._state_path(run_id)
        if not path.exists():
            raise FileNotFoundError(f"No state file for run_id={run_id!r}")
        return self._load_raw(path)

    def load_prior_outputs(self, run_id: str) -> dict[str, ActionResult]:
        """Reconstruct prior_outputs from stored action_results."""
        state = self.load(run_id)
        prior: dict[str, ActionResult] = {}
        valid_fields = set(ActionResult.__dataclass_fields__)
        for step_state in state.completed_steps:
            for idx, ar_dict in enumerate(step_state.action_results):
                action_type = ar_dict.get("action_type", "unknown")
                filtered = {k: v for k, v in ar_dict.items() if k in valid_fields}
                try:
                    action_result = ActionResult(**filtered)  # type: ignore[arg-type]
                except TypeError:
                    # ActionResult is a plain dataclass; the only realistic
                    # failure from an arbitrary stored dict is a missing
                    # required field (e.g. success/action_type/outputs absent
                    # from an older or hand-edited state file). One bad
                    # record must not block reconstructing the rest.
                    _logger.warning(
                        "Could not reconstruct ActionResult from stored dict: %r",
                        ar_dict,
                        exc_info=True,
                    )
                    continue
                key = f"{action_type}-{idx}"
                prior[key] = action_result
        return prior

    def first_unfinished_step(self, run_id: str, definition: PipelineDefinition) -> str | None:
        """Load *run_id* and return its first unfinished step (see first_unfinished_step_of)."""
        return first_unfinished_step_of(self.load(run_id), definition)

    def resume_iteration_for(self, run_id: str, step_name: str) -> int:
        """Return the recorded loop iteration to resume *step_name* at.

        First reader of StepState.iteration. Returns 0 (the established
        "not in a loop" sentinel; see ActionContext.iteration and
        _execute_step_once) when the step is absent from completed_steps or
        its recorded iteration is 0. If the step name appears more than
        once, returns the last occurrence's iteration.
        """
        state = self.load(run_id)
        iteration = 0
        for step_state in state.completed_steps:
            if step_state.step_name == step_name:
                iteration = step_state.iteration
        return iteration

    def scan_runs(self) -> RunScan:
        """Every run-state file: the readable states and the unreadable files (174 D9).

        Unlike ``list_runs``, an unreadable file is returned, not logged, so a
        caller can act on it (``sq runs prune``).
        """
        states: list[RunState] = []
        unreadable: list[UnreadableRun] = []
        for path in self._state_files():
            try:
                states.append(self._load_raw(path))
            except STATE_READ_ERRORS as exc:
                unreadable.append(_unreadable(path, exc))
        return RunScan(states, unreadable)

    def _state_files(self) -> list[Path]:
        """Run-state files in the runs dir; batch reports beside them are not runs."""
        from squadron.pipeline.batch_report import REPORT_JSON_SUFFIX

        return [
            path
            for path in self._runs_dir.glob("*.json")
            if not path.name.endswith(REPORT_JSON_SUFFIX)  # slice 197 D7
        ]

    def list_runs(
        self,
        pipeline: str | None = None,
        status: str | None = None,
    ) -> list[RunState]:
        """List all run states, optionally filtered, sorted by started_at desc."""
        runs: list[RunState] = []
        for path in self._state_files():
            try:
                run = self._load_raw(path)
            except STATE_READ_ERRORS:
                # One bad run-state file must not stop the rest of the listing.
                _logger.warning("Skipping unreadable state file: %s", path, exc_info=True)
                continue
            if pipeline is not None and run.pipeline != pipeline:
                continue
            if status is not None and run.status != status:
                continue
            runs.append(run)
        runs.sort(key=lambda r: r.started_at, reverse=True)
        return runs

    def find_matching_run(
        self,
        pipeline_name: str,
        params: dict[str, object],
        status: str | None = "paused",
    ) -> RunState | None:
        """Find most recent run matching pipeline+params with given status."""
        for run in self.list_runs(pipeline=pipeline_name, status=status):
            if run.params == params:
                return run
        return None

    def prune(self, pipeline_name: str, keep: int = 10) -> int:
        """Delete oldest completed/failed runs beyond *keep* for *pipeline_name*.

        Paused runs are never pruned. Returns count of deleted files.
        """
        terminal_statuses = {
            ExecutionStatus.COMPLETED.value,
            ExecutionStatus.FAILED.value,
        }
        candidates = [
            r for r in self.list_runs(pipeline=pipeline_name) if r.status in terminal_statuses
        ]
        # list_runs returns desc; reverse to get oldest-first
        candidates.sort(key=lambda r: r.started_at)

        to_delete = candidates[: max(0, len(candidates) - keep)]
        deleted = 0
        for run in to_delete:
            path = self._state_path(run.run_id)
            try:
                path.unlink()
                deleted += 1
            except FileNotFoundError:
                pass
        return deleted
