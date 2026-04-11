---
docType: tasks
slice: compact-and-summary-unification
project: squadron
lld: user/slices/166-slice.compact-and-summary-unification.md
dependencies: [161-summary-step-with-emit-destinations, 164-profile-aware-summary-model-routing]
projectState: Slice 166 design complete. Slices 161 and 164 complete. SDK mode already treats compact as a summary alias (compact.py delegates to _execute_summary). Prompt-only compact is broken (emits stale `/compact [...]` slash command). Working tree has pending edits under project-documents/; no code changes in-flight.
dateCreated: 20260411
dateUpdated: 20260411
status: complete
---

## Context Summary

- **Slice**: 166 — Compact and Summary Unification. A pure refactoring
  slice with no new user-facing behavior.
- **Goal**: Finish unification started in slice 161. Delete the
  `CompactAction` runtime path entirely and route `compact:` YAML steps
  through `SummaryAction` with `emit=[rotate]` at the step-expansion
  layer. The `compact:` YAML keyword survives as a step-type alias only.
- **Why**: Prompt-only mode is currently broken for every pipeline
  using `compact:` (P6, slice, tasks, app, example). `_render_compact`
  emits a literal `/compact [...]` string that Claude Code does not
  interpret as a slash command, so those pipelines stall. SDK mode
  already works via `_execute_summary` delegation.
- **Key change**: `CompactStepType.expand()` returns
  `[("summary", {..., "emit": ["rotate"]})]` instead of
  `[("compact", {...})]`. All runtime compact plumbing is deleted.
- **One real risk**: `StateManager._maybe_record_compact_summaries` is
  currently gated on `ar.action_type != "compact"`. After the refactor
  no action is compact-typed. The gate must be rewritten to fire on
  summary actions whose effective emit list includes `rotate`. If
  mis-coded, resume-with-reinjection silently stops working.
- **Preserved names** (to avoid schema bump): `RunState.compact_summaries`,
  `CompactSummary` dataclass, `src/squadron/data/compaction/` template
  directory.
- **Template helpers** (`load_compaction_template`, `render_instructions`,
  `CompactionTemplate`, `_parse_template`) currently live in
  `src/squadron/pipeline/actions/compact.py`. They are imported from
  multiple sites (`summary.py`, `summary_run.py`, `prompt_renderer.py`,
  `summary_render.py`, tests). They must be **moved** to a new module,
  not deleted, before `actions/compact.py` can go.
- **Backward compat**: all pipeline YAML files using `compact:` stay
  unchanged — the loader still parses `compact:` → `CompactStepType`.
- **Next**: Phase 6 implementation.

---

## Tasks

### T1: Verify source files and locate all call sites

- [ ] Read `src/squadron/pipeline/actions/compact.py` — confirm the
  four template helpers (`CompactionTemplate`, `_parse_template`,
  `load_compaction_template`, `render_instructions`) and the
  `CompactAction` class; note the `_USER_COMPACTION_DIR` constant
- [ ] Read `src/squadron/pipeline/actions/summary.py` — confirm
  `SummaryAction`, `_execute_summary`, and the `emit_results` outputs
  shape written by a successful summary run
- [ ] Read `src/squadron/pipeline/steps/compact.py` — confirm current
  `CompactStepType.expand()` returns `[("compact", action_config)]`
- [ ] Read `src/squadron/pipeline/prompt_renderer.py` — confirm
  `_render_compact` at ~line 234, its `_BUILDERS` entry at ~line 344,
  and the `from squadron.pipeline.actions.compact import (...)` at the
  top of the file
- [ ] Read `src/squadron/pipeline/state.py` — confirm
  `_maybe_record_compact_summaries` at ~line 228 and its
  `ar.action_type != "compact"` gate
- [ ] Read `src/squadron/pipeline/actions/__init__.py` — confirm
  `ActionType.COMPACT = "compact"` and the StrEnum structure
- [ ] Read `commands/sq/run.md` — confirm the `### compact` section at
  line 86 and the `### summary` section that follows
- [ ] Grep for every import of `squadron.pipeline.actions.compact` in
  both `src/` and `tests/`; list them in this task file:
  - [ ] `src/squadron/cli/commands/summary_run.py`
  - [ ] `src/squadron/pipeline/prompt_renderer.py`
  - [ ] `src/squadron/pipeline/summary_render.py`
  - [ ] `src/squadron/pipeline/actions/summary.py`
  - [ ] `tests/cli/commands/test_summary_run.py`
  - [ ] `tests/pipeline/actions/test_compact.py`
  - [ ] `tests/pipeline/actions/test_compact_sdk.py`
  - [ ] `tests/pipeline/actions/test_registry_integration.py`
- [ ] Grep for every occurrence of `CompactAction`, `ActionType.COMPACT`,
  and `_render_compact` in `src/` and `tests/` and catalog them
- [ ] Grep for every occurrence of the literal string `"compact"` in
  `src/squadron/pipeline/` — confirm the ones that are safe to keep
  (step-type name, `action_type=` equality checks in state.py,
  `test_summary_integration.py` regression test) vs. ones that become
  dead
  - [ ] Every call site understood before any code is touched
  - [ ] Test sites that will fail are listed in the task file

---

### T2: Create `compaction_templates.py` module and move helpers

- [ ] Create new file
  `src/squadron/pipeline/compaction_templates.py` with module docstring
  explaining its role as the shared source for compaction/summary
  template loading
- [ ] Add `from __future__ import annotations` at the top
- [ ] Move the following verbatim from
  `src/squadron/pipeline/actions/compact.py` into the new module:
  - [ ] `_USER_COMPACTION_DIR` constant
  - [ ] `CompactionTemplate` dataclass
  - [ ] `_parse_template` function
  - [ ] `load_compaction_template` function
  - [ ] `render_instructions` function
- [ ] Keep the existing imports each helper uses (`Path`, `yaml`, `cast`,
  `data_dir`, `LenientDict`) — move them too, pruning anything not
  referenced in the moved code
- [ ] Do **not** touch `CompactAction` yet; leave `actions/compact.py`
  importing from the new module so the old class still works during
  the migration. Add at the top of `actions/compact.py`:
  - `from squadron.pipeline.compaction_templates import (CompactionTemplate, load_compaction_template, render_instructions, _parse_template)` (or just the names the old class actually uses)
- [ ] Verify old module no longer has duplicate definitions
  - [ ] New module created at correct path
  - [ ] Old `actions/compact.py` still compiles (imports from new home)
  - [ ] No behavior change in this task

### T3: Update all consumers to import from `compaction_templates`

- [ ] Update `src/squadron/cli/commands/summary_run.py` import from
  `squadron.pipeline.actions.compact` → `squadron.pipeline.compaction_templates`
- [ ] Update `src/squadron/pipeline/prompt_renderer.py` import likewise
- [ ] Update `src/squadron/pipeline/summary_render.py` import likewise
- [ ] Update `src/squadron/pipeline/actions/summary.py` import likewise
  (note: this is a deferred `from … import …` inside a function body —
  update the deferred import too)
- [ ] Update every test file that imports from
  `squadron.pipeline.actions.compact` for the template helpers (not
  `CompactAction`):
  - [ ] `tests/cli/commands/test_summary_run.py` (three occurrences)
- [ ] Run `uv run ruff check` — confirm no unused-import warnings in
  `actions/compact.py` from re-exporting the moved helpers (if any
  appear, add an `__all__` or direct re-export)
  - [ ] Every non-test consumer imports from the new module
  - [ ] `actions/compact.py` no longer owns the helpers (it may still
    import them for its own `CompactAction.execute` body during the
    migration)

### T4: Test — template helpers still load from new module

- [ ] Run `uv run pytest tests/cli/commands/test_summary_run.py -v` —
  confirm green (these tests exercise `load_compaction_template` /
  `render_instructions` via the CLI)
- [ ] Run `uv run pytest tests/pipeline/ -v` — confirm baseline still
  green before any behavior change
  - [ ] Baseline remains green after the move

### T5: Commit — template helper extraction

- [ ] `uv run ruff format .`
- [ ] `git add src/squadron/pipeline/compaction_templates.py src/squadron/pipeline/actions/compact.py src/squadron/cli/commands/summary_run.py src/squadron/pipeline/prompt_renderer.py src/squadron/pipeline/summary_render.py src/squadron/pipeline/actions/summary.py tests/cli/commands/test_summary_run.py`
- [ ] `git commit -m "refactor: extract compaction template helpers to shared module"`
  - [ ] Working tree clean after commit
  - [ ] Slice branch has one new commit

---

### T6: Rewrite `CompactStepType.expand()` to emit a summary action

- [ ] In `src/squadron/pipeline/steps/compact.py` `expand()`:
  - [ ] Build the same `action_config` dict as today (template, model,
    keep, summarize — preserve the `model` key even when `None` to
    match current behavior)
  - [ ] Add `action_config["emit"] = ["rotate"]`
  - [ ] Return `[("summary", action_config)]` instead of
    `[("compact", action_config)]`
- [ ] Do **not** change `CompactStepType.validate()` — field validation
  stays as-is
- [ ] Do **not** change the `register_step_type(StepTypeName.COMPACT, …)`
  line — `compact:` remains a valid YAML step-type
  - [ ] `expand()` returns a single tuple with `"summary"` and
    `emit=["rotate"]`
  - [ ] `template`, `model`, `keep`, `summarize` all pass through
    unchanged
  - [ ] Step-type registration unchanged

### T7: Test `CompactStepType.expand()` new shape

- [ ] In the existing compact step tests (likely
  `tests/pipeline/steps/test_compact_step.py` — locate it; if it does
  not exist, add it):
- [ ] **Update or add** `test_compact_step_expands_to_summary_with_rotate`:
  - Assert `expand()` returns a single tuple
  - Assert `tup[0] == "summary"`
  - Assert `tup[1]["emit"] == ["rotate"]`
- [ ] **Add** `test_compact_step_passes_through_template_model_keep_summarize`:
  - Build a `StepConfig` with all four fields populated
  - Assert each one is present unchanged in the expanded action config
- [ ] **Add** `test_compact_step_with_no_model_emits_none`:
  - `StepConfig` without a `model` key → expanded action_config has
    `model: None` (matches current behavior)
- [ ] Delete or update any existing test in the file that asserted
  `expand()` returns `[("compact", …)]`
- [ ] Run `uv run pytest tests/pipeline/steps/test_compact_step.py -v`
  (or the correct path)
  - [ ] All tests pass
  - [ ] No test still expects the `("compact", …)` shape

### T8: Rewrite `_maybe_record_compact_summaries` gate

- [ ] In `src/squadron/pipeline/state.py`:
  - [ ] Change the gate from `ar.action_type != "compact"` to
    `ar.action_type != "summary"`
  - [ ] Inside the loop body, after the success and type checks, parse
    the effective emit destinations from
    `ar.outputs.get("emit_results")`:
    - Expect a `list[dict[str, object]]` with each entry containing a
      `"destination"` key (string). `SummaryAction` writes this shape
      today — see `actions/summary.py` near the return of
      `_execute_summary`
    - If any entry has `destination == "rotate"` and `ok is True`,
      proceed to record the summary; otherwise `continue`
  - [ ] The existing `"summary" in outputs and "source_step_index" in outputs`
    check stays (SummaryAction writes both)
  - [ ] Keep the function name `_maybe_record_compact_summaries` — the
    **name** `compact_summaries` is preserved per the slice doc
- [ ] Do **not** add a helper for emit parsing unless clarity demands
  it; one inline comprehension is enough
  - [ ] Gate fires for summary-action results with successful rotate
    emit
  - [ ] Gate does not fire for summary actions with stdout/file/clipboard
    only
  - [ ] Gate does not fire for non-summary action types

### T9: Test `_maybe_record_compact_summaries` new gate

- [ ] Open `tests/pipeline/test_summary_integration.py` — it already
  has `test_compact_alias_state_callback_still_fires` that exercises
  `_maybe_record_compact_summaries` directly with an ActionResult
- [ ] **Update** that test so the fake `ActionResult` has
  `action_type="summary"` (not `"compact"`) and otherwise matches what
  the post-refactor summary action produces — including
  `emit_results=[{"destination": "rotate", "ok": True, ...}]`
- [ ] **Add** `test_summary_action_without_rotate_emit_does_not_record`:
  - Fake `ActionResult` with `action_type="summary"`, success, outputs
    including `emit_results=[{"destination": "stdout", "ok": True}]`
  - After `cb(StepResult(...))`, assert
    `state.compact_summaries == {}`
- [ ] **Add** `test_summary_action_with_failed_rotate_does_not_record`:
  - `emit_results=[{"destination": "rotate", "ok": False, "detail": "failure"}]`
  - Assert state is not recorded (the slice gate requires
    `ok is True`)
- [ ] **Add** `test_non_summary_action_does_not_record`:
  - `action_type="dispatch"`, success, outputs contain a `"summary"`
    key (shouldn't matter)
  - Assert state is not recorded
- [ ] Run `uv run pytest tests/pipeline/test_summary_integration.py -v`
  - [ ] All four tests pass
  - [ ] The existing compact-alias regression test is the canonical
    path test for the refactor

### T10: Commit — step expansion + state gate rewrite

- [ ] `uv run ruff format .`
- [ ] `uv run pytest tests/pipeline/ -v` — everything green except
  any compact-tests that will be deleted in T15
- [ ] `git add src/squadron/pipeline/steps/compact.py src/squadron/pipeline/state.py tests/pipeline/steps/ tests/pipeline/test_summary_integration.py`
- [ ] `git commit -m "refactor: route compact step through summary action"`
  - [ ] Commit leaves tree in a buildable state (old `CompactAction`
    still exists and still registers, but no step type emits it — so
    the registration is dead code that will be removed next)

---

### T11: Delete `_render_compact` from `prompt_renderer.py`

- [ ] In `src/squadron/pipeline/prompt_renderer.py`:
  - [ ] Delete the entire `_render_compact` function (~lines 234–253)
  - [ ] Remove the `ActionType.COMPACT: _render_compact,` entry from
    the `_BUILDERS` dict (~line 344)
  - [ ] Remove the `load_compaction_template` / `render_instructions`
    imports at the top **only if** no other function in the file still
    uses them. `_render_summary` still calls them — so they stay.
- [ ] Verify no other reference to `_render_compact` exists in the file
  - [ ] `_BUILDERS` no longer maps `compact`
  - [ ] File still imports from `compaction_templates` for summary use

### T12: Test — `_render_compact` removal

- [ ] Open `tests/pipeline/test_prompt_renderer.py`:
- [ ] **Delete** the entire `TestRenderCompact` class (all its test
  methods)
- [ ] If any other test in the file constructs an `ActionInstruction`
  with `action_type=ActionType.COMPACT` or asserts on
  `/compact [...]` output, update or delete it
- [ ] Scan for any test building a fake step with step_type `compact`
  and asserting the resulting `ActionInstruction.action_type` — those
  tests should now expect `action_type="summary"` (because
  `CompactStepType.expand()` emits a summary action). Update as needed.
- [ ] Run `uv run pytest tests/pipeline/test_prompt_renderer.py -v`
  - [ ] All remaining tests pass
  - [ ] No test references `_render_compact` or `ActionType.COMPACT`

### T13: Add prompt-only smoke test — compact step renders as summary

- [ ] In `tests/pipeline/test_prompt_renderer.py` (or the nearest
  integration-style test file for the renderer), add
  `test_compact_yaml_renders_as_summary_with_rotate`:
  - Build a fake pipeline config with a single `compact:` step
  - Run it through `build_step_instructions()` (or whatever the
    public entry point is — see how other tests call it)
  - Assert the resulting `StepInstructions.actions[0].action_type == "summary"`
  - Assert `actions[0].emit == ["rotate"]`
  - Assert no `ActionInstruction` in the result has
    `action_type == "compact"`
  - Assert no action's `command` field contains the literal `/compact [`
- [ ] Run `uv run pytest tests/pipeline/test_prompt_renderer.py -v`
  - [ ] New test passes
  - [ ] Success criterion #1 from the slice doc is exercised

---

### T14: Delete `CompactAction` class and its action registration

- [ ] In `src/squadron/pipeline/actions/compact.py`:
  - [ ] Delete the `CompactAction` class (the entire
    `class CompactAction:` block, ~lines 118–251)
  - [ ] Delete the `register_action(ActionType.COMPACT, CompactAction())`
    call at the bottom
- [ ] At this point `actions/compact.py` should only contain the
  module docstring, `from __future__ import annotations`, and (if any
  left) re-exports of the moved template helpers for backward-compat
- [ ] If `actions/compact.py` is effectively empty after the deletions,
  **delete the file entirely** (`git rm`) and ensure nothing imports
  from it anywhere. Run grep to confirm:
  - `grep -rn "squadron.pipeline.actions.compact" src/ tests/`
  - Expect: zero matches
  - [ ] `CompactAction` class is gone
  - [ ] `register_action(ActionType.COMPACT, …)` is gone
  - [ ] `actions/compact.py` either gone entirely or reduced to a
    no-op placeholder (prefer fully deleted)

### T15: Delete compact-specific action tests

- [ ] Delete `tests/pipeline/actions/test_compact.py`
- [ ] Delete `tests/pipeline/actions/test_compact_sdk.py`
- [ ] In `tests/pipeline/actions/test_registry_integration.py`:
  - [ ] Remove the `CompactAction` import
  - [ ] Remove any assertion that `ActionType.COMPACT` appears in the
    registered actions list
  - [ ] Add an assertion that `ActionType.COMPACT` does **not** appear
    in `list_actions()` (positive confirmation of the deletion)
- [ ] Run `uv run pytest tests/pipeline/actions/ -v`
  - [ ] All remaining action tests pass
  - [ ] No test imports `CompactAction`
  - [ ] Registry integration test explicitly guards against
    re-registration

### T16: Delete `ActionType.COMPACT` enum value

- [ ] In `src/squadron/pipeline/actions/__init__.py`:
  - [ ] Remove the `COMPACT = "compact"` line from the `ActionType`
    StrEnum
- [ ] Grep for `ActionType.COMPACT` across `src/` and `tests/`:
  - Expect: zero matches
  - If any remain, fix them (most likely in a test this slice hasn't
    touched yet)
- [ ] Run `uv run pyright` — zero errors
  - [ ] `ActionType.COMPACT` no longer exists
  - [ ] Type-check clean

### T17: Commit — runtime compact deletion

- [ ] `uv run ruff format .`
- [ ] `uv run ruff check` — zero warnings
- [ ] `uv run pyright` — zero errors
- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] `git add -A`
- [ ] `git commit -m "refactor(reduce): delete compact action runtime path"`
  - [ ] Commit includes `actions/compact.py` deletion, enum removal,
    test deletions, and registry test update
  - [ ] All green before commit

---

### T18: Delete `### compact` section from `commands/sq/run.md`

- [ ] In `commands/sq/run.md`:
  - [ ] Delete the `### compact` section (~lines 86–91, from the
    heading through the blank line before `### summary`)
  - [ ] Confirm `### summary` now immediately follows `### commit`
- [ ] Grep `commands/sq/run.md` for `/compact [` — expect zero matches
- [ ] The "Note: session rotation cannot be automated…" paragraph in
  the summary section (line ~98) stays as-is
  - [ ] `### compact` section removed
  - [ ] `### summary` section unchanged

### T19: Refresh installed command file and commit run.md

- [ ] Run `uv run sq install-commands` to refresh
  `~/.claude/commands/sq/run.md`; grep to confirm `### compact` is gone
- [ ] `git add commands/sq/run.md`
- [ ] `git commit -m "docs: remove compact section from sq run command"`
  - [ ] Installed copy refreshed (local only, not committed)
  - [ ] Committed change isolated to the single file

---

### T20: Pipeline YAML validation — backward compat smoke test

- [ ] For each built-in pipeline using `compact:`, run
  `uv run sq run --validate <pipeline>` and confirm it passes:
  - [ ] `P6`
  - [ ] `slice`
  - [ ] `tasks`
  - [ ] `app`
  - [ ] `example`
  - [ ] Any `test-pipeline.yaml` under `src/squadron/data/pipelines/`
- [ ] Any validation error means `CompactStepType` no longer parses —
  stop and diagnose
  - [ ] All listed pipelines validate cleanly
  - [ ] Success criterion #7 from the slice doc exercised

### T21: End-to-end prompt-only smoke test

- [ ] Pick a lightweight slice with existing tasks (any completed slice
  under `project-documents/user/slices/`)
- [ ] Run `uv run sq run P6 <slice-name> --prompt-only > /tmp/166-smoke.json`
- [ ] Inspect the JSON:
  - [ ] Find the action whose parent step is a compact step
  - [ ] Assert `action_type == "summary"` and `emit == ["rotate"]`
  - [ ] Assert no action has a `command` starting with `/compact [`
  - [ ] Confirm steps after the compact step are well-formed
  - [ ] Prompt-only P6 produces a valid summary action for the compact step
  - [ ] Success criterion #1 from the slice doc exercised end-to-end

### T22: End-to-end SDK-mode smoke test

- [ ] Run `uv run sq run P6 <slice-name>` in SDK mode (no `--prompt-only`)
- [ ] Observe session rotation at the compact step
- [ ] Inspect the run state file and confirm at least one
  `compact_summaries` key corresponds to the rotated step
- [ ] If feasible, interrupt and `uv run sq run --resume <run-id>`;
  confirm the prior summary is reinjected
  - [ ] SDK mode still rotates; `compact_summaries` still populated
  - [ ] Resume seeding still works
  - [ ] Success criteria #2 and #8 from the slice doc exercised

### T23: Source-cleanup grep verification

- [ ] `grep -rn "ActionType.COMPACT" src/` → zero matches
- [ ] `grep -rn "CompactAction" src/` → zero matches
- [ ] `grep -rn "_render_compact" src/` → zero matches
- [ ] `grep -rn "/compact \[" commands/ src/` → zero matches
- [ ] `grep -rn "ActionType.COMPACT" tests/` → zero matches
  - [ ] Every grep returns zero hits
  - [ ] Success criteria #3–#6 from the slice doc satisfied

### T24: Full quality gate

- [ ] `uv run ruff format .` — clean
- [ ] `uv run ruff check` — zero errors, zero unused-import warnings
- [ ] `uv run pyright` — zero errors
- [ ] `uv run pytest tests/ -v` — full suite green
- [ ] If any fixes needed, commit them:
  `git commit -m "fix: address lint/type findings from 166 refactor"`
  - [ ] All four gates clean
  - [ ] Success criterion #9 from the slice doc satisfied

---

### T25: Verify architecture document edits

- [ ] Re-read `project-documents/user/architecture/140-arch.pipeline-foundation.md`
- [ ] Confirm the four edits from the slice doc's "Architecture
  Document Updates" section are in place (action registry table line
  ~106, detailed subsection lines ~246–251, action registry diagram
  line ~514, `actions/` package structure line ~549)
- [ ] If any edit is missing, apply it now per the slice doc's exact
  language
- [ ] Confirm frontmatter `dateUpdated` is `20260411`
- [ ] Confirm the deliberately-unchanged references (lines 16, 22,
  222, 407, 444, 474, 509, 558, 640) are still intact
  - [ ] All four required edits present
  - [ ] Success criterion #11 from the slice doc satisfied

### T26: Mark slice complete and write DEVLOG

- [ ] Mark slice 166's checkbox `[x]` in
  `project-documents/user/architecture/140-slices.pipeline-foundation.md`
- [ ] Update slice frontmatter in
  `project-documents/user/slices/166-slice.compact-and-summary-unification.md`:
  `status: complete`, `dateUpdated: 20260411`
- [ ] Append a DEVLOG entry under `## 20260411` titled "Slice 166:
  Compact/Summary Unification — Complete" covering: the
  `CompactAction` / `ActionType.COMPACT` / `_render_compact` deletions,
  the `CompactStepType.expand()` rewrite, the state gate rewrite, the
  template helper move, and any surprises
- [ ] `git add project-documents/user/architecture/140-arch.pipeline-foundation.md project-documents/user/architecture/140-slices.pipeline-foundation.md project-documents/user/slices/166-slice.compact-and-summary-unification.md DEVLOG.md`
- [ ] `git commit -m "docs: mark slice 166 complete"`
  - [ ] Slice plan checkbox flipped
  - [ ] Slice frontmatter marked complete
  - [ ] DEVLOG entry written
  - [ ] Slice 166 ready for merge to main

---

## Out-of-Scope / Future Work

Captured for visibility; **do not** implement in this slice:

1. Rename `RunState.compact_summaries` → `session_summaries` and
   `CompactSummary` → `PersistedSessionSummary`. Schema version bump
   with backward-compat read path. Effort: 2/5.
2. Rename `src/squadron/data/compaction/` → `src/squadron/data/summaries/`
   and `load_compaction_template` → `load_summary_template`. Effort: 1/5.
3. Deprecation warning when `compact:` YAML is parsed, and eventual
   alias removal. Not urgent. Effort: 1/5.
