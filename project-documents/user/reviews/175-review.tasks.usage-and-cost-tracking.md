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
reviewedSha: 73ca0db651df0c246a1a5c5012ed35ae90ecb42c
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 49.1
runId: run-20261015-p5-e75c92b8
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: completeness
    summary: "Duration (D6, criterion 4) is unspecified for review, compact, and the failed-review path"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:166-178"
  - id: F002
    severity: concern
    category: completeness
    summary: "Task 26 does not say how frontmatter rows feed `usage_totals`"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:251,260-267"
  - id: F003
    severity: concern
    category: testing
    summary: "Executor wiring for `UsageCapture` is untested"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:177,184"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 13 mixes too many concerns"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:145-152"
  - id: F005
    severity: note
    category: nfr
    summary: "No load-test task is required"
    location: "unverified"
  - id: F006
    severity: note
    category: process
    summary: "Release bump is not tasked"
    location: "project-documents/user/slices/175-slice.usage-and-cost-tracking.md:369"
  - id: F007
    severity: note
    category: verification
    summary: "Walkthrough step 7 cannot be run by an agent"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md:308"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success-criteria coverage and sequencing"
    location: "project-documents/user/tasks/175-tasks.usage-and-cost-tracking.md"
---

# Review: tasks — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Duration (D6, criterion 4) is unspecified for review, compact, and the failed-review path

Task 15 says each builder "computes `duration_seconds = time.monotonic() - started`". But `record_from_review(result, resolved, effort_sent)` (line 170) takes no `started`. Nothing says whether it reads the duration already on `ReviewResult` (931 D9) or measures it.
- Task 17 says to take `started` before the LLM call, and Task 19 says "same pattern". Task 21 (compact and review) never mentions `started`.
- The failed-review path in Task 21 calls `record_from_telemetry(exc.telemetry, ...)` from `_exception_result`. That function is outside the call scope, so `started` is not obviously available there.
- Criterion 4 (duration on success, failure, and stall) is asserted only for dispatch (Task 18, line 204). Tasks 20 and 22 never assert `duration_seconds`.

Fix:
1. State the duration source for `record_from_review`.
2. Say where `started` is captured for compact and review, and how it reaches `_exception_result`.
3. Add a duration assertion to Tasks 20 and 22 for the failure paths.

### [CONCERN] Task 26 does not say how frontmatter rows feed `usage_totals`

Task 24 defines `usage_totals(records)` over `UsageRecord`s, and Task 26 says it reuses that helper for review totals. Review artifacts hold only frontmatter keys (`promptTokens`, `cachedTokens`, `costUsd`, `costBasis`, and so on). They have no `alias`, `profile`, or `partial` fields.
- No task states the mapping from frontmatter to `TokenUsage`/cost. That covers key names, type leniency, and a `costUsd` that is missing or the wrong type.
- No task says how the `api-rate equiv.` label (Task 28) is derived for reviews.
- Task 27 does not test malformed token or cost values in frontmatter.

Fix: add one sub-item to Task 26 for the frontmatter-to-totals-input mapping, and a matching case to Task 27.

### [CONCERN] Executor wiring for `UsageCapture` is untested

Task 15 has the executor create one `UsageCapture` per run and set `ActionContext.usage_capture` for every step. The "once per alias per process" pricing warning and the once-per-process D7 DEBUG line depend on that sharing. Task 16 tests dedupe only on a hand-built `UsageCapture`. Tasks 18 and 20 likely build their own contexts. Nothing asserts that two steps in one executor run share the same instance.

Fix: add one executor-level test to Task 16 or Task 18. It should check that two steps in a run see the same `UsageCapture`, so the pricing warning fires once.

### [CONCERN] Task 13 mixes too many concerns

Task 13 covers four kinds of change:
- `DispatchTurns` telemetry folding.
- A new `SessionReply` return type.
- Error-telemetry attachment on every raise path.
- Caller migration across four modules plus an unbounded sweep of test fakes found by grep.

The caller and fake migration is mechanical but could touch many files. Consider splitting it into 13a (telemetry folding, `SessionReply`, error telemetry) and 13b (caller and fake migration, with a pyright-clean checkpoint). That gives a junior a smaller blast radius and a commit between the two.

### [NOTE] No load-test task is required

The slice states no performance NFR that needs a load test. Its hot-path bounds (zero extra state saves, frontmatter-only reads) are covered by unit assertions in Task 18 and Task 27. No `tests/load/` or CI-gating task is needed.

### [NOTE] Release bump is not tasked

The slice design calls this a minor-release feature. Under the project's versioning rule, the Project Manager must confirm a minor bump before any files change. No task covers the bump, which is acceptable if the bump happens at Phase 7. Task 31 could add a one-line "propose version bump to the Project Manager" item.

### [NOTE] Walkthrough step 7 cannot be run by an agent

The `/sq:stats` check in Claude Code is interactive. Task 32 already says to stop and report any step that cannot run, so this is handled.

### [PASS] Success-criteria coverage and sequencing

- **Criterion 1:** Tasks 9, 11, 12.
- **Criterion 2:** Tasks 15–22.
- **Criterion 3:** Tasks 13, 14.
- **Criterion 4:** Tasks 17, 18 (see the concern above for the gaps).
- **Criterion 5:** Tasks 4, 5.
- **Criterion 6:** Tasks 17–20.
- **Criterion 7:** Tasks 15–20.
- **Criterion 8:** Tasks 24–29.
- **Criterion 9:** Tasks 23, 29.
- **Criterion 10:** Task 30.

No task is scope creep. Each traces to a criterion, a failure-table row, or the design's closure steps. `resolve_cost` and `usage_capture` are justified by the DRY and 300-line constraints. Test tasks directly follow their implementation tasks, with commits at roughly every second task. No task writes a merge.

### Run Digest

- Response length: 5725 chars
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
- Duration: 49.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
