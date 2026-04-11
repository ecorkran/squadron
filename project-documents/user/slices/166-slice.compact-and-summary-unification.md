---
docType: slice-design
slice: compact-and-summary-unification
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [161-summary-step-with-emit-destinations, 164-profile-aware-summary-model-routing]
interfaces: [CompactStepType, SummaryAction, ActionType, RunState.compact_summaries]
dateCreated: 20260411
dateUpdated: 20260411
status: complete
---

# Slice Design: Compact and Summary Unification

## Overview

Finish the abandoned refactor started in slice 161. Today `compact` and
`summary` are two half-merged code paths: in SDK mode `CompactAction`
delegates internally to `_execute_summary` with `emit=[rotate]`, so the
SDK path already treats compact as a summary alias. In prompt-only mode
`_render_compact` still emits a literal `/compact [...]` slash-command
string that does nothing — slash commands only fire when typed by the
user, so every prompt-only pipeline using `compact:` stalls.

The fix is to finish the unification at the source:
`CompactStepType.expand()` emits a **summary** action instead of a
compact action. `CompactAction`, `ActionType.COMPACT`, `_render_compact`,
the compact test class, and the compact section of `commands/sq/run.md`
are deleted. `compact:` in YAML remains a valid step-type alias at the
loader level — existing pipeline YAML files do not change. The summary
action becomes the single canonical runtime path for both step types in
both execution modes.

This is a **refactoring slice**. No new user-facing behavior. Success is
measured by (a) P6 and other compact-using pipelines working correctly
in prompt-only mode and (b) significant code deletion.

---

## Motivation

Slice 161 introduced `summary:` with `emit:` destinations and declared
`compact:` a backward-compatible alias. It did the work at the SDK
action level (`compact.py:200-218` delegates to `_execute_summary` with
`emit=[rotate]`), but stopped short of finishing the unification:

- `CompactAction` still exists as a separate action class
- `ActionType.COMPACT` still exists as a separate enum value
- `_render_compact` in `prompt_renderer.py` still emits the stale
  `/compact [...]` slash command (pre-161 design, now broken)
- `commands/sq/run.md` still has a `### compact` section telling the
  model to output the slash command and stop
- Tests still exercise compact as a distinct type

In prompt-only mode this leaves `compact:` steps broken: the model
outputs `/compact [...]` as text, Claude Code does not interpret it as a
slash command (only user-typed slash commands trigger), and the pipeline
stalls. Every pipeline shipping `compact:` (P6, slice, tasks, app,
example) is affected. P6 is the currently visible failure.

The fix is structural, not cosmetic: eliminate compact as a runtime
distinct code path, keep it only as YAML sugar, and route everything
through the summary action.

---

## Dependencies

| Dependency | What 166 Needs |
|---|---|
| 161 — Summary Step with Emit Destinations | `SummaryAction`, `emit` registry, `EmitKind.ROTATE`, `_execute_summary` |
| 164 — Profile-Aware Summary Model Routing | Summary path that handles both SDK and non-SDK model profiles |

Both are complete.

---

## Migration Plan

This is a refactor slice. The source/destination mapping is the core
deliverable.

### Source → Destination map

| Source (to delete / rewrite) | Destination |
|---|---|
| `CompactAction` class in `src/squadron/pipeline/actions/compact.py` | **Deleted.** All behavior already exists in `SummaryAction`. |
| `register_action(ActionType.COMPACT, CompactAction())` | **Deleted.** No runtime action is typed as compact anymore. |
| `ActionType.COMPACT` enum value in `src/squadron/pipeline/actions/__init__.py` | **Deleted.** Only `ActionType.SUMMARY` remains for this capability. |
| `CompactStepType.expand()` in `src/squadron/pipeline/steps/compact.py` — returns `[("compact", {...})]` | **Rewritten** to return `[("summary", {..., "emit": ["rotate"]})]`. Template, model, keep, summarize pass through. Step type registration stays — `compact:` YAML still parses. |
| `_render_compact()` in `src/squadron/pipeline/prompt_renderer.py` | **Deleted.** No code path produces a compact action, so no renderer is needed. |
| `ActionType.COMPACT: _render_compact` entry in `_BUILDERS` dispatch map | **Deleted.** |
| `### compact` section in `commands/sq/run.md` | **Deleted.** The summary section handles everything now. |
| `TestRenderCompact` class in `tests/pipeline/test_prompt_renderer.py` | **Deleted.** |
| `TestCompactAction` (and similar) in `tests/pipeline/actions/` | **Deleted.** SDK-mode coverage moves under summary tests (existing `TestSummaryAction` already covers `emit=[rotate]` — verify). |
| `_maybe_record_compact_summaries` in `src/squadron/pipeline/state.py` — gated on `ar.action_type != "compact"` | **Rewritten** to gate on summary actions whose resolved emit includes rotate. See §"Compact Summaries Recording" below. |

### Consumer updates (call sites that change)

- **Pipeline YAML files** using `compact:` (P6, slice, tasks, app, example):
  **no change**. `compact:` still parses and still produces rotate
  behavior. Backward compat verified by loader round-trip tests.
- **`CompactStepType.validate()`**: continues to validate the same
  config fields (`template`, `model`, `keep`, `summarize`). No field
  removals.
- **Runtime execution paths**: both SDK and prompt-only paths already
  handle summary actions with `emit=[rotate]`. No executor changes.

### What the `compact` YAML keyword means after this slice

| Layer | Pre-slice | Post-slice |
|---|---|---|
| YAML loader | parses `compact:` → `CompactStepType` | parses `compact:` → `CompactStepType` *(unchanged)* |
| Step expansion | `CompactStepType.expand()` → `[("compact", cfg)]` | `CompactStepType.expand()` → `[("summary", {..., "emit": ["rotate"]})]` |
| Action registry | `compact` → `CompactAction` | no `compact` action registered |
| SDK execution | `CompactAction.execute()` → `_execute_summary(..., emit=[rotate])` | `SummaryAction.execute()` with `emit=[rotate]` directly |
| Prompt-only rendering | `_render_compact()` → broken `/compact [...]` string | `_render_summary()` → summary instruction with `emit=["rotate"]` |
| `run.md` dispatch | hits `### compact` section (broken) | hits `### summary` section (works) |

`compact:` survives as a two-word YAML alias with no unique code below
the step expansion layer.

---

## Compact Summaries Recording

The trickiest corner. `state.py::_maybe_record_compact_summaries` is
currently gated on `ar.action_type != "compact"`:

```python
for ar in step_result.action_results:
    if ar.action_type != "compact" or not ar.success:
        continue
    # ... record ActionResult.outputs into state.compact_summaries
```

It persists successful compact-step outputs into
`RunState.compact_summaries` so resume logic (`active_compact_summary_for_resume`)
can reinject a prior summary when a pipeline resumes from a later step.

After the refactor, no action is compact-typed. If the gate is not
updated, resume loses the reinjection feature — silently. This is the
one real risk in the slice.

### Decision

Gate the recording on "**summary action whose effective emit
destinations include rotate**":

```python
for ar in step_result.action_results:
    if ar.action_type != "summary" or not ar.success:
        continue
    if "rotate" not in _effective_emit_destinations(ar):
        continue
    # ... record into state.compact_summaries as before
```

`_effective_emit_destinations` reads the recorded emit list from the
ActionResult's outputs (SummaryAction already writes it). The field
name `compact_summaries` in `RunState` is **preserved** to avoid a
schema bump; the dataclass name `CompactSummary` is also preserved.
Both are legacy names for "persisted session summaries eligible for
resume seeding."

A later cleanup pass can rename `compact_summaries` → `session_summaries`
and `CompactSummary` → `PersistedSessionSummary`, but that is a schema
migration, out of scope here. A note goes in the slice's Future Work.

### Schema version

**No schema version bump.** Field names and shapes are unchanged. The
only runtime difference is *which* action triggers the recording, and
that gate lives in Python, not in the persisted schema.

---

## Files Affected

### Modified

- `src/squadron/pipeline/steps/compact.py` — rewrite `expand()` to emit
  a summary action. Keep validation and registration.
- `src/squadron/pipeline/prompt_renderer.py` — delete `_render_compact`
  and its entry in `_BUILDERS`. No other changes required (summary
  rendering already works).
- `src/squadron/pipeline/state.py` — rewrite
  `_maybe_record_compact_summaries` gate per the decision above.
- `commands/sq/run.md` — delete `### compact` section.
- `src/squadron/pipeline/actions/__init__.py` — remove `ActionType.COMPACT`.
- `project-documents/user/architecture/140-arch.pipeline-foundation.md` —
  **updated during review to address F004** (documentation-sync
  concern). See §"Architecture Document Updates" below for the applied
  changes.

### Deleted

- `src/squadron/pipeline/actions/compact.py` — entire file (including
  `CompactAction`, `register_action(ActionType.COMPACT, ...)`, and the
  action-level config validation). **Exception:** the
  `load_compaction_template()` and `render_instructions()` helpers
  currently living in this file are shared with the summary action —
  they must be **moved**, not deleted. See §"Template helpers" below.
- `tests/pipeline/test_prompt_renderer.py::TestRenderCompact` — delete.
- Any `tests/pipeline/actions/test_compact*.py` — delete (identify
  during implementation; coverage must migrate into summary tests if
  any scenario is not already covered).

### Unchanged

- All pipeline YAML files (P6, slice, tasks, app, example,
  test-pipeline) — `compact:` continues to parse and function.
- `src/squadron/data/compaction/*.yaml` templates — still used as the
  instruction source for both `compact:` and `summary:` step types.
  Template naming is historical, not functional; renaming the directory
  is a separate cleanup.
- `SummaryAction`, `SummaryStepType`, `_render_summary`,
  `_execute_summary` — all untouched.
- `RunState.compact_summaries` field and `CompactSummary` dataclass —
  names preserved, schema unchanged.

### Template helpers (subtle)

`compact.py` currently hosts `load_compaction_template` and
`render_instructions`, which the summary action imports from it.
Deleting `compact.py` wholesale would break those imports. During
implementation, **move** both functions (plus `CompactionTemplate` and
`_parse_template`) into a new `src/squadron/pipeline/compaction_templates.py`
module (or into `pipeline/actions/summary.py` if simpler — implementer's
call). Update summary's import accordingly. This move is mechanical but
must not be skipped.

---

## Architecture Document Updates

`140-arch.pipeline-foundation.md` was updated during review to address
finding F004 (documentation-sync concern). Four edits applied:

1. **Action registry table (line 106).** Removed the `compact` row.
   Added a `summary` row: *"Generate a session summary and emit to
   destinations (stdout, file, clipboard, rotate) — Instruction
   rendering, summary capture, emit dispatch, session rotation."*

2. **"compact" detailed subsection (lines ~246-251).** Rewritten as
   **`compact` / `summary`** with an explanation that `summary` is the
   single runtime action; `compact` survives as a YAML step-type alias
   that expands to `summary` with `emit=[rotate]` hardcoded. Frames the
   step-type layer as the policy surface and the action layer as
   unified under summary.

3. **Action registry diagram (line 514).** Replaced
   `dispatch │ review │ compact │ checkpoint │ cf-op │ …` with
   `dispatch │ review │ summary │ checkpoint │ cf-op │ …`.

4. **`actions/` package structure (line ~549).** Replaced
   `compact.py  # Parameterized compaction` with
   `summary.py  # Generate + emit session summaries`. The
   `steps/compact.py` entry further down is **kept** — that file
   remains as the step-type alias surface.

Frontmatter `dateUpdated` bumped to `20260411`.

### Deliberately left unchanged

Compact references at the concept or step-type layer are correct
post-refactor and were **not** touched:

- Prose about "compaction" as a capability concept (lines 16, 22).
- YAML example `- compact:` in a pipeline snippet (line 222).
- Unrelated "compact, machine-parseable" JSON description (line 407).
- Example JSON with `"step": "compact"` (line 444) — valid step-type label.
- "When a compact step executes, the session rotates..." (line 474) —
  accurate at step-type level.
- Step type registry diagram including `compact` (line 509).
- `steps/compact.py` package entry (line 558) — file still exists.
- "core step types (phase, compact, review, collection, devlog)"
  (line 640).

---

## Cross-Slice Interfaces

### Provided

- **Simplified step/action layer**: after this slice, there is exactly
  one runtime action type for generating and emitting session
  summaries. Downstream slices (180-band, future refactors) have one
  fewer half-abstraction to reason about.
- **Unblocked P6**: P6 (and every other pipeline using `compact:`) is
  immediately functional in prompt-only mode.

### Consumed

- `SummaryAction` and its `emit=[rotate]` behavior (slice 161)
- `run_review_with_profile`-style profile-aware routing as applied to
  summary (slice 164)

### Not Affected

- `PreCompact` hook (slice 157) — entirely unrelated. That hook
  intercepts the user-typed `/compact` command in interactive Claude
  Code sessions. It shares naming with the compact step type but no
  code.
- `/sq:summary` slash command (slice 162) — independent.
- Compaction templates directory (`src/squadron/data/compaction/`) —
  data files stay in place. Directory rename is out of scope.

---

## Success Criteria

1. Running `sq run P6 <slice> --prompt-only` produces step JSON where
   the compact step's action has `action_type: "summary"` and
   `emit: ["rotate"]`. The `/compact [...]` slash-command string does
   not appear anywhere in the rendered output.

2. Running `sq run P6 <slice>` (SDK mode) completes the compact step
   successfully with the same rotate behavior as before this slice.
   Session rotation still seeds the next session with the summary.

3. `grep -r "ActionType.COMPACT" src/` returns no matches (in source).
4. `grep -r "CompactAction" src/` returns no matches.
5. `grep -r "_render_compact" src/` returns no matches.
6. `grep -r "/compact \[" commands/` returns no matches.

7. All pipelines using `compact:` (`P6.yaml`, `slice.yaml`, `tasks.yaml`,
   `app.yaml`, `example.yaml`, `test-pipeline.yaml` if applicable) pass
   `sq run --validate <pipeline>` without error or warning.

8. Pipeline runs that rotate (via either `compact:` or `summary: emit:
   [rotate]`) continue to populate `RunState.compact_summaries` in the
   persisted state file. Resume from a later step reinjects the summary
   as before. Validated with an explicit integration test.

9. Full test suite (`pytest`) passes. Compact-specific tests are
   deleted; summary tests cover all paths. No new dead-code warnings.

10. `commands/sq/run.md` has no `### compact` section. `sq install-commands`
    writes the updated file to `~/.claude/commands/sq/run.md`.

11. `140-arch.pipeline-foundation.md` no longer lists compact as a
    distinct action in any of the four locations called out in §"Architecture
    Document Updates". **Applied during review.**

---

## Verification Walkthrough

Post-implementation demo:

```bash
# 1. Confirm step expansion produces a summary action
sq run P6 <any-slice-with-tasks> --prompt-only 2>/dev/null | \
  python3 -c "import sys, json; d = json.load(sys.stdin); \
  [print(a['action_type'], a.get('emit')) for a in d['actions']]"
# Expect: the compact step's action printed as 'summary ['rotate']'
# Expect: no '/compact' slash commands anywhere

# 2. Confirm source cleanup
grep -rn "ActionType.COMPACT\|CompactAction\|_render_compact" src/
# Expect: no matches

grep -n "### compact" commands/sq/run.md
# Expect: no matches

# 3. Confirm YAML backward compat
for p in P6 slice tasks app example; do
  sq run --validate $p 2>&1 && echo "$p OK"
done
# Expect: all five validate cleanly

# 4. Confirm resume seeding still works
#    (run a pipeline with compact, interrupt, resume, check state file)
sq run slice <some-slice>     # SDK mode run that hits a compact step
# ... let it rotate, then interrupt ...
cat ~/.config/squadron/runs/run-*-slice-*.json | \
  python3 -c "import sys, json; d = json.load(sys.stdin); \
  print('compact_summaries:', list(d.get('compact_summaries', {}).keys()))"
# Expect: at least one key corresponding to the rotated step

sq run --resume <run-id>
# Expect: the resumed run injects the prior summary as before

# 5. Full test suite
pytest
# Expect: green
```

---

## Implementation Notes

### Development Approach

Suggested order:

1. **Move template helpers** out of `actions/compact.py` into a new
   module (or into `actions/summary.py`). Update summary's imports. Run
   `pytest tests/pipeline/` — baseline should still be green.
2. **Rewrite `CompactStepType.expand()`** to emit a summary action with
   `emit=[rotate]`. Run `pytest` — some tests will fail (compact step
   tests expecting `[("compact", ...)]` output). Fix or delete those
   tests as appropriate.
3. **Update `state.py::_maybe_record_compact_summaries`** to gate on
   summary + rotate emit. Add a targeted integration test that proves
   `compact_summaries` still populates after a summary-with-rotate step.
4. **Delete `_render_compact`** and its `_BUILDERS` entry. Delete
   `TestRenderCompact`. Run `pytest`.
5. **Delete `CompactAction`** and the `compact` action registration.
   Delete any remaining tests that directly instantiate `CompactAction`.
   Delete `ActionType.COMPACT`.
6. **Delete `actions/compact.py`** entirely once all its contents have
   been moved or deleted.
7. **Delete `### compact` section** from `commands/sq/run.md`. Run
   `sq install-commands` locally to refresh the installed copy.
8. **End-to-end smoke test**: run `sq run P6 <slice> --prompt-only` and
   `sq run P6 <slice>` (SDK mode) against a real slice with existing
   tasks. Confirm both modes complete without stalling.

This order keeps the tree green as long as possible and localizes
breakage to predictable steps.

### Testing Strategy

- **Unit**: rewritten `CompactStepType.expand()` has a test that asserts
  output shape is `[("summary", {"emit": ["rotate"], ...})]` and that
  template/model/keep/summarize fields pass through.
- **Unit**: `_maybe_record_compact_summaries` has a test with a fake
  StepResult containing a summary-action ActionResult whose outputs
  include rotate in the emit list — asserts the state record is created.
- **Integration**: existing tests for P6, slice, etc. pipelines should
  be run in both SDK and prompt-only modes and continue to pass. If any
  of those tests mock `CompactAction` directly, they need to be updated
  to mock `SummaryAction` or removed.
- **Validation**: `sq run --validate <pipeline>` for every built-in
  pipeline containing `compact:`.
- **`pyright` / `ruff`** clean after all deletions — no unused imports,
  no references to deleted symbols.

### Risks

- **Low overall.** SDK mode already treats compact as a summary alias
  internally, so there is no behavior change for the currently-working
  path. Prompt-only mode is currently broken, so any change is a net
  improvement.
- **One real risk**: the `_maybe_record_compact_summaries` gate change.
  If mis-coded, resume-with-reinjection silently stops working. This is
  why it has its own targeted integration test in the acceptance
  criteria rather than relying on the broader test suite.
- **Import fan-out from deleting `actions/compact.py`**: multiple tests
  and non-test modules may import from it. The implementer must find
  every import site and fix it before running the full suite.

---

## Future Work

1. **Rename `compact_summaries` → `session_summaries`** in `RunState`
   and `CompactSummary` → `PersistedSessionSummary`. This is a schema
   version bump with a backward-compat read path for old state files.
   Effort: 2/5.

2. **Rename `src/squadron/data/compaction/` → `src/squadron/data/summaries/`**
   and rename `load_compaction_template` → `load_summary_template`.
   Historical naming; functionally it is a summary template directory
   now. Effort: 1/5.

3. **Deprecation note for `compact:` YAML keyword.** Once the ecosystem
   has moved to `summary: emit: [rotate]` as the canonical form, emit a
   deprecation warning when `compact:` is parsed and eventually remove
   the alias. Not urgent — no user harm from keeping the alias
   indefinitely. Effort: 1/5.

---

## DEVLOG Entry

See DEVLOG.md under `## 20260411` — new entry: "Slice 166:
Compact/Summary Unification — Design Complete".
