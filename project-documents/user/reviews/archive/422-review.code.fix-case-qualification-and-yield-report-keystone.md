---
docType: review
layer: project
reviewType: code
slice: fix-case-qualification-and-yield-report-keystone
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261111
dateUpdated: 20261111
reviewedSha: 70f45a3ed80e091ccf0300d9bf1103c0c26f960c
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
diffTruncated: false
effort: xhigh
turns: 22
promptTokens: 2305586
cachedTokens: 2012909
cacheWriteTokens: 292661
completionTokens: 49603
durationSeconds: 223.5
costUsd: 0.63157
costBasis: provider
runId: run-20261111-p6-62b55a9e
squadronVersion: 0.24.26
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: correctness
    summary: "Stored qualification is reused even when the repeat count changed"
    location: "src/squadron/benchmark/qualify_types.py:146"
  - id: F002
    severity: concern
    category: correctness
    summary: "Config is validated after the build has written its results"
    location: "src/squadron/cli/commands/benchmark_fix_cases.py:148"
  - id: F003
    severity: concern
    category: correctness
    summary: "A root commit is recorded as a harness error"
    location: "src/squadron/benchmark/qualify_stages.py:117"
  - id: F004
    severity: concern
    category: architectural-decay
    summary: "Harness-error helpers duplicated across modules"
    location: "src/squadron/benchmark/python_boundary.py:31"
  - id: F005
    severity: concern
    category: error-handling-observability
    summary: "Unparseable `pyproject.toml` falls back to default test-side rules"
    location: "src/squadron/benchmark/python_fairness.py:73"
  - id: F006
    severity: concern
    category: test-debt
    summary: "No load test for the new network and environment paths"
    location: "src/squadron/codehost/github_cli.py#GitHubCli.get_issue"
  - id: F007
    severity: note
    category: other
    summary: "Squadron-specific exemption inside the generic verdict module"
    location: "src/squadron/benchmark/trace_verdict.py:26"
  - id: F008
    severity: note
    category: error-handling-observability
    summary: "Re-raise in the patch interceptor does not log"
    location: "src/squadron/benchmark/pytest_trace/squadron_fixcase_patches.py:92"
  - id: F009
    severity: note
    category: correctness
    summary: "Null comment authors render as an empty name"
    location: "src/squadron/codehost/github_parse.py#to_issue_comment"
  - id: F010
    severity: note
    category: consistency-rot
    summary: "Asymmetric handling of `not_run` and `skipped` between hidden and regression tests"
    location: "src/squadron/benchmark/qualify_survivors.py#_excluded_rejection"
---

# Review: code — slice 422

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5
**Evidence:** 21 successful tool call(s) of 21 made; 493875 of 493875 diff characters reached the model

## Findings

### [CONCERN] Stored qualification is reused even when the repeat count changed

`reusable_record` accepts a stored record when the project, commit, environment digest and `FAIRNESS_RULE_VERSION` match, and when the outcome is not `harness_error`. It never compares `record.repeats` with `deps.repeats`, although `_new_record` stores that value (line 137). The flakiness verdicts and the excluded-test list come from those repeats. Raising `benchmark.qualification_repeats` therefore leaves old verdicts in place, and a hidden test judged flaky with fewer repeats can stay in a case. Neither `test_qualify_sandbox.py` nor the end-to-end reuse test covers this. Either add the comparison or document in the predicate's docstring that repeats are deliberately excluded.

### [CONCERN] Config is validated after the build has written its results

`build_command` reads the build settings and validates them at the top. It reads the report inputs only after `build_fix_cases` has run (line 140), and `_report_inputs` (line 95) can raise `stderr_exit`. An invalid `benchmark.target_pass_rate_difference`, such as 1.5, therefore exits 1 after the case set and every qualification record are already stored. The command reports a config error after side effects. Validate `_report_inputs` with the other settings before the build starts.

### [CONCERN] A root commit is recorded as a harness error

`FixCandidate.parent_sha` is empty for a root commit (`fix_discovery.py:60`). `_classify` then calls `_read_at(deps, "", "pyproject.toml")`, and the git argv fails. `run_pre_sandbox_stages` records that as `harness_error`. The commit's status is a property of the commit, not of the harness, so the outcome is wrong. `reusable_record` never reuses a `harness_error`, so every build re-runs the commit and the yield report counts it as a harness failure. I did not run git with an empty tree-ish, so this follows from the argv. Record a candidate rejection for root commits instead.

### [CONCERN] Harness-error helpers duplicated across modules

The same policy appears in several places. `_harness_failure` in `python_boundary.py:31` and in `python_fairness.py:59` has identical bodies: log at ERROR, then return `HarnessFailure`. `_failure` in `python_tree_files.py:30` does the same. `_halt` appears in `case_build.py:65` and `fix_discovery.py:102`. The `ProcessTimedOutError`/`ProcessNotFoundError` to `HarnessFailure` translation is repeated at about five call sites. `_read_at` exists twice with different semantics (`qualify_stages.py:76` returns `None` when the path is absent, `file_states.py:36` raises). Consolidate the policy into one module, and give the two `_read_at` functions distinct names.

### [CONCERN] Unparseable `pyproject.toml` falls back to default test-side rules

`_configured_testpaths` logs a WARNING and returns `None`, so `is_test_side` (line 99) uses the default patterns. CLAUDE.md prohibits silent fallbacks on bad input. The fallback runs in stage 2 (`classify_diff`), before any sandbox reports the parse error, so a candidate can be rejected (for example `NO_TEST_CHANGE` or `TEST_DATA_CHANGED`) on a classification built from guessed rules. The warning also fires once per changed path, because `is_test_side` re-parses the file on every call. Raise a harness failure for an unparseable parent config, and parse once per candidate.

### [CONCERN] No load test for the new network and environment paths

`python.md` requires at least one load test for code on network or environment-layer paths. `get_issue` makes up to `MAX_DISCUSSION_PAGES` sequential GraphQL calls per issue, and each qualified candidate builds a sandbox. The existing `tests/load/test_benchmark_sandbox_concurrency.py` predates this slice and does not exercise issue paging or qualification. A glob of `tests/load/**/*.py` finds no test for either. Add a load test with a realistic comment count, asserting latency or call-count bounds.

### [NOTE] Squadron-specific exemption inside the generic verdict module

`ENVIRONMENT_ISOLATION_PATCH_TARGETS` names squadron's own `squadron.cli.app._load_env_file`. The exemption is documented and fails safe: if the target is renamed, the test is rejected rather than admitted. It still puts one repository's conftest into an adapter meant for any project. Consider moving it to per-project configuration.

### [NOTE] Re-raise in the patch interceptor does not log

The `except (ImportError, AttributeError)` handler records an `unresolved` patch and re-raises without logging. CLAUDE.md requires a re-raise to be preceded by `logger.exception`. The failure is still observable, because the unresolved patch is recorded and pytest reports the failing test, so this is a rule deviation rather than a silent failure.

### [NOTE] Null comment authors render as an empty name

`_nested_str` (line 80) returns `""` for a null author, and the comment heading becomes `## Comment by  on …` with a double space. A deleted account's comment should carry an explicit placeholder login.

### [NOTE] Asymmetric handling of `not_run` and `skipped` between hidden and regression tests

`_hidden_rejection` treats any outcome other than `passed` as a failure at the reference. `_excluded_rejection` excludes only `failed` and `error`, so an unchanged test that was `not_run` or `skipped` in every reference run stays in the regression set. Reference collection failures are caught earlier, so the practical impact is small. Pick one rule and state it in both docstrings.

### Run Digest

- Response length: 9004 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 22
- Tokens — prompt / cached / cache write / completion / reasoning: 2305586 / 2012909 / 292661 / 49603 / not computed
- Duration: 223.5 s
- Cost: $0.63 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
