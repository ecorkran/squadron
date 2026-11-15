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
reviewedSha: 9ceb6701f199a817fb0b06647f461b4fed17db14
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
diffTruncated: false
effort: xhigh
turns: 25
promptTokens: 3577670
cachedTokens: 3167670
cacheWriteTokens: 409982
completionTokens: 80463
durationSeconds: 348.0
costUsd: 0.92415
costBasis: provider
runId: run-20261115-p6-26b3510a
squadronVersion: 0.24.31
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Slice-case reuse ignores the qualification repeat count"
    location: "src/squadron/benchmark/slice_qualify.py:58"
  - id: F002
    severity: concern
    category: correctness
    summary: "Read-side mapping sends canonical categories to `other`"
    location: "src/squadron/metrology/review_category_map.py:46"
  - id: F003
    severity: concern
    category: correctness
    summary: "Overlapping PATHS are ingested twice"
    location: "src/squadron/metrology/review_ingest.py:95"
  - id: F004
    severity: concern
    category: error-handling-observability
    summary: "A held-lock handler does not meet the exception rule"
    location: "src/squadron/benchmark/diff_judge_runner.py:100"
  - id: F005
    severity: note
    category: architectural-decay
    summary: "Duplicated slice and fix table renderers"
    location: "src/squadron/benchmark/report_slice_table.py#render_slice_table"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "Configuration comment describes a different read path"
    location: "src/squadron/config/keys.py:40"
  - id: F007
    severity: note
    category: correctness
    summary: "Plan message says \"nothing to judge\" while forfeits are still written"
    location: "src/squadron/benchmark/diff_judge_plan.py:222"
  - id: F008
    severity: note
    category: consistency-rot
    summary: "Label fallback differs within one module"
    location: "src/squadron/benchmark/pairwise_report.py#build_pairwise"
  - id: F009
    severity: note
    category: test-debt
    summary: "Runner tests use a double that re-implements production logic"
    location: "tests/benchmark/slice_runner_support.py#SandboxDouble.producer_env"
  - id: F010
    severity: note
    category: test-debt
    summary: "One test has a non-behavioral assertion and a single-item loop"
    location: "tests/benchmark/test_mixed_kinds.py#test_a_mixed_case_set_runs_judges_and_reports_each_kind_apart"
  - id: F011
    severity: pass
    category: error-handling-observability
    summary: "Judge spend accounting covers provider failures"
    location: "src/squadron/replay/judge_dispatch.py#one_shot_judge_dispatcher"
  - id: F012
    severity: pass
    category: correctness
    summary: "Requalification handles rejected slice records"
    location: "src/squadron/benchmark/replay_one.py:123"
---

# Review: code — slice 426

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 24 successful tool call(s) of 24 made; 692085 of 692085 diff characters reached the model

## Findings

### [CONCERN] Slice-case reuse ignores the qualification repeat count

`can_skip` checks the rule version, the harness-error outcome and the environment digest. It never compares the stored `repeats` with the configured `benchmark.qualification_repeats`. `slice_qualification_for` (line 75) and the `_lookup` path inherit the gap. After the repeat count changes, `sq benchmark slice-cases build` reuses results made under the old count, so flaky and always-failing exclusions are never recomputed. The fix path does compare: `reusable_record` in `src/squadron/benchmark/qualify_types.py:161-164` checks `record.repeats != repeats`. Add the same check to `can_skip` and thread `repeats` through its callers.

### [CONCERN] Read-side mapping sends canonical categories to `other`

`map_historical_category` looks the key up only in `HISTORICAL_CATEGORIES`, which holds the D7 historical strings. Canonical `ReviewCategory` values are not in that table, except `correctness`. A historical review that already says `architectural-decay`, `test-debt`, `security-hygiene` or `error-handling-observability` therefore becomes `other` with its raw string kept. That inflates the `other` share, which the audit treats as a signal. The same function also keeps `raw` for a canonical `other`, unlike `normalize_category`. Check the lenient key against `ReviewCategory` values first and return `(member, None)` on a match. The parametrized tests only cover historical strings, so this gap is untested.

### [CONCERN] Overlapping PATHS are ingested twice

`resolve_review_files` extends `files` for each root with no dedupe. `sq metrology ingest-reviews reviews reviews/a.md` lists `a.md` twice, and `ingest_reviews` writes it twice. The store keeps one record, but the summary prints `Ingested 2 ... (1 replaced)`. Dedupe by resolved path inside `resolve_review_files`, and add a CLI test with overlapping inputs.

### [CONCERN] A held-lock handler does not meet the exception rule

`run_judging` catches `BenchmarkRefusal` when the judge lock is held, logs at WARNING, and re-raises as `JudgeRefusal`. The project rule requires an ERROR log via `logger.exception` before a re-raise, or an inline comment justifying the handling. The test `test_a_held_lock_refuses_naming_the_lock_file_and_logs_a_warning` asserts WARNING, so the level looks deliberate. Either log at ERROR with the exception, or keep WARNING and add the justifying comment.

### [NOTE] Duplicated slice and fix table renderers

`render_slice_table` repeats the objective, reference, paired and checks loops from `render_fix_table` in `report_fix_table.py`. `_reference` repeats the case loop in `reference_line`. The literals `"paired (95% bootstrap over cases)"` and `REFERENCE_LABEL` are defined in both modules (`report_slice_table.py:35-36`, `report_fix_table.py:182,205`). Extract the shared sections, or at least the shared constants.

### [NOTE] Configuration comment describes a different read path

The comment says the prompt limit is "read through get_positive_int_config". `benchmark_judge._plan` reads it through `read_config` and `check_positive_int`. Both give the same result for values stored by `set_config`, which coerces to the declared type, so this is drift and not a bug. Correct the comment or the call.

### [NOTE] Plan message says "nothing to judge" while forfeits are still written

`render_bound` returns "nothing to judge" when `plan.calls == 0`. `run_judging` still writes the forfeit records for pending pairs with no calls. The message is accurate about calls but reads as if nothing will happen. Say "no calls; N forfeits to record".

### [NOTE] Label fallback differs within one module

`build_pairwise` builds labels with `matrix.labels.get(key, key.model)`, a silent fallback. `_pairs` in the same module reads `matrix.labels[a]`, which fails loudly. Pick one behavior. Failing loudly fits the project rule against silent fallbacks.

### [NOTE] Runner tests use a double that re-implements production logic

`SandboxDouble.producer_env` rebuilds the `ScrubbedEnvironment` and tool-linking steps instead of calling `BenchmarkSandbox.producer_env`. Runner tests can therefore pass while the real sandbox changes. The network end-to-end test is the only test that exercises the real path. Either delegate to the real method or name the double's gap in the test module.

### [NOTE] One test has a non-behavioral assertion and a single-item loop

The assertion `assert len(world.grades) == 4 and fix_ids and slice_ids` checks setup, not behavior. The loop `for config in (CONFIG,)` iterates once. The test also imports a helper from another test module. Replace the assertion with one on the grades that matter, and move the shared helper into a support module.

### [PASS] Judge spend accounting covers provider failures

The dispatcher wraps every `Exception` from the provider as `JudgeCallError`. `metered` in `diff_judge_budget.py` charges that and `CancelledError` at the per-call figure before re-raising, so no failed call is counted as free.

### [PASS] Requalification handles rejected slice records

`replay_one` checks `CandidateRejection` first, then reads `verdict.outcome`, so a rejected `SliceQualification` becomes a `CaseDrop` with its rejection reason. The pairwise fit also matches its docstring: INCONSISTENT counts as a tie and INVALID is excluded (`src/squadron/replay/bradley_terry.py#_game`).

### Run Digest

- Response length: 9768 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 3577670 / 3167670 / 409982 / 80463 / not computed
- Duration: 348.0 s
- Cost: $0.92 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 12
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 12
- Finding-shaped matches — surviving validation: 12
