---
docType: review
layer: project
reviewType: code
slice: grading-and-paired-report
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/slices/425-slice.grading-and-paired-report.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261115
dateUpdated: 20261115
reviewedSha: 4a325e7da266e006b1c02cbf51d03cf1597396ce
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 14
diffTruncated: false
effort: xhigh
turns: 15
promptTokens: 2029843
cachedTokens: 1680641
cacheWriteTokens: 349190
completionTokens: 84174
durationSeconds: 362.1
costUsd: 0.775327
costBasis: provider
runId: run-20261114-p6-27f2e9a4
squadronVersion: 0.24.28
categoriesNormalized: true
findings:
  - id: F001
    severity: fail
    category: test-debt
    summary: "Test module imports a function that no longer exists, so pytest collection fails"
    location: "tests/config/test_keys.py:9"
  - id: F002
    severity: fail
    category: correctness
    summary: "Absence detail is not bounded, so a long message crashes the run instead of recording an absence"
    location: "src/squadron/benchmark/grade_one.py#_absent_record"
  - id: F003
    severity: concern
    category: correctness
    summary: "Precondition for replays is checked after a paid review has already run"
    location: "src/squadron/benchmark/grade_one.py#_grade_steps"
  - id: F004
    severity: concern
    category: type-contract-debt
    summary: "Stringly-typed absence kinds are built and parsed by prefix matching"
    location: "src/squadron/benchmark/grade_matrix.py#_exclusion"
  - id: F005
    severity: concern
    category: correctness
    summary: "Report shows whatever estimate the benchmark last stored, with no grader or freshness check"
    location: "src/squadron/cli/commands/benchmark_grade.py#_report"
  - id: F006
    severity: concern
    category: test-debt
    summary: "No load test for the grading path, which the rules require for environment-layer and concurrency code"
    location: "tests/load"
  - id: F007
    severity: note
    category: documentation-drift
    summary: "Config key comment describes a read path that production does not use"
    location: "src/squadron/config/keys.py#BENCHMARK_REVIEW_FLOOR_RUNS_KEY"
  - id: F008
    severity: note
    category: correctness
    summary: "Tool-config restoration does not cover setup.cfg or tox.ini, which pytest reads"
    location: "src/squadron/benchmark/python_grading.py#TOOL_CONFIG_FILES"
  - id: F009
    severity: note
    category: correctness
    summary: "The no-tools change in the shared review client also affects the CLI's `--no-tools` path"
    location: "src/squadron/review/review_client.py#run_review_with_profile"
  - id: F010
    severity: note
    category: test-debt
    summary: "Test helpers are shared across test modules, and one test locates records by slicing ids"
    location: "tests/benchmark/test_bench_report_inclusion.py#test_a_missing_sample_excludes_the_case_as_incomplete"
  - id: F011
    severity: pass
    category: other
    summary: "Production wiring and cross-module names resolve"
    location: "src/squadron/benchmark/grade_services.py"
---

# Review: code — slice 425

**Verdict:** FAIL
**Model:** claude-haiku-5-5
**Evidence:** 14 successful tool call(s) of 14 made; 587520 of 587520 diff characters reached the model

## Findings

### [FAIL] Test module imports a function that no longer exists, so pytest collection fails

Line 9 imports `read_review_floor_runs` from `squadron.benchmark.grading_config`. A repo-wide search finds no definition in `src/`, and the `grading_config.py` shown in this diff defines only `check_review_floor_runs`, `check_review_timeout`, and `check_target_difference`. Pytest aborts the session on a collection error by default, so the whole suite stops, not only the new `TestBenchmarkGradingKeys` class. An earlier review note (`project-documents/user/reviews/425-review.code.grading-and-paired-report.md`) flagged this function as dead and suggested removing it or wiring it into production. It was removed, but the tests that call it were not updated. Point the tests at `check_review_floor_runs` through the config read, or drop them.

### [FAIL] Absence detail is not bounded, so a long message crashes the run instead of recording an absence

`check_detail` in `grade_models.py` raises when `detail` exceeds `DETAIL_MAX_CHARS` (1000), and `_check_result_or_absence` runs it on both grade record types. `absent()` passes its detail through unchanged, and nothing caps it earlier. Several producers emit unbounded text:
- `python_adapter.py` `_failure` (lines 106, 136, 158) puts the full `result.stderr.strip()` into `EnvironmentResolutionError.detail`. That reaches `grade_one`'s outer `except` through `str(exc)` on sandbox enter, and reaches `grade_prepare.reinstall_if_dependencies_changed` as `f"{exc.reason.value}: {exc.detail}"`.
- `grade_review.review_tree_diff` wraps `f"the review call raised {type(exc).__name__}: {exc}"` into `ReviewFailed`.
- `grade_checks.measure_and_store` wraps `f"{type(exc).__name__}: {exc}"`.

When the detail is over the cap, `_absent_record` raises a pydantic `ValidationError` inside the `except` block of `grade_one`. The error escapes `grade_one`, the run aborts, and no absence record is written. D16 says these failures must be recorded. The environment install failure is the most likely trigger, since uv's stderr can be long. No test uses a long detail; the sandbox tests use short strings. Bound the detail once, in `absent()` or `_absent_record`, and add a test with a stderr over 1000 characters.

### [CONCERN] Precondition for replays is checked after a paid review has already run

`_grade_steps` calls `prepare_tree(run)` first. That step runs the reviewer through `review_once` and charges the budget. Only after that does it call `load_baseline(run)` for replays, which raises `MissingReferenceGrade` when the reference is missing. That exception is not an absence, so it aborts the run after the spend. The check only reads the store, so move `load_baseline` ahead of `prepare_tree`. The test `test_a_replay_with_no_reference_grade_raises_and_logs_error` does not assert that no review ran.

### [CONCERN] Stringly-typed absence kinds are built and parsed by prefix matching

`Cell.harness` is a plain `str`. `_cell` builds `f"replay:{...}"` and `f"grade:{...}"`, and `_exclusion` decides between `HARNESS_REPLAY` and `HARNESS_GRADE` by `harness[0].startswith("replay:")`. `bench_report.py` `_absence_counts` builds the same prefixes again, so the literals are duplicated across two modules. The repo rules say a value used in a comparison is defined once. Use an enum or a single constant, and have `Exclusion` and the absence-kind labels derive from it.

### [CONCERN] Report shows whatever estimate the benchmark last stored, with no grader or freshness check

`_report` passes `services.grade_store.estimate_for(benchmark_id)` straight into `build_report`. `estimate_for` returns the stored estimate without comparing `grader_digest` to the grader the report uses. `write_estimate` writes only when an estimate can be computed and never deletes an earlier one. So after a later run can no longer estimate (for example, a case drops out), the old estimate remains and is printed next to a report built under a different grader. The rendered line shows only k and n, so the mismatch is not visible. Return `None` when `estimate.grader_digest != grader.digest`, or clear the stored estimate on the no-estimate path. Also show `created_at`.

### [CONCERN] No load test for the grading path, which the rules require for environment-layer and concurrency code

The diff adds sandbox creation, environment install and reinstall, git subprocesses, and the grade lock, all of which are environment-layer and concurrency paths. The Python rules say these require at least one load test with latency, throughput, or resource bounds, and that CI gates it. This diff adds nothing under `tests/load/`.

### [NOTE] Config key comment describes a read path that production does not use

The comment says the key is read through `get_positive_int_config`. The production path in `benchmark_grade.py` reads it with `services.read_config` (which uses `get_config`) and then applies `check_review_floor_runs`. `grading_config.py`'s docstring has the same stale description. Correct both comments.

### [NOTE] Tool-config restoration does not cover setup.cfg or tox.ini, which pytest reads

`TOOL_CONFIG_FILES` lists `ruff.toml`, `.ruff.toml`, `pyrightconfig.json`, `mypy.ini`, `pytest.ini`, and `.coveragerc`. It omits `setup.cfg` and `tox.ini`. Pytest reads `[pytest]` from `tox.ini` and `[tool:pytest]` from `setup.cfg` when `pytest.ini` and `pyproject.toml` do not define config. A producer could change test configuration through either file and it would survive restoration. Confirm whether D4 intends to exclude them.

### [NOTE] The no-tools change in the shared review client also affects the CLI's `--no-tools` path

`NO_TOOLS_NOTICE` is now appended, and the preset is dropped, for every caller that passes `no_tools=True`. That includes `sq review --no-tools` (`cli/commands/review.py:791`) and `review_pr --no-tools` (`cli/commands/review_pr.py:428`), not only grading. The new tests cover only the SDK path. The comment attributes the change to the slice 425 walkthrough. Confirm that the change to the existing CLI behavior is intended.

### [NOTE] Test helpers are shared across test modules, and one test locates records by slicing ids

The test finds a replay with `cases[0].case_id[5:17]` string slicing. The `len(lost) == 1` assertion will catch a mismatch, but the test is tied to the id format. Several test support modules also import helpers from other test modules, and `report_support.py` imports private `_environment` from `tests.metrology`. Move shared builders into a support module.

### [PASS] Production wiring and cross-module names resolve

I checked the new code's external imports against their definitions: `OrphanSweep`, `CollectedTests`, `SnapshotConfig`, `AdapterRegistry`, `LEAK_RULES_VERSION`, `CASE_LANGUAGE`, `GIT_QUERY_TIMEOUT_SECONDS`, `BuildHalted`, `MissingCredentialError`, `BenchmarkLock`, `BenchmarkRefusal`, `model_effort`, `normalize_result_categories`, `summarize_counts`, `extract_diff_paths`, `load_review_rules`, `run_git` (which can return `None`, and `grade_review` handles that), `STDERR_TAIL_CHARS`, and `ProcessRunner.run` with `stdin` and `replace_env`. `BenchmarkSandbox` has the `__enter__`/`__exit__`, `keep`, `home`, and `output_dir` the grade seam uses. `collect().digests` is keyed by node id, so `_collect_node_ids` returns node ids. `_z_total` and `audit_variance._stat` have no remaining callers under the old names, and `REPLAY_ID_PREFIX` has one definition. `harness_env=dict(os.environ)` follows an existing pattern in `production_deps.py`, `benchmark_fix_cases.py`, and `benchmark_sandbox.py`, and the grade sandbox uses `CredentialGrant.none()`, so it adds no credential exposure.

### Run Digest

- Response length: 10566 chars
- Response is newline-free: no
- Tool calls made: 14
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 15
- Tokens — prompt / cached / cache write / completion / reasoning: 2029843 / 1680641 / 349190 / 84174 / not computed
- Duration: 362.1 s
- Cost: $0.78 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 11
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 11
- Finding-shaped matches — surviving validation: 11
