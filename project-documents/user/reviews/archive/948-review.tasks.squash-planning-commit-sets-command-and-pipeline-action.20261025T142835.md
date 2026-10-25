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
reviewedSha: 495f7f0decce9622755eaad3183424732f693aa5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 166710
cachedTokens: 75723
cacheWriteTokens: 90981
completionTokens: 3415
durationSeconds: 28.6
costUsd: 0.418571
costBasis: provider
runId: run-20261025-p5-a6068cdc
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Slice scope and decisions D1–D7 map to tasks"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and test-with pattern hold"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md"
  - id: F003
    severity: concern
    category: consistency
    summary: "D5 in the slice design contradicts the task breakdown and is left uncorrected"
    location: "project-documents/user/slices/948-slice.squash-planning-commit-sets-command-and-pipeline-action.md:71"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Task file is overweight for an Effort 3 slice"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md"
  - id: F005
    severity: concern
    category: task-size
    summary: "T4 is large and mixes detection with five refusal paths"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md"
  - id: F006
    severity: note
    category: scope
    summary: "Part B test location and Part A architecture decisions"
    location: "project-documents/user/tasks/948-tasks.squash-planning-commit-sets-command-and-pipeline-action.md"
  - id: F007
    severity: note
    category: coverage
    summary: "No NFR or load-test requirement"
    location: "unverified"
---

# Review: tasks — slice 948

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Slice scope and decisions D1–D7 map to tasks

Every in-scope item in the slice has a task:
- Path-set extraction: T2 and T3.
- Run detection and refusals (D1–D3): T4 and T5.
- Rewrite, backup tag and restore (D3, D4): T6 and T7.
- `sq squash` with `--dry-run`: T8 and T9.
- Action, step and prompt-only renderer: T10 and T11.
- Pipeline placement (D6): T12 and T13.
- Part B `sq metr` (D7): T15, as its own commit.

Each test case the slice's Tests section lists appears in T5, T7, T9 or T11. That includes the real-git rule, the `caplog` assertions for commit failure, tree mismatch and root commit, and the action failing the step on refusal and succeeding on a no-op. No success criterion is left without a task.

### [PASS] Sequencing and test-with pattern hold

The tasks run in order: extraction, plan, apply, CLI, action and step, pipelines, docs, then Part B. There are no circular dependencies. Each implementation task is followed by its test task. Commits are spread across T3, T5, T7, T9, T11, T13, T14 and T15, not batched at the end. No merge task is written, which is correct under the project's Phase 7 rule. T12 checks that the batch pipelines `slices-plan` and `tasks-plan` use `commit_each_iteration: true` per slice, and the YAML confirms it.

### [CONCERN] D5 in the slice design contradicts the task breakdown and is left uncorrected

D5 says the survivor's date becomes the squash time, shown as the author date. The task file's Context Summary says `git commit -C` keeps the author date and only the committer date changes. It adds no code and asserts only message and author in T7. That is the right call, but the slice design still states the incorrect behavior and no task fixes it. An implementer reading the design could add date-rewriting code. Add a small task step, for example in T14 or T7, to correct D5 in the slice design. Alternatively, note in T6 that D5's date remark is superseded.

### [CONCERN] Task file is overweight for an Effort 3 slice

The slice is rated Effort 3/5, but the breakdown has 16 tasks, 7 of which are test tasks with long case lists (T5 has 10 cases). Several tasks dictate detail the slice does not need.
- **Merge T2 and T3.** T2 has no commit of its own, so it already depends on T3's commit. Combine them into one extract-and-test task.
- **Cut from T13.**
  - The "confirm the parity test still passes" step is already covered by T12's success criterion.
  - The `on_exhaust: checkpoint` executor-pause test and the `sq run P4 --dry-run` test are the heaviest items. D6 asserts both behaviors, but neither is a distinct success criterion. Keep one of them, or fold it into T11.
- **Trim T5.** Cases 9 and 10 (backup-tag reuse and "HEAD unchanged after every case") overlap with T7's tag tests. Keep case 10 as a shared assertion helper, not a separate case.
- **Merge T1 and T16.** The setup task and the validation task could also be folded into neighbors.

### [CONCERN] T4 is large and mixes detection with five refusal paths

T4 (Effort 4) defines the error types, the dataclasses and the tag-name function. It also implements the run walk and trim, and five refusal checks. It then suggests splitting into a helper module if the file grows past 300 lines, which defers a size decision to the implementer. A junior AI would be better served by a firm split. T4a covers types, tag name and run detection. T4b covers refusals as a `_check_refusals` helper, with its own tests (the T5 cases 8–9). `squash.py` would then also hold `apply_squash` without getting near the file-size limit.

### [NOTE] Part B test location and Part A architecture decisions

`tests/metrology/test_cli.py` exists, so T15's test target is valid. The architecture `--plan N` option and the batch-pipeline additions go beyond the slice's `--slice N` wording. D6 and the Technical Scope delegate both choices to the breakdown, so this is not scope creep. The Context Summary records the decisions.

### [NOTE] No NFR or load-test requirement

The slice states no NFR, so no `tests/load/` task or CI gating task is needed.

### Run Digest

- Response length: 4917 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 166710 / 75723 / 90981 / 3415 / not computed
- Duration: 28.6 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
