---
docType: tasks
slice: sdk-session-management-and-compaction
project: squadron
parent: 157-slice.sdk-session-management-and-compaction.md
dependencies: [155-sdk-pipeline-executor, 156-pipeline-executor-hardening]
projectState: Slice 156 complete (pipeline executor hardening); SDK mode working for pipelines without compact steps. Compact step currently stubbed via configure_compaction() which stores config but never applies it.
dateCreated: 20260406
dateUpdated: 20260406
status: not_started
---

# Tasks: SDK Session Management and Compaction

## Context Summary

- Working on slice 157 (SDK Session Management and Compaction)
- Replaces the unconnected `configure_compaction()` stub from slice 155 with working compaction via session rotation
- Core flow: switch to cheap summarizer in current session → query with compact instructions → capture summary → disconnect → create new session → inject summary → restore model
- Agent SDK does not expose `context_management`, `compaction_control`, or compaction thresholds — session rotation is the only deterministic path
- Also wires `PreCompact` hook for interactive `/compact` instruction injection in prompt-only mode
- Adds optional `model` field to compact YAML for cost control

**Files to change:**
- `src/squadron/pipeline/sdk_session.py` — add `compact()`, `session_id`, store options; remove stub
- `src/squadron/pipeline/actions/compact.py` — replace stub call with real `compact()` invocation
- `src/squadron/pipeline/steps/compact.py` — pass through `model` field
- `src/squadron/cli/commands/run.py` — pass options to session, wire `PreCompact` hook
- `src/squadron/providers/sdk/translation.py` — capture `session_id` from `ResultMessage`

**Next planned slice:** 152 (Pipeline Documentation and Authoring Guide)

---

## Tasks

### T1 — Capture `session_id` from `ResultMessage` in translation

- [ ] In `src/squadron/providers/sdk/translation.py`, update `_translate_result` to include `session_id` in the metadata dict:
  ```python
  metadata={
      "sdk_type": SDK_RESULT_TYPE,
      "subtype": "success",
      "session_id": msg.session_id,
  }
  ```
- [ ] Apply the same change to the error subtype branch
- [ ] The field is `msg.session_id` per the `ResultMessage` dataclass from `claude_agent_sdk`

**Test T1** — `tests/providers/sdk/test_translation.py`

- [ ] Add test: `_translate_result` for a success `ResultMessage` with `session_id="sess-abc"` produces a Message whose metadata includes `session_id == "sess-abc"`
- [ ] Add test: same for error subtype

**Commit:** `feat: capture session_id from ResultMessage in SDK translation`

---

### T2 — Add `session_id` field and `_options` to `SDKExecutionSession`

- [ ] In `src/squadron/pipeline/sdk_session.py`, import `ClaudeAgentOptions` from `claude_agent_sdk`
- [ ] Add two new fields to the `SDKExecutionSession` dataclass:
  - `options: ClaudeAgentOptions` — the options used to create the client (required, no default)
  - `session_id: str | None = None` — populated during `dispatch()`
- [ ] Update `dispatch()` to extract `session_id` from each translated message's metadata and store the most recent one on `self.session_id`
- [ ] Log the captured session ID at DEBUG level: `"SDKExecutionSession: session_id=%s"`

**Test T2** — `tests/pipeline/test_sdk_session.py`

- [ ] Add test: `SDKExecutionSession.dispatch()` captures `session_id` from a mocked `ResultMessage` response — after dispatch, `session.session_id` equals the mocked value
- [ ] Add test: session_id is updated on subsequent dispatches (latest wins)

**Commit:** `feat: add session_id and options to SDKExecutionSession`

---

### T3 — Update `_run_pipeline_sdk` to pass options to session

- [ ] In `src/squadron/cli/commands/run.py`, update `_run_pipeline_sdk` to pass `options` when constructing `SDKExecutionSession`:
  ```python
  options = claude_agent_sdk.ClaudeAgentOptions(cwd=str(Path.cwd()))
  client = claude_agent_sdk.ClaudeSDKClient(options=options)
  session = SDKExecutionSession(client=client, options=options)
  ```
- [ ] Verify any other construction sites in the codebase are updated (grep for `SDKExecutionSession(`)

**Test T3** — `tests/cli/commands/test_run_pipeline.py` and `tests/pipeline/test_sdk_wiring.py`

- [ ] Update existing tests that mock `SDKExecutionSession` to account for the new required `options` argument (or verify that tests patch the constructor in a way that's unaffected)
- [ ] All prior SDK tests still pass

**Commit:** `feat: pass ClaudeAgentOptions into SDKExecutionSession`

---

### T4 — Implement `SDKExecutionSession.compact()` method

- [ ] In `src/squadron/pipeline/sdk_session.py`, add a new async method:
  ```python
  async def compact(
      self,
      instructions: str,
      summary_model: str | None = None,
      restore_model: str | None = None,
  ) -> str:
      """Perform session-rotate compaction. Returns the summary text."""
  ```
- [ ] Implementation order inside the method:
  1. If `summary_model` provided and different from current, `await self.set_model(summary_model)`
  2. `summary = await self.dispatch(instructions)` — query live session with compact template
  3. `await self.disconnect()` — close old conversation
  4. Import `ClaudeSDKClient` locally and create a new client using `self.options`
  5. Replace `self.client = new_client`
  6. Reset `self.current_model = None` and `self.session_id = None`
  7. `await self.connect()` — this also re-applies `bypassPermissions`
  8. `await self.dispatch(summary)` — seed new session with the summary text (discard response, it's just the model acknowledging)
  9. If `restore_model` provided, `await self.set_model(restore_model)`
  10. Return `summary`
- [ ] Log each major step at DEBUG level (model switch, dispatch sent, summary length, disconnect, new connect, summary injected, model restored)
- [ ] Error handling: allow exceptions to propagate — the compact action catches them and returns `ActionResult(success=False)`

**Test T4** — `tests/pipeline/test_sdk_session.py`

- [ ] Add test class `TestCompactSessionRotate`
- [ ] Test: `compact()` with `summary_model=None` skips the initial set_model call
- [ ] Test: `compact()` with `summary_model="haiku-id"` calls `set_model("haiku-id")` before dispatch
- [ ] Test: `compact()` dispatches the instructions, captures the response as summary, and returns it
- [ ] Test: `compact()` calls `disconnect()` on the old client and creates a new `ClaudeSDKClient`
- [ ] Test: after `compact()`, `self.client` is the new client and `self.current_model` matches `restore_model`
- [ ] Test: `compact()` with `restore_model="sonnet-id"` calls `set_model("sonnet-id")` at the end
- [ ] Use `patch("squadron.pipeline.sdk_session.ClaudeSDKClient")` to intercept client creation
- [ ] Mock `set_model`, `dispatch`, `connect`, `disconnect` on the session or underlying client as needed

**Commit:** `feat: add SDKExecutionSession.compact() session rotate method`

---

### T5 — Remove `configure_compaction()` stub and `_compaction_config`

- [ ] In `src/squadron/pipeline/sdk_session.py`, delete:
  - The `_compaction_config` field
  - The `configure_compaction()` method
  - The import of `field` from `dataclasses` if no longer needed
- [ ] Verify no other code references `configure_compaction` or `_compaction_config` (grep first)

**Test T5** — `tests/pipeline/test_sdk_session.py`

- [ ] Delete any tests that exercised `configure_compaction()` directly
- [ ] Run the full `test_sdk_session.py` file to confirm no references remain

**Commit:** `refactor: remove configure_compaction stub from SDKExecutionSession`

---

### T6 — Add `model` field to compact step YAML and step validator

- [ ] In `src/squadron/pipeline/steps/compact.py`, update the step's `validate()` method to check for an optional `model` field:
  - Allow `None`, must be `str` if present
  - Add a `ValidationError` with field `"model"` if type is wrong
- [ ] In the step's `expand()` method, pass the `model` field through to the compact action config:
  ```python
  action_config = {"template": template, "model": cfg.get("model"), ...}
  ```
- [ ] Ensure `validate_pipeline` in `loader.py` picks up the compact step's model for alias validation — verify the existing `_validate_model_alias` loop covers compact step config (it iterates over all steps and checks `step.config.get("model")`, so this should work automatically)

**Test T6** — `tests/pipeline/steps/test_compact.py`

- [ ] Add test: compact step with `model: haiku` validates successfully
- [ ] Add test: compact step with `model: 42` (non-string) produces a `ValidationError` on field `"model"`
- [ ] Add test: compact step without `model` validates successfully (field is optional)
- [ ] Add test: `expand()` includes `model` in the action config when present
- [ ] Add test: `expand()` produces `model: None` in the action config when absent

**Commit:** `feat: add optional model field to compact step`

---

### T7 — Wire compact action to call `SDKExecutionSession.compact()`

- [ ] In `src/squadron/pipeline/actions/compact.py`, update the SDK-mode branch of `execute()`:
  - Remove the `configure_compaction()` call
  - Resolve the summary model if `context.params.get("model")` is set: use `context.resolver.resolve(action_model=model, step_model=None)` to get `model_id`
  - Capture the current model before compact for potential restore: `restore_model = context.sdk_session.current_model`
  - Call `summary = await context.sdk_session.compact(instructions=instructions, summary_model=model_id, restore_model=restore_model)`
  - Return `ActionResult(success=True, outputs={"summary": summary, "instructions": instructions}, metadata={"summary_model": model_id or ""})`
- [ ] Wrap in `try/except` to catch provider/SDK errors and return `ActionResult(success=False, error=str(exc))`
- [ ] Update the compact action's `validate()` to accept `model` as an optional string field (mirror the pattern from T6)

**Test T7** — `tests/pipeline/actions/test_compact.py` and `tests/pipeline/actions/test_compact_sdk.py`

- [ ] Update existing SDK tests that used `configure_compaction()` to verify `compact()` is called instead
- [ ] Test: SDK-mode compact with `model: "haiku"` calls `resolver.resolve("haiku", None)` and passes the resolved model_id as `summary_model`
- [ ] Test: SDK-mode compact without `model` passes `summary_model=None`
- [ ] Test: SDK-mode compact captures `current_model` before invoking `compact()` and passes it as `restore_model`
- [ ] Test: successful compact returns `ActionResult(success=True)` with `summary` and `instructions` in outputs
- [ ] Test: exception from `session.compact()` returns `ActionResult(success=False)` with the error message
- [ ] Test: non-SDK-mode compact path (no `sdk_session`) still uses CF compaction — unchanged

**Commit:** `feat: wire compact action to session rotate compaction`

---

### T8 — Wire `PreCompact` hook in `_run_pipeline_sdk`

- [ ] In `src/squadron/cli/commands/run.py`, before constructing `ClaudeAgentOptions`, resolve the compact instructions that should be injected on auto/manual compaction:
  - Find any compact steps in the loaded `definition.steps`
  - For the first compact step (typical case), load its template and render instructions with `params`
  - If no compact steps, skip hook registration
- [ ] Define a local async hook function:
  ```python
  async def _pre_compact_hook(
      hook_input: PreCompactHookInput,
      tool_use_id: str | None,
      context: HookContext,
  ) -> dict[str, object]:
      return {"hookSpecificOutput": {"hookEventName": "PreCompact", "additionalContext": rendered_instructions}}
  ```
  — **Note:** verify the exact return format for `PreCompactHookInput` by checking the `claude_agent_sdk` types; the task author should confirm via a small investigation before implementing. If the correct field is `custom_instructions`, use that instead.
- [ ] Register the hook in `ClaudeAgentOptions.hooks`:
  ```python
  hooks={
      "PreCompact": [
          claude_agent_sdk.HookMatcher(matcher=None, hooks=[_pre_compact_hook])
      ]
  }
  ```
- [ ] Only register the hook when compact instructions were successfully resolved; pass empty/no hook dict otherwise

**Test T8** — `tests/cli/commands/test_run_pipeline.py`

- [ ] Add test: `_run_pipeline_sdk` with a pipeline containing a compact step constructs `ClaudeAgentOptions` with a `PreCompact` hook registered
- [ ] Add test: `_run_pipeline_sdk` with a pipeline containing no compact steps does not register the hook
- [ ] Add test: the hook function, when called with a mock `PreCompactHookInput`, returns a dict containing the rendered compact instructions

**Commit:** `feat: wire PreCompact hook for interactive compact instruction injection`

---

### T9 — End-to-end smoke test with test-pipeline

- [ ] Verify `src/squadron/data/pipelines/test-pipeline.yaml` includes a compact step (it does, per the current file)
- [ ] Add `model: haiku` to the compact step in `test-pipeline.yaml` to exercise the summary-model path
- [ ] Manual verification (not automated): run `uv run sq run test-pipeline 154 -vv` from a standard terminal
  - Expected: compact step logs model switch to haiku, dispatches instructions, captures summary, disconnects, reconnects, injects summary, restores model
  - Expected: subsequent dispatch steps succeed with the new session
  - This task is a verification checklist item — no automated test is added here
- [ ] Document the expected log lines in DEVLOG when complete

**Commit:** `test: add model field to test-pipeline compact step`

---

### T10 — Lint, type-check, and full test suite

- [ ] Run `uv run ruff check src/ tests/` — zero errors
- [ ] Run `uv run ruff format src/ tests/` — no reformatting needed on changed files
- [ ] Run `uv run pyright src/squadron/pipeline/sdk_session.py src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/compact.py src/squadron/cli/commands/run.py src/squadron/providers/sdk/translation.py` — zero errors, zero warnings
- [ ] Run `uv run pytest -q` — all tests pass

**Commit:** `chore: lint and verify slice 157 session management and compaction`

---

### T11 — Slice closeout

- [ ] Mark all T1–T10 tasks complete in this file
- [ ] Set `status: complete` and update `dateUpdated` in this task file's frontmatter
- [ ] Set `status: complete` and update `dateUpdated` in `157-slice.sdk-session-management-and-compaction.md`
- [ ] In `140-slices.pipeline-foundation.md`, check off slice 157 and update `dateUpdated`
- [ ] Add DEVLOG entry summarizing the implementation per `prompt.ai-project.system.md` Session State Summary format
- [ ] Add CHANGELOG entry under `### Added` for session rotate compaction and under `### Fixed` for the removed stub
- [ ] Final commit

**Commit:** `docs: mark slice 157 SDK session management and compaction complete`

---

## Notes

- **PreCompact hook return format uncertainty (T8)**: The exact return schema for `PreCompactHookInput` hooks should be verified against the `claude_agent_sdk.types` module before implementation. The task includes a note to do this first. If the SDK expects a different field name or nesting, adjust accordingly — the design intent is to inject the rendered compact instructions.
- **Summary injection seeding (T4)**: The new session receives the summary as the first user message via `dispatch()`. The response to this seeding dispatch is typically a brief acknowledgment from the model; we discard it but it establishes the summary as the conversation's starting context. If this proves unreliable (model treats the summary as a task to execute rather than context), consider using a system prompt prefix instead — this is a fallback for implementation discovery, not the default approach.
- **Client recreation uses stored options (T4)**: The `options` stored on the session must remain consistent across rotations. Any future changes to `ClaudeAgentOptions` at runtime (e.g., permission mode) should be re-applied after reconnect. The current design re-applies `bypassPermissions` in `connect()` which handles the current scope.
