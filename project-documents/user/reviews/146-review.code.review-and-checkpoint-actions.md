---
docType: review
layer: project
reviewType: code
slice: review-and-checkpoint-actions
project: squadron
verdict: UNKNOWN
sourceDocument: project-documents/user/slices/146-slice.review-and-checkpoint-actions.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260402
dateUpdated: 20260402
---

# Review: code — slice 146

**Verdict:** UNKNOWN
**Model:** minimax/minimax-m2.7

No specific findings.

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

Run `git diff 4d2a139d74a00818403be6691feb65c06741377b...146-slice.review-and-checkpoint-actions` to identify changed files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/CHANGELOG.md b/CHANGELOG.md
index f058100..3cfb59c 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -13,6 +13,19 @@ and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0
 ## [Unreleased]
 
 ### Added
+- `ReviewAction` — pipeline action for review gates (slice 146)
+  - Delegates to `run_review_with_profile()`, maps `ReviewResult` to `ActionResult` with verdict and structured findings
+  - Model/profile resolution via 5-level cascade, same pattern as dispatch
+  - Review file persistence (non-fatal on failure)
+  - Auto-registers at module import time
+- `CheckpointAction` — pipeline action for quality gates (slice 146)
+  - Evaluates trigger (`always`, `on-concerns`, `on-fail`, `never`) against prior review verdict
+  - Returns `paused`/`skipped` data — executor interprets the result
+  - `CheckpointTrigger` StrEnum with four values
+  - Auto-registers at module import time
+- `review/persistence.py` — shared review file formatting and saving (slice 146)
+  - `format_review_markdown()`, `save_review_file()`, `yaml_escape()`, `SliceInfo` TypedDict
+  - Extracted from `cli/commands/review.py` for reuse by pipeline review action
 - `DispatchAction` — pipeline action for language model dispatch (slice 145)
   - Resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent, sends prompt, captures response
   - Profile resolution: explicit param override > alias-derived profile > SDK default
diff --git a/DEVLOG.md b/DEVLOG.md
index ee41616..d1d7a2a 100644
--- a/DEVLOG.md
+++ b/DEVLOG.md
@@ -2,7 +2,7 @@
 docType: devlog
 project: squadron
 dateCreated: 20260218
-dateUpdated: 20260331
+dateUpdated: 20260402
 ---
 
 # Development Log
@@ -12,6 +12,13 @@ Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).
 
 ---
 
+## 20260402
+
+**Slice 146: Review and Checkpoint Actions — Implementation Complete (Phase 6)**
+Implemented all 8 tasks (T1–T8). Extracted review persistence to shared `review/persistence.py` (`format_review_markdown`, `save_review_file`, `yaml_escape`, `SliceInfo`). Implemented `CheckpointAction` with `CheckpointTrigger` enum and trigger×verdict evaluation matrix. Implemented `ReviewAction` delegating to `run_review_with_profile()` with model/profile resolution, template input passthrough, review file persistence (non-fatal), and verdict/findings mapping. 57 new tests (13 persistence + 21 checkpoint + 21 review + 2 registry), 884 total pass, pyright 0 errors, ruff clean. Slice 146 marked complete.
+
+---
+
 ## 20260331
 
 **Slice 146: Review and Checkpoint Actions — Task Breakdown Complete (Phase 5)**
diff --git a/project-documents/user/architecture/140-slices.pipeline-foundation.md b/project-documents/user/architecture/140-slices.pipeline-foundation.md
index cdc2897..9b641c1 100644
--- a/project-documents/user/architecture/140-slices.pipeline-foundation.md
+++ b/project-documents/user/architecture/140-slices.pipeline-foundation.md
@@ -36,7 +36,7 @@ status: in_progress
 
 6. [x] **(145) Dispatch Action** — Send assembled context to a model via agent registry, capture output (file artifacts or code changes), record metadata (model used, token counts). Integrates with model resolver for alias resolution through the cascade chain. Handles both SDK and API provider dispatch transparently through the AgentProvider protocol. Dependencies: [142, Agent Registry (102)]. Risk: Low. Effort: 2/5
 
-7. [ ] **(146) Review and Checkpoint Actions** — Review action: run a review template against an artifact within a pipeline step, consume structured findings from slice 143, produce verdict and structured finding set, handle review file persistence. Checkpoint action: pause pipeline execution for human decision, serialize pipeline state for resume, present findings and status summary, accept human input (approve, revise, skip, abort, override model/config for subsequent steps). Checkpoint triggers: always, on-concerns, on-fail, never. Dependencies: [143, 145]. Risk: Medium (checkpoint interactive UX). Effort: 3/5
+7. [x] **(146) Review and Checkpoint Actions** — Review action: run a review template against an artifact within a pipeline step, consume structured findings from slice 143, produce verdict and structured finding set, handle review file persistence. Checkpoint action: pause pipeline execution for human decision, serialize pipeline state for resume, present findings and status summary, accept human input (approve, revise, skip, abort, override model/config for subsequent steps). Checkpoint triggers: always, on-concerns, on-fail, never. Dependencies: [143, 145]. Risk: Medium (checkpoint interactive UX). Effort: 3/5
 
 8. [ ] **(147) Compact Action and Step Types** — Compact action: issue parameterized compaction instructions via CF with configurable context preservation rules. Step type implementations: phase step (expands to cf-op → dispatch → review → checkpoint → commit action sequence), compact step, standalone review step, devlog step. Each step type is a named expansion into an action sequence, bridging the terse YAML grammar and the action layer. Dependencies: [144, 145, 146]. Risk: Low. Effort: 3/5
 
diff --git a/project-documents/user/slices/146-slice.review-and-checkpoint-actions.md b/project-documents/user/slices/146-slice.review-and-checkpoint-actions.md
index 8586857..30ce008 100644
--- a/project-documents/user/slices/146-slice.review-and-checkpoint-actions.md
+++ b/project-documents/user/slices/146-slice.review-and-checkpoint-actions.md
@@ -6,8 +6,8 @@ parent: 140-slices.pipeline-foundation.md
 dependencies: [143, 145]
 interfaces: [147, 149, 150]
 dateCreated: 20260331
-dateUpdated: 20260331
-status: not_started
+dateUpdated: 20260402
+status: complete
 ---
 
 # Slice Design: Review and Checkpoint Actions (146)
@@ -464,40 +464,40 @@ The CLI commands would then import from `review/persistence.py` instead of using
 
 ### Functional Requirements
 
-- [ ] `ReviewAction` satisfies the `Action` protocol (`isinstance` check passes)
-- [ ] `ReviewAction.action_type` returns `"review"`
-- [ ] `ReviewAction.validate()` returns error when `template` is missing
-- [ ] `ReviewAction.validate()` returns error when `cwd` is missing
-- [ ] `ReviewAction.validate()` returns empty list for valid config
-- [ ] `ReviewAction.execute()` resolves template via `get_template()`
-- [ ] `ReviewAction.execute()` resolves model through `context.resolver.resolve()`
-- [ ] `ReviewAction.execute()` calls `run_review_with_profile()` with correct template, inputs, model, profile
-- [ ] `ReviewAction.execute()` populates `ActionResult.verdict` from review verdict
-- [ ] `ReviewAction.execute()` populates `ActionResult.findings` from structured findings
-- [ ] `ReviewAction.execute()` persists review file to disk
-- [ ] `ReviewAction.execute()` returns `success=False` on any error (never raises)
-- [ ] `ReviewAction` auto-registers at module import time
-- [ ] `CheckpointAction` satisfies the `Action` protocol
-- [ ] `CheckpointAction.action_type` returns `"checkpoint"`
-- [ ] `CheckpointAction.validate()` rejects invalid trigger values
-- [ ] `CheckpointAction.validate()` accepts valid triggers and empty config
-- [ ] `CheckpointAction.execute()` returns `checkpoint="skipped"` when trigger is `never`
-- [ ] `CheckpointAction.execute()` returns `checkpoint="paused"` when trigger is `always`
-- [ ] `CheckpointAction.execute()` evaluates `on-concerns` correctly: fires on CONCERNS and FAIL, skips on PASS
-- [ ] `CheckpointAction.execute()` evaluates `on-fail` correctly: fires on FAIL only, skips on PASS and CONCERNS
-- [ ] `CheckpointAction.execute()` handles missing prior review verdict gracefully (no review = no fire, except `always`)
-- [ ] `CheckpointAction` auto-registers at module import time
-- [ ] `CheckpointTrigger` enum has values: `always`, `on-concerns`, `on-fail`, `never`
+- [x] `ReviewAction` satisfies the `Action` protocol (`isinstance` check passes)
+- [x] `ReviewAction.action_type` returns `"review"`
+- [x] `ReviewAction.validate()` returns error when `template` is missing
+- [x] `ReviewAction.validate()` returns error when `cwd` is missing
+- [x] `ReviewAction.validate()` returns empty list for valid config
+- [x] `ReviewAction.execute()` resolves template via `get_template()`
+- [x] `ReviewAction.execute()` resolves model through `context.resolver.resolve()`
+- [x] `ReviewAction.execute()` calls `run_review_with_profile()` with correct template, inputs, model, profile
+- [x] `ReviewAction.execute()` populates `ActionResult.verdict` from review verdict
+- [x] `ReviewAction.execute()` populates `ActionResult.findings` from structured findings
+- [x] `ReviewAction.execute()` persists review file to disk
+- [x] `ReviewAction.execute()` returns `success=False` on any error (never raises)
+- [x] `ReviewAction` auto-registers at module import time
+- [x] `CheckpointAction` satisfies the `Action` protocol
+- [x] `CheckpointAction.action_type` returns `"checkpoint"`
+- [x] `CheckpointAction.validate()` rejects invalid trigger values
+- [x] `CheckpointAction.validate()` accepts valid triggers and empty config
+- [x] `CheckpointAction.execute()` returns `checkpoint="skipped"` when trigger is `never`
+- [x] `CheckpointAction.execute()` returns `checkpoint="paused"` when trigger is `always`
+- [x] `CheckpointAction.execute()` evaluates `on-concerns` correctly: fires on CONCERNS and FAIL, skips on PASS
+- [x] `CheckpointAction.execute()` evaluates `on-fail` correctly: fires on FAIL only, skips on PASS and CONCERNS
+- [x] `CheckpointAction.execute()` handles missing prior review verdict gracefully (no review = no fire, except `always`)
+- [x] `CheckpointAction` auto-registers at module import time
+- [x] `CheckpointTrigger` enum has values: `always`, `on-concerns`, `on-fail`, `never`
 
 ### Technical Requirements
 
-- [ ] pyright clean (0 errors) on both action modules
-- [ ] ruff clean on all modified files
-- [ ] All existing tests continue to pass
-- [ ] New tests mock all external boundaries (no real API calls, no real file I/O for review)
-- [ ] Review persistence logic extracted to shared module (not duplicated from CLI)
-- [ ] Both actions registered and visible in `list_actions()`
-- [ ] Integration tests verify coexistence with dispatch, cf-op, commit, devlog actions
+- [x] pyright clean (0 errors) on both action modules
+- [x] ruff clean on all modified files
+- [x] All existing tests continue to pass
+- [x] New tests mock all external boundaries (no real API calls, no real file I/O for review)
+- [x] Review persistence logic extracted to shared module (not duplicated from CLI)
+- [x] Both actions registered and visible in `list_actions()`
+- [x] Integration tests verify coexistence with dispatch, cf-op, commit, devlog actions
 
 ### Verification Walkthrough
 
@@ -554,15 +554,17 @@ print('valid:', a.validate({'template': 'code', 'cwd': '.'}))
 
 **5. Full test suite:**
 ```bash
-python -m pytest tests/pipeline/actions/test_review_action.py -v
-python -m pytest tests/pipeline/actions/test_checkpoint.py -v
-python -m pytest tests/pipeline/actions/test_registry_integration.py -v
-python -m pytest --tb=short -q  # all tests pass
-pyright src/squadron/pipeline/actions/review.py
-pyright src/squadron/pipeline/actions/checkpoint.py
-ruff check src/squadron/pipeline/actions/
+python -m pytest tests/pipeline/actions/test_review_action.py -v  # 21 passed
+python -m pytest tests/pipeline/actions/test_checkpoint.py -v  # 21 passed
+python -m pytest tests/pipeline/actions/test_registry_integration.py -v  # 8 passed
+python -m pytest --tb=short -q  # 884 passed
+pyright src/squadron/pipeline/actions/review.py  # 0 errors
+pyright src/squadron/pipeline/actions/checkpoint.py  # 0 errors
+ruff check src/squadron/pipeline/actions/  # All checks passed
 ```
 
+**Verified:** 2026-04-02. All steps pass as expected.
+
 ---
 
 ## Risk Assessment
diff --git a/project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md b/project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md
index 9dcc49a..4db0b39 100644
--- a/project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md
+++ b/project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md
@@ -6,8 +6,8 @@ lld: user/slices/146-slice.review-and-checkpoint-actions.md
 dependencies: [142, 143, 145]
 projectState: Pipeline scaffolding complete (slice 142). Structured review findings operational (slice 143). Dispatch action complete (slice 145). Utility actions operational (slice 144). Review system with templates, rules injection, and structured output from slices 105/128/143. Review file formatting in cli/commands/review.py as private functions.
 dateCreated: 20260401
-dateUpdated: 20260401
-status: not_started
+dateUpdated: 20260402
+status: complete
 ---
 
 ## Context Summary
@@ -25,21 +25,21 @@ status: not_started
 
 ### T1 — Extract Review File Persistence to Shared Module
 
-- [ ] **Extract `_format_review_markdown()`, `_save_review_file()`, and `_yaml_escape()` from `src/squadron/cli/commands/review.py` to `src/squadron/review/persistence.py`**
-  - [ ] Create `src/squadron/review/persistence.py` with:
+- [x] **Extract `_format_review_markdown()`, `_save_review_file()`, and `_yaml_escape()` from `src/squadron/cli/commands/review.py` to `src/squadron/review/persistence.py`**
+  - [x] Create `src/squadron/review/persistence.py` with:
     - `yaml_escape(text: str) -> str` (renamed from private `_yaml_escape`)
     - `format_review_markdown(result, review_type, slice_info, source_document, model) -> str` — pure formatting, returns markdown string with YAML frontmatter and findings
     - `save_review_file(content, review_type, slice_name, slice_index, cwd) -> Path | None` — writes to `project-documents/user/reviews/{index}-review.{type}.{slice_name}.md`, returns path
     - Move `SliceInfo` TypedDict to this module (used by both CLI and pipeline)
-  - [ ] Ensure function signatures accept all data needed without CLI-specific types (no `typer` imports, no `rich` imports)
-  - [ ] Update `src/squadron/cli/commands/review.py`:
+  - [x] Ensure function signatures accept all data needed without CLI-specific types (no `typer` imports, no `rich` imports)
+  - [x] Update `src/squadron/cli/commands/review.py`:
     - Import from `squadron.review.persistence` instead of using private functions
     - Remove the extracted private functions and `SliceInfo`
     - Verify calls still work with the new import paths
-  - [ ] Ensure `from __future__ import annotations` is present in new file
-  - [ ] Verify all existing tests pass (`python -m pytest --tb=short -q`)
-  - [ ] pyright clean on both `review/persistence.py` and `cli/commands/review.py`
-  - [ ] ruff clean on both files
+  - [x] Ensure `from __future__ import annotations` is present in new file
+  - [x] Verify all existing tests pass (`python -m pytest --tb=short -q`)
+  - [x] pyright clean on both `review/persistence.py` and `cli/commands/review.py`
+  - [x] ruff clean on both files
 
 **Commit**: `refactor: extract review file persistence to shared module`
 
@@ -47,16 +47,16 @@ status: not_started
 
 ### T2 — Review Persistence: Tests
 
-- [ ] **Create tests at `tests/review/test_persistence.py`**
-  - [ ] Test `yaml_escape` — escapes backslashes and double quotes
-  - [ ] Test `format_review_markdown` — produces valid YAML frontmatter with verdict, model, findings array
-  - [ ] Test `format_review_markdown` — structured findings appear in frontmatter with id, severity, category, summary, location
-  - [ ] Test `format_review_markdown` — handles missing `slice_info` gracefully (fewer frontmatter fields, still valid)
-  - [ ] Test `format_review_markdown` — includes prose body with finding descriptions
-  - [ ] Test `save_review_file` — writes file to correct path and returns `Path` (use `tmp_path`)
-  - [ ] Test `save_review_file` — creates parent directories if needed
-  - [ ] Test `save_review_file` — returns `None` on write failure (mock `Path.write_text` to raise `OSError`)
-  - [ ] All tests pass
+- [x] **Create tests at `tests/review/test_persistence.py`**
+  - [x] Test `yaml_escape` — escapes backslashes and double quotes
+  - [x] Test `format_review_markdown` — produces valid YAML frontmatter with verdict, model, findings array
+  - [x] Test `format_review_markdown` — structured findings appear in frontmatter with id, severity, category, summary, location
+  - [x] Test `format_review_markdown` — handles missing `slice_info` gracefully (fewer frontmatter fields, still valid)
+  - [x] Test `format_review_markdown` — includes prose body with finding descriptions
+  - [x] Test `save_review_file` — writes file to correct path and returns `Path` (use `tmp_path`)
+  - [x] Test `save_review_file` — creates parent directories if needed
+  - [x] Test `save_review_file` — returns `None` on write failure (mock `Path.write_text` to raise `OSError`)
+  - [x] All tests pass
 
 **Commit**: `test: add review persistence unit tests`
 
@@ -64,9 +64,9 @@ status: not_started
 
 ### T3 — CheckpointAction: Implementation
 
-- [ ] **Implement `CheckpointAction` in `src/squadron/pipeline/actions/checkpoint.py`**
-  - [ ] Define `CheckpointTrigger` StrEnum with values: `ALWAYS = "always"`, `ON_CONCERNS = "on-concerns"`, `ON_FAIL = "on-fail"`, `NEVER = "never"`
-  - [ ] Implement `CheckpointAction` class satisfying the `Action` protocol:
+- [x] **Implement `CheckpointAction` in `src/squadron/pipeline/actions/checkpoint.py`**
+  - [x] Define `CheckpointTrigger` StrEnum with values: `ALWAYS = "always"`, `ON_CONCERNS = "on-concerns"`, `ON_FAIL = "on-fail"`, `NEVER = "never"`
+  - [x] Implement `CheckpointAction` class satisfying the `Action` protocol:
     - `action_type` property returns `ActionType.CHECKPOINT` value (`"checkpoint"`)
     - `validate(config)`:
       - If `"trigger"` present, validate it's a valid `CheckpointTrigger` value
@@ -78,8 +78,8 @@ status: not_started
       - **Trigger evaluation**: implement `_should_fire(trigger, verdict)` per the trigger threshold table in the slice design
       - **Skip result**: return `ActionResult(success=True, action_type=self.action_type, outputs={"checkpoint": "skipped", "trigger": trigger.value, "verdict_seen": verdict or "none"})`
       - **Fire result**: return `ActionResult(success=True, action_type=self.action_type, outputs={"checkpoint": "paused", "reason": f"Review verdict: {verdict}", "trigger": trigger.value, "human_options": ["approve", "revise", "skip", "abort"]}, verdict=verdict, metadata={"step": context.step_name, "pipeline": context.pipeline_name})`
-  - [ ] Add module-level auto-registration: `register_action(ActionType.CHECKPOINT, CheckpointAction())`
-  - [ ] Ensure `from __future__ import annotations` is present
+  - [x] Add module-level auto-registration: `register_action(ActionType.CHECKPOINT, CheckpointAction())`
+  - [x] Ensure `from __future__ import annotations` is present
 
 **Commit**: `feat: implement CheckpointAction with trigger evaluation`
 
@@ -87,28 +87,28 @@ status: not_started
 
 ### T4 — CheckpointAction: Tests
 
-- [ ] **Create tests at `tests/pipeline/actions/test_checkpoint.py`**
-  - [ ] Test `action_type` property returns `"checkpoint"`
-  - [ ] Test `isinstance(CheckpointAction(), Action)` (protocol compliance)
-  - [ ] Test `CheckpointTrigger` enum has all four values with correct string representations
-  - [ ] Test `validate()` — empty config returns empty list
-  - [ ] Test `validate()` — valid trigger value returns empty list
-  - [ ] Test `validate()` — invalid trigger value returns `ValidationError`
-  - [ ] Test `execute()` — trigger `never` with any verdict returns `checkpoint="skipped"`
-  - [ ] Test `execute()` — trigger `always` with any verdict returns `checkpoint="paused"`
-  - [ ] Test `execute()` — trigger `always` with no prior verdict still fires
-  - [ ] Test `execute()` — trigger `on-concerns` + verdict `PASS` returns `checkpoint="skipped"`
-  - [ ] Test `execute()` — trigger `on-concerns` + verdict `CONCERNS` returns `checkpoint="paused"`
-  - [ ] Test `execute()` — trigger `on-concerns` + verdict `FAIL` returns `checkpoint="paused"`
-  - [ ] Test `execute()` — trigger `on-fail` + verdict `PASS` returns `checkpoint="skipped"`
-  - [ ] Test `execute()` — trigger `on-fail` + verdict `CONCERNS` returns `checkpoint="skipped"`
-  - [ ] Test `execute()` — trigger `on-fail` + verdict `FAIL` returns `checkpoint="paused"`
-  - [ ] Test `execute()` — no prior review verdict (empty `prior_outputs`) with `on-concerns` returns `checkpoint="skipped"`
-  - [ ] Test `execute()` — default trigger (no trigger in params) behaves as `on-concerns`
-  - [ ] Test `execute()` — fired result includes `human_options`, `reason`, and `verdict`
-  - [ ] Test `execute()` — fired result metadata includes `step` and `pipeline` names
-  - [ ] Create `_make_context` helper to build `ActionContext` with configurable prior outputs and params
-  - [ ] All tests pass, pyright clean on the action module
+- [x] **Create tests at `tests/pipeline/actions/test_checkpoint.py`**
+  - [x] Test `action_type` property returns `"checkpoint"`
+  - [x] Test `isinstance(CheckpointAction(), Action)` (protocol compliance)
+  - [x] Test `CheckpointTrigger` enum has all four values with correct string representations
+  - [x] Test `validate()` — empty config returns empty list
+  - [x] Test `validate()` — valid trigger value returns empty list
+  - [x] Test `validate()` — invalid trigger value returns `ValidationError`
+  - [x] Test `execute()` — trigger `never` with any verdict returns `checkpoint="skipped"`
+  - [x] Test `execute()` — trigger `always` with any verdict returns `checkpoint="paused"`
+  - [x] Test `execute()` — trigger `always` with no prior verdict still fires
+  - [x] Test `execute()` — trigger `on-concerns` + verdict `PASS` returns `checkpoint="skipped"`
+  - [x] Test `execute()` — trigger `on-concerns` + verdict `CONCERNS` returns `checkpoint="paused"`
+  - [x] Test `execute()` — trigger `on-concerns` + verdict `FAIL` returns `checkpoint="paused"`
+  - [x] Test `execute()` — trigger `on-fail` + verdict `PASS` returns `checkpoint="skipped"`
+  - [x] Test `execute()` — trigger `on-fail` + verdict `CONCERNS` returns `checkpoint="skipped"`
+  - [x] Test `execute()` — trigger `on-fail` + verdict `FAIL` returns `checkpoint="paused"`
+  - [x] Test `execute()` — no prior review verdict (empty `prior_outputs`) with `on-concerns` returns `checkpoint="skipped"`
+  - [x] Test `execute()` — default trigger (no trigger in params) behaves as `on-concerns`
+  - [x] Test `execute()` — fired result includes `human_options`, `reason`, and `verdict`
+  - [x] Test `execute()` — fired result metadata includes `step` and `pipeline` names
+  - [x] Create `_make_context` helper to build `ActionContext` with configurable prior outputs and params
+  - [x] All tests pass, pyright clean on the action module
 
 **Commit**: `test: add CheckpointAction unit tests`
 
@@ -116,8 +116,8 @@ status: not_started
 
 ### T5 — ReviewAction: Implementation
 
-- [ ] **Implement `ReviewAction` in `src/squadron/pipeline/actions/review.py`**
-  - [ ] Implement `ReviewAction` class satisfying the `Action` protocol:
+- [x] **Implement `ReviewAction` in `src/squadron/pipeline/actions/review.py`**
+  - [x] Implement `ReviewAction` class satisfying the `Action` protocol:
     - `action_type` property returns `ActionType.REVIEW` value (`"review"`)
     - `validate(config)` checks:
       - `"template"` key present in config — return `ValidationError(field="template", ...)` if missing
@@ -132,9 +132,9 @@ status: not_started
       - **Execute review**: call `run_review_with_profile(template, inputs, profile=..., model=..., rules_content=...)`
       - **File persistence**: call persistence functions from `review/persistence.py` to save review file; wrap in try/except and log warning on failure (non-fatal)
       - **Result mapping**: return `ActionResult(success=True, action_type=self.action_type, outputs={"response": result.raw_output, "review_file": str(path)}, verdict=result.verdict.value, findings=[f.__dict__ for f in result.structured_findings], metadata={"model": model_id, "profile": profile_name, "template": template_name})`
-  - [ ] Error handling — same pattern as dispatch: catch known exceptions (`ModelResolutionError`, `ModelPoolNotImplemented`, `KeyError`) and unexpected `Exception`, return `ActionResult(success=False, ...)`; log unexpected errors at ERROR level
-  - [ ] Add module-level auto-registration: `register_action(ActionType.REVIEW, ReviewAction())`
-  - [ ] Ensure `from __future__ import annotations` is present
+  - [x] Error handling — same pattern as dispatch: catch known exceptions (`ModelResolutionError`, `ModelPoolNotImplemented`, `KeyError`) and unexpected `Exception`, return `ActionResult(success=False, ...)`; log unexpected errors at ERROR level
+  - [x] Add module-level auto-registration: `register_action(ActionType.REVIEW, ReviewAction())`
+  - [x] Ensure `from __future__ import annotations` is present
 
 **Commit**: `feat: implement ReviewAction for pipeline review gates`
 
@@ -142,31 +142,31 @@ status: not_started
 
 ### T6 — ReviewAction: Tests
 
-- [ ] **Create tests at `tests/pipeline/actions/test_review_action.py`**
-  - [ ] Test `action_type` property returns `"review"`
-  - [ ] Test `isinstance(ReviewAction(), Action)` (protocol compliance)
-  - [ ] Test `validate()` — missing `template` returns error with `field="template"`
-  - [ ] Test `validate()` — missing `cwd` (but template present) returns error with `field="cwd"`
-  - [ ] Test `validate()` — both `template` and `cwd` present returns empty list
-  - [ ] Test `execute()` — happy path: template resolved, review executed, result mapped correctly
-  - [ ] Test `execute()` — `ActionResult.verdict` populated from `ReviewResult.verdict.value`
-  - [ ] Test `execute()` — `ActionResult.findings` populated from `ReviewResult.structured_findings` as dicts
-  - [ ] Test `execute()` — `ActionResult.outputs["response"]` contains raw review output
-  - [ ] Test `execute()` — model resolution: `resolver.resolve()` called with `action_model` and `step_model`
-  - [ ] Test `execute()` — profile from alias: alias-derived profile used when no explicit `profile` param
-  - [ ] Test `execute()` — profile override: explicit `profile` param takes precedence
-  - [ ] Test `execute()` — default profile: `ProfileName.SDK` when no alias profile and no explicit profile
-  - [ ] Test `execute()` — template inputs: `diff`, `files`, `against` keys passed through to review inputs
-  - [ ] Test `execute()` — review file persisted (mock persistence, verify called)
-  - [ ] Test `execute()` — persistence failure is non-fatal: logs warning, still returns successful result
-  - [ ] Test `execute()` — template not found (KeyError from `get_template`) returns `success=False`
-  - [ ] Test `execute()` — `ModelResolutionError` returns `success=False`
-  - [ ] Test `execute()` — review execution error returns `success=False`, logged at ERROR
-  - [ ] Test `execute()` — metadata includes model, profile, template name
-  - [ ] Mock boundaries: `get_template()`, `run_review_with_profile()`, `ModelResolver`, persistence functions
-  - [ ] Create `_make_context` helper for building `ActionContext` with review-specific params
-  - [ ] Create `_make_review_result` helper for building canned `ReviewResult` with structured findings
-  - [ ] All tests pass, pyright clean on the action module
+- [x] **Create tests at `tests/pipeline/actions/test_review_action.py`**
+  - [x] Test `action_type` property returns `"review"`
+  - [x] Test `isinstance(ReviewAction(), Action)` (protocol compliance)
+  - [x] Test `validate()` — missing `template` returns error with `field="template"`
+  - [x] Test `validate()` — missing `cwd` (but template present) returns error with `field="cwd"`
+  - [x] Test `validate()` — both `template` and `cwd` present returns empty list
+  - [x] Test `execute()` — happy path: template resolved, review executed, result mapped correctly
+  - [x] Test `execute()` — `ActionResult.verdict` populated from `ReviewResult.verdict.value`
+  - [x] Test `execute()` — `ActionResult.findings` populated from `ReviewResult.structured_findings` as dicts
+  - [x] Test `execute()` — `ActionResult.outputs["response"]` contains raw review output
+  - [x] Test `execute()` — model resolution: `resolver.resolve()` called with `action_model` and `step_model`
+  - [x] Test `execute()` — profile from alias: alias-derived profile used when no explicit `profile` param
+  - [x] Test `execute()` — profile override: explicit `profile` param takes precedence
+  - [x] Test `execute()` — default profile: `ProfileName.SDK` when no alias profile and no explicit profile
+  - [x] Test `execute()` — template inputs: `diff`, `files`, `against` keys passed through to review inputs
+  - [x] Test `execute()` — review file persisted (mock persistence, verify called)
+  - [x] Test `execute()` — persistence failure is non-fatal: logs warning, still returns successful result
+  - [x] Test `execute()` — template not found (KeyError from `get_template`) returns `success=False`
+  - [x] Test `execute()` — `ModelResolutionError` returns `success=False`
+  - [x] Test `execute()` — review execution error returns `success=False`, logged at ERROR
+  - [x] Test `execute()` — metadata includes model, profile, template name
+  - [x] Mock boundaries: `get_template()`, `run_review_with_profile()`, `ModelResolver`, persistence functions
+  - [x] Create `_make_context` helper for building `ActionContext` with review-specific params
+  - [x] Create `_make_review_result` helper for building canned `ReviewResult` with structured findings
+  - [x] All tests pass, pyright clean on the action module
 
 **Commit**: `test: add ReviewAction unit tests`
 
@@ -174,14 +174,14 @@ status: not_started
 
 ### T7 — Action Registration and Integration Verification
 
-- [ ] **Verify both actions register correctly alongside existing actions**
-  - [ ] Update `tests/pipeline/actions/test_registry_integration.py`:
+- [x] **Verify both actions register correctly alongside existing actions**
+  - [x] Update `tests/pipeline/actions/test_registry_integration.py`:
     - Add imports for `squadron.pipeline.actions.review` and `squadron.pipeline.actions.checkpoint`
     - Add `"review"` and `"checkpoint"` to `test_list_actions_includes_all_registered()`
     - Add test: `get_action("review")` returns a `ReviewAction` instance
     - Add test: `get_action("checkpoint")` returns a `CheckpointAction` instance
-  - [ ] Confirm no import errors or circular dependencies
-  - [ ] All existing tests still pass (`python -m pytest --tb=short -q`)
+  - [x] Confirm no import errors or circular dependencies
+  - [x] All existing tests still pass (`python -m pytest --tb=short -q`)
 
 **Commit**: `test: add review and checkpoint to action registry integration tests`
 
@@ -189,19 +189,19 @@ status: not_started
 
 ### T8 — Full Verification and Closeout
 
-- [ ] **Run full verification suite**
-  - [ ] `python -m pytest --tb=short -q` — all tests pass
-  - [ ] `pyright src/squadron/pipeline/actions/review.py` — 0 errors
-  - [ ] `pyright src/squadron/pipeline/actions/checkpoint.py` — 0 errors
-  - [ ] `pyright src/squadron/review/persistence.py` — 0 errors
-  - [ ] `ruff check src/squadron/pipeline/actions/review.py src/squadron/pipeline/actions/checkpoint.py src/squadron/review/persistence.py` — 0 warnings
-  - [ ] `ruff format --check src/squadron/pipeline/actions/ src/squadron/review/persistence.py` — no formatting issues
-  - [ ] Run the verification walkthrough from the slice design document
-  - [ ] Update slice design verification walkthrough with actual commands and output
-  - [ ] Check off success criteria in slice design
-  - [ ] Mark slice 146 as complete in slice design frontmatter
-  - [ ] Mark slice 146 as complete in slice plan (`140-slices.pipeline-foundation.md`)
-  - [ ] Update CHANGELOG.md with slice 146 entries
-  - [ ] Update DEVLOG.md with implementation completion entry
+- [x] **Run full verification suite**
+  - [x] `python -m pytest --tb=short -q` — all tests pass
+  - [x] `pyright src/squadron/pipeline/actions/review.py` — 0 errors
+  - [x] `pyright src/squadron/pipeline/actions/checkpoint.py` — 0 errors
+  - [x] `pyright src/squadron/review/persistence.py` — 0 errors
+  - [x] `ruff check src/squadron/pipeline/actions/review.py src/squadron/pipeline/actions/checkpoint.py src/squadron/review/persistence.py` — 0 warnings
+  - [x] `ruff format --check src/squadron/pipeline/actions/ src/squadron/review/persistence.py` — no formatting issues
+  - [x] Run the verification walkthrough from the slice design document
+  - [x] Update slice design verification walkthrough with actual commands and output
+  - [x] Check off success criteria in slice design
+  - [x] Mark slice 146 as complete in slice design frontmatter
+  - [x] Mark slice 146 as complete in slice plan (`140-slices.pipeline-foundation.md`)
+  - [x] Update CHANGELOG.md with slice 146 entries
+  - [x] Update DEVLOG.md with implementation completion entry
 
 **Commit**: `docs: mark slice 146 review and checkpoint actions complete`
diff --git a/src/squadron/cli/commands/review.py b/src/squadron/cli/commands/review.py
index 1d09353..e7fe8fc 100644
--- a/src/squadron/cli/commands/review.py
+++ b/src/squadron/cli/commands/review.py
@@ -5,7 +5,6 @@ from __future__ import annotations
 import asyncio
 import json
 from pathlib import Path
-from typing import TypedDict
 
 import typer
 from openai import RateLimitError
@@ -23,6 +22,7 @@ from squadron.integrations.context_forge import (
 from squadron.models.aliases import resolve_model_alias
 from squadron.review.git_utils import resolve_slice_diff_range
 from squadron.review.models import ReviewResult, Severity, Verdict
+from squadron.review.persistence import SliceInfo, save_review_result
 from squadron.review.review_client import run_review_with_profile
 from squadron.review.rules import (
     detect_languages_from_paths,
@@ -138,131 +138,6 @@ def _write_file(result: ReviewResult, output_path: str | None) -> None:
     rprint(f"[green]Review result written to {path}[/green]")
 
 
-# ---------------------------------------------------------------------------
-# Review file persistence
-# ---------------------------------------------------------------------------
-
-
-def _yaml_escape(text: str) -> str:
-    """Escape double quotes in a string for YAML double-quoted values."""
-    return text.replace("\\", "\\\\").replace('"', '\\"')
-
-
-def _format_review_markdown(
-    result: ReviewResult,
-    review_type: str,
-    slice_info: SliceInfo,
-    input_file: str | None = None,
-) -> str:
-    """Format a ReviewResult as markdown with YAML frontmatter."""
-    today = result.timestamp.strftime("%Y%m%d")
-    source_doc = input_file or slice_info.get("design_file") or ""
-    lines = [
-        "---",
-        "docType: review",
-        "layer: project",
-        f"reviewType: {review_type}",
-        f"slice: {slice_info['slice_name']}",
-        "project: squadron",
-        f"verdict: {result.verdict.value}",
-        f"sourceDocument: {source_doc}",
-        f"aiModel: {result.model or 'unknown'}",
-        "status: complete",
-        f"dateCreated: {today}",
-        f"dateUpdated: {today}",
-    ]
-
-    if result.findings:
-        lines.append("findings:")
-        for sf in result.structured_findings:
-            lines.append(f"  - id: {sf.id}")
-            lines.append(f"    severity: {sf.severity}")
-            lines.append(f"    category: {sf.category}")
-            lines.append(f'    summary: "{_yaml_escape(sf.summary)}"')
-            if sf.location:
-                lines.append(f"    location: {sf.location}")
-
-    lines.append("---")
-    lines.append("")
-    lines.append(f"# Review: {review_type} — slice {slice_info['index']}")
-    lines.append("")
-    lines.append(f"**Verdict:** {result.verdict.value}")
-    lines.append(f"**Model:** {result.model or 'default'}")
-    lines.append("")
-
-    if result.findings:
-        lines.append("## Findings")
-        lines.append("")
-        for finding in result.findings:
-            lines.append(f"### [{finding.severity.value}] {finding.title}")
-            if finding.description:
-                lines.append("")
-                lines.append(finding.description)
-            if finding.file_ref:
-                lines.append(f"\n-> {finding.file_ref}")
-            lines.append("")
-    else:
-        lines.append("No specific findings.")
-        lines.append("")
-
-    # Debug appendix — included when prompt capture fields are populated
-    if result.system_prompt is not None:
-        lines.append("---")
-        lines.append("")
-        lines.append("## Debug: Prompt & Response")
-        lines.append("")
-        lines.append("### System Prompt")
-        lines.append("")
-        lines.append(result.system_prompt)
-        lines.append("")
-        lines.append("### User Prompt")
-        lines.append("")
-        lines.append(result.user_prompt or "")
-        lines.append("")
-        lines.append("### Rules Injected")
-        lines.append("")
-        lines.append(result.rules_content_used or "None")
-        lines.append("")
-        lines.append("### Raw Response")
-        lines.append("")
-        lines.append(result.raw_output)
-        lines.append("")
-
-    return "\n".join(lines)
-
-
-_REVIEWS_DIR = Path("project-documents/user/reviews")
-
-
-def _save_review_file(
-    result: ReviewResult,
-    review_type: str,
-    slice_info: SliceInfo,
-    as_json: bool = False,
-    reviews_dir: Path | None = None,
-    input_file: str | None = None,
-) -> Path:
-    """Save review output to the reviews directory.
-
-    Returns the path of the saved file.
-    """
-    target = reviews_dir or _REVIEWS_DIR
-    target.mkdir(parents=True, exist_ok=True)
-
-    base = f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"
-
-    if as_json:
-        path = target / f"{base}.json"
-        path.write_text(json.dumps(result.to_dict(), indent=2))
-    else:
-        path = target / f"{base}.md"
-        path.write_text(
-            _format_review_markdown(result, review_type, slice_info, input_file)
-        )
-
-    return path
-
-
 # ---------------------------------------------------------------------------
 # Shared helpers
 # ---------------------------------------------------------------------------
@@ -341,17 +216,6 @@ def _resolve_arch_file(num: str) -> str:
     return str(matches[0])
 
 
-class SliceInfo(TypedDict):
-    """Resolved slice metadata from Context-Forge."""
-
-    index: int
-    name: str
-    slice_name: str
-    design_file: str | None
-    task_files: list[str]
-    arch_file: str
-
-
 def _resolve_slice_number(num: str) -> SliceInfo:
     """Resolve a bare slice number to file paths via Context-Forge.
 
@@ -633,7 +497,7 @@ def review_slice(
     )
 
     if slice_info and not no_save:
-        path = _save_review_file(
+        path = save_review_result(
             result, "slice", slice_info, as_json=use_json, input_file=input_file
         )
         rprint(f"[green]Saved review to {path}[/green]")
@@ -717,7 +581,7 @@ def review_arch(
             task_files=[],
             arch_file=input_file,
         )
-        path = _save_review_file(
+        path = save_review_result(
             result, "arch", arch_slice_info, as_json=use_json, input_file=input_file
         )
         rprint(f"[green]Saved review to {path}[/green]")
@@ -802,7 +666,7 @@ def review_tasks(
     )
 
     if slice_info and not no_save:
-        path = _save_review_file(
+        path = save_review_result(
             result, "tasks", slice_info, as_json=use_json, input_file=input_file
         )
         rprint(f"[green]Saved review to {path}[/green]")
@@ -920,7 +784,7 @@ def review_code(
     )
 
     if slice_info and not no_save:
-        path = _save_review_file(result, "code", slice_info, as_json=use_json)
+        path = save_review_result(result, "code", slice_info, as_json=use_json)
         rprint(f"[green]Saved review to {path}[/green]")
 
     if result.verdict == Verdict.FAIL:
diff --git a/src/squadron/pipeline/actions/checkpoint.py b/src/squadron/pipeline/actions/checkpoint.py
index 3608271..243a44a 100644
--- a/src/squadron/pipeline/actions/checkpoint.py
+++ b/src/squadron/pipeline/actions/checkpoint.py
@@ -1,4 +1,119 @@
-"""Checkpoint action — saves pipeline state at a named point.
+"""Checkpoint action — quality gate that evaluates prior review verdicts."""
 
-# TODO: slice 146
-"""
+from __future__ import annotations
+
+from enum import StrEnum
+
+from squadron.pipeline.actions import ActionType, register_action
+from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+
+
+class CheckpointTrigger(StrEnum):
+    """When a checkpoint should fire based on the prior review verdict."""
+
+    ALWAYS = "always"
+    ON_CONCERNS = "on-concerns"
+    ON_FAIL = "on-fail"
+    NEVER = "never"
+
+
+_TRIGGER_THRESHOLDS: dict[CheckpointTrigger, set[str]] = {
+    CheckpointTrigger.ALWAYS: set(),  # fires regardless
+    CheckpointTrigger.ON_CONCERNS: {"CONCERNS", "FAIL"},
+    CheckpointTrigger.ON_FAIL: {"FAIL"},
+    CheckpointTrigger.NEVER: set(),  # never fires
+}
+
+
+def _find_review_verdict(prior_outputs: dict[str, ActionResult]) -> str | None:
+    """Find the most recent review verdict from prior action outputs.
+
+    Iterates prior_outputs in reverse insertion order and returns the
+    first ``result.verdict`` that is not ``None``.
+    """
+    for result in reversed(list(prior_outputs.values())):
+        if result.verdict is not None:
+            return result.verdict
+    return None
+
+
+def _should_fire(trigger: CheckpointTrigger, verdict: str | None) -> bool:
+    """Evaluate whether the checkpoint should fire given a trigger and verdict."""
+    if trigger == CheckpointTrigger.ALWAYS:
+        return True
+    if trigger == CheckpointTrigger.NEVER:
+        return False
+    if verdict is None:
+        return False
+    return verdict in _TRIGGER_THRESHOLDS[trigger]
+
+
+class CheckpointAction:
+    """Pipeline action that gates execution based on prior review verdicts.
+
+    Evaluates a trigger condition against the most recent review verdict
+    from ``context.prior_outputs``. Returns data indicating whether the
+    pipeline should pause — the executor (slice 149) interprets the result.
+    """
+
+    @property
+    def action_type(self) -> str:
+        return ActionType.CHECKPOINT
+
+    def validate(self, config: dict[str, object]) -> list[ValidationError]:
+        trigger_val = config.get("trigger")
+        if trigger_val is not None:
+            try:
+                CheckpointTrigger(str(trigger_val))
+            except ValueError:
+                valid = [t.value for t in CheckpointTrigger]
+                return [
+                    ValidationError(
+                        field="trigger",
+                        message=(
+                            f"Invalid trigger value '{trigger_val}'. "
+                            f"Valid values: {valid}"
+                        ),
+                        action_type=ActionType.CHECKPOINT,
+                    )
+                ]
+        return []
+
+    async def execute(self, context: ActionContext) -> ActionResult:
+        # Trigger resolution
+        trigger_str = str(context.params.get("trigger", CheckpointTrigger.ON_CONCERNS))
+        trigger = CheckpointTrigger(trigger_str)
+
+        # Prior verdict lookup
+        verdict = _find_review_verdict(context.prior_outputs)
+
+        # Trigger evaluation
+        if _should_fire(trigger, verdict):
+            return ActionResult(
+                success=True,
+                action_type=self.action_type,
+                outputs={
+                    "checkpoint": "paused",
+                    "reason": f"Review verdict: {verdict}",
+                    "trigger": trigger.value,
+                    "human_options": ["approve", "revise", "skip", "abort"],
+                },
+                verdict=verdict,
+                metadata={
+                    "step": context.step_name,
+                    "pipeline": context.pipeline_name,
+                },
+            )
+
+        return ActionResult(
+            success=True,
+            action_type=self.action_type,
+            outputs={
+                "checkpoint": "skipped",
+                "trigger": trigger.value,
+                "verdict_seen": verdict or "none",
+            },
+        )
+
+
+register_action(ActionType.CHECKPOINT, CheckpointAction())
diff --git a/src/squadron/pipeline/actions/review.py b/src/squadron/pipeline/actions/review.py
index fe90a57..66bc8bb 100644
--- a/src/squadron/pipeline/actions/review.py
+++ b/src/squadron/pipeline/actions/review.py
@@ -1,4 +1,161 @@
-"""Review action — runs a structured review against a target.
+"""Review action — runs a structured review within a pipeline step."""
 
-# TODO: slice 146
-"""
+from __future__ import annotations
+
+import logging
+
+from squadron.pipeline.actions import ActionType, register_action
+from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+from squadron.pipeline.resolver import ModelPoolNotImplemented, ModelResolutionError
+from squadron.providers.base import ProfileName
+from squadron.review.persistence import (
+    format_review_markdown,
+    save_review_file,
+)
+from squadron.review.review_client import run_review_with_profile
+from squadron.review.templates import get_template, load_all_templates
+
+_logger = logging.getLogger(__name__)
+
+_INPUT_PASSTHROUGH_KEYS = ("diff", "files", "against", "input")
+
+
+class ReviewAction:
+    """Pipeline action that delegates to the review subsystem.
+
+    Resolves template, model, and profile from ``context.params``,
+    executes the review, persists the output file, and maps the
+    ``ReviewResult`` to an ``ActionResult`` with verdict and findings.
+    """
+
+    @property
+    def action_type(self) -> str:
+        return ActionType.REVIEW
+
+    def validate(self, config: dict[str, object]) -> list[ValidationError]:
+        errors: list[ValidationError] = []
+        if "template" not in config:
+            errors.append(
+                ValidationError(
+                    field="template",
+                    message="'template' is required for review action",
+                    action_type=ActionType.REVIEW,
+                )
+            )
+        if "cwd" not in config:
+            errors.append(
+                ValidationError(
+                    field="cwd",
+                    message="'cwd' is required for review action",
+                    action_type=ActionType.REVIEW,
+                )
+            )
+        return errors
+
+    async def execute(self, context: ActionContext) -> ActionResult:
+        try:
+            return await self._review(context)
+        except (ModelResolutionError, ModelPoolNotImplemented, KeyError) as exc:
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=str(exc),
+            )
+        except Exception as exc:
+            _logger.exception("review: unexpected error in step %s", context.step_name)
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={},
+                error=str(exc),
+            )
+
+    async def _review(self, context: ActionContext) -> ActionResult:
+        # Template resolution
+        load_all_templates()
+        template_name = str(context.params["template"])
+        template = get_template(template_name)
+        if template is None:
+            raise KeyError(f"Review template '{template_name}' not found")
+
+        # Model resolution — same pattern as dispatch
+        action_model = (
+            str(context.params["model"]) if "model" in context.params else None
+        )
+        step_model = (
+            str(context.params["step_model"])
+            if "step_model" in context.params
+            else None
+        )
+        model_id, alias_profile = context.resolver.resolve(action_model, step_model)
+
+        # Profile resolution — explicit param → alias-derived → SDK default
+        profile_name = (
+            str(context.params["profile"])
+            if "profile" in context.params
+            else alias_profile or ProfileName.SDK
+        )
+
+        # Build review inputs
+        cwd = str(context.params["cwd"])
+        inputs: dict[str, str] = {"cwd": cwd}
+        for key in _INPUT_PASSTHROUGH_KEYS:
+            if key in context.params:
+                inputs[key] = str(context.params[key])
+
+        # Rules content
+        rules_content: str | None = None
+        if "rules_content" in context.params:
+            rules_content = str(context.params["rules_content"])
+
+        # Execute review
+        result = await run_review_with_profile(
+            template,
+            inputs,
+            profile=profile_name,
+            model=model_id,
+            rules_content=rules_content,
+        )
+
+        # File persistence (non-fatal)
+        review_file_path: str | None = None
+        try:
+            md_content = format_review_markdown(
+                result, template_name, source_document=inputs.get("input")
+            )
+            path = save_review_file(
+                md_content,
+                template_name,
+                context.step_name,
+                context.step_index,
+                cwd=cwd,
+            )
+            if path is not None:
+                review_file_path = str(path)
+        except Exception:
+            _logger.warning(
+                "review: failed to persist review file for step %s",
+                context.step_name,
+            )
+
+        # Map ReviewResult → ActionResult
+        outputs: dict[str, object] = {"response": result.raw_output}
+        if review_file_path is not None:
+            outputs["review_file"] = review_file_path
+
+        return ActionResult(
+            success=True,
+            action_type=self.action_type,
+            outputs=outputs,
+            verdict=result.verdict.value,
+            findings=[sf.__dict__ for sf in result.structured_findings],
+            metadata={
+                "model": model_id,
+                "profile": profile_name,
+                "template": template_name,
+            },
+        )
+
+
+register_action(ActionType.REVIEW, ReviewAction())
diff --git a/src/squadron/review/persistence.py b/src/squadron/review/persistence.py
new file mode 100644
index 0000000..7b7cfd1
--- /dev/null
+++ b/src/squadron/review/persistence.py
@@ -0,0 +1,205 @@
+"""Review file persistence — formatting and saving review output files.
+
+Shared between CLI review commands and pipeline review actions.
+"""
+
+from __future__ import annotations
+
+import json
+import logging
+from pathlib import Path
+from typing import TypedDict
+
+from squadron.review.models import ReviewResult
+
+_logger = logging.getLogger(__name__)
+
+_REVIEWS_DIR = Path("project-documents/user/reviews")
+
+
+class SliceInfo(TypedDict):
+    """Resolved slice metadata from Context-Forge."""
+
+    index: int
+    name: str
+    slice_name: str
+    design_file: str | None
+    task_files: list[str]
+    arch_file: str
+
+
+def yaml_escape(text: str) -> str:
+    """Escape backslashes and double quotes for YAML double-quoted values."""
+    return text.replace("\\", "\\\\").replace('"', '\\"')
+
+
+def format_review_markdown(
+    result: ReviewResult,
+    review_type: str,
+    slice_info: SliceInfo | None = None,
+    source_document: str | None = None,
+    model: str | None = None,
+) -> str:
+    """Format a ReviewResult as markdown with YAML frontmatter.
+
+    Args:
+        result: The review result to format.
+        review_type: Review type label (e.g. ``"slice"``, ``"code"``).
+        slice_info: Optional slice metadata for frontmatter fields.
+        source_document: Explicit source document path; falls back to
+            ``slice_info["design_file"]`` when not provided.
+        model: Explicit model name; falls back to ``result.model``.
+    """
+    today = result.timestamp.strftime("%Y%m%d")
+    resolved_model = model or result.model or "unknown"
+
+    # Source document resolution
+    if source_document is None and slice_info is not None:
+        source_document = slice_info.get("design_file") or ""
+    source_doc = source_document or ""
+
+    # Slice-derived fields
+    slice_name = slice_info["slice_name"] if slice_info else "unknown"
+    slice_index = slice_info["index"] if slice_info else 0
+
+    lines = [
+        "---",
+        "docType: review",
+        "layer: project",
+        f"reviewType: {review_type}",
+        f"slice: {slice_name}",
+        "project: squadron",
+        f"verdict: {result.verdict.value}",
+        f"sourceDocument: {source_doc}",
+        f"aiModel: {resolved_model}",
+        "status: complete",
+        f"dateCreated: {today}",
+        f"dateUpdated: {today}",
+    ]
+
+    if result.findings:
+        lines.append("findings:")
+        for sf in result.structured_findings:
+            lines.append(f"  - id: {sf.id}")
+            lines.append(f"    severity: {sf.severity}")
+            lines.append(f"    category: {sf.category}")
+            lines.append(f'    summary: "{yaml_escape(sf.summary)}"')
+            if sf.location:
+                lines.append(f"    location: {sf.location}")
+
+    lines.append("---")
+    lines.append("")
+    lines.append(f"# Review: {review_type} — slice {slice_index}")
+    lines.append("")
+    lines.append(f"**Verdict:** {result.verdict.value}")
+    lines.append(f"**Model:** {resolved_model}")
+    lines.append("")
+
+    if result.findings:
+        lines.append("## Findings")
+        lines.append("")
+        for finding in result.findings:
+            lines.append(f"### [{finding.severity.value}] {finding.title}")
+            if finding.description:
+                lines.append("")
+                lines.append(finding.description)
+            if finding.file_ref:
+                lines.append(f"\n-> {finding.file_ref}")
+            lines.append("")
+    else:
+        lines.append("No specific findings.")
+        lines.append("")
+
+    # Debug appendix — included when prompt capture fields are populated
+    if result.system_prompt is not None:
+        lines.append("---")
+        lines.append("")
+        lines.append("## Debug: Prompt & Response")
+        lines.append("")
+        lines.append("### System Prompt")
+        lines.append("")
+        lines.append(result.system_prompt)
+        lines.append("")
+        lines.append("### User Prompt")
+        lines.append("")
+        lines.append(result.user_prompt or "")
+        lines.append("")
+        lines.append("### Rules Injected")
+        lines.append("")
+        lines.append(result.rules_content_used or "None")
+        lines.append("")
+        lines.append("### Raw Response")
+        lines.append("")
+        lines.append(result.raw_output)
+        lines.append("")
+
+    return "\n".join(lines)
+
+
+def save_review_file(
+    content: str,
+    review_type: str,
+    slice_name: str,
+    slice_index: int,
+    cwd: str | None = None,
+    as_json: bool = False,
+) -> Path | None:
+    """Write review content to the reviews directory.
+
+    Args:
+        content: Pre-formatted review content (markdown or JSON string).
+        review_type: Review type label (e.g. ``"slice"``, ``"code"``).
+        slice_name: Kebab-case slice name for the filename.
+        slice_index: Numeric slice index for the filename prefix.
+        cwd: Working directory root; reviews dir is relative to this.
+        as_json: If True, use ``.json`` extension instead of ``.md``.
+
+    Returns:
+        The path of the saved file, or ``None`` on write failure.
+    """
+    base_dir = Path(cwd) if cwd else Path(".")
+    target = base_dir / _REVIEWS_DIR
+    ext = "json" if as_json else "md"
+    filename = f"{slice_index}-review.{review_type}.{slice_name}.{ext}"
+    path = target / filename
+
+    try:
+        path.parent.mkdir(parents=True, exist_ok=True)
+        path.write_text(content)
+    except OSError:
+        _logger.warning("Failed to save review file: %s", path)
+        return None
+
+    return path
+
+
+def save_review_result(
+    result: ReviewResult,
+    review_type: str,
+    slice_info: SliceInfo,
+    as_json: bool = False,
+    reviews_dir: Path | None = None,
+    input_file: str | None = None,
+) -> Path:
+    """Save a ReviewResult to the reviews directory (CLI compatibility).
+
+    This preserves the interface used by ``cli/commands/review.py``.
+    Returns the path of the saved file.
+    """
+    target = reviews_dir or _REVIEWS_DIR
+    target.mkdir(parents=True, exist_ok=True)
+
+    base = f"{slice_info['index']}-review.{review_type}.{slice_info['slice_name']}"
+
+    if as_json:
+        path = target / f"{base}.json"
+        path.write_text(json.dumps(result.to_dict(), indent=2))
+    else:
+        path = target / f"{base}.md"
+        path.write_text(
+            format_review_markdown(
+                result, review_type, slice_info, source_document=input_file
+            )
+        )
+
+    return path
diff --git a/tests/cli/test_review_format.py b/tests/cli/test_review_format.py
index cfdc23f..550d202 100644
--- a/tests/cli/test_review_format.py
+++ b/tests/cli/test_review_format.py
@@ -6,17 +6,17 @@ from datetime import datetime
 
 import yaml
 
-from squadron.cli.commands.review import (
-    SliceInfo,
-    _format_review_markdown,
-    _yaml_escape,
-)
 from squadron.review.models import (
     ReviewFinding,
     ReviewResult,
     Severity,
     Verdict,
 )
+from squadron.review.persistence import (
+    SliceInfo,
+    format_review_markdown,
+    yaml_escape,
+)
 
 SLICE_INFO: SliceInfo = {
     "index": 143,
@@ -76,12 +76,12 @@ class TestFrontmatterFindings:
 
     def test_findings_block_present(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert "findings:" in md
 
     def test_finding_has_required_fields(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert "  - id: F001" in md
         assert "    severity: concern" in md
         assert "    category: error-handling" in md
@@ -89,12 +89,12 @@ class TestFrontmatterFindings:
 
     def test_finding_with_location(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert "    location: src/foo.py:10" in md
 
     def test_finding_without_location_omits_field(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         # Second finding (F002) has no location — check it's not emitted
         lines = md.split("\n")
         f002_idx = next(i for i, line in enumerate(lines) if "id: F002" in line)
@@ -125,12 +125,12 @@ class TestFrontmatterFindings:
             timestamp=datetime(2026, 3, 30, 12, 0, 0),
             model="opus",
         )
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert r'summary: "Variable \"x\" unclear"' in md
 
     def test_frontmatter_is_valid_yaml(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         # Extract frontmatter between --- markers
         parts = md.split("---")
         frontmatter_text = parts[1]
@@ -144,24 +144,24 @@ class TestFrontmatterFindings:
 
     def test_no_findings_block_when_empty(self) -> None:
         result = _make_result_no_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert "findings:" not in md
 
     def test_prose_body_unchanged(self) -> None:
         result = _make_result_with_structured_findings()
-        md = _format_review_markdown(result, "code", SLICE_INFO)
+        md = format_review_markdown(result, "code", SLICE_INFO)
         assert "### [CONCERN] Missing error handling" in md
         assert "### [NOTE] Variable name unclear" in md
 
 
 class TestYamlEscape:
-    """Test _yaml_escape helper."""
+    """Test yaml_escape helper."""
 
     def test_escapes_double_quotes(self) -> None:
-        assert _yaml_escape('hello "world"') == 'hello \\"world\\"'
+        assert yaml_escape('hello "world"') == 'hello \\"world\\"'
 
     def test_no_quotes_unchanged(self) -> None:
-        assert _yaml_escape("hello world") == "hello world"
+        assert yaml_escape("hello world") == "hello world"
 
     def test_escapes_backslash(self) -> None:
-        assert _yaml_escape("path\\to\\file") == "path\\\\to\\\\file"
+        assert yaml_escape("path\\to\\file") == "path\\\\to\\\\file"
diff --git a/tests/cli/test_review_resolve.py b/tests/cli/test_review_resolve.py
index ebf7fdc..9fccb51 100644
--- a/tests/cli/test_review_resolve.py
+++ b/tests/cli/test_review_resolve.py
@@ -111,7 +111,7 @@ def test_resolve_slice_cf_not_installed() -> None:
 # ---------------------------------------------------------------------------
 
 
-@patch("squadron.cli.commands.review._save_review_file")
+@patch("squadron.cli.commands.review.save_review_result")
 @patch("squadron.cli.commands.review._run_review_command")
 def test_review_tasks_digit_routes_through_resolver(
     mock_review: object,
@@ -133,7 +133,7 @@ def test_review_tasks_digit_routes_through_resolver(
     assert "118-slice.composed-workflows.md" in inputs["against"]
 
 
-@patch("squadron.cli.commands.review._save_review_file")
+@patch("squadron.cli.commands.review.save_review_result")
 @patch("squadron.cli.commands.review._run_review_command")
 def test_review_slice_digit_routes_through_resolver(
     mock_review: object,
@@ -155,7 +155,7 @@ def test_review_slice_digit_routes_through_resolver(
     assert "100-arch.orchestration-v2.md" in inputs["against"]
 
 
-@patch("squadron.cli.commands.review._save_review_file")
+@patch("squadron.cli.commands.review.save_review_result")
 @patch("squadron.cli.commands.review._run_review_command")
 def test_review_arch_resolves_index(
     mock_review: object,
diff --git a/tests/cli/test_review_save.py b/tests/cli/test_review_save.py
index 5d59b7f..d94ad75 100644
--- a/tests/cli/test_review_save.py
+++ b/tests/cli/test_review_save.py
@@ -6,17 +6,17 @@ import json
 from datetime import datetime
 from pathlib import Path
 
-from squadron.cli.commands.review import (
-    SliceInfo,
-    _format_review_markdown,
-    _save_review_file,
-)
 from squadron.review.models import (
     ReviewFinding,
     ReviewResult,
     Severity,
     Verdict,
 )
+from squadron.review.persistence import (
+    SliceInfo,
+    format_review_markdown,
+    save_review_result,
+)
 
 
 def _make_result(
@@ -57,10 +57,10 @@ SLICE_INFO: SliceInfo = {
 }
 
 
-def test_format_review_markdown_has_frontmatter() -> None:
+def testformat_review_markdown_has_frontmatter() -> None:
     """Markdown output includes YAML frontmatter with correct fields."""
     result = _make_result()
-    md = _format_review_markdown(result, "arch", SLICE_INFO)
+    md = format_review_markdown(result, "arch", SLICE_INFO)
     assert "---" in md
     assert "docType: review" in md
     assert "reviewType: arch" in md
@@ -70,19 +70,19 @@ def test_format_review_markdown_has_frontmatter() -> None:
     assert "dateCreated: 20260321" in md
 
 
-def test_format_review_markdown_has_findings() -> None:
+def testformat_review_markdown_has_findings() -> None:
     """Markdown output includes findings with severity badges."""
     result = _make_result()
-    md = _format_review_markdown(result, "arch", SLICE_INFO)
+    md = format_review_markdown(result, "arch", SLICE_INFO)
     assert "### [CONCERN] Test concern" in md
     assert "A test finding." in md
     assert "### [PASS] Looks good" in md
 
 
-def test_save_review_file_writes_markdown(tmp_path: Path) -> None:
+def testsave_review_result_writes_markdown(tmp_path: Path) -> None:
     """Saves a markdown review file with correct name."""
     result = _make_result()
-    path = _save_review_file(result, "arch", SLICE_INFO, reviews_dir=tmp_path)
+    path = save_review_result(result, "arch", SLICE_INFO, reviews_dir=tmp_path)
     assert path.exists()
     assert path.name == "118-review.arch.composed-workflows.md"
     content = path.read_text()
@@ -90,10 +90,10 @@ def test_save_review_file_writes_markdown(tmp_path: Path) -> None:
     assert "verdict: CONCERNS" in content
 
 
-def test_save_review_file_writes_json(tmp_path: Path) -> None:
+def testsave_review_result_writes_json(tmp_path: Path) -> None:
     """Saves a JSON review file when as_json=True."""
     result = _make_result()
-    path = _save_review_file(
+    path = save_review_result(
         result, "arch", SLICE_INFO, as_json=True, reviews_dir=tmp_path
     )
     assert path.exists()
@@ -103,26 +103,26 @@ def test_save_review_file_writes_json(tmp_path: Path) -> None:
     assert len(data["findings"]) == 2
 
 
-def test_save_review_file_overwrites_existing(tmp_path: Path) -> None:
+def testsave_review_result_overwrites_existing(tmp_path: Path) -> None:
     """Re-saving overwrites the existing file."""
     existing = tmp_path / "118-review.arch.composed-workflows.md"
     existing.write_text("old content")
 
     result = _make_result(verdict=Verdict.PASS)
-    _save_review_file(result, "arch", SLICE_INFO, reviews_dir=tmp_path)
+    save_review_result(result, "arch", SLICE_INFO, reviews_dir=tmp_path)
 
     content = existing.read_text()
     assert "old content" not in content
     assert "verdict: PASS" in content
 
 
-def test_save_review_file_creates_directory(tmp_path: Path) -> None:
+def testsave_review_result_creates_directory(tmp_path: Path) -> None:
     """Creates the reviews directory if it doesn't exist."""
     reviews_dir = tmp_path / "nested" / "reviews"
     assert not reviews_dir.exists()
 
     result = _make_result()
-    path = _save_review_file(result, "arch", SLICE_INFO, reviews_dir=reviews_dir)
+    path = save_review_result(result, "arch", SLICE_INFO, reviews_dir=reviews_dir)
 
     assert reviews_dir.exists()
     assert path.exists()
diff --git a/tests/pipeline/actions/test_checkpoint.py b/tests/pipeline/actions/test_checkpoint.py
new file mode 100644
index 0000000..f6db180
--- /dev/null
+++ b/tests/pipeline/actions/test_checkpoint.py
@@ -0,0 +1,222 @@
+"""Tests for CheckpointAction."""
+
+from __future__ import annotations
+
+from unittest.mock import MagicMock
+
+import pytest
+
+from squadron.pipeline.actions.checkpoint import CheckpointAction, CheckpointTrigger
+from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.models import ActionContext, ActionResult
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+def _make_context(
+    prior_outputs: dict[str, ActionResult] | None = None,
+    params: dict[str, object] | None = None,
+) -> ActionContext:
+    """Build an ActionContext with configurable prior outputs and params."""
+    return ActionContext(
+        pipeline_name="test-pipeline",
+        run_id="run-12345678",
+        params=params or {},
+        step_name="quality-gate",
+        step_index=1,
+        prior_outputs=prior_outputs or {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        cwd="/tmp/test",
+    )
+
+
+def _review_result(verdict: str) -> ActionResult:
+    """Build a minimal ActionResult with a verdict."""
+    return ActionResult(
+        success=True,
+        action_type="review",
+        outputs={"response": "review text"},
+        verdict=verdict,
+    )
+
+
+# ---------------------------------------------------------------------------
+# Basic properties and protocol
+# ---------------------------------------------------------------------------
+
+
+class TestCheckpointActionBasics:
+    def test_action_type(self) -> None:
+        action = CheckpointAction()
+        assert action.action_type == "checkpoint"
+
+    def test_protocol_compliance(self) -> None:
+        assert isinstance(CheckpointAction(), Action)
+
+
+class TestCheckpointTriggerEnum:
+    def test_all_values(self) -> None:
+        assert CheckpointTrigger.ALWAYS == "always"
+        assert CheckpointTrigger.ON_CONCERNS == "on-concerns"
+        assert CheckpointTrigger.ON_FAIL == "on-fail"
+        assert CheckpointTrigger.NEVER == "never"
+
+    def test_has_four_members(self) -> None:
+        assert len(CheckpointTrigger) == 4
+
+
+# ---------------------------------------------------------------------------
+# Validation
+# ---------------------------------------------------------------------------
+
+
+class TestCheckpointValidation:
+    def test_empty_config(self) -> None:
+        errors = CheckpointAction().validate({})
+        assert errors == []
+
+    def test_valid_trigger(self) -> None:
+        errors = CheckpointAction().validate({"trigger": "on-concerns"})
+        assert errors == []
+
+    def test_invalid_trigger(self) -> None:
+        errors = CheckpointAction().validate({"trigger": "bogus"})
+        assert len(errors) == 1
+        assert errors[0].field == "trigger"
+        assert "bogus" in errors[0].message
+
+
+# ---------------------------------------------------------------------------
+# Execute — trigger × verdict matrix
+# ---------------------------------------------------------------------------
+
+
+class TestCheckpointExecute:
+    @pytest.mark.asyncio
+    async def test_never_skips(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("FAIL")},
+            params={"trigger": "never"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "skipped"
+
+    @pytest.mark.asyncio
+    async def test_always_fires(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("PASS")},
+            params={"trigger": "always"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_always_fires_no_prior_verdict(self) -> None:
+        ctx = _make_context(params={"trigger": "always"})
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_on_concerns_pass_skips(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("PASS")},
+            params={"trigger": "on-concerns"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "skipped"
+
+    @pytest.mark.asyncio
+    async def test_on_concerns_concerns_fires(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("CONCERNS")},
+            params={"trigger": "on-concerns"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_on_concerns_fail_fires(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("FAIL")},
+            params={"trigger": "on-concerns"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_on_fail_pass_skips(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("PASS")},
+            params={"trigger": "on-fail"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "skipped"
+
+    @pytest.mark.asyncio
+    async def test_on_fail_concerns_skips(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("CONCERNS")},
+            params={"trigger": "on-fail"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "skipped"
+
+    @pytest.mark.asyncio
+    async def test_on_fail_fail_fires(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("FAIL")},
+            params={"trigger": "on-fail"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_no_prior_verdict_on_concerns_skips(self) -> None:
+        ctx = _make_context(params={"trigger": "on-concerns"})
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "skipped"
+
+    @pytest.mark.asyncio
+    async def test_default_trigger_is_on_concerns(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("CONCERNS")},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["checkpoint"] == "paused"
+
+    @pytest.mark.asyncio
+    async def test_fired_result_has_human_options(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("FAIL")},
+            params={"trigger": "always"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.outputs["human_options"] == [
+            "approve",
+            "revise",
+            "skip",
+            "abort",
+        ]
+        assert "Review verdict:" in str(result.outputs["reason"])
+        assert result.verdict == "FAIL"
+
+    @pytest.mark.asyncio
+    async def test_fired_result_metadata(self) -> None:
+        ctx = _make_context(
+            prior_outputs={"review": _review_result("FAIL")},
+            params={"trigger": "always"},
+        )
+        result = await CheckpointAction().execute(ctx)
+        assert result.metadata["step"] == "quality-gate"
+        assert result.metadata["pipeline"] == "test-pipeline"
+
+    @pytest.mark.asyncio
+    async def test_success_is_always_true(self) -> None:
+        """Both fired and skipped results are success=True."""
+        ctx_fire = _make_context(params={"trigger": "always"})
+        ctx_skip = _make_context(params={"trigger": "never"})
+        assert (await CheckpointAction().execute(ctx_fire)).success is True
+        assert (await CheckpointAction().execute(ctx_skip)).success is True
diff --git a/tests/pipeline/actions/test_registry_integration.py b/tests/pipeline/actions/test_registry_integration.py
index fbcf53c..18ca616 100644
--- a/tests/pipeline/actions/test_registry_integration.py
+++ b/tests/pipeline/actions/test_registry_integration.py
@@ -3,23 +3,29 @@
 from __future__ import annotations
 
 import squadron.pipeline.actions.cf_op  # noqa: F401
+import squadron.pipeline.actions.checkpoint  # noqa: F401
 import squadron.pipeline.actions.commit  # noqa: F401
 import squadron.pipeline.actions.devlog  # noqa: F401
 import squadron.pipeline.actions.dispatch  # noqa: F401
+import squadron.pipeline.actions.review  # noqa: F401
 from squadron.pipeline.actions import get_action, list_actions
 from squadron.pipeline.actions.cf_op import CfOpAction
+from squadron.pipeline.actions.checkpoint import CheckpointAction
 from squadron.pipeline.actions.commit import CommitAction
 from squadron.pipeline.actions.devlog import DevlogAction
 from squadron.pipeline.actions.dispatch import DispatchAction
 from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.actions.review import ReviewAction
 
 
 def test_list_actions_includes_all_registered() -> None:
     actions = list_actions()
     assert "cf-op" in actions
+    assert "checkpoint" in actions
     assert "commit" in actions
     assert "devlog" in actions
     assert "dispatch" in actions
+    assert "review" in actions
 
 
 def test_get_action_cf_op() -> None:
@@ -46,6 +52,18 @@ def test_get_action_dispatch() -> None:
     assert isinstance(action, Action)
 
 
+def test_get_action_review() -> None:
+    action = get_action("review")
+    assert isinstance(action, ReviewAction)
+    assert isinstance(action, Action)
+
+
+def test_get_action_checkpoint() -> None:
+    action = get_action("checkpoint")
+    assert isinstance(action, CheckpointAction)
+    assert isinstance(action, Action)
+
+
 def test_no_import_errors() -> None:
     """Importing all action modules should not raise."""
 
diff --git a/tests/pipeline/actions/test_review_action.py b/tests/pipeline/actions/test_review_action.py
new file mode 100644
index 0000000..dcb7e8a
--- /dev/null
+++ b/tests/pipeline/actions/test_review_action.py
@@ -0,0 +1,486 @@
+"""Tests for ReviewAction."""
+
+from __future__ import annotations
+
+from datetime import datetime
+from pathlib import Path
+from unittest.mock import MagicMock, patch
+
+import pytest
+
+from squadron.pipeline.actions.protocol import Action
+from squadron.pipeline.actions.review import ReviewAction
+from squadron.pipeline.models import ActionContext
+from squadron.pipeline.resolver import ModelResolutionError
+from squadron.providers.base import ProfileName
+from squadron.review.models import (
+    ReviewFinding,
+    ReviewResult,
+    Severity,
+    Verdict,
+)
+from squadron.review.templates import ReviewTemplate
+
+_P = "squadron.pipeline.actions.review"
+
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+def _make_context(**overrides: object) -> ActionContext:
+    """Build an ActionContext with review-specific defaults."""
+    resolver = MagicMock()
+    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
+    defaults: dict[str, object] = {
+        "pipeline_name": "test-pipeline",
+        "run_id": "run-12345678",
+        "params": {
+            "template": "code",
+            "cwd": "/tmp/test",
+        },
+        "step_name": "review-step",
+        "step_index": 0,
+        "prior_outputs": {},
+        "resolver": resolver,
+        "cf_client": MagicMock(),
+        "cwd": "/tmp/test",
+    }
+    defaults.update(overrides)
+    return ActionContext(**defaults)  # type: ignore[arg-type]
+
+
+def _make_review_result(
+    verdict: Verdict = Verdict.CONCERNS,
+    model: str | None = "claude-sonnet-4-20250514",
+) -> ReviewResult:
+    """Build a canned ReviewResult with structured findings."""
+    return ReviewResult(
+        verdict=verdict,
+        findings=[
+            ReviewFinding(
+                severity=Severity.CONCERN,
+                title="Missing error handling",
+                description="No try/except.",
+                file_ref="src/foo.py:10",
+                category="error-handling",
+                location="src/foo.py:10",
+            ),
+        ],
+        raw_output="## Review\nCONCERNS\n",
+        template_name="code",
+        input_files={"cwd": "/tmp/test"},
+        timestamp=datetime(2026, 4, 1, 12, 0, 0),
+        model=model,
+    )
+
+
+def _mock_template() -> ReviewTemplate:
+    return MagicMock(spec=ReviewTemplate, name="code")
+
+
+# ---------------------------------------------------------------------------
+# Basic properties
+# ---------------------------------------------------------------------------
+
+
+class TestReviewActionBasics:
+    def test_action_type(self) -> None:
+        assert ReviewAction().action_type == "review"
+
+    def test_protocol_compliance(self) -> None:
+        assert isinstance(ReviewAction(), Action)
+
+
+# ---------------------------------------------------------------------------
+# Validation
+# ---------------------------------------------------------------------------
+
+
+class TestReviewValidation:
+    def test_missing_template(self) -> None:
+        errors = ReviewAction().validate({"cwd": "."})
+        assert len(errors) == 1
+        assert errors[0].field == "template"
+
+    def test_missing_cwd(self) -> None:
+        errors = ReviewAction().validate({"template": "code"})
+        assert len(errors) == 1
+        assert errors[0].field == "cwd"
+
+    def test_valid_config(self) -> None:
+        errors = ReviewAction().validate({"template": "code", "cwd": "."})
+        assert errors == []
+
+    def test_both_missing(self) -> None:
+        errors = ReviewAction().validate({})
+        assert len(errors) == 2
+        fields = {e.field for e in errors}
+        assert fields == {"template", "cwd"}
+
+
+# ---------------------------------------------------------------------------
+# Execute — happy path
+# ---------------------------------------------------------------------------
+
+
+class TestReviewExecuteHappyPath:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_happy_path(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context()
+        result = await ReviewAction().execute(ctx)
+
+        assert result.success is True
+        assert result.action_type == "review"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_verdict_populated(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result(Verdict.CONCERNS)
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.verdict == "CONCERNS"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_findings_as_dicts(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        result = await ReviewAction().execute(_make_context())
+        assert len(result.findings) == 1
+        assert isinstance(result.findings[0], dict)
+        f = result.findings[0]
+        assert f["id"] == "F001"  # type: ignore[index]
+        assert f["severity"] == "concern"  # type: ignore[index]
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_response_in_outputs(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        review_result = _make_review_result()
+        mock_run_review.return_value = review_result
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.outputs["response"] == review_result.raw_output
+
+
+# ---------------------------------------------------------------------------
+# Execute — model and profile resolution
+# ---------------------------------------------------------------------------
+
+
+class TestReviewModelResolution:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_resolver_called_with_action_model(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(params={"template": "code", "cwd": "/tmp", "model": "opus"})
+        await ReviewAction().execute(ctx)
+        ctx.resolver.resolve.assert_called_once_with("opus", None)
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_alias_derived_profile(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(params={"template": "code", "cwd": "/tmp"})
+        ctx.resolver.resolve.return_value = ("gpt-4o", "openrouter")
+
+        result = await ReviewAction().execute(ctx)
+        assert result.metadata["profile"] == "openrouter"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_explicit_profile_overrides_alias(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(
+            params={"template": "code", "cwd": "/tmp", "profile": "openai"}
+        )
+        ctx.resolver.resolve.return_value = ("gpt-4o", "openrouter")
+
+        result = await ReviewAction().execute(ctx)
+        assert result.metadata["profile"] == "openai"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_default_profile_is_sdk(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(params={"template": "code", "cwd": "/tmp"})
+        ctx.resolver.resolve.return_value = ("sonnet", None)
+
+        result = await ReviewAction().execute(ctx)
+        assert result.metadata["profile"] == ProfileName.SDK
+
+
+# ---------------------------------------------------------------------------
+# Execute — template inputs passthrough
+# ---------------------------------------------------------------------------
+
+
+class TestReviewInputPassthrough:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_passthrough_keys(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(
+            params={
+                "template": "code",
+                "cwd": "/tmp",
+                "diff": "main",
+                "files": "src/**/*.py",
+                "against": "arch.md",
+            }
+        )
+        await ReviewAction().execute(ctx)
+
+        call_args = mock_run_review.call_args
+        inputs = call_args[0][1]
+        assert inputs["diff"] == "main"
+        assert inputs["files"] == "src/**/*.py"
+        assert inputs["against"] == "arch.md"
+        assert inputs["cwd"] == "/tmp"
+
+
+# ---------------------------------------------------------------------------
+# Execute — persistence
+# ---------------------------------------------------------------------------
+
+
+class TestReviewPersistence:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_review_file_persisted(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        result = await ReviewAction().execute(_make_context())
+        mock_save.assert_called_once()
+        assert result.outputs["review_file"] == "/tmp/reviews/review.md"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", side_effect=OSError("disk full"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_persistence_failure_is_nonfatal(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.success is True
+        assert "review_file" not in result.outputs
+
+
+# ---------------------------------------------------------------------------
+# Execute — error handling
+# ---------------------------------------------------------------------------
+
+
+class TestReviewErrors:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.get_template", return_value=None)
+    @patch(f"{_P}.load_all_templates")
+    async def test_template_not_found(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+    ) -> None:
+        result = await ReviewAction().execute(_make_context())
+        assert result.success is False
+        assert "not found" in (result.error or "")
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_model_resolution_error(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+
+        ctx = _make_context()
+        ctx.resolver.resolve.side_effect = ModelResolutionError("no model")
+
+        result = await ReviewAction().execute(ctx)
+        assert result.success is False
+        assert "no model" in (result.error or "")
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.run_review_with_profile", side_effect=RuntimeError("API down"))
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_review_execution_error(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.success is False
+        assert "API down" in (result.error or "")
+
+
+# ---------------------------------------------------------------------------
+# Execute — metadata
+# ---------------------------------------------------------------------------
+
+
+class TestReviewMetadata:
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_metadata_fields(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result()
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.metadata["model"] == "claude-sonnet-4-20250514"
+        assert result.metadata["template"] == "code"
+        assert "profile" in result.metadata
diff --git a/tests/review/test_persistence.py b/tests/review/test_persistence.py
new file mode 100644
index 0000000..8d91d96
--- /dev/null
+++ b/tests/review/test_persistence.py
@@ -0,0 +1,182 @@
+"""Tests for review persistence — shared formatting and file saving."""
+
+from __future__ import annotations
+
+from datetime import datetime
+from pathlib import Path
+from unittest.mock import patch
+
+import yaml
+
+from squadron.review.models import (
+    ReviewFinding,
+    ReviewResult,
+    Severity,
+    Verdict,
+)
+from squadron.review.persistence import (
+    SliceInfo,
+    format_review_markdown,
+    save_review_file,
+    yaml_escape,
+)
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+def _make_result(
+    verdict: Verdict = Verdict.CONCERNS,
+    model: str | None = "claude-opus-4-5",
+) -> ReviewResult:
+    return ReviewResult(
+        verdict=verdict,
+        findings=[
+            ReviewFinding(
+                severity=Severity.CONCERN,
+                title="Missing error handling",
+                description="No try/except around I/O.",
+                file_ref="src/foo.py:10",
+                category="error-handling",
+                location="src/foo.py:10",
+            ),
+            ReviewFinding(
+                severity=Severity.NOTE,
+                title="Variable name unclear",
+                description="Variable x is vague.",
+                category="naming",
+            ),
+        ],
+        raw_output="raw review output",
+        template_name="code",
+        input_files={"input": "file.md"},
+        timestamp=datetime(2026, 4, 1, 12, 0, 0),
+        model=model,
+    )
+
+
+def _make_slice_info() -> SliceInfo:
+    return SliceInfo(
+        index=146,
+        name="review-and-checkpoint-actions",
+        slice_name="review-and-checkpoint-actions",
+        design_file="project-documents/user/slices/146-slice.md",
+        task_files=["146-tasks.review-and-checkpoint-actions.md"],
+        arch_file="project-documents/user/architecture/140-arch.md",
+    )
+
+
+# ---------------------------------------------------------------------------
+# yaml_escape
+# ---------------------------------------------------------------------------
+
+
+class TestYamlEscape:
+    def test_escapes_backslashes(self) -> None:
+        assert yaml_escape("path\\to\\file") == "path\\\\to\\\\file"
+
+    def test_escapes_double_quotes(self) -> None:
+        assert yaml_escape('say "hello"') == 'say \\"hello\\"'
+
+    def test_unchanged_when_no_special_chars(self) -> None:
+        assert yaml_escape("plain text") == "plain text"
+
+    def test_both_backslash_and_quotes(self) -> None:
+        assert yaml_escape('a\\b "c"') == 'a\\\\b \\"c\\"'
+
+
+# ---------------------------------------------------------------------------
+# format_review_markdown
+# ---------------------------------------------------------------------------
+
+
+class TestFormatReviewMarkdown:
+    def test_valid_yaml_frontmatter(self) -> None:
+        result = _make_result()
+        md = format_review_markdown(result, "code", _make_slice_info())
+        parts = md.split("---")
+        data = yaml.safe_load(parts[1])
+        assert data["docType"] == "review"
+        assert data["verdict"] == "CONCERNS"
+        assert data["aiModel"] == "claude-opus-4-5"
+
+    def test_structured_findings_in_frontmatter(self) -> None:
+        result = _make_result()
+        md = format_review_markdown(result, "code", _make_slice_info())
+        parts = md.split("---")
+        data = yaml.safe_load(parts[1])
+        assert isinstance(data["findings"], list)
+        assert len(data["findings"]) == 2
+        f1 = data["findings"][0]
+        assert f1["id"] == "F001"
+        assert f1["severity"] == "concern"
+        assert f1["category"] == "error-handling"
+        assert f1["summary"] == "Missing error handling"
+        assert f1["location"] == "src/foo.py:10"
+
+    def test_handles_missing_slice_info(self) -> None:
+        result = _make_result()
+        md = format_review_markdown(result, "code")
+        assert "---" in md
+        assert "slice: unknown" in md
+        parts = md.split("---")
+        data = yaml.safe_load(parts[1])
+        assert data["docType"] == "review"
+
+    def test_prose_body_with_findings(self) -> None:
+        result = _make_result()
+        md = format_review_markdown(result, "code", _make_slice_info(

[truncated at 100KB — file too large for API review]
```

### Rules Injected

None

### Raw Response

Let me examine the key implementation files to provide a thorough review.
Reading the implementation files...
Reading test files... Let me also check the project conventions:
<minimax:tool_call>
<invoke name="Read">
<parameter name="file_path">./project-documents/user/CLAUDE.md</parameter>
</invoke>
</minimax:tool_call>
