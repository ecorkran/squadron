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
reviewedSha: ac9e6a0c7d45be4a51f7696100e31715192e5797
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
effort: xhigh
turns: 22
promptTokens: 1744991
cachedTokens: 1551081
cacheWriteTokens: 193886
completionTokens: 72979
durationSeconds: 322.1
costUsd: 0.441841
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: security
    summary: "Task 25's producer invoker does not scrub the child environment"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:230"
  - id: F002
    severity: concern
    category: sequencing
    summary: "Tasks that need no 421–423 names are blocked by the Task 11 gate"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:136"
  - id: F003
    severity: concern
    category: sequencing
    summary: "The slice branch never picks up 421–423 when they land"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:136"
  - id: F004
    severity: concern
    category: completeness
    summary: "Production collaborators have no constructor in any task"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:192"
  - id: F005
    severity: concern
    category: scope
    summary: "The branch preflight in Task 7 is a behavior change the design does not approve"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:100"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "A pre-dispatch hang has no bound and no signal"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:203"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Module size is deferred to the last task"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:250"
  - id: F008
    severity: concern
    category: task-quality
    summary: "Task 31 is underspecified and touches another slice's file"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:267"
  - id: F009
    severity: concern
    category: task-quality
    summary: "The walkthrough's first step needs a scratch slice nothing creates"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:303"
  - id: F010
    severity: concern
    category: proportionality
    summary: "Task 36 repeats gates and tests that Tasks 21 and 37 already run"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:301"
  - id: F011
    severity: note
    category: docs
    summary: "Two intentional departures from the design need to be recorded"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:216"
  - id: F012
    severity: note
    category: task-quality
    summary: "Minor wording and constants"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:216"
  - id: F013
    severity: pass
    category: coverage
    summary: "Every success criterion has a task"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:410"
  - id: F014
    severity: pass
    category: commit-cadence
    summary: "Commit markers sit at working, tested points"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:80"
  - id: F015
    severity: pass
    category: coverage
    summary: "Code references in the plan check out"
    location: "src/squadron/data/pipelines/P456.yaml:16"
  - id: F016
    severity: pass
    category: coverage
    summary: "Load test and CI gating are present for the budget path"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:126"
---

# Review: tasks — slice 424

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] Task 25's producer invoker does not scrub the child environment

Task 25 runs the producer "through the injected invoker with `cwd=<tree>` and `env=ScrubbedEnvironment(...)`". Nothing in the plan makes that true:
- `run_sq_subprocess` (`src/squadron/replay/runner.py:83`) takes only `(argv, cwd)`. It has no env parameter and the child inherits everything.
- `SubprocessRunner.run` (`src/squadron/core/process_runner.py:117-118`) merges `env` over `os.environ`. A scrubbed mapping passed there still leaves `GH_TOKEN` and the rest in the child.
- 421 found this and adds `replace_env=True` to `ProcessRunner.run` (`project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:56-60`). Its scrubbed environment is consumed through `process_env()` (same file, line 265). 424 mentions neither, and Task 11's precondition checks do not include `replace_env`.
- Task 25's test asserts on the env the invoker *received*. That passes under the merge behavior, so a leaking child stays green.
- The design repeats the `env=` claim (`project-documents/user/slices/424-slice.producer-only-replay-runner.md:203`).

Fix: add `replace_env` to Task 11's checks. Task 25 should build the production invoker with `env=ScrubbedEnvironment(...).process_env()` and `replace_env=True`, not the existing `run_sq_subprocess`. The test should check the child's real environment (a real child that prints its env, as 421 Task 3 does), not the argument. Correct the design's D5 wording with it.

### [CONCERN] Tasks that need no 421–423 names are blocked by the Task 11 gate

Task 11 stops everything from Task 12 on. Several tasks need none of 421–423:
- Task 16 (registry and `iter_jsonl`) needs only `ProfileName`.
- Tasks 19–20 (leak rules, path extraction, git and package rules) are pure functions over `ToolCall` and injected facts.
- Task 22 (id arithmetic) is pure.
- Task 23's `resolve_caps` and `format_bound` use only `_positive_usd`, `RunSpend` and the config key. Only its `BenchmarkPlan` case-type import depends on 421/422.

Tasks 17, 18 and 21 depend on the Task 13 fixtures, so they stay gated. The system rule is to finish what does not depend on the blocked part. Move Tasks 16, 19, 20 and 22 (and the caps part of 23) ahead of Task 11.

### [CONCERN] The slice branch never picks up 421–423 when they land

Task 1 forks the slice branch from the target now. Task 11 then greps `src/squadron` on that branch for the 421–423 names. Those names exist only once 421–423 reach the target. No task tells the agent to bring the target into the 424 branch, so Task 11 would stay BLOCKED on a branch whose target already has the code. Add a step: once the names are on the target, merge the target into the slice branch (abort and ask the PM on conflict), then rerun the gate.

### [CONCERN] Production collaborators have no constructor in any task

- `LeakRules` inputs (Task 19): `uv cache dir` output, the install location of the `squadron` package, `[project].name` at the start commit, the code-host owner and name, the real `HOME`, and `repo_root`. Design D7 (`project-documents/user/slices/424-slice.producer-only-replay-runner.md:223`) lists them, but no task gathers them. Task 19's factory "runs no command itself", so some caller must, and no task names one.
- The `deps` bundle (Task 27, line 243) has a sandbox factory, invoker, store, state reader, transcript registry, process runner and clock. Task 32 says "injected deps through the command's dependency seam" (line 276), but not where real instances are built.
- The producer invoker is covered by the FAIL above.

Without these, walkthrough step 4 (a real `leak` verdict) cannot pass. Name the construction site, probably Task 32's command module, and the task that writes it.

### [CONCERN] The branch preflight in Task 7 is a behavior change the design does not approve

Task 7 refuses a producer-only run whose commit is a code commit unless the current branch is the slice's branch, on fresh runs and dry runs. Neither the design's functional requirements nor D1–D3 include this. The design's walkthrough assumes a slice branch (`project-documents/user/slices/424-slice.producer-only-replay-runner.md:442`). The reason is sound: without the check, the dispatch spends before `_check_placement` refuses. But:
- The CLI would expand the step config and read `SUBJECT_PARAM` from the commit action (`src/squadron/pipeline/commit_plan.py:43`), so it knows commit-action internals.
- The dry-run tests (line 102) need a repo on a slice branch, which the test list does not say.
- Task 36 step 2 (line 305) depends on it.

Either amend the design first and keep it, or cut it and accept the post-dispatch refusal. Decide before Task 7 starts.

### [CONCERN] A pre-dispatch hang has no bound and no signal

D5 says "Existing bounds end a hang", naming the SDK stall bound and the Codex turn timeout. Both start only once a dispatch begins. The plan's context (task file line 46) admits that `sq run` stuck in cf, git or prompt assembly has no bound and no signal, and defers it to "issue #297". The review rule requires every new I/O failure mode to be observable and tested. `FixCaseRunner.run` (Task 25) is a new subprocess with no timeout, so a pre-dispatch hang blocks the whole benchmark with no record. Decide between a harness-side watchdog that records `producer_failed` and an explicit design acceptance. I did not check GitHub, but `#297` appears nowhere else in the project documents, so confirm it exists and covers this.

### [CONCERN] Module size is deferred to the last task

Tasks 28–30 all land in `bench_runner.py`: lock, interruption, sweep, schedule, caps, resume, retry, case drops and store failure. Tasks 19–21 land in `leak_scan.py`, and Task 20 says "in the same module(s)". Task 37 (line 322) notes both are likely over the ~300-line limit and tells the agent to split at the end, after all tests pass. Plan the split now. For example, put lock, interruption and sweep in `bench_lifecycle.py` under Task 28, and the git and code-host rules in their own module under Task 20.

### [CONCERN] Task 31 is underspecified and touches another slice's file

Task 31 is four lines but needs several things it does not specify:
- a child process that blocks at a known point inside the second replay (no mechanism named),
- fake deps rebuilt inside the child from a shared store path,
- a real 421 sandbox created by the child and orphaned by SIGKILL,
- a parent `begin_benchmark` call.

Its "helper module under `tests/benchmark/support.py`" is also a file 421 Task 3 already creates (`ScriptedRunner`, 421 task file line 105). The task would edit another slice's file without saying so. Specify the blocking mechanism (for example, a gate file the child waits on), how the child builds deps, and move the helper into its own step.

### [CONCERN] The walkthrough's first step needs a scratch slice nothing creates

Step 1 runs `sq run P6 <slice> …` "on a scratch slice branch with a design and task file". No task creates that scratch slice, and `<slice>` is never named. Name the slice, or add a step that creates the design and task file. Without it, the first walkthrough step cannot start.

### [CONCERN] Task 36 repeats gates and tests that Tasks 21 and 37 already run

Task 36's first bullet (ruff, pyright and the full pytest run on the whole branch) duplicates Task 37 (line 320). Step 7's `uv run pytest tests/benchmark/test_leak_scan.py -v` (line 315) repeats Task 21's test (line 205). Keep the live `--keep` inspection in Step 7 and drop the duplicate gate and test runs.

### [NOTE] Two intentional departures from the design need to be recorded

- The scan uses `turns` where the design asks for a tool-call count. The plan says usage records carry no tool-call count. A grep of `src/squadron` finds none outside providers and review, which supports that. Task 13 confirms it per profile.
- `scan(source, home, rules, *, turns)` (Task 21, line 204) differs from the design's Component Structure, `scan(tool_calls, rules)` (line 89).

Task 37 should record both in the design, including the signature.

### [NOTE] Minor wording and constants

- Task 23 writes the per-replay key as `pipeline.max_cost_usd`. Use the existing `COST_CAP_KEY` (`src/squadron/config/keys.py:23`), as Task 32 does for `benchmark.planned_samples`.
- Task 17's last test bullet (line 181), "a synthetic extra line is also covered, but the fixture test must exist", is unclear about which test is required.
- Task 4's trigger "~330 lines" (line 75) conflicts with the project's ~300.

### [PASS] Every success criterion has a task

The mapping:
- FR1 → Tasks 5–7, 9, 36 step 1
- FR2 → Tasks 4, 9
- FR3 → Tasks 5–7
- FR4 → Task 8
- FR5 → Tasks 23, 24, 32
- FR6 → Tasks 23, 28, 29, 33
- FR7 → Tasks 19–21
- FR8 → Tasks 14, 15, 34
- FR9 → Tasks 28, 31
- FR10 → Tasks 26, 27
- Technical requirements → Tasks 10, 13, 17–21, 37
- Integration requirements → Tasks 15, 24, 25

The failure-mode rule's list (transcript missing, `sq` killed, stall, diff failure, store failure, lock contention, peer killed) is also covered by tests (task file line 47). Test-with pattern holds throughout.

### [PASS] Commit markers sit at working, tested points

There are 20 markers, at Tasks 4, 5, 7, 8, 9, 10, 12, 13, 15, 18, 21, 24, 26, 27, 30, 31, 33, 34, 35 and 37. None follows every task, and none is only at the end. Tasks 6, 14, 25, 32 and 36 have no marker and ride with a later commit, which is fine because none is a working point alone.

### [PASS] Code references in the plan check out

- P6 has one `phase` step, `implement` (`src/squadron/data/pipelines/P6.yaml:16`).
- P456 has three: `design`, `tasks` and `implement` (`P456.yaml:16`, `:34`, `:63`). Task 5's refusal test is correct.
- No built-in pipeline is named `slice`.
- `parse_slice_branch` is at `src/squadron/pr/branch.py:14`. The same-named function at `review/git_utils.py:212` is the one the plan warns against.
- `RESERVED_PARAMS` (`pipeline/control_params.py:29`), `open_pipeline_session` (`pipeline/sdk_session.py:661`) and `FailureKind.COST_CAP` (`pipeline/failure_kind.py:29`) exist.
- `_positive_usd` is private (`pipeline/run_spend.py:59`), which Task 23 already handles.
- `BenchmarkSandbox`, `CaseKind`, `qualification_for` and `FixStepType` are absent, as the Task 11 gate expects.

### [PASS] Load test and CI gating are present for the budget path

Task 10 adds a load test under `tests/load/` and confirms CI does not exclude it. The Python rules require load tests for budget overruns, so this stays.

### Run Digest

- Response length: 12770 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 1744991 / 1551081 / 193886 / 72979 / not computed
- Duration: 322.1 s
- Cost: $0.44 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16

## Responses

- **F001 (fixed, different mechanism):** Real gap. The producer child inherited the harness environment. The fix is not `replace_env`: `SubprocessRunner.run` requires a timeout and the producer has none, so Task 25 instead adds an optional `env` to `run_sq_subprocess` (`subprocess.run(env=...)` replaces the environment exactly; `None` keeps `sq replay` unchanged). The test uses a real child with `GH_TOKEN` set in the test process. Beyond the finding: 421's `BenchmarkSandbox` hardcodes `CredentialGrant.none()`, so the producer had no credentials in the sandbox home it is read back from. Task 25 adds `BenchmarkSandbox.producer_env(profile)` with tests. Task 11 checks the 421 names it uses, and Task 37 corrects D5 and the Data Flow line.
- **F002 (declined):** 421–423 are declared dependencies and are implemented first, so the gate passes in the normal order. Reordering four tasks to save work in a case the dependency order excludes is churn.
- **F003 (declined):** Same reason. The slice branch forks when 424 implementation starts, after 421–423 have merged.
- **F004 (fixed):** Task 32 now builds the production collaborators in `benchmark/production_deps.py` (the `deps` dataclass, every `LeakRules` input, the `sq` path), refuses on a missing input, and has a test.
- **F005 (declined):** Already recorded as a deliberate design gap in the Context Summary, and Task 37 writes it into the design. The check protects against a dispatch that spends and then refuses.
- **F006 (declined):** Issue #297 exists (open, "Bound and signal for a benchmark replay that hangs before dispatch") and the task file's Context Summary defers to it.
- **F007 (declined):** Task 37 already checks sizes and splits by concern. Moving the split earlier only reorders the same work.
- **F008, F009, F010 (declined):** An implementer can choose the blocking mechanism, scratch slice and gate trimming. None changes what gets built.
- **F011 (fixed):** Task 37 lists the `scan` signature change and the producer-environment wording alongside the `turns` departure.
- **F012 (fixed in part):** Task 23 uses `COST_CAP_KEY`. The other wording items are left.
