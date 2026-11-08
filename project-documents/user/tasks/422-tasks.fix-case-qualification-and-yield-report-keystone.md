---
docType: tasks
slice: fix-case-qualification-and-yield-report-keystone
project: squadron
lld: user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md
dependencies:
- 421
- 420
projectState: v0.24.23 released, main is the target (git.integration_branch unset).
  Slice 421 tasks written, not implemented. Slice 422 design written.
dateCreated: 20261106
dateUpdated: 20261107
status: in_progress
turns: 23
promptTokens: 1290204
cachedTokens: 1184813
cacheWriteTokens: 105361
completionTokens: 33778
durationSeconds: 244.7
costUsd: 0.878086
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.8780863
    completionTokens: 33778
---

## Context Summary
- Working on slice 422: the keystone of the model benchmark (initiative 420). Design: `user/slices/422-slice.fix-case-qualification-and-yield-report-keystone.md`; the design's D-numbers (D1–D13) are cited below instead of repeating them.
- Delivers: `CodeHost.get_issue`; frozen issue text; closing-commit discovery; test sets from closure digests; the Python fairness checks (test-first, packaging boundary, no patching); repeated qualification; `FixQualification` records; the case set; the yield report with its separability answer; `sq benchmark fix-cases build|show`, `sq benchmark yield` and `/sq:benchmark`.
- **Prerequisite:** every 421 name used here (`BenchmarkCase`, `CaseSet`, `BenchmarkRecordStore`, `BenchmarkSandbox`, `EnvironmentIdentity`, `FailureKind`, `NodeOutcome`, `SuiteSelection`, `SandboxContext`, `adapter_for`, `registry.py`, `cli/commands/benchmark.py`, `tests/benchmark/support.py::git_tree`) comes from slice 421, which is not implemented yet. Task 1 stops the work until it is. 421's sandbox, records and suite runner are used unchanged: any change this slice needs in them is a 421 defect, fixed there. This slice only adds to them what the design's Component Structure lists (record types, store methods, `registry.py` entry).
- Design gaps found while breaking down. Gaps 1–3 are interface corrections that Task 31 writes into the design. Gaps 4 and 5 touch the design's Success Criteria and Verification Walkthrough, which these tasks do not edit: they need a Project Manager decision, and Task 31 records them in the DEVLOG.
  1. `trace` also takes the `AllowedBoundary`, because the verdict needs it.
  2. `FixCaseAdapter` gains `lockfile_names` and `is_test_source`, and `is_test_side` takes the parent's `pyproject.toml` text instead of a tree. Diff classification runs before any sandbox exists, so no tree exists to read.
  3. The protocol's `TraceVerdict` and the component list's `FairnessVerdict` are one type, named `FairnessVerdict`.
  4. Of the commits the design names as real examples, 9fc4fc1c and d6535d62 both close #291, so discovery rejects both as `multiple_closing_commits`, and ebd45f3f has no closing keyword, so it is not a candidate. None can reach the fairness checks through `build`. Task 29 runs the sandbox stages on them directly, which is the closest check available.
  5. Walkthrough step 4 cannot show `reused` on every line: candidates rejected before the sandbox have no environment key and are recomputed (D10 reuses only after the install). Task 30 checks what is possible.
- Pinned plugin interface (Tasks 12, 13, 14, 17–21). One environment variable, `SQUADRON_FIXCASE_TRACE_CONFIG`, names a JSON file `{mode: "collect"|"trace", tree, test_side_files: [relative paths], output}`. In trace mode the node ids to trace are pytest's positional arguments, as 421's suite runner passes them; collect mode takes none. The plugin imports only the standard library and `pytest`, and creates (truncates) `output` in `pytest_configure`, so a file that exists proves the plugin loaded. At session finish it writes one JSON object to `output`:
  - collect mode: `{items: [{node_id, digest, fixtures: [[conftest_path, name], ...]}], conftest_fixtures: [[conftest_path, name], ...], collection_errors: [{file, message}]}`
  - trace mode: `{has_co_qualname: bool, nodes: {node_id: {references: [[kind, module, qualname], ...], crossings: [[module, co_qualname, kind], ...], patches: [[api, owner_kind, owner_module, target], ...]}}}`; reference `kind` is `module|class|function`, crossing `kind` is `function|constructor|method`, patch `owner_kind` is `project_module|project_class|project_instance|foreign|unresolved`; a crossing's `module` is the callee frame's `f_globals["__name__"]`, the same form as the resolver's `obj.__module__`
- Tests live in `tests/benchmark/`, `tests/metrology/` and `tests/codehost/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Tests needing network or `gh` carry the existing `network` marker.
- Load tests: nothing here is concurrent (candidates are qualified one at a time). Every I/O path (`git log`, `git diff`, `git show`, `gh`, overlay writes, record writes, suite runs, collection, the resolver, the trace run) has a test that asserts its failure is observable (an ERROR log plus `harness_error`, `HarnessFailure` or `BuildHalted`), which is the failure-mode coverage for this slice.
- Effort: 4/5.

## Tasks

### Task 1: Create the slice branch
- [x] Run `cf config get git.integration_branch`; the target is its value, or `main` when empty
- [x] `git checkout -b 422-slice.fix-case-qualification-and-yield-report-keystone <target>` (or switch to it if it exists)
  - [x] Success: `git branch --show-current` prints the slice branch
- [x] Confirm slice 421 is implemented: `grep -c '^\s*- \[ \]' project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md` prints `0` and `src/squadron/benchmark/registry.py` exists. If not, write `BLOCKED: slice 421 is not implemented` under this task, leave it unchecked, and stop

### Task 2: Config keys (D9, D12)
- [x] In `src/squadron/config/keys.py` add keys beside 421's benchmark keys, each with a constant, a `CONFIG_KEYS` entry, a description and a default: `benchmark.qualification_repeats` (int, 3), `benchmark.planned_samples` (int, 3), `benchmark.target_pass_rate_difference` (float, 0.20). Read the ints through `get_positive_int_config` and the float through `get_typed_config(..., float)`
  - [x] A float key with a value `<= 0` or `>= 1` fails loudly where it is read; add that check in one reader function, not at each caller
- [x] Tests (`tests/benchmark/test_config_keys.py`, extend 421's): defaults, overrides, and rejection of a zero repeat count and an out-of-range difference
  - [x] Success: tests pass

**Commit**: `feat: add benchmark qualification config keys`

### Task 3: Qualification record models (D8, D10, Patterns)
- [ ] In `metrology/benchmark_models.py` add `StrEnum`s `CandidateRejection`, `TestRejection`, `QualificationOutcome` (`qualified`, `rejected`, `harness_error`) and `HiddenTestVerdictKind` (`qualified`, `rejected`). Values are exactly the lists in the design's Patterns and Conventions
- [ ] Add frozen models `HiddenTestVerdict` and `FixQualification` with the fields in the design's Database / Storage Schema. A `model_validator` enforces: `qualified` has a `case_id` and no rejection; `rejected` has a `rejection` and no `case_id`; `harness_error` has neither; a `rejected` verdict has a `TestRejection` and a `qualified` one has none
- [ ] Add `fix_qualification_record_id(project_id, commit_sha, env_digest | None)` returning `fixqual-<sha256(project_id.value)[:12]>-<commit[:12]>-<env digest[:12] or "pre">` (D10)
- [ ] Tests (extend `tests/metrology/test_benchmark_models.py`)
  - [ ] Each enum has exactly the design's values (a value added without a design change fails)
  - [ ] Each validator rule rejects its bad combination; a JSON round trip equals the original
  - [ ] Record id: the `pre` form when no environment, the digest form otherwise; two projects with the same commit differ

### Task 4: Store the qualification records (D10)
- [ ] `metrology/models.py`: add `RECORD_TYPE_FIX_QUALIFICATION` and an optional `fix_qualification` field on `MetrologyRecord` (extend the docstring of record types); `schema_version` unchanged
- [ ] `benchmark_store.py`: add `write_fix_qualification(q)` (a newer result under the same id overwrites), `get_fix_qualification(project_id, commit_sha, env_digest)` and `list_fix_qualifications(project_id=None)`. Error mapping is the same as 421's `get_case`: absent → `None`; a tampered or wrong-type file → ERROR log and `MetrologyStoreError`; `list_` skips a mismatching file with a WARNING
- [ ] Tests (extend `tests/metrology/test_benchmark_store.py`)
  - [ ] Write then get is equal; a second write under the same key leaves one file holding the later result; a different environment digest leaves two
  - [ ] `list_fix_qualifications` filters by project; a tampered file raises from `get_` and is skipped (with WARNING via `caplog`) by `list_`
  - [ ] A record file written before this change still loads
  - [ ] Success: `tests/metrology/` passes

**Commit**: `feat: add fix qualification records`

### Task 5: Issue snapshot models and `get_issue` (D2)
- [ ] Capture real responses for the new query with `gh api graphql` into `tests/codehost/fixtures/gh/` (as the module docstring of `github_queries.py` requires): one issue with comments, one of them with a non-null `lastEditedAt` (any public issue will do; if none can be found, write `BLOCKED:` with the search tried under this task), one issue never edited, one issue with a title rename event (any public issue; same fallback), one number that is a pull request, one number that does not exist. Record the command used in a comment at the top of the query
- [ ] `codehost/models.py`: frozen `IssueComment` (author_login, body, created_at, last_edited_at | None) and `IssueSnapshot` (locator, number, title, body, created_at, last_edited_at | None, comments, `title_renamed_at`: a tuple of the timestamps of title rename events)
- [ ] `codehost/github_queries.py`: `ISSUE_QUERY` through `issueOrPullRequest`, selecting `__typename`, the issue fields, comments, and title rename events (`timelineItems` with `itemTypes: [RENAMED_TITLE_EVENT]`, `createdAt` only; the snapshot's only source for title edits). Page each connection the way `REVIEW_THREADS_QUERY` is paged, bounded by the existing `MAX_DISCUSSION_PAGES` in `github_cli.py`; exceeding the bound raises rather than truncating
- [ ] `codehost/errors.py`: `IssueNotFoundError` and `ReferenceIsPullRequestError`, both `CodeHostError`
- [ ] `codehost/protocol.py` and `github_cli.py`: add `get_issue(locator, number) -> IssueSnapshot`. A GraphQL NOT_FOUND maps to `IssueNotFoundError`; a pull-request typename to `ReferenceIsPullRequestError`; every other failure keeps its existing typed error. Update every other `CodeHost` implementation in `src` and `tests` (find them with grep for `serves_host`)
- [ ] Tests (`tests/codehost/test_github_cli.py` style, scripted runner replaying the captured fixtures)
  - [ ] Each fixture maps to the expected snapshot or error; the edited comment carries `last_edited_at` and the rename fixture carries `title_renamed_at`; a multi-page comment list is joined in order; the page bound raises
  - [ ] Timeout and unauthenticated failures surface as `HostCommandTimeoutError` and `HostUnauthenticatedError`, unchanged
  - [ ] Success: `tests/codehost/` passes, including `test_import_boundaries.py`

**Commit**: `feat: add CodeHost.get_issue`

### Task 6: Frozen issue text (D2)
- [ ] `src/squadron/benchmark/issue_freeze.py`: `render_issue(snapshot, cutoff: datetime | None) -> str` and `freeze_issue(snapshot, cutoff) -> FrozenIssue | CandidateRejection`; `FrozenIssue` is a frozen dataclass with one field, `task_text`
  - [ ] No cutoff: title, body and every comment, rendered as markdown with a heading per comment (author and date); no edited-after check
  - [ ] Cutoff: the title, the body, and each comment created before the cutoff in order; a comment created at or after the cutoff is omitted
  - [ ] Cutoff and the body, or an included comment, with `last_edited_at` after the cutoff, or any title rename at or after the cutoff → `issue_edited_after_fix`. An omitted comment's edits are ignored
  - [ ] Timestamps compare as timezone-aware values; a naive timestamp raises
- [ ] Tests `tests/benchmark/test_issue_freeze.py`
  - [ ] A late comment does not change the rendered text; a late comment's edit does not reject; an edited body rejects; a comment edited after the cutoff rejects; a title rename after the cutoff rejects and one before the cutoff does not
  - [ ] No-cutoff rendering includes every comment and never rejects
  - [ ] Heading format is pinned by one exact-string assertion

**Commit**: `feat: freeze issue text at the fix commit date`

### Task 7: Closing-commit discovery (D1)
- [ ] `src/squadron/benchmark/build_errors.py`: `BuildHalted`, an error meaning the build cannot continue and the reason is in its message. It is raised only after an ERROR log
- [ ] `src/squadron/benchmark/fix_discovery.py`: frozen `FixCandidate` (sha, parent_sha, committer_date, issue reference as written, owner/repo or `None`, number) and `DiscoveryResult` (`candidates`, `rejections` as `(sha, CandidateRejection, detail)`); `discover(runner, repo_root) -> DiscoveryResult`. It runs one `git log` over `HEAD` with an unambiguous record separator and parents in the format, through `ProcessRunner`. A `git log` that times out, is not found or exits non-zero is logged at ERROR and raised as `BuildHalted` naming the command
- [ ] Closing keyword regex per D1, case-insensitive, followed by `#n` or `owner/repo#n`; one pattern constant, defined once. A bare `(#283)` suffix is not a reference. Parse leniently: keyword and number separated by any whitespace or a colon, any line of the body
- [ ] Rejections: `merge_commit`; `multiple_issues_closed` (distinct issues, the same issue twice counts once); `multiple_closing_commits` applies to **every** commit that closes an issue closed by more than one commit. Each commit gets exactly one outcome, in this precedence: merge, multiple issues, multiple closing commits
- [ ] Add `closing_commit_repo(tmp_path)` to `tests/benchmark/support.py`: a git repository whose commits cover every discovery reason, a `(#283)` suffix, a closing keyword in a body line other than the first, and one commit with no closing keyword. Task 26 reuses it
- [ ] Tests `tests/benchmark/test_fix_discovery.py`
  - [ ] On `closing_commit_repo`, each commit gets the expected candidate or rejection, and candidates plus rejections cover every closing commit exactly once
  - [ ] Parser fixture from real history: capture the `git log` output of these real squadron commits into `tests/benchmark/fixtures/git_log_samples.txt`, in the exact format `discover` requests: 29850399 and 38060838 (#216), 9fc4fc1c and d6535d62 (#291), ebd45f3f (no closing keyword), the most recent commit whose body closes two distinct issues, and the three most recent commits with a `Fixes #n` body line. Assert the outcome of each
  - [ ] Failure mode: with a scripted runner, a `git log` timeout and a non-zero exit each raise `BuildHalted` with an ERROR log (`caplog`)

**Commit**: `feat: discover fix candidates from closing commits`

### Task 8: Issue repository resolution (D1)
- [ ] In `fix_discovery.py` add `resolve_locator(candidate, remotes, host: CodeHost)`: an `owner/repo#n` reference uses that repository on the host of the matching remote; a bare `#n` uses the single remote the host serves (use `list_remotes` and the same selection `remotes.py` uses for bare targets; do not duplicate its logic). No serving remote → `no_issue_host`
- [ ] Tests (extend `tests/benchmark/test_fix_discovery.py`, scripted remotes): both reference forms resolve; `no_issue_host` with no remote and with a remote on an unserved host

**Commit**: `feat: resolve issue repositories for fix candidates`

### Task 9: Fairness types, adapter protocol, diff classification (D1, D3, D4, D6, D10, API Contracts)
- [ ] `src/squadron/benchmark/fairness.py`: `FAIRNESS_RULE_VERSION = 1` with a comment that it is bumped whenever any check changes; frozen `CollectedTests` (node id → closure digest; conftest fixtures reached per node; every conftest fixture defined, by path and name); `AllowedBoundary` (entries as `(module, qualname)`); `FairnessVerdict` (rejection `TestRejection | None`, detail); errors `BoundaryUndecidable`, `CollectionFailed` (names the file) and `HarnessFailure` (carries the detail; a harness failure is never a test verdict); the `FixCaseAdapter` protocol as in the design's API Contracts with the Context Summary changes: `is_test_side(pyproject_text: str | None, path)`, `lockfile_names()`, `is_test_source(path)`, `trace(ctx, node_ids, allowed)`
- [ ] `src/squadron/benchmark/diff_classify.py`: `classify_diff(changes, adapter, parent_pyproject, read_parent, read_reference) -> DiffClassification | CandidateRejection`; `DiffClassification` holds `added`, `changed`, `deleted` and `test_side` path tuples. `changes` come from `git diff --name-status parent..commit` (renames and copies parse as delete plus add; handle quoted paths leniently)
  - [ ] No test-side file in the diff → `no_test_change`
  - [ ] A test-side file that is not test source (`adapter.is_test_source` false) → `test_data_changed`
  - [ ] A diff path in `adapter.lockfile_names()` → `changes_lockfile`
  - [ ] A changed or deleted `conftest.py` → `modifies_test_support` unless every difference is an added top-level `pytest.fixture` function or an added import (D3). An added plain function, class or constant, and any changed or removed definition, are rejected. Compare with `ast`; an unparsable conftest at either side is `modifies_test_support` with the syntax error in `detail`
  - [ ] Precedence is the order above
- [ ] Tests `tests/benchmark/test_diff_classify.py` with synthetic changes, a stub adapter and conftest text: one case per reason, a conftest that only adds a fixture and an import passing, a conftest whose existing fixture body changes failing, a conftest that adds a plain helper function failing, a rename
  - [ ] Success: tests pass; `pyright` is clean on the protocol

**Commit**: `feat: classify fix diffs and define the fix-case adapter seam`

### Task 10: Test sets (D3)
- [ ] `src/squadron/benchmark/test_sets.py`: pure `sort_tests(parent: CollectedTests, reference: CollectedTests) -> TestSets` giving `hidden_candidates`, `superseded`, `unchanged`, and `hidden_fixtures` (a conftest fixture present at the reference, absent at the parent, reached by some hidden candidate's closure, as 421's `ConftestFixture`). Sorting rules are D3's four cases exactly; outputs are sorted tuples
- [ ] Tests `tests/benchmark/test_test_sets.py` on synthetic `CollectedTests` pairs: one shaped like the success-criteria fix (adds one test to an existing file, changes one test, deletes one test, adds one conftest fixture) produces exactly those entries; an added fixture no hidden test reaches is not hidden; a changed test is in both hidden and superseded; equal digests are unchanged

**Commit**: `feat: sort tests into hidden and superseded sets`

### Task 11: Fixture project and history helper (test infrastructure)
- [ ] Create the fixture project `tests/benchmark/fixtures/fixfair_project/` (a `uv.lock` from `uv lock`, pytest as a dev dependency, `pythonpath = ["src"]`, package `fixpkg` with a top-level `__all__`, a `[project.scripts]` entry, an internal module with a function not in `__all__`, a class). Add tests with fixtures in a `conftest.py`, helper functions, parametrized tests and a test-side constant, each reached in different ways. 421's `collect_ignore_glob = ["fixtures/*"]` covers it
- [ ] Create two more small uv projects under `tests/benchmark/fixtures/`, each with its own `uv.lock` from `uv lock`, for Task 20: `fixfair_no_boundary` (a package with no `__all__` and no `[project.scripts]`) and `fixfair_bad_import` (a package whose `__init__.py` raises on import)
- [ ] Add `fix_history(fixture, scenario, tmp_path)` to `tests/benchmark/support.py`: copies the base project into a git repository (commit 1), applies `tests/benchmark/fixtures/fixfair_changes/<scenario>/` (files to write; a `deleted.txt` lists removals) and commits (commit 2) with a closing message; returns the repo, parent sha and fix sha. Create the scenario `sort_sets`: adds one test file, changes one test, deletes one test, and adds a conftest fixture used by a new test
- [ ] Tests `tests/benchmark/test_fix_history_helper.py`: the two commits exist, `git diff --name-status` between them lists exactly the scenario's writes and removals, and the commit message carries a closing keyword
  - [ ] Success: `uv sync --locked` works in each of the three fixture projects; `uv run pytest tests/benchmark --collect-only -q` lists no node under `fixtures/`

**Commit**: `test: add fixfair fixture project and history helper`

### Task 12: Trace plugin, collect mode: node ids and closure digests (D3)
- [ ] `src/squadron/benchmark/pytest_trace/squadron_fixcase_trace.py`: configuration and output as the Context Summary pins. This task fills `items` with `node_id` and `digest` and writes `fixtures`, `conftest_fixtures` and `collection_errors` as empty lists (Task 13 fills them). Collect mode implements `pytest_collection_finish`. For each item it writes the node id and the closure digest: sha256 over the test source (decorators and parametrize ids included) plus every test-side definition reached (fixtures from pytest's resolved definitions; module-level functions, classes and constants named in `co_names` of the test and fixtures, recursively within test-side files only). Test-side is membership in `test_side_files`
- [ ] Tests `tests/benchmark/test_trace_collect.py`: run the harness's pytest with `-p squadron_fixcase_trace` and the config JSON on a `git_tree` copy of the fixture (no venv)
  - [ ] Digest changes when the test body changes, when a fixture it uses changes, when a helper it calls (two levels deep) changes, and when its parametrize ids change; it does not change when an unrelated test changes
  - [ ] A parametrized id with brackets round-trips exactly; a run that collects nothing writes valid JSON with empty `items`
  - [ ] The plugin file imports only `pytest` and the standard library (assert by AST)

**Commit**: `feat: add trace plugin node ids and closure digests`

### Task 13: Trace plugin, collect mode: conftest fixtures, collection errors, packaging (D3)
- [ ] Fill `fixtures` (the conftest fixtures each item reaches, by path and name) and `conftest_fixtures` (every conftest fixture defined). Add a `pytest_collectreport` hook that writes each failed collection to `collection_errors` with its file and message
- [ ] Packaging: locate the plugin directory at runtime with `importlib.resources` or `Path(__file__)`; confirm with `uv build` and `unzip -l` that the wheel ships it, adding a `pyproject.toml` include if hatch omits it
- [ ] Tests (extend `tests/benchmark/test_trace_collect.py`)
  - [ ] Conftest fixtures reached by an item and all conftest fixtures defined are reported by path and name
  - [ ] A test-side file that fails to import appears in `collection_errors` with its file
  - [ ] The wheel-content check passes

**Commit**: `feat: report conftest fixtures and collection errors from the trace plugin`

### Task 14: `PythonFixCaseAdapter` collection (D3)
- [ ] `src/squadron/benchmark/python_fairness.py` (split by concern if it nears 300 lines; `python_boundary.py` in Task 20 is the likely split): `PythonFixCaseAdapter` with `language`, `is_test_side` (parent's `[tool.pytest.ini_options] testpaths` read from the `pyproject_text` argument; with none set, `test_*.py`, `*_test.py`, `conftest.py` and anything under `tests/` or `test/`), `is_test_source` (`.py`), `lockfile_names` (`uv.lock`), and `collect(ctx)`
- [ ] `collect` lists test-side files with `git ls-files --cached --others --exclude-standard` in the tree (so files the diff adds but nothing has committed are included), writes the config JSON, copies the plugin directory with `shutil.copytree` into `<out>/fixcase_plugin` (421's runner is not touched), runs `<tree>/.venv/bin/python -m pytest --collect-only -q -p squadron_fixcase_trace -p no:cacheprovider` with `replace_env=True`, the sandbox environment and `PYTHONPATH` at that copy, and reads the output. Any `collection_errors` entry raises `CollectionFailed` naming the file. A missing output file (the plugin never loaded) or a `ProcessTimedOutError` raises `HarnessFailure` with the detail
- [ ] Tests `tests/benchmark/test_python_fairness.py` (`network` marker for tests that install). Create the scenario `collection_broken` (the reference adds a test file with a syntax error)
  - [ ] Build one `BenchmarkSandbox` at the parent sha and a second at the fix sha of `sort_sets` (no `FileStates` yet; Task 15 adds the switch), `collect` in each, and `sort_tests` on the results gives the expected entries
  - [ ] `collect` in a sandbox at the fix sha of `collection_broken` raises `CollectionFailed` naming the file; a scripted runner timeout and a missing output file each raise `HarnessFailure`
  - [ ] `is_test_side` with and without `testpaths` in the text

**Commit**: `feat: add python fix-case adapter collection`

### Task 15: File states, overlay, grader commands (D4, D11)
- [ ] `overlay(ctx, files)` on the adapter: writes each `path → bytes` and removes each `path → None`, creating directories; paths are validated to stay inside the tree; an `OSError` is logged at ERROR and raised as `HarnessFailure`
- [ ] `src/squadron/benchmark/file_states.py`: `FileStates` built from the user's checkout with `git show <sha>:<path>`: `reference_files`, `overlay_files` (test-side only) and `parent_files` for the same paths, so the sandbox can be switched between parent, reference and parent-plus-overlay by rewriting whole files (D4). `FileState` is a `StrEnum` (`parent`, `reference`, `parent_plus_overlay`) and `FileStates.switch_to(ctx, adapter, state)` is the one operation that moves the sandbox to a state, by calling `adapter.overlay` with the right files; every later task calls it. Deleted-at-reference files map to `None`; files added by the diff map to `None` when restoring the parent. A `git show` that fails (path absent at the sha, timeout, non-zero exit) is logged at ERROR and raised as `HarnessFailure`
- [ ] `grader_commands(tree)` per D11: `suite` always; `lint` only with `[tool.ruff]` or `ruff.toml`; `typecheck` only with `[tool.pyright]` or `pyrightconfig.json`. Nothing here runs them
- [ ] Tests `tests/benchmark/test_file_states.py` (a module-scoped sandbox of `sort_sets`; `network` marker)
  - [ ] `overlay` then `git status --porcelain` shows exactly the overlaid paths; `switch_to` parent → reference → parent leaves the tree byte-identical to the start; a path escaping the tree raises
  - [ ] After `switch_to(reference)`, `collect` includes the test file the diff added (its path is in the config JSON's `test_side_files`)
  - [ ] `EnvironmentIdentity.identity_digest` is unchanged across the switches (D4)
  - [ ] `grader_commands` for four trees: neither tool configured, ruff only, pyright only, both
  - [ ] Failure modes: a `FileStates` request for a path absent at the sha, and an overlay into a read-only directory, each raise `HarnessFailure` with an ERROR log (`caplog`)

**Commit**: `feat: add file states, overlay and grader commands`

### Task 16: Test-first check (D5)
- [ ] `src/squadron/benchmark/test_first.py`: `judge_parent_result(result: NodeResult) -> TestRejection | None` as an ordered rule list over `NodeOutcome` and `FailureKind`, first match wins:
  1. kind `collection_error` or `missing_symbol`, whatever the outcome → `uses_symbol_added_by_fix`
  2. outcome `error` (a setup or teardown failure) → `undecidable_failure_at_parent`
  3. outcome `passed` → `passes_at_parent`
  4. outcome `failed` with kind `assertion_failure` or `project_exception` → holds (`None`)
  5. anything else (`failed` with `other_exception`, `skipped`, `xfailed`, `xpassed`, `not_run`) → `undecidable_failure_at_parent`
- [ ] `run_test_first(adapter, ctx, node_ids, repeats)`: runs `run_suite(nodes(ids))` `repeats` times and returns per-node verdict plus per-run outcome and failure kind in `detail`. A node whose verdict differs across runs is `flaky`. A timeout or `SuiteRunError` raises `HarnessFailure` carrying the detail
- [ ] Tests `tests/benchmark/test_test_first.py`: every reachable `(outcome, kind)` pair, including `error` with `collection_error` and with `missing_symbol` (rule 1) and `error` with `assertion_failure` (rule 2); a new `NodeOutcome` or `FailureKind` value fails a test until the rules are reviewed; a scripted flaky sequence → `flaky`; scripted timeout and `SuiteRunError` each raise `HarnessFailure` with the detail and log at ERROR. Create the scenario `test_first` (the reference adds one test that calls a symbol the fix added, and one test whose assertion fails against the parent's behavior), then on its parent plus overlay in a real sandbox (`network` marker): the first gives `uses_symbol_added_by_fix`, the second holds

**Commit**: `feat: add test-first check for hidden tests`

### Task 17: Trace plugin, static references (D6)
- [ ] Trace mode, part 1: for each requested test, follow the globals named by the test function, its fixtures and test-side helpers (`co_names`, recursing through nested code objects), resolve them in `__globals__`, and record every project module, class or function reached as `references`. "Project" is a file under `tree`, outside `.venv`, and not in `test_side_files`. A reference to a project module object is kind `module`
- [ ] Add tests to `fixfair_project` for each: reference to an exported function, to an internal function, to a non-exported class, to a project module object, a fixture or helper that reaches an internal function, and a test that drives the CLI entry point by calling the script target
- [ ] Tests `tests/benchmark/test_trace_static.py` (harness pytest, no venv): each fixture test yields the expected reference set; nested code objects (a lambda or comprehension naming a project function) are followed

### Task 18: Trace plugin, dynamic crossings (D6)
- [ ] Trace mode, part 2: a `sys.setprofile` hook records each call whose immediate caller frame is test-side code and whose callee frame is project source, as `crossings` `(module, co_qualname, kind)` with `module` the callee frame's `f_globals["__name__"]`, only while the test's call phase runs (and its fixtures' setup), restoring any previous profiler. `kind` is `constructor` when the callee's `co_name` is `__init__` or `__new__`, `function` when the `co_qualname` has no class prefix, and `method` otherwise. The plugin also records `has_co_qualname`; an interpreter without it sets it false
- [ ] Tests `tests/benchmark/test_trace_crossings.py` (harness pytest, no venv; add the fixture tests to `fixfair_project`)
  - [ ] A test calling an exported function records one `function` crossing; a test calling an internal function records it
  - [ ] Constructing a class records one `constructor` crossing, and a method call on the instance records a `method` crossing; the two are distinct records
  - [ ] Dependency-invoked callback: a project function registered with `contextlib.ExitStack.callback` and run when the stack closes is **not** a crossing (the stdlib frame is its caller); the Typer-style case in the design is the same mechanism
  - [ ] Two tests in one run do not leak crossings into each other; a test that installs its own profiler does not break the run

**Commit**: `feat: add trace plugin references and crossings`

### Task 19: Trace plugin, patch interception (D7)
- [ ] Trace mode, part 3: wrap `unittest.mock._patch.__enter__` and `start`, and `pytest.MonkeyPatch.setattr`, `delattr`, `setitem`, `delitem`; resolve the owner object being modified and record `patches` `(api, owner_kind, owner_module, target)`. Unresolvable target strings are recorded with `owner_kind` `unresolved`. Wrappers are removed at session end. `patch.dict` and `patch.object` are covered by the same `_patch` wrapper
- [ ] Add tests to `fixfair_project` modeled on the real cases: `patch("fixpkg.mod.run")` after `from subprocess import run` in the project module (owner is the project module: project patch); `patch("subprocess.run")` and `monkeypatch.setenv`/`os.environ` patches (foreign, allowed); `patch.object` on a project class; `monkeypatch.setattr` on an instance of a project class; `patch.dict` on a project dict; `monkeypatch.delattr` on a project module attribute; `monkeypatch.setitem` and `monkeypatch.delitem` on a project dict; a target that does not resolve
- [ ] Tests `tests/benchmark/test_trace_patches.py` (harness pytest, no venv): one test per API and owner kind above, asserting the recorded facts; wrappers are restored after the run (assert on `_patch.__enter__` identity in a follow-up test)

**Commit**: `feat: add trace plugin patch interception`

### Task 20: Boundary resolver and `boundary` (D6)
- [ ] `pytest_trace/boundary_resolver.py` (plugin directory, shipped as package data): run under the parent's `.venv/bin/python`; reads `[project].name`, `[project.scripts]` and `[project.gui-scripts]` from `pyproject.toml`, finds the distribution's top-level packages with `importlib.metadata.packages_distributions()`, imports each, and prints JSON of allowed entries: each script target, and each top-level `__all__` name resolved to `(obj.__module__, obj.__qualname__)`. Only top-level `__all__` counts. A failure while importing a package is caught by the resolver itself (a documented process-boundary handler, so a broad `except` that prints the traceback to stderr is allowed there), which exits with the dedicated code `IMPORT_FAILURE_EXIT` (3, repeated as a constant on the harness side because the resolver cannot import harness code). Any other failure exits with Python's default code
- [ ] `PythonFixCaseAdapter.boundary(ctx)` runs it through `ctx.runner` with `replace_env=True` and the sandbox environment. Exit `IMPORT_FAILURE_EXIT` (the package would not import, D6) raises `BoundaryUndecidable` with stderr in the message. Any other non-zero exit (a bug in the resolver), a `ProcessTimedOutError`, or exit 0 with output that does not parse is logged at ERROR and raised as `HarnessFailure`. An empty allowed set is returned as empty (the caller rejects with `no_packaging_boundary`)
- [ ] Tests `tests/benchmark/test_python_boundary.py` (module-scoped sandbox of `fixfair_project`, `network` marker): the allowed set equals the expected exports and script target; `fixfair_no_boundary` (its own module-scoped sandbox) gives an empty set; `fixfair_bad_import` (same) raises `BoundaryUndecidable`; scripted runs with exit 1, a timeout and exit-0 garbage output each raise `HarnessFailure`

**Commit**: `feat: add packaging boundary resolver`

### Task 21: Trace verdict, `trace`, registry (D6, D7, D13)
- [ ] `trace_verdict.py`: pure `judge_trace(facts, allowed) -> FairnessVerdict` per D6 and D7:
  - [ ] a static reference, or a `function` or `constructor` crossing, not in `allowed` → `reaches_past_boundary` naming the symbol; for a `constructor` crossing the symbol checked is the class (`co_qualname` without its last segment); a `method` crossing is allowed
  - [ ] a static `module` reference, `has_co_qualname: false`, or an `unresolved` patch → `boundary_undecidable`
  - [ ] any `project_module`, `project_class` or `project_instance` patch → `patches_project_code` naming the target; `foreign` is allowed
  - [ ] precedence when several apply: `patches_project_code`, then `reaches_past_boundary`, then `boundary_undecidable`
- [ ] `PythonFixCaseAdapter.trace(ctx, node_ids, allowed)`: runs trace mode at the reference state with `node_ids` as pytest's positional arguments and applies `judge_trace` to each node's facts; a missing output file or `ProcessTimedOutError` is logged at ERROR and raised as `HarnessFailure`
- [ ] Extend 421's `registry.py` with `fix_case_adapter_for(language: SourceLanguage) -> FixCaseAdapter` (Python only; other languages raise the same named error as `adapter_for`); it stays the only importer of concrete adapters (D13)
- [ ] Tests
  - [ ] `tests/benchmark/test_trace_verdict.py` (pure): one case per bullet, a constructor crossing into a non-exported class versus a method crossing on an allowed instance, plus precedence
  - [ ] `tests/benchmark/test_python_trace.py` (module-scoped sandbox of `fixfair_project`, `network` marker): the test that calls the script target qualifies, a direct call to an internal function is `reaches_past_boundary` naming it, `patch("fixpkg.mod.run")` is `patches_project_code`; a scripted timeout and a missing output file each raise `HarnessFailure`
  - [ ] `tests/benchmark/test_fix_registry.py`: Python returns the adapter, every other `SourceLanguage` raises, `pyright` accepts it as a `FixCaseAdapter` (the adapter is complete only now)

**Commit**: `feat: add trace verdict, patch checks and fix-case registry`

### Task 22: Qualification pipeline, pre-sandbox stages (D1, D2, D3, D9, D10)
- [ ] `src/squadron/benchmark/qualify.py`: `qualify_candidate(candidate, deps) -> QualifyResult(record, reused)`; `deps` is one injected object holding the host, store, runner, adapters, the sandbox-stage function (`deps.sandbox_stages`, supplied by Task 23), repeats and timeouts (DIP; tests inject fakes). The function is a short sequence over stage functions (each under ~50 lines, split into `qualify_stages.py` if the file nears 300 lines)
- [ ] Stage 1: resolve the locator (`no_issue_host`), `get_issue`, `freeze_issue` with the fix commit's committer date. `IssueNotFoundError` → `issue_not_found`; `ReferenceIsPullRequestError` → `reference_is_pull_request`; `issue_edited_after_fix` from the freezer
- [ ] Stage 2: test for `pyproject.toml` at the parent with `git ls-tree --name-only <parent> -- pyproject.toml`: exit 0 with empty output means absent → `no_fix_case_adapter` (D13), while a non-zero exit is a failing git command (below). When present, read it with `git show`, then run `git diff --name-status parent..commit` and `classify_diff`
- [ ] Every outcome writes one `FixQualification` through one helper (`environment=None` before the sandbox). `case_build` (Task 26) uses the same helper for discovery rejections. A `MetrologyStoreError` from the write is logged at ERROR and raised as `BuildHalted` (a result that cannot be stored is lost)
- [ ] Harness failures: `CodeHostError` other than not-found, and a failing git command (`git remote`, `git ls-tree`, `git show`, `git diff`: timeout, not found or non-zero exit) → logged at ERROR with `logger.exception` and recorded as `harness_error` with the detail; a `harness_error` is never counted as a case-blaming reason. The one exception is `GitHubCliMissingError`: every later candidate would fail the same way, so it is logged at ERROR and raised as `BuildHalted` with no record
- [ ] Tests `tests/benchmark/test_qualify_pre_sandbox.py` with scripted host, runner and store
  - [ ] One test per rejection reached in these stages, asserting the record's rejection and `environment is None`; a parent with no `pyproject.toml` gives `no_fix_case_adapter`, not `harness_error`
  - [ ] `gh` timeout, unauthenticated host, a `git ls-tree` failure, a `git show` failure, a `git diff` failure and a `git remote` failure each produce `harness_error` with the detail and an ERROR log (`caplog`) and no rejection; `gh` missing raises `BuildHalted` and writes no record; a failing store write raises `BuildHalted` with an ERROR log
  - [ ] `deps.sandbox_stages` is not called for any pre-sandbox rejection

### Task 23: Qualification pipeline, sandbox stages (D4, D5, D6, D9, D10)
- [ ] `qualify_in_sandbox(candidate, classification, task_text, deps) -> QualifyResult`, the function Task 22's `deps.sandbox_stages` calls. Stage 3: build the one `BenchmarkSandbox` at the parent through the factory; `EnvironmentResolutionError` → `environment_unresolved` with the reason in `detail`. **Reuse check here** (the environment digest is only known now): an existing record for this project, commit and environment digest with the current `FAIRNESS_RULE_VERSION` and a non-`harness_error` outcome is returned unchanged with `reused=True`, and nothing further runs
- [ ] Stage 4, parent state: `collect` (`CollectionFailed` → `collection_failed`), then `boundary` (`BoundaryUndecidable` → `boundary_undecidable`; empty set → `no_packaging_boundary`)
- [ ] Stage 5, **reference state**: `FileStates.switch_to(..., reference)` (D4), `collect` again (`CollectionFailed` → `collection_failed`), `sort_tests`; no hidden candidates → `no_qualifying_hidden_test`; `trace` the hidden candidates while still in the reference state
- [ ] Stage 6, parent plus overlay: `FileStates.switch_to(..., parent_plus_overlay)`, `run_test_first` on the trace survivors; none survive → `no_qualifying_hidden_test`
- [ ] `HarnessFailure` or `ProcessTimedOutError` from any adapter, `FileStates` or suite call in stages 3–6 → `harness_error` with the detail, logged at ERROR. This is distinct from `BoundaryUndecidable`, which is a rejection. Per-test verdicts are collected in order (trace rejection first, then test-first) into `HiddenTestVerdict`s; the sandbox is removed after the candidate unless `keep` is set (the factory handles this)
- [ ] Tests `tests/benchmark/test_qualify_sandbox.py` with a scripted `FixCaseAdapter` and fake sandbox
  - [ ] Stage order and early exit: a rejection at stage N means no later adapter method is called (assert the call log). The call log shows `collect` at parent state, `collect` and `trace` at reference state, the test-first runs at parent plus overlay
  - [ ] `CollectionFailed` at the parent and at the reference each give `collection_failed`; `BoundaryUndecidable` gives `boundary_undecidable` and no `harness_error`
  - [ ] Reuse: a matching record skips every adapter method after sandbox creation and returns `reused=True`; a different rule version, a different environment digest, and a `harness_error` record each re-qualify
  - [ ] A `HarnessFailure` from `collect`, `boundary`, `trace`, a `FileStates` switch and a suite run, and a `SuiteRunError`, each yield `harness_error` with detail and an ERROR log

**Commit**: `feat: add qualification pipeline through test-first`

### Task 24: Qualification pipeline, repeats, exclusions, case build (D8, D9, D11)
- [ ] Stage 7, in `qualify_in_sandbox`: with at least one surviving hidden test, switch back to the reference state and run the full suite `benchmark.qualification_repeats` times. Hidden test differing across reference runs → `flaky`; failing every reference run → `fails_at_reference`; a non-hidden node differing across runs → `excluded_tests` with `flaky`; a non-hidden node failing every run → `excluded_tests` with `fails_at_reference`. Superseded tests are removed from the regression set but never excluded for failing. A `HarnessFailure`, `ProcessTimedOutError` or `SuiteRunError` from a stage 7 run → `harness_error` with the detail, logged at ERROR (the same rule as stages 3–6)
- [ ] Build the `BenchmarkCase` (`BenchmarkCase.build`) from the qualified hidden tests, hidden fixtures reached by them, superseded tests, sorted excluded tests, `adapter.grader_commands(parent_tree)` and the frozen `task_text`; provenance source ref is the issue reference. Write it with `write_case`; a `MetrologyStoreError` is logged at ERROR and raised as `BuildHalted`. No qualified hidden test → `no_qualifying_hidden_test` with per-test reasons kept in the record (D8). The record's `case_id` is set when qualified
- [ ] `qualification_for(case, environment, store) -> FixQualification | None` returns a record only when project, commit, environment digest and rule version match (D10). `qualify_candidate` is re-runnable by 424 with the sandbox it already holds
- [ ] Tests `tests/benchmark/test_qualify_repeats.py` with scripted suite results
  - [ ] Each of the four exclusion and hidden-flake rules; a test with differing outcomes across parent runs is `flaky`
  - [ ] A case built with a flaky non-hidden node has a different `case_id` from one built without it
  - [ ] A fix with one fair and one patching hidden test qualifies with one hidden test (D8) and the other's reason in the record
  - [ ] `qualification_for` returns the record on a full match and `None` for a different environment digest and for a bumped rule version
  - [ ] A scripted suite timeout and a `SuiteRunError` in a repeat each yield `harness_error` with detail and an ERROR log
  - [ ] A failing `write_case` raises `BuildHalted` with an ERROR log

**Commit**: `feat: add repeated qualification and case construction`

### Task 25: Real-fixture end-to-end qualification (success criteria)
- [ ] Create these scenarios in `fixfair_changes/` and test them in `tests/benchmark/test_qualify_end_to_end.py` (`network` marker, real sandbox, scripted host serving fixture issues, history from `fix_history`): a qualifying crash fix, a coupled test (direct internal call), a patching test, a test using a symbol added by the fix, a flaky test (using a state file in a temp dir), a conftest-changing fix, and a lockfile-changing fix
  - [ ] Each ends with the expected outcome and rejection; the qualifying one has the expected hidden node, task text and grader commands; the flaky node is on `excluded_tests`
  - [ ] Running the qualifying scenario twice runs no suite the second time (assert with a counting runner wrapper); bumping `FAIRNESS_RULE_VERSION` in the test re-qualifies
  - [ ] A fixture issue with a later comment gives the same `case_id` before and after the comment is added; an issue edited after the fix is `issue_edited_after_fix`

**Commit**: `test: add end-to-end fix qualification scenarios`

### Task 26: `case_build` and separability (D9, D12, D13)
- [ ] `src/squadron/benchmark/case_build.py`: `build_fix_cases(repo_root, set_name, commits, deps, on_candidate) -> BuildResult(project_id, records, case_set | None)`. It derives the `ProjectId`, picks adapters once through the registry (`adapter_for` and `fix_case_adapter_for`), runs `discover`, writes a record for each discovery rejection with Task 22's helper, qualifies each candidate (optionally limited to `commits`, matching by sha prefix; an unknown prefix raises), calls `on_candidate(line)` per candidate (`qualified case-… (n hidden)`, `reused` when `QualifyResult.reused`, or the rejection reason), and writes the case set from the qualified case ids. With zero qualified cases no case set is written and the result says so. A `MetrologyStoreError` from `write_case_set` is logged at ERROR and raised as `BuildHalted`; `BuildHalted` from any stage propagates
- [ ] `src/squadron/benchmark/separability.py`: `SIGNIFICANCE = 0.05`, `POWER = 0.80`; `minimum_detectable_difference(n, k)` and `cases_needed(target_difference, k)` per D12 using `statistics.NormalDist` for the z values; `n = 0` returns an explicit "no qualified cases" result, not a division error; `k` and `target` are validated
- [ ] Tests
  - [ ] `tests/benchmark/test_separability.py`: hand-computed values: k=3, target 0.20 needs 33 cases; n=33 gives MDD 0.199 (enough) and n=32 gives 0.202 (not enough); `n=0`; invalid inputs raise
  - [ ] `tests/benchmark/test_case_build.py` with a scripted host and a fake `deps.sandbox_stages` over `closing_commit_repo`: the store holds exactly one `FixQualification` per closing commit (discovery rejections and qualified, rejected and `harness_error` candidates alike), which is the success criterion; `--commit` limits the run; an unknown prefix raises; a second run reports `reused` for reused candidates and creates no new case-set version; zero qualified writes no set; `gh` missing raises `BuildHalted`; a failing `write_case_set` raises `BuildHalted` with an ERROR log

**Commit**: `feat: add fix-case build orchestration and separability bound`

### Task 27: Yield report (D12)
- [ ] `src/squadron/benchmark/yield_report.py`: `build_yield(records, case_sets, planned_samples, target_difference) -> YieldReport(rows, pooled, case_sets)` and renderers `render_text` and `render_json`. **Counting unit:** one candidate is one `(project, commit_sha)`, represented by its latest record by `created_at` whatever its environment digest or rule version; earlier records for that commit are ignored. Each `YieldRow` holds: project, candidates, qualified, rejected per `CandidateRejection`, `harness_error` count, per-`TestRejection` counts (one per hidden-test verdict of the `no_qualifying_hidden_test` candidates, not per candidate), and a separability line (n, MDD, answer, needed count) with the D12 assumption sentence beside it. The pooled row sums the rows. Grouping is by enum value, never by message text. JSON also lists every stored case set (name, version) containing a case id of the given projects
- [ ] A project with records but zero qualified cases still gets a row and a line saying no qualified cases (not an error); a project with no records is omitted
- [ ] Tests `tests/benchmark/test_yield_report.py`: counts from a synthetic record list equal hand counts; pooled row sums; test-rejection counts are per verdict; the text output matches the design's table layout (one exact-string snapshot); JSON round trips and names case set and version; zero-qualified row; a commit with a `pre` record and a later environment record counts once, as the later one

**Commit**: `feat: add yield report`

### Task 28: CLI commands (Data Flow, API Contracts)
- [ ] In `cli/commands/benchmark.py` register, the way 421 registers `sandbox`, `fix-cases build --set NAME [--repo PATH] [--commit SHA ...] [--keep]`, `fix-cases show COMMIT|CASE_ID`, `yield [--repo PATH ...] [--json]`. If `benchmark.py` would pass ~300 lines, put them in `cli/commands/benchmark_fix_cases.py` as a sub-app registered from `benchmark.py`. Concrete adapters are reached only through `registry.py`
  - [ ] `build`: sweeps benchmark orphans first (as 421's `sandbox` does), prints one line per candidate, then the yield report for this project; `--keep` is passed to the sandbox factory so sandboxes are kept; exit 0 whenever the run finished, 1 on `BuildHalted` or an unresolvable repository with the reason
  - [ ] `show`: `case-…` looks up by `case_id`; anything else is a commit prefix matched against the project's records (ambiguous prefix → exit 1 listing the matches). Prints the environment digest, each hidden test with verdict and detail, superseded and excluded tests with reasons, and the frozen task text. No record → exit 1
  - [ ] `yield`: no `--repo` reads every project with `fix_qualification` records; `--json` prints the report's JSON only
- [ ] `commands/sq/benchmark.md`: a slash command that runs `sq benchmark $ARGUMENTS`, in the form of `commands/sq/replay.md`, listing the three subcommands with their arguments (no interpretation, so output is identical to the CLI)
- [ ] Tests `tests/benchmark/test_fix_cases_cli.py` with the build function patched at its boundary: each command's output and exit codes, including `--commit` repeated, ambiguous prefix, missing record, `BuildHalted`, `--json`, and `--keep` (the factory receives keep set with the flag and unset without it); `tests/cli/test_command_surface.py` and `tests/cli/test_install_commands.py` pass, with the new command file covered wherever those tests enumerate command files
  - [ ] Success: tests pass; `sq benchmark --help` lists the new commands

**Commit**: `feat: add sq benchmark fix-cases and yield commands`

### Task 29: Real-commit fairness examples (design step 6, Functional Requirements)
- [ ] Discovery pins (`tests/benchmark/test_real_commit_verdicts.py`, `network` marker): on this repository 9fc4fc1c and d6535d62 are `multiple_closing_commits` (both close #291) and ebd45f3f is not a candidate. A commit absent from the clone fails the test with a message naming the sha and saying full history is required (CI checks out with `fetch-depth: 0`); a commit present with a different outcome fails too. There is no skip
- [ ] Fairness pins for those three: call `qualify_in_sandbox` directly with a hand-built `FixCandidate` (`issue_ref=None`) and a placeholder `task_text` for each, run through the real sandbox, and pin each hidden test's verdict and deciding symbol or patch target. The design expects ebd45f3f (the summary test patching an internal function by module path) and the #291 pipeline-mock tests to be disqualified by `patches_project_code`. If an observed verdict contradicts that, write `BLOCKED:` with the evidence under this task and stop for the PM
- [ ] Once, by hand (this step needs `gh` and the local store), run the full `sq benchmark fix-cases build --set fix-squadron` and select, with `fix-cases show`, one real example each: (a) a crash fix: the most recent qualified case whose parent-run detail records `project_exception`; (b) test-first: the most recent hidden verdict `uses_symbol_added_by_fix`, with the symbol in its detail; (c) boundary: the most recent hidden verdict `reaches_past_boundary`; (d) a qualified hidden test that drives `sq` through the CLI: the most recent qualified case whose hidden test source contains `CliRunner`; (e) test-first holding by assertion: the most recent qualified case whose parent-run detail records `assertion_failure`. If any of (a)–(e) has no instance, write `BLOCKED:` with the per-candidate evidence under this task and stop for the PM
- [ ] Pin (a)–(e) in the same test file. Each pin names its commit sha and calls `qualify_in_sandbox` directly with a hand-built candidate (`issue_ref=None`, a placeholder `task_text`, a temporary store), so no `gh` call and no read of the local store is needed and the tests run under CI's plain `uv run pytest`. Each asserts `outcome`, rejection and the deciding symbol or patch target in the hidden verdict, with the same missing-commit failure
  - [ ] Success: tests pass against this repository's history; verdict details are recorded in the DEVLOG entry

**Commit**: `test: pin real squadron fix commits against the fairness rules`

### Task 30: Verification walkthrough (design Verification Walkthrough)
- [ ] Run the design's steps 1 to 6 and note each result in the DEVLOG entry
  - [ ] Step 1: candidate count versus the grep; commits with several closing lines show as `multiple_issues_closed` in `show`
  - [ ] Steps 2 and 3: a rejection and a qualification via `show`; the frozen text of one case against `gh issue view <n> --comments` and the commit's committer date
  - [ ] Step 4: a rerun installs; every candidate that reached the sandbox stage prints `reused`, and every candidate rejected earlier prints the same rejection reason as the first run. Task 25 is the proof that no suite runs. Note in the DEVLOG that the design's "every line says `reused`" is not met (Context Summary gap 5)
  - [ ] Step 5: take the first project in `cf project list` order, other than squadron, that is a uv Python project with a `uv.lock` and a GitHub remote; build with `--repo`, then `yield --repo . --repo <path>`. If none exists, write `BLOCKED:` with `cf project list` output under this task and stop. Record both separability answers and the order decision they imply (423 → 424 → 425, or pool, or 426 earlier) in the DEVLOG
  - [ ] Step 6: `yield --json` shows the case-set name and version, and the rerun created no new version

### Task 31: Final validation, design correction, CHANGELOG, DEVLOG
- [ ] Run `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean; existing tests unmodified except where a task above named an edit
- [ ] Confirm no source file exceeds ~300 lines (`python_fairness.py`, `qualify.py`, `cli/commands/benchmark.py` are the likeliest; split by concern if so)
- [ ] Correct the slice design's interfaces and decisions to match what was built: Context Summary gaps 1–3 (API Contracts, Component Structure), the added modules and names (`build_errors.py`, `diff_classify.py`, `test_first.py`, `trace_verdict.py`, `file_states.py`, `qualify_in_sandbox`, `QualifyResult`, `IssueNotFoundError`, `ReferenceIsPullRequestError`, `HarnessFailure`, `BuildHalted`, `CollectionFailed`), the `store` argument that `qualification_for` gains (Task 24; 424 consumes it), and two definitions the design lacks: the yield counting unit (Task 27) and the reference and crossing kinds with the constructor rule (Tasks 17, 18). Do **not** edit Success Criteria or the Verification Walkthrough
  - [ ] Success: the design names `lockfile_names`, `is_test_source`, the `pyproject_text` argument, the `allowed` parameter of `trace`, one verdict type, the `store` argument of `qualification_for`, and the two definitions
- [ ] CHANGELOG: one short user-facing bullet each for `sq benchmark fix-cases build|show`, `sq benchmark yield` and `/sq:benchmark`
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, verification results, both yield answers, Context Summary gaps 4 and 5 as deviations from the approved Success Criteria and Walkthrough awaiting the Project Manager's decision, next: 423); mark the slice design `status: complete` and tick its slice-plan entry when all tasks are complete
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked, including dropped items marked `[x]` with a note
- [ ] Before the commit run `git status`. Stage this slice's files by path, and stage `DEVLOG.md` with `git add -p` if it holds changes this slice did not make, so unrelated changes stay out of the commit

**Commit**: `feat: complete fix case qualification and yield report slice`
