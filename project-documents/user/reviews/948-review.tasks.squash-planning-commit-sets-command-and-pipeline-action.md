---
docType: review
layer: project
reviewType: tasks
slice: squash-planning-commit-sets-command-and-pipeline-action
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261025
dateUpdated: 20261025
reviewedSha: 26a430bad34992d8a5d84d40b2af0636227a0517
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 91674
cachedTokens: 50606
cacheWriteTokens: 41064
completionTokens: 5227
durationSeconds: 43.3
costUsd: 0.231995
costBasis: provider
runId: run-20261025-p5-a6068cdc
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Coverage of slice scope, decisions and test list"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:47-199"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit checkpoints"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:62-183"
  - id: F003
    severity: concern
    category: completeness
    summary: "`SquashPlan` contents are underspecified: nothing in T2 records the pre-rewrite tree id"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:64-81,110-116"
  - id: F004
    severity: concern
    category: test-design
    summary: "Test fixtures are local to one test file but needed by three others"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:84,107,120,142,164"
  - id: F005
    severity: concern
    category: test-design
    summary: "T15 asserts `metr` is absent from `sq --help`, which a substring check cannot do"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:197"
  - id: F006
    severity: concern
    category: scope
    summary: "Architecture scope uses `--plan`, which the slice design does not include"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:39,71,131-132,152"
  - id: F007
    severity: concern
    category: completeness
    summary: "D4 \"says so\" on tag reuse is not specified in any output"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:102,112,134-137"
  - id: F008
    severity: note
    category: test-coverage
    summary: "\"Git cannot run\" failure mode has no test"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:79,96-108"
  - id: F009
    severity: note
    category: proportionality
    summary: "Proportionality"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md:180-183"
---

# Review: tasks — slice 948

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Coverage of slice scope, decisions and test list

The slice design has no numbered success criteria, so I used its Technical Scope, D1–D7, Failure Modes and Tests list instead. Each maps to a task:
- Path-set extraction: T1.
- Run detection (D1, D2): T2 and T3.
- Refusals (D3): T4 and T5.
- Rewrite, backup tag, survivor, restore and recovery text (D3–D5): T6 and T7.
- Command with `--dry-run`: T8 and T9.
- Action, step and prompt-only rendering: T10 and T11.
- Pipeline placement (D6): T12 and T13. This includes the batch pipelines the design deferred to the breakdown.
- Part B (D7): T15.
Every task traces to the slice, so I found no scope creep other than the architecture-flag decision below.

### [PASS] Sequencing and commit checkpoints

Dependencies run one way, from T1's extraction through T2, T4 and T6 into the command, the action and the pipelines. The `_check_refusals` stub in T2 is resolved by T4. Each implementation task is followed immediately by its test task, and commits land at T1, T3, T5, T7, T9, T11, T13, T14 and T15. They are spread through the file, not batched at the end. Part B is its own commit, as the design asks. No merge task appears, which follows the git rules.

### [CONCERN] `SquashPlan` contents are underspecified: nothing in T2 records the pre-rewrite tree id

T6 compares `HEAD^{tree}` with "the plan's tree id". The `plan_squash` steps in T2 (items 1–7) never read `HEAD^{tree}`. They also don't name the other fields `apply_squash` needs: the parent sha of the oldest commit, the survivor sha, and the commit list for the dry run. "Carrying what the dry run prints and what `apply_squash` needs" leaves a junior to guess. Add one line to T2 listing the `SquashPlan` fields, including the tree id read at plan time. T7 case 4 depends on that field existing.

### [CONCERN] Test fixtures are local to one test file but needed by three others

T3 defines the "write a slice's design, review and DEVLOG files at the paths `subject_paths` returns and commit them" helper locally in `test_squash_plan.py`. T5 reuses it, but T7 (`test_squash_apply.py`), T9 (`tests/cli/`) and T11 (`tests/pipeline/actions/`) each need the same repo-building setup and don't say where it comes from. A junior will likely copy it three times. Say in T3 that the helper goes in a shared module, such as a `tests/pipeline/` helper or `conftest.py`, and that T7, T9 and T11 import it.

### [CONCERN] T15 asserts `metr` is absent from `sq --help`, which a substring check cannot do

`metr` is a substring of `metrology`, so `"metr" not in help_output` always fails. The task should say to match a whole-word or line-start token. Alternatively, it can inspect `app.registered_groups` for the `hidden` flag.

### [CONCERN] Architecture scope uses `--plan`, which the slice design does not include

The design's CLI scope is `sq squash <subject> --slice N`, with `architecture` listed as a subject. The task breakdown adds `--plan N`, a two-way scope rule in `check_squash_scope`, a conditional default for the `slice` key, and architecture-specific test cases in T3 and T11. The reasoning is sound, since the architecture target is initiative-scoped. It does add surface, and no built-in pipeline uses it. Either confirm this is intended and update the slice design's Technical Scope to match, or drop architecture support from this slice and leave it to the Project Manager. The breakdown records it as a "decision made in this breakdown", but the slice design should not contradict its tasks.

### [CONCERN] D4 "says so" on tag reuse is not specified in any output

D4 says a rerun on the same HEAD finds the tag present "and says so". T6 only skips creation, and T8's squash output doesn't mention a reused tag. T7 case 5 tests only that no second tag is created. Add a line to T8's output, or a log message in T6, saying the existing tag was reused, and assert it in T7 case 5.

### [NOTE] "Git cannot run" failure mode has no test

Failure Modes lists "git cannot answer", which T2 item 7 turns into `GitEnvironmentError`. The design's `caplog` assertions name only the commit-failure, tree-mismatch and root-commit cases, so the breakdown meets what the design requires. A single test with a non-existent cwd would cover it cheaply, if wanted.

### [NOTE] Proportionality

Sixteen tasks in one file is acceptable for three new modules, a pipeline step and a second mini-feature. T10 is the largest task, touching 5 to 6 files, but it follows the existing `branch` pattern and is readable as written. T13's `sq run P4 --dry-run` test adds a second pipeline-level check. It is justified by the design's "pipeline `--dry-run` lists the step and runs no git", so I don't flag it as overweight.

### Run Digest

- Response length: 6020 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 91674 / 50606 / 41064 / 5227 / not computed
- Duration: 43.3 s
- Cost: $0.23 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
