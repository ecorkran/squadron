---
docType: devlog
scope: project-wide
description: Internal session log for development work and project context
---

# Development Log

Internal work log for squadron project development.

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Phase 4 Design Complete

**Completed:**
- Created `user/slices/191-slice.dispatch-summary-context-injection.md`
- New module `pipeline/summary_context.py` with `assemble_dispatch_context()` — pure function that extracts content from `prior_outputs` by action type (dispatch responses, review findings, build_context text, prior summaries) and assembles a delimited context block
- Integration point: `_execute_summary()` prepends context block to instructions for non-SDK profiles only; SDK path unchanged
- Dependencies: slices 161 (summary step) and 164 (profile-aware routing), both complete

**Design decisions:**
- Context prepended to instructions (not a separate system message) — keeps `capture_summary_via_profile` interface unchanged across providers
- Full artifact contents injected, not metadata summaries — the summary model's job is to summarize
- No YAML configuration — context injection is unconditional for non-SDK profiles
- `match/case` on `ActionType` enum for extraction dispatch, not string labels

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/163-tasks.pipeline-run-summary-persistence-and-restore.md` (158 lines, 14 tasks)
- Tasks cover: source verification (T1), emit.py changes (T2–T4), _project threading (T5–T6), commit (T7), summary_instructions --restore (T8–T9), summary.md --restore branch (T10), run.md alignment (T11), commit (T12), verification (T13), slice completion (T14)
- Test-with pattern: T4 follows T3, T6 follows T5, T9 follows T8
- Review: PASS (minimax). One NOTE addressed: T11 updated to remove stale `_precompact-hook` reference (removed in slice 162); uses `cf status` for project name resolution instead

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

### Slice 163: Pipeline Run Summary Persistence and Restore — Phase 4 Design Complete

**Completed:**
- Created slice design at `user/slices/163-slice.pipeline-run-summary-persistence-and-restore.md`
- Added slice overview to `140-slices.pipeline-foundation.md` as entry 23 (index 163)
- Fixed `run.md` clipboard bug: summary action handler now uses `pbcopy`/`xclip`/`wl-copy` via Bash instead of telling the user to copy manually

**Design decisions:**
- Default `emit: [file]` path: `~/.config/squadron/runs/summaries/{project}-{pipeline}.md` (latest-only overwrite)
- Restore via `/sq:summary --restore` — reads most recent summary for current project, no run-id needed
- Project name resolved from CF via `gather_cf_params()` (existing helper)
- Prompt-only `run.md` handler writes to same conventional path via Bash
- `_project` threaded as internal param through `ActionContext` during pipeline init

**Status:**
- Phase 4 complete. Ready for review, then Phase 5 (task breakdown).

---

### Slice 152: Pipeline Documentation and Authoring Guide — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/152-tasks.pipeline-documentation-and-authoring-guide.md` (172 lines, 14 tasks)
- Tasks cover: source artifact verification, `docs/PIPELINES.md` creation (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline, Prompt-Only Mode), README.md update, final verification walkthrough, and DEVLOG
- Verification tasks follow each major section (T1 verifies source before writing; T12 runs the full design walkthrough; T13 verifies README)
- No code changes in this slice — documentation only

**Key notes:**
- T1 (source verification) must be completed before writing documentation — particularly to confirm ActionType enum, registered step types, and built-in pipeline file list match the slice design
- The YAML quoting footgun for parameter placeholders must be prominent in the grammar section
- `test-pipeline.yaml` and `app.yaml` in pipelines/ are not for user documentation; exclude from the built-in pipelines table

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/154-tasks.prompt-only-loops.md` (260 lines, 19 tasks)
- Tasks follow test-with pattern: each implementation task is immediately followed by its tests before the next implementation task
- Commit checkpoints placed after coherent logical units (state model, state manager methods, render function, each CLI handler, integration test, closeout)
- No schema version bump needed — `LoopContext` additive with `None` default on `RunState`
- Key implementation sequence: `LoopContext` model → `StateManager` loop methods → `LoopInstructionContext` + `render_each_step_instructions()` → `executor.py` rename → `_handle_prompt_only_init` → `_handle_prompt_only_next` → `_handle_step_done` → integration test → verification walkthrough

**Status:**
- Phase 5 complete. Ready for Phase 6 (Slice Execution).

---

### Slice 154: Prompt-Only Loops — Design Complete (Refreshed)

**Completed:**
- Recreated slice design document at `user/slices/154-slice.prompt-only-loops.md` (previous version was deleted from working tree)
- Design refreshed to reflect current codebase state: schema v3 (no version bump needed — `LoopContext` is additive with `None` default), existing `CompactSummary` pattern, `ExecutionMode` enum
- Core design unchanged from original: flatten `each` loop iterations into prompt-only instruction stream via `LoopContext` state tracking
- Key implementation points: `LoopContext` Pydantic model on `RunState`, `render_each_step_instructions()` in prompt renderer, loop-aware `--step-done` advancement, cached collection items in state for deterministic resume
- Slice plan entry at `140-slices.pipeline-foundation.md` already has materialized index (154) and design-complete link

**Status:**
- Design complete. Ready for Phase 5 (Task Breakdown).

---

## 20260407

### Slice 157: PreCompact Hook for Interactive Claude Code — Phase 6 Implementation Complete

**Completed:**
- All 15 tasks (T1–T15) in `user/tasks/157-tasks.precompact-hook-for-interactive-claude-code.md` implemented and marked complete.
- New shared module `src/squadron/pipeline/compact_render.py` with `LenientDict` + `render_with_params`, extracted from `actions/compact.py`. Both the compact action and the PreCompact hook consume it.
- New hidden Typer subcommand `sq _precompact-hook` (registered on the top-level app with `hidden=True`). Not listed in `sq --help`; direct invocation still works. Emits the Claude Code `PreCompact` payload on stdout, always exits 0.
- New module `src/squadron/cli/commands/install_settings.py` with `settings_json_path`, `_load_settings`, `_save_settings`, `write_precompact_hook`, `remove_precompact_hook`, and `_is_squadron_entry`. Squadron owns its entry in `.claude/settings.json` via a `_managed_by: "squadron"` marker; third-party hooks are preserved on both install and uninstall.
- `sq install-commands` / `sq uninstall-commands` extended with `--hook-target` option (default `./.claude/settings.json`). Installation is idempotent; uninstall tidies `hooks.PreCompact` and `hooks` keys when they become empty.
- Two new config keys: `compact.template` (default `"minimal"`) and `compact.instructions` (default `None`). Literal wins at resolve time.
- `_gather_params` uses best-effort `ContextForgeClient()` with `os.chdir` context management (the CF client has no `cwd` kwarg — task file's pseudocode was updated in practice to match the real API). Catches `ContextForgeError`, `ContextForgeNotAvailable`, `FileNotFoundError`, `OSError`.
- Empty CF values (e.g. `slice=""` as the current squadron project reports) are **omitted** from params so `{slice}` renders as a literal placeholder rather than empty text — discovered during smoke testing and fixed in T14.
- README updated with "Interactive `/compact` for Claude Code" section.
- Full test suite: 1315 passed, 0 failures. Pyright: 0 errors. Ruff: clean.

**Commits on `157-slice.precompact-hook-for-interactive-claude-code` branch:**
- `feat: add compact.template and compact.instructions config keys`
- `refactor: extract LenientDict and render_with_params to compact_render module`
- `feat: add hidden _precompact-hook subcommand for interactive Claude Code`
- `feat: add settings.json merge helpers for PreCompact hook install`
- `feat: install PreCompact hook entry during sq install-commands`
- `docs: document PreCompact hook and compact config keys`
- `chore: rename hook helpers to public names to satisfy pyright`
- `fix: omit empty CF params so PreCompact hook preserves placeholders`
- `docs: mark slice 157 PreCompact hook for interactive Claude Code complete` (pending)

**Deviations from task file:**
- Renamed module-public helpers from `_write_precompact_hook` / `_remove_precompact_hook` / `_settings_json_path` to non-underscored names because pyright's `reportPrivateUsage` flagged cross-module usage with leading underscores. Functionally identical; names reflect convention more accurately.
- Tests for T3/T4/T5 and the module file itself were combined into one commit because all three helpers live in the same file; splitting would have been artificial.
- Test T14 revealed the CF empty-string behavior, which was fixed in `_gather_params` with a tiny non-destructive change: only populate `slice` and `phase` when truthy.
- Also moved the `patch_config_paths` fixture from `tests/config/conftest.py` up to `tests/conftest.py` so CLI command tests can reuse it.

**Smoke tested (automatable parts):**
- `sq install-commands` writes the expected `.claude/settings.json` shape.
- `sq _precompact-hook` emits valid JSON with `hookEventName == "PreCompact"`.
- `{slice}` placeholder preserved when CF reports empty slice.
- Literal `compact.instructions` override wins over template.
- `sq --help` hides the command; `sq _precompact-hook --help` still works.
- `sq uninstall-commands` cleanly removes the entry.

**Not verified (requires human in the loop):**
- Step 6 of the verification walkthrough: real `/compact` in an interactive VS Code Claude Code session or `claude` CLI. Flagged in the slice design for follow-up. The hook payload schema (`hookSpecificOutput.additionalContext`) is based on Claude Code docs; if it turns out to differ, the fix is a single line in `precompact_hook.py` plus one test update.

**Status:**
- Slice 157 complete. Slice plan `140-slices.pipeline-foundation.md` slot 157 checked off.
- Branch: `157-slice.precompact-hook-for-interactive-claude-code` — ready for merge to `main` pending the human-driven `/compact` smoke test.

---

## 20260405

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Created comprehensive slice design document at `user/slices/154-slice.prompt-only-loops.md`
- Detailed design for extending prompt-only executor (slice 153) with collection loop support
- State schema extension: `RunState` with `LoopContext` field for tracking loop progress across `--next` calls
- Loop iteration tracking: Inner steps within `each` blocks named with iteration index (e.g., `design-each-0`, `tasks-each-1`)
- Successive iteration as instruction stream: Caller doesn't need loop awareness, just calls `--next` repeatedly
- Step instruction output format extended: JSON includes `loop_context` with current item data and loop position
- State persistence for loop resume: Saved loop state allows resuming mid-iteration without re-querying collection
- Verification walkthrough with concrete examples: 6-step scenario (3 items × 2 inner steps)
- Integration: Slash command (`/sq:run`) automatically compatible with loops (no changes needed)

**Status:**
- Design complete and ready for Phase 5 (Task Breakdown)
- Slice plan entry updated: `140-slices.pipeline-foundation.md` now marks slice 154 complete with link to design

**Key Design Decisions:**
- **Loop iterations flattened into instruction stream:** Progressive `--next` calls return successive iteration steps as if sequential. Caller logic unchanged.
- **LoopContext in RunState:** Tracks current item, item index, completed items, total items. Allows mid-loop resume without re-execution or re-querying.
- **Step naming with iteration index:** `{step_name}-each-{item_index}` ensures uniqueness and traceability across iterations.
- **Prompt-only loop output includes item data:** JSON `loop_context` field contains the bound item's resolved fields (e.g., `slice.index: "151"`).
- **No convergence strategies in prompt-only mode:** Falls back to basic max-iteration (inherited from slice 149). Convergence is SDK executor (slice 155) scope.
- **Variables resolved at instruction-generation time:** Bound item fields like `{slice.index}` are replaced in instruction JSON, not left as placeholders.
- **Collection items persisted in state:** Avoids re-querying CF mid-loop. Enables fast resume and deterministic iteration order.

**Dependencies:**
- Slice 153 (Prompt-Only Pipeline Executor) — prerequisite, extends `render_step_instructions()` and state model
- Slice 149 (Pipeline Executor and Loops) — loop execution logic reference; prompt-only mirrors this behavior
- Slice 150 (Pipeline State and Resume) — extended `RunState` schema with loop context
- Slice 126 (CF Integration) — collection sources (`cf.unfinished_slices()`)

**Architecture Overview:**
- No new modules; extends existing `prompt_renderer.py` with loop awareness
- `LoopContext` dataclass added to `models.py` for state tracking
- `StepInstructions` output extended with `loop_context` field (JSON-serializable)
- `StateManager.record_step_done()` enhanced to detect iteration-pattern step names and update `loop_context.completed_items`
- State file schema versioned; v1 (pre-loop) files backward compatible with `loop_context: null`

**Implementation Notes:**
- Effort: 2/5 (low complexity; leverages existing slice 153 patterns and slice 149 loop logic)
- Test strategy: Mock CF queries, verify iteration progression, validate step naming, test state serialization
- No changes needed to `/sq:run` slash command (works transparently with loop iterations)
- Convergence loop strategies generate warning and fall back to max-iteration (same as executor in 149)

