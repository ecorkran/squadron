---
docType: tasks
slice: compact-action-and-step-types
project: squadron
lld: user/slices/147-slice.compact-action-and-step-types.md
dependencies: [142, 144, 145, 146]
projectState: Pipeline scaffolding complete (slice 142). All 7 action types implemented (slices 144–146) except compact (stub). Step type protocol, registry, and StepTypeName enum in place (slice 142). Step type modules are stubs (TODO slice 147). Review templates in src/squadron/data/templates/ with loading infrastructure from slice 141.
dateCreated: 20260402
dateUpdated: 20260402
status: complete
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

- [x] **Create `src/squadron/data/compaction/default.yaml` with draft compaction instructions**
  - [x] YAML structure with `name`, `description`, and `instructions` fields
  - [x] `instructions` field contains the prompt text template with placeholder support for `keep` and `summarize` params
  - [x] Content is draft/placeholder — will be refined during end-to-end testing in slice 151
  - [x] Follow the pattern established by review templates in `src/squadron/data/templates/`
- [x] **Create template loader function** in a suitable location (e.g., `src/squadron/pipeline/actions/compact.py` or a shared utility)
  - [x] Load template by name from `src/squadron/data/compaction/` (built-in) with `~/.config/squadron/compaction/` override layering
  - [x] Render the `instructions` field with provided params (`keep`, `summarize`)
  - [x] Default template name is `"default"`
- [x] Verify template file loads correctly in a quick smoke test
- [x] ruff clean on new/modified files

**Commit**: `feat: add compaction instruction template and loader`

---

### T2 — Compact Action Implementation

- [x] **Implement `CompactAction` in `src/squadron/pipeline/actions/compact.py`** (replace stub)
  - [x] `action_type` property returns `ActionType.COMPACT`
  - [x] `validate(config)`:
    - [x] If `keep` is present, validate it is a list of strings (semantic whitelist validation deferred to slice 151 when artifact names are finalized through E2E testing)
    - [x] If `summarize` is present, validate it is a boolean
    - [x] If `template` is present, validate it is a string
    - [x] Return `list[ValidationError]`
  - [x] `async execute(context)`:
    - [x] Load compaction instruction template using `context.params.get("template", "default")` to select template name
    - [x] Render template with `keep` and `summarize` params from `context.params`
    - [x] Issue rendered instructions to CF via `cf_client._run()` (same pattern as `CfOpAction`)
    - [x] If `summarize` is truthy, also call `cf summarize`
    - [x] Return `ActionResult(success=True, ...)` with `outputs` containing `stdout` and instruction text
    - [x] On `ContextForgeError`, return `ActionResult(success=False, error=str(exc))`
  - [x] Module-level `register_action(ActionType.COMPACT, CompactAction())`
  - [x] `from __future__ import annotations` present
- [x] pyright clean on `compact.py`
- [x] ruff clean on `compact.py`

**Commit**: `feat: implement CompactAction with template-based instructions`

---

### T3 — Compact Action Tests

- [x] **Create `tests/pipeline/actions/test_compact.py`**
  - [x] Test `validate` — empty config is valid (all optional)
  - [x] Test `validate` — `keep` as list of strings passes
  - [x] Test `validate` — `keep` as non-list returns validation error
  - [x] Test `validate` — `summarize` as bool passes
  - [x] Test `validate` — `summarize` as non-bool returns validation error
  - [x] Test `execute` — happy path with `keep` and `summarize`, mock `cf_client._run()`, verify CF commands issued
  - [x] Test `execute` — template rendering includes `keep` values in instruction text
  - [x] Test `execute` — `ContextForgeError` returns `ActionResult(success=False)`
  - [x] Test `execute` — `summarize=True` triggers CF summarize call
  - [x] Test `execute` — no `keep` or `summarize` still succeeds (defaults)
  - [x] Test `execute` — custom `template` param selects non-default template
  - [x] Test `action_type` returns `ActionType.COMPACT`
  - [x] All tests pass

**Commit**: `test: add CompactAction unit tests`

---

### T4 — Phase Step Type Implementation

- [x] **Implement `PhaseStepType` in `src/squadron/pipeline/steps/phase.py`** (replace stub)
  - [x] Constructor accepts `phase_name: str` (one of `"design"`, `"tasks"`, `"implement"`)
  - [x] `step_type` property returns the `phase_name`
  - [x] `validate(config)`:
    - [x] `phase` (int) is required — return `ValidationError` if missing or non-int
    - [x] If `review` is present, validate it is a `str` or a `dict` with required `template` key
    - [x] If `checkpoint` is present, validate it is a valid trigger value
    - [x] If `model` is present, validate it is a string
    - [x] Return `list[ValidationError]`
  - [x] `expand(config)` — returns `list[tuple[str, dict[str, object]]]`:
    - [x] Always includes: `("cf-op", {"operation": "set_phase", "phase": N})`
    - [x] Always includes: `("cf-op", {"operation": "build_context"})`
    - [x] Always includes: `("dispatch", {"model": config_model_or_None})`
    - [x] If `review` is configured (str or dict):
      - [x] If str: `("review", {"template": review_str, "model": None})`
      - [x] If dict: `("review", {"template": dict["template"], "model": dict.get("model")})`
      - [x] `("checkpoint", {"trigger": checkpoint_value_or_"never"})`
    - [x] Always includes: `("commit", {"message_prefix": f"phase-{phase}"})`
  - [x] Module-level registration for all three phase names:
    ```
    register_step_type(StepTypeName.DESIGN, PhaseStepType("design"))
    register_step_type(StepTypeName.TASKS, PhaseStepType("tasks"))
    register_step_type(StepTypeName.IMPLEMENT, PhaseStepType("implement"))
    ```
  - [x] `from __future__ import annotations` present
- [x] pyright clean on `phase.py`
- [x] ruff clean on `phase.py`

**Commit**: `feat: implement PhaseStepType with 3-phase registration`

---

### T5 — Phase Step Type Tests

- [x] **Create `tests/pipeline/steps/test_phase.py`**
  - [x] Test `step_type` property returns the phase name for each of `design`, `tasks`, `implement`
  - [x] Test `validate` — missing `phase` returns validation error
  - [x] Test `validate` — valid config with all optional fields passes
  - [x] Test `validate` — invalid `review` type returns validation error
  - [x] Test `validate` — invalid `checkpoint` value returns validation error
  - [x] Test `expand` — full config (phase + model + review str + checkpoint) produces 6-action sequence
  - [x] Test `expand` — review as dict with template + model override
  - [x] Test `expand` — no review config omits review and checkpoint actions (4-action sequence)
  - [x] Test `expand` — review present but no checkpoint defaults checkpoint trigger to `"never"`
  - [x] Test `expand` — dispatch includes model from config when provided
  - [x] Test `expand` — dispatch model is `None` when not in config
  - [x] Test `expand` — commit message_prefix includes phase number
  - [x] All tests pass

**Commit**: `test: add PhaseStepType unit tests`

---

### T6 — Compact Step Type Implementation

- [x] **Implement `CompactStepType` in `src/squadron/pipeline/steps/compact.py`** (replace stub)
  - [x] `step_type` property returns `StepTypeName.COMPACT`
  - [x] `validate(config)`:
    - [x] If `keep` is present, validate it is a list of strings
    - [x] If `summarize` is present, validate it is a boolean
    - [x] Return `list[ValidationError]`
  - [x] `expand(config)` — returns single-element list:
    - [x] `[("compact", {"keep": ..., "summarize": ..., "template": ...})]`
    - [x] Pass through config values; omit keys not present in config
  - [x] Module-level `register_step_type(StepTypeName.COMPACT, CompactStepType())`
- [x] pyright and ruff clean

**Commit**: `feat: implement CompactStepType`

---

### T7 — Compact Step Type Tests

- [x] **Create `tests/pipeline/steps/test_compact.py`**
  - [x] Test `step_type` returns `"compact"`
  - [x] Test `validate` — empty config is valid
  - [x] Test `validate` — `keep` as non-list returns error
  - [x] Test `expand` — config with `keep` and `summarize` produces single compact action tuple
  - [x] Test `expand` — empty config produces compact action with no extra params
  - [x] Test `expand` — config with `template` passes through to action config
  - [x] All tests pass

**Commit**: `test: add CompactStepType unit tests`

---

### T8 — Review Step Type Implementation

- [x] **Implement `ReviewStepType` in `src/squadron/pipeline/steps/review.py`** (replace stub)
  - [x] `step_type` property returns `StepTypeName.REVIEW`
  - [x] `validate(config)`:
    - [x] `template` (str) is required — return `ValidationError` if missing
    - [x] If `checkpoint` is present, validate it is a valid trigger value
    - [x] If `model` is present, validate it is a string
    - [x] Return `list[ValidationError]`
  - [x] `expand(config)`:
    - [x] Always includes: `("review", {"template": ..., "model": ...})`
    - [x] If `checkpoint` is present: `("checkpoint", {"trigger": ...})`
    - [x] If `checkpoint` is absent, no checkpoint action in expansion
  - [x] Module-level `register_step_type(StepTypeName.REVIEW, ReviewStepType())`
- [x] pyright and ruff clean

**Commit**: `feat: implement ReviewStepType`

---

### T9 — Review Step Type Tests

- [x] **Create `tests/pipeline/steps/test_review.py`**
  - [x] Test `step_type` returns `"review"`
  - [x] Test `validate` — missing `template` returns validation error
  - [x] Test `validate` — valid config with template + model + checkpoint passes
  - [x] Test `expand` — template + model + checkpoint produces 2-action sequence (review + checkpoint)
  - [x] Test `expand` — template only (no checkpoint) produces 1-action sequence (review only)
  - [x] Test `expand` — model is `None` when not in config
  - [x] All tests pass

**Commit**: `test: add ReviewStepType unit tests`

---

### T10 — Devlog Step Type Implementation

- [x] **Implement `DevlogStepType` in `src/squadron/pipeline/steps/devlog.py`** (replace stub)
  - [x] `step_type` property returns `StepTypeName.DEVLOG`
  - [x] `validate(config)`:
    - [x] If `mode` is present, validate it is `"auto"` or `"explicit"`
    - [x] If `mode` is `"explicit"`, `content` (str) is required
    - [x] Return `list[ValidationError]`
  - [x] `expand(config)`:
    - [x] Returns `[("devlog", {"mode": ..., "content": ...})]`
    - [x] Defaults `mode` to `"auto"` if not present
    - [x] Passes through `content` if present
  - [x] Module-level `register_step_type(StepTypeName.DEVLOG, DevlogStepType())`
- [x] pyright and ruff clean

**Commit**: `feat: implement DevlogStepType`

---

### T11 — Devlog Step Type Tests

- [x] **Create `tests/pipeline/steps/test_devlog.py`**
  - [x] Test `step_type` returns `"devlog"`
  - [x] Test `validate` — empty config is valid (defaults to auto)
  - [x] Test `validate` — `mode: "auto"` is valid
  - [x] Test `validate` — `mode: "explicit"` without `content` returns validation error
  - [x] Test `validate` — `mode: "explicit"` with `content` passes
  - [x] Test `validate` — invalid `mode` value returns validation error
  - [x] Test `expand` — `mode: "auto"` produces single devlog action
  - [x] Test `expand` — `mode: "explicit"` with content passes both through
  - [x] Test `expand` — no mode in config defaults to `"auto"`
  - [x] All tests pass

**Commit**: `test: add DevlogStepType unit tests`

---

### T12 — Registry Integration Tests

- [x] **Update `tests/pipeline/actions/test_registry_integration.py`**
  - [x] Add `import squadron.pipeline.actions.compact` (noqa: F401)
  - [x] Add `from squadron.pipeline.actions.compact import CompactAction`
  - [x] Add `test_get_action_compact()` — verify `get_action("compact")` returns `CompactAction` instance satisfying `Action` protocol
  - [x] Update `test_list_actions_includes_all_registered()` — verify `"compact"` is in the list (should already be there if prior tests passed, but confirm)
- [x] **Create `tests/pipeline/steps/test_registry_integration.py`**
  - [x] Import all step type modules to trigger registration
  - [x] `test_list_step_types_includes_all_registered()` — verify `design`, `tasks`, `implement`, `compact`, `review`, `devlog` are all present
  - [x] `test_get_step_type_design()` — returns `StepType` protocol instance
  - [x] `test_get_step_type_tasks()` — returns `StepType` protocol instance
  - [x] `test_get_step_type_implement()` — returns `StepType` protocol instance
  - [x] `test_get_step_type_compact()` — returns `StepType` protocol instance
  - [x] `test_get_step_type_review()` — returns `StepType` protocol instance
  - [x] `test_get_step_type_devlog()` — returns `StepType` protocol instance
  - [x] `test_no_import_errors()` — importing all modules raises no errors
  - [x] All tests pass
- [x] Full test suite passes: `uv run pytest --tb=short -q`

**Commit**: `test: add step type and compact action registry integration tests`

---

### T13 — Verification and Closeout

- [x] **Full verification**
  - [x] `uv run pytest --tb=short -q` — all tests pass, no regressions
  - [x] `uv run pyright src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — no errors
  - [x] `ruff check src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — clean
  - [x] `ruff format --check src/squadron/pipeline/actions/compact.py src/squadron/pipeline/steps/` — clean
- [x] **Update slice design** (`147-slice.compact-action-and-step-types.md`):
  - [x] Status → `complete`
  - [x] dateUpdated → today
  - [x] Check off success criteria
  - [x] Update verification walkthrough with actual commands and results
- [x] **Update slice plan** (`140-slices.pipeline-foundation.md`):
  - [x] Check off entry 8 (147)
- [x] **Update CHANGELOG.md** with slice 147 entries
- [x] **Write DEVLOG entry** for Phase 6 completion

**Commit**: `docs: mark slice 147 compact action and step types complete`
