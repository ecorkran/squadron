---
docType: review
layer: project
reviewType: code
slice: run-liveness-stall-bounds-pruning-and-readable-listings
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: ba637c2e3e62b8437832cd5aff6e92479214f504
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
durationSeconds: 45.0
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Default prune deletes state files it can't read because of a newer schema version"
    location: "src/squadron/pipeline/run_prune.py:DEFAULT_CATEGORIES"
  - id: F002
    severity: concern
    category: error-handling
    summary: "`RunHeartbeat.__aexit__` can swallow cancellation of the enclosing task"
    location: "src/squadron/pipeline/run_heartbeat.py:__aexit__"
  - id: F003
    severity: concern
    category: concurrency
    summary: "`claim` is a non-atomic check-then-write"
    location: "src/squadron/pipeline/state.py:StateManager.claim"
  - id: F004
    severity: concern
    category: design
    summary: "Foreground and background idle timeouts use inconsistent validation"
    location: "src/squadron/pipeline/sdk_session.py:_background_idle_timeout_s"
  - id: F005
    severity: note
    category: design
    summary: "Liveness display strings duplicate enum values"
    location: "src/squadron/cli/run_views.py:LIVENESS_STATUSES"
  - id: F006
    severity: note
    category: DRY
    summary: "Duplicated atomic-write serialization in `StateManager`"
    location: "src/squadron/pipeline/state.py:finalize"
  - id: F007
    severity: note
    category: testing
    summary: "Typing suppressions and a script that writes to the real HOME"
    location: "tests/pipeline/test_run_prune.py:_assess"
  - id: F008
    severity: pass
    category: design
    summary: "Liveness, observer and stall-handling design"
    location: "src/squadron/pipeline/run_liveness.py"
---

# Review: code — slice 174

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Default prune deletes state files it can't read because of a newer schema version

`UNREADABLE` is in the default set. `StateManager.scan_runs` puts every `STATE_READ_ERRORS` failure into `unreadable`, and that includes `SchemaVersionError`. The new tests confirm this: `test_returns_readable_states_and_unreadable_files` lists a `SchemaVersionError` file as unreadable. A run file written by a newer squadron (schema 6+, for example after a downgrade or from a second checkout) is therefore classed as junk. `sq runs prune --yes` deletes it, and it could belong to a live run. `_filtered_out` and the protection rules don't cover it.

Consider keeping schema-mismatch files out of the default set. They could be a separate category, or `UNREADABLE` could cover only parse and validation failures. Also, any non-state `*.json` in the runs dir is treated as an unreadable run and deleted by default.

### [CONCERN] `RunHeartbeat.__aexit__` can swallow cancellation of the enclosing task

`await self._task` is wrapped in `except asyncio.CancelledError: pass`. That is correct for the cancel just issued to the heartbeat task. If the outer task is cancelled while it awaits the heartbeat during teardown, the same exception is swallowed and the cancellation is lost. Check `self._task.cancelled()` or `asyncio.current_task().cancelling()` before swallowing, or re-raise when the heartbeat task itself isn't the one that was cancelled. The trailing `except Exception: pass  # noqa: BLE001` is justified by its comment and by `_report_crash`, so it is acceptable under the project's rule (b).

### [CONCERN] `claim` is a non-atomic check-then-write

`claim` loads the state, asserts it is not live, then writes. Two `--resume` invocations racing on the same paused run can both pass the liveness check and both write an owner, each believing it holds the run. The docstring promises "two processes cannot own one run". Either narrow the claim to say it only guards against an already-live owner, or take a short lock. `project_run_lock` already exists, and the writes sit in the same project.

### [CONCERN] Foreground and background idle timeouts use inconsistent validation

The foreground bound goes through `get_positive_int_config`, which raises a named `ValueError` for 0 or negative values. The background bound still uses `get_typed_config`, so a zero or negative `pipeline.background_idle_timeout_s` is accepted unvalidated. `_foreground_idle_timeout_s` is annotated `-> float` but returns `int`. Use the same validated reader for both.

### [NOTE] Liveness display strings duplicate enum values

`"orphaned"` and `"stale"` are literals that repeat the `RunLiveness` values, and `PruneCategory` repeats them again. Deriving the text from `RunLiveness.X.value` would keep these in one place, as the project's single-definition rule asks. `unavailable_summary` also prints "1 runs reference 1 unavailable pipelines" with no pluralization.

### [NOTE] Duplicated atomic-write serialization in `StateManager`

`_save` was introduced, but `finalize` still calls `_write_atomic(self._state_path(run_id), json.dumps(state.model_dump(...)))` directly. The same pattern likely remains in `_append_step` and elsewhere. Route them all through `_save`.

### [NOTE] Typing suppressions and a script that writes to the real HOME

`_assess` uses `# type: ignore[no-untyped-def]` instead of a return annotation (`LivenessAssessment | None`). `_stall_patches() -> object` in `test_sdk_session.py` is used as a context manager and needs a type-ignore; annotate it as `ExitStack`. Strict pyright is a merge blocker in this project. `tests/pipeline/walkthrough_seed.py` writes to `StateManager()`'s default runs dir under `~`. That is safe only if the caller sets HOME as documented, so consider failing fast when HOME isn't an obvious scratch path.

### [PASS] Liveness, observer and stall-handling design

- Orphaned and stale are defined once and shared by the listing, `wait` and `prune`. Assessment is derived on every read and never persisted.
- `process_alive` rejects pid ≤ 0 and returns unknown.
- Progress-write failures are logged at WARNING, and non-I/O errors propagate.
- A foreground stall interrupts and drains the turn, then marks the session unusable on failure with an ERROR log.
- `apply_prune` refuses paths outside the runs dir.
- Tests use real PIDs and cover the failure signals.

### Run Digest

- Response length: 5388 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 45.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
