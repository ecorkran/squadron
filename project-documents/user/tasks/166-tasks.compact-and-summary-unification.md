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

- [x] Read `src/squadron/pipeline/actions/compact.py` — confirm the
  four template helpers (`CompactionTemplate`, `_parse_template`,
  `load_compaction_template`, `render_instructions`) and the
  `CompactAction` class; note the `_USER_COMPACTION_DIR` constant
- [x] Read `src/squadron/pipeline/actions/summary.py` — confirm
  `SummaryAction`, `_execute_summary`, and the `emit_results` outputs
  shape written by a successful summary run
- [x] Read `src/squadron/pipeline/steps/compact.py` — confirm current
  `CompactStepType.expand()` returns `[("compact", action_config)]`
- [x] Read `src/squadron/pipeline/prompt_renderer.py` — confirm
  `_render_compact` at ~line 234, its `_BUILDERS` entry at ~line 344,
  and the `from squadron.pipeline.actions.compact import (...)` at the
  top of the file
- [x] Read `src/squadron/pipeline/state.py` — confirm
  `_maybe_record_compact_summaries` at ~line 228 and its
  `ar.action_type != "compact"` gate
- [x] Read `src/squadron/pipeline/actions/__init__.py` — confirm
  `ActionType.COMPACT = "compact"` and the StrEnum structure
- [x] Read `commands/sq/run.md` — confirm the `### compact` section at
  line 86 and the `### summary` section that follows
- [x] Grep for every import of `squadron.pipeline.actions.compact` in
  both `src/` and `tests/`; list them in this task file:
  - [x] `src/squadron/cli/commands/summary_run.py`
  - [x] `src/squadron/pipeline/prompt_renderer.py`
  - [x] `src/squadron/pipeline/summary_render.py`
  - [x] `src/squadron/pipeline/actions/summary.py`
  - [x] `tests/cli/commands/test_summary_run.py`
  - [x] `tests/pipeline/actions/test_compact.py`
  - [x] `tests/pipeline/actions/test_compact_sdk.py`
  - [x] `tests/pipeline/actions/test_registry_integration.py`
- [x] Grep for every occurrence of `CompactAction`, `ActionType.COMPACT`,
  and `_render_compact` in `src/` and `tests/` and catalog them
- [x] Grep for every occurrence of the literal string `"compact"` in
  `src/squadron/pipeline/` — confirm the ones that are safe to keep
  (step-type name, `action_type=` equality checks in state.py,
  `test_summary_integration.py` regression test) vs. ones that become
  dead
  - [x] Every call site understood before any code is touched
  - [x] Test sites that will fail are listed in the task file

---

### T2: Create `compaction_templates.py` module and move helpers

- [x] Create new file
  `src/squadron/pipeline/compaction_templates.py` with module docstring
  explaining its role as the shared source for compaction/summary
  template loading
- [x] Add `from __future__ import annotations` at the top
- [x] Move the following verbatim from
  `src/squadron/pipeline/actions/compact.py` into the new module:
  - [x] `_USER_COMPACTION_DIR` constant
  - [x] `CompactionTemplate` dataclass
  - [x] `_parse_template` function
  - [x] `load_compaction_template` function
  - [x] `render_instructions` function
- [x] Keep the existing imports each helper uses (`Path`, `yaml`, `cast`,
  `data_dir`, `LenientDict`) — move them too, pruning anything not
  referenced in the moved code
- [x] Do **not** touch `CompactAction` yet; leave `actions/compact.py`
  importing from the new module so the old class still works during
  the migration. Add at the top of `actions/compact.py`:
  - [x] `from squadron.pipeline.compaction_templates import (CompactionTemplate, load_compaction_template, render_instructions, _parse_template)` (or just the names the old class actually uses)
- [x] Verify old module no longer has duplicate definitions
  - [x] New module created at correct path
  - [x] Old `actions/compact.py` still compiles (imports from new home)
  - [x] No behavior change in this task

### T3: Update all consumers to import from `compaction_templates`

- [x] Update `src/squadron/cli/commands/summary_run.py` import from
  `squadron.pipeline.actions.compact` → `squadron.pipeline.compaction_templates`
- [x] Update `src/squadron/pipeline/prompt_renderer.py` import likewise
- [x] Update `src/squadron/pipeline/summary_render.py` import likewise
- [x] Update `src/squadron/pipeline/actions/summary.py` import likewise
  (note: this is a deferred `from … import …` inside a function body —
  update the deferred import too)
- [x] Update every test file that imports from
  `squadron.pipeline.actions.compact` for the template helpers (not
  `CompactAction`):
  - [x] `tests/cli/commands/test_summary_run.py` (three occurrences)
- [x] Run `uv run ruff check` — confirm no unused-import warnings in
  `actions/compact.py` from re-exporting the moved helpers (if any
  appear, add an `__all__` or direct re-export)
  - [x] Every non-test consumer imports from the new module
  - [x] `actions/compact.py` no longer owns the helpers (it may still
    import them for its own `CompactAction.execute` body during the
    migration)

### T4: Test — template helpers still load from new module

- [x] Run `uv run pytest tests/cli/commands/test_summary_run.py -v` —
  confirm green (these tests exercise `load_compaction_template` /
  `render_instructions` via the CLI)
- [x] Run `uv run pytest tests/pipeline/ -v` — confirm baseline still
  green before any behavior change
  - [x] Baseline remains green after the move

### T5: Commit — template helper extraction

- [x] `uv run ruff format .`
- [x] `git add src/squadron/pipeline/compaction_templates.py src/squadron/pipeline/actions/compact.py src/squadron/cli/commands/summary_run.py src/squadron/pipeline/prompt_renderer.py src/squadron/pipeline/summary_render.py src/squadron/pipeline/actions/summary.py tests/cli/commands/test_summary_run.py`
- [x] `git commit -m "refactor: extract compaction template helpers to shared module"`
  - [x] Working tree clean after commit
  - [x] Slice branch has one new commit

---

### T6: Rewrite `CompactStepType.expand()` to emit a summary action

- [x] In `src/squadron/pipeline/steps/compact.py` `expand()`:
  - [x] Build the same `action_config` dict as today (template, model,
    keep, summarize — preserve the `model` key even when `None` to
    match current behavior)
  - [x] Add `action_config["emit"] = ["rotate"]`
  - [x] Return `[("summary", action_config)]` instead of
    `[("compact", action_config)]`
- [x] Do **not** change `CompactStepType.validate()` — field validation
  stays as-is
- [x] Do **not** change the `register_step_type(StepTypeName.COMPACT, …)`
  line — `compact:` remains a valid YAML step-type
  - [x] `expand()` returns a single tuple with `"summary"` and
    `emit=["rotate"]`
  - [x] `template`, `model`, `keep`, `summarize` all pass through
    unchanged
  - [x] Step-type registration unchanged

### T7: Test `CompactStepType.expand()` new shape

- [x] In the existing compact step tests (likely
  `tests/pipeline/steps/test_compact_step.py` — locate it; if it does
  not exist, add it):
- [x] **Update or add** `test_compact_step_expands_to_summary_with_rotate`:
  - Assert `expand()` returns a single tuple
  - Assert `tup[0] == "summary"`
  - Assert `tup[1]["emit"] == ["rotate"]`
- [x] **Add** `test_compact_step_passes_through_template_model_keep_summarize`:
  - Build a `StepConfig` with all four fields populated
  - Assert each one is present unchanged in the expanded action config
- [x] **Add** `test_compact_step_with_no_model_emits_none`:
  - `StepConfig` without a `model` key → expanded action_config has
    `model: None` (matches current behavior)
- [x] Delete or update any existing test in the file that asserted
  `expand()` returns `[("compact", …)]`
- [x] Run `uv run pytest tests/pipeline/steps/test_compact_step.py -v`
  (or the correct path)
  - [x] All tests pass
  - [x] No test still expects the `("compact", …)` shape

### T8: Rewrite `_maybe_record_compact_summaries` gate

- [x] In `src/squadron/pipeline/state.py`:
  - [x] Change the gate from `ar.action_type != "compact"` to
    `ar.action_type != "summary"`
  - [x] Inside the loop body, after the success and type checks, parse
    the effective emit destinations from
    `ar.outputs.get("emit_results")`:
    - Expect a `list[dict[str, object]]` with each entry containing a
      `"destination"` key (string). `SummaryAction` writes this shape
      today — see `actions/summary.py` near the return of
      `_execute_summary`
    - If any entry has `destination == "rotate"` and `ok is True`,
      proceed to record the summary; otherwise `continue`
  - [x] The existing `"summary" in outputs and "source_step_index" in outputs`
    check stays (SummaryAction writes both)
  - [x] Keep the function name `_maybe_record_compact_summaries` — the
    **name** `compact_summaries` is preserved per the slice doc
- [x] Do **not** add a helper for emit parsing unless clarity demands
  it; one inline comprehension is enough
  - [x] Gate fires for summary-action results with successful rotate
    emit
  - [x] Gate does not fire for summary actions with stdout/file/clipboard
    only
  - [x] Gate does not fire for non-summary action types

### T9: Test `_maybe_record_compact_summaries` new gate

- [x] Open `tests/pipeline/test_summary_integration.py` — it already
  has `test_compact_alias_state_callback_still_fires` that exercises
  `_maybe_record_compact_summaries` directly with an ActionResult
- [x] **Update** that test so the fake `ActionResult` has
  `action_type="summary"` (not `"compact"`) and otherwise matches what
  the post-refactor summary action produces — including
  `emit_results=[{"destination": "rotate", "ok": True, ...}]`
- [x] **Add** `test_summary_action_without_rotate_emit_does_not_record`:
  - Fake `ActionResult` with `action_type="summary"`, success, outputs
    including `emit_results=[{"destination": "stdout", "ok": True}]`
  - After `cb(StepResult(...))`, assert
    `state.compact_summaries == {}`
- [x] **Add** `test_summary_action_with_failed_rotate_does_not_record`:
  - `emit_results=[{"destination": "rotate", "ok": False, "detail": "failure"}]`
  - Assert state is not recorded (the slice gate requires
    `ok is True`)
- [x] **Add** `test_non_summary_action_does_not_record`:
  - `action_type="dispatch"`, success, outputs contain a `"summary"`
    key (shouldn't matter)
  - Assert state is not recorded
- [x] Run `uv run pytest tests/pipeline/test_summary_integration.py -v`
  - [x] All four tests pass
  - [x] The existing compact-alias regression test is the canonical
    path test for the refactor

### T10: Commit — step expansion + state gate rewrite

- [x] `uv run ruff format .`
- [x] `uv run pytest tests/pipeline/ -v` — everything green except
  any compact-tests that will be deleted in T15
- [x] `git add src/squadron/pipeline/steps/compact.py src/squadron/pipeline/state.py tests/pipeline/steps/ tests/pipeline/test_summary_integration.py`
- [x] `git commit -m "refactor: route compact step through summary action"`
  - [x] Commit leaves tree in a buildable state (old `CompactAction`
    still exists and still registers, but no step type emits it — so
    the registration is dead code that will be removed next)

---

### T11: Delete `_render_compact` from `prompt_renderer.py`

- [x] In `src/squadron/pipeline/prompt_renderer.py`:
  - [x] Delete the entire `_render_compact` function (~lines 234–253)
  - [x] Remove the `ActionType.COMPACT: _render_compact,` entry from
    the `_BUILDERS` dict (~line 344)
  - [x] Remove the `load_compaction_template` / `render_instructions`
    imports at the top **only if** no other function in the file still
    uses them. `_render_summary` still calls them — so they stay.
- [x] Verify no other reference to `_render_compact` exists in the file
  - [x] `_BUILDERS` no longer maps `compact`
  - [x] File still imports from `compaction_templates` for summary use

### T12: Test — `_render_compact` removal

- [x] Open `tests/pipeline/test_prompt_renderer.py`:
- [x] **Delete** the entire `TestRenderCompact` class (all its test
  methods)
- [x] If any other test in the file constructs an `ActionInstruction`
  with `action_type=ActionType.COMPACT` or asserts on
  `/compact [...]` output, update or delete it
- [x] Scan for any test building a fake step with step_type `compact`
  and asserting the resulting `ActionInstruction.action_type` — those
  tests should now expect `action_type="summary"` (because
  `CompactStepType.expand()` emits a summary action). Update as needed.
- [x] Run `uv run pytest tests/pipeline/test_prompt_renderer.py -v`
  - [x] All remaining tests pass
  - [x] No test references `_render_compact` or `ActionType.COMPACT`

### T13: Add prompt-only smoke test — compact step renders as summary

- [x] In `tests/pipeline/test_prompt_renderer.py` (or the nearest
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
- [x] Run `uv run pytest tests/pipeline/test_prompt_renderer.py -v`
  - [x] New test passes
  - [x] Success criterion #1 from the slice doc is exercised

---

### T14: Delete `CompactAction` class and its action registration

- [x] In `src/squadron/pipeline/actions/compact.py`:
  - [x] Delete the `CompactAction` class (the entire
    `class CompactAction:` block, ~lines 118–251)
  - [x] Delete the `register_action(ActionType.COMPACT, CompactAction())`
    call at the bottom
- [x] At this point `actions/compact.py` should only contain the
  module docstring, `from __future__ import annotations`, and (if any
  left) re-exports of the moved template helpers for backward-compat
- [x] If `actions/compact.py` is effectively empty after the deletions,
  **delete the file entirely** (`git rm`) and ensure nothing imports
  from it anywhere. Run grep to confirm:
  - `grep -rn "squadron.pipeline.actions.compact" src/ tests/`
  - Expect: zero matches
  - [x] `CompactAction` class is gone
  - [x] `register_action(ActionType.COMPACT, …)` is gone
  - [x] `actions/compact.py` either gone entirely or reduced to a
    no-op placeholder (prefer fully deleted)

### T15: Delete compact-specific action tests

- [x] Delete `tests/pipeline/actions/test_compact.py`
- [x] Delete `tests/pipeline/actions/test_compact_sdk.py`
- [x] In `tests/pipeline/actions/test_registry_integration.py`:
  - [x] Remove the `CompactAction` import
  - [x] Remove any assertion that `ActionType.COMPACT` appears in the
    registered actions list
  - [x] Add an assertion that `ActionType.COMPACT` does **not** appear
    in `list_actions()` (positive confirmation of the deletion)
- [x] Run `uv run pytest tests/pipeline/actions/ -v`
  - [x] All remaining action tests pass
  - [x] No test imports `CompactAction`
  - [x] Registry integration test explicitly guards against
    re-registration

### T16: Delete `ActionType.COMPACT` enum value

- [x] In `src/squadron/pipeline/actions/__init__.py`:
  - [x] Remove the `COMPACT = "compact"` line from the `ActionType`
    StrEnum
- [x] Grep for `ActionType.COMPACT` across `src/` and `tests/`:
  - Expect: zero matches
  - If any remain, fix them (most likely in a test this slice hasn't
    touched yet)
- [x] Run `uv run pyright` — zero errors
  - [x] `ActionType.COMPACT` no longer exists
  - [x] Type-check clean

### T17: Commit — runtime compact deletion

- [x] `uv run ruff format .`
- [x] `uv run ruff check` — zero warnings
- [x] `uv run pyright` — zero errors
- [x] `uv run pytest tests/ -v` — all tests pass
- [x] `git add -A`
- [x] `git commit -m "refactor(reduce): delete compact action runtime path"`
  - [x] Commit includes `actions/compact.py` deletion, enum removal,
    test deletions, and registry test update
  - [x] All green before commit

---

### T18: Delete `### compact` section from `commands/sq/run.md`

- [x] In `commands/sq/run.md`:
  - [x] Delete the `### compact` section (~lines 86–91, from the
    heading through the blank line before `### summary`)
  - [x] Confirm `### summary` now immediately follows `### commit`
- [x] Grep `commands/sq/run.md` for `/compact [` — expect zero matches
- [x] The "Note: session rotation cannot be automated…" paragraph in
  the summary section (line ~98) stays as-is
  - [x] `### compact` section removed
  - [x] `### summary` section unchanged

### T19: Refresh installed command file and commit run.md

- [x] Run `uv run sq install-commands` to refresh
  `~/.claude/commands/sq/run.md`; grep to confirm `### compact` is gone
- [x] `git add commands/sq/run.md`
- [x] `git commit -m "docs: remove compact section from sq run command"`
  - [x] Installed copy refreshed (local only, not committed)
  - [x] Committed change isolated to the single file

---

### T20: Pipeline YAML validation — backward compat smoke test

- [x] For each built-in pipeline using `compact:`, run
  `uv run sq run --validate <pipeline>` and confirm it passes:
  - [x] `P6`
  - [x] `slice`
  - [x] `tasks`
  - [x] `app`
  - [x] `example`
  - [x] Any `test-pipeline.yaml` under `src/squadron/data/pipelines/`
- [x] Any validation error means `CompactStepType` no longer parses —
  stop and diagnose
  - [x] All listed pipelines validate cleanly
  - [x] Success criterion #7 from the slice doc exercised

### T21: End-to-end prompt-only smoke test

- [x] Pick a lightweight slice with existing tasks (any completed slice
  under `project-documents/user/slices/`)
- [x] Run `uv run sq run P6 <slice-name> --prompt-only > /tmp/166-smoke.json`
- [x] Inspect the JSON:
  - [x] Find the action whose parent step is a compact step
  - [x] Assert `action_type == "summary"` and `emit == ["rotate"]`
  - [x] Assert no action has a `command` starting with `/compact [`
  - [x] Confirm steps after the compact step are well-formed
  - [x] Prompt-only P6 produces a valid summary action for the compact step
  - [x] Success criterion #1 from the slice doc exercised end-to-end

### T22: End-to-end SDK-mode smoke test

- [x] Run `uv run sq run P6 <slice-name>` in SDK mode (no `--prompt-only`)
- [x] Observe session rotation at the compact step
- [x] Inspect the run state file and confirm at least one
  `compact_summaries` key corresponds to the rotated step
- [x] If feasible, interrupt and `uv run sq run --resume <run-id>`;
  confirm the prior summary is reinjected
  - [x] SDK mode still rotates; `compact_summaries` still populated
  - [x] Resume seeding still works
  - [x] Success criteria #2 and #8 from the slice doc exercised

### T23: Source-cleanup grep verification

- [x] `grep -rn "ActionType.COMPACT" src/` → zero matches
- [x] `grep -rn "CompactAction" src/` → zero matches
- [x] `grep -rn "_render_compact" src/` → zero matches
- [x] `grep -rn "/compact \[" commands/ src/` → zero matches
- [x] `grep -rn "ActionType.COMPACT" tests/` → zero matches
  - [x] Every grep returns zero hits
  - [x] Success criteria #3–#6 from the slice doc satisfied

### T24: Full quality gate

- [x] `uv run ruff format .` — clean
- [x] `uv run ruff check` — zero errors, zero unused-import warnings
- [x] `uv run pyright` — zero errors
- [x] `uv run pytest tests/ -v` — full suite green
- [x] If any fixes needed, commit them:
  `git commit -m "fix: address lint/type findings from 166 refactor"`
  - [x] All four gates clean
  - [x] Success criterion #9 from the slice doc satisfied

---

### T25: Verify architecture document edits

- [x] Re-read `project-documents/user/architecture/140-arch.pipeline-foundation.md`
- [x] Confirm the four edits from the slice doc's "Architecture
  Document Updates" section are in place (action registry table line
  ~106, detailed subsection lines ~246–251, action registry diagram
  line ~514, `actions/` package structure line ~549)
- [x] If any edit is missing, apply it now per the slice doc's exact
  language
- [x] Confirm frontmatter `dateUpdated` is `20260411`
- [x] Confirm the deliberately-unchanged references (lines 16, 22,
  222, 407, 444, 474, 509, 558, 640) are still intact
  - [x] All four required edits present
  - [x] Success criterion #11 from the slice doc satisfied

### T26: Mark slice complete and write DEVLOG

- [x] Mark slice 166's checkbox `[x]` in
  `project-documents/user/architecture/140-slices.pipeline-foundation.md`
- [x] Update slice frontmatter in
  `project-documents/user/slices/166-slice.compact-and-summary-unification.md`:
  `status: complete`, `dateUpdated: 20260411`
- [x] Append a DEVLOG entry under `## 20260411` titled "Slice 166:
  Compact/Summary Unification — Complete" covering: the
  `CompactAction` / `ActionType.COMPACT` / `_render_compact` deletions,
  the `CompactStepType.expand()` rewrite, the state gate rewrite, the
  template helper move, and any surprises
- [x] `git add project-documents/user/architecture/140-arch.pipeline-foundation.md project-documents/user/architecture/140-slices.pipeline-foundation.md project-documents/user/slices/166-slice.compact-and-summary-unification.md DEVLOG.md`
- [x] `git commit -m "docs: mark slice 166 complete"`
  - [x] Slice plan checkbox flipped
  - [x] Slice frontmatter marked complete
  - [x] DEVLOG entry written
  - [x] Slice 166 ready for merge to main

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
