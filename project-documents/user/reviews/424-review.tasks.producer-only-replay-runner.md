---
docType: review
layer: project
reviewType: tasks
slice: producer-only-replay-runner
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/424-tasks.producer-only-replay-runner.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 526897ea8996bd8cd9bc3974a74cf6d0d8747bb2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
effort: xhigh
turns: 15
promptTokens: 1056272
cachedTokens: 878204
cacheWriteTokens: 178052
completionTokens: 60258
durationSeconds: 262.2
costUsd: 0.358201
costBasis: provider
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Task 7 bundles four separable changes into one task"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:97-103"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Task 28 gives two conflicting instructions for when a resumed run is marked `running`"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:253"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Task 10 floors the remaining cap, which is a silent fallback"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:122"
  - id: F004
    severity: concern
    category: failure-modes
    summary: "Task 30 omits the keep-sandbox rule for record-write failures"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:263"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Task 32 bundles production wiring with the CLI"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:277-278"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Task 21 refers to a type that is defined later"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:204"
  - id: F007
    severity: note
    category: commit-cadence
    summary: "The Task 13 commit is fixture-only and not a tested point"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:158"
  - id: F008
    severity: note
    category: load-test
    summary: "The lock's contention path has no load-tier coverage rationale"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:252-255"
  - id: F009
    severity: note
    category: task-quality
    summary: "Items declined in revision 2 are still visible in this file"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:307"
  - id: F010
    severity: note
    category: task-quality
    summary: "Three wording gaps an implementer cannot resolve"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:163"
  - id: F011
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:410-436"
  - id: F012
    severity: pass
    category: sequencing
    summary: "The Task 11 gate is correct, and the names Tasks 1–10 use exist"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:136-140"
  - id: F013
    severity: pass
    category: load-test
    summary: "The Task 10 load test is required, and its CI gate is checked"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:126-130"
  - id: F014
    severity: pass
    category: scope
    summary: "Nothing outside the design is built"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:42-48"
  - id: F015
    severity: pass
    category: commit-cadence
    summary: "Commit markers sit at working points, with one exception noted above"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md"
---

# Review: tasks — slice 424

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 7 bundles four separable changes into one task

Task 7 covers (a) fresh-run and dry-run wiring, the stop line and the state stamp; (b) a branch preflight that expands the step config, reads `SUBJECT_PARAM`, parses the branch and has its own refusal path; (c) the `_load_run_definition` reload with its error path; and (d) eight test scenarios, one of which needs a real temp git repo. Its single commit (line 105) ships all of it. Split it into 7a (wiring, stop line, stamp), 7b (branch preflight with its git-repo tests) and 7c (resume reload), each with its own success check. Revision 2 declined the preflight itself; this finding is about size only.

### [CONCERN] Task 28 gives two conflicting instructions for when a resumed run is marked `running`

Line 253 first says the interrupted record is set back to `running` with the new caps, before planning. The same line then says `write BenchmarkRun(status=running)` only after the bound is printed, and the test list asserts that order. Both cannot hold. The design's Data Flow (slice design lines 128–129) puts the write after the bound. Say that the stored status stays `interrupted` until the bound is printed, and that the write then sets `running` with the new caps.

### [CONCERN] Task 10 floors the remaining cap, which is a silent fallback

Line 122 says the remaining cap is never below "a tiny positive floor defined once as a constant." A zero or negative remainder is then replaced by a value the operator never set. The project rule forbids that. The 947 check runs after each action, so a session should normally open with spend still under the cap. If the remainder is not positive at open, the dispatch should fail with `FailureKind.COST_CAP` and an explicit message, not a substituted budget.

### [CONCERN] Task 30 omits the keep-sandbox rule for record-write failures

The design requires that a replay whose record write fails "keeps its sandbox and stops the benchmark" (slice design line 153, repeated in Patterns at line 303). Task 27 keeps the sandbox only for a `git diff` or sidecar failure (line 246). Task 30 stops the run with exit 1 and status `running` (line 263), but no step or test asserts that the sandbox survives a record-write failure. Add the step and a test that the sandbox directory still exists afterwards.

### [CONCERN] Task 32 bundles production wiring with the CLI

Line 277 puts the production wiring into the CLI task. That wiring builds seven collaborators, reads `pyproject.toml` at the start commit, runs `uv cache dir` through `SubprocessRunner`, derives the code-host owner from provenance and resolves the installed `sq`. Task 32 also covers `--samples` and every refusal test. `production_deps.py` is absent from the design's Component Structure (slice design lines 73–99) until Task 37 records it. Give the wiring its own task with its own test (line 278). Leave the CLI task with the options, `--samples` and the refusals.

### [CONCERN] Task 21 refers to a type that is defined later

Line 204 takes `turns` "carried on the Task 26 classification." Task 26 comes after Task 21 in both the file and the commit order (Task 21's marker is at line 208, Task 26's at line 242). Task 21's `scan` should take `turns: int | None` as a plain parameter, and Task 27 supplies it from the classification. Say so in the task so the implementer does not wait on Task 26 or invent a type.

### [NOTE] The Task 13 commit is fixture-only and not a tested point

The Task 13 commit contains captured fixtures and DEVLOG notes. Nothing reads the fixtures until Tasks 17 and 18. Consider moving that marker to the Task 18 commit (line 189), so the fixtures land with their first consumers. The other 19 markers sit at working points.

### [NOTE] The lock's contention path has no load-tier coverage rationale

The Context Summary says the harness is sequential, so nothing is on a concurrent path. `python.md:57` names concurrency paths and says unit and integration tests cannot catch contention. Task 28's second-invocation refusal is a contention case, and the plan does not address it. Confirm that the concurrency category does not reach a single-owner lock, or add a contention test at load tier.

### [NOTE] Items declined in revision 2 are still visible in this file

I did not re-raise the declined items as findings. They remain open and are for the PM to accept or act on:
- Tasks 28–30 all land in `bench_runner.py`, and the size split is deferred to Task 37 (line 326).
- Task 36 step 1 needs a scratch slice that no task creates, and `<slice>` is never named.
- The gate in Task 36 (line 305) and the test in step 7 (line 319) repeat Task 37 (line 324) and Task 21 (line 205).
- Task 31's helper path, `tests/benchmark/support.py` (line 270), is a file that the earlier review says 421 Task 3 creates.

### [NOTE] Three wording gaps an implementer cannot resolve

Task 14 names "a stored 320 record fixture" without a path, so the implementer cannot find it. Task 17's last test bullet (line 181) says "a synthetic extra line is also covered, but the fixture test must exist," which leaves unclear whether the synthetic-line test is required. Task 4 (line 75) sets a "~330 lines" trigger against a 300-line limit. Each is quick to fix.

### [PASS] Every success criterion has a task

Each functional, technical and integration requirement maps to at least one task, and each test task follows its implementation task. Walkthrough steps 1–7 map to Task 36 steps 1–7. Step 2's `sq run slice` is replaced by `P456`, which the Context Summary (line 38) records as a design gap.

### [PASS] The Task 11 gate is correct, and the names Tasks 1–10 use exist

I grepped `src/squadron`. `BenchmarkSandbox`, `ScrubbedEnvironment`, `BenchmarkRecordStore`, `CaseKind`, `FixStepType` and `qualification_for` are absent, so the gate will stop at BLOCKED as planned. The names used before the gate are present: `parse_slice_branch` (`pr/branch.py:14`, the correct one), `resolve_placeholders`, `CommitSubject.CODE`, `SUBJECT_PARAM`, `current_branch`, `GitEnvironmentError`, `RESERVED_PARAMS`, `_apply_param_overrides`, `_load_run_definition`, `_display_result`, `_handle_prompt_only_init`, `_render_prompt_only_step`, `RunState`, `StateManager`, `read_cost_cap`, `RunSpend`, `FailureKind.COST_CAP`, `open_pipeline_session`, `get_step_type`, `bootstrap_step_types` and `run_sq_subprocess` (`replay/runner.py:83`). `_positive_usd` is private, which Task 23 already handles.

### [PASS] The Task 10 load test is required, and its CI gate is checked

`project-documents/ai-project-guide/project-guides/rules/python.md:57` requires a load test for code on the network path and requires CI to gate it. The SDK budget path is on that path. Lines 128–130 check the CI gate by reading the workflow and the pytest config. Keep both.

### [PASS] Nothing outside the design is built

Grading, the cf sandbox registration (426), concurrent replays and the cross-benchmark status view are absent from the tasks. The tasks add modules the design does not list (`bench_refusals.py`, `replay_outcome.py`, `run_producer_only.py`, `production_deps.py`). Each is needed by a success criterion, and Task 37 is set to record them.

### [PASS] Commit markers sit at working points, with one exception noted above

There are 20 `**Commit**:` markers. None follows every task, and none sits only at the end. Each follows code and tests that pass together, except the Task 13 marker noted above. Tasks 1, 2, 6, 11, 14, 16, 25, 32 and 36 have no marker and ride with a later one.

### Run Digest

- Response length: 11438 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 1056272 / 878204 / 178052 / 60258 / not computed
- Duration: 262.2 s
- Cost: $0.36 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Responses

- **F001 (declined):** Size only. Splitting Task 7 renumbers every later task and the commit markers for no change to what gets built; the task has one commit and one success check per behavior.
- **F002 (fixed):** Task 28 now says the stored status stays `interrupted` until the bound is printed, and `running` with the new caps is written only after it.
- **F003 (fixed):** Task 10 no longer substitutes a floor. A remainder that is not positive fails the dispatch with `FailureKind.COST_CAP` and a message naming the cap and the spend; a test covers it.
- **F004 (fixed):** Task 30 keeps the replay's sandbox on a failed record write, and the test asserts the sandbox directory survives.
- **F005 (declined):** Same as F001. The wiring has its own bullet and its own test inside Task 32, and `production_deps.py` is recorded in the design by Task 37.
- **F006 (fixed):** Task 21 takes `turns` as a plain `int | None` parameter; Task 27 supplies it from Task 26's classification.
- **F007 (declined):** The fixtures land with the spike that captures them, and the Task 13 commit records the spike's answers for the PM.
- **F008 (declined):** The lock is single-owner and refuses a second invocation at once, never waiting. Task 31 covers it with a real killed process.
- **F009 (noted):** The declined items are recorded in the earlier round's responses. No change.
- **F010 (fixed in part):** Task 4 says ~300 lines and Task 17 says both tests are required. Task 14's fixture path is left for the implementer, who builds it from the existing replay model's JSON.
