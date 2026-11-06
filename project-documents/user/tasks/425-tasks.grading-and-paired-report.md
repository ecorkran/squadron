---
docType: tasks
slice: grading-and-paired-report
project: squadron
lld: user/slices/425-slice.grading-and-paired-report.md
dependencies:
- 300
- 320
- 400
- 420
- 421
- 422
- 424
projectState: Slices 420–424 have tasks written, not implemented (src/squadron/benchmark
  does not exist at the time of writing). Slice 425 design written. main is the target
  unless cf config get git.integration_branch says otherwise.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 17
promptTokens: 1201207
cachedTokens: 1099502
cacheWriteTokens: 101675
completionTokens: 31664
durationSeconds: 221.1
costUsd: 0.833666
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.8336662
    completionTokens: 31664
---

## Context Summary
- Working on slice 425: `sq benchmark grade` and `sq benchmark report`. Design: `user/slices/425-slice.grading-and-paired-report.md`; its D-numbers (D1–D16) are cited below instead of repeating them.
- Delivers: the `GradingAdapter` protocol and `PythonGradingAdapter` (hidden-test injection, tool-config restoration, dependency-change test, test-edit and suppression counts); `grade_one`; the fixed grading review, its noise floor and its spend budget; `ContentSidecars`; `measure_snapshot`; the grade and estimate records; `paired_stats`; the grade runner; the report and its case-kind table registry; both CLI commands, their slash-command mirrors and the measured line in `sq benchmark yield`. Nothing here runs a producer (424) or builds slice cases (426).
- Order: the design correction and the extractions and config keys that need nothing from 421–424 (Tasks 1–4); the precondition gate (Task 5); sidecars, models, records and store (Tasks 6–10); the adapter, fixtures and Python grading (Tasks 11–19); the grading review (Tasks 20–22); the review budget and `grade_one` (Tasks 23–31); `paired_stats` (Tasks 32–33); plan and runner (Tasks 34–36); report (Tasks 37–41); CLI, slash commands and yield line (Tasks 42–44); walkthrough (Task 45); final validation (Task 46).
- **Preconditions (Task 5):** Tasks 1–4 touch only the design, slice 320, 400 and config code and are committed before the gate. Everything after it needs something 421–424 create: `paired_stats` lives in the `benchmark/` package 421 creates and needs 422's `SIGNIFICANCE` and `POWER` and this slice's records. Task 5 confirms the 300, 320, 400, 420, 421, 422 and 424 names later tasks use. At the time of writing the 421, 422 and 424 names do not exist, so Task 5 stops with `BLOCKED:` there and Tasks 6 onward wait. Every 421/422/424 name below is the name those task files give; read the real module before using one, and if a name differs use the real one and say so in the DEVLOG entry.
- Design gaps found while reading the code (Task 1 writes each into the design; these tasks follow the corrections):
  - **`measure_snapshot` needs a file list (D12).** `take_snapshot_at` measures `exported.files` from `export_commit`; `resolve_files(root, exclusions)` (`snapshot/files.py`) lists tracked files at HEAD, which suits a sandbox tree whose grade commit exists. The signature gets a `files: list[str]` parameter (Task 3).
  - **`_stat` is private (D8).** `audit_variance._stat` is module-private, so Task 22 renames it to a public name (no behavior change) rather than copying it.
  - **`benchmark.review_timeout_s` has no stated default (D7).** It is declared with no default (like `grading_review_model`); `grade` refuses naming it when unset. No value is invented (Task 4).
  - **The 16 KB record bound (Database Schema).** `GradeResult` has unbounded parts: `hidden`, `hidden_id_map` and the review findings grow with the case, and only `regression_failures` is capped. Task 8 stores hidden counts plus the non-passing nodes, puts the id map and the findings in sidecars (`nodes`, and a new `reviews` kind, Task 6), and caps every remaining listing at one constant; Task 10 refuses a record over the bound.
  - **Report row key (D13).** D13 keys rows on `(alias, model, profile, effort_sent)`; the design's Prerequisites (420 D6) group by model, profile, effort sent, `tool_use` and `max_output_tokens`. Task 37 follows 420's identity; the alias is a label, never a key.
  - **Empty selections (D1, D2).** pytest given no node ids runs every test, so an empty hidden set (the 426 slice-case shape) would select the whole suite. `grade_one` never calls `run_suite` with an empty id list (Tasks 26–28).
  - **Rules hash (D7, D10).** `ReviewerRef.rules_hash` comes from the start commit's rules directory, which differs per case, but D10 makes the grader identity one value per benchmark. `ReviewerRef` drops it; each `ReviewOutcome` and `ReviewSummary` carries the rules hash of the tree it reviewed (Tasks 7, 21).
  - **`inject_hidden` signature (API Contracts).** The conftest import difference needs the start tree, so it takes `(tree, case, start, reference)` (Tasks 11, 17).
  - **One reference per environment digest (D8, D9).** A case's replays can carry different environment digests, so one reference is graded per (case, digest), not per case (Task 34).
  - **Seed and sample-count formula (D14, D15).** The seed derives from the benchmark id and the pair, but not how: Task 32 fixes it (sha256, never `hash()`). D15 gives no cases-needed formula or zero-variance result: Task 33 does. An estimate with no pairs is never written (Task 36).
  - **Report extension point (D13, Provides to 426).** 426 adds a table beside the fix-case one without editing report code: Task 38 adds a registry of case-kind tables.
  - **`lockfile_sha256` (Database Schema).** It is a required `str`, but no value exists for a tree with no lock. It becomes `str | None` and is always recorded: the sha256 of the producer's `uv.lock`, `None` when the tree has none (Tasks 8, 25).
  - **Malformed producer TOML and install failures (D5, D16).** The design names no absence for an unparseable producer `pyproject.toml` or a hung reinstall. A parse failure and a stale, missing or unsupported lock are `producer_env_unresolvable` (config); an install timeout (`benchmark.install_timeout_s`, 421) and a missing `uv` are `environment_failed` (harness) (Tasks 14, 25).
  - **Reference lookup (D8, D9).** A `ReferenceGrade` belongs to the case, not to a benchmark. Replays, `--retry-harness` and the report find it with `get_reference_grade(case_id, grader digest, replay environment digest)`; `--retry-harness` also deletes harness-absent reference records; a failed reference is one with an absence or a result that does not pass (Tasks 10, 26, 35, 36, 39).
  - **Walkthrough step 4 test path.** The design names `tests/benchmark/test_grade_one.py`; the tests are in `test_grade_one_edits.py` (Task 29).
  - **Home for the grade models and store (Component Structure).** `benchmark_models.py` and `benchmark_store.py` are shared with 421/424 and near the ~300-line limit, so the grade enums, models and records go in `metrology/grade_models.py` and the grade record methods in `metrology/grade_store.py` (`GradeRecordStore`); only the sidecar kinds extend `benchmark_store.py` (Tasks 6–10).
- Shared names (defined once): `GradeAbsence`, `GradeSubject`, `PairVerdict` StrEnums only in `grade_models.py` (Task 7); `MAX_LISTED_ITEMS`, `DETAIL_MAX_CHARS` only in `grade_models.py` (Task 8); `MAX_GRADE_RECORD_BYTES` only in `grade_store.py` (Task 10); `GRADER_VERSION` only in `grade_one.py`; `PACKAGING_TOOL_TABLES` and `TOOL_CONFIG_FILES` only in `python_grading.py`; `BOOTSTRAP_RESAMPLES`, `MIN_PAIRED_CASES`, `PROJECTED_SAMPLE_COUNTS` only in `paired_stats.py`. Never compare against a literal.
- Absence coverage (Technical Requirements): each `GradeAbsence` is asserted with its class in the task that produces it: Task 24 (`environment_failed`, `environment_changed`, `diff_apply_failed`, `reference_unreadable`), Task 25 (`review_failed`, `producer_env_unresolvable`), Task 26 (`check_tool_mismatch`, `snapshot_failed`, `suite_error`, `grader_timeout`), Task 30 (`reference_failed_grade`). Task 7 asserts every value has a class.
- Failure modes (review rule): every new I/O path has a test that asserts an observable signal (ERROR log plus a recorded `GradeAbsence`): review call raises, times out or returns `UNKNOWN`; suite run times out or raises `SuiteRunError`; diff does not apply; reinstall fails or times out; producer `pyproject.toml` does not parse; snapshot raises; reference unreadable; store write failure or oversized record; grade lock held; run stopped mid-grade (no record, rerun grades again; Task 36).
- Load test: none added. Grading is sequential (one subject at a time under the grade lock) and has no concurrency of its own. Its sandbox and install paths reuse 421's code, whose concurrency load test (421 Task 26) covers them. Every call 425 adds is bounded by a timeout with a test of the observable signal: the review (`benchmark.review_timeout_s`, Task 21), the reinstall (`benchmark.install_timeout_s`, Task 25) and the suites (`benchmark.suite_timeout_s`, Task 26).
- Pyright covers `src` only (`[tool.pyright] include`), so tests are held to `ruff` and a passing run, and every source module to zero pyright errors.
- Tests live in `tests/benchmark/`, `tests/metrology/`, `tests/config/` and `tests/cli/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Nothing here pushes or merges.
- Effort 4/5. Next planned slice: 426.

## Tasks

### Task 1: Create the slice branch and correct the design
- [ ] Read the target: `cf config get git.integration_branch` (its value, or `main` when empty). Check out the target. If `git status --short` lists this task file as modified or untracked, commit it there by path as `docs: add slice 425 tasks`; planning work commits to the target. Stage every later commit by path
  - [ ] Success: `git status --short` does not list the task file
- [ ] Correct the design on the target before any code: edit `user/slices/425-slice.grading-and-paired-report.md` so it states each design-gap bullet in the Context Summary (those bullets are the spec for the edits), and remove the D9 and Consumes sentences saying the architecture and 424 need to change. The architecture (`user/architecture/420-arch.model-benchmark.md`, "Spend is visible before it happens" and Cost) already says grading has its own cap; the 425 entry in the slice plan (`user/architecture/420-slices.model-benchmark.md`) does not, so add one sentence there: grading is its own command with its own cap and bound (D9), and a benchmark's total is the run's cap plus each grade invocation's cap. In `user/slices/424-slice.producer-only-replay-runner.md` change the line saying `bench_plan` arithmetic is something "425 extends with grading terms" to say grading has its own bound (425 D9)
  - [ ] Success: the design's Component Structure, D1, D2, D7–D16, State Management, Database Schema, API Contracts, Integration Points and Verification Walkthrough (step 4 names `test_grade_one_edits.py`) agree with the gap bullets; the slice plan's 425 entry states the grading cap; `grep -n "extends with grading terms" project-documents/user/slices/424-slice.producer-only-replay-runner.md` finds nothing

**Commit**: `docs: correct slice 425 design, add its grading cap to the slice plan, fix 424's bound sentence`

- [ ] `git checkout -b 425-slice.grading-and-paired-report <target>` (or switch to it if it exists)
  - [ ] Success: `git branch --show-current` prints the slice branch

### Task 2: `is_within_floor` accepts floats (D13, 320)
- [ ] `metrology/audit_delta.py`: change the `delta` parameter of `is_within_floor` from `int` to `float`; update its docstring. Behavior is unchanged
- [ ] Tests in `tests/metrology/test_audit_delta.py`: add float cases (a float delta below, at and above `max - min`; a `None` floor returns `None`)
  - [ ] Success: existing int cases in that file pass unchanged; pyright is clean

**Commit**: `refactor: accept float deltas in is_within_floor`

### Task 3: Extract `measure_snapshot` (D12)
- [ ] Read `metrology/snapshot/take.py`, `files.py` and `export.py` first. In `take.py` add `measure_snapshot(root, environment_root, config, registry, runner, project_id, commit_sha, files) -> CodeSnapshot` holding the body `take_snapshot_at` runs inside its `with export_commit` block (build `AdapterContext` from the config's limits and `tool_timeout_s`, `_measure_all`, `_assemble`). It writes no record
- [ ] `take_snapshot_at` calls it with `root=exported.root`, `environment_root=repo_root`, `files=exported.files`, then writes the record exactly as before. If `take.py` would pass ~300 lines, move the helpers it shares into a sibling module
  - [ ] Success: the existing 400 snapshot tests pass unchanged
- [ ] Tests `tests/metrology/snapshot/test_measure_snapshot.py` (use the directory the existing take tests live in): a fake adapter registry and runner; `measure_snapshot` returns a snapshot with the given `project_id` and `commit_sha` and writes nothing to a store (a store double that fails on any write is never called)
  - [ ] Success: tests pass; pyright is clean

**Commit**: `refactor: extract measure_snapshot from take_snapshot_at`

### Task 4: Config keys (D7, D8)
- [ ] `config/keys.py`: add a benchmark-grading group with a constant, a `CONFIG_KEYS` entry and a description for each key (421 and 422 add their benchmark keys in the same file; keep this group together and do not depend on theirs): `benchmark.grading_review_model` (alias string, no default), `benchmark.review_timeout_s` (positive number, no default), `benchmark.review_floor_runs` (int, default 3). Read the floor runs with `get_positive_int_config` and reject a value below 2 with the error type it raises
- [ ] Tests in `tests/config/test_keys.py`: the two unset keys read as unset, never as a value; the floor-runs default is 3; 1 and 0 are rejected; 2 is accepted
  - [ ] Success: tests pass

**Commit**: `feat: add grading config keys`

### Task 5: Preconditions
- [ ] Confirm by grep in `src/squadron` that these exist. 421: `class BenchmarkSandbox`, `class EnvironmentIdentity`, `class ScrubbedEnvironment`, `class CredentialGrant`, `class SuiteSelection`, `class NodeResult`, `class FailureKind`, `class SuiteRunError`, `resolve_environment` with `EnvironmentFailureReason`, `benchmark.install_timeout_s`, `class BenchmarkRecordStore`, `class BenchmarkCase`, `class CaseKind`, `class CaseSet`, `class ProcessRunner`, `benchmark.suite_timeout_s`, the adapter registry in `benchmark/registry.py`, `tests/benchmark/conftest.py` with `collect_ignore_glob`. 422: `is_test_side`, `FixCaseAdapter` with `collect`, `hidden_tests`, `hidden_fixtures`, `superseded_tests`, `excluded_tests` and `grader_commands` on the case, `ConftestFixture`, `benchmark.target_pass_rate_difference`, `benchmark.planned_samples`, `benchmark/yield_report.py`, `SIGNIFICANCE` and `POWER` in `benchmark/separability.py`, and `commands/sq/benchmark.md`. 424: `ImplementationReplay`, `BenchmarkRun`, `ProducerOutcome`, `AbsenceClass`, `LeakScanResult`, `LEAK_RULES_VERSION`, `DiffSidecars`, `replays_for`, the benchmark lock helper (`bench_runner.py`), `sq benchmark run --help` exits 0. 420: `effort_sent`, `tool_use` and `max_output_tokens` on `ProducerConfigRef`. 300, 320 and 400: `run_review_with_profile` (`review/review_client.py`), `resolve_rules_dir` and `load_rules_content`, `normalize_result_categories`, `CodeReviewFinding`, `FloorStat`, `take_snapshot_at`, `derive_project_id`, `SourceLanguage`. If any is missing write `BLOCKED: <name> is not implemented (slice <n>)` under this task, leave it unchecked, and stop (Tasks 2–4 are already committed)
- [ ] Run `uv run pytest tests/metrology tests/review tests/benchmark tests/replay -q` once and record the pass count in a comment under this task, so later tasks can tell their failures from existing ones
  - [ ] Success: all names found; no `BLOCKED:` line

### Task 6: `ContentSidecars` (D11)
- [ ] `metrology/benchmark_store.py`: generalize 424's `DiffSidecars` to `ContentSidecars(root, kind)` with kinds `diffs` (`.diff`), `snapshots` (`.json`), `nodes` (`.json`) and `reviews` (`.json`, the review findings of one grade, Task 8), each under `<store>/sidecars/<kind>/`. `put`/`get` behave as `DiffSidecars` does (write-once, atomic, hash-verified on read, `MetrologyStoreError` on a mismatch or missing file, logged at ERROR). Kinds live in one `StrEnum`. `store.diffs` keeps its name and its `put` return type, so 424's call sites do not change; add `store.snapshots`, `store.nodes` and `store.reviews`
- [ ] Tests `tests/benchmark/test_content_sidecars.py`: each kind round-trips; same bytes twice writes once; a tampered file raises on `get` and logs ERROR; a missing hash raises; sidecars are not read as records by `iter_records`; kinds do not share a directory
  - [ ] Success: 424's diff sidecar tests pass unchanged; new tests pass

**Commit**: `refactor: generalize diff sidecars into content sidecars`

### Task 7: Enums and small models (D10, D16, Patterns)
- [ ] In new `metrology/grade_models.py` add `GradeSubject` (`reference`, `replay`), `GradeAbsence` (the eleven values of D16's table), `PairVerdict` (`a_ahead`, `b_ahead`, `not_distinguishable`, `too_few_cases`), and one mapping `GRADE_ABSENCE_CLASS: dict[GradeAbsence, AbsenceClass]` built from the D16 table (only `producer_env_unresolvable` is `config`). Add frozen `ReviewerRef` (alias, model, profile, effort, `template_hash`, and derived `reviewer_key`: sha256 of model, profile, effort, template_hash; it has no rules hash, because the rules directory differs per case and the grader identity is one value per benchmark, D10), `GraderIdentity` (derived, validated `digest`: sha256 of the canonical JSON of `grader_version`, the reviewer and `review_floor_runs`), `SnapshotRef(sha256)`, `SuppressionCounts` (`noqa` and `type_ignore` × `source` and `test`), `ReviewOutcome` (findings, `unnormalized_count`, `cost_usd`, and `rules_hash`: the sha256 of the rules the reviewed tree supplied, `None` when it had none) and `ReviewSummary` (what a record keeps of one review: counts by severity, total, `unnormalized_count`, `cost_usd`, `rules_hash`, `findings_sha256` of the `reviews` sidecar)
- [ ] Tests `tests/benchmark/test_grade_identity.py`: the mapping covers every `GradeAbsence`; the digest is stable across field order and changes with the reviewer, the version and the floor runs; `reviewer_key` ignores `alias`; `ReviewerRef` has no rules-hash field; a tampered digest fails validation; a `ReviewSummary` built from a `ReviewOutcome` has the same total and severity counts
  - [ ] Success: tests pass

### Task 8: `GradeResult` and its size caps (D2, Database Schema)
- [ ] `GradeResult` in `grade_models.py` per the design, with these changes so a record can hold the 16 KB bound: `lockfile_sha256` is `str | None` (the sha256 of the producer's `uv.lock`, `None` when the tree has none; recorded for every grade, not only after a reinstall); `hidden` becomes `hidden_total`, `hidden_passed` and `hidden_failures` (every hidden node whose outcome is not `passed`, as `NodeResult`); the hidden id map is stored as a `nodes` sidecar (`hidden_id_map_sha256`); `reviews` is `tuple[ReviewSummary, ...]`. Define `MAX_LISTED_ITEMS = 50` and `DETAIL_MAX_CHARS` once. A validator raises on more than `MAX_LISTED_ITEMS` entries in `regression_failures`, `hidden_failures`, `injection_clashes`, `config_edits` or `test_edits`, and on a `detail` over `DETAIL_MAX_CHARS`; each capped list has its true count beside it (`regression_failure_count`, `injection_clash_count`, `config_edit_count`, `test_edit_count`). `passed` is a property: `hidden_passed == hidden_total` and `regression_failure_count == 0` (D2); never a stored field
- [ ] Tests `tests/benchmark/test_grade_models.py`: `passed` truth table (all hidden pass and no regressions; one hidden fail; one hidden `skipped` or `not_run` counts as not passed; one regression with hidden passing; zero hidden and zero regressions, the 426 slice-case shape, passes); a list over the cap and a `detail` over its cap each fail validation
  - [ ] Success: tests pass

### Task 9: Grade and estimate records (D10, Database Schema)
- [ ] In `grade_models.py`: `ReferenceGrade`, `ImplementationGrade`, `PairEstimate` (σ²_w, σ²_b, MDD now, cases needed per k), `SampleSizeEstimate`. `MetrologyRecord` (`metrology/models.py`) gains `reference_grade`, `implementation_grade`, `sample_size_estimate` as optional siblings with `RECORD_TYPE_*` constants; no migration
- [ ] Tests in `tests/benchmark/test_grade_models.py`: a record with `result=None` and an absence round-trips; a typical-heavy `ReferenceGrade` (50 regression ids of 100 characters, 10 entries in each other capped list, three `ReviewSummary`) serializes under 16 KB
  - [ ] Success: tests pass; an old `MetrologyRecord` JSON without the new fields still loads

**Commit**: `feat: add grade and sample-size records`

### Task 10: Record ids and store methods (D10, State Management)
- [ ] `metrology/grade_store.py`: `reference_grade_id(case_id, grader, environment_digest)` → `refgrade-<case_id[5:17]>-<grader digest[:12]>-<environment digest[:8]>` and `implementation_grade_id(replay_id, grader)` → `implgrade-<replay id without its prefix>-<grader digest[:8]>`
- [ ] `GradeRecordStore(records: BenchmarkRecordStore)` in the same module (sidecars stay on `records.snapshots`, `.nodes` and `.reviews`): `write_reference_grade`, `get_reference_grade(case_id, grader_digest, environment_digest)`, `write_grade`, `grades_for(benchmark_id)` (implementation grades only), `delete_grades(ids) -> int` (takes reference and implementation grade ids; for `--retry-harness` only), `write_estimate` (overwrites the benchmark's one record), `latest_estimate(case_set)`. Define `MAX_GRADE_RECORD_BYTES = 16 * 1024`: a grade record whose JSON is larger is not written, logs ERROR naming the record id and its largest field, and raises `MetrologyStoreError`. A second write of the same grade id with different content raises; a write failure logs ERROR and raises `MetrologyStoreError`. Reuse 421's `write_record` and `iter_records`. Lookup contract: a `ReferenceGrade` carries no benchmark id (it belongs to the case and is shared by every benchmark of it); a replay, the report and `--retry-harness` find it with `get_reference_grade(replay.case_id, grader.digest, replay.environment_digest)`
- [ ] Tests `tests/benchmark/test_grade_ids.py` and `test_grade_store.py`: ids are deterministic; a new reviewer, a bumped `grader_version` and a different environment digest each give a new id; the replay prefix is removed exactly once; round trips; `get_reference_grade` with a different environment digest returns `None` and with a replay's own digest returns that case's reference whichever benchmark wrote it; `grades_for` returns only that benchmark's; `delete_grades` removes only the named ids, reference or implementation, and returns the count; `write_estimate` twice leaves one record; `latest_estimate` picks the newest `created_at` for the case set; a failing write logs ERROR; an oversized record is refused with an ERROR naming its largest field and nothing is written; the Task 9 typical-heavy record is accepted
  - [ ] Success: tests pass; 421 and 424 store tests unchanged

**Commit**: `feat: add grade ids and store methods`

### Task 11: `GradingAdapter` protocol, registry and tree reader (API Contracts, Patterns)
- [ ] `benchmark/grading_adapter.py`: the `GradingAdapter` Protocol as the design lists it, except that `inject_hidden` takes `(tree, case, start, reference)`, because the conftest import difference needs the start tree; frozen `RestorationResult(config_edits)`, `InjectionResult(id_map, files_written, clashes)`; `TreeReader` Protocol (`read(path) -> bytes`, `list_paths() -> tuple[str, ...]`). `benchmark/registry.py`: register grading adapters by `SourceLanguage` beside 421's, with a lookup that raises a named error for a language with none (logged at ERROR)
- [ ] `benchmark/tree_reader.py`: `GitTreeReader(runner, repo_root, sha)` reading through `git show <sha>:<path>` and `git ls-tree -r --name-only` using `ProcessRunner`; a failing call raises `TreeReadError` carrying the stderr tail
- [ ] Tests `tests/benchmark/test_grading_registry.py` and `test_tree_reader.py`: lookup of a registered and an unregistered language; the reader against a tmp git repo (file, missing path raises, listing)
  - [ ] Success: tests pass

**Commit**: `feat: add the grading adapter protocol, registry and git tree reader`

### Task 12: Fixture trees: start and reference (test infrastructure)
- [ ] Find the fixture source in squadron history: `git log --diff-filter=M --format='%h %s' -- 'tests/**/test_*.py'`, then pick a commit whose subject starts with `fix:` and whose changed test file has a class with a parametrized method, whose directory has a `conftest.py`, and whose test file and conftest import only pytest, the standard library and `squadron` (the fixture trees run under the repo's own interpreter). Record the commit sha and file paths in a comment at the top of `tests/benchmark/grading_fixtures.py`
- [ ] Copy that test file (start and fixed versions), the conftest and a minimal `pyproject.toml` into `tests/benchmark/fixtures/grading/start/` and `reference/`. The reference conftest adds one import and one fixture over the start's. `grading_fixtures.py` builds a tmp git repo with the start commit and the reference commit and returns shas and a `GitTreeReader` for each
- [ ] In `grading_fixtures.py` add `run_pytest_ids(tree, ids) -> dict[str, str]` (node id to `passed`, `failed`, `skipped` or `error`): it runs `sys.executable -m pytest -p no:cacheprovider --junitxml=<tmp file>` with `cwd=tree` and the ids as arguments, and reads the XML. `collect_ids(tree, ids)` does the same with `--collect-only -q` and returns the collected ids. Tasks 17 and 18 use both
- [ ] Keep the fixtures out of the repo's own runs: confirm `tests/benchmark/conftest.py`'s `collect_ignore_glob` covers `fixtures/grading` (421 sets `fixtures/*`); if `ruff check` flags the copies, add `tests/benchmark/fixtures` to ruff's `extend-exclude`
- [ ] Tests `tests/benchmark/test_grading_fixtures.py`: the builder yields the two commits; the start and reference test files differ; the hidden node id for the parametrized class method is `<file>::<Class>::<method>[<param>]`; `collect_ids` on the start tree returns that id; `run_pytest_ids` reports `passed` for it on the reference tree and `failed` after a one-line edit that breaks it in a tmp copy
  - [ ] Success: tests pass; `uv run pytest tests/benchmark --collect-only -q` lists no node under `fixtures/`; `ruff check` is clean

**Commit**: `test: add start and reference fixture trees and a pytest runner for grading`

### Task 13: Fixture trees: producer variants (test infrastructure)
- [ ] Under `tests/benchmark/fixtures/grading/` add `producer_*/` variants as plain files (same ignore rules as Task 11): (a) edits an existing assertion, (b) adds `# type: ignore` and `# noqa: E501`, (c) loosens `[tool.pyright]` and `[tool.ruff]` while adding a `[project].dependencies` entry and a `[tool.uv]` change, (d) a test and a fixture with the same names as the hidden ones, (e) an existing `test_sqhidden_<stem>.py`. The builder gains a function that applies a variant over the start commit and returns the tree
- [ ] Tests in `test_grading_fixtures.py`: each variant builds; each differs from the start only in the files described
  - [ ] Success: tests pass; collect-only and `ruff check` still clean

**Commit**: `test: add producer variant trees for grading`

### Task 14: Tool-config restoration and dependency-change detection (D4, D5)
- [ ] `benchmark/python_grading.py`: define `PACKAGING_TOOL_TABLES` and `TOOL_CONFIG_FILES` once. `restore_tool_config(tree, start)`: in `pyproject.toml` replace every `[tool.*]` table except the packaging ones with the start commit's (a table absent at start is removed), read with `tomllib`, written with `tomli-w`; standalone files in `TOOL_CONFIG_FILES` are restored to start content or deleted when the start had none. Return `config_edits` naming each table or file whose producer content differed (`tool.ruff`, `pyrightconfig.json`). A producer `pyproject.toml` that does not parse raises `ProducerConfigError` (path and parse error), logged at ERROR
- [ ] `deps_changed(tree, start)`: true when `uv.lock` differs from the start, or when `pyproject.toml` with the restored tool tables removed differs in content from the start's (compare parsed data, not text)
- [ ] Tests `tests/benchmark/test_python_grading_restore.py` on the Task 12–13 trees: variant (c) restores `[tool.ruff]` and `[tool.pyright]`, keeps `[project].dependencies` and `[tool.uv]`, and reports exactly `tool.pyright`, `tool.ruff`; an unchanged table is not reported; a producer-added `ruff.toml` is deleted and reported; a start `pyrightconfig.json` the producer edited is restored; a pyproject with no `[tool]` section is untouched. Further rules: a `[tool.*]` table the producer added and the start lacked is removed and reported; a start table or start standalone file the producer deleted is restored and reported; every entry of `PACKAGING_TOOL_TABLES` (parametrized over the constant) follows the producer; after restoration `uv lock --check` passes in the rewritten tree (D4's `--locked` claim); a malformed producer `pyproject.toml` raises `ProducerConfigError` and logs ERROR, in both `restore_tool_config` and `deps_changed`
- [ ] Tests for `deps_changed`: variant (c) is true; a change only in `[tool.ruff]` is false; a comment-only or reformat-only pyproject change is false; a changed `uv.lock` alone is true
  - [ ] Success: tests pass

**Commit**: `feat: add tool-config restoration and dependency-change detection`

### Task 15: Test-side edit detection and restoration (D6)
- [ ] `test_side_edits(tree, start)` returns the existing test-side files (422's `is_test_side`, judged at the start tree) the producer modified or deleted, sorted. `restore_test_files(tree, start, paths)` writes the start content back (recreating deleted files). Producer-added test files are not touched
- [ ] Tests on the Task 12–13 trees: variant (a) reports its file and the restore brings back the original assertion; a deleted test file is recreated; a new test file is neither reported nor removed; a modified non-test file is not reported
  - [ ] Success: tests pass

### Task 16: Suppression counting (D6)
- [ ] `count_suppressions(diff: bytes) -> SuppressionCounts`: only added lines (`+` lines outside `+++` headers) carrying `# noqa` or `# type: ignore` (including `# pyright: ignore`), counted separately for source and test files (`is_test_side` on the diff's path). Lenient about spacing and case and about a rule list after the marker. Parse the semantic marker, not the formatting
- [ ] Tests: the variant (b) diff gives one `noqa` and one `type_ignore` in the right bucket; `#noqa`, `#  NOQA:E501,F401`, `# type:ignore[attr-defined]`, `# pyright: ignore[reportX]` all count; removed lines and context lines do not; a marker inside a diff header path does not; an empty diff gives zeros; a test-file addition counts under `test`
  - [ ] Success: tests pass

**Commit**: `feat: count test edits and added suppressions`

### Task 17: Hidden-test injection, module and id mapping (D3)
- [ ] `inject_hidden(tree, case, start, reference)`: for each test file holding hidden tests, write `test_sqhidden_<stem>.py` in the same directory. Content in order: the import lines in the reference's `conftest.py` that the start's lacks (both read through their `TreeReader`), the reference's whole version of the file via the `TreeReader`, then the source of each hidden fixture whose `conftest.py` is on that file's path (`ConftestFixture`). Return `InjectionResult` with the id map (replace only the file part of the node id; class nesting and parametrization suffix are kept). Nothing the producer wrote is removed or overwritten
- [ ] Tests `tests/benchmark/test_python_grading_inject.py` on the Task 12–13 trees: the mapped id for the class-nested parametrized node is exact; the written module contains the conftest import, the reference file body and the fixture source in that order; a producer file in the same directory is byte-identical afterwards; `collect_ids` (Task 12) on the injected tree returns exactly the hidden ids and none of the other tests in the copied file
  - [ ] Success: tests pass

### Task 18: Injection clashes and filename collisions (D3)
- [ ] In `inject_hidden`, record clashes and never resolve them by overwriting: a producer test with the same name as a hidden test in the original file (both run, different module names); a producer fixture with a hidden fixture's name (the injected module's own fixture shadows the conftest one for that module); an existing sibling filename (append `_2`, `_3`, and record the rename)
- [ ] Tests on variants (d) and (e), each through `run_pytest_ids` (Task 12) on the tree: for the same-name test clash, selecting the producer's test id and the injected module's hidden id yields two separate results, and making only the hidden one fail leaves the producer's passing (both sides run and are independent); for the fixture clash, a test in the injected module sees the hidden fixture's value while the producer's module sees the producer's; the clash is recorded for each; the sibling name becomes `test_sqhidden_<stem>_2.py` with the rename in `clashes` and in the id map, and its tests run; a second collision gives `_3`; each clash string is stable text the report can count
  - [ ] Success: tests pass

**Commit**: `feat: inject hidden tests as sibling modules with clash records`

### Task 19: `PythonGradingAdapter` assembly (Technical Scope)
- [ ] Gather the Tasks 14–18 functions into `PythonGradingAdapter` in `python_grading.py`, registered for Python in the grading registry. If the module passes ~300 lines, split injection into `python_injection.py` and keep the class a thin composition
- [ ] Tests: `isinstance(PythonGradingAdapter(), GradingAdapter)`; the registry returns it for Python; one end-to-end pass over the fixture trees calls every method once on a producer variant
  - [ ] Success: tests pass; `wc -l` of each new module is under ~300

**Commit**: `feat: add the Python grading adapter`

### Task 20: Reviewer resolution (D7)
- [ ] `benchmark/grade_review.py`: `resolve_reviewer(alias) -> ReviewerRef` from `models.toml` alias resolution (model, profile, effort) and the sha256 of the `code` template text. An unknown alias raises a named error listing the alias
- [ ] Tests `tests/benchmark/test_grade_reviewer.py`: a known alias resolves with a stable `template_hash`; changing the template text changes `reviewer_key`; an unknown alias raises naming it
  - [ ] Success: tests pass

### Task 21: `review_tree_diff` (D7)
- [ ] `review_tree_diff(tree, base_sha, reviewer) -> ReviewOutcome`: calls `run_review_with_profile` with the `code` template, `inputs={"diff": base_sha, "cwd": tree}`, `no_tools=True`, the alias's effort and the tree's own rules (`resolve_rules_dir` and `load_rules_content` over `tree`; the outcome's `rules_hash` is the sha256 of the loaded content, `None` when the tree has none), under `asyncio.wait_for(..., benchmark.review_timeout_s)`. Call `normalize_result_categories(result)`, which returns nothing and normalizes `result.findings` in place, then build each `CodeReviewFinding` from those findings (severity, category, raw category, location, summary from the title); a finding whose severity is off the review scale is dropped and counted in `unnormalized_count`. Read `cost_usd` the way `review/run_cost.py` does. A raise, a timeout, or verdict `UNKNOWN` with no findings raises `ReviewFailed(detail)` after logging at ERROR with the error text; a review that ran and found nothing is a valid outcome with zero findings. The module's collaborator (the review function) is a parameter, so tests pass a double
- [ ] Tests `tests/benchmark/test_review_tree_diff.py`: findings normalize to the 400 shape (a lenient emitted category maps to its canonical value, an absent one stays `None`); a tree without rules gives `rules_hash=None` and different rules content gives a different hash; an off-scale severity increments `unnormalized_count`; zero findings with a real verdict is valid; a raising double, a double that sleeps past a short timeout, and an `UNKNOWN`-empty result each raise `ReviewFailed` and log ERROR (`caplog`); the double records `no_tools=True` and the `diff`/`cwd` inputs; `cost_usd=None` is carried as `None`
  - [ ] Success: tests pass

### Task 22: Review floor (D8)
- [ ] In `metrology/audit_variance.py` rename `_stat` to a public name and update its callers (no behavior change). In `grade_review.py` add `review_floor(outcomes, runs) -> FloorStat`: total findings per run reduced with that function; fewer than `runs` outcomes, or a failed run, raises (a floor never comes from fewer runs). `runs` below 2 raises
- [ ] Tests: three outcomes with 2, 4, 3 findings give min 2, max 4, mean 3, the sample stddev; two outcomes work; one outcome raises; the existing `audit_variance` tests pass unchanged
  - [ ] Success: tests pass

**Commit**: `feat: add the fixed grading review and its noise floor`

### Task 23: Review budget (D9)
- [ ] `benchmark/grade_budget.py`: `ReviewBudget(cap_usd, per_review_usd)`, one instance shared by every `grade_one` call in a run. `before_review()` raises `GradeCapReached` when spent is at or above the cap, and is called before every review call, including each floor run. `after_review(cost_usd)` adds the cost, or `per_review_usd` when it is `None`, and counts the unpriced review. Exposes `spent` and `unpriced`
- [ ] Tests `tests/benchmark/test_grade_budget.py`: under the cap passes; at the cap raises; a review that crosses the cap is allowed and the next is refused; `None` counts at the per-review figure and increments `unpriced`; `spent` sums priced and unpriced alike
  - [ ] Success: tests pass

### Task 24: `grade_one` context and sandbox step (D1, D16)
- [ ] `benchmark/grade_one.py`: define `GRADER_VERSION` (int) and a frozen `GradeDeps` of injected collaborators (sandbox factory, grading adapter registry, reviewer function, `ReviewBudget`, snapshot measurer, store, process runner, clock). `grade_one(case, subject, deps)` part 1: open `BenchmarkSandbox(start_sha)`; `environment_failed` when the environment does not resolve; digest differing from the replay's (for a reference: from the environment digest it was planned for, Task 34) is `environment_changed`; `git apply --binary` of the diff (sidecar for a replay, `git diff --binary start..reference` in the user's checkout for a reference) then commit as the benchmark identity (the sequence keeps a named step before the apply, empty for replays, so Task 30 adds the reference baseline there without reordering); a failing apply is `diff_apply_failed`; a failing `git show`/`git diff` of the reference is `reference_unreadable`. Each absence logs ERROR with the stderr tail and returns a record carrying the class from `GRADE_ABSENCE_CLASS`
- [ ] Tests `tests/benchmark/test_grade_one_sandbox.py` with doubles: each of the four absences is produced by its own double with the right class and an ERROR log; a clean apply produces a commit whose parent is `start_sha`; the sandbox is removed afterwards unless keep is set
  - [ ] Success: tests pass

### Task 25: `grade_one` review, restoration and reinstall (D1, D5, D9)
- [ ] Part 2, in this order: review of `start..HEAD` first (a replay: `budget.before_review()`, one call, `budget.after_review(cost)`; the review's findings go to `store.reviews` and its `ReviewSummary`, carrying the tree's `rules_hash`, into the result; a reference: Task 30); then `restore_tool_config` to get `config_edits`; then `deps_changed` and, when true, 421's `resolve_environment` (`uv sync --locked --all-extras --dev` under the harness environment, bounded by `benchmark.install_timeout_s`) with `reinstalled=True`. 421's failure reasons map to absences: `lock_stale_or_unresolvable`, `no_lockfile` and `lockfile_unsupported` are `producer_env_unresolvable` (config); `install_timeout` and `installer_missing` are `environment_failed` (harness). A `ProducerConfigError` (Task 14) is `producer_env_unresolvable`. Every grade records `lockfile_sha256`, `None` when the producer's tree has no `uv.lock`; a `ReviewFailed` is `review_failed`. `GradeCapReached` is not caught here: it propagates and no record is written. The record's `grading_cost_usd` is the sum of the priced review costs, `None` when none was priced
- [ ] Tests `tests/benchmark/test_grade_one_prep.py`: an ordered call log shows budget check, review, budget accounting, then restore, then deps check, then reinstall; a changed lock triggers the reinstall; `lockfile_sha256` is the lock's hash with or without a reinstall and `None` for a tree with no lock; a stale lock, a missing lock and a malformed producer `pyproject.toml` each give `producer_env_unresolvable` (class `config`) with an ERROR log naming the cause; a reinstall timeout and a missing `uv` each give `environment_failed` (class `harness`) with an ERROR log; `review_failed` stops before any test run; the review sees the tree as the producer wrote it (the double inspects `pyproject.toml` and finds the producer's `[tool.ruff]`); a budget at its cap raises `GradeCapReached` before any review call and writes no record; the review's cost reaches the budget and the record
  - [ ] Success: tests pass

**Commit**: `feat: add the review budget and the grade sandbox, review and reinstall steps`

### Task 26: `grade_one` producer-new tests and snapshot (D1, D12)
- [ ] Part 3: collect node ids (`collect`), producer-new = collected minus the start ids (the `baseline_nodes` sidecar of the reference found with `get_reference_grade(case_id, grader.digest, replay.environment_digest)`, Task 10; a replay with no such reference raises `MissingReferenceGrade`, logged at ERROR, because the runner grades a reference before its replays), `run_suite(nodes(producer-new))` giving `producer_new_passed` and `producer_new_failed` (never part of `passed`); an empty producer-new list runs nothing (0 and 0), because `run_suite` with no ids would run every test. Then `measure_snapshot` (tree as root and environment root, `files` from `resolve_files(tree, effective_exclusions(config.project_exclusions, registry.values()))` with `config = read_snapshot_config(tree)`, the case's `project_id`), snapshot stored through `store.snapshots`. Lint and type totals are the sums of `per_file`, reported only when the case's `grader_commands` include that check; a tool identity that does not name `ruff`/`pyright` is `check_tool_mismatch`; a measurement the snapshot marks absent gives `None`; a raising measurer is `snapshot_failed`. `SuiteRunError` is `suite_error`; a suite timeout is `grader_timeout`
- [ ] Tests `tests/benchmark/test_grade_one_snapshot.py`: a replay with no reference grade raises `MissingReferenceGrade` and logs ERROR; producer-new selection never includes a start id; a producer that added no tests never calls `run_suite` for this step (the double fails if it is called with an empty list); failing producer-new tests do not change `passed`; totals sum correctly; a case without a type command leaves `type_total=None`; an absent lint measurement gives `None`, not 0; `check_tool_mismatch`, `snapshot_failed`, `suite_error` and `grader_timeout` each come from a double with their class and an ERROR log
  - [ ] Success: tests pass

### Task 27: `grade_one` test restoration and regression run (D1, D2, D6)
- [ ] Part 4, after the snapshot: `test_side_edits` → `restore_test_files` → `test_edits`; regression run `nodes(start ids − superseded − excluded)` (never `all_tests()` plus deselect; the start ids are the reference's `baseline_nodes`, as in Task 26), failures = `failed`, `error` or `not_run` (`skipped`, `xfailed` are not), truncated to `MAX_LISTED_ITEMS` ids with the full count kept. An empty regression selection never calls `run_suite` (an empty id list would run every test)
- [ ] Tests `tests/benchmark/test_grade_one_regression.py`: superseded and excluded ids and producer-added ids are never in the regression selection; regression nodes ending `skipped` or `xfailed` record no failure, while `failed`, `error` and `not_run` each record one; the order of calls is review, restore config, producer-new, snapshot, restore tests, regression (ordered log, D1); a producer that weakened an existing assertion has the original run in the regression step and `test_edits` lists the file; 51 failures keep 50 ids and count 51; an empty regression selection never calls `run_suite`
  - [ ] Success: tests pass

**Commit**: `feat: add producer-new, snapshot and regression steps to grade_one`

### Task 28: `grade_one` hidden run, suppressions and the grade record (D1, D3, D6)
- [ ] Part 5, after the regression run: `inject_hidden` into the restored tree then `run_suite(nodes(injected ids))`, storing the id map as a `nodes` sidecar; `count_suppressions` on `git diff start..HEAD` (suppressions stay in the tree). An empty hidden set never calls `run_suite` and gives `hidden_total=0`. Assemble `GradeResult` (every capped list truncated to its cap with its true count, `detail` truncated) and write `ImplementationGrade` with the environment digest, cost and wall time
- [ ] Tests `tests/benchmark/test_grade_one_hidden.py`: the hidden run is the last step in the ordered log; an empty hidden set (the 426 shape) never calls `run_suite` for the hidden step and `passed` reduces to no regressions; suppressions are counted from the diff; the id map sidecar exists and its hash is on the record; 51 test edits keep 50 names and count 51; the written record has `absence=None`
  - [ ] Success: tests pass

**Commit**: `feat: add the hidden, suppression and record steps to grade_one`

### Task 29: Edits are counted, not honored (Functional Requirements)
- [ ] Tests `tests/benchmark/test_grade_one_edits.py` (named so `-k edits` selects it): grade the Task 13 variants (a), (b) and (c) through `grade_one` with doubles whose suite results depend only on the restored tree; each count (`test_edits`, `suppressions`, `config_edits`) shows, and `passed` equals the pass of the same replay without the edit
  - [ ] Success: `uv run pytest tests/benchmark/test_grade_one_edits.py -k edits -v` passes (walkthrough step 4)

**Commit**: `test: verify grade_one counts edits without honoring them`

### Task 30: Reference grade, baseline and floor (D8)
- [ ] Reference path in `grade_one`: in the step Task 24 left before the apply, collect start node ids → `store.nodes` sidecar and `measure_snapshot` of the start tree → `store.snapshots` sidecar (baseline totals recorded); then the reference diff, then `review_floor_runs` reviews, each preceded by `budget.before_review()` (any `ReviewFailed` fails the reference with `review_failed`; `GradeCapReached` between floor runs propagates and writes no record) and `review_floor`; the rest as a replay. A reference whose own grade does not pass records `reference_failed_grade`. Writes `ReferenceGrade`
- [ ] Tests `tests/benchmark/test_grade_one_reference.py`: baseline sidecars exist and are taken before the diff applies (ordered log); three floor reviews run and the floor equals their reduction; one failing floor run gives `review_failed` and no floor; a budget that reaches its cap after the second floor run raises `GradeCapReached` and no `ReferenceGrade` is written; a hidden failure on the reference gives `reference_failed_grade` (class harness); a `ReferenceGrade` is written once per (case, grader, environment)
  - [ ] Success: tests pass; with Tasks 24–26 all eleven `GradeAbsence` values are asserted with their class

### Task 31: Live grade of one reference (Development Approach 5)
- [ ] With a scratch script under `/tmp` (not the repo), build one squadron case from a recent `fix:` commit using 422's case builder, then call `grade_one` for its reference with the real sandbox factory, real git and uv, a reviewer double, and `keep` set. Record in a comment under this task the grade's pass, `reinstalled`, the injected filename and the kept path
  - [ ] Success: the reference grade passes; `test_sqhidden_*.py` sits beside the original test file in the kept tree; `git diff <start_sha> -- pyproject.toml` there shows no `[tool.*]` change. If injection fails, fix it here with a test (the design says to adjust the injection method), and record the failure in the DEVLOG; the fix is committed with this task's marker. Delete the kept tree afterwards
- [ ] If the case builder cannot produce a case for any recent squadron fix commit, write `BLOCKED:` with the builder's output under this task and stop

**Commit**: `feat: add the reference grade with baseline and review floor`

### Task 32: Per-case reduction and the paired comparison (D14)
- [ ] `benchmark/paired_stats.py` (pure: no I/O, no store, no model): `BOOTSTRAP_RESAMPLES = 10_000`, `MIN_PAIRED_CASES = 5`; `case_pass_fraction(samples)` (passes over k, config absences counted as fails); `paired_differences(a, b)`; `bootstrap_mean_interval(values, seed) -> (low, high)` as the percentile 95% interval of the mean over resamples of cases with replacement, and `pair_seed(benchmark_id, key_a, key_b) -> int`: the first 8 bytes of the sha256 of the benchmark id and the two configs' identity strings in sorted order (never `hash()`, which is salted per process). The pair is reported in that sorted order, cases are processed sorted by case id, and the resampling uses its own `random.Random(seed)`; `compare_pair(d, seed) -> PairComparison(mean, low, high, verdict)`: fewer than `MIN_PAIRED_CASES` gives `too_few_cases` with no interval; an interval containing zero is `not_distinguishable`; else `a_ahead`/`b_ahead`
- [ ] Tests `tests/benchmark/test_paired_stats.py` against hand-computed values: `p_A` of `[1,1,0]` is 2/3; a pair with constant difference 0.2 over six cases gives mean 0.2 and an interval of (0.2, 0.2), both compared with `pytest.approx`, and `a_ahead`; a symmetric pair with mean 0 gives an interval containing zero; four cases gives `too_few_cases`; the same seed gives the same interval and a different seed may differ; `pair_seed` gives one value for (A, B) and (B, A), and the same value and the same interval in two subprocesses started with different `PYTHONHASHSEED`; `bootstrap_mean_interval` is importable by name for 427
  - [ ] Success: tests pass

**Commit**: `feat: add the paired bootstrap`

### Task 33: Sample-count estimate (D15)
- [ ] In `paired_stats.py`: `estimate_sample_count(per_case_samples, target_difference) -> tuple[PairEstimate, ...]`: for each config pair with k ≥ 2 and at least `MIN_PAIRED_CASES` cases, `σ²_w` is the pooled sample variance of per-sample pass outcomes within (case, config) summed over the two configs, `σ²_b = max(0, Var_c(d) − σ²_w / k)` (`Var_c` is the sample variance, n − 1, of the per-case mean differences), `MDD(n,k) = (z₀.₉₇₅ + z₀.₈₀)·√((σ²_b + σ²_w/k)/n)` with `z₀.₉₇₅ = NormalDist().inv_cdf(1 − SIGNIFICANCE / 2)` and `z₀.₈₀ = NormalDist().inv_cdf(POWER)` (`SIGNIFICANCE` and `POWER` imported from 422's `benchmark/separability.py`, never redefined), and cases needed for the target at each k in `PROJECTED_SAMPLE_COUNTS = (1, 2, 3, 5)`: `max(MIN_PAIRED_CASES, ceil((z₀.₉₇₅ + z₀.₈₀)² · (σ²_b + σ²_w / k) / target²))`, so zero total variance gives MDD 0 and `MIN_PAIRED_CASES` cases. Fewer cases or k < 2 returns an empty tuple
- [ ] Tests: a hand-computed two-config fixture (σ²_w, σ²_b, MDD and cases-needed values written out in the test); the cases-needed values written out by hand for k = 1 and k = 3; zero within- and between-case variance gives MDD 0 and `MIN_PAIRED_CASES`; a fixture whose between-case variance is smaller than `σ²_w / k` gives `σ²_b == 0`; identical samples give zero within-case variance; k = 1 and four cases each return empty; the function is deterministic
  - [ ] Success: tests pass

**Commit**: `feat: add the measured sample-count estimate`

### Task 34: Grade plan, refusals and the stated bound (D9)
- [ ] `benchmark/grade_plan.py`: `plan_grading(...)`: references to grade (one per case and distinct environment digest among the case's gradable replays that has no `ReferenceGrade` under this grader identity; a case with no gradable replay needs none; each replay is graded against the reference of its own digest) and replays to grade (committed, non-harness-absent, no `ImplementationGrade`), after 421's orphan sweep. Refusals raise `GradeRefusal` naming what is missing: no `--max-cost`; no reviewer (names `--review-model` and `benchmark.grading_review_model`); `benchmark.review_timeout_s` unset; a case's `project_id` with no `--repo` matching `derive_project_id` (names the project); no per-review figure (largest observed `review.cost_usd` among stored grades with the same `reviewer_key`, else `--review-cost`; names the flag). `render_bound(plan)` prints the design's block, including the "capped at run cap" and "+ one review of overshoot" lines, and says no per-review cap exists. The plan carries the figure so the runner can build the `ReviewBudget`
- [ ] Tests `tests/benchmark/test_grade_plan.py`: each refusal; the figure comes from the store's largest observed cost over `--review-cost`; two replays of one case with different environment digests plan two references and both count in the bound; the review count is `references × floor runs + replays`; already graded subjects are excluded; the bound text matches the design's example for a fixture with 10 references, 54 replays, $0.18
  - [ ] Success: tests pass

**Commit**: `feat: add grade planning, refusals and the stated bound`

### Task 35: Runner order, cap and lock (D8, D9)
- [ ] `benchmark/grade_runner.py`: take `<benchmark root>/<benchmark_id>.grade.lock` (424's lock helper; a second live holder refuses naming the benchmark); print the bound before any dispatch; build one `ReviewBudget` from the run cap and the plan's figure and put it in `GradeDeps`; for each case grade its reference or references first (a failed reference, meaning a `ReferenceGrade` with an absence or a result that does not pass, marks the case dropped and skips its replays), then its replays sample-major then config. The runner does not check the cap itself: it catches `GradeCapReached` from `grade_one`, stops, keeps every record already written, and returns the status for exit 2. The summary reads `budget.spent` and `budget.unpriced`
- [ ] Tests `tests/benchmark/test_grade_runner.py` with doubles: the bound prints before the first double call (ordered log); references precede their replays; replay order is sample-major; a reference with an absence and a reference whose result does not pass each drop the case and skip its replays; a double that raises `GradeCapReached` on its third review stops the run, no record is lost and the status is the cap status; the summary reports spent and unpriced from the budget; a held lock refuses and leaves the holder untouched
  - [ ] Success: tests pass

### Task 36: Resume, retry-harness and the estimate (D9, D15, D16)
- [ ] In `grade_runner.py`: a rerun skips every subject that has a record id (D10); a grade with a harness absence is skipped unless `--retry-harness`, which first deletes the harness-absent reference and implementation grade records of the planned subjects (references are found with the Task 10 lookup) and reports how many; `--case` filters; a grade killed mid-way writes no record, so a rerun grades it again. At the end, write one `SampleSizeEstimate` (overwritten each run) from `estimate_sample_count` only when it returns at least one pair; otherwise write nothing and have the summary say why (one config, k below 2, or fewer than `MIN_PAIRED_CASES` included cases). The summary reports counts by outcome and absence kind
- [ ] Tests: a second run grades nothing new; a harness-absent grade is skipped, then retried with `--retry-harness` and the deleted count is reported; a harness-absent reference is deleted and graded again; an interrupted double leaves no record and the rerun grades it; the estimate is written for two configs at k = 3 with enough included cases; with four included cases, one config, or k = 1 nothing is written and the summary names the reason; a store write failure stops the run with an ERROR log
  - [ ] Success: tests pass

**Commit**: `feat: add the grade runner with caps, resume and retry handling`

### Task 37: Report rows and case inclusion (D13)
- [ ] `benchmark/bench_report.py`: `BenchmarkReport` (frozen) assembled from the benchmark's records. Scope is the latest grader identity (older grades counted in one line). Rows key on 420's D6 identity (model, profile, `effort_sent`, `tool_use`, `max_output_tokens`); the alias is the label shown, never a key. Replays under one identity that span more than one prompt identity split into one row per prompt identity with a warning line; a replay with no effort stamp is counted by its failure class, never as an effort `None` row. A case is compared only if every config has all k samples and none is a harness absence (replay or grade); each excluded case is counted under its reason, a pending one as `incomplete`. The model has no field that combines two signals
- [ ] Tests `tests/benchmark/test_bench_report_inclusion.py`: two replays differing only in `tool_use` (or only in `max_output_tokens`) give two rows; two aliases with one identity give one row; a split prompt identity gives two rows and a warning; a missing sample excludes the case as `incomplete`; a harness replay absence and a harness grade absence each exclude the case under their reason; a config absence keeps it (counted as a fail); older-identity grades appear only in the count line; no-effort replay is not an effort-`None` row; a reflection test asserts no field name or type on the model is a composite score
  - [ ] Success: tests pass

### Task 38: Report extension points: case-kind tables and `review_flag` (D13, Provides to 426 and 427)
- [ ] `benchmark/report_tables.py`: a `CaseKindTable` Protocol (the case kind it covers; builds its sections 1–3 from the included cases of that kind and renders them) and a registry keyed by `CaseKind`. `BenchmarkReport` holds one table per kind present among the included cases, and `render_text` and `render_json` iterate the registry. A kind with no registered table raises a named error, logged at ERROR, and is never silently omitted. 426 registers its slice-case table without editing `bench_report.py` or `grade_runner.py`
- [ ] `review_flag(reviewer: ReviewerRef) -> str` in `bench_report.py`, returning exactly `unmeasured reviewer: no recall data for <alias>`. It is the only place that text exists; 427 changes this function alone
- [ ] Tests `tests/benchmark/test_report_tables.py`: a stub kind with a stub table registered inside the test appears in the report text and JSON with no change to report code; an unregistered kind raises and logs ERROR; `review_flag` text for two aliases, and a grep of `src/squadron/benchmark` for the literal `unmeasured reviewer` finds one file
  - [ ] Success: tests pass

### Task 39: Report sections 1–3 (D13)
- [ ] The table registered for fix cases (Task 38) holds these three sections. Objective grade (mean pass fraction, hidden passed over total, regressions, producer-new passed and failed, config absences by kind, n and k; the reference line, never ranked, read with `get_reference_grade` for each included replay's environment digest); paired comparison (every config pair through `compare_pair`); checks and snapshot (mean change from baseline in lint and type totals, `config_edits`, `test_edits`, suppressions, reinstalls; `None` totals shown as "not measured")
- [ ] Tests `tests/benchmark/test_bench_report_grades.py`: hand-computed rows for a fixture of two configs, six cases and k = 2; the paired verdict for a clear and a null pair; a `None` lint total is "not measured" and not 0; a case set below five cases shows `too few cases (n)`; the table is the one registered for the fix kind
  - [ ] Success: tests pass

### Task 40: Report sections 4–7 (D13, D15)
- [ ] Review findings (mean per replay by severity and total, from each record's `ReviewSummary`; per pair the count of cases beyond the case's floor in each direction through `is_within_floor`, "within", and "no floor" for a missing floor; heading carries `review_flag`); cost, turns and time (producer cost, grading cost from `grading_cost_usd`, turns, wall time, mean and total, unpriced counts); absences and exclusions (counts by `AbsenceClass` and kind, case drops, incomplete cases, replays scanned under an older `LEAK_RULES_VERSION`); sample count line when an estimate exists
- [ ] Tests `tests/benchmark/test_bench_report_review.py`: a case whose floor is missing is "no floor", never "within"; a delta equal to the floor spread is beyond it; unpriced counts appear; the leak-version count uses the current constant; the sample-count line states n and k and is absent without an estimate
  - [ ] Success: tests pass

### Task 41: Renderers (D13, API Contracts)
- [ ] `render_text(report)` in the design's section order and layout, and `render_json(report)` (the `BenchmarkReport` model). If `bench_report.py` passes ~300 lines, put the renderers in `bench_report_render.py`
- [ ] Tests: section headings appear in D13's order; the JSON loads back into `BenchmarkReport`; the text carries the unmeasured-reviewer flag; a golden text for the Task 39 fixture
  - [ ] Success: tests pass

**Commit**: `feat: add the benchmark report`

### Task 42: `sq benchmark grade` (API Contracts, D9)
- [ ] `cli/commands/benchmark_grade.py`, registered on the benchmark group: `grade BENCHMARK_ID --max-cost USD [--review-model ALIAS] [--review-cost USD] [--repo PATH …] [--case CASE_ID …] [--retry-harness] [--keep]`. `--repo` defaults to the current directory. Output: the bound, one line per subject (`reference case-… pass`; `case-… <alias> s<n> pass | fail (n regressions) | absent <kind>`), then the summary; with `--keep` print the kept path and that it holds the reference's hidden tests. Exit 0 complete, 2 cap reached, 1 refusal or harness stop. The CLI holds no grading logic
- [ ] Tests `tests/cli/test_benchmark_grade.py`: each refusal exits 1 and names the missing item; the bound prints first; exit 2 on a cap stop; exit 0 on completion; `--keep` prints the notice; `--case` limits the plan
  - [ ] Success: tests pass; `sq benchmark grade --help` lists every option

**Commit**: `feat: add sq benchmark grade`

### Task 43: `sq benchmark report` and the slash-command mirrors (API Contracts)
- [ ] In the same module as `grade`: `report BENCHMARK_ID [--json]`, printing `render_text` or `render_json`. An unknown benchmark id exits 1 naming it; a benchmark with no grades exits 1 saying so
- [ ] `commands/sq/benchmark.md`: add `grade` and `report` with the same arguments and no interpretation, so output is identical to the CLI (the form 424 gave `run` and `replay-show`)
- [ ] Tests `tests/cli/test_benchmark_report.py`: text and JSON output for a stored fixture; unknown id; no grades; `--json` output parses
  - [ ] Success: tests pass; the slash-command file lists both subcommands with the options of the Typer commands (read against `sq benchmark grade --help` and `sq benchmark report --help`) and holds no behavior text beyond running `sq benchmark $ARGUMENTS`

**Commit**: `feat: add sq benchmark report and the grade and report slash commands`

### Task 44: Measured line in `sq benchmark yield` (D15)
- [ ] `benchmark/yield_report.py`: when `latest_estimate(case_set)` exists, add one line beside the analytic separability bound, labelled `measured (bench-…, n=…, k=…)` with n and k from the estimate, showing the pair that needs the most cases at that k (its MDD now and the cases needed); the analytic bound stays, and with no estimate the output is unchanged. Text and JSON both carry it
- [ ] Tests: output with an estimate shows both lines; with two pairs the line shows the one needing more cases; without one it is byte-identical to the existing golden; 422's yield tests pass unchanged
  - [ ] Success: tests pass

**Commit**: `feat: show the measured sample-count estimate in the yield report`

### Task 45: Verification walkthrough (design Verification Walkthrough)
Scratch work goes in new directories under `/tmp`; nothing is pushed. LLM spend and live runs are pre-authorized. Steps need a 422 case set, replays from 424, and `benchmark.grading_review_model` set to an alias that answered yes in `sq benchmark auth-check`; a missing prerequisite no task here can produce is written as `BLOCKED:` with the evidence.
- [ ] Step 1 (small run): at least five qualified cases, two configs, `sq benchmark run … --samples 3`, then `sq benchmark grade <bench-id> --max-cost 10 --review-cost 0.25`
  - [ ] Success: the bound prints first and counts references × floor runs plus replays; reference lines print `pass`; each replay prints pass, fail with its regression count, or an absence kind
- [ ] Steps 2–3: `sq benchmark report <bench-id>`, then `sq benchmark yield`
  - [ ] Success: sections appear in D13's order with n and k; the pair shows an interval and a verdict; the review section carries the unmeasured-reviewer flag; the sample-count line shows MDD and cases needed per k; yield shows `measured (bench-…, n=…, k=…)` beside the analytic bound
- [ ] Steps 4–5: `uv run pytest tests/benchmark/test_grade_one_edits.py -k edits -v`; `sq benchmark replay-show <record-id> --diff` for one graded replay and compare with the reference line
  - [ ] Success: counts show and the pass equals the unedited diff's; the reference passes every hidden test with zero regressions
- [ ] Step 6 (cap and resume): `sq benchmark grade <bench-id> --max-cost 0.30` then `--max-cost 10`
  - [ ] Success: the first stops after the review that crosses $0.30 and exits 2; the second skips graded subjects and finishes
- [ ] Step 7 (inspect a sandbox): `--keep --retry-harness --case <id>` for one case
  - [ ] Success: `test_sqhidden_*.py` sits beside the producer's test files; `git diff <start_sha> -- pyproject.toml` shows only non-tool changes. Delete the kept tree afterwards
- [ ] Any defect the walkthrough found in this slice's code is fixed here with a test and recorded in the DEVLOG; run the gates in Task 46's first bullet before the commit below. If the walkthrough changed no file there is nothing to commit and the marker below is skipped

**Commit**: `fix: correct defects found by the grading walkthrough`

### Task 46: Final validation, design names and DEVLOG
- [ ] Run the gates on the whole branch: `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean, or failures recorded as already failing on the target with the test names; `tests/benchmark/`, `tests/replay/` and the 400 snapshot tests pass unchanged except where D11 and D12 changed call sites
- [ ] Confirm no source file added or changed by this slice exceeds ~300 lines (`wc -l`; likeliest: `grade_one.py`, `python_grading.py`, `bench_report.py`, `grade_models.py`, `grade_store.py`); split by concern where one does
- [ ] Update this slice's design with the names the implementation added (`GradeDeps`, `ReviewBudget`, `GradeCapReached`, `GradeRefusal`, `ReviewFailed`, `TreeReadError`, `GitTreeReader`, `ReviewSummary`, `grade_plan.py`, `grade_budget.py`, any split modules). The design gaps were corrected in Task 1; add any further gap the implementation found
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, Task 31's live result, walkthrough results, measured sample-count estimate from Task 45, next: 426); mark the slice design `status: complete` and tick its slice-plan entry when every task above is checked, dropped items `[x]` with a note
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked

**Commit**: `feat: complete grading and paired report slice`
