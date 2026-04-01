---
docType: tasks
slice: review-and-checkpoint-actions
project: squadron
lld: user/slices/146-slice.review-and-checkpoint-actions.md
dependencies: [142, 143, 145]
projectState: Pipeline scaffolding complete (slice 142). Structured review findings operational (slice 143). Dispatch action complete (slice 145). Utility actions operational (slice 144). Review system with templates, rules injection, and structured output from slices 105/128/143. Review file formatting in cli/commands/review.py as private functions.
dateCreated: 20260401
dateUpdated: 20260401
status: not_started
---

## Context Summary

- Working on slice 146 (Review and Checkpoint Actions) — quality gate layer for pipelines
- Two actions: `ReviewAction` and `CheckpointAction` in `src/squadron/pipeline/actions/`
- Review action delegates to existing `run_review_with_profile()`, maps `ReviewResult` to `ActionResult` with verdict and structured findings
- Checkpoint action evaluates trigger (always, on-concerns, on-fail, never) against prior review verdict, returns paused/skipped data
- Includes minor refactor: extract review file persistence from `cli/commands/review.py` to shared `review/persistence.py`
- Next slices: 147 (Step Types), 149 (Executor) — both depend on review and checkpoint actions

---

## Tasks

### T1 — Extract Review File Persistence to Shared Module

- [ ] **Extract `_format_review_markdown()`, `_save_review_file()`, and `_yaml_escape()` from `src/squadron/cli/commands/review.py` to `src/squadron/review/persistence.py`**
  - [ ] Create `src/squadron/review/persistence.py` with:
    - `yaml_escape(text: str) -> str` (renamed from private `_yaml_escape`)
    - `format_review_markdown(result, review_type, slice_info, source_document, model) -> str` — pure formatting, returns markdown string with YAML frontmatter and findings
    - `save_review_file(content, review_type, slice_name, slice_index, cwd) -> Path | None` — writes to `project-documents/user/reviews/{index}-review.{type}.{slice_name}.md`, returns path
    - Move `SliceInfo` TypedDict to this module (used by both CLI and pipeline)
  - [ ] Ensure function signatures accept all data needed without CLI-specific types (no `typer` imports, no `rich` imports)
  - [ ] Update `src/squadron/cli/commands/review.py`:
    - Import from `squadron.review.persistence` instead of using private functions
    - Remove the extracted private functions and `SliceInfo`
    - Verify calls still work with the new import paths
  - [ ] Ensure `from __future__ import annotations` is present in new file
  - [ ] Verify all existing tests pass (`python -m pytest --tb=short -q`)
  - [ ] pyright clean on both `review/persistence.py` and `cli/commands/review.py`
  - [ ] ruff clean on both files

**Commit**: `refactor: extract review file persistence to shared module`

---

### T2 — Review Persistence: Tests

- [ ] **Create tests at `tests/review/test_persistence.py`**
  - [ ] Test `yaml_escape` — escapes backslashes and double quotes
  - [ ] Test `format_review_markdown` — produces valid YAML frontmatter with verdict, model, findings array
  - [ ] Test `format_review_markdown` — structured findings appear in frontmatter with id, severity, category, summary, location
  - [ ] Test `format_review_markdown` — handles missing `slice_info` gracefully (fewer frontmatter fields, still valid)
  - [ ] Test `format_review_markdown` — includes prose body with finding descriptions
  - [ ] Test `save_review_file` — writes file to correct path and returns `Path` (use `tmp_path`)
  - [ ] Test `save_review_file` — creates parent directories if needed
  - [ ] Test `save_review_file` — returns `None` on write failure (mock `Path.write_text` to raise `OSError`)
  - [ ] All tests pass

**Commit**: `test: add review persistence unit tests`

---

### T3 — CheckpointAction: Implementation

- [ ] **Implement `CheckpointAction` in `src/squadron/pipeline/actions/checkpoint.py`**
  - [ ] Define `CheckpointTrigger` StrEnum with values: `ALWAYS = "always"`, `ON_CONCERNS = "on-concerns"`, `ON_FAIL = "on-fail"`, `NEVER = "never"`
  - [ ] Implement `CheckpointAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.CHECKPOINT` value (`"checkpoint"`)
    - `validate(config)`:
      - If `"trigger"` present, validate it's a valid `CheckpointTrigger` value
      - Return `ValidationError` if trigger value is invalid
      - Return empty list for valid config or missing trigger (defaults at runtime)
    - `execute(context)`:
      - **Trigger resolution**: read `context.params.get("trigger", CheckpointTrigger.ON_CONCERNS)`, convert to `CheckpointTrigger`
      - **Prior verdict**: implement `_find_review_verdict(prior_outputs)` — iterate `prior_outputs` in reverse, return first `result.verdict` that is not `None`
      - **Trigger evaluation**: implement `_should_fire(trigger, verdict)` per the trigger threshold table in the slice design
      - **Skip result**: return `ActionResult(success=True, action_type=self.action_type, outputs={"checkpoint": "skipped", "trigger": trigger.value, "verdict_seen": verdict or "none"})`
      - **Fire result**: return `ActionResult(success=True, action_type=self.action_type, outputs={"checkpoint": "paused", "reason": f"Review verdict: {verdict}", "trigger": trigger.value, "human_options": ["approve", "revise", "skip", "abort"]}, verdict=verdict, metadata={"step": context.step_name, "pipeline": context.pipeline_name})`
  - [ ] Add module-level auto-registration: `register_action(ActionType.CHECKPOINT, CheckpointAction())`
  - [ ] Ensure `from __future__ import annotations` is present

**Commit**: `feat: implement CheckpointAction with trigger evaluation`

---

### T4 — CheckpointAction: Tests

- [ ] **Create tests at `tests/pipeline/actions/test_checkpoint.py`**
  - [ ] Test `action_type` property returns `"checkpoint"`
  - [ ] Test `isinstance(CheckpointAction(), Action)` (protocol compliance)
  - [ ] Test `CheckpointTrigger` enum has all four values with correct string representations
  - [ ] Test `validate()` — empty config returns empty list
  - [ ] Test `validate()` — valid trigger value returns empty list
  - [ ] Test `validate()` — invalid trigger value returns `ValidationError`
  - [ ] Test `execute()` — trigger `never` with any verdict returns `checkpoint="skipped"`
  - [ ] Test `execute()` — trigger `always` with any verdict returns `checkpoint="paused"`
  - [ ] Test `execute()` — trigger `always` with no prior verdict still fires
  - [ ] Test `execute()` — trigger `on-concerns` + verdict `PASS` returns `checkpoint="skipped"`
  - [ ] Test `execute()` — trigger `on-concerns` + verdict `CONCERNS` returns `checkpoint="paused"`
  - [ ] Test `execute()` — trigger `on-concerns` + verdict `FAIL` returns `checkpoint="paused"`
  - [ ] Test `execute()` — trigger `on-fail` + verdict `PASS` returns `checkpoint="skipped"`
  - [ ] Test `execute()` — trigger `on-fail` + verdict `CONCERNS` returns `checkpoint="skipped"`
  - [ ] Test `execute()` — trigger `on-fail` + verdict `FAIL` returns `checkpoint="paused"`
  - [ ] Test `execute()` — no prior review verdict (empty `prior_outputs`) with `on-concerns` returns `checkpoint="skipped"`
  - [ ] Test `execute()` — default trigger (no trigger in params) behaves as `on-concerns`
  - [ ] Test `execute()` — fired result includes `human_options`, `reason`, and `verdict`
  - [ ] Test `execute()` — fired result metadata includes `step` and `pipeline` names
  - [ ] Create `_make_context` helper to build `ActionContext` with configurable prior outputs and params
  - [ ] All tests pass, pyright clean on the action module

**Commit**: `test: add CheckpointAction unit tests`

---

### T5 — ReviewAction: Implementation

- [ ] **Implement `ReviewAction` in `src/squadron/pipeline/actions/review.py`**
  - [ ] Implement `ReviewAction` class satisfying the `Action` protocol:
    - `action_type` property returns `ActionType.REVIEW` value (`"review"`)
    - `validate(config)` checks:
      - `"template"` key present in config — return `ValidationError(field="template", ...)` if missing
      - `"cwd"` key present in config — return `ValidationError(field="cwd", ...)` if missing
      - Return empty list for valid config
    - `execute(context)` implementation:
      - **Template resolution**: `get_template(str(context.params["template"]))` from review template registry
      - **Model resolution**: extract `model` and `step_model` from `context.params`, call `context.resolver.resolve(action_model, step_model)` — same pattern as dispatch
      - **Profile resolution**: explicit `profile` param → alias-derived → `ProfileName.SDK` default — same pattern as dispatch
      - **Build inputs dict**: `cwd` from params, pass through template-relevant keys (`diff`, `files`, `against`, `input`) when present
      - **Rules content**: load from `context.params.get("rules_content")` if present
      - **Execute review**: call `run_review_with_profile(template, inputs, profile=..., model=..., rules_content=...)`
      - **File persistence**: call persistence functions from `review/persistence.py` to save review file; wrap in try/except and log warning on failure (non-fatal)
      - **Result mapping**: return `ActionResult(success=True, action_type=self.action_type, outputs={"response": result.raw_output, "review_file": str(path)}, verdict=result.verdict.value, findings=[f.__dict__ for f in result.structured_findings], metadata={"model": model_id, "profile": profile_name, "template": template_name})`
  - [ ] Error handling — same pattern as dispatch: catch known exceptions (`ModelResolutionError`, `ModelPoolNotImplemented`, `KeyError`) and unexpected `Exception`, return `ActionResult(success=False, ...)`; log unexpected errors at ERROR level
  - [ ] Add module-level auto-registration: `register_action(ActionType.REVIEW, ReviewAction())`
  - [ ] Ensure `from __future__ import annotations` is present

**Commit**: `feat: implement ReviewAction for pipeline review gates`

---

### T6 — ReviewAction: Tests

- [ ] **Create tests at `tests/pipeline/actions/test_review_action.py`**
  - [ ] Test `action_type` property returns `"review"`
  - [ ] Test `isinstance(ReviewAction(), Action)` (protocol compliance)
  - [ ] Test `validate()` — missing `template` returns error with `field="template"`
  - [ ] Test `validate()` — missing `cwd` (but template present) returns error with `field="cwd"`
  - [ ] Test `validate()` — both `template` and `cwd` present returns empty list
  - [ ] Test `execute()` — happy path: template resolved, review executed, result mapped correctly
  - [ ] Test `execute()` — `ActionResult.verdict` populated from `ReviewResult.verdict.value`
  - [ ] Test `execute()` — `ActionResult.findings` populated from `ReviewResult.structured_findings` as dicts
  - [ ] Test `execute()` — `ActionResult.outputs["response"]` contains raw review output
  - [ ] Test `execute()` — model resolution: `resolver.resolve()` called with `action_model` and `step_model`
  - [ ] Test `execute()` — profile from alias: alias-derived profile used when no explicit `profile` param
  - [ ] Test `execute()` — profile override: explicit `profile` param takes precedence
  - [ ] Test `execute()` — default profile: `ProfileName.SDK` when no alias profile and no explicit profile
  - [ ] Test `execute()` — template inputs: `diff`, `files`, `against` keys passed through to review inputs
  - [ ] Test `execute()` — review file persisted (mock persistence, verify called)
  - [ ] Test `execute()` — persistence failure is non-fatal: logs warning, still returns successful result
  - [ ] Test `execute()` — template not found (KeyError from `get_template`) returns `success=False`
  - [ ] Test `execute()` — `ModelResolutionError` returns `success=False`
  - [ ] Test `execute()` — review execution error returns `success=False`, logged at ERROR
  - [ ] Test `execute()` — metadata includes model, profile, template name
  - [ ] Mock boundaries: `get_template()`, `run_review_with_profile()`, `ModelResolver`, persistence functions
  - [ ] Create `_make_context` helper for building `ActionContext` with review-specific params
  - [ ] Create `_make_review_result` helper for building canned `ReviewResult` with structured findings
  - [ ] All tests pass, pyright clean on the action module

**Commit**: `test: add ReviewAction unit tests`

---

### T7 — Action Registration and Integration Verification

- [ ] **Verify both actions register correctly alongside existing actions**
  - [ ] Update `tests/pipeline/actions/test_registry_integration.py`:
    - Add imports for `squadron.pipeline.actions.review` and `squadron.pipeline.actions.checkpoint`
    - Add `"review"` and `"checkpoint"` to `test_list_actions_includes_all_registered()`
    - Add test: `get_action("review")` returns a `ReviewAction` instance
    - Add test: `get_action("checkpoint")` returns a `CheckpointAction` instance
  - [ ] Confirm no import errors or circular dependencies
  - [ ] All existing tests still pass (`python -m pytest --tb=short -q`)

**Commit**: `test: add review and checkpoint to action registry integration tests`

---

### T8 — Full Verification and Closeout

- [ ] **Run full verification suite**
  - [ ] `python -m pytest --tb=short -q` — all tests pass
  - [ ] `pyright src/squadron/pipeline/actions/review.py` — 0 errors
  - [ ] `pyright src/squadron/pipeline/actions/checkpoint.py` — 0 errors
  - [ ] `pyright src/squadron/review/persistence.py` — 0 errors
  - [ ] `ruff check src/squadron/pipeline/actions/review.py src/squadron/pipeline/actions/checkpoint.py src/squadron/review/persistence.py` — 0 warnings
  - [ ] `ruff format --check src/squadron/pipeline/actions/ src/squadron/review/persistence.py` — no formatting issues
  - [ ] Run the verification walkthrough from the slice design document
  - [ ] Update slice design verification walkthrough with actual commands and output
  - [ ] Check off success criteria in slice design
  - [ ] Mark slice 146 as complete in slice design frontmatter
  - [ ] Mark slice 146 as complete in slice plan (`140-slices.pipeline-foundation.md`)
  - [ ] Update CHANGELOG.md with slice 146 entries
  - [ ] Update DEVLOG.md with implementation completion entry

**Commit**: `docs: mark slice 146 review and checkpoint actions complete`
