---
docType: tasks
slice: dispatch-action
project: squadron
lld: user/slices/145-slice.dispatch-action.md
dependencies: [142]
projectState: Pipeline scaffolding complete (slice 142). Action protocol, registries, and stub modules in place. Utility actions operational (slice 144). Agent registry and provider system from slices 102/128.
dateCreated: 20260331
dateUpdated: 20260331
status: complete
---

## Context Summary

- Working on slice 145 (Dispatch Action) — the pipeline's interface to language models
- Single action: `DispatchAction` in `src/squadron/pipeline/actions/dispatch.py` (stub exists)
- Resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent, sends prompt, captures response
- Includes minor refactor: extract `_ensure_provider_loaded` from `review_client.py` to shared `providers/loader.py`
- Tests mock all external boundaries (no real API calls)
- Next slices: 146 (Review and Checkpoint Actions), 147 (Step Types) — both depend on dispatch

---

## Tasks

### T1 — Extract Provider Loader to Shared Module

- [x] **Extract `_ensure_provider_loaded` from `src/squadron/review/review_client.py` to `src/squadron/providers/loader.py`**
  - [x] Create `src/squadron/providers/loader.py` with:
    - `_PROVIDER_MODULES` dict (moved from `review_client.py`)
    - `ensure_provider_loaded(provider_type: str) -> None` (public, renamed from private)
    - Same logic: `importlib.import_module(f"squadron.providers.{module_name}")`, swallow `ImportError`
  - [x] Update `src/squadron/review/review_client.py`:
    - Remove `_PROVIDER_MODULES` dict and `_ensure_provider_loaded` function
    - Import `ensure_provider_loaded` from `squadron.providers.loader`
    - Replace `_ensure_provider_loaded(...)` call with `ensure_provider_loaded(...)`
  - [x] Ensure `from __future__ import annotations` is present in new file
  - [x] Verify all existing tests pass (`python -m pytest --tb=short -q`)
  - [x] pyright clean on both `providers/loader.py` and `review/review_client.py`

**Commit**: `refactor: extract provider loader to shared module`

---

### T2 — Provider Loader: Tests

- [x] **Create tests at `tests/providers/test_loader.py`**
  - [x] Create `tests/providers/__init__.py` if it doesn't exist
  - [x] Test `ensure_provider_loaded` with a known provider type (mock `importlib.import_module`)
  - [x] Test `ensure_provider_loaded` with unknown provider type falls back to type as module name
  - [x] Test `ensure_provider_loaded` swallows `ImportError` silently
  - [x] Test `_PROVIDER_MODULES` contains expected entries (`openai`, `sdk`, `openai-oauth`)
  - [x] All tests pass

**Commit**: `test: add provider loader unit tests`

---

### T3 — DispatchAction: Implementation

- [x] **Implement `DispatchAction` in `src/squadron/pipeline/actions/dispatch.py`**
  - [x] Implement `DispatchAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.DISPATCH` value (`"dispatch"`)
    - `validate(config)` checks:
      - `"prompt"` key present in config
      - Returns `ValidationError(field="prompt", message="...", action_type="dispatch")` if missing
      - Returns empty list for valid config
    - `execute(context)` implementation:
      - **Model resolution**: extract `model` and `step_model` from `context.params`, call `context.resolver.resolve(action_model, step_model)`
      - **Profile resolution**: use explicit `profile` from `context.params` if present, otherwise alias-derived profile, otherwise `ProfileName.SDK`
      - **Agent config**: build `AgentConfig` with resolved model, profile settings (`base_url`, `api_key_env`, `default_headers`), `system_prompt` from params, `cwd` from context
      - **Agent name**: `f"dispatch-{context.step_name}-{context.run_id[:8]}"`
      - **Provider loading**: call `ensure_provider_loaded(profile.provider)` before spawning
      - **Dispatch**: spawn agent via `get_registry().spawn(config)`, send `Message` via `agent.handle_message()`, collect response parts
      - **SDK dedup**: skip messages where `metadata.get("sdk_type") == "result"`
      - **Token metadata**: extract `prompt_tokens`, `completion_tokens`, `total_tokens` from response metadata when present
      - **Shutdown**: always shut down agent in `finally` block via `registry.shutdown_agent(config.name)`
      - **Result**: return `ActionResult(success=True, action_type=self.action_type, outputs={"response": text}, metadata={"model": ..., "profile": ..., **token_metadata})`
  - [x] Error handling — catch all exceptions, return `ActionResult(success=False, action_type=self.action_type, outputs={}, error=str(exc))`:
    - `ModelResolutionError` / `ModelPoolNotImplemented` from resolver
    - `KeyError` from `get_profile()` or `get_provider()`
    - Any exception from `agent.handle_message()`
    - Agent shutdown must still execute (use `try/finally`)
  - [x] Add module-level auto-registration: `register_action(ActionType.DISPATCH, DispatchAction())`
  - [x] Ensure `from __future__ import annotations` is present

**Commit**: `feat: implement DispatchAction for pipeline model dispatch`

---

### T4 — DispatchAction: Tests

- [x] **Create tests at `tests/pipeline/actions/test_dispatch.py`**
  - [x] Test `action_type` property returns `"dispatch"`
  - [x] Test `isinstance(DispatchAction(), Action)` (protocol compliance)
  - [x] Test `validate()` — missing `prompt` key returns error with `field="prompt"`
  - [x] Test `validate()` — config with `prompt` present returns empty list
  - [x] Test `execute()` — happy path: prompt dispatched, response captured in `outputs["response"]`
  - [x] Test `execute()` — model resolution: `resolver.resolve()` called with `action_model` and `step_model` from params
  - [x] Test `execute()` — profile from alias: when resolver returns `(model_id, "openrouter")`, profile is `"openrouter"`
  - [x] Test `execute()` — profile override: explicit `profile` in params takes precedence over alias-derived profile
  - [x] Test `execute()` — default profile: when no alias profile and no explicit profile, defaults to `ProfileName.SDK`
  - [x] Test `execute()` — system prompt passed as `instructions` in AgentConfig
  - [x] Test `execute()` — SDK dedup: messages with `sdk_type="result"` are filtered out
  - [x] Test `execute()` — token metadata: `prompt_tokens`/`completion_tokens` extracted from response metadata into `ActionResult.metadata`
  - [x] Test `execute()` — token metadata absent: result metadata still has `model` and `profile` but no token keys
  - [x] Test `execute()` — agent shutdown always called (even on error)
  - [x] Test `execute()` — `ModelResolutionError` returns `success=False` with error message
  - [x] Test `execute()` — `KeyError` from `get_profile()` returns `success=False` with error message
  - [x] Test `execute()` — agent `handle_message()` exception returns `success=False`, agent still shut down
  - [x] Mock boundaries: `ModelResolver`, `get_registry()`, `get_profile()`, `ensure_provider_loaded()`, `Agent.handle_message()`, `Agent.shutdown()`
  - [x] All tests pass, pyright clean on the action module

**Commit**: `test: add DispatchAction unit tests`

---

### T5 — Action Registration and Integration Verification

- [x] **Verify dispatch registers correctly alongside existing actions**
  - [x] Update `tests/pipeline/actions/test_registry_integration.py`:
    - Add import for `squadron.pipeline.actions.dispatch`
    - Add test: `"dispatch"` appears in `list_actions()`
    - Add test: `get_action("dispatch")` returns a `DispatchAction` instance
  - [x] Confirm no import errors or circular dependencies
  - [x] All existing tests still pass (`python -m pytest --tb=short -q`)

**Commit**: `test: add dispatch to action registry integration tests`

---

### T6 — Full Verification and Closeout

- [x] **Run full verification suite**
  - [x] `python -m pytest --tb=short -q` — all tests pass
  - [x] `pyright src/squadron/pipeline/actions/dispatch.py` — 0 errors
  - [x] `pyright src/squadron/providers/loader.py` — 0 errors
  - [x] `ruff check src/squadron/pipeline/actions/dispatch.py` — 0 warnings
  - [x] `ruff check src/squadron/providers/loader.py` — 0 warnings
  - [x] `ruff format --check src/squadron/pipeline/actions/ src/squadron/providers/loader.py` — no formatting issues
  - [x] Run the verification walkthrough from the slice design document
  - [x] Update slice design verification walkthrough with actual commands and output
  - [x] Check off success criteria in slice design
  - [x] Mark slice 145 as complete in slice design frontmatter
  - [x] Mark slice 145 as complete in slice plan (`140-slices.pipeline-foundation.md`)
  - [x] Update CHANGELOG.md with slice 145 entries
  - [x] Update DEVLOG.md with implementation completion entry

**Commit**: `docs: mark slice 145 dispatch action complete`
