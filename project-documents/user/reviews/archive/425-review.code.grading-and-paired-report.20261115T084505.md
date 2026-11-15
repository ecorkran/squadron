---
docType: review
layer: project
reviewType: code
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: f1c4f788efffadd20be4be27613a51ae2bd48a24
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 24
diffTruncated: false
effort: xhigh
turns: 25
promptTokens: 3441402
cachedTokens: 3077474
cacheWriteTokens: 363908
completionTokens: 73919
durationSeconds: 326.7
costUsd: 0.831477
costBasis: provider
runId: run-20261114-p6-27f2e9a4
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Failed reviews are never charged to the run cap"
    location: "src/squadron/benchmark/grade_prepare.py:98-103"
  - id: F002
    severity: concern
    category: consistency-rot
    summary: "Minimum-value constants are defined four times, and one is used for the wrong quantity"
    location: "src/squadron/benchmark/grade_estimate.py:49"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "A git timeout while reading a tree escapes grading with no absence record"
    location: "src/squadron/benchmark/tree_reader.py:68-74"
  - id: F004
    severity: concern
    category: correctness
    summary: "The grading review reads its rules from the producer's own diff"
    location: "src/squadron/benchmark/grade_review.py#_tree_rules"
  - id: F005
    severity: note
    category: correctness
    summary: "Regression and producer-new counts assume the adapter reports every requested id"
    location: "src/squadron/benchmark/grade_checks.py:184-194"
  - id: F006
    severity: note
    category: documentation-drift
    summary: "`assemble_system_prompt` says it is the one place the prompt is built, but a notice is appended outside it"
    location: "src/squadron/review/review_client.py:126-127"
  - id: F007
    severity: note
    category: correctness
    summary: "Restoring a producer-deleted `pyproject.toml` creates a partial file"
    location: "src/squadron/benchmark/python_grading.py:128"
  - id: F008
    severity: note
    category: correctness
    summary: "Restored files are written with LF line endings"
    location: "src/squadron/benchmark/tree_reader.py:47"
  - id: F009
    severity: pass
    category: dependency-config-debt
    summary: "`tomli-w` is a declared dependency"
    location: "pyproject.toml:34"
  - id: F010
    severity: pass
    category: security-hygiene
    summary: "The sandbox environment handoff is not a new exposure"
    location: "src/squadron/benchmark/grade_services.py:89"
  - id: F011
    severity: pass
    category: correctness
    summary: "The grading review does not reload user or config rules"
    location: "src/squadron/review/review_client.py#run_review_with_profile"
---

# Review: code — slice 425

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 24 successful tool call(s) of 24 made; 574617 of 574617 diff characters reached the model

## Findings

### [CONCERN] Failed reviews are never charged to the run cap

`review_once` calls `before_review()` (line 98), then the reviewer. If the reviewer raises `ReviewFailed`, the `except` at lines 101-102 raises an absence before `after_review` (line 103) runs. The failed call therefore adds nothing to the budget. The absent record's `grading_cost_usd` is built from `review_costs`, which only gets entries on success (line 110). `review_tree_diff` in `grade_review.py` raises before it returns `cost_usd`, so a review that timed out or returned UNKNOWN, but still billed, counts as $0. `render_bound` presents the result as "at most $X", and retries after harness absences can push real spend past `--max-cost` without any signal. D9 already says an unpriced review counts at the per-review figure. Failures should follow the same rule. No test in `test_grade_one_prep.py` covers a charge on a failed review.

### [CONCERN] Minimum-value constants are defined four times, and one is used for the wrong quantity

The floor-run minimum is defined twice: `REVIEW_FLOOR_RUNS_MINIMUM = 2` in `config/keys.py:37` and `MIN_FLOOR_RUNS = 2` in `grade_review.py:96`. The samples-per-case minimum is also defined twice: `MIN_SAMPLES = 2` in `grade_estimate.py:21` and `MIN_SAMPLES_FOR_VARIANCE = 2` in `paired_stats.py:26`. Line 49 of `grade_estimate.py` reuses `MIN_SAMPLES` to gate the number of configs ("needs two configs"), which is a different quantity. The project rule is that changing a value should require editing exactly one place. Define each minimum once and give the config-count gate its own name.

### [CONCERN] A git timeout while reading a tree escapes grading with no absence record

`GitTreeReader._git` calls `self._runner.run(...)` with no handling. `SubprocessRunner.run` raises `ProcessTimedOutError` and `ProcessNotFoundError` (`core/process_runner.py:144-160`). `grade_one` catches only `GradeAbsent` and `TreeReadError` around `_grade_steps` (`grade_one.py:150-152`). The CLI's `_REFUSED_ERRORS` does not list the process errors either. A timeout while reading the start or reference tree, from `restore_tool_config`, `inject_hidden`, or `test_side_edits`, therefore propagates out of `run_grading` with no record and a traceback. The sibling `run_git` in `grade_run.py` converts the same errors to `GitFailure`, which becomes an absence, so the two readers disagree. Map the process errors to `TreeReadError` in `_git`, and add a test using a runner double that raises `ProcessTimedOutError`.

### [CONCERN] The grading review reads its rules from the producer's own diff

`review_once` runs the review after `apply_subject` has committed the producer's diff (`grade_prepare.py:100`). `_tree_rules` then reads `project_rules_dir(tree)` from that same tree. A diff that adds or edits `rules/` or `.claude/rules/` changes the "Additional Review Rules" section of its own grading review, and the recorded `rules_hash` moves with it. The slice design (D7) limits rules to the tree's own directory to avoid leaking a machine's rules, but it does not cover the producer editing them. The start commit is already readable through the `start` tree reader, so the rules could be pinned there the same way config is restored. This needs a decision: either pin the rules to `start_sha`, or record in the design that a diff editing rules is out of scope. Either way, add a test with a diff that edits rules.

### [NOTE] Regression and producer-new counts assume the adapter reports every requested id

`run_hidden` maps an unreported injected id to `NOT_RUN` (line 154), so every hidden id has exactly one result. `run_regression` (line 193) and `run_producer_new` (line 69) count only the results the suite returned. A requested id missing from the results is therefore not a failure. The production adapter fills every requested id (`python_suite.py:104-122`: the folded result, a collection error, `NOT_RUN` on timeout, or `ERROR` with `NOT_COLLECTED`), so nothing is silently passing today. The guarantee lives in one adapter that the grade layer does not check, unlike the hidden step. Mirror the hidden step's `reported.get(i, NOT_RUN)` in both places, and add a test that omits an id from a suite double.

### [NOTE] `assemble_system_prompt` says it is the one place the prompt is built, but a notice is appended outside it

The docstring says "The one place a review's system prompt is built, for every non-judge and judge alike." The diff appends `NO_TOOLS_NOTICE` in `run_review_with_profile`, after the call (`review_client.py:212-214`), so the prompt is now assembled in two places. No other caller of `assemble_system_prompt` exists in `src`, so nothing is broken today. Either move the no-tools append into `assemble_system_prompt` behind a `no_tools` parameter, or correct the docstring.

### [NOTE] Restoring a producer-deleted `pyproject.toml` creates a partial file

When the producer deletes `pyproject.toml`, `_producer_pyproject` returns `{}` (`python_grading.py:108`). If the start commit has tool tables, `_restore_pyproject_tables` writes `tomli_w.dumps(producer)` to `pyproject.toml` (line 128). That creates a file holding only the restored `[tool.*]` tables. The deletion is never reported as a config edit. The only later sign is `deps_changed` returning true and a reinstall failing. No test covers this case. A missing producer file should be handled explicitly, as a config absence or a counted edit.

### [NOTE] Restored files are written with LF line endings

`ProcessRunner` decodes with `text=True` (`core/process_runner.py:138`), which applies universal newlines. `GitTreeReader.read` therefore returns the commit's content with CRLF converted to LF, and `restore_test_files` and `_restore_files` write those bytes back. A restored CRLF file is not byte-identical to the start commit. The docstring states this, and comparisons are done on normalized content, so grades are probably unaffected. Still, "restore" does not restore bytes. Either read raw bytes from git, or state the limitation in the restore functions' docstrings.

### [PASS] `tomli-w` is a declared dependency

`python_grading.py` imports `tomli_w`, and `pyproject.toml` declares `tomli-w>=1.0` at line 34, so no new dependency is introduced.

### [PASS] The sandbox environment handoff is not a new exposure

`harness_env=dict(os.environ)` is the same pattern already used in `production_deps.py` and `benchmark_sandbox.py`. The scrubbed environment passes through only the named allowlist (`HARNESS_TOOL_ALLOWLIST`, `scrubbed_env.py:18`), so the new code adds no broader credential scope.

### [PASS] The grading review does not reload user or config rules

`rules_content` is only passed through in `run_review_with_profile` and never resolved from home or config. When the caller supplies `None`, no rules are loaded from anywhere else, so the isolation claimed in `test_user_and_config_rules_never_reach_the_review` holds for this path.

### Run Digest

- Response length: 11148 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 3441402 / 3077474 / 363908 / 73919 / not computed
- Duration: 326.7 s
- Cost: $0.83 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
