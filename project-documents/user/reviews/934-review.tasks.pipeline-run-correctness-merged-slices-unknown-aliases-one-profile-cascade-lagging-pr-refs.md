---
docType: review
layer: project
reviewType: tasks
slice: pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: 5431d67f5b97df851569f0b83c8d33ff8301b364
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
durationSeconds: 42.4
runId: run-20261007-p5-56b33e7c
squadronVersion: 0.20.1
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "Success-criteria coverage is complete"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md"
  - id: F002
    severity: pass
    category: process
    summary: "Test-with pattern and commit cadence"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Suppression is wired before the adjustment line exists"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md (Tasks 19, 22b, 25a–25c)"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 22a leaves the lag branch undefined"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md (Tasks 21, 22a)"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "D10 `cat-file` timeout row has no test"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md (Task 21)"
  - id: F006
    severity: note
    category: implementation-detail
    summary: "`logger.exception` outside an exception context"
    location: "src/squadron/pipeline/git_ops.py#GitStateUnknownError"
  - id: F007
    severity: note
    category: scope
    summary: "Task 24b sweep is open-ended"
    location: "project-documents/user/tasks/934-tasks.pipeline-run-correctness-merged-slices-unknown-aliases-one-profile-cascade-lagging-pr-refs.md (Task 24b)"
---

# Review: tasks — slice 934

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Success-criteria coverage is complete

The #188 criteria map to Task 13 (predicate, git-failure rows, temp repos), Task 15 (selection, WARNING, `cwd` test) and Task 16 (resume and reconcile). The #184 and #175 criteria map to Tasks 2–6 (shared module, parity test), Tasks 7–9 (template lookup, unknown template, per-action profile source) and Tasks 10–11 (`_classify_for_run`, dry-run, byte-identical artifact). The #186 criteria map to Tasks 18–25c: lagging fixture with the API sha absent locally, source-naming errors, a single printed failure, and fetch timeouts. Issue closure is covered in the Notes and Task 29. Every task traces to a design decision or success criterion.

### [PASS] Test-with pattern and commit cadence

Every code task carries its own tests and a semantic commit. Validation tasks 12, 17 and 26 close each part, so commits are not batched at the end. No merge task appears, which follows the git rules. The lettered splits of Tasks 22, 24 and 25 keep each task a manageable size. Task 21 and Task 8 are the largest tasks, and both are still acceptable.

### [CONCERN] Suppression is wired before the adjustment line exists

Tasks 19 and 22b tag the base fast-forward and head-lag WARNINGs with `RENDERED_BY_CALLER`. Task 25a then makes `sq review pr` drop tagged records below `-vv`. Task 25c is the task that prints the adjustment line that is meant to replace those records. Between 25a and 25c the user sees neither the WARNING nor the adjustment line. That includes the #131 base fast-forward notice that is visible today, which contradicts D8's "nothing visible today disappears". Move 25c before 25a, or merge 25c into 25a and 25b, so the replacement output lands in the same commit as the suppression.

### [CONCERN] Task 22a leaves the lag branch undefined

Task 22a says "Ancestor → lag (handled in 22b)" but does not say what the code does in the lag case before 22b lands. The committed intermediate state could silently build a range on the stale PR-ref sha, which the design forbids. State the interim behaviour, for example raising `RefMovedSinceResolutionError` or a `NotImplementedError` until 22b. Alternatively fold 22a and 22b into one task. Task 21 also adds the `head_fallback_sources` argument to `fetch_and_range`, but nothing calls the helper until 22a. Say explicitly that the `fetch_and_range` signature change belongs in 22a and 23, so the commit does not leave a dead parameter.

### [CONCERN] D10 `cat-file` timeout row has no test

D10 says a timeout on `cat-file -e <sha>^{commit}` raises `HostCommandTimeoutError`. The fetch-timeout row is covered, since Task 21 records a fallback timeout and Task 20 covers the primary fetch. The Task 21 test list has no case for the `cat-file` timeout. The project's Failure-Mode Enumeration rule requires a test for each failure-mode row. Add that case, plus the non-zero `cat-file` exit meaning "absent" that produces the DEBUG record.

### [NOTE] `logger.exception` outside an exception context

Task 13 requires `logger.exception` when `run_git` returns `None` on a timeout or spawn failure. `run_git` returns `None` rather than raising, so no exception is active there. The log record would then carry `NoneType: None` instead of a traceback. The test should assert the ERROR level, the command and the stderr text. The implementer may use `logger.error` there, since the exception-handling rule only applies to `try/except` blocks. `GitStateUnknownError` already exists, so Task 13 correctly reuses it and does not create it.

### [NOTE] Task 24b sweep is open-ended

The task asks for every pre-raise WARNING in `refs.py` and the GitHub adapter to be tagged, with only "e.g." examples. The grep check at the end (every `RENDERED_BY_CALLER` site precedes a raise or describes a `RefAdjustment`) checks only the sites that were tagged. A WARNING that was missed fails no check. Consider listing the candidate sites found by `grep -n "logger.warning" src/squadron/codehost/refs.py src/squadron/codehost/github_cli.py` in the task, so the sweep has a closed set.

### Run Digest

- Response length: 5562 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: not computed
- Tokens — prompt / cached / completion / reasoning: not computed / not computed / not computed / not computed
- Duration: 42.4 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
