---
docType: review
layer: project
reviewType: tasks
slice: isolated-file-in-file-out-dispatch-steps
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261102
dateUpdated: 20261102
reviewedSha: a371dfc2351812c0ff092bd09a5eaa604c39b93c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 103475
cachedTokens: 8831
cacheWriteTokens: 94640
completionTokens: 4726
durationSeconds: 41.0
costUsd: 0.427482
costBasis: provider
runId: run-20261102-p5-96163899
squadronVersion: 0.24.13
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage and sequencing"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:46-183"
  - id: F002
    severity: concern
    category: task-scope
    summary: "T15 is oversized and its success check contradicts its own steps"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:144-150"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Output-write failure path has no specified error type or handling"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:138"
  - id: F004
    severity: concern
    category: commit-placement
    summary: "Commit marker at the end mislabels code as `docs:`"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:166-183"
  - id: F005
    severity: concern
    category: proportionality
    summary: "T16 duplicates unit-test coverage and is heavier than the criteria need"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:152-160"
  - id: F006
    severity: concern
    category: test-coverage
    summary: "Criterion 6's \"including on resume\" is only partly tested"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:157-158"
  - id: F007
    severity: note
    category: design-consistency
    summary: "`ReplyFormat` placed in a different module than the design's component table"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:103"
  - id: F008
    severity: note
    category: clarity
    summary: "T19 contains an unexplained, unneeded clause"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:177"
  - id: F009
    severity: note
    category: task-scope
    summary: "Part A, T1 touches every step module"
    location: "project-documents/user/tasks/949-tasks.isolated-file-in-file-out-dispatch-steps.md:48-54"
---

# Review: tasks — slice 949

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage and sequencing

Each criterion maps to at least one implementation task and a test:
- **Criteria 1, 2 and 4:** T13, T14, T16.
- **Criterion 3:** T12 (including `NaN`) and T16.
- **Criterion 5:** T5–T7.
- **Criterion 6:** T10, T11, T14, T16.
- **Criteria 7 and 8:** T2–T4.
- **Criterion 9:** T17.

The A→B→C→D→E order follows the design's Development Approach and has no circular dependencies. Test tasks follow their implementation tasks (T5/T6, T8/T9, T10/T11). Part D's tests sit in T12–T14 and T16, with T15 in between.

### [CONCERN] T15 is oversized and its success check contradicts its own steps

T15 is the highest-risk task, and it bundles five jobs:
- Restructure `_dispatch` and remove prompt resolution from both existing paths.
- Add the `DispatchInputError` catch in `execute`.
- Add JSON extraction and failure handling.
- Choose the content for `reply_file` and `delivered_prompt_file`.
- Add the file writes.

It also states "`dispatch.py` gains call sites only (no new logic)", but its own steps add new branching: the `reply_format: json` failure, the choice of what `reply_file` receives, and error handling. A junior reading that success check can't tell what is allowed. It also touches the ~1000-line file the design wants kept small.

Split it in two: (a) the restructure, with the prompt resolved once, the `DispatchInputError` catch, and the existing tests passing unchanged; (b) the reply contract (JSON failure, `reply_json`, the file writes). Move that logic into a `dispatch_io` helper so the "call sites only" check holds. Then reword the success check.

### [CONCERN] Output-write failure path has no specified error type or handling

T14 says `write_step_files` "raise[s] an error naming the path" on an `OSError`, but never says which type. T15 only says `execute` catches `DispatchInputError`, and describes that as the failure "before any model call". The design's Failure Surface says an output-write error happens after dispatch, so the step must fail rather than propagate to the generic `logger.exception` path. As written, it's unclear whether that failure becomes a failed `ActionResult` and which signal it emits. T16 item 6 says it asserts each failure row's signal. Name the exception type, say where it is caught, and state the log level. A single `DispatchInputError`-style type with a clear "output" case would do.

### [CONCERN] Commit marker at the end mislabels code as `docs:`

The last `**Commit**:` marker follows T17, T18 and T19 with the message `docs: document dispatch file keys, tool guard and validate --strict`. T17 is a code change: `_render_dispatch` rejects the new keys, with tests. Committing it under `docs:` misdescribes the work and breaks the semantic-commit rule. Either add a `feat:` marker after T17 (it is a working, tested point), or change the final marker to a combined `feat:` message. T19 is verification only and doesn't need to share a marker with docs.

### [CONCERN] T16 duplicates unit-test coverage and is heavier than the criteria need

Item 3 (injected `reply_file` failure leaves both files as they were) re-tests what T14 already covers at unit level. Item 6 re-asserts "each failure row of the design's API Contracts table", and most of those rows are already asserted in T13, T14 and T7. T16 should keep only what needs the full executor: the two-step happy path, the JSON-failure no-write case, `reply_from` on a failed or skipped step, and resume. Drop or narrow items 3 and 6 to the rows not tested elsewhere.

### [CONCERN] Criterion 6's "including on resume" is only partly tested

Success Criterion 6 requires that a named step with a failed or skipped result fails the reading step "including on resume". T16 item 4 covers failed or skipped in a live run, and item 5 covers only the happy-path resume (restored reply is read). No task tests a resumed run where the named step's restored result is failed or has no `response`. Add that case to item 5.

### [NOTE] `ReplyFormat` placed in a different module than the design's component table

The design's component table lists `ReplyFormat` under `dispatch_io.py`. T8 defines it in `steps/dispatch.py`, and T12's title is "`ReplyFormat` use". Putting it in `steps/dispatch.py` is sensible: the step module's `validate` needs it, and `steps` shouldn't import from `actions`. Record the deviation in the Context Summary decisions so a reviewer doesn't read it as a mistake.

### [NOTE] T19 contains an unexplained, unneeded clause

"If failures appear that are cf schema-drift in a worktree, say so rather than fixing them here" refers to something neither this task file nor the design explains. A junior can't act on it. Remove it, or replace it with the general rule (failures unrelated to the slice get an issue filed).

### [NOTE] Part A, T1 touches every step module

T1 edits roughly a dozen step modules and derives each `known_keys` set by reading that module. It's rated Effort 3, which is fair, and pyright plus the built-in strict check in T3 catch omissions. If the junior stalls, splitting off the non-dispatch step types would be the natural cut. No change required.

### Run Digest

- Response length: 6610 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 103475 / 8831 / 94640 / 4726 / not computed
- Duration: 41.0 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
