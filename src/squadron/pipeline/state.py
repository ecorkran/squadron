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
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel

from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
from squadron.pipeline.models import ActionResult

if TYPE_CHECKING:
    from squadron.pipeline.models import PipelineDefinition

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

_SCHEMA_VERSION = 4
_SUPPORTED_SCHEMA_VERSIONS = {3, 4}


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


# ---------------------------------------------------------------------------
# Pydantic models (external boundary: file I/O)
# ---------------------------------------------------------------------------


class StepState(BaseModel):
    """Persisted record of a single completed pipeline step."""

    step_name: str
    step_type: str
    status: str  # ExecutionStatus string value
    verdict: str | None = None
    outputs: dict[str, object] = {}
    action_results: list[dict[str, object]] = []
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

    def active_compact_summary_for_resume(
        self, resume_step_index: int
    ) -> CompactSummary | None:
        """Return the most recent applicable compact summary for resume.

        Returns the summary whose ``source_step_index`` is the highest value
        strictly less than ``resume_step_index``, or ``None`` if no such
        summary exists.
        """
        applicable = [
            s
            for s in self.compact_summaries.values()
            if s.source_step_index < resume_step_index
        ]
        if not applicable:
            return None
        return max(applicable, key=lambda s: s.source_step_index)


# ---------------------------------------------------------------------------
# StateManager
# ---------------------------------------------------------------------------

_DEFAULT_RUNS_DIR = Path.home() / ".config" / "squadron" / "runs"
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class StateManager:
    """Manages pipeline run state files on disk."""

    def __init__(self, runs_dir: Path | None = None) -> None:
        self._runs_dir = runs_dir if runs_dir is not None else _DEFAULT_RUNS_DIR
        self._runs_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _state_path(self, run_id: str) -> Path:
        return self._runs_dir / f"{run_id}.json"

    def _write_atomic(self, path: Path, data: str) -> None:
        """Write *data* to *path* atomically via a sibling .tmp file."""
        tmp = path.with_suffix(".tmp")
        tmp.write_text(data, encoding="utf-8")
        tmp.rename(path)

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
    ) -> str:
        """Create an initial state file and return the run_id."""
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
            status="running",
        )
        self._write_atomic(
            self._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )
        self.prune(pipeline_name)
        return run_id

    def make_step_callback(self, run_id: str) -> Callable[[StepResult], None]:
        """Return a closure for use as execute_pipeline's on_step_complete."""

        def _callback(step_result: StepResult) -> None:
            self._append_step(run_id, step_result)
            self._maybe_record_compact_summaries(run_id, step_result)

        return _callback

    def _maybe_record_compact_summaries(
        self, run_id: str, step_result: StepResult
    ) -> None:
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
                if (
                    entry_dict.get("destination") == "rotate"
                    and entry_dict.get("ok") is True
                ):
                    has_rotate = True
                    break
            if not has_rotate:
                continue
            key = f"{outputs['source_step_index']}:{outputs['source_step_name']}"
            summary_model = outputs.get("summary_model")
            summary = CompactSummary(
                key=key,
                text=str(outputs["summary"]),
                summary_model=(
                    str(summary_model) if isinstance(summary_model, str) else None
                ),
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

        # Extract outputs from last action
        outputs: dict[str, object] = {}
        if step_result.action_results:
            outputs = step_result.action_results[-1].outputs

        # Serialize action_results as plain dicts
        action_results_dicts = [
            dataclasses.asdict(ar) for ar in step_result.action_results
        ]

        step_state = StepState(
            step_name=step_result.step_name,
            step_type=step_result.step_type,
            status=step_result.status.value,
            verdict=verdict,
            outputs=outputs,
            action_results=action_results_dicts,
            completed_at=now,
        )
        state.completed_steps.append(step_state)
        state.updated_at = now
        state.current_step = step_result.step_name

        if step_result.status == ExecutionStatus.PAUSED:
            state.status = ExecutionStatus.PAUSED.value
            state.checkpoint = CheckpointState(
                reason=step_result.error or "checkpoint",
                step=step_result.step_name,
                verdict=verdict,
                paused_at=now,
            )

        self._write_atomic(
            self._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )

    def record_compact_summary(self, run_id: str, summary: CompactSummary) -> None:
        """Add or replace a compact summary in the run state and persist.

        Keyed by ``summary.key``; an existing entry with the same key is
        overwritten.
        """
        state = self.load(run_id)
        state.compact_summaries[summary.key] = summary
        state.updated_at = datetime.now(UTC)
        self._write_atomic(
            self._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )

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
        self._write_atomic(
            self._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )

    def finalize(self, run_id: str, result: PipelineResult) -> None:
        """Write terminal status to the run file."""
        state = self.load(run_id)
        state.status = result.status.value
        state.updated_at = datetime.now(UTC)
        # Clear current_step for terminal statuses
        if result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.FAILED):
            state.current_step = None
        self._write_atomic(
            self._state_path(run_id),
            json.dumps(state.model_dump(mode="json"), indent=2),
        )

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
                except Exception:
                    _logger.warning(
                        "Could not reconstruct ActionResult from stored dict: %r",
                        ar_dict,
                    )
                    continue
                key = f"{action_type}-{idx}"
                prior[key] = action_result
        return prior

    def first_unfinished_step(
        self, run_id: str, definition: PipelineDefinition
    ) -> str | None:
        """Return name of the first step in definition not in completed_steps."""
        state = self.load(run_id)
        completed = {s.step_name for s in state.completed_steps}
        for step in definition.steps:
            if step.name not in completed:
                return step.name
        return None

    def list_runs(
        self,
        pipeline: str | None = None,
        status: str | None = None,
    ) -> list[RunState]:
        """List all run states, optionally filtered, sorted by started_at desc."""
        runs: list[RunState] = []
        for path in self._runs_dir.glob("*.json"):
            try:
                run = self._load_raw(path)
            except Exception:
                _logger.warning("Skipping unreadable state file: %s", path)
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
            r
            for r in self.list_runs(pipeline=pipeline_name)
            if r.status in terminal_statuses
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
