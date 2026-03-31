---
docType: tasks
slice: utility-actions
project: squadron
lld: user/slices/144-slice.utility-actions.md
dependencies: [142]
projectState: Pipeline scaffolding complete (slice 142). Action protocol, registries, and stub modules in place. ContextForgeClient available from slice 126.
dateCreated: 20260331
dateUpdated: 20260331
status: not_started
---

## Context Summary

- Working on slice 144 (Utility Actions) — first concrete action implementations
- Three actions: `CfOpAction`, `CommitAction`, `DevlogAction`
- Each wraps existing I/O (CF CLI, git, file system) behind the `Action` protocol from slice 142
- Stub files already exist at `src/squadron/pipeline/actions/{cf_op,commit,devlog}.py`
- Actions auto-register in the action registry at import time
- Tests mock I/O boundaries; no network or real CF calls
- Next slice: 145 (Dispatch Action) or 147 (Step Types) — both depend on these actions

---

## Tasks

### T1 — CfOpAction: Implementation

- [ ] **Implement `CfOpAction` in `src/squadron/pipeline/actions/cf_op.py`**
  - [ ] Define `CfOperation` StrEnum with members: `SET_PHASE`, `BUILD_CONTEXT`, `SUMMARIZE`
  - [ ] Implement `CfOpAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.CF_OP` value (`"cf-op"`)
    - `validate(config)` checks:
      - `"operation"` key present and is a valid `CfOperation` value
      - For `SET_PHASE`: `"phase"` key must be present
      - Returns `ValidationError` list for any failures
    - `execute(context)` implementation:
      - Extract `operation` from `context.params` (the step config passed via params)
      - Cast `context.cf_client` to `ContextForgeClient`
      - Route to the correct CF CLI command:
        - `SET_PHASE` → `cf_client._run(["set", "phase", str(phase)])`
        - `BUILD_CONTEXT` → `cf_client._run(["build"])`
        - `SUMMARIZE` → `cf_client._run(["summarize"])`
      - Return `ActionResult` with `success=True`, `outputs={"stdout": ..., "operation": ...}`
      - On `ContextForgeError`: return `ActionResult` with `success=False`, `error=str(exc)`
  - [ ] Add module-level auto-registration: `register_action(ActionType.CF_OP, CfOpAction())`
  - [ ] Ensure `from __future__ import annotations` is present

**Commit**: `feat: implement CfOpAction for pipeline CF operations`

---

### T2 — CfOpAction: Tests

- [ ] **Create tests at `tests/pipeline/actions/test_cf_op.py`**
  - [ ] Create `tests/pipeline/actions/__init__.py` if it doesn't exist
  - [ ] Test `action_type` property returns `"cf-op"`
  - [ ] Test `isinstance(CfOpAction(), Action)` (protocol compliance)
  - [ ] Test `validate()` — missing `operation` key returns error
  - [ ] Test `validate()` — invalid operation value returns error
  - [ ] Test `validate()` — `SET_PHASE` without `phase` returns error
  - [ ] Test `validate()` — valid config returns empty list
  - [ ] Test `execute()` — `SET_PHASE` calls `cf_client._run(["set", "phase", "4"])`
  - [ ] Test `execute()` — `BUILD_CONTEXT` calls `cf_client._run(["build"])`
  - [ ] Test `execute()` — `SUMMARIZE` calls `cf_client._run(["summarize"])`
  - [ ] Test `execute()` — returns `success=True` with stdout in outputs
  - [ ] Test `execute()` — `ContextForgeError` returns `success=False` with error message
  - [ ] Mock `ContextForgeClient` — never call real CF CLI
  - [ ] All tests pass, pyright clean on the action module

**Commit**: `test: add CfOpAction unit tests`

---

### T3 — CommitAction: Implementation

- [ ] **Implement `CommitAction` in `src/squadron/pipeline/actions/commit.py`**
  - [ ] Implement `CommitAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.COMMIT` value (`"commit"`)
    - `validate(config)` checks:
      - `cwd` is provided (from context, not config — but validate config structure is reasonable)
      - Returns `ValidationError` for structural issues
    - `execute(context)` implementation:
      - Use `context.cwd` as working directory for all git commands
      - Run `git status --porcelain` to check for changes
      - If no changes: return `ActionResult(success=True, outputs={"committed": False})`
      - Stage files: if `paths` in params, `git add {paths}`; otherwise `git add -A`
      - Build commit message:
        - Use `message` from params if provided
        - Otherwise auto-generate: `"{type}: {step_name} for {pipeline_name}"` where `type` comes from params or defaults to `"chore"`
      - Run `git commit -m "{message}"`
      - Extract commit SHA from `git rev-parse HEAD`
      - Return `ActionResult(success=True, outputs={"committed": True, "sha": ..., "message": ...})`
      - On subprocess failure: return `ActionResult(success=False, error=stderr)`
  - [ ] Use `subprocess.run()` with `capture_output=True, text=True, cwd=context.cwd`
  - [ ] Add module-level auto-registration: `register_action(ActionType.COMMIT, CommitAction())`

**Commit**: `feat: implement CommitAction for pipeline git commits`

---

### T4 — CommitAction: Tests

- [ ] **Create tests at `tests/pipeline/actions/test_commit.py`**
  - [ ] Test `action_type` property returns `"commit"`
  - [ ] Test `isinstance(CommitAction(), Action)` (protocol compliance)
  - [ ] Test `execute()` — no changes returns `committed=False`, `success=True`
  - [ ] Test `execute()` — creates commit when changes exist (use `tmp_path` with `git init`)
  - [ ] Test `execute()` — commit message from params used verbatim
  - [ ] Test `execute()` — auto-generated message when no `message` param
  - [ ] Test `execute()` — `paths` param scopes staging to specific files
  - [ ] Test `execute()` — returns SHA in outputs
  - [ ] Test `execute()` — git failure returns `success=False` with error
  - [ ] Use `tmp_path` fixture with real `git init` for integration-style tests (no network)
  - [ ] All tests pass, pyright clean on the action module

**Commit**: `test: add CommitAction unit tests`

---

### T5 — DevlogAction: Implementation

- [ ] **Implement `DevlogAction` in `src/squadron/pipeline/actions/devlog.py`**
  - [ ] Implement `DevlogAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.DEVLOG` value (`"devlog"`)
    - `validate(config)` — minimal validation; returns empty list (devlog is always valid)
    - `execute(context)` implementation:
      - Determine DEVLOG path: `params.get("path")` or `Path(context.cwd) / "DEVLOG.md"`
      - Determine entry content:
        - If `content` in params: use verbatim
        - Otherwise auto-generate from `context.prior_outputs`:
          - Extract step names and their success/failure status
          - Extract review verdicts from steps that produced them
          - Format as: `**{title}**\n{summary}`
          - Title from params or auto-generate from `context.pipeline_name` and `context.step_name`
      - Determine today's date header: `## YYYYMMDD`
      - Read existing DEVLOG.md (create minimal file if absent)
      - Find insertion point:
        - After frontmatter (`---` pairs) and header
        - If today's date header exists: insert after it
        - Otherwise: insert new date header before first existing `## YYYYMMDD` entry
      - Write updated file
      - Return `ActionResult(success=True, outputs={"path": str, "entry": str})`
      - On I/O error: return `ActionResult(success=False, error=str(exc))`
  - [ ] Add module-level auto-registration: `register_action(ActionType.DEVLOG, DevlogAction())`

**Commit**: `feat: implement DevlogAction for pipeline DEVLOG entries`

---

### T6 — DevlogAction: Tests

- [ ] **Create tests at `tests/pipeline/actions/test_devlog.py`**
  - [ ] Test `action_type` property returns `"devlog"`
  - [ ] Test `isinstance(DevlogAction(), Action)` (protocol compliance)
  - [ ] Test `execute()` — explicit content written to DEVLOG.md
  - [ ] Test `execute()` — auto-generated content from prior_outputs
  - [ ] Test `execute()` — creates DEVLOG.md if it doesn't exist
  - [ ] Test `execute()` — inserts under existing today's date header (no duplicate)
  - [ ] Test `execute()` — creates new date header when today's date not present
  - [ ] Test `execute()` — preserves existing DEVLOG content (no data loss)
  - [ ] Test `execute()` — custom `path` param overrides default location
  - [ ] Test `execute()` — returns path and entry text in outputs
  - [ ] Use `tmp_path` fixture with sample DEVLOG.md files
  - [ ] All tests pass, pyright clean on the action module

**Commit**: `test: add DevlogAction unit tests`

---

### T7 — Action Registration and Integration Verification

- [ ] **Verify all three actions register correctly and coexist in the registry**
  - [ ] Ensure importing `squadron.pipeline.actions.cf_op`, `commit`, `devlog` populates the registry
  - [ ] Verify `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`
  - [ ] Verify `get_action("cf-op")` returns a `CfOpAction` instance
  - [ ] Verify `get_action("commit")` returns a `CommitAction` instance
  - [ ] Verify `get_action("devlog")` returns a `DevlogAction` instance
  - [ ] Add these as tests in `tests/pipeline/actions/test_registry_integration.py`
  - [ ] Confirm no import errors or circular dependencies
  - [ ] All existing tests still pass (`python -m pytest --tb=short -q`)

**Commit**: `test: add action registry integration tests`

---

### T8 — Full Verification and Closeout

- [ ] **Run full verification suite**
  - [ ] `python -m pytest --tb=short -q` — all tests pass
  - [ ] `pyright src/squadron/pipeline/actions/` — 0 errors
  - [ ] `ruff check src/squadron/pipeline/actions/` — 0 warnings
  - [ ] `ruff format --check src/squadron/pipeline/actions/` — no formatting issues
  - [ ] Run the verification walkthrough from the slice design document
  - [ ] Update slice design verification walkthrough with actual commands and output
  - [ ] Check off success criteria in slice design
  - [ ] Mark slice 144 as complete in slice design frontmatter
  - [ ] Mark slice 144 as complete in slice plan (`140-slices.pipeline-foundation.md`)
  - [ ] Update CHANGELOG.md with slice 144 entries
  - [ ] Update DEVLOG.md with implementation completion entry

**Commit**: `docs: mark slice 144 utility actions complete`
