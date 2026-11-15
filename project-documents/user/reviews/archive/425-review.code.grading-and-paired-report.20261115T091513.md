---
docType: review
layer: project
reviewType: code
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 965f822367d896740c7b17fed4e5d39cd673d2a7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 17
diffTruncated: false
effort: xhigh
turns: 18
promptTokens: 2342457
cachedTokens: 2006527
cacheWriteTokens: 335916
completionTokens: 64111
durationSeconds: 277.8
costUsd: 0.727244
costBasis: provider
runId: run-20261114-p6-27f2e9a4
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Report drops this benchmark's estimate when a newer benchmark shares its case set"
    location: "src/squadron/cli/commands/benchmark_grade.py:274"
  - id: F002
    severity: concern
    category: correctness
    summary: "Duplicate (case, config, sample) records are silently overwritten"
    location: "src/squadron/benchmark/grade_matrix.py:190"
  - id: F003
    severity: concern
    category: correctness
    summary: "A failed review's spend is charged to the budget but missing from the grade record"
    location: "src/squadron/benchmark/grade_prepare.py:102-114"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "Producer-controlled non-UTF-8 bytes crash the whole grade run instead of recording an absence"
    location: "src/squadron/benchmark/python_grading.py:75"
  - id: F005
    severity: concern
    category: type-contract-debt
    summary: "Test helpers suppress missing-annotation errors with `type: ignore` (36 occurrences in 21 files)"
    location: "tests/benchmark/report_support.py#grade_result"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "`read_review_floor_runs` is dead in production"
    location: "src/squadron/benchmark/grading_config.py#read_review_floor_runs"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "Identity-text formatting is duplicated"
    location: "src/squadron/benchmark/report_rows.py#identity_label"
  - id: F008
    severity: note
    category: other
    summary: "Estimate labels fall back to raw identity JSON"
    location: "src/squadron/benchmark/bench_report_render.py:125"
  - id: F009
    severity: note
    category: architectural-decay
    summary: "The grade planner imports a constant from the executor module"
    location: "src/squadron/benchmark/grade_plan.py:17"
  - id: F010
    severity: note
    category: other
    summary: "A reinstall's resolved environment identity is discarded"
    location: "src/squadron/benchmark/grade_prepare.py:154"
---

# Review: code — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 16 successful tool call(s) of 17 made; 583129 of 583129 diff characters reached the model

## Findings

### [CONCERN] Report drops this benchmark's estimate when a newer benchmark shares its case set

`_report` gets the estimate with `latest_estimate(loaded.run.case_set)`, which returns the newest estimate across every benchmark on that case set. It then keeps the result only if `benchmark_id` matches (line 285). The design stores one estimate per benchmark (`estimate_id(benchmark_id)`, slice design line 178). If benchmark B on the same case set is graded after benchmark A, A's report silently omits its own sample-count section. The test `test_an_estimate_of_another_benchmark_is_not_shown` (tests/cli/test_benchmark_report.py) only covers one stored estimate, so it cannot catch this. The fix is a lookup by benchmark id in `GradeRecordStore`, which currently has no such method.

### [CONCERN] Duplicate (case, config, sample) records are silently overwritten

`build_matrix` stores cells in `by_case_row[case][row][replay.sample] = ...`. If two replays share a case, identity, and sample index, the second silently replaces the first. That can happen when two aliases share an identity and both sample index 0. `_exclusion` then counts the surviving k cells and includes the case, so one config's records vanish without an error. The test `test_two_aliases_with_one_identity_give_one_row` (tests/benchmark/test_bench_report_inclusion.py) avoids the collision by giving the two aliases sample indices 0 and 1. That hides the problem. The collision should raise, or the two aliases should be merged explicitly.

### [CONCERN] A failed review's spend is charged to the budget but missing from the grade record

In `review_once`, a `ReviewFailed` charges `exc.cost_usd` to the budget (line 105), but `run.review_costs.append` runs only on success (line 114). `GradeRun.grading_cost_usd()` sums only `review_costs`, so an absent record's `grading_cost_usd` leaves out a failed review's cost. The run summary's `spent` includes it, and the stored records do not, so `grading_cost_total` in the report under-counts. The failed cost should be recorded alongside the successful ones.

### [CONCERN] Producer-controlled non-UTF-8 bytes crash the whole grade run instead of recording an absence

`_producer_pyproject` calls `path.read_text(encoding="utf-8")` outside any handler. `_parse` only catches `TOMLDecodeError`, and `restore_config` only catches `ProducerConfigError`. A producer's `pyproject.toml` with invalid UTF-8 therefore raises `UnicodeDecodeError` out of `grade_one`, and `run_grading` only catches `GradeCapReached`. The whole `sq benchmark grade` invocation aborts with a traceback. The same pattern is in `python_injection.py:241` (`_same_name_tests`) and `:263` (`_same_name_fixtures`): `read_text` sits inside a `try` that catches only `SyntaxError`. Decoding failures on producer files should become `ProducerConfigError`, which is recorded as a `producer_env_unresolvable` absence, and no test covers this path.

### [CONCERN] Test helpers suppress missing-annotation errors with `type: ignore` (36 occurrences in 21 files)

Examples: `def grade_result(passed: bool = True, **kwargs: Any):  # type: ignore[no-untyped-def]`, plus `graded(world, diff)` in `test_grade_one_hidden.py`, `SandboxFactory.__call__` in `grade_support.py`, and `fix_data(world)` in `test_bench_report_grades.py`. The project rules require type-hinting every signature and running pyright strict over tests. These suppressions hide the untyped signatures instead of fixing them. I could not run pyright, so I have not confirmed the resulting error count.

### [NOTE] `read_review_floor_runs` is dead in production

The production path reads the floor-runs key through `_config_value(check_review_floor_runs, ...)` in `benchmark_grade.py`. `read_review_floor_runs` has no caller in `src/`; only tests use it. That leaves two readers for one key. Remove it, or make the production path call it.

### [NOTE] Identity-text formatting is duplicated

`identity_label` repeats the `profile or "no profile"` and `effort …` formatting from `config_text` (`report_rows.py:33-36`). The two can drift apart. Share one formatter.

### [NOTE] Estimate labels fall back to raw identity JSON

`labels.get(pair.config_a, pair.config_a)` shows the raw canonical identity JSON when no row has that identity. This is a silent fallback, which the project rules prohibit. The row set is built from the same included cases, so the fallback should rarely fire, but when it does the output is unlabeled rather than an error.

### [NOTE] The grade planner imports a constant from the executor module

`grade_plan` imports `GRADER_VERSION` from `grade_one`, which pulls in sandbox, git, and review code. Move the version constant to a small config or identity module.

### [NOTE] A reinstall's resolved environment identity is discarded

`reinstall_if_dependencies_changed` ignores the identity that `BenchmarkSandbox.reinstall()` returns. The records keep only the start environment's digest, the lockfile hash, and a `reinstalled` flag. This matches the design's "identity keeps naming the start environment" (D5), but the environment that actually ran the tests is not recorded. Confirm this is intended.

### Run Digest

- Response length: 8485 chars
- Response is newline-free: no
- Tool calls made: 17
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 18
- Tokens — prompt / cached / cache write / completion / reasoning: 2342457 / 2006527 / 335916 / 64111 / not computed
- Duration: 277.8 s
- Cost: $0.73 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10

### Raw Response

I'll verify the diff's key claims against the working tree before reporting. I can read and search here but can't run ruff, pyright, or the tests, so I'll say so in the summary.
Bash isn't available, so I'll verify by reading and searching only. Next I'll read the specific code paths behind the candidate findings.
Confirmed so far: the report's estimate lookup (`benchmark_grade.py:274-285`) uses the newest estimate for the case set and drops it if it belongs to another benchmark. `normalize_result_categories` maps categories to valid enum values, so `ReviewCategory(...)` in `grade_review._findings` can't raise. Next I'll check the review-cost path, the sandbox protocol, and the enum that `REINSTALL_ABSENCE` has to cover.
The review-cost gap is confirmed: a failed review is charged to the budget but never added to `review_costs`, so the absent record under-reports spend. All five `EnvironmentFailureReason` members are covered, so that `KeyError` isn't reachable. Next I'll check the design for the run order and the estimate lookup, then the matrix overwrite.
The design (line 146) specifies sample-major order per case, so the run-order concern is not a defect and I'm dropping it. The estimate design (line 178) is one record per benchmark, which makes the report's latest-per-case-set lookup a real bug. I'll check the remaining candidates next: producer-controlled decoding and the layering and typing items.
## Summary

**Overall: CONCERNS.** I found no FAIL-level defects. Five items need fixing, and five notes are cleanup or design-level.

I read the working-tree files behind each finding. Bash is disabled in this session, so I did not run ruff, pyright, or pytest. The lint, typecheck, and test status of this branch is unverified.

Checked and ruled out, so they are not findings:
- Run order matches the slice design (`425-slice...md:146`): references first, then replays sample-major within each case.
- `REINSTALL_ABSENCE` covers all five `EnvironmentFailureReason` members, so no `KeyError` is reachable.
- `normalize_result_categories` only emits valid `ReviewCategory` values, so `ReviewCategory(...)` in `grade_review._findings` cannot raise.
- `BenchmarkSandbox` implements `__enter__`/`__exit__`, `tree`, `identity`, `keep`, `context`, `run_suite`, and `process_env`, so it satisfies the sandbox factory contract.
- `tomli-w` is declared in `pyproject.toml`, and the `line-length = 104` config matches the long lines in the diff.

## Findings

### [CONCERN] Report drops this benchmark's estimate when a newer benchmark shares its case set
category: correctness
location: src/squadron/cli/commands/benchmark_grade.py:274

`_report` gets the estimate with `latest_estimate(loaded.run.case_set)`, which returns the newest estimate across every benchmark on that case set. It then keeps the result only if `benchmark_id` matches (line 285). The design stores one estimate per benchmark (`estimate_id(benchmark_id)`, slice design line 178). If benchmark B on the same case set is graded after benchmark A, A's report silently omits its own sample-count section. The test `test_an_estimate_of_another_benchmark_is_not_shown` (tests/cli/test_benchmark_report.py) only covers one stored estimate, so it cannot catch this. The fix is a lookup by benchmark id in `GradeRecordStore`, which currently has no such method.

### [CONCERN] Duplicate (case, config, sample) records are silently overwritten
category: correctness
location: src/squadron/benchmark/grade_matrix.py:190

`build_matrix` stores cells in `by_case_row[case][row][replay.sample] = ...`. If two replays share a case, identity, and sample index, the second silently replaces the first. That can happen when two aliases share an identity and both sample index 0. `_exclusion` then counts the surviving k cells and includes the case, so one config's records vanish without an error. The test `test_two_aliases_with_one_identity_give_one_row` (tests/benchmark/test_bench_report_inclusion.py) avoids the collision by giving the two aliases sample indices 0 and 1. That hides the problem. The collision should raise, or the two aliases should be merged explicitly.

### [CONCERN] A failed review's spend is charged to the budget but missing from the grade record
category: correctness
location: src/squadron/benchmark/grade_prepare.py:102-114

In `review_once`, a `ReviewFailed` charges `exc.cost_usd` to the budget (line 105), but `run.review_costs.append` runs only on success (line 114). `GradeRun.grading_cost_usd()` sums only `review_costs`, so an absent record's `grading_cost_usd` leaves out a failed review's cost. The run summary's `spent` includes it, and the stored records do not, so `grading_cost_total` in the report under-counts. The failed cost should be recorded alongside the successful ones.

### [CONCERN] Producer-controlled non-UTF-8 bytes crash the whole grade run instead of recording an absence
category: error-handling-observability
location: src/squadron/benchmark/python_grading.py:75

`_producer_pyproject` calls `path.read_text(encoding="utf-8")` outside any handler. `_parse` only catches `TOMLDecodeError`, and `restore_config` only catches `ProducerConfigError`. A producer's `pyproject.toml` with invalid UTF-8 therefore raises `UnicodeDecodeError` out of `grade_one`, and `run_grading` only catches `GradeCapReached`. The whole `sq benchmark grade` invocation aborts with a traceback. The same pattern is in `python_injection.py:241` (`_same_name_tests`) and `:263` (`_same_name_fixtures`): `read_text` sits inside a `try` that catches only `SyntaxError`. Decoding failures on producer files should become `ProducerConfigError`, which is recorded as a `producer_env_unresolvable` absence, and no test covers this path.

### [CONCERN] Test helpers suppress missing-annotation errors with `type: ignore` (36 occurrences in 21 files)
category: type-contract-debt
location: tests/benchmark/report_support.py#grade_result

Examples: `def grade_result(passed: bool = True, **kwargs: Any):  # type: ignore[no-untyped-def]`, plus `graded(world, diff)` in `test_grade_one_hidden.py`, `SandboxFactory.__call__` in `grade_support.py`, and `fix_data(world)` in `test_bench_report_grades.py`. The project rules require type-hinting every signature and running pyright strict over tests. These suppressions hide the untyped signatures instead of fixing them. I could not run pyright, so I have not confirmed the resulting error count.

### [NOTE] `read_review_floor_runs` is dead in production
category: architectural-decay
location: src/squadron/benchmark/grading_config.py#read_review_floor_runs

The production path reads the floor-runs key through `_config_value(check_review_floor_runs, ...)` in `benchmark_grade.py`. `read_review_floor_runs` has no caller in `src/`; only tests use it. That leaves two readers for one key. Remove it, or make the production path call it.

### [NOTE] Identity-text formatting is duplicated
category: consistency-rot
location: src/squadron/benchmark/report_rows.py#identity_label

`identity_label` repeats the `profile or "no profile"` and `effort …` formatting from `config_text` (`report_rows.py:33-36`). The two can drift apart. Share one formatter.

### [NOTE] Estimate labels fall back to raw identity JSON
category: other
location: src/squadron/benchmark/bench_report_render.py:125

`labels.get(pair.config_a, pair.config_a)` shows the raw canonical identity JSON when no row has that identity. This is a silent fallback, which the project rules prohibit. The row set is built from the same included cases, so the fallback should rarely fire, but when it does the output is unlabeled rather than an error.

### [NOTE] The grade planner imports a constant from the executor module
category: architectural-decay
location: src/squadron/benchmark/grade_plan.py:17

`grade_plan` imports `GRADER_VERSION` from `grade_one`, which pulls in sandbox, git, and review code. Move the version constant to a small config or identity module.

### [NOTE] A reinstall's resolved environment identity is discarded
category: other
location: src/squadron/benchmark/grade_prepare.py:154

`reinstall_if_dependencies_changed` ignores the identity that `BenchmarkSandbox.reinstall()` returns. The records keep only the start environment's digest, the lockfile hash, and a `reinstalled` flag. This matches the design's "identity keeps naming the start environment" (D5), but the environment that actually ran the tests is not recorded. Confirm this is intended.
