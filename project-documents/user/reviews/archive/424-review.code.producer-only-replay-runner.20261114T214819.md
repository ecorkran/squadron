---
docType: review
layer: project
reviewType: code
slice: producer-only-replay-runner
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/424-slice.producer-only-replay-runner.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: eb3253f80a6f9de22e138422d9e64f898bf537b5
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
diffTruncated: false
effort: xhigh
turns: 32
promptTokens: 4856745
cachedTokens: 4492935
cacheWriteTokens: 363782
completionTokens: 73712
durationSeconds: 324.0
costUsd: 0.903505
costBasis: provider
runId: run-20261114-p6-24ce0506
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "Capped SDK sessions pass `max_budget_usd` to an SDK that does not define it"
    location: "src/squadron/pipeline/sdk_session.py#open_pipeline_session"
  - id: F002
    severity: concern
    category: correctness
    summary: "An invocation's spend is not persisted until the run finishes"
    location: "src/squadron/benchmark/bench_runner.py:207"
  - id: F003
    severity: concern
    category: correctness
    summary: "The benchmark lock can be taken over during another process's create-then-write window"
    location: "src/squadron/benchmark/bench_lock.py:43"
  - id: F004
    severity: concern
    category: correctness
    summary: "The leak scan misses commands run through wrappers and backtick substitution"
    location: "src/squadron/benchmark/leak_shell.py:21"
  - id: F005
    severity: concern
    category: documentation-drift
    summary: "The kept-sandbox warning says symlinks, but the carryover is a copy of the login files"
    location: "src/squadron/cli/commands/benchmark_run_report.py:17"
  - id: F006
    severity: concern
    category: test-debt
    summary: "Load test's overshoot bound is set by the fake, not by the code under test"
    location: "tests/load/test_sdk_budget_bound.py#_BudgetedClient"
  - id: F007
    severity: concern
    category: consistency-rot
    summary: "The replay driver hard-codes the run-state directory that `state.py` defines"
    location: "src/squadron/benchmark/replay_one.py:63"
  - id: F008
    severity: concern
    category: type-contract-debt
    summary: "Benchmark tests suppress type errors and use `Any` on the new modules"
    location: "tests/benchmark/test_replay_one.py"
  - id: F009
    severity: concern
    category: correctness
    summary: "The auth-check reminder is suppressed when a profile's first replay is not `no_run_state`"
    location: "src/squadron/cli/commands/benchmark_run_report.py:43"
  - id: F010
    severity: concern
    category: error-handling-observability
    summary: "The producer child process has no wall-clock bound at the harness level"
    location: "src/squadron/benchmark/case_runners.py#FixCaseRunner.run"
  - id: F011
    severity: note
    category: documentation-drift
    summary: "Enum location in the replay-models docstring is wrong"
    location: "src/squadron/metrology/benchmark_replay_models.py:4"
  - id: F012
    severity: note
    category: consistency-rot
    summary: "The `fix` pipeline name is defined in two modules"
    location: "src/squadron/benchmark/replay_records.py:19"
  - id: F013
    severity: note
    category: correctness
    summary: "The headline bound says \"capped at run cap\" even when the total is below the cap"
    location: "src/squadron/benchmark/bench_plan.py#format_bound"
  - id: F014
    severity: note
    category: error-handling-observability
    summary: "A dangling or out-of-tree `CLAUDE.md` symlink aborts the whole benchmark"
    location: "src/squadron/benchmark/instruction_files.py#instruction_files"
---

# Review: code — slice 424

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 31 successful tool call(s) of 31 made; 569100 of 569100 diff characters reached the model

## Findings

### [FAIL] Capped SDK sessions pass `max_budget_usd` to an SDK that does not define it

`open_pipeline_session` adds `max_budget_usd` to `ClaudeAgentOptions(...)` (`sdk_session.py:695-706`) whenever a run cap is set. The installed `claude_agent_sdk` 0.2.179 in `.venv` has no such field. `ClaudeAgentOptions` (`claude_agent_sdk/types.py:2339`) is a plain dataclass with `max_turns` at `:2418` and nothing budget-related. A grep of the whole package for "budget" returns zero matches. The subtype constant `SDK_BUDGET_SUBTYPE = "error_max_budget_usd"` (`sdk_session.py:129`) also appears nowhere in the installed SDK.

If this environment is the one used, every capped SDK session raises `TypeError` at open, before any dispatch. The budget-stop mapping cannot be exercised against the real SDK either. `pyproject.toml` declares `claude-agent-sdk>=0.2.162`, which does not guarantee the field exists.

Confirm with `uv run pytest tests/pipeline/test_sdk_budget.py -k carries_the_budget`; that test builds the real options. Fix by pinning an SDK version that defines the field and verifying the subtype string against it, or by enforcing the cap on the harness side.

### [CONCERN] An invocation's spend is not persisted until the run finishes

`run_benchmark` writes the run record once, after the loop (`:213`). `spent_usd` is `started.run.spent_usd + tally.spent_usd`, where the first term is carried from an earlier invocation. If the process is killed after a replay stores its record, or a `ReplayStoreError` propagates, that spend is missing from the stored total, and the next invocation carries the understated figure forward.

`_unpriced_in_store` (`:159-166`) recounts from the store for exactly this reason ("an invocation killed before it stored its totals would otherwise leave the count wrong"), but the same argument applies to spend and is not applied. The interrupt test (`tests/benchmark/test_bench_interrupt.py`) asserts replay counts but not spend. The killed child stores one replay at $0.50; after resume the stored total is $1.00 while the store holds $1.50.

The cap is per invocation, so resume behavior is unaffected. The reported "spent … of run cap" line is wrong. Fix by recomputing spend from stored replays, as unpriced is recomputed, or by writing running totals after each replay. Assert spend in the interrupt test.

### [CONCERN] The benchmark lock can be taken over during another process's create-then-write window

`acquire` creates the lock with `O_EXCL` (`:43`) and writes the owner JSON only after `os.fdopen` (`:57-58`). A second invocation in that window reads an empty file. `read_lock` returns `None` on the decode error (`core/process_lock.py:108-111`), `is_orphan(None)` is `True` (`process_lock.py:126-127`), and the second process unlinks the live lock (`bench_lock.py:55`) and succeeds on retry. Both invocations then hold the benchmark, which breaks the guarantee that a second live invocation refuses.

The window is small, but it lasts as long as the first process is paused between the two statements. Fix by publishing the lock atomically (write a temp file, then `os.link` or rename into place), or by treating a just-created empty file as held. Add a test that holds the file empty and asserts refusal.

### [CONCERN] The leak scan misses commands run through wrappers and backtick substitution

`WRAPPER_PROGRAMS` (`:21`) strips only `env`, `command`, `exec`, `nohup`, `time`, and `sudo`. `timeout 30 gh issue view 3`, `xargs gh …`, `nice`, `eval "gh …"`, and `watch` all report the wrapper as the program, so the `gh` and `git` rules never fire. Backticks are not treated as command substitution, because `_PUNCTUATION` (`:16`) excludes them. A command substituted with backticks therefore has its first word as `` `gh ``, not `gh`. `$(…)` and `bash -c` are handled, so the gap is specific.

Neither the git/host nor the package test lists (`tests/benchmark/test_leak_rule_git_package.py`) include these forms. Fix by adding the common wrappers, splitting backtick substitution the way `$(` is split, and adding these forms to the hit tests. The module docstring says `LEAK_RULES_VERSION` must be bumped when a rule changes, so bump it.

### [CONCERN] The kept-sandbox warning says symlinks, but the carryover is a copy of the login files

`KEEP_WARNING` says the kept home "holds symlinks to your auth files". `_link_carryover` copies them (`scrubbed_env.py:222`, "A copy, not a symlink", using `copy2`). Two docstrings also say "linked": `sandbox.py:159` and `scrubbed_env.py:141`. The test `test_keep_prints_the_paths_and_the_symlink_warning` (`tests/benchmark/test_benchmark_run_command.py:278`) asserts the wrong text, so the error is locked in.

The practical risk is the reverse of what the warning implies: a kept home holds real copies of the login files, and the warning never says so. Correct the three docstrings and the warning text, and fix the test.

### [CONCERN] Load test's overshoot bound is set by the fake, not by the code under test

`_BudgetedClient` is given the same budget constant as the run cap, decides for itself when to emit `SDK_BUDGET_SUBTYPE`, and never receives `options.max_budget_usd`. The assertion `RUN_CAP_USD <= spent <= RUN_CAP_USD + MESSAGE_COST_USD` therefore holds by the fake's construction. The subtype constant is imported from the module under test, so a wrong subtype string would also pass.

The test does verify something useful: a budget subtype maps to `COST_CAP`, and the loop keeps running while streaming. It does not test SDK enforcement, and the tier rule asks for latency, throughput, or resource bounds. Fix by having the fake enforce `options.max_budget_usd`, taking the subtype from the SDK's own types, and adding a measured bound.

### [CONCERN] The replay driver hard-codes the run-state directory that `state.py` defines

`RUNS_DIRECTORY = Path(".config") / "squadron" / "runs"` duplicates `_default_runs_dir()` in `src/squadron/pipeline/state.py:350`. The producer writes its state under the scrubbed HOME using its own `StateManager`, and the harness reads from its copy of the path. If the default moves, `_read_state` gets `FileNotFoundError`, every replay classifies as `no_run_state` (a harness absence), and the only hint is the auth-check reminder, which points at the wrong fix. Expose the runs-directory logic from `state.py` as one function and call it with the sandbox home, or have the producer report its run directory.

### [CONCERN] Benchmark tests suppress type errors and use `Any` on the new modules

Pyright strict covers tests, per the Python rules. The new test modules contain many `Any` annotations and `# type: ignore` markers: `test_replay_one.py` (18 matches), `test_fix_case_runner.py` (13), `test_benchmark_run_command.py` (6), `test_replay_show_command.py` (5), `test_bench_runner_run.py` (3), and `test_bench_runner_begin.py` (3). Examples: `def run(self, run_cap: float):  # type: ignore[no-untyped-def]` (`test_bench_runner_run.py:110`), `def replay(case, config, sample):  # type: ignore[no-untyped-def]` (`test_bench_interrupt.py:92`), and `world.runner.run = write_rule_then_run  # type: ignore[method-assign]`.

The suppressions hide the same class of error strict mode exists to catch, and `Any` on the fixture objects means a wrong attribute name passes checking. Annotate the helpers, use `Protocol`s for the doubles, remove the suppressions, and run pyright on `tests/benchmark`.

### [CONCERN] The auth-check reminder is suppressed when a profile's first replay is not `no_run_state`

`ReplayReporter.__call__` adds the profile to `_profiles_seen` on every call (`:44`), before checking the outcome. If a profile's first replay is committed and a later one is `no_run_state`, `first_of_profile` is already false, so the hint never prints for that profile. The docstring promises "once per profile". The test `test_no_run_state_prints_the_auth_check_reminder_once_per_profile` covers only the case where the first replay is `no_run_state`. Track the profiles already hinted, and add the hint only when the profile is not in that set.

### [CONCERN] The producer child process has no wall-clock bound at the harness level

`FixCaseRunner.run` calls the invoker without a timeout, and `run_sq_subprocess` (`src/squadron/replay/runner.py`) is documented as "captured output, no timeout". The harness has timeouts for git and installs (`BENCHMARK_INSTALL_TIMEOUT_KEY`, `BENCHMARK_SUITE_TIMEOUT_KEY`) but none for the producer, which is the longest step. A hung `sq run` blocks the benchmark indefinitely, with no log line or record, while the lock stays held by a live pid. sq's own stall detection may bound this, but the harness does not check. Add a producer timeout from config, classify a timeout as `producer_failed` with a logged reason, and test it.

### [NOTE] Enum location in the replay-models docstring is wrong

The docstring says the enums "live in `benchmark_models` and are defined once there". They are defined in `benchmark_replay_enums.py`, and this module imports them from there (`:19`). Fix the docstring.

### [NOTE] The `fix` pipeline name is defined in two modules

`FIX_PIPELINE_NAME = "fix"` here and `FIX_PIPELINE = "fix"` in `case_runners.py:31` name the same pipeline, once for the producer argv and once for the record. Use one constant.

### [NOTE] The headline bound says "capped at run cap" even when the total is below the cap

`format_bound` always prints "capped at run cap $X", whether or not the pending total reaches the cap. The test `test_headline_below_the_run_cap_is_not_inflated` asserts the same misleading text. Print "within run cap" when the total is below the cap.

### [NOTE] A dangling or out-of-tree `CLAUDE.md` symlink aborts the whole benchmark

`instruction_files` calls `path.read_bytes()` on every matching name. `os.walk` lists symlinks as files, and `read_bytes` follows them, so a dangling symlink raises `FileNotFoundError`. `replay_one` catches only `EnvironmentResolutionError` and `SandboxError`, so this escapes as an unhandled exception, outside the `ReplayStoreError` path that `run_command` handles. No test covers it. Skip or record non-regular entries explicitly, and add a dangling-link test.

### Run Digest

- Response length: 14810 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 32
- Tokens — prompt / cached / cache write / completion / reasoning: 4856745 / 4492935 / 363782 / 73712 / not computed
- Duration: 324.0 s
- Cost: $0.90 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
