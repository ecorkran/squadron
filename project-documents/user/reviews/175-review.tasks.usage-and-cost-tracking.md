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
reviewedSha: 945b8ba6004c0ab3eb5451304524b817b039f980
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
durationSeconds: 38.4
runId: run-20261015-p5-e75c92b8
squadronVersion: 0.21.9
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 16 adds an `ActionContext` field without a default or a migration step"
    location: "unverified"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 12 does not test the `review_client` cost wiring that criterion 1 depends on"
    location: "unverified"
  - id: F003
    severity: note
    category: clarity
    summary: "Task 33 refers to a \"DEVLOG entry\" that no task creates"
    location: "unverified"
  - id: F004
    severity: note
    category: scope
    summary: "Task 16's \"under ~150 lines\" target is probably too tight"
    location: "unverified"
  - id: F005
    severity: note
    category: scope
    summary: "Task 31 runs `sq install-commands` against the local environment"
    location: "unverified"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success criteria coverage and traceability"
    location: "unverified"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern, and commit distribution"
    location: "unverified"
  - id: F008
    severity: pass
    category: scope
    summary: "Proportionality"
    location: "unverified"
---

# Review: tasks — slice 175

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 16 adds an `ActionContext` field without a default or a migration step

Task 16 says `ActionContext` gains a `usage_capture: UsageCapture` field "set by the executor for every step". `ActionContext` is built in at least five places outside the executor's step path (`executor.py:913`, `executor.py:1507`, `branch_run.py:33`, `commit_run.py:68`) and in about 35 test files. If the field is required, all of them break at once. If it has a default, that default would be a silent fallback or an obviously-placeholder value, which the project rules restrict. The task does not choose between making the field required and migrating every constructor, or giving it an explicit non-silent default. Without a choice, the junior implementer will either break 35+ tests or add an unreviewed default. Task 16 should state which option to use. If it migrates call sites, it should name the standalone `branch_run` and `commit_run` commands, which have no executor-owned capture. Task 17 or 19 should include the test-helper updates.

### [CONCERN] Task 12 does not test the `review_client` cost wiring that criterion 1 depends on

Criterion 1 (an SDK review artifact carries `costUsd` and `costBasis: provider`) depends on Task 11's change in `review_client`. That change calls `resolve_cost` with `capture.cost_usd`, and does the same on the `ProviderError` path using `telemetry.cost_usd`. Task 12 tests `RunCost` rendering, and Task 10 tests the agent. Nothing exercises `review_client` itself with a captured provider cost, and nothing exercises the error-path cost. A break in that glue would only show up in the Task 33 live walkthrough. Add one `review_client` test with an SDK-style capture (provider cost → `provider`) and one with a `ProviderError` carrying telemetry cost.

### [NOTE] Task 33 refers to a "DEVLOG entry" that no task creates

Task 33 says to record each walkthrough step's outcome in the DEVLOG entry. No task creates or names a DEVLOG file. State where the outcomes go, or fold this into the Phase 6 completion convention.

### [NOTE] Task 16's "under ~150 lines" target is probably too tight

`usage_capture.py` is meant to hold five builders, `stamp`, `effort_for_session`, the pricing WARNING and the D5 WARNING. A ~150-line target is likely to be exceeded. This is only a guideline and the project limit is ~300 lines, so no change is needed. Consider raising the target to avoid pressure to inline logic back into the oversized action files.

### [NOTE] Task 31 runs `sq install-commands` against the local environment

Task 31 runs `sq install-commands` locally. It is traceable to criterion 10 and walkthrough step 7, and it only modifies the user's command directory. It is outward-facing enough that the task should say to run it only on the Project Manager's machine or in the scratch project.

### [PASS] Success criteria coverage and traceability

- **Criterion 1:** Tasks 9, 11, 12.
- **Criterion 2:** Tasks 18–23.
- **Criterion 3:** Tasks 13 and 15.
- **Criterion 4:** Tasks 16–23.
- **Criterion 5:** Tasks 4 and 5.
- **Criterion 6:** Tasks 18 and 20.
- **Criterion 7:** Tasks 18–21.
- **Criterion 8:** Tasks 25–30.
- **Criterion 9:** Task 24.
- **Criterion 10:** Task 31.

Every task traces to a criterion, a decision (D1–D10) or a listed issue closure. The "Hot-path cost" bound is tested in Tasks 19 and 28. No NFR in the slice calls for a `tests/load/` test or a CI gate.

### [PASS] Sequencing, test-with pattern, and commit distribution

Dependencies run one way: neutral types, then constants, then pricing, then the SDK reader and agent, then review artifacts, then session telemetry, then `usage_capture`, then the actions, then stats, then the CLI, then docs and validation. Test tasks immediately follow their implementation tasks. There are commits after Tasks 3, 5, 10, 12, 13, 15, 17, 19, 21, 23, 24, 26, 28, 30, 31 and 32. The merge is correctly left to Phase 7. Task 6 is guarded: it stops rather than hand-writing a fixture if the live capture fails.

### [PASS] Proportionality

There are 34 tasks in one file, which fits effort 4/5 and a slice spanning providers, pipeline, review, stats and CLI. The tasks keep the oversized `dispatch.py` and `review.py` small by pushing logic into `usage_capture.py`. Task 14 (migrating callers and fakes) is the largest single task. It is still a mechanical, grep-guided change and does not need splitting.

### Run Digest

- Response length: 5078 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 38.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
