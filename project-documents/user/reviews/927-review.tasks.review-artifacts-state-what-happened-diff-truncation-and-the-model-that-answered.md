---
docType: review
layer: project
reviewType: tasks
slice: review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md
aiModel: claude-opus-5-5
status: complete
dateCreated: 20260926
dateUpdated: 20260926
reviewedSha: 04061e85e5e1b45127cd462347fbece8e1bd3692
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 8
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "S.1 reads the integration branch, then forks from `main` anyway"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:42-43"
  - id: F002
    severity: concern
    category: commit-checkpoints
    summary: "W.2 can change `snapshot.py` but has no code commit of its own"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:191-200"
  - id: F003
    severity: note
    category: coverage
    summary: "SC4's exit code and checkpoint behavior are only checked in the walkthrough"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:120-123"
  - id: F004
    severity: note
    category: coverage
    summary: "Parity between `sq review code` and `sq run review` is checked by hand only"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:186-189"
  - id: F005
    severity: note
    category: consistency
    summary: "B.1's `or 0` goes against the file's own rule, but it's correct here"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:109"
  - id: F006
    severity: pass
    category: coverage
    summary: "Every success criterion traces to a task"
    location: "project-documents/user/slices/927-slice.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:284-311"
  - id: F007
    severity: pass
    category: sequencing
    summary: "Order and size of tasks"
    location: "project-documents/user/tasks/927-tasks.review-artifacts-state-what-happened-diff-truncation-and-the-model-that-answered.md:46-182"
  - id: F008
    severity: pass
    category: nfr
    summary: "No load test needed"
    location: "unverified"
---

# Review: tasks — slice 927

**Verdict:** CONCERNS
**Model:** claude-opus-5-5

## Findings

### [CONCERN] S.1 reads the integration branch, then forks from `main` anyway

S.1 runs `cf config get git.integration_branch` and then does `git checkout -b 927-slice... main`, so the value it just read is ignored. If the key is set, this forks from the wrong base, which breaks the CLAUDE.md branch rule. Write the checkout as `git checkout -b <branch> <target>`, where the target is the value read on line 42 (or `main` if it's empty).

### [CONCERN] W.2 can change `snapshot.py` but has no code commit of its own

If W.2 finds a false substitution, it edits `src/squadron/models/snapshot.py` and `tests/models/test_snapshot.py`. The next commit is W.3's `docs: complete slice 927`, so that code change would go in under a docs commit and with no ruff/pyright step. Add a conditional commit to W.2 (`fix: accept <profile> answering-model form in answers_as_requested`), preceded by ruff, pyright, and `tests/models`.

### [NOTE] SC4's exit code and checkpoint behavior are only checked in the walkthrough

SC4 includes "exit code / checkpoint behavior of CONCERNS". B.3 tests `result.verdict == CONCERNS`, but nothing automated checks the CLI exit code or that the pipeline stops at `on-concerns` on an imposed verdict. Both follow from the verdict, so this is probably fine, and W.1 step 4 checks the pause by hand. One CLI exit-code assertion in B.3 would cover it for good.

### [NOTE] Parity between `sq review code` and `sq run review` is checked by hand only

The integration requirement is covered by the shared-code-path design plus W.1 steps 1 and 4. C.9 tests the pipeline's `metadata["model"]` but not that the pipeline writes `diffTruncated`. That's acceptable given the design's point that there's only one rendering path.

### [NOTE] B.1's `or 0` goes against the file's own rule, but it's correct here

The constraint on line 29 says to never use `or 0` for counts, but B.1 uses `(tool_calls_made or 0)`. D4 says outright that None counts as zero, so the code is right. Add a one-line comment pointing at D4 so a junior agent doesn't "fix" it.

### [PASS] Every success criterion traces to a task

- SC1–3 → A.1–A.5
- SC4–6 → B.1–B.3
- SC7 → B.4
- SC8 → C.1–C.4
- SC9–11 → C.6–C.8
- SC12 → C.9
- The byte-identical snapshot requirement is pinned in A.4 and C.8.
- `collect_turn` folding → C.5
- The captured model ids from D9 → W.2
- CHANGELOG and DEVLOG → W.3

Nothing in the tasks goes beyond the design.

### [PASS] Order and size of tasks

M.2 comes before M.4, which uses it. Part B follows Part A. B.3 calls the cap after `diff_injection` and the tool counts are assigned. C.5 comes before C.6. No task is bigger than 2/5 effort, and each one says what counts as done.

### [PASS] No load test needed

The design states no performance or scale requirement, so no `tests/load/` task or CI wiring is needed.

### Run Digest

- Response length: 4590 chars
- Response is newline-free: no
- Tool calls made: 8
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
