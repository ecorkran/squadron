---
docType: tasks
slice: compact-action-and-step-types
project: squadron
lld: user/slices/147-slice.compact-action-and-step-types.md
dependencies: [142, 144, 145, 146]
projectState: Pipeline scaffolding complete (slice 142). All 7 action types implemented (slices 144–146) except compact (stub). Step type protocol, registry, and StepTypeName enum in place (slice 142). Step type modules are stubs (TODO slice 147). Review templates in src/squadron/data/templates/ with loading infrastructure from slice 141.
dateCreated: 20260402
dateUpdated: 20260402
status: not_started
---

## Context Summary

- Working on slice 147 (Compact Action and Step Types) — the composition layer between YAML pipeline grammar and the action layer
- One action: `CompactAction` issues parameterized compaction instructions to CF via instruction templates
- Four step types: phase (6-action expansion), compact (1-action), review (review + optional checkpoint), devlog (1-action)
- Step types are pure data transformers — `expand()` returns `(action_type, action_config)` tuples, no I/O
- Compaction instruction templates ship as YAML in `src/squadron/data/compaction/` with user overrides in `~/.config/squadron/compaction/`
- All step type and action stubs already exist in the codebase — this slice replaces stubs with implementations
- Next slices: 148 (Pipeline Definitions), 149 (Executor) — both consume step type expansions

---

## Tasks

### T1 — Compaction Instruction Template

- [ ] **Create `src/squadron/data/compaction/default.yaml` with draft compaction instructions**
  - [ ] YAML structure with `name`, `description`, and `instructions` fields
  - [ ] `instructions` field contains the prompt text template with placeholder support for `keep` and `summarize` params
  - [ ] Content is draft/placeholder — will be refined during end-to-end testing in slice 151
  - [ ] Follow the pattern established by review templates in `src/squadron/data/templates/`
- [ ] **Create template loader function** in a suitable location (e.g., `src/squadron/pipeline/actions/compact.py` or a shared utility)
  - [ ] Load template by name from `src/squadron/data/compaction/` (built-in) with `~/.config/squadron/compaction/` override layering
  - [ ] Render the `instructions` field with provided params (`keep`, `summarize`)
  - [ ] Default template name is `"default"`
- [ ] Verify template file loads correctly in a quick smoke test
- [ ] ruff clean on new/modified files

**Commit**: `feat: add compaction instruction template and loader`

---

### T2 — Compact Action Implementation

- [ ] **Implement `CompactAction` in `src/squadron/pipeline/actions/compact.py`** (replace stub)
  - [ ] `action_type` property returns `ActionType.COMPACT`
  - [ ] `validate(config)`:
    - [ ] If `keep` is present, validate it is a list of strings (semantic whitelist validation deferred to slice 151 when artifact names are finalized through E2E testing)
    - [ ] If `summarize` is present, validate it is a boolean
    - [ ] If `template` is present, validate it is a string
    - [ ] Return `list[ValidationError]`
  - [ ] `async execute(context)`:
    - [ ] Load compaction instruction template using `context.params.get("template", "default")` to select template name
    - [ ] Render template with `keep` and `summarize` params from `context.params`
    - [ ] Issue rendered instructions to CF via `cf_client._run()` (same pattern as `CfOpAction`)
    - [ ] If `summarize` is truthy, also call `cf summarize`
    - [ ] Return `ActionResult(success=True, ...)` with `outputs` containing `stdout` and instruction text
    - [ ] On `ContextForgeError`, return `ActionResult(success=False, error=str(exc))`
  - [ ] Module-level `register_action(ActionType.COMPACT, CompactAction())`
  - [ ] `from __future__ import annotations` present
- [ ] pyright clean on `compact.py`
- [ ] ruff clean on `compact.py`

**Commit**: `feat: implement CompactAction with template-based instructions`

---

### T3 — Compact Action Tests

- [ ] **Create `tests/pipeline/actions/test_compact.py`**
  - [ ] Test `validate` — empty config is valid (all optional)
  - [ ] Test `validate` — `keep` as list of strings passes
  - [ ] Test `validate` — `keep` as non-list returns validation error
  - [ ] Test `validate` — `summarize` as bool passes
  - [ ] Test `validate` — `summarize` as non-bool returns validation error
  - [ ] Test `execute` — happy path with `keep` and `summarize`, mock `cf_client._run()`, verify CF commands issued
  - [ ] Test `execute` — template rendering includes `keep` values in instruction text
  - [ ] Test `execute` — `ContextForgeError` returns `ActionResult(success=False)`
  - [ ] Test `execute` — `summarize=True` triggers CF summarize call
  - [ ] Test `execute` — no `keep` or `summarize` still succeeds (defaults)
  - [ ] Test `execute` — custom `template` param selects non-default template
  - [ ] Test `action_type` returns `ActionType.COMPACT`
  - [ ] All tests pass

**Commit**: `test: add CompactAction unit tests`

---

### T4 — Phase Step Type Implementation

- [ ] **Implement `PhaseStepType` in `src/squadron/pipeline/steps/phase.py`** (replace stub)
  - [ ] Constructor accepts `phase_name: str` (one of `"design"`, `"tasks"`, `"implement"`)
  - [ ] `step_type` property returns the `phase_name`
  - [ ] `validate(config)`:
    - [ ] `phase` (int) is required — return `ValidationError` if missing or non-int
    - [ ] If `review` is present, validate it is a `str` or a `dict` with required `template` key
    - [ ] If `checkpoint` is present, validate it is a valid trigger value
    - [ ] If `model` is present, validate it is a string
    - [ ] Return `list[ValidationError]`
  - [ ] `expand(config)` — returns `list[tuple[str, dict[str, object]]]`:
    - [ ] Always includes: `("cf-op", {"operation": "set_phase", "phase": N})`
    - [ ] Always includes: `("cf-op", {"operation": "build_context"})`
    - [ ] Always includes: `("dispatch", {"model": config_model_or_None})`
    - [ ] If `review` is configured (str or dict):
      - [ ] If str: `("review", {"template": review_str, "model": None})`
      - [ ] If dict: `("review", {"template": dict["template"], "model": dict.get("model")})`
      - [ ] `("checkpoint", {"trigger": checkpoint_value_or_"never"})`
    - [ ] Always includes: `("commit", {"message_prefix": f"phase-{phase}"})`
  - [ ] Module-level registration for all three phase names:
    ```
    register_step_type(StepTypeName.DESIGN, PhaseStepType("design"))
    register_step_type(StepTypeName.TASKS, PhaseStepType("tasks"))
    register_step_type(StepTypeName.IMPLEMENT, PhaseStepType("implement"))
    ```
  - [ ] `from __future__ import annotations` present
- [ ] pyright clean on `phase.py`
- [ ] ruff clean on `phase.py`

**Commit**: `feat: implement PhaseStepType with 3-phase registration`

---

### T5 — Phase Step Type Tests

- [ ] **Create `tests/pipeline/steps/test_phase.py`**
  - [ ] Test `step_type` property returns the phase name for each of `design`, `tasks`, `implement`
  - [ ] Test `validate` — missing `phase` returns validation error
  - [ ] Test `validate` — valid config with all optional fields passes
  - [ ] Test `validate` — invalid `review` type returns validation error
  - [ ] Test `validate` — invalid `checkpoint` value returns validation error
  - [ ] Test `expand` — full config (phase + model + review str + checkpoint) produces 6-action sequence
  - [ ] Test `expand` — review as dict with template + model override
  - [ ] Test `expand` — no review config omits review and checkpoint actions (4-action sequence)
  - [ ] Test `expand` — review present but no checkpoint defaults checkpoint trigger to `"never"`
  - [ ] Test `expand` — dispatch includes model from config when provided
  - [ ] Test `expand` — dispatch model is `None` when not in config
  - [ ] Test `expand` — commit message_prefix includes phase number
  - [ ] All tests pass

**Commit**: `test: add PhaseStepType unit tests`

---

### T6 — Compact Step Type Implementation

- [ ] **Implement `CompactStepType` in `src/squadron/pipeline/steps/compact.py`** (replace stub)
  - [ ] `step_type` property returns `StepTypeName.COMPACT`
  - [ ] `validate(config)`:
    - [ ] If `keep` is present, validate it is a list of strings
    - [ ] If `summarize` is present, validate it is a boolean
    - [ ] Return `list[ValidationError]`
  - [ ] `expand(config)` — returns single-element list:
    - [ ] `[("compact", {"keep": ..., "summarize": ..., "template": ...})]`
    - [ ] Pass through config values; omit keys not present in config
  - [ ] Module-level `register_step_type(StepTypeName.COMPACT, CompactStepType())`
- [ ] pyright and ruff clean

**Commit**: `feat: implement CompactStepType`

---

### T7 — Compact Step Type Tests

- [ ] **Create `tests/pipeline/steps/test_compact.py`**
  - [ ] Test `step_type` returns `"compact"`
  - [ ] Test `validate` — empty config is valid
  - [ ] Test `validate` — `keep` as non-list returns error
  - [ ] Test `expand` — config with `keep` and `summarize` produces single compact action tuple
  - [ ] Test `expand` — empty config produces compact action with no extra params
  - [ ] Test `expand` — config with `template` passes through to action config
  - [ ] All tests pass

**Commit**: `test: add CompactStepType unit tests`

---

### T8 — Review Step Type Implementation

- [ ] **Implement `ReviewStepType` in `src/squadron/pipeline/steps/review.py`** (replace stub)
  - [ ] `step_type` property returns `StepTypeName.REVIEW`
  - [ ] `validate(config)`:
    - [ ] `template` (str) is required — return `ValidationError` if missing
    - [ ] If `checkpoint` is present, validate it is a valid trigger value
    - [ ] If `model` is present, validate it is a string
    - [ ] Return `list[ValidationError]`
  - [ ] `expand(config)`:
    - [ ] Always includes: `("review", {"template": ..., "model": ...})`
    - [ ] If `checkpoint` is present: `("checkpoint", {"trigger": ...})`
    - [ ] If `checkpoint` is absent, no checkpoint action in expansion
  - [ ] Module-level `register_step_type(StepTypeName.REVIEW, ReviewStepType())`
- [ ] pyright and ruff clean

**Commit**: `feat: implement ReviewStepType`

---

### T9 — Review Step Type Tests

- [ ] **Create `tests/pipeline/steps/test_review.py`**
  - [ ] Test `step_type` returns `"review"`
  - [ ] Test `validate` — missing `template` returns validation error
  - [ ] Test `validate` — valid config with template + model + checkpoint passes
  - [ ] Test `expand` — template + model + checkpoint produces 2-action sequence (review + checkpoint)
  - [ ] Test `expand` — template only (no checkpoint) produces 1-action sequence (review only)
  - [ ] Test `expand` — model is `None` when not in config
  - [ ] All tests pass

**Commit**: `test: add ReviewStepType unit tests`

---

### T10 — Devlog Step Type Implementation

- [ ] **Implement `DevlogStepType` in `src/squadron/pipeline/steps/devlog.py`** (replace stub)
  - [ ] `step_type` property returns `StepTypeName.DEVLOG`
  - [ ] `validate(config)`:
    - [ ] If `mode` is present, validate it is `"auto"` or `"explicit"`
    - [ ] If `mode` is `"explicit"`, `content` (str) is required
    - [ ] Return `list[ValidationError]`
  - [ ] `expand(config)`:
    - [ ] Returns `[("devlog", {"mode": ..., "content": ...})]`
    - [ ] Defaults `mode` to `"auto"` if not present
    - [ ] Passes through `content` if present
  - [ ] Module-level `register_step_type(StepTypeName.DEVLOG, DevlogStepType())`
- [ ] pyright and ruff clean

**Commit**: `feat: implement DevlogStepType`

---

### T11 — Devlog Step Type Tests

- [ ] **Create `tests/pipeline/steps/test_devlog.py`**
  - [ ] Test `step_type` returns `"devlog"`
  - [ ] Test `validate` — empty config is valid (defaults to auto)
  - [ ] Test `validate` — `mode: "auto"` is valid
  - [ ] Test `validate` — `mode: "explicit"` without `content` returns validation error
  - [ ] Test `validate` — `mode: "explicit"` with `content` passes
  - [ ] Test `validate` — invalid `mode` value returns validation error
  - [ ] Test `expand` — `mode: "auto"` produces single devlog action
  - [ ] Test `expand` — `mode: "explicit"` with content passes both through
  - [ ] Test `expand` — no mode in config defaults to `"auto"`
  - [ ] All tests pass

**Commit**: `test: add DevlogStepType unit tests`

---

### T12 — Registry Integration Tests

- [ ] **Update `tests/pipeline/actions/test_registry_integration.py`**
  - [ ] Add `import squadron.pipeline.actions.compact` (noqa: F401)
  - [ ] Add `from squadron.pipeline.actions.compact import CompactAction`
  - [ ] Add `test_get_action_compact()` — verify `get_action("compact")` returns `CompactAction` instance satisfying `Action` protocol
  - [ ] Update `test_list_actions_includes_all_registered()` — verify `"compact"` is in the list (should already be there if prior tests passed, but confirm)
- [ ] **Create `tests/pipeline/steps/test_registry_integration.py`**
  - [ ] Import all step type modules to trigger registration
  - [ ] `test_list_step_types_includes_all_registered()` — verify `design`, `tasks`, `implement`, `compact`, `review`, `devlog` are all present
  - [ ] `test_get_step_type_design()` — returns `StepType` protocol instance
  - [ ] `test_get_step_type_tasks()` — returns `StepType` protocol instance
  - [ ] `test_get_step_type_implement()` — returns `StepType` protocol instance
  - [ ] `test_get_step_type_compact()` — returns `StepType` protocol instance
  - [ ] `test_get_step_type_review()` — returns `StepType` protocol instance
  - [ ] `test_get_step_type_devlog()` — returns `StepType` protocol instance
  - [ ] `test_no_import_errors()` — importing all modules raises no errors
  - [ ] All tests pass
- [ ] Full test suite passes: `uv run pytest --tb=short -q`

**Commit**: `test: add step type and compact action registry integration tests`

---

### T13 — Verification and Closeout

- [ ] **Full verification**
  - [ ] `uv run pytest --tb=short -q` — all tests pass, no regressions
  - [ ] `uv run pyright src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — no errors
  - [ ] `ruff check src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — clean
  - [ ] `ruff format --check src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — clean
- [ ] **Update slice design** (`147-slice.compact-action-and-step-types.md`):
  - [ ] Status → `complete`
  - [ ] dateUpdated → today
  - [ ] Check off success criteria
  - [ ] Update verification walkthrough with actual commands and results
- [ ] **Update slice plan** (`140-slices.pipeline-foundation.md`):
  - [ ] Check off entry 8 (147)
- [ ] **Update CHANGELOG.md** with slice 147 entries
- [ ] **Write DEVLOG entry** for Phase 6 completion

**Commit**: `docs: mark slice 147 compact action and step types complete`
