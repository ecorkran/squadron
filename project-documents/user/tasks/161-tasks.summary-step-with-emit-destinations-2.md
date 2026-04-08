---
docType: tasks
slice: summary-step-with-emit-destinations
project: squadron
parent: 161-slice.summary-step-with-emit-destinations.md
dependencies: [158-sdk-session-management-and-compaction]
projectState: Slice 158 complete — SDK session-rotate compaction via SDKExecutionSession.compact() working end-to-end. compact action populates RunState.compact_summaries. claude_code system prompt preset wired in run.py. Response-text duplication bug fixed. PreCompact hook no longer installed by default. Test pipeline extended with tasks+post-compact-dispatch for smoke tests.
dateCreated: 20260408
dateUpdated: 20260408
status: not_started
---

# Tasks: Summary Step with Emit Destinations (Part 2 of 2)

> **Part 1** (`161-tasks.summary-step-with-emit-destinations-1.md`)
> covers dependency + core mechanism: pyperclip, the
> `SDKExecutionSession` capture/rotate split, the emit registry and
> its built-in destinations, the emit parser, and the new summary
> action implementation. Tasks T1–T9.
>
> **Part 2** (this file) covers the compact alias refactor, summary
> step type, loader validation, end-to-end integration tests, smoke
> pipeline update, lint/type-check, and closeout. Tasks T10–T17.

## Context Summary (abridged)

- T1–T9 have landed: pyperclip is a dependency, `SDKExecutionSession`
  has `capture_summary()` and a `summary=` overload on `compact()`,
  the emit module has a registry with stdout/file/clipboard/rotate
  destinations and a YAML parser, `SummaryAction` exists with
  config validation, and `_execute_summary()` is the shared helper
  that captures the summary once and dispatches it across emit
  destinations.
- T10–T17 integrate the new machinery with the existing pipeline:
  refactor compact to delegate into `_execute_summary()` with
  `emit=[rotate]` (backward compatible), add the `summary` step
  type with `checkpoint:` shorthand, wire everything into the
  executor's import-side-effect block, extend loader validation,
  add end-to-end integration tests, update the smoke pipeline, run
  lint/type-check/full pytest, and close the slice out.

---

## Tasks

### T10 — Refactor `CompactAction` SDK path to delegate into `_execute_summary()`

- [ ] In `src/squadron/pipeline/actions/compact.py`, modify the
  SDK branch of `CompactAction.execute()`:
  1. Keep the existing template loading and `render_instructions`
     call unchanged.
  2. Replace the `session.compact(...)` block with:
     ```python
     from squadron.pipeline.actions.summary import _execute_summary
     from squadron.pipeline.emit import EmitDestination, EmitKind

     return await _execute_summary(
         context=context,
         instructions=instructions,
         summary_model_alias=context.params.get("model"),
         emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
         action_type=self.action_type,  # stays "compact"
     )
     ```
- [ ] CRITICAL: the compact action's `action_type` stays `"compact"`
  — the state callback
  (`StateManager._maybe_record_compact_summaries`) keys on
  `action_type == "compact"`, so this must not be changed to
  `"summary"` or compact summaries stop persisting.
- [ ] Verify outputs shape is compatible with
  `_maybe_record_compact_summaries()`: the existing code reads
  `outputs["summary"]`, `outputs["source_step_index"]`,
  `outputs["source_step_name"]`, `outputs["summary_model"]`. All
  of these are still present from `_execute_summary()`. The
  `"instructions"` key is also there.
- [ ] Non-SDK (CF) path in compact action: UNCHANGED. Still calls
  `cf_client._run(["compact", "--instructions", ...])`.
- [ ] Remove the now-unused direct call to
  `context.sdk_session.compact(...)` and the restore_model
  capture (that logic lives inside `_execute_summary`).

**Test T10** — `tests/pipeline/actions/test_compact_sdk.py`

- [ ] Update existing tests: the compact action now goes through
  `_execute_summary` which calls `capture_summary` + the rotate
  emit (which calls `session.compact(summary=...)`). Tests that
  asserted `session.compact(instructions=..., summary_model=...,
  restore_model=...)` need to be updated to assert on the new
  call chain.
- [ ] Add test: compact action with SDK session and
  `params={"model": "haiku"}` produces outputs with
  `summary`, `instructions`, `source_step_index`, `source_step_name`,
  `summary_model` all present (backward-compatible with slice 158
  state persistence).
- [ ] Add test: compact action's result `action_type` is
  `"compact"`, not `"summary"`.
- [ ] Add test: running the state callback
  `StateManager.make_step_callback(run_id)` against a StepResult
  containing the compact action's result still records a
  `CompactSummary` in `compact_summaries` (regression test for
  the refactor — ensures
  `_maybe_record_compact_summaries()` still fires).
- [ ] Add test: non-SDK compact path is byte-identical to before
  (pass `sdk_session=None`, verify CF client is called).
- [ ] Add test: exception from rotate emit is surfaced as
  `ActionResult(success=False)` with the rotate error.

**Commit:** `refactor: delegate compact SDK path into _execute_summary`

---

### T11 — Add `StepTypeName.SUMMARY` and create summary step module

- [ ] In `src/squadron/pipeline/steps/__init__.py`, add
  `SUMMARY = "summary"` to the `StepTypeName` StrEnum.
- [ ] Create `src/squadron/pipeline/steps/summary.py`.
- [ ] Implement `SummaryStepType` with:
  - `step_type` property returning `StepTypeName.SUMMARY`.
  - `validate(config)` that checks:
    - `template` optional (string)
    - `model` optional (string)
    - `emit` optional (delegate to `parse_emit_list`, catch
      `ValueError`, produce `ValidationError(field="emit", ...)`)
    - `checkpoint` optional (string; validated against the
      existing checkpoint trigger enum — reuse the validation
      used by phase steps; if a shared helper doesn't exist, add
      one in `steps/__init__.py` or `steps/_shared.py`)
  - `expand(config)`:
    1. Build the summary action config dict by copying
       `template`, `model`, `emit` (if present).
    2. If `checkpoint` is set, return
       `[("summary", summary_config), ("checkpoint", {"trigger": checkpoint_value})]`.
    3. Otherwise return `[("summary", summary_config)]`.
- [ ] Register via `register_step_type(StepTypeName.SUMMARY,
  SummaryStepType())` at module bottom.

**Test T11** — `tests/pipeline/steps/test_summary.py` (new file)

- [ ] Test: `SummaryStepType().step_type == "summary"`.
- [ ] Test: `validate({"template": "minimal-sdk"})` returns no errors.
- [ ] Test: `validate({"template": 42})` returns one error on
  field `"template"`.
- [ ] Test: `validate({"emit": ["banana"]})` returns one error on
  field `"emit"`.
- [ ] Test: `validate({"checkpoint": "always"})` returns no errors.
- [ ] Test: `validate({"checkpoint": "nope"})` returns one error
  on field `"checkpoint"`.
- [ ] Test: `expand({"template": "minimal-sdk"})` returns exactly
  one action tuple: `("summary", {"template": "minimal-sdk"})`.
- [ ] Test: `expand({"template": "minimal-sdk", "model": "haiku",
  "emit": ["stdout", "clipboard"]})` returns one action tuple
  with all three fields preserved.
- [ ] Test: `expand({"template": "minimal-sdk", "checkpoint":
  "always"})` returns TWO action tuples: `("summary", {...})`
  followed by `("checkpoint", {"trigger": "always"})`.
- [ ] Test: `expand({"template": "minimal-sdk", "checkpoint":
  "on-fail"})` produces a checkpoint action with
  `{"trigger": "on-fail"}`.

**Commit:** `feat: add SummaryStepType with checkpoint shorthand`

---

### T12 — Register new action and step modules in executor imports

- [ ] In `src/squadron/pipeline/executor.py`, locate the block of
  import-side-effect statements at the top of `execute_pipeline()`
  (currently imports `_a_cf_op`, `_a_ckpt`, `_a_commit`,
  `_a_compact`, `_a_devlog`, `_a_dispatch`, `_a_review`,
  `_s_collection`, `_s_compact`, `_s_devlog`, `_s_phase`,
  `_s_review`).
- [ ] Add:
  ```python
  import squadron.pipeline.actions.summary as _a_summary  # noqa: F401
  import squadron.pipeline.steps.summary as _s_summary  # noqa: F401
  ```
- [ ] Add `_a_summary` and `_s_summary` to the `_ = (...)` tuple
  that pins the imports (to satisfy ruff F401 and keep the
  registrations alive).

**Test T12** — verified via existing integration tests

- [ ] No new unit test. The new step type and action are exercised
  via T13 smoke-pipeline tests and any integration test that runs
  `execute_pipeline` with a summary step (see T14).
- [ ] Run `uv run pytest tests/pipeline/ -q` to confirm no
  regressions from the new imports.

**Commit:** `feat: register summary action and step type in executor`

---

### T13 — Pipeline loader validation: reject unknown emit entries

- [ ] Verify that `validate_pipeline` in
  `src/squadron/pipeline/loader.py` already walks each step's
  config via the step type's `validate()` method. If yes, the
  T11 validator catches unknown emit entries at load time —
  NO additional loader changes are needed.
- [ ] If the loader does NOT walk step validators, add a minimal
  call to each registered step type's `validate()` during
  `validate_pipeline`.
- [ ] Do NOT attempt a load-time "rotate requires SDK mode"
  warning — that is deferred per the slice design's Open Questions.

**Test T13** — `tests/pipeline/test_loader.py` (or wherever
`validate_pipeline` is tested)

- [ ] Add test: a pipeline containing
  `- summary: { template: minimal-sdk, emit: [banana] }`
  produces a ValidationError with field `"emit"` when validated.
- [ ] Add test: a pipeline containing
  `- summary: { template: minimal-sdk }` validates clean.
- [ ] Add test: a pipeline containing
  `- summary: { template: minimal-sdk, emit: [rotate] }`
  validates clean (no load-time rotate warning in 161).

**Commit:** `feat: validate summary step emit entries at pipeline load`

---

### T14 — End-to-end integration test: summary action through executor

- [ ] In `tests/pipeline/test_compact_integration.py` (reuse the
  existing file from slice 158), add a new test class or
  function group `TestSummaryStep`.
- [ ] Test: a pipeline with `- summary: { template: minimal-sdk,
  emit: [stdout] }` run via `execute_pipeline` with a mocked
  SDK session produces a StepResult with the summary action's
  outputs, emits to stdout (captured via `capsys`), and does NOT
  rotate the session.
- [ ] Test: a pipeline with `- summary: { template: minimal-sdk,
  emit: [file: ./out.md] }` writes to `tmp_path / "out.md"` when
  the pipeline's cwd is set to `tmp_path`.
- [ ] Test: a pipeline with `- summary: { ..., emit: [rotate] }`
  calls `session.compact(summary=<captured>)` exactly once.
  Verify via mock that `session.compact` was called with a
  non-None `summary` kwarg.
- [ ] Test: a pipeline with `- summary: { ..., checkpoint: always }`
  causes the pipeline to pause (PAUSED status) after the summary
  emits.
- [ ] Test: a pipeline with `- summary: { ..., emit: [rotate] }`
  and `sdk_session=None` (prompt-only mode) produces a FAILED
  step result with the "requires SDK execution mode" error.
- [ ] Test: a pipeline with `- compact: { template: minimal-sdk,
  model: haiku }` (the existing alias) produces outputs that the
  state callback records into `compact_summaries` — regression
  check for the T10 refactor.

**Commit:** `test: add end-to-end summary step integration tests`

---

### T15 — Update test-pipeline.yaml with a summary smoke step

- [ ] In `src/squadron/data/pipelines/test-pipeline.yaml`, modify
  the existing compact step location or add a new step between
  tasks and the post-compact design step. Choose ONE of:

  **Option A** (recommended) — replace the existing compact step
  with an equivalent summary step to prove the alias is not
  needed for correctness:
  ```yaml
    - summary:
        template: minimal-sdk
        model: haiku
        emit: [rotate]
  ```

  **Option B** — keep the compact step, add a second summary
  step earlier (e.g. after design) that exercises non-rotate
  emits:
  ```yaml
    - summary:
        template: minimal-sdk
        model: haiku
        emit:
          - stdout
          - file: /tmp/sq-test-summary.md
  ```

- [ ] Pick Option A for the default; it proves `summary` can
  fully replace `compact`. Document in a YAML comment that
  compact is still the preferred alias for the common case.
- [ ] Verify validation passes: `uv run sq run --validate test-pipeline`.

**Test T15** — manual smoke only

- [ ] On the developer machine, run
  `uv run sq run test-pipeline 154 -vv` from a standard terminal.
- [ ] Confirm the log shows: design → tasks → summary (with
  model switch to haiku, dispatch of minimal-sdk instructions,
  summary captured, session disconnected, new client created,
  framed seed dispatched to new session) → post-compact design.
- [ ] Confirm the post-compact dispatch step responds with
  awareness of pre-rotation context (the verification signature
  from slice 158 — the model should reference the prior design
  work for slice 154).
- [ ] Document the observed behavior in the slice closeout
  DEVLOG entry.

**Commit:** `chore: update test-pipeline to exercise summary step`

---

### T16 — Lint, type-check, and full test suite

- [ ] Run `uv run ruff format src/ tests/` — should report
  no file changes on already-formatted code.
- [ ] Run `uv run ruff check src/ tests/` — zero errors.
- [ ] Run
  `uv run pyright src/squadron/pipeline/emit.py
  src/squadron/pipeline/sdk_session.py
  src/squadron/pipeline/actions/summary.py
  src/squadron/pipeline/actions/compact.py
  src/squadron/pipeline/steps/summary.py
  src/squadron/pipeline/executor.py` — zero errors, zero
  warnings.
- [ ] Run `uv run pytest -q` — all tests pass.
- [ ] If any slice 158 test broke from the T3/T10 refactors, fix
  the test (NOT the refactor) — the refactor's correctness is
  verified by the updated tests, and backward-compat is verified
  by the state-callback regression test in T10.

**Commit:** `chore: lint and verify slice 161 summary step`

---

### T17 — Slice closeout

- [ ] Mark all T1–T16 tasks complete in both task files (part 1
  and part 2).
- [ ] Set `status: complete` and update `dateUpdated` in both task
  file frontmatters.
- [ ] Set `status: complete` and update `dateUpdated` in
  `161-slice.summary-step-with-emit-destinations.md`.
- [ ] In `140-slices.pipeline-foundation.md`, check off slice 161
  and update `dateUpdated`.
- [ ] Add CHANGELOG entries under `[Unreleased]`:
  - `### Added` — summary step type with emit destinations
    (stdout, file, clipboard, rotate), emit registry, checkpoint
    shorthand, `SDKExecutionSession.capture_summary()`
  - `### Changed` — `SDKExecutionSession.compact()` gained an
    optional `summary=` kwarg so pre-captured summaries can be
    reused for session rotation without a second summarizer
    dispatch; `CompactAction`'s SDK path now delegates into the
    shared summary helper (backward compatible — same outputs,
    same state persistence)
- [ ] Add a DEVLOG entry summarizing the implementation per
  `prompt.ai-project.system.md` Session State Summary format.
  Include: commits made, the manual smoke test result from T15,
  any surprises, and the status of the `clear` follow-up
  (deferred, not filed as a slice yet).
- [ ] Final commit.

**Commit:** `docs: mark slice 161 summary step with emit destinations complete`

---

## Notes

- **Capture-then-rotate factoring (T2/T3/T5/T10)**: the whole
  point of splitting `capture_summary()` out of `compact()` and
  giving `compact()` a `summary=` overload is so that when a user
  writes `emit: [stdout, rotate]`, the summarizer model runs
  exactly once. The captured text is reused for both the stdout
  emit AND the rotate's seed. Without this factoring, rotate
  would re-run the summarizer on the (now-seeded) new session,
  which is nonsensical.

- **Compact alias preservation (T10)**: keeping
  `action_type == "compact"` on the refactored compact action is
  load-bearing — the state callback
  `StateManager._maybe_record_compact_summaries()` filters on it.
  Changing that string would break `compact_summaries`
  persistence and in turn break resume-after-compact behavior
  from slice 158. T10's state-callback regression test is the
  guard.

- **Failure isolation (T8 — part 1)**: the emit chain is *not* a
  transaction. A failing clipboard emit does not un-do a
  successful file emit, and a successful later emit does not
  retroactively rescue an earlier failure. Each destination is
  independent, and the `emit_results` list records all of them
  for post-mortem. Only `rotate` failures halt the action — the
  semantics being that rotation is consequential (the session
  state changes) while the others are observational.

- **Pyperclip lazy import (T5 — part 1)**: pyperclip's platform
  probe can misbehave in niche environments (headless CI,
  restricted containers). Deferring `import pyperclip` to inside
  `_emit_clipboard` keeps the emit module itself import-clean
  everywhere. The cost is a first-call delay when clipboard is
  used; negligible.

- **Empty `instructions` in rotate emit (T5 — part 1)**: when
  rotate is called from the summary action, `_execute_summary()`
  has already captured the summary. The rotate emit calls
  `session.compact(instructions="", summary=<captured>, ...)`.
  The empty `instructions` string is safe because the new
  `summary=` overload of compact() (T3 — part 1) skips the
  capture phase entirely when `summary` is provided —
  `instructions` is never sent anywhere when `summary` is truthy.

- **Prompt-only mode (T8 part 1 / T14 part 2)**: the action-level
  check (`context.sdk_session is None`) is the authoritative
  "prompt-only mode blocks summary" guard. The slice design
  defers load-time warnings because the validator surface is
  error-only today; adding a warning channel is not worth a
  feature for this one use case.

- **`checkpoint: always` shorthand (T11)**: this is pure sugar.
  `expand()` returns two action tuples whose runtime behavior is
  identical to writing the checkpoint as a separate step
  immediately after the summary step. The shorthand exists
  because "summarize and pause" is the single most common shape
  for this feature, and reading
  `- summary: { ..., checkpoint: always }` is much clearer than
  two separate steps.

- **No state file changes**: no `RunState` field additions, no
  schema bump. `compact_summaries` stays compact-only. If a
  future slice wants to seed from summary steps on resume,
  extending `_maybe_record_compact_summaries()` to also key on
  `action_type == "summary"` is a small additive change.
