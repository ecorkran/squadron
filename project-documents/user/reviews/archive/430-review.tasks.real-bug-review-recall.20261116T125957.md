---
docType: review
layer: project
reviewType: tasks
slice: real-bug-review-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/430-tasks.real-bug-review-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261116
dateUpdated: 20261116
reviewedSha: ce11459f7696a9124ee63e0526da55a30f385b2d
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 793723
cachedTokens: 670946
cacheWriteTokens: 122759
completionTokens: 72209
durationSeconds: 320.2
costUsd: 0.191365
costBasis: provider
runId: run-20261116-p5-c59b9eb6
squadronVersion: 0.24.31
findings:
  - id: F001
    severity: pass
    category: verification
    summary: "Cited symbols and amendments match the code"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:39"
  - id: F002
    severity: pass
    category: coverage
    summary: "Coverage and sequencing of the main criteria"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md"
  - id: F003
    severity: concern
    category: spec-conflict
    summary: "Task 22 says \"sum\" where the criterion is a union"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:199"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Task 18's fallback edits a case file after import, which changes its record ids"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:177"
  - id: F005
    severity: concern
    category: sequencing
    summary: "Task 25 uses a \"run loop helper\" that no earlier task creates"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:222"
  - id: F006
    severity: concern
    category: granularity
    summary: "Task 27 is too large for one task"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:232"
  - id: F007
    severity: concern
    category: test-coverage
    summary: "Some D8 modes have no named test"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:216"
  - id: F008
    severity: concern
    category: traceability
    summary: "The Context Summary points the `cases add` and import D8 tests at the wrong tasks"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:49"
  - id: F009
    severity: concern
    category: test-coverage
    summary: "No test for \"two live aliases with the same settings are one row\""
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:508"
  - id: F010
    severity: concern
    category: criterion-coverage
    summary: "The D11 bound criterion is checked only on a fake set"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:519"
  - id: F011
    severity: concern
    category: spec-gap
    summary: "Task 16 leaves the overrides schema, labeler name and grade precedence unspecified"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:164"
  - id: F012
    severity: concern
    category: conventions
    summary: "Task 23 puts the template in the wrong directory, and task paths name no root"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:205"
  - id: F013
    severity: note
    category: granularity
    summary: "Task 2 is too granular and could fold into its first consumer"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:66"
  - id: F014
    severity: note
    category: granularity
    summary: "Task 29 is a check-only task that repeats checks in Tasks 9 and 24"
    location: "project-documents/user/tasks/430-tasks.real-bug-review-recall.md:247"
  - id: F015
    severity: note
    category: ambiguity
    summary: "Two `write_record` functions exist; Task 6 should name the store method"
    location: "src/squadron/metrology/store.py:436"
  - id: F016
    severity: note
    category: design-correction
    summary: "Task 1 leaves the D13 fallback sentence in the design"
    location: "project-documents/user/slices/430-slice.real-bug-review-recall.md:406"
---

# Review: tasks — slice 430

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [PASS] Cited symbols and amendments match the code

I checked the symbols in the Context Summary: `BenchmarkLock.acquire` (`benchmark/bench_lock.py:62`), `check_review_timeout` (`grading_config.py:27`), `pair_seed` and `compare_pair` (`paired_stats.py:62, 88`), `MIN_PAIRED_CASES = 5` (`paired_stats.py:23`), `EXIT_CAP_REACHED` (`benchmark_grade.py:49`), `ReviewBudget` and `GradeCapReached` (`grade_budget.py`), `render_bound` (`grade_plan.py:240`), `run_auth_check`, `resolve_sq_path`, `build_leak_rules`, `leak_scan.scan`, `transcript_source_for`, `ConfigKey.type_`, `TemplateOutput.DECISIONS`, `run_review_with_profile`, and `HistoryFreeSandbox(start_sha=)`. The `--diff`, `--output-path` and `--no-save` flags exist. The D7 architecture amendment (`420-arch.model-benchmark.md:36`) and the D11 plan amendment (`420-slices.model-benchmark.md:165`) are already present, so Task 1's removal of "PM to confirm" text is consistent.

### [PASS] Coverage and sequencing of the main criteria

Most functional criteria trace to a task: case files and sets (Task 11), import counts and idempotence (Tasks 14–17), the section 1 reproduction (Task 22), pool and fan-out (Task 22), the hit gate (Task 18), bound, caps, resume and retry (Tasks 26–27), leak verdicts (Tasks 24, 27), the stub-kind run (Task 27), and `report --json` (Task 22). Dependencies run forward with no cycles. There are 16 commit markers, each at a tested point, and each implementation task has tests except Tasks 29 and 31. The design restates no NFR, so no load test is required.

### [CONCERN] Task 22 says "sum" where the criterion is a union

Task 22 says to "sum their run-1 bug-hits" across the four recipes. D2 (`430-slice…md:189`) defines fan-out as a union: a known bug counts once if any reviewer's kept finding hits it. RESULTS.md section 5 reports `N/14` "aggregated over all four reviewers" (`RESULTS.md:112–126`), so the denominator is distinct bugs, and a sum can exceed 14. Change "sum" to "union". The "14 uncombed" baseline is not in section 5's table, so the test should compute it from the records rather than assert it.

### [CONCERN] Task 18's fallback edits a case file after import, which changes its record ids

D1 makes `case_id` a hash of the resolved locations (`430-slice…md:145`), so adding an `extra_locations` entry gives a new case id. D4 derives run record ids from `(case_id, run_index)` (`430-slice…md:241`). Tasks 14–17 write run records under the old id. Task 18's "add an `extra_locations` entry" fallback would orphan those records and change set membership, and no step re-imports. Either run the gate check before the import commit, or state the consequence: a new case version, `cases add` again, and a re-import into a new set version.

### [CONCERN] Task 25 uses a "run loop helper" that no earlier task creates

Task 25 puts the sandbox-per-case lifecycle "in the run loop helper". The run loop is built in Task 27, which comes after Task 25, and no module or function is named for the helper. Name where it lives, or move the lifecycle into Task 27.

### [CONCERN] Task 27 is too large for one task

Task 27 covers the serial loop, the bound, both caps, `--case`, resume, orphan ingest with leak scan, `--retry-harness`, the lock, and `write_record` failure. Its test file lists about nine scenarios, and it adds an end-to-end test. Split it into: (a) bound, caps, `--case`, resume and wiring; (b) orphan ingest, retry, lock and `write_record` failure; (c) the end-to-end test. Task 22's reproduction suites could also be their own task.

### [CONCERN] Some D8 modes have no named test

Technical Requirements (`430-slice…md:524`) require a test asserting outcome and log for every D8 row. These are not named in any task:
- Leak verdict `scan_unavailable`. Task 24 tests `leaked` and `confined` only (design row at `:310`).
- The orphan path that repeats the call with a WARNING. Task 27 tests ingest only (design row at `:311`).
- The auth preflight refusal's ERROR log. Task 26 lists "auth failure" without a log assertion (design row at `:304`).
- A `HistoryFreeSandbox` build failure. Tasks 9 and 25 do not name it (design row at `:309`).
- A failing `git show` without a timeout, with its ERROR log. Task 8 tests only the timeout (design row at `:319`).
Add each to the named task's test list.

### [CONCERN] The Context Summary points the `cases add` and import D8 tests at the wrong tasks

It says the `cases add` and import rows are tested in "Tasks 9, 19, 20". Task 9 is the sandbox and Tasks 19 and 20 are scoring. `cases add` is Task 10 (with Task 8), and import is Tasks 14–17.

### [CONCERN] No test for "two live aliases with the same settings are one row"

This is a Functional Requirements criterion. Task 19 tests that live and imported rows stay separate, and Task 22 tests display. No task asserts that two live aliases with the same `config_key` and `effort_sent` collapse into one row. Add it to Task 19's tests.

### [CONCERN] The D11 bound criterion is checked only on a fake set

The criterion says `run` with `haiku-sol-luna-opus` on `real-bugs-nonsquadron` prints its bound. Task 27 checks the bound on a fake 14-case set, and Task 31 says step 7 is not run. Nothing shows the bound on the real set. Either amend the criterion to match D11 (step 7 prints it), or add a Task 31 check on the real set. Note that the first call always runs (the overshoot term), so that check spends one call.

### [CONCERN] Task 16 leaves the overrides schema, labeler name and grade precedence unspecified

Task 16 creates `review-recall-overrides.yaml` and writes the adjudications "as person labels", with no schema, no labeler name, and no rule for whether a person grade beats an imported grade. D3 sets person-over-import precedence for hits only. Grades drive real share and the person-checked count (D5), so the junior would have to guess. Specify all three.

### [CONCERN] Task 23 puts the template in the wrong directory, and task paths name no root

Task 23 says `data/templates/comb.yaml`. The existing templates live under `src/squadron/data/templates/`. Most task paths (`metrology/…`, `config/keys.py`, `benchmark/…`, `cli/commands/…`) also omit `src/squadron/`, and only Task 9 writes it out. Name the root once and write `src/squadron/data/templates/comb.yaml`.

### [NOTE] Task 2 is too granular and could fold into its first consumer

It is one config key with one test. Fold it into Task 8, where `derive_locations` first uses it. Its default of 120 repeats the value of the sandbox's `SANDBOX_COMMAND_TIMEOUT_SECONDS` (used at `history_free_sandbox.py:51`). State that the two are separate knobs, as the design intends.

### [NOTE] Task 29 is a check-only task that repeats checks in Tasks 9 and 24

Tasks 9 and 24 already check their own diffs. Task 29 adds `grade_models.py` and the `sq review code` module. Fold it into Task 31 so all gates sit in one place.

### [NOTE] Two `write_record` functions exist; Task 6 should name the store method

`MetrologyStore.write_record(record_id, record)` is the method meant. `benchmark/replay_records.py:89` has a different `write_record(deps, …)`. Task 6 says "rewrite via `write_record`" (line 93), and Task 27's failure handling depends on which one is meant.

### [NOTE] Task 1 leaves the D13 fallback sentence in the design

The PM decided D13, so the "If not, …" fallback is now dead text. Remove it in the same edit as the "PM to confirm" sentence. Task 1's grep check would not catch it.

### Run Digest

- Response length: 11098 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 793723 / 670946 / 122759 / 72209 / not computed
- Duration: 320.2 s
- Cost: $0.19 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 16
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 16
- Finding-shaped matches — surviving validation: 16
