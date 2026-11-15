---
docType: review
layer: project
reviewType: code
slice: slice-cases
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/426-slice.slice-cases.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 207d56831828645031d9c706c7ad6d84c67b33ad
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 27
diffTruncated: false
effort: xhigh
turns: 28
promptTokens: 4242051
cachedTokens: 3837940
cacheWriteTokens: 404089
completionTokens: 68379
durationSeconds: 302.1
costUsd: 0.919317
costBasis: provider
runId: run-20261115-p6-26b3510a
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: documentation-drift
    summary: "The build line never says a result was reused, though its docstring claims it does"
    location: "src/squadron/benchmark/slice_case_build.py:100"
  - id: F002
    severity: concern
    category: architectural-decay
    summary: "Three copies of \"run git, map process failures, log\" in the slice-case code"
    location: "src/squadron/benchmark/diff_judge_reference.py:54"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "Re-raising handlers log at ERROR without `logger.exception`, against the project rule"
    location: "src/squadron/replay/cf_registration.py:69"
  - id: F004
    severity: concern
    category: test-debt
    summary: "The mixed-kinds test says it grades, but only fixture helpers create grade records"
    location: "tests/benchmark/test_mixed_kinds.py:77"
  - id: F005
    severity: concern
    category: type-contract-debt
    summary: "New test code hides missing annotations behind suppressions"
    location: "tests/benchmark/test_diff_judge_size.py:20"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "`indices_of` is production code that only a test calls"
    location: "src/squadron/benchmark/slice_discovery.py:149"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "Config readers and the judge timeout key are duplicated in the CLI"
    location: "src/squadron/cli/commands/benchmark_judge.py:136"
  - id: F008
    severity: note
    category: correctness
    summary: "The judge cost cap does not charge calls that fail or time out"
    location: "src/squadron/benchmark/diff_judge_budget.py#metered"
  - id: F009
    severity: note
    category: performance-resource
    summary: "Observed-cost lookup scans the whole store once per stored run"
    location: "src/squadron/cli/commands/benchmark_judge.py#_plan"
  - id: F010
    severity: note
    category: documentation-drift
    summary: "Stale module docstring names the wrong home for `judge`"
    location: "src/squadron/cli/commands/benchmark_slice.py:1"
---

# Review: code — slice 426

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 27 successful tool call(s) of 27 made; 682187 of 682187 diff characters reached the model

## Findings

### [CONCERN] The build line never says a result was reused, though its docstring claims it does

`describe` says ``reused`` is named "when it was not re-run", but it takes only the stored `SliceQualification`, and nothing in the module prints that word. `_settle` (lines 122-126) unpacks `SliceQualifyResult` and returns only `result.record` and `result.kept_paths`, so the `reused` flag set by `qualify_slice_candidate` never reaches the output. The CLI and end-to-end tests in the diff do not assert on it either. Either carry the flag into `describe` so the build line says `reused`, or remove the docstring claim.

### [CONCERN] Three copies of "run git, map process failures, log" in the slice-case code

`slice_git.run_git` (slice_git.py:30-43) already runs a git query and maps `ProcessNotFoundError`, `ProcessCwdNotFoundError` and `ProcessTimedOutError` to a logged error. This diff adds two more copies. `ReferenceDiffReader._git` (lines 26 and 54-60) repeats the same exception tuple and the same log-and-raise. `SliceCaseRunner._current_branch` (slice_runner.py:148-160) repeats the tuple inline and the non-zero-exit handling. They differ only in the exception type they raise (`SliceHarnessError`, `JudgeHalted`, `SandboxError`) and in whether they return a `ProcessResult` or stdout. The tuple is defined twice (slice_git.py:23 and diff_judge_reference.py:26). The codebase already has other git wrappers (`replay_one._git`, `tree_reader`, `qualify_stages.run_git`, `grade_run.run_git`), so this is part of a wider pattern. Still, this slice could use one helper parameterized by the exception type.

### [CONCERN] Re-raising handlers log at ERROR without `logger.exception`, against the project rule

The Python rules require a handler that re-raises to log with `logger.exception`. At line 69, the handler catches a process exception, logs it with `_logger.error(...)`, then raises `CfRegistrationError ... from exc`, so no traceback is logged at the failure point. `SliceCaseRunner.run` in slice_runner.py has the same shape: `_logger.error("cf registration failed for slice ...")` followed by `raise SandboxError(str(exc)) from exc`. Both sites have an exception object, so `logger.exception` is the compliant choice. The non-zero-exit branches (cf_registration.py:73, slice_git.py:41) have no exception to log, so `error` is correct there. The exception chain is preserved, so this is a logging gap rather than a lost error.

### [CONCERN] The mixed-kinds test says it grades, but only fixture helpers create grade records

The test is named `test_a_mixed_case_set_runs_grades_judges_and_reports_each_kind_apart`, and line 77 says "grades: both kinds are graded". The code calls `world.add_sample(...)`, a `report_support` helper that writes replay and grade records directly, then asserts `len(world.grades) == 4 and fix_ids and slice_ids`. Neither `grade_one` nor the grade runner runs, so this assertion would pass with grading broken. Slice-case grading is exercised for real in `test_slice_pipeline_end_to_end.py`, so this is a misleading claim rather than a coverage hole. The name and comment should say grades are fixture-built, or the test should call the grade runner. The `fix_ids and slice_ids` check is a list truthiness test and asserts nothing about the records.

### [CONCERN] New test code hides missing annotations behind suppressions

The Python rules require typed signatures and zero strict-pyright errors, test code included. The new test files suppress the checker instead. Examples:
- `_longest(pairs, normalized) -> int:  # type: ignore[no-untyped-def]` (test_diff_judge_size.py:20)
- `_section(world: ReportWorld, judgments):  # type: ignore[no-untyped-def]` (test_pairwise_report.py:27)
- `_Runner.run(self, case, config, sandbox, caps, record_id):  # type: ignore[no-untyped-def]` (test_mixed_kinds.py:51)
- `watched(prompt: str):  # type: ignore[no-untyped-def]` (test_diff_judge_bound.py:67)

Several helpers have no return annotation and carry `# noqa: ANN20x`. The required ruff set does not enable ANN, so the comment does nothing: `_world` (test_diff_judge_bound.py:23, test_diff_judge_plan.py:37), `_setup` (test_diff_judge_size.py:14), and `registration_factory` (slice_runner_support.py:182). The loosest types are `object` parameters with a call-site suppression: `run_plan(store: object | None)` in diff_judge_run_support.py, and `make_setup(runner: object | None, ...)` with `**overrides: object` in slice_qualify_support.py. Real types already exist for these (`JudgeStore`, `ProcessRunner`, `ReportWorld`), so the suppressions can go.

### [NOTE] `indices_of` is production code that only a test calls

`indices_of` is defined in the production module. Its only caller is `tests/benchmark/test_slice_discovery.py:144`. Move the check into the test or delete the function.

### [NOTE] Config readers and the judge timeout key are duplicated in the CLI

`config/keys.py:40-41` says the judge prompt limit "is read through get_positive_int_config". `benchmark_judge._positive_int` (lines 136-140) is a second validator that calls `get_config` directly and raises `JudgeRefusal` instead. `production_deps._positive_int` is a third wrapper. The result is two error paths for a bad value, and a comment that names a reader the code does not use. The string `"metrology.judge_timeout_s"` is also defined as `JUDGE_TIMEOUT_KEY` in both `benchmark_judge.py:52` and `replay_judge.py:21`. Read the limit through `get_positive_int_config` or one shared helper, and define the timeout key once.

### [NOTE] The judge cost cap does not charge calls that fail or time out

`metered` charges the budget only after `dispatcher(prompt)` returns. A call that raises `JudgeCallError`, or is cancelled by `asyncio.wait_for`, is never charged, and the run moves on to the next pair. The docstring says so, so this is a deliberate choice. Whether it matters depends on whether the provider bills failed or cancelled requests, which the code cannot tell me. If it does bill them, a run whose calls keep timing out can spend past the cap without stopping. The design should state which behaviour is intended, and a test should cover the failure path. The timeout test in `test_diff_judge_resume.py` does not check cost.

### [NOTE] Observed-cost lookup scans the whole store once per stored run

When a judge alias is set, `_plan` loops over every stored run and calls `slice_store.diff_judgments_for(run.benchmark_id, alias)` for each one. Each call iterates all store records through `iter_records()` in `slice_case_store.py`, so the work is runs × records on every `judge` invocation. It is small for one benchmark. Scan once and group by benchmark id if the store grows.

### [NOTE] Stale module docstring names the wrong home for `judge`

The module docstring says "``judge`` joins it in this module", but `judge` lives in `cli/commands/benchmark_judge.py`, which `benchmark.py` imports from. Remove the sentence.

### Run Digest

- Response length: 10789 chars
- Response is newline-free: no
- Tool calls made: 27
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 28
- Tokens — prompt / cached / cache write / completion / reasoning: 4242051 / 3837940 / 404089 / 68379 / not computed
- Duration: 302.1 s
- Cost: $0.92 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
