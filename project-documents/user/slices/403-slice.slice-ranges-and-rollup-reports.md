---
docType: slice-design
slice: slice-ranges-and-rollup-reports
project: squadron
parent: ../architecture/400-slices.code-quality-measurement.md
dependencies:
- 400
- 401
- 402
interfaces:
- 420
dateCreated: 20261022
dateUpdated: 20261023
status: not_started
turns: 27
promptTokens: 2192201
cachedTokens: 2060306
cacheWriteTokens: 131847
completionTokens: 41158
durationSeconds: 415.5
costUsd: 2.290537
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Slice Ranges and Rollup Reports

## Overview

400 measures a clean HEAD. 402 puts code-review findings in the store with a category from the closed vocabulary. Nothing yet answers "did this slice make the code better?", because:

- A slice's commit range is resolved only for `sq review code`. The fork point is read from the branch reflog, which a fresh clone doesn't have and `git gc` expires.
- Only HEAD can be measured, so a slice's before and after can't be snapshotted after the fact.
- No report reads snapshots, audit runs and review records together.

This slice adds three things:

- **Durable slice ranges.** A slice's landings are resolved from git topology, or from the reflog while it lasts, and written to the store the first time they resolve.
- **Commit export.** `git archive` exports any commit to a temporary directory, and the 400 adapters measure it there.
- **Reports.** `sq metrology report slice`, `report project` and `report history` show breakdowns across snapshots, audit runs and review records. Missing boundary snapshots are taken on demand.

## Value

- **Developer value.** A slice's static before and after, its audit delta and its review findings by category appear in one breakdown, with sample sizes and comparability flags.
- **Durability.** A fast-forward slice's range survives reflog expiry once it has been resolved one time. A slice merged with a merge commit needs no reflog at all.
- **Architectural enablement.** 420 can measure a replay at any commit through commit export, and can find a slice's boundaries through the slice-range record.

## Technical Scope

**Included**
- The `slice_ranges` record type: one record per project, holding every slice's landings (D1). Store read and write methods.
- A structured range resolver. Merge-commit landings come from the target's first-parent history, and fast-forward landings come from the reflog through the existing `git_utils` helpers.
- `sq metrology slice-ranges INDEX...`: resolves and persists the named slices' ranges (D4).
- Commit export (`snapshot/export.py`) and `take_snapshot_at(commit)`. The snapshot command gains `--commit REV`.
- One contract field: `AdapterContext.environment_root`. Tools and environments are resolved there, and the measured tree is `repo_root` (D5).
- The type-count lockfile gate at an export (D6).
- A comparability module that decides, measurement by measurement, whether two snapshots can be diffed (D7).
- Three report commands under the existing `report` group: `slice`, `project` and `history`, each with `--json`.

**Excluded**
- Running audits or reviews from a report. Reports read audit runs and review records. They only take snapshots, which cost no LLM calls.
- A review noise floor. None is measured anywhere, so review figures say so (D8).
- Installing dependencies at an exported commit. Type counts there are absent unless the lockfile matches (Future Work in the slice plan).
- Recording ESLint's `node_modules` environment identity (#250, unchanged).
- Any composite score, gate or pipeline hook.
- Ranges for slices that landed on a branch other than the target and reached it through a later merge. Those are resolved from a checkout whose target is that branch (D2).
- A slice table in `report project`. No success criterion needs it.

## Dependencies

### Prerequisites
- **400 (complete):** `CodeSnapshot`, `Measurement` identity, `take_snapshot`, the adapter contract, `default_registry()`, `resolve_files`, preflight and `store.list_snapshots`.
- **402 (designed, not implemented):** `CodeReviewRecord`, `store.list_code_reviews` and `ReviewCategory`. 403 can't be implemented before 402 lands.
- **323 (complete):** `baseline_report`, `compute_delta` and `is_within_floor` for the audit section.
- **401 (designed, not implemented):** a prerequisite, so 401 is implemented before 403. The reports iterate over `SnapshotMetric`, so 401's metrics appear in them unchanged. 401 adds no tool-resolving code: complexity (`complexity.py`, `python_complexity.py`, `typescript_complexity.py`) and duplication (`duplication.py`) are counted in-process on the measured tree, and coverage (`coverage.py`) reads a report file located from `repo_root`. None of them moves to `environment_root`, and 403 changes none of them. At an export, `repo_root` is the export directory, so coverage is absent, as 401 states. The export conformance test (D5) covers 401's adapter code along with 400's.

### Interfaces Required
- `squadron.review.git_utils`: `run_git`, `resolve_diff_base` (the target), and the slice helpers `_find_slice_branch`, `_resolve_fork_point` and `_search_merge_commit`. The helpers are renamed to public names, and the slice-number grep pattern is moved into one module function that both the review resolver and this slice call (D2).
- 400's `preflight`, split so that config reading (limits, exclusions, timeout) can run without the clean-tree check (D4).
- `derive_project_id`, `MetrologyStore`, and the `MetrologyRecord` envelope.

## Architecture

### Component Structure

| Module | Responsibility |
|---|---|
| `metrology/slice_range_models.py` | `LandingMethod`, `SliceLanding`, `SliceRanges`, `RangeUnresolvedReason` |
| `metrology/slice_range.py` | `resolve_slice_landings(index, repo_root, target) -> list[SliceLanding] \| RangeUnresolvedReason`, `record_slice_ranges(...)` (merge new landings into the project's record and write it once) |
| `review/git_utils.py` | Helpers made public, `slice_merge_grep_pattern(n)`, and a `first_parent` argument on the merge search |
| `metrology/snapshot/export.py` | `export_commit(repo_root, sha, exclusions, environment_root)`, a context manager yielding the export directory and its file list |
| `metrology/snapshot/preflight.py` | `read_snapshot_config(repo_root)`, split out of `preflight` |
| `metrology/snapshot/take.py` | `take_snapshot_at(repo_root, commit, registry, runner, store)` beside `take_snapshot`, sharing `_measure_all` |
| `metrology/snapshot/contract.py` | `AdapterContext.environment_root` |
| `metrology/snapshot/python_types.py`, `typescript_lint.py`, `python_lint.py` | Resolve tools and the venv from `environment_root`, and sources and configs from `repo_root` |
| `metrology/quality_report/models.py` | Report models: `MetricComparison`, `ComparabilityBreak`, `AuditSection`, `ReviewSection`, `SliceReport`, `ProjectReport`, `HistoryReport` |
| `metrology/quality_report/compare.py` | `compare_snapshots(before, after) -> list[MetricComparison]` |
| `metrology/quality_report/reviews.py` | Review findings per `ReviewCategory`, with the write-time and read-side-mapped totals |
| `metrology/quality_report/slice_report.py` | Assembles the slice report. `ensure_snapshot(commit, ...)` reads the stored snapshot or takes one by export. No git and no store writes beyond what `ensure_snapshot` and `record_slice_ranges` do |
| `metrology/quality_report/project_report.py`, `history_report.py` | Assemble the other two reports from stored records only |
| `cli/commands/metrology_quality.py` | `report slice\|project\|history` and `slice-ranges`, mounted on `report_app` and `metrology_app` |
| `cli/commands/metrology_snapshot.py` | `--commit REV` |

The report assembly modules take the store, the resolver and `ensure_snapshot` as arguments, so tests pass fakes and no report module imports a concrete adapter.

### Data Flow

**Range resolution** (`slice-ranges`, and `report slice` before it reads):
```
target = resolve_diff_base(repo_root)            (git.integration_branch, or main)
stored = store.get_slice_ranges(project_id)           (one store scan per command, not per slice)
landings = merge-commit landings:
    git log --merges --first-parent --reverse --format=%H -E --grep=<slice pattern> <target>
    for each M: before = M^1, after = M, tip = M^2, fork = merge-base(M^1, M^2)
  none found → fast-forward landing:
    branch = <index>-slice.* (local)          none → NO_LANDING
    tip contained in target?                   no   → NOT_LANDED
    tip on target's first-parent line?         no   → LANDED_ELSEWHERE
    fork = reflog "branch: Created from"       none → REFLOG_UNAVAILABLE
    fork == tip                                     → EMPTY_BRANCH
    fork not an ancestor of tip                     → FORK_NOT_ANCESTOR
    before = fork, after = tip
per slice: merged = stored landings ∪ new landings (keyed on after_sha; stored ones never change)
           merged empty → the reason (INFO line), nothing added
any slice gained a landing → re-read the record, merge the new landings into that copy,
                             WARN if it differs from `stored`, then store.write_slice_ranges (one write)
a git call returning None → that slice is GIT_ERROR (WARNING), nothing persisted for it
```

**Commit export** (`snapshot --commit`, and `ensure_snapshot`):
```
sha = git rev-parse --verify <rev>^{commit}
config = read_snapshot_config(repo_root)                 (live checkout, no clean check)
exclusions = effective_exclusions(config, registry)
tmp = TemporaryDirectory()
git archive --format=tar -o tmp/export.tar <sha> -- . <exclude pathspecs>
extract with tarfile filter="data" → tmp/tree
files = the archive's member names (regular files)
link tmp/tree/node_modules → <live>/node_modules     (only when the live one exists)
AdapterContext(repo_root=tmp/tree, environment_root=<live>, ...)
_measure_all → CodeSnapshot(commit_sha=sha) → store.write_snapshot
tmp removed (also on error)
```

**Slice report:**
```
range = resolve + record (above)                    unresolved → reason only, nothing attributed
for each landing (oldest first):
    a boundary commit missing from the repo → that landing shows `commit <sha> not found`, next landing
    before = ensure_snapshot(landing.before_sha); after = ensure_snapshot(landing.after_sha)
    compare_snapshots(before, after) → static rows
    audit: baseline at before_sha, latest run at after_sha, same prompt hash → compute_delta
reviews: list_code_reviews(project) where slice_index == N → per-category counts
```

**Failure modes:**

| Failure | Handling | Signal |
|---|---|---|
| `git archive` or `rev-parse` returns `None` or non-zero | `SnapshotExportError` naming the call. Nothing is written and the temp directory is removed. | ERROR, exit 1 |
| `git archive` hangs | `run_git` kills it at `GIT_COMMAND_TIMEOUT_SECONDS` (30 s) and returns `None`: the row above, with the message naming the timeout | ERROR, exit 1 |
| Extraction fails (disk full, permissions, or any `OSError`), or the `node_modules` symlink can't be created | `SnapshotExportError` naming the path and the OS error. Extraction is in-process and not time-bounded, like 400's parse: it's linear in the archive's size | ERROR, exit 1 |
| An unknown revision is passed to `--commit` | `SnapshotExportError` naming the revision | ERROR, exit 1 |
| An archive member is refused by the `data` filter (absolute path, or a link outside the tree) | `SnapshotExportError` naming the member | ERROR, exit 1 |
| A tool hangs or fails inside the export | Unchanged from 400: absent `tool_failed`, bounded by `metrology.snapshot_tool_timeout_s` | WARNING |
| A boundary snapshot fails during `report slice` | The report stops with the error. A report never shows half a before and after. | exit 1 |
| The merge search or the reflog read returns `None` (a git hang, timeout or non-zero exit) | The resolver returns `GIT_ERROR` for that slice, naming the git call, and doesn't try the next path or the `NO_LANDING` and `REFLOG_UNAVAILABLE` conclusions: those mean git answered. Nothing is persisted. The reason is never treated as an empty range. | WARNING naming the slice and the call, and the reason in the output |
| A slice has no landing for a reason git answered (`NO_LANDING`, `NOT_LANDED`, `LANDED_ELSEWHERE`, `REFLOG_UNAVAILABLE`, `EMPTY_BRANCH`, `FORK_NOT_ANCESTOR`) | The reason is reported and nothing is persisted | INFO line per slice, and the reason in the output |
| A stored landing names a commit that no longer exists (rewritten history) | Checked with `git cat-file -e` before `ensure_snapshot`. That landing shows `commit <sha> not found`, with no before and after. Other landings and the reviews are still reported. The stored landing isn't deleted. | WARNING naming the slice and commit |
| Two commands write `slice_ranges` at once | Concurrent runs aren't supported, but a lost write is detected. Just before writing, the command re-reads the record and merges the new landings into that fresh copy. If the stored landings differ from what it read at the start, another run wrote in between: the merge still keeps both runs' landings, and a WARNING says so. The window left is the gap between the re-read and `_write_atomic`. | WARNING naming the project's record |
| Store write fails | `MetrologyStoreError` propagates, as in 400 | exit 1 |

### State Management

Two record types are written, both to the user-level store:

- `slice_ranges`: one record per project, holding each slice's landings. Landings are appended and never edited or removed. The id is `sliceranges-{sha256(project_id)[:12]}`.
- `code_snapshot`: written by commit export under 400's id and overwrite rules (400 D3).

Reports hold no state between runs. Because the store is user-level and keyed on `ProjectId` (the git remote), a range resolved in one checkout is read by a fresh clone of the same remote on the same machine.

## Technical Decisions

### D1 — A slice range is a list of landings, append-only
Status: decided
- A slice can land more than once. On squadron's `main`, slices 172, 305 and 940 each have two landing merges on the first-parent line, for example "merge: slice 940 code review follow-up fixes". Keeping only the newest landing would show the follow-up alone as the slice's effect.
- One record per project holds every slice's landings, following the coarse-records principle: a command reads it once and writes it at most once, however many slices it resolves.
- `SliceLanding`: `method` (`merge_commit` or `fast_forward`), `target_ref`, `before_sha`, `after_sha`, `fork_sha`, `tip_sha`, `merge_sha` (None for a fast-forward), and `resolved_at`.
- Each landing is reported separately, oldest first. Nothing sums them: the commits between two landings belong to other work.
- A stored landing is never changed. A later resolution adds landings it didn't have, matched on `after_sha`. This makes the record durable and still lets a later follow-up merge reach it.
- Rejected: one range from the first fork to the last landing. That spans other slices' merges.

### D2 — Merge commits are searched on the target's first-parent line, with no fallback to main
Status: decided
- Merge-commit landings are found by the existing slice-number pattern (the project's merge convention, which the architecture accepts), restricted to `--first-parent` history of the target. Without that restriction, a sync merge into the slice branch matches too. Squadron has them, for example "Merge branch 'squadron-pr' into 381-slice.code-host-adapter-and-pr-target-resolution".
- For a merge M: before = `M^1`, after = M, tip = `M^2`, and fork = `merge-base(M^1, M^2)`. This is pure topology, with no reflog.
- The fallback to `main` in `_find_merge_commit` isn't used. It can return a merge whose diff spans a batch promotion, which is acceptable as a logged warning for a review diff, but not for a record that's kept forever.
- Consequence: a slice that landed on a branch that was later merged into the target (squadron's `squadron-brownfield` worktree branch) isn't on the target's first-parent line. The fast-forward path refuses it too: a real fast-forward puts the tip on the target's first-parent line, so a tip that's only reachable through another merge is `LANDED_ELSEWHERE`, not a fast-forward. It resolves when `slice-ranges` runs in a checkout whose target is that branch. Otherwise it stays unresolved.
- The grep pattern moves into `slice_merge_grep_pattern(n)` in `git_utils`, used by both resolvers, and `_search_merge_commit` gains `first_parent: bool`. `sq review code`'s own resolution is unchanged.

### D3 — Before and after are the target just before and just after the landing
Status: decided
- For a merge commit, before = `M^1` and after = M. For a fast-forward, before = the reflog fork and after = the branch tip. In both cases the difference between the two is exactly what the landing changed on the target.
- This refines the architecture's "fork commit against merge commit". If the target moved after the fork, the fork-to-merge diff includes other work merged in the meantime. `fork_sha` and `tip_sha` are still stored, so a consumer that wants the slice's own commits (`fork..tip`) has them.
- A fast-forward is only possible if the target hadn't moved past the fork, so for that case the two definitions agree.

### D4 — `slice-ranges` persists ranges ahead of need
Status: decided
- `sq metrology slice-ranges INDEX... [--cwd]` resolves the named slices, persists every new landing, and prints one line per slice: resolved (method, landings) or unresolved (reason).
- It stays a separate command, rather than relying on `report slice`, because it records a fast-forward slice's reflog before `git gc` expires it without taking boundary snapshots, which run pyright. Criterion 2 depends on it. There's no pipeline hook (architecture non-goal), so recording happens only when a command runs. `report slice` does the same for its one slice.
- An in-progress branch (`NOT_LANDED`) isn't persisted. Its range isn't final yet.

### D5 — Exports measure the exported tree with the live checkout's tools
Status: decided
- `AdapterContext` gains `environment_root: Path`, a required field with no default. For an in-place snapshot it equals `repo_root`. For an export it's the live checkout, and `repo_root` is the export directory.
- Adapters resolve tools (`.venv/bin/*`, `node_modules/.bin/eslint`), the venv and the uv check from `environment_root`. Source files, rule-set configs (`pyproject.toml`, `ruff.toml`, `eslint.config.*`) and the lockfile identity come from `repo_root`. Tools run with `cwd=repo_root`. A rule-set change between two commits therefore shows up as a rule-set change (architecture).
- The export gets a `node_modules` symlink to the live one, so the exported `eslint.config.*` can import its plugins. The symlink is in the temp directory, never in the measured repo. ESLint's plugins are therefore the live ones. That's the unrecorded part of the ESLint environment that #250 already tracks.
- The squadron settings (limits, exclusions, tool timeout) are read from the live checkout for an export too, through `read_snapshot_config`. Both boundaries of a slice are then measured under the same settings, and each record states which settings it used.
- `LanguageAdapter`'s contract gains one rule: tools and environments are resolved from `environment_root`, never from `repo_root`. A conformance test runs every adapter in `default_registry()` on an export whose tree has no `.venv` or `node_modules`, with the live tools available. Every metric the adapter measures in place must be present, or absent for a reason other than `tool_missing`. An adapter that resolves tools from `repo_root` fails it.
- A snapshot of a clean HEAD taken by export gives the same JSON as one taken in place, apart from `measured_at`. A test asserts this. It's the check that the export path doesn't measure something different.
- `git archive` leaves out files with the `export-ignore` attribute, so on a project that uses it, an export measures fewer files than an in-place snapshot. The export's file set is the archive's members, and each language's `file_count` shows it. Squadron and context-forge set no such attribute.
- Rejected: symlinking `.venv` into the export and leaving the contract unchanged. An editable install of the project itself (squadron's own) makes `uv sync --check` fail on any commit whose version differs, so it wouldn't test what the slice plan specifies (D6).

### D6 — Type counts at an export need an identical lockfile
Status: decided
- At an export, Python type errors are measured only when the export's `uv.lock` has the same SHA-256 as the live `uv.lock`, and the live environment passes 400's D7 check. Otherwise they're absent with `environment_unresolved` and detail `uv.lock at <sha12> differs from the live environment's` or the D7 condition that failed.
- Pyright runs on the exported files with `--pythonpath <live>/.venv/bin/python`. The environment identity is the export's `uv.lock` and its hash, which is equal to the live one by construction.
- Coverage at an export is absent, because no coverage report exists in a fresh export (401).

### D7 — Comparability is decided per measurement, and breaks are named
Status: decided
- Two measurements are diffed only when both are present and their metric, language, tool (name, version, counting), rule set (source, hash) and environment (lockfile hash, interpreter) are equal. Otherwise the row carries one or more `ComparabilityBreak` values and no delta: `tool_changed`, `rule_set_changed`, `environment_changed`, `absent_before`, `absent_after` (with the absence reason).
- At snapshot level, a difference in `exclusions` or `limits` marks every row `settings_changed`, with a detail naming which differs. The exclusions change the file set, and the limits change the over-limit figures. Rows aren't split into the ones the limits would and wouldn't affect.
- An export reads the live checkout's settings (D5), so `settings_changed` can only fire against a snapshot taken earlier under other settings. Two boundaries exported together always share settings. `report slice` prints each boundary's limits and exclusions in its header, and a slice that edits them shows no break (see Risk Assessment).
- A break shows its fix where there is one, for example `re-measure both with sq metrology snapshot --commit <sha>` after a tool upgrade.
- Cross-language rows are never compared. Each row is one language.

### D8 — Each figure carries its source, sample size and noise floor state
Status: decided
- **Static figures:** n files or n functions, from the distribution. These are deterministic, so they have no floor.
- **Audit figures:** reuse 323's `compute_delta` and `is_within_floor`, with three states (within floor, beyond floor, no floor measured) and the floor's `n_runs`. The baseline is the latest run at `before_sha` and the new run is the latest at `after_sha`, under the same `audit_prompt_hash`. If either is missing, the section says which, and no audit is run.
- **Review figures:** counts per `ReviewCategory` with n review files and n findings. The header line gives the write-time and read-side-mapped totals. Category rows show one combined count. Severity uses the review scale only. Every review figure is marked `no floor measured`, because none exists. The share of `other` among write-time findings is shown, which is the architecture's vocabulary-fit evidence.
- No report model has a field that combines sources or metrics. A test asserts that no serialized report has a key containing `score`, following `audit_report`'s precedent.

### D9 — Attribution: ranges for snapshots and audits, the review's own field for reviews
Status: decided
- Snapshots and audit runs are attributed to a slice only through a resolved landing's `before_sha` and `after_sha`. Without a range, a slice has no before and after. Its commits' snapshots appear only in `report history`, and its audits only in `report project`.
- Review records carry `slice_index` from their source document (402 D6). They're listed under a slice only when that slice has a resolved landing. A slice whose range never resolved shows only its reason, and its reviews count at project level, as the slice plan requires. Reviews with no `slice_index` also appear only at project level.
- Commit messages are never used to attribute a commit to a slice, other than the merge convention in D2.

### D10 — Command names and placement
Status: decided
- `sq metrology report slice INDEX`, `report project` and `report history` go in the existing `report` group, beside `baseline`. `trend` is already taken by the calibration report, so the time-ordered report is `history`. The `report` group's help text is updated, since it currently describes only samples.
- `sq metrology slice-ranges` is a flat command, like `snapshot` and `ingest-reviews`.
- `sq metrology snapshot --commit REV` exposes export directly.
- The new commands live in `cli/commands/metrology_quality.py`, because `metrology.py` is already over 1,000 lines. They're mounted the way 324's and 400's commands are.

### Technology Choices
- Stdlib `tarfile` with `filter="data"` for extraction (Python ≥ 3.12, which squadron requires). It refuses absolute paths and links outside the tree.
- `git archive` accepts `:(exclude,glob)` pathspecs, checked on 20261022 with git 2.50.1. On squadron's HEAD, `git archive` and `git ls-files` both list 2,127 files.
- No new dependencies.

### Patterns and Conventions
- `SnapshotExportError` subclasses `MetrologyError`, and each message names the fix. `RangeUnresolvedReason` is data, not an exception.
- Every compared value is an enum: `LandingMethod`, `RangeUnresolvedReason` and `ComparabilityBreak`.
- Store methods follow the existing shape: `write_slice_ranges(record)` and `get_slice_ranges(project_id) -> SliceRanges | None`.

## Implementation Details

### API Contracts

```
sq metrology slice-ranges INDEX... [--cwd DIR] [--json]
sq metrology snapshot [--commit REV] [--cwd DIR] [--json]
sq metrology report slice INDEX [--cwd DIR] [--json]
sq metrology report project [--cwd DIR] [--json]
sq metrology report history [--cwd DIR] [--json]
```

- **`slice-ranges`:** one line per slice, `403  merge_commit  1 landing  (new)` or `388  unresolved: reflog_unavailable`. Exits 0 when every slice either resolved or was unresolved for a stated reason. Exits 1 on a git or store error.
- **`snapshot --commit`:** the same output as 400, with `(exported)` after the commit. Without `--commit`, behavior is unchanged.
- **`report slice`:** a header (slice, target, landings, and the limits and exclusions each boundary snapshot was measured under), then for each landing a static section, an audit section and a comparability footnote, and then the review section. When a boundary snapshot has to be taken, it first prints an INFO line naming the commit.

```
Slice 940 — 2 landings on main
Landing 1  merge cc5d09d1  before 1a2b3c4d → after cc5d09d1
  python  file_length        total 41,210 → 41,876 (+666)  over 300: 104 → 106  n=928 → 931 files
          function_length    over 50: 187 → 189           n=11,032 → 11,057 functions
          lint_count         0 → 0                        [ruff 0.15.1, pyproject.toml[tool.ruff]]
          type_errors        not compared: environment_changed (uv.lock 3f9a… → 77c1…)
  audit   no audit run at 1a2b3c4d
Landing 2  merge 288ec439 …
Reviews (by source document; no floor measured)
  n=3 review files, 14 findings (write-time 0, read-side mapped 14)
  correctness                      5   (CONCERN 3, NOTE 2)
  error-handling-observability     4
  other                            3   raw: style, scope
```

The figures are illustrative. `--json` prints the report model.

- **`report project`:** the latest snapshot's summary per language and metric, the latest audit baseline with its floor (from `baseline_report`), and review findings per category split into slice-attributed (the slice has a resolved landing) and project-only.
- **`report history`:** snapshots ordered by the target's first-parent history, one row per commit with each metric's headline figure, and a break marker between rows that aren't comparable. Snapshots of commits off that line are left out, and a closing line gives their count. History shows snapshots only: audits and reviews are in `report project` and `report slice`.

### Database / Storage Schema

```
SliceRanges
  record_id, project_id: ProjectId
  slices: dict[int, list[SliceLanding]] (each list non-empty, oldest first, unique after_sha)
SliceLanding
  method: LandingMethod                 merge_commit | fast_forward
  target_ref: str
  before_sha, after_sha, fork_sha, tip_sha: str
  merge_sha: str | None                 required for merge_commit, None for fast_forward
  resolved_at: datetime
```

- `MetrologyRecord.slice_ranges: SliceRanges | None = None` and `RECORD_TYPE_SLICE_RANGES = "slice_ranges"`. `schema_version` stays 1, and existing records load unchanged.
- The model validator rejects an empty `landings`, a duplicate `after_sha`, and a `merge_sha` that doesn't match `method`.

## Integration Points

### Provides to Other Slices
- **420:** `take_snapshot_at(commit)` to measure a replay's output at any commit, and `get_slice_ranges` for a slice's boundaries and own commits (`fork..tip`).
- **404:** nothing new. The `read_snapshot_config` split leaves `take_snapshot`'s signature unchanged.

### Consumes from Other Slices
- **400:** the snapshot pipeline. The `environment_root` field and its resolution rule are the only contract change, and both 400 adapters are updated in this slice. 401's code needs no change (see Prerequisites).
- **402:** `list_code_reviews`, under its contract: a `None` category is missing, `read_side_mapped` is labeled, and records without a `slice_index` are project-level only.
- **323:** `baseline_report` and `compute_delta`, unchanged.
- **`git_utils`:** a `None` from `run_git` is never an answer. See the failure-mode table.

## Success Criteria

### Functional Requirements
1. A slice merged with a merge commit resolves from first-parent topology with no reflog, including in a fresh clone. A sync merge into the slice branch is never taken as a landing.
2. A fast-forward slice resolves from the reflog while its creation entry exists. After `slice-ranges` has persisted it, it still resolves with the branch deleted and the reflog expired.
3. A slice with two landing merges has two landings, reported separately. A later landing is added to a stored range, and stored landings never change.
4. `sq metrology snapshot --commit <sha>` measures that commit from an export and writes a record keyed on it. The measured repo's `.git` and working tree are unchanged, and the temp directory is removed even on failure.
5. A snapshot of a clean HEAD by export equals the in-place one, apart from `measured_at`.
6. At an export, type errors are present only when the export's `uv.lock` hash equals the live one. Otherwise they're absent `environment_unresolved` with the reason.
7. `report slice` takes missing boundary snapshots, then shows per-landing static rows. A row is diffed only on full identity match, and otherwise names its break. A difference in limits or exclusions between two snapshots marks every row `settings_changed`. Two boundaries exported together share the live settings, so this fires only against a snapshot taken earlier under other settings, and `report slice` prints each boundary's settings.
8. The audit section uses `compute_delta` when runs exist at both boundaries under one prompt hash. Otherwise it says which run is missing, and no audit is run.
9. Review figures carry n files, n findings, separate write-time and read-side-mapped counts, review-scale severity, and `no floor measured`. No serialized report has a key containing `score`.
10. An unresolved slice shows only its reason, with no before and after and no reviews. Its reviews and audits appear only at project level in `report project`, and its snapshots only in `report history`.
11. Every failure mode in the Failure modes table behaves as stated.

### Technical Requirements
- ruff format, ruff check and pyright (zero errors) are clean, and the full test suite passes.
- New modules stay at ~300 lines or less. `git_utils.py` doesn't grow beyond the rename, the pattern function and the `first_parent` argument.
- Resolver tests build throwaway repos under `tmp_path` covering a `--no-ff` landing, a fast-forward, a sync merge into the slice branch, two landings of one slice, a rebased branch (`FORK_NOT_ANCESTOR`), an empty branch, a slice merged into a side branch that was then merged into the target (`LANDED_ELSEWHERE`), and a fresh `git clone` of the `--no-ff` repo.
- Export tests: the in-place equals export check, the adapter conformance test (D5), a link outside the tree (error), an unknown revision, a `git archive` timeout and an extraction `OSError` (error, temp directory removed), a different `uv.lock` (absent), and a `.git` listing (paths, sizes, mtimes) that's identical before and after.
- Each failure mode's signal is asserted with `caplog`: the resolver's INFO line for an unresolved slice, the WARNING and `GIT_ERROR` reason when a faked `run_git` returns `None` (with nothing persisted), the WARNING when the stored record changed between the start read and the write (both runs' landings kept), the WARNING for a missing landing commit, and the ERROR for each export failure.
- A report test with a stored landing whose commit is gone still prints the slice's other landings and reviews.
- `sq review code`'s range-resolution tests pass unchanged.
- Report tests use store fixtures and a fake `ensure_snapshot`. No test uses the user store.
- `docs/COMMANDS.md` documents the four commands and `--commit`, and CHANGELOG gets a user-facing bullet.

### Integration Requirements
- 420 can call `take_snapshot_at` and `get_slice_ranges` with no change to this slice's records.
- `sq metrology snapshot` without `--commit`, `report baseline`, `audit delta` and `ingest-reviews` behave as before.

### Verification Walkthrough

None of these commands exist yet, and the expected outputs describe structure, not exact numbers. Run from the squadron root, with 400's `.squadron.toml` values in place and 402's `ingest-reviews` already run.

1. **Persist ranges.** Run `sq metrology slice-ranges 172 305 400 940 946 947 <a squadron-brownfield slice>`. Expect one line per slice. 400, 946 and 947 show `merge_commit`. 940, 305 and 172 show two landings. Slices that landed only on `squadron-brownfield` shows `unresolved: landed_elsewhere` (branch still local) or `unresolved: no_landing`. `ls ~/.config/squadron/metrology/sliceranges-*` shows one file. Run it again: no line says `(new)`.
2. **Durable in a fresh clone.** Run `git clone . /tmp/sq-clone && sq metrology slice-ranges 400 --cwd /tmp/sq-clone`. Expect `merge_commit` with the same `before_sha` and `after_sha` as step 1, with no local slice branch in the clone.
3. **Export equals in place.** On a clean HEAD, run `sq metrology snapshot --json > a.json`, then `sq metrology snapshot --commit HEAD --json > b.json`. `diff <(jq 'del(.measured_at)' a.json) <(jq 'del(.measured_at)' b.json)` prints nothing.
4. **Old commit, nothing written to the repo.** Note `git status --porcelain` and `ls -la .git`. Run `sq metrology snapshot --commit <400's before_sha>`. Expect type errors `absent: environment_unresolved (uv.lock at … differs …)` if the lockfile changed since then. Lint and length are present. `git status --porcelain` and `.git` are unchanged.
5. **Slice report.** Run `sq metrology report slice 400`. Expect the INFO line for any boundary snapshot it takes, then the static rows with n, the audit line (`no audit run at …` unless one exists), and the review section with `no floor measured`.
6. **Comparability break.** Change `metrology.max_function_lines` to 40, then run `sq metrology snapshot --commit <400's after_sha>` and `report slice 400`. Expect the rows between that snapshot and the earlier one marked `settings_changed`, naming the limits. Restore the value and re-snapshot.
7. **Unresolved slice.** Take the slice from step 1 marked unresolved. `report slice <n>` shows only the reason. `report project` counts its reviews as project-only.
8. **Project and history.** `sq metrology report project` and `report history` print the sections described under API Contracts.

## Risk Assessment

### Technical Risks
- **The editable self-install at an export.** Squadron's venv has squadron installed in editable mode, pointing at the live `src`. If pyright resolved `import squadron` through site-packages rather than the exported tree, export type counts would reflect the live code.
- **Range resolution is persisted once and never corrected.** A wrong landing stays in the store.
- **Settings changed inside a slice don't show between two exports.** Both boundaries are exported under the live checkout's limits and exclusions (D5), so a slice that edits them shows no `settings_changed` break. That break fires only against a snapshot taken earlier under other settings. Each record states the settings it used, and `report slice` prints them in its header. Squadron's `.squadron.toml` is gitignored, so an export has no committed settings to read instead.

### Mitigation Strategies
- Pyright resolves workspace code before site-packages. The in-place-equals-export test (criterion 5) catches a mismatch at HEAD, and the walkthrough step 4 is checked against a known older commit. If they differ, type counts at an export become absent `environment_unresolved` with that reason, rather than wrong.
- First-parent restriction, no main fallback, the fork-ancestor check and the sync-merge test fixture all target the known wrong-landing cases. The project's record can be deleted by hand to force re-resolution, and `slice-ranges` prints its path. Deleting it also drops fast-forward landings whose reflog has since expired.

## Implementation Notes

### Development Approach
1. `git_utils`: make the helpers public, add the pattern function and `first_parent`, and confirm the review resolver tests still pass.
2. Slice-range models, envelope field and store methods, with a back-compat load test.
3. Resolver and `slice-ranges`, with the throwaway-repo fixtures.
4. `read_snapshot_config` split, `environment_root` in the contract and adapters (in place: `environment_root == repo_root`, and the 400 tests pass unchanged).
5. Export, `take_snapshot_at`, `--commit`, the lockfile gate and the export tests, including in place equals export.
6. `compare.py` and `reviews.py`, then the three reports and their CLI.
7. Docs, CHANGELOG and the walkthrough.

### Special Considerations
- **Reports write records.** `report slice` writes snapshots and ranges. Earlier `report` commands are read-only, so the help text for `report slice` says that it measures missing boundaries.
- **Security.** An export runs the live checkout's tools on an older tree, including that tree's `eslint.config.*` (JavaScript). That's the same trust boundary as 400's in-place snapshot, and `docs/COMMANDS.md` says so.
- **Cost.** A boundary snapshot runs pyright, which is the slowest step. It's bounded per call by `metrology.snapshot_tool_timeout_s`, and stored snapshots are reused.
