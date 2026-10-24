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
reviewedSha: ac3afee74451dbcfeb59e408efdee74c3b67bbe9
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
turns: 6
promptTokens: 191672
cachedTokens: 95894
cacheWriteTokens: 95772
completionTokens: 4413
durationSeconds: 38.1
costUsd: 0.437553
costBasis: provider
runId: run-20261024-p5-b9ca268a
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F003
    severity: concern
    category: proportionality
    summary: "Task file is heavier than the slice needs"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F004
    severity: note
    category: test-coverage
    summary: "Criterion 10 and the failure table's \"other metrics unaffected\" has no adapter-level assertion"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
  - id: F005
    severity: note
    category: task-quality
    summary: "Task 28 has no success line"
    location: "project-documents/user/tasks/401-tasks.complexity-duplication-and-coverage.md"
---

# Review: tasks — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage

Every criterion maps to a task and a test:
- **Criteria 1–3:** Tasks 8, 9, 4 and 6.
- **Criterion 4:** Tasks 11, 13 and 15, including the cross-language clause in Task 15.
- **Criteria 5 and 9:** Tasks 22 and 17.
- **Criteria 6–8:** Tasks 20 and 24.
- **Criterion 10:** Task 11.
- **Criterion 11:** Task 26.
- **Criterion 12:** Task 7.

Every row of the slice's failure-mode table has a test: tokenizer errors, `MemoryError`, `RecursionError`, malformed Cobertura, stat `OSError`, and `git ls-files` `None` or non-zero. Task 30 re-checks the criteria and the frozen-contract diff, and Task 29 covers the walkthrough. Nothing in the file is scope creep.

### [PASS] Sequencing and test-with pattern

- **Dependencies:** each task's prerequisites come earlier.
  - Task 2 fixes `PythonAdapter.metrics`, which is currently `frozenset(SnapshotMetric)` (`python_adapter.py:105`). That would make `take_snapshot` raise once the enum grows.
  - `typescript_adapter.py:22` already spells its set out, so Task 2 correctly touches only Python.
  - Task 7 extracts the read-and-decode helper before Task 10 reuses it.
  - Task 18 captures real fixtures before the Task 19 parser.
- **Commits:** they come after each implementation and test pair (4, 6, 9, 11, 13, 15, 17, 20, 22, 24, 26, 27) and are spread through the file. Nothing is batched at the end.
- **Gitignore:** `.squadron.toml` is gitignored (`.gitignore:174`), so the walkthrough's key edits in Task 29 won't dirty the tree and trip preflight.

### [CONCERN] Task file is heavier than the slice needs

The file has 30 tasks, and several are separate tasks for work that fits in one. Suggested cuts:
- **Task 1 (branch):** fold it into Task 2 as its first sub-item. It has a one-line success check and no commit.
- **Tasks 16 and 17:** merge them. Together they are a config key, a path parser and a few preflight cases, with one commit.
- **Tasks 12 and 13, and Tasks 14 and 15:** each pair is already an implementation task plus its test task. Merge each pair into one task per language, keeping the single commit. Tokenizer wiring has no standalone commit, so the split adds ceremony only.
- **Task 24:** it overlaps Task 20's assertions and Task 26's per-language cases. Keep the `tool_ignored_files` zero-hit case, the absence-propagation case and the Istanbul `counting` case. Drop the rest.
- **Task 30:** fold it into the end of Task 29. It re-runs checks every earlier commit already requires.

These cuts reduce the file to roughly 22–23 tasks without losing any criterion coverage.

### [NOTE] Criterion 10 and the failure table's "other metrics unaffected" has no adapter-level assertion

Success Criterion 10 and the failure-mode table both say other metrics are unchanged when `duplicated_lines` is `tool_failed`.
- **What Task 11 checks:** it asserts only the duplication result, at the `measure_duplication` level.
- **What Task 13 checks:** it checks that function length is unaffected for tokenizer errors, not for a ceiling failure.
- **Suggested fix:** add one assertion to Task 13 or Task 26. With `DUPLICATION_MAX_TOKENS` lowered, a `PythonAdapter` run should still return present function length and complexity.

### [NOTE] Task 28 has no success line

Task 28 lists edits and a commit but no verifiable success condition. Add something checkable, such as: the CHANGELOG bullet exists, and `docs/COMMANDS.md` names all four metrics and the config key.

### Run Digest

- Response length: 4280 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 6
- Tokens — prompt / cached / cache write / completion / reasoning: 191672 / 95894 / 95772 / 4413 / not computed
- Duration: 38.1 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
