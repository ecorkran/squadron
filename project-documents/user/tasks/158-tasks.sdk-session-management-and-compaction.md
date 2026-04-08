---
docType: tasks
slice: sdk-session-management-and-compaction
project: squadron
parent: 158-slice.sdk-session-management-and-compaction.md
dependencies: [155-sdk-pipeline-executor, 156-pipeline-executor-hardening]
projectState: Slice 156 complete (pipeline executor hardening); SDK mode working for pipelines without compact steps. Compact step currently stubbed via configure_compaction() which stores config but never applies it. RunState schema is v2.
dateCreated: 20260406
dateUpdated: 20260407
status: complete
---

# Tasks: SDK Session Management and Compaction

## Context Summary

- Working on slice 158 (SDK Session Management and Compaction)
- Replaces the unconnected `configure_compaction()` stub from slice 155 with working compaction via session rotation
- Core flow: switch to cheap summarizer in current session → query with compact instructions → capture summary → disconnect → create new session → inject summary → restore model
- Compact summaries persisted in `RunState.compact_summaries` (schema v3) so they survive checkpoint and resume
- On resume, the executor seeds the new SDK session with the most recent applicable compact summary before running the next step
- Agent SDK does not expose `context_management`, `compaction_control`, or compaction thresholds — session rotation is the only deterministic path
- Adds optional `model` field to compact YAML for cost control
- Keying scheme is forward-compatible with slice 159 (fan-out branches)

**Files to change:**
- `src/squadron/pipeline/state.py` — `CompactSummary` dataclass, schema v3 bump, `compact_summaries` field, helper, `record_compact_summary` method
- `src/squadron/pipeline/sdk_session.py` — add `compact()`, `seed_context()`, `session_id`, `options`; remove stub
- `src/squadron/pipeline/actions/compact.py` — replace stub with real `compact()` invocation; emit summary in outputs
- `src/squadron/pipeline/steps/compact.py` — pass through `model` field
- `src/squadron/pipeline/executor.py` — persist compact summaries via state callback; inject summary on resume entry
- `src/squadron/cli/commands/run.py` — pass options to session
- `src/squadron/providers/sdk/translation.py` — capture `session_id` from `ResultMessage`

**Next planned slice:** 159 (Pipeline Fan-Out / Fan-In Step Type)

---

## Tasks

### T1 — Capture `session_id` from `ResultMessage` in translation

- [x] In `src/squadron/providers/sdk/translation.py`, update `_translate_result` to include `session_id` in the metadata dict for both success and error subtype branches:
  ```python
  metadata={
      "sdk_type": SDK_RESULT_TYPE,
      "subtype": "success",
      "session_id": msg.session_id,
  }
  ```
- [x] The field is `msg.session_id` per the `ResultMessage` dataclass from `claude_agent_sdk`

**Test T1** — `tests/providers/sdk/test_translation.py`

- [x] Add test: `_translate_result` for a success `ResultMessage` with `session_id="sess-abc"` produces a Message whose metadata includes `session_id == "sess-abc"`
- [x] Add test: same for the error subtype branch

**Commit:** `feat: capture session_id from ResultMessage in SDK translation`

---

### T2 — Add `CompactSummary` dataclass and bump RunState schema to v3

- [x] In `src/squadron/pipeline/state.py`, add a new dataclass before the `RunState` definition:
  ```python
  @dataclass
  class CompactSummary:
      key: str
      text: str
      summary_model: str | None
      source_step_index: int
      source_step_name: str
      created_at: datetime
  ```
- [x] Add `CompactSummary` to `__all__`
- [x] Bump `_SCHEMA_VERSION` from 2 → 3
- [x] Add `compact_summaries: dict[str, CompactSummary] = Field(default_factory=dict)` to `RunState` (use the appropriate Pydantic field syntax — confirm whether `RunState` uses Pydantic or dataclass; existing `execution_mode` field is the pattern reference)
- [x] Confirm `_load_raw` raises `SchemaVersionError` for version mismatches (existing behavior — verify v2 files now fail-load for the same reason v1 did before)

**Test T2** — `tests/pipeline/test_state.py`

- [x] Add test class `TestCompactSummary` with serialization round-trip test (build a `CompactSummary`, dump to dict, reload, assert equal)
- [x] Add test: `RunState` round-trip with `compact_summaries={}` (empty default)
- [x] Add test: `RunState` round-trip with `compact_summaries={"3:compact": CompactSummary(...)}` — full populated case
- [x] Add test: loading a v2-shaped JSON dict (with `schema_version: 2`) raises `SchemaVersionError`
- [x] Add test: loading a JSON dict at v3 without `compact_summaries` field defaults to `{}`

**Commit:** `feat: add CompactSummary and bump RunState schema to v3`

---

### T3 — Add `record_compact_summary` and `active_compact_summary_for_resume`

- [x] In `src/squadron/pipeline/state.py`, add a method to `StateManager`:
  ```python
  def record_compact_summary(self, run_id: str, summary: CompactSummary) -> None:
      """Load state, add summary to compact_summaries dict keyed by summary.key, persist."""
  ```
- [x] Add a method to `RunState`:
  ```python
  def active_compact_summary_for_resume(
      self, resume_step_index: int
  ) -> CompactSummary | None:
      """Return the compact summary with the highest source_step_index strictly
      less than resume_step_index, or None if no such summary exists."""
  ```
- [x] The lookup logic: iterate `self.compact_summaries.values()`, filter by `source_step_index < resume_step_index`, return the one with the highest `source_step_index` (or None if filter is empty)

**Test T3** — `tests/pipeline/test_state.py`

- [x] Add test: `record_compact_summary` adds a new summary to a state file and persists it (load the file back, verify the summary is present)
- [x] Add test: `record_compact_summary` overwrites an existing summary with the same key
- [x] Add test: `active_compact_summary_for_resume` returns `None` when `compact_summaries` is empty
- [x] Add test: with one summary at `source_step_index=3`, `active_compact_summary_for_resume(5)` returns it
- [x] Add test: with one summary at `source_step_index=3`, `active_compact_summary_for_resume(3)` returns `None` (strict less-than)
- [x] Add test: with two summaries at indices 2 and 5, `active_compact_summary_for_resume(7)` returns the index-5 one

**Commit:** `feat: add compact summary persistence and resume lookup helpers`

---

### T4 — Add `session_id` field and `options` to `SDKExecutionSession`

- [x] In `src/squadron/pipeline/sdk_session.py`, import `ClaudeAgentOptions` from `claude_agent_sdk`
- [x] Add two new fields to the `SDKExecutionSession` dataclass:
  - `options: ClaudeAgentOptions` — required, no default
  - `session_id: str | None = None`
- [x] Update `dispatch()` to extract `session_id` from each translated message's metadata and store the most recent one on `self.session_id`
- [x] Log captured session ID at DEBUG level: `"SDKExecutionSession: session_id=%s"`

**Test T4** — `tests/pipeline/test_sdk_session.py`

- [x] Add test: `SDKExecutionSession.dispatch()` captures `session_id` from a mocked response — after dispatch, `session.session_id` equals the mocked value
- [x] Add test: session_id is updated on subsequent dispatches (latest wins)

**Commit:** `feat: add session_id and options to SDKExecutionSession`

---

### T5 — Update `_run_pipeline_sdk` to pass options to session

- [x] In `src/squadron/cli/commands/run.py`, update `_run_pipeline_sdk` to pass `options` when constructing `SDKExecutionSession`:
  ```python
  options = claude_agent_sdk.ClaudeAgentOptions(cwd=str(Path.cwd()))
  client = claude_agent_sdk.ClaudeSDKClient(options=options)
  session = SDKExecutionSession(client=client, options=options)
  ```
- [x] Grep for any other `SDKExecutionSession(` construction sites and update them

**Test T5** — `tests/cli/commands/test_run_pipeline.py` and `tests/pipeline/test_sdk_wiring.py`

- [x] Update existing tests that mock `SDKExecutionSession` to provide `options` (or verify patches are unaffected)
- [x] All prior SDK tests still pass

**Commit:** `feat: pass ClaudeAgentOptions into SDKExecutionSession`

---

### T6 — Implement `SDKExecutionSession.compact()` method

- [x] In `src/squadron/pipeline/sdk_session.py`, add a new async method:
  ```python
  async def compact(
      self,
      instructions: str,
      summary_model: str | None = None,
      restore_model: str | None = None,
  ) -> str:
      """Perform session-rotate compaction. Returns the summary text."""
  ```
- [x] Implementation order:
  1. If `summary_model` provided and different from current, `await self.set_model(summary_model)`
  2. `summary = await self.dispatch(instructions)` — query live session with compact template
  3. `await self.disconnect()` — close old conversation
  4. Create a new client: `new_client = ClaudeSDKClient(options=self.options)`
  5. Replace `self.client = new_client`
  6. Reset `self.current_model = None` and `self.session_id = None`
  7. `await self.connect()` — re-applies `bypassPermissions`
  8. `await self.dispatch(summary)` — seed new session with summary text (discard response)
  9. If `restore_model` provided, `await self.set_model(restore_model)`
  10. Return `summary`
- [x] Log each major step at DEBUG level
- [x] Allow exceptions to propagate — caller (compact action) catches them

**Test T6** — `tests/pipeline/test_sdk_session.py`

- [x] Add test class `TestCompactSessionRotate`
- [x] Test: `compact()` with `summary_model=None` skips the initial set_model call
- [x] Test: `compact()` with `summary_model="haiku-id"` calls `set_model("haiku-id")` before dispatch
- [x] Test: `compact()` dispatches the instructions, captures the response as summary, returns it
- [x] Test: `compact()` calls `disconnect()` on the old client and creates a new `ClaudeSDKClient`
- [x] Test: after `compact()`, `self.client` is the new client and `self.current_model` matches `restore_model`
- [x] Test: `compact()` with `restore_model="sonnet-id"` calls `set_model("sonnet-id")` at the end
- [x] Use `patch("squadron.pipeline.sdk_session.ClaudeSDKClient")` to intercept client creation

**Commit:** `feat: add SDKExecutionSession.compact() session rotate method`

---

### T7 — Add `seed_context` method to `SDKExecutionSession`

- [x] In `src/squadron/pipeline/sdk_session.py`, add:
  ```python
  async def seed_context(self, text: str) -> None:
      """Seed a fresh session with prior compact summary on resume.

      Thin wrapper around dispatch() that logs distinctly so verbose
      output identifies seeding events vs. real step dispatches.
      """
  ```
- [x] Implementation: log at DEBUG `"SDKExecutionSession: seed_context (%d chars)"`, then call `await self.dispatch(text)`, discard the response

**Test T7** — `tests/pipeline/test_sdk_session.py`

- [x] Add test: `seed_context("summary text")` calls `dispatch("summary text")` exactly once
- [x] Add test: return value is `None` even though dispatch returns a string (response is discarded)

**Commit:** `feat: add seed_context method for resume re-injection`

---

### T8 — Remove `configure_compaction()` stub and `_compaction_config`

- [x] In `src/squadron/pipeline/sdk_session.py`, delete:
  - The `_compaction_config` field
  - The `configure_compaction()` method
  - The import of `field` from `dataclasses` if no longer needed
- [x] Grep for `configure_compaction` and `_compaction_config` to verify no remaining references

**Test T8** — `tests/pipeline/test_sdk_session.py`

- [x] Delete any tests that exercised `configure_compaction()` directly
- [x] Run the full file to confirm no references remain

**Commit:** `refactor: remove configure_compaction stub from SDKExecutionSession`

---

### T9 — Add `model` field to compact step YAML and step validator

- [x] In `src/squadron/pipeline/steps/compact.py`, update `validate()` to check optional `model` field:
  - Allow `None`
  - Must be `str` if present
  - Add `ValidationError` with field `"model"` on type mismatch
- [x] In `expand()`, pass `model` through to the compact action config:
  ```python
  action_config = {"template": template, "model": cfg.get("model"), ...}
  ```
- [x] Verify `validate_pipeline` in `loader.py` picks up compact step's model for alias validation (the existing `_validate_model_alias` loop iterates over all steps and checks `step.config.get("model")`)

**Test T9** — `tests/pipeline/steps/test_compact.py`

- [x] Add test: compact step with `model: haiku` validates successfully
- [x] Add test: compact step with `model: 42` (non-string) produces `ValidationError` on field `"model"`
- [x] Add test: compact step without `model` validates successfully (optional)
- [x] Add test: `expand()` includes `model` in the action config when present
- [x] Add test: `expand()` produces `model: None` in the action config when absent

**Commit:** `feat: add optional model field to compact step`

---

### T10 — Wire compact action to call `SDKExecutionSession.compact()`

- [x] In `src/squadron/pipeline/actions/compact.py`, update the SDK-mode branch of `execute()`:
  - Remove the `configure_compaction()` call
  - Resolve summary model if `context.params.get("model")` is set: `model_id, _ = context.resolver.resolve(action_model=model, step_model=None)`
  - Capture current model before compact: `restore_model = context.sdk_session.current_model`
  - Call `summary = await context.sdk_session.compact(instructions=instructions, summary_model=model_id, restore_model=restore_model)`
  - Build `outputs` dict including `summary` (text) and `instructions`; also include the keying primitives the executor needs to persist (`source_step_index=context.step_index`, `source_step_name=context.step_name`, `summary_model=model_id`)
  - Return `ActionResult(success=True, outputs=outputs, metadata={"summary_model": model_id or ""})`
- [x] Wrap in `try/except` to catch provider/SDK errors → `ActionResult(success=False, error=str(exc))`
- [x] Update the compact action's `validate()` to accept `model` as optional string

**Test T10** — `tests/pipeline/actions/test_compact.py` and `tests/pipeline/actions/test_compact_sdk.py`

- [x] Update existing SDK tests that used `configure_compaction()` to verify `compact()` is called instead
- [x] Test: SDK-mode compact with `model: "haiku"` calls `resolver.resolve("haiku", None)` and passes the resolved model_id as `summary_model`
- [x] Test: SDK-mode compact without `model` passes `summary_model=None`
- [x] Test: SDK-mode compact captures `current_model` before invoking `compact()` and passes it as `restore_model`
- [x] Test: successful compact returns `ActionResult(success=True)` with `summary`, `instructions`, `source_step_index`, `source_step_name` in outputs
- [x] Test: exception from `session.compact()` returns `ActionResult(success=False)` with the error message
- [x] Test: non-SDK-mode compact path (no `sdk_session`) still uses CF compaction — unchanged

**Commit:** `feat: wire compact action to session rotate compaction`

---

### T11 — Persist compact summary via executor `on_step_complete` callback

- [x] In `src/squadron/pipeline/executor.py`, locate the per-step completion handling. After a successful compact action, the executor should:
  - Detect that the action type is `compact` and `outputs` contains `summary` and the keying primitives
  - Build a `CompactSummary` record with `key=f"{source_step_index}:{source_step_name}"` and the other fields from outputs (and `created_at=datetime.now(UTC)`)
  - Call `state_manager.record_compact_summary(run_id, summary)` (the state manager reference is already wired through `make_step_callback` per slice 156)
- [x] If the callback wiring doesn't currently expose the state manager directly, route via the existing callback signature (the `on_step_complete` callable). If the callable can't reach `record_compact_summary`, extend it — but prefer the smallest plumbing change

**Test T11** — `tests/pipeline/test_executor.py` (or an executor-focused test file)

- [x] Build a fake compact `ActionResult` with `success=True`, `outputs={"summary": "abc", "instructions": "...", "source_step_index": 3, "source_step_name": "compact-mid", "summary_model": "haiku-id"}`
- [x] Test: after the executor processes this result, `state_manager.record_compact_summary` is called once with a `CompactSummary` whose key is `"3:compact-mid"` and text is `"abc"`
- [x] Test: a non-compact `ActionResult` does not trigger `record_compact_summary`

**Commit:** `feat: persist compact summaries via executor callback`

---

### T12 — Executor resume injection

- [x] In `src/squadron/pipeline/executor.py`, at the resume entry point (when `start_from is not None`), add logic before the first action runs:
  ```python
  if start_from is not None and sdk_session is not None:
      active = state.active_compact_summary_for_resume(start_step_index)
      if active is not None:
          _logger.info(
              "executor: resuming at step %d; seeding session from compact summary %s",
              start_step_index, active.key,
          )
          await sdk_session.seed_context(active.text)
  ```
- [x] `start_step_index` here is the index of the step the executor is about to run (not the last completed step). Verify the existing resume code computes this — name it consistently with what's already there.
- [x] The state object available in the executor: confirm `RunState` is loaded and accessible at this point (it should be, since the executor already uses it for `prior_outputs`). If not, load it via `state_manager.load(run_id)`.

**Test T12** — `tests/pipeline/test_executor.py`

- [x] Build a `RunState` with one `CompactSummary` at `source_step_index=2`
- [x] Mock an `SDKExecutionSession` (specifically its `seed_context` method)
- [x] Invoke `execute_pipeline` with `start_from` pointing to step index 4 (or whatever maps to a step beyond the compact)
- [x] Assert: `sdk_session.seed_context` is called once with the summary text BEFORE any action executes
- [x] Test: when `start_from is None` (fresh run), `seed_context` is NOT called
- [x] Test: when `sdk_session is None` (prompt-only resume), `seed_context` is NOT called
- [x] Test: when `compact_summaries` is empty, `seed_context` is NOT called

**Commit:** `feat: executor seeds SDK session from compact summary on resume`

---

### T13 — (removed: PreCompact hook moved to a separate slice)

The `PreCompact` hook for interactive Claude Code (VS Code extension, CLI Claude Code) is a `.claude/settings.json` shell hook, not an Agent SDK option. It is unrelated to SDK-mode session management and is covered by a follow-up slice.

---

### T14 — Automated integration test for full session rotate flow

- [x] In `tests/pipeline/test_sdk_wiring.py`, add a test that exercises dispatch → compact → dispatch with a mocked session:
  - Build a pipeline definition with three steps: dispatch → compact → dispatch
  - Mock `SDKExecutionSession` (or pass a mock via `_action_registry`) so that:
    - `dispatch()` returns a fake response
    - `compact()` returns a summary string and is callable
    - `set_model()`, `connect()`, `disconnect()`, `seed_context()` are spy methods
  - Run `execute_pipeline()` end-to-end against this mock
  - Assert: dispatch is called for step 1; `compact()` is called for step 2; dispatch is called for step 3
  - Assert: the post-compact dispatch call sees the same session object (no executor confusion about client identity)
  - Assert: state recording for the compact step persists a `CompactSummary` keyed correctly

**Commit:** `test: add integration test for SDK session rotate flow`

---

### T15 — Automated test for resume-after-compact

- [x] In `tests/cli/commands/test_run_pipeline.py` (or `tests/pipeline/test_executor.py` if it fits better), add a test:
  - Pre-build a state file with: completed dispatch (step 0), completed compact (step 1) including a `CompactSummary` in `compact_summaries`, paused checkpoint, status `paused`
  - Mock `SDKExecutionSession` with spy methods on `seed_context`, `set_model`, `dispatch`, `connect`, `disconnect`
  - Invoke `_run_pipeline_sdk` with the existing `run_id` (resume path)
  - Assert: a fresh `ClaudeSDKClient` is created (not a stale reference)
  - Assert: `seed_context` is called once with the summary text BEFORE any subsequent action
  - Assert: the next dispatch step runs after seeding

**Commit:** `test: add resume-after-compact integration test`

---

### T16 — End-to-end manual smoke test with test-pipeline

- [x] Add `model: haiku` to the compact step in `src/squadron/data/pipelines/test-pipeline.yaml`
- [x] Manual verification (not automated):
  - Run `uv run sq run test-pipeline 154 -vv` from a standard terminal
  - Expected log lines: model switch to haiku, compact dispatch, summary captured, disconnect, new connect, summary injected, model restored
  - Expected: subsequent dispatch steps succeed with the new session
  - Inspect `~/.config/squadron/runs/<run-id>.json` and confirm `compact_summaries` contains the recorded summary
- [x] Manual resume verification:
  - Modify `test-pipeline.yaml` temporarily to add a checkpoint after compact (`always` trigger)
  - Run the pipeline; checkpoint fires after compact and exits
  - Run `uv run sq run --resume <run-id> -vv`
  - Expected log lines: `executor: resuming at step N; seeding session from compact summary "..."` followed by `SDKExecutionSession: seed_context (... chars)`
  - Revert the test-pipeline.yaml change after verification
- [x] Document the captured log lines in the DEVLOG entry for closeout

**Commit:** `test: add model field to test-pipeline compact step for verification`

---

### T17 — Lint, type-check, and full test suite

- [x] Run `uv run ruff check src/ tests/` — zero errors
- [x] Run `uv run ruff format src/ tests/` — no reformatting needed on changed files
- [x] Run `uv run pyright src/squadron/pipeline/state.py src/squadron/pipeline/sdk_session.py src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/compact.py src/squadron/pipeline/executor.py src/squadron/cli/commands/run.py src/squadron/providers/sdk/translation.py` — zero errors, zero warnings
- [x] Run `uv run pytest -q` — all tests pass

**Commit:** `chore: lint and verify slice 158 session management and compaction`

---

### T18 — Slice closeout

- [x] Mark all T1–T17 tasks complete in this file
- [x] Set `status: complete` and update `dateUpdated` in this task file's frontmatter
- [x] Set `status: complete` and update `dateUpdated` in `157-slice.sdk-session-management-and-compaction.md`
- [x] In `140-slices.pipeline-foundation.md`, check off slice 158 and update `dateUpdated`
- [x] Add DEVLOG entry summarizing the implementation per `prompt.ai-project.system.md` Session State Summary format
- [x] Add CHANGELOG entries: `### Added` (session rotate compaction, persisted compact summaries, schema v3, executor resume injection, compact model field) and `### Removed` (`configure_compaction()` stub)
- [x] Final commit

**Commit:** `docs: mark slice 158 SDK session management and compaction complete`

---

## Notes

- **Summary injection seeding (T6)**: The new session receives the summary as the first user message via `dispatch()`. The model's response is typically a brief acknowledgment, which we discard. This establishes the summary as the conversation's starting context. If this proves unreliable (model treats the summary as a task to execute), consider a system prompt prefix instead — fallback for implementation discovery, not the default approach.
- **Executor callback wiring for T11**: Slice 156 already wired `make_step_callback` through `execute_pipeline` for state updates. T11 should reuse that path. If the callback signature doesn't naturally surface compact-specific persistence, extend it minimally (e.g., the callback could detect compact action type and dispatch accordingly), but avoid re-architecting the callback wiring.
- **State manager reference in compact action**: The action does NOT call `state_manager` directly. The summary travels in `ActionResult.outputs`, and the executor's per-step handler builds the `CompactSummary` record and calls `record_compact_summary`. This keeps actions free of state-manager coupling and matches how prior outputs are already handled.
- **Schema bump impact**: v2 → v3 means any v2 state files in the wild will fail to load with `SchemaVersionError`. This matches the v1 → v2 pattern from slice 156. Users who hit this should start fresh runs.
- **Keying scheme alignment with slice 159**: Top-level compact summaries use `{step_index}:{step_name}`. Slice 159 will extend to branch-internal compactions with `{step_index}:{step_name}#branch{n}`. The storage shape (`dict[str, CompactSummary]`) does not change. The lookup helper will be extended in 159 to consider branch context.
