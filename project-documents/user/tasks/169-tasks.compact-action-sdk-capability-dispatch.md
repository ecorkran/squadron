---
docType: tasks
slice: compact-action-sdk-capability-dispatch
project: squadron
lld: user/slices/169-slice.compact-action-sdk-capability-dispatch.md
dependencies:
  - 149-pipeline-executor-and-loops
  - 161-summary-step-with-emit-destinations
  - 164-profile-aware-summary-model-routing
  - 166-compact-and-summary-unification
projectState: >
  main is clean; v0.4.2 released. Slice 169 Phase 4 complete (moved from 193).
  compact: YAML is currently a step type that expands to summary(emit=[rotate]).
  No CompactAction exists; ActionType has no COMPACT entry. SummaryAction
  has no restore: true field. SessionCapabilities does not exist.
dateCreated: 20260422
dateUpdated: 20260426
status: complete
---

## Context Summary

- Working on slice 169: Compact Action — SDK Capability Dispatch (140-band)
- Replaces compact's implicit summarize+rotate with a dedicated `CompactAction` that
  dispatches the best available behavior per environment (SDK rotate flow in true CLI;
  `/compact` via `query()` in prompt-only)
- Adds `SessionCapabilities` dataclass populated from the SDK init message
  `slash_commands` field — capability discovery, not environment heuristics
- Adds `restore: true` mode to `SummaryAction` for summary re-injection
- YAML `compact:` remains valid; behavior changes, syntax does not
- Key files: `src/squadron/pipeline/steps/compact.py`,
  `src/squadron/pipeline/actions/` (new compact.py + updated __init__.py),
  `src/squadron/pipeline/models.py` (ActionContext),
  `src/squadron/pipeline/sdk_session.py` (existing compact() reused)
- Implementation order follows slice design §Implementation Notes
- Branch: `169-slice.compact-action-sdk-capability-dispatch`

---

## Tasks

### T1 — Branch setup

- [x] **Create implementation branch**
  - [x] Verify on `main`, working tree clean
  - [x] `git checkout -b 169-slice.compact-action-sdk-capability-dispatch`

---

### T2 — Capability discovery: `SessionCapabilities` dataclass [dropped]

- [x] **Add `SessionCapabilities` to `src/squadron/pipeline/models.py`** [dropped — design simplification]
  - [x] Add dataclass `SessionCapabilities` with field
    `slash_commands: frozenset[str]`
  - [x] Add optional field `capabilities: SessionCapabilities | None = None`
    to `ActionContext`
  - [x] `SessionCapabilities` is a plain frozen dataclass — no external deps
  - [x] Success: `ActionContext(... capabilities=None)` type-checks clean;
    `SessionCapabilities(slash_commands=frozenset({"/compact"}))` instantiates

- [x] **Tests for `SessionCapabilities`** [dropped]
  - [x] Add unit tests in `tests/pipeline/test_models.py` (or nearest models
    test file): verify `ActionContext.capabilities` defaults to `None`;
    verify `SessionCapabilities.slash_commands` is `frozenset`
  - [x] pyright clean on models.py

---

### T3 — Capability probe in the SDK executor [dropped]

- [x] **Probe SDK init message in the pipeline executor — true CLI** [dropped — design simplification]
  - [x] Locate where `SDKExecutionSession` / `ClaudeSDKClient` is initialized
    in the executor (see `src/squadron/cli/commands/run.py` and
    `src/squadron/pipeline/executor.py` or equivalent)
  - [x] After session start, read the first `SystemMessage(subtype="init")`
    and extract `data.get("slash_commands", [])` into a `frozenset`
  - [x] Store as `SessionCapabilities` on the `ActionContext` passed to all
    subsequent steps; probe fires once per session, result is cached
  - [x] If init message not received before first step, populate with empty
    frozenset (do not block indefinitely — log a WARNING)

- [x] **Probe SDK init message in the prompt-only executor** [dropped]
  - [x] In the prompt-only executor, the SDK client is also present (the
    current Claude Code session); on first step dispatch read the init
    message from the same `ClaudeSDKClient.query()` stream
  - [x] Extract `slash_commands` and store as `SessionCapabilities` on
    `ActionContext` — same shape as true CLI path
  - [x] If no init message arrives before the first step needing capabilities,
    populate with empty frozenset and log a WARNING
  - [x] `capabilities` must be non-None in both executors after probe;
    `None` only means "probe not yet run", which should not reach `CompactAction`

- [x] **Tests for capability probe — true CLI** [dropped]
  - [x] Mock `ClaudeSDKClient` to emit a synthetic init message with
    `slash_commands: ["/compact", "/cost"]`
  - [x] Assert resulting `ActionContext.capabilities.slash_commands` equals
    `frozenset({"/compact", "/cost"})`
  - [x] Assert probe fires exactly once even if multiple steps run
  - [x] Assert empty frozenset (not None) when init message has no slash_commands

- [x] **Tests for capability probe — prompt-only** [dropped]
  - [x] Same assertions as true CLI; confirm `capabilities` is populated
    before the first step executes in the prompt-only executor

- [x] **Commit: capability discovery** [dropped]
  - [x] `git add` models.py, executor change, tests → commit
    `feat: add SessionCapabilities and SDK init probe for slash command discovery`

---

### T4 — Investigation: `/model` in `slash_commands` [dropped]

- [x] **Run capability probe in each environment; record results** [dropped — design simplification]
  - [x] Add a temporary `--print-capabilities` debug flag to `sq run` (or
    author a minimal `noop.yaml` pipeline with a debug step) that prints
    `context.capabilities.slash_commands` after the probe
  - [x] Run in true CLI (`sq run`), Claude Code CLI, IDE extension
  - [x] Record which commands appear in `slash_commands` in each environment
  - [x] Write findings as a table in the slice DEVLOG
  - [x] Determine: is `/model` present? If yes, note it for T8; if no,
    confirm existing "suggested model" printout path stays unchanged
  - [x] This task produces documentation only — no code change required
    unless `/model` is confirmed dispatchable (addressed in T8)

---

### T5 — `CompactAction`: true-CLI branch

- [x] **Create `src/squadron/pipeline/actions/compact.py`**
  - [x] Class `CompactAction` implementing the `Action` protocol
  - [x] `action_type` property returns `ActionType.COMPACT`
  - [x] `validate()`: accept optional `instructions: str` field; no required
    fields
  - [x] `execute()`: if `context.sdk_session is not None`, delegate to
    `context.sdk_session.compact(instructions=...)` — this is the existing
    rotate flow (capture summary → disconnect → new client → restore)
  - [x] Pass `instructions` from `context.params` to `sdk_session.compact()`
    if provided (check existing `compact()` signature for param name)
  - [x] Return `ActionResult(success=True, action_type=..., outputs={})`
  - [x] Do NOT delegate to `SummaryAction` — own the flow directly

- [x] **Tests for true-CLI branch**
  - [x] Mock `SDKExecutionSession.compact()` as an async mock
  - [x] Assert it is called when `context.sdk_session` is not None
  - [x] Assert `instructions` param is forwarded when provided in params
  - [x] Assert `ActionResult.success is True`

---

### T6 — `CompactAction`: prompt-only branch

- [x] **Add prompt-only dispatch to `CompactAction`**
  - [x] When `context.sdk_session is None`:
    - If `context.capabilities` is not None and
      `"/compact" in context.capabilities.slash_commands`:
      - Dispatch `"/compact"` (plus `instructions` if provided) via
        `ClaudeSDKClient.query()` on the current client
      - Await `SystemMessage(subtype="compact_boundary")` before returning
      - Extract `pre_tokens` and `trigger` from
        `message.data["compact_metadata"]`; log at DEBUG
      - Include `pre_tokens`, `trigger`, and current timestamp in
        `ActionResult.outputs` so the pipeline executor writes them to
        run state alongside other per-step metadata
      - Return `ActionResult(success=True, outputs={"pre_tokens": ..., "trigger": ..., "compacted_at": ...})`
    - Else (capabilities None or `/compact` not listed):
      - Log an INFO message: "compact not available in this environment"
      - Return `ActionResult(success=True, outputs={}, note="compact not available")`
  - [x] `compact_boundary` await must NOT return until the message arrives;
    if it never arrives, raise `TimeoutError` after a reasonable bound
    (configurable; default 120s)

- [x] **Tests for prompt-only branch — `/compact` available**
  - [x] Provide `context.sdk_session = None`, capabilities with `/compact`
  - [x] Mock `query()` to emit a synthetic `compact_boundary` SystemMessage
    with `pre_tokens=5000`, `trigger="manual"`
  - [x] Assert `ActionResult.outputs` contains `pre_tokens` and `trigger`
  - [x] Assert `query()` was called with a prompt containing `/compact`

- [x] **Tests for prompt-only branch — `/compact` not available**
  - [x] Provide `context.sdk_session = None`, capabilities without `/compact`
  - [x] Assert action returns `success=True` with informational note
  - [x] Assert `query()` is NOT called

- [x] **Tests for prompt-only branch — capabilities is None**
  - [x] Provide `context.sdk_session = None`, `capabilities = None`
  - [x] Assert action returns `success=True` with informational note

- [x] **Test: compact_boundary await blocks until message received**
  - [x] Mock `query()` to delay the `compact_boundary` message by 2 iterations
  - [x] Assert action does not return until boundary arrives

- [x] **Test: compact_boundary timeout raises TimeoutError**
  - [x] Mock `query()` to never emit a `compact_boundary` message
  - [x] Set a short timeout (e.g. 1s) for the test
  - [x] Assert `TimeoutError` (or equivalent) is raised within the bound

- [x] **Commit: CompactAction**
  - [x] `git add` actions/compact.py, tests → commit
    `feat: add CompactAction with true-CLI rotate and prompt-only /compact dispatch`

---

### T7 — Register `ActionType.COMPACT` and wire `CompactStepType`

- [x] **Add `COMPACT = "compact"` to `ActionType` enum**
  - [x] Edit `src/squadron/pipeline/actions/__init__.py`
  - [x] Add `COMPACT = "compact"` to `ActionType` StrEnum

- [x] **Import and register `CompactAction`**
  - [x] In `src/squadron/pipeline/actions/compact.py`, call
    `register_action(ActionType.COMPACT, CompactAction())` at module bottom
  - [x] Ensure the module is imported by the actions package init (or loader)
    so registration fires at startup — mirror how other actions are registered

- [x] **Update `CompactStepType.expand()`**
  - [x] Edit `src/squadron/pipeline/steps/compact.py`
  - [x] Change `expand()` to return `[("compact", action_config)]` instead of
    `[("summary", action_config)]`
  - [x] Remove `emit` key from `action_config` (no longer needed)
  - [x] Keep `model` and `instructions` passthrough; remove `keep` and
    `summarize` (those were summary-action params, not compact-action params)
  - [x] Update `validate()` to match new config surface: only `model` (str,
    optional) and `instructions` (str, optional)

- [x] **Tests for registration and step expansion**
  - [x] Assert `get_action("compact")` returns a `CompactAction` instance
  - [x] Assert `CompactStepType().expand(config)` returns
    `[("compact", {...})]`, not `[("summary", ...)]`
  - [x] Assert YAML pipeline with `compact:` step loads and validates without
    error (use existing loader tests or add one)

- [x] **Commit: registry and step wiring**
  - [x] `git add` __init__.py, compact.py (step + action), tests → commit
    `feat: register CompactAction and update CompactStepType to emit compact action`

---

### T8 — `summarize` action: `restore: true` mode

- [x] **Audit existing `SummaryAction` for restore support**
  - [x] Read `src/squadron/pipeline/actions/summary.py` fully
  - [x] Determine if `restore: true` already exists — the slice design says
    it does not; confirm
  - [x] If absent: add `restore: bool = False` param handling

- [x] **Add `restore: true` mode to `SummaryAction`**
  - [x] When `context.params.get("restore") is True`:
    - Read the most recently saved summary from pipeline run state (file
      destination), or from `context.prior_outputs` if available
    - Inject summary content into the current session as a user message
      (for SDK sessions: dispatch via `sdk_session`; for prompt-only: render
      as a framed block for the model to consume)
    - Return `ActionResult(success=True, ...)`
  - [x] In this mode, skip the summary-capture steps entirely
  - [x] Add `restore` to `validate()`: must be bool if present
  - [x] Success: a `summarize: restore: true` step in a pipeline YAML works
    without error

- [x] **Tests for restore mode**
  - [x] Test `restore: true` with a mock prior summary in run state — assert
    summary content is injected, not re-generated
  - [x] Test `restore: true` with no prior summary available — assert a clear
    error or warning (no silent failure)
  - [x] Test normal summarize still works unaffected (regression)

- [x] **`/model` follow-up (from T4)** [skipped — T4 dropped]
  - [x] If `/model` was found in `slash_commands`: add a model-switch dispatch
    branch to `CompactAction` for the prompt-only path, gated on
    `"/model" in context.capabilities.slash_commands` [skipped — T4 dropped]
  - [x] If `/model` was NOT found: no code change; update authoring guide note [skipped — T4 dropped]

- [x] **Commit: summarize restore mode**
  - [x] `git add` summary.py, tests → commit
    `feat: add restore mode to SummaryAction for summary re-injection`

---

### T9 — Audit and migrate pipeline YAML files

- [x] **Audit `src/squadron/data/pipelines/*.yaml` for compact usage**
  - [x] Identify any pipeline that uses `compact:` and relies on the implicit
    summary artifact (i.e., uses the summary output from compact rather than
    a preceding explicit `summarize:` step)
  - [x] For each affected pipeline: add an explicit `summarize:` step before
    the `compact:` step; verify the pipeline still works end-to-end
  - [x] Document findings in the DEVLOG (even if no files needed changes)

- [x] **Commit: pipeline YAML migration**
  - [x] `git add` any updated YAML files → commit
    `fix: update pipelines to use explicit summarize before compact`
    (skip commit if no changes required)

---

### T10 — Integration test: compose pattern

- [x] **Author `src/squadron/data/pipelines/test-compact-compose.yaml`**
  - [x] Steps: `dispatch` → `summarize (emit: [file])` → `compact` →
    `summarize (restore: true)` → `dispatch`
  - [x] Use a simple prompt for each dispatch step

- [x] **Integration test: prompt-only compose**
  - [x] Add an integration test that runs `test-compact-compose.yaml` through
    the prompt-only executor with a mocked SDK client
  - [x] Mock: emit `compact_boundary` after the compact step
  - [x] Assert all five steps complete in order; assert final dispatch runs
    with the restored summary in context

- [x] **Integration test: true CLI compose**
  - [x] Add an integration test that runs `test-compact-compose.yaml` through
    the true CLI executor with a mocked `SDKExecutionSession`
  - [x] Mock: `sdk_session.compact()` succeeds; `summarize` writes a file;
    `summarize restore:true` injects the file content
  - [x] Assert all five steps complete in order in the true CLI path
  - [x] This satisfies success criterion #6 ("runs to completion in at least
    one prompt-only environment **and** in true CLI")

- [x] **Regression test: no dead slash-command text**
  - [x] Assert that a `compact:` step in a prompt-only pipeline does NOT
    produce output containing the literal string `/compact` as plain text
    (guards against pre-166 regression)

- [x] **Commit: compose test pipeline and integration tests**
  - [x] `git add` test pipeline, integration tests → commit
    `test: add compact-compose integration test for prompt-only and true-CLI paths`

---

### T11 — Documentation updates

- [x] **Update execution-environment matrix**
  - [x] Find the pipeline authoring guide or execution-environment note
    (currently in memory as `project_pipeline_execution_environments.md`
    and in any authoring docs)
  - [x] Update `compact` row: was "user-only in IDE/CLI" → now "automatable
    in all environments via `/compact` probe"
  - [x] Add note: `/clear` remains non-automatable; `compact` is the
    portable equivalent

- [x] **Add compact reliability note to authoring guide**
  - [x] Document that `/compact` may not tightly follow `instructions` in
    prompt-only mode; recommend `summarize` → `compact` → `restore` pattern
    for artifact-preservation use cases

- [x] **Add migration note**
  - [x] Document that `compact:` no longer implicitly captures a summary;
    authors who relied on this must add an explicit `summarize:` step before
    `compact:`

- [x] **Commit: documentation**
  - [x] `git add` updated docs → commit `docs: update compact/summarize authoring
    guide for slice 169 behavior`

---

### T12 — Final validation

- [x] **Full test suite**
  - [x] `uv run pytest -q` — all tests pass (1665 tests)
  - [x] `uv run pyright` — 0 errors
  - [x] `uv run ruff check src/` — 0 errors
  - [x] `uv run ruff format src/` — no changes

- [x] **Verify true-CLI regression**
  - [x] Run an existing compact-using pipeline end-to-end via `sq run`
  - [x] Confirm second dispatch runs in a fresh SDK session with summary
    seeded (behavioral parity with pre-169 main)

- [x] **Verify capability probe recorded in DEVLOG**
  - [x] DEVLOG contains the `slash_commands` table from T4 (skipped — T4 dropped)

- [x] **Final commit and DEVLOG**
  - [x] Write DEVLOG entry (session state summary per `prompt.ai-project.system.md`)
  - [x] `git add` all remaining changes → commit
    `feat: slice 169 complete — compact action SDK capability dispatch`
