---
docType: review
layer: project
reviewType: code
slice: producer-only-replay-runner
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/424-slice.producer-only-replay-runner.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261114
dateUpdated: 20261114
reviewedSha: 2e25cfb7e15f976389255500d57328ae9ae3041e
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 29
diffTruncated: false
effort: xhigh
turns: 30
promptTokens: 3156096
cachedTokens: 2801273
cacheWriteTokens: 354805
completionTokens: 73455
durationSeconds: 322.2
costUsd: 0.814957
costBasis: provider
runId: run-20261114-p6-24ce0506
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Leak scan misses env-prefixed git directories and key=value path arguments"
    location: "src/squadron/benchmark/leak_git_package.py#_git_hits"
  - id: F002
    severity: concern
    category: correctness
    summary: "Unbalanced quotes and sudo wrappers hide git, host, and package invocations"
    location: "src/squadron/benchmark/leak_shell.py#command_tokens"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Candidate-rebuild and producer-environment errors escape the CLI's handler list"
    location: "src/squadron/benchmark/case_runners.py:158-164"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "The producer subprocess has no wall-clock bound"
    location: "src/squadron/replay/runner.py#run_sq_subprocess"
  - id: F005
    severity: note
    category: correctness
    summary: "Prompt-only stop line omits the commit sha"
    location: "src/squadron/cli/commands/run.py:979-985"
  - id: F006
    severity: note
    category: type-contract-debt
    summary: "SDK budget keyword is passed through a conditional splat"
    location: "src/squadron/pipeline/sdk_session.py:705"
  - id: F007
    severity: note
    category: architectural-decay
    summary: "Store construction and benchmark id are duplicated"
    location: "src/squadron/benchmark/production_deps.py:208"
  - id: F008
    severity: note
    category: type-contract-debt
    summary: "CaseDrop's reason type loses the rejection enum"
    location: "src/squadron/metrology/benchmark_replay_models.py#CaseDrop"
  - id: F009
    severity: note
    category: documentation-drift
    summary: "Docstring says \"link\" where the code copies"
    location: "src/squadron/benchmark/scrubbed_env.py:140-141"
  - id: F010
    severity: note
    category: test-debt
    summary: "Tests import helpers from other test modules"
    location: "tests/benchmark/test_bench_runner_run.py"
---

# Review: code — slice 424

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 29 successful tool call(s) of 29 made; 596791 of 596791 diff characters reached the model

## Findings

### [CONCERN] Leak scan misses env-prefixed git directories and key=value path arguments

The git rule reads only `invocation.args`, but `_strip_prefixes` (`leak_shell.py`, line 82) removes leading `NAME=value` words before the invocation is built. So `GIT_DIR=/home/u/checkout/.git git log --all` yields args `("log", "--all")`: no `-C`, no hit. The path rule has the same hole from the other side. `_candidates` (`leak_paths.py:34-37`) splits only `--opt=value` tokens, and `_as_path` (`leak_paths.py:49`) judges a token only if it starts with `/` or `~` or climbs with `..`. So `dd if=~/.ssh/id_rsa` and `FOO=/abs/path cat` are never judged. Neither gap is in the known-gaps list in `leak_paths.py`'s docstring, and no test in `test_leak_rule_git_package.py` or `test_leak_rule_paths.py` covers them. Fix by judging `NAME=value` words (as env prefixes for `GIT_DIR`/`GIT_WORK_TREE`, and as option-style values), add both cases to the hit lists, and bump `LEAK_RULES_VERSION`, since replays already scanned under v1 must not look equivalent.

### [CONCERN] Unbalanced quotes and sudo wrappers hide git, host, and package invocations

Two parser gaps. (a) On an unbalanced quote, `command_tokens` falls back to `_TOKEN_FALLBACK.findall` (line 57), whose pattern (line 35) excludes `;|&()`, so every separator is dropped. `ls; gh issue view "3` becomes one command with program `ls`, and the GIT_OR_HOST rule misses `gh`. The docstring says the fallback keeps evidence of intent, and losing the separators defeats that for the git and package rules. (b) `_strip_prefixes` reads `sudo -u bob gh` as program `bob`, because the option value is not consumed. The comment at line 26 says this is deliberate, but the effect is a missed `gh`. Fix: keep operator tokens in the fallback, consume the value of known wrapper options, and add both shapes to the hit lists in `test_leak_rule_git_package.py`.

### [CONCERN] Candidate-rebuild and producer-environment errors escape the CLI's handler list

`FixCaseRunner.requalify` calls `candidate_from_case` through `self._candidate_for`, which raises `BuildHalted` (`build_errors.py:10`). Nothing on the replay path catches it. The only place it becomes a refusal is `LeakRuleSource._owner_and_name` (`leak_rule_source.py:92-93`), which runs later, inside the replay. `run_command` catches only `BenchmarkRefusal`, `MetrologyStoreError`, and `ReplayStoreError` (`benchmark_run.py:263`). So a closing commit that cannot be read produces a traceback after the record has been written as `running`. Two more plain `Exception` subclasses escape the same way: `MissingCredentialError` (`scrubbed_env.py:39`, raised from `variables` at line 179, reached through `producer_env`) and `MissingHarnessHomeError` (`scrubbed_env.py:47`, from `_real_home`, reached through `grant_carryover_into_home`). The lock is released in `finally`, and the next invocation reports the interruption, so the outcome is safe but noisy. Convert these to `BenchmarkRefusal` at the replay boundary, or add them to the CLI's catch list with a message that names the fix, and add a test for one of them.

### [CONCERN] The producer subprocess has no wall-clock bound

`run_sq_subprocess` is documented as "captured output, no timeout" and calls `subprocess.run` without a timeout. It is now the benchmark's producer invoker (`production_deps.py`), so each replay is an unbounded wait that holds the benchmark lock. The same module bounds sandbox resolution with `_RESOLUTION_TIMEOUT_SECONDS` (`runner.py:234`), and the benchmark already has install and suite timeout keys. The per-replay cost cap bounds spend, not time, and `sq` may have its own stall detection (`FailureKind.STALL`) that covers model-side hangs; I did not verify which hangs that detection covers. The failure-mode rule asks the author to answer "what if this hangs" explicitly for every new I/O path. Either add a configured timeout that maps to a logged, recorded failure with a test, or state in the docstring why the stall detector suffices.

### [NOTE] Prompt-only stop line omits the commit sha

`_handle_prompt_only_next` builds `completed` with `step_results=[]`, so `commit_sha_of` returns `None`. A fresh run prints `(commit <sha>)` and a prompt-only run does not. `test_run_producer_only_prompt.py` encodes the gap by asserting the line without a commit. Pass the commit sha through the step results so both paths print the same line.

### [NOTE] SDK budget keyword is passed through a conditional splat

`**({} if max_budget_usd is None else {"max_budget_usd": max_budget_usd})` hides the keyword from pyright. The installed SDK's `ClaudeAgentOptions.max_budget_usd` defaults to `None` (`claude_agent_sdk/types.py`, around line 2424), so `max_budget_usd=max_budget_usd` works and matches its neighbours.

### [NOTE] Store construction and benchmark id are duplicated

`build_production_services` builds `BenchmarkRecordStore(MetrologyStore(store_dir=resolve_store_dir(...)))` directly, although `open_store` in `cli/commands/benchmark_common.py` exists for this and converts `MetrologyStoreError` into a stderr exit. Separately, `benchmark_run.py:132` recomputes `benchmark_id` that `build_plan` already computes. Use the shared helper and read the id from the plan.

### [NOTE] CaseDrop's reason type loses the rejection enum

`reason: CandidateRejection | str` makes the field ambiguous. By reading, pydantic's union resolution will return a stored value as a plain `str`, which is why the report code calls `str(...)` on it. The round-trip test passes only because a `StrEnum` compares equal to its string value. Consider storing the enum and a separate free-text detail.

### [NOTE] Docstring says "link" where the code copies

`grant_carryover_into_home` says it links the grant's files into the home, but `_link_carryover` copies them, and its own comment says "A copy, not a symlink." Correct the docstring. `BenchmarkSandbox.producer_env` repeats the wrong wording.

### [NOTE] Tests import helpers from other test modules

The run tests import `Env`, `NOW`, `OPUS`, and `OPUS_REF` from `test_bench_runner_begin`, `World` and `CONFIG` from `test_replay_one`, and `fix_case` from `test_fix_case_runner`. `interrupt_support.py` also imports the private `_replay` from the metrology tests. The testing rules put shared fixtures in `conftest.py` or a support module. Move these helpers there so test modules stay independent.

### Run Digest

- Response length: 10385 chars
- Response is newline-free: no
- Tool calls made: 29
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 30
- Tokens — prompt / cached / cache write / completion / reasoning: 3156096 / 2801273 / 354805 / 73455 / not computed
- Duration: 322.2 s
- Cost: $0.81 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
