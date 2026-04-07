---
docType: slice-design
slice: pipeline-executor-hardening
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [155-sdk-pipeline-executor]
interfaces: [152-pipeline-documentation]
dateCreated: 20260404
dateUpdated: 20260405
status: complete
---

# Slice Design: Pipeline Executor Hardening

## Overview

Fix two classes of bugs discovered after SDK executor (slice 155) was completed:

1. **Resume dispatches with the wrong runner** — both explicit `--resume` and implicit resume paths call `_run_pipeline` / `execute_pipeline` directly, bypassing `_run_pipeline_sdk`. When the original run was in SDK mode, the compact action falls through to a CF code path that calls `cf compact --instructions ...` — a command that does not exist in CF, causing a hard failure.

2. **Pipeline names are case-sensitive** — `load_pipeline` searches for `{name}.yaml` with an exact case match; `find_matching_run` and `list_runs` compare pipeline names as raw strings. This causes silent miss-matches on macOS (HFS+ is case-insensitive) and hard failures on Linux/CI.

Both bugs require touching state schema (adding `execution_mode`), the loader, and the CLI resume paths. Grouped into a single hardening slice.

## Value

- `sq run --resume <id>` works correctly regardless of whether the original run was SDK or prompt-only.
- Implicit resume detection is reliable: finds paused runs even if the user typed the pipeline name in a different case.
- Pipeline name lookup is deterministic across macOS and Linux.

## Technical Scope

### In Scope

1. **`ExecutionMode` enum** — New `StrEnum` in `src/squadron/pipeline/state.py`. Values: `SDK = "sdk"`, `PROMPT_ONLY = "prompt-only"`. No string literals for mode identity elsewhere in the code.

2. **`RunState.execution_mode` field** — Add `execution_mode: ExecutionMode` to `RunState` (Pydantic). Default to `ExecutionMode.SDK` for forward-compat with any schema v1 files that lack the field (they were all SDK runs anyway — prompt-only runs do not call `_run_pipeline`). Bump `_SCHEMA_VERSION` to `2`. Old files raise `SchemaVersionError` on resume; the error message already guides users to abandon the stale run.

3. **State recording** — `init_run()` gains an `execution_mode: ExecutionMode` parameter. Both `_run_pipeline_sdk` and `_run_pipeline` (when called with a session) pass the appropriate value when creating the initial state.

4. **Resume dispatch by enum** — In `run.py`, both the `--resume` path and the implicit resume path:
   - Load `state.execution_mode`
   - Match against `ExecutionMode` enum values; dispatch to `_run_pipeline_sdk` (pass `run_id`) or `_run_pipeline` accordingly
   - No hardcoded string comparisons

5. **`_run_pipeline_sdk` accepts `run_id`** — To resume an SDK run under the existing run ID (not create a new state file), `_run_pipeline_sdk` must accept an optional `run_id: str | None` parameter and forward it to `_run_pipeline`, which forwards it to `StateManager.init_run`.

6. **Pipeline name normalisation** — Normalise to lowercase at two boundaries:
   - `load_pipeline`: normalise `name_or_path` before building the `.yaml` filename (only when it does not resolve to a direct file path)
   - `discover_pipelines`: normalise `schema.name.lower()` when building the `found` dict key
   - `StateManager.init_run`: normalise `pipeline_name.lower()` when storing in `RunState.pipeline`
   - CLI input: normalise `pipeline` argument before passing to any loader or state function

### Out of Scope

- Changing the compact action's non-SDK CF path (it's never called by a live pipeline; the correct fix is the resume mode dispatch above).
- Multiple paused runs for the same pipeline+params (the current single-match behaviour is correct by design).
- Collection loop resume (slice 154 scope).
- Convergence loops (160 scope).

## Architecture

### ExecutionMode Enum and RunState

```python
# src/squadron/pipeline/state.py

class ExecutionMode(StrEnum):
    SDK = "sdk"
    PROMPT_ONLY = "prompt-only"

class RunState(BaseModel):
    schema_version: int = _SCHEMA_VERSION  # bumped to 2
    run_id: str
    pipeline: str
    params: dict[str, object]
    execution_mode: ExecutionMode = ExecutionMode.SDK  # NEW
    started_at: datetime
    updated_at: datetime
    status: str
    current_step: str | None = None
    completed_steps: list[StepState] = []
    checkpoint: CheckpointState | None = None
```

The default `ExecutionMode.SDK` allows existing schema v1 files to be loaded via `model_validate` when the field is absent, without requiring a migration path (since no v1 files from prompt-only runs exist — prompt-only mode never calls `_run_pipeline` in a way that creates a state file with the old schema).

**Schema version bump:** `_SCHEMA_VERSION = 2`. `_load_raw` raises `SchemaVersionError` for version 1 files. The error message is already user-friendly ("Unsupported state file schema_version: 1").

### State Recording

```python
def init_run(
    self,
    pipeline_name: str,
    params: dict[str, object],
    run_id: str | None = None,
    execution_mode: ExecutionMode = ExecutionMode.SDK,
) -> str:
    ...
    state = RunState(
        ...
        execution_mode=execution_mode,
    )
```

Callers:
- `_run_pipeline_sdk` → passes `ExecutionMode.SDK` (explicit, not default)
- `_handle_prompt_only_init` → passes `ExecutionMode.PROMPT_ONLY`
- `_run_pipeline` when called without an sdk_session → passes `ExecutionMode.PROMPT_ONLY`; this case currently only arises from implicit resume of a prompt-only run, which will be handled by the dispatch logic below

### Resume Dispatch Logic

Both resume paths in `run.py` become:

```python
state = state_mgr.load(resume)
...
match state.execution_mode:
    case ExecutionMode.SDK:
        result = asyncio.run(
            _run_pipeline_sdk(
                state.pipeline,
                dict(state.params),
                model_override=resume_model,
                run_id=resume,          # reuse existing run ID
                from_step=resume_from,
            )
        )
    case ExecutionMode.PROMPT_ONLY:
        result = asyncio.run(
            _run_pipeline(
                state.pipeline,
                dict(state.params),
                model_override=resume_model,
                from_step=resume_from,
                run_id=resume,          # reuse existing run ID
            )
        )
```

No `if mode == "sdk"` or equivalent string matching.

### `_run_pipeline_sdk` Signature Change

```python
async def _run_pipeline_sdk(
    pipeline_name: str,
    params: dict[str, object],
    model_override: str | None = None,
    runs_dir: Path | None = None,
    from_step: str | None = None,
    run_id: str | None = None,       # NEW — None means fresh run
) -> PipelineResult:
```

When `run_id` is provided, `_run_pipeline` must not call `state_mgr.init_run`; instead it reuses the existing run ID. A new parameter `run_id: str | None = None` is added to `_run_pipeline` for this purpose. When provided, `init_run` is skipped and the given ID is used directly.

### Pipeline Name Normalisation

Three touch points:

| Location | Change |
|---|---|
| `load_pipeline(name_or_path)` | `name_or_path = name_or_path.lower()` before building the yaml filename; only when `not Path(name_or_path).is_file()` |
| `discover_pipelines()` | `pipeline_name = schema.name.lower()` when keying the `found` dict |
| `StateManager.init_run()` | `pipeline_name = pipeline_name.lower()` as first line |
| `run()` CLI entry point | `pipeline = pipeline.lower()` after the not-None guard |

YAML `name:` fields in shipped pipelines should also be lowercase (they already are). User pipelines with mixed-case `name:` fields will be normalised at load time.

## Implementation Details

### Files to change

| File | Change |
|---|---|
| `src/squadron/pipeline/state.py` | Add `ExecutionMode` enum; add `execution_mode` field to `RunState`; bump `_SCHEMA_VERSION` to 2; add `execution_mode` param to `init_run` |
| `src/squadron/pipeline/loader.py` | Normalise pipeline name in `load_pipeline` and `discover_pipelines` |
| `src/squadron/cli/commands/run.py` | Add `ExecutionMode` import; normalise `pipeline` arg; fix `--resume` path; fix implicit resume path; add `run_id` param to `_run_pipeline_sdk` and `_run_pipeline`; pass `ExecutionMode` to `init_run` |

### Test changes

| File | What to test |
|---|---|
| `tests/pipeline/test_state.py` | `ExecutionMode` enum serialises/deserialises correctly; `RunState` with `execution_mode` field; `init_run` stores the mode; schema version mismatch raises `SchemaVersionError` |
| `tests/pipeline/test_loader.py` | `load_pipeline` finds pipeline with mixed-case name; `discover_pipelines` keyed by lowercase name |
| `tests/cli/test_run.py` | `--resume` for SDK run calls `_run_pipeline_sdk`; `--resume` for prompt-only run calls `_run_pipeline`; implicit resume uses stored mode; pipeline name normalised at CLI boundary |

## Integration Points

### Provides to downstream slices

- `ExecutionMode` enum available for 160-series slices that may add further execution modes (e.g. one-shot agent).
- `RunState.execution_mode` field available for display in `sq run --status` (optional enhancement; not required by this slice).

### Consumes

- `SDKExecutionSession` from slice 155 — unchanged; this slice only changes how it is invoked on resume.

## Success Criteria

### Functional

1. `sq run test-pipeline 154` starts an SDK run, pauses at checkpoint, then `sq run --resume <id>` successfully resumes with an SDK session — compact action uses the SDK path, not the CF path.
2. `sq run --prompt-only test-pipeline 154` starts a prompt-only run, pauses at checkpoint, then `sq run --prompt-only --resume <id>` resumes correctly (prompt-only path).
3. `sq run Test-Pipeline 154` and `sq run test-pipeline 154` find the same pipeline definition.
4. `sq run --status <id>` shows `execution_mode` in the run summary.
5. Resuming a schema v1 state file prints a `SchemaVersionError` with a clear message rather than silently failing.

### Technical

1. No string literals `"sdk"` or `"prompt-only"` used in conditional dispatch logic — only `ExecutionMode` enum values.
2. `_SCHEMA_VERSION = 2` in `state.py`.
3. `pyright --strict` passes with zero errors across all changed files.
4. All new tests pass; no existing tests broken.

### Integration

- `sq run --list` shows pipeline names in lowercase (normalised at discover time).
- `sq run --status` output includes `execution_mode` field when printing run details.

## Verification Walkthrough

> These steps verify the slice against a real CF project. Refine with actual command output during Phase 6.

**Setup:** Have a pipeline `test-pipeline` with a checkpoint step. Run from straight terminal (no `CLAUDECODE`).

1. Start a fresh SDK run and let it pause at checkpoint:
   ```
   sq run test-pipeline 154
   # pipeline pauses at checkpoint, prints run_id
   ```

2. Inspect state file — confirm `execution_mode` field is `"sdk"`:
   ```
   cat ~/.config/squadron/runs/<run_id>.json | python3 -m json.tool | grep execution_mode
   # expected: "execution_mode": "sdk"
   ```

3. Resume — should use SDK runner, compact succeeds:
   ```
   sq run --resume <run_id>
   # no "unknown command 'compact'" error; pipeline completes or pauses at next checkpoint
   ```

4. Verify case-insensitive lookup:
   ```
   sq run Test-Pipeline 154    # finds test-pipeline.yaml
   sq run TEST-PIPELINE 154    # finds test-pipeline.yaml
   ```

5. Verify schema version error on stale files:
   ```
   # Manually edit a state file to schema_version: 1
   sq run --resume <modified_id>
   # Expected: "Error: Unsupported state file schema_version: 1"
   ```

6. Verify prompt-only run resumes correctly:
   ```
   sq run --prompt-only test-pipeline 154
   # pauses at checkpoint
   sq run --prompt-only --resume <run_id> --next
   # resumes with prompt-only renderer, not SDK session
   ```
