---
docType: review
layer: project
reviewType: tasks
slice: usage-and-cost-tracking
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261014
dateUpdated: 20261014
reviewedSha: e87fe4e5e121d4de58e41b697cf0272673e7821f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 46.8
runId: run-20261015-p5-e75c92b8
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 15 changes return types without fixing existing mocks"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:151-166"
  - id: F002
    severity: concern
    category: consistency
    summary: "Task 17 and Task 19 contradict each other on module state"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:178, 198"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Failure-table signals and criterion 4 are not fully asserted by tests"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:159-166, 203-209"
  - id: F004
    severity: concern
    category: correctness
    summary: "Tasks 19 and 24 call `.to_dict()` on a value that may be `None`"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:172-176, 195, 228"
  - id: F005
    severity: concern
    category: scope
    summary: "`stats/usage_report.py` will exceed the project's file-size guideline"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:247-269"
  - id: F006
    severity: concern
    category: process
    summary: "Task 36 closes issues before code review and integration"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:314-317"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Task granularity is slightly heavy for the slice"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:32-36, 64-67, 223-230"
  - id: F008
    severity: note
    category: prompt-hygiene
    summary: "Task 8 pairs a retrieval step with example values"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:98"
  - id: F009
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and sequencing"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md"
---

# Review: tasks — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 15 changes return types without fixing existing mocks

Task 15 makes `dispatch`, `capture_summary` and `compact` return `SessionReply` instead of `str`. It changes four callers to read `.text`. Task 16 then requires `pytest tests/pipeline -q` to pass. Existing action and session tests that stub these methods to return a `str` will break, and no step updates them. Add an explicit step to Task 16, or a new sub-item in Task 15, to migrate the existing fakes and mocks to `SessionReply`, so the test run is expected to be green.

### [CONCERN] Task 17 and Task 19 contradict each other on module state

Task 17 says `usage_capture` "holds no state beyond `warned`". The design's `CancelledError` row also relies on it holding no state. Task 19 then adds a module-level once-per-process flag in `usage_capture.py` for the D7 DEBUG line. A mutable module global also needs a reset hook for tests, and no task provides one. Reconcile the two. Either carry the flag on `UsageCapture` (once per run is acceptable for a DEBUG line, if the PM agrees), or amend Task 17 and add a test reset.

### [CONCERN] Failure-table signals and criterion 4 are not fully asserted by tests

The design requires every failure-table row to have a test asserting its signal. Several have none:
- **D7 DEBUG log.** The "once per process" log for an SDK session with alias effort is never asserted. Task 20 only checks that `effort` is `None`.
- **Session `usage is None` WARNING.** The "once per `dispatch()`" warning that Task 15 implements has no test in Task 16. Task 12 covers only the agent path.
- **Criterion 4.** `duration_seconds` on failure and on stall is only unit-tested through the patched `monotonic` in Task 18. Task 20 does not assert that the failed and stalled dispatch results carry a duration.

Add these assertions to Tasks 16 and 20.

### [CONCERN] Tasks 19 and 24 call `.to_dict()` on a value that may be `None`

Task 17 says each `record_*` method returns `None` when nothing was reported. Task 19 writes `metadata[USAGE_KEY] = record.to_dict()`, and Task 24 chains `record_from_review(...).to_dict()`. For a provider that reports nothing, the chain raises `AttributeError` inside the action. Specify that the actions write the key only when a record is returned. Better, make a single `usage_capture` helper own that guard so it isn't repeated in four actions. Task 24 also does not say how a review that fails with telemetry reaches the "failed actions record usage" requirement (criterion 2, D5). State which path covers it.

### [CONCERN] `stats/usage_report.py` will exceed the project's file-size guideline

Task 27 gives `usage_report.py` a "~300 lines" success bound. Task 29 then adds the reviews report, with its own row types, frontmatter parsing and skip and exclude counters, to the same file. The CLAUDE.md guideline is about 300 lines. Put the reviews report in its own module (for example `stats/reviews_report.py`), or relax the Task 27 bound. The shared totals logic should be a small helper used by both, so it isn't duplicated.

### [CONCERN] Task 36 closes issues before code review and integration

Task 36 closes #172, #36, #154, #151 and #158 at the end of Phase 6. Under the project's git rules, review and merge happen later, in Phase 7. Closing the issues now is outward-facing and hard to reverse, and it asserts completion before the slice has passed review. Either move it to the Phase 7 closure, or change it to "prepare comments and ask the PM before posting or closing".

### [CONCERN] Task granularity is slightly heavy for the slice

The checklist has 36 tasks. Some could be merged without losing a checkpoint:
- **Tasks 1 and 5.** Task 1 (branch) and Task 5 (verify and commit) are standalone tasks with no deliverable of their own. Fold Task 1 into Task 2 and Task 5 into Task 4.
- **Tasks 23 and 24.** Compact and review wiring are each a few lines and are tested together in Task 25. Merge them into one "wire compact and review" task.

### [NOTE] Task 8 pairs a retrieval step with example values

The Task 8 success text lists example usage keys followed by "or whatever the CLI emitted". The fixture must come from the real CLI output. Reword it to say "the keys the CLI actually emitted", and to stop and report if the capture fails or returns no `usage` object. That avoids the hallucination-trap pattern from CLAUDE.md. The task also spends real tokens on a live `claude` call, which is fine but worth stating.

### [PASS] Success-criteria coverage and sequencing

Each criterion maps to tasks:
- **Criterion 1:** Tasks 4, 11, 13, 14.
- **Criterion 2:** Tasks 17-25.
- **Criterion 3:** Tasks 15, 16.
- **Criterion 4:** Tasks 17, 19, 20.
- **Criterion 5:** Tasks 6, 7.
- **Criterion 6:** Tasks 19, 21.
- **Criterion 7:** Tasks 19-22.
- **Criterion 8:** Tasks 27-32.
- **Criterion 9:** Tasks 26, 28, 32.
- **Criterion 10:** Task 33.

Dependencies run forward only, with no cycles. `resolve_cost` (Task 6) exists before its callers in Tasks 13 and 17. No task writes a merge. No NFR is restated, so no load test or CI gating task is needed. The walkthrough in Task 35 covers the slice design's verification steps. I did not check the file paths and line numbers cited in the tasks against the source tree.

### Run Digest

- Response length: 6585 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 46.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
