---
docType: review
layer: project
reviewType: tasks
slice: producer-only-replay-runner
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/424-tasks.producer-only-replay-runner.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 3d0e78ca2081261e9b8b97673040e1a92eaeeae0
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
effort: xhigh
turns: 25
promptTokens: 967487
cachedTokens: 807623
cacheWriteTokens: 159848
completionTokens: 52718
durationSeconds: 229.7
costUsd: 0.320012
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: sequencing
    summary: "Task 2 halts the whole slice, including work with no dependency on 421–423"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:58"
  - id: F002
    severity: concern
    category: scope
    summary: "Producer-only drops `branch: enter`, which `implement` requires"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:99"
  - id: F003
    severity: concern
    category: completability
    summary: "The multi-producer case uses a pipeline name that is not built in"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:117"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 24 depends on a registry that Task 25 creates"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:207"
  - id: F005
    severity: concern
    category: completability
    summary: "Walkthrough step 6 needs Ctrl-C, which an agent cannot send"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:286"
  - id: F006
    severity: concern
    category: coverage
    summary: "No load-tier test or CI gate for the SDK budget path that the Python rules name"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:45"
  - id: F007
    severity: concern
    category: coverage
    summary: "The `--samples` default has no implementation step and no test"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:254"
  - id: F008
    severity: concern
    category: proportionality
    summary: "Task 29 and Task 31 each bundle too many behaviours"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:239"
  - id: F009
    severity: note
    category: process
    summary: "Task 1's commit message says \"revise\" for a file that is new"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:52"
  - id: F010
    severity: note
    category: completability
    summary: "Task 4 points to \"the project's memory\" for the alias choice"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:71"
  - id: F011
    severity: note
    category: completability
    summary: "Task 2's grep check may fail on macOS and in chained commands"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:58"
  - id: F012
    severity: note
    category: scope
    summary: "Task 35 adds docs and a CHANGELOG bullet that trace to no success criterion"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:298"
  - id: F013
    severity: note
    category: process
    summary: "Task 34's `fix:` commit is conditional, and Task 3 writes the issue number into two places"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:292"
  - id: F014
    severity: pass
    category: coverage
    summary: "Coverage and existing references check out"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:1"
---

# Review: tasks — slice 424

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 2 halts the whole slice, including work with no dependency on 421–423

Task 2 writes BLOCKED and stops if 421–423 are unimplemented. They are only task files today (`git log` ends at "docs: add slice 423 tasks"), so the slice cannot start. Tasks 5, 6, 9, 10, 11 and 13 need only existing code: `pipeline/control_params.py`, `steps/phase.py`, `pipeline/state.py`, `cli/commands/run.py` (1561 lines, `_load_run_definition` at line 231), `pipeline/sdk_session.py` (`is_error` path at line 441), and `commands/sq/run.md`. Task 3 (the issue) has no dependency either. Project rules say a blocked part does not block the rest. Fix: limit the gate to tasks that need 421–423 (4, 7, the `fix` test in 8, 12, 14–35), and let 3, 5, 6, 9, 10, 11 and 13 run while it is blocked. Also, the grep paths `user/tasks/...` are relative to `project-documents/` and need that prefix. As written, the check fails for the wrong reason.

### [CONCERN] Producer-only drops `branch: enter`, which `implement` requires

Task 8 keeps only the producer step and skips every other top-level step. In P6, that includes the first step, `branch: {op: enter}` (`src/squadron/data/pipelines/P6.yaml:15`). `pipeline/branch_rules.py:38-40` treats a preceding enter as required for every `implement` step, and its docstring says an implement without one runs on whatever branch is checked out. The design's FR1 forbids only `merge`, but its Data Flow (design line 115) skips `branch`, so the design does not decide this. Task 12 (line 129) asserts that no `branch` action runs. Recommend keeping enter in producer-only (it prepares the producer, it is not post-producer work), stating that in Task 8, and narrowing Task 12's assertion to merge. Add a test that the stripped definition still passes `implement_branch_errors`.

### [CONCERN] The multi-producer case uses a pipeline name that is not built in

Task 10 (line 117) and walkthrough step 2 (line 278) run `sq run slice <n> --producer-only` and expect candidate names in the refusal. No pipeline named `slice` exists in `src/squadron/data/pipelines/`. The built-in with several producers is `P456.yaml`, which has `phase:` 4, 5 and 6. Task 8 (line 101) hedges with "or whichever built-in has several phase steps," but Tasks 10 and 34 do not. Replace with `sq run P456 <slice> --producer-only`. I checked only the repo's built-ins; if a user-level `slice` pipeline is intended, the file should say so.

### [CONCERN] Task 24 depends on a registry that Task 25 creates

Task 24 builds `check_plan(cases, configs, runners, ...)` and tests "a case kind with no registered `CaseKindRunner`." The `CaseKindRunner` protocol and its registry are defined in Task 25 (line 213). Task 24 cannot be finished in order. Move the protocol and registry into Task 24, or reorder so that Task 25 comes first.

### [CONCERN] Walkthrough step 6 needs Ctrl-C, which an agent cannot send

Step 6 says "Ctrl-C during a replay." Name the signal and the process: `kill -INT <pid>` from a second shell tests the Python KeyboardInterrupt path, and `kill -KILL <pid>` tests the crash path. Task 30 already covers SIGKILL in a test, so step 6 should say which signal it adds. If no second shell is available, the task should say BLOCKED with the reason.

### [CONCERN] No load-tier test or CI gate for the SDK budget path that the Python rules name

Line 45 justifies having no load test because the harness is sequential. That answers only the concurrency question. The Python rules in `.claude/rules/python.md` require at least one `tests/load/` test for code on network or environment-layer paths, say CI must gate those tests, and name budget overruns as something only load tests catch. Task 13 changes the SDK dispatch path (`open_pipeline_session`, `sdk_session.py:661`) to enforce `max_budget_usd`, and Tasks 26–27 run `sq` as a subprocess. The design restates no NFR, so the trigger here is the Python rule, not the NFR rule. Add a `tests/load/` task that checks the cap holds under a realistic configuration, plus a CI wiring task. Or record an explicit exemption with its reason.

### [CONCERN] The `--samples` default has no implementation step and no test

Design line 313 says `--samples` defaults to `benchmark.planned_samples`. Task 24 tests only the refusal when both are absent. Task 31 never says to read the key, and no test checks that a run uses the configured value. Add both. The key comes from 422, so this depends on that slice.

### [CONCERN] Task 29 and Task 31 each bundle too many behaviours

Task 29 covers ordering, cap and overshoot, resume, `--retry-harness`, unpriced replays, case drops, `--case` filtering and store-failure stops, with nine tests. Task 31 covers refusals, the bound, output, the summary, the auth-check reminder, `--keep` and exit codes. Split 29 into schedule and cap, and resume, retry, drops and unpriced. Split 31 into refusal and bound, and output and summary. Each part keeps its own test run.

### [NOTE] Task 1's commit message says "revise" for a file that is new

`git status` shows the task file as untracked (`??`), so the commit adds it. Use `docs: add slice 424 tasks`.

### [NOTE] Task 4 points to "the project's memory" for the alias choice

A fresh agent cannot read that memory, so the pointer is not actionable. State the rule directly: use `sq models`, pick a cheap alias, and confirm auth-check yes.

### [NOTE] Task 2's grep check may fail on macOS and in chained commands

I have not run it. `\s` may not be supported by BSD grep, so use `[[:space:]]`. Also, `grep -c` exits 1 when the count is 0, so a chained `&&` check would fail on the success case.

### [NOTE] Task 35 adds docs and a CHANGELOG bullet that trace to no success criterion

`docs/PIPELINES.md` and the benchmark CHANGELOG bullet are not in the design's success criteria. They are small and sensible for a user-facing flag. Keep them or cut them explicitly. The Task 13 CHANGELOG bullets do trace to D9.

### [NOTE] Task 34's `fix:` commit is conditional, and Task 3 writes the issue number into two places

Line 292 commits a `fix:` only if verification found defects. If none are found, the marker produces nothing, so say "commit only if a fix was made." Separately, Task 3 (line 65) writes the issue number into the design as well as the task file. Design line 264 names only the task file. The `gh issue create` call is authorized by the design's D9 decision, so it needs no separate confirmation.

### [PASS] Coverage and existing references check out

Every functional requirement, technical requirement, integration requirement and walkthrough step maps to a task. Each D10 outcome has a test (Tasks 26–27), and the failure-mode rule has observable-signal tests across Tasks 15, 21, 26, 27, 28 and 30. Referenced symbols exist: `read_cost_cap`, `RunSpend`, `FailureKind.COST_CAP`, `ProducerConfigRef.effort_sent`, `run_sq_subprocess`, `replay/outcome.py`, `FAILURE_KIND_KEY`, `usage_limit_stamp`, and `pipeline.max_cost_usd`. `_positive_usd` is private, which Task 23 already handles. Commit markers sit at tested working points, and each test follows its implementation.

### Run Digest

- Response length: 10356 chars
- Response is newline-free: no
- Tool calls made: 24
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 25
- Tokens — prompt / cached / cache write / completion / reasoning: 967487 / 807623 / 159848 / 52718 / not computed
- Duration: 229.7 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
