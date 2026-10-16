---
docType: tasks
slice: effort-calibration-and-producer-model-effectiveness
project: squadron
lld: user/slices/176-slice.effort-calibration-and-producer-model-effectiveness.md
dependencies: [175, 321, 941]
projectState: >
  Slice 176 design approved after two review rounds (20261015). 175 records a UsageRecord
  per LLM action in run state and review artifacts and ships `sq stats run|reviews`. This
  slice persists every loop round and adds `sq stats slice|slices|producers|runs`.
  Addresses #214 and the observed half of #210; replay and judging moved to slice 177.
dateCreated: 20261015
dateUpdated: 20261015
status: in_progress
---

## Context Summary

- Working on **176 effort-calibration-and-producer-model-effectiveness**. Loop rounds persist in `StepState` (D3); new read-only cores turn task files, slice plans, git history and run state into planned-vs-actual effort (D4–D7), observed producer effectiveness (D8), and cross-run totals.
- Decisions D1–D9, the API contracts, report shapes, UI layout and the D9 failure table live in the slice design. Tasks reference them and do not repeat them. Use the design's row notes and footer texts verbatim.
- Key files: `pipeline/state.py`, `stats/usage_report.py`, new `stats/{planning_docs,git_history,effort_report,producer_report}.py`, `cli/commands/stats.py`, `cli/stats_views.py`, `documents/frontmatter.py`, `review/persistence.py`.
- Implementation choices not spelled out in the design, fixed here so no task has to decide them:
  - **One renderer module per report.** `cli/stats_views.py` is 242 lines and keeps only `run` and `reviews`. `slice`/`slices` go in new `cli/stats_effort_views.py`, `producers` in new `cli/stats_producer_views.py`, `runs` in new `cli/stats_runs_views.py`. Shared cells (`count_cell`, cost cells, totals) are imported from `stats_views`, not copied. Every touched CLI module stays under ~300 lines.
  - **Frontmatter from text.** `git show` returns text, not a path. Extract `parse_frontmatter(text) -> dict[str, object] | None` from `read_frontmatter` in `documents/frontmatter.py`; `read_frontmatter` calls it. No second YAML parse path.
  - **Document locations.** Add `SLICES_DIR` and `ARCHITECTURE_DIR` beside the existing `REVIEWS_DIR` / `TASKS_DIR` in `review/persistence.py`. Planning readers take a project root and use these constants.
  - **Split task files.** A slice whose tasks span `{index}-tasks.{name}-1.md`, `-2.md`, … is read as one task list in suffix order. The slice window starts at the commit that added the earliest of them.
  - **Git injection.** `GitHistory(project_root, run=run_git)` takes the git runner as a parameter (production passes `run_git`). Tests pass a counting wrapper around the real `run_git` to assert D6's call count.
  - **`min_n`** is read in the CLI with `get_typed_config("metrology.min_evidence_n", int)` and passed to `producer_report`; the core reads no config.
- Every task ends with `ruff format`, `ruff check`, `pyright` (zero errors), the touched tests, and a commit on the slice branch with the subject the task names.
- #214 closes when this slice merges (Phase 7). #210 stays open for slice 177.
- Effort: 3/5. Next planned slice: 177 Producer Replay and Pairwise Judging.

## Tasks

### Loop-round persistence (D3)

- [x] **Task 1: Persist every loop round in `StepState`**
  - [x] Read the target (`cf config get git.integration_branch`, empty means `main`) and create `176-slice.effort-calibration-and-producer-model-effectiveness` from it
  - [x] Before any state change, check whether `StepResult.prior_rounds` (`executor.py:226`, built near `executor.py:1089`) keeps round boundaries. It is declared as a flat `list[ActionResult]`.
  - [x] If boundaries are lost: change it to `list[list[ActionResult]]`, flatten it where `executor.py:643` builds `prior_outputs`, run `pytest tests/pipeline -q`, and commit `refactor: keep loop prior rounds grouped per round`. If they are recoverable, say so in this task's commit body and make no executor change.
  - [x] Add the three D3 fields to `StepState` in `pipeline/state.py`, with defaults so older files load and no schema version bump
  - [x] `_append_step` writes them per D3; `action_results`, the hoisted `verdict` and `score`, and `outputs` still come from the final round only
  - [x] Commit: `feat: persist every loop round in run state`
  - **Success:** a loop step's state file holds one `prior_round_results` entry per earlier round, plus `accepted` / `exhausted`; non-loop steps write `[]`, `False`, `False`

- [x] **Task 2: Test loop-round persistence**
  - [x] In `tests/pipeline/` (beside the existing state tests): a `StepResult` with two earlier rounds round-trips through `_append_step` / `load` with rounds in order and `accepted` / `exhausted` preserved
  - [x] A state file without the three keys loads with `[]`, `False`, `False`
  - [x] The final round's `verdict` hoist is unchanged when earlier rounds carry different verdicts
  - [x] If Task 1 regrouped `prior_rounds`: an executor test shows `prior_outputs` still sees every round (#170 behavior)
  - [x] Commit: `test: cover loop-round persistence`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 3: Earlier rounds and partial loops in `run_usage_report`**
  - [x] `ActionUsageRow` gains `round: int | None = None` (1-based; `None` for non-loop steps). A loop step's earlier-round rows come first, then the final round's rows, per D3
  - [x] A malformed `prior_round_results` entry is handled per the D9 row (`unreadable` row and WARNING, as 175's `_row` does)
  - [x] `RunUsageReport` gains `partial_loop: bool` for the D9 "run stopped or resumed inside a loop step" row; compare `step_type` through the loop step type constant, not a literal
  - [x] `UsageTotals` are built from every round's records
  - [x] `render_run_report` shows the round for loop rows and the D9 row note; `run_report_json` adds `round` per row and `partial_loop`
  - [x] A run with no loop steps renders exactly as before (Integration Requirements); `stats_views.py` stays under ~300 lines
  - [x] Commit: `feat: report every loop round in sq stats run`
  - **Success:** `sq stats run` lists every round of a loop and its totals include them

- [x] **Task 4: Test earlier-round usage rows**
  - [x] In `tests/stats/test_usage_report.py`: a two-round loop yields rows with rounds 1 and 2, and totals equal the sum of both rounds' records
  - [x] A pre-176 run file (no `prior_round_results`) reports the same rows and totals as before this slice
  - [x] Malformed `prior_round_results` → `unreadable` row + WARNING (assert with `caplog`)
  - [x] A `failed` run whose `current_step` is a loop step → `partial_loop` true and the note in rendered output; a `completed` run → false
  - [x] Existing `tests/cli/test_stats.py` output assertions for loop-free runs still pass unchanged
  - [x] Commit: `test: cover loop rounds in sq stats run`
  - **Success:** tests pass, zero pyright errors

### Planning-document readers (D4)

- [x] **Task 5: Shared frontmatter and path constants**
  - [x] Extract `parse_frontmatter(text)` from `read_frontmatter` in `documents/frontmatter.py` (same `None` rules); `read_frontmatter` reads the file and calls it
  - [x] Add `SLICES_DIR` and `ARCHITECTURE_DIR` to `review/persistence.py` beside `TASKS_DIR` (SLICES_DIR was added to review/persistence.py; ARCHITECTURE_DIR already existed in integrations/context_forge.py as a str, so it is reused, not duplicated.)
  - [x] Test `parse_frontmatter`: valid block, no fence, unclosed fence, non-mapping YAML
  - [x] Commit: `refactor: extract parse_frontmatter and add planning document dirs`
  - **Success:** existing frontmatter tests pass unchanged; the new test passes

- [x] **Task 6: `read_task_file` in `stats/planning_docs.py`**
  - [x] New module with `PlannedTask` and `PlannedSlice` exactly as in the design's API Contracts
  - [x] `read_task_file(paths) -> tuple[PlannedTask, ...]` over one task file or an ordered list of split parts, parsing headings, effort, commit subjects and checkboxes per D4
  - [x] Open points D4 leaves to the parser: every effort form also accepts a `/5` suffix (`100-tasks.foundation.md` uses `**Effort**: 1/5`), and `git commit -m "…"` may follow other text on the line (`170-tasks.*` uses `git add … && git commit -m`) (also: a bullet task's block ends at the first flush, non-indented line, so 173's trailing "Effort: 3/5 overall." is not read as task 24's effort; an Effort line must start the item)
  - [x] `read_task_files_for(index, project_root)` finds `{index}-tasks.*.md` under `TASKS_DIR` and returns `None` when there is none
  - [x] No git, no Typer imports
  - [x] Commit: `feat: add task file reader for effort reports`
  - **Success:** the module imports cleanly and pyright passes

- [x] **Task 7: Fixtures and tests for the task-file reader**
  - [x] Create `tests/stats/fixtures/planning/` with verbatim copies of `100-tasks.foundation.md`, `170-tasks.profile-aware-dispatch-model-routing.md`, `175-tasks.usage-and-cost-tracking.md`, `173-tasks.user-definable-actions-on-supported-events.md`, and `architecture/140-slices.pipeline-foundation.md`. Add a synthetic two-part task file and a synthetic file with `**Effort**: Relative`, marked synthetic in a fixture README line.
  - [x] New `tests/stats/test_planning_docs.py`. Per real fixture, assert the task numbers, efforts and commit subjects read from the real file (175: 16 ``Commit:`` subjects; 173: none)
  - [x] Split parts read as one ordered list; `**Effort**: Relative` → `effort is None` + WARNING naming file and line; checked/total for one fully and one partly checked task
  - [x] A parser that returns no tasks for any real fixture fails the test (D4)
  - [x] Commit: `test: cover task file reader with real task files`
  - **Success:** tests pass, zero pyright errors

- [x] **Task 8: Slice plans and slice status**
  - [x] `read_slice_plans(project_root) -> dict[int, PlannedSlice]` reads every `*-slices.*.md` under `ARCHITECTURE_DIR` per D4; `tasks` is filled from `read_task_files_for` (the unknown-index error is raised by planned_slice(index, project_root); a plan entry ends at the next checkbox item or heading, since entries contain plain numbered lines)
  - [x] `slice_status(index, project_root) -> tuple[bool, str | None]`: completion per D4 and the design's `dateCreated` for `--since`
  - [x] An index in no plan file raises a typed error carrying the plan files searched (D9 "unknown index")
  - [x] Commit: `feat: add slice plan and status readers`
  - **Success:** every entry in the 140 fixture is read with its index, title and effort

- [x] **Task 9: Test slice plans and status**
  - [x] Against the 140 fixture: entry count, a checked and an unchecked entry, an entry with `Effort: N/5` and one without
  - [x] `slice_status` on a temp design with `status: complete`, one with another status, and a missing design
  - [x] Unknown index → the typed error lists the plan files searched
  - [x] Commit: `test: cover slice plan and status readers`
  - **Success:** tests pass, zero pyright errors

### Git history (D5, D6)

- [x] **Task 10: `GitHistory` log pass**
  - [x] New `stats/git_history.py`, the only `stats/` module that runs git. `WindowSource` and `ReviewRound` as in the API Contracts, plus a frozen `Commit` (sha, parents, authored_at, subject, changes as `(status, path, blob_id)`)
  - [x] `GitHistory(project_root, run=run_git)`; `load()` runs the two whole-history calls in D6 "Bound" and builds the in-memory graph. The log call is `git log --all --raw --no-abbrev --no-renames`: `--raw` gives each change's blob id (needed by Task 12 dedupe), `--no-renames` keeps every change a single path
  - [x] Failures per the first two D9 rows, as typed errors; never a partial graph
  - [x] In-memory query helpers: branch tip for `refs/heads/{index}-slice.*`, first-parent chain, commit that added a path, commits touching a path glob (also `GitHistory.commit(sha)` and `GitHistory.show(sha, path)`, the latter being the only other git call, used by Task 12)
  - [x] Commit: `feat: add git history log pass for stats`
  - **Success:** two git calls build the graph; failures raise, never return partial data

- [x] **Task 11: Test the log pass**
  - [x] `tests/stats/conftest.py`: a fixture that builds a temp git repo with `main`, a `NNN-slice.x` branch, a task-file commit, code and document commits, and controlled author dates. It serves Tasks 11–19. (the helper is `tests/stats/repo_support.py` `StatsRepo`, exposed as the `stats_repo` fixture in `tests/stats/conftest.py`)
  - [x] Graph contents: parents, `%aI` dates, subjects, changes with blob ids; a file moved into `archive/` appears as a delete plus an add, never a rename
  - [x] A counting wrapper around `run_git` sees exactly 2 calls for `load()`
  - [x] Temp dir without git → error naming cwd; a `run` stub returning `None` for the log call → error naming the command and no graph
  - [x] Commit: `test: cover git history log pass`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 12: Review rounds from committed versions**
  - [ ] `review_rounds(index, review_type) -> list[ReviewRound]` and `rounds_to_accept(rounds)` per D6, reading each version through `run` and `parse_frontmatter`. Dedupe happens before any `git show`: collect the commits that touched `N-review.T.*.md` (top level and `archive/`), drop versions whose blob id was already seen (keep the earliest commit), then order by commit date
  - [ ] An unreadable version follows the D9 `git show` / unreadable-frontmatter rows; the result carries a skipped count for the footer
  - [ ] Lower-bound flag ("Consumes from Other Slices"): set when the earliest round is authored before the cutoff, stored as one module constant with a comment citing 941. Read the cutoff with `git log -1 --format=%aI 941-slice.review-and-revise-loop-from-sq-review-max` (the author date of the 941 branch tip, the same cutoff the design footer text names). If that branch is missing, stop and ask the Project Manager for the date.
  - [ ] Commit: `feat: read per-round review verdicts from git`
  - **Success:** the call count for a report is `2 + V` (V = versions read)

- [ ] **Task 13: Test review rounds**
  - [ ] In the temp repo: three committed versions (FAIL, CONCERNS, PASS) plus an archive copy of round 1 → three rounds after dedupe, rounds-to-accept 2
  - [ ] Lower-bound flag: earliest round authored before the cutoff → set; after the cutoff → unset (one case each, cutoff constant monkeypatched)
  - [ ] A version with broken frontmatter, and a `run` stub failing one `git show` → each skipped with WARNING naming sha and path; skipped count 2
  - [ ] Call count `2 + V` asserted with the counting wrapper
  - [ ] Commit: `test: cover per-round review verdicts`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 14: Slice window and task attribution**
  - [ ] `slice_window(index, task_paths)` and `attribute(window, tasks)` per D5 rules 1–5, from the in-memory graph only
  - [ ] When no task in the file prescribes a commit subject, there are no markers to anchor groups: groups read `unavailable`, the same as window `NONE` (Success Criterion 3)
  - [ ] Commit: `feat: attribute slice commits to task groups`
  - **Success:** attribution needs no git calls beyond `load()`

- [ ] **Task 15: Test window and attribution**
  - [ ] Branch present → `BRANCH`, window excludes the task-file commit and anything before it; branch absent → `NONE`
  - [ ] Three prescribed subjects, one reworded → two groups with markers and extras, one `marker not found`; duplicate subject → earliest wins
  - [ ] Branch present but no task prescribes a subject → groups `unavailable`
  - [ ] Document-only commits are not implementation commits; a code commit after the code review artifact is a fix-up, one before is not
  - [ ] Commit: `test: cover slice window and task attribution`
  - **Success:** tests pass, zero pyright errors

### Effort reports (D2, D7)

- [ ] **Task 16: `slice_effort_report`**
  - [ ] New `stats/effort_report.py`: `slice_effort_report(index, *, project_root, history, state_manager)` returns the D7 header and per-group rows, with recorded spend per D7 (all loop rounds, via Task 3)
  - [ ] No task file, window `NONE`, and no prescribed subjects → the D9 row notes / `unavailable` groups
  - [ ] Footer counts: markers not found, review rounds skipped, lower-bound flag, unreadable run files
  - [ ] `to_json_dict()` serializes the dataclass fields
  - [ ] Commit: `feat: add single-slice effort report core`
  - **Success:** the core imports no Typer and runs no git outside `GitHistory`

- [ ] **Task 17: Test `slice_effort_report`**
  - [ ] Temp repo with planning docs, a branch, review versions and a run file for the index: header values, groups, and recorded spend match the inputs
  - [ ] Missing task file → `no task file`; missing branch → `unavailable` groups with planned effort, rounds and spend still present
  - [ ] Unknown index → the typed error with plan files searched
  - [ ] Call count `2 + V` for one slice (D6)
  - [ ] `to_json_dict()` values equal the dataclass values
  - [ ] Commit: `test: cover single-slice effort report`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 18: `slices_effort_report`**
  - [ ] `slices_effort_report(*, since, project_root, history, state_manager)` per D2 and D7, with one `GitHistory.load()` for the whole report
  - [ ] A measure that is `unknown`/`unavailable` for a slice is left out of that measure's distribution, and the measure's n is reported separately from the level's n
  - [ ] No completed slices → empty report with that reason (D9)
  - [ ] Commit: `feat: add effort rollup across completed slices`
  - **Success:** `to_json_dict()` has `levels[].measures`

- [ ] **Task 19: Test `slices_effort_report`**
  - [ ] Three completed slices at two effort levels plus one `unplanned` → correct grouping, n, median and range
  - [ ] `since` excludes an older slice; a not-complete slice is excluded; a slice with no branch contributes rounds and spend but not commit measures
  - [ ] No completed slices → empty report with its reason
  - [ ] Call count `2 + V` for the whole rollup
  - [ ] Commit: `test: cover effort rollup`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 20: `sq stats slice` and `sq stats slices` CLI**
  - [ ] In `cli/commands/stats.py`: `slice <index>` and `slices [--since YYYYMMDD]`, both with `--json`; project root is the cwd; build `GitHistory(Path.cwd(), run=run_git)` and `StateManager()`
  - [ ] `--since` that is not a valid `YYYYMMDD` date → error naming the value and the expected format, exit 1
  - [ ] Typed core errors → `Error: …` on stderr, exit 1; empty rollup → message, exit 0
  - [ ] New `cli/stats_effort_views.py` renders the design's UI layout with widths from `cli/columns.py` `fit_widths`
  - [ ] Commit: `feat: add sq stats slice and sq stats slices`
  - **Success:** `sq stats slice 175` and `sq stats slices` render without error in this repo

- [ ] **Task 21: Test the effort CLI**
  - [ ] In `tests/cli/test_stats.py` (or a new `test_stats_effort.py` if it would exceed ~300 lines), using the temp repo fixture with `chdir`: table and `--json` for both commands; JSON values equal the table's
  - [ ] No git repo → exit 1 naming the cwd; unknown index → exit 1 naming plan files; malformed `--since` → exit 1; empty rollup → message, exit 0
  - [ ] No file, ref, or run state is written (compare `git status --porcelain`, `for-each-ref`, and the runs dir before/after)
  - [ ] Commit: `test: cover sq stats slice and slices`
  - **Success:** tests pass, zero pyright errors

### Producer effectiveness (D8)

- [ ] **Task 22: Producer units and config keys**
  - [ ] New `stats/producer_report.py`: extract units and their producer config keys from `StateManager.scan_runs()` per D8 "Unit" and "Producer config key"; `phase` is `StepTypeName.DESIGN` or `TASKS`
  - [ ] Excluded with a count each: loops with no phase step before them, phase work inside `each`, partial-loop runs, phase steps without a dispatch or review action (D9)
  - [ ] Commit: `feat: extract producer units and config keys from run state`
  - **Success:** units come only from top-level phase steps, compared through `StepTypeName`

- [ ] **Task 23: Test producer units and keys**
  - [ ] Run files with `design, loop` and `tasks, loop` pairs → one unit each, with the loop attached
  - [ ] Same dispatch model with two reviewer models → two config keys
  - [ ] Each exclusion case above → excluded and counted
  - [ ] Commit: `test: cover producer units and config keys`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 24: Producer aggregation**
  - [ ] `producer_report(*, phase, state_manager, min_n)` computes the D8 per-config metrics, the `below floor` rule, and the D8 "Honesty" footer flags; unreadable run file count from `scan_runs`
  - [ ] `to_json_dict()`
  - [ ] Commit: `feat: add observed producer effectiveness report core`
  - **Success:** the report reads run state only through `StateManager.scan_runs()`

- [ ] **Task 25: Test producer aggregation**
  - [ ] Two configs across several runs: first-round counts, median rounds, accepted and failure rates, cost per accepted with priced counts
  - [ ] n below `min_n` → `below floor`; a pre-176 run file uses loop `iteration` for rounds
  - [ ] An unreadable run file → footer count (D9)
  - [ ] Commit: `test: cover producer aggregation`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 26: `sq stats producers` CLI**
  - [ ] `producers [--phase design|tasks]` with `--json`; `--phase` parsed into `StepTypeName`, other values rejected with an error naming the allowed ones. Without `--phase`, report both phases.
  - [ ] `min_n` read in the CLI; a non-integer value → error naming the key and value, exit 1 (D9)
  - [ ] New `cli/stats_producer_views.py` renders the design's layout; no phase runs → message, exit 0
  - [ ] Commit: `feat: add sq stats producers`
  - **Success:** `sq stats producers --phase design` renders in this repo

- [ ] **Task 27: Test the producers CLI**
  - [ ] Table and `--json` agree on values; `--phase` filtering; invalid `--phase` → nonzero exit with the allowed values
  - [ ] Non-integer `metrology.min_evidence_n` in a temp project config → exit 1 naming key and value
  - [ ] No phase runs → message, exit 0; nothing written to the runs dir
  - [ ] Commit: `test: cover sq stats producers`
  - **Success:** tests pass, zero pyright errors

### Cross-run totals

- [ ] **Task 28: `runs_usage_report`**
  - [ ] In `stats/usage_report.py`: `runs_usage_report(*, slice_index, pipeline, state_manager)` over `scan_runs()`, one D7 row per run plus `partial_loop`, built from `run_usage_report`'s row logic, not a copy of it
  - [ ] Filters on `params["slice"]` and pipeline name; total via `usage_totals` (175 D9); unreadable file count from `scan_runs`
  - [ ] `to_json_dict()`; `usage_report.py` stays under ~300 lines
  - [ ] Commit: `feat: add cross-run usage report core`
  - **Success:** one report covers every readable run

- [ ] **Task 29: Test `runs_usage_report`**
  - [ ] Three runs across two slices and two pipelines: each filter, both together, and no filter
  - [ ] Totals equal the sum of per-run totals including loop rounds; a pre-175 run counts as unpriced, not $0
  - [ ] An unreadable run file → footer count; a partial-loop run → row note
  - [ ] Commit: `test: cover cross-run usage report`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 30: `sq stats runs` CLI**
  - [ ] `runs [--slice INDEX] [--pipeline NAME]` with `--json`; renderer in new `cli/stats_runs_views.py` with the `Total` row in the `$X (k of m priced)` form; no matching runs → message, exit 0
  - [ ] Tests: table/JSON parity, filters, empty case, nothing written
  - [ ] Commit: `feat: add sq stats runs`
  - **Success:** tests pass, zero pyright errors; `cli/commands/stats.py` under ~300 lines

### Documentation and verification

- [ ] **Task 31: Docs and wrappers**
  - [ ] README `## Usage and cost (sq stats)`: the four subcommands, `span` and `recorded spend` meanings, and the observational caveat for `producers`
  - [ ] `commands/sq/stats.md` and `commands/agents/sq-stats/SKILL.md`: extend the subcommand list (pass-through stays unchanged)
  - [ ] `140-arch.pipeline-foundation.md` run-state section: the three `StepState` fields
  - [ ] Confirm slice plan entry 177 in `140-slices.pipeline-foundation.md` still matches what this slice provides (D8 config key, D3 rounds); edit only if it does not
  - [ ] CHANGELOG: short user-facing bullets under Unreleased (new subcommands; `sq stats run` now counts every loop round)
  - [ ] Commit: `docs: document sq stats slice, slices, producers, and runs`
  - **Success:** the README documents all four subcommands; both wrappers list them

- [ ] **Task 32: Full validation**
  - [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full `pytest` green
  - [ ] Map each D9 failure-table row to a passing test; list the test name per row (recorded in the task file notes below)
  - [ ] `grep` confirms each D9 row note and footer text appears in code exactly once
  - [ ] `grep` confirms no Typer import under `stats/`, no `run_git` use in `stats/` outside `git_history.py`, and no bare-string comparison of step types, verdicts or window sources
  - [ ] Record the D9 row-to-test map under a `## Verification Notes` heading at the end of this task file, then commit that file with `docs: map slice 176 failure table to tests`
  - **Success:** full suite green; every D9 row has a named test in the task file notes

- [ ] **Task 33: Verification walkthrough and issue comments**
  - [ ] Run design Verification Walkthrough steps 2–7 with `.venv/bin/sq` in this repo; record each output under `## Verification Notes` in this task file. Step 1 (scratch project live run) and step 8 (slash parity) need a live model run and Claude Code respectively: run them if available, otherwise list them as not run.
  - [ ] Commit the task file notes: `docs: record slice 176 verification walkthrough`
  - [ ] Draft the #214 and #210 comments (subcommands, the observed-only scope for #210, slice 177 for replay) under `## Verification Notes`. Post them only after the Project Manager confirms; this task does not post.
  - **Success:** walkthrough results recorded; comments drafted
