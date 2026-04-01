---
docType: review
layer: project
reviewType: code
slice: utility-actions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/144-slice.utility-actions.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260331
dateUpdated: 20260331
---

# Review: code — slice 144

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Validate-execute parameter mismatch in CfOpAction

In `src/squadron/pipeline/actions/cf_op.py`, the `validate()` method checks `config.get("operation")` and `config.get("phase")`, but `execute()` reads from `context.params.get("operation")` and `context.params["phase"]`. If config and params diverge at runtime, validation passes but execution could fail or behave unexpectedly.

**Recommendation:** Consider validating `context.params` directly in `execute()`, or document the expectation that config and params must be consistent.

---

### [CONCERN] Validate-execute parameter mismatch in CommitAction

In `src/squadron/pipeline/actions/commit.py`, `validate()` accepts any config (returns empty list) but `execute()` reads from `context.params.get("paths")` and `context.params.get("message")`. This means validation provides no actual safety guarantee.

**Recommendation:** If validation is intentionally minimal, document this. Otherwise, validate required params exist or warn if `cwd` is not a valid git repository.

---

### [CONCERN] DevlogAction validate uses config flag, not context

In `src/squadron/pipeline/actions/devlog.py`, `validate()` checks `config.get("_has_prior_outputs")` to determine if auto-generation is possible, but `execute()` checks `context.prior_outputs` directly. The test mocks `_has_prior_outputs` in config, but there's no clear mechanism for this flag to be set during normal pipeline operation.

In `tests/pipeline/actions/test_devlog.py`, test `test_validate_warns_no_content_no_prior()` creates a context with `prior_outputs={}` but the `validate()` method checks config, not context:

```python
def test_validate_warns_no_content_no_prior(action: DevlogAction) -> None:
    errors = action.validate({})
    assert len(errors) == 1
```

The actual test verifies config behavior, not context behavior.

**Recommendation:** Consider checking `context.prior_outputs` directly in `validate()` rather than relying on a config flag, or ensure the flag is consistently populated upstream.

---

### [PASS] Phase value not validated in CfOpAction

The `validate()` method checks that `phase` key exists for `SET_PHASE` operation, but does not validate its type or range. The `execute()` method converts with `str(phase)`, which handles both int and string inputs. This is acceptable since phase is passed through to CF CLI which handles validation.

---

### [PASS] Comprehensive test coverage

The test files demonstrate the "test-with" pattern:
- `test_cf_op.py`: 13 tests covering validation paths, all three operations, success/failure cases, and protocol compliance
- `test_commit.py`: 9 tests with real git repos via `tmp_path`, including edge cases (no changes, scoped paths, SHA verification)
- `test_devlog.py`: 12 tests covering explicit/auto-generated content, file creation, header deduplication, and path override
- `test_registry_integration.py`: 5 tests verifying registration and protocol satisfaction

All tests properly mock external dependencies (ContextForgeClient) and use appropriate fixtures.

---

### [PASS] Auto-registration pattern implemented correctly

All three actions use module-level `register_action()` calls that execute at import time, consistent with the provider registry pattern noted in the slice design.

---

### [PASS] Error handling patterns

- `cf_op.py`: Catches `ContextForgeError` and returns `success=False` with error message
- `commit.py`: Returns `None` from `_git()` helper on `OSError`, then checks for None before accessing returncode/stdout
- `devlog.py`: Catches `OSError` on file operations and returns `success=False`

---

### [PASS] pyright ignore comment per project convention

The `pyright: ignore[reportPrivateUsage]` comment is used appropriately in `cf_op.py` for `cf_client._run()` calls, as documented in DEVLOG.md.

---

## Debug: Prompt & Response

### System Prompt

You are a code reviewer. Review code against language-specific rules, testing
standards, and project conventions loaded from CLAUDE.md.

Focus areas:
- Project conventions (from CLAUDE.md)
- Language-appropriate style and correctness
- Test coverage patterns (test-with, not test-after)
- Error handling patterns
- Security concerns
- Naming, structure, and documentation quality

CRITICAL: Your verdict and findings MUST be consistent.
- If verdict is CONCERNS or FAIL, include at least one finding with that severity.
- If no CONCERN or FAIL findings exist, verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title

Report your findings using severity levels:

## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
Description with specific file and line references.


### User Prompt

Review code in the project at: ./project-documents/user

Run `git diff bfef47be5edb1da9c2f881ca47e819326cc9ed14...144-slice.utility-actions` to identify changed files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/CHANGELOG.md b/CHANGELOG.md
index 51df34b..b8326aa 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -13,6 +13,11 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 ## [Unreleased]
 
 ### Added
+- Three utility actions for the pipeline system (slice 144)
+  - `CfOpAction` in `pipeline/actions/cf_op.py` — delegates `set_phase`, `build_context`, `summarize` to ContextForge CLI via `cf_client._run()`
+  - `CommitAction` in `pipeline/actions/commit.py` — stages files and creates git commits with semantic messages; returns `committed=False` on clean working tree
+  - `DevlogAction` in `pipeline/actions/devlog.py` — appends structured entries to DEVLOG.md; auto-generates content from `prior_outputs` or accepts explicit content; handles date header deduplication
+  - All three satisfy the `Action` protocol and auto-register at import time
 - Structured review findings in YAML frontmatter (slice 143)
   - `StructuredFinding` dataclass in `review/models.py` — machine-readable finding with `id`, `severity`, `category`, `summary`, `location`
   - `NOTE` severity level added to `Severity` enum (between PASS and CONCERN)
diff --git a/DEVLOG.md b/DEVLOG.md
index 2466f49..267e4c7 100644
--- a/DEVLOG.md
+++ b/DEVLOG.md
@@ -14,6 +14,9 @@ Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).
 
 ## 20260331
 
+**Slice 144: Utility Actions — Implementation Complete (Phase 6)**
+Implemented all 8 tasks (T1–T8). `CfOpAction` delegates to `cf_client._run()` with `pyright: ignore[reportPrivateUsage]` per project convention. `CommitAction` uses `subprocess.run()` with real `git init` test repos via `tmp_path`. `DevlogAction` handles DEVLOG insertion with date header deduplication and auto-generation from `prior_outputs`. All three actions satisfy `Action` protocol and auto-register at import time. 39 new tests, 800 total pass, pyright 0 errors, ruff clean. Slice 144 marked complete.
+
 **Slice 144: Utility Actions — Task Breakdown Complete (Phase 5)**
 Created `project-documents/user/tasks/144-tasks.utility-actions.md`. 8 tasks (T1–T8): CfOpAction implementation + tests, CommitAction implementation + tests, DevlogAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.
 
diff --git a/project-documents/user/architecture/140-slices.pipeline-foundation.md b/project-documents/user/architecture/140-slices.pipeline-foundation.md
index 2b27ae3..f3e6023 100644
--- a/project-documents/user/architecture/140-slices.pipeline-foundation.md
+++ b/project-documents/user/architecture/140-slices.pipeline-foundation.md
@@ -32,7 +32,7 @@ status: in_progress
 
 ## Feature Slices
 
-5. [ ] **(144) Utility Actions** — Implement three simple actions that validate the action protocol against well-defined operations: cf-op action (set phase, build context, summarize via ContextForgeClient), commit action (git commit at phase boundaries with semantic message conventions), and devlog action (structured DEVLOG entries auto-generated from pipeline state). Dependencies: [142, CF Integration (126)]. Risk: Low. Effort: 2/5
+5. [x] **(144) Utility Actions** — Implement three simple actions that validate the action protocol against well-defined operations: cf-op action (set phase, build context, summarize via ContextForgeClient), commit action (git commit at phase boundaries with semantic message conventions), and devlog action (structured DEVLOG entries auto-generated from pipeline state). Dependencies: [142, CF Integration (126)]. Risk: Low. Effort: 2/5
 
 6. [ ] **(145) Dispatch Action** — Send assembled context to a model via agent registry, capture output (file artifacts or code changes), record metadata (model used, token counts). Integrates with model resolver for alias resolution through the cascade chain. Handles both SDK and API provider dispatch transparently through the AgentProvider protocol. Dependencies: [142, Agent Registry (102)]. Risk: Low. Effort: 2/5
 
diff --git a/project-documents/user/slices/144-slice.utility-actions.md b/project-documents/user/slices/144-slice.utility-actions.md
index 13767c1..f927702 100644
--- a/project-documents/user/slices/144-slice.utility-actions.md
+++ b/project-documents/user/slices/144-slice.utility-actions.md
@@ -9,7 +9,7 @@ dependencies: [142]
 interfaces: [147]
 dateCreated: 20260331
 dateUpdated: 20260331
-status: not_started
+status: complete
 ---
 
 # Slice Design: Utility Actions (144)
@@ -265,60 +265,68 @@ This mirrors the provider registry pattern established in the codebase. Actions
 
 ### Functional
 
-- [ ] `CfOpAction` successfully executes `set_phase`, `build_context`, and `summarize` operations against a mocked `ContextForgeClient`
-- [ ] `CommitAction` creates a git commit with the expected message in a test repository
-- [ ] `CommitAction` returns `committed=False` (not an error) when there are no changes
-- [ ] `DevlogAction` appends an entry to DEVLOG.md at the correct insertion point
-- [ ] `DevlogAction` auto-generates content from `prior_outputs` when no explicit content is provided
-- [ ] Each action's `validate()` method returns errors for missing required config
+- [x] `CfOpAction` successfully executes `set_phase`, `build_context`, and `summarize` operations against a mocked `ContextForgeClient`
+- [x] `CommitAction` creates a git commit with the expected message in a test repository
+- [x] `CommitAction` returns `committed=False` (not an error) when there are no changes
+- [x] `DevlogAction` appends an entry to DEVLOG.md at the correct insertion point
+- [x] `DevlogAction` auto-generates content from `prior_outputs` when no explicit content is provided
+- [x] Each action's `validate()` method returns errors for missing required config
 
 ### Technical
 
-- [ ] All three actions satisfy the `Action` protocol (runtime checkable)
-- [ ] All three actions auto-register in the action registry at import time
-- [ ] `get_action(ActionType.CF_OP)` / `COMMIT` / `DEVLOG` returns the registered instance
-- [ ] Pyright reports 0 errors
-- [ ] Ruff reports 0 warnings
-- [ ] All existing tests continue to pass
+- [x] All three actions satisfy the `Action` protocol (runtime checkable)
+- [x] All three actions auto-register in the action registry at import time
+- [x] `get_action(ActionType.CF_OP)` / `COMMIT` / `DEVLOG` returns the registered instance
+- [x] Pyright reports 0 errors
+- [x] Ruff reports 0 warnings
+- [x] All existing tests continue to pass
 
 ### Integration
 
-- [ ] Action registry contains all three new actions plus any previously registered
-- [ ] `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`
+- [x] Action registry contains all three new actions plus any previously registered
+- [x] `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`
 
 ---
 
 ## Verification Walkthrough
 
-*Draft — to be refined during implementation.*
+*Verified during implementation — 2026-03-31.*
 
 ```bash
-# 1. Run the new tests
+# 1. Run the new tests (13 + 9 + 12 + 5 = 39 tests)
 cd /Users/manta/source/repos/manta/squadron
-python -m pytest tests/pipeline/actions/test_cf_op.py -v
-python -m pytest tests/pipeline/actions/test_commit.py -v
-python -m pytest tests/pipeline/actions/test_devlog.py -v
+python -m pytest tests/pipeline/actions/test_cf_op.py -v          # 13 passed
+python -m pytest tests/pipeline/actions/test_commit.py -v         # 9 passed
+python -m pytest tests/pipeline/actions/test_devlog.py -v         # 12 passed
+python -m pytest tests/pipeline/actions/test_registry_integration.py -v  # 5 passed
 
 # 2. Verify action registration
+# NOTE: Action modules must be explicitly imported to trigger registration.
+# The actions package __init__.py does NOT auto-import them.
+# The executor (slice 149) will import the package to populate the registry.
 python -c "
-from squadron.pipeline.actions import list_actions, get_action, ActionType
+import squadron.pipeline.actions.cf_op
+import squadron.pipeline.actions.commit
+import squadron.pipeline.actions.devlog
+from squadron.pipeline.actions import list_actions, get_action
 actions = list_actions()
 print('Registered actions:', actions)
 assert 'cf-op' in actions
 assert 'commit' in actions
 assert 'devlog' in actions
-# Verify instances satisfy protocol
 from squadron.pipeline.actions.protocol import Action
 for name in ['cf-op', 'commit', 'devlog']:
     a = get_action(name)
     assert isinstance(a, Action), f'{name} does not satisfy Action protocol'
 print('All actions registered and protocol-compliant')
 "
+# Output: Registered actions: ['cf-op', 'commit', 'devlog']
+# Output: All actions registered and protocol-compliant
 
 # 3. Verify no regressions
-python -m pytest --tb=short -q
-pyright src/squadron/pipeline/actions/
-ruff check src/squadron/pipeline/actions/
+python -m pytest --tb=short -q     # 800 passed
+pyright src/squadron/pipeline/actions/  # 0 errors
+ruff check src/squadron/pipeline/actions/  # All checks passed
 ```
 
 ---
diff --git a/project-documents/user/tasks/144-tasks.utility-actions.md b/project-documents/user/tasks/144-tasks.utility-actions.md
index a4c9e33..e975951 100644
--- a/project-documents/user/tasks/144-tasks.utility-actions.md
+++ b/project-documents/user/tasks/144-tasks.utility-actions.md
@@ -7,7 +7,7 @@ dependencies: [142]
 projectState: Pipeline scaffolding complete (slice 142). Action protocol, registries, and stub modules in place. ContextForgeClient available from slice 126.
 dateCreated: 20260331
 dateUpdated: 20260331
-status: not_started
+status: complete
 ---
 
 ## Context Summary
@@ -26,9 +26,9 @@ status: not_started
 
 ### T1 — CfOpAction: Implementation
 
-- [ ] **Implement `CfOpAction` in `src/squadron/pipeline/actions/cf_op.py`**
-  - [ ] Define `CfOperation` StrEnum with members: `SET_PHASE`, `BUILD_CONTEXT`, `SUMMARIZE`
-  - [ ] Implement `CfOpAction` class satisfying the `Action` protocol:
+- [x] **Implement `CfOpAction` in `src/squadron/pipeline/actions/cf_op.py`**
+  - [x] Define `CfOperation` StrEnum with members: `SET_PHASE`, `BUILD_CONTEXT`, `SUMMARIZE`
+  - [x] Implement `CfOpAction` class satisfying the `Action` protocol:
     - `action_type` property returns `ActionType.CF_OP` value (`"cf-op"`)
     - `validate(config)` checks:
       - `"operation"` key present and is a valid `CfOperation` value
@@ -43,8 +43,8 @@ status: not_started
         - `SUMMARIZE` → `cf_client._run(["summarize"])`
       - Return `ActionResult` with `success=True`, `outputs={"stdout": ..., "operation": ...}`
       - On `ContextForgeError`: return `ActionResult` with `success=False`, `error=str(exc)`
-  - [ ] Add module-level auto-registration: `register_action(ActionType.CF_OP, CfOpAction())`
-  - [ ] Ensure `from __future__ import annotations` is present
+  - [x] Add module-level auto-registration: `register_action(ActionType.CF_OP, CfOpAction())`
+  - [x] Ensure `from __future__ import annotations` is present
 
 **Commit**: `feat: implement CfOpAction for pipeline CF operations`
 
@@ -52,21 +52,21 @@ status: not_started
 
 ### T2 — CfOpAction: Tests
 
-- [ ] **Create tests at `tests/pipeline/actions/test_cf_op.py`**
-  - [ ] Create `tests/pipeline/actions/__init__.py` if it doesn't exist
-  - [ ] Test `action_type` property returns `"cf-op"`
-  - [ ] Test `isinstance(CfOpAction(), Action)` (protocol compliance)
-  - [ ] Test `validate()` — missing `operation` key returns error
-  - [ ] Test `validate()` — invalid operation value returns error
-  - [ ] Test `validate()` — `SET_PHASE` without `phase` returns error
-  - [ ] Test `validate()` — valid config returns empty list
-  - [ ] Test `execute()` — `SET_PHASE` calls `cf_client._run(["set", "phase", "4"])`
-  - [ ] Test `execute()` — `BUILD_CONTEXT` calls `cf_client._run(["build"])`
-  - [ ] Test `execute()` — `SUMMARIZE` calls `cf_client._run(["summarize"])`
-  - [ ] Test `execute()` — returns `success=True` with stdout in outputs
-  - [ ] Test `execute()` — `ContextForgeError` returns `success=False` with error message
-  - [ ] Mock `ContextForgeClient` — never call real CF CLI
-  - [ ] All tests pass, pyright clean on the action module
+- [x] **Create tests at `tests/pipeline/actions/test_cf_op.py`**
+  - [x] Create `tests/pipeline/actions/__init__.py` if it doesn't exist
+  - [x] Test `action_type` property returns `"cf-op"`
+  - [x] Test `isinstance(CfOpAction(), Action)` (protocol compliance)
+  - [x] Test `validate()` — missing `operation` key returns error
+  - [x] Test `validate()` — invalid operation value returns error
+  - [x] Test `validate()` — `SET_PHASE` without `phase` returns error
+  - [x] Test `validate()` — valid config returns empty list
+  - [x] Test `execute()` — `SET_PHASE` calls `cf_client._run(["set", "phase", "4"])`
+  - [x] Test `execute()` — `BUILD_CONTEXT` calls `cf_client._run(["build"])`
+  - [x] Test `execute()` — `SUMMARIZE` calls `cf_client._run(["summarize"])`
+  - [x] Test `execute()` — returns `success=True` with stdout in outputs
+  - [x] Test `execute()` — `ContextForgeError` returns `success=False` with error message
+  - [x] Mock `ContextForgeClient` — never call real CF CLI
+  - [x] All tests pass, pyright clean on the action module
 
 **Commit**: `test: add CfOpAction unit tests`
 
@@ -74,8 +74,8 @@ status: not_started
 
 ### T3 — CommitAction: Implementation
 
-- [ ] **Implement `CommitAction` in `src/squadron/pipeline/actions/commit.py`**
-  - [ ] Implement `CommitAction` class satisfying the `Action` protocol:
+- [x] **Implement `CommitAction` in `src/squadron/pipeline/actions/commit.py`**
+  - [x] Implement `CommitAction` class satisfying the `Action` protocol:
     - `action_type` property returns `ActionType.COMMIT` value (`"commit"`)
     - `validate(config)` checks:
       - `cwd` is provided (from context, not config — but validate config structure is reasonable)
@@ -92,8 +92,8 @@ status: not_started
       - Extract commit SHA from `git rev-parse HEAD`
       - Return `ActionResult(success=True, outputs={"committed": True, "sha": ..., "message": ...})`
       - On subprocess failure: return `ActionResult(success=False, error=stderr)`
-  - [ ] Use `subprocess.run()` with `capture_output=True, text=True, cwd=context.cwd`
-  - [ ] Add module-level auto-registration: `register_action(ActionType.COMMIT, CommitAction())`
+  - [x] Use `subprocess.run()` with `capture_output=True, text=True, cwd=context.cwd`
+  - [x] Add module-level auto-registration: `register_action(ActionType.COMMIT, CommitAction())`
 
 **Commit**: `feat: implement CommitAction for pipeline git commits`
 
@@ -101,18 +101,18 @@ status: not_started
 
 ### T4 — CommitAction: Tests
 
-- [ ] **Create tests at `tests/pipeline/actions/test_commit.py`**
-  - [ ] Test `action_type` property returns `"commit"`
-  - [ ] Test `isinstance(CommitAction(), Action)` (protocol compliance)
-  - [ ] Test `execute()` — no changes returns `committed=False`, `success=True`
-  - [ ] Test `execute()` — creates commit when changes exist (use `tmp_path` with `git init`)
-  - [ ] Test `execute()` — commit message from params used verbatim
-  - [ ] Test `execute()` — auto-generated message when no `message` param
-  - [ ] Test `execute()` — `paths` param scopes staging to specific files
-  - [ ] Test `execute()` — returns SHA in outputs
-  - [ ] Test `execute()` — git failure returns `success=False` with error
-  - [ ] Use `tmp_path` fixture with real `git init` for integration-style tests (no network)
-  - [ ] All tests pass, pyright clean on the action module
+- [x] **Create tests at `tests/pipeline/actions/test_commit.py`**
+  - [x] Test `action_type` property returns `"commit"`
+  - [x] Test `isinstance(CommitAction(), Action)` (protocol compliance)
+  - [x] Test `execute()` — no changes returns `committed=False`, `success=True`
+  - [x] Test `execute()` — creates commit when changes exist (use `tmp_path` with `git init`)
+  - [x] Test `execute()` — commit message from params used verbatim
+  - [x] Test `execute()` — auto-generated message when no `message` param
+  - [x] Test `execute()` — `paths` param scopes staging to specific files
+  - [x] Test `execute()` — returns SHA in outputs
+  - [x] Test `execute()` — git failure returns `success=False` with error
+  - [x] Use `tmp_path` fixture with real `git init` for integration-style tests (no network)
+  - [x] All tests pass, pyright clean on the action module
 
 **Commit**: `test: add CommitAction unit tests`
 
@@ -120,10 +120,10 @@ status: not_started
 
 ### T5 — DevlogAction: Implementation
 
-- [ ] **Implement `DevlogAction` in `src/squadron/pipeline/actions/devlog.py`**
-  - [ ] Implement `DevlogAction` class satisfying the `Action` protocol:
+- [x] **Implement `DevlogAction` in `src/squadron/pipeline/actions/devlog.py`**
+  - [x] Implement `DevlogAction` class satisfying the `Action` protocol:
     - `action_type` property returns `ActionType.DEVLOG` value (`"devlog"`)
-    - `validate(config)` — minimal validation; returns empty list (devlog is always valid)
+    - `validate(config)` — warn if `content` absent and no `prior_outputs` in context (return `ValidationError` with warning severity); otherwise return empty list
     - `execute(context)` implementation:
       - Determine DEVLOG path: `params.get("path")` or `Path(context.cwd) / "DEVLOG.md"`
       - Determine entry content:
@@ -142,7 +142,7 @@ status: not_started
       - Write updated file
       - Return `ActionResult(success=True, outputs={"path": str, "entry": str})`
       - On I/O error: return `ActionResult(success=False, error=str(exc))`
-  - [ ] Add module-level auto-registration: `register_action(ActionType.DEVLOG, DevlogAction())`
+  - [x] Add module-level auto-registration: `register_action(ActionType.DEVLOG, DevlogAction())`
 
 **Commit**: `feat: implement DevlogAction for pipeline DEVLOG entries`
 
@@ -150,19 +150,21 @@ status: not_started
 
 ### T6 — DevlogAction: Tests
 
-- [ ] **Create tests at `tests/pipeline/actions/test_devlog.py`**
-  - [ ] Test `action_type` property returns `"devlog"`
-  - [ ] Test `isinstance(DevlogAction(), Action)` (protocol compliance)
-  - [ ] Test `execute()` — explicit content written to DEVLOG.md
-  - [ ] Test `execute()` — auto-generated content from prior_outputs
-  - [ ] Test `execute()` — creates DEVLOG.md if it doesn't exist
-  - [ ] Test `execute()` — inserts under existing today's date header (no duplicate)
-  - [ ] Test `execute()` — creates new date header when today's date not present
-  - [ ] Test `execute()` — preserves existing DEVLOG content (no data loss)
-  - [ ] Test `execute()` — custom `path` param overrides default location
-  - [ ] Test `execute()` — returns path and entry text in outputs
-  - [ ] Use `tmp_path` fixture with sample DEVLOG.md files
-  - [ ] All tests pass, pyright clean on the action module
+- [x] **Create tests at `tests/pipeline/actions/test_devlog.py`**
+  - [x] Test `action_type` property returns `"devlog"`
+  - [x] Test `isinstance(DevlogAction(), Action)` (protocol compliance)
+  - [x] Test `validate()` — returns warning when `content` absent and no `prior_outputs`
+  - [x] Test `validate()` — returns empty list when `content` provided
+  - [x] Test `execute()` — explicit content written to DEVLOG.md
+  - [x] Test `execute()` — auto-generated content from prior_outputs
+  - [x] Test `execute()` — creates DEVLOG.md if it doesn't exist
+  - [x] Test `execute()` — inserts under existing today's date header (no duplicate)
+  - [x] Test `execute()` — creates new date header when today's date not present
+  - [x] Test `execute()` — preserves existing DEVLOG content (no data loss)
+  - [x] Test `execute()` — custom `path` param overrides default location
+  - [x] Test `execute()` — returns path and entry text in outputs
+  - [x] Use `tmp_path` fixture with sample DEVLOG.md files
+  - [x] All tests pass, pyright clean on the action module
 
 **Commit**: `test: add DevlogAction unit tests`
 
@@ -170,15 +172,15 @@ status: not_started
 
 ### T7 — Action Registration and Integration Verification
 
-- [ ] **Verify all three actions register correctly and coexist in the registry**
-  - [ ] Ensure importing `squadron.pipeline.actions.cf_op`, `commit`, `devlog` populates the registry
-  - [ ] Verify `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`
-  - [ ] Verify `get_action("cf-op")` returns a `CfOpAction` instance
-  - [ ] Verify `get_action("commit")` returns a `CommitAction` instance
-  - [ ] Verify `get_action("devlog")` returns a `DevlogAction` instance
-  - [ ] Add these as tests in `tests/pipeline/actions/test_registry_integration.py`
-  - [ ] Confirm no import errors or circular dependencies
-  - [ ] All existing tests still pass (`python -m pytest --tb=short -q`)
+- [x] **Verify all three actions register correctly and coexist in the registry**
+  - [x] Ensure importing `squadron.pipeline.actions.cf_op`, `commit`, `devlog` populates the registry
+  - [x] Verify `list_actions()` includes `"cf-op"`, `"commit"`, `"devlog"`
+  - [x] Verify `get_action("cf-op")` returns a `CfOpAction` instance
+  - [x] Verify `get_action("commit")` returns a `CommitAction` instance
+  - [x] Verify `get_action("devlog")` returns a `DevlogAction` instance
+  - [x] Add these as tests in `tests/pipeline/actions/test_registry_integration.py`
+  - [x] Confirm no import errors or circular dependencies
+  - [x] All existing tests still pass (`python -m pytest --tb=short -q`)
 
 **Commit**: `test: add action registry integration tests`
 
@@ -186,17 +188,17 @@ status: not_started
 
 ### T8 — Full Verification and Closeout
 
-- [ ] **Run full verification suite**
-  - [ ] `python -m pytest --tb=short -q` — all tests pass
-  - [ ] `pyright src/squadron/pipeline/actions/` — 0 errors
-  - [ ] `ruff check src/squadron/pipeline/actions/` — 0 warnings
-  - [ ] `ruff format --check src/squadron/pipeline/actions/` — no formatting issues
-  - [ ] Run the verification walkthrough from the slice design document
-  - [ ] Update slice design verification walkthrough with actual commands and output
-  - [ ] Check off success criteria in slice design
-  - [ ] Mark slice 144 as complete in slice design frontmatter
-  - [ ] Mark slice 144 as complete in slice plan (`140-slices.pipeline-foundation.md`)
-  - [ ] Update CHANGELOG.md with slice 144 entries
-  - [ ] Update DEVLOG.md with implementation completion entry
+- [x] **Run full verification suite**
+  - [x] `python -m pytest --tb=short -q` — all tests pass
+  - [x] `pyright src/squadron/pipeline/actions/` — 0 errors
+  - [x] `ruff check src/squadron/pipeline/actions/` — 0 warnings
+  - [x] `ruff format --check src/squadron/pipeline/actions/` — no formatting issues
+  - [x] Run the verification walkthrough from the slice design document
+  - [x] Update slice design verification walkthrough with actual commands and output
+  - [x] Check off success criteria in slice design
+  - [x] Mark slice 144 as complete in slice design frontmatter
+  - [x] Mark slice 144 as complete in slice plan (`140-slices.pipeline-foundation.md`)
+  - [x] Update CHANGELOG.md with slice 144 entries
+  - [x] Update DEVLOG.md with implementation completion entry
 
 **Commit**: `docs: mark slice 144 utility actions complete`
diff --git a/src/squadron/pipeline/actions/cf_op.py b/src/squadron/pipeline/actions/cf_op.py
index b6ed430..bdc1699 100644
--- a/src/squadron/pipeline/actions/cf_op.py
+++ b/src/squadron/pipeline/actions/cf_op.py
@@ -1,4 +1,99 @@
-"""CF-op action — performs a ContextForge operation (e.g. context build).
+"""CF-op action — delegates to the ContextForge CLI."""
 
-# TODO: slice 144
-"""
+from __future__ import annotations
+
+from enum import StrEnum
+
+from squadron.integrations.context_forge import ContextForgeClient, ContextForgeError
+from squadron.pipeline.actions import ActionType, register_action
+from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+
+
+class CfOperation(StrEnum):
+    """Supported ContextForge operations."""
+
+    SET_PHASE = "set_phase"
+    BUILD_CONTEXT = "build_context"
+    SUMMARIZE = "summarize"
+
+
+class CfOpAction:
+    """Pipeline action that delegates to the ContextForge CLI."""
+
+    @property
+    def action_type(self) -> str:
+        return ActionType.CF_OP
+
+    def validate(self, config: dict[str, object]) -> list[ValidationError]:
+        errors: list[ValidationError] = []
+
+        operation = config.get("operation")
+        if operation is None:
+            errors.append(
+                ValidationError(
+                    field="operation",
+                    message="'operation' is required",
+                    action_type=self.action_type,
+                )
+            )
+            return errors
+
+        if operation not in CfOperation.__members__.values():
+            errors.append(
+                ValidationError(
+                    field="operation",
+                    message=f"'{operation}' is not a valid CfOperation",
+                    action_type=self.action_type,
+                )
+            )
+            return errors
+
+        if operation == CfOperation.SET_PHASE and "phase" not in config:
+            errors.append(
+                ValidationError(
+                    field="phase",
+                    message="'phase' is required for SET_PHASE operation",
+                    action_type=self.action_type,
+                )
+            )
+
+        return errors
+
+    async def execute(self, context: ActionContext) -> ActionResult:
+        operation_raw = context.params.get("operation")
+        if operation_raw is None:
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error="'operation' missing from params",
+            )
+
+        operation = CfOperation(str(operation_raw))
+        cf_client: ContextForgeClient = context.cf_client  # type: ignore[assignment]
+
+        try:
+            match operation:
+                case CfOperation.SET_PHASE:
+                    phase = context.params["phase"]
+                    stdout = cf_client._run(["set", "phase", str(phase)])  # pyright: ignore[reportPrivateUsage]
+                case CfOperation.BUILD_CONTEXT:
+                    stdout = cf_client._run(["build"])  # pyright: ignore[reportPrivateUsage]
+                case CfOperation.SUMMARIZE:
+                    stdout = cf_client._run(["summarize"])  # pyright: ignore[reportPrivateUsage]
+        except ContextForgeError as exc:
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=str(exc),
+            )
+
+        return ActionResult(
+            success=True,
+            action_type=self.action_type,
+            outputs={"stdout": stdout, "operation": operation.value},
+        )
+
+
+register_action(ActionType.CF_OP, CfOpAction())
diff --git a/src/squadron/pipeline/actions/commit.py b/src/squadron/pipeline/actions/commit.py
index fe7de83..859a0c6 100644
--- a/src/squadron/pipeline/actions/commit.py
+++ b/src/squadron/pipeline/actions/commit.py
@@ -1,4 +1,109 @@
-"""Commit action — stages and commits changes via git.
+"""Commit action — stages and commits changes via git."""
 
-# TODO: slice 144
-"""
+from __future__ import annotations
+
+import subprocess
+from typing import cast
+
+from squadron.pipeline.actions import ActionType, register_action
+from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+
+
+class CommitAction:
+    """Pipeline action that stages files and creates a git commit."""
+
+    @property
+    def action_type(self) -> str:
+        return ActionType.COMMIT
+
+    def validate(self, config: dict[str, object]) -> list[ValidationError]:
+        """Validate config structure. Actual cwd check happens at execute time."""
+        return []
+
+    async def execute(self, context: ActionContext) -> ActionResult:
+        cwd = context.cwd
+
+        # Check for changes
+        status = _git(["status", "--porcelain"], cwd=cwd)
+        if status is None or status.returncode != 0:
+            stderr = status.stderr if status else "git status failed"
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=stderr or "git status failed — is this a git repository?",
+            )
+
+        if not status.stdout.strip():
+            return ActionResult(
+                success=True,
+                action_type=self.action_type,
+                outputs={"committed": False},
+            )
+
+        # Stage files
+        paths_raw = context.params.get("paths")
+        if paths_raw and isinstance(paths_raw, list):
+            stage_result = _git(
+                ["add", *(str(p) for p in cast(list[object], paths_raw))],
+                cwd=cwd,
+            )
+        else:
+            stage_result = _git(["add", "-A"], cwd=cwd)
+
+        if stage_result is None or stage_result.returncode != 0:
+            stderr = stage_result.stderr if stage_result else "git add failed"
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=stderr,
+            )
+
+        # Build commit message
+        message = context.params.get("message")
+        if not message:
+            commit_type = context.params.get("type", "chore")
+            message = f"{commit_type}: {context.step_name} for {context.pipeline_name}"
+        message = str(message)
+
+        # Commit
+        commit_result = _git(["commit", "-m", message], cwd=cwd)
+        if commit_result is None or commit_result.returncode != 0:
+            stderr = commit_result.stderr if commit_result else "git commit failed"
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=stderr,
+            )
+
+        # Get SHA
+        sha_result = _git(["rev-parse", "HEAD"], cwd=cwd)
+        sha = sha_result.stdout.strip() if sha_result else "unknown"
+
+        return ActionResult(
+            success=True,
+            action_type=self.action_type,
+            outputs={
+                "committed": True,
+                "sha": sha,
+                "message": message,
+            },
+        )
+
+
+def _git(args: list[str], *, cwd: str) -> subprocess.CompletedProcess[str] | None:
+    """Run a git command, returning the CompletedProcess or None on error."""
+    try:
+        return subprocess.run(
+            ["git", *args],
+            capture_output=True,
+            text=True,
+            cwd=cwd,
+        )
+    except OSError:
+        return None
+
+
+register_action(ActionType.COMMIT, CommitAction())
diff --git a/src/squadron/pipeline/actions/devlog.py b/src/squadron/pipeline/actions/devlog.py
index b944d4c..e580fce 100644
--- a/src/squadron/pipeline/actions/devlog.py
+++ b/src/squadron/pipeline/actions/devlog.py
@@ -1,4 +1,181 @@
-"""Devlog action — writes a structured DEVLOG entry.
+"""Devlog action — writes a structured DEVLOG entry."""
 
-# TODO: slice 144
-"""
+from __future__ import annotations
+
+import re
+from datetime import date
+from pathlib import Path
+
+from squadron.pipeline.actions import ActionType, register_action
+from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+
+_DATE_HEADER_RE = re.compile(r"^## \d{8}$")
+
+
+class DevlogAction:
+    """Pipeline action that appends a structured entry to DEVLOG.md."""
+
+    @property
+    def action_type(self) -> str:
+        return ActionType.DEVLOG
+
+    def validate(self, config: dict[str, object]) -> list[ValidationError]:
+        errors: list[ValidationError] = []
+        has_content = "content" in config
+        has_prior = bool(config.get("_has_prior_outputs"))
+
+        if not has_content and not has_prior:
+            errors.append(
+                ValidationError(
+                    field="content",
+                    message=(
+                        "No 'content' provided and no prior_outputs available "
+                        "— entry will be minimal"
+                    ),
+                    action_type=self.action_type,
+                )
+            )
+        return errors
+
+    async def execute(self, context: ActionContext) -> ActionResult:
+        # Determine file path
+        path_param = context.params.get("path")
+        devlog_path = (
+            Path(str(path_param)) if path_param else Path(context.cwd) / "DEVLOG.md"
+        )
+
+        # Build entry content
+        content = context.params.get("content")
+        if content:
+            entry_text = str(content)
+        else:
+            entry_text = _auto_generate(context)
+
+        # Build full entry with title
+        title = context.params.get("title")
+        if title:
+            entry = f"**{title}**\n{entry_text}"
+        else:
+            entry = f"**{context.pipeline_name}: {context.step_name}**\n{entry_text}"
+
+        today = date.today().strftime("%Y%m%d")
+        today_header = f"## {today}"
+
+        try:
+            lines = _read_or_create(devlog_path)
+            updated = _insert_entry(lines, today_header, entry)
+            devlog_path.write_text("\n".join(updated))
+        except OSError as exc:
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=str(exc),
+            )
+
+        return ActionResult(
+            success=True,
+            action_type=self.action_type,
+            outputs={"path": str(devlog_path), "entry": entry},
+        )
+
+
+def _auto_generate(context: ActionContext) -> str:
+    """Build an entry from prior_outputs."""
+    if not context.prior_outputs:
+        return "No prior outputs recorded."
+
+    parts: list[str] = []
+    for step_name, result in context.prior_outputs.items():
+        status = "PASS" if result.success else "FAIL"
+        line = f"- {step_name}: {status}"
+        if result.verdict:
+            line += f" (verdict: {result.verdict})"
+        parts.append(line)
+
+    return "\n".join(parts)
+
+
+def _read_or_create(path: Path) -> list[str]:
+    """Read existing DEVLOG.md or create a minimal one."""
+    if path.exists():
+        return path.read_text().splitlines()
+
+    path.parent.mkdir(parents=True, exist_ok=True)
+    minimal = [
+        "---",
+        "docType: devlog",
+        "---",
+        "",
+        "# Development Log",
+        "",
+        "---",
+        "",
+    ]
+    path.write_text("\n".join(minimal))
+    return minimal
+
+
+def _insert_entry(lines: list[str], today_header: str, entry: str) -> list[str]:
+    """Insert entry under today's date header, creating it if needed."""
+    result = list(lines)
+    entry_lines = ["", *entry.splitlines(), ""]
+
+    # Find existing today header
+    for i, line in enumerate(result):
+        if line.strip() == today_header:
+            # Insert after the header (skip blank line after header if present)
+            insert_at = i + 1
+            if insert_at < len(result) and not result[insert_at].strip():
+                insert_at += 1
+            result[insert_at:insert_at] = entry_lines
+            return result
+
+    # No today header — find first date header or separator after frontmatter
+    insert_at = _find_content_start(result)
+    result[insert_at:insert_at] = [today_header, "", *entry.splitlines(), ""]
+    return result
+
+
+def _find_content_start(lines: list[str]) -> int:
+    """Find the index where new date entries should be inserted.
+
+    Skips past frontmatter, the title line, description, and the
+    separator that follows.
+    """
+    in_frontmatter = False
+    past_frontmatter = False
+    separator_count = 0
+
+    for i, line in enumerate(lines):
+        stripped = line.strip()
+
+        if stripped == "---" and not past_frontmatter:
+            separator_count += 1
+            if separator_count == 2:
+                past_frontmatter = True
+                in_frontmatter = False
+            elif separator_count == 1:
+                in_frontmatter = True
+            continue
+
+        if in_frontmatter:
+            continue
+
+        if past_frontmatter:
+            # Look for the content separator (--- after title/description)
+            if stripped == "---":
+                # Return position after this separator + blank line
+                next_i = i + 1
+                while next_i < len(lines) and not lines[next_i].strip():
+                    next_i += 1
+                return next_i
+
+            # Look for first date header
+            if _DATE_HEADER_RE.match(stripped):
+                return i
+
+    return len(lines)
+
+
+register_action(ActionType.DEVLOG, DevlogAction())
diff --git a/tests/pipeline/actions/__init__.py b/tests/pipeline/actions/__init__.py
new file mode 100644
index 0000000..e69de29
diff --git a/tests/pipeline/actions/test_cf_op.py b/tests/pipeline/actions/test_cf_op.py
new file mode 100644
index 0000000..9ff9831
--- /dev/null
+++ b/tests/pipeline/actions/test_cf_op.py
@@ -0,0 +1,166 @@
+"""Tests for CfOpAction."""
+
+from __future__ import annotations
+
+from unittest.mock import MagicMock
+
+import pytest
+
+from squadron.integrations.context_forge import ContextForgeError
+from squadron.pipeline.actions.cf_op import CfOpAction, CfOperation
+from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.models import ActionContext, ActionResult
+
+
+@pytest.fixture
+def action() -> CfOpAction:
+    return CfOpAction()
+
+
+@pytest.fixture
+def mock_context() -> ActionContext:
+    resolver = MagicMock()
+    cf_client = MagicMock()
+    return ActionContext(
+        pipeline_name="test-pipeline",
+        run_id="run-001",
+        params={},
+        step_name="cf-step",
+        step_index=0,
+        prior_outputs={},
+        resolver=resolver,
+        cf_client=cf_client,
+        cwd="/tmp/test",
+    )
+
+
+def test_action_type(action: CfOpAction) -> None:
+    assert action.action_type == "cf-op"
+
+
+def test_protocol_compliance(action: CfOpAction) -> None:
+    assert isinstance(action, Action)
+
+
+# --- validate() ---
+
+
+def test_validate_missing_operation(action: CfOpAction) -> None:
+    errors = action.validate({})
+    assert len(errors) == 1
+    assert errors[0].field == "operation"
+    assert "required" in errors[0].message
+
+
+def test_validate_invalid_operation(action: CfOpAction) -> None:
+    errors = action.validate({"operation": "nonexistent"})
+    assert len(errors) == 1
+    assert errors[0].field == "operation"
+    assert "not a valid" in errors[0].message
+
+
+def test_validate_set_phase_without_phase(action: CfOpAction) -> None:
+    errors = action.validate({"operation": CfOperation.SET_PHASE})
+    assert len(errors) == 1
+    assert errors[0].field == "phase"
+
+
+def test_validate_valid_set_phase(action: CfOpAction) -> None:
+    errors = action.validate(
+        {
+            "operation": CfOperation.SET_PHASE,
+            "phase": 4,
+        }
+    )
+    assert errors == []
+
+
+def test_validate_valid_build_context(action: CfOpAction) -> None:
+    errors = action.validate({"operation": CfOperation.BUILD_CONTEXT})
+    assert errors == []
+
+
+def test_validate_valid_summarize(action: CfOpAction) -> None:
+    errors = action.validate({"operation": CfOperation.SUMMARIZE})
+    assert errors == []
+
+
+# --- execute() ---
+
+
+@pytest.mark.asyncio
+async def test_execute_set_phase(
+    action: CfOpAction, mock_context: ActionContext
+) -> None:
+    mock_context.params = {
+        "operation": CfOperation.SET_PHASE,
+        "phase": "4",
+    }
+    mock_context.cf_client._run = MagicMock(return_value="Phase set to 4")  # type: ignore[union-attr]
+
+    result = await action.execute(mock_context)
+
+    mock_context.cf_client._run.assert_called_once_with(["set", "phase", "4"])  # type: ignore[union-attr]
+    assert result.success is True
+    assert result.outputs["stdout"] == "Phase set to 4"
+    assert result.outputs["operation"] == "set_phase"
+
+
+@pytest.mark.asyncio
+async def test_execute_build_context(
+    action: CfOpAction, mock_context: ActionContext
+) -> None:
+    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
+    mock_context.cf_client._run = MagicMock(return_value="Context built")  # type: ignore[union-attr]
+
+    result = await action.execute(mock_context)
+
+    mock_context.cf_client._run.assert_called_once_with(["build"])  # type: ignore[union-attr]
+    assert result.success is True
+    assert result.outputs["stdout"] == "Context built"
+    assert result.outputs["operation"] == "build_context"
+
+
+@pytest.mark.asyncio
+async def test_execute_summarize(
+    action: CfOpAction, mock_context: ActionContext
+) -> None:
+    mock_context.params = {"operation": CfOperation.SUMMARIZE}
+    mock_context.cf_client._run = MagicMock(return_value="Summary done")  # type: ignore[union-attr]
+
+    result = await action.execute(mock_context)
+
+    mock_context.cf_client._run.assert_called_once_with(["summarize"])  # type: ignore[union-attr]
+    assert result.success is True
+    assert result.outputs["stdout"] == "Summary done"
+
+
+@pytest.mark.asyncio
+async def test_execute_success_outputs(
+    action: CfOpAction, mock_context: ActionContext
+) -> None:
+    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
+    mock_context.cf_client._run = MagicMock(return_value="ok")  # type: ignore[union-attr]
+
+    result = await action.execute(mock_context)
+
+    assert isinstance(result, ActionResult)
+    assert result.success is True
+    assert "stdout" in result.outputs
+    assert result.action_type == "cf-op"
+
+
+@pytest.mark.asyncio
+async def test_execute_cf_error(
+    action: CfOpAction, mock_context: ActionContext
+) -> None:
+    mock_context.params = {"operation": CfOperation.BUILD_CONTEXT}
+    mock_context.cf_client._run = MagicMock(  # type: ignore[union-attr]
+        side_effect=ContextForgeError("cf build failed")
+    )
+
+    result = await action.execute(mock_context)
+
+    assert result.success is False
+    assert result.error == "cf build failed"
+    assert result.action_type == "cf-op"
diff --git a/tests/pipeline/actions/test_commit.py b/tests/pipeline/actions/test_commit.py
new file mode 100644
index 0000000..6a41e62
--- /dev/null
+++ b/tests/pipeline/actions/test_commit.py
@@ -0,0 +1,170 @@
+"""Tests for CommitAction."""
+
+from __future__ import annotations
+
+import subprocess
+from pathlib import Path
+from unittest.mock import MagicMock
+
+import pytest
+
+from squadron.pipeline.actions.commit import CommitAction
+from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.models import ActionContext
+
+
+@pytest.fixture
+def action() -> CommitAction:
+    return CommitAction()
+
+
+@pytest.fixture
+def git_repo(tmp_path: Path) -> Path:
+    """Create a temporary git repo with initial commit."""
+    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
+    subprocess.run(
+        ["git", "config", "user.email", "test@test.com"],
+        cwd=tmp_path,
+        capture_output=True,
+        check=True,
+    )
+    subprocess.run(
+        ["git", "config", "user.name", "Test"],
+        cwd=tmp_path,
+        capture_output=True,
+        check=True,
+    )
+    # Initial commit so HEAD exists
+    readme = tmp_path / "README.md"
+    readme.write_text("init")
+    subprocess.run(["git", "add", "-A"], cwd=tmp_path, capture_output=True, check=True)
+    subprocess.run(
+        ["git", "commit", "-m", "init"],
+        cwd=tmp_path,
+        capture_output=True,
+        check=True,
+    )
+    return tmp_path
+
+
+def _make_context(cwd: str, **params: object) -> ActionContext:
+    return ActionContext(
+        pipeline_name="test-pipeline",
+        run_id="run-001",
+        params=dict(params),
+        step_name="commit-step",
+        step_index=0,
+        prior_outputs={},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        cwd=cwd,
+    )
+
+
+def test_action_type(action: CommitAction) -> None:
+    assert action.action_type == "commit"
+
+
+def test_protocol_compliance(action: CommitAction) -> None:
+    assert isinstance(action, Action)
+
+
+@pytest.mark.asyncio
+async def test_no_changes_returns_committed_false(
+    action: CommitAction, git_repo: Path
+) -> None:
+    ctx = _make_context(str(git_repo))
+    result = await action.execute(ctx)
+
+    assert result.success is True
+    assert result.outputs["committed"] is False
+
+
+@pytest.mark.asyncio
+async def test_creates_commit_when_changes_exist(
+    action: CommitAction, git_repo: Path
+) -> None:
+    (git_repo / "new_file.txt").write_text("hello")
+    ctx = _make_context(str(git_repo), message="feat: test commit")
+
+    result = await action.execute(ctx)
+
+    assert result.success is True
+    assert result.outputs["committed"] is True
+    assert result.outputs["message"] == "feat: test commit"
+    assert isinstance(result.outputs["sha"], str)
+    assert len(str(result.outputs["sha"])) == 40
+
+
+@pytest.mark.asyncio
+async def test_commit_message_from_params(action: CommitAction, git_repo: Path) -> None:
+    (git_repo / "file.txt").write_text("data")
+    ctx = _make_context(str(git_repo), message="docs: custom message")
+
+    result = await action.execute(ctx)
+
+    assert result.success is True
+    assert result.outputs["message"] == "docs: custom message"
+
+
+@pytest.mark.asyncio
+async def test_auto_generated_message(action: CommitAction, git_repo: Path) -> None:
+    (git_repo / "file.txt").write_text("data")
+    ctx = _make_context(str(git_repo))
+
+    result = await action.execute(ctx)
+
+    assert result.success is True
+    msg = str(result.outputs["message"])
+    assert "commit-step" in msg
+    assert "test-pipeline" in msg
+    assert msg.startswith("chore:")
+
+
+@pytest.mark.asyncio
+async def test_paths_param_scopes_staging(action: CommitAction, git_repo: Path) -> None:
+    (git_repo / "include.txt").write_text("yes")
+    (git_repo / "exclude.txt").write_text("no")
+    ctx = _make_context(str(git_repo), paths=["include.txt"], message="feat: scoped")
+
+    result = await action.execute(ctx)
+
+    assert result.success is True
+    assert result.outputs["committed"] is True
+    # Verify exclude.txt is still untracked
+    status = subprocess.run(
+        ["git", "status", "--porcelain"],
+        cwd=git_repo,
+        capture_output=True,
+        text=True,
+    )
+    assert "exclude.txt" in status.stdout
+
+
+@pytest.mark.asyncio
+async def test_returns_sha_in_outputs(action: CommitAction, git_repo: Path) -> None:
+    (git_repo / "file.txt").write_text("data")
+    ctx = _make_context(str(git_repo), message="feat: sha test")
+
+    result = await action.execute(ctx)
+
+    sha = str(result.outputs["sha"])
+    # Verify SHA matches actual HEAD
+    head = subprocess.run(
+        ["git", "rev-parse", "HEAD"],
+        cwd=git_repo,
+        capture_output=True,
+        text=True,
+    )
+    assert sha == head.stdout.strip()
+
+
+@pytest.mark.asyncio
+async def test_git_failure_returns_error(action: CommitAction, tmp_path: Path) -> None:
+    # tmp_path is NOT a git repo — git status will fail
+    ctx = _make_context(str(tmp_path))
+
+    result = await action.execute(ctx)
+
+    assert result.success is False
+    assert result.error is not None
diff --git a/tests/pipeline/actions/test_devlog.py b/tests/pipeline/actions/test_devlog.py
new file mode 100644
index 0000000..782ebe9
--- /dev/null
+++ b/tests/pipeline/actions/test_devlog.py
@@ -0,0 +1,247 @@
+"""Tests for DevlogAction."""
+
+from __future__ import annotations
+
+from pathlib import Path
+from unittest.mock import MagicMock, patch
+
+import pytest
+
+from squadron.pipeline.actions.devlog import DevlogAction
+from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.models import ActionContext, ActionResult
+
+
+@pytest.fixture
+def action() -> DevlogAction:
+    return DevlogAction()
+
+
+def _make_context(
+    cwd: str,
+    prior_outputs: dict[str, ActionResult] | None = None,
+    **params: object,
+) -> ActionContext:
+    return ActionContext(
+        pipeline_name="test-pipeline",
+        run_id="run-001",
+        params=dict(params),
+        step_name="devlog-step",
+        step_index=0,
+        prior_outputs=prior_outputs or {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        cwd=cwd,
+    )
+
+
+SAMPLE_DEVLOG = """\
+---
+docType: devlog
+project: test
+dateCreated: 20260101
+dateUpdated: 20260330
+---
+
+# Development Log
+
+A lightweight, append-only record.
+
+---
+
+## 20260330
+
+**Previous entry**
+Some earlier content.
+
+---
+
+## 20260329
+
+**Even older entry**
+Old content.
+"""
+
+
+def test_action_type(action: DevlogAction) -> None:
+    assert action.action_type == "devlog"
+
+
+def test_protocol_compliance(action: DevlogAction) -> None:
+    assert isinstance(action, Action)
+
+
+# --- validate() ---
+
+
+def test_validate_warns_no_content_no_prior(action: DevlogAction) -> None:
+    errors = action.validate({})
+    assert len(errors) == 1
+    assert errors[0].field == "content"
+    assert "minimal" in errors[0].message
+
+
+def test_validate_ok_with_content(action: DevlogAction) -> None:
+    errors = action.validate({"content": "Some text"})
+    assert errors == []
+
+
+# --- execute() ---
+
+
+@pytest.mark.asyncio
+async def test_explicit_content(action: DevlogAction, tmp_path: Path) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    ctx = _make_context(str(tmp_path), content="Explicit entry text")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    text = devlog.read_text()
+    assert "Explicit entry text" in text
+
+
+@pytest.mark.asyncio
+async def test_auto_generated_from_prior_outputs(
+    action: DevlogAction, tmp_path: Path
+) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    prior = {
+        "step-a": ActionResult(success=True, action_type="cf-op", outputs={}),
+        "step-b": ActionResult(
+            success=False,
+            action_type="commit",
+            outputs={},
+            verdict="FAIL",
+        ),
+    }
+    ctx = _make_context(str(tmp_path), prior_outputs=prior)
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    text = devlog.read_text()
+    assert "step-a: PASS" in text
+    assert "step-b: FAIL" in text
+    assert "verdict: FAIL" in text
+
+
+@pytest.mark.asyncio
+async def test_creates_devlog_if_missing(action: DevlogAction, tmp_path: Path) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    assert not devlog.exists()
+
+    ctx = _make_context(str(tmp_path), content="New entry")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    assert devlog.exists()
+    text = devlog.read_text()
+    assert "New entry" in text
+    assert "## 20260331" in text
+
+
+@pytest.mark.asyncio
+async def test_inserts_under_existing_today_header(
+    action: DevlogAction, tmp_path: Path
+) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    ctx = _make_context(str(tmp_path), content="Today's addition")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260330"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    text = devlog.read_text()
+    # Should only have one ## 20260330 header
+    assert text.count("## 20260330") == 1
+    assert "Today's addition" in text
+    # Existing content preserved
+    assert "Previous entry" in text
+
+
+@pytest.mark.asyncio
+async def test_creates_new_date_header(action: DevlogAction, tmp_path: Path) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    ctx = _make_context(str(tmp_path), content="New day entry")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    text = devlog.read_text()
+    assert "## 20260331" in text
+    # New header should appear before existing dates
+    idx_new = text.index("## 20260331")
+    idx_old = text.index("## 20260330")
+    assert idx_new < idx_old
+
+
+@pytest.mark.asyncio
+async def test_preserves_existing_content(action: DevlogAction, tmp_path: Path) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    ctx = _make_context(str(tmp_path), content="Added entry")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    text = devlog.read_text()
+    assert "Previous entry" in text
+    assert "Even older entry" in text
+    assert "docType: devlog" in text
+
+
+@pytest.mark.asyncio
+async def test_custom_path_override(action: DevlogAction, tmp_path: Path) -> None:
+    custom_path = tmp_path / "subdir" / "MY_DEVLOG.md"
+    ctx = _make_context(
+        str(tmp_path), content="Custom path entry", path=str(custom_path)
+    )
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    assert custom_path.exists()
+    assert "Custom path entry" in custom_path.read_text()
+    assert result.outputs["path"] == str(custom_path)
+
+
+@pytest.mark.asyncio
+async def test_returns_path_and_entry_in_outputs(
+    action: DevlogAction, tmp_path: Path
+) -> None:
+    devlog = tmp_path / "DEVLOG.md"
+    devlog.write_text(SAMPLE_DEVLOG)
+
+    ctx = _make_context(str(tmp_path), content="Output test")
+
+    with patch("squadron.pipeline.actions.devlog.date") as mock_date:
+        mock_date.today.return_value.strftime.return_value = "20260331"
+        result = await action.execute(ctx)
+
+    assert result.success is True
+    assert result.outputs["path"] == str(devlog)
+    assert "Output test" in str(result.outputs["entry"])
diff --git a/tests/pipeline/actions/test_registry_integration.py b/tests/pipeline/actions/test_registry_integration.py
new file mode 100644
index 0000000..b739c39
--- /dev/null
+++ b/tests/pipeline/actions/test_registry_integration.py
@@ -0,0 +1,44 @@
+"""Integration tests — verify all three utility actions register and coexist."""
+
+from __future__ import annotations
+
+import squadron.pipeline.actions.cf_op  # noqa: F401
+import squadron.pipeline.actions.commit  # noqa: F401
+import squadron.pipeline.actions.devlog  # noqa: F401
+from squadron.pipeline.actions import get_action, list_actions
+from squadron.pipeline.actions.cf_op import CfOpAction
+from squadron.pipeline.actions.commit import CommitAction
+from squadron.pipeline.actions.devlog import DevlogAction
+from squadron.pipeline.actions.protocol import Action
+
+
+def test_list_actions_includes_all_three() -> None:
+    actions = list_actions()
+    assert "cf-op" in actions
+    assert "commit" in actions
+    assert "devlog" in actions
+
+
+def test_get_action_cf_op() -> None:
+    action = get_action("cf-op")
+    assert isinstance(action, CfOpAction)
+    assert isinstance(action, Action)
+
+
+def test_get_action_commit() -> None:
+    action = get_action("commit")
+    assert isinstance(action, CommitAction)
+    assert isinstance(action, Action)
+
+
+def test_get_action_devlog() -> None:
+    action = get_action("devlog")
+    assert isinstance(action, DevlogAction)
+    assert isinstance(action, Action)
+
+
+def test_no_import_errors() -> None:
+    """Importing all action modules should not raise."""
+
+    # If we got here, no circular dependency or import error
+    assert True

```

### Rules Injected

None

### Raw Response

Looking at this git diff, I need to review the implementation of three utility actions (CfOpAction, CommitAction, DevlogAction) and their tests.

## Summary
CONCERNS

## Findings

### [CONCERN] Validate-execute parameter mismatch in CfOpAction
In `src/squadron/pipeline/actions/cf_op.py`, the `validate()` method checks `config.get("operation")` and `config.get("phase")`, but `execute()` reads from `context.params.get("operation")` and `context.params["phase"]`. If config and params diverge at runtime, validation passes but execution could fail or behave unexpectedly.

**Recommendation:** Consider validating `context.params` directly in `execute()`, or document the expectation that config and params must be consistent.

---

### [CONCERN] Validate-execute parameter mismatch in CommitAction
In `src/squadron/pipeline/actions/commit.py`, `validate()` accepts any config (returns empty list) but `execute()` reads from `context.params.get("paths")` and `context.params.get("message")`. This means validation provides no actual safety guarantee.

**Recommendation:** If validation is intentionally minimal, document this. Otherwise, validate required params exist or warn if `cwd` is not a valid git repository.

---

### [CONCERN] DevlogAction validate uses config flag, not context
In `src/squadron/pipeline/actions/devlog.py`, `validate()` checks `config.get("_has_prior_outputs")` to determine if auto-generation is possible, but `execute()` checks `context.prior_outputs` directly. The test mocks `_has_prior_outputs` in config, but there's no clear mechanism for this flag to be set during normal pipeline operation.

In `tests/pipeline/actions/test_devlog.py`, test `test_validate_warns_no_content_no_prior()` creates a context with `prior_outputs={}` but the `validate()` method checks config, not context:

```python
def test_validate_warns_no_content_no_prior(action: DevlogAction) -> None:
    errors = action.validate({})
    assert len(errors) == 1
```

The actual test verifies config behavior, not context behavior.

**Recommendation:** Consider checking `context.prior_outputs` directly in `validate()` rather than relying on a config flag, or ensure the flag is consistently populated upstream.

---

### [PASS] Phase value not validated in CfOpAction
The `validate()` method checks that `phase` key exists for `SET_PHASE` operation, but does not validate its type or range. The `execute()` method converts with `str(phase)`, which handles both int and string inputs. This is acceptable since phase is passed through to CF CLI which handles validation.

---

### [PASS] Comprehensive test coverage
The test files demonstrate the "test-with" pattern:
- `test_cf_op.py`: 13 tests covering validation paths, all three operations, success/failure cases, and protocol compliance
- `test_commit.py`: 9 tests with real git repos via `tmp_path`, including edge cases (no changes, scoped paths, SHA verification)
- `test_devlog.py`: 12 tests covering explicit/auto-generated content, file creation, header deduplication, and path override
- `test_registry_integration.py`: 5 tests verifying registration and protocol satisfaction

All tests properly mock external dependencies (ContextForgeClient) and use appropriate fixtures.

---

### [PASS] Auto-registration pattern implemented correctly
All three actions use module-level `register_action()` calls that execute at import time, consistent with the provider registry pattern noted in the slice design.

---

### [PASS] Error handling patterns
- `cf_op.py`: Catches `ContextForgeError` and returns `success=False` with error message
- `commit.py`: Returns `None` from `_git()` helper on `OSError`, then checks for None before accessing returncode/stdout
- `devlog.py`: Catches `OSError` on file operations and returns `success=False`

---

### [PASS] pyright ignore comment per project convention
The `pyright: ignore[reportPrivateUsage]` comment is used appropriately in `cf_op.py` for `cf_client._run()` calls, as documented in DEVLOG.md.
