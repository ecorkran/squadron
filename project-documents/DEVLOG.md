---
docType: devlog
scope: project-wide
description: Internal session log for development work and project context
---

# Development Log

Internal work log for squadron project development.

---

## 20260520

### Slice 908: `sq setup` — Phase 6 Implementation Complete

**Completed:** Phase 6 implementation for slice 908. Slice is complete.

**Shipped:**
- `src/squadron/cli/commands/setup_steps.py` (~220 lines): pure conversion layer (`CheckResult → SetupStep`). `StepKind` StrEnum, `SetupStep` frozen dataclass, `_RECHECK_MAP`, `_classify`, `build_steps` with profile filtering, `_DOCS_ANCHOR`, `_EXPLANATION`, synthesised per-profile recheck lambdas.
- `src/squadron/cli/commands/setup.py` (~120 lines): Typer command with `--non-interactive`, `--check-only`, `--profile`, `--verbose` flags. Rendering functions `_render_check_only`, `_render_non_interactive`, `_run_interactive` (re-prompt cap=5, `q` exits 2).
- `src/squadron/cli/app.py`: `app.command("setup")(setup)` registration.
- `scripts/install.sh` (~100 lines): bash bootstrap with `set -euo pipefail`, interactive prompts, `uv`/`pipx` detection, `npm` detection, `--yes`/`--help` flags, `exec sq setup` handoff.
- `tests/cli/test_setup_steps.py`: 20 tests covering T3, T6, T10, T11, T12.
- `tests/cli/test_setup.py`: 10 tests covering T18a, T18b, T19, T20, T21, T22, T23, T24.
- `tests/scripts/test_install_sh.sh` + `test_install_sh.py`: idempotency smoke test (T26).
- README: "Fresh install (one liner)" section added (T27).
- CHANGELOG: `sq setup` and `scripts/install.sh` entries added.

**Deviations from design:** None. All design decisions implemented as specified.
- T28 (QUICKSTART callout) skipped — `docs/QUICKSTART.md` does not exist yet (slice 906 not merged). DEVLOG follow-up noted.
- Aggregate "at least one provider OK" suppression optimisation deferred per design decision (initial release shows all profile rows).

**Test results (final gate):**
- `pytest tests/cli/test_setup.py tests/cli/test_setup_steps.py tests/scripts/test_install_sh.py -q`: **31 passed**
- `pytest -q` (full suite): **1936 passed, 2 skipped**
- `ruff check && ruff format --check && pyright`: **all clean**

**Exit codes verified:** 0 (all OK), 1 (MISSING present), 2 (user quit), 3 (internal error), 64 (unknown profile).

**Follow-up:** When slice 906 merges and `docs/QUICKSTART.md` exists, add the `sq setup` callout under Step 5 / Troubleshooting (T28).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

---

## 20260519

### Slice 908: `sq setup` One-Call Install Orchestrator — Phase 4 Slice Design Complete

**Completed:** Phase 4 low-level design for slice 908.

**Document created:**
- `project-documents/user/slices/908-slice.sq-setup-one-call-install-orchestrator.md` — full slice design (status: `not_started`)

**Slice plan updated:** `900-slices.maintenance-and-refactoring.md` entry 7 now references the materialized design path.

**Design highlights:**
- `sq setup` is a *renderer* over slice 905's `run_all_checks()` — no new check logic. Conversion layer maps each `CheckResult` to a `SetupStep` with kind `ALREADY_DONE` / `INSTALL` / `CONFIGURE` / `OPTIONAL`.
- Three modes: interactive (default, one prompt per missing step with `enter/s/q`), `--non-interactive` (emit all steps without prompts; pipe-to-file friendly), `--check-only` (one-liner per step, exits with `sq doctor`'s code).
- `--profile <name>` filters Provider-section steps to a single profile.
- Per-step re-check via a local "check-name → function" map inside `setup_steps.py`. Degrades to "press enter when done" if 905 adds checks we haven't mapped.
- Companion `scripts/install.sh` (bash) handles only the pre-Squadron bootstrap (pipx/uv → `pipx install squadron-ai` → `npm i -g @manta-digital/context-forge` → handoff to `sq setup`). No automatic shell execution from Python.
- Distribution via GitHub raw URL: `curl -sSL <raw URL> | sh`. Pinning to a tag is a follow-up.
- Idempotency contract: setup is re-runnable, install.sh is re-runnable; both detect existing state and skip done steps.

**Cross-slice contract:**
- Strict consumer of slice 905's `CheckResult`, `CheckStatus`, `run_all_checks()`. No API changes requested upstream.
- References slice 906 (QUICKSTART) anchors for `docs_anchor`. If 906 ships later, anchors degrade gracefully to plain section names.

**Branch:** `908-sq-setup-one-call-install-orchestrator` (created from `main`).

**Next:** Phase 5 task breakdown — `task-checker`-friendly checklist derived from this design.

---

### Slice 908: `sq setup` — Phase 5 Task Breakdown Complete

**Completed:** Phase 5 task breakdown for slice 908.

**Document created:**
- `project-documents/user/tasks/908-tasks.sq-setup-one-call-install-orchestrator.md` — 32 tasks (T1–T32) across seven phases (status: `not_started`).

**Phase shape (test-with-pattern preserved throughout):**
- **A. Setup and data model** — branch confirmation, skeleton files, `StepKind` / `SetupStep` dataclass, baseline tests.
- **B. `build_steps` conversion layer (pure)** — recheck-function map, `_classify`, `build_steps`, docs-anchor map, explanation strings; each implementation immediately followed by its tests.
- **C. `setup.py` Typer command and rendering** — command skeleton with all flags, `--check-only` / `--non-interactive` / interactive renderers, registration in `cli/app.py`.
- **D. Tests for `setup.py`** — `CliRunner`-based coverage of every flag combination, profile filter, `q`-quit, recheck loop, and the internal-error fallback.
- **E. `install.sh` bootstrap** — bash script with `set -euo pipefail`, explicit prompts before each install, plus a `pytest`-wrapped idempotency smoke test using PATH-shimmed stubs.
- **F. Documentation** — README one-liner pointer; optional QUICKSTART callout gated on slice 906 merge order.
- **G. Final gate** — full `pytest` / `ruff` / `pyright` gate, verification walkthrough recording into the slice design, slice-plan checkbox flip, DEVLOG closeout.

**Notable design constraints carried into tasks:**
- No automatic shell execution from Python beyond `install_commands()` with explicit consent.
- Per-step re-check cap = 5 (prevents infinite loops in scripted stdin).
- `q` exits 2 (user-aborted), distinct from 1 (`sq doctor` reports missing) and 3 (internal error).
- `_DOCS_ANCHOR` and `_EXPLANATION` maps are local to `setup_steps.py` — no upstream API changes to slice 905.

**Review note:** Phase 4 review flagged 908 as "new feature under maintenance arch" (F001). PM decision was to leave categorisation alone — 905/906/908 form a cohesive onboarding trio that has historically lived under the 900 maintenance architecture. No design changes resulted.

**Task file size:** 259 lines (well under 450-line target; no split needed).

**Branch:** `908-sq-setup-one-call-install-orchestrator`.

**Next:** Phase 6 implementation following T1–T32 in order.

---

## 20260510

### Slice 250: Container Step Classification — Implementation Complete

**Completed:** Phase 6 implementation. Slice 250 is complete.

**Summary of changes (commit 91f8ccd):**
- New `src/squadron/pipeline/steps/utils.py` — `unpack_inner_steps` extracted from `executor.py` to eliminate circular import
- `executor.py` — replaced local `_unpack_inner_steps` with imported utility
- `EachStepType.inner_steps()`, `LoopStepType.inner_steps()` — parse `steps:` list, return `StepConfig` objects
- `FanOutStepType.inner_steps()` — returns one synthetic `_fan_out_aggregate` sentinel carrying the `models:` value
- `classification.py` — added `_classify_alias_set` (shared alias-set aggregator), `_classify_container_inner` (classifies a single inner step / handles `_fan_out_aggregate` sentinel), extended main step loop to descend into containers when `expand()` returns `[]`; added `container_path: str | None = None` field to `StepClassification`
- `run.py` — `_render_explain` emits dim container header rows and `↳ {inner_name}` indented inner-step rows
- 27 new tests across `test_inner_steps.py`, `test_classification.py`, `test_run.py`
- Full suite: 1869 passed, 2 pre-existing failures (compact compose integration)

**Notable implementation decisions:**
- Used `getattr(step_impl, "inner_steps", None)` instead of a lambda to avoid pyright `Unknown` errors
- Rich wraps cell content in narrow test terminals — `↳` assertions check for the symbol presence rather than `"↳ name"` substring
- `_classify_pool_step` refactored to a thin wrapper over `_classify_alias_set` preserving `pool_name`

---

### Slice 250: Container Step Classification — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/250-tasks.container-step-classification-each-loop-fan-out.md` — 12 tasks, 321 lines

**Task structure:**
- T1: Branch setup
- T2: Extract `_unpack_inner_steps` → `steps/utils.py` (removes circular import); update executor call sites
- T3: `EachStepType.inner_steps()` + tests
- T4: `LoopStepType.inner_steps()` + tests
- T5: `FanOutStepType.inner_steps()` returning sentinel `_fan_out_aggregate` + tests
- T6: Extract `_classify_alias_set` from `_classify_pool_step`; regression test
- T7: Add `container_path: str | None = None` to `StepClassification`; regression test
- T8: Core classifier extension — `_classify_container_inner` helper + modified step loop; 9 new classification tests
- T9: `_render_explain` container rendering (header row + `↳` indent) + 3 rendering tests
- T10: ruff format/check, pyright, full pytest gate
- T11: Implementation commit
- T12: Slice closeout (status, slice plan, CHANGELOG, DEVLOG, docs commit)

**Key task notes:**
- T2 is the prerequisite for T3/T4 (circular import blocker). T5 is independent of T3/T4.
- T6 must precede T8 (T8 calls `_classify_alias_set`).
- T7 must precede T8 and T9 (both use `container_path`).
- T8's `_classify_container_inner` asserts `inner.step_type != "_fan_out_aggregate"` before `get_step_type()`, enforcing the sentinel invariant.

**Status:** Ready for Phase 6 (Implementation).

---

### Slice 250: Container Step Classification — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/250-slice.container-step-classification-each-loop-fan-out.md` — full LLD
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice 250 entry updated with design link and today's date

**Key design decisions:**
- `inner_steps(config)` added as an optional extension method on step types (detected via `hasattr`, not a required protocol method) — avoids touching all existing step type files.
- `_unpack_inner_steps` extracted from `executor.py` to a shared location so `EachStepType` and `LoopStepType` can reuse it in `inner_steps()` without a circular import.
- `fan_out` returns one synthetic sentinel `StepConfig` (`step_type="_fan_out_aggregate"`) encoding the `models:` field. The classifier detects the sentinel and routes to pool-classify or alias-list-classify accordingly.
- `_classify_alias_set` extracted from `_classify_pool_step` as a shared helper — both the pool path and the fan_out literal-list path call the same aggregation rule.
- `StepClassification` gains `container_path: str | None = None` (backward-compatible, defaults to `None`).
- `--explain` rendering uses `  ↳` indent in the Step column rather than a new column — keeps table width manageable.
- Parent step attribution: inner-step `StepClassification` rows carry the container's `step_name` and `step_index`, not the inner step's own name (which goes in `container_path`).
- No executor changes in scope.

**Status:** Ready for Phase 5 (Task Breakdown).

---

## 20260504

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Task Breakdown Complete

**Completed:** Phase 5 task breakdown.

**Documents created:**
- `project-documents/user/tasks/245-tasks.pool-resolution-classification-policy-and-mid-run-session-construction.md` — 19 tasks across: enum addition, `PipelineClassification` policy field, `classify_pipeline` default change, `auth_policy` YAML field (`PipelineSchema` + `PipelineDefinition`), `execute_pipeline` mid-run hook + helpers, connect-failure UX, `--strict` CLI flag, policy resolution, existing test audit, build/format, and closeout.

**Key task notes:**
- T7: `PipelineSchema` has `extra="forbid"` — `auth_policy` must be added as a declared field; validator rejects anything other than `None`/`"lazy"`/`"strict"`.
- T9: `_step_needs_sdk` ignores pool candidates (returns `False`) — hook fires only on statically confirmed SDK steps.
- T11: connect failure → run state `failed` + re-raise → `_run_pipeline_sdk` catches and prints red message.
- T15: existing pool-uncertain tests relied on the old conservative default; they need `policy=STRICT` annotations or assertion updates.

**Pending:** Phase 6 (implementation). No open questions.

---

### Slice 245: Pool-Resolution Classification Policy and Mid-Run Session Construction — Design Complete

**Completed:** Phase 4 slice design.

**Documents created/updated:**
- `project-documents/user/slices/245-slice.pool-resolution-classification-policy-and-mid-run-session-construction.md` — slice design
- `project-documents/user/architecture/240-slices.pipeline-auth-boundary-flexibility.md` — slice plan entry 5 updated with design link and revised policy framing

**Design summary:**
- **Lazy is the default.** Session not constructed at startup for pool-uncertain pipelines. `--strict` CLI flag (and `auth_policy: strict` pipeline config key) opts into eager upfront connection.
- `PoolClassificationPolicy` enum (`lazy` / `strict`) in `pipeline/classification.py`; default is `LAZY`.
- `classify_pipeline` gains optional `policy` parameter (default `LAZY`); `PipelineClassification` stores the policy used.
- `needs_persistent_session`: under `LAZY`, `POOL_UNCERTAIN` does not force session construction; only statically-confirmed `SDK_REQUIRED` steps do.
- Mid-run hook in `execute_pipeline` (arch §5a): fires on first confirmed-SDK step when `sdk_session is None`; all subsequent steps reuse the same session. Hook is policy-agnostic (dead path under strict mode since session is pre-constructed).
- Auth-failure UX: connect failure mid-run → `failed` run state + clear message; runtime pool selects SDK with no session → `FAILED` step result with `--strict` remediation hint.
- 12 new tests planned across `test_run_pipeline_lazy.py` and `test_classification.py`. Existing pool-uncertain tests need policy annotation update.

**Pending:** Phase 5 (task breakdown) and Phase 6 (implementation). No open questions; design is self-contained.

---

### Slice 244: Conditional Persistent Session Construction — Implementation Complete

**Completed:** Phase 6 implementation (commit c939fb2, branch `244-slice.conditional-persistent-session-construction`)

**Files changed:**
- `src/squadron/cli/commands/run.py` — Added `pool_backend: PoolBackend | None = None` param to `_run_pipeline`; added guard replacing unconditional `DefaultPoolBackend()`. In `_run_pipeline_sdk`: lifted `DefaultPoolBackend()` construction, added `_classify_resolver` (no `on_pool_selection`), added `classify_pipeline` call with `ClassificationError` handler, added INFO/DEBUG logging of classification shape, added session gate (`if classification.needs_persistent_session`). Added `_logger = logging.getLogger(__name__)`.
- `tests/cli/commands/test_run_pipeline_sdk.py` — New test file: 11 tests covering T3 (fallback), T6 (classification gate: all 6 scenarios), T7 (resume path: 2 scenarios).
- `tests/pipeline/test_sdk_wiring.py` — Updated 2 tests to mock `classify_pipeline`/`DefaultPoolBackend`/`ModelResolver` for `needs_persistent_session=True` (tests verify connect/disconnect lifecycle; mock classification is correct because those tests are about lifecycle, not classification).

**Design decisions confirmed during implementation:**
- `on_pool_selection` callback needs `state_mgr`/`_run_id` (initialized inside `_run_pipeline`), so the classification resolver `_classify_resolver` is built without a callback — classification is side-effect-free and never calls `pool_backend.select()`.
- `typer.Exit` raises `click.exceptions.Exit`, not `SystemExit` — tests use `pytest.raises(typer.Exit)` with `exc_info.value.exit_code == 1`.
- Tests run inside Claude Code session (`CLAUDECODE` env var set), so all `_run_pipeline_sdk` tests patch `_resolve_execution_mode` to bypass the session guard.
- Pre-existing failures: `tests/pipeline/test_compact_compose_integration.py` (2 tests) were already failing on main before this slice; not introduced here.

**Audit (T9):** `sdk_session=None` guards confirmed present in `compact.py:62`, `summary.py:149`, `summary.py:218`. No changes needed.

**Test results:** 1806 passing, 2 pre-existing failures (compact compose, unrelated), 0 new failures.

---

### Slice 244: Conditional Persistent Session Construction — Task Breakdown Complete

**Completed:**
- Created `user/tasks/244-tasks.conditional-persistent-session-construction.md` (11 tasks, 192 lines)

**Task structure:**
- T1: Branch setup
- T2: Add optional `resolver`/`pool_backend` params to `_run_pipeline` (backward-compatible)
- T3: Test fallback path (no params supplied)
- T4: Lift `pool_backend`/`resolver` construction into `_run_pipeline_sdk`; wire `on_pool_selection`
- T5: Add `classify_pipeline` call and session gate in `_run_pipeline_sdk`
- T6: Tests for classification gate (T1–T5, T8 from design — non-SDK, SDK, pool-uncertain, ClassificationError, connect failure)
- T7: Tests for resume path (T6, T7 from design)
- T8: Intermediate commit (ruff + pyright + pytest gate)
- T9: Audit `sdk_session=None` correctness for summary/compact (belt-and-suspenders verification)
- T10: Final validation and commit
- T11: Documentation and slice closeout

**Key design note in tasks:** `on_pool_selection` callback depends on `state_mgr`/`_run_id`, which are initialized inside `_run_pipeline`. T4 explicitly flags that the callback must be attached after `state_mgr` is known — implementer must set `resolver._on_pool_selection` inside `_run_pipeline` when `resolver is not None`, or add a setter. Classification never fires pool selection (side-effect-free), so the callback is safe to attach late.

**Status:**
- Task breakdown complete and ready for Phase 6 (Implementation).

---

### Slice 244: Conditional Persistent Session Construction — Design Complete

**Completed:**
- Created `user/slices/244-slice.conditional-persistent-session-construction.md`
- Updated slice plan entry 244 in `240-slices.pipeline-auth-boundary-flexibility.md` with design link

**Key design decisions:**
- Classification runs inside `_run_pipeline_sdk` after `definition` is loaded and `resolver` is constructed — before any session work.
- `pool_backend` and `resolver` are constructed in `_run_pipeline_sdk` and threaded into `_run_pipeline` as optional params; `_run_pipeline`'s internal fallback construction is preserved for callers that don't supply them.
- `POOL_UNCERTAIN` steps take the conservative-pessimistic path (session constructed); lazy opt-in is slice 245.
- `ClassificationError` → `typer.Exit(1)` with a clear message; not an unhandled exception.
- Resume re-classifies from current YAML + alias state; seeding path unchanged (runs only when `sdk_session is not None`).
- Three observable shapes fully established: `claude_required_persistent`, `claude_required_one_shot`, `claude_free`.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260518

### Slice 907: Optional Dependency Split — Task Breakdown Complete

**Completed:** Phase 5 task breakdown. Task file created at `user/tasks/907-tasks.optional-dependency-split-serve-and-codex-extras.md` (173 lines, 8 task groups, 31 checklist items).

**Task structure:**
- T1: Branch setup
- T2: `pyproject.toml` — remove fastapi/uvicorn from deps, add `[serve]` and `[codex]` extras
- T3: Extract `src/squadron/server/pid.py` (DaemonConfig + PID helpers); update `daemon.py` to import from it; update `tests/server/test_daemon.py`
- T4: Update `serve.py` — top-level imports switch to `pid.py`; `start_server`/`SquadronEngine` deferred into `_start_daemon()` after import guard
- T5: Codex binary guard in `provider.py` — `create_agent()` raises `ProviderError` (not `ProviderAuthError`) when binary absent
- T6: Full test suite + static analysis (ruff, pyright, pytest)
- T7: Clean-venv verification walkthrough
- T8: Commit

**Status:** Ready for Phase 6 (Implementation).

---

## 20260514

### Slice 907: Optional Dependency Split — Design Complete

**Completed:**
- Created `user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md`

**Key Design Decisions:**
- `fastapi` and `uvicorn` move from `[project.dependencies]` to a new `[serve]` optional extra.
- `[codex]` extra is declared empty (PyPI rejects direct URL refs); a comment block carries the GitHub install command.
- `sq serve` start guard lives inside `_start_daemon()` — `--status` and `--stop` remain usable without `[serve]`.
- `start_server` and `SquadronEngine` imports deferred into `_start_daemon` after the guard; `DaemonConfig`/PID helpers stay top-level (verify they don't transitively pull fastapi; extract to `server/pid.py` if they do).
- `CodexProvider.create_agent()` gains an early binary check (`resolve_codex_binary is None` → `ProviderAuthError` with `npm i -g @openai/codex`). SDK import guard already present in `_run_prompt`; no change needed there.

**Status:**
- Design ready for Phase 5 (Task Breakdown).

---

## 20260424

### Slice 167: Per-Action Model Override Convention — Design Complete

**Completed:**
- Created `user/slices/167-slice.per-action-model-override-convention.md`
- Enhanced existing stub with full design: data flow, cascade position, code
  change, YAML/params interaction (no loader change required), test list,
  verification walkthrough, and documentation target
- Key technical decision: `params["review_model"]` is a separate params channel
  from `params["model"]`; step-level `review.model: X` wires into `params["model"]`
  (unchanged), while `--param review_model=Y` writes to the new key — no conflict
- `docs/PIPELINES.md` Model Resolution section is the documentation target
- First adopter: `ReviewAction` only; future actions adopt independently

**Design decisions recorded:**
- `review_model` (underscore) is the canonical convention key matching Python dict
  and `--param` syntax; existing `review-model` (hyphen) YAML param continues to
  work via step-level wiring unchanged
- No loader change needed — the two channels are naturally separate by how params
  merge in the executor

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Design Complete

**Completed:**
- Verified `user/slices/154-slice.prompt-only-loops.md` against current codebase — all technical assumptions confirmed accurate
- Codebase verification: all 5 executor functions to be reused (`_parse_source`, `_SOURCE_REGISTRY`, `resolve_placeholders`, `_unpack_inner_steps`, `_resolve_str`) exist and are module-level; all 3 CLI handlers exist; `ExecutionMode` enum, `EachStepType`, `StepTypeName.EACH` in place
- Schema v4 confirmed current; design's v4→v5 bump plan is correct
- Implementation targets confirmed absent (as expected): `LoopContext` model, `loop_context` field on `RunState` and `StepInstructions`
- Updated frontmatter status from `not_started` to `in_progress`
- Note: Phase 5 task file (`154-tasks.prompt-only-loops.md`) was created in a prior session (20260410) but reverted (`39c575d`) — Phase 5 needs to be re-executed

**Status:**
- Phase 4 complete. Design verified and current. Ready for Phase 5 (task breakdown).

---

### Slice 154: Prompt-Only Loops — Phase 4 Design Refreshed

**Completed:**
- Refreshed `user/slices/154-slice.prompt-only-loops.md` against current codebase state (post slices 153–169)
- Updated data models to use Pydantic `BaseModel` (matching `RunState` pattern, was dataclass)
- Schema version bump: v4 → v5 (was v1 → v2 in original design; actual codebase is now at v4)
- Clarified `StateManager` interaction: `first_unfinished_step` remains loop-unaware; loop logic lives in CLI handlers (`_handle_prompt_only_init`, `_handle_prompt_only_next`, `_handle_step_done`)
- Added `LoopContext` model with cached `items` list for deterministic resume
- Documented reuse of executor internals: `_SOURCE_REGISTRY`, `_parse_source`, `resolve_placeholders`, `_unpack_inner_steps`
- Updated out-of-scope references to reflect completed slices (160 checkpoints, 169 compact dispatch)
- Updated slice plan entry from "Design preserved" to "Design Complete"

**Design decisions (unchanged from original, validated against current code):**
- Loop iterations flattened into instruction stream — callers are loop-unaware
- Step names follow `{inner_step_name}-each-{item_index}` pattern
- Flattened step names go into `completed_steps`; parent `each` step recorded on loop completion
- Source items cached in LoopContext for deterministic resume

**Status:**
- Phase 4 complete. Ready for Phase 5 (task breakdown).

---

## 20260412

### Slice 191: Dispatch Summary Context Injection — Phase 5 Task Breakdown Complete

**Completed:**
- Created `user/tasks/191-tasks.dispatch-summary-context-injection.md` (171 lines, 7 tasks)
- Tasks cover: new `summary_context.py` module (T1), unit tests for assembler (T2),
  integration into `_execute_summary()` (T3), integration tests (T4), full verification
  and commit (T5), end-to-end verification (T6), slice completion (T7)
- Implementation note captured: `ActionType` has no `COMPACT` entry; compact steps
  expand to `"summary"` action type — the `match/case` only needs `ActionType.SUMMARY`

**Status:**
- Phase 5 complete. Ready for Phase 6 (implementation).

---

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

