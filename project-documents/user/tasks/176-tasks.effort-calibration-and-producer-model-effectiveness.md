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
status: not_started
---

## Context Summary

- Working on **176 effort-calibration-and-producer-model-effectiveness**. Loop rounds persist in `StepState` (D3); new read-only cores turn task files, slice plans, git history and run state into planned-vs-actual effort (D4–D7), observed producer effectiveness (D8), and cross-run totals.
- Decisions D1–D9, the API contracts, report shapes, UI layout and the D9 failure table live in the slice design. Tasks reference them and do not repeat them. Use the design's row notes and footer texts verbatim.
- Key files: `pipeline/state.py`, `stats/usage_report.py`, new `stats/{planning_docs,git_history,effort_report,producer_report}.py`, `cli/commands/stats.py`, `cli/stats_views.py`, `documents/frontmatter.py`, `review/persistence.py`.
- Implementation choices not spelled out in the design, fixed here so no task has to decide them:
  - **Renderers split by report.** `cli/stats_views.py` is 242 lines. The `runs` renderer goes there; `slice`/`slices` go in new `cli/stats_effort_views.py` and `producers` in new `cli/stats_producer_views.py`. Shared cells (`count_cell`, cost cells, totals) are imported from `stats_views`, not copied.
  - **Frontmatter from text.** `git show` returns text, not a path. Extract `parse_frontmatter(text) -> dict[str, object] | None` from `read_frontmatter` in `documents/frontmatter.py`; `read_frontmatter` calls it. No second YAML parse path.
  - **Document locations.** Add `SLICES_DIR` and `ARCHITECTURE_DIR` beside the existing `REVIEWS_DIR` / `TASKS_DIR` in `review/persistence.py`. Planning readers take a project root and use these constants.
  - **Split task files.** A slice whose tasks span `{index}-tasks.{name}-1.md`, `-2.md`, … is read as one task list in suffix order. The slice window starts at the commit that added the earliest of them.
  - **Git injection.** `GitHistory(project_root, run=run_git)` takes the git runner as a parameter (production passes `run_git`). Tests pass a counting wrapper around the real `run_git` to assert D6's call count.
  - **`min_n`** is read in the CLI with `get_typed_config("metrology.min_evidence_n", int)` and passed to `producer_report`; the core reads no config.
- Every code task ends with `ruff format`, `ruff check`, `pyright` (zero errors) and the touched tests. Commit on the slice branch where a task says so.
- #214 closes when this slice merges (Phase 7). #210 stays open for slice 177.
- Effort: 3/5. Next planned slice: 177 Producer Replay and Pairwise Judging.

## Tasks

### Loop-round persistence (D3)

- [ ] **Task 1: Persist every loop round in `StepState`**
  - [ ] Read the target (`cf config get git.integration_branch`, empty means `main`) and create `176-slice.effort-calibration-and-producer-model-effectiveness` from it
  - [ ] In `pipeline/state.py`, `StepState` gains `prior_round_results: list[list[dict[str, object]]] = []`, `accepted: bool = False`, `exhausted: bool = False`, each with a one-line comment citing 176 D3. No schema version bump.
  - [ ] `_append_step` serializes `step_result.prior_rounds` as one list of `dataclasses.asdict(ActionResult)` per earlier round, in order, and copies `accepted` and `exhausted` from the `StepResult`
  - [ ] `action_results`, the hoisted `verdict` and `score`, and `outputs` still come from the final round only; no other reader changes
  - [ ] Confirm how `StepResult.prior_rounds` groups rounds (a flat `list[ActionResult]` at `executor.py:226`). If round boundaries cannot be recovered from it, change the executor to keep `prior_rounds` as `list[list[ActionResult]]` and update `executor.py:643` (`prior_outputs`) to flatten it. Record which case applied in the commit body.
  - **Success:** a loop step's state file holds one `prior_round_results` entry per earlier round, plus `accepted` / `exhausted`; non-loop steps write `[]`, `False`, `False`

- [ ] **Task 2: Test loop-round persistence**
  - [ ] In `tests/pipeline/` (beside the existing state tests): a `StepResult` with two earlier rounds round-trips through `_append_step` / `load` with rounds in order and `accepted` / `exhausted` preserved
  - [ ] A state file written without the three keys (copy an existing fixture or build one by dropping them) loads with `[]`, `False`, `False`
  - [ ] The final round's `verdict` hoist is unchanged when earlier rounds carry different verdicts
  - [ ] If Task 1 changed `prior_rounds` grouping: an executor test shows `prior_outputs` still sees every round (#170 behavior)
  - [ ] Run `pytest tests/pipeline -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 3: Earlier rounds and partial loops in `run_usage_report`**
  - [ ] `ActionUsageRow` gains `round: int | None = None` (1-based; `None` for non-loop steps). For a loop step, rows for `prior_round_results` come first with rounds `1..k`, then the final round's rows with round `k+1`
  - [ ] A malformed `prior_round_results` entry (not a list, or an item not a mapping) yields an `unreadable` row and one WARNING naming run and step, the same handling as 175's `_row`
  - [ ] `RunUsageReport` gains `partial_loop: bool`: true when `status` is not `completed` and `current_step` names a loop step (compare `step_type` through the loop step type constant, not a literal)
  - [ ] `UsageTotals` are built from every round's records
  - [ ] `render_run_report` shows the round in the step cell for loop rows and prints the row note `partial loop not recorded` when `partial_loop`; `run_report_json` adds `round` per row and `partial_loop`
  - [ ] A run with no loop steps renders exactly as before (Integration Requirements)
  - **Success:** `sq stats run` lists every round of a loop and its totals include them

- [ ] **Task 4: Test earlier-round usage rows**
  - [ ] In `tests/stats/test_usage_report.py`: a two-round loop yields rows with rounds 1 and 2, and totals equal the sum of both rounds' records
  - [ ] A pre-176 run file (no `prior_round_results`) reports the same rows and totals as before this slice
  - [ ] Malformed `prior_round_results` → `unreadable` row + WARNING (assert with `caplog`)
  - [ ] A `failed` run whose `current_step` is a loop step → `partial_loop` true and the note in rendered output; a `completed` run → false
  - [ ] Existing `tests/cli/test_stats.py` output assertions for loop-free runs still pass unchanged
  - [ ] Run `pytest tests/stats tests/cli/test_stats.py -q`, ruff, pyright
  - [ ] Commit: `feat: persist every loop round and report it in sq stats run`
  - **Success:** tests pass, zero pyright errors

### Planning-document readers (D4)

- [ ] **Task 5: Shared frontmatter and path constants**
  - [ ] Extract `parse_frontmatter(text)` from `read_frontmatter` in `documents/frontmatter.py` (same `None` rules); `read_frontmatter` reads the file and calls it
  - [ ] Add `SLICES_DIR` and `ARCHITECTURE_DIR` to `review/persistence.py` beside `TASKS_DIR`
  - [ ] Add a test for `parse_frontmatter`: valid block, no fence, unclosed fence, non-mapping YAML
  - [ ] Run `pytest tests/documents -q`, ruff, pyright
  - **Success:** existing frontmatter tests pass unchanged; the new test passes

- [ ] **Task 6: Real-file parser fixtures**
  - [ ] Create `tests/stats/fixtures/planning/` with verbatim copies of `100-tasks.foundation.md`, `170-tasks.profile-aware-dispatch-model-routing.md`, `175-tasks.usage-and-cost-tracking.md`, `173-tasks.user-definable-actions-on-supported-events.md`, and `architecture/140-slices.pipeline-foundation.md`
  - [ ] Add one synthetic two-part task file (`-1.md`, `-2.md`) and one task file containing `**Effort**: Relative`, for cases no real file covers alone. Mark them synthetic in a fixture README line.
  - [ ] Record, from reading the real files, the expected task numbers, efforts and commit subjects for each fixture in the test module (not in the fixture)
  - **Success:** fixtures are byte-identical to the repo files at copy time

- [ ] **Task 7: `read_task_file` in `stats/planning_docs.py`**
  - [ ] New module with `PlannedTask` and `PlannedSlice` exactly as in the design's API Contracts
  - [ ] `read_task_file(paths) -> tuple[PlannedTask, ...]` over one task file or an ordered list of split parts, parsing each field per D4:
    1. Task headings: `**Task N: Title**`, `### Task N: Title`, `### TN: Title`, with or without checkbox, any indentation. Items before the first heading are not tasks.
    2. Effort: `Effort: N`, `**Effort**: N`, `**Effort:** N`, each with optional `/5`, optional checkbox or bullet. Non-numeric → `None` and a WARNING naming file and line.
    3. Commit subjects: ``Commit: `subject` `` and `git commit -m "subject"` anywhere in a line (e.g. after `git add … &&`)
    4. Checkboxes: the task's own item and its sub-items, `checked` and `total`
  - [ ] `read_task_files_for(index, project_root)` finds `{index}-tasks.*.md` under `TASKS_DIR` and returns `None` when there is none
  - [ ] No git, no Typer imports
  - **Success:** every fixture parses to a non-empty task tuple

- [ ] **Task 8: Test the task-file reader**
  - [ ] New `tests/stats/test_planning_docs.py`. Per real fixture, assert the recorded task numbers, efforts and commit subjects (100: `**Effort**: 1/5` headings; 170: `### TN:` with `git commit -m`; 175: bold-checkbox tasks with 16 ``Commit:`` subjects; 173: tasks with no subjects)
  - [ ] Split fixture parts read as one ordered list
  - [ ] `**Effort**: Relative` → `effort is None` + WARNING naming file and line
  - [ ] Checked/total counts for one fully checked and one partly checked task
  - [ ] A parser that returns no tasks for any real fixture fails the test (D4)
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 9: Slice plans and slice status**
  - [ ] `read_slice_plans(project_root) -> dict[int, PlannedSlice]` reads every `*-slices.*.md` under `ARCHITECTURE_DIR`: entries `**(NNN) Title**`, `[x]` / `[ ]`, `Effort: N/5` anywhere in the entry. `tasks` is filled from `read_task_files_for`.
  - [ ] `slice_status(index, project_root) -> tuple[bool, str | None]`: `complete` from the slice design frontmatter `status: complete` (not the plan checkbox), and `dateCreated` for `--since`
  - [ ] An index in no plan file raises a typed error carrying the plan files searched (D9 row "unknown index")
  - **Success:** every entry in the 140 fixture is read with its index, title and effort

- [ ] **Task 10: Test slice plans and status**
  - [ ] Against the 140 fixture: entry count, a checked and an unchecked entry, an entry with `Effort: N/5` and one without
  - [ ] `slice_status` on a temp design with `status: complete`, one with another status, and a missing design
  - [ ] Unknown index → the typed error lists the plan files searched
  - [ ] Run `pytest tests/stats tests/documents -q`, ruff, pyright
  - [ ] Commit: `feat: add planning-document readers for effort reports`
  - **Success:** tests pass, zero pyright errors

### Git history (D5, D6)

- [ ] **Task 11: `GitHistory` log pass**
  - [ ] New `stats/git_history.py`, the only `stats/` module that runs git. `WindowSource` and `ReviewRound` as in the API Contracts; a frozen `Commit` (sha, parents, authored_at, subject, changes as `(status, path)` pairs)
  - [ ] `GitHistory(project_root, run=run_git)`. `load()` runs exactly `git for-each-ref refs/heads` and one `git log --all --name-status --format=<sha, parents, %aI, subject>` and builds the in-memory graph
  - [ ] Not a git repo or git missing → typed error naming the cwd. `run` returns `None` or non-zero for either call → typed error naming the git command; never a partial graph (D9)
  - [ ] Query helpers, all in memory: branch tip for `{index}-slice.*` (match `refs/heads/` names structurally), first-parent chain, commit that added a path, commits touching a path glob
  - [ ] Commit bodies and diffs are never requested
  - **Success:** two git calls build the graph; failures raise, never return partial data

- [ ] **Task 12: Test the log pass**
  - [ ] `tests/stats/conftest.py`: a fixture that builds a temp git repo with a `main`, a `NNN-slice.x` branch, a task file commit, code and document commits, and controlled author dates. This fixture serves Tasks 12–20.
  - [ ] Graph contents: parents, `%aI` dates, subjects, name-status changes
  - [ ] A counting wrapper around `run_git` sees exactly 2 calls for `load()`
  - [ ] Failure signals: temp dir without git → error naming cwd; a `run` stub returning `None` for the log call → error naming the command and no graph
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 13: Review rounds from committed versions**
  - [ ] `review_rounds(index, review_type) -> list[ReviewRound]`: versions of `{index}-review.{type}.*.md` under `REVIEWS_DIR` and its `archive/`, from the in-memory graph; deduplicated by blob id, ordered by commit date
  - [ ] Each version read with `git show <sha>:<path>` through `run`, parsed with `parse_frontmatter`: `verdict`, `aiModel`, `revision_number`, `runId`, cost keys
  - [ ] `git show` failure or unreadable frontmatter → that round skipped, WARNING naming sha, path (and git stderr when present), and a skipped count on the result for the footer
  - [ ] `rounds_to_accept(rounds)`: count up to and including the first verdict `LoopCondition.REVIEW_CONCERNS_OR_BETTER.met_by_verdict` accepts; later rounds listed, not counted; `None` when none accepted
  - [ ] A flag on the result when the earliest round is authored before 941 landed (footer: rounds are a lower bound). 941 was fast-forwarded onto `main` (no merge commit) and its branch exists only in this repo, so the cutoff is one module constant, the date 941 reached `main` (20261013), with a comment citing 941 and design "Consumes from Other Slices"
  - **Success:** the call count for a report is `2 + V` (V = versions read)

- [ ] **Task 14: Test review rounds**
  - [ ] In the temp repo: three committed versions (FAIL, CONCERNS, PASS) plus an archive copy of round 1 → three rounds after dedupe, rounds-to-accept 2
  - [ ] A version with broken frontmatter, and a `run` stub failing one `git show` → each skipped with WARNING naming sha and path; skipped count 2
  - [ ] Call count `2 + V` asserted with the counting wrapper
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 15: Slice window and task attribution**
  - [ ] `slice_window(index, task_paths)`: `BRANCH` when `refs/heads/{index}-slice.*` exists — the tip's first-parent chain back to, not including, the commit that added the earliest task file; else `NONE` with no commits
  - [ ] `attribute(window, tasks)`: per D5 rules 1–2 — exact subject match, earliest in window on duplicates, groups from the task after the previous marker through the marker task, non-marker commits counted as `extra`, unmatched subject → `marker not found` with actuals `unknown`
  - [ ] Implementation commit: touches any path outside `project-documents/` (D5 rule 4). Fix-up: implementation commit authored after the commit that first added `{index}-review.code.*` (rule 5)
  - [ ] Spans from author dates; labeled `span` downstream
  - **Success:** attribution needs no git calls beyond `load()`

- [ ] **Task 16: Test window and attribution**
  - [ ] Branch present → `BRANCH`, window excludes the task-file commit and anything before it; branch absent → `NONE`
  - [ ] Three prescribed subjects, one reworded → two groups with markers and extras, one `marker not found`
  - [ ] Duplicate subject in window → earliest wins
  - [ ] Document-only commits are not implementation commits; a code commit after the code review artifact is a fix-up, one before is not
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add git history reader for slice windows and review rounds`
  - **Success:** tests pass, zero pyright errors

### Effort reports (D2, D7)

- [ ] **Task 17: `slice_effort_report`**
  - [ ] New `stats/effort_report.py`: `slice_effort_report(index, *, project_root, history, state_manager)` returns a frozen report with the D7 header (planned effort, window source, span, implementation commits, fix-ups, review rounds per type, recorded spend) and one row per task group (tasks, planned effort as the sum of task efforts or `None`, checked/total, marker, extra, span)
  - [ ] Recorded spend: `usage_totals` over records from runs whose `params["slice"]` equals the index (all rounds, via Task 3) plus `reviews_usage_report` for the slice (D7)
  - [ ] No task file → no groups and the row note `no task file`; window `NONE` → groups `unavailable`
  - [ ] Footer counts: markers not found, review rounds skipped, lower-bound flag, unreadable run files
  - [ ] `to_json_dict()` serializes the dataclass fields
  - **Success:** the core imports no Typer and runs no git outside `GitHistory`

- [ ] **Task 18: Test `slice_effort_report`**
  - [ ] Temp repo with planning docs, a branch, review versions and a run file for the index: header values, groups, and recorded spend match the inputs
  - [ ] Missing task file → `no task file`; missing branch → `unavailable` groups with planned effort, rounds and spend still present
  - [ ] Unknown index → the typed error with plan files searched
  - [ ] `to_json_dict()` values equal the dataclass values
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 19: `slices_effort_report`**
  - [ ] `slices_effort_report(*, since, project_root, history, state_manager)`: completed slices (D4 status) grouped by planned effort `1..5` then `unplanned`; per level n and median (min–max) of span, implementation commits, fix-ups, design rounds, tasks rounds, recorded spend (D2: distributions, not ratios)
  - [ ] `since` filters on the slice design's `dateCreated`
  - [ ] A measure that is `unknown`/`unavailable` for a slice is left out of that measure's distribution, and the measure's n is reported separately from the level's n
  - [ ] Every task counts as `untagged` (#218); no completed slices → empty report with that reason
  - [ ] One `GitHistory.load()` for the whole report
  - **Success:** `to_json_dict()` has `levels[].measures`

- [ ] **Task 20: Test `slices_effort_report`**
  - [ ] Three completed slices at two effort levels plus one `unplanned` → correct grouping, n, median and range
  - [ ] `--since` excludes an older slice; a not-complete slice is excluded
  - [ ] A slice with no branch contributes rounds and spend but not commit measures
  - [ ] Call count `2 + V` for the whole rollup
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add planned vs actual effort report cores`
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 21: `sq stats slice` and `sq stats slices` CLI**
  - [ ] In `cli/commands/stats.py`: `slice <index>` and `slices [--since YYYYMMDD]`, both with `--json`; project root is the cwd; build `GitHistory(Path.cwd(), run=run_git)` and `StateManager()`
  - [ ] Map typed errors to `Error: …` on stderr and exit 1 (not a git repo, git command failure, unknown index)
  - [ ] New `cli/stats_effort_views.py`: renderers matching the design's UI layout, `—` for missing values, `span` label, `recorded spend` label with the interactive-work footer, window source and marker coverage printed; widths via `cli/columns.py` `fit_widths`
  - [ ] Empty rollup prints the message and exits 0
  - **Success:** `sq stats slice 175` and `sq stats slices` render without error in this repo

- [ ] **Task 22: Test the effort CLI**
  - [ ] In `tests/cli/test_stats.py` (or a new `test_stats_effort.py` if it would exceed ~300 lines), using the temp repo fixture with `chdir`: table and `--json` for both commands; JSON values equal the table's
  - [ ] Failure signals: no git repo → exit 1 naming the cwd; unknown index → exit 1 naming plan files; empty rollup → message, exit 0
  - [ ] No file, ref, or run state is written (compare `git status --porcelain`, `for-each-ref`, and the runs dir before/after)
  - [ ] Run `pytest tests/cli tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add sq stats slice and sq stats slices`
  - **Success:** tests pass, zero pyright errors

### Producer effectiveness (D8)

- [ ] **Task 23: `producer_report`**
  - [ ] New `stats/producer_report.py`: `producer_report(*, phase, state_manager, min_n)`; `phase` is `StepTypeName.DESIGN` or `TASKS`
  - [ ] Units per D8: top-level `completed_steps` entries with that `step_type`; the loop is the entry at i+1 when its type is the loop type; `each` children and loops with no phase step before them are not units
  - [ ] Config key from the phase step's `action_results`: dispatch model (answering, else requested), profile, `usage.effort`, and the reviewer model from the review action. Pipeline name is a column, not part of the key
  - [ ] Per config: n, first-round verdict counts (by `Verdict`), median revise rounds (D3 rounds, else loop `iteration`), accepted rate (loop `accepted`, else first verdict through `met_by_verdict`), failure rate (phase step status failed), cost per accepted artifact with "k of m priced"
  - [ ] Cells with n below `min_n` are `below floor` and not ranked. Excluded from units, each with a footer count: runs with `partial_loop`, phase steps without a dispatch or review action, unreadable run files (from `scan_runs`)
  - [ ] Footer flags per D8 Honesty: observational, templates pooled, pre-175 runs unpriced, pre-176 runs without per-round data
  - [ ] `to_json_dict()`
  - **Success:** the report reads run state only through `StateManager.scan_runs()`

- [ ] **Task 24: Test `producer_report`**
  - [ ] Build run files with `design, loop` and `tasks, loop` step pairs across two configs: grouping, first-round counts, median rounds, accepted and failure rates, cost per accepted with priced counts
  - [ ] Same dispatch model with two reviewer models → two configs
  - [ ] A loop with no preceding phase step, a phase step inside `each`, a partial-loop run, and a phase step without a review action → each excluded and counted in its footer
  - [ ] n below `min_n` → `below floor`; a pre-176 run file uses loop `iteration` for rounds
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 25: `sq stats producers` CLI**
  - [ ] `producers [--phase design|tasks]` with `--json`; `--phase` parsed into `StepTypeName` (reject other values with an error naming the allowed ones). Without `--phase`, report both phases.
  - [ ] Read `min_n` with `get_typed_config("metrology.min_evidence_n", int)`; `ValueError` → error naming the key and value, exit 1
  - [ ] New `cli/stats_producer_views.py`: the design's layout, `n` on every row, `below floor` cells, the footer lines; no phase runs → message, exit 0
  - **Success:** `sq stats producers --phase design` renders in this repo

- [ ] **Task 26: Test the producers CLI**
  - [ ] Table and `--json` agree on values; `--phase` filtering; invalid `--phase` → exit nonzero with the allowed values
  - [ ] Non-integer `metrology.min_evidence_n` in a temp project config → exit 1 naming key and value
  - [ ] No phase runs → message, exit 0; nothing written to the runs dir
  - [ ] Run `pytest tests/cli tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add sq stats producers for observed producer effectiveness`
  - **Success:** tests pass, zero pyright errors

### Cross-run totals

- [ ] **Task 27: `runs_usage_report`**
  - [ ] In `stats/usage_report.py`: `runs_usage_report(*, slice_index, pipeline, state_manager)` over `scan_runs()`; one row per run (run id, pipeline, slice, status, started, LLM actions recorded, tokens, cost, `partial_loop`), built from `run_usage_report`'s row logic, not a copy of it
  - [ ] Filters on `params["slice"]` and pipeline name; total with 175's D9 rules via `usage_totals`; unreadable file count from `scan_runs`
  - [ ] `to_json_dict()`
  - **Success:** `usage_report.py` stays under ~300 lines

- [ ] **Task 28: Test `runs_usage_report`**
  - [ ] Three runs across two slices and two pipelines: each filter, both together, and no filter
  - [ ] Totals equal the sum of per-run totals including loop rounds; a pre-175 run counts as unpriced, not $0
  - [ ] An unreadable run file → footer count; a partial-loop run → row note
  - [ ] Run `pytest tests/stats -q`, ruff, pyright
  - **Success:** tests pass, zero pyright errors

- [ ] **Task 29: `sq stats runs` CLI**
  - [ ] `runs [--slice INDEX] [--pipeline NAME]` with `--json`; renderer in `cli/stats_views.py` with the `Total` row in the `$X (k of m priced)` form
  - [ ] No matching runs → message, exit 0
  - [ ] Tests: table/JSON parity, filters, empty case, nothing written
  - [ ] Run `pytest tests/cli tests/stats -q`, ruff, pyright
  - [ ] Commit: `feat: add sq stats runs`
  - **Success:** tests pass, zero pyright errors

### Documentation and verification

- [ ] **Task 30: Docs and wrappers**
  - [ ] README `## Usage and cost (sq stats)`: the four subcommands, `span` and `recorded spend` meanings, and the observational caveat for `producers`
  - [ ] `commands/sq/stats.md` and `commands/agents/sq-stats/SKILL.md`: extend the subcommand list (pass-through stays unchanged)
  - [ ] `140-arch.pipeline-foundation.md` run-state section: the three `StepState` fields
  - [ ] Confirm slice plan entry 177 in `140-slices.pipeline-foundation.md` still matches what this slice provides (D8 config key, D3 rounds); edit only if it does not
  - [ ] CHANGELOG: short user-facing bullets under Unreleased (new subcommands; `sq stats run` now counts every loop round)
  - [ ] Commit: `docs: document sq stats slice, slices, producers, and runs`
  - **Success:** each D9 row note and footer text appears in code exactly once (grep)

- [ ] **Task 31: Full validation and verification walkthrough**
  - [ ] `ruff format`, `ruff check`, `pyright` (zero errors), full `pytest` green
  - [ ] Confirm each D9 failure-table row maps to a passing test; list the test name per row in the commit body
  - [ ] `grep` confirms no Typer import under `stats/`, no `run_git` use outside `stats/git_history.py` within `stats/`, and no bare-string comparison of step types, verdicts or window sources
  - [ ] Run design Verification Walkthrough steps 2–7 with `.venv/bin/sq` in this repo; record the output of each in the commit body. Step 1 (scratch project live run) and step 8 (slash parity) need a live model run and Claude Code respectively: run them if available, otherwise list them as not run.
  - [ ] Comment on #214 and #210 with what landed (subcommands, the observed-only scope for #210, slice 177 for replay)
  - [ ] Commit: `test: verify slice 176 reports against this repo`
  - **Success:** full suite green; walkthrough results recorded; issues commented
