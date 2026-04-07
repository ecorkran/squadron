---
docType: tasks
slice: pipeline-executor-hardening
project: squadron
parent: 156-slice.pipeline-executor-hardening.md
dependencies: [155-sdk-pipeline-executor]
dateCreated: 20260404
dateUpdated: 20260405
status: complete
---

# Tasks: Pipeline Executor Hardening

## Context

Two bugs found after slice 155 (SDK executor):

1. **Wrong runner on resume** — both `--resume` and implicit resume paths call `_run_pipeline` / `execute_pipeline` directly, bypassing `_run_pipeline_sdk`. On SDK runs this causes compact action to fall through to a `cf compact` CLI call that does not exist.

2. **Case-sensitive pipeline names** — `load_pipeline` uses exact-case filename match; `find_matching_run` compares names as raw strings. Breaks across macOS/Linux.

**Files changed:**
- `src/squadron/pipeline/state.py` — `ExecutionMode` enum, `RunState.execution_mode`, schema v2
- `src/squadron/pipeline/loader.py` — lowercase normalisation in load and discover
- `src/squadron/cli/commands/run.py` — `run_id` params, resume dispatch by enum, name normalisation

**Tests updated/created:**
- `tests/pipeline/test_state.py`
- `tests/pipeline/test_loader.py`
- `tests/cli/test_run_pipeline.py` (new file)

---

## Tasks

### T1 — Add `ExecutionMode` enum to `state.py`

- [x] In `src/squadron/pipeline/state.py`, add after the imports and before `_SCHEMA_VERSION`:
  ```python
  class ExecutionMode(StrEnum):
      SDK = "sdk"
      PROMPT_ONLY = "prompt-only"
  ```
- [x] Add `ExecutionMode` to the `__all__` list in `state.py`
- [x] Import `StrEnum` from `enum` (it is already imported for other uses — verify; add if missing)

**Test T1** — `tests/pipeline/test_state.py`

- [x] Add `ExecutionMode` to the import from `squadron.pipeline.state`
- [x] Test `ExecutionMode.SDK.value == "sdk"` and `ExecutionMode.PROMPT_ONLY.value == "prompt-only"`
- [x] Test that `ExecutionMode("sdk") == ExecutionMode.SDK` (round-trip from string)

**Commit:** `feat: add ExecutionMode enum to pipeline state`

---

### T2 — Bump schema version and update `RunState`

- [x] Change `_SCHEMA_VERSION = 1` to `_SCHEMA_VERSION = 2` in `state.py`
- [x] Add `execution_mode: ExecutionMode = ExecutionMode.SDK` field to `RunState`, after `params` and before `started_at`
- [x] Confirm `_load_raw` already raises `SchemaVersionError` for version mismatches (it does — verify, no change needed)

**Test T2** — `tests/pipeline/test_state.py`

- [x] In `TestPydanticModels.test_run_state_round_trip`, add `execution_mode=ExecutionMode.SDK` to the `RunState` constructor
- [x] Add test: `RunState` serialises `execution_mode` as `"sdk"` in `model_dump(mode="json")`
- [x] Add test: `RunState` with `execution_mode=ExecutionMode.PROMPT_ONLY` serialises as `"prompt-only"`
- [x] Add test: loading a JSON dict without `execution_mode` field defaults to `ExecutionMode.SDK` (forward-compat for any lingering v1 files)
- [x] Add test: loading a state file with `schema_version: 1` raises `SchemaVersionError` with a message containing `"Unsupported state file schema_version"` (verify existing test covers this or add it)

**Commit:** `feat: bump RunState schema to v2 with execution_mode field`

---

### T3 — Add `execution_mode` parameter to `StateManager.init_run`

- [x] Update `init_run` signature in `state.py`:
  ```python
  def init_run(
      self,
      pipeline_name: str,
      params: dict[str, object],
      run_id: str | None = None,
      execution_mode: ExecutionMode = ExecutionMode.SDK,
  ) -> str:
  ```
- [x] Pass `execution_mode=execution_mode` when constructing `RunState` inside `init_run`
- [x] Add `pipeline_name = pipeline_name.lower()` as the first statement in `init_run` (before slug generation and `RunState` construction)

**Test T3** — `tests/pipeline/test_state.py`

- [x] Add test: `init_run` called with `ExecutionMode.PROMPT_ONLY` stores `"prompt-only"` in the loaded state
- [x] Add test: `init_run` normalises pipeline name to lowercase — `init_run("Test-Pipeline", {})` stores `pipeline="test-pipeline"`
- [x] Update any existing `init_run` tests that construct `RunState` directly to include `execution_mode` if needed to keep them passing

**Commit:** `feat: add execution_mode param to StateManager.init_run`

---

### T4 — Add `run_id` parameter to `_run_pipeline` in `run.py`

- [x] Update `_run_pipeline` signature to accept `run_id: str | None = None`
- [x] Inside `_run_pipeline`, replace the unconditional `run_id = state_mgr.init_run(pipeline_name, params)` with:
  ```python
  if run_id is None:
      run_id = state_mgr.init_run(pipeline_name, params, execution_mode=execution_mode)
  ```
- [x] Add `execution_mode: ExecutionMode = ExecutionMode.SDK` parameter to `_run_pipeline` so the caller can specify the mode when creating a new run
- [x] Import `ExecutionMode` from `squadron.pipeline.state` in `run.py`

**Test T4** — `tests/cli/test_run_pipeline.py` (new file)

- [x] Create `tests/cli/test_run_pipeline.py` with appropriate module docstring
- [x] Test: when `run_id` is `None`, `_run_pipeline` calls `init_run` and creates a new state file
- [x] Test: when `run_id` is provided, `_run_pipeline` skips `init_run` and uses the given ID (verify the state file for the provided `run_id` is updated, not a new one created)

**Commit:** `feat: add run_id and execution_mode params to _run_pipeline`

---

### T5 — Add `run_id` parameter to `_run_pipeline_sdk` in `run.py`

- [x] Update `_run_pipeline_sdk` signature to accept `run_id: str | None = None`
- [x] Forward `run_id` to the `_run_pipeline(...)` call inside `_run_pipeline_sdk`
- [x] Pass `execution_mode=ExecutionMode.SDK` explicitly when calling `_run_pipeline` from within `_run_pipeline_sdk`

**Test T5** — `tests/cli/test_run_pipeline.py`

- [x] Test: `_run_pipeline_sdk` called with an explicit `run_id` reuses that run ID (no new state file created)
- [x] Test: `_run_pipeline_sdk` called without `run_id` generates a new run ID

**Commit:** `feat: add run_id param to _run_pipeline_sdk`

---

### T6 — Fix explicit `--resume` path to dispatch by `ExecutionMode`

- [x] In the `--resume` branch of `run()` (around line 696 in `run.py`), replace the `asyncio.run(execute_pipeline(...))` call with a `match state.execution_mode:` block:
  - `case ExecutionMode.SDK:` → call `asyncio.run(_run_pipeline_sdk(..., run_id=resume, from_step=resume_from))`
  - `case ExecutionMode.PROMPT_ONLY:` → call `asyncio.run(_run_pipeline(..., run_id=resume, from_step=resume_from))`
- [x] Remove the now-unused direct `execute_pipeline` import from this branch (keep the import if used elsewhere; remove only the call)
- [x] Pass `resolver` and `cf_client` construction inside each branch as needed (they are already constructed before the match — keep them)

**Test T6** — `tests/cli/test_run_pipeline.py`

- [x] Test: resuming a state with `execution_mode=ExecutionMode.SDK` calls `_run_pipeline_sdk`
- [x] Test: resuming a state with `execution_mode=ExecutionMode.PROMPT_ONLY` calls `_run_pipeline` (not SDK)

**Commit:** `fix: dispatch --resume to correct runner via ExecutionMode enum`

---

### T7 — Fix implicit resume path to dispatch by `ExecutionMode`

- [x] In the implicit resume block (around line 763 in `run.py`), replace the `asyncio.run(_run_pipeline(...))` call with the same `match state.execution_mode:` dispatch pattern
  - `case ExecutionMode.SDK:` → `asyncio.run(_run_pipeline_sdk(..., run_id=match.run_id, from_step=implicit_from))`
  - `case ExecutionMode.PROMPT_ONLY:` → `asyncio.run(_run_pipeline(..., run_id=match.run_id, from_step=implicit_from))`

**Test T7** — `tests/cli/test_run_pipeline.py`

- [x] Test: implicit resume with SDK state calls `_run_pipeline_sdk`
- [x] Test: implicit resume with prompt-only state calls `_run_pipeline`

**Commit:** `fix: dispatch implicit resume to correct runner via ExecutionMode enum`

---

### T8 — Pass correct `ExecutionMode` from `_handle_prompt_only_init`

- [x] In `_handle_prompt_only_init`, update the `state_mgr.init_run(pipeline_name, params)` call to pass `execution_mode=ExecutionMode.PROMPT_ONLY`
- [x] Verify `run()` fresh-run path already calls `_run_pipeline_sdk` which passes `ExecutionMode.SDK` (no change needed there — confirm)

**Test T8** — `tests/cli/test_run_pipeline.py`

- [x] Test: `_handle_prompt_only_init` creates a state file with `execution_mode = "prompt-only"`

**Commit:** `fix: record execution_mode=PROMPT_ONLY in prompt-only init`

---

### T9 — Normalise pipeline name in `load_pipeline`

- [x] In `loader.py`, `load_pipeline` function: after the `candidate = Path(name_or_path)` check, add:
  ```python
  if not candidate.is_file():
      name_or_path = name_or_path.lower()
  ```
  This ensures direct file paths are not modified, but name-based lookups are lowercased.

**Test T9** — `tests/pipeline/test_loader.py`

- [x] Add test: `load_pipeline("Test-Pipeline")` finds `test-pipeline.yaml` (write a temp yaml, try mixed-case lookup)
- [x] Add test: `load_pipeline("TEST-PIPELINE")` also finds `test-pipeline.yaml`
- [x] Add test: `load_pipeline("/path/to/My-Pipeline.yaml")` still loads the file at the exact path (file path not normalised)

**Commit:** `fix: normalise pipeline name to lowercase in load_pipeline`

---

### T10 — Normalise pipeline name in `discover_pipelines`

- [x] In `loader.py`, `discover_pipelines` function: change `pipeline_name = schema.name` to `pipeline_name = schema.name.lower()` when building the `found` dict

**Test T10** — `tests/pipeline/test_loader.py`

- [x] Add test: if two YAML files have names `"MyPipeline"` and `"mypipeline"`, `discover_pipelines` returns only one entry keyed `"mypipeline"` (project overrides built-in, as before)
- [x] Add test: `discover_pipelines()` returns `PipelineInfo` with lowercase `name`

**Commit:** `fix: normalise pipeline names to lowercase in discover_pipelines`

---

### T11 — Normalise pipeline name at CLI input boundary

- [x] In `run()` in `run.py`, find the `pipeline` not-None guard near line 753 and add `pipeline = pipeline.lower()` immediately after it
- [x] Verify `--validate`, `--dry-run`, and `--list` branches also use the normalised value (they all reference `pipeline` after the guard — confirm this is the case)

**Test T11** — `tests/cli/test_run_pipeline.py`

- [x] Test: calling `run()` with `pipeline="Test-Pipeline"` passes `"test-pipeline"` to `load_pipeline`

**Commit:** `fix: normalise pipeline name to lowercase at CLI input boundary`

---

### T12 — Show `execution_mode` in `sq run --status` output

- [x] In `_display_run_status` in `run.py`, add a line to the `lines` list:
  ```python
  f"[bold]Mode:[/bold]     {state.execution_mode.value}",
  ```
  Place it after the `Status:` line.

**Test T12** — `tests/cli/test_run_pipeline.py`

- [x] Test: `_display_run_status` called with a `RunState` that has `execution_mode=ExecutionMode.SDK` includes `"sdk"` in the output

**Commit:** `feat: show execution_mode in sq run --status output`

---

### T13 — Lint, type-check, and full test suite

- [x] Run `ruff format src/ tests/` and fix any formatting issues
- [x] Run `ruff check src/ tests/` and fix any lint errors
- [x] Run `pyright --strict src/squadron/pipeline/state.py src/squadron/pipeline/loader.py src/squadron/cli/commands/run.py` — zero errors
- [x] Run full test suite: `uv run pytest tests/` — all tests pass, no regressions
- [x] Run `uv run pytest tests/pipeline/test_state.py tests/pipeline/test_loader.py tests/cli/test_run_pipeline.py -v` to confirm new tests pass

**Commit:** `chore: lint and verify pipeline executor hardening`

---

### T14 — Closeout

- [x] Update `156-slice.pipeline-executor-hardening.md` frontmatter: `status: complete`, `dateUpdated: today`
- [x] Check off slice 156 in `140-slices.pipeline-foundation.md`
- [x] Update `DEVLOG.md` with implementation summary
- [x] Update `CHANGELOG.md` with slice 156 entry
