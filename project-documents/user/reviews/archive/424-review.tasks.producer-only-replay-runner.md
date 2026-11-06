---
docType: review
layer: project
reviewType: tasks
slice: producer-only-replay-runner
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
reviewedSha: 1258e664e0368f42020345105ea87b8395704d5e
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 18
effort: xhigh
turns: 19
promptTokens: 1029311
cachedTokens: 861372
cacheWriteTokens: 167923
completionTokens: 51030
durationSeconds: 226.7
costUsd: 0.326261
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: process
    summary: "Task 2 commit marker would commit a note only"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:64"
  - id: F002
    severity: concern
    category: coverage
    summary: "Source of `expected_tool_calls` is never named"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:239"
  - id: F003
    severity: concern
    category: correctness
    summary: "Task 7 names a helper that exists twice with different signatures"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:98"
  - id: F004
    severity: concern
    category: scope
    summary: "Task 6 adds refusals and a display line the design does not contain"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:89"
  - id: F005
    severity: concern
    category: ci
    summary: "CI gating of the load test can be waived"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:126"
  - id: F006
    severity: concern
    category: failure-modes
    summary: "A hang before dispatch has no bound and no signal"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:226"
  - id: F007
    severity: concern
    category: proportionality
    summary: "Test scope beyond the success criteria"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:291"
  - id: F008
    severity: note
    category: testing
    summary: "pyright gate does not cover the tests this plan adds"
    location: "pyproject.toml:100"
  - id: F009
    severity: note
    category: testing
    summary: "Load-test assertion is timing-based"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:124"
  - id: F010
    severity: note
    category: coverage
    summary: "Two coverage gaps in the bound and drop paths"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:213"
  - id: F011
    severity: note
    category: documentation
    summary: "Store-failure stops are recorded as `interrupted`"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:257"
  - id: F012
    severity: note
    category: documentation
    summary: "Names and modules drift from the design"
    location: "project-documents/user/slices/424-slice.producer-only-replay-runner.md:76"
  - id: F013
    severity: note
    category: sequencing
    summary: "Precondition check is a proxy"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:134"
  - id: F014
    severity: pass
    category: coverage
    summary: "Every success criterion traces to a task"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:53"
  - id: F015
    severity: pass
    category: sequencing
    summary: "Sequencing, dependencies and test pairing hold"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:133"
  - id: F016
    severity: pass
    category: proportionality
    summary: "Task count fits the slice"
    location: "project-documents/user/tasks/424-tasks.producer-only-replay-runner.md:1"
---

# Review: tasks — slice 424

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 2 commit marker would commit a note only

Task 2 changes no code. Its only file change is the issue number and its check-off, so the `**Commit**:` marker at line 64 would make a commit that only adds a note. The commit cadence forbids that (CLAUDE.md, Source Control and Builds). Remove the marker. Carry the issue number into the next marker commit (line 78) or the Task 37 DEVLOG entry.

### [CONCERN] Source of `expected_tool_calls` is never named

Task 27 passes `expected_tool_calls` "from the usage records". Design D6 (project-documents/user/slices/424-slice.producer-only-replay-runner.md:216) makes this cross-check the thing that turns an empty transcript into `scan_unavailable`. No task names the field or the reader. Task 26's classify inputs (line 232) list cost, turns, `effort_sent` and prompt identity, not tool calls. The codebase has `TOOL_CALLS_MADE_KEY = "tool_calls_made"` (`src/squadron/providers/base.py:15`). The review path writes it (`pipeline/actions/review.py:729`), and dispatch telemetry appears to carry it (`pipeline/actions/dispatch_outcome.py:40`). No task says whether a producer run's state or usage record exposes it. Name the key and its reader in Task 26, and add it to the Task 11 checks. If no such field exists, Task 11 should write `BLOCKED:`.

### [CONCERN] Task 7 names a helper that exists twice with different signatures

Task 7 says `parse_slice_branch(current_branch(cwd)) ==` the slice index, without naming a module. Two functions share that name. `src/squadron/pr/branch.py:14` takes a branch name and returns `int | None`, which is what the check needs. `src/squadron/review/git_utils.py:212` takes git stdout and returns `str | None`. An implementer who imports the second one will refuse the correct branch. Name the module (`squadron.pr.branch`) in the task.

### [CONCERN] Task 6 adds refusals and a display line the design does not contain

Task 6 refuses five more flags, `--explain`, `--validate`, `--status`, `--step-done` and `--next` (line 90). Design D3 (design:182) and success criterion FR3 (design:416) name only `--from`, `--item` and `--flagged`. Task 6 also adds a producer-only line to `sq runs show` (line 89, test at line 92). No design section or criterion requires that line. The Context Summary says the design is not edited until Task 37, so implementers would work from a design that contradicts the tasks. Amend design D3 now so the spec and the tasks agree. Cut the `sq runs show` line; the walkthrough needs `sq runs show` only to read the run.

### [CONCERN] CI gating of the load test can be waived

CI runs a plain `uv run pytest` (`.github/workflows/ci.yml:38`), and `testpaths = ["tests"]` (`pyproject.toml:89`) includes `tests/load/`. The load test is therefore gated today. Task 10 only confirms this. If it finds an exclusion, it says to record the exclusion in the DEVLOG and move on. That leaves the load test ungated, which the gating rule forbids. Change the item so an exclusion must be removed in the CI step, or else the task writes `BLOCKED:`.

### [CONCERN] A hang before dispatch has no bound and no signal

Task 25 runs `sq run fix` with no timeout, as design D5 does (design:203). The design answers "what if it hangs" only for the dispatch, through the stall bound and the Codex turn timeout. A hang before dispatch (cf ops, a git hook, a prompt waiting on stdin) has no bound and no recorded outcome. `replay_one` would never return, so no record is written and the benchmark never reports. The review rule (review-code.md, Failure-Mode Enumeration) requires each I/O path to answer this explicitly and to have an observable signal. Add a bound or a heartbeat log for the non-dispatch phase, and a test that asserts the signal.

### [CONCERN] Test scope beyond the success criteria

Task 35 adds a parity test that checks `benchmark.md` for every option and for no behavior text. No success criterion requires `/sq:benchmark` parity. Design line 320 only says it mirrors the CLI. Task 8 adds a similar plain-text check on `run.md` (line 108). Cut the parity test, or reduce it to one assertion, and keep the manual check in Task 36.

### [NOTE] pyright gate does not cover the tests this plan adds

Every gate says "pyright (zero errors)", but `include = ["src"]` means test files are not type-checked. The comment there says widening is tracked in issue #50. Say in the gate what it covers, so "zero errors" is not read as covering the new tests.

### [NOTE] Load-test assertion is timing-based

"A ticker never stalls longer than a small multiple of the fake's per-message delay" is a wall-clock assertion and can flake in CI. Make the threshold a named constant with a generous margin, and assert on a fixed number of ticks.

### [NOTE] Two coverage gaps in the bound and drop paths

D8 (design:257) says configs with unpriced replays are listed as not bounded. Task 23's `format_bound` lists only configs outside the SDK-bounded set, so no task covers the unpriced case. Also, D10 (design:286) says a blocked run's sandbox is removed like any other. Task 27's tests (line 241) do not assert removal for `blocked`.

### [NOTE] Store-failure stops are recorded as `interrupted`

Task 30 sets status `interrupted` on a `ReplayStoreError`. The status enum has no failure value, and design line 153 says only that the benchmark stops. Reports will therefore say "interrupted" for a write failure, which is a different condition. Either document that in D4, or add a status value.

### [NOTE] Names and modules drift from the design

- Design line 76 lists `select_producer_step`, but no task creates it; Task 5 inlines the lookup.
- Design lines 89 and 143 use `scan(tool_calls, rules)` and `tool_calls(...)`. Tasks 16 and 21 use `read(home)` and `scan(source, home, rules, *, expected_tool_calls)`.
- The tasks add modules the design does not name: `bench_caps.py`, `bench_refusals.py`, `replay_outcome.py`, `leak_paths.py` and `benchmark_run.py`. Each is justified by the 300-line rule. Sync the design signatures and module list now, rather than at Task 37.

### [NOTE] Precondition check is a proxy

Task 11 counts unchecked boxes in the 421–423 task files and checks two paths. It does not check `metrology/benchmark_models.py`, `metrology/benchmark_store.py`, `cli/commands/benchmark.py` or the `benchmark.planned_samples` key. Tasks 14, 15, 32 and 35 extend those. None of them exists in `src/` now, so the gate still blocks correctly, because `src/squadron/benchmark/` is absent. Add those paths and that key to the check so the gate does not depend on that.

### [PASS] Every success criterion traces to a task

Mapping from design success criteria (project-documents/user/slices/424-slice.producer-only-replay-runner.md:412–436) to tasks:
- FR1: T4–T7, T9. FR2: T4, T9. FR3: T5–T7. FR4: T8.
- FR5: T23, T24, T32. FR6: T23, T28, T29, T33.
- FR7: T19–T21. FR8: T14, T15, T34. FR9: T28, T29, T31.
- FR10: T26, T27, T30.
- TR1: T36, T37. TR2: T13, T17, T18, T21. TR3: T19, T20. TR4: T10. TR5: T37.
- IR1: T14, T15. IR2: T25. Walkthrough: T36.

### [PASS] Sequencing, dependencies and test pairing hold

Tasks 1–10 use only the P4–P6 pipelines and existing code, so they can proceed before 421–423. Task 11 gates everything that needs them. No circular dependencies. Each implementation task carries its tests in the same task, and each commit marker (apart from line 64) follows tests. Names and sizes I checked match the code: `run.py` is 1561 lines and `phase.py` is 325; `CommitSubject`, `SUBJECT_PARAM`, `_check_placement`, `_load_run_definition`, `_handle_prompt_only_init` and `current_branch` exist; `open_pipeline_session` exists; `max_budget_usd` exists in the installed SDK (`.venv/lib/python3.13/site-packages/claude_agent_sdk/types.py:2056`); `tests/load/test_grep_timeout.py` exists.

### [PASS] Task count fits the slice

37 tasks in one 324-line file for a slice with about 20 modules. The heaviest tasks are Task 10 (SDK option, error mapping, load test, CI check, CHANGELOG), Task 27 (eight outcome scenarios) and Task 36 (seven live steps). Each is coherent, so none needs splitting. The file does not need to be split.

### Run Digest

- Response length: 11745 chars
- Response is newline-free: no
- Tool calls made: 18
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 19
- Tokens — prompt / cached / cache write / completion / reasoning: 1029311 / 861372 / 167923 / 51030 / not computed
- Duration: 226.7 s
- Cost: $0.33 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
