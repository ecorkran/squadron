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
reviewedSha: 95f439844d8ec94a9bb2da925de2c08083df4092
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
turns: 3
promptTokens: 99983
cachedTokens: 11118
cacheWriteTokens: 88861
completionTokens: 4414
durationSeconds: 36.4
costUsd: 0.401471
costBasis: provider
runId: run-20261101-p5-3954488f
squadronVersion: 0.24.12
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success criteria are fully covered"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:50-267"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Wrong task cross-reference in 4.3"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:123-124"
  - id: F003
    severity: concern
    category: scope
    summary: "Ledger value after collapse is unspecified (7.4)"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:216-217"
  - id: F004
    severity: concern
    category: testability
    summary: "Test seam rules are inconsistent between 6.2 and the \"no mocks\" rule"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:185-191"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 8.2 is probably already done, and 8.1 can add unplanned work"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:240-246"
  - id: F006
    severity: note
    category: task-size
    summary: "Task 7 is large but kept whole"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:197-236"
  - id: F007
    severity: note
    category: verification
    summary: "Live walkthrough depends on model behavior"
    location: "project-documents/user/tasks/202-tasks.one-commit-per-planning-document-loops-collapse-their-own-round-commits.md:256-267"
---

# Review: tasks — slice 202

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success criteria are fully covered

Each Functional, Technical and Integration requirement traces to a task:
- **Single resulting commit:** 7.5 and 9.1.
- **Skip and single-commit loops:** 7.5.
- **Exhaustion accept versus pause, fail or skip:** 7.5.
- **Pause and resume:** 7.5.
- **Each D3 refusal:** 5.3.
- **Item rerun, retry and accept:** 7.5.
- **Staged and unstaged edits preserved:** 6.2.
- **Backup ref:** 6.2.
- **Code loops never collapse:** 3.2 and 7.5.
- **Findings-addressed gate unchanged:** 7.5.
- **`sq review resolve` through the backup ref:** 8.1.
- **CHANGELOG, size limits and lint:** 8.3 and 8.4.

No task falls outside the design, so I found no scope creep. The slice states no NFR, so no load-test or CI-gating task is needed.

### [CONCERN] Wrong task cross-reference in 4.3

The 4.3 sub-item about an `each` item's ledger not leaking says "cover this in task 6 test". Task 6 covers collapse writes. The executor-level `each` rerun tests are in 7.5 (lines 229-231). A junior implementer would look in the wrong place. Change the reference to 7.5, or delete the sub-item, since 7.5 already covers it.

### [CONCERN] Ledger value after collapse is unspecified (7.4)

7.4 says the returned ledger is "the post-collapse one only if the collapse succeeded". The slice design never defines a post-collapse ledger. It doesn't say whether `commits` becomes `[new]` or whether `base_sha` changes. A COMPLETED loop is never resumed, so this step has no consumer. Either drop it and attach the ledger unchanged, or state the exact value and add a test for it. As written, a junior has to invent behavior.

### [CONCERN] Test seam rules are inconsistent between 6.2 and the "no mocks" rule

The CAS-race test allows "a hook point or patching only the seam between the check function and the write function". The `GitStateUnknownError` test then calls its `run_git` seam "the one permitted test seam". That is two seams, and the Context Summary says there are no git mocks. Make the CAS race seam-free by splitting `collapse_loop_commits` into a check function and a write function. Task 5 already separates the checks from the writes in 6.1. The race test can then call the write function with a stale `old_head` after moving HEAD, with no patching. Then say explicitly that the timeout-injecting `run_git` seam is the only one.

### [CONCERN] Task 8.2 is probably already done, and 8.1 can add unplanned work

8.2 is a conditional "check first" step. The recent commit `1910eaed` ("record slice 202 loop-collapse in the 180 architecture") suggests the architecture update is already done. Replace 8.2 with a one-line check inside 8.4, or remove it, so no checklist item is a probable no-op. The 8.1 branch for the case where `sq review resolve` ignores the backup ref says to file an issue. That is acceptable, but the Integration Requirement then stays unmet. State in 9.2 that this criterion counts as unmet until the issue is resolved. Otherwise the 9.2 "every criterion met" gate is ambiguous.

### [NOTE] Task 7 is large but kept whole

Task 7 has five implementation sub-items and nine test bullets at effort 4, and it touches a very large `executor.py`. Splitting the tests from the call sites would break the test-with pattern, so keeping it whole is defensible. If it proves unwieldy, a natural split is 7.1–7.4 plus the basic completed-loop and skip tests, then the pause/resume and `each`-rerun tests. Also note that 7.1 detects a resume by "`start_iteration > 1` or the `--decision accept` resume path". Confirm that this cannot misclassify a loop paused before its first round. Otherwise that loop would open a fresh ledger and lose the phase commit.

### [NOTE] Live walkthrough depends on model behavior

Steps 1 and 3 of 9.1 need a real run where reviews actually fail twice, or where a strict model exhausts `max-revisions=1`. That is non-deterministic. The 7.5 executor tests already cover the same paths deterministically, so 9.1 is a sanity check. If the live run doesn't reproduce a revision loop, record that in the DEVLOG rather than treating it as a blocker.

### Run Digest

- Response length: 5549 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 99983 / 11118 / 88861 / 4414 / not computed
- Duration: 36.4 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
