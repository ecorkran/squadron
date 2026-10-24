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
reviewedSha: 542cdfcbe991661fc2dea627265b9da360cb806f
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 277880
cachedTokens: 181044
cacheWriteTokens: 96828
completionTokens: 5524
durationSeconds: 44.2
costUsd: 0.461406
costBasis: provider
runId: run-20261024-p5-b9ca268a
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria traceability"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:42-269"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 10 bundles a refactor of 400's code with the whole duplication pass"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:115-127"
  - id: F004
    severity: concern
    category: git-workflow
    summary: "Final validation diffs against a hard-coded `main`"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:286"
  - id: F005
    severity: note
    category: task-definition
    summary: "Task 5 has no Success line"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:70-76"
  - id: F006
    severity: note
    category: task-definition
    summary: "Task 8 doesn't name where the TypeScript complexity measurement is returned"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md:97-104"
  - id: F007
    severity: note
    category: proportionality
    summary: "Proportionality is acceptable"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
---

# Review: tasks — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria traceability

Each success criterion maps to a task:
- SC1–2: Tasks 8–9.
- SC3: Tasks 4 and 6.
- SC4: Tasks 11, 13 and 15.
- SC5: Task 22.
- SC6: Tasks 20 and 24.
- SC7: Task 24.
- SC8: Tasks 20 and 24.
- SC9: Task 17.
- SC10: Task 11.
- SC11: Task 26.
- SC12: Task 7.

Every row of the slice's failure-mode table has a test. These are the tokenizer errors, the token ceiling and `MemoryError`, `RecursionError`, malformed XML, `OSError` on stat, and `run_git` returning `None` or non-zero.

No task lacks a source in the slice, so I found no scope creep. Load tests and CI gating are not required. The slice states no NFR beyond the token ceiling, and Task 11 tests the ceiling by lowering the constant.

### [PASS] Sequencing and test-with pattern

The order is enum members, then the complexity counters, then `MeasuredFunction`, then the measurement. Duplication follows, then the config key, the Cobertura reader, freshness and the adapter wiring, and render and docs come last. There are no circular dependencies.

Task 2 handles the `PythonAdapter.metrics = frozenset(SnapshotMetric)` trap. I checked `typescript_adapter.py:22`. Its `metrics` is already an explicit set, so only the Python adapter needs the change.

Task 18 captures the real report fixtures before Task 19 parses them. That follows the CLAUDE.md parser rule.

### [CONCERN] Task 10 bundles a refactor of 400's code with the whole duplication pass

Task 10 is rated effort 4, and it carries two kinds of work:
- It extracts a shared read-and-decode helper from `lengths._measure_source`. That is a behavior-preserving change to 400's code, which Success Criterion 12 protects.
- It builds the full hash and window index, the ceiling and `MemoryError` handling, and the `per_file` and `counting` output.

The Success line checks only module size and language-neutrality. It says nothing about 400's length tests still passing after the extraction. Nothing is committed or verified until Task 11.

Fix: move the helper extraction into its own small task. Run 400's length tests after it, and make it a `refactor:` commit like Task 7. Alternatively, add "400's length tests pass unchanged" to Task 10's Success line.

### [CONCERN] Final validation diffs against a hard-coded `main`

Task 30 runs `git diff main -- src/squadron/metrology/snapshot_models.py`. The Context Summary says the branch forks from the target, which is `cf config get git.integration_branch` or `main` if that is empty. CLAUDE.md says never to infer the target.

If an integration branch is set, `git diff main` also shows every unrelated commit on that branch. The enum-members-only and no-diff checks on `take.py`, `contract.py`, `files.py` and `store.py` then fail or mislead.

Fix: diff against the target as read from config, or against the branch's fork point.

### [NOTE] Task 5 has no Success line

Every other implementation task ends with a Success item. Task 5 doesn't. Its grammar node-name confirmation step is the riskiest part of the task, because a wrong node name would silently count zero.

Suggested line: "constant node names confirmed against both grammars, and the module imports nothing from `typescript_length`". Task 6 does exercise the names later.

### [NOTE] Task 8 doesn't name where the TypeScript complexity measurement is returned

Task 8 renames `measure_length_metrics` to `measure_parse_metrics` and adds complexity to its return. The TypeScript adapter's `measure()` currently returns `measure_typescript_lengths(ctx, files)` plus lint. Task 8 doesn't say that `measure_typescript_lengths` must pass the third measurement through.

`take_snapshot` raises if the measurements returned differ from `adapter.metrics`. A missed pass-through would fail Task 9's tests immediately. The cost is a short hunt for the cause, so one clause in Task 8 would help.

### [NOTE] Proportionality is acceptable

Thirty tasks in one file is a lot. It fits a slice that adds four metrics across two languages, with a new reader, a freshness rule and render, docs and walkthrough work. Tasks 4, 6, 11, 22 and 24 list many cases, but each traces to a decision or a failure-mode row, and the ones that share a pattern can be parametrized. I don't recommend merging or cutting any task.

### Run Digest

- Response length: 5393 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 277880 / 181044 / 96828 / 5524 / not computed
- Duration: 44.2 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
