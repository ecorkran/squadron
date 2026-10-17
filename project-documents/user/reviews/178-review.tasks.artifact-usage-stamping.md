---
docType: review
layer: project
reviewType: tasks
slice: artifact-usage-stamping
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/178-tasks.artifact-usage-stamping.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261016
dateUpdated: 20261016
reviewedSha: 1c2682e61a6d8d185ee89ff8d83c6478626ef533
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 94395
cachedTokens: 10984
cacheWriteTokens: 83407
completionTokens: 4705
durationSeconds: 37.3
costUsd: 0.382449
costBasis: provider
runId: run-20261017-p5-a1cd3acb
squadronVersion: 0.23.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and checkpoints"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md"
  - id: F003
    severity: concern
    category: test-with-pattern
    summary: "Failure-handling code is committed before its tests"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:139-187"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task 5 adds tests beyond what the move requires"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:76-83"
  - id: F005
    severity: concern
    category: task-clarity
    summary: "Task 17 hedges on whether the report shape changes"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:228"
  - id: F006
    severity: note
    category: task-clarity
    summary: "Reuse of the reviews report's slice-index rule may need a visibility change"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:199"
  - id: F007
    severity: note
    category: risk
    summary: "Task 19 spends real budget and deletes files, with guards in place"
    location: "project-documents/user/tasks/178-tasks.artifact-usage-stamping.md:250-258"
---

# Review: tasks — slice 178

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

Each functional, technical and integration criterion traces to a task:
- **Stamping on P4, P5 and P2:** Tasks 10 and 11.
- **Revision-loop sums, and restart with the D2 WARNING:** Tasks 11 and 13.
- **Nothing stamped for `existing: keep`, failed dispatch, implement, summary or compact:** the Task 11 eligibility cases.
- **Split task breakdown:** Task 13.
- **Unpriced round:** Task 11.
- **Artifact spend survives prune, and is not summed with recorded spend:** Task 17.
- **Review artifacts byte-identical:** Task 3.
- **`dispatch-artifact` tests pass unchanged:** Task 7.
- **No `StateManager` writes:** Task 11.
- **179 works with no run state:** Task 15.
- **`events.yaml` `disable:` works:** Task 12.
- **Every D6 row has a test:** Task 13.
- **Walkthrough steps 1–6:** Task 19.

I found no scope creep. Every task traces to a design decision (D1–D6) or a success criterion.

### [PASS] Sequencing and checkpoints

Dependencies run in one direction:
- The refactors (Part A) come first.
- The usage model (Part B) comes next. It depends on Task 2's key constants and Task 4's reader.
- The stamp (Part C) depends on Tasks 6 and 8.
- The report (Part D) depends on Task 8.
- Docs and validation come last.

There are no cycles. Commits land at the end of every part and sub-part, not batched at the end. The task file puts no merge in any task, which matches the Git rules. The load-test and CI-wiring checks do not apply: the slice states no NFR.

### [CONCERN] Failure-handling code is committed before its tests

Task 10 implements the D6 failure handling, the revision-round WARNING and the multi-candidate rule. Task 11 commits the action with only the happy-path and eligibility tests. Task 12 then registers the binding and commits. The failure-mode tests do not arrive until Task 13. So the stamp is bound into `DEFAULT_BINDINGS`, and so reachable by every pipeline run, for two commits with its failure paths untested. Move Task 13 ahead of Task 12, or fold it into Task 11. Registration then comes after the action is fully tested.

### [CONCERN] Task 5 adds tests beyond what the move requires

The criterion for the reader move is that `sq stats reviews` output is unchanged. That is met by running the existing `test_reviews_report.py` and the CLI tests unchanged, which is Task 5's first item. The new `tests/review/test_frontmatter_usage.py` is a direct test file for verbatim-moved code. Task 9's `read_artifact_usage` round-trip and malformed cases already exercise `record_from_frontmatter`. Cut the new file, or cut it to the single real-artifact fixture case. Task 7's "resolver error propagates" test is similarly marginal, but it pins the contract that Task 10's error handling relies on, so I would keep it.

### [CONCERN] Task 17 hedges on whether the report shape changes

Task 16 attaches `artifacts_usage_report` to the slice report in `effort_report.py`, so the report shape does change. The qualifier "`tests/stats/test_effort_report.py` if the report shape changed" is therefore unnecessary and leaves a junior implementer a decision. State that the attachment is tested. The first Task 17 bullet should also assert the `(floor)` label. Task 16 and D5 require it, but the design's UI example omits it, so nothing currently pins it.

### [NOTE] Reuse of the reviews report's slice-index rule may need a visibility change

Task 14 says to import the reviews report's rule for deriving the slice from the file name, and not to reimplement it. If that helper is private (underscore-prefixed), importing it across modules needs a rename or a move, as in Task 4. The task does not say so. Tell the implementer to make it public in place if needed.

### [NOTE] Task 19 spends real budget and deletes files, with guards in place

The task asks the Project Manager to confirm before running live pipelines. It limits pruning to the scratch runs and says to stop and ask if it cannot select only those runs. It also covers the case where the walkthrough is not run. This is appropriate.

### Run Digest

- Response length: 5020 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 94395 / 10984 / 83407 / 4705 / not computed
- Duration: 37.3 s
- Cost: $0.38 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
