---
docType: review
layer: project
reviewType: tasks
slice: pipeline-tasks-review-covers-every-split-task-file
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260929
dateUpdated: 20260929
reviewedSha: 23e67b2f941bddbbaf4fd5ce90cba97dc968ea64
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
squadronVersion: 0.16.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria coverage is complete"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern respected"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 7 is too large for one junior-completable task"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md:191-252"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Regression snapshot is generated after the code it guards has already changed"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md:244-250"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "Some fold behaviors in Task 7 lack explicit tests"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md:219-241"
  - id: F006
    severity: note
    category: process
    summary: "No explicit commit for close-out documentation"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md:350-363"
  - id: F007
    severity: note
    category: scope
    summary: "Minor out-of-scope edit in Task 4"
    location: "project-documents/user/tasks/930-tasks.pipeline-tasks-review-covers-every-split-task-file.md:116-117"
---

# Review: tasks — slice 930

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria coverage is complete

- **Per-part reviews and `part-N` artifacts:** Tasks 2, 4 and 7 cover the multi-file `tasks` review.
- **Worst-verdict gating:** Task 7 covers it, and Task 10 covers the `skip_if_met` loop that runs a revise round.
- **`judge.tasks-vs-slice` fan-out:** Task 4 registers the fan-out and Task 7 tests per-part enforcement, lowest score, and unscored parts skipped.
- **Single-file regression:** Task 7.
- **CLI and pipeline filename parity:** Task 10.
- **UNKNOWN `KeyError` fix:** Task 3.
- **Dispatch feedback prompt:** Task 8.
- **Unsaved parts in the batch report:** Task 9.
- **`review_outputs.py` typed readers and `TypeError` on wrong shapes:** Task 5.
- **Failure modes:** Task 7 covers the provider failure and save failure paths. It also covers pre-validation of every part before any model call.
- **Verification walkthrough:** Task 12 follows the design's steps.

### [PASS] Sequencing and test-with pattern respected

- **Dependencies:** `parts.py` (Task 2) comes before its CLI use (Task 3). The registry (Task 4) and the output keys (Task 5) come before the pure refactor (Task 6), which comes before the multi-part loop (Task 7). Dispatch (Task 8) and the batch report (Task 9) come after the writer.
- **Interim shim:** Task 4's shim keeps the build green until Task 7 replaces it, and there are no circular dependencies.
- **Tests:** each implementation task carries its tests in the same task.
- **Commits:** every code task ends with its own commit, so checkpoints are spread through the breakdown.
- **Scope:** I found no scope creep. Task 13's close-out items are standard housekeeping.
- **NFRs:** the slice states no NFR, so no load test or CI gate task is required.

### [CONCERN] Task 7 is too large for one junior-completable task

Task 7 bundles six separate pieces of work:
- the `_resolve_slice_inputs` signature change;
- up-front validation of every part;
- the sequential loop with logging;
- provider and save failure handling;
- the full `_fold` table with about 8 field rules;
- about 8 test scenarios plus the single-file snapshot regression.

That is the riskiest work in the slice, all under one commit. Split it into:
- 7a: the part loop, validation, and failure handling;
- 7b: `_fold` and its tests;
- 7c: the single-file regression.

Each piece then gets its own commit checkpoint.

### [CONCERN] Regression snapshot is generated after the code it guards has already changed

The single-file snapshot is produced in Task 7, but Tasks 4 and 6 have already modified the review path by then. Task 7 says to generate it from `main` via `git show` or a worktree. That works, but it depends on the implementer remembering and on the last two commits not mattering. Move snapshot capture into Task 1 or Task 6, before the refactor. Task 6 would then also have a byte-level check beyond "no test edits".

### [CONCERN] Some fold behaviors in Task 7 lack explicit tests

The fold rules define these behaviors, but no test scenario covers them:
- the `RESPONSE` join under `## <input path>` headers;
- the summed `tool_calls_made` metadata;
- `INPUT_FILE` / `REVIEW_FILE` omitting `REVIEW_FILE` when the worst part is unsaved;
- `provenance` taken from the first part;
- a judge part whose verdict degrades to UNKNOWN while the score still reports the lowest real score.

Add these to the test list, or drop the requirements from the fold.

### [NOTE] No explicit commit for close-out documentation

Tasks 11 and 12 have no commit step, which is fine because they are validation only. Task 13 edits the CHANGELOG, DEVLOG, slice status, and slice index, but never says to commit them before the merge. Add a `docs:` commit item so the merge carries the close-out changes. The merge step also hard-codes `main` while Task 1 only checks the target once. That is acceptable, but the design says to re-read `git.integration_branch`, which the task already does.

### [NOTE] Minor out-of-scope edit in Task 4

Updating the `_tasks_input` docstring reference in `src/squadron/pr/tasks.py` is small and justified by the final grep in Task 11. It is not in the slice design, so it is worth noting, but it needs no action.

### Run Digest

- Response length: 5364 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
