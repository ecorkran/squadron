---
docType: review
layer: project
reviewType: tasks
slice: pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 3652be1cca355ab957d4fcc013e960a1c06def04
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
squadronVersion: 0.15.1
findings:
  - id: F001
    severity: concern
    category: source-control
    summary: "Commits are batched per part, not per task"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#A6"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Suite is red between A3 and A6, and A6 bundles unrelated test rewrites"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#A3"
  - id: F003
    severity: concern
    category: task-scope
    summary: "B2 and A3 are oversized"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#B2"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "D13 failure-mode signals at the action level are untested"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D13"
  - id: F005
    severity: note
    category: design-conformance
    summary: "`sdk_settings_options` and `seed_context` signatures differ from the design's API contracts"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#D2"
  - id: F006
    severity: note
    category: completability
    summary: "Live-verification and code-review tasks depend on external resources or people"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#E1"
  - id: F007
    severity: note
    category: nfr-coverage
    summary: "No load-test or CI-gating task is needed"
    location: "unverified"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria traceability"
    location: "project-documents/user/slices/932-slice.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#Success Criteria"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/932-tasks.pipeline-sdk-session-control-seeding-without-a-turn-dispatch-that-waits-for-background-work-and-explicit-prompt-and-settings.md#Part D"
---

# Review: tasks — slice 932

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Commits are batched per part, not per task

The only commits are A6, B7, D8, C7 and E2, each at the end of a part. Part A has six implementation tasks (A1–A6) and one commit. Part D has eight tasks and one commit. The project rule in CLAUDE.md says "Git add and commit from project root at least once per task." Add a commit step to each implementation+test pair, for example `feat: add seeded options helper` after A1/A1-T. Keep the part-end full-suite commit as the closing checkpoint.

### [CONCERN] Suite is red between A3 and A6, and A6 bundles unrelated test rewrites

A3 changes `compact()` and `seed_context()` to stop calling `dispatch()`. The existing tests that assert seeding goes through `dispatch()` or `query` (`test_compact_integration.py`, `test_compact_compose_integration.py`, `test_dispatch_session.py`, `test_run_pipeline.py`) break at that point. They are only fixed in A6. A3-T, A4-T and A5-T run targeted files, so the breakage is invisible until A6, and the "test-with" pattern is violated for those files. Move each rewrite into the task that breaks it: compact and emit tests into A3-T, resume tests into A4-T. A6 then reduces to the full-suite run and commit.

### [CONCERN] B2 and A3 are oversized

B2 is Effort 3 and bundles:
- the constant
- the ledger class
- `_is_own_result`
- a restructure of the read loop while preserving the rate-limit retry
- the waited counter
- the stream-ended `ProviderError`

Its own success criterion asks for functions of about 50 lines. Split it into B2a (ledger, constant, own-result helper, with unit tests) and B2b (the loop restructure, stream-end error and metadata). A3 similarly mixes `_reconnect`, `compact()` rework, `seed_context`, `unusable_reason` and the `_require_usable` guard. Consider splitting the guard and `unusable_reason` into their own task.

### [CONCERN] D13 failure-mode signals at the action level are untested

D13 says that after a failed reconnect, compact, emit and restore report a failed step with the error. It also says that in an `each` batch with a continue policy, the remaining items are flagged with the "SDK session unusable" reason. A3-T tests only the session-level behavior: `ProviderError` on the next `dispatch`. No task asserts that the `compact`/`summary restore` actions surface a failed `ActionResult`. No task asserts that the batch flags the remaining items. The project's failure-mode rule requires a test asserting the observable signal. Add one action-level test and one `each`-batch test.

### [NOTE] `sdk_settings_options` and `seed_context` signatures differ from the design's API contracts

Task D2 adds a `base_env` parameter to `sdk_settings_options`. The design contract has none. A3 and A5 add a `source: SeedSource` parameter to `seed_context`, where the design contract has `seed_context(text)`. The task file lists `SeedSource` under "Names added" but not `base_env`. Both changes are reasonable. The design's API Contracts section should be updated at close-out (E2) so the two documents agree.

### [NOTE] Live-verification and code-review tasks depend on external resources or people

E1 needs real model calls and a scratch repo. E3 is gated on the Project Manager running `sq review code`. A junior AI cannot complete either alone. Both are legitimate gates and the SC wording ("passes or has an open issue linked") handles failure. Label E1 and E3 explicitly as PM-assisted preconditions, so they are not mistaken for autonomous checklist items.

### [NOTE] No load-test or CI-gating task is needed

The slice restates no throughput or latency NFR. The idle-timeout bound is a functional behavior covered by B4-T with a small timeout. The absence of a `tests/load/` task and a CI wiring task is correct.

### [PASS] Success-criteria traceability

The functional criteria all trace to tasks:
- No-turn seeding and restore framing: A1–A5.
- Background wait, injected-turn drop, idle timeout and stream-end error: B2–B4.
- Post-condition tail: B6.
- Preset+append and the session guard: C1–C2.
- Per-path settings: D2–D7.
- Auto-memory: D1 and D3–D5.
- Digest, JSON and metadata: C3–C6.

I found no scope creep. D1 (bool config coercion) is a necessary prerequisite for `pipeline.auto_memory`, and the task file flags it as found during breakdown.

### [PASS] Sequencing and test-with pattern

Dependencies flow forward with no cycles:
- A2 defers settings to D4.
- D4 exposes the session fields that C6 consumes.
- B3 defines `tail_text` before B6 uses it.
- D3 precedes D5 and D7.

Most implementation tasks have an immediately following `-T` task. The exceptions are D7, which is itself a test task, and the two tasks noted above.

### Run Digest

- Response length: 6655 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Response (20260928)

- **F001, fixed.** Each implementation+test pair now ends in its own `Commit:` step: 26 commits, one per pair, with D7 counted as its own. The part-end tasks (A6, B7, D8, C7) are now checkpoints that run the full suite. The cadence is stated in the Context Summary.
- **F002, fixed.** Each test rewrite now lives in the task that breaks it:
  - compact, emit-rotate, and session-dispatch rewrites in A3-T, whose SC runs all of `tests/pipeline`;
  - resume rewrites in A4-T, whose SC runs `tests/cli/commands` and `tests/pipeline`;
  - the `session.options` → `base_options` updates in A2-T.

  A6 is now only the full-suite checkpoint.
- **F003, fixed.**
  - A3 is split into A3 (`_reconnect`, `compact`, `seed_context`, `SeedSource`) and A3b (`unusable_reason` and `_require_usable`).
  - B2 is split into B2a (`WAITED_TASK_TYPES`, `_BackgroundLedger`, and `_is_own_result`, which are pure and unit-tested) and B2b (the loop restructure, the stream-end error, and `background_tasks_waited`).
- **F004, fixed.** A3b-T adds the action-level test (compact, emit rotate, and summary restore return a failed result on reconnect failure). It also adds the `each`-batch test: with a continue policy, the remaining items are FLAGGED with `SDK session unusable`, and `query` is never reached.
- **F005, fixed.** The Context Summary lists every name the tasks add beyond the design, including `base_env` and `source: SeedSource`. E2 now has an explicit step to update the design's API Contracts to match.
- **F006, fixed.** E1 is labeled PM-assisted and E3 PM-gated.
- **F007, no action.**
- Also fixed: B3's warning format had a double `…`, because `tail_text` adds its own.
