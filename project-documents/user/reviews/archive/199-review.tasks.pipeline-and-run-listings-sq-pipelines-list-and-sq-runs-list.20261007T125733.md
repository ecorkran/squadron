---
docType: review
layer: project
reviewType: tasks
slice: pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 3ed120e7961475a3293f746bef6f60579ab64221
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
durationSeconds: 31.8
runId: run-20261007-p5-f492c43d
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Task 36 walkthrough step 4 cannot be run read-only"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:393-396"
  - id: F002
    severity: concern
    category: task-scoping
    summary: "Task 25 is too large for one task"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:263-277"
  - id: F003
    severity: concern
    category: specification-gap
    summary: "Marker text for three `ResumeProblem` members is left to the implementer"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:285-287"
  - id: F004
    severity: concern
    category: test-with-pattern
    summary: "Implementation tasks 7–8 and 21–23 have no immediate tests"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:88-115"
  - id: F005
    severity: concern
    category: coverage
    summary: "Smaller gaps in verification and traceability"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:34"
  - id: F006
    severity: note
    category: process
    summary: "Task 1 and Task 36 follow the merge rule"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md:401"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md"
  - id: F008
    severity: pass
    category: sequencing
    summary: "Sequencing and checkpoints"
    location: "project-documents/user/tasks/199-tasks.pipeline-and-run-listings-sq-pipelines-list-and-sq-runs-list.md"
---

# Review: tasks — slice 199

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Task 36 walkthrough step 4 cannot be run read-only

Task 36 says to run walkthrough steps 3, 4 and 7 against `~/.config/squadron/runs` "read-only". Design step 4 executes `sq run --resume <run-id> --item <index> --decision retry`. That mutates real run state and reports, and it runs the executor against git. Following the task literally is impossible, or it modifies the developer's real runs. Step 4 should run against a scratch runs dir with a fixture batch run, or be marked as needing the PM's explicit approval on a named run. The task should also say what to do if no run with open items exists, since the design says "if one of them is…".

### [CONCERN] Task 25 is too large for one task

Task 25 bundles four separate test groups:
- filter and ordering tests;
- the four `ResumeProblem` tests with `caplog` assertions;
- the 300-run I/O-bounds test;
- the listing/resume parity test.

It also carries the lint gate and the commit. A junior AI could fail partway with no intermediate checkpoint. Split it into at least two tasks, for example filtering plus problems, then bounds plus parity. Task 22 likewise combines per-status helpers, a cached loader, and logging. It is acceptable, but it is the next candidate to split.

### [CONCERN] Marker text for three `ResumeProblem` members is left to the implementer

Task 26 specifies only `<pipeline unavailable>` and says to "choose analogous bracketed texts for the other three". The slice design also specifies only the one marker. User-visible strings for `NO_UNFINISHED_STEP`, `ITEM_RESUME_UNSUPPORTED` and `REPORT_UNREADABLE` are therefore invented at implementation time. Specify the three texts in the task (or the design), or state that the PM approves them in review.

### [CONCERN] Implementation tasks 7–8 and 21–23 have no immediate tests

Task 7 (create `item_eligibility.py`) and Task 8 (move `item_resume` onto it) are followed by their tests only in Task 9. Tasks 21, 22 and 23 (`run_listing` types, resolution and `list_run_summaries`) are untested until Tasks 24–25. The grouping is defensible because the parity tests need the full module. Still, Task 8 could run item-resume tests before moving on, and Task 23 should have at least a smoke test before the large test tasks.

### [CONCERN] Smaller gaps in verification and traceability

Three small items:
- **`no_args_is_help`:** Tasks 14, 18, 27 and 31 specify it, but no test covers that `sq pipelines`, `sq runs` or `sq agents` print help. Add one assertion per group.
- **CHANGELOG/DEVLOG:** Task 34 says technical detail goes to DEVLOG, but no task writes a DEVLOG entry.
- **Slice-design edits:** Task 35 edits the slice design to link the new issue numbers but has no commit. Task 36 is the only thing that would commit them, and its commit message ("finalize verification") will not describe them.

### [NOTE] Task 1 and Task 36 follow the merge rule

The breakdown creates the slice branch from the target and correctly defers review and merge to Phase 7, with no merge task. This matches the project git rules.

### [PASS] Success-criteria coverage is complete

Every functional and technical requirement maps to a task:
- **Pipeline listing:** grouping, shadowing and the enum are covered by Tasks 10–15.
- **Removed flag:** Tasks 16–17 cover `sq run --list` removal.
- **`sq agents list`:** Tasks 18–20 cover it, including the three messages and the slash command and skill.
- **Run listing:** Tasks 21–28 cover it, including each `ResumeProblem` with `caplog`, the 300-run bounds test, and the parity tests.
- **`wait`:** Tasks 29–32 cover `wait` with the exit-code mapping.
- **Docs and issues:** Tasks 33–35 cover docs, CHANGELOG and the three issues.

I found no scope creep. Every task traces to a design section.

### [PASS] Sequencing and checkpoints

`RUNNING_STATUS`, `RESUMABLE_STATUSES` and `first_unfinished_step_of` (Task 3) precede their consumers in Tasks 22 and 29. `STATUS_COLORS` (Task 12) precedes the renderers. Commits fall after Tasks 4, 6, 9, 11, 15, 17, 20, 25, 28, 30, 32 and 34. Each code part ends with the lint, type and test gate.

### Run Digest

- Response length: 5787 chars
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
- Duration: 31.8 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
