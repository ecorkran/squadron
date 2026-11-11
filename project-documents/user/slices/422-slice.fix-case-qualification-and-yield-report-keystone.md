---
docType: slice-design
slice: fix-case-qualification-and-yield-report-keystone
project: squadron
parent: user/architecture/420-slices.model-benchmark.md
dependencies: [421, 420]
interfaces: [424, 425, 426]
dateCreated: 20261104
dateUpdated: 20261108
status: complete
---

# Slice Design: Fix Case Qualification and Yield Report (keystone)

## Overview

This slice turns a project's fix history into qualified fix cases and reports how many it got. It does four things:

1. **Discovery.** Every commit whose message closes an issue becomes a candidate. Each candidate ends as a case or as a rejection with a reason.
2. **Case construction.** The issue text is frozen into the case. The reference diff is sorted into per-node hidden and superseded test sets.
3. **Qualification.** The Python fairness rule runs on each hidden test: test-first at the parent, packaging boundary only, no patching of project code. Repeated runs put flaky tests on the case's exclusion list. Every result is written as a qualification record keyed on environment identity.
4. **The yield report.** It shows qualified and rejected counts per project, broken down by reason, and says whether the qualified count can separate two configs.

Nothing here dispatches a producer or grades a replay. Those are 423–425.

## Value

This is the first measured answer to "can this project be benchmarked on fixes, and how many cases does it give?" That answer sets the rest of the initiative's order. If the qualified count can separate two configs, 423 → 424 → 425 stands. If it cannot, fix cases are pooled across cf projects, or 426's case building moves ahead of 424.

The slice also leaves the qualified fix cases and a versioned case set in the store, ready for 424 to replay.

## Technical Scope

**Included**

- Candidate discovery from git history, with a closed set of rejection reasons.
- Issue fetching through `CodeHost` (new `get_issue`) and freezing the issue text.
- Test collection with per-node closure digests, and sorting into hidden and superseded sets, plus added `conftest.py` fixtures.
- The Python fairness checks: test-first through 421's `FailureKind`, the packaging-boundary trace, and patch detection.
- Repeated qualification, flaky and failing-at-reference exclusions, and grader commands for the case.
- The `FixQualification` record type, with reuse and re-qualification by environment identity and rule version.
- Building the case set from the qualified cases.
- The yield report and its separability answer.
- CLI `sq benchmark fix-cases build|show` and `sq benchmark yield`, and the `/sq:benchmark` slash command (`commands/sq/benchmark.md`), created here with the same subcommands.

**Excluded**

- Injecting hidden tests into a producer's tree (425). This slice only overlays whole reference files onto the parent sandbox, where no producer output exists.
- The leak scan, the producer-only run mode, and replays (424).
- The paired bootstrap over real replay results (425). The yield report uses an analytic bound (D12).
- Adapters for other languages (Future Work 1). A project with no adapter yields zero fix cases and gets one reason for all of them. Choosing the adapters by project language, instead of the hard-coded Python in `case_build` and the benchmark commands, is deferred to #314.
- Slice cases (426).

## Dependencies

### Prerequisites

- **421:** `BenchmarkCase`, `CaseSet`, `BenchmarkRecordStore`, `BenchmarkSandbox`, `EnvironmentIdentity`, `ScrubbedEnvironment`, `adapter_for`, and `run_suite` with `FailureKind` and `SuiteSelection.deselect`.
- **420:** nothing is read directly. It is a prerequisite of 421.
- **External:** `gh` with access to the project's issue host, for issue fetching only. It runs in the harness environment, never in a sandbox.

### Interfaces Required

- `CodeHost` / `GitHubCli` (`codehost/protocol.py`, `codehost/github_cli.py`). This slice adds `get_issue`.
- `list_remotes` and `RepositoryLocator` (`codehost/remotes.py`), to resolve which repository a bare `#n` refers to.
- `ProjectId` and `derive_project_id` (`metrology/identity.py`).
- `ProcessRunner`, for `git log` and `git show` in the user's checkout.
- Config key declarations (`config/keys.py`).

## Architecture

### Component Structure

```
src/squadron/
  codehost/
    protocol.py, github_cli.py   + get_issue(locator, number) -> IssueSnapshot
    models.py                    + IssueSnapshot, IssueComment
    errors.py                    + IssueNotFoundError, ReferenceIsPullRequestError
  metrology/
    benchmark_models.py          + FixQualification, CandidateRejection, TestRejection,
                                   HiddenTestVerdict, HiddenTestVerdictKind, QualificationOutcome
    benchmark_store.py           + write/get/list for fix_qualification records
  benchmark/
    fix_discovery.py             git history -> FixCandidate list, discovery rejections
    issue_freeze.py              IssueSnapshot + optional cutoff -> issue text or rejection
    diff_classify.py             name-status diff -> DiffClassification or DiffRejection,
                                 before any sandbox exists (D3, D4)
    test_sets.py                 two collections -> hidden / superseded / added fixtures
    fairness.py                  FixCaseAdapter protocol, FairnessVerdict (the one verdict
                                 type), rule version, BoundaryUndecidable, CollectionFailed,
                                 HarnessFailure
    python_fairness.py           PythonFixCaseAdapter: collect, overlay, boundary, trace
    python_boundary.py, python_tree_files.py   adapter helpers (resolver run; tree files)
    pytest_trace/                trace plugin source (stdlib + pytest), package data
    trace_verdict.py             pure judge_trace(facts, allowed) -> FairnessVerdict (D6, D7)
    file_states.py               the three file states of one parent sandbox (D4)
    test_first.py                parent-plus-overlay judgement of a node's result (D5)
    qualify.py                   qualify_candidate and qualification_for (D9, D10)
    qualify_types.py             QualifyDeps, QualifyResult, record_outcome
    qualify_stages.py            pre-sandbox stages (discovery to diff classification)
    qualify_sandbox.py           qualify_in_sandbox: the sandbox stages through test-first
    qualify_survivors.py         repeated reference runs, exclusions, case construction
    build_errors.py              BuildHalted: the build cannot continue (logged at ERROR)
    case_build.py                orchestrates discovery -> qualify -> cases -> case set
    yield_report.py              aggregation and rendering
    separability.py              minimum detectable difference (D12)
  cli/commands/benchmark_fix_cases.py   + fix-cases build, fix-cases show, yield
commands/sq/benchmark.md         new: the same subcommands
```

`fairness.py` holds the protocol and the rule version. `PythonFixCaseAdapter` is registered by `SourceLanguage` in 421's `benchmark/registry.py`, and `case_build.py` and `qualify.py` reach it only through that registry (D13).

### Data Flow

For one repository (`--repo`, default the current directory):

1. **Discover** (`fix_discovery`). `git log --format=<sha, parents, committer date, body>` over every commit reachable from `HEAD`. A commit is a candidate when its message contains a GitHub closing keyword (D1). Discovery-stage rejections are written straight to the store.
2. **Freeze issue text** (`issue_freeze`). `CodeHost.get_issue` returns the title, body, comments and edit timestamps. The frozen text is built from content that existed before the fix commit's committer date (D2).
3. **Classify the diff** (`diff_classify`). `git diff --name-status parent..commit`, with file text read from git: no tree exists yet. Test-side files are found with the adapter's rule (D3). A candidate with no test-side change is rejected. Non-Python test-side changes, support changes beyond added fixtures, and lockfile changes are rejected as well.
4. **Sandbox.** One `BenchmarkSandbox` is built at the parent. Its `EnvironmentIdentity` is the record key (D10). An existing record with the same key and rule version is reused, and the candidate is skipped.
5. **Parent state.** Collect through the trace plugin's collect mode, then run the boundary resolver under the sandbox's interpreter. It prints the allowed `(module, qualname)` set (D6).
6. **Reference state** (D4). Collect again. `test_sets` produces the hidden candidates, the superseded set and the added fixtures (D3). One trace run on the hidden candidates (D6, D7).
7. **Parent plus overlay** (D4). The surviving hidden tests run `benchmark.qualification_repeats` test-first runs (D5).
8. **Reference state again.** The full suite runs `benchmark.qualification_repeats` times. Disagreeing nodes and nodes that fail every run go on exclusion lists (D9).
9. **Write.** A `BenchmarkCase` is written when at least one hidden test survives (D8). Every outcome writes a `FixQualification`.
10. **Case set.** `write_case_set(--set, qualified case ids)`.
11. **Report.** `yield_report` reads `FixQualification` records for the given projects and renders them (D12).

### State Management

- **Store records** (persistent): `fix_qualification` envelopes, an optional sibling payload on `MetrologyRecord` added as 421 D3 describes. `BenchmarkCase` and `CaseSet` are 421's.
- **Sandboxes** (transient): one per candidate under 421's benchmark root, removed after each candidate unless `--keep` is given.
- **Resumability:** the build is restartable without extra state. A candidate whose record matches the key and rule version is skipped. A `harness_error` record is never reused.

## Technical Decisions

### D1 — Discovery: every closing commit is a candidate
Status: decided
- A candidate is any commit reachable from `HEAD` whose message matches a GitHub closing keyword (`close[sd]?`, `fix(e[sd])?`, `resolve[sd]?`, case-insensitive), followed by `#n` or `owner/repo#n`. A title suffix like `(#283)` alone is not a closing reference, because it often names a pull request.
- A closing commit that adds no test is still a candidate. It is rejected with `no_test_change`, so the yield report shows how much fix history exists without tests.
- Discovery-stage rejections (`CandidateRejection`):
  - `merge_commit`: the commit has more than one parent, so its diff does not isolate the fix.
  - `multiple_closing_commits`: more than one commit closes the same issue (for example #216, closed by 29850399 and 38060838). Splicing a range is rejected for now. The count shows whether it is worth adding.
  - `multiple_issues_closed`: the commit closes more than one distinct issue. The same issue named twice counts once.
  - `no_issue_host`: no remote resolves to a host `CodeHost` serves.
  - `issue_not_found`, or `reference_is_pull_request`.
- Rejected: building candidates only from commits that touch `tests/`. That would silently drop the closing commits without tests.

### D2 — Frozen issue text
Status: decided
- `CodeHost.get_issue(locator, number) -> IssueSnapshot` makes one GraphQL query through `issueOrPullRequest`. It returns the title, body, `createdAt`, `lastEditedAt`, and comments with author, body, `createdAt` and `lastEditedAt`. It is fetched once, in the harness environment, when the candidate is built.
- The renderer takes an optional cutoff. With no cutoff (423's live fix) it renders the title, the body and every comment, and runs no edited-after-fix check. The cutoff filter and `issue_edited_after_fix` below apply only when a cutoff is given.
- For a case, the cutoff is the fix commit's committer date. The frozen text is the title, the body, and every comment created before the cutoff, in order. It is rendered as markdown with a heading for each comment (author and date). This string is the case's `task_text`.
- If the body, or an included comment, was edited after the cutoff, the candidate is rejected with `issue_edited_after_fix`. The text as it stood at the cutoff cannot be recovered without the edit history, and today's version may describe the fix. If this reason dominates the yield, recovering text from `userContentEdits` is the follow-up.
- A later comment cannot change a case: `task_text` is part of the case id, and the case is never fetched again.

### D3 — Test sets from per-node closure digests
Status: decided
- **Test-side files** are the files under the parent's `[tool.pytest.ini_options] testpaths`. When that is not set, they are `test_*.py`, `*_test.py`, `conftest.py`, and anything under a `tests/` or `test/` directory.
- **Collect mode.** The trace plugin runs `pytest --collect-only` with the plugin enabled. For each item it records the node id and a **closure digest**: sha256 over the test function's source (decorators and parametrize ids included), plus the source of every test-side definition the test reaches. That covers fixtures (from pytest's resolved fixture definitions) and the module-level functions, classes and constants named in the code objects of the test and its fixtures, recursively within test-side code.
- **Sorting:**
  - A node only at the reference → hidden candidate.
  - A node at both with different digests → hidden candidate and superseded.
  - A node only at the parent → superseded.
  - A node at both with equal digests → unchanged regression test.
- **Hidden fixtures:** top-level `pytest.fixture` functions in a `conftest.py` that exist at the reference but not at the parent, and that some hidden candidate's closure reaches. They are recorded as 421's `ConftestFixture`.
- **Rejections:**
  - `test_data_changed`: a non-Python test-side file was added or changed. No data flow can be traced to it.
  - `modifies_test_support`: a `conftest.py` change other than added fixtures and added imports. A changed fixture would change existing tests in ways the digests attribute to every test that uses it, and 425 injects only added fixtures.
  - `collection_failed`: a test-side file the reference touched fails collection at the parent or at the reference.
- Rejected: file-level sets. A fix usually adds one function to an existing file.

### D4 — One sandbox, three file states
Status: decided
- Every check runs in the parent sandbox, in the environment the replays use. The harness switches it between three states by rewriting whole files the diff touched, with content from `git show <sha>:<path>` in the user's checkout:
  - **parent**: as built.
  - **reference**: the reference's version of every file the diff added or changed, and the deleted files removed.
  - **parent plus overlay**: parent code with the reference's test-side files. This is "reference tests, parent code", for the test-first check.
- Files are rewritten after the environment resolves, so the `EnvironmentIdentity` is unchanged. A fix that changes the lockfile would run in an environment it was not written for, so it is rejected at diff classification with `changes_lockfile`.
- An overlay is not 425's injection. It replaces whole files in a tree that has no producer work to keep. Hidden tests run on it by node id.

### D5 — Test-first check
Status: decided
- Each hidden candidate runs at parent plus overlay through `run_suite(nodes(ids))`. Results map from 421's `FailureKind` as follows:
  - `assertion_failure`, `project_exception` → test-first holds.
  - `passed` → `passes_at_parent`.
  - `missing_symbol`, `collection_error` → `uses_symbol_added_by_fix`.
  - `other_exception`, or `error` in setup or teardown → `undecidable_failure_at_parent`.
  - `skipped`, `xfailed`, `xpassed`, `not_run` → `undecidable_failure_at_parent`.
- A timeout or `SuiteRunError` records `harness_error` for the candidate. It is not a test verdict.

### D6 — Packaging boundary: allowed set at the parent, trace at the reference
Status: decided
- **Allowed set.** A resolver script runs under the parent's `.venv/bin/python` in the scrubbed environment. It reads `[project].name` and `[project.scripts]` / `[project.gui-scripts]` from the parent's `pyproject.toml`, and it finds the distribution's top-level packages through `importlib.metadata.packages_distributions()`. It imports each package. Allowed entries are:
  - each script target `module:attr`, and
  - each name in a top-level package's `__all__`, resolved to its defining `(obj.__module__, obj.__qualname__)`.
  Only top-level `__all__` counts. Internal modules often define `__all__` for star-import hygiene, which is not a packaging declaration.
- An empty allowed set rejects the candidate with `no_packaging_boundary`. A resolver import failure rejects it with `boundary_undecidable`.
- **Trace.** At the reference, the trace plugin runs the hidden candidates (where they pass, so the whole path executes) and records two things:
  - **Static references.** It follows globals named by the test function, its fixtures and test-side helpers (`co_names`, recursing through nested code objects), and resolves them in the function's `__globals__`. Every project module, class or function reached is recorded.
  - **Dynamic crossings.** A `sys.setprofile` hook records each call whose immediate caller frame is test-side code and whose callee frame is project source (421 D11's definition), as `(module, co_qualname)`.
- **Verdict:**
  - Each static reference and each crossing into a module-level function or a class constructor must be in the allowed set. Otherwise `reaches_past_boundary`, naming the symbol.
  - A crossing into a method (a `co_qualname` with a class prefix) is allowed. An instance can only come from an allowed constructor or function, and any direct reference to a non-exported class is already caught statically.
  - A static reference to a project module object, which might be read through any attribute, is `boundary_undecidable`.
  - An interpreter without `co_qualname` (before 3.11) is `boundary_undecidable`.
- **Known gaps** (recorded so the trace never claims more than it sees): reading a non-callable project constant through an allowed module, and module-level instances such as a Typer app, whose type is defined outside the project. Calls into project code made by dependencies (Typer invoking a command callback) are not crossings. That is what lets "drive the CLI" pass.
- The resolver checks names as they stood at the parent. If the reference moved or renamed a definition, it fails the check, which errs toward exclusion.
- Rejected: a static-only AST check, because it cannot follow fixtures and helpers to their real targets. Also rejected: perturbation, which the architecture already rejected.
- **Reference and crossing kinds** (the trace plugin's output; `trace_verdict.py` judges them):
  - A **reference** is `(kind, module, qualname)` with `kind` one of `module`, `class` or `function`. A `module` reference is a project module object read by a test, and it is `boundary_undecidable`. `class` and `function` references must be in the allowed set.
  - A **crossing** is `(module, co_qualname, kind)`, with `module` the callee frame's `f_globals["__name__"]` (the same form as the resolver's `obj.__module__`) and `kind` one of `function`, `constructor` or `method`.
  - **Constructor rule.** A crossing is a `constructor` when the callee's `co_name` is `__init__` or `__new__`. It is judged by its class: the `__init__`/`__new__` qualname minus its last component must be in the allowed set. A `function` crossing is judged by its own qualname. `method` crossings are not judged (see the Verdict list above). A function nested inside another function (`<locals>` before its name) has no class prefix, so it is a `function`.

### D7 — No patching project code
Status: decided
- During the reference trace run, the trace plugin wraps `unittest.mock._patch.__enter__` / `start` (which covers `patch`, `patch.object` and `patch.dict`), plus `pytest.MonkeyPatch.setattr`, `delattr`, `setitem` and `delitem`. For each, it resolves the owner object being modified.
- A patch whose owner is a project module, a project class, or an instance of a project class is `patches_project_code`. This applies even when the replaced value comes from a dependency (`patch("pkg.mod.run")` after `from subprocess import run`), because the patch site still ties the test to the module where the fix put its call.
- Patching anything owned outside the project (`subprocess.run`, `os.environ`, SDK classes) is allowed.
- `ENVIRONMENT_ISOLATION_PATCH_TARGETS` exempts project targets that only keep the checkout's `.env` out of tests (today `squadron.cli.app._load_env_file`). It is hard-coded in `trace_verdict.py`; moving it to per-project configuration is deferred to #315.
- A target string that does not resolve at the reference makes the test `boundary_undecidable`. The same failure at the parent is already `uses_symbol_added_by_fix` (D5).

### D8 — Verdicts are per test; a case needs one surviving hidden test
Status: decided
- Every hidden candidate gets a `HiddenTestVerdict`: qualified, or one `TestRejection`. The case's `hidden_tests` are the qualified ones. If none qualify, the candidate is rejected with `no_qualifying_hidden_test`, and its per-test reasons stay in the record.
- A changed test that fails a check is still superseded: its old version leaves the regression count. Its new version is simply not hidden.
- Rejected: all-or-nothing per case. A fix that adds one fair test and one test with a patch would be lost for no reason.

### D9 — Check order and repeats
Status: decided
- Checks run from cheapest to most expensive, and each later step runs only on what survived:
  1. discovery and issue freeze (no sandbox)
  2. diff classification
  3. environment resolution (one sandbox)
  4. collection and the boundary resolver
  5. one trace run of the hidden candidates
  6. the test-first runs of the hidden survivors
  7. the full-suite repeats
- Repeats: `benchmark.qualification_repeats` (default 3, declared in `config/keys.py`). The hidden survivors run that many times at the parent plus overlay, and the full suite runs that many times at the reference.
- Outcomes from the repeats:
  - A hidden test whose outcome differs across parent runs or across reference runs is rejected as `flaky`.
  - A hidden test that fails at the reference in every run is rejected as `fails_at_reference`.
  - A non-hidden node whose outcome differs across reference runs goes on `excluded_tests` (reason `flaky` in the record).
  - A non-hidden node that fails every reference run goes on `excluded_tests` (reason `fails_at_reference`). These are typically tests that read the developer's environment, and they would charge every config alike.
- `excluded_tests` is sorted and is part of the case id (421 D1). A different flaky set makes a different case.

### D10 — Qualification records: key, reuse and re-qualification
Status: decided
- `FixQualification` holds:
  - `project_id`, `commit_sha`, `parent_sha`, `issue_ref`
  - `rule_version` (`FAIRNESS_RULE_VERSION`, an int constant in `fairness.py`, bumped whenever any check changes)
  - `environment`: the sandbox's full `EnvironmentIdentity`, or `None` when it was rejected before the sandbox
  - `repeats`
  - `outcome`: `qualified` with a `case_id`, or `rejected`, `harness_error`
  - `rejection` and `detail`
  - `hidden_verdicts` and `excluded_with_reasons`
  - `created_at`
- The record id is `fixqual-<sha256(project_id.value)[:12]>-<commit[:12]>-<env digest[:12] or "pre">`. A newer result under the same key overwrites, so the store holds the latest per environment.
- Reuse: `build` skips a candidate whose record exists for the current environment digest and `rule_version`, unless the outcome is `harness_error`. The digest includes the interpreter version, so it is known only after the install. A rebuild therefore still builds one sandbox per candidate that reaches step 4, and skips collection and every test run.
- Re-qualification for 424: `qualification_for(case, environment) -> FixQualification | None` returns a record only when its key and rule version match. Otherwise the caller runs `qualify_candidate` again. A case that no longer qualifies gets a rejected record, which 424 uses to drop it with that reason.
- The reference is checked in the start environment (D4), the same one the replays and the grade use, as the architecture requires.

### D11 — Grader commands
Status: decided
- `FixCaseAdapter.grader_commands(parent_tree)` returns 421's `GraderCommand` list:
  - always `suite` (the runner's pytest invocation)
  - `lint` (`ruff check`), only when `[tool.ruff]` or `ruff.toml` exists at the parent
  - `typecheck` (`pyright`), only when `[tool.pyright]` or `pyrightconfig.json` exists at the parent
- This slice does not run lint or typecheck. They are case identity for 425, which reports them as totals against the start tree's baseline, not as a pass condition. A reference with lint or type errors therefore does not fail its grade.

### D12 — Yield report and the separability answer
Status: decided
- **Counts** per project: candidates, qualified, and rejected per `CandidateRejection`. For `no_qualifying_hidden_test` candidates, it also counts per `TestRejection`, and it counts `harness_error`. A pooled row covers all the given projects.
- **Separability** uses an analytic bound until 425 measures real variance. With *n* qualified cases and *k* samples per case, each config's per-case value is a pass fraction. The bound is the worst case per-case variance for independent outcomes, p = 0.5 for both configs, which gives Var(D) ≤ 0.5/k.
  - Minimum detectable difference: MDD = (z₀.₉₇₅ + z₀.₈₀) · √(0.5/k) / √n
  - Cases needed for a target difference d: n = ⌈(z₀.₉₇₅ + z₀.₈₀)² · 0.5/k / d²⌉
  - The answer is **enough cases** when MDD ≤ `benchmark.target_pass_rate_difference`, and **not enough** otherwise.
- The report states what the bound assumes: within-case outcomes are independent, and the true difference is the same in every case. Correlation between configs on the same case lowers the real variance. Case-to-case variation in the true difference raises it. So "enough cases" holds only if per-case differences are similar, and the report says so beside it. 425 replaces the bound with the measured paired bootstrap.
- Config keys, declared once in `config/keys.py`:
  - `benchmark.planned_samples` (default 3)
  - `benchmark.target_pass_rate_difference` (default 0.20, a difference between configs big enough to change which alias the PM configures)
- The significance level and power (0.05 and 0.80) are named constants in `separability.py`.
- **Counting unit.** One candidate is one `(project, commit_sha)`. It is represented by its latest `FixQualification` by `created_at`, whatever its environment digest or rule version; earlier records for the commit are ignored. A commit with a `pre` record and a later record in an environment counts once, as the later one. `no_qualifying_hidden_test` candidates also contribute one count per hidden-test verdict (not one per candidate) to the per-`TestRejection` counts. Grouping is by enum value, never by message text.
- Rejected: simulating a bootstrap here. With no real per-case data it adds only assumptions, not information.

### D13 — Any project, no configuration
Status: decided
- `build` and `yield` take `--repo PATH` (default the current directory). Project identity is `derive_project_id`. `case_build` picks the adapters once per repository: 421's `adapter_for(SourceLanguage.PYTHON)` gives the `BenchmarkAdapter`, and the same `registry.py` maps that language to the `FixCaseAdapter`. Python is the only language, so there is no detection step (as in 421). `qualify` runs suites through that `BenchmarkAdapter.run_suite`. `PythonFixCaseAdapter` does not import `PythonBenchmarkAdapter`. Every input comes from git, the project's `pyproject.toml` and its issue host. Nothing is read from per-project configuration.
- When the repository is not a Python project with packaging metadata (no `pyproject.toml`), each candidate is rejected with `no_fix_case_adapter`. The project still appears in the report, with a yield of zero.
- `yield` accepts `--repo` more than once, and with no `--repo` it reads every project with `fix_qualification` records. Pooling a case set across projects is done by naming those projects' case ids in one `write_case_set` call. `build --set` takes the current repository's qualified ids. `sq benchmark fix-cases pool --set NAME --repo …` is not added until the yield answer calls for it.

### Technology Choices

- pytest plugin hooks and `sys.setprofile` for collection, closure digests, crossings and patch interception. These are stdlib and pytest only, inside the same pytest ≥ 7.0 constraint as 421's reporter.
- GraphQL through the existing `gh` wrapper for issues.
- No new dependencies.

### Patterns and Conventions

- `CandidateRejection`, `TestRejection`, `QualificationOutcome` and `HiddenTestVerdictKind` are `StrEnum`s defined once in `benchmark_models.py`. The report groups by these values, never by message text. The two rejection enums are:
  - `CandidateRejection` (whole candidate): `merge_commit`, `root_commit` (no parent to diff against), `multiple_closing_commits`, `multiple_issues_closed`, `no_issue_host`, `issue_not_found`, `reference_is_pull_request`, `issue_edited_after_fix`, `no_fix_case_adapter`, `no_test_change`, `test_data_changed`, `modifies_test_support`, `changes_lockfile`, `environment_unresolved` (421's `EnvironmentResolutionError`, its reason in `detail`; the reasons `installer_missing` and `install_timeout` say nothing about the case and are `harness_error` records instead), `collection_failed`, `no_packaging_boundary`, `boundary_undecidable` (resolver failure), `no_qualifying_hidden_test`.
  - `TestRejection` (one hidden test, or an `excluded_tests` entry): `passes_at_parent`, `uses_symbol_added_by_fix`, `undecidable_failure_at_parent`, `reaches_past_boundary`, `patches_project_code`, `boundary_undecidable` (trace), `flaky`, `fails_at_reference`.
- `FixCaseAdapter` is a separate protocol from 421's `BenchmarkAdapter` (ISP: slice-case languages need no fairness methods).
- Harness failures (timeouts, `SuiteRunError`, `CodeHostError` other than not-found) are logged at ERROR and recorded as `harness_error` with the detail. They are never counted as a rejection reason that blames the case.

## Implementation Details

### API Contracts

```python
class FixCaseAdapter(Protocol):
    language: SourceLanguage
    # Diff classification runs before any sandbox exists, so there is no tree to read:
    # is_test_side takes the parent's pyproject.toml text (None when it has none).
    def is_test_side(self, pyproject_text: str | None, path: str) -> bool: ...
    def is_test_source(self, path: str) -> bool: ...                       # source code, not test data
    def lockfile_names(self) -> tuple[str, ...]: ...                       # a diff touching one is rejected
    def collect(self, ctx: SandboxContext) -> CollectedTests: ...          # node id -> closure digest, fixtures
                                                                           # raises CollectionFailed
    def overlay(self, ctx: SandboxContext, files: Mapping[str, bytes | None]) -> None: ...
    def boundary(self, ctx: SandboxContext) -> AllowedBoundary: ...        # raises BoundaryUndecidable
    def trace(
        self, ctx: SandboxContext, node_ids: Sequence[str], allowed: AllowedBoundary
    ) -> Mapping[str, FairnessVerdict]: ...                                # the verdict needs the boundary
    def grader_commands(self, tree: Path) -> tuple[GraderCommand, ...]: ...
```

`FairnessVerdict` (`rejection: TestRejection | None`, `detail: str`) is the only verdict type; `None` means the test is fair. A harness problem (timeout, missing output, I/O error) is never a verdict: the adapter raises `HarnessFailure`, and qualification records `harness_error`. The `FixCaseAdapter` is reached only through `registry.py`.

```python
# benchmark/qualify.py
def qualify_candidate(candidate: FixCandidate, deps: QualifyDeps) -> QualifyResult: ...
def qualification_for(
    case: BenchmarkCase, environment: EnvironmentIdentity, store: BenchmarkRecordStore
) -> FixQualification | None: ...

@dataclass(frozen=True)
class QualifyResult:
    record: FixQualification
    reused: bool = False       # True when an earlier record with the same key and rule version was used

# benchmark/qualify_sandbox.py: what QualifyDeps.sandbox_stages holds
def qualify_in_sandbox(
    candidate: FixCandidate, classification: DiffClassification, task_text: str, deps: QualifyDeps
) -> QualifyResult: ...
```

`qualification_for` matches on project, the case's reference commit, the environment digest and the current rule version. It returns a rejected record (the reason the case no longer qualifies), and it returns `None` for a missing record, a stale rule version or a `harness_error`; the caller then runs `qualify_candidate` again. `store` is an argument because the function has no other way to reach the records.

Errors: `IssueNotFoundError` and `ReferenceIsPullRequestError` (codehost) become the rejections `issue_not_found` and `reference_is_pull_request`. `BoundaryUndecidable` becomes `boundary_undecidable`, and `CollectionFailed` (it names the file) becomes `collection_failed`. `HarnessFailure` becomes a `harness_error` record. `BuildHalted` (`build_errors.py`) stops the whole build, after an ERROR log, for failures that apply to every candidate (for example `gh` missing); it is never used for one candidate's failure.

**`sq benchmark fix-cases build --set NAME [--repo PATH] [--commit SHA …] [--keep]`**

This runs discovery, qualification and case-set writing for the repository. `--commit` limits the run to the given candidates, for debugging. It prints one line per candidate (`qualified case-… (2 hidden)` or the rejection reason), then the yield report for this project. It exits 0 when the run finished, whatever the yield. It exits 1 on a harness failure that stops the build (for example, `gh` missing while candidates need it).

**`sq benchmark fix-cases show COMMIT|CASE_ID`** prints the latest qualification record:

- the environment digest
- each hidden candidate with its verdict and detail (symbol reached, patch target, per-run outcomes)
- superseded and excluded tests with reasons
- the frozen task text

**`sq benchmark yield [--repo PATH …] [--json]`**

```
project      candidates  qualified  top rejections
squadron     53          n          no_qualifying_hidden_test 31 (patches_project_code 18, reaches_past_boundary 9, …), no_test_change 5, …
pooled       …

separability (k=3 samples, target 0.20): n=… qualified → MDD 0.xx → enough cases | not enough (need ≥ 33 cases)
assumes independent outcomes, p=0.5, constant per-case difference; "enough" fails if per-case differences vary; 425 replaces this with measured variance
```

The `/sq:benchmark` slash command mirrors all three subcommands with the same arguments and output.

### Database / Storage Schema

```python
class HiddenTestVerdict(BaseModel, frozen=True):
    node_id: str
    kind: HiddenTestVerdictKind            # qualified | rejected
    rejection: TestRejection | None
    detail: str                            # symbol, patch target, per-run outcomes

class FixQualification(BaseModel, frozen=True):
    project_id: ProjectId
    commit_sha: str
    parent_sha: str
    issue_ref: str | None                  # "owner/repo#n"
    rule_version: int
    environment: EnvironmentIdentity | None
    repeats: int
    outcome: QualificationOutcome          # qualified | rejected | harness_error
    case_id: str | None
    rejection: CandidateRejection | None
    detail: str
    hidden_verdicts: tuple[HiddenTestVerdict, ...]
    excluded_with_reasons: tuple[tuple[str, TestRejection], ...]
    created_at: datetime
```

`MetrologyRecord` gains `fix_qualification: FixQualification | None` and `RECORD_TYPE_FIX_QUALIFICATION`. `BenchmarkRecordStore` gains `write_fix_qualification`, `get_fix_qualification(project_id, commit, env_digest)` and `list_fix_qualifications(project_id=None)`. No migration is needed.

## Integration Points

### Provides to Other Slices

- **424:** qualified fix cases and their case set, `qualification_for(case, environment, store)` and `qualify_candidate` for re-qualification in the run's environment, and frozen `task_text` to pass to `sq run fix`.
- **425:** `hidden_tests`, `hidden_fixtures`, `superseded_tests`, `excluded_tests` and `grader_commands` on each case.
- **426:** `test_sets` (superseded computation from closure digests) and the repeat-and-exclude step, reused for slice cases, which have no hidden set.
- **Initiative ordering:** the yield report's separability answer.

### Consumes from Other Slices

- **421:** everything listed under Prerequisites. If the 421 auth check answered no, nothing here is affected, because this slice runs no producer.
- **Codehost:** `get_issue` is added to the `CodeHost` protocol and `GitHubCli`. Other hosts do not exist today.

## Success Criteria

### Functional Requirements

- `sq benchmark fix-cases build` runs on any cf project's checkout with no per-project configuration and writes one `FixQualification` per closing commit.
- Every candidate ends as `qualified`, `rejected` with a `CandidateRejection`, or `harness_error`. The number of records equals the number of closing commits, which a test checks against a fixture repository.
- A case's `task_text` contains no comment created after the fix commit's committer date. A fixture issue with a later comment produces the same `case_id` before and after the comment. A fixture issue edited after the fix is rejected with `issue_edited_after_fix`.
- Hidden and superseded sets list individual node ids. A fixture fix that adds one test to an existing file, changes one test, deletes one test and adds one `conftest.py` fixture produces exactly those entries.
- Each fairness check has tests with qualifying and disqualifying examples taken from squadron's real fix commits:
  - **test-first:** a test that fails with an `AttributeError` on a symbol the fix added, and one that fails by assertion
  - **boundary:** a test that drives `sq` through the CLI, and one that calls an internal function directly
  - **no patching:** the summary test from ebd45f3f, which patches an internal function by module path, and the #291 tests (9fc4fc1c, d6535d62) for the pipeline mock
  - **a crash fix that qualifies:** chosen from the squadron build in step 6 of the development approach
- Repeated qualification puts disagreeing nodes on `excluded_tests`, and the resulting case id differs from one built with no exclusions.
- A second `build` with nothing changed runs no collection or test for reused candidates. After `FAIRNESS_RULE_VERSION` is bumped, every candidate is re-qualified.
- `sq benchmark yield` runs on squadron and on at least one other cf project, and it prints the counts and the separability answer for each project and pooled.

### Technical Requirements

- `ruff format`, `ruff check` and `pyright` (zero errors) are clean.
- The trace plugin is tested against real pytest runs on fixture projects under `tests/benchmark/fixtures/`, covering each crossing type, each patch API, a static module reference and a dependency-invoked callback.
- Every harness failure path (issue fetch failure, suite timeout, resolver crash) has a test that asserts `harness_error` and its detail.
- `separability.py` is tested against hand-computed MDD and required-n values.

### Integration Requirements

- 424 can load a case set version, call `qualification_for` with its own sandbox's environment, and get either a valid record or a reason to re-qualify.
- 421's sandbox, records and suite runner are used unchanged. Any change this slice needs from them is a 421 defect, fixed there.

### Verification Walkthrough

These are draft commands. They do not exist until this slice is implemented.

1. **Build squadron's fix cases (once, whole history).** This is the only full-history run; later steps read its records.
   ```bash
   cd ~/source/repos/manta/squadron
   sq benchmark fix-cases build --set fix-squadron
   ```
   Expect one line per closing commit, then a yield table. The candidate count matches `git log --format=%B | grep -ciE '(close|fix|resolve)[a-z]*\s+#[0-9]+'`, give or take commits with more than one closing line. Those are rejected as `multiple_issues_closed`, which `fix-cases show` confirms.

2. **Inspect a rejection and a qualification.**
   ```bash
   sq benchmark fix-cases show 13e8381a
   sq benchmark fix-cases show <case-id from step 1>
   ```
   Expect per-test verdicts with the symbol or patch target that decided them. For a qualified case, expect its frozen issue text, hidden node ids and excluded tests.

3. **Frozen text matches the cutoff.** For one qualified case, compare its task text with `gh issue view <n> --comments`. Comments dated after `git log -1 --format=%cI <commit>` are absent.

4. **Reuse.** Rerun `build --commit <sha>` for three commits only: one qualified, one rejected at the sandbox stage, one rejected earlier. It runs installs but no tests; the first two say `reused` and the third repeats its rejection reason.

5. **Second project.** Pick another cf project from `cf project list` (a uv Python project gives a non-trivial answer). Count its closing commits first; at 30 or fewer build it whole, above 30 build only its 10 most recent with repeated `--commit` and treat the result as a sample:
   ```bash
   sq benchmark fix-cases build --set fix-<name> --repo <path>
   sq benchmark yield --repo . --repo <path>
   ```
   Expect a row per project, a pooled row, and a separability line for each. Record the answer in the DEVLOG. It decides the order after 423.

6. **Case set.** `sq benchmark yield --json | jq` shows the case set name and version. Running step 1 again does not create a new version.

## Risk Assessment

### Technical Risks

- **Boundary trace precision.** Re-exports, dynamic imports and the stated gaps (D6) can admit a coupled test or reject a fair one.
- **Yield.** The architecture's own count (23 of 46 fix tests mock or patch, 37 use private-looking names) suggests that squadron alone yields a small set.
- **Qualification cost.** The full suite runs `qualification_repeats` times per surviving candidate, at the reference.

### Mitigation Strategies

- Any undecidable result excludes with a named reason. `fix-cases show` makes every verdict inspectable. The fixture tests from real commits pin both sides of each check.
- Low yield is the result the report exists to produce, and its answer is planned for in the slice plan.
- Cheap checks run first (D9), so the full suite only runs for candidates that already have a fair hidden test. Records make the build resumable.

## Implementation Notes

### Development Approach

1. `IssueSnapshot` and `get_issue`, then `issue_freeze`, with fixture issues.
2. `fix_discovery` against a fixture git repository built in the test, covering every discovery reason.
3. The trace plugin's collect mode, closure digests and `test_sets`, against fixture projects.
4. Overlay and the test-first mapping on top of 421's `run_suite`.
5. The boundary resolver, crossings, static references and patch interception, against fixture projects.
6. `qualify`, `FixQualification` records, `case_build` and the CLI. Run on squadron once over its whole history, and take the real-commit fairness examples from the records that run wrote; do not build again. A category with no instance among those records is noted in the DEVLOG, not a blocker.
7. `separability` and `yield_report`. Run the walkthrough on squadron and a second project.

Effort: 4/5.

### Special Considerations

- Issue fetching is the only network call outside installs. It runs in the harness, never under the scrubbed environment, and `gh` credentials never reach a sandbox.
- The parent overlay runs the reference's tests against older code. Those tests may import modules that do not exist at the parent. That is the intended `uses_symbol_added_by_fix` signal, not a harness error.
- The trace plugin and the resolver run model-free code from history under the scrubbed environment, at the same trust level as 421's suite runner.
