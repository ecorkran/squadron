---
docType: tasks
slice: pipeline-state-and-resume
project: squadron
lld: project-documents/user/slices/150-slice.pipeline-state-and-resume.md
dependencies: [149]
projectState: Slice 149 (executor) complete on branch 149-pipeline-executor-and-loops. Branch 150-pipeline-state-and-resume created from it.
dateCreated: 20260403
dateUpdated: 20260403
status: not_started
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

- [ ] **T1 — Test infrastructure: conftest fixture**
  - [ ] In `tests/pipeline/conftest.py`, add a `state_manager` fixture that returns
        `StateManager(runs_dir=tmp_path)` using pytest's built-in `tmp_path`
  - [ ] Add a `completed_pipeline_result` fixture returning a `PipelineResult` with
        `status=ExecutionStatus.COMPLETED` and one dummy `StepResult`
  - [ ] Verify fixture is importable with no errors (`pytest --collect-only`)
  - [ ] Success: fixtures available in `tests/pipeline/` scope with no import errors

- [ ] **T2 — Pydantic models: `StepState`, `CheckpointState`, `RunState`**
  - [ ] Create `src/squadron/pipeline/state.py`
  - [ ] Define `StepState(BaseModel)` with fields: `step_name: str`, `step_type: str`,
        `status: str`, `verdict: str | None = None`,
        `outputs: dict[str, object] = {}`,
        `action_results: list[dict[str, object]] = []`,
        `completed_at: datetime`
  - [ ] Define `CheckpointState(BaseModel)` with fields: `reason: str`, `step: str`,
        `verdict: str | None = None`, `paused_at: datetime`
  - [ ] Define `RunState(BaseModel)` with fields: `schema_version: int = 1`,
        `run_id: str`, `pipeline: str`, `params: dict[str, object]`,
        `started_at: datetime`, `updated_at: datetime`, `status: str`,
        `current_step: str | None = None`,
        `completed_steps: list[StepState] = []`,
        `checkpoint: CheckpointState | None = None`
  - [ ] Define `SchemaVersionError(Exception)` with message carrying the offending version
  - [ ] Export all four from module `__all__`
  - [ ] Success: `from squadron.pipeline.state import RunState, StepState, CheckpointState, SchemaVersionError` works; pyright strict 0 errors on the file

- [ ] **T3 — Tests: Pydantic models**
  - [ ] Create `tests/pipeline/test_state.py`
  - [ ] Test `RunState` round-trips through `model_dump(mode="json")` → `RunState.model_validate()`
  - [ ] Test `StepState` with all optional fields omitted deserializes with correct defaults
  - [ ] Test `CheckpointState` round-trip
  - [ ] Test `SchemaVersionError` can be raised and caught as `Exception`
  - [ ] All tests pass; pyright 0 errors on test file

- [ ] **T4 — `StateManager.__init__` and atomic write helper**
  - [ ] Add `StateManager` class with `__init__(self, runs_dir: Path | None = None)`
  - [ ] Default `runs_dir` = `Path.home() / ".config" / "squadron" / "runs"`; create it if absent
  - [ ] Add private `_write_atomic(path: Path, data: str) -> None` — writes to a `.tmp`
        sibling then renames to `path` (atomic on POSIX; acceptable on Windows)
  - [ ] Add private `_state_path(run_id: str) -> Path` — returns `runs_dir / f"{run_id}.json"`
  - [ ] Success: `StateManager(runs_dir=tmp_path)` creates the directory if missing; `tmp_path` is used (no real `~/.config` accessed)

- [ ] **T4a — Tests: atomic write helper**
  - [ ] Test that `_write_atomic` creates the target file with the expected content
  - [ ] Test that a `.tmp` sibling left from a prior interrupted write is overwritten cleanly
        (write a stale `.tmp` file manually, then call `_write_atomic` and verify target is correct)
  - [ ] Test that the original target file is not modified if a second write's content is
        the same (i.e., the rename is idempotent and the original survives a new write)
  - [ ] All tests pass; no `.tmp` files left on disk after any passing test

- [ ] **T5 — `StateManager.init_run`**
  - [ ] Implement `init_run(self, pipeline_name: str, params: dict[str, object], run_id: str | None = None) -> str`
  - [ ] If `run_id` is `None`, generate: `f"run-{date}-{slug}-{uuid4().hex[:8]}"` where
        `date = datetime.now(UTC).strftime("%Y%m%d")` and
        `slug = re.sub(r"[^a-z0-9]+", "-", pipeline_name.lower()).strip("-")`
  - [ ] Write initial `RunState` JSON with `status="running"`, empty `completed_steps`,
        `started_at=updated_at=now(UTC)`, `current_step=None`, `checkpoint=None`
  - [ ] Call `self.prune(pipeline_name)` after writing the new file
  - [ ] Return the `run_id`
  - [ ] Success: state file exists at `runs_dir/{run_id}.json` with correct initial fields

- [ ] **T6 — Tests: `init_run`**
  - [ ] Test that `init_run` creates a JSON file in `runs_dir`
  - [ ] Test that the file deserializes to a valid `RunState` with `status="running"`
  - [ ] Test that a caller-supplied `run_id` is used verbatim
  - [ ] Test that a generated `run_id` starts with `"run-"` and contains the pipeline slug
  - [ ] All tests pass

- [ ] **T7 — `StateManager.make_step_callback` and `_append_step`**
  - [ ] Implement private `_append_step(self, run_id: str, step_result: StepResult) -> None`:
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
  - [ ] Implement `make_step_callback(self, run_id: str) -> Callable[[StepResult], None]`
        returning a closure that calls `self._append_step(run_id, step_result)`
  - [ ] Success: after calling the callback with a `StepResult`, `load(run_id).completed_steps`
        has one more entry with correct fields

- [ ] **T8 — Tests: `make_step_callback` and `_append_step`**
  - [ ] Build a `StepResult` with two `ActionResult`s (second has `verdict="PASS"`) and call
        the callback; verify `completed_steps[0].verdict == "PASS"`
  - [ ] Test that `outputs` matches `action_results[-1].outputs`
  - [ ] Test that calling callback twice results in two entries in `completed_steps`
  - [ ] Test that a `StepResult` with `status=PAUSED` sets `run_state.status == "paused"`
        and populates `checkpoint`
  - [ ] Test that `action_results` stored as list of dicts (serializable)
  - [ ] All tests pass

- [ ] **T9 — `StateManager.finalize`**
  - [ ] Implement `finalize(self, run_id: str, result: PipelineResult) -> None`
  - [ ] Load current `RunState`, set `status = result.status` (string value),
        `updated_at = now(UTC)`, `current_step = None` for terminal statuses
  - [ ] Write back atomically
  - [ ] Success: after finalize, `load(run_id).status` equals `result.status`

- [ ] **T10 — Tests: `finalize`**
  - [ ] Test that `finalize` with `COMPLETED` result sets `status="completed"` and `current_step=None`
  - [ ] Test that `finalize` with `FAILED` result sets `status="failed"`
  - [ ] All tests pass

**Commit:** `feat: add state models, init_run, step callback, finalize`

- [ ] **T11 — `StateManager.load` and `SchemaVersionError`**
  - [ ] Implement `load(self, run_id: str) -> RunState`:
    - Read file at `_state_path(run_id)` — raises `FileNotFoundError` if absent
    - Parse JSON with `json.loads`
    - Check `data.get("schema_version")` — raise `SchemaVersionError(version)` if not `== 1`
    - Return `RunState.model_validate(data)`
  - [ ] Success: `load` returns a valid `RunState` for a file written by `init_run`

- [ ] **T12 — Tests: `load` and `SchemaVersionError`**
  - [ ] Test `load` after `init_run` returns `RunState` with correct `pipeline` and `params`
  - [ ] Test `load` with a nonexistent run_id raises `FileNotFoundError`
  - [ ] Test `load` on a file with `schema_version: 99` raises `SchemaVersionError`
  - [ ] Test `load` on a file with `schema_version: 0` raises `SchemaVersionError`
  - [ ] All tests pass

- [ ] **T13 — `StateManager.load_prior_outputs`**
  - [ ] Implement `load_prior_outputs(self, run_id: str) -> dict[str, ActionResult]`:
    - Call `self.load(run_id)`
    - For each `StepState` in `completed_steps`, for each `(idx, ar_dict)` in
      `enumerate(step_state.action_results)`:
      - Reconstruct `ActionResult(**ar_dict)` (use `ActionResult(**{k: v for k, v in ar_dict.items() if k in ActionResult.__dataclass_fields__})` to be defensive)
      - Store at key `f"{ar_dict.get('action_type', 'unknown')}-{idx}"`
    - Return accumulated dict; return `{}` if any step has empty `action_results`
  - [ ] Success: returns a populated dict for runs with stored `action_results`; returns `{}` for runs without

- [ ] **T14 — Tests: `load_prior_outputs`**
  - [ ] Build a run state with one completed step storing two `action_results` dicts;
        call `load_prior_outputs` and verify both keys are present with correct types
  - [ ] Test that `load_prior_outputs` returns `{}` for a run with no stored `action_results`
  - [ ] Test that unknown fields in stored dict don't cause `ActionResult` reconstruction to crash
  - [ ] All tests pass

- [ ] **T15 — `StateManager.first_unfinished_step`**
  - [ ] Implement `first_unfinished_step(self, run_id: str, definition: PipelineDefinition) -> str | None`:
    - Load run state
    - Build set of completed step names from `completed_steps`
    - Iterate `definition.steps` in order; return first `step.name` not in completed set
    - Return `None` if all steps in definition are in completed set
  - [ ] Success: returns correct step name when partial progress exists; `None` when fully complete

- [ ] **T16 — Tests: `first_unfinished_step`**
  - [ ] Test with no completed steps → returns first step name
  - [ ] Test with first two steps completed → returns third step name
  - [ ] Test with all steps completed → returns `None`
  - [ ] All tests pass

- [ ] **T17 — `StateManager.list_runs`**
  - [ ] Implement `list_runs(self, pipeline: str | None = None, status: str | None = None) -> list[RunState]`:
    - Glob `runs_dir/*.json`, load each via `self.load`; skip files that fail to parse (log warning)
    - Filter by `pipeline` if provided (exact match on `RunState.pipeline`)
    - Filter by `status` if provided (exact match on `RunState.status`)
    - Sort by `started_at` descending (most recent first)
    - Return filtered list
  - [ ] Success: returns all matching runs in correct order

- [ ] **T18 — Tests: `list_runs`**
  - [ ] Create three runs (two for pipeline A, one for pipeline B); verify `list_runs()` returns all three
  - [ ] Verify `list_runs(pipeline="A")` returns only two
  - [ ] Verify `list_runs(status="running")` returns only running runs
  - [ ] Verify sort order is most-recent-first (use `run_id` or `started_at` to confirm)
  - [ ] Verify a corrupt JSON file in `runs_dir` is skipped, not a crash
  - [ ] All tests pass

- [ ] **T19 — `StateManager.find_matching_run`**
  - [ ] Implement `find_matching_run(self, pipeline_name: str, params: dict[str, object], status: str | None = "paused") -> RunState | None`:
    - Call `list_runs(pipeline=pipeline_name, status=status)`
    - Filter to runs where `run_state.params == params` (exact equality)
    - Return the first (most recent) match, or `None`
  - [ ] Success: returns correct run when match exists; `None` when no match

- [ ] **T20 — Tests: `find_matching_run`**
  - [ ] Create a paused run with params `{"slice": "191"}`; verify `find_matching_run` returns it
  - [ ] Verify `find_matching_run` returns `None` when params differ (`{"slice": "192"}`)
  - [ ] Verify `find_matching_run` returns `None` when status doesn't match
  - [ ] Verify returns most recent when multiple matches exist
  - [ ] All tests pass

- [ ] **T21 — `StateManager.prune`**
  - [ ] Implement `prune(self, pipeline_name: str, keep: int = 10) -> int`:
    - List all runs for `pipeline_name` with `status` in `{"completed", "failed"}` (never prune paused)
    - Sort by `started_at` ascending (oldest first)
    - Delete files for all entries beyond `keep` limit (i.e., delete `runs[:-keep]` if `len(runs) > keep`)
    - Return count of deleted files
  - [ ] Success: count of runs after prune ≤ `keep` (paused runs excluded from count and from deletion)

- [ ] **T22 — Tests: `prune`**
  - [ ] Create 12 completed runs for pipeline A; call `prune("A", keep=10)`; verify 2 deleted, 10 remain
  - [ ] Verify the 2 oldest are deleted (check by `started_at`)
  - [ ] Verify a paused run among the 12 is never deleted even if `len > keep`
  - [ ] Verify `prune` returns correct count
  - [ ] Verify `prune` is a no-op when count ≤ keep (returns 0)
  - [ ] All tests pass

**Commit:** `feat: add state load, prior_outputs, list/find/prune operations`

- [ ] **T23 — Integration test: full run → state file reflects all steps**
  - [ ] In `tests/pipeline/test_state_integration.py`, write a test that:
    1. Uses `_no_project_pipeline("slice-lifecycle")` (from existing integration test helpers)
    2. Creates `StateManager(runs_dir=tmp_path)`
    3. Calls `init_run`, then `execute_pipeline` with `on_step_complete=mgr.make_step_callback(run_id)` and mock action registry returning success
    4. Calls `finalize`
    5. Loads state and asserts `status="completed"`, `len(completed_steps)==5`
  - [ ] Success: test passes; `state.completed_steps` has an entry for every step in the pipeline

- [ ] **T24 — Integration test: resume from paused state**
  - [ ] Simulate a paused run by calling `make_step_callback` for steps 1–2, then
        calling it with a `StepResult` of `status=PAUSED` for step 3
  - [ ] Load state, assert `status="paused"`, `current_step="implement"` (or third step name)
  - [ ] Call `first_unfinished_step` and `load_prior_outputs`
  - [ ] Call `execute_pipeline` with `start_from` and reconstructed `prior_outputs`
  - [ ] Finalize and assert final `status="completed"`, all 5 steps in `completed_steps`
  - [ ] Success: resumed run accumulates all completed steps across both execution segments

**Commit:** `test: add state integration tests for full run and resume`

- [ ] **T25 — Exports and module wiring**
  - [ ] Add `__all__` to `state.py` listing: `StateManager`, `RunState`, `StepState`,
        `CheckpointState`, `SchemaVersionError`
  - [ ] Verify `from squadron.pipeline.state import StateManager` works from project root
  - [ ] Run full test suite (`pytest tests/pipeline/`); all tests pass
  - [ ] Run `ruff check src/squadron/pipeline/state.py tests/pipeline/test_state.py tests/pipeline/test_state_integration.py`; zero issues
  - [ ] Run `ruff format` on modified files
  - [ ] Run pyright on `src/squadron/pipeline/state.py`; zero errors
  - [ ] Success: clean ruff and pyright; all pipeline tests pass

**Commit:** `feat: wire state module exports, final lint and type check pass`

- [ ] **T26 — Closeout**
  - [ ] Mark slice `status: complete` and add `dateCompleted: 20260403` in
        `150-slice.pipeline-state-and-resume.md`
  - [ ] Mark slice 150 checklist item `[x]` in `140-slices.pipeline-foundation.md`
  - [ ] Update `CHANGELOG.md` under `[Unreleased]` with `StateManager`, `RunState`,
        `StepState`, atomic write, resume support
  - [ ] Update `DEVLOG.md` with Phase 6 completion summary
  - [ ] Success: all documentation current; branch `150-pipeline-state-and-resume` ready for review

**Commit:** `docs: mark slice 150 pipeline state and resume complete`
