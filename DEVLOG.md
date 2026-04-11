---
docType: devlog
project: squadron
dateCreated: 20260218
dateUpdated: 20260411
---

# Development Log

A lightweight, append-only record of development activity. Newest entries first.
Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).  This file differs from
CHANGELOG.md, in that this file is written from implementor perspective where CHANGELOG.md is
written from user perspective.

---

## 20260411

### Slice 181: Pool Resolver Integration and CLI — Design Complete

Created `project-documents/user/slices/181-slice.pool-resolver-integration-and-cli.md`.

Design extends `ModelResolver` with `pool_backend` and `on_pool_selection` callback params.
`_resolve_pool()` delegates to `PoolBackend.select()` (slice 180), then resolves the returned
alias through the existing alias registry — transparent to all action handlers. `RunState` gains
`pool_selections: list[dict]` with schema version bump to 4 (backwards-compatible). New
`sq pools` CLI (list / show / reset) follows the `sq models` pattern. Executor wires up
`PoolLoader.load()` and the logging callback when building `ModelResolver`.

---

### Slice 160: Interactive Checkpoint Resolution — Implementation Complete

Phase 6 complete. Three files changed:

- `executor.py`: Added `CheckpointResolution(StrEnum)`, `CheckpointDecision` dataclass,
  `_is_interactive()`, `_prompt_checkpoint_interactive()`. Modified `_execute_step_once`
  checkpoint detection block to call the handler; EXIT path returns PAUSED (unchanged),
  Accept/Override inject `override_instructions` into `merged_params` and continue.
- `actions/dispatch.py`: `_resolve_prompt` now reads `override_instructions` from
  `context.params` and prepends a delimited block when present.
- `prompt_renderer.py`: `_render_checkpoint` now describes all three options per trigger
  type. `run_id` injected into `render_params` so the resume command is correct.

All 1477 tests pass. `pyright` clean. No `RunState` schema change (stays v3).

---

### Slice 160: Interactive Checkpoint Resolution — Design Complete

Created `project-documents/user/slices/160-slice.interactive-checkpoint-resolution.md`.

Design confines the change to three files: `executor.py` (interactive handler +
`CheckpointResolution`/`CheckpointDecision` types), `actions/dispatch.py` (pick up
`override_instructions` from params), and `prompt_renderer.py` (enhanced checkpoint
instruction text). The Accept/Override path injects instructions into `merged_params` and
continues in-place; the Exit path is unchanged. No `RunState` schema bump required.
Updated slice plan entry 18 with Design Complete pointer.

---

### CHANGELOG rewrite — user perspective

Rewrote all CHANGELOG entries to answer "what can I do / what bug is fixed"
rather than listing internal class names, module paths, and slice refs.
Net: 338 lines removed, changelog is now readable without source context.

---

## 20260411

### Slice 164 implementation complete: profile-aware summary model routing

**Slice 164 — Phase 6 complete.**

- **What changed:**
  - New module `src/squadron/pipeline/summary_oneshot.py`:
    `is_sdk_profile()` predicate and `capture_summary_via_profile()` —
    near-copy of the ~40 relevant lines from `run_review_with_profile()`,
    review-specific paths stripped.
  - `_execute_summary()` now branches on resolved profile: SDK path
    (profile `None` or `"sdk"`) keeps `sdk_session.capture_summary()`;
    non-SDK path dispatches through the provider registry via
    `capture_summary_via_profile()`.
  - Rotation emit + non-SDK profile fails fast with a descriptive error
    at execution time (resolver not available at schema-validation time).
  - `_render_summary()` in `prompt_renderer.py` emits `model_switch` for
    SDK profiles and `command` (runnable `sq _summary-run …`) for
    non-SDK profiles.
  - New hidden CLI subcommand `sq _summary-run` (registered alongside
    `sq _summary-instructions`) as the CLI surface for prompt-only
    non-SDK summary execution.
  - `CompactAction` inherits the fix for free via the shared
    `_execute_summary()` helper.
  - 1452 tests pass; pyright and ruff clean.

- **OQ1 resolved:** Option A — new hidden `sq _summary-run` subcommand,
  matching the `_summary-instructions` naming convention. The subcommand
  name uses leading underscore (`_summary-run`) per project convention.

- **Surprises:**
  - `compact.py` imports `_execute_summary` inside the method body
    (deferred import), so tests must patch
    `squadron.pipeline.actions.summary._execute_summary`, not
    `squadron.pipeline.actions.compact._execute_summary`.
  - `--validate` in `sq run` only calls schema-level `validate()` — the
    rotate+non-SDK profile check fires at execution time, not validation
    time (resolver is execution-time only). Slice doc updated with
    caveat.

- **Pipelines unblocked:** Any pipeline summary step can now use cheap
  external models (minimax, gemini-flash, local) via their respective
  profiles. The only restriction is `emit: [rotate]`, which remains
  SDK-only.

---

### Slice 164 design + tasks; CI fix; phase pipelines now write summary files

**v0.3.8 release.**

- **Slice 164 (Profile-Aware Summary Model Routing)** — Phase 4 design
  and Phase 5 task breakdown complete via `/sq:run P4 164` and
  `/sq:run P5 164`. Both phases reviewed PASS by minimax-m2.7. Slice
  routes the summary action through the provider registry for non-SDK
  profiles, mirroring `run_review_with_profile()`. New module
  `summary_oneshot.py` houses `capture_summary_via_profile()` and the
  `is_sdk_profile()` predicate. 17 implementation tasks in
  `164-tasks.profile-aware-summary-model-routing.md`. Implementation
  deferred (Phase 6 not yet started).
- **CI fix** — `prompt_renderer.py:270` had a `dict[str, object]`
  narrow that pyright couldn't infer through; added
  `cast(list[object], emit_raw)` after the `isinstance(list)` check.
  Seven consecutive `main` builds had been red on this same error.
- **Phase pipelines now write summary files** — after re-running
  `sq install-commands` to refresh stale `summary.md` and `run.md`
  skills, discovered that all five phase pipelines (P1, P2, P4, P5, P6)
  emit only `[stdout, clipboard]` and never `[file]` — so slice 163's
  default-file-path branch had nothing to write to. Added `file` to
  every P*.yaml emit list. `/sq:summary --restore` now works
  end-to-end after any phase pipeline run.

**Commits:**
- `5d7ab9d` docs: add slice 164 profile-aware summary model routing design
- `32fc9e7` fix: cast emit list to satisfy pyright in _render_summary
- `f8c887a` docs: add slice 164 task breakdown
- (this commit) feat: emit pipeline summaries to file + bump to v0.3.8

## 20260410

### Slice 163: Pipeline Run Summary Persistence and Restore — Complete

**Phase 6 (implementation) complete.**

- Closes the "run pipeline in CLI terminal, restore context in VS Code" workflow gap
- Three implementation sites: `emit.py` (default file path), `executor.py` (_project injection), `summary_instructions.py` (--restore), `commands/sq/summary.md` (--restore branch), `commands/sq/run.md` (file-write step)
- Key decision: bare `"file"` in `emit:` YAML list now produces `EmitDestination(kind=FILE, arg=None)` rather than raising; default path is `~/.config/squadron/runs/summaries/{project}-{pipeline}.md`
- `_project` threaded into `ActionContext.params` via `gather_cf_params()` at pipeline init in `executor.py`; falls back to `"unknown"` when CF unavailable; caller-supplied `_project` not overwritten
- 31 new tests added (28 in test_emit.py, 3 in test_executor.py, 5 in test_summary_instructions.py)

**Commits:**
- `51a3342` feat: add default summaries path to emit and thread _project into ActionContext
- `1d6281f` feat: add --restore to /sq:summary and write summary to conventional path in run.md


**tasks: devlog-4**
- cf-op-0: PASS
- cf-op-1: PASS
- cf-op-2: PASS
- dispatch-3: PASS
- review-4: PASS (verdict: UNKNOWN)
- checkpoint-5: PASS
- commit-6: PASS
- compact-0: PASS

### Slice 152: Pipeline Documentation and Authoring Guide — Complete

**Deliverables created:**
- `docs/PIPELINES.md` — authoritative pipeline authoring guide (Quick Start, YAML Grammar, Step Type Catalog, Action Type Catalog, Model Resolution, Configuration Surface, Built-in Pipelines, Custom Pipeline Walkthrough, Prompt-Only Mode)
- `README.md` — added `## Pipelines (sq run)` section with quick-start and link to guide

**Discrepancies found during T1 verification (documented, not propagated from slice design):**
- `slice` pipeline has 2 params (`slice`, `review-model`); slice design table listed only `slice`
- `tasks`, `P5`, `P6` each have 3 params including `model`; design table showed 2
- `example.yaml` inline comment shows stale project path (`.squadron/pipelines/`); loader uses `project-documents/user/pipelines/` — guide uses loader path
- `app.yaml` is a WIP pipeline (same description as design-batch, has TODO comment) — excluded from docs

**Commits:**
- `4056c7b` docs: add pipeline authoring guide
- `5460177` docs: add sq run section to README

## 20260409

### Slice 162: /sq:summary — Clipboard Summary for Manual Context Reset

**Phase 4 (design) + Phase 5 (task breakdown) + Phase 6 (implementation) complete.**

- Motivated by unreliable `/compact [with instructions]` — user wants deterministic "clear with custom summary" using templates already built for pipeline compaction (slices 157/158)
- Design: slash command `/sq:summary [template]` + hidden `sq _summary-instructions` CLI. Current CC session generates the summary inline; squadron supplies template instructions + clipboard sink.
- Created `pipeline/summary_render.py` with `resolve_template_instructions()` and `gather_cf_params()` — logic salvaged from dead `precompact_hook.py`
- Removed `precompact_hook.py`, `install_settings.py`, and all PreCompact hook install/uninstall logic (dead code since 0.3.3)
- Reuses `compact.template` config key — no new config surface
- Clipboard via shell chain: `pbcopy` → `xclip` → `wl-copy` (Windows deferred)
- All 1400 tests pass, ruff clean, pyright clean
- Post-implementation: removed misleading "do not print to chat" instruction from summary.md — summary appearing in chat is correct and lets user verify before `/clear`; bumped to v0.3.4

## 20260408 (session 2)

**v0.3.3 release — merge, tag, PyPI publish**

- Caught that dispatch fix landed on `test-161-pipeline` instead of `161`; cherry-picked `07881d5` → `210950d`
- Bumped version 0.3.2 → 0.3.3, merged `161-slice.summary-step-with-emit-destinations` → main, tagged `v0.3.3`
- CI: both push and tag runs triggered; `publish` job succeeded; `squadron-ai==0.3.3` live on PyPI
- Verified full pipeline smoke test end-to-end (design → tasks → summary:rotate → design again) on separate branch; discarded test branch
- CHANGELOG restructured: collapsed duplicate `[Unreleased]` sections into proper versioned entries; fixed orphaned `## [Unreleased]` mid-file (was 0.2.7-era content); made entries more concise for human readers
- **Latent bug fixed:** `DispatchAction` — Claude CLI surfaces API errors (e.g. 500) as assistant text with `"API Error:"` prefix; dispatch was returning `success=True`, allowing review/checkpoint to run against a non-existent output file. Added `_check_cli_error()` detection in both session and agent paths.

## 20260408

### Slice 161: Summary Step with Emit Destinations — Complete

**Commits (8 slice commits):**
- `877f1e6` chore: add pyperclip dependency for summary clipboard emit
- `2bbbcb7` feat: add SDKExecutionSession.capture_summary() method
- `1a953ae` feat: add summary= overload to SDKExecutionSession.compact()
- `6f78e1e` feat: add emit destination registry and types
- `76b0e65` feat: add SummaryAction with config validation
- `9b043a7` feat: implement _execute_summary shared helper
- `c613422` feat: wire SummaryAction.execute to shared helper
- `7293394` feat: add SummaryStepType, register summary action+step, validate emit, update test-pipeline

**Delivered:**
- `SDKExecutionSession.capture_summary()` — captures summary without rotating session
- `SDKExecutionSession.compact(summary=...)` — `summary=` overload skips capture phase for reuse
- `emit.py` — `EmitKind` registry with stdout, file, clipboard (pyperclip), rotate destinations
- `actions/summary.py` — `SummaryAction` + `_execute_summary()` shared helper; single capture, multi-destination dispatch; rotate failures fail the action, others log warning
- `CompactAction` SDK path refactored to delegate into `_execute_summary()` with `emit=[rotate]`; `action_type` kept as `"compact"` — state persistence unaffected
- `SummaryStepType` with `emit` validation and `checkpoint:` shorthand (expands to summary + checkpoint action pair)
- `test-pipeline.yaml` updated to use `summary:emit:[rotate]` in place of `compact:`
- 1429 tests passing; pyright clean; ruff clean

**Pending / deferred:**
- T15 manual smoke test (`sq run test-pipeline 154 -vv`) deferred — requires live Claude SDK session; no blockers
- `clear` follow-up (rotate without seeding) not yet filed as a slice; design open question from 161 slice doc

---

## 20260407

**Slices 158, 159: Pipeline plan additions**
Added two new feature slices to `140-slices.pipeline-foundation.md`. Slice 158 (Pipeline Fan-Out / Fan-In Step Type) — general parallel branch infrastructure with pluggable fan-in reducer; ships with identity reducer, consensus reducer is a stub for 160; demonstrates with N>1 reviews against multiple models; foundational for consensus review infrastructure. Slice 159 (Interactive Checkpoint Resolution) — replace pause-and-exit with interactive prompt offering accept/override/exit options; first two avoid the full resume cycle. Both slices need design (Phase 4) before implementation.

**Slice 157: SDK Session Management and Compaction — Design Updated (Phase 4 revision)**
Revised `157-slice.sdk-session-management-and-compaction.md` to address two review concerns: (1) checkpoint resume after compact loses the summary because the previous process's session is gone — fixed by persisting compact summaries in a new keyed `compact_summaries` dict on `RunState` (schema bump v2 → v3); (2) executor-owned re-injection on resume via a new `seed_context()` session method. Keying scheme `{step_index}:{step_name}` is forward-compatible with slice 158 fan-out branches (will extend with `#branch{n}` suffix). Added `CompactSummary` dataclass, `record_compact_summary` state manager method, and `active_compact_summary_for_resume` helper. Re-reviewed task breakdown follows in same session.

**Slice 157: SDK Session Management and Compaction — Task Breakdown Updated (Phase 5 revision)**
Expanded `157-tasks.sdk-session-management-and-compaction.md` from 11 tasks to 18 to cover the design revision: T2/T3 add `CompactSummary` dataclass, schema v3 bump, state manager persistence and lookup helpers; T7 adds `seed_context()` method; T11 wires the compact summary persistence via the executor's `on_step_complete` callback (action stays free of state-manager coupling); T12 implements executor resume injection; T14 adds an automated integration test for the full session rotate flow; T15 adds an automated test specifically for resume-after-compact. T13 (PreCompact hook) retains its investigation-first note. Test-with pattern throughout; 452 lines.

## 20260406

**Slice 157: SDK Session Management and Compaction — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/157-tasks.sdk-session-management-and-compaction.md`. 11 tasks (T1–T11): capture `session_id` from `ResultMessage` in translation (T1); add `session_id` and `options` fields to `SDKExecutionSession` (T2); pass options into session from `_run_pipeline_sdk` (T3); implement `compact()` session rotate method (T4); remove `configure_compaction()` stub (T5); add `model` field to compact step YAML (T6); wire compact action to call `session.compact()` (T7); register `PreCompact` hook for interactive instruction injection (T8); end-to-end smoke test via test-pipeline (T9); lint/type-check/full suite (T10); closeout (T11). Test-with pattern throughout; commits after each implementation+test pair. Note: T8 includes verification-before-implement note for the `PreCompact` hook return format as that API detail needs confirmation.

**Slice 157: SDK Session Management and Compaction — Design Complete (Phase 4)**
Created `project-documents/user/slices/157-slice.sdk-session-management-and-compaction.md`. Core approach: session rotate compaction at pipeline step boundaries. When compact step executes, switch model to cheap summarizer (e.g. haiku) in the *current* session, query with compact template instructions, capture summary, disconnect, start fresh session seeded with summary. Key insight: summarize in the live session (model has full context) rather than resuming in a new process (loads entire context just to read it). Also wires `PreCompact` hook for interactive `/compact` instruction injection. Adds optional `model` field to compact YAML. Removes unconnected `configure_compaction()` stub from slice 155. Agent SDK investigation confirmed: no `context_management`, no `compaction_control`, no threshold control — session rotate is the only deterministic compaction path. Dependencies: [155, 156]. Effort: 3/5.

## 20260405

**Fix: validate pipeline before execution, not just `--validate`**
`_run_pipeline` now calls `validate_pipeline()` before `execute_pipeline()`, so invalid action parameters (e.g. `checkpoint: concerns` instead of `on-concerns`) are caught with a clear error before execution begins. Previously validation only ran for `--validate` and `--dry-run`. Also added defense-in-depth in `CheckpointAction.execute()` — invalid trigger values now return `ActionResult(success=False)` instead of an unhandled `ValueError`. 1253 tests pass.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md`. Slice extends slice 153's prompt-only mode to transparently support `each`/collection loops. Core design: `EachLoopState` dataclass tracks iteration context (current item index, inner step name, cached source query results) persisted in `RunState`; `render_each_step_instructions()` resolves CF source queries on first entry; placeholder resolution enhanced to support `{param.field}` dot-path syntax for item binding; `StateManager` methods `first_unfinished_step()` and `advance_iteration()` handle navigation within/across iterations. To the caller, loops are transparent — each `--next` returns the next instruction in flattened execution order, whether it's a new step or next iteration. Model switching is informational only (slash command handles manually). Technical decisions documented: transparent iteration, params-based item binding, single-depth loops (nesting deferred to 160), convergence strategies stubbed (160 scope). Data flows, state persistence format, and integration points detailed. Ready for Phase 5 (task breakdown) and Phase 6 (implementation). Effort: 2/5, risk: low.

**Slice 156: Pipeline Executor Hardening — Implementation Complete (Phase 6)**
Implemented all 14 tasks. `ExecutionMode` StrEnum added to `state.py`; `RunState` schema bumped to v2 with `execution_mode` field (default `SDK` for forward-compat with v1 files); `init_run` gains `execution_mode` param and `pipeline_name.lower()` normalisation. `_run_pipeline` gains `run_id` param (skips `init_run` when provided); `_run_pipeline_sdk` gains `run_id` param and forwards with `execution_mode=SDK`. Both `--resume` and implicit resume paths rewritten to dispatch via `match state.execution_mode:` — no string literals. `_handle_prompt_only_init` records `PROMPT_ONLY`. `load_pipeline` and `discover_pipelines` normalise names to lowercase; CLI `run()` normalises at `--validate`, `--dry-run`, `--prompt-only`, and standard execution entry points. `--status` output includes `Mode:` line. 1251 tests pass; pyright zero errors; ruff clean. Branch: `156-slice.pipeline-executor-hardening`.

## 20260404

**Slice 156: Pipeline Executor Hardening — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/156-tasks.pipeline-executor-hardening.md`. 14 tasks (T1–T14): `ExecutionMode` StrEnum in state.py (T1); schema v2 with `execution_mode` field on `RunState` (T2); `init_run` gains `execution_mode` param and lowercase normalisation (T3); `_run_pipeline` gains `run_id` and `execution_mode` params (T4); `_run_pipeline_sdk` gains `run_id` param (T5); fix `--resume` dispatch via `match state.execution_mode` (T6); fix implicit resume dispatch (T7); `_handle_prompt_only_init` records `PROMPT_ONLY` (T8); lowercase normalisation in `load_pipeline` (T9) and `discover_pipelines` (T10); CLI input normalisation (T11); display `execution_mode` in `--status` (T12); lint/type-check/full suite (T13); closeout (T14). Test-with pattern throughout; 6 commit checkpoints.

**Slice 156: Pipeline Executor Hardening — Design Complete (Phase 4)**
Diagnosed resume failure: both `--resume` and implicit resume paths bypass `_run_pipeline_sdk`, so `sdk_session` is `None` on resume; compact action falls through to `cf compact --instructions ...` which does not exist. Fix scope: (1) `ExecutionMode` StrEnum added to `state.py`; (2) `RunState.execution_mode` field (schema v2); (3) both resume paths dispatch by enum match to the correct runner; (4) `_run_pipeline_sdk` accepts `run_id` for resume-in-place; (5) pipeline name normalised to lowercase at load and CLI input boundary. Design created at `project-documents/user/slices/156-slice.pipeline-executor-hardening.md`.

**Slice 154: Prompt-Only Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/154-slice.prompt-only-loops.md` and `project-documents/user/tasks/154-tasks.prompt-only-loops.md`. Slice extends prompt-only mode to transparently support `each`/collection loops — executor expands loops internally, returns successive iteration instructions via `--next` calls. To the caller, a loop appears as a sequence of steps. Enables design-batch pipelines (multi-slice batch operations) in interactive prompt-only mode. Architecture: loop state tracking (iteration count, bound item) in StateManager; placeholder resolution (`{slice.index}` → actual value from item); query source executor for CF `cf.unfinished_slices(plan)` integration; loop expansion in executor's `next_step()` / advancement in `step_done()`. Convergence loop syntax acknowledged in YAML but stubbed (strategies are 155/160 scope). 20 implementation tasks; test-with pattern throughout. No design blockers; ready for implementation.

**Slice 155: SDK Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 20 tasks (T1–T20). Created `src/squadron/pipeline/sdk_session.py`: `SDKExecutionSession` dataclass wrapping `ClaudeSDKClient` with `set_model()` (skips if unchanged), `dispatch()` (rate-limit retry, error translation), `configure_compaction()` (stores config), `connect()`/`disconnect()` lifecycle. Extended `ActionContext` with `sdk_session: SDKExecutionSession | None = None`. Dispatch action gains `_dispatch_via_session()` path; routing checks `context.sdk_session`. Compact action gains SDK path that calls `session.configure_compaction()` instead of CF. Environment detection via `_resolve_execution_mode()` raises `typer.Exit(1)` for `CLAUDECODE` env var. CLI wiring: `_run_pipeline_sdk()` async helper creates session, connects, calls `_run_pipeline()`, disconnects in `finally`. Executor propagates `sdk_session` through all `_execute_step_once()`/loop/each call chains. 38 new tests across 5 test files. Full suite: 1228 tests pass, zero regressions. Slice 155 marked complete.

**Slice 155: SDK Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/155-tasks.sdk-pipeline-executor.md`. 20 tasks (T1–T20): SDKExecutionSession module with persistent client lifecycle and set_model()/dispatch()/configure_compaction() methods (T1-T3), ActionContext extension with sdk_session field (T4), dispatch action session path with model switching (T5-T7), compact action SDK compaction path via context_management API (T8-T10), environment detection for CLAUDECODE rejection (T11-T13), CLI wiring and executor propagation (T14-T17), integration test with full pipeline cycle (T18-T19), lint/verify/closeout (T20). Test-with pattern throughout; 7 commit checkpoints.

**Slice 155: SDK Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/155-slice.sdk-pipeline-executor.md`. Full pipeline automation via `ClaudeSDKClient` with persistent session, per-step model switching via `set_model()`, and server-side compaction via `context_management` API (`compact_20260112` beta). Slice review (glm-5) raised FAIL on persistent session violating 140's "stateless steps" principle. Resolved by updating `140-arch.pipeline-foundation.md` to distinguish SDK session persistence (runtime optimization, 140 scope) from conversation persistence (semantic dependency, 160 scope). Architecture updated: "Interaction with Conversations" section clarified, dependency notes updated.

**Slice 153: Verification and Pipeline Testing**
Ran prompt-only pipeline end-to-end in IDE extension, Claude Code CLI, and straight CLI. Findings: (1) reviews blocked inside Claude Code sessions ("no nested Claude Code") regardless of model — review dispatch goes through SDK subprocess; (2) `/model` and `/compact` slash commands cannot be automated — only user can issue slash commands; (3) checkpoint `always` trigger required stronger prompt language to enforce. Fixed: review command now uses model alias (not resolved ID) to preserve profile resolution; removed invalid `--template` flag; strengthened checkpoint/compact instructions in `/sq:run`. Added `test-pipeline.yaml` for low-cost pipeline testing. Added slice 155 to slice plan, updated slice 154 scope (loops only, model switching informational).

**Slice 153: Prompt-Only Pipeline Executor — Implementation Complete (Phase 6)**
Implemented all 17 tasks (T1–T17). Created `src/squadron/pipeline/prompt_renderer.py`: `StepInstructions`, `ActionInstruction`, `CompletionResult` dataclasses, per-action-type builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point. Added `StateManager.record_step_done()` public method. CLI: `--prompt-only`, `--next`, `--step-done`, `--verdict` flags on `sq run`. `/sq:run` slash command rewritten to consume prompt-only output. 30 unit tests, 4 integration tests, 12 CLI tests. Full verification walkthrough passed: all 6 slice pipeline steps cycle correctly, model aliases resolve, compact params resolve `{slice}` → target. 1193 total tests pass, zero regressions. Slice 153 complete.

## 20260403

**Slice 153: Prompt-Only Pipeline Executor — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/153-tasks.prompt-only-pipeline-executor.md`. 17 tasks (T1–T17): data models (`StepInstructions`, `ActionInstruction`, `CompletionResult`), per-action-type instruction builders (cf-op, dispatch, review, checkpoint, commit, compact, devlog), `render_step_instructions()` entry point, `StateManager.record_step_done()` public method, CLI flags (`--prompt-only`, `--next`, `--step-done`), integration test (full prompt-only cycle), `/sq:run` slash command rewrite to consume executor output, lint/verify, closeout. Test-with pattern throughout; 7 commit checkpoints. No blockers.

**Slice 153: Prompt-Only Pipeline Executor — Design Complete (Phase 4)**
Created `project-documents/user/slices/153-slice.prompt-only-pipeline-executor.md`. Adds `--prompt-only --next` mode to `sq run` that outputs one step's structured instructions (JSON) at a time without dispatching to LLMs. Each call advances state via existing `StateManager`. `--step-done <run-id> [--verdict V]` feeds back completion/verdict for checkpoint evaluation. New `prompt_renderer.py` module: pure function that expands step types via existing `expand()`, resolves models via `ModelResolver`, renders compact templates with pipeline params — produces `StepInstructions` dataclass. `/sq:run` slash command rewritten to consume executor output instead of hardcoding workflow. Added slice overview to `140-slices.pipeline-foundation.md` (item 13). Added future work item for external model dispatch to non-Claude-Code LLMs. Dependencies: [151].

**Slice 151: CLI Integration and End-to-End Validation — Implementation Complete (Phase 6)**
Implemented all tasks T1–T21. Created `src/squadron/cli/commands/run.py` (~300 lines): `run()` Typer command with positional `pipeline`/`target` args, `--model`, `--param key=value`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. `_resolve_target()` maps positional target to pipeline's first required param at runtime. `_assemble_params()` combines target, `--param`, and model. `_check_cf()` pre-flight verifies CF availability. `_run_pipeline()` async helper: load → validate → init_run → execute → finalize. `--resume` loads state, finds next step, re-executes. Implicit resume detection via `find_matching_run()` + `typer.confirm()`. Keyboard interrupt handling saves state and prints resume instructions. Rich output: Table for `--list`, Panel for `--status`, colored summary for execution results. Registered in `app.py`. 38 unit tests (`tests/cli/commands/test_run.py`), 5 integration tests (`tests/pipeline/test_cli_integration.py`). pyright 0 errors; ruff clean. Slice 151 marked complete — completes Pipeline Foundation initiative (140).

**Slice 151: CLI Integration and End-to-End Validation — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/151-tasks.cli-integration-and-end-to-end-validation.md`. 21 tasks (T1–T21): command skeleton + registration, Typer argument signatures, mutual exclusivity validation, `--list`, `--validate`, `--status` (with `"latest"` sentinel), `--dry-run`, parameter assembly helper, CF pre-flight check, core execution flow (`_run_pipeline` async helper + `asyncio.run` bridge), `--resume` flow, implicit resume detection (`find_matching_run` + `typer.confirm`), `--from` mid-process adoption, keyboard interrupt handling, 4 integration tests (full run, resume, from-step, dry-run no state file), exports/lint/pyright, verification and closeout. Test-with pattern throughout; 5 commit checkpoints. No blockers.

**Slice 151: CLI Integration and End-to-End Validation — Design Complete (Phase 4)**
Created `project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md`. Typer `sq run` command surface wiring executor, state manager, and pipeline loader into the CLI presentation layer. Options: `--slice`, `--model`, `--from`, `--resume`, `--dry-run`, `--validate`, `--list`, `--status`. Implicit resume detection when paused run matches pipeline+params. Rich terminal output for all display modes. Integration tests with mock action registries. Async executor bridged via `asyncio.run()`. Pre-flight CF check to avoid orphan state files. Dependencies: [148, 149, 150]. Completes the Pipeline Foundation initiative (140).

**Slice 150: Pipeline State and Resume — Implementation Complete (Phase 6)**
Implemented all tasks T1–T26. Created `src/squadron/pipeline/state.py` (~280 lines): Pydantic models (`RunState`, `StepState`, `CheckpointState`), `SchemaVersionError`, and `StateManager` with full public interface (10 methods). Atomic write via `.tmp` sibling + rename; `init_run` generates `run-{YYYYMMDD}-{slug}-{hash8}` IDs and auto-prunes; `make_step_callback` returns executor-ready closure; `_append_step` extracts verdict (last non-None) and outputs (last action); paused steps set `status="paused"` + `checkpoint` field; `finalize` writes terminal status; `load` validates schema version; `load_prior_outputs` reconstructs `dict[str, ActionResult]` defensively; `first_unfinished_step` scans definition in order; `list_runs` globs+filters+sorts; `find_matching_run` exact params match; `prune` skips paused runs. 43 unit tests + 2 integration tests (full run + resume) all pass. pyright 0 errors; ruff clean. Slice 150 marked complete.

**Slice 150: Pipeline State and Resume — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/150-tasks.pipeline-state-and-resume.md`. 26 tasks (T1–T26): test infrastructure (conftest fixtures), Pydantic models (`RunState`/`StepState`/`CheckpointState`/`SchemaVersionError`), `StateManager.__init__` + atomic write helper, `init_run`, `make_step_callback` + `_append_step`, `finalize`, `load` + `SchemaVersionError` check, `load_prior_outputs`, `first_unfinished_step`, `list_runs`, `find_matching_run`, `prune`, integration tests (full run + resume), exports/lint, closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 150: Pipeline State and Resume — Design Complete (Phase 4)**
Created `project-documents/user/slices/150-slice.pipeline-state-and-resume.md`. `StateManager` persists `RunState` JSON to `~/.config/squadron/runs/` after every completed step via `on_step_complete` callback. Pydantic models: `RunState`, `StepState`, `CheckpointState`. Atomic write pattern for corruption safety. `load_prior_outputs` reconstructs `dict[str, ActionResult]` from stored `action_results`. `find_matching_run` enables implicit resume detection. `prune(keep=10)` per-pipeline auto-prune on `init_run`. `SchemaVersionError` for forward-compatibility. Provides `StateManager` interface to slice 151 (CLI). Dependencies: [149]. Status: not_started.

**Slice 149: Pipeline Executor and Loops — Implementation Complete (Phase 6)**
Implemented all tasks T1–T10. Created `src/squadron/pipeline/executor.py` (~570 lines): `ExecutionStatus`/`StepResult`/`PipelineResult` result types; `resolve_placeholders` with dotted-path traversal; `LoopCondition`/`evaluate_condition` with closed 3-value enum; `ExhaustBehavior`/`LoopConfig`; `_cf_unfinished_slices` source fn + `_SOURCE_REGISTRY`; `_parse_source` with regex validation; `execute_pipeline` async core with sequential steps, `start_from` skip, checkpoint and failure propagation, `each` branch via `_execute_each_step`, and loop wrapping via `_execute_loop_step`. Replaced `steps/collection.py` stub with `EachStepType` (structural validation, empty `expand()`). Added `collection` import to `validate_pipeline` in `loader.py`. 52 unit tests in `test_executor.py`, 6 integration tests in `test_executor_integration.py`. 296 total pipeline tests pass; pyright 0 errors; ruff clean. Slice 149 marked complete.

**Slice 149: Pipeline Executor and Loops — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/149-tasks.pipeline-executor-and-loops.md`. 10 tasks (T1–T10): test infrastructure, result types (`ExecutionStatus`, `StepResult`, `PipelineResult`), placeholder resolution, loop condition grammar (`LoopCondition` enum + `evaluate_condition`), core sequential executor with checkpoint/failure handling, retry loop execution (`LoopConfig`, `ExhaustBehavior`), `EachStepType` implementation, source registry + `each` execution branch, integration tests, verification and closeout. Test-with pattern throughout; 3 commit checkpoints. No blockers.

**Slice 149: Pipeline Executor and Loops — Design Complete (Phase 4)**
Created `project-documents/user/slices/149-slice.pipeline-executor-and-loops.md`. Async executor engine takes validated `PipelineDefinition`, expands step types into action sequences, resolves `{param}` placeholders, and executes actions sequentially. Retry loops (`loop: {max, until, on_exhaust}`) with closed condition grammar (`review.pass`, `review.concerns_or_better`, `action.success`). `each` collection loop step type with source query dispatch (`cf.unfinished_slices`) and dot-path item binding (`{slice.index}`). Convergence loop strategy field acknowledged but stubbed (160 scope). Checkpoint pausing and action failure propagation. `on_step_complete` callback for state manager/CLI integration. Dependencies: [147, 148]. Unblocks slices 150 (State/Resume) and 151 (CLI).

## 20260402

**Slice 148: Pipeline Definitions and Loader — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created `schema.py` with `PipelineSchema` and `StepSchema` Pydantic v2 models — `@model_validator(mode="before")` unpacks YAML step grammar, scalar shorthand expansion (`devlog: auto` → `{"mode": "auto"}`), `to_definition()` converts to existing dataclasses. Created `loader.py` with `load_pipeline()` (path or name with project→user→built-in search), `discover_pipelines()` (scan+merge with source attribution), and `validate_pipeline()` (step type registry, model alias resolution, review template existence, param placeholder declaration checks). Four built-in pipeline YAMLs: slice-lifecycle (5 steps), review-only (1), implementation-only (2), design-batch (1 `each`). 43 new tests (12 schema + 11 loader + 9 validation + 11 integration), 995 total pass, pyright 0 errors, ruff clean. Slice 148 marked complete.

**Slice 148: Pipeline Definitions and Loader — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/148-tasks.pipeline-definitions-and-loader.md`. 13 tasks (T1–T13): Pydantic schema models + tests, four built-in pipeline YAML files, pipeline loader with 3-source discovery + tests, `discover_pipelines` + tests, semantic validation (`validate_pipeline`) + tests, integration tests for all built-ins, two commit checkpoints, closeout. Test-with pattern throughout. No blockers.

**Slice 148: Pipeline Definitions and Loader — Design Complete (Phase 4)**
Created `project-documents/user/slices/148-slice.pipeline-definitions-and-loader.md`. YAML pipeline grammar with Pydantic v2 schema validation (`schema.py`), loader with 3-source discovery (built-in → user → project), four built-in pipelines (slice-lifecycle, review-only, implementation-only, design-batch), and semantic validation (step types, model aliases, review templates, param references). Pydantic validates at boundary, converts to existing `PipelineDefinition`/`StepConfig` dataclasses. Dependencies: [147]. Unblocks slice 149 (Executor) and 151 (CLI).

**Slice 147: Compact Action and Step Types — Implementation Complete (Phase 6)**
Implemented all 13 tasks (T1–T13). Created compaction instruction template (`data/compaction/default.yaml`) with loader supporting user overrides from `~/.config/squadron/compaction/`. Implemented `CompactAction` with template-based CF instructions, `keep`/`summarize` params, and optional CF summarize call. Implemented four step types: `PhaseStepType` (3 registrations, 6-action expansion with optional review/checkpoint), `CompactStepType` (single compact action passthrough), `ReviewStepType` (review + optional checkpoint), `DevlogStepType` (single devlog with auto/explicit mode). 76 new tests (17 compact action + 17 phase + 7 compact step + 8 review step + 9 devlog step + 17 registry integration + 1 init), 952 total pass, pyright 0 errors, ruff clean. Slice 147 marked complete.

**Slice 147: Compact Action and Step Types — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/147-tasks.compact-action-and-step-types.md`. 13 tasks (T1–T13): compaction instruction template + loader, CompactAction implementation + tests, PhaseStepType (3-phase registration) + tests, CompactStepType + tests, ReviewStepType + tests, DevlogStepType + tests, registry integration tests, verification and closeout. Test-with pattern throughout. No blockers.

**Slice 147: Compact Action and Step Types — Design Complete (Phase 4)**
Created `project-documents/user/slices/147-slice.compact-action-and-step-types.md`. Compact action issues parameterized compaction instructions to CF with configurable `keep`/`summarize` params. Four step types: phase (cf-op→dispatch→review→checkpoint→commit), compact (single compact action), review (review + optional checkpoint), devlog (single devlog action). Step types are pure data transformers — `expand()` returns `(action_type, action_config)` tuples for the executor. Dependencies: [144, 145, 146]. Unblocks slice 148 (Pipeline Definitions) and 149 (Executor).

**Slice 146: Review and Checkpoint Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). Extracted review persistence to shared `review/persistence.py` (`format_review_markdown`, `save_review_file`, `yaml_escape`, `SliceInfo`). Implemented `CheckpointAction` with `CheckpointTrigger` enum and trigger×verdict evaluation matrix. Implemented `ReviewAction` delegating to `run_review_with_profile()` with model/profile resolution, template input passthrough, review file persistence (non-fatal), and verdict/findings mapping. 57 new tests (13 persistence + 21 checkpoint + 21 review + 2 registry), 884 total pass, pyright 0 errors, ruff clean. Slice 146 marked complete.

---

## 20260331

**Slice 146: Review and Checkpoint Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/146-tasks.review-and-checkpoint-actions.md`. 8 tasks (T1–T8): review persistence extraction + tests, CheckpointAction implementation + tests, ReviewAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 146: Review and Checkpoint Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/146-slice.review-and-checkpoint-actions.md`. Two actions: ReviewAction delegates to `run_review_with_profile()`, populates `ActionResult.verdict` and `ActionResult.findings` from structured findings (slice 143), persists review files. CheckpointAction evaluates trigger (always, on-concerns, on-fail, never) against prior review verdict, returns paused/skipped result for executor interpretation. Includes persistence extraction from CLI to shared `review/persistence.py`. Dependencies: [143, 145]. Unblocks slices 147, 149, 150.

**Slice 145: Dispatch Action — Implementation Complete (Phase 6)**
Implemented all 6 tasks (T1–T6). Extracted `_ensure_provider_loaded` from `review_client.py` to shared `providers/loader.py`. Implemented `DispatchAction` with 5-level model resolution, profile resolution (explicit override > alias > SDK default), one-shot agent lifecycle, SDK response deduplication, token metadata passthrough, and comprehensive error handling (never raises). 26 new tests (17 dispatch + 9 loader), 827 total pass, pyright 0 errors, ruff clean. Slice 145 marked complete.

**Slice 145: Dispatch Action — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/145-tasks.dispatch-action.md`. 6 tasks (T1–T6): provider loader extraction + tests, DispatchAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 145: Dispatch Action — Design Complete (Phase 4)**
Created `project-documents/user/slices/145-slice.dispatch-action.md`. Dispatch action resolves model alias via 5-level cascade (`ModelResolver`), creates one-shot agent through provider registry, sends prompt via `handle_message()`, captures response and token metadata. Follows review system's proven dispatch pattern. Includes provider loader extraction from `review_client.py` to shared location. Dependencies: [142, 102]. Unblocks slices 146, 147.

**Slice 144: Utility Actions — Implementation Complete (Phase 6)**
Implemented all 8 tasks (T1–T8). `CfOpAction` delegates to `cf_client._run()` with `pyright: ignore[reportPrivateUsage]` per project convention. `CommitAction` uses `subprocess.run()` with real `git init` test repos via `tmp_path`. `DevlogAction` handles DEVLOG insertion with date header deduplication and auto-generation from `prior_outputs`. All three actions satisfy `Action` protocol and auto-register at import time. 39 new tests, 800 total pass, pyright 0 errors, ruff clean. Slice 144 marked complete.

**Slice 144: Utility Actions — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/144-tasks.utility-actions.md`. 8 tasks (T1–T8): CfOpAction implementation + tests, CommitAction implementation + tests, DevlogAction implementation + tests, registry integration verification, full verification and closeout. Test-with pattern throughout. No blockers.

**Slice 144: Utility Actions — Design Complete (Phase 4)**
Created `project-documents/user/slices/144-slice.utility-actions.md`. Three action implementations: CfOpAction (set_phase, build_context, summarize via ContextForgeClient), CommitAction (git commit with semantic messages, no-op on clean tree), DevlogAction (structured DEVLOG entries auto-generated from pipeline state or explicit content). Each action auto-registers at import time. Mock I/O boundaries for testing. Unblocks slice 147 (step types).

---

## 20260330

**Slice 143: Structured Review Findings — Implementation Complete (Phase 6)**
Implemented all 10 tasks (T1–T10). Added `StructuredFinding` dataclass and `NOTE` severity to `review/models.py`. Extended parser with NOTE support, `category:` and `location:` tag extraction from finding blocks. Extended frontmatter formatter to emit `findings:` YAML array with structured entries. Extended `to_dict()` with `structured_findings` and `category`/`location` on findings. Injected structured output instructions into all review template system prompts via `review_client.py`. 761 tests pass (0 pre-existing failures), pyright 0 errors, ruff clean. Slice 143 marked complete.

**Slice 143: Structured Review Findings — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/143-tasks.structured-review-findings.md`. 10 tasks (T1–T10): models (StructuredFinding + NOTE severity), parser extensions (category/location extraction), frontmatter formatter, JSON serialization, prompt enhancement, full verification. Test-with pattern throughout. No blockers.

**Slice 143: Structured Review Findings — Design Complete (Phase 4)**
Created `project-documents/user/slices/143-slice.structured-review-findings.md`. Extends review output with machine-readable structured findings in YAML frontmatter. Adds `StructuredFinding` dataclass (id, severity, category, summary, location), `NOTE` severity level, parser extensions for category extraction, and prompt enhancement for all review templates. Single-file format: frontmatter is the programmatic index, prose body unchanged. Absorbs former slice 123 scope. Designed for slice 160 cross-iteration identity matching via (category, location) fingerprint.

**Slice 142: Pipeline Core Models and Action Protocol — Implementation Complete (Phase 6)**
Implemented full `src/squadron/pipeline/` package: 5 dataclasses in `models.py`, `Action` protocol + `ActionType` StrEnum + action registry, `StepType` protocol + `StepTypeName` StrEnum + step-type registry, `ModelResolver` (5-level cascade, pool: stub), stub modules for 7 actions and 5 step types, public `__init__` surface. 26 new tests across 3 test files — all pass. Pyright: 0 errors. Full repo: 707 passed, 8 pre-existing failures (unrelated). Slice 142 marked complete.

**Slice 142: Pipeline Core Models and Action Protocol — Task Breakdown Complete (Phase 5)**
Created `project-documents/user/tasks/142-tasks.pipeline-core-models-and-action-protocol.md`. 14 tasks (T1–T14): package skeleton + stubs, data models, Action protocol + registry, StepType protocol + registry, ModelResolver (5-level cascade, pool: stub), pipeline `__init__` public surface, full test/pyright pass, verification walkthrough and closeout. Tests interleaved after each implementation group. No blockers.

**Slice 142: Pipeline Core Models and Action Protocol — Design Complete (Phase 4)**
Created `project-documents/user/slices/142-slice.pipeline-core-models-and-action-protocol.md`. Defines `ActionContext`, `ActionResult`, `PipelineDefinition`, `StepConfig`, `ValidationError` dataclasses; `Action` and `StepType` protocols; action/step-type registries; `ModelResolver` with 5-level cascade chain and `pool:` prefix error stub. Full `src/squadron/pipeline/` package layout with stub modules for all future action and step type files. No blockers — all design decisions resolved by architecture.

---

## 20260329

**Slice 141: Configuration Externalization — Implementation Complete (Phase 6)**
Created `src/squadron/data/` package with `data_dir()` two-path fallback. Transcribed 18 built-in model aliases to `data/models.toml`. Moved review templates to `data/templates/`. Refactored `aliases.py` (extracted `_load_aliases_from_file`, removed `BUILT_IN_ALIASES`). Updated `review/templates/__init__.py` to use `data_dir()`. Updated `pyproject.toml` force-include. Deleted `review/templates/builtin/`. Updated all tests referencing old paths. 681 tests pass (8 pre-existing failures unrelated to this slice). Slice 141 marked complete.

---

## 20260328

### Slice 141: Configuration Externalization — Task Breakdown Complete (Phase 5)
- Task file created: `project-documents/user/tasks/141-tasks.configuration-externalization.md`
- 11 tasks (T1–T11): create data/ package, copy templates, transcribe models.toml, refactor aliases.py, update template loader, update pyproject.toml, delete builtin/, verify, commit
- Test tasks interleaved after each implementation task (T5 after T4, T7 after T6)
- No blockers — straightforward reorganization, all design decisions resolved

### Slice 141: Configuration Externalization — Design Complete (Phase 4)
- Slice design created: `project-documents/user/slices/141-slice.configuration-externalization.md`
- Scope: move `BUILT_IN_ALIASES` Python dict → `src/squadron/data/models.toml`; move `review/templates/builtin/*.yaml` → `src/squadron/data/templates/`; add `DataLoader.data_dir()` utility; reserve `data/pipelines/` for slice 148
- Key decision: `data_dir()` uses same two-path fallback pattern as `install.py`'s `_get_commands_source()`
- Public APIs unchanged; merge precedence (built-ins → user overrides) preserved
- Slice plan entry already had (141) index materialized — no update needed

### Slice 140: Command Surface Parity — Task Breakdown (Phase 5) [revised]
- 11 tasks: create review.md (4 subcommands), create auth.md, delete 4 old files, handle run-slice, fix installer stale removal, smoke-test, close
- install.py gets stale-file cleanup (source-authoritative deletion, same pattern as CF daec117)
- Revised after design correction: consolidated dispatch pattern replaces per-subcommand files

### Slice 140: Command Surface Parity — Slice Design (Phase 4)
- Designed slash command parity: add `/sq:review arch`, deprecate `/sq:run-slice`
- Naming convention formalized: `commands/sq/{parent}-{child}.md` maps to `sq {parent} {child}`
- Existing names already follow convention — primary work is adding `review-arch.md` and deprecation banner
- Effort: 1/5 — markdown files and settings only, no Python changes

## 20260327

### Slice 128: Review Transport Unification — Implementation Complete (Phase 6)
- Reviews unified through `Agent.handle_message()` via provider registry — one code path for all profiles
- `runner.py` deleted (net -700 lines), `AsyncOpenAI` removed from review module
- `ProviderCapabilities` on all providers; file injection conditional on `can_read_files`
- `ProviderType`, `ProfileName`, `AuthType` enums — all identifiers defined once
- `OAuthFileStrategy` + `CodexProvider`/`CodexAgent` via MCP transport
- Profile renamed `codex` → `openai-oauth`; auth type `codex` → `oauth`
- `SDKAgent` → `ClaudeSDKAgent`; auth dispatch via `from_config` factory
- 687 tests pass; ruff/pyright clean

## 20260326

### Slice 124: Codex Agent Integration — Rewound
- Implementation completed but discovered fundamental architecture gap: review system bypasses Agent/AgentProvider Protocols entirely, tightly coupled to AsyncOpenAI and ClaudeSDKClient
- Codex subscription auth (OAuth token from `~/.codex/auth.json`) can't call Chat Completions API directly — must route through Codex runtime. But review system can't use non-OpenAI transports
- String-based dispatch (`if profile == "sdk"`, `if auth_type == "codex"`) throughout codebase
- Branch rewound to main. Slice superseded by 128

### Slice 128: Review Transport Unification — Slice Design Complete (Phase 4)
- Reviews use `Agent.handle_message()` via provider registry instead of bespoke transport implementations
- `ProviderCapabilities` dataclass: `can_read_files`, `supports_system_prompt`, `supports_streaming`
- Auth strategy dispatch via registry (eliminate if/elif chains), `"codex"` auth type → `"oauth"`
- `SDKAgent` → `ClaudeSDKAgent`, `runner.py` deleted (absorbed into agent)
- Enables Codex subscription reviews and future Anthropic API without review system changes

### Slice 128: Review Transport Unification — Task Breakdown Complete (Phase 5)
- 19 tasks: capabilities, auth refactor, OAuth strategy, SDK rename, Codex provider, runner.py migration, review_client unification, CLI auth cleanup, model aliases, validation, docs
- Test-with pattern throughout; 9 commit checkpoints
- Key sequence: capabilities first → auth cleanup → providers → review client unification → CLI cleanup

## 20260325

### Initiative Plan & 900-Band Maintenance Initiative
- Created `001-initiative-plan.squadron.md` retroactively documenting all initiatives (100, 140, 160, 200, 900)
- Created `900-arch.maintenance-and-refactoring.md` and `900-slices.maintenance-and-refactoring.md` as cross-cutting maintenance home

### Slice 124: Codex Agent Integration — Task Breakdown Complete (Phase 5)
- 12 tasks: transport evaluation, CodexAuthStrategy + tests, CodexAgent + tests, CodexProvider + tests, registration/profile + tests, model aliases, validation, documentation
- Test-with pattern throughout; 7 commit checkpoints
- Key design: Codex models already work for reviews via `openai` profile (Chat Completions API) — no review system changes; agentic provider is for spawn/task workflows only

### Slice 124: Codex Agent Integration — Slice Design Complete (Phase 4)
- Codex integration via MCP server path (`codex mcp-server`), not TypeScript SDK
- `CodexProvider`/`CodexAgent` implementing existing Protocols via MCP stdio client
- `CodexAuthStrategy` checks `~/.codex/auth.json` or `OPENAI_API_KEY`
- Review system gets third path: `_run_codex_review()` alongside SDK and non-SDK paths
- Lazy subprocess start, read-only sandbox for reviews

### Slice 127: Scoped Code Review & Prompt Logging — Implementation Complete (Phase 6)

- `git_utils.py`: `_find_slice_branch()`, `_find_merge_commit()`, `resolve_slice_diff_range()` — three-tier resolution (branch → merge commit → fallback to main)
- Prompt log: `_write_prompt_log()` writes `review-prompt-{ts}.md` at `-vvv`; prompt fields on `ReviewResult` populated at `-vv`
- `review_code()` uses `resolve_slice_diff_range()` instead of `diff = "main"` when slice number provided; `--diff` flag overrides
- Debug appendix `## Debug: Prompt & Response` appended to saved review markdown when prompt fields present
- 637 tests pass; 6 semantic commits on branch `127-slice.scoped-code-review-prompt-logging`

### Slice 127: Scoped Code Review & Prompt Logging — Task Breakdown Complete (Phase 5)

- 16 tasks: git_utils.py (branch/merge resolution + tests), ReviewResult prompt fields + tests, prompt log writer + tests, scoped diff wiring + tests, debug appendix + tests, validation pass, documentation
- Test-with pattern throughout; 6 commit checkpoints

### Slice 127: Scoped Code Review & Prompt Logging — Slice Design Complete (Phase 4)

- Scoped diff resolution: `sq review code 122` auto-resolves to slice branch's commits via merge-base or merge-commit detection, falls back to `--diff main`
- Prompt log persistence: `-vvv` writes full prompt to `~/.config/squadron/logs/review-prompt-{ts}.md`; `-vv` embeds debug appendix in saved review file
- New `git_utils.py` module; optional fields on `ReviewResult` for prompt/response capture

### Slice 122: Review Context Enrichment — Implementation Complete (Phase 6)

- Expanded `_FINDING_RE` to 5 formats; lenient fallback + synthesized finding when verdict/findings mismatch; `fallback_used` flag on `ReviewResult`; debug log at `~/.config/squadron/logs/review-debug.jsonl`
- CRITICAL consistency block added to all three builtin templates; `rules.py` module: `resolve_rules_dir()`, language detection, glob matching, template rules injection
- `review code` auto-detects language rules from diff paths; `--rules-dir`/`--no-rules` flags on review commands; template rules prepended from `rules/review.md` + `rules/review-{template}.md`
- Review file YAML aligned: `layer`, `sourceDocument`, `aiModel` (resolved ID), `status: complete`; `-vvv` debug output shows system/user prompt + injected rules
- 609 tests pass; 4 semantic commits on branch `122-slice.review-context-enrichment`

### Slice 122: Review Context Enrichment — Task Breakdown Complete (Phase 5)

- 19 tasks across: parser hardening (lenient parsing + fallback + debug log), template prompt hardening, `rules.py` auto-detection module, review CLI wiring (`--rules-dir`, `--no-rules`), review file YAML alignment, prompt debug output (`-vvv`)
- Slice design updated: added Section 5 (YAML alignment), Section 6 (prompt debug), prompt hardening renames to Section 7
- v0.2.6 tagged and published (slice 126 complete — `ContextForgeClient`)

---

## 20260324

### Slice 126: Context Forge Integration Layer — Implementation Complete

- `ContextForgeClient` implemented in `src/squadron/integrations/context_forge.py` with typed methods: `list_slices()`, `list_tasks()`, `get_project()`, `is_available()`
- `review.py` migrated: `_run_cf()` removed, `_resolve_slice_number()` uses `ContextForgeClient`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) replace inline `typer.Exit`
- 16 unit tests for client, 3 new CLI error path tests, 7 existing resolve tests updated
- Markdown command files updated to CF's new command surface (`cf list slices`, `cf list tasks`)
- All 556 tests pass, pyright 0 errors, ruff clean

### Slice 126: Context Forge Integration Layer — Task Breakdown Complete

Task file at `project-documents/user/tasks/126-tasks.context-forge-integration-layer.md` (14 tasks: T1-T14). Three workstreams: client implementation with typed dataclasses (T1-T9), review.py migration (T10-T11), markdown command file updates and validation (T12-T14). Test-with pattern throughout.

### Slice 126: Context Forge Integration Layer — Design Complete

- Created `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- `ContextForgeClient` class in `src/squadron/integrations/context_forge.py` — typed methods replacing scattered `subprocess.run(["cf", ...])` calls
- Typed return dataclasses: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) separated from CLI layer
- Adapts to CF's new command surface (`cf list slices --json` replacing `cf slice list --json`)
- Markdown command files updated to reference new CF command names
- Scope limited to abstraction and migration — MCP transport, command aliasing deferred

### Slice 122: Review Context Enrichment — Design Complete

- Created `project-documents/user/slices/122-slice.review-context-enrichment.md`
- Two-pronged scope: (1) fix verdict/findings inconsistency (issue #5) via prompt hardening + parser post-processing guard, (2) auto-detect and inject language-specific rules for code reviews
- Language detection from diff file paths or glob matches, matched against rules files' `paths` frontmatter globs
- Rules directory resolution: `--rules-dir` flag > config `rules_dir` > `{cwd}/rules/` > `{cwd}/.claude/rules/`
- Slice/task reviews inject `rules/general.md` if present
- `--no-rules` flag to suppress all rule injection
- Legacy P0-P3 priorities extracted as optional copyable rules file, not baked into templates

## 20260323

### .env support for API keys

Added `python-dotenv` dependency. `load_dotenv()` runs at CLI startup (`cli/app.py`), so API keys (ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY, etc.) can be set in a `.env` file instead of exported in the shell. `.env` already gitignored.

### Slice 121: Model Alias Metadata — Implementation Complete

- All 12 tasks (T1-T12) complete. 537 tests pass, pyright/ruff/format clean.
- `ModelPricing` TypedDict (input, output, cache_read, cache_write — USD per 1M tokens)
- `ModelAlias` extended with `private`, `cost_tier`, `notes`, `pricing` — all optional via inheritance pattern (`_ModelAliasRequired` base + `total=False`)
- All 12 `BUILT_IN_ALIASES` populated with curated metadata and pricing
- `load_user_aliases()` extracts metadata and pricing from TOML (inline and sub-table formats)
- `estimate_cost()` utility: alias name + token counts → USD float or None
- `sq models` compact by default; `sq models -v` shows Private, Cost, In $/1M, Out $/1M, Notes columns
- 21 new tests across T4 (3), T6 (6), T8 (6), T10 (6)

## 20260322

### Slice 121: Model Alias Metadata — Task Breakdown Complete

Task file at `project-documents/user/tasks/121-tasks.model-alias-metadata.md` (12 tasks: T1-T12). Three workstreams: type extensions with built-in metadata (T1-T4), TOML parsing and cost estimation (T5-T8), display updates and validation (T9-T12). Test-with pattern: each implementation task followed immediately by its test task.

### Slice 121: Model Alias Metadata — Design Complete

- Created `project-documents/user/slices/121-slice.model-alias-metadata.md`
- Extends `ModelAlias` TypedDict with optional `private` (bool), `cost_tier` (str), `notes` (str), `pricing` (ModelPricing) fields
- `ModelPricing` TypedDict: `input`, `output`, `cache_read`, `cache_write` (USD per 1M tokens)
- `total=False` on TypedDict for backward-compatible optional fields
- `cost_tier` values: free, cheap, moderate, expensive, subscription (new — for Max sub models)
- `estimate_cost()` utility: pure function, alias name + token counts → USD or None
- `sq models` gains Private, Cost, In $/1M, Out $/1M, Notes columns with compact mode
- Curated metadata and pricing for all 12 built-in aliases
- Also in this session: slice plan refactored (100-series trimmed, 160-series created for multi-agent), reindexing (161-172, 121-125), test fixes, template clarification, architecture docs updated to squadron naming

## 20260321

### Slice 120: Model Alias Registry — Implementation Complete

- All 22 tasks (T1-T22) complete. 514 tests pass, pyright/ruff clean.
- `review arch` renamed to `review slice` with backward-compat hidden alias + deprecation notice
- `src/squadron/models/aliases.py`: `resolve_model_alias()` with built-in defaults (opus, sonnet, haiku, gpt4o, o3, o1) and user `~/.config/squadron/models.toml` override
- `_infer_profile_from_model()` removed — alias registry handles all model→profile inference
- `_inject_file_contents()` in `review_client.py`: reads file contents and appends to prompt for non-SDK reviews; handles git diff and glob patterns for code reviews; size limits (100KB/file, 500KB total)
- `sq model list` command showing built-in + user aliases in a rich table
- 5 commits on branch `120-model-alias-registry`
- Post-impl live tests remain for PM (alias resolution, content injection, diff injection)

### Slice 120: Model Alias Registry — Task Breakdown Complete

Task file at `project-documents/user/tasks/120-tasks.model-alias-registry.md` (22 tasks: T1-T22). Three workstreams: rename review arch→slice (T1-T5), model alias registry with wiring (T6-T10), content injection for non-SDK reviews including code review diff/files (T11-T16), plus model list CLI (T17-T19) and slash command updates (T20-T22). Post-impl: live tests with OpenRouter, alias customization, diff injection.

### Slice 120: Model Alias Registry — Design Complete

- Slice design at `project-documents/user/slices/120-slice.model-alias-registry.md`
- Two problems addressed: (1) hardcoded model inference replaced by data-driven alias registry in `models.toml`, (2) non-SDK reviews fail because prompts contain file paths but models can't read files — content injection adds file contents to prompt for non-SDK path
- Ships built-in aliases (opus, sonnet, gpt4o, etc.) + user `~/.config/squadron/models.toml`
- Content injection: auto-reads files from `inputs` dict, appends to prompt; handles git diff for code reviews; 100KB/file, 500KB total limits
- New `sq model list` command

### Slice 119: Review Provider & Model Selection — Implementation Complete

- All 20 implementation tasks (T1-T20) complete. 491 tests pass.
- New `review_client.py` with `run_review_with_profile()` — SDK delegation or OpenAI-compatible API path
- `--profile` flag on all `sq review` commands (arch, tasks, code)
- `_resolve_profile()`: CLI flag → model inference → template → config → sdk fallback
- `_infer_profile_from_model()`: opus→sdk, gpt-4o→openai, slash→openrouter
- `load_all_templates()` loads from built-in + `~/.config/squadron/templates/` (user override by name)
- `default_review_profile` config key added
- Slash commands updated with `--profile` documentation
- Slice 120 (Model Alias Registry) added to slice plan as next priority
- Post-impl live tests remain for PM

### Slice 119: Review Provider & Model Selection — Task Breakdown Complete

Task file created at `project-documents/user/tasks/119-tasks.review-provider-model-selection.md` (20 tasks: T1-T20). Key task groups: template profile field (T1-T2), config key + profile resolution (T3-T7), review client with provider routing (T9-T10), CLI `--profile` flag (T12-T13), user template loading (T15-T16), slash command updates (T18), validation (T19-T20). Post-impl: live tests with OpenRouter, OpenAI, user templates, config defaults.

### Slice 119: Review Provider & Model Selection — Design Complete

- Slice design created at `project-documents/user/slices/119-slice.review-provider-model-selection.md`
- Scope: decouple review execution from hardcoded Claude SDK. Add `--profile` flag, `profile` field in templates, user-customizable templates from `~/.config/squadron/templates/`, config default `default_review_profile`, model-to-profile inference
- Key decision: SDK path preserved exactly (delegation), non-SDK path uses `AsyncOpenAI` directly via existing profile/auth infrastructure
- Known limitation: non-SDK reviews have no tool access (prompt-only)
- Slice plan updated: new slice 119 inserted, old 119 (Conversation Persistence) re-indexed to 134

---

## 20260320

### Slice 118: Claude Code Commands — Composed Workflows — In Progress

- Implementation complete (T1-T9 checked off). Remaining items are PM manual tests.
- Commits:
  - `a2058c9` feat: add /sq:run-slice command, update review commands with number shorthand
  - `f31cd44` test: update install tests for 9 command files
- What works: all 448 tests pass, ruff/pyright clean, wheel bundles `run-slice.md`, install produces 9 commands
- Scope expanded from original design:
  - Updated `review-tasks.md`, `review-code.md`, `review-arch.md` with bare number shorthand (e.g., `/sq:review-tasks 191`)
  - Path resolution via `cf slice list --json` / `cf task list --json` — worktree-aware, CF owns conventions
  - `review-arch` performs holistic check: slice design vs. architecture doc + slice plan entry
  - Review file persistence to `project-documents/user/reviews/` with YAML frontmatter
  - DEVLOG entry step added to `run-slice` pipeline (Step 5)
- Pending: PM live tests (`/sq:run-slice` on real slice, `/sq:review-tasks {nnn}` shorthand), prompt iteration

---

## 20260317

### Slice 118: Claude Code Commands — Composed Workflows — Task Breakdown Complete

Task file created at `project-documents/user/tasks/118-tasks.claude-code-commands-composed-workflows.md` (6 tasks: T1-T6). T1 create `run-slice.md` command file with full pipeline prompt. T2 update install tests (8→9 expected files). T3 commit. T4 validation pass. T5 commit. T6 verify wheel bundling. Post-impl: live test on a real slice, iterate on prompt.

### Slice 118: Claude Code Commands — Composed Workflows — Design Complete

Slice design created at `project-documents/user/slices/118-slice.claude-code-commands-composed-workflows.md`.

Scope: Single `/sq:run-slice` command that automates the full slice lifecycle — phase 4 (design) → phase 5 (task breakdown + review) → compact → phase 6 (implementation + code review). Chains `cf set/build` with `sq review tasks/code` and `/compact`. Review gates: PASS proceeds, FAIL stops for human input. Smart resume (skip completed phases) documented as future enhancement. Lives in existing `sq/` namespace — no new directories or Python code.

---

## 20260307

### Slice 117: PyPI Publishing & Global Install — Task Breakdown Complete

Task file created at `project-documents/user/tasks/117-tasks.pypi.md` (13 tasks: T1-T13). T1-T2 version flag + test, T3 commit. T4-T5 metadata polish + wheel verification, T6 commit. T7-T8 GitHub Actions CI (test + publish jobs), T9 commit. T10 README install section, T11 commit. T12-T13 validation pass + commit. Post-implementation section documents manual PM steps (PyPI account, first publish, smoke test).

---

## 20260306

### Slice 117: PyPI Publishing & Global Install — Design Complete

Slice design created at `project-documents/user/slices/117-slice.pypi.md`.

Scope: Publish `squadron` to PyPI for global install via `pipx install squadron` / `uv tool install squadron`. SemVer versioning (start at 0.1.0, single-sourced in pyproject.toml). `sq --version` via `importlib.metadata`. pyproject.toml metadata polish (classifiers, license, project-urls). GitHub Actions CI workflow (lint+test on push, publish to TestPyPI+PyPI on version tag). README install instructions.

Key decisions: SemVer over CalVer, tag-driven manual releases, `pypa/gh-action-pypi-publish` with OIDC trusted publisher preferred, TestPyPI dry-run before real publish, `astral-sh/setup-uv` for CI.

### Slice 116: Claude Code Commands — Implementation Complete

All 15 tasks complete. Eight command files in `commands/sq/` (`spawn.md`, `task.md`, `list.md`, `shutdown.md`, `review-arch.md`, `review-tasks.md`, `review-code.md`, `auth-status.md`). `pyproject.toml` updated with `force-include` for wheel bundling. `install.py` with `install_commands`/`uninstall_commands` wired into Typer app. 11 tests (8 install/uninstall + 3 source verification). 446 total tests pass, pyright clean, ruff clean.

---

## 20260305

### Slice 116: Claude Code Commands — sq Wrappers — Design Complete

Slice design created at `project-documents/user/slices/116-slice.sq-slash-command.md`.

Scope: Eight Claude Code slash command files (`/sq:spawn`, `/sq:task`, `/sq:list`, `/sq:shutdown`, `/sq:review-arch`, `/sq:review-tasks`, `/sq:review-code`, `/sq:auth-status`) in `commands/sq/`. Install/uninstall CLI commands (`sq install-commands`, `sq uninstall-commands`). Command files bundled in package wheel via `pyproject.toml`. Commands are thin prompts that instruct Claude to execute the corresponding `sq` CLI command via Bash.

### Slice 116: Claude Code Commands — Task Breakdown Complete

Task file created at `project-documents/user/tasks/116-tasks.sq-slash-command.md` (15 tasks). T1 directory setup, T2-T9 command file authoring (one per command), T10 package bundling, T11-T12 install/uninstall CLI, T13-T14 tests, T15 validation.

---

### Slice 115: Project Rename — orchestration → squadron — Complete

- Renamed `src/orchestration/` → `src/squadron/`, updated pyproject.toml (name, dual entry points: `sq` + `squadron`)
- Updated all imports across 127 .py files (61 src + 66 tests)
- Config paths: `~/.config/squadron/`, `.squadron.toml`, `~/.squadron/` for daemon
- Added config migration logic in `config/manager.py` — copies old config dir on first run, writes `MIGRATED.txt`
- Renamed `OrchestrationEngine` → `SquadronEngine`
- Updated README.md, docs/COMMANDS.md, docs/TEMPLATES.md
- 435 tests pass, `sq --help` and `squadron --help` both work

---

## 20260301

### Slice 114: Auth Strategy & Credential Management — Implementation Complete

Implemented all 18 tasks for slice 114. Added `AuthStrategy` protocol and `ApiKeyStrategy` in `providers/auth.py` — direct extraction of existing credential resolution from `OpenAICompatibleProvider`, same behavior. Added `resolve_auth_strategy()` factory and `AUTH_STRATEGIES` registry. Extended `ProviderProfile` with `auth_type` field (default `"api_key"`). Refactored `OpenAICompatibleProvider.create_agent()` to delegate to the strategy. Added `orchestration auth login <profile>` and `orchestration auth status` CLI commands. 435 tests pass; pyright and ruff clean.

New files: `src/orchestration/providers/auth.py`, `src/orchestration/cli/commands/auth.py`, `tests/providers/test_auth.py`, `tests/providers/test_auth_resolution.py`, `tests/cli/test_auth.py`.

---

### Slice 114: Auth Strategy & Credential Management — Design Complete

Research into OpenAI OAuth revealed the API has no general OAuth2 flow — authentication is purely key-based (project-scoped, service account). OAuth exists only for Codex subscription access (browser-based, ChatGPT Plus/Pro/Teams). This finding reshaped slice 114 from "implement OAuth" to "formalize auth strategy abstraction with API key as concrete implementation."

Documents created:
- `project-documents/user/slices/114-slice.oauth-advanced-auth.md` — slice design
- Updated `100-slices.orchestration-v2.md` — revised slice 114 entry, new slice 116 (Codex Agent Integration)

Key decisions:
- `AuthStrategy` protocol with `get_credentials()`, `refresh_if_needed()`, `is_valid()`
- `ApiKeyStrategy` as direct extraction of existing provider credential resolution
- `auth_type` field on `ProviderProfile` for strategy dispatch
- CLI `auth login`/`auth status` commands for credential validation
- Codex agent integration (OAuth) deferred to new slice 116

Scope: `AuthStrategy` protocol, `ApiKeyStrategy`, `ProviderProfile.auth_type`, CLI auth commands, provider refactor

| Hash | Description |
|------|-------------|
| `156d78f` | docs: add slice 114 design (auth strategy) and slice 116 entry (codex) |

---

### Slice 113: Provider Variants & Registry — Post-Merge Fix

Live testing with OpenRouter/Kimi revealed `credentials` dropped at daemon boundary. `SpawnRequest` was missing the field; fixed in `server/models.py` and `routes/agents.py`. Verified working end-to-end with OpenRouter profile.

| Hash | Description |
|------|-------------|
| `146ed4b` | fix: pass credentials through SpawnRequest to AgentConfig |

---

## 20260228

### Slice 113: Provider Variants & Registry — Complete

All 15 tasks implemented across 4 groups. 408 tests passing (31 new). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `b1831c0` | feat: add provider profile model and TOML loading |
| `7eb9eff` | feat: enhance credential resolution and default headers support |
| `45ec6b8` | feat: add --profile flag to spawn and models command |

**What works:**
- `ProviderProfile` frozen dataclass with 4 built-ins: `openai`, `openrouter`, `local`, `gemini`
- TOML loading from `~/.config/orchestration/providers.toml`; user profiles override built-ins
- Credential resolution chain: `config.api_key` → profile env var → `OPENAI_API_KEY` → localhost placeholder
- OpenRouter `default_headers` via `AsyncOpenAI(default_headers=...)` constructor
- `orchestration spawn --profile openrouter --model x` fully functional
- `orchestration models --profile local` for model discovery (direct HTTP, no daemon)

**Key decisions:**
- Profiles are data (frozen dataclass), not subclasses — all three variants reuse `OpenAICompatibleProvider`
- Localhost placeholder: `"not-needed"` when no API key and `base_url` starts with `http://localhost` or `http://127.0.0.1`
- `models` command calls `/v1/models` directly via `httpx`, bypassing daemon

**Next:** Slice 114 (OAuth & Advanced Auth)

---

### Slice 113: Provider Variants & Registry — Phase 4 Design Complete

Slice design created at `project-documents/user/slices/113-slice.provider-variants.md`.

Key design decisions:
- **Profiles, not subclasses**: All three variants (OpenRouter, local, Gemini) are configurations of `OpenAICompatibleProvider`, bundled as named `ProviderProfile` entries.
- **Separate `providers.toml`**: Structured profile data lives in its own file (`~/.config/orchestration/providers.toml`), not in the flat `config.toml`.
- **`--profile` CLI flag**: New flag on spawn command, separate from `--provider`. Profile provides defaults; CLI flags override.
- **Localhost auth bypass**: Local model servers get a placeholder API key (`"not-needed"`) instead of raising `ProviderAuthError`.
- **`models` command**: Direct HTTP query to `/v1/models` for model discovery, bypasses daemon.

| Hash | Description |
|------|-------------|
| `e399e5f` | docs: add slice 113 design |

### Slice 112: Local Server & CLI Client — Phase 7 Implementation Complete

All 27 tasks (T1-T27) implemented. 35 new tests (377 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `e8350b2` | chore: add httpx dependency |
| `46c4380` | feat: add test infrastructure for server and client (T2) |
| `ae55e8b` | feat: implement OrchestrationEngine (T3) |
| `5301aa5` | test: add OrchestrationEngine tests (T4) |
| `d0591f6` | feat: add server models and health route (T5) |
| `73acbd8` | feat: add agent CRUD and messaging routes (T6) |
| `4a0dccb` | feat: add app factory and route tests (T7, T8) |
| `51b6f3d` | feat: add daemon module with PID management (T9) |
| `f6c74af` | feat: server core checkpoint (T11) |
| `48a5068` | feat: add DaemonClient (T12-T14) |
| `1733974` | feat: add serve command (T15-T16) |
| `c908121` | refactor: CLI commands use DaemonClient (T17-T20) |
| `2079bfd` | feat: add message and history commands (T21-T23) |
| `1de8866` | feat: validation pass and format fixes (T25) |
| `ca8b1f5` | test: add daemon integration test (T26-T27) |

**New modules:**
- `src/orchestration/server/engine.py` — OrchestrationEngine with agent lifecycle and conversation history
- `src/orchestration/server/models.py` — Pydantic request/response schemas
- `src/orchestration/server/routes/` — FastAPI agent CRUD, messaging, and health routes
- `src/orchestration/server/app.py` — Application factory
- `src/orchestration/server/daemon.py` — PID management, signal handling, dual-transport server
- `src/orchestration/client/http.py` — DaemonClient with Unix socket / HTTP transport
- `src/orchestration/cli/commands/serve.py` — `orchestration serve` with --status/--stop
- `src/orchestration/cli/commands/message.py` — `orchestration message`
- `src/orchestration/cli/commands/history.py` — `orchestration history` with --limit

**Refactored modules:**
- `spawn.py`, `list.py`, `task.py`, `shutdown.py` — all use DaemonClient instead of direct registry

**Next:** Slice 113 (Provider Variants & Registry).

---

### Slice 112: Local Server & CLI Client — Slice Design Complete

**Documents created:**
- `user/slices/112-slice.local-daemon.md` — slice design
- `user/slices/112-slice.local-daemon-agent-brief.md` — technical brief from PM

**Scope:** Persistent daemon process (`orchestration serve`) holding agent registry, agent instances, and conversation history in memory. CLI commands become thin clients communicating with daemon via Unix domain socket (primary) or localhost HTTP (secondary). New `OrchestrationEngine` composes existing `AgentRegistry` and adds conversation history tracking. FastAPI app serves both transports. New commands: `serve`, `message`, `history`. Existing commands (`spawn`, `list`, `task`, `shutdown`) refactored to use `DaemonClient`.

**Key design decisions:**
- `OrchestrationEngine` composes `AgentRegistry` (not subclass/replace) — registry manages lifecycle, engine adds history and coordination
- Dual transport: Unix socket (`~/.orchestration/daemon.sock`) for CLI, HTTP (`127.0.0.1:7862`) for external consumers — same FastAPI app serves both via two uvicorn instances
- `httpx.AsyncHTTPTransport(uds=path)` for CLI→daemon Unix socket communication
- Explicit `orchestration serve` — no auto-start magic, predictable daemon lifecycle
- All agent commands route through daemon — one execution path, enables future observability
- Conversation history at engine level (not just agent-internal) — provider-agnostic, supports `history` command
- Agent lifecycle categories: ephemeral (task) and session (spawn+message) — behavioral patterns, not formal types
- PID file + socket file in `~/.orchestration/` — stale file detection on startup
- `review` and `config` commands left unchanged for now (review uses SDK directly, config is stateless)

**Commit:** `dcab7a9` docs: add slice 112 design for local daemon & CLI client

**Next:** Phase 5 (Task Breakdown) on slice 112.

---

## 20260226

### Slice 111: OpenAI-Compatible Provider Core — Phase 7 Implementation Complete

All 17 tasks (T1-T17) implemented. 41 new tests (342 total project tests passing). Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `3965380` | chore: add openai>=1.0.0 dependency |
| `b4d1da9` | feat: add OpenAI provider translation module with tests |
| `c53c64c` | feat: add OpenAICompatibleProvider with tests |
| `fba88e6` | feat: implement OpenAICompatibleAgent with tests |
| `ab12531` | feat: add OpenAI-compatible provider |
| `4c547c7` | feat: add provider auto-loader and --base-url to spawn command |

**What was added:**
- `providers/openai/` package: `translation.py`, `provider.py`, `agent.py`, `__init__.py`
- `OpenAICompatibleProvider`: API key resolution (config → env → ProviderAuthError), `AsyncOpenAI` client construction, `base_url` pass-through, explicit `ProviderError` on missing model
- `OpenAICompatibleAgent`: conversation history, streaming accumulation, tool call reconstruction by chunk index, full error mapping (AuthenticationError→ProviderAuthError, RateLimitError→ProviderAPIError(429), APIStatusError→ProviderAPIError(status_code), APIConnectionError→ProviderError, APITimeoutError→ProviderTimeoutError)
- `translation.py`: `build_text_message`, `build_tool_call_message`, `build_messages` — pure functions, independently testable
- Auto-registration: `get_provider("openai")` available after import
- `_load_provider(name)` auto-loader in `spawn.py` — lazy `importlib.import_module` triggers provider registration; silent `ImportError` catch; benefits all providers retroactively
- `--base-url` flag on `spawn` command — passed through to `AgentConfig.base_url`

**Architecture note:** Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns. Accumulate full stream then yield complete `Message` objects to preserve `AsyncIterator[Message]` Protocol contract. Validated that `AgentProvider` Protocol generalizes beyond Anthropic with zero core engine changes.

**Issues logged:** None.

**Next:** Slice 112 (Provider Variants & Registry — OpenRouter, local, Gemini configs + model alias profiles).

### Slice 111: OpenAI-Compatible Provider Core — Slice Design Complete

**Documents created:**
- `user/slices/111-slice.openai-provider-core.md` — slice design (410 lines)

**Scope:** `OpenAICompatibleProvider` and `OpenAICompatibleAgent` using the `openai` Python SDK's `AsyncOpenAI` client with `base_url` override. Single implementation covers OpenAI, OpenRouter, Ollama/vLLM, and Gemini-compatible endpoints. Validates that `AgentProvider` Protocol generalizes beyond Anthropic with no core engine changes. Also fixes provider auto-loader gap in `spawn.py` and adds `--base-url` CLI flag.

**Key design decisions:**
- Per-agent `AsyncOpenAI` client (not per-provider) — credentials and `base_url` are per-agent concerns
- Accumulate full stream response before yielding `Message` objects — preserves `AsyncIterator[Message]` Protocol contract; streaming-through deferred as future evolution
- No silent model default — `ProviderError` if `config.model` is None (billing concern)
- Tool calls surfaced as `system` Messages with metadata; no execution (needs message bus + executor, future slice)
- `_load_provider(name)` auto-loader via `importlib.import_module` in `spawn.py` — silent `ImportError` catch; benefits all current and future providers retroactively
- Model alias / provider profile registry (`codex_53` → openai + model + base_url) deferred to slice 112

**Commit:** `864ed9c` docs: add slice design for 111-openai-provider-core

### Slice 111: OpenAI-Compatible Provider Core — Task Breakdown Complete

Task file created at `project-documents/user/tasks/111-tasks.openai-provider-core.md` (169 lines, 17 tasks). Test-with pattern applied; two commit checkpoints (T11 after providers/openai, T17 after CLI changes).

**Tasks overview:** T1 add dependency → T2 test infra → T3-T4 translation.py → T5-T6 provider.py → T7-T8 agent.py → T9-T10 `__init__.py` registration → T11 commit → T12-T13 auto-loader → T14-T15 `--base-url` flag → T16 full validation → T17 commit.

**Commit:** `5f4a7be` docs: add task breakdown for 111-openai-provider-core

---

## 20260223

### Model selection support (Issue #2)

Added `--model` flag to all review commands and spawn. Model threads through the full pipeline: config key (`default_model`) → ReviewTemplate YAML field → runner → `ClaudeAgentOptions`. Precedence: CLI flag → config → template default → None (SDK default). Template defaults: `opus` for arch/tasks, `sonnet` for code. Model shown in review output panel header at all verbosity levels. 17 new tests (298 total).

**Commit:** `9eae0f7` feat: add model selection support to review and spawn commands

### Rate limit handling fix (Issue #1)

Replaced the retry-entire-session loop (3 retries, 10s delay each) with a `receive_response()` restart on the same session. The SDK's `MessageParseError` (not publicly exported) fires on `rate_limit_event` messages the CLI emits while handling API rate limits internally. Fix catches `ClaudeSDKError` (public parent) with string match, restarts the async generator on the same connected session (anyio channel survives generator death), circuit breaker at 10 retries. Eliminates ~10-20s unnecessary delay. 3 new tests (301 total).

### Post-implementation: code review findings and fixes

Ran `orchestration review code` against its own codebase. Addressed three findings from the review:

1. **`_coerce_value` guard** — added explicit `str` check and `ValueError` for unsupported types (was silently falling through)
2. **Unknown config key warnings** — `load_config` now logs warnings for unrecognized keys in TOML files (catches typos)
3. **Double template loading** — `_execute_review` now accepts `ReviewTemplate` directly instead of re-loading by name
4. **CLAUDE.md exception** — documented that public-facing docs (`docs/`, root `README.md`) are exempt from YAML frontmatter rule

Also added rate-limit retry (3 attempts, 10s delay) in runner and friendlier CLI error message.

**Deferred findings** (logged for future work):
- Duplicated `cli_runner` fixture across 6 test files → promote to root `conftest.py`
- `_resolve_verbosity` can't override config back to 0 from CLI → consider `--quiet` flag

---

## 20260222

### Slice 106: M1 Polish & Publish — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 49 new tests (28 config + 12 verbosity + 6 rules + 3 cwd), 281 total project tests passing. Zero pyright/ruff errors on src/.

**Key commits:**
| Hash | Description |
|------|-------------|
| `9034843` | feat: add persistent config system with TOML storage |
| `196f03f` | feat: add config CLI commands (set, get, list, path) |
| `b002801` | feat: add verbosity levels and improve text colors |
| `b945fb4` | feat: add --rules flag, config-based cwd, and rules injection |
| `85c953e` | chore: format and fix pyright issues in slice 106 code |
| `eb44cef` | docs: add README, COMMANDS, and TEMPLATES documentation |

**What was added:**
- `config/` package: typed key definitions, TOML load/merge/persist manager, user + project config with precedence
- Config CLI: `config set/get/list/path` commands
- Verbosity levels (0/1/2) with `-v`/`-vv` flags on all review commands
- Text color improvements: bright severity badges, white headings, default foreground body text
- `--rules` flag on `review code` with config-based `default_rules`
- Config-based `--cwd` resolution across all review commands
- Documentation: `docs/README.md`, `docs/COMMANDS.md`, `docs/TEMPLATES.md`

**Architecture note:** `config.py` restructured to `config/__init__.py` package (same pattern as templates in slice 105) to coexist with `keys.py` and `manager.py`. TOML reading via stdlib `tomllib`, writing via `tomli-w`.

### Slice 106: M1 Polish & Publish — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/106-tasks.m1-polish-and-publish.md` (219 lines, 22 tasks).

**Commit:** `09a69cd` docs: add slice 106 task breakdown (m1-polish-and-publish)

### Slice 105: Review Workflow Templates — Phase 7 Implementation Complete

All 22 tasks (T1-T22) implemented. 76 review-specific tests, 226 total project tests passing. Zero pyright/ruff errors. Build succeeds.

**Key commits:**
| Hash | Description |
|------|-------------|
| `29c53e2` | feat: add pyyaml dependency |
| `dc8a4a4` | feat: add review result models |
| `fad9109` | feat: add ReviewTemplate, YAML loader, and registry |
| `1d29679` | refactor: restructure templates as package with builtin directory |
| `ea5839d` | feat: add built-in review templates (arch, tasks, code) |
| `a430358` | feat: add review result parser |
| `bff53a0` | feat: add review runner |
| `2feca18` | feat: add review CLI subcommand |
| `74eca88` | chore: review slice 105 final validation pass |

**Architecture note:** `templates.py` moved to `templates/__init__.py` package to coexist with `templates/builtin/` YAML directory. SDK literal types handled via `type: ignore` comments since template values are dynamic from YAML.

### Slice 105: Review Workflow Templates — Phase 5 Task Breakdown Complete

Task file created at `project-documents/user/tasks/105-tasks.review-workflow-templates.md` (210 lines, 22 tasks). Covers result models, YAML loader/registry, three built-in templates (arch, tasks, code), result parser, review runner, and CLI subcommand. Test-with ordering applied throughout; commit checkpoints after each stable milestone. Merge conflict in slice frontmatter resolved by PM prior to task creation.

---

## 20260220

### Slice 103: CLI Foundation & SDK Agent Tasks — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `8e76a6d` | feat: add Typer app scaffolding and pyproject.toml entry point |
| `4a4a478` | feat: implement CLI commands (spawn, list, task, shutdown) and test infra |
| `faaa5cc` | feat: refactor CLI commands to plain functions + add command tests |
| `b58d539` | feat: add integration smoke test + fix lint/type issues |

**What works:**
- 150 tests passing (22 new + 128 existing), ruff clean, pyright zero errors on src/ and tests/cli/
- `orchestration spawn --name NAME [--type sdk] [--provider P] [--cwd PATH] [--system-prompt TEXT] [--permission-mode MODE]`
- `orchestration list [--state STATE] [--provider P]` — rich table with color-coded state
- `orchestration task AGENT PROMPT` — `handle_message` async bridge, displays text and tool-use summaries
- `orchestration shutdown AGENT` / `orchestration shutdown --all` — individual and bulk with `ShutdownReport`
- `pyproject.toml` entry point registered; `orchestration --help` works
- All commands use `asyncio.run()` bridge pattern (sync Typer → async registry/agent)
- Unit tests: mocked registry via `patch_registry` fixture; integration smoke test: real registry + mock provider

**Key decisions:**
- Commands registered as plain functions via `app.command("name")(fn)` — not sub-typers. Sub-typers created nested groups (`spawn spawn --name`) rather than flat commands (`spawn --name`).
- `task` command uses `agent.handle_message(message)` (the actual Agent Protocol method), not a hypothetical `query()` method referenced in the task design
- `asyncio.run()` per command invocation — no persistent event loop, clean for CLI use
- Integration test patches the provider registry (not the agent registry) to use a mock SDK provider

**Issues logged:** None.

**Next:** Slice 5 (SDK Client Warm Pool).

---

## 20260219

### Slice 103: CLI Foundation & SDK Agent Tasks — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/103-slice.cli-foundation.md` — slice design
- `user/tasks/103-tasks.cli-foundation.md` — 11 tasks, test-with pattern

**Scope:** Typer CLI with four commands (`spawn`, `list`, `task`, `shutdown`) wiring the full path from terminal through Agent Registry and SDK Agent Provider to Claude execution. Async bridge via `asyncio.run()`. Rich output formatting (tables for `list`, styled text for responses). User-friendly error handling for all known failure modes. `pyproject.toml` script entry point. Integration smoke test (spawn → list → task → shutdown). **Completes Milestone 1.**

**Next:** Phase 7 (Implementation) on slice 103.

---

### Slice 102: Agent Registry & Lifecycle — Implementation Complete

**Commits:**
| Hash | Description |
|------|-------------|
| `23747c4` | feat: add AgentRegistry core with models, errors, spawn, and lookup |
| `9a40ff3` | feat: add list_agents filtering and individual shutdown to AgentRegistry |
| `26f61b4` | feat: add bulk shutdown and singleton accessor to AgentRegistry |
| `16d2a8a` | chore: fix linting, formatting, and type errors for agent registry |
| `a045636` | docs: mark slice 102 (Agent Registry & Lifecycle) as complete |

**What works:**
- 127 tests passing (26 new + 101 existing), ruff clean, pyright zero errors on src/ and new test file
- `AgentInfo` and `ShutdownReport` Pydantic models in `core/models.py`
- `AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError` error hierarchy
- `AgentRegistry.spawn()`: resolves provider, creates agent, tracks by unique name
- `AgentRegistry.get()`, `has()`: lookup by name with proper error raising
- `AgentRegistry.list_agents()`: returns `AgentInfo` summaries with optional state/provider filtering
- `AgentRegistry.shutdown_agent()`: always-remove semantics (agent removed even if shutdown raises)
- `AgentRegistry.shutdown_all()`: best-effort bulk shutdown returning `ShutdownReport`
- `get_registry()` / `reset_registry()` singleton accessor

**Key decisions:**
- Imports moved above error class definitions (ruff E402) — error classes placed after imports, not before
- `AgentInfo.provider` sourced from stored `AgentConfig`, not from the agent object (registry owns this mapping)
- `shutdown_agent()` uses try/finally to guarantee removal regardless of shutdown errors
- `shutdown_all()` collects errors per-agent without aborting — returns structured `ShutdownReport`
- MockAgent uses `set_state()` method instead of direct `_state` access to satisfy pyright's `reportPrivateUsage`

**Issues logged:** None.

**Next:** Slice 4 (CLI Foundation & SDK Agent Tasks).

---

### Slice 102: Agent Registry & Lifecycle — Design and Task Breakdown Complete

**Documents created:**
- `user/slices/102-slice.agent-registry.md` — slice design
- `user/tasks/102-tasks.agent-registry.md` — 14 tasks, test-with pattern

**Scope:** `AgentRegistry` class in `core/agent_registry.py` — spawn, get, has, list_agents (with state/provider filtering), shutdown_agent, shutdown_all. Registry errors (`AgentRegistryError`, `AgentNotFoundError`, `AgentAlreadyExistsError`). `AgentInfo` and `ShutdownReport` models added to `core/models.py`. Module-level `get_registry()` singleton. All tests use mock providers.

**Next:** Phase 7 (Implementation) on slice 102.

---

### Slice 101: SDK Agent Provider — Complete

**Objective:** Implement the first concrete provider — `SDKAgentProvider` and `SDKAgent` wrapping `claude-agent-sdk` for one-shot and multi-turn agent execution.

**Commits:**
| Hash | Description |
|------|-------------|
| `b44914a` | feat: implement SDK message translation module with tests |
| `f7d15e0` | feat: implement SDKAgentProvider with options mapping and tests |
| `3055fcf` | feat: implement SDKAgent with query and client modes |
| `83611a5` | feat: auto-register SDK provider and add integration tests |
| `8743255` | chore: fix linting, formatting, and type errors |

**What works:**
- 96 tests passing (51 new + 45 foundation), ruff clean, pyright strict zero errors
- `translation.py`: Converts SDK message types (AssistantMessage, ToolUseBlock, ToolResultBlock, ResultMessage) to orchestration Messages
- `SDKAgentProvider`: Maps `AgentConfig` to `ClaudeAgentOptions`, defaults `permission_mode` to `"acceptEdits"`, reads mode from `credentials` dict
- `SDKAgent` query mode: One-shot via `sdk_query()`, translates and yields response messages
- `SDKAgent` client mode: Multi-turn via `ClaudeSDKClient` (create once, reuse), `shutdown()` disconnects
- Error mapping: All 5 SDK exception types → orchestration `ProviderError` hierarchy
- Auto-registration: Importing `orchestration.providers.sdk` registers `"sdk"` in the provider registry
- `validate_credentials()` returns bool without throwing

**Key decisions:**
- `translate_sdk_message` returns `list[Message]` (not `Message | None`) — `AssistantMessage` with multiple blocks produces multiple Messages, empty list for unknown types
- Deferred import of `SDKAgent` in `provider.py` to avoid stub-state issues at module load
- ruff requires `query as sdk_query` alias in a separate import block from other `claude_agent_sdk` imports (isort rule)
- Used `__import__("claude_agent_sdk")` in `validate_credentials` to satisfy pyright's `reportUnusedImport`
- Real SDK dataclasses used for test fixtures (no MagicMock — `TextBlock`, `AssistantMessage`, etc. are simple dataclasses)

**Issues logged:** None.

**Next:** Slice 3 (Agent Registry & Lifecycle) or slice 4 (CLI Foundation).

---

### Slice 100: Foundation Migration — Complete

**Objective:** Migrate foundation from v1 (LLMProvider-based) to v2 (dual-provider Agent/AgentProvider architecture) per `100-arch.orchestration-v2.md`.

**Commits:**
| Hash | Description |
|------|-------------|
| `7200b4e` | feat: add claude-agent-sdk dependency |
| `b6e1264` | feat: add SDK and Anthropic provider subdirectories with stubs |
| `6a389a5` | feat: add shared provider error hierarchy |
| `9700bed` | refactor: rename Agent to AgentConfig, remove ProviderConfig |
| `5ebf6cb` | test: update model tests for AgentConfig migration |
| `2433494` | refactor: replace LLMProvider with Agent and AgentProvider Protocols |
| `0b4302e` | refactor: retype provider registry for AgentProvider instances |
| `90dd38b` | test: update provider tests for AgentProvider instances and error hierarchy |
| `cb1d56c` | refactor: update Settings for dual-provider architecture |
| `0d3da45` | test: update config tests for new Settings fields |
| `f944f02` | docs: update .env.example for dual-provider architecture |
| `fd45a0d` | docs: update stub docstrings with correct slice numbers |
| `f189dc2` | fix: type checking — zero pyright errors |
| `5aaf718` | docs: mark foundation migration tasks and slice complete |

**What works:**
- 45 tests passing, ruff check clean, ruff format clean, pyright strict zero errors
- `AgentConfig` model with SDK-specific fields (cwd, setting_sources, allowed_tools, permission_mode) and API fields (model, api_key, auth_token, base_url)
- `Agent` and `AgentProvider` Protocols (runtime_checkable, structural typing)
- Provider registry maps type names to `AgentProvider` instances
- Shared error hierarchy: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`, `ProviderTimeoutError`
- Settings with `default_provider="sdk"`, `default_agent_type="sdk"`, auth token and base URL support
- Provider subdirectories: `providers/sdk/` and `providers/anthropic/` with stubs
- All stub docstrings updated to correct slice numbers per v2 plan

**Key decisions:**
- `handle_message` in Agent Protocol is a sync method signature (not `async def`) — implementations are async generators, callers use `async for` directly without `await`
- `ProviderTimeoutError` chosen over `ProviderConfigError` — config errors caught at Pydantic validation time; timeout is the real operational concern
- `sdk_default_cwd` kept off Settings (per-agent config via AgentConfig, not global)
- `claude-agent-sdk` imports as `claude_agent_sdk` (module name differs from package name)

**Issues logged:** None.

**Next:** Slice 2 (SDK Agent Provider) or slice 101 (Anthropic Provider) — both can proceed in parallel as they only depend on foundation.

---

## 20260218

### Slice 101: Anthropic Provider — Design Complete

**Documents created:**
- `user/slices/101-slice.anthropic-provider.md` — slice design

**Key design decisions:**
- **API key auth only**: The official Anthropic Python SDK supports `api_key` / `ANTHROPIC_API_KEY` exclusively. No native `auth_token` parameter exists. Claude Max / OAuth bearer token usage requires external gateways (e.g., LiteLLM) — out of scope for this slice but extensible via `ProviderConfig.extra["base_url"]` in future.
- **Async-only client**: `AsyncAnthropic` exclusively — no sync path needed given async framework.
- **SDK streaming helper**: Uses `client.messages.stream()` context manager (not raw `stream=True`) for typed text_stream iterator and automatic cleanup.
- **Minimal error hierarchy**: `ProviderError` → `ProviderAuthError`, `ProviderAPIError`. SDK exceptions mapped to provider-level errors at boundaries.
- **No custom retry**: SDK built-in retry (2 retries, exponential backoff) is sufficient.
- **Default max_tokens=4096**: Required by Anthropic API, configurable via `ProviderConfig.extra`.

**Scope summary:**
- `AnthropicProvider` class satisfying `LLMProvider` Protocol (send_message, stream_message, validate)
- Message conversion: `orchestration.Message` → Anthropic dict format (role mapping, system extraction, consecutive role merging)
- API key resolution: `ProviderConfig.api_key` → `Settings.anthropic_api_key` → explicit error
- Auto-registration in provider registry via `providers/__init__.py`
- Full mock-based test suite (no real API calls)

**Commits:**
- `3c418e0` docs: add slice 101 design (Anthropic Provider)

**Next:** Phase 5 (Task Breakdown) on slice 101, then Phase 7 (Implementation).

### Slice 100: Foundation — Design and Task Creation Complete

**Documents created:**
- `user/slices/100-slice.foundation.md` — slice design (project setup, package structure, core Pydantic models, config, logging, provider protocol, test infrastructure)
- `user/tasks/100-tasks.foundation.md` — 19 granular tasks, sequentially ordered

**Key design decisions:**
- **Test-with ordering**: Tasks are structured so each implementation unit (models, providers, config, logging) is immediately followed by its tests, catching contract issues early rather than batching tests at the end
- **All dependencies installed up front**: `pyproject.toml` includes all project dependencies (anthropic, typer, fastapi, google-adk, mcp, etc.) so later slices just import and use
- **Protocol over ABC**: `LLMProvider` defined as a `Protocol` for structural typing, better ADK compatibility later
- **Stdlib logging only**: No third-party logging library; JSON formatter on stdlib `logging` keeps dependencies minimal

**Scope summary:**
- Project init with `uv`, `src/orchestration/` package layout matching HLD 4-layer architecture
- Pydantic models: Agent, Message, ProviderConfig, TopologyConfig (with StrEnum types)
- Pydantic Settings for env-based config (`ORCH_` prefix), `.env.example`
- LLMProvider Protocol + dict-based provider registry
- Structured logging (JSON + text formats)
- Full test infrastructure and validation pass

**Commits:**
- `007b02f` planning: slice 100 foundation — design and task breakdown complete

**Next:** Phase 6 (Task Expansion) on `100-tasks.foundation.md`, or proceed directly to Phase 7 (implementation) if PM approves skipping expansion for this low-complexity slice.