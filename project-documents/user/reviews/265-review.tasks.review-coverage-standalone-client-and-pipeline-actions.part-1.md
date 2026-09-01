---
docType: review
layer: project
reviewType: tasks
slice: review-coverage-standalone-client-and-pipeline-actions
project: squadron
verdict: FAIL
sourceDocument: project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-1.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260901
dateUpdated: 20260901
reviewedSha: 97b5d10b3a33b8315e7f288043da4fa6b4c8fd04
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 18.2 reads `ReviewResult` fields that Task 19 hasn't created yet"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:165-166"
  - id: F002
    severity: concern
    category: test-coverage
    summary: "Task 18 spans three action types with no dedicated test task"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:151-176"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task 14's test coverage is deferred to Task 15, bundled with an unrelated action"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:54-81"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "SC9's `RunState.action_results` persistence claim has no automated test"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-2.md:178-194"
  - id: F005
    severity: pass
    category: coverage
    summary: "All ten success criteria trace to at least one task, no scope creep"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-1.md"
  - id: F006
    severity: pass
    category: process
    summary: "Commit checkpoints are distributed per-task, not batched"
    location: "project-documents/user/tasks/265-tasks.review-coverage-standalone-client-and-pipeline-actions-1.md:89-96"
---

# Review: tasks — slice 265

**Verdict:** FAIL
**Model:** claude-sonnet-5

## Findings

### [FAIL] Task 18.2 reads `ReviewResult` fields that Task 19 hasn't created yet

Task 18.2 says: "capture the same telemetry from `run_review_with_profile`'s result (task 19 adds the fields to `ReviewResult`) into `ActionResult.metadata`." Task 19 (lines 178-188) is what adds `tools_given`/`tool_calls_made` to the `ReviewResult` dataclass *and* makes `run_review_with_profile` populate them (19.3). Task 18 is numbered — and per the file's own commit protocol, executed and committed — before Task 19. A junior AI following the list in order hits 18.2 with no `ReviewResult.tools_given` attribute to read from; the subtask cannot be implemented as written without either stubbing the field itself (undocumented, duplicates Task 19's work) or skipping ahead out of order. Fix by moving the `ReviewResult` field additions (19.1/19.3) before Task 18, or by moving 18.2 into Task 19 as a single "wire review telemetry end-to-end" task.

### [CONCERN] Task 18 spans three action types with no dedicated test task

Every other implementation task in this breakdown pairs 1:1 with an immediately-following test task: 3→4, 5→6, 7→8, 9→10, 11→12, 16→17, 21→22. Task 18 (effort 4/5, three subtasks touching `dispatch.py`, `review.py`, and `summary.py`) breaks that pattern — its own success criteria list behavioral outcomes but no `pytest` command, and no "Task 18b: test telemetry carry" follows it. The only automated check that exercises this path is Task 20.3, which explicitly covers "at least one action type end to end," not all three. Given SC8 names dispatch, review, *and* summary explicitly, unit-level regression coverage for two of the three carriers is left implicit.

### [CONCERN] Task 14's test coverage is deferred to Task 15, bundled with an unrelated action

Task 14 (wire `allowed_tools` into `ReviewAction`) has no test subtask and no `pytest` command in its own success criteria — unlike Task 15, which tests itself (summary) at 15.3 and *also* retroactively covers "the review-side change from task 14, if not already covered there" (line 96-97). The commit protocol at the top of file 1 requires "the relevant scoped test command passes first" before each task's commit; as written, Task 14's commit has no scoped test asserting its own new behavior — the assertion arrives a task later, conditioned on "if not already covered." This should either be pulled into Task 14 directly, or Task 14/15 should be explicitly merged so the dependency is visible.

### [CONCERN] SC9's `RunState.action_results` persistence claim has no automated test

SC9 requires `tools_given`/`tool_calls_made` to "appear in `RunState.action_results` for pipeline steps." Task 19 gives the review-JSON half of SC9 automated coverage (`tests/review/test_models.py`, persisted review JSON asserted). The `RunState.action_results` half relies only on Task 24.1's manual `sq run -v` + hand-inspection of `~/.config/squadron/runs/<run>.json` — there's no pytest asserting the dict shape lands in `RunState.action_results` for a pipeline step. The design's justification ("no schema change needed, already receives action metadata") is a reasonable basis for *not* needing new plumbing, but it isn't a substitute for a regression test proving the new keys actually flow through.

### [PASS] All ten success criteria trace to at least one task, no scope creep

SC1/SC1a→3,4,5,6; SC2→21; SC3→7,8,22; SC4→7,9,8,10; SC5→11,12; SC6→23; SC7→13,14,15; SC8→16,18,20,24.1; SC9→19(+gap above); SC10→24.2. Every Out-of-Scope item in the slice design (write/shell tools on review path, `--no-tools` flag, models.toml capability field, streaming intermediate turns, SDK reviewer behavior changes) is correctly absent from the task list — no scope creep found.

### [PASS] Commit checkpoints are distributed per-task, not batched

The commit protocol requires `ruff format` + a semantic commit at the end of every task (1-25), each with its own message. This is followed consistently through both files; Task 25's "close-out" commit is appropriately reserved for docs/checklist bookkeeping only, not a dumping ground for code changes.
