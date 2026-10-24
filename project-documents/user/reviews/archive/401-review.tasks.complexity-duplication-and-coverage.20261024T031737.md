---
docType: review
layer: project
reviewType: tasks
slice: complexity-duplication-and-coverage
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261023
dateUpdated: 20261023
reviewedSha: bc639c0d2b562a2ff1c94fec87aa165aa899dd25
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 103738
cachedTokens: 11222
cacheWriteTokens: 92512
completionTokens: 4618
durationSeconds: 36.3
costUsd: 0.418092
costBasis: provider
runId: run-20261024-p5-b9ca268a
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Wrong task references in Tasks 3 and 5 send the implementer to the wrong task"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:56"
  - id: F002
    severity: concern
    category: test-sequencing
    summary: "Task 2's `test_take.py` test goes stale as soon as later tasks add metrics"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:44"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 7 is overweight and has no checkpoint of its own"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:88"
  - id: F004
    severity: concern
    category: scoping
    summary: "Task 13 may push `typescript_length.py` past ~300 lines, and unlike Task 11 it has no fallback or success line"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:149-153"
  - id: F005
    severity: note
    category: coverage
    summary: "Success Criterion 12 and the read-only property have thin direct coverage"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:145"
  - id: F006
    severity: pass
    category: coverage
    summary: "Success criteria trace to tasks, with no scope creep"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing and proportionality are sound"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
---

# Review: tasks — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Wrong task references in Tasks 3 and 5 send the implementer to the wrong task

Task 3 says the exported text is "for the `counting` text in Task 5". Task 5 is the TypeScript decision-point count. The `counting` text is built in Task 7.

Task 5 has two matching errors:
- It says `_is_counted` "is passed in by Task 6". Task 6 is the TypeScript complexity tests, and the wiring happens in Task 7.
- It says its text is "for the `counting` text in Task 6". That should also be Task 7.

A junior AI that follows these references literally will look in the wrong place. Change all three to Task 7.

### [CONCERN] Task 2's `test_take.py` test goes stale as soon as later tasks add metrics

Task 2 adds a test asserting that all four new metrics are `metric_unsupported` for both languages. Task 7 then adds `cyclomatic_complexity` to both adapters' `metrics`. Tasks 11 and 13 add `duplicated_lines`, and Task 24 adds the coverage metrics. After Task 7 that test fails, and no later task says to update or remove it.

The per-commit gate ("tests for the touched area") would then block the Task 8 commit. Either:
- scope the Task 2 test to a throwaway fake adapter that claims no new metrics, or
- add an explicit step in Tasks 7, 11, 13 and 24 to adjust or delete it.

Task 25's "every language section holds all eight metrics" check could replace it.

### [CONCERN] Task 7 is overweight and has no checkpoint of its own

Task 7 combines six changes:
- the `FunctionLength` → `MeasuredFunction` rename
- the `measure_length_metrics` → `measure_parse_metrics` rename
- a new `complexity.py` module
- a signature change taking a second `ToolIdentity`
- Python wiring and a new tool identity
- TypeScript wiring and a new tool identity

It also changes the `metrics` sets of both adapters. It carries no commit, and its tests are deferred to Task 8.

Split it in two:
- **7a:** the renames plus `complexity.py` and the `measure_parse_metrics` signature, with the 400 length tests green and a commit.
- **7b:** the Python and TypeScript wiring, with Task 8's tests.

That leaves a safe checkpoint after the rename, which touches many call sites.

### [CONCERN] Task 13 may push `typescript_length.py` past ~300 lines, and unlike Task 11 it has no fallback or success line

Task 11 includes "if it would exceed, move the tokenizer into a new module and update the slice design's module table". Task 13 puts the tokenizer straight into `typescript_length.py`. That file already holds the function walk, the parser helper, `_is_counted` and `_extract_functions`, and Task 7 adds more to it. I did not check the file's current size.

Task 13 also has no `Success:` line, which every other implementation task has.

Add a Success line that includes the line-count check and the same extraction fallback as Task 11.

### [NOTE] Success Criterion 12 and the read-only property have thin direct coverage

Task 12 asserts identical file-length and function-length values only for Python. For TypeScript the plan relies on 400's existing tests passing (Task 7). That is probably enough, but it is implicit.

No task asserts that the snapshot stays read-only (400 criterion 8, restated in Success Criterion 11). Task 25 covers determinism only. If 400's read-only test runs the real adapters, name it in Task 25. Otherwise add one assertion that the repo is unchanged.

### [PASS] Success criteria trace to tasks, with no scope creep

Each criterion maps to a task that tests it:

| Criterion | Task |
|---|---|
| 1 | 7, 9, 11, 13 |
| 2 | 8 |
| 3 | 4, 6 |
| 4 | 10, 14 |
| 5 | 21 |
| 6 | 19 |
| 7 | 19, 23 |
| 8 | 19 |
| 9 | 16 |
| 10 | 10 |
| 11 | 25 |
| 12 | 12 |

The technical and integration requirements map to Tasks 17, 26, 27 and 29. Every task traces to the design. There is no load-test requirement, so the NFR load-test and CI-gating checks don't apply. Merging is correctly left out of the task file.

### [PASS] Sequencing and proportionality are sound

Dependencies run forward with no cycles:
- Fixtures (Task 17) come before the reader (Task 18).
- The reader comes before freshness (Task 20), the measurements (Task 22) and the adapter wiring (Task 24).
- Render, docs, the walkthrough and final validation come last.

Commits fall at every test-bearing task from Task 2 to Task 29. A single task file for 29 tasks is proportionate to a slice that adds four metrics across two languages, and the test tasks stay within what the success criteria need.

### Run Digest

- Response length: 5659 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 103738 / 11222 / 92512 / 4618 / not computed
- Duration: 36.3 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
