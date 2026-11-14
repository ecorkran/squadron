---
docType: review
layer: project
reviewType: code
slice: producer-only-replay-runner
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/424-slice.producer-only-replay-runner.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: cd126e56b6214816e0bc27051f06df13f3fffab2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 25
diffTruncated: false
effort: xhigh
turns: 26
promptTokens: 2478254
cachedTokens: 2114331
cacheWriteTokens: 363909
completionTokens: 66515
durationSeconds: 294.7
costUsd: 0.768995
costBasis: provider
runId: run-20261114-p6-24ce0506
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "JSONL reader splits lines on Unicode separators, so valid transcripts can be marked unavailable"
    location: "src/squadron/benchmark/transcripts.py:71"
  - id: F002
    severity: concern
    category: correctness
    summary: "Stale-lock takeover can let two processes both hold the benchmark lock"
    location: "src/squadron/benchmark/bench_lock.py:61-77"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "`producer_config_ref` falls back silently to the SDK profile"
    location: "src/squadron/benchmark/bench_configs.py:56-58"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Replay driver hard-codes fix-pipeline behavior, breaking the case-kind seam"
    location: "src/squadron/benchmark/replay_one.py:150-151"
  - id: F005
    severity: concern
    category: error-handling-observability
    summary: "Instruction files that cannot be read are dropped from the record without a marker"
    location: "src/squadron/benchmark/instruction_files.py:31-42"
  - id: F006
    severity: concern
    category: error-handling-observability
    summary: "The producer subprocess has no timeout"
    location: "src/squadron/replay/runner.py:83-86"
  - id: F007
    severity: concern
    category: architectural-decay
    summary: "`build_production_services` is about 105 lines"
    location: "src/squadron/benchmark/production_deps.py:99-203"
  - id: F008
    severity: concern
    category: architectural-decay
    summary: "Duplicate action helpers in `stats/producer_units.py`"
    location: "src/squadron/stats/producer_units.py:152-158"
  - id: F009
    severity: concern
    category: test-debt
    summary: "Test seams hide untyped signatures behind `type: ignore`"
    location: "tests/benchmark/test_bench_interrupt.py:92"
  - id: F010
    severity: concern
    category: type-contract-debt
    summary: "Test double's `_Runner` likely violates the `CaseKindRunner` protocol under pyright strict"
    location: "tests/benchmark/test_bench_refusals.py:46-58"
  - id: F011
    severity: note
    category: consistency-rot
    summary: "Benchmark CLI repeats validation to narrow a type"
    location: "src/squadron/cli/commands/benchmark_run.py:207"
  - id: F012
    severity: note
    category: type-contract-debt
    summary: "`build_record` takes untyped keyword arguments"
    location: "src/squadron/benchmark/replay_records.py:34"
  - id: F013
    severity: note
    category: architectural-decay
    summary: "`BenchmarkRecordStore` deletes through the storage layer"
    location: "src/squadron/metrology/benchmark_store.py:245"
  - id: F014
    severity: note
    category: correctness
    summary: "\"Installed package\" protects the whole site-packages directory"
    location: "src/squadron/benchmark/leak_rule_source.py:41"
  - id: F015
    severity: pass
    category: correctness
    summary: "Producer-only phase config strips review and checkpoint correctly"
    location: "src/squadron/pipeline/steps/phase.py:286-304"
  - id: F016
    severity: pass
    category: correctness
    summary: "Producer-only resume reload handles a changed pipeline"
    location: "src/squadron/cli/commands/run.py:244-269"
  - id: F017
    severity: pass
    category: correctness
    summary: "The new budget error does not change retry behavior"
    location: "src/squadron/providers/errors.py:73"
---

# Review: code — slice 424

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 25 successful tool call(s) of 25 made; 580602 of 580602 diff characters reached the model

## Findings

### [CONCERN] JSONL reader splits lines on Unicode separators, so valid transcripts can be marked unavailable

`iter_jsonl` iterates `text.splitlines()`. Python's `splitlines` also breaks on U+2028, U+2029 and U+0085, and Node's `JSON.stringify` does not escape those characters. A valid transcript line whose string holds one of them is split into two invalid JSON fragments. Each fragment becomes a "not JSON" problem, and `scan()` then returns `scan_unavailable` for a run that may be clean. The fixtures contain none of these characters, so no test catches this. Split on `"\n"` only, strip a trailing `"\r"`, and add a fixture line containing U+2028.

### [CONCERN] Stale-lock takeover can let two processes both hold the benchmark lock

Two invocations that find the same dead owner can both reach the takeover. Process A reads the dead holder, unlinks it, and links its own lock. Process B, having read the same dead holder, then unlinks at line 75, which removes A's live lock, and links its own. Both return a `BenchmarkLock` and both dispatch replays for the same benchmark id. The code comment promises that takeover is safe, and the test suite covers only single-process takeover. Use a compare-and-delete (re-read and confirm the file is still the dead holder's, using inode or content) or a second atomic takeover step, and add a test that interleaves two takeovers.

### [CONCERN] `producer_config_ref` falls back silently to the SDK profile

`profile or ProfileName.SDK` substitutes a magic profile when the alias has none. The project rules forbid silent fallbacks, and the `production_deps` docstring claims "nothing here has a default," which this contradicts. Planning refuses profile-less aliases today, so the path is not reachable yet. Raise, as `_leak_result` in `replay_one.py` already does, and add a test.

### [CONCERN] Replay driver hard-codes fix-pipeline behavior, breaking the case-kind seam

The `case_runners.py` docstring says `replay_one` "calls only this protocol, so adding a kind means writing a runner and registering it, not editing the replay driver." That is not true of this diff:
- `replay_one.py:150-151` computes the issue SHA-256 from `case.task_text` in the generic driver.
- `replay_outcome.py:88-102` (`_frozen_text_problem`) checks `fix-context` outputs, a fix-only action, and `classify_producer_run` takes the SHA as an argument.
- `replay_records.py:9, 20, 49-50` hard-codes `FIX_PIPELINE` and `FIX_PRODUCER_STEP` in `build_record`.

Slice 426 would have to edit the driver. Move the frozen-text check and the pipeline/step identity behind `CaseKindRunner`, so each runner supplies its own classification inputs and record identity.

### [CONCERN] Instruction files that cannot be read are dropped from the record without a marker

`_digest` returns `None` for an out-of-tree symlink or an unreadable file and logs a WARNING. `instruction_files` then omits it. The stored record has no trace of the omission. Decision D5 exists so a result is "never compared across different instructions without saying so," and this breaks that promise. Record excluded files with a reason, or fail the replay as harness-absent.

### [CONCERN] The producer subprocess has no timeout

`run_sq_subprocess` is documented as "captured output, no timeout," and `FixCaseRunner` uses it as the default invoker. The Failure-Mode Enumeration rule requires an explicit answer to "what if this hangs?" The code has none. A hung `sq run` holds the benchmark lock indefinitely and blocks every later replay. Add a producer timeout key alongside the existing install, suite and probe timeouts, map expiry to an observable outcome, and add a test for that outcome.

### [CONCERN] `build_production_services` is about 105 lines

The function spans lines 99 to 203 and holds four nested closures (`sandbox_at`, `kept_sandboxes`, `replay_function`, and the qualify wiring). The project guideline is about 50 lines per function. Extract the qualify-deps and leak-rule wiring into builders that each return one collaborator.

### [CONCERN] Duplicate action helpers in `stats/producer_units.py`

This diff made `first_action` and `action_metadata` public in `replay/outcome.py` so the benchmark could reuse them. `producer_units.py` still has private copies with the same bodies (`_first_action`, `_metadata`). Import the shared helpers instead.

### [CONCERN] Test seams hide untyped signatures behind `type: ignore`

The project runs strict pyright over tests too. Several test seams suppress the checker instead of being typed:
- `test_bench_interrupt.py:92`: `def replay(case, config, sample):  # type: ignore[no-untyped-def]`
- `test_bench_runner_run.py:110`: `def run(self, run_cap: float):` with no return annotation.
- `interrupt_support.py:100`: `# type: ignore[return-value]` on `store.get_replay(...)`, which returns `Optional`. A missing record would reach the test as `None` without failing.
- `test_benchmark_run_command.py:119-120`: suppressions on the test doubles' return types.

Annotate these properly. Without that, the strict-mode gate does not cover the seams that matter most.

### [CONCERN] Test double's `_Runner` likely violates the `CaseKindRunner` protocol under pyright strict

`_Runner.run` takes `sandbox: BenchmarkSandbox`, but `CaseKindRunner.run` declares `sandbox: ReplaySandbox`. `_Runner` is then passed wherever `CaseKindRunner` is expected. Method parameters are contravariant, so pyright strict should reject this, and under the project rule a strict-mode error is a merge blocker. I could not run pyright to confirm. Annotate the parameter as `ReplaySandbox` and run the check.

### [NOTE] Benchmark CLI repeats validation to narrow a type

`_run` re-checks `samples is None` with the comment "check_plan refused this already; this narrows the type." The second check uses different wording from `check_plan`. Have `check_plan` return the narrowed value, or pass a validated type through.

### [NOTE] `build_record` takes untyped keyword arguments

`build_record(deps, case, sample, record_id, **fields: object)` loses all type checking. `ImplementationReplay` uses pydantic's default `extra="ignore"`, so a misspelled keyword is dropped silently and only surfaces if it was required. Replace the kwargs with explicit typed parameters.

### [NOTE] `BenchmarkRecordStore` deletes through the storage layer

`delete_replays` calls `self._store.record_location(record_id).unlink()`. That leaks the file layout into the benchmark store. Deletion belongs on `MetrologyStore`.

### [NOTE] "Installed package" protects the whole site-packages directory

`installed_package_location()` returns the directory that contains the `squadron` package, which is site-packages. `LeakRules` documents this as the "harness install location," but in practice every installed library becomes a protected root and reading any of them counts as a leak. Narrow it to the squadron package directory, or document the wider scope.

### [PASS] Producer-only phase config strips review and checkpoint correctly

I checked the expansion directly. `checkpoint` is appended only inside the `if review is not None:` block, so dropping the `review` and `checkpoint` keys is the whole change, as `producer_only_config` claims.

### [PASS] Producer-only resume reload handles a changed pipeline

After the `ProducerOnlyError` branch the function falls through to `raise typer.Exit(1)`, so a reload against a changed pipeline cannot return an unnarrowed definition.

### [PASS] The new budget error does not change retry behavior

`BudgetExhaustedError` subclasses `ProviderAPIError`, but a grep of `src/squadron` finds no `except` or `isinstance` that branches on `ProviderAPIError`. The subclass changes no retry path. Failure classification is handled by `cost_cap_stamp`, which runs after the generic provider-error stamp in `dispatch.py`.

### Run Digest

- Response length: 11397 chars
- Response is newline-free: no
- Tool calls made: 25
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 26
- Tokens — prompt / cached / cache write / completion / reasoning: 2478254 / 2114331 / 363909 / 66515 / not computed
- Duration: 294.7 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 17
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 17
- Finding-shaped matches — surviving validation: 17

### Raw Response

I'll start by confirming the working tree matches the branch under review, then check the specific risk points I found while reading the diff.
The line-length setting is 104 in `pyproject.toml`, so the 88-column count above is not a real violation. `producer_units.py` still has private copies of helpers that this diff made public, which I'll check. Next I'm pinning down exact line numbers for the candidate findings.
Several concrete leads are confirmed by line number. Next I'm reading the code around each one to verify the behavior, not just the grep hit.
The reminder is the same Python rules file as before, so nothing changes. Continuing verification: next I'm checking the duplicated stats helpers, the length of `build_production_services`, the phase checkpoint claim, and how a mistyped cap is handled on the SDK path.
The phase-step claim depends on whether `checkpoint` sits inside the `if review is not None:` block, and the `build_production_services` span is now confirmed at about 105 lines. Reading the phase expansion and the SDK cap error path before deciding severities.
Both reminders are the project's own rules files, so there's nothing new to act on. The phase-step claim holds: `checkpoint` is inside the `if review is not None:` block (phase.py:286-304). The `_load_run_definition` path is fine too: after the `ProducerOnlyError` branch it falls through to `raise typer.Exit(1)`. Last step is pinning line numbers for the test-double and CLI findings.
## Summary

**Verdict: CONCERNS**

No finding blocks correctness outright. Several need fixing before this slice merges: a transcript parser that can mis-report clean runs as unavailable, a benchmark lock race, a silent fallback the project's rules forbid, and a replay driver that breaks the case-kind seam the design promises.

Verification limits: this session had only Read, Grep and Glob, so I could not run `git diff`, `ruff`, `pyright` or `pytest`. I read the working-tree files at the branch. The session's git status was clean, but I did not confirm HEAD matches the diff's tip. The pyright finding below is unverified for that reason.

## Findings

### [CONCERN] JSONL reader splits lines on Unicode separators, so valid transcripts can be marked unavailable
category: correctness
location: src/squadron/benchmark/transcripts.py:71

`iter_jsonl` iterates `text.splitlines()`. Python's `splitlines` also breaks on U+2028, U+2029 and U+0085, and Node's `JSON.stringify` does not escape those characters. A valid transcript line whose string holds one of them is split into two invalid JSON fragments. Each fragment becomes a "not JSON" problem, and `scan()` then returns `scan_unavailable` for a run that may be clean. The fixtures contain none of these characters, so no test catches this. Split on `"\n"` only, strip a trailing `"\r"`, and add a fixture line containing U+2028.

### [CONCERN] Stale-lock takeover can let two processes both hold the benchmark lock
category: correctness
location: src/squadron/benchmark/bench_lock.py:61-77

Two invocations that find the same dead owner can both reach the takeover. Process A reads the dead holder, unlinks it, and links its own lock. Process B, having read the same dead holder, then unlinks at line 75, which removes A's live lock, and links its own. Both return a `BenchmarkLock` and both dispatch replays for the same benchmark id. The code comment promises that takeover is safe, and the test suite covers only single-process takeover. Use a compare-and-delete (re-read and confirm the file is still the dead holder's, using inode or content) or a second atomic takeover step, and add a test that interleaves two takeovers.

### [CONCERN] `producer_config_ref` falls back silently to the SDK profile
category: error-handling-observability
location: src/squadron/benchmark/bench_configs.py:56-58

`profile or ProfileName.SDK` substitutes a magic profile when the alias has none. The project rules forbid silent fallbacks, and the `production_deps` docstring claims "nothing here has a default," which this contradicts. Planning refuses profile-less aliases today, so the path is not reachable yet. Raise, as `_leak_result` in `replay_one.py` already does, and add a test.

### [CONCERN] Replay driver hard-codes fix-pipeline behavior, breaking the case-kind seam
category: architectural-decay
location: src/squadron/benchmark/replay_one.py:150-151

The `case_runners.py` docstring says `replay_one` "calls only this protocol, so adding a kind means writing a runner and registering it, not editing the replay driver." That is not true of this diff:
- `replay_one.py:150-151` computes the issue SHA-256 from `case.task_text` in the generic driver.
- `replay_outcome.py:88-102` (`_frozen_text_problem`) checks `fix-context` outputs, a fix-only action, and `classify_producer_run` takes the SHA as an argument.
- `replay_records.py:9, 20, 49-50` hard-codes `FIX_PIPELINE` and `FIX_PRODUCER_STEP` in `build_record`.

Slice 426 would have to edit the driver. Move the frozen-text check and the pipeline/step identity behind `CaseKindRunner`, so each runner supplies its own classification inputs and record identity.

### [CONCERN] Instruction files that cannot be read are dropped from the record without a marker
category: error-handling-observability
location: src/squadron/benchmark/instruction_files.py:31-42

`_digest` returns `None` for an out-of-tree symlink or an unreadable file and logs a WARNING. `instruction_files` then omits it. The stored record has no trace of the omission. Decision D5 exists so a result is "never compared across different instructions without saying so," and this breaks that promise. Record excluded files with a reason, or fail the replay as harness-absent.

### [CONCERN] The producer subprocess has no timeout
category: error-handling-observability
location: src/squadron/replay/runner.py:83-86

`run_sq_subprocess` is documented as "captured output, no timeout," and `FixCaseRunner` uses it as the default invoker. The Failure-Mode Enumeration rule requires an explicit answer to "what if this hangs?" The code has none. A hung `sq run` holds the benchmark lock indefinitely and blocks every later replay. Add a producer timeout key alongside the existing install, suite and probe timeouts, map expiry to an observable outcome, and add a test for that outcome.

### [CONCERN] `build_production_services` is about 105 lines
category: architectural-decay
location: src/squadron/benchmark/production_deps.py:99-203

The function spans lines 99 to 203 and holds four nested closures (`sandbox_at`, `kept_sandboxes`, `replay_function`, and the qualify wiring). The project guideline is about 50 lines per function. Extract the qualify-deps and leak-rule wiring into builders that each return one collaborator.

### [CONCERN] Duplicate action helpers in `stats/producer_units.py`
category: architectural-decay
location: src/squadron/stats/producer_units.py:152-158

This diff made `first_action` and `action_metadata` public in `replay/outcome.py` so the benchmark could reuse them. `producer_units.py` still has private copies with the same bodies (`_first_action`, `_metadata`). Import the shared helpers instead.

### [CONCERN] Test seams hide untyped signatures behind `type: ignore`
category: test-debt
location: tests/benchmark/test_bench_interrupt.py:92

The project runs strict pyright over tests too. Several test seams suppress the checker instead of being typed:
- `test_bench_interrupt.py:92`: `def replay(case, config, sample):  # type: ignore[no-untyped-def]`
- `test_bench_runner_run.py:110`: `def run(self, run_cap: float):` with no return annotation.
- `interrupt_support.py:100`: `# type: ignore[return-value]` on `store.get_replay(...)`, which returns `Optional`. A missing record would reach the test as `None` without failing.
- `test_benchmark_run_command.py:119-120`: suppressions on the test doubles' return types.

Annotate these properly. Without that, the strict-mode gate does not cover the seams that matter most.

### [CONCERN] Test double's `_Runner` likely violates the `CaseKindRunner` protocol under pyright strict
category: type-contract-debt
location: tests/benchmark/test_bench_refusals.py:46-58

`_Runner.run` takes `sandbox: BenchmarkSandbox`, but `CaseKindRunner.run` declares `sandbox: ReplaySandbox`. `_Runner` is then passed wherever `CaseKindRunner` is expected. Method parameters are contravariant, so pyright strict should reject this, and under the project rule a strict-mode error is a merge blocker. I could not run pyright to confirm. Annotate the parameter as `ReplaySandbox` and run the check.

### [NOTE] Benchmark CLI repeats validation to narrow a type
category: consistency-rot
location: src/squadron/cli/commands/benchmark_run.py:207

`_run` re-checks `samples is None` with the comment "check_plan refused this already; this narrows the type." The second check uses different wording from `check_plan`. Have `check_plan` return the narrowed value, or pass a validated type through.

### [NOTE] `build_record` takes untyped keyword arguments
category: type-contract-debt
location: src/squadron/benchmark/replay_records.py:34

`build_record(deps, case, sample, record_id, **fields: object)` loses all type checking. `ImplementationReplay` uses pydantic's default `extra="ignore"`, so a misspelled keyword is dropped silently and only surfaces if it was required. Replace the kwargs with explicit typed parameters.

### [NOTE] `BenchmarkRecordStore` deletes through the storage layer
category: architectural-decay
location: src/squadron/metrology/benchmark_store.py:245

`delete_replays` calls `self._store.record_location(record_id).unlink()`. That leaks the file layout into the benchmark store. Deletion belongs on `MetrologyStore`.

### [NOTE] "Installed package" protects the whole site-packages directory
category: correctness
location: src/squadron/benchmark/leak_rule_source.py:41

`installed_package_location()` returns the directory that contains the `squadron` package, which is site-packages. `LeakRules` documents this as the "harness install location," but in practice every installed library becomes a protected root and reading any of them counts as a leak. Narrow it to the squadron package directory, or document the wider scope.

### [PASS] Producer-only phase config strips review and checkpoint correctly
category: correctness
location: src/squadron/pipeline/steps/phase.py:286-304

I checked the expansion directly. `checkpoint` is appended only inside the `if review is not None:` block, so dropping the `review` and `checkpoint` keys is the whole change, as `producer_only_config` claims.

### [PASS] Producer-only resume reload handles a changed pipeline
category: correctness
location: src/squadron/cli/commands/run.py:244-269

After the `ProducerOnlyError` branch the function falls through to `raise typer.Exit(1)`, so a reload against a changed pipeline cannot return an unnarrowed definition.

### [PASS] The new budget error does not change retry behavior
category: correctness
location: src/squadron/providers/errors.py:73

`BudgetExhaustedError` subclasses `ProviderAPIError`, but a grep of `src/squadron` finds no `except` or `isinstance` that branches on `ProviderAPIError`. The subclass changes no retry path. Failure classification is handled by `cost_cap_stamp`, which runs after the generic provider-error stamp in `dispatch.py`.
