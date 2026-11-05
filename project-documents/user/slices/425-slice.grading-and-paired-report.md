---
docType: slice-design
slice: grading-and-paired-report
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [421, 422, 424]
interfaces: [426, 427]
dateCreated: 20261104
dateUpdated: 20261105
status: not_started
---

# Slice Design: Grading and Paired Report

## Overview

This slice grades the replays 424 records and reports configs against each other. It adds three layers:

1. **The grader** (`sq benchmark grade`). For each committed replay it rebuilds the producer's tree in a fresh sandbox (start commit plus the replay's diff) and grades it with its own commands: a fixed code review of the producer's diff, the start commit's tool config restored by section, a reinstall if the producer changed dependencies, the producer's new tests as a separate signal, the start commit's suite minus the superseded and excluded tests, the hidden set injected beside the producer's tests, a 400 snapshot, and counts of edits to existing tests and tool config and of added suppressions. Each case's reference commit is graded the same way first. That gives the reference line, the start-tree baseline and the grading reviewer's noise floor.
2. **Paired statistics.** Each config's samples on a case reduce to one pass fraction. Configs are compared on paired per-case differences with a paired bootstrap interval. The small first run's data also gives a measured sample-count estimate.
3. **The report** (`sq benchmark report`). Objective grade first, then review findings against the floor, then cost, turns and time, all with n. Absences are counted by class. No composite score is computed anywhere.

After this slice, the fix-case path runs end to end: cases (422) → replays (424) → grades and a report (425).

## Value

Developer value. This is the first objective answer to "does config X implement fixes as well as config Z, and at what cost?" The answer comes from tests and tools that give the same result every time, and a pair of configs whose interval spans zero is shown as not distinguishable rather than ranked.

The measured sample-count estimate tells the PM what a benchmark that can separate two configs costs before any large run is paid for. It replaces 422's analytic bound with measured variance.

## Technical Scope

**Included**

- `GradingAdapter` protocol and `PythonGradingAdapter`: hidden-test injection, tool-config restoration by section, the dependency-change test, test-side edit detection and suppression counting.
- The grade pipeline for one subject (replay or reference) and the grade runner: plan, bound, run-level cap, resume, reference-first ordering.
- The fixed grading review: the 300 code-review template under a configured alias, findings normalized the way 400 stores them, and the per-case review noise floor from repeated reference reviews.
- `measure_snapshot`, extracted from 400's `take_snapshot_at`, to measure a sandbox tree without writing a `code_snapshot` record.
- `ContentSidecars`: 424's `DiffSidecars` generalized by kind, with a `snapshots` kind added.
- Record types `ReferenceGrade`, `ImplementationGrade` and `SampleSizeEstimate`.
- Paired per-case reduction, the paired bootstrap and the sample-count estimate (pure functions).
- CLI `sq benchmark grade` and `sq benchmark report`, with matching `/sq:benchmark` subcommands. 422's `sq benchmark yield` shows the measured estimate when one exists.

**Excluded**

- Slice cases, diff normalization for the judge and pairwise judging (426). The grader runs on any case kind. Only `fix` cases exist until 426.
- Reviewer recall (427). Until 427 lands, the review columns are always flagged as coming from an unmeasured reviewer.
- Grading inside `sq benchmark run`. Grading is its own command with its own caps (D9).
- Languages other than Python (Future Work 1).

## Dependencies

### Prerequisites

- **421:** `BenchmarkSandbox`, `EnvironmentIdentity`, `ScrubbedEnvironment` with `CredentialGrant.none()`, `run_suite` with `SuiteSelection.nodes(...)`, `NodeResult`, `FailureKind`, `SuiteRunError`, the `BenchmarkAdapter` registry, `BenchmarkCase`, `CaseSet`, `BenchmarkRecordStore` and `benchmark.suite_timeout_s`.
- **422:** `hidden_tests`, `hidden_fixtures`, `superseded_tests`, `excluded_tests` and `grader_commands` on each case. `FixCaseAdapter.collect` (node ids) and `is_test_side`. `benchmark.target_pass_rate_difference` and `benchmark.planned_samples`, and the yield report this slice extends.
- **424:** `ImplementationReplay` and `BenchmarkRun` records, `ProducerOutcome`, `AbsenceClass`, `LeakScanResult`, `DiffSidecars` (generalized here, D11) and `replays_for(benchmark_id)`.
- **420:** `effort_sent`, `tool_use` and `max_output_tokens` on each replay's `ProducerConfigRef`. Report rows group by 420's D6 identity rule (model, profile, effort sent, `tool_use`, `max_output_tokens`). A replay with no effort stamp counts by its failure class, never as an effort `None` row.
- **400:** snapshot measurement (`metrology/snapshot/take.py`), the lint and type measurements in a `CodeSnapshot`, `normalize_result_categories` (`review/categories.py`) and `CodeReviewFinding`.
- **320:** `FloorStat` and `is_within_floor` (`metrology/audit_delta.py`).
- **300:** the `code` review template and `run_review_with_profile`.

### Interfaces Required

- `run_review_with_profile(template, inputs, profile=…, model=…, no_tools=True, effort=…, alias=…)` returning `ReviewResult`, with `cost_usd` read the way `review/run_cost.py` reads it.
- `resolve_rules_dir` and `load_rules_content` (`review/rules.py`), pointed at the sandbox tree.
- Model alias resolution (`models.toml`).
- `derive_project_id`, to check that each `--repo` matches its cases' `project_id`.
- `ProcessRunner`, for `git apply`, `git show` and `git diff` in the sandbox and the user's checkout.

## Architecture

### Component Structure

```
src/squadron/
  benchmark/
    grading_adapter.py        GradingAdapter protocol, InjectionResult, RestorationResult
    python_grading.py         PythonGradingAdapter: inject, restore, deps_changed, edits, suppressions
    grade_one.py              one subject: sandbox -> apply -> review -> restore -> tests -> snapshot
    grade_review.py           grading review call, normalization, review floor
    grade_runner.py           plan, bound, cap, resume, reference-first ordering
    paired_stats.py           per-case reduction, paired bootstrap, sample-count estimate
    bench_report.py           BenchmarkReport model assembled from records
    registry.py               + grading adapters
  metrology/
    benchmark_models.py       + GraderIdentity, ReviewerRef, GradeAbsence, GradeResult,
                                ReferenceGrade, ImplementationGrade, SampleSizeEstimate
    benchmark_store.py        + grade and estimate records; ContentSidecars
    snapshot/take.py          + measure_snapshot (extracted, no store write)
    audit_delta.py            is_within_floor accepts float deltas
  cli/commands/
    benchmark_grade.py        `sq benchmark grade`, `sq benchmark report` (registered on the benchmark group)
commands/sq/benchmark.md      + grade, report
```

`grade_runner` reaches language details only through the `GradingAdapter` registry and reaches the reviewer only through `grade_review`. `paired_stats` is pure: no I/O, no store, no model. Each module stays under 300 lines.

### Data Flow

**Grading a benchmark:**

```
sq benchmark grade bench-3f9c… --max-cost 15
  load BenchmarkRun, its case set version, its replays (424)
  resolve reviewer (benchmark.grading_review_model or --review-model) → ReviewerRef
  refuse: missing run cap | no reviewer | case project without a --repo | no per-review cost figure
  plan: references to grade = cases with no ReferenceGrade under this grader identity
                              and the environment digest on the case's replays (424)
        replays to grade    = committed, non-harness-absent replays with no ImplementationGrade
  print bound (D9) ─── nothing dispatched before this line
  for case in set:
     if no ReferenceGrade: grade_one(case, subject=reference)  ← baseline + floor
        reference failed its own grade → case marked dropped (harness), its replays skipped
     for replay of case (sample-major, then config):
        if spent ≥ run cap → stop, exit 2
        grade_one(case, subject=replay)
  if ≥ 2 configs and k ≥ 2: write SampleSizeEstimate
  print summary
```

**One subject (`grade_one`):**

```
BenchmarkSandbox(start_sha) → EnvironmentIdentity
   digest ≠ replay's environment digest → absence environment_changed
[reference only] collect start node ids → sidecar; measure start snapshot → sidecar
git apply --binary <diff> ; commit as the benchmark identity          (diff: sidecar, or start..reference)
   apply fails → absence diff_apply_failed
grading review of start..HEAD (no tools, diff injected)               (reference: R runs → floor)
restore tool config by section from start_sha → config_edits
deps_changed? → uv sync --locked (harness env) → reinstalled=true
   reinstall fails → absence producer_env_unresolvable (config)
collect node ids; producer-new = collected − start ids → run_suite(nodes(producer-new))
measure snapshot → sidecar; lint and type totals
restore existing test-side files the producer changed or deleted → test_edits
run_suite(nodes(start ids − superseded − excluded))                    regression
inject hidden set → run_suite(nodes(injected ids))                     hidden
count suppressions added in start..HEAD
write ReferenceGrade | ImplementationGrade
```

### State Management

- **Store records** (persistent): one `reference_grade` per (case, grader identity), one `implementation_grade` per (replay, grader identity), and one `sample_size_estimate` per benchmark (overwritten at each grade run). All are optional sibling payloads on `MetrologyRecord`. No migration.
- **Sidecars** (persistent, content-addressed): `<store>/sidecars/snapshots/<sha256>.json` for snapshots and `<store>/sidecars/nodes/<sha256>.json` for the start tree's node id list. Diffs stay in `sidecars/diffs/` (424).
- **Sandboxes** (transient): 421's directories, one per subject, removed after each grade unless `--keep` is given.
- **Grade lock:** `<benchmark root>/<benchmark_id>.grade.lock`, the same process lock 424 uses. It is separate from the run lock, so grading can follow a partial run while nothing else grades the same benchmark.

## Technical Decisions

### D1 — The grade order inside one sandbox
Status: decided
- The order in the Data Flow is fixed and each step has one reason:
  - **Review first**, on the producer's commit exactly as written, before the grader changes anything.
  - **Tool config restored before any test or check runs**, so pytest, ruff and pyright all run under the start commit's config.
  - **Producer-new tests run before test files are restored.** A producer usually adds its tests to an existing file, and restoring that file removes them.
  - **Snapshot before test restoration**, so it measures the producer's tree, test code included, under the start tool config.
  - **Regression run after test restoration.** It runs the start commit's existing tests, not the producer's edited versions, so editing a test cannot change the grade.
  - **Hidden set last**, injected into the restored tree.
- The tree is rebuilt from `start_sha` plus the stored diff, as 424 states. The replay sandbox is never kept alive for grading.
- The grade sandbox's environment digest must equal the replay's, and for a reference, the digest on the case's replays. Each grade record stores it. A mismatch (a lockfile that resolved differently, a new uv or interpreter) is the harness absence `environment_changed`, because the replay and its grade would not share an environment.

### D2 — Pass, and what counts as a regression
Status: decided
- A subject **passes** when every hidden test passes and the regression run has no failing node. A regression is any selected node whose outcome is `failed`, `error` or `not_run`. `skipped` and `xfailed` are not regressions, because the start tree gives the same answer.
- The regression selection is the start tree's collected node ids minus `superseded_tests` minus `excluded_tests`. It is selected with `nodes(ids)`, never `all_tests()` plus deselect, so producer-added tests never enter it.
- The producer-new signal (passed, failed, count) is reported and never enters the pass.
- `passed` is computed from stored fields by a property, never stored on its own.
- Rejected: weighting hidden and regression results. That is a composite.

### D3 — Hidden-set injection: a sibling module per hidden test file
Status: decided
- For each test file that holds hidden tests, the adapter writes `test_sqhidden_<stem>.py` in the same directory. Its content is:
  1. the import lines the reference added to `conftest.py` (422 D3 permits only added imports and added fixtures),
  2. the reference's whole version of the test file, read with `git show <reference_sha>:<path>` in the user's checkout,
  3. the source of each hidden fixture whose `conftest.py` sits on that file's path (422's `ConftestFixture`).
- Hidden node ids map by replacing the file part (`tests/test_cli.py::TestFix::test_x[a]` → `tests/test_sqhidden_test_cli.py::TestFix::test_x[a]`). Only the mapped hidden ids are selected, so the other tests copied with the file never run.
- Nothing the producer wrote is removed or overwritten. Same directory means relative imports and the directory's `conftest.py` behave as they did at the reference.
- **Clashes** are recorded on the grade, never resolved by overwriting:
  - A producer test with the same name as a hidden test in the original file. Both run, under different module names.
  - A producer fixture with the same name as a hidden fixture. The fixture defined in the injected module shadows the conftest one for that module only, which is pytest's own rule.
  - The sibling filename already exists in the producer's tree. The adapter appends `_2`, `_3`, and records the rename.
- Rejected: splicing hidden functions into the producer's file. It needs source rewriting, and a name clash would then overwrite one side.

### D4 — Tool config restored by section
Status: decided
- In `pyproject.toml`, every `[tool.*]` table comes from the start commit except those in `PACKAGING_TOOL_TABLES = ("uv", "hatch", "setuptools", "poetry", "pdm", "flit", "maturin", "scikit-build")`, defined once in `python_grading.py`. Those decide dependencies and packaging, so they follow the producer, like `[project]` and `[dependency-groups]`.
- Standalone files in `TOOL_CONFIG_FILES = ("ruff.toml", ".ruff.toml", "pyrightconfig.json", "mypy.ini", "pytest.ini", ".coveragerc")` are restored to their start content, or deleted if the start had none.
- The file is read with `tomllib` and written with `tomli-w` (already a dependency). Formatting and comments are lost in the grading copy, which nobody reads. uv compares the lock to `pyproject.toml` by content, so a rewrite with the same dependency tables still passes `--locked`.
- `config_edits` lists every restored table or file whose producer content differed from the start, by name (`tool.ruff`, `pyrightconfig.json`). It is counted and reported, and never changes the grade.

### D5 — Reinstall on dependency change
Status: decided
- `deps_changed` is true when `uv.lock` differs from the start, or when `pyproject.toml` with the restored tool tables removed differs from the start's in content.
- Then the grader runs 421's `uv sync --locked --all-extras --dev` under the harness environment and records `reinstalled=true` and the producer's lockfile hash. The grader identity still names the start environment, as the architecture requires.
- A reinstall that fails is `producer_env_unresolvable`. It is a **config** absence: the producer left a lock that does not resolve, so it counts as a fail for that config.

### D6 — Edits and suppressions are counted, never honored
Status: decided
- `test_edits`: existing test-side files (422's `is_test_side`, judged at the start tree) that the producer modified or deleted. They are restored to start content before the regression run (D1).
- `suppressions_added`: lines added in `start..HEAD` that carry `# noqa` or `# type: ignore` (including `# pyright: ignore`), counted separately for source and test files. Matching is lenient about spacing and case and about any rule list after the marker.
- An added suppression stays in the producer's source. The lint and type totals are therefore measured with it in place, and the count is shown beside them so a reader can see it.

### D7 — The grading review
Status: decided
- **Reviewer:** the alias in `benchmark.grading_review_model`, declared in `config/keys.py` with no default, or `--review-model`. With neither, `grade` refuses and names both. The alias resolves to a `ReviewerRef(alias, model, profile, effort, template_hash, rules_hash)`.
- **Call:** `review_tree_diff(tree, base_sha, reviewer) -> ReviewOutcome` in `grade_review.py`, which 427 imports. It calls `run_review_with_profile` with the `code` template, `inputs={"diff": start_sha, "cwd": tree}`, `no_tools=True`, the alias's effort, and rules from the sandbox tree's own rules directory (the start commit's). With no tools the diff and file contents are injected into the prompt, so the reviewer cannot read outside the sandbox, including the user's checkout, where the reference fix lives.
- **Normalization:** `normalize_result_categories(result)`, then each finding becomes a `CodeReviewFinding` (severity, category, raw category, location, summary from the title). That is the write-side mapping 400's ingest reads back. Findings with a severity outside the review scale are dropped and counted in `unnormalized_count`, as ingest does.
- `run_review_with_profile` has no timeout, so the call runs under `asyncio.wait_for` with `benchmark.review_timeout_s` (declared in `config/keys.py`).
- A review call that raises, times out, or returns verdict `UNKNOWN` with no findings, is the harness absence `review_failed`, logged at ERROR with the error text. A review that ran but found nothing is recorded with zero findings.

### D8 — Reference grade, baseline and review noise floor
Status: decided
- Each case's reference is graded once per grader identity, before any of its replays. The subject is `start..reference_sha`, built with `git diff --binary` in the user's checkout.
- The reference sandbox also records the **baseline**: the start tree's collected node ids (a sidecar) and the start tree's snapshot (a sidecar), both taken before the reference diff is applied. Replay grades read the baseline from the reference grade, so every replay of a case is compared to the same start measurement.
- **Review floor:** the reference review runs `benchmark.review_floor_runs` times (default 3, minimum 2, declared in `config/keys.py`). Its `FloorStat` over total findings uses the same reduction as 320's `_stat`. Any failed floor run fails the reference with `review_failed`, so a floor never comes from fewer runs. A cap hit between floor runs writes no reference record, and a rerun grades it again. That is 320's method applied to this instrument. 320's stored floors measure the audit prompt, not this reviewer, so they are not reused.
- A reference that does not pass its own grade means the grade environment no longer matches qualification. The case is dropped from every config with the harness reason `reference_failed_grade`, and its replays are not graded.

### D9 — Caps, bound and resume for grading
Status: decided
- `grade` requires `--max-cost USD`, a run-level cap for this invocation, refused when missing (as 424 D8 does).
- **Per-review figure** for the bound: the largest observed `review.cost_usd` among stored grades with the same `reviewer_key`, or `--review-cost USD` when the store has none. With neither, `grade` refuses and names the flag. The figure is an estimate. No per-review cap exists, and the bound says so.
- **Bound**, printed before the first review:

```
grade bench-3f9c…  reviewer gpt-review (openai-oauth)  floor runs 3
references 10 × 3 reviews + replays 54 × 1 review = 84 reviews
bound: 84 × $0.18 (max observed) = $15.12, capped at run cap $15.00
       + one review of overshoot $0.18 → at most $15.18
```

- The cap is checked before each review. A review with `cost_usd=None` counts at the per-review figure, and the summary reports how many were unpriced. Hitting it stops grading and keeps every record already written, and the CLI exits 2.
- **Resume** is a lookup by record id (D10). A grade with a harness absence is skipped on rerun unless `--retry-harness` is given, which deletes those grade records first and reports how many, as 424 does.
- Grading is a separate command, not part of `sq benchmark run`. It can run after a partial run, again under a new reviewer, and with its own cap. Rejected: grading inside the replay loop, which would mix two caps and two lock scopes.
- This departs from the architecture, whose run-level cap covers grading. A benchmark's total spend is bounded by the run's cap plus each grade invocation's cap. The architecture's cost section should say so.

### D10 — Grader identity and record ids
Status: decided
- `GraderIdentity` holds `grader_version` (`GRADER_VERSION`, an int constant in `grade_one.py`, bumped whenever any grading step changes), the `ReviewerRef` and `review_floor_runs`. Its `digest` is the sha256 of the canonical JSON of those fields, and it is one value for the whole benchmark. The case's grader commands and test sets are already part of the case id.
- The environment differs per case, so it is not in `GraderIdentity`. Each grade record stores its `environment_digest`, and D1's equality check ties it to the replay's. Together they are the grader identity the architecture names, start environment included.
- Record ids:
  - `refgrade-<case_id[5:17]>-<grader digest[:12]>-<environment digest[:8]>`
  - `implgrade-<replay record id without its prefix>-<grader digest[:8]>`
- A changed reviewer or grader version is a new identity, so its grades sit beside the old ones and never overwrite them. The report reads the latest grader identity only (D13).

### D11 — Content sidecars, generalized
Status: decided
- 424's `DiffSidecars` becomes `ContentSidecars(kind)`, with kinds `diffs` (`.diff`), `snapshots` (`.json`) and `nodes` (`.json`), each under `<store>/sidecars/<kind>/`. `put` and `get` behave as 424 D11 describes: write-once, hash-verified on read, `MetrologyStoreError` on a mismatch. `store.diffs` keeps its name, so 424's call sites do not change.
- Snapshots are sidecars because a `CodeSnapshot` holds per-file maps and can run to hundreds of KB. A grade record keeps only a `SnapshotRef(sha256)` and the totals the report needs.

### D12 — Snapshot of a sandbox tree
Status: decided
- `measure_snapshot(root, environment_root, config, registry, runner, project_id, commit_sha) -> CodeSnapshot` is extracted from `take_snapshot_at`, which then calls it and writes the record as before. The grader calls it with `root = environment_root = tree`, the snapshot config read from the tree, and the case's `project_id`.
- It writes no `code_snapshot` record. A sandbox commit is not in the project's history, and a record keyed on it would show up in 400's project rollups.
- **Check totals** come from the snapshot's lint and type measurements: the sum of `per_file` for each. A check is reported only when the case's `grader_commands` include it (422 D11). If the snapshot's tool identity for that measurement does not name the command's tool (`ruff`, `pyright`), the grade is the harness absence `check_tool_mismatch`. The tools are not run a second time.
- A measurement the snapshot marks absent gives `None` for that total, and the report shows "not measured", never zero.
- `measure_snapshot` runs its tools under the snapshot config's `tool_timeout_s`, as `take_snapshot_at` does. If it raises, the grade is the harness absence `snapshot_failed`.

### D13 — Report contents and order
Status: decided
- **Scope:** one benchmark and its latest grader identity. Grades under older identities are counted in one line and not shown.
- **Rows** are configs keyed by `(alias, model, profile, effort_sent)` (420). An alias whose replays span more than one prompt identity is split into one row per identity, with a warning line. Rows are never silently merged.
- **Case inclusion:** a case enters the comparison only if every config has all k samples recorded and none of them is a harness absence, from the replay (424 D10) or from grading. Each excluded case is counted under its reason. A case still pending is counted as `incomplete`.
- **Sections, in order:**
  1. **Objective grade.** Per config: mean per-case pass fraction, hidden tests passed, regressions, producer-new tests passed and failed, config-caused absences by kind, with n cases and k samples. The reference line shows the reference's pass and is never ranked.
  2. **Paired comparison.** Per pair of configs: mean paired difference, the 95% paired bootstrap interval, and `A ahead`, `B ahead` or `not distinguishable` (D14).
  3. **Checks and snapshot.** Per config: mean change from the baseline in lint and type totals, `config_edits`, `test_edits`, suppressions added, and reinstalls.
  4. **Review findings.** Per config: mean findings per replay, by severity and in total. Per pair: the number of cases where the difference in mean findings is beyond the case's floor in each direction, using `is_within_floor`. A case whose floor is missing is "no floor", never "within". The section heading carries the text `review_flag(reviewer) -> str` returns. In this slice that is always `unmeasured reviewer: no recall data for <alias>`. 427 changes `review_flag` alone to return the reviewer's recall line when it has one.
  5. **Cost, turns and time.** Per config: producer cost, grading cost, turns and wall time, as mean and total, with unpriced counts.
  6. **Absences and exclusions.** Counts by `AbsenceClass` and kind, case drops, incomplete cases, and replays scanned under an older `LEAK_RULES_VERSION` than the current one.
  7. **Sample count** (D15), when an estimate exists.
- No composite is computed. `bench_report.py` has no function that combines two signals into one number, and a test checks that the report model has no such field.

### D14 — Paired bootstrap
Status: decided
- Per case c and config A: `p_A(c)` is passes over k, with config absences counted as fails. Per pair: `d(c) = p_A(c) − p_B(c)`.
- The interval comes from `bootstrap_mean_interval(values, seed)` in `paired_stats.py`, which 427 imports for its recall intervals. It is the percentile 95% interval of the mean of `values` (here `d`) over `BOOTSTRAP_RESAMPLES = 10_000` resamples of cases with replacement. The seed is derived from the benchmark id and the pair, so a report is reproducible. Constants live in `paired_stats.py`.
- An interval that contains zero is `not distinguishable`. With fewer than `MIN_PAIRED_CASES = 5` cases, no interval is computed and the pair shows `too few cases (n)`.
- Rejected: per-sample pooling across cases. Cases differ in difficulty, and the case is the unit of difficulty (architecture design goal).

### D15 — Sample-count estimate
Status: decided
- From graded data with k ≥ 2 samples and at least `MIN_PAIRED_CASES` included cases, for each pair:
  - within-case variance `σ²_w`: the pooled sample variance of per-sample pass outcomes within (case, config), summed over the two configs;
  - between-case variance `σ²_b = max(0, Var_c(d(c)) − σ²_w / k)`;
  - projected `MDD(n, k) = (z₀.₉₇₅ + z₀.₈₀) · √((σ²_b + σ²_w / k) / n)`, using 422's constants;
  - cases needed for `benchmark.target_pass_rate_difference` at each k in `PROJECTED_SAMPLE_COUNTS = (1, 2, 3, 5)`.
- `grade` writes the result as one `SampleSizeEstimate` per benchmark at the end of each grade run. It is a pure function of the grades, so it is recomputed, not appended.
- `sq benchmark yield` (422) shows the latest estimate for a case set beside its analytic bound, labelled `measured (bench-…, n=…, k=…)`. 422's bound stays when no estimate exists.
- The walkthrough's small run is the measurement the architecture asks for before any large run.

### D16 — Absence classes in grading
Status: decided

| `GradeAbsence` | When | `AbsenceClass` |
|---|---|---|
| `producer_env_unresolvable` | reinstall after a dependency change failed | config |
| `environment_failed` | the grade sandbox's environment did not resolve | harness |
| `environment_changed` | its digest differs from the replay's | harness |
| `diff_apply_failed` | the stored diff did not apply to `start_sha` | harness |
| `grader_timeout` | a suite run hit `benchmark.suite_timeout_s` | harness |
| `suite_error` | `SuiteRunError` | harness |
| `review_failed` | D7, D8 | harness |
| `check_tool_mismatch` | D12 | harness |
| `snapshot_failed` | D12 | harness |
| `reference_unreadable` | `git show` or `git diff` of the reference in the user's checkout failed (a missing `reference_sha`) | harness |
| `reference_failed_grade` | D8, on the reference only | harness |

- Replays that are not `committed`, or that carry a harness absence from 424, are not graded. The report takes their class from the replay record.
- Every harness absence is logged at ERROR with the command's stderr tail and recorded with its detail. Nothing falls back to a partial grade.
- A grade killed mid-way writes no record, so a rerun grades that subject again. The grade lock behaves as 424's benchmark lock does, and 421's orphan sweep runs before planning, as in 424.

### Technology Choices

- No new dependencies. `tomllib` and `tomli-w` for section restoration, `random` and `statistics` from the standard library for the bootstrap and the estimate.

### Patterns and Conventions

- `GradeAbsence`, `GradeSubject` (`reference`, `replay`) and `PairVerdict` (`a_ahead`, `b_ahead`, `not_distinguishable`, `too_few_cases`) are `StrEnum`s in `benchmark_models.py`. The report groups by enum values, never by message text.
- Every collaborator of `grade_runner` and `grade_one` is injected (sandbox factory, adapter registry, reviewer, snapshot measurer, store, clock). Tests run no model and no git outside fixtures.
- `GradingAdapter` is its own protocol, registered by `SourceLanguage`, separate from 421's `BenchmarkAdapter` and 422's `FixCaseAdapter`. Slice cases (426) use it without fairness methods.

## Implementation Details

### API Contracts

```python
class GradingAdapter(Protocol):
    language: SourceLanguage
    def restore_tool_config(self, tree: Path, start: TreeReader) -> RestorationResult: ...   # config_edits
    def deps_changed(self, tree: Path, start: TreeReader) -> bool: ...
    def test_side_edits(self, tree: Path, start: TreeReader) -> tuple[str, ...]: ...
    def restore_test_files(self, tree: Path, start: TreeReader, paths: Sequence[str]) -> None: ...
    def inject_hidden(self, tree: Path, case: BenchmarkCase, reference: TreeReader) -> InjectionResult: ...
    def count_suppressions(self, diff: bytes) -> SuppressionCounts: ...
```

`TreeReader` reads a file at a commit (`git show <sha>:<path>` in the user's checkout) and lists paths. `InjectionResult` holds the id mapping, the files written and the clashes.

**`sq benchmark grade BENCHMARK_ID --max-cost USD [--review-model ALIAS] [--review-cost USD] [--repo PATH …] [--case CASE_ID …] [--retry-harness] [--keep]`**

- `--repo` defaults to the current directory. Each case's `project_id` must match one given repository, or `grade` refuses at planning and names the project.
- Output: the bound, one line per subject (`reference case-… pass` or `case-… opus s2 pass | fail (2 regressions) | absent review_failed`), then a summary.
- Exit codes: 0 complete, 2 run cap reached, 1 refusal or harness stop.

**`sq benchmark report BENCHMARK_ID [--json]`**

```
benchmark bench-3f9c…  set fixes v2  grader 7c1e… (gpt-review, floor runs 3)
cases: 12 in set · 10 compared · 1 dropped (harness: review_failed) · 1 incomplete

objective grade                     n   k  pass frac  hidden   regr  new tests  config absences
  opus  (sdk, effort high)         10   3    0.73     22/30     4   41/44      cost_cap 1
  sol   (openai-oauth, effort med) 10   3    0.60     18/30     7   30/38      no_commit 2
  reference                        10   –    1.00     10/10     0    –

paired (95% bootstrap over cases)
  opus − sol   +0.13  [−0.03, +0.30]  not distinguishable

checks vs baseline                  lint Δ  types Δ  config edits  test edits  suppressions  reinstalls
  …

review findings (unmeasured reviewer: no recall data for gpt-review)
  …   opus vs sol: beyond floor on 3 cases (opus more 1, sol more 2), within 6, no floor 1

cost / turns / time                 producer $   grading $   turns   wall
  …

sample count (measured, k=3, n=10): opus vs sol  MDD 0.24 at n=10 · need 15 cases at k=3, 21 at k=2
```

`/sq:benchmark` mirrors `grade` and `report` with the same arguments and output. `--json` emits the `BenchmarkReport` model.

### Database / Storage Schema

```python
class ReviewerRef(BaseModel, frozen=True):
    alias: str
    model: str
    profile: str
    effort: str | None
    template_hash: str
    rules_hash: str | None
    reviewer_key: str                          # derived: sha256 of model, profile, effort, template_hash

class GraderIdentity(BaseModel, frozen=True):
    grader_version: int
    reviewer: ReviewerRef
    review_floor_runs: int
    digest: str                                # derived, validated

class ReviewOutcome(BaseModel, frozen=True):
    findings: tuple[CodeReviewFinding, ...]
    unnormalized_count: int
    cost_usd: float | None

class GradeResult(BaseModel, frozen=True):
    hidden: tuple[NodeResult, ...]             # by injected id
    hidden_id_map: tuple[tuple[str, str], ...]
    injection_clashes: tuple[str, ...]
    regression_selected: int
    regression_failures: tuple[str, ...]       # ≤ 50 node ids
    regression_failure_count: int
    producer_new_passed: int
    producer_new_failed: int
    config_edits: tuple[str, ...]
    test_edits: tuple[str, ...]
    suppressions: SuppressionCounts            # noqa / type_ignore × source / test
    reinstalled: bool
    lockfile_sha256: str
    snapshot: SnapshotRef
    lint_total: int | None
    type_total: int | None
    reviews: tuple[ReviewOutcome, ...]         # 1 for a replay, review_floor_runs for a reference

class ReferenceGrade(BaseModel, frozen=True):
    case_id: str
    grader: GraderIdentity
    environment_digest: str
    result: GradeResult | None
    absence: GradeAbsence | None
    detail: str | None
    baseline_nodes: str                        # sidecar sha256
    baseline_snapshot: SnapshotRef
    baseline_lint_total: int | None
    baseline_type_total: int | None
    review_floor: FloorStat | None
    grading_cost_usd: float | None
    wall_seconds: float
    created_at: datetime

class ImplementationGrade(BaseModel, frozen=True):
    replay_id: str
    benchmark_id: str
    case_id: str
    grader: GraderIdentity
    environment_digest: str
    result: GradeResult | None                 # None when absent
    absence: GradeAbsence | None
    absence_class: AbsenceClass | None
    detail: str | None
    grading_cost_usd: float | None
    wall_seconds: float
    created_at: datetime

class SampleSizeEstimate(BaseModel, frozen=True):
    benchmark_id: str
    case_set: str
    case_set_version: int
    grader_digest: str
    n_cases: int
    samples: int
    pairs: tuple[PairEstimate, ...]            # σ²_w, σ²_b, MDD now, cases needed per k
    created_at: datetime
```

`MetrologyRecord` gains `reference_grade`, `implementation_grade` and `sample_size_estimate`, with `RECORD_TYPE_*` constants. `BenchmarkRecordStore` gains `write_reference_grade`, `get_reference_grade(case_id, grader_digest, environment_digest)`, `write_grade`, `grades_for(benchmark_id)`, `delete_grades(ids)` (for `--retry-harness` only), `write_estimate`, `latest_estimate(case_set)`, and `snapshots` and `nodes` sidecar attributes. A grade record stays under 16 KB: node lists and snapshots are sidecars, failures are capped at 50 ids.

## Integration Points

### Provides to Other Slices

- **426:** `grade_one` and `GradingAdapter` for slice cases, which have an empty hidden set (the hidden step selects nothing and the pass reduces to no regressions). The report's case-kind tables: 426 adds a slice-case table beside the fix-case one.
- **427:** `ReviewerRef` with `reviewer_key`, `review_tree_diff` (D7), `bootstrap_mean_interval` (D14), and the single function `review_flag(reviewer) -> str` in `bench_report.py`, which 427 changes to return the recall line from its `latest_recall_for(reviewer_key)`. 427 imports these and defines no copies.
- **422:** `latest_estimate(case_set)` for the yield report's measured line.

### Consumes from Other Slices

- **421:** sandbox, environment identity and suite runner, used as specified. Suite runs use `CredentialGrant.none()`.
- **422:** case test sets and grader commands, `collect` and `is_test_side`, and the target difference. The yield report's rendering gains one line (D15). No 422 decision changes.
- **424:** replay records and diff sidecars. `DiffSidecars` is generalized without changing 424's call sites (D11). 424 says "425 extends the bound with grading costs". Grading is a separate command with its own bound instead (D9), so that sentence in 424 should change.
- **400:** `take_snapshot_at` keeps its behavior after `measure_snapshot` is extracted, and its tests pass unchanged.
- **320:** `is_within_floor` takes `float`. Existing int callers are unaffected.

## Success Criteria

### Functional Requirements

- Each case's reference, graded like a replay, passes. A test case where it does not records `reference_failed_grade`, and that case's replays are not graded.
- A replay that edits an existing test, adds `# noqa` or `# type: ignore`, or changes a `[tool.*]` table is graded, the edit is counted under `test_edits`, `suppressions` or `config_edits`, and its pass is the same as the same replay without the edit.
- A `[tool.uv]` or `[project].dependencies` change triggers a reinstall that is recorded. A lock that does not resolve records `producer_env_unresolvable` as a config absence.
- Superseded and excluded tests are never selected in the regression run. Producer-added tests are never selected in it.
- Hidden tests are injected without removing any producer file. A producer test or fixture with a hidden test's name, and an existing sibling filename, are each recorded as a clash, and both sides run.
- Config-caused absences count as fails for that config. Harness-caused absences, from the replay or the grade, drop the case from every config. The report counts both kinds by kind.
- Two configs on the same cases get a paired bootstrap interval. A pair whose interval contains zero shows `not distinguishable`. Fewer than five cases shows `too few cases`.
- The report has no composite score, and the report model has no field that combines signals.
- After a graded run with k ≥ 2, a `SampleSizeEstimate` is written and shown in `sq benchmark report` and in `sq benchmark yield`.
- `grade` without `--max-cost`, without a reviewer, or without a per-review figure refuses and names what is missing. The bound prints before the first review. Hitting the cap exits 2 and keeps every record. A rerun skips graded subjects.

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean.
- `paired_stats` has tests against hand-computed values: a pair with a known difference, a pair with no difference whose interval contains zero, the `σ²_b` floor at zero, and reproducibility under the same seed.
- Injection and restoration have fixture-tree tests built from a real squadron fix commit's test file (a class-nested, parametrized node id; a hidden conftest fixture; a clash; a `[tool.ruff]` edit beside a `[project]` dependency change), not only synthetic files.
- Every `GradeAbsence` in D16 is produced by a test double for its condition, with its class.
- `tests/benchmark/`, `tests/replay/` and the 400 snapshot tests pass unchanged except where D11 and D12 refactor call sites.

### Integration Requirements

- 426 can grade a slice case through `grade_one` with an empty hidden set and add its report table without editing `grade_runner.py`.
- 427 can remove the unmeasured-reviewer flag by changing `review_flag` alone.

### Verification Walkthrough

These are draft commands. `sq benchmark grade` and `sq benchmark report` do not exist until this slice is implemented. The steps need a case set from 422 (`sq benchmark fix-cases build --set fixes`), replays from 424, and `benchmark.grading_review_model` set to an alias that answered yes in `sq benchmark auth-check`.

1. **Small run for the sample-count measurement.** Pick at least five qualified cases and two configs:
   ```bash
   sq benchmark run --set fixes --model opus --model sol --samples 3 \
     --max-cost 40 --max-cost-per-replay 1.50 --case <id1> … --case <id5>
   sq benchmark grade <bench-id> --max-cost 10 --review-cost 0.25
   ```
   The bound prints first and counts five references × floor runs plus up to 30 replays. Reference lines print `pass`. Each replay prints pass, fail with the regression count, or an absence kind.

2. **The report.**
   ```bash
   sq benchmark report <bench-id>
   ```
   Sections appear in D13's order. Each config row shows n and k. The pair shows an interval and a verdict. The review section carries the unmeasured-reviewer flag. The sample-count line shows the measured MDD and the cases needed at each k.

3. **The yield report reads the measurement.**
   ```bash
   sq benchmark yield
   ```
   The separability line shows the analytic bound and, beside it, `measured (bench-…, n=5, k=3)`.

4. **Edits are counted, not honored.** Run `uv run pytest tests/benchmark/test_grade_one.py -k edits -v`. Its fixtures replay a diff that weakens an existing assertion, adds `# type: ignore` and loosens `[tool.pyright]`. The grade shows each count, and the pass equals the unedited diff's.

5. **Reference grade.** `sq benchmark replay-show <record-id> --diff` for one graded replay. Then compare its grade with the reference line in the report: the reference passes every hidden test with zero regressions.

6. **Cap and resume.** `sq benchmark grade <bench-id> --max-cost 0.30` stops after the review that crosses $0.30 and exits 2. Rerunning with `--max-cost 10` skips graded subjects and finishes.

7. **Inspecting a grade sandbox.** Rerun step 1's grade for one case with `--keep --retry-harness --case <id>`. In the kept tree, `test_sqhidden_*.py` sits beside the producer's test files, and `git diff <start_sha> -- pyproject.toml` shows only the producer's non-tool changes.

## Risk Assessment

### Technical Risks

- **Injection by sibling module.** A reference test file that imports itself by module name, or that relies on module-level state shared with other tests in the same file, may behave differently under a new module name.
- **Measured variance from a small run.** Five cases at k = 3 gives a coarse `σ²_b`. The estimate can be off by a large factor.

### Mitigation Strategies

- The reference grade runs the injected module first. A hidden test that passed qualification but fails as injected fails the reference, and the case is dropped with `reference_failed_grade`, never charged to a config. The drop count shows whether injection needs a different method.
- The estimate line states n and k, and it is recomputed on every grade run, so it tightens as cases are added.

## Implementation Notes

### Development Approach

1. `ContentSidecars` (D11), `measure_snapshot` (D12) and `is_within_floor(float)`, with the existing tests passing.
2. Records, grader identity and store methods.
3. `PythonGradingAdapter`: restoration, deps-changed, test edits, suppressions and injection, against fixture trees taken from squadron history.
4. `grade_review`: the reviewer call, normalization and the floor reduction, with a reviewer test double.
5. `grade_one` with injected doubles for every step and every absence in D16. Then a live grade of one squadron reference with `--keep`.
6. `paired_stats` (D14, D15), pure, with hand-computed tests.
7. `grade_runner`: plan, bound, cap, lock, resume and `--retry-harness`.
8. `bench_report`, the CLI, the slash command and the yield line. Run walkthrough steps 1–7 on squadron.

Effort: 4/5.

### Special Considerations

- The grading review sees the producer's diff with no tools. That keeps the reviewer out of the user's checkout. It also means the reviewer cannot open unchanged files for context beyond what the template injects. Every config is reviewed the same way, so the comparison stays fair.
- Suite runs and the snapshot run in the scrubbed environment with no credentials. The install and reinstall run in the harness environment (421 D5).
- `--keep` on `grade` leaves a tree with the reference's hidden tests in it. The CLI prints that beside the kept path.
