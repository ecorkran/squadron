---
docType: slice-design
slice: pipeline-state-and-resume
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [149]
interfaces: [151]
dateCreated: 20260403
dateUpdated: 20260403
status: not_started
---

# Slice Design: Pipeline State and Resume

## Overview

Implement persistent pipeline run state so that interrupted or paused runs can
be resumed without restarting from the beginning. State is written to disk as
JSON after every completed step (using the executor's `on_step_complete`
callback). Resume reconstructs `prior_outputs` from persisted state and calls
`execute_pipeline` with `start_from` pointing at the first unfinished step.
Old run files are pruned automatically to prevent unbounded growth.

This slice is a library only — no CLI surface. Slice 151 wires the state
manager into `sq run`.

---

## Value

- **Resilient pipelines.** A long-running pipeline interrupted mid-way (network
  drop, checkpoint pause, unhandled exception) can resume from where it stopped
  rather than restarting all completed steps.
- **Checkpoint continuity.** When a checkpoint action pauses execution for human
  review, the human can resume days later with `sq run --resume <run-id>`.
- **Mid-process adoption.** `--from <step>` lets users adopt a partially-done
  pipeline (e.g. design and tasks already exist) without faking prior steps.
- **Implicit resume detection.** Callers can query for an existing run matching
  a pipeline+params combination and offer the user a resume prompt.

---

## Technical Scope

### Included

1. **`RunState` Pydantic model** — structured representation of the JSON state
   file: run_id, pipeline name, params, started_at, status, current_step,
   completed steps with outputs and verdicts, checkpoint metadata.

2. **`StateManager`** — creates, updates, loads, lists, and prunes state files
   in `~/.config/squadron/runs/`.

3. **`StepState`** — per-step record: step name, step type, status, action
   results (including verdict and outputs), completed_at timestamp.

4. **`on_step_complete` integration** — `StateManager` provides a callback
   factory (`make_step_callback(run_id)`) that writes updated state to disk
   after every step. Passed as `on_step_complete` to `execute_pipeline`.

5. **`prior_outputs` reconstruction** — `StateManager.load_prior_outputs(run_id)`
   rebuilds the `dict[str, ActionResult]` the executor expects for a resumed run.

6. **`find_matching_run`** — given pipeline name + params dict, return the most
   recent non-pruned run matching those values (for implicit resume detection).

7. **Run pruning** — `StateManager.prune(keep=10)` deletes the oldest run files
   beyond the `keep` threshold, per-pipeline. Pruning runs automatically when a
   new run is initialized.

8. **Schema versioning** — `schema_version: int` field in state JSON. Version 1
   for this slice. A `SchemaVersionError` is raised if a loaded file has an
   unsupported version.

### Excluded

- **CLI command surface** — slice 151. `StateManager` is a pure library;
  `sq run --resume` is wired in 151.
- **Interactive checkpoint UX** — the checkpoint action (slice 146) handles
  pause/resume interaction. This slice only persists the paused state.
- **Conversation persistence across steps** — 160 scope.
- **State migration between schema versions** — only schema_version=1 in this
  slice. Future migrations are 160+ scope.

---

## Dependencies

### Prerequisites

- **Slice 149** (Executor and Loops) — `StepResult`, `PipelineResult`,
  `ExecutionStatus`, `ActionResult`, `execute_pipeline(on_step_complete=...)`,
  and `start_from` parameter are all required.

### Interfaces Required

- `executor.StepResult` — deserialized from stored `StepState` for callback writes.
- `executor.execute_pipeline(start_from=..., on_step_complete=...)` — resume uses both.
- `models.ActionResult` — reconstructed from stored step outputs for `prior_outputs`.

---

## Architecture

### Component Structure

```
src/squadron/pipeline/
├── state.py           # NEW: StateManager, RunState, StepState
└── executor.py        # EXISTING: on_step_complete callback consumed here
```

State files live at:
```
~/.config/squadron/runs/
    <run-id>.json          # one file per run
```

Run IDs follow the pattern `run-<YYYYMMDD>-<pipeline>-<hash8>` where `hash8`
is the first 8 hex digits of `uuid4()`. Example:
`run-20260403-slice-lifecycle-a3f7b21c`.

### Data Flow

**New run:**
```
caller
  → StateManager.init_run(pipeline, params) → writes initial JSON (status=running)
  → execute_pipeline(..., on_step_complete=mgr.make_step_callback(run_id))
      → [after each step] callback fires → StateManager._write_step(run_id, step_result)
      → [on pipeline end] caller invokes StateManager.finalize(run_id, result)
```

**Resume:**
```
caller
  → StateManager.load(run_id) → RunState
  → start_from = first unfinished step from RunState
  → prior_outputs = StateManager.load_prior_outputs(run_id)
  → execute_pipeline(start_from=..., on_step_complete=..., run_id=run_id)
```

### State File Schema (JSON, schema_version=1)

```json
{
  "schema_version": 1,
  "run_id": "run-20260403-slice-lifecycle-a3f7b21c",
  "pipeline": "slice-lifecycle",
  "params": { "slice": "191" },
  "started_at": "2026-04-03T14:30:00Z",
  "updated_at": "2026-04-03T14:42:00Z",
  "status": "paused",
  "current_step": "implement",
  "completed_steps": [
    {
      "step_name": "design",
      "step_type": "phase",
      "status": "completed",
      "verdict": "PASS",
      "outputs": { "design_file": "191-slice.some-feature.md" },
      "completed_at": "2026-04-03T14:35:00Z"
    },
    {
      "step_name": "compact-2",
      "step_type": "compact",
      "status": "completed",
      "verdict": null,
      "outputs": {},
      "completed_at": "2026-04-03T14:40:00Z"
    }
  ],
  "checkpoint": {
    "reason": "on_concerns",
    "step": "implement",
    "verdict": "CONCERNS",
    "paused_at": "2026-04-03T15:01:00Z"
  }
}
```

Field notes:
- `status` mirrors `ExecutionStatus` string values: `"running"`, `"completed"`,
  `"paused"`, `"failed"`.
- `current_step` is the step that is currently executing or paused at. `null`
  when `status=completed` or `status=failed` with no partial step.
- `checkpoint` is only present when `status=paused`.
- `outputs` in each completed step stores the `ActionResult.outputs` dict from
  the *last* action in the step (the one carrying the step's primary output).
  For phases, this is typically the review action's `findings` or the commit
  action's file path. All action results are in `action_results` for full
  fidelity.
- `action_results` is an optional extended field (list of all
  `ActionResult`-compatible dicts) used to reconstruct `prior_outputs` for
  resume. When space is a concern this can be omitted and `prior_outputs` will
  be empty on resume (resume still works; actions just won't see prior step
  outputs).

### Pydantic Models

```python
class StepState(BaseModel):
    step_name: str
    step_type: str
    status: str                        # ExecutionStatus string value
    verdict: str | None = None
    outputs: dict[str, object] = {}
    action_results: list[dict[str, object]] = []  # raw ActionResult dicts
    completed_at: datetime

class CheckpointState(BaseModel):
    reason: str
    step: str
    verdict: str | None = None
    paused_at: datetime

class RunState(BaseModel):
    schema_version: int = 1
    run_id: str
    pipeline: str
    params: dict[str, object]
    started_at: datetime
    updated_at: datetime
    status: str                        # ExecutionStatus string value
    current_step: str | None = None
    completed_steps: list[StepState] = []
    checkpoint: CheckpointState | None = None
```

`RunState` is a Pydantic model (external boundary: file I/O). `StepState` and
`CheckpointState` likewise. Serialized with `model.model_dump(mode="json")`,
deserialized with `RunState.model_validate(json.loads(...))`.

### StateManager Interface

```python
class StateManager:
    def __init__(self, runs_dir: Path | None = None) -> None:
        # Default: Path.home() / ".config" / "squadron" / "runs"
        # runs_dir is injected for tests

    def init_run(
        self,
        pipeline_name: str,
        params: dict[str, object],
        run_id: str | None = None,
    ) -> str:
        # Create initial state file. Returns run_id.
        # Generates run_id if not provided.
        # Auto-prunes old runs for this pipeline.

    def make_step_callback(
        self, run_id: str
    ) -> Callable[[StepResult], None]:
        # Returns a function suitable for execute_pipeline's on_step_complete.
        # Each call appends a completed StepState to the run file.

    def finalize(self, run_id: str, result: PipelineResult) -> None:
        # Write final status (completed/failed) and updated_at to run file.

    def load(self, run_id: str) -> RunState:
        # Load and validate a run file. Raises FileNotFoundError or
        # SchemaVersionError if incompatible.

    def load_prior_outputs(self, run_id: str) -> dict[str, ActionResult]:
        # Reconstruct the prior_outputs dict from stored action_results.
        # Returns {} if action_results not stored.

    def first_unfinished_step(
        self, run_id: str, definition: PipelineDefinition
    ) -> str | None:
        # Return name of first step in definition not present in
        # completed_steps. Returns None if all steps complete.

    def list_runs(
        self,
        pipeline: str | None = None,
        status: str | None = None,
    ) -> list[RunState]:
        # List run states, optionally filtered by pipeline name and/or status.
        # Sorted by started_at descending (most recent first).

    def find_matching_run(
        self,
        pipeline_name: str,
        params: dict[str, object],
        status: str | None = "paused",
    ) -> RunState | None:
        # Find most recent run for pipeline+params with given status.
        # Params comparison is exact equality on string values.

    def prune(self, pipeline_name: str, keep: int = 10) -> int:
        # Delete oldest completed/failed runs for pipeline beyond `keep`.
        # Paused runs are not pruned. Returns count of deleted files.
```

---

## Technical Decisions

### Pydantic for State Files

State files are an external boundary (written and read from disk, potentially
hand-edited or inspected by users). Pydantic gives automatic validation and
clean serialization, consistent with the project's pattern for external
boundaries.

### Atomic Writes

State files are updated after every step completion. Use a write-then-rename
pattern (`tmp_path.write_text(...)` → `tmp_path.rename(final_path)`) to avoid
partial writes leaving a corrupt state file if interrupted.

### `prior_outputs` Reconstruction Strategy

`ActionResult` is a dataclass, not a Pydantic model. Serialization stores each
`ActionResult` as a plain dict. Reconstruction calls `ActionResult(**d)` for
each stored dict, with a defensive fallback (empty dict) for any field not
present in the stored version.

The executor's `prior_outputs` dict uses keys of the form
`"{action_type}-{index_within_step}"`. The stored `action_results` list
preserves insertion order, so reconstruction replays the same key generation
logic.

### Pruning Strategy

Pruning is per-pipeline (not global) so that a single heavily-used pipeline
doesn't crowd out others. Default `keep=10`. Pruning runs automatically in
`init_run` to avoid users needing to call it manually. Paused runs are never
auto-pruned (the user may still intend to resume them).

### Run ID Format

`run-{YYYYMMDD}-{pipeline_name}-{hash8}` where `hash8 = uuid4().hex[:8]`.
Pipeline name has spaces/underscores normalized to `-` for filesystem safety.
Example: `run-20260403-slice-lifecycle-a3f7b21c`. This is human-readable in
directory listings, making it easy to identify runs by date and pipeline.

---

## Integration Points

### Provides to Slice 151 (CLI Integration)

- `StateManager` with the full interface above
- `RunState`, `StepState`, `CheckpointState` Pydantic models
- `SchemaVersionError` exception type
- `StateManager.find_matching_run()` for implicit resume detection
- `StateManager.list_runs()` for `sq run --list`
- `StateManager.first_unfinished_step()` for resume `start_from` resolution

### Consumes from Slice 149 (Executor)

- `on_step_complete: Callable[[StepResult], None]` — callback signature
- `StepResult.step_name`, `.step_type`, `.status`, `.action_results`, `.error`
- `PipelineResult.status`, `.step_results`, `.paused_at`
- `execute_pipeline(start_from=..., run_id=..., on_step_complete=...)`

---

## Success Criteria

### Functional Requirements

1. `StateManager.init_run()` creates a valid JSON state file under `~/.config/squadron/runs/`.
2. The `on_step_complete` callback appends a completed step to the state file
   after each step executes.
3. `StateManager.finalize()` sets terminal status (`completed` or `failed`) and
   `updated_at`.
4. `StateManager.load()` deserializes a state file into a valid `RunState`.
5. `StateManager.load_prior_outputs()` returns a non-empty `dict[str, ActionResult]`
   for a completed run that stored `action_results`.
6. `StateManager.first_unfinished_step()` returns the correct next step when
   some steps are complete and some are not.
7. `StateManager.find_matching_run()` returns the most recent paused run for
   the given pipeline+params, or `None` if no match.
8. `StateManager.prune()` deletes completed/failed runs beyond `keep`,
   preserves paused runs, and returns the count deleted.
9. `SchemaVersionError` raised when loading a file with `schema_version != 1`.
10. Atomic writes: interrupted writes do not corrupt the existing state file.

### Technical Requirements

- Pydantic models for all state types (RunState, StepState, CheckpointState).
- All public methods type-annotated; pyright strict, zero errors.
- `ruff` clean.
- Test coverage: unit tests use a `tmp_path` fixture (no real `~/.config`).
- Tests cover: init, step append, finalize, load, prior_outputs reconstruction,
  find_matching_run, prune, SchemaVersionError, atomic write behavior.

### Integration Requirements

- `execute_pipeline` with `on_step_complete=mgr.make_step_callback(run_id)`
  produces a state file that reflects all completed steps after a full run.
- A resumed pipeline (via `start_from + load_prior_outputs`) completes
  correctly with the reconstructed `prior_outputs` context.

---

## Verification Walkthrough

These are draft verification steps, to be refined with actual commands after
Phase 6 implementation.

**1. State file is created and updated during a test run:**

```python
# In a pytest session with tmp_path
from squadron.pipeline.state import StateManager
from squadron.pipeline.executor import execute_pipeline

mgr = StateManager(runs_dir=tmp_path)
run_id = mgr.init_run("slice-lifecycle", {"slice": "191"})
# State file exists
assert (tmp_path / f"{run_id}.json").exists()

await execute_pipeline(
    definition,
    {"slice": "191"},
    ...,
    run_id=run_id,
    on_step_complete=mgr.make_step_callback(run_id),
)
mgr.finalize(run_id, result)

state = mgr.load(run_id)
assert state.status == "completed"
assert len(state.completed_steps) == 5   # slice-lifecycle has 5 steps
```

**2. Resume from a paused run:**

```python
run_id = mgr.init_run("slice-lifecycle", {"slice": "191"})

# Simulate a run that pauses after step 2
...  # (mock checkpoint action to pause on step 3)

state = mgr.load(run_id)
assert state.status == "paused"
assert state.current_step == "implement"

start_from = mgr.first_unfinished_step(run_id, definition)
prior_outputs = mgr.load_prior_outputs(run_id)

result = await execute_pipeline(
    definition,
    {"slice": "191"},
    ...,
    run_id=run_id,
    start_from=start_from,
    on_step_complete=mgr.make_step_callback(run_id),
)
mgr.finalize(run_id, result)

final = mgr.load(run_id)
assert final.status == "completed"
assert len(final.completed_steps) == 5
```

**3. Implicit run detection:**

```python
mgr.init_run("slice-lifecycle", {"slice": "191"})
# ...simulate paused state...

match = mgr.find_matching_run("slice-lifecycle", {"slice": "191"}, status="paused")
assert match is not None
assert match.params["slice"] == "191"
```

**4. Pruning:**

```python
# Create 12 completed runs for same pipeline
for _ in range(12):
    rid = mgr.init_run("review-only", {"slice": "10", "template": "arch"})
    mgr.finalize(rid, completed_result)

deleted = mgr.prune("review-only", keep=10)
assert deleted == 2
assert len(list(tmp_path.glob("*.json"))) == 10
```

**5. Schema version mismatch:**

```python
from squadron.pipeline.state import SchemaVersionError

bad_file = tmp_path / "run-bad.json"
bad_file.write_text('{"schema_version": 99, "run_id": "run-bad", ...}')

with pytest.raises(SchemaVersionError):
    mgr.load("run-bad")
```

---

## Implementation Notes

### Development Approach

1. Define `RunState`, `StepState`, `CheckpointState` Pydantic models and
   `SchemaVersionError`.
2. Implement `StateManager.__init__` and `init_run` with atomic write helper.
3. Implement `make_step_callback` and the internal `_append_step` method.
4. Implement `finalize`.
5. Implement `load` and `load_prior_outputs`.
6. Implement `first_unfinished_step`, `list_runs`, `find_matching_run`.
7. Implement `prune`.
8. Write unit tests throughout using `tmp_path` fixture.
9. Integration test: full run → finalize → load confirms all steps present.

### Special Considerations

- **`runs_dir` injection** — Always inject `runs_dir` in tests via
  `StateManager(runs_dir=tmp_path)`. Never read/write to real `~/.config`
  in tests.
- **`action_results` storage** — `ActionResult` is a dataclass. Store as
  `dataclasses.asdict(ar)` and reconstruct with `ActionResult(**d)`. Field
  `findings` is `list[object]`; store as-is (JSON serializable in practice).
- **`verdict` extraction** — The step's verdict comes from the most recent
  `ActionResult.verdict` that is not `None` in the step's action list.
