---
docType: tasks
slice: slice-ranges-and-rollup-reports
project: squadron
lld: user/slices/403-slice.slice-ranges-and-rollup-reports.md
dependencies:
- 400
- 401
- 402
- 323
projectState: 0.24.6 released; slices 400, 401 and 402 complete on main; slice 403
  design complete, all decisions decided
dateCreated: 20261027
dateUpdated: 20261028
status: not_started
turns: 18
promptTokens: 1221616
cachedTokens: 1135903
cacheWriteTokens: 85679
completionTokens: 23129
durationSeconds: 223.6
costUsd: 1.375634
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-opus-5-5:
    rounds: 1
    costUsd: 1.3756339999999996
    completionTokens: 23129
---

# Tasks: Slice Ranges and Rollup Reports

## Context Summary
- Slice 403 answers "did this slice make the code better?". It adds durable slice-range records (a slice's landings on the target, resolved from git topology or the reflog and stored the first time they resolve), commit export (`git archive` any commit to a temp directory and measure it there with the live checkout's tools), and three reports under `sq metrology report`: `slice`, `project` and `history`.
- All decisions live in the slice design (the `lld` above), D1–D10. Each task cites its decision. Read the cited decision before starting the task. The module table is under Architecture → Component Structure, the three flows and the failure-mode table are under Data Flow, and the record schema is under Database / Storage Schema.
- Prerequisites on `main` (all complete): 400's snapshot pipeline (`metrology/snapshot/`), 401's complexity, duplication and coverage adapters, 402's `CodeReviewRecord`, `ReviewCategory` (`core/finding_categories.py`) and `MetrologyStore.list_code_reviews`, and 323's `baseline_report` (`metrology/audit_report.py`), `compute_delta` and `is_within_floor` (`metrology/audit_delta.py`).
- **Decision recorded at task breakdown (refines D2 and Interfaces Required).** The existing helpers `_find_slice_branch` and `_resolve_fork_point` return `None` both when git fails and when nothing is found, and `_search_merge_commit` returns only the newest merge (`-1`). The resolver needs every landing and must tell a failed git call (`GIT_ERROR`) from an answer. So the resolver calls `run_git` itself, and `git_utils` gains only the shared pieces it needs: `slice_merge_grep_pattern(n)`, `parse_slice_branch(stdout)` and `parse_fork_point(reflog_stdout)`. The three private helpers call these and keep their names and behavior. No `first_parent` argument is added, because no caller would use it. `sq review code` is unchanged.
- **Coverage at an export.** `read_coverage` reads `metrology.coverage_report` with `cwd=repo_root`, so at an export it's absent (`coverage_not_configured` or `report_missing`) and never reaches its `git ls-files` call. Squadron sets no `metrology.coverage_report`, so in place and export agree. The in-place-equals-export test uses a fixture with coverage not configured.
- Contract changes: `AdapterContext.environment_root` (required, no default) is the only adapter contract change. `take_snapshot`'s signature doesn't change. `schema_version` stays 1. `sq review code`'s range resolution doesn't change.
- Branch: `403-slice.slice-ranges-and-rollup-reports`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`.
- New modules stay at ~300 lines or less. `store.py` is already 560 lines: add only the two methods and the id function there. Live runs (the walkthrough) are pre-authorized. No test uses the user store.
- Next slices: 404 (adoption baseline, deferred) and 420 (consumes `take_snapshot_at` and `get_slice_ranges`).

## Task 1: Slice branch — Effort 1
- [ ] Create `403-slice.slice-ranges-and-rollup-reports` from the target
- [ ] Success: `git branch --show-current` prints the slice branch

## Task 2: Shared slice-lookup pieces in `git_utils` (D2) — Effort 2
- [ ] In `src/squadron/review/git_utils.py`, add `slice_merge_grep_pattern(slice_number: int) -> str` returning the ERE now built inline in `_search_merge_commit`. `_search_merge_commit` calls it
- [ ] Add `parse_slice_branch(stdout: str) -> str | None` (the `git branch --list` line parsing now in `_find_slice_branch`) and `parse_fork_point(reflog_stdout: str) -> str | None` (the "branch: Created from" scan now in `_resolve_fork_point`). The two private helpers call them
- [ ] Each new function gets a docstring. Behavior of the three private helpers is unchanged
- [ ] Success: `tests/review/test_git_utils.py` and `tests/pipeline/test_code_pipelines_branching.py` pass with no edits

## Task 3: `git_utils` piece tests — Effort 1
- [ ] In `tests/review/test_git_utils.py`: `slice_merge_grep_pattern(303)` matches "Merge slice 303: x" and "303-slice.foo" and not "slice 3033"; `parse_slice_branch` handles a `* ` current-branch prefix and empty output; `parse_fork_point` returns the "Created from" sha and ignores "Reset to" and checkout entries
- [ ] Success: tests pass
- [ ] Commit: `refactor(review): extract slice merge pattern and reflog parsing helpers`

## Task 4: Slice-range models (D1, Storage Schema) — Effort 2
- [ ] Create `src/squadron/metrology/slice_range_models.py` with `LandingMethod(StrEnum)` (`merge_commit`, `fast_forward`), `RangeUnresolvedReason(StrEnum)` (`no_landing`, `not_landed`, `landed_elsewhere`, `reflog_unavailable`, `empty_branch`, `fork_not_ancestor`, `git_error`), `SliceLanding` and `SliceRanges`, fields as in the design's Storage Schema
- [ ] `SliceRanges` validator rejects an empty landing list, a duplicate `after_sha` within one slice, and a `merge_sha` that doesn't match `method` (required for `merge_commit`, `None` for `fast_forward`). Each error names the slice and the field
- [ ] Add `RECORD_TYPE_SLICE_RANGES = "slice_ranges"` beside the other record types in `metrology/models.py`, and `slice_ranges: SliceRanges | None = None` on `MetrologyRecord`. Follow how `code_review` was added by 402
- [ ] Success: pyright clean; `tests/metrology/test_models.py` passes unchanged

## Task 5: Slice-range model tests — Effort 2
- [ ] Create `tests/metrology/test_slice_range_models.py`: each validator rejection; a valid two-landing slice round-trips through `model_dump_json` / `model_validate_json`; `slices` keys survive JSON as `int`
- [ ] Back-compat: an existing stored record JSON of each existing record type (no `slice_ranges` key) loads unchanged, with `slice_ranges` `None` and `schema_version` 1
- [ ] Success: tests pass

## Task 6: Store methods (State Management, Patterns) — Effort 2
- [ ] In `metrology/store.py`, add `slice_ranges_record_id(project_id) -> str` returning `sliceranges-{sha256(project_id.value)[:12]}`, `write_slice_ranges(ranges: SliceRanges) -> str` (replace-by-id, through the existing `_write_atomic`, following `write_snapshot`), and `get_slice_ranges(project_id) -> SliceRanges | None`
- [ ] `get_slice_ranges` reads the one record by id. A missing file is `None`. An unreadable record raises `MetrologyStoreError` naming the path (a corrupt range record is never treated as empty)
- [ ] Success: pyright clean

## Task 7: Store tests — Effort 1
- [ ] Add `tests/metrology/test_slice_ranges_store.py` using the existing store fixture (no user store): write then get round-trips; a second write replaces the first (one file on disk); a missing record is `None`; a corrupt file raises `MetrologyStoreError`
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): add slice_ranges record type and store methods`

## Task 8: Throwaway-repo fixtures for the resolver (test infrastructure) — Effort 3
- [ ] Create `tests/metrology/slice_range_repos.py` with builders on `tmp_path`, using `tests.conftest.run_test_git`, one function per shape. Each returns the repo path and a named-tuple of the shas the tests assert on:
  1. `no_ff_landing`: slice `401-slice.x` forked from `main`, `main` moves, `--no-ff` merge with message "Merge slice 401: x"
  2. `fast_forward_landing`: branch created with `git checkout -b`, fast-forwarded into `main`
  3. `sync_merge`: `main` merged into the slice branch (message naming the slice branch), then a `--no-ff` landing
  4. `two_landings`: two `--no-ff` merges of the same slice on `main`
  5. `rebased_branch`: the branch is rebased after creation, so the reflog fork isn't an ancestor of the tip
  6. `empty_branch`: branch created and fast-forward "merged" with no commits
  7. `landed_elsewhere`: slice merged into a side branch, which is then merged into `main`
  8. `not_landed`: branch with commits, never merged
- [ ] Add a helper that `git clone`s a fixture repo to a second `tmp_path` directory (no local slice branches in the clone)
- [ ] Success: each builder runs, and a smoke test per builder asserts `git log --oneline` length

## Task 9: Resolver — merge-commit path (D2, D3, Data Flow) — Effort 3
- [ ] Create `src/squadron/metrology/slice_range.py` with `resolve_slice_landings(index, repo_root, target) -> list[SliceLanding] | RangeUnresolvedReason`
- [ ] Merge path: `run_git(["log", "--merges", "--first-parent", "--reverse", "--format=%H", "-E", f"--grep={slice_merge_grep_pattern(index)}", target])`. For each M: `before = M^1`, `after = M`, `tip = M^2`, `fork = merge-base(M^1, M^2)`, `merge_sha = M`, `method = merge_commit`, `target_ref = target`, `resolved_at` = now (UTC)
- [ ] Any `run_git` returning `None` or a non-zero exit returns `GIT_ERROR` immediately and logs WARNING naming the slice and the git call. No later path is tried
- [ ] No fallback to `main`. When no merge is found, fall through to the fast-forward path (Task 11)
- [ ] Success: pyright clean

## Task 10: Merge-path tests (criteria 1, 3) — Effort 2
- [ ] In `tests/metrology/test_slice_range.py`: `no_ff_landing` resolves one landing with the expected before, after, tip, fork and merge shas; the same in its fresh clone; `sync_merge` yields exactly one landing (the sync merge is never taken); `two_landings` yields two, oldest first
- [ ] A faked `run_git` returning `None` for the merge search returns `GIT_ERROR` and `caplog` has the WARNING naming the slice and call
- [ ] Success: tests pass

## Task 11: Resolver — fast-forward path and reasons (D2, Data Flow) — Effort 3
- [ ] When no merge landing exists, follow the Data Flow ladder in order, each step through `run_git` and the Task 2 parsers:
  1. `git branch --list <index>-slice.*` → `parse_slice_branch`; none → `NO_LANDING`
  2. tip contained in target (`merge-base --is-ancestor tip target`; exit 1 is "no", not an error) → else `NOT_LANDED`
  3. tip on the target's first-parent line (`rev-list --first-parent target` contains tip) → else `LANDED_ELSEWHERE`
  4. `reflog show --format=%H %gs <branch>` → `parse_fork_point`; none → `REFLOG_UNAVAILABLE`
  5. fork == tip → `EMPTY_BRANCH`
  6. fork not an ancestor of tip → `FORK_NOT_ANCESTOR`
  7. else one landing: `method = fast_forward`, `before = fork`, `after = tip`, `merge_sha = None`
- [ ] A `None` result at any step is `GIT_ERROR` (WARNING), never one of the other reasons. Reasons git answered log one INFO line naming the slice and reason
- [ ] Success: pyright clean; module under ~300 lines

## Task 12: Fast-forward path tests (criterion 2, Technical Requirements) — Effort 2
- [ ] `fast_forward_landing` resolves one `fast_forward` landing; `rebased_branch` → `FORK_NOT_ANCESTOR`; `empty_branch` → `EMPTY_BRANCH`; `landed_elsewhere` → `LANDED_ELSEWHERE`; `not_landed` → `NOT_LANDED`; a repo with no slice branch and no merge → `NO_LANDING`; `fast_forward_landing` after `git reflog expire --expire=now --all` → `REFLOG_UNAVAILABLE`
- [ ] Each reason's INFO line is asserted with `caplog`. A faked `run_git` returning `None` at the reflog step returns `GIT_ERROR` with the WARNING
- [ ] Success: tests pass

## Task 13: `record_slice_ranges` (D1, D4, concurrent-write row) — Effort 3
- [ ] In `slice_range.py`, add `record_slice_ranges(indices, repo_root, target, store, project_id)` returning a per-slice result (landings with a `new` flag, or the reason). It reads `get_slice_ranges` once at the start
- [ ] Per slice: merged = stored landings ∪ resolved landings, keyed on `after_sha`; stored landings are never changed. An unresolved reason adds nothing. `GIT_ERROR` persists nothing for that slice
- [ ] If any slice gained a landing: re-read the record, merge the new landings into that fresh copy, log WARNING naming the record if the fresh copy differs from the start read, then call `write_slice_ranges` once. No new landing → no write
- [ ] A slice with stored landings but an unresolved resolution keeps its stored landings and reports them (a fast-forward whose reflog expired)
- [ ] Success: pyright clean

## Task 14: `record_slice_ranges` tests (criteria 2, 3) — Effort 2
- [ ] Persist `fast_forward_landing`, delete the branch and expire the reflog, run again: still resolves from the store, no write
- [ ] A second run with no new landings doesn't write (assert file mtime or a spy store). A stored range plus one new merge gains exactly that landing, and the stored landing is byte-identical
- [ ] Concurrent write: a store fake whose second read returns an extra landing → both runs' landings kept, WARNING asserted
- [ ] `GIT_ERROR` for one of two slices: the other is persisted, the failing one isn't
- [ ] Success: tests pass

## Task 15: `slice-ranges` command (D4, D10, API Contracts) — Effort 2
- [ ] Create `src/squadron/cli/commands/metrology_quality.py` with `register_quality_commands(metrology_app, report_app)`, following `metrology_snapshot.py`'s mounting pattern. Call it from `cli/commands/metrology.py`
- [ ] `sq metrology slice-ranges INDEX... [--cwd DIR] [--json]`: target from `resolve_diff_base`, project id from `derive_project_id`, store from `resolve_store_dir`. One line per slice in the API Contracts form (`(new)` when a landing was added), then the record's path
- [ ] Exit 0 when every slice resolved or was unresolved for a reason git answered. Exit 1 on `GIT_ERROR` or a store error, with the message on stderr
- [ ] Success: `sq metrology slice-ranges --help` lists the options

## Task 16: `slice-ranges` CLI tests — Effort 1
- [ ] In `tests/metrology/test_quality_cli.py` with `CliRunner` and a temp store dir: resolved line, unresolved line, `(new)` only on the first run, `--json` parses, exit 1 on `GIT_ERROR`
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): resolve and persist slice ranges`

## Task 17: Split `read_snapshot_config` out of `preflight` (D4, D5) — Effort 2
- [ ] In `metrology/snapshot/preflight.py`, add `read_snapshot_config(repo_root) -> SnapshotConfig` returning limits, exclusions and tool timeout, with no clean-tree or HEAD check. `preflight` calls it and its result and errors are unchanged
- [ ] Success: `tests/metrology/snapshot/test_preflight.py` passes unchanged

## Task 18: `read_snapshot_config` tests — Effort 1
- [ ] In `test_preflight.py`: on a dirty tree `read_snapshot_config` returns the config while `preflight` still refuses; an invalid limit raises the same `SnapshotPreflightError` as `preflight`
- [ ] Success: tests pass
- [ ] Commit: `refactor(metrology): split snapshot config reading from preflight`

## Task 19: `environment_root` in the contract (D5) — Effort 2
- [ ] Add `environment_root: Path` (required, no default) to `AdapterContext` in `snapshot/contract.py`. Add the rule to the `LanguageAdapter` docstring: tools and environments come from `environment_root`, sources, rule-set configs and the lockfile identity from `repo_root`, and tools run with `cwd=repo_root`
- [ ] `take.py` passes `environment_root=repo_root` for in-place snapshots. Update every other `AdapterContext(...)` construction in `src/` and `tests/` (grep for it)
- [ ] Success: pyright clean; the full `tests/metrology/snapshot/` suite passes

## Task 20: Python lint resolves ruff from `environment_root` (D5) — Effort 1
- [ ] In `python_lint.py`, `resolve_tool` takes `ctx.environment_root`. `resolve_ruff_rule_set` and `repo_relative` keep `ctx.repo_root`
- [ ] Success: `test_python_lint.py` passes

## Task 21: Python types resolve uv, venv and pyright from `environment_root` (D5) — Effort 2
- [ ] In `python_types.py`: the `.venv` check, `uv` resolution, the `uv sync --check` run (`cwd=environment_root`), the interpreter probe and `resolve_tool` for pyright use `ctx.environment_root`. The lockfile hash, `resolve_pyright_rule_set` and the pyright run (`cwd=repo_root`) use `ctx.repo_root`
- [ ] Pass `--pythonpath <environment_root>/.venv/bin/python` to pyright
- [ ] Success: `test_python_types.py` passes (update only assertions on the argv for `--pythonpath`)

## Task 22: ESLint resolves from `environment_root` (D5) — Effort 1
- [ ] In `typescript_lint.py`, `resolve_tool` takes `ctx.environment_root`. `resolve_eslint_rule_set` and report parsing keep `ctx.repo_root`
- [ ] Success: `test_typescript_lint.py` passes

## Task 23: Adapter `environment_root` tests — Effort 2
- [ ] One test per adapter module (ruff, pyright, ESLint) with `repo_root` and `environment_root` set to different `tmp_path` dirs and a recording fake runner: the tool path is under `environment_root`, the run's `cwd` is `repo_root`, and the rule-set source is read from `repo_root`
- [ ] Success: tests pass; the full `tests/metrology/` suite passes
- [ ] Commit: `feat(metrology): resolve snapshot tools from environment_root`

## Task 24: Commit export (D5, Commit export flow, failure modes) — Effort 3
- [ ] Add `SnapshotExportError(MetrologyError)` to `metrology/errors.py`. Each message names the failing call or path and the fix
- [ ] Create `src/squadron/metrology/snapshot/export.py` with a context manager `export_commit(repo_root, sha, exclusions, environment_root)` yielding the export tree path and its file list:
  1. `TemporaryDirectory`; `git archive --format=tar -o <tmp>/export.tar <sha> -- . <:(exclude,glob)pattern per exclusion>` through `run_git`. `None` (including the 30 s timeout) or non-zero → `SnapshotExportError` naming the call, and the timeout when that's the cause
  2. extract with `tarfile` `filter="data"` into `<tmp>/tree`. A refused member → `SnapshotExportError` naming the member. Any `OSError` → `SnapshotExportError` naming the path and the OS error
  3. files = the archive's regular-file member names, sorted
  4. when `<environment_root>/node_modules` exists, symlink `<tmp>/tree/node_modules` to it. Failure → `SnapshotExportError`
- [ ] Every error logs at ERROR, and the temp directory is removed on every path
- [ ] Add `resolve_commit(repo_root, rev) -> str` (`rev-parse --verify <rev>^{commit}`). An unknown revision → `SnapshotExportError` naming it
- [ ] Success: pyright clean; module under ~300 lines

## Task 25: Export tests (criterion 4, Technical Requirements) — Effort 3
- [ ] In `tests/metrology/snapshot/test_export.py`, using the snapshot `conftest.py` repo factory:
  1. export of a commit lists exactly that commit's tracked files minus exclusions
  2. the repo's `.git` listing (paths, sizes, mtimes) and `git status --porcelain` are identical before and after
  3. the temp directory is gone after a normal exit and after an exception inside the `with` block
  4. a tar containing a link outside the tree (fake `run_git` writing a crafted tar) → `SnapshotExportError` naming the member
  5. unknown revision → `SnapshotExportError`
  6. `run_git` returning `None` for `archive` → `SnapshotExportError` naming the timeout, temp directory removed
  7. extraction `OSError` (monkeypatched `tarfile` extract) → `SnapshotExportError`, temp directory removed
  8. `node_modules` symlink present only when the live one exists
- [ ] Each error case asserts its ERROR record with `caplog`
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): export a commit to a temp tree for measurement`

## Task 26: Lockfile gate at an export (D6) — Effort 2
- [ ] In `python_types.py`, when `repo_root != environment_root`: compare SHA-256 of `<repo_root>/uv.lock` and `<environment_root>/uv.lock`. Different, or the export has none → absent `environment_unresolved` with detail `uv.lock at <sha12> differs from the live environment's` (or the missing-lockfile reason). Equal → run the existing D7 check against `environment_root`
- [ ] Success: pyright clean

## Task 27: Lockfile gate tests (criterion 6) — Effort 1
- [ ] In `test_python_types.py`: different lockfiles → absent with the detail; equal lockfiles → the D7 path runs (fake runner); in place (`repo_root == environment_root`) is unchanged
- [ ] Success: tests pass

## Task 28: `take_snapshot_at` (D5, Commit export flow) — Effort 2
- [ ] In `snapshot/take.py`, add `take_snapshot_at(repo_root, commit, registry, runner, store) -> CodeSnapshot`: `resolve_commit`, `read_snapshot_config(repo_root)`, effective exclusions as `take_snapshot` computes them, `export_commit`, `AdapterContext(repo_root=<export tree>, environment_root=repo_root, ...)`, the shared `_measure_all`, `CodeSnapshot(commit_sha=sha)`, `store.write_snapshot`
- [ ] No clean-tree check on the live checkout. Project id from the live `repo_root`
- [ ] Success: pyright clean; `take.py` under ~300 lines

## Task 29: `take_snapshot_at` tests (criteria 4, 5, D5 conformance) — Effort 3
- [ ] In-place equals export: on a clean fixture repo with coverage not configured, `take_snapshot` and `take_snapshot_at(HEAD)` serialize identically apart from `measured_at`
- [ ] Conformance: for every adapter in `default_registry()`, on an export of a tree with no `.venv` or `node_modules` and the live tools available, every metric the adapter measures in place is present, or absent for a reason other than `tool_missing`. Skip with a stated reason when the live tools aren't installed
- [ ] An older commit writes a record keyed on that sha. A tool failure inside the export is absent `tool_failed`, as in 400
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): measure any commit with take_snapshot_at`

## Task 30: `snapshot --commit REV` (D10, API Contracts) — Effort 1
- [ ] In `cli/commands/metrology_snapshot.py`, add `--commit REV`. With it, call `take_snapshot_at` and print `(exported)` after the commit. `SnapshotExportError` → stderr, exit 1. Without it, behavior is unchanged
- [ ] Add tests to `test_snapshot_cli.py`: `--commit HEAD` output has `(exported)`; an unknown revision exits 1; the existing tests pass unchanged
- [ ] Success: tests pass
- [ ] Commit: `feat(cli): add --commit to sq metrology snapshot`

## Task 31: Report models (D7, D8, D9) — Effort 2
- [ ] Create `src/squadron/metrology/quality_report/__init__.py` and `models.py` with `ComparabilityBreak(StrEnum)` (`tool_changed`, `rule_set_changed`, `environment_changed`, `settings_changed`, `absent_before`, `absent_after`), `MetricComparison`, `AuditSection`, `ReviewSection`, `LandingReport`, `SliceReport`, `ProjectReport`, `HistoryReport`
- [ ] `MetricComparison` holds language, metric, before and after figures with n, a delta only when comparable, the breaks with detail and fix text. `AuditSection` holds the delta or a "missing run at <sha>" state and the floor state (within, beyond, no floor measured) with `n_runs`. `ReviewSection` holds n files, n findings, write-time and read-side-mapped totals, per-category counts with review-scale severity, raw strings for `other`, the `other` share, and the `no floor measured` marker
- [ ] No field combines sources or metrics
- [ ] Success: pyright clean

## Task 32: Report model tests (criterion 9) — Effort 1
- [ ] In `tests/metrology/test_quality_report_models.py`: build one of each report and assert no key anywhere in its serialized JSON contains `score` (follow `audit_report`'s precedent test)
- [ ] Success: tests pass

## Task 33: `compare_snapshots` (D7) — Effort 3
- [ ] Create `quality_report/compare.py` with `compare_snapshots(before, after) -> list[MetricComparison]`, one row per (language, metric) in either snapshot
- [ ] A row is diffed only when both are present and tool (name, version, counting), rule set (source, hash) and environment (lockfile hash, interpreter) are equal. Otherwise it carries every applicable break, with the absence reason for `absent_*`, and the fix text where one exists (`re-measure both with sq metrology snapshot --commit <sha>` for a tool change)
- [ ] Differing `exclusions` or `limits` mark every row `settings_changed` with a detail naming which differs
- [ ] Success: pyright clean

## Task 34: `compare_snapshots` tests (criterion 7) — Effort 2
- [ ] In `tests/metrology/test_quality_compare.py` with snapshot builders from `tests/metrology/snapshot/builders.py`: identical identity → delta; each of tool, rule set, environment changed → its break and no delta; absent before and after → the reason; different limits → every row `settings_changed` naming the limits; different exclusions → the same naming exclusions
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): compare snapshots per measurement with named breaks`

## Task 35: Review section (D8, D9) — Effort 2
- [ ] Create `quality_report/reviews.py` with `review_section(reviews: Sequence[CodeReviewRecord]) -> ReviewSection`, counting per `ReviewCategory`. A `None` category is counted as missing, never as `other`. Read-side-mapped findings are counted separately in the header. The `other` share is over write-time findings
- [ ] Add `split_by_attribution(reviews, resolved_indices) -> (slice_attributed, project_only)`: a review is slice-attributed only when its `slice_index` is in `resolved_indices`
- [ ] Tests in `tests/metrology/test_quality_reviews.py`: counts, write-time vs mapped totals, severity counts, `other` raw strings and share, `None` category, attribution split including `slice_index None`
- [ ] Success: tests pass

## Task 36: Slice report assembly (D3, D8, D9, Slice report flow) — Effort 3
- [ ] Create `quality_report/slice_report.py` with `ensure_snapshot(commit, repo_root, store, project_id, take_at) -> CodeSnapshot`: the newest stored snapshot at that commit, else log INFO naming the commit and call `take_at`
- [ ] `build_slice_report(index, record_result, store, project_id, commit_exists, ensure_snapshot) -> SliceReport`, all dependencies passed in:
  1. unresolved → report holds only the reason; no landings, no reviews
  2. per landing, oldest first: a boundary missing (`commit_exists` false) → that landing shows `commit <sha> not found`, WARNING naming the slice and commit, next landing
  3. before and after via `ensure_snapshot`, then `compare_snapshots`; header carries each boundary's limits and exclusions
  4. audit: latest run at `before_sha` and at `after_sha` under the same `audit_prompt_hash` → `compute_delta` and `is_within_floor`; otherwise state which is missing. Never run an audit
  5. reviews: `list_code_reviews(project_id)` filtered on `slice_index == index` → `review_section`
- [ ] A failing `ensure_snapshot` propagates: no half report
- [ ] Success: pyright clean; module under ~300 lines

## Task 37: Slice report tests (criteria 7, 8, 10, failure modes) — Effort 3
- [ ] In `tests/metrology/test_quality_slice_report.py` with a store fixture and a fake `ensure_snapshot`: two landings reported separately; a missing snapshot is taken (INFO asserted) and a stored one is reused; a landing whose commit is gone shows `not found` (WARNING asserted) and the other landing and the reviews still appear; audit with both runs → delta; audit with one missing → names it; unresolved slice → reason only; a failing `ensure_snapshot` raises
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): assemble the slice rollup report`

## Task 38: Project report (D9, API Contracts) — Effort 2
- [ ] Create `quality_report/project_report.py` with `build_project_report(store, project_id, resolved_indices) -> ProjectReport`: the latest snapshot's per-language, per-metric summary; the latest audit baseline with its floor from `baseline_report` (filtered to the project); reviews split by `split_by_attribution`
- [ ] Tests in `tests/metrology/test_quality_project_report.py`: an unresolved slice's reviews count as project-only; reviews with no `slice_index` are project-only; no snapshots or audits → the sections say so
- [ ] Success: tests pass

## Task 39: History report (API Contracts) — Effort 2
- [ ] Create `quality_report/history_report.py` with `build_history_report(store, project_id, first_parent_shas) -> HistoryReport`. The caller passes the target's first-parent commits (oldest first). One row per snapshotted commit on that line, with each metric's headline figure, and a break marker between adjacent rows that `compare_snapshots` finds not comparable. Snapshots of other commits are counted, not listed
- [ ] Tests in `tests/metrology/test_quality_history_report.py`: ordering follows the passed list, not `measured_at`; a tool change between rows inserts a break marker; off-line snapshots are counted
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): add project and history rollup reports`

## Task 40: Report rendering — Effort 2
- [ ] Create `quality_report/render.py` with one text renderer per report, following the API Contracts example layout (landing header, per-language rows with n, breaks as `not compared: <break> (<detail>)`, audit line, review section with `no floor measured`)
- [ ] Tests in `tests/metrology/test_quality_render.py`: each renderer's key lines for a built report, including a break line and an unresolved slice's reason line
- [ ] Success: tests pass

## Task 41: Report commands (D10, API Contracts) — Effort 2
- [ ] In `metrology_quality.py`, add `report slice INDEX`, `report project` and `report history`, each with `--cwd` and `--json` (`--json` prints the report model). `report slice` runs `record_slice_ranges` for its slice, then `build_slice_report` with the real `take_snapshot_at`, and its help text says it measures missing boundaries. `report history` gets the first-parent list with `run_git(["rev-list", "--first-parent", "--reverse", target])`; `None` → stderr, exit 1
- [ ] Update the `report` group help text in `metrology.py`, which describes only samples
- [ ] Keep `metrology_quality.py` under ~300 lines; move helpers out if it isn't
- [ ] Success: each command's `--help` renders

## Task 42: Report command tests — Effort 2
- [ ] In `test_quality_cli.py` with a temp store and fixture repos: `report slice` on an unresolved slice prints the reason; on a resolved slice with stored boundary snapshots prints the landing (no snapshot taken); `--json` parses for all three; a boundary snapshot failure exits 1. Help assertions check the command's options, not `--help` text styling
- [ ] `report baseline`, `audit delta`, `ingest-reviews` and plain `snapshot` tests pass unchanged
- [ ] Success: tests pass
- [ ] Commit: `feat(cli): add report slice, project and history`

## Task 43: Docs and CHANGELOG — Effort 1
- [ ] `docs/COMMANDS.md`: document `slice-ranges`, `snapshot --commit`, and `report slice|project|history`, including that `report slice` writes snapshots and ranges, that `slice-ranges` prints the record path (delete it to force re-resolution), and the export trust boundary (Special Considerations → Security)
- [ ] `CHANGELOG.md`: one short user-facing bullet under Unreleased
- [ ] Commit: `docs: document slice ranges, commit export and rollup reports`

## Task 44: Full validation — Effort 1
- [ ] `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors), and the full test suite pass
- [ ] `git diff <target> -- src/squadron/review/git_utils.py` shows only Task 2's additions and the helpers calling them
- [ ] Every new module is under ~300 lines (`wc -l`)
- [ ] Commit any fixes: `fix: address 403 validation findings`

## Task 45: Verification walkthrough (design → Verification Walkthrough) — Effort 2
- [ ] Run the eight walkthrough steps from the squadron root in order. For step 1's `squadron-brownfield` slice, pick one from `git log --merges --first-parent main --grep=squadron-brownfield` and the slice merges on that branch
- [ ] Step 3: the `diff` of the two snapshots minus `measured_at` prints nothing
- [ ] Step 4: `git status --porcelain` and `ls -la .git` are unchanged
- [ ] Step 6: restore `metrology.max_function_lines` to 50 and re-snapshot afterward
- [ ] Record each step's outcome (pass, or the actual output when it differs) in a `## Verification` section at the end of this file
- [ ] Success: every step passes, or a failing step is fixed (with its test) before checking it off
- [ ] Commit: `docs: record slice 403 verification walkthrough`
