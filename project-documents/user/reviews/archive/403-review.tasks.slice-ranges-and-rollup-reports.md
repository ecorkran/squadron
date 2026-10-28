---
docType: review
layer: project
reviewType: tasks
slice: slice-ranges-and-rollup-reports
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261027
dateUpdated: 20261027
reviewedSha: 4d9014a32a324fe36fb9ae0e3deccbeeee5a8e1b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 112077
cachedTokens: 8820
cacheWriteTokens: 103253
completionTokens: 4802
durationSeconds: 41.2
costUsd: 0.462673
costBasis: provider
runId: run-20261028-p5-6a61c3b7
squadronVersion: 0.24.6
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria 1–10 each trace to implementation and test tasks"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md"
  - id: F002
    severity: concern
    category: coverage
    summary: "Nothing implements the real `commit_exists` check for the missing-landing failure mode"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:262-264"
  - id: F003
    severity: concern
    category: task-sizing
    summary: "Task 41 is under-scoped for its effort rating"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:292-296"
  - id: F004
    severity: concern
    category: proportionality
    summary: "Per-builder smoke tests in Task 8 go beyond what the criteria need"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:94"
  - id: F005
    severity: note
    category: test-coverage
    summary: "No test covers a failed `node_modules` symlink"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:196-203"
  - id: F006
    severity: note
    category: consistency
    summary: "The `git_utils` approach differs from the design text, and the divergence is recorded"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:39"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit cadence"
    location: "project-documents/user/tasks/403-tasks.slice-ranges-and-rollup-reports.md:47-323"
---

# Review: tasks — slice 403

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria 1–10 each trace to implementation and test tasks

- Criteria 1 and 3: Tasks 8–10 and 13–14.
- Criterion 2: Tasks 11–14.
- Criteria 4 and 5: Tasks 24, 25, 28 and 29.
- Criterion 6: Tasks 26–27.
- Criterion 7: Tasks 33–34 and 36–37.
- Criterion 8: Tasks 36–37.
- Criterion 9: Tasks 31–32 and 35.
- Criterion 10: Tasks 36–39.

Every task cites a decision (D1–D10), and I found no scope creep. The Technical Requirements fixture list (all eight repo shapes, plus the fresh clone) matches Tasks 8, 10 and 12. The `docs/COMMANDS.md` and CHANGELOG requirement is Task 43.

### [CONCERN] Nothing implements the real `commit_exists` check for the missing-landing failure mode

- Task 36 makes `commit_exists` an injected dependency of `build_slice_report`. Task 37 tests it only with a fake.
- The design's failure-mode table (line 169) requires a `git cat-file -e` check for a stored landing whose commit is gone.
- Task 41 wires "the real `take_snapshot_at`" into `report slice` but never mentions the real `commit_exists`. No task writes the `git cat-file -e` call, so it would be wired by whoever happens to notice.
- A `run_git` returning `None` must not be read as "commit missing". It should follow the same `None` rule as the resolver.
- Fix: add to Task 41, or to a small helper in Task 36, the `commit_exists` implementation. State how `None` and non-zero exits are distinguished, with one test.

### [CONCERN] Task 41 is under-scoped for its effort rating

Task 41 is rated Effort 2, but it bundles several pieces of work in `metrology_quality.py`, which Task 15 already created:
- three commands, each with `--cwd` and `--json`;
- `record_slice_ranges` wiring and the real `take_snapshot_at`;
- the `commit_exists` wiring from the previous finding;
- the `rev-list --first-parent` call with its error path;
- a rewrite of the `report` group help text in `metrology.py`.

It carries a ~300-line cap on a file that already holds `slice-ranges`. Split it into `report slice` and `report project|history`, or rate it Effort 3 and name the helper module up front.

### [CONCERN] Per-builder smoke tests in Task 8 go beyond what the criteria need

Task 8 asks for "a smoke test per builder asserting `git log --oneline` length", which is eight tests. Tasks 10, 12 and 14 exercise every builder with stronger assertions, so a builder that is broken fails there. Drop the smoke-test requirement, or keep a single parametrized test.

### [NOTE] No test covers a failed `node_modules` symlink

Task 24 specifies that a symlink failure raises `SnapshotExportError`, and criterion 11 says every failure-mode row behaves as stated. Task 25 only tests that the symlink is present or absent (item 8). Add one case with a monkeypatched `os.symlink` raising `OSError`, asserting the error, the ERROR record and temp-directory removal. It reuses the setup of item 7.

### [NOTE] The `git_utils` approach differs from the design text, and the divergence is recorded

- The task file's recorded decision adds `parse_slice_branch` and `parse_fork_point` and drops the `first_parent` argument.
- The design's Component Structure (line 90) and Technical Requirements (line 351) still say `first_parent`, "helpers made public", and "no growth beyond the rename, pattern function and `first_parent` argument".
- The refinement is sound and is documented. Task 44's diff check is aligned with the task file, not the design.
- Optionally, update the design text so a later reader isn't confused.

### [PASS] Sequencing, test-with pattern and commit cadence

- Dependencies run in order: models, store, resolver, `record_slice_ranges`, CLI, preflight split, `environment_root`, export, lockfile gate, `take_snapshot_at`, compare and reviews, reports, then docs and walkthrough. No circular dependencies.
- Each implementation task is followed by its tests.
- There are 14 commit checkpoints, spread across the file rather than batched at the end.
- No task writes a merge or push.

### Run Digest

- Response length: 5080 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 112077 / 8820 / 103253 / 4802 / not computed
- Duration: 41.2 s
- Cost: $0.46 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
