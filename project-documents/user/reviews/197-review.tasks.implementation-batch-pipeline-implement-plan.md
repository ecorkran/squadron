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
aiModel: claude-opus-5-5
status: complete
dateCreated: 20261005
dateUpdated: 20261005
reviewedSha: 4f2af384a74184ae4ec39a8817caefcb06730c06
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 53.1
squadronVersion: 0.18.4
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Item resume maps some errors to the wrong exit code"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:291-323"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 3 tests a `set_arch` failure that only exists after Task 7"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:59-66"
  - id: F003
    severity: note
    category: coverage
    summary: "Some criteria have no test listed, though Task 31 should catch them"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:219-246"
  - id: F004
    severity: note
    category: clarity
    summary: "Task 2 doesn't say where the new helpers live"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:52-57"
  - id: F005
    severity: note
    category: sequencing
    summary: "The run lock may break existing `sq run` tests"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:272-278"
  - id: F006
    severity: pass
    category: coverage
    summary: "Every design criterion maps to a task, with no scope creep"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, test placement and commits"
    location: "project-documents/user/tasks/197-tasks.implementation-batch-pipeline-implement-plan.md:40-378"
  - id: F008
    severity: pass
    category: nfr
    summary: "No load test or CI wiring needed"
    location: "project-documents/user/slices/197-slice.implementation-batch-pipeline-implement-plan.md:504-522"
---

# Review: tasks — slice 197

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] Item resume maps some errors to the wrong exit code

The design's D12 table gives specific exit codes that Tasks 26 and 28 don't fully carry over:
- **Run lock, `rev-parse --git-dir` failure:** the design raises `GitEnvironmentError` and exits 2, because nothing ran.
- **Run lock, any other `OSError`:** exits 2.
- **Report temp write or rename fails with `OSError`:** item resume exits 3.

Task 26 only says "held → REJECTED". Task 28 maps every `GitEnvironmentError` to HALTED, so a junior implementer will most likely return exit 3 for a lock-acquisition `GitEnvironmentError`. That breaks the Amoeba contract, where exit 2 means "nothing ran, retry later" and exit 3 means a human is needed. Task 28 also never maps the report-write `OSError` to HALTED.

The fix is to state the mapping explicitly:
- In Task 26: lock `GitEnvironmentError` and lock `OSError` → REJECTED.
- In Task 28: report-write `OSError` → HALTED.
- Add tests for both to Task 29 or Task 26.

The same gap applies to `sq run` in Task 24, which only tests the "held" case. The `rev-parse` failure there should also exit 2.

### [CONCERN] Task 3 tests a `set_arch` failure that only exists after Task 7

Task 3 requires a test showing that a "failed `set_arch`" reports `failure: other`. But `branch: { plan: }`, which inserts the `set_arch` cf-op before enter, isn't added until Task 7 (lines 99-105).

There is also a design problem. `set_arch` runs as a separate cf-op step, not inside the branch action, so the branch action's outputs can't hold a `failure` key for it. Under D7, it reaches STEP_FAILED through the "anything else" rule. Task 7 already tests "a failed `set_arch` flags the item with `failure: other`", which has the same mismatch.

The fix:
- Remove `set_arch` from Task 3.
- In Task 7, assert that a failed `set_arch` produces flag kind `step_failed`, not a `failure: other` output.
- Keep the criterion-13 check in Task 15 as it is.

### [NOTE] Some criteria have no test listed, though Task 31 should catch them

- **Criterion 12:** no task tests that P6, `implement`, P56 or P456 *pauses* on exhaust. Task 20 only checks that the files validate, and Task 21 tests the step structure.
- **Criterion 3:** Task 19 doesn't assert that a flagged item's work is all committed or that the next item starts from a clean target.
- **Integration requirement:** Task 29 tests item resume on a `tasks-plan` run but not on a `slices-plan` run.
- **D12 "ends with no commits" row:** no test asserts that `EmptyDiffError` gives `step_failed` plus the WARNING record.

Task 31's mapping step should pick these up, but listing them directly in Tasks 19, 20 and 29 would make that less dependent on the checkpoint.

### [NOTE] Task 2 doesn't say where the new helpers live

Both `branch_ops.py` (D5) and `actions/dispatch.py` (D4) use the work-count helper, but Task 2 doesn't name a module. To avoid a guess or an import cycle, name the file, most likely `pipeline/git_ops.py` next to `run_git`.

### [NOTE] The run lock may break existing `sq run` tests

Once Task 24 lands, any mutating `sq run` runs `git rev-parse --git-dir` first. Existing CLI or pipeline tests that run P-pipelines in a temp directory that isn't a git repo will start exiting 2. Task 24 should tell the implementer to find and update those tests, as Task 20 does for the step-list tests.

### [PASS] Every design criterion maps to a task, with no scope creep

Each criterion (SC1–17) and decision (D1–D12) traces to at least one task:
- **Branch work:** D5 and D6 in Tasks 4–7.
- **Keep on implement:** D4 in Task 9.
- **Source and ordering:** D2 and D3 in Tasks 10–12.
- **Flags and report:** D7 in Tasks 13–17.
- **Pipelines:** D1 and D10 in Tasks 19–21.
- **Reserved params and lock:** D11 in Tasks 22–24.
- **Item resume:** D8 and D9 in Tasks 25–30.
- **Docs and walkthrough:** Tasks 32–33.

The only task beyond the design is the CHANGELOG entry in Task 32, which is normal project upkeep. Items the design excludes are restated as out of scope.

### [PASS] Sequencing, test placement and commits

- The order follows the design's Development Approach, and there are no circular dependencies. Task 22's constants come before Task 25 uses them, and Task 23's lock comes before Tasks 24 and 26.
- Separate test tasks come directly after their implementation tasks (4→5, 11→12, 28→29), and the other tasks include their own tests.
- Commits fall at the end of each task, and quality-gate checkpoints sit at the end of Parts A, D and G.
- Task sizes are reasonable. Task 28 is the largest, but its tests are split out into Task 29.

### [PASS] No load test or CI wiring needed

The slice design states no performance or load NFR, so neither a `tests/load/` task nor a CI gating task is needed.

### Run Digest

- Response length: 6278 chars
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
- Duration: 53.1 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Responses

- **F001 (fixed):** Task 26 maps all three lock failures (held, `rev-parse` `GitEnvironmentError`, other `OSError`) to REJECTED and says only post-lock errors are HALTED. Task 28 maps a report-write `OSError` to HALTED. Task 24 gives `sq run` exit 2 for the same three lock failures. Tests added in Tasks 24, 26 and 29.
- **F002 (fixed):** `set_arch` removed from Task 3; it is a cf-op step with no `failure` key. Task 7 asserts the item fails before the branch action; Task 15 keeps the `step_failed` check.
- **F003 (fixed):** Task 20 tests the pause on exhaust for all four single-slice pipelines (criterion 12). Task 19 asserts criterion 3 and the D12 empty-diff row. Task 29 covers `slices-plan` as well as `tasks-plan`.
- **F004 (fixed):** Task 2 places the helpers in `pipeline/git_ops.py`.
- **F005 (fixed):** Task 24 tells the implementer to find mutating-pipeline tests that run outside a git repo and give them a repo or lock fixture.
