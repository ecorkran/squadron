---
docType: review
layer: project
reviewType: tasks
slice: sq-onboard
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/440-tasks.sq-onboard.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261026
dateUpdated: 20261026
reviewedSha: 94f2b92fe33a5f206e5f9cbb5a4547f14026f3fa
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 105985
cachedTokens: 11222
cacheWriteTokens: 94759
completionTokens: 5671
durationSeconds: 49.7
costUsd: 0.437607
costBasis: provider
runId: run-20261026-p5-9ba2586e
squadronVersion: 0.24.5
findings:
  - id: F001
    severity: concern
    category: test-quality
    summary: "Agent-surface step test cannot fail meaningfully"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:264-270"
  - id: F002
    severity: concern
    category: coverage-gap
    summary: "Open Integration Requirements have no trackable item"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:41"
  - id: F003
    severity: concern
    category: verification
    summary: "No final full-suite and lint gate after the last code task"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:281-284"
  - id: F004
    severity: concern
    category: task-scoping
    summary: "The probe move is split in a way that duplicates code between commits"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:159-171"
  - id: F005
    severity: note
    category: proportionality
    summary: "Task count is heavy for an effort-3 slice"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:45-285"
  - id: F006
    severity: note
    category: clarity
    summary: "Protocol placement is left open"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:143"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:49-284"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing and commit distribution"
    location: "project-documents/user/tasks/440-tasks.sq-onboard.md:49-284"
---

# Review: tasks — slice 440

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Agent-surface step test cannot fail meaningfully

T25 asserts that "each `OnboardStep` value appears in both" files. The values are `handoff`, `ask-adopt`, `build-graph`, `comprehension`, `concept` and `adopt`. Plain substring matching makes this nearly vacuous:
- `adopt` matches inside `ask-adopt`.
- `concept` and `comprehension` appear in the command names the files already contain (`/sq:analysis understand concept` and so on).
- A file with no per-step block for `adopt` still passes.

The same applies to the no-progress stop rule assertion. T23 and T24 don't say what marker the test looks for, so the implementer has to invent one.

Change T23 and T24 so each step block carries a distinguishable marker, such as a heading per step. Then have T25 assert on those markers, for example one heading per `OnboardStep` value matched exactly. Give the stop rule an equally specific marker.

### [CONCERN] Open Integration Requirements have no trackable item

The slice design makes two criteria hard requirements:
- The live run (walkthrough steps 1 and 2) must pass.
- The recorded fixtures must match what the released cf prints.

The task file moves both into a "Slice precondition, not a task" note. The design says the slice isn't complete until the live run passes, yet no unchecked item exists to hold that. With every T1–T27 checked, the slice can look finished while those criteria are still open.

Add a final unchecked task covering fixture regeneration and the two walkthrough steps. It should carry a `BLOCKED:` line naming cf 271, cf 272 and ai-project-guide #47. That is the form the project rules prescribe for work that can't proceed.

### [CONCERN] No final full-suite and lint gate after the last code task

The design's Technical Requirements say `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite must pass. The last full `pytest` run is in T13. Everything after it (T14–T25) runs only its own test directory.

T27 runs only greps. It has no full-suite, lint or type-check success criterion, even though it may commit `refactor:` fixes. Add a full `pytest`, `ruff format`, `ruff check` and `pyright` run to T27's success criteria.

### [CONCERN] The probe move is split in a way that duplicates code between commits

T12 creates `onboard/graph.py` and `onboard/surfaces.py` and moves their tests. It leaves `probe/graph.py`, `probe/surfaces.py` and `probe/report.py` in place "so `sq probe` still builds". For one commit the code exists twice, which T12 calls a "move" but which is really a copy. T13 then deletes the originals.

Both tasks are effort 2 and touch the same files. Either merge them into one commit, with the probe deletion and the "`sq probe` not registered" test, or state in T12 that it is a copy and that T13 removes the original. The single-commit form is simpler and avoids the interim duplication.

### [NOTE] Task count is heavy for an effort-3 slice

There are 27 tasks, and 9 of them are separate test tasks (T3, T7, T9, T11, T16, T18, T20, T22, T25). The test-with pattern is respected, so this is not a defect. Several pairs are small enough to be one task with a single commit:
- T6 and T7
- T15 and T16
- T14, which is already self-contained
- T23, T24 and T25

Merging them would cut about ten task headers without losing any coverage. The task file is not oversized in steps or files, so I'm not asking for a change.

### [NOTE] Protocol placement is left open

T10 says to place the `Protocol` "here or in `onboard/`; one definition". `onboard/__init__.py` already imports from `cf_adoption`, so putting it in `cf_adoption.py` avoids a circular import and removes the ambiguity. Pick one location in the task.

### [PASS] Success criteria coverage

Each functional criterion in the design maps to a task:
- No writes: T20.3
- D1 table rows: T16
- D7 (version, outcome, envelope, timeout): T3, T4, T9, T20
- D8: T11 and T22
- D4 monorepo: T20.4
- D11: T5 and T7
- `sq probe` removal: T13
- Single-definition and no-cf-names requirements: T27

No task lacks a traceable criterion.

### [PASS] Sequencing and commit distribution

Dependencies run forward only:
- Fixtures (T1) come before every test that uses them.
- Client changes (T2–T5) come before the adoption client (T8–T11).
- Graph and surface code (T12) and the comprehension module (T14) come before `build_onboard_report` (T17).
- The report (T17) comes before the CLI (T19–T22), and the CLI before the agent surfaces (T23–T25).

Commits land at most every one to three tasks, not at the end. Branch creation is in T1, and no task merges or pushes.

### Run Digest

- Response length: 5763 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 105985 / 11222 / 94759 / 5671 / not computed
- Duration: 49.7 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
