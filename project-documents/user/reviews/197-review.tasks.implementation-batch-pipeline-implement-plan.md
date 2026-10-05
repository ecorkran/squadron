---
docType: review
layer: project
reviewType: tasks
slice: implementation-batch-pipeline-implement-plan
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261005
dateUpdated: 20261005
reviewedSha: e87b2474497242a650c29f8fffffb4303339de5f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 38.8
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: concern
    category: task-sizing
    summary: "Task 28 is too large for one junior-AI task"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:317-327"
  - id: F002
    severity: concern
    category: test-sequencing
    summary: "Implementation tasks are committed before their tests (Tasks 4, 11, 28)"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:68-89"
  - id: F003
    severity: concern
    category: coverage-gap
    summary: "Task 24 may not cover plain `--resume` of a mutating run"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:275-282"
  - id: F004
    severity: concern
    category: coverage-gap
    summary: "Task 19's pipeline-level test doesn't assert criteria 1, 2 and 11"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:221-229"
  - id: F005
    severity: note
    category: task-sizing
    summary: "Task 17 combines three changes"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:203-210"
  - id: F006
    severity: note
    category: task-sizing
    summary: "Task 20 touches four pipeline files plus test rewrites"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:231-242"
  - id: F007
    severity: note
    category: nfr
    summary: "No NFR load-test obligation applies"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:479-528"
  - id: F008
    severity: pass
    category: coverage
    summary: "Success criteria traceability"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:358"
  - id: F009
    severity: pass
    category: sequencing
    summary: "Sequencing and commit cadence"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:107-112"
---

# Review: tasks — slice 197

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 28 is too large for one junior-AI task

Task 28 bundles six separate concerns in one task and one commit:
- loading run state and stripping the reserved keys
- applying the `--model`/`-p` overrides
- the reconcile path (`merge-base --is-ancestor`)
- the single-item dependency check
- running the body through `_run_each_item`
- replacing the record, rewriting the report, and mapping exceptions to `ResumeExit`

Its tests all sit in Task 29, so a large amount of untested code is committed first. Split it. One option is "param loading and reserved-key strip", then "source re-evaluation, reconcile and dependency check", then "body run, record replace and exit mapping". Give each part its tests, or move Task 29's matching cases next to them.

### [CONCERN] Implementation tasks are committed before their tests (Tasks 4, 11, 28)

Tasks 4 and 5, 11 and 12, and 28 and 29 split implementation from tests. The tests do follow immediately, which is acceptable. But Tasks 4, 11 and 28 each end with a commit whose only success check is "pyright clean". That breaks the "tests with implementation" pattern used elsewhere in this file: Tasks 2, 3, 6, 7, 9, 10, 13, 14, 15, 16, 17, 22 and 23 all test in the same task. Fold each test task into its implementation task, or at least run the existing tests before the implementation commit. Task 4 is the riskiest because it changes git-mutating behavior.

### [CONCERN] Task 24 may not cover plain `--resume` of a mutating run

D11 says item resume, and "any `sq run` whose pipeline mutates", take the lock. A plain `sq run --resume <id>` of a paused P6, P456 or `implement-plan` run mutates git and cf state just as a fresh run does. Task 24 only says "`sq run` holds `project_run_lock` for the whole run", and none of its tests cover the resume path. State explicitly that the fresh-run and plain-`--resume` paths both take the lock. Add a test that a plain resume with the lock held exits 2. Item resume takes the lock separately in Task 26.

### [CONCERN] Task 19's pipeline-level test doesn't assert criteria 1, 2 and 11

The Task 19 test uses fake cf, dispatch and review. It checks ordering, `review_unresolved`, dependency flagging, an independent item merging, and the `EmptyDiffError` case. It does not explicitly assert:
- Criterion 1: the checkout ends on the target, with one `merge: slice N — …` commit per merged slice.
- Criterion 2: a `not_ready` slice's body doesn't run (no dispatch calls for it).
- Criterion 4: a dependency on an undesigned slice flags the dependent `dependency N not designed`. The source half is covered in Task 12, but not through the pipeline.

Task 31 maps criteria to tests, and it would catch these gaps late. Add the assertions here, and say whether branch ops run against a temp repo or are faked.

### [NOTE] Task 17 combines three changes

Task 17 covers the per-item report rewrite, the halt handling that records the in-flight item and the `not_run` items, and the CLI summary line. It is still completable. If it grows during implementation, split the CLI summary line off.

### [NOTE] Task 20 touches four pipeline files plus test rewrites

The edits are mechanical and use the same D10 body, so one task is defensible. Task 21's drift test is what guards against divergence. Consider committing after the first two files, since each file has its own param additions.

### [NOTE] No NFR load-test obligation applies

The slice design doesn't state a performance or throughput NFR, so neither a `tests/load/` task nor a CI gating task is required.

### [PASS] Success criteria traceability

Criteria 1–17 map to tasks as follows:
- 3, 4, 5: Tasks 10, 12 and 19
- 6: Tasks 16, 17 and 29
- 7, 8, 9: Tasks 26 and 29
- 10: Tasks 4 and 5
- 11: Task 7
- 12: Tasks 20 and 21
- 13: Task 15
- 14: Task 27
- 15: Tasks 24, 26 and 30
- 16, 17: Tasks 16, 22, 24, 28 and 29

Every D12 row has a named test with an asserted log record. Task 31 adds a final criteria-to-test mapping step. No task lacks a design anchor.

### [PASS] Sequencing and commit cadence

The dependencies hold:
- Task 2's helpers come before Tasks 4 and 9.
- Task 3's `BranchFailure` comes before Tasks 4 and 15.
- Task 13's fields come before Tasks 15–17.
- Task 14's `exhausted` comes before Task 15.
- Task 16's load comes before Task 26.
- Task 23's lock comes before Tasks 24 and 26.
- Task 25's `accept_decision` comes before Task 28.
- Task 6's `restore_target` comes before Task 27.

There are no cycles. Commits are spread across 25 tasks, with checkpoints at Tasks 8, 18 and 31, rather than batched at the end.

### Run Digest

- Response length: 6008 chars
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
- Duration: 38.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9

## Responses

- **F001 (fixed):** Task 28 split into 28a (params from run state, reserved-key strip, decision keys), 28b (source re-evaluation, reconcile, single-item dependency check) and 28c (body run, record replace, exit mapping). Each has its own tests and commit; Task 29 is removed.
- **F002 (fixed):** Tasks 4 and 11 no longer commit on their own. They check that existing tests pass, and the commit comes after their test tasks (5 and 12), so each commit carries both the code and its tests. Task 28 is covered by F001.
- **F003 (fixed):** Task 24 takes the lock on both a fresh run and a plain `--resume` of a paused mutating run, and tests that a plain resume with the lock held exits 2.
- **F004 (fixed):** Task 19's pipeline test runs real branch ops against a temp repo with fake cf, dispatch and review. It now asserts criterion 1 (ends on the target, one merge commit per merged slice), criterion 2 (no dispatch for a `not_ready` item) and criterion 4 (`dependency N not designed` through the pipeline). Criterion 11 is covered by Task 7.
- **F005 (no change):** Task 17 is still a coherent unit; the review accepts it as is.
- **F006 (fixed):** Task 20 commits after P6 and `implement`, then again after P56 and P456.
