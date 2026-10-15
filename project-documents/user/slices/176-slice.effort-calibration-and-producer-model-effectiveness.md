---
docType: slice-design
slice: effort-calibration-and-producer-model-effectiveness
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [175]
interfaces: []
dateCreated: 20261015
dateUpdated: 20261015
status: not_started
---

# Slice Design: Effort Calibration and Producer Model Effectiveness

## Overview

Slice 175 records what every LLM action spends. This slice turns those records, the project's git history, and its planning documents into the two reports 175 deferred (175 D10):

- **Planned vs actual effort ([#214](https://github.com/ecorkran/squadron/issues/214)).** `sq stats slice <index>` and `sq stats slices` compare each slice's planned `Effort` with what it took: commits, elapsed span, review rounds per phase, post-review fix-ups, and recorded spend.
- **Producer effectiveness from observed runs ([#210](https://github.com/ecorkran/squadron/issues/210)).** `sq stats producers` reports, per phase, each producer config's first-round verdicts, revise rounds, acceptance and failure rates, and cost per accepted artifact, each with its sample size.
- **`sq stats runs`**, the cross-run totals deferred from 175.

The replay runner and pairwise judge in #210 (regenerating past artifacts per config in throwaway worktrees) split into a follow-on slice (D1).

## Value

- **Estimates get checked.** Planning assigns an `Effort` to every slice and nothing ever compares it with the outcome. `sq stats slices` shows, for each planned effort level, what slices at that level actually took, with n.
- **Model choice per phase becomes evidence.** P4 and P5 pipeline runs already record the producer model, the reviewer's verdict per round, and (since 175) the cost. `sq stats producers` shows which config gets accepted in fewer rounds for less money, using runs that happened anyway.
- **Loop cost becomes correct.** Run state keeps only a loop's final round today, so 175's `sq stats run` undercounts any run that revised. This slice persists every round (D3), which fixes that report too.
- **Data that can be pooled.** Every report has `--json`, so results from several projects can be combined later.

## Technical Scope

**Included:**

1. **Loop-round persistence (D3).** `StepState` keeps the action results of every loop round, plus the loop's `accepted` and `exhausted` outcome. `sq stats run` includes earlier rounds.
2. **Planning-document readers (D4).** These read slice plan entries (index, planned slice effort), task files (task number, title, optional per-task `Effort`, checkbox counts, prescribed commit subjects) and slice design status.
3. **Git history reader (D5, D6).** This reads commits for a slice, attributes them to task groups through the task file's prescribed commit subjects, and reads per-round review verdicts from the committed versions of review artifacts.
4. **`sq stats slice <index>`**, which reports one slice per task group, and **`sq stats slices`**, which rolls up completed slices by planned effort level (D7).
5. **`sq stats producers [--phase design|tasks]`**: observed producer effectiveness (D8).
6. **`sq stats runs [--slice INDEX] [--pipeline NAME]`**: one row per run, plus totals.
7. `--json` on every new subcommand. The existing `/sq:stats` slash command and `sq-stats` skill pass the arguments through unchanged, so no wrapper code is needed.

**Excluded:**

- **Replay runner, pairwise judge, and the metrology record type** (#210 items 2–4 beyond the observed report). These move to a follow-on slice plan entry (D1), which also takes this slice's dependency on 320.
- **Task-kind parsing and the by-kind split** ([#218](https://github.com/ecorkran/squadron/issues/218)). The tag format is not defined yet ([ai-project-guide#42](https://github.com/ecorkran/ai-project-guide/issues/42)), and no task file carries one. Every task is in the `untagged` bucket until it is.
- **Attributing post-review fix-ups to individual tasks.** Fix-ups are counted per slice only. File-overlap attribution is a guess this slice does not make.
- **Producer data from `sq review --max`.** It writes no run state (`pipeline/review_revise.py:33`, D4 of 941), so the observed producer report covers pipeline runs only. The review rounds still count in the effort reports, because they come from git.
- **Prompt-template identity in the producer config.** Neither run state nor dispatch metadata records which prompt-template revision a dispatch used. The report pools across template revisions and says so (D8).
- **MCP tool** ([#217](https://github.com/ecorkran/squadron/issues/217)), for the same reason as in 175.

## Dependencies

### Prerequisites

- **175** (complete): `UsageRecord` in `ActionResult.metadata["usage"]`, `stats/usage_report.py` (`run_usage_report`, `usage_totals`), `stats/reviews_report.py`, `cli/commands/stats.py`, `cli/stats_views.py`, and the `/sq:stats` wrappers.
- **321** (complete): the `metrology.min_evidence_n` config key. Only the key is read; the metrology store is not used.
- **941** (complete): `commit_each_iteration: true` is required on review-revise loops, so every round's review artifact is committed. Per-round verdicts can therefore be read from git.

### Interfaces Required

- `StateManager.scan_runs()` / `list_runs()` / `load()` (`pipeline/state.py:675,700,618`).
- `StepResult.prior_rounds`, `accepted` and `exhausted` (`pipeline/executor.py:215-226`), which today are dropped by `_append_step` (`state.py:484-538`).
- `StepTypeName` (`pipeline/steps/__init__.py:27-29`: `DESIGN`, `TASKS`, `IMPLEMENT`) to identify phase steps.
- `run_git` (`review/git_utils.py:28`) and `read_frontmatter`.
- `LoopCondition.REVIEW_CONCERNS_OR_BETTER.met_by_verdict` (`pipeline/loop_config.py:22`), the single definition of an accepted verdict.
- Config key `metrology.min_evidence_n` (`config/keys.py:221`, `int`, default 5, defined by 321). It is read with `get_typed_config(..., int)`. That call raises `ValueError` on a non-integer value, and the CLI reports it as an error and exits 1.
- Review artifact frontmatter: `verdict`, `aiModel`, `revision_number`, `runId`, `slice`, plus the 175 cost and token keys. The file name is `{index}-review.{type}.{name}.md`.

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| `StepState` loop fields | `pipeline/state.py` | add `prior_round_results`, `accepted`, `exhausted`, with defaults so older files still load |
| Run usage report | `stats/usage_report.py` | rows for earlier rounds, with a round number |
| Planning readers | `stats/planning_docs.py` (new) | `read_slice_plans`, `read_task_file`, `slice_status`. Pure parsing, no git |
| Git history | `stats/git_history.py` (new) | `git log` and `git show` through `run_git`; typed commits and review-round records |
| Slice effort core | `stats/effort_report.py` (new) | `slice_effort_report`, `slices_effort_report` |
| Producer core | `stats/producer_report.py` (new) | `producer_report` |
| Runs core | `stats/usage_report.py` | `runs_usage_report` |
| CLI | `cli/commands/stats.py`, `cli/stats_views.py` | `slice`, `slices`, `producers`, `runs` subcommands and their renderers |

The cores take their inputs as parameters (a `StateManager`, a project root, a `GitHistory`), contain no Typer code, and return typed reports, which is 175's split. `stats/git_history.py` is the only module that runs git.

### Data Flow

```
task files ─┐
slice plans ├─ planning_docs ─┐
designs ────┘                 │
git log + show ───── git_history ─┼─ effort_report ──► sq stats slice | slices
run state ─ StateManager ─────┤
                              └─ producer_report ─► sq stats producers
                                 usage_report ────► sq stats run | runs
```

Everything is computed when the report is read, and nothing is stored. That matches 175: one source of truth per fact.

### State Management

The only change to persisted data is D3: three new `StepState` fields with defaults, and no schema version bump, the same as 175's metadata addition. Files written before this slice load with `prior_round_results = []`, and every report marks such a loop step's earlier rounds as `not recorded`. When the slice lands, the run-state section of `140-arch.pipeline-foundation.md` gains the three fields.

## Technical Decisions

### D1 — #210 splits: observed report here, replay and judging in a follow-on

The slice plan leaves two questions to this design: whether (b) splits again, and whether it adopts an existing eval tool.

**Split.** Replay needs real dispatches in isolated worktrees, a scoring method, a new metrology record type, and an operator to run experiments. (a) is read-only and deterministic. The two share only the run-state readers. The observed producer report (D8) needs the same readers as (a), costs nothing to run, and gives #210 its first answer from runs that already happened. It stays here. Replay, the pairwise judge with order swap, and the metrology `producer_score` record go to slice plan entry 33 (Producer Replay and Pairwise Judging), which depends on this slice and on 320.

**Eval tooling.** Borrow the method (pairwise comparison with order swap, Bradley-Terry or Elo aggregation, n on every number) and adopt no tool. promptfoo is a Node CLI with its own provider layer. inspect_ai is Python, but it also brings its own model-provider layer. Either one would run producers outside squadron's profiles, aliases, and dispatch path, and that path is what is being measured. The git replay is squadron-specific in any case (#210). The follow-on records this decision and does not reopen it.

### D2 — Planned effort is ordinal; report distributions, not ratios

`Effort` is a 1–5 rank, not a quantity, so "actual divided by planned" means nothing. `sq stats slices` groups completed slices by planned slice effort and reports, for each level, the median and range of each actual measure along with n. Per-task planned effort is shown where the task file has it, and a task group's planned effort is the sum of its tasks' values. Most task files do not have per-task effort: none of 160–175 do, and 95 of 159 files in this repo have no effort marker at all. The slice-level `Effort: N/5` in the slice plan entry is therefore the primary planned figure.

### D3 — Persist every loop round

`_append_step` saves `step_result.prior_rounds` as `prior_round_results: list[list[dict]]` (one list of `asdict(ActionResult)` per earlier round, in order), along with `accepted` and `exhausted`. A loop's earlier dispatches and reviews spent tokens, and their verdicts are how rounds-to-accept is computed. The final round stays in `action_results`, so conditions, failure reporting, and the hoisted `verdict` read it exactly as they do now.

`run_usage_report` emits rows for earlier rounds with a `round` value (1-based; the final round is the highest). `UsageTotals` then cover every round, which corrects 175's loop undercount. The size cost is one more copy of each round's action dicts, in a file that already holds the final round's.

### D4 — Lenient planning-document parsing, anchored on real files

Formats vary across the repo's own history, so each field is parsed by its meaning, not its layout (CLAUDE.md parsing rules):

- **Task heading**: `**Task N: Title**`, `### Task N: Title`, `### TN: Title`, with or without a checkbox and with varying indentation. Items before the first task heading (setup, context) are not tasks.
- **Effort**: `Effort: N`, `Effort: N/5`, `**Effort**: N`, `**Effort:** N`, with an optional checkbox or bullet. A non-numeric value (`**Effort**: Relative` exists once) is read as no effort and logs a WARNING naming the file and line.
- **Prescribed commit subject**: ``Commit: `subject` `` or `git commit -m "subject"`, in the task that contains it.
- **Checkboxes**: each task's own item and its sub-items, counted checked and total.
- **Slice plan entries**: `**(NNN) Title**` with `[x]` / `[ ]`, and `Effort: N/5` anywhere in the entry. Every `*-slices.*.md` under `project-documents/user/architecture/` is read, so slices from all initiatives are covered.
- **Completed slice**: the slice design's frontmatter `status: complete`. The plan checkbox is not used, because it can lag the design's own status.

Test fixtures are copies of real files: `100-tasks.foundation.md` (heading tasks with `**Effort**`), `170-tasks.*` (`### TN:` with `git commit -m`), `175-tasks.*` (bold-checkbox tasks with ``Commit: ` ` ``), and `140-slices.pipeline-foundation.md`. A parser that returns nothing for one of them fails its test.

### D5 — Task attribution through prescribed commit subjects

Code commits do not cite task numbers, but task files written since 174 prescribe exact commit subjects, and all 16 in 175's file match `git log` verbatim. These subjects are the anchors:

1. **Marker commits.** Each prescribed subject is matched exactly against commits in the slice window (below). A subject that matches more than one commit takes the earliest one inside the window. A subject with no match is reported as `marker not found`, and that group's actuals are `unknown`.
2. **Task groups.** A group runs from the task after the previous marker task through the marker task. Its commits are the window's commits after the previous marker, up to and including this one. Commits that are not the marker are counted as `extra` commits in the group, which is the rework signal per task.
3. **Slice window.** The window is resolved in this order, and the source is printed:
   - `branch`: the local branch `{index}-slice.*` exists. The window is `git log --first-parent <commit that added the task file>..<branch>`.
   - `merge`: a merge commit `merge: slice {index}…` exists. The window is `M^1..M^2`.
   - `none`: neither exists. Implementation actuals and task groups are `unavailable`, and the slice still reports planned effort, review rounds, and spend.
4. **Implementation commit**: a commit in the window that touches any path outside `project-documents/`. Planning and review commits touch only documents.
5. **Post-review fix-up**: an implementation commit dated after the commit that first added the slice's `{index}-review.code.*` artifact.

Spans use author dates (`%aI`), which survive rebases. A span is wall-clock time and includes idle time. The report labels it `span`, not `time worked`.

### D6 — Review rounds come from git, not run state

Each review artifact is rewritten every round, but every round is committed (941). The rounds for slice `N`, review type `T`, are the committed versions of `N-review.T.*.md`, at top level and in `archive/`. The archive holds timestamped copies of earlier versions, so versions are deduplicated by blob id and ordered by commit date. Each version is read with `git show <sha>:<path>` through `run_git`, so every git call has its timeout and its WARNING. The version's frontmatter gives `verdict`, `aiModel`, `revision_number`, `runId`, and cost. Rounds-to-accept for a type is the number of versions up to and including the first one that `LoopCondition.REVIEW_CONCERNS_OR_BETTER.met_by_verdict` accepts. Any rounds after it are listed but not counted. This covers pipeline loops, `sq review --max`, and manual reviews in the same way.

**Bound.** One report invocation runs one `git log --name-status` pass, plus one `git show` per review artifact version it reads. Versions are read only for the slices the report covers. A test asserts the count.

### D7 — Report shapes

`sq stats slice <index>`: a header with planned slice effort, window source, span, implementation commits, fix-ups, review rounds per type, and recorded spend. Then one row per task group: tasks, planned effort (when present), checked / total, marker commit, extra commits, and span.

`sq stats slices [--since YYYYMMDD]`: one row per planned effort level (1–5, then `unplanned`), each with n and the median (min–max) of span, implementation commits, fix-ups, design rounds, tasks rounds, and recorded spend. Every task is `untagged` until #218.

`sq stats runs [--slice INDEX] [--pipeline NAME]`: one row per run (run id, pipeline, slice, status, started, LLM actions recorded, tokens, cost), with a total that uses 175's D9 rules.

**Recorded spend** for a slice is the sum of the `UsageRecord`s from runs whose `params["slice"]` equals the index, plus standalone review artifacts for that slice (175 `reviews_usage_report`, which already excludes pipeline artifacts). Interactive work in a Claude Code session is not recorded anywhere. The column is labeled `recorded spend`, and a footer says so.

### D8 — Observed producer effectiveness

**Unit.** A pipeline run's phase step (`StepTypeName.DESIGN` or `TASKS`), together with the loop step that follows it in the same run, if any.

**Producer config key.** The phase step's dispatch metadata gives model (answering, else requested), profile, and the `usage.effort` that was sent (175 D7). The key adds the reviewer's model from the phase step's review action, because rounds-to-accept depends on the reviewer (#210, "under a fixed reviewer"). Pipeline name is shown as a column but is not part of the key.

**Per config, per phase:**
- n runs
- first-round verdict counts
- median revise rounds (from D3 rounds, else the loop's `iteration`)
- accepted rate: the loop's `accepted`, or, when there is no loop, a first-round verdict that `LoopCondition.REVIEW_CONCERNS_OR_BETTER.met_by_verdict` accepts
- failure rate: the phase step's status is failed, which includes dispatch errors, stalls, and the 945 no-artifact post-condition
- cost per accepted artifact: total recorded cost of the phase and loop steps, divided by accepted runs, shown with D9's "k of m priced"

**Honesty.** Each cell carries n. A cell below `metrology.min_evidence_n` (see Interfaces Required) is marked `below floor` and not ranked. The footer states three things: the data is observational (different slices per config, so slice difficulty is a confound); prompt-template revisions are pooled; and runs from before 175 have no cost, and runs from before this slice have no per-round data.

### D9 — Failure modes

| Failure | Behavior | Signal |
|---|---|---|
| Not a git repo, or git missing | report not produced | error naming the cwd, exit 1 |
| `run_git` returns `None` for `git log` or `git show` (hang past the timeout, cannot run) | report not produced | `run_git`'s timeout WARNING, then an error naming the git command, exit 1; never a partial report |
| `git show <sha>:<path>` exits non-zero (missing object, e.g. in a shallow clone) | report not produced | error naming the sha, path, and git's stderr, exit 1 |
| `metrology.min_evidence_n` is not an integer | `producers` not produced | error naming the key and value, exit 1 |
| Shallow clone | report produced | WARNING plus footer `history is shallow; commit counts may be incomplete` |
| `sq stats slice` with an unknown index | nothing printed | error naming the index and the plan files searched, exit 1 |
| Task file missing for a slice | slice row has no task groups | row note `no task file`; included in `slices` |
| Prescribed subject not found | group actuals `unknown` | row `marker not found`; footer count |
| Non-numeric `Effort` | effort `None` | WARNING naming file and line |
| A review artifact version with unreadable frontmatter | that round skipped | WARNING naming sha and path; footer count |
| Unreadable or schema-obsolete run file | run skipped | footer `N run file(s) unreadable` (from `scan_runs`) |
| Malformed `prior_round_results` entry | that round's rows `unreadable` | WARNING naming run and step (same handling as 175 D9) |
| No completed slices / no phase runs | empty table | message saying which, exit 0 |

## Implementation Details

### API Contracts

```python
# stats/planning_docs.py
@dataclass(frozen=True)
class PlannedTask:
    number: int
    title: str
    effort: int | None
    checked: int
    total: int
    commit_subjects: tuple[str, ...]

@dataclass(frozen=True)
class PlannedSlice:
    index: int
    title: str
    effort: int | None
    complete: bool
    tasks: tuple[PlannedTask, ...] | None   # None when there is no task file

# stats/git_history.py
class WindowSource(StrEnum):
    BRANCH = "branch"; MERGE = "merge"; NONE = "none"

@dataclass(frozen=True)
class ReviewRound:
    review_type: str
    sha: str
    authored_at: datetime
    verdict: str | None
    model: str | None
    run_id: str | None
```

The core functions are `slice_effort_report(index, *, project_root, history, state_manager)`, `slices_effort_report(*, since, ...)`, `producer_report(*, phase, state_manager, min_n)` and `runs_usage_report(*, slice_index, pipeline, state_manager)`. Each one returns a frozen report dataclass that has a `to_json_dict()`.

**JSON.** Each report's `to_json_dict()` serializes its dataclass fields, the same way 175's `stats_views` serializers do, and adds `schema_version: 1`. The table and the JSON read the same values. A fixed cross-project key contract waits until something consumes pooled data.

### UI Specifications

`sq stats slice 175`, illustrative only (these are not real values):

```
Slice 175  Usage and Cost Tracking  planned effort 4/5  window: branch
span 1d 2h  impl commits 16  fix-ups 1  rounds: slice 3 · tasks 3 · code 1
recorded spend $4.12 (5 of 5 priced)

Group    Tasks  Effort  Done     Marker    Extra  Span
1        1–3    —       9/9      0ac74136      0  1h 12m
2        4–6    —       12/12    3812c815      0  38m
...
```

`sq stats producers --phase design` (again illustrative):

```
Phase design   min n 5   pipeline runs 36

Model / effort        Profile  Reviewer          n  First PASS/CONC/FAIL  Rev. rounds  Accepted  Failed  $/accepted
opus / high           sdk      deepseek4-flash  12  5 / 6 / 1             1            11/12     0/12    $2.40 (4 of 11 priced)
glm-flash / —         openai   deepseek4-flash   3  1 / 1 / 1             1            2/3       1/3     below floor
Observational: configs saw different slices. Prompt-template revisions are pooled.
```

Width handling reuses `cli/columns.py` (`fit_widths`), as in 175.

## Integration Points

### Provides to Other Slices

- **Replay follow-on (#210)**: the D8 producer config key and per-round run data from D3. The follow-on designs its own git interface for finding replay start points.
- **`sq stats run`**: per-round loop rows and correct loop totals.

### Consumes from Other Slices

- **175** usage records and report cores. A pre-175 run has no usage and reports `not recorded`, never $0.
- **941** committed rounds. A slice reviewed before `commit_each_iteration` existed shows only its committed versions, and the rounds count is a lower bound (stated in the footer when the earliest round predates 941's merge).

## Success Criteria

### Functional Requirements

1. A pipeline run with a review loop persists every round's action results, plus `accepted` and `exhausted`. `sq stats run` lists each round, and its totals include all rounds. Pre-slice run files load unchanged.
2. `sq stats slice 175` reports window source `branch`, 16 marker commits found, and review rounds for slice, tasks, and code that match the review artifact's git history.
3. `sq stats slice 173` (no markers) still reports planned effort, span, review rounds, and spend, and its task groups read `unavailable`.
4. Every D4 format in the real fixture files parses to the expected task numbers, efforts, and commit subjects.
5. `sq stats slices` groups completed slices by planned effort with n and median (min–max) per measure. `--since` filters by the slice design's `dateCreated`.
6. `sq stats producers --phase design|tasks` reports the D8 columns. Cells below `metrology.min_evidence_n` are marked and not ranked, and the observational footer is printed.
7. `sq stats runs --slice INDEX` lists that slice's runs and totals under 175 D9 rules.
8. Every new subcommand's `--json` emits the D7 / API Contracts keys. `/sq:stats slices` in Claude Code prints the same table as the CLI.
9. No subcommand writes a file, a git ref, or run state.

### Technical Requirements

- Every row of the D9 failure table has a test asserting its signal.
- A test asserts the D6 git call count for `slice` and `slices`.
- Parser fixtures are copies of real repo files (D4).
- `stats/` cores import no Typer. `stats/git_history.py` is the only module that runs git.
- Step types are compared through `StepTypeName`, verdicts through the existing verdict enum, and window sources through `WindowSource`. There are no bare string comparisons.
- ruff format, ruff check, pyright with zero errors, full suite green.
- CHANGELOG bullets. The README `sq stats` section gains the four subcommands and the observational caveat.

### Integration Requirements

- 175's existing `sq stats run` and `sq stats reviews` outputs are unchanged for runs without loops.

### Verification Walkthrough

Run these in this repo with `.venv/bin/sq` (editable install), unless noted. None of the commands exist before this slice.

1. **Loop rounds persist.** In the scratch project (`~/source/repos/manta/temp/scratch-945`), run `sq run P4 <index> -p model=glm-flash -p max-revisions=2` on a slice whose first review will not PASS. Then run `sq stats run <run_id>`. The loop rows show round 1 and round 2, and `Total` includes both. In the run file, the loop step has `prior_round_results` with one entry per earlier round, plus `accepted` / `exhausted`.
2. **One slice, with markers.** `sq stats slice 175` shows `window: branch` and 16 groups, each with a marker sha, and review rounds `slice 3 · tasks 3 · code ≥1`. Compare with `git log --oneline -- project-documents/user/reviews/175-review.slice.*`.
3. **One slice, without markers.** `sq stats slice 173` shows planned effort, span, and review rounds, and its groups read `unavailable`.
4. **Rollup.** `sq stats slices` prints one row per effort level, each with n. `sq stats slices --json | python -m json.tool` has `levels[].measures`.
5. **Producers.** `sq stats producers --phase design` lists configs from this machine's P4 runs, each with n. The cells below 5 read `below floor`, and the footer prints the observational caveat.
6. **Runs.** `sq stats runs --slice 175` lists 175's pipeline runs with a `Total` in the `$X (k of m priced)` form.
7. **Failure signals.** In a temp directory with no git repo, `sq stats slice 1` exits 1 and names the cwd. `sq stats slice 9999` exits 1 and names the plan files searched.
8. **Slash parity.** `/sq:stats slices` in Claude Code prints the same table as step 4.

## Risk Assessment

### Technical Risks

- **Attribution is heuristic.** Slices without prescribed commit subjects get no per-task actuals, and wall-clock spans include idle time. #214's numbers are useful mainly when pooled across many slices.
- **Observed producer data is confounded.** Different configs saw different slices.

### Mitigation Strategies

- Each report prints its window source, marker coverage, and the `span` label (D5). It reports distributions with n, not ratios (D2).
- The observational footer and the `below floor` rule (D8) apply. Controlled comparison is the replay follow-on's job (D1).

## Implementation Notes

### Development Approach

1. D3: the `StepState` fields, `_append_step`, and `run_usage_report` rounds, plus round-trip tests with old files. This lands first because it fixes 175's totals.
2. `planning_docs.py` with the real-file fixtures.
3. `git_history.py`: the log pass, versioned artifact reads, window resolution, and marker matching. Tests use a temporary repo built in the fixture.
4. `effort_report.py`, then the `slice` and `slices` CLI.
5. `producer_report.py`, then the `producers` CLI.
6. `runs_usage_report`, then the `runs` CLI.
7. README and CHANGELOG. Update the follow-on slice plan entry (D1). Comment on #214 and #210 with what landed. #214 closes. #210 stays open for the replay follow-on.

Effort: 3/5.

### Special Considerations

- **Release.** New `sq stats` subcommands in an existing group count as a patch under the versioning rule, unless the Project Manager rules otherwise.
- **Privacy.** The reports read commit subjects, dates, and counts. Commit bodies and diffs are never read.
