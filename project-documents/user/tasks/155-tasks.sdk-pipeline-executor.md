---
docType: tasks
slice: sdk-pipeline-executor
project: squadron
lld: user/slices/155-slice.sdk-pipeline-executor.md
dependencies: [154-prompt-only-loops]
projectState: Pipeline foundation complete (140). Prompt-only executor (153) complete and verified. SDK provider and ClaudeSDKClient already in use for reviews.
dateCreated: 20260404
dateUpdated: 20260404
status: not_started
---

## Context Summary

- Working on slice 155: SDK Pipeline Executor
- Adds fully automated pipeline execution via `ClaudeSDKClient` with persistent session, per-step model switching (`set_model()`), and server-side compaction (`context_management` API)
- Runs from straight CLI only — outside Claude Code sessions
- Existing dispatch action, compact action, executor, and SDK agent are all reusable; changes are additive
- Dependencies: slice 154 (prompt-only loops) for `each` loop support in prompt-only mode
- Next: slice 152 (pipeline documentation)

---

## Tasks

### T1: SDK Execution Session — Core Module

- [ ] **Create `src/squadron/pipeline/sdk_session.py` with `SDKExecutionSession` dataclass**
  - [ ] Fields: `client: ClaudeSDKClient`, `current_model: str | None`, `_compaction_config: dict | None`
  - [ ] `async def connect()` — call `self.client.connect()`
  - [ ] `async def disconnect()` — call `self.client.disconnect()` with best-effort cleanup
  - [ ] `async def set_model(model_alias: str)` — skip if `model_alias == self.current_model`, otherwise call `self.client.set_model(model_alias)` and update `current_model`
  - [ ] `async def dispatch(prompt: str) -> str` — call `self.client.query(prompt)`, collect response from `self.client.receive_response()`, return joined text
  - [ ] `async def configure_compaction(instructions: str, trigger_tokens: int, pause_after: bool)` — store config dict for next dispatch
  - [ ] Rate-limit retry logic: reuse pattern from existing `ClaudeSDKAgent._handle_client_mode()` (retry on `rate_limit_event` up to max retries)
  - [ ] Add module to `squadron/pipeline/__init__.py` exports
  - [ ] Success: module imports cleanly, all public methods have type hints

### T2: SDK Execution Session — Unit Tests

- [ ] **Create `tests/pipeline/test_sdk_session.py`**
  - [ ] Test `connect()` calls `client.connect()`
  - [ ] Test `disconnect()` calls `client.disconnect()`, handles exception gracefully
  - [ ] Test `set_model()` calls `client.set_model()` when model differs from current
  - [ ] Test `set_model()` skips call when model matches current
  - [ ] Test `dispatch()` sends query and collects response
  - [ ] Test `configure_compaction()` stores config
  - [ ] Test rate-limit retry on `ClaudeSDKError` with `rate_limit_event`
  - [ ] All tests use `AsyncMock` for `ClaudeSDKClient` — no real SDK calls
  - [ ] Success: all tests pass, `pytest tests/pipeline/test_sdk_session.py` green

### T3: Commit — SDK session module and tests

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `feat: add SDKExecutionSession for persistent pipeline client`

### T4: ActionContext Extension

- [ ] **Add `sdk_session` field to `ActionContext` in `src/squadron/pipeline/models.py`**
  - [ ] Add `sdk_session: SDKExecutionSession | None = None` field
  - [ ] Use `TYPE_CHECKING` import to avoid circular dependency
  - [ ] Success: existing tests still pass (field defaults to `None`), `pyright` clean

### T5: Dispatch Action — Session Path

- [ ] **Extend `src/squadron/pipeline/actions/dispatch.py` with SDK session dispatch**
  - [ ] Rename existing `_dispatch()` to `_dispatch_via_agent()` (no behavior change)
  - [ ] Add `_dispatch_via_session(context, session)` method:
    - Resolve model via cascade chain (existing `context.resolver.resolve()`)
    - Call `session.set_model(resolved_model_alias)` — use the alias, not the resolved ID
    - Build prompt from `context.params["prompt"]`
    - Call `session.dispatch(prompt)` and capture response
    - Return `ActionResult` with response text and model metadata
  - [ ] Add routing in `_dispatch()`: check `context.sdk_session`, delegate to session path or agent path
  - [ ] Success: existing dispatch tests still pass (sdk_session is None → agent path)

### T6: Dispatch Action — Session Path Tests

- [ ] **Add tests for session dispatch path in `tests/pipeline/test_dispatch_session.py`**
  - [ ] Test session dispatch calls `session.set_model()` with resolved alias
  - [ ] Test session dispatch calls `session.dispatch()` with prompt
  - [ ] Test session dispatch returns `ActionResult` with response and model metadata
  - [ ] Test routing: `sdk_session=None` routes to agent path
  - [ ] Test routing: `sdk_session` present routes to session path
  - [ ] Test error handling: session dispatch failure returns `ActionResult(success=False)`
  - [ ] Mock `SDKExecutionSession` — no real SDK calls
  - [ ] Success: all tests pass

### T7: Commit — Dispatch action session path

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `feat: add SDK session dispatch path to dispatch action`

### T8: Compact Action — SDK Compaction Path

- [ ] **Extend `src/squadron/pipeline/actions/compact.py` with SDK compaction**
  - [ ] In `execute()`, check `context.sdk_session` for SDK mode
  - [ ] SDK path: resolve template and render instructions (existing logic)
  - [ ] Call `session.configure_compaction(instructions=resolved, trigger_tokens=50_000, pause_after=True)`
  - [ ] Return `ActionResult(success=True)` with `outputs={"compaction_configured": True, "instructions": resolved}`
  - [ ] Existing CF compaction path unchanged (when `sdk_session` is `None`)
  - [ ] Success: existing compact tests still pass

### T9: Compact Action — SDK Path Tests

- [ ] **Add tests for SDK compaction path in existing compact test file or new `tests/pipeline/test_compact_sdk.py`**
  - [ ] Test SDK path calls `session.configure_compaction()` with rendered instructions
  - [ ] Test SDK path returns success with compaction_configured output
  - [ ] Test non-SDK path (sdk_session=None) still uses CF compaction
  - [ ] Success: all tests pass

### T10: Commit — Compact action SDK path

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `feat: add SDK compaction path to compact action`

### T11: Environment Detection

- [ ] **Add `_resolve_execution_mode()` to `src/squadron/cli/commands/run.py`**
  - [ ] If `--prompt-only` flag: return `"prompt-only"`
  - [ ] If `CLAUDECODE` env var is set: raise clear error message directing user to `--prompt-only` mode
  - [ ] Otherwise: return `"sdk"`
  - [ ] Wire into `run()` command: call before pipeline execution
  - [ ] Success: `sq run` from normal terminal resolves to `"sdk"` mode

### T12: Environment Detection Tests

- [ ] **Add tests for environment detection**
  - [ ] Test `--prompt-only` returns prompt-only mode
  - [ ] Test `CLAUDECODE` env var set raises error with helpful message
  - [ ] Test normal environment returns SDK mode
  - [ ] Use `monkeypatch` for env var manipulation
  - [ ] Success: all tests pass

### T13: Commit — Environment detection

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `feat: add execution mode detection for SDK vs prompt-only`

### T14: CLI Wiring — SDK Executor Entry Point

- [ ] **Wire SDKExecutionSession into the `run()` command in `src/squadron/cli/commands/run.py`**
  - [ ] When execution mode is `"sdk"`:
    - Create `ClaudeAgentOptions` with appropriate settings (cwd, model from pipeline)
    - Create `SDKExecutionSession` with `ClaudeSDKClient(options)`
    - Call `session.connect()`
    - Pass `sdk_session` through to `execute_pipeline()` via action registry or context factory
  - [ ] Ensure session is disconnected in `finally` block (cleanup on success, failure, or interrupt)
  - [ ] Pass session through to `ActionContext` construction in the executor
  - [ ] Success: `sq run test-pipeline 154` from terminal creates session and attempts execution

### T15: Executor — ActionContext Session Propagation

- [ ] **Update executor to propagate `sdk_session` to `ActionContext`**
  - [ ] `execute_pipeline()` accepts optional `sdk_session` parameter
  - [ ] When building `ActionContext` for each action, pass `sdk_session` through
  - [ ] Success: existing tests still pass (sdk_session defaults to None)

### T16: CLI and Executor Wiring Tests

- [ ] **Add tests for SDK executor wiring**
  - [ ] Test `execute_pipeline()` with `sdk_session=None` works as before
  - [ ] Test `execute_pipeline()` with mock `sdk_session` propagates to action contexts
  - [ ] Test CLI cleanup: session disconnect called on success
  - [ ] Test CLI cleanup: session disconnect called on failure
  - [ ] Success: all tests pass

### T17: Commit — CLI wiring and executor propagation

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `feat: wire SDK execution session into CLI and executor`

### T18: Integration Test — Full SDK Pipeline Cycle

- [ ] **Create `tests/pipeline/test_sdk_integration.py`**
  - [ ] Test full pipeline cycle with mock `SDKExecutionSession`:
    - Load real `test-pipeline` definition
    - Mock session: `set_model()`, `dispatch()`, `configure_compaction()` all succeed
    - Mock review action returns PASS verdict
    - Verify all steps complete
    - Verify `set_model()` called with correct aliases per step
    - Verify `configure_compaction()` called at compact step
  - [ ] Test checkpoint triggers session disconnect and state persistence
  - [ ] Test resume after checkpoint creates new session and continues
  - [ ] Success: all integration tests pass

### T19: Commit — Integration tests

- [ ] **Commit checkpoint**
  - [ ] `ruff format` and `ruff check`
  - [ ] All tests pass
  - [ ] Commit: `test: add SDK pipeline executor integration tests`

### T20: Lint, Verify, and Closeout

- [ ] **Final verification pass**
  - [ ] `ruff format` across all changed files
  - [ ] `ruff check` clean
  - [ ] `pyright` or type checking clean
  - [ ] Full test suite passes: `pytest tests/`
  - [ ] No regressions in existing prompt-only or executor tests
  - [ ] Update slice design status to `complete`
  - [ ] Update slice plan entry: check off slice 155
  - [ ] Write DEVLOG entry
  - [ ] Commit: `chore: lint and verify SDK pipeline executor`
