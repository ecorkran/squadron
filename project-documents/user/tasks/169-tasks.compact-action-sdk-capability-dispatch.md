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
dateUpdated: 20260422
status: not_started
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

- [ ] **Create implementation branch**
  - [ ] Verify on `main`, working tree clean
  - [ ] `git checkout -b 169-slice.compact-action-sdk-capability-dispatch`

---

### T2 — Capability discovery: `SessionCapabilities` dataclass

- [ ] **Add `SessionCapabilities` to `src/squadron/pipeline/models.py`**
  - [ ] Add dataclass `SessionCapabilities` with field
    `slash_commands: frozenset[str]`
  - [ ] Add optional field `capabilities: SessionCapabilities | None = None`
    to `ActionContext`
  - [ ] `SessionCapabilities` is a plain frozen dataclass — no external deps
  - [ ] Success: `ActionContext(... capabilities=None)` type-checks clean;
    `SessionCapabilities(slash_commands=frozenset({"/compact"}))` instantiates

- [ ] **Tests for `SessionCapabilities`**
  - [ ] Add unit tests in `tests/pipeline/test_models.py` (or nearest models
    test file): verify `ActionContext.capabilities` defaults to `None`;
    verify `SessionCapabilities.slash_commands` is `frozenset`
  - [ ] pyright clean on models.py

---

### T3 — Capability probe in the SDK executor

- [ ] **Probe SDK init message in the pipeline executor**
  - [ ] Locate where `SDKExecutionSession` / `ClaudeSDKClient` is initialized
    in the executor (see `src/squadron/cli/commands/run.py` and
    `src/squadron/pipeline/executor.py` or equivalent)
  - [ ] After session start, read the first `SystemMessage(subtype="init")`
    and extract `data.get("slash_commands", [])` into a `frozenset`
  - [ ] Store as `SessionCapabilities` on the `ActionContext` passed to all
    subsequent steps; probe fires once per session, result is cached
  - [ ] If init message not received before first step, populate with empty
    frozenset (do not block indefinitely — log a WARNING)
  - [ ] For prompt-only executor (no persistent session), capabilities remain
    `None`; `CompactAction` will handle the None case explicitly

- [ ] **Tests for capability probe**
  - [ ] Mock `ClaudeSDKClient` to emit a synthetic init message with
    `slash_commands: ["/compact", "/cost"]`
  - [ ] Assert resulting `ActionContext.capabilities.slash_commands` equals
    `frozenset({"/compact", "/cost"})`
  - [ ] Assert probe fires exactly once even if multiple steps run
  - [ ] Assert empty frozenset on missing init message

- [ ] **Commit: capability discovery**
  - [ ] `git add` models.py, executor change, tests → commit
    `feat: add SessionCapabilities and SDK init probe for slash command discovery`

---

### T4 — Investigation: `/model` in `slash_commands`

- [ ] **Run capability probe in each environment; record results**
  - [ ] Add a temporary `--print-capabilities` debug flag to `sq run` (or
    author a minimal `noop.yaml` pipeline with a debug step) that prints
    `context.capabilities.slash_commands` after the probe
  - [ ] Run in true CLI (`sq run`), Claude Code CLI, IDE extension
  - [ ] Record which commands appear in `slash_commands` in each environment
  - [ ] Write findings as a table in the slice DEVLOG
  - [ ] Determine: is `/model` present? If yes, note it for T8; if no,
    confirm existing "suggested model" printout path stays unchanged
  - [ ] This task produces documentation only — no code change required
    unless `/model` is confirmed dispatchable (addressed in T8)

---

### T5 — `CompactAction`: true-CLI branch

- [ ] **Create `src/squadron/pipeline/actions/compact.py`**
  - [ ] Class `CompactAction` implementing the `Action` protocol
  - [ ] `action_type` property returns `ActionType.COMPACT`
  - [ ] `validate()`: accept optional `instructions: str` field; no required
    fields
  - [ ] `execute()`: if `context.sdk_session is not None`, delegate to
    `context.sdk_session.compact(instructions=...)` — this is the existing
    rotate flow (capture summary → disconnect → new client → restore)
  - [ ] Pass `instructions` from `context.params` to `sdk_session.compact()`
    if provided (check existing `compact()` signature for param name)
  - [ ] Return `ActionResult(success=True, action_type=..., outputs={})`
  - [ ] Do NOT delegate to `SummaryAction` — own the flow directly

- [ ] **Tests for true-CLI branch**
  - [ ] Mock `SDKExecutionSession.compact()` as an async mock
  - [ ] Assert it is called when `context.sdk_session` is not None
  - [ ] Assert `instructions` param is forwarded when provided in params
  - [ ] Assert `ActionResult.success is True`

---

### T6 — `CompactAction`: prompt-only branch

- [ ] **Add prompt-only dispatch to `CompactAction`**
  - [ ] When `context.sdk_session is None`:
    - If `context.capabilities` is not None and
      `"/compact" in context.capabilities.slash_commands`:
      - Dispatch `"/compact"` (plus `instructions` if provided) via
        `ClaudeSDKClient.query()` on the current client
      - Await `SystemMessage(subtype="compact_boundary")` before returning
      - Extract and log `pre_tokens` and `trigger` from
        `message.data["compact_metadata"]`
      - Return `ActionResult(success=True, outputs={"pre_tokens": ..., "trigger": ...})`
    - Else (capabilities None or `/compact` not listed):
      - Log an INFO message: "compact not available in this environment"
      - Return `ActionResult(success=True, outputs={}, note="compact not available")`
  - [ ] `compact_boundary` await must NOT return until the message arrives;
    if it never arrives, raise `TimeoutError` after a reasonable bound
    (configurable; default 120s)

- [ ] **Tests for prompt-only branch — `/compact` available**
  - [ ] Provide `context.sdk_session = None`, capabilities with `/compact`
  - [ ] Mock `query()` to emit a synthetic `compact_boundary` SystemMessage
    with `pre_tokens=5000`, `trigger="manual"`
  - [ ] Assert `ActionResult.outputs` contains `pre_tokens` and `trigger`
  - [ ] Assert `query()` was called with a prompt containing `/compact`

- [ ] **Tests for prompt-only branch — `/compact` not available**
  - [ ] Provide `context.sdk_session = None`, capabilities without `/compact`
  - [ ] Assert action returns `success=True` with informational note
  - [ ] Assert `query()` is NOT called

- [ ] **Tests for prompt-only branch — capabilities is None**
  - [ ] Provide `context.sdk_session = None`, `capabilities = None`
  - [ ] Assert action returns `success=True` with informational note

- [ ] **Test: compact_boundary await blocks until message received**
  - [ ] Mock `query()` to delay the `compact_boundary` message by 2 iterations
  - [ ] Assert action does not return until boundary arrives

- [ ] **Commit: CompactAction**
  - [ ] `git add` actions/compact.py, tests → commit
    `feat: add CompactAction with true-CLI rotate and prompt-only /compact dispatch`

---

### T7 — Register `ActionType.COMPACT` and wire `CompactStepType`

- [ ] **Add `COMPACT = "compact"` to `ActionType` enum**
  - [ ] Edit `src/squadron/pipeline/actions/__init__.py`
  - [ ] Add `COMPACT = "compact"` to `ActionType` StrEnum

- [ ] **Import and register `CompactAction`**
  - [ ] In `src/squadron/pipeline/actions/compact.py`, call
    `register_action(ActionType.COMPACT, CompactAction())` at module bottom
  - [ ] Ensure the module is imported by the actions package init (or loader)
    so registration fires at startup — mirror how other actions are registered

- [ ] **Update `CompactStepType.expand()`**
  - [ ] Edit `src/squadron/pipeline/steps/compact.py`
  - [ ] Change `expand()` to return `[("compact", action_config)]` instead of
    `[("summary", action_config)]`
  - [ ] Remove `emit` key from `action_config` (no longer needed)
  - [ ] Keep `model` and `instructions` passthrough; remove `keep` and
    `summarize` (those were summary-action params, not compact-action params)
  - [ ] Update `validate()` to match new config surface: only `model` (str,
    optional) and `instructions` (str, optional)

- [ ] **Tests for registration and step expansion**
  - [ ] Assert `get_action("compact")` returns a `CompactAction` instance
  - [ ] Assert `CompactStepType().expand(config)` returns
    `[("compact", {...})]`, not `[("summary", ...)]`
  - [ ] Assert YAML pipeline with `compact:` step loads and validates without
    error (use existing loader tests or add one)

- [ ] **Commit: registry and step wiring**
  - [ ] `git add` __init__.py, compact.py (step + action), tests → commit
    `feat: register CompactAction and update CompactStepType to emit compact action`

---

### T8 — `summarize` action: `restore: true` mode

- [ ] **Audit existing `SummaryAction` for restore support**
  - [ ] Read `src/squadron/pipeline/actions/summary.py` fully
  - [ ] Determine if `restore: true` already exists — the slice design says
    it does not; confirm
  - [ ] If absent: add `restore: bool = False` param handling

- [ ] **Add `restore: true` mode to `SummaryAction`**
  - [ ] When `context.params.get("restore") is True`:
    - Read the most recently saved summary from pipeline run state (file
      destination), or from `context.prior_outputs` if available
    - Inject summary content into the current session as a user message
      (for SDK sessions: dispatch via `sdk_session`; for prompt-only: render
      as a framed block for the model to consume)
    - Return `ActionResult(success=True, ...)`
  - [ ] In this mode, skip the summary-capture steps entirely
  - [ ] Add `restore` to `validate()`: must be bool if present
  - [ ] Success: a `summarize: restore: true` step in a pipeline YAML works
    without error

- [ ] **Tests for restore mode**
  - [ ] Test `restore: true` with a mock prior summary in run state — assert
    summary content is injected, not re-generated
  - [ ] Test `restore: true` with no prior summary available — assert a clear
    error or warning (no silent failure)
  - [ ] Test normal summarize still works unaffected (regression)

- [ ] **`/model` follow-up (from T4)**
  - [ ] If `/model` was found in `slash_commands`: add a model-switch dispatch
    branch to `CompactAction` for the prompt-only path, gated on
    `"/model" in context.capabilities.slash_commands`
  - [ ] If `/model` was NOT found: no code change; update authoring guide note

- [ ] **Commit: summarize restore mode**
  - [ ] `git add` summary.py, tests → commit
    `feat: add restore mode to SummaryAction for summary re-injection`

---

### T9 — Audit and migrate pipeline YAML files

- [ ] **Audit `src/squadron/data/pipelines/*.yaml` for compact usage**
  - [ ] Identify any pipeline that uses `compact:` and relies on the implicit
    summary artifact (i.e., uses the summary output from compact rather than
    a preceding explicit `summarize:` step)
  - [ ] For each affected pipeline: add an explicit `summarize:` step before
    the `compact:` step; verify the pipeline still works end-to-end
  - [ ] Document findings in the DEVLOG (even if no files needed changes)

- [ ] **Commit: pipeline YAML migration**
  - [ ] `git add` any updated YAML files → commit
    `fix: update pipelines to use explicit summarize before compact`
    (skip commit if no changes required)

---

### T10 — Integration test: compose pattern

- [ ] **Author `src/squadron/data/pipelines/test-compact-compose.yaml`**
  - [ ] Steps: `dispatch` → `summarize (emit: [file])` → `compact` →
    `summarize (restore: true)` → `dispatch`
  - [ ] Use a simple prompt for each dispatch step

- [ ] **Integration test: prompt-only compose**
  - [ ] Add an integration test that runs `test-compact-compose.yaml` through
    the prompt-only executor with a mocked SDK client
  - [ ] Mock: emit `compact_boundary` after the compact step
  - [ ] Assert all five steps complete in order; assert final dispatch runs
    with the restored summary in context

- [ ] **Regression test: no dead slash-command text**
  - [ ] Assert that a `compact:` step in a prompt-only pipeline does NOT
    produce output containing the literal string `/compact` as plain text
    (guards against pre-166 regression)

- [ ] **Commit: compose test pipeline and integration tests**
  - [ ] `git add` test pipeline, integration tests → commit
    `test: add compact-compose integration test for prompt-only and true-CLI paths`

---

### T11 — Documentation updates

- [ ] **Update execution-environment matrix**
  - [ ] Find the pipeline authoring guide or execution-environment note
    (currently in memory as `project_pipeline_execution_environments.md`
    and in any authoring docs)
  - [ ] Update `compact` row: was "user-only in IDE/CLI" → now "automatable
    in all environments via `/compact` probe"
  - [ ] Add note: `/clear` remains non-automatable; `compact` is the
    portable equivalent

- [ ] **Add compact reliability note to authoring guide**
  - [ ] Document that `/compact` may not tightly follow `instructions` in
    prompt-only mode; recommend `summarize` → `compact` → `restore` pattern
    for artifact-preservation use cases

- [ ] **Add migration note**
  - [ ] Document that `compact:` no longer implicitly captures a summary;
    authors who relied on this must add an explicit `summarize:` step before
    `compact:`

- [ ] **Commit: documentation**
  - [ ] `git add` updated docs → commit `docs: update compact/summarize authoring
    guide for slice 193 behavior`

---

### T12 — Final validation

- [ ] **Full test suite**
  - [ ] `uv run pytest -q` — all tests pass
  - [ ] `uv run pyright` — 0 errors
  - [ ] `uv run ruff check src/` — 0 errors
  - [ ] `uv run ruff format src/` — no changes

- [ ] **Verify true-CLI regression**
  - [ ] Run an existing compact-using pipeline end-to-end via `sq run`
  - [ ] Confirm second dispatch runs in a fresh SDK session with summary
    seeded (behavioral parity with pre-193 main)

- [ ] **Verify capability probe recorded in DEVLOG**
  - [ ] DEVLOG contains the `slash_commands` table from T4

- [ ] **Final commit and DEVLOG**
  - [ ] Write DEVLOG entry (session state summary per `prompt.ai-project.system.md`)
  - [ ] `git add` all remaining changes → commit
    `feat: slice 169 complete — compact action SDK capability dispatch`
