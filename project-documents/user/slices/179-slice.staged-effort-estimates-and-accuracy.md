---
docType: slice-design
slice: staged-effort-estimates-and-accuracy
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [176, 178]
interfaces: []
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---

# Slice Design: Staged Effort Estimates and Accuracy

## Overview

Effort is estimated once, as `Effort: N/5` in the slice plan entry, and never revisited. 176 compares that one number with what the slice actually took. This slice adds a design-stage estimate and revised estimates, keeps their history, and measures how well each stage predicts the outcome. Fixes [#221](https://github.com/ecorkran/squadron/issues/221).

- **Where estimates live.** The slice design's frontmatter carries one key, `effort` (an integer 1–5). The design author sets it. Any agent whose revision changes the slice's scope updates it. Nothing else stores an estimate (D1).
- **History from git.** The slice design is committed at every review round (941), so each committed change of `effort` is one estimate. Each change takes its stage from the latest review that precedes it. No history list is written into the document (D2, D3).
- **The re-estimate prompt.** Squadron's revise prompt (`feedback: review`) tells the revising agent to update `effort` when its revision changes scope (D4).
- **Accuracy.** `sq stats slice` shows the estimate history. `sq stats slices` can group by any stage's estimate, and it gains an accuracy table: the rank correlation between each stage's estimate and each actual measure, with n (D5, D6).

Routing work to models by estimated effort is out of scope.

## Value

- **Estimates that track what is known.** A plan estimate is made before the design exists. The design estimate and the revisions record what was learned, so a slice that grew is visible as a slice that grew, not as a miss.
- **Drift is visible.** `sq stats slice N` shows `plan 2 → design 3 → after slice review 4`, with the commit of each change.
- **Estimate quality becomes measurable.** The accuracy table shows whether design estimates predict cost, review rounds, and fix-ups better than plan estimates, and by how much. Every number carries n.
- **Groundwork for routing.** A later slice that routes by effort needs to know which estimate to trust. This slice only measures that.

## Technical Scope

**Included:**

1. **`effort` frontmatter key** on slice designs, defined once in `documents/schema.py` and read leniently (D1).
2. **Estimate history reader** `stats/estimate_history.py`. It takes the plan value from the plan entry and the design values from the committed versions of the design whose `effort` changed. Each version is labelled with a stage (D2, D3).
3. **One extra whole-history git call** in `stats/git_history.py`, which finds the commits that changed an `effort:` line under the slices directory (D3).
4. **Re-estimate instruction** appended to the `feedback: review` revise prompt when the step has a slice whose design exists (D4).
5. **`sq stats slice <index>`**: an `estimates` header line and a JSON `estimates` list (D5).
6. **`sq stats slices`**: `--stage plan|design|final` selects which estimate groups the levels table (default `plan`, so today's output is unchanged). Also an `artifact_spend` measure from 178, an estimate-accuracy table, and a drift line (D5, D6).
7. Help text in the `/sq:stats` slash command and the `sq-stats` skill, the README `sq stats` section, and a CHANGELOG bullet.

**Excluded:**

- **Routing by estimated effort** (#221).
- **Adding `effort` to the slice-design template and guide.** The template lives in ai-project-guide. A companion issue there adds the key to `templates/slice-design.md` and adds the estimate guidance to `guide.ai-project.004-slice-design`. Until it lands, pipeline designs carry no design-stage estimate and reports show `not estimated` (D1, Dependencies).
- **Back-filling estimates.** 14 of the 149 existing designs state `Effort: N/5` in prose. Several state more than one value (`Part A 1/5, Part B 2/5 … Overall 2/5`, `3/5 (up from the plan's 2/5)`), so parsing them would pick the wrong value. They are not read. A Project Manager can add `effort` to any design by hand, and the change then counts at the stage its commit falls in.
- **A task-stage estimate.** Per-task `Effort` (176 D4) uses a per-task scale. Its sum is not on the slice's 1–5 scale. A task-time scope change updates the design's `effort` like any other revision.
- **Editing plan entries.** The plan stage is the current plan entry value, the same figure 176 reports. Re-estimates go into the design, never into the plan entry. The ai-project-guide issue states that rule.
- **Uncommitted edits.** History is read from commits only, like 176's review rounds.
- **Prompt-only mode.** `prompt_renderer` does not render `feedback: review` prompts today, so it gains no re-estimate sentence. Interactive revisions follow the ai-project-guide guidance.

## Dependencies

### Prerequisites

- **176** (complete): `stats/planning_docs.py` (plan entries and `Effort: N/5`), `stats/git_history.py` (`GitHistory`, its single whole-history pass, `show`), `stats/review_rounds.py` (`ReviewRound` with `sha` and `authored_at`), `stats/effort_report.py` (`build_slice_report`, `REPORTED_REVIEW_TYPES`), `stats/effort_rollup.py` (`Measure`, `LevelRow`), and the `metrology.min_evidence_n` handling from 176 D8.
- **178** (designed, not implemented): `stats/artifacts_report.artifacts_usage_report(project_root, slice_filter)`, which gives each slice's design and task artifact spend without depending on run state. 179 reads it as the `artifact_spend` measure. Only that function and `ArtifactUsage` are used.
- **941** (complete): `commit_each_iteration: true` on review-revise loops, so every revision of the design, and every review round, is committed.
- **ai-project-guide companion issue** (to be filed in implementation step 1). It is not a build dependency. The reader, the prompt sentence and the reports all work without it. It is what makes P4 designers write the first `effort`.

### Interfaces Required

- `DispatchAction._resolve_feedback_prompt` (`pipeline/actions/dispatch.py:756`) builds every `feedback: review` prompt: P4, P5, P6 and the composite pipelines, `implement`, `sq review --max` (through `review_revise`), and the judge and findings-addressed cycles.
- `review/persistence.py`: `SLICES_DIR` and `resolve_slice_info`, to resolve the design path from the `slice` param.
- `documents/frontmatter.parse_frontmatter`, used for `git show` text, as `review_rounds` already does.
- `statistics.correlation(x, y, method="ranked")` (Python 3.12+, and the project requires `>=3.12`). It computes Spearman's rho with tied values averaged. It raises `StatisticsError` when there are fewer than two points or an input is constant.
- `get_typed_config("metrology.min_evidence_n", int)`, as in 176.

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| Key constant | `documents/schema.py` | `EFFORT_ESTIMATE_KEY = "effort"`, plus `EFFORT_SCALE = range(1, 6)` |
| Lenient value reader | `documents/schema.py` | `read_effort_estimate(value: object) -> int \| None` (D1) |
| Git query | `stats/git_history.py` | `GitHistory.commits_changing_effort() -> dict[str, tuple[str, ...]]` (sha → changed design paths), one lazy cached call |
| Estimate history | `stats/estimate_history.py` (new) | `EstimateStage`, `Estimate`, `EstimateHistory`, `estimate_history(...)` |
| Slice report | `stats/effort_report.py` | `SliceEffortReport.estimates`; reuses the review rounds `build_slice_report` already reads |
| Rollup | `stats/effort_rollup.py` | `stage` parameter, `Measure.ARTIFACT_SPEND`, `accuracy`, `drift` |
| Accuracy core | `stats/estimate_accuracy.py` (new) | `estimate_accuracy(...)`, `estimate_drift(...)` |
| Re-estimate prompt | `pipeline/actions/reestimate.py` (new) | `reestimate_instruction(slice_param, cf_client) -> str \| None` |
| Revise prompt | `pipeline/actions/dispatch.py` | `_resolve_feedback_prompt` appends the instruction when it is not `None` |
| CLI | `cli/commands/stats.py`, `cli/stats_views.py` | `--stage`, the estimates line, the accuracy table and the drift line |
| Wrappers | `commands/sq/stats.md`, `commands/agents/sq-stats/SKILL.md` | help text only |

`stats/git_history.py` remains the only module that runs git (176). The `stats/` cores contain no Typer code.

### Data Flow

```
writing side
  P4 designer (ai-project-guide template) ──► design frontmatter `effort`
  revise dispatch ◄── reestimate_instruction(slice) ◄── _resolve_feedback_prompt
        └──► updates `effort` only if scope changed ──► round commit (941)

reading side
  plan entry Effort ─────────────────────────────┐
  git log -G '^effort:' ─► changed design versions ─► git show ─► estimate_history ─┐
  review rounds (176, already read) ── stage labels ┘                               │
                                                     effort_report ◄────────────────┤
  artifacts_usage_report (178) ──► effort_rollup ◄──────────────────────────────────┘
                                        └─► estimate_accuracy ─► sq stats slices
```

### State Management

No new persisted state. The design's `effort` key is the only stored estimate, and git holds its history. As in 176, every report is computed at read time.

## Technical Decisions

### D1 — One key in the design: `effort`

The estimate is an integer on the plan's 1–5 scale, stored as `effort` in the slice design's frontmatter.

- **Why the design.** The design is the document whose scope the estimate describes, and it is committed at every review round of the design, tasks and code loops (941). A key in the slice plan would mean an agent editing a shared multi-slice document, and the plan stage would be lost.
- **Why one key, not a list.** Agents rewrite the files they revise and can drop keys (178 D2). One scalar is easy to keep, and git already holds every value it ever had. A list in frontmatter would be a second history that can disagree with git.
- **Name.** `effort` matches the plan entry's `Effort:` and the guide's "1–5 relative effort scale". It does not collide with model reasoning effort: that lives in profiles and in run-state usage records (175 D7), never in design frontmatter, and 178 stamps no effort key (178 Technical Scope). In code the concept is called `EffortEstimate` throughout, to keep the two apart.
- **Lenient read.** `read_effort_estimate` accepts an int, a numeric string, or `N/5` (the plan's spelling). A value outside 1–5, or any other value, reads as `None` and its caller logs a WARNING naming the file and the commit.
- **Schema.** Context Forge owns the frontmatter schema. `cf validate frontmatter` accepts an added key on a slice design (checked on an in-root probe file during this design). The ai-project-guide issue adds `effort` to the template so the key is documented, not merely tolerated.

### D2 — Stages come from review order

Each committed version of the design whose `effort` differs from the previous committed value is one estimate. Its stage comes from the latest review round for this slice that was committed strictly before it: earlier author date, and not in the same commit.

| Latest earlier review type | Stage |
|---|---|
| none | `design` |
| `slice` | `after-slice-review` |
| `tasks` | `after-tasks-review` |
| `code` | `after-code-review` |

The plan entry's current value is stage `plan`. It has no commit.

**Why strictly before.** A phase step commits the dispatch and its first review together (dispatch → review → checkpoint → commit, 178 Interfaces). The first draft therefore shares a commit with review round 1, and it must read as `design`. Revise round *k* is committed with review round *k+1*, and the latest review strictly before it is round *k*, the one it answered.

**Derived estimates.** Three figures are used by the reports:

- **plan**: the plan entry value.
- **design**: the last `design`-stage value, which is what the design said when it first went to review.
- **final**: the latest value at any stage. When there was no revision, final equals design.

A slice whose first `effort` comes after a review has no `design` estimate (for example, a key added by hand to an old design). Its first value carries the stage of the review before it.

Review types other than the three slice types (`arch`, judge templates) do not label stages. The mapping is one `dict[str, EstimateStage]` keyed by the `REPORTED_REVIEW_TYPES` constants in `effort_report`.

### D3 — Reading the history within 176's git bound

176 D6 limits a report to two whole-history calls plus one `git show` per review version. This slice adds:

- **One call:** `git log --all -G '^effort:' --format=%H --name-only -- project-documents/user/slices/`. It lists the commits whose diff adds or removes a line starting with `effort:` under the slices directory, and the files each one touched. It runs lazily, once per invocation, and is cached on `GitHistory`.
- **One `git show` per candidate:** a pair of commit and path, where the path is the slice's design (`{index}-slice.*.md`, which survives renames because 176's pass uses `--no-renames` and each path is matched by pattern). The text is parsed with `parse_frontmatter`, and only the frontmatter `effort` counts. A body line that starts with `effort:` (for example in a YAML example) makes its commit a candidate, but it is never read as an estimate.

The total becomes 3 + V + E, where E is the number of candidate design versions read. 176's call-count test is updated to that figure. A slice with no `effort` history costs no `show` calls. Until estimates are routine, E is small next to V.

Consecutive versions with the same value are collapsed, so a commit that only reformatted the line adds nothing. If the latest committed version has no `effort` while an earlier one did, the history keeps the earlier values and sets `key_removed`. The report notes it (D7), so a dropped key is not read as "never estimated".

### D4 — The re-estimate instruction

`reestimate_instruction(slice_param, cf_client)` returns one paragraph when the step's `slice` param resolves, through `resolve_slice_info`, to a design file that exists:

> If addressing these findings changes the slice's scope, set `effort` in the frontmatter of `{design_path}` to your revised estimate on the 1–5 scale. If the scope is unchanged, leave `effort` as it is. Do not add `effort` if the file has none.

`_resolve_feedback_prompt` appends it after the "revise in place" line. The design path is given explicitly because a tasks or code revision does not otherwise have the design open.

- The last sentence prevents a revise round from adding a first estimate, which would be mislabelled as a revision. A first estimate comes from the design author or a person.
- There is no example value near the slot (CLAUDE.md hallucination traps). The range is a constraint, not an example.
- The judge and findings-addressed cycles also use `feedback: review`. When their params carry a slice, they get the sentence too. It changes only frontmatter, and every configuration that is compared receives it, so it does not bias a comparison.

**Failure modes.** A missing `slice` param (plan-scoped steps) returns `None` and logs nothing, because that is not a failure. A `slice` param whose design cannot be resolved returns `None` and logs a WARNING naming the slice and the reason. The revise prompt is otherwise unchanged, and the dispatch proceeds.

### D5 — Report changes

**`sq stats slice N`** gets one header line under `planned effort`:

```
estimates: plan 2 · design 3 · after slice review 4 (a1b2c3d)   drift +2
```

Each revision lists its short sha. `drift` is final minus plan. When the design has no estimate, the line reads `estimates: plan 2 · design not estimated`. JSON gains `estimates: [{stage, effort, sha, authored_at}]`, `key_removed`, and `estimates_skipped`.

**`sq stats slices --stage plan|design|final`** groups the levels table by the chosen stage's estimate. Slices without that estimate go in a final `unestimated` row, the same way `unplanned` works today. The default is `plan`, and in that case the table, apart from the new measure column, is byte-identical to today's (a test asserts this). `Measure.ARTIFACT_SPEND` is the sum of the slice's design and tasks artifact spend from 178, priced rounds only. The JSON key is `artifact_spend`.

### D6 — Accuracy is rank correlation, with n

Effort is ordinal (176 D2), so accuracy is not a ratio and not an error in units. The question is whether a higher estimate goes with more actual work. For each stage and each `Measure`, the report gives Spearman's rho between the estimate and the measure across completed slices, computed with `statistics.correlation(..., method="ranked")`, plus n. A slice missing either value is left out of that cell.

Rows:

| Row | Slices |
|---|---|
| `plan (all)` | every completed slice that has a plan estimate |
| `plan` | completed slices that have both a plan and a design estimate |
| `design` | the same set |
| `final` | the same set |

The last three rows use one shared set, so plan, design and final are compared on the same slices. `plan (all)` shows the larger history that only has plan estimates.

**Floors.** A cell with n below `metrology.min_evidence_n` reads `below floor`. A cell where `correlation` raises `StatisticsError` (an input with no spread, or fewer than two points) reads `—`, and the JSON gives the reason `no spread`. A footer says that later stages see more of the work, so a better `final` correlation is partly hindsight, and that rho measures ordering, not calibration.

**Drift line:** `drift: k of n slices changed estimate after plan · median |final − plan| m`, over the shared set.

### D7 — Failure modes

| Failure | Behavior | Signal |
|---|---|---|
| `git log -G` returns `None` or non-zero (timeout, cannot run) | report not produced | `run_git` WARNING, then an error naming the command; exit 1 (176 D9 rule for whole-history calls) |
| `git show` fails for a candidate version | version skipped | WARNING naming sha and path; `estimates_skipped` count and footer |
| Candidate version's frontmatter does not parse | version skipped | WARNING naming sha and path; same count |
| `effort` value invalid or outside 1–5 | version skipped | WARNING naming sha, path and value; same count |
| Latest committed design has no `effort` but an earlier one did | earlier history kept | row note `effort key removed` |
| Slice has no design in history | plan stage only | `design not estimated` |
| `--stage design` or `final` and no completed slice has that estimate | empty levels table | message `no completed slices with a design estimate`, exit 0 |
| Accuracy cell below floor, no spread, or n < 2 | cell not ranked | `below floor` or `—`, with the reason in JSON |
| `metrology.min_evidence_n` not an integer | `slices` not produced | error naming key and value, exit 1 (176 D9) |
| 178's artifacts report finds an unreadable stamp | that file's spend is missing | 178's WARNING and footer, passed through |
| Revise step: `slice` set, design not resolvable | no re-estimate sentence | WARNING naming slice and reason |

## Implementation Details

### API Contracts

```python
# documents/schema.py
EFFORT_ESTIMATE_KEY = "effort"
EFFORT_SCALE = range(1, 6)
def read_effort_estimate(value: object) -> int | None: ...   # int, "3", "3/5"; else None

# stats/estimate_history.py
class EstimateStage(StrEnum):
    PLAN = "plan"
    DESIGN = "design"
    AFTER_SLICE_REVIEW = "after-slice-review"
    AFTER_TASKS_REVIEW = "after-tasks-review"
    AFTER_CODE_REVIEW = "after-code-review"

@dataclass(frozen=True)
class Estimate:
    stage: EstimateStage
    effort: int
    sha: str | None            # None for PLAN
    authored_at: datetime | None

@dataclass(frozen=True)
class EstimateHistory:
    estimates: tuple[Estimate, ...]   # PLAN first (when planned), then commit order
    key_removed: bool
    skipped: int
    @property
    def plan(self) -> int | None: ...
    @property
    def design(self) -> int | None: ...
    @property
    def final(self) -> int | None: ...

def estimate_history(
    history: GitHistory, index: int, plan_effort: int | None,
    rounds: Mapping[str, Sequence[ReviewRound]],   # by review type, as build_slice_report reads them
) -> EstimateHistory: ...

# stats/estimate_accuracy.py
class AccuracyRow(StrEnum):
    PLAN_ALL = "plan (all)"; PLAN = "plan"; DESIGN = "design"; FINAL = "final"

@dataclass(frozen=True)
class AccuracyCell:
    n: int
    rho: float | None
    reason: str | None         # "below floor" | "no spread"; None when rho is set

# pipeline/actions/reestimate.py
def reestimate_instruction(slice_param: object, cf_client: CfClientProtocol) -> str | None: ...
```

`slices_effort_report` gains `stage: EstimateStage` (only `PLAN`, `DESIGN`, `FINAL` are accepted; the CLI exposes those three) and `min_n: int`. `SlicesEffortReport` gains `stage`, `accuracy: dict[str, dict[str, AccuracyCell]]` (row → measure → cell), `drift`, and `estimates_skipped`.

### UI Specifications

`sq stats slices` (illustrative values):

```
Effort (plan)  n   Span ...  Artifact spend
2/5            31  ...       $1.80 (0.4–6.1)
...

Estimate accuracy (Spearman rho, n)   min n 5
Stage        Span        Impl commits  Fix-ups     Design rounds  Tasks rounds  Spend       Artifact spend
plan (all)   0.41 (112)  0.38 (112)    0.12 (97)   0.09 (120)     0.15 (118)    0.33 (40)   below floor (3)
plan         below floor (4) ...
design       below floor (4) ...
final        below floor (4) ...
drift: 2 of 4 slices changed estimate after plan · median |final − plan| 1
Later stages see more of the work; rho measures ordering, not calibration.
```

Width handling reuses `cli/columns.py` (`fit_widths`).

## Integration Points

### Provides to Other Slices

- **A future effort-routing slice:** `EstimateHistory` (plan, design, final per slice) and the per-stage accuracy, which tell it which estimate to route on.
- **ai-project-guide:** the key name and semantics for the template and guide change.

### Consumes from Other Slices

- **176:** the report cores, git history, review rounds and the evidence floor. Review rounds are reused, not read again.
- **178:** `artifacts_usage_report`. If 178 has not landed when this slice is implemented, `Measure.ARTIFACT_SPEND` and its column wait for it. Nothing else in this slice depends on 178.
- **941:** committed rounds. Before 941, revisions may not have been committed, so their estimates are missing. In practice this changes nothing, because no design carried `effort` before this slice.

## Success Criteria

### Functional Requirements

1. A design with `effort: 3` committed before its first review, and `effort: 4` committed with review round 2, reports `plan N · design 3 · after slice review 4 (<sha>)` in `sq stats slice`.
2. The first draft, committed together with review round 1, is labelled `design`, not `after-slice-review`.
3. `effort` values `3`, `"3"` and `"3/5"` all read as 3. `"high"`, `0` and `6` are skipped with a WARNING and counted.
4. A body line `effort: 2` inside a code block is never read as an estimate.
5. A latest version without `effort` keeps the earlier history and shows `effort key removed`.
6. A `feedback: review` revise prompt for a step with a resolvable slice contains the re-estimate paragraph with the design's path. A plan-scoped revise prompt does not, and logs nothing. An unresolvable slice logs the WARNING.
7. `sq stats slices` with no `--stage` prints the same levels table as before plus the `Artifact spend` column, the accuracy table, and the drift line. `--stage design` groups by design estimate, with an `unestimated` row.
8. Accuracy cells show rho with n, `below floor` under `metrology.min_evidence_n`, and `—` with the reason `no spread` for constant inputs.
9. `--json` on `slice` and `slices` carries the same values as the tables.

### Technical Requirements

- Every D7 row has a test that asserts its signal.
- The git call-count test asserts 3 + V + E.
- Stages, accuracy rows and measures are enums. The review-type → stage mapping is one dict. There are no bare string comparisons.
- The key name exists only as `EFFORT_ESTIMATE_KEY`. The prompt text and the reader both use it.
- Stage-labelling tests build a temporary repo with the real commit shape: draft and review round 1 in one commit, then revise *k* with review *k+1*.
- `ruff format`, `ruff check`, `pyright` with zero errors, and the full suite green.

### Integration Requirements

- 176's `sq stats slice` output for a slice without `effort` history is unchanged except for the `estimates: plan N · design not estimated` line.
- `sq review --max` and P4/P5/P6 revise rounds all include the sentence through the same function.

### Verification Walkthrough

These commands come from the design. `--stage`, the estimates line and the accuracy table do not exist yet. Use `.venv/bin/sq` in this repo, or the scratch project `~/source/repos/manta/temp/scratch-945`.

1. **Hand-added estimate.** In the scratch project, add `effort: 3` to a slice design that has no review yet, and commit it. `sq stats slice <index>` shows `estimates: plan <N> · design 3`.
2. **Revision after review.** Run `sq review slice <index> --model <alias>` and commit the review. Then change the design to `effort: 4` and commit. `sq stats slice <index>` shows `· after slice review 4 (<sha>)` and `drift` equal to 4 minus the plan value. `sq stats slice <index> --json | python -m json.tool` lists three `estimates` entries.
3. **Pipeline loop.** Run `sq run P4 <index> -p max-revisions=2` on a slice whose first review returns CONCERNS. The revise round's prompt contains the re-estimate paragraph naming the design path (the dispatch prompt test asserts the text). If the revising agent changed `effort`, `git log -p -- <design>` shows it in a round commit, and `sq stats slice` labels it `after-slice-review`.
4. **Rollup in this repo.** `sq stats slices` prints today's table, plus the `Artifact spend` column, then the accuracy table. `plan (all)` has values over the completed slices. `plan`, `design` and `final` read `below floor`, because no completed design carries `effort` yet. `sq stats slices --stage design` prints only `unestimated`.
5. **Bad value.** In the scratch project, set `effort: high` and commit. `sq stats slice <index>` logs a WARNING naming the sha, the path and `high`, and the footer counts one skipped estimate.
6. **Removed key.** Delete the `effort` line and commit. The history stays, and the row note reads `effort key removed`.

## Risk Assessment

### Technical Risks

- **Revising agents may change `effort` when the scope did not change**, which adds noise to the revised stages.

### Mitigation Strategies

- The instruction is conditional, and it forbids adding a first estimate (D4). Every change is a visible commit with a sha in `sq stats slice`. The accuracy table keeps `design` separate from `final`, so noisy revisions do not corrupt the design-stage measure.

## Implementation Notes

### Development Approach

1. File the ai-project-guide issue: add `effort` to `templates/slice-design.md` frontmatter, add the estimate and re-estimate guidance to `guide.ai-project.004-slice-design`, and state that re-estimates go in the design, never the plan entry. Link it from #221.
2. `documents/schema.py` key, scale and lenient reader, with unit tests.
3. `GitHistory.commits_changing_effort` and `stats/estimate_history.py`. Stage-labelling tests on a temporary repo with the real commit shape. Then update the call-count test.
4. `SliceEffortReport.estimates` and the `slice` renderer and JSON.
5. `Measure.ARTIFACT_SPEND` (after 178), `--stage`, `stats/estimate_accuracy.py`, and the accuracy and drift rendering.
6. `pipeline/actions/reestimate.py` and the `_resolve_feedback_prompt` hook, with prompt-text tests for slice, plan-scoped and unresolvable steps.
7. Wrapper help text, README `sq stats`, CHANGELOG. Comment on #221 with what landed.

Effort: 3/5.

### Special Considerations

- **Release.** A new option and new report sections in an existing command group are a patch under the versioning rule.
- **Reports stay read-only.** The only write this slice adds is the agent's own edit to `effort`, made at its own instruction. No squadron code writes the key.
