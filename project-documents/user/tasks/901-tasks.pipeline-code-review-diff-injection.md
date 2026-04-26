---
docType: tasks
slice: pipeline-code-review-diff-injection
project: squadron
lldReference: user/slices/901-slice.pipeline-code-review-diff-injection.md
dependencies: [149]
dateCreated: 20260425
dateUpdated: 20260425
status: complete
---

# Tasks: Pipeline Code-Review Diff Injection and UNKNOWN-Fails-Closed

## Context

Fixes issue #11. Pipeline `code`-template reviews silently produce
`UNKNOWN`/no-findings because `_resolve_slice_inputs` in
`pipeline/actions/review.py` has no `case "code":` branch — the diff is never
assembled. Three coordinated changes:

1. **UNKNOWN fails closed** — add `"UNKNOWN"` to `ON_FAIL` and `ON_CONCERNS`
   threshold sets in `pipeline/actions/checkpoint.py`.
2. **Forward `slice` through `expand()`** — `phase.py` and `review.py` step
   types stop dropping the `slice` param when emitting the review action config.
3. **Declarative template-input registry** — replace the per-template `match`
   in `_resolve_slice_inputs` with a registry in
   `src/squadron/review/template_inputs.py` that each template opts into.
   The `code` template entry calls `resolve_slice_diff_range`, populating
   `inputs["diff"]` automatically.

Key files:
- `src/squadron/pipeline/actions/checkpoint.py` — `_TRIGGER_THRESHOLDS`
- `src/squadron/pipeline/steps/phase.py` — `PhaseStepType.expand()` lines 108-122
- `src/squadron/pipeline/steps/review.py` — `ReviewStepType.expand()` lines 57-67
- `src/squadron/review/template_inputs.py` — new file
- `src/squadron/pipeline/actions/review.py` — `_resolve_slice_inputs` lines 228-267
- `tests/pipeline/actions/test_review_action.py` — existing review tests
- `tests/pipeline/actions/test_checkpoint.py` — existing checkpoint tests (if present)
- `tests/pipeline/steps/test_phase.py` — existing phase step tests (if present)

---

## Tasks

### 1. UNKNOWN fails closed in checkpoint thresholds

- [x] In `checkpoint.py`, add `"UNKNOWN"` to both threshold sets:
  ```python
  CheckpointTrigger.ON_CONCERNS: {"CONCERNS", "FAIL", "UNKNOWN"},
  CheckpointTrigger.ON_FAIL:     {"FAIL", "UNKNOWN"},
  ```
- [x] Confirm `_should_fire` still returns `False` when `verdict is None`
  (no review in prior outputs) — this case must remain distinct from UNKNOWN.

### 2. Tests: checkpoint UNKNOWN behavior

- [x] `_should_fire(ON_FAIL, "UNKNOWN")` → `True`
- [x] `_should_fire(ON_CONCERNS, "UNKNOWN")` → `True`
- [x] `_should_fire(ON_FAIL, None)` → `False` (regression — no review)
- [x] `_should_fire(ON_CONCERNS, None)` → `False` (regression — no review)
- [x] `_should_fire(ON_FAIL, "FAIL")` → `True` (regression)
- [x] `_should_fire(ON_FAIL, "PASS")` → `False` (regression)
- [x] `_should_fire(NEVER, "UNKNOWN")` → `False`
- [x] `_should_fire(ALWAYS, "UNKNOWN")` → `True`

**Commit:** `fix(pipeline): treat UNKNOWN verdict as FAIL for on-fail/on-concerns checkpoints`

---

### 3. Forward `slice` from `PhaseStepType.expand()`

- [x] In `phase.py` `expand()`, when emitting the `("review", {...})` action
  tuple, include `"slice": "{slice}"` (the same placeholder format already
  used for `set_slice`) in the review action dict.
- [x] Only add `"slice"` when a `review:` sub-field is present (the guard
  already exists at line 108).

### 4. Tests: phase step forwards `slice`

- [x] Expand a phase step config that includes `review: code`; assert the
  emitted review action tuple contains `"slice"` as a key.
- [x] Expand a phase step config with no `review:` sub-field; assert the
  actions list contains no review action (regression — existing behavior).

---

### 5. Forward `slice` from `ReviewStepType.expand()`

- [x] In `review.py` `expand()`, include `"slice": cfg.get("slice")` in the
  emitted `("review", {...})` action dict when `"slice"` is present in `cfg`.
  Use `cfg.get` so steps without an explicit `slice` key are unaffected.

### 6. Tests: review step forwards `slice`

- [x] Expand a `review:` step config that includes `slice: 194`; assert the
  emitted review action tuple contains `"slice": 194`.
- [x] Expand a `review:` step config without a `slice` key; assert `"slice"`
  is absent from the emitted action dict (not set to None).

**Commit:** `fix(pipeline): forward slice param through phase and review step expand()`

---

### 7. Create template-input registry

- [x] Create `src/squadron/review/template_inputs.py`.
- [x] Define a frozen `TemplateInputSpec` dataclass:
  - `key: str` — the `inputs[key]` this spec populates
  - `source: Callable[[SliceInfo, str], str | None]` — `(slice_info, cwd) -> value`
- [x] Define `TEMPLATE_INPUTS: dict[str, list[TemplateInputSpec]]` with
  entries for `"slice"`, `"tasks"`, `"arch"`, and `"code"` that reproduce
  the exact same inputs the current per-template `match` produces, plus the
  new `code` entry:
  - `"slice"` → `input` from `info["design_file"]`, `against` from `info["arch_file"]`
  - `"tasks"` → `input` from `project-documents/user/tasks/{info["task_files"][0]}`,
    `against` from `info["design_file"]`
  - `"arch"` → `input` from `info["arch_file"]`
  - `"code"` → `diff` from `resolve_slice_diff_range(info["index"], cwd)`
    (import from `squadron.review.git_utils`)
- [x] `SliceInfo` must be imported from `squadron.review.persistence`.
  `resolve_slice_diff_range` from `squadron.review.git_utils`. No other new
  imports in the module.
- [x] Export a helper `resolve_template_inputs(template_name, info, cwd,
  inputs)` that iterates `TEMPLATE_INPUTS.get(template_name, [])` and
  populates `inputs[spec.key] = value` when `source` returns non-None.

### 8. Tests: template-input registry

- [x] For each of the four templates (`slice`, `tasks`, `arch`, `code`),
  assert that `resolve_template_inputs` populates the expected keys from a
  `SliceInfo` fixture.
- [x] Assert that a template name not in the registry produces no key/value
  changes to `inputs` (no KeyError, no crash).
- [x] For `"code"` entry, use a monkeypatched `resolve_slice_diff_range` that
  returns a deterministic string; assert `inputs["diff"]` is set to it.
- [x] Assert that a `source` returning `None` does not set the key (i.e.
  `task_files` being empty for `tasks` template does not set `input` to None).

---

### 9. Rewrite `_resolve_slice_inputs` to use the registry

- [x] In `review.py` action, replace the body of `_resolve_slice_inputs`
  (lines 247-265) with a call to `resolve_template_inputs(template_name,
  info, cwd, inputs)` from `template_inputs.py`.
- [x] Remove the per-template `match` block entirely.
- [x] The existing guard (`if slice_param is not None and "input" not in
  inputs`) at line 120 is the entry point for `_resolve_slice_inputs`. For
  the `code` template, `"input"` is never in inputs, so the guard passes —
  confirm this behavior is preserved. Do not add a second guard; rely on the
  existing one.
- [x] The `_resolve_slice_inputs` debug-log line for unrecognised templates
  can be removed — unknown templates are handled gracefully by the registry's
  empty list fallback.
- [x] Preserve the return of `SliceInfo | None` — needed for file persistence
  naming downstream (lines 182-188).
- [x] Import `resolve_template_inputs` and `TEMPLATE_INPUTS` from
  `squadron.review.template_inputs`.

### 10. Tests: `_resolve_slice_inputs` regression

- [x] For `slice`, `tasks`, `arch` templates: assert `_resolve_slice_inputs`
  produces identical `inputs` dicts before and after the rewrite. Use the
  same `SliceInfo` fixture as Task 8; mock `resolve_slice_info` to return it.
- [x] For `code` template: assert `inputs["diff"]` is now set to the
  monkeypatched diff range (was previously not set — this is the fix).
- [x] For an unknown template name: assert `inputs` is unchanged and no
  exception is raised.

**Commit:** `fix(pipeline): declarative template-input registry, inject diff for code reviews`

---

### 11. Integration test: end-to-end pipeline review with `code` template

- [x] Write a test in `tests/pipeline/actions/test_review_action.py` (or a
  new `test_review_action_integration.py`) that:
  1. Constructs an `ActionContext` where `context.params` contains
     `template: code`, `slice: 194`, and a valid `cwd`.
  2. Mocks `resolve_slice_info` to return a `SliceInfo` fixture and
     `resolve_slice_diff_range` to return `"abc123...slice-194"`.
  3. Mocks `run_review_with_profile` to return a stub `ReviewResult` with
     `verdict = Verdict.CONCERNS` and non-empty `structured_findings`.
  4. Asserts the mock `run_review_with_profile` was called with a prompt
     that **contains** the diff range string (confirming the diff was injected).
  5. Asserts the returned `ActionResult.verdict == "CONCERNS"`.
- [x] Write a parallel test where `slice` is absent from `context.params`;
  assert `inputs["diff"]` is not set (no crash, no side effects).

### 12. Regression: full test suite and lint

- [x] `uv run pytest tests/pipeline/actions/ tests/pipeline/steps/ -q` —
  all pass.
- [x] `uv run pytest -q` — full suite passes.
- [x] `uv run ruff check && uv run ruff format --check` — clean.
- [x] `uv run pyright` — 0 errors.

**Commit:** `test(pipeline): add integration tests for code-review diff injection`

---

### 13. Mark slice complete and update DEVLOG

- [x] Update `dateUpdated` in slice frontmatter to today's date.
- [x] Update `status` in slice frontmatter to `complete`.
- [x] Update `900-slices.maintenance-and-refactoring.md` — change slice 901
  status line to `complete`.
- [x] Update `CHANGELOG.md` — add entry under current version.
- [x] Write DEVLOG entry summarising what shipped (the three changes, files
  touched, test count, gates passed).

**Commit:** `docs: mark slice 901 complete; update DEVLOG and CHANGELOG`
