---
docType: review
layer: project
reviewType: tasks
slice: effort-calibration-and-producer-model-effectiveness
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261015
dateUpdated: 20261015
reviewedSha: 7e1c6fe22b7a021fd995e8306938e4a3471164ad
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 99815
cachedTokens: 8724
cacheWriteTokens: 91087
completionTokens: 6562
durationSeconds: 52.7
costUsd: 0.431517
costBasis: provider
runId: run-20261015-p5-8a59ee89
squadronVersion: 0.22.0
findings:
  - id: F001
    severity: concern
    category: coverage-gap
    summary: "Success Criterion 3 (slice 173, no markers) has no implementing or testing task"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:154-159"
  - id: F002
    severity: concern
    category: process
    summary: "Commit checkpoints are fewer than the project rule requires"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:29"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 1 puts the grouping check after the code that depends on it"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:40-42"
  - id: F004
    severity: concern
    category: unverified-value
    summary: "The review-lower-bound cutoff date is not in the design"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:144"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Tasks restate large parts of the design, which contradicts the task file's own stated approach"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:20"
  - id: F006
    severity: concern
    category: task-sizing
    summary: "Task 23 is too large for one task"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:222-230"
  - id: F007
    severity: concern
    category: code-structure
    summary: "Renderer file size is not controlled"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:23"
  - id: F008
    severity: concern
    category: test-coverage
    summary: "Test coverage gaps against the design's technical requirements"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:180-186"
  - id: F009
    severity: note
    category: error-handling
    summary: "`--since` format validation is unspecified"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:206"
  - id: F010
    severity: pass
    category: coverage
    summary: "Remaining success criteria are traceable and ordered correctly"
    location: "project-documents/user/tasks/176-tasks.effort-calibration-and-producer-model-effectiveness.md:35-295"
---

# Review: tasks — slice 176

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Success Criterion 3 (slice 173, no markers) has no implementing or testing task

Criterion 3 requires `sq stats slice 173` to read task groups as `unavailable`. The design uses three states: `unavailable` (window `NONE`), `unknown` (marker not found), and no subjects at all. Task 15 covers the first two, and Task 17 maps only window `NONE` to `unavailable`.
- A slice with a branch and a task file whose tasks prescribe no commit subjects is covered by neither task. Slice 173 is likely this case, since Task 8 asserts its fixture has no subjects.
- Task 8 checks that the 173 fixture parses to tasks with no subjects, but no test checks what the report shows for it.

Add a step to Task 15 or 17 saying what groups are when no task has a commit subject. Add a matching case to Task 16 or 18.

### [CONCERN] Commit checkpoints are fewer than the project rule requires

The project rule is "Git add and commit from project root at least once per task". Line 29 says "Commit on the slice branch where a task says so". Only 9 tasks carry commits, and they sit at the ends of groups (4, 10, 16, 20, 22, 26, 29, 30, 31). Tasks 1–3, 5–9, 11–15 and 27–28 have no commit step. Add a commit step to each task, or at least to each implementation/test pair. Alternatively, record an explicit PM-approved exception.

### [CONCERN] Task 1 puts the grouping check after the code that depends on it

The serializer step (line 40) assumes `prior_rounds` can be split per round. The check of whether `StepResult.prior_rounds` is flat (`executor.py:226`) comes last, at line 42, and may force an executor change. Move the check to the first step after branch creation. The executor change is a separate behavior change touching `executor.py:643`, so give it its own step and commit.

### [CONCERN] The review-lower-bound cutoff date is not in the design

The task hardcodes `20261013` as the date slice 941 shipped. The design says only "when the earliest round predates 941's merge" and gives no date. This is a guessed value in a constant, which the project rules forbid. The rationale "941's branch exists only in this repo" is also unclear. Have the task say where the date comes from (for example, the merge commit date of 941, read by the implementer) and require the implementer to confirm it with the PM if it can't be found.

### [CONCERN] Tasks restate large parts of the design, which contradicts the task file's own stated approach

Line 20 says decisions live in the design and "Tasks reference them and do not repeat them". Several tasks copy them nearly in full:
- Task 7 lists the D4 parse formats.
- Task 15 reproduces D5 rules 1–5.
- Task 23 restates the D8 unit, key and metric definitions.
- Task 13 restates D6.

Duplicated rules can drift from the design. Replace them with "per D4 / D5 / D8" and keep only the choices the design leaves open. The 31-task count (about 14 of them test tasks) is high for an Effort 3/5 slice. Task 5's test and Task 6's fixture copying could fold into the tasks that use them.

### [CONCERN] Task 23 is too large for one task

Task 23 covers four things:
- unit extraction (phase step plus loop pairing)
- config-key derivation
- six aggregate metrics
- exclusion counting with footer flags, plus the JSON output

That is too much for a junior AI in one pass. Split it into unit/key extraction and aggregation/exclusions, each followed by its tests. Task 31 is similarly overloaded: validation, D9 mapping, grep audits, a live walkthrough and issue comments.

### [CONCERN] Renderer file size is not controlled

`cli/stats_views.py` is already 242 lines. Task 3 adds a round column, a row note and JSON fields to it. Task 29 then adds the `runs` renderer. That likely exceeds the ~300-line guideline. Task 27 guards `usage_report.py` with a size check, but nothing guards `stats_views.py` or `cli/commands/stats.py`, which gain four subcommands. Move the `runs` renderer to its own module, as was done for the other reports, or add a size check.

### [CONCERN] Test coverage gaps against the design's technical requirements

- The design requires a git call-count assertion for both `slice` and `slices`. Task 20 asserts it for `slices`. Task 18 has no equivalent for `slice_effort_report`.
- The D9 row "unreadable run file" is tested for `runs` (Task 28) but not for `producers` (Task 24), although Task 23 produces that footer.
- The D9 empty-state row "no completed slices" is tested at the CLI (Task 22) but not for `slices_effort_report` (Task 20).

Task 31's D9 row-to-test mapping would expose these. Add the cases now.

### [NOTE] `--since` format validation is unspecified

Task 21 accepts `--since YYYYMMDD` but doesn't say what happens on malformed input. The project forbids silent fallbacks, so add an explicit error and exit 1. Add a test in Task 22.

### [PASS] Remaining success criteria are traceable and ordered correctly

- **Criterion 1:** Tasks 1–4.
- **Criterion 2:** Tasks 11–17, 21 and the Task 31 walkthrough.
- **Criteria 4–5:** Tasks 6–10 and 19–22.
- **Criterion 6:** Tasks 23–26.
- **Criterion 7:** Tasks 27–29.
- **Criterion 9:** no-write assertions in Tasks 22, 26 and 29.

Dependencies run forward only, with no cycles: Task 3 follows Task 1, Task 13 uses Task 5, Task 17 uses Task 3, and the Task 12 fixture feeds Tasks 12–20. Each implementation task is followed by its tests. The design states no NFR, so no load test or CI gating task is needed. There is no scope creep: every task traces to a design decision or success criterion.

### Run Digest

- Response length: 7084 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 99815 / 8724 / 91087 / 6562 / not computed
- Duration: 52.7 s
- Cost: $0.43 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
