---
docType: review
layer: project
reviewType: tasks
slice: one-commit-per-planning-document-loops-collapse-their-own-round-commits
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261101
dateUpdated: 20261101
reviewedSha: b2a6d3424a6bea865d50966efe91e5c714627e04
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 100253
cachedTokens: 11118
cacheWriteTokens: 89131
completionTokens: 4126
durationSeconds: 33.4
costUsd: 0.399672
costBasis: provider
runId: run-20261101-p5-3954488f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md"
  - id: F002
    severity: pass
    category: sequencing
    summary: "Sequencing and commit distribution"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md"
  - id: F003
    severity: concern
    category: task-clarity
    summary: "`round_commit_params` source is ambiguous for the resumed path in 7.1/7.4"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:223-226"
  - id: F004
    severity: concern
    category: task-sizing
    summary: "Task 7 is overweight, and the `_target_from_params` refactor in 5.4 has no stated test"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:210-251"
  - id: F005
    severity: note
    category: task-clarity
    summary: "Minor underspecified edges"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:136"
---

# Review: tasks — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

- **Single commit after two revisions:** covered by 7.5 and 5.5.
- **Skip or single commit leaves history unchanged:** covered by 7.5.
- **Exhaustion accept, pause, fail and skip:** covered by 7.5.
- **Pause and resume, via more rounds or `--decision accept`:** covered by 7.5.
- **Each D3 refusal leaves history byte-identical:** covered by 5.3.
- **WARNING and INFO log lines once each:** covered by 6.2 (`caplog`).
- **`each` item rerun, retry and accept:** covered by 7.5.
- **Staged and unstaged edits preserved:** covered by 6.2.
- **Backup ref exists and points at the old head:** covered by 6.2.
- **Code loops never collapse:** covered by 3.2 and 7.5.
- **Findings-addressed gate unchanged:** covered by 7.5.
- **`sq review resolve` integration:** covered by the 6.2 reachability test, with the rationale stated in the task.
- **New modules under ~300 lines, ruff/pyright, CHANGELOG bullet:** covered by 8.1 and 8.2.

The walkthrough in task 9 is correctly labelled as evidence rather than a gate. I found no scope creep, and no NFR or load-test requirement applies to this slice.

### [PASS] Sequencing and commit distribution

The dependency order works: commit outputs (1), then ledger model (2), then open (3), then record and carry (4), then collapse checks and message (5), then collapse writes (6), then executor wiring (7). Each implementation task carries its own tests, and each task ends with a `**Commit**:` marker, so commits are spread across the work and not batched at the end. There are no circular dependencies.

### [CONCERN] `round_commit_params` source is ambiguous for the resumed path in 7.1/7.4

- **What 7.4 says:** it passes "the `round_commit_params` result already computed for the loop" to `collapse_loop_commits`.
- **Where it's computed:** only in 3.1, inside `open_ledger`, which doesn't return it.
- **Resumed path:** `carried_ledger` doesn't compute it either, so a junior implementer has no defined value to pass.
- **Failure behavior:** nothing says what happens if `round_commit_params` raises on resume. Task 3 returns `None` for the fresh path, but 7.1 and 7.4 don't say whether a resumed loop skips collapse.

Fix: add a 7.1 step stating that the executor computes `round_commit_params` once per loop invocation, on both the fresh and resumed paths. It should hand the result to `open_ledger` and to collapse, and the task should give the raise behavior.

### [CONCERN] Task 7 is overweight, and the `_target_from_params` refactor in 5.4 has no stated test

- **Task 7:** it combines four executor edits (7.1–7.4) with nine executor-level test scenarios in one commit. It touches `executor.py`, which is already well past the size guideline. A junior implementer is most likely to stall here.
- **Suggested split:** call sites 7.1–7.3 plus basic completed/skip tests as one commit, then 7.4 collapse-on-COMPLETED with the pause/resume, exhaustion and `each` scenarios as the next. This keeps test-with and spreads the commits.
- **5.4 refactor:** it changes `_target_from_params` in `actions/commit.py`, a file Task 1 also edits, to take params plus a round number. The refactor's only test is "existing commit tests still pass", which is acceptable. Say so explicitly in 5.4, and confirm Task 1's new tests exercise the refactored path.

### [NOTE] Minor underspecified edges

- **`cf_client` parameter:** 5.1 lists it in the `collapse_loop_commits` signature without saying what it is used for. Name its use, or drop it if `read_integration_target` and `subject_paths` don't need it.
- **Root commit:** 3.1 computes `base_sha = start_head^` via `git rev-parse`. If the phase commit is a root commit, that call fails. The task says nothing about the outcome, and the "unreadable" branch in 3.1 only covers `HEAD`. Add a one-line rule, for example an `unprovable` ledger.
- **Timeout fake in 6.2:** the slice says "no git mocks", while 6.2 injects a fake runner for the `update-ref` timeout. The task documents this as the single exception and `GitStateUnknownError` is not a `CollapseOutcome`, so it is defensible. It is worth a one-line note in the slice.
- **Changelog commit:** the Task 8 commit contains only a CHANGELOG bullet. Consider folding 8.1 into Task 7's commit so no commit stands alone for a one-line doc change. Task 9's commit is DEVLOG and status only, which is borderline against the "never a commit that only adds notes" rule, but it also updates slice status.

### Run Digest

- Response length: 5417 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 100253 / 11118 / 89131 / 4126 / not computed
- Duration: 33.4 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
