---
docType: tasks
slice: pipeline-state-and-resume
project: squadron
lld: project-documents/user/slices/150-slice.pipeline-state-and-resume.md
dependencies: [149]
projectState: Slice 149 (executor) complete on branch 149-pipeline-executor-and-loops. Branch 150-pipeline-state-and-resume created from it.
dateCreated: 20260403
dateUpdated: 20260403
status: complete
---

## Context Summary

- Implementing `src/squadron/pipeline/state.py` — a library module (no CLI surface)
- Provides `StateManager`, `RunState`, `StepState`, `CheckpointState`, `SchemaVersionError`
- State files written as JSON to `~/.config/squadron/runs/` using atomic write-then-rename
- `on_step_complete` callback from executor drives incremental state updates
- Resume reconstructs `prior_outputs` from stored `action_results` and passes `start_from` to executor
- All tests use `tmp_path` fixture — never touch real `~/.config`
- Slice 151 (CLI) is the sole consumer of this module's public interface
- One new file: `src/squadron/pipeline/state.py`
- One new test file: `tests/pipeline/test_state.py`

---

## Tasks

- [x] **T1 — Test infrastructure: conftest fixture**
  - [x] In `tests/pipeline/conftest.py`, add a `state_manager` fixture that returns
        `StateManager(runs_dir=tmp_path)` using pytest's built-in `tmp_path`
  - [x] Add a `completed_pipeline_result` fixture returning a `PipelineResult` with
        `status=ExecutionStatus.COMPLETED` and one dummy `StepResult`
  - [x] Verify fixture is importable with no errors (`pytest --collect-only`)
  - [x] Success: fixtures available in `tests/pipeline/` scope with no import errors

- [x] **T2 — Pydantic models: `StepState`, `CheckpointState`, `RunState`**
  - [x] Create `src/squadron/pipeline/state.py`
  - [x] Define `StepState(BaseModel)` with fields: `step_name: str`, `step_type: str`,
        `status: str`, `verdict: str | None = None`,
        `outputs: dict[str, object] = {}`,
        `action_results: list[dict[str, object]] = []`,
        `completed_at: datetime`
  - [x] Define `CheckpointState(BaseModel)` with fields: `reason: str`, `step: str`,
        `verdict: str | None = None`, `paused_at: datetime`
  - [x] Define `RunState(BaseModel)` with fields: `schema_version: int = 1`,
        `run_id: str`, `pipeline: str`, `params: dict[str, object]`,
        `started_at: datetime`, `updated_at: datetime`, `status: str`,
        `current_step: str | None = None`,
        `completed_steps: list[StepState] = []`,
        `checkpoint: CheckpointState | None = None`
  - [x] Define `SchemaVersionError(Exception)` with message carrying the offending version
  - [x] Export all four from module `__all__`
  - [x] Success: `from squadron.pipeline.state import RunState, StepState, CheckpointState, SchemaVersionError` works; pyright strict 0 errors on the file

- [x] **T3 — Tests: Pydantic models**
  - [x] Create `tests/pipeline/test_state.py`
  - [x] Test `RunState` round-trips through `model_dump(mode="json")` → `RunState.model_validate()`
  - [x] Test `StepState` with all optional fields omitted deserializes with correct defaults
  - [x] Test `CheckpointState` round-trip
  - [x] Test `SchemaVersionError` can be raised and caught as `Exception`
  - [x] All tests pass; pyright 0 errors on test file

- [x] **T4 — `StateManager.__init__` and atomic write helper**
  - [x] Add `StateManager` class with `__init__(self, runs_dir: Path | None = None)`
  - [x] Default `runs_dir` = `Path.home() / ".config" / "squadron" / "runs"`; create it if absent
  - [x] Add private `_write_atomic(path: Path, data: str) -> None` — writes to a `.tmp`
        sibling then renames to `path` (atomic on POSIX; acceptable on Windows)
  - [x] Add private `_state_path(run_id: str) -> Path` — returns `runs_dir / f"{run_id}.json"`
  - [x] Success: `StateManager(runs_dir=tmp_path)` creates the directory if missing; `tmp_path` is used (no real `~/.config` accessed)

- [x] **T4a — Tests: atomic write helper**
  - [x] Test that `_write_atomic` creates the target file with the expected content
  - [x] Test that a `.tmp` sibling left from a prior interrupted write is overwritten cleanly
        (write a stale `.tmp` file manually, then call `_write_atomic` and verify target is correct)
  - [x] Test that the original target file is not modified if a second write's content is
        the same (i.e., the rename is idempotent and the original survives a new write)
  - [x] All tests pass; no `.tmp` files left on disk after any passing test

- [x] **T5 — `StateManager.init_run`**
  - [x] Implement `init_run(self, pipeline_name: str, params: dict[str, object], run_id: str | None = None) -> str`
  - [x] If `run_id` is `None`, generate: `f"run-{date}-{slug}-{uuid4().hex[:8]}"` where
        `date = datetime.now(UTC).strftime("%Y%m%d")` and
        `slug = re.sub(r"[^a-z0-9]+", "-", pipeline_name.lower()).strip("-")`
  - [x] Write initial `RunState` JSON with `status="running"`, empty `completed_steps`,
        `started_at=updated_at=now(UTC)`, `current_step=None`, `checkpoint=None`
  - [x] Call `self.prune(pipeline_name)` after writing the new file
  - [x] Return the `run_id`
  - [x] Success: state file exists at `runs_dir/{run_id}.json` with correct initial fields

- [x] **T6 — Tests: `init_run`**
  - [x] Test that `init_run` creates a JSON file in `runs_dir`
  - [x] Test that the file deserializes to a valid `RunState` with `status="running"`
  - [x] Test that a caller-supplied `run_id` is used verbatim
  - [x] Test that a generated `run_id` starts with `"run-"` and contains the pipeline slug
  - [x] All tests pass

- [x] **T7 — `StateManager.make_step_callback` and `_append_step`**
  - [x] Implement private `_append_step(self, run_id: str, step_result: StepResult) -> None`:
    - Load current `RunState` from disk
    - Extract `verdict` = last non-None `action_result.verdict` in `step_result.action_results`
    - Extract `outputs` = `step_result.action_results[-1].outputs` if action_results non-empty, else `{}`
    - Serialize `action_results` via `[dataclasses.asdict(ar) for ar in step_result.action_results]`
    - Append a new `StepState` to `completed_steps`
    - Update `updated_at` and `current_step` to `step_result.step_name`
    - If `step_result.status == ExecutionStatus.PAUSED`, set `status="paused"` and populate
      `checkpoint` with `reason` from `step_result.error or "checkpoint"`,
      `step=step_result.step_name`, `verdict=verdict`, `paused_at=now(UTC)`
    - Write back atomically
  - [x] Implement `make_step_callback(self, run_id: str) -> Callable[[StepResult], None]`
        returning a closure that calls `self._append_step(run_id, step_result)`
  - [x] Success: after calling the callback with a `StepResult`, `load(run_id).completed_steps`
        has one more entry with correct fields

- [x] **T8 — Tests: `make_step_callback` and `_append_step`**
  - [x] Build a `StepResult` with two `ActionResult`s (second has `verdict="PASS"`) and call
        the callback; verify `completed_steps[0].verdict == "PASS"`
  - [x] Test that `outputs` matches `action_results[-1].outputs`
  - [x] Test that calling callback twice results in two entries in `completed_steps`
  - [x] Test that a `StepResult` with `status=PAUSED` sets `run_state.status == "paused"`
        and populates `checkpoint`
  - [x] Test that `action_results` stored as list of dicts (serializable)
  - [x] All tests pass

- [x] **T9 — `StateManager.finalize`**
  - [x] Implement `finalize(self, run_id: str, result: PipelineResult) -> None`
  - [x] Load current `RunState`, set `status = result.status` (string value),
        `updated_at = now(UTC)`, `current_step = None` for terminal statuses
  - [x] Write back atomically
  - [x] Success: after finalize, `load(run_id).status` equals `result.status`

- [x] **T10 — Tests: `finalize`**
  - [x] Test that `finalize` with `COMPLETED` result sets `status="completed"` and `current_step=None`
  - [x] Test that `finalize` with `FAILED` result sets `status="failed"`
  - [x] All tests pass

**Commit:** `feat: add state models, init_run, step callback, finalize`

- [x] **T11 — `StateManager.load` and `SchemaVersionError`**
  - [x] Implement `load(self, run_id: str) -> RunState`:
    - Read file at `_state_path(run_id)` — raises `FileNotFoundError` if absent
    - Parse JSON with `json.loads`
    - Check `data.get("schema_version")` — raise `SchemaVersionError(version)` if not `== 1`
    - Return `RunState.model_validate(data)`
  - [x] Success: `load` returns a valid `RunState` for a file written by `init_run`

- [x] **T12 — Tests: `load` and `SchemaVersionError`**
  - [x] Test `load` after `init_run` returns `RunState` with correct `pipeline` and `params`
  - [x] Test `load` with a nonexistent run_id raises `FileNotFoundError`
  - [x] Test `load` on a file with `schema_version: 99` raises `SchemaVersionError`
  - [x] Test `load` on a file with `schema_version: 0` raises `SchemaVersionError`
  - [x] All tests pass

- [x] **T13 — `StateManager.load_prior_outputs`**
  - [x] Implement `load_prior_outputs(self, run_id: str) -> dict[str, ActionResult]`:
    - Call `self.load(run_id)`
    - For each `StepState` in `completed_steps`, for each `(idx, ar_dict)` in
      `enumerate(step_state.action_results)`:
      - Reconstruct `ActionResult(**ar_dict)` (use `ActionResult(**{k: v for k, v in ar_dict.items() if k in ActionResult.__dataclass_fields__})` to be defensive)
      - Store at key `f"{ar_dict.get('action_type', 'unknown')}-{idx}"`
    - Return accumulated dict; return `{}` if any step has empty `action_results`
  - [x] Success: returns a populated dict for runs with stored `action_results`; returns `{}` for runs without

- [x] **T14 — Tests: `load_prior_outputs`**
  - [x] Build a run state with one completed step storing two `action_results` dicts;
        call `load_prior_outputs` and verify both keys are present with correct types
  - [x] Test that `load_prior_outputs` returns `{}` for a run with no stored `action_results`
  - [x] Test that unknown fields in stored dict don't cause `ActionResult` reconstruction to crash
  - [x] All tests pass

- [x] **T15 — `StateManager.first_unfinished_step`**
  - [x] Implement `first_unfinished_step(self, run_id: str, definition: PipelineDefinition) -> str | None`:
    - Load run state
    - Build set of completed step names from `completed_steps`
    - Iterate `definition.steps` in order; return first `step.name` not in completed set
    - Return `None` if all steps in definition are in completed set
  - [x] Success: returns correct step name when partial progress exists; `None` when fully complete

- [x] **T16 — Tests: `first_unfinished_step`**
  - [x] Test with no completed steps → returns first step name
  - [x] Test with first two steps completed → returns third step name
  - [x] Test with all steps completed → returns `None`
  - [x] All tests pass

- [x] **T17 — `StateManager.list_runs`**
  - [x] Implement `list_runs(self, pipeline: str | None = None, status: str | None = None) -> list[RunState]`:
    - Glob `runs_dir/*.json`, load each via `self.load`; skip files that fail to parse (log warning)
    - Filter by `pipeline` if provided (exact match on `RunState.pipeline`)
    - Filter by `status` if provided (exact match on `RunState.status`)
    - Sort by `started_at` descending (most recent first)
    - Return filtered list
  - [x] Success: returns all matching runs in correct order

- [x] **T18 — Tests: `list_runs`**
  - [x] Create three runs (two for pipeline A, one for pipeline B); verify `list_runs()` returns all three
  - [x] Verify `list_runs(pipeline="A")` returns only two
  - [x] Verify `list_runs(status="running")` returns only running runs
  - [x] Verify sort order is most-recent-first (use `run_id` or `started_at` to confirm)
  - [x] Verify a corrupt JSON file in `runs_dir` is skipped, not a crash
  - [x] All tests pass

- [x] **T19 — `StateManager.find_matching_run`**
  - [x] Implement `find_matching_run(self, pipeline_name: str, params: dict[str, object], status: str | None = "paused") -> RunState | None`:
    - Call `list_runs(pipeline=pipeline_name, status=status)`
    - Filter to runs where `run_state.params == params` (exact equality)
    - Return the first (most recent) match, or `None`
  - [x] Success: returns correct run when match exists; `None` when no match

- [x] **T20 — Tests: `find_matching_run`**
  - [x] Create a paused run with params `{"slice": "191"}`; verify `find_matching_run` returns it
  - [x] Verify `find_matching_run` returns `None` when params differ (`{"slice": "192"}`)
  - [x] Verify `find_matching_run` returns `None` when status doesn't match
  - [x] Verify returns most recent when multiple matches exist
  - [x] All tests pass

- [x] **T21 — `StateManager.prune`**
  - [x] Implement `prune(self, pipeline_name: str, keep: int = 10) -> int`:
    - List all runs for `pipeline_name` with `status` in `{"completed", "failed"}` (never prune paused)
    - Sort by `started_at` ascending (oldest first)
    - Delete files for all entries beyond `keep` limit (i.e., delete `runs[:-keep]` if `len(runs) > keep`)
    - Return count of deleted files
  - [x] Success: count of runs after prune ≤ `keep` (paused runs excluded from count and from deletion)

- [x] **T22 — Tests: `prune`**
  - [x] Create 12 completed runs for pipeline A; call `prune("A", keep=10)`; verify 2 deleted, 10 remain
  - [x] Verify the 2 oldest are deleted (check by `started_at`)
  - [x] Verify a paused run among the 12 is never deleted even if `len > keep`
  - [x] Verify `prune` returns correct count
  - [x] Verify `prune` is a no-op when count ≤ keep (returns 0)
  - [x] All tests pass

**Commit:** `feat: add state load, prior_outputs, list/find/prune operations`

- [x] **T23 — Integration test: full run → state file reflects all steps**
  - [x] In `tests/pipeline/test_state_integration.py`, write a test that:
    1. Uses `_no_project_pipeline("slice-lifecycle")` (from existing integration test helpers)
    2. Creates `StateManager(runs_dir=tmp_path)`
    3. Calls `init_run`, then `execute_pipeline` with `on_step_complete=mgr.make_step_callback(run_id)` and mock action registry returning success
    4. Calls `finalize`
    5. Loads state and asserts `status="completed"`, `len(completed_steps)==5`
  - [x] Success: test passes; `state.completed_steps` has an entry for every step in the pipeline

- [x] **T24 — Integration test: resume from paused state**
  - [x] Simulate a paused run by calling `make_step_callback` for steps 1–2, then
        calling it with a `StepResult` of `status=PAUSED` for step 3
  - [x] Load state, assert `status="paused"`, `current_step="implement"` (or third step name)
  - [x] Call `first_unfinished_step` and `load_prior_outputs`
  - [x] Call `execute_pipeline` with `start_from` and reconstructed `prior_outputs`
  - [x] Finalize and assert final `status="completed"`, all 5 steps in `completed_steps`
  - [x] Success: resumed run accumulates all completed steps across both execution segments

**Commit:** `test: add state integration tests for full run and resume`

- [x] **T25 — Exports and module wiring**
  - [x] Add `__all__` to `state.py` listing: `StateManager`, `RunState`, `StepState`,
        `CheckpointState`, `SchemaVersionError`
  - [x] Verify `from squadron.pipeline.state import StateManager` works from project root
  - [x] Run full test suite (`pytest tests/pipeline/`); all tests pass
  - [x] Run `ruff check src/squadron/pipeline/state.py tests/pipeline/test_state.py tests/pipeline/test_state_integration.py`; zero issues
  - [x] Run `ruff format` on modified files
  - [x] Run pyright on `src/squadron/pipeline/state.py`; zero errors
  - [x] Success: clean ruff and pyright; all pipeline tests pass

**Commit:** `feat: wire state module exports, final lint and type check pass`

- [x] **T26 — Closeout**
  - [x] Mark slice `status: complete` and add `dateCompleted: 20260403` in
        `150-slice.pipeline-state-and-resume.md`
  - [x] Mark slice 150 checklist item `[x]` in `140-slices.pipeline-foundation.md`
  - [x] Update `CHANGELOG.md` under `[Unreleased]` with `StateManager`, `RunState`,
        `StepState`, atomic write, resume support
  - [x] Update `DEVLOG.md` with Phase 6 completion summary
  - [x] Success: all documentation current; branch `150-pipeline-state-and-resume` ready for review

**Commit:** `docs: mark slice 150 pipeline state and resume complete`
