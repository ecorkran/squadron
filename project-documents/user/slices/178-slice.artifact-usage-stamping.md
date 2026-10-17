---
docType: slice-design
slice: artifact-usage-stamping
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [175, 176]
interfaces: [179]
dateCreated: 20261016
dateUpdated: 20261016
status: not_started
---

# Slice Design: Artifact Usage Stamping

## Overview

Slice 175 records a `UsageRecord` for every LLM action, but only review artifacts carry it in their frontmatter. For the artifacts a pipeline produces (slice designs, task breakdowns, architecture documents) the record lives only in run state, and `sq runs prune` deletes it. This slice stamps the cumulative usage of every dispatch that wrote such an artifact into the artifact's own frontmatter, under the review key names, and adds `sq stats artifacts` plus an artifact-spend line on `sq stats slice` to read it back. Fixes [#222](https://github.com/ecorkran/squadron/issues/222).

**Scope finding.** The plan entry names dispatch, summary and compact. Only dispatch writes an artifact with frontmatter. Compact writes no file (`pipeline/actions/compact.py`). Summary's `file` emit writes the summary text verbatim with no frontmatter block (`pipeline/emit.py:_emit_file`). Summary and compact keep their run-state records and are not stamped (Technical Scope). The slice plan entry (`140-slices.pipeline-foundation.md`, entry 34) is amended to the same scope.

## Value

- **Cost by stage survives pruning.** A slice's design and task files say what producing them cost, for as long as the files exist, across runs and resumes.
- **Input for 179.** Staged effort estimates (#221) and estimate accuracy (#214) need per-artifact cost by stage. 179 reads it from the files instead of from whatever run state remains.
- **One format.** The keys match review artifacts, so one reader serves both.

## Technical Scope

**Included:**

1. **`squadron.usage-stamp`**, a built-in POST_ACTION event action registered after `squadron.revision-stamp`. After a successful phase dispatch, it folds the action's `UsageRecord` into the artifact's frontmatter (D1, D2).
2. **Initiative-scoped artifacts.** The architecture document written by a plan-scoped design step (P2) is stamped too. Path resolution for slice-scoped and initiative-scoped artifacts moves into `events/builtin/artifact_paths.py`, so the post-condition and the stamp resolve paths the same way (D3).
3. **Cumulative usage** over every stamped dispatch, with round and priced-round counts (D2).
4. **One key table.** `RunCost` exposes its frontmatter keys as a field mapping. Review persistence and the stamp both use it (D4).
5. **One reader.** The mapping from frontmatter keys back to `UsageRecord` moves out of `stats/reviews_report.py` into `review/frontmatter_usage.py`, beside `RunCost`. The stamp and both reports use it (D4).
6. **`sq stats artifacts [--slice INDEX]`**, and an `artifact spend` line in `sq stats slice` (D5).
7. Updated subcommand lists in the `/sq:stats` slash command and the `sq-stats` skill, whose "All take `--json`" line now excludes `artifacts`.

**Excluded:**

- **Summary and compact.** They write no frontmatter artifact (Overview).
- **Implement-phase dispatch.** It writes code, not a document. `ArtifactKind` has no implement member, and the run record stays the source.
- **Failed dispatches.** No artifact was confirmed, so there is nothing to stamp. Run state still keeps their spend (175 D5).
- **Model, profile and effort keys.** A cumulative total can span rounds run on different models. Per-round attribution stays in run state, which `sq stats producers` reads (176 D8).
- **Back-filling existing artifacts** from surviving run state. Artifacts written before this slice show no stamp.
- **Pipeline review artifacts after pruning.** `sq stats reviews` excludes review artifacts that carry a `runId` because the run counts them, so their spend drops out of every view once the run is pruned. That is a separate gap in the 175 reviews report. It should get its own issue.
- **Cost basis on stamps** ([#231](https://github.com/ecorkran/squadron/issues/231)). A cumulative total can mix provider-reported and alias-priced rounds. Recording that needs a new `CostBasis` member or key removal, so `costBasis` is not stamped. Per-round basis stays in run state.
- **`--json` on `sq stats artifacts`.** No consumer: 179 calls `artifacts_usage_report` directly.
- **Extending `revision_number` to architecture documents.** `squadron.revision-stamp` behaves as before.

## Dependencies

### Prerequisites

- **175** (complete): `UsageRecord` in `ActionResult.metadata[USAGE_KEY]` (`pipeline/usage_capture.py:stamp`), `RunCost` (`review/run_cost.py`), `stats/reviews_report.py`, `stats/usage_report.py:usage_totals`, `cli/commands/stats.py`, and the `/sq:stats` wrappers.
- **176** (complete): every loop round persisted in run state (D3), and `sq stats slice` (`stats/effort_report.py`, `stats/slice_spend.py`).
- **171/173** (complete): the POST_ACTION event mechanism, `PostActionContext`, and built-in binding order in `events/manifest.py:DEFAULT_BINDINGS`.

### Interfaces Required

- `PostActionContext` (`events/contexts.py:40`): `action_type`, `result` (whose `metadata` carries the usage record), `expected_artifact_kind`, `params` (`slice` or `plan`), `run_started_at`, `cf_client`, `cwd`.
- `events/dispatcher.py:fire`: a failed POST_ACTION outcome stops later bindings. Because `usage-stamp` runs after `dispatch-artifact`, it runs only when the post-condition has passed.
- `documents/frontmatter.py`: `read_frontmatter` and `update_frontmatter`. The latter preserves key order, appends new keys, and keeps the body byte-for-byte.
- `review/persistence.py`: `SLICES_DIR`, `TASKS_DIR`, `resolve_slice_info`, `resolve_arch_file`. Also `integrations/context_forge.ARCHITECTURE_DIR`.
- The phase step expands to dispatch → review → checkpoint → commit (`pipeline/steps/phase.py:expand`). The stamp is therefore written before the step's commit, and with 941's `commit_each_iteration` each revision round's stamp is committed with that round.

## Architecture

### Component Structure

| Component | Location | Change |
|---|---|---|
| Artifact usage model | `pipeline/artifact_usage.py` (new) | `ArtifactUsage`, `fold`, `read_artifact_usage`, `artifact_usage_fields`, key constants |
| Stamp action | `events/builtin/usage_stamp.py` (new) | `UsageStampAction` (`squadron.usage-stamp`), POST_ACTION |
| Binding | `events/manifest.py` | append to `DEFAULT_BINDINGS` after `revision-stamp` |
| Path resolution | `events/builtin/artifact_paths.py` | add `dispatch_artifact_paths(kind, slice_param, plan_param, cf_client, cwd)`. `dispatch-artifact` calls it, and its error messages and the `dispatch post-condition` log prefix stay unchanged |
| Key table | `review/run_cost.py` | `RunCost.frontmatter_fields() -> dict[str, object]`, with `frontmatter_lines()` rendered from it; `RunCost.from_record(UsageRecord)` |
| Frontmatter reader | `review/frontmatter_usage.py` (new) | `record_from_frontmatter(path, front)`, moved from `reviews_report._record` and its field helpers |
| Artifacts report | `stats/artifacts_report.py` (new) | `artifacts_usage_report(project_root, slice_filter)` |
| Slice report | `stats/effort_report.py`, `cli/stats_views.py` | artifact spend per kind on the `slice` header |
| CLI | `cli/commands/stats.py`, `cli/stats_views.py` | `artifacts` subcommand and renderer |
| Wrappers | `commands/sq/stats.md`, `commands/agents/sq-stats/SKILL.md` | subcommand list text only |

### Data Flow

```
dispatch action ──► ActionResult.metadata["usage"] ──► run state (unchanged, 175/176)
        │
        └─ POST_ACTION: dispatch-artifact (pass) → dispatch-branch-work → revision-stamp → usage-stamp
                                                                                            │
           artifact frontmatter (prior ArtifactUsage) ─► fold(prior, record) ─► update_frontmatter
                                                                                            │
   slices/*.md, tasks/*.md, architecture/*-arch.*.md ─► artifacts_report ─► sq stats artifacts
                                                                      └──► sq stats slice (artifact spend line)
```

### State Management

The artifact's frontmatter is the only new persisted state, and it is the source of its own running total. Each stamp reads the prior total from the file, adds one record, and writes the result back. Run state is not changed. No total is stored anywhere else.

## Technical Decisions

### D1 — Eligibility

`usage-stamp` acts when all of these hold, and otherwise returns success with no effect:

- `action_type` is dispatch, `result.success` is true, and `expected_artifact_kind` is not `None`.
- `result.metadata` holds a usage record. When it does not, the stamp is skipped and a DEBUG line names the step.

The stamp does not read `result.outputs`, which keeps it inside the 140-arch event-action rule. It needs no skip check: a kept artifact (`existing: keep`) returns before any model call with empty `metadata` (`pipeline/actions/dispatch.py:_dispatch`), so it has no usage record. Prompt-only mode records no usage either. In both cases no spend was measured, so not stamping is correct by construction, not by coincidence.

**Which file.** The stamp runs only after the post-condition confirmed that a candidate was written this run. It stamps the first candidate from `dispatch_artifact_paths`, in numeric-suffix order, with a file without a suffix first. A design or arch doc has one candidate. A split task breakdown (`nnn-tasks.name-1.md`, `-2.md`; 13 of the repo's task breakdowns) is one artifact, as 177 treats it, and its first part carries the total for every round, whichever part a round rewrote. The record is never split or duplicated, so no task spend goes unattributed.

**Never fails a run.** This follows 911 D4, the same as `revision-stamp`. Any resolution, parse or write failure (`FrontmatterError`, `OSError`, a cf client error) is logged at WARNING with the path and the reason, and the action returns success. A cost stamp must not fail a converging loop.

### D2 — Loop rounds: one cumulative total per artifact

A file revised in a loop gets one cumulative total, not one entry per round. Per-round detail already lives in run state (176 D3) and in git history, because each round's stamped file is committed. Frontmatter carries the durable total that survives pruning. A per-round list would grow without bound in a human-edited document, and the review keys are flat.

`ArtifactUsage` holds a `RunCost` plus two counts:

| Key | Meaning |
|---|---|
| `turns`, `promptTokens`, `cachedTokens`, `cacheWriteTokens`, `completionTokens`, `reasoningTokens`, `durationSeconds`, `costUsd` | the review keys (931 D10, 175), summed over stamped rounds. `costBasis` is not stamped (#231) |
| `usageRounds` | dispatches folded into the total |
| `pricedRounds` | of those, how many had a cost |

`fold(prior, record)` follows 175 D9:

- Tokens and turns use `add_optional`. A field that no round reported is left out.
- Cost sums priced rounds only, and `pricedRounds` counts them. An unpriced round is never counted as $0, so a reader renders `$x (k of m rounds priced)`.
- Duration sums the LLM call times.

The stamp counts dispatches that wrote this file, from any run. The initial draft (iteration 0), each loop revision, and a later run that rewrites the file all add to the same total.

**Agent rewrites.** A revision agent may rewrite the file and drop the keys. The total then restarts at that round, along with `usageRounds`, so the stamp stays internally consistent and is a floor. The committed earlier rounds in git keep the prior totals.

**Malformed prior keys.** A non-numeric value is treated like the 175 reviews reader does (D4): that field reads as `None` and a WARNING names the key. When `usageRounds` itself is not a positive int, the total restarts and the WARNING says so.

### D3 — Path resolution in one place

`dispatch_artifact_paths` contains the slice-or-plan branching that is now inline in `dispatch_artifact._dispatch_artifact_post_condition_error`. A slice index goes to `expected_artifact_paths`, and a plan index with no slice goes to `[resolve_arch_file(index, cwd)]`. The post-condition keeps its own error messages, mtime check and log prefix, which existing tests assert. The stamp and the post-condition therefore see the same candidate list.

### D4 — One key table, one reader

- `RunCost.frontmatter_fields()` returns the D10 key→value mapping (keys present only when they have a value, `costUsd` rounded to 6 places, `durationSeconds` as a float to 1 place). `frontmatter_lines()` renders from it, so review artifacts stay byte-identical. The existing review persistence tests assert that.
- `RunCost.from_record(UsageRecord)` maps a record onto the same fields.
- `review/frontmatter_usage.record_from_frontmatter` moves verbatim from `reviews_report._record` together with `_INT_KEYS` and the `_int`/`_float`/`_basis` helpers. `reviews_report` imports it, and its behavior does not change. `pipeline/artifact_usage.read_artifact_usage` uses it plus the two counts. Each key name is defined once. `stats` and `pipeline` both import from `review/`, and neither imports the other for this.

### D5 — `sq stats` reads artifacts beside runs, never summed with them

- `sq stats artifacts [--slice INDEX]` reads the top-level `*.md` files in `SLICES_DIR` and `TASKS_DIR`, and `*-arch.*.md` in `ARCHITECTURE_DIR`, frontmatter only. It shows one row per file that has `usageRounds`: kind, file, slice, rounds, tokens, duration, cost (`k of m rounds priced`). It ends with a total. **Kind** is an `ArtifactKind`, taken from the directory the file was found in, not from its name or `docType`: `TASKS_DIR` gives `TASKS`; `SLICES_DIR` and `ARCHITECTURE_DIR` give `DESIGN`, which is the kind the P2 design step already assigns to the arch doc. **Slice** is the file name's leading index, using the reviews report's rule. Files without `usageRounds` are not stamped (most predate this slice) and are skipped silently. Unreadable frontmatter or a malformed `usageRounds` counts toward a `N file(s) unreadable` footer and logs a WARNING.
- `sq stats slice <index>` gains one header line, `artifact spend: design $x (k of m rounds) · tasks $y (…)`, read through `artifacts_usage_report(..., slice_filter=index)`. It sits beside `recorded spend` and is never added to it, because both describe the same dispatches whenever the run still exists.

### D6 — Failure modes

| Failure | Behavior | Signal |
|---|---|---|
| Path resolution fails (cf error, no arch doc, non-numeric slice/plan) | no stamp; dispatch result unchanged | WARNING naming kind, scope, reason |
| No path written this run | no stamp | none. The post-condition already failed the step, and later bindings did not run |
| Artifact has no frontmatter block / invalid YAML | no stamp | WARNING naming path and `FrontmatterError` |
| Write fails (`OSError`) | no stamp | WARNING naming path |
| Malformed prior key | that field restarts | WARNING naming path and key |
| No usage record on the result | no stamp | DEBUG naming step |
| `sq stats artifacts`: a stamped file is unreadable | row skipped | WARNING plus footer count |
| `sq stats artifacts`: no stamped files | empty table | message `no stamped artifacts`, exit 0 |

## Implementation Details

### API Contracts

```python
# pipeline/artifact_usage.py
USAGE_ROUNDS_KEY = "usageRounds"
PRICED_ROUNDS_KEY = "pricedRounds"

@dataclass(frozen=True)
class ArtifactUsage:
    cost: RunCost
    rounds: int
    priced_rounds: int

def fold(prior: ArtifactUsage | None, record: UsageRecord) -> ArtifactUsage: ...
def read_artifact_usage(path: Path, front: Mapping[str, object]) -> ArtifactUsage | None: ...
def artifact_usage_fields(usage: ArtifactUsage) -> dict[str, object]: ...

# events/builtin/artifact_paths.py
def dispatch_artifact_paths(
    kind: ArtifactKind, slice_param: object, plan_param: object,
    cf_client: CfClientProtocol, cwd: str,
) -> list[str]: ...          # raises as the resolvers do; callers decide how to report

# stats/artifacts_report.py
@dataclass(frozen=True)
class ArtifactUsageRow:
    path: Path
    kind: ArtifactKind          # from the directory (D5)
    slice: str | None
    usage: ArtifactUsage

def artifacts_usage_report(project_root: Path, slice_filter: str | None) -> ArtifactsUsageReport: ...
```

**Example stamp** on a slice design after a draft and one revision (keys appended after the existing frontmatter; values illustrative):

```yaml
revision_number: 1
turns: 41
promptTokens: 1893312
cachedTokens: 1702240
cacheWriteTokens: 151020
completionTokens: 30544
durationSeconds: 512.4
costUsd: 2.418731
usageRounds: 2
pricedRounds: 2
```

### UI Specifications

`sq stats artifacts --slice 178` (illustrative):

```
Kind    File                                   Slice  Rounds  Tokens (prompt / cached / completion)  Duration  Cost
design  178-slice.artifact-usage-stamping.md   178    2       1.89M / 1.70M / 30.5K                   512.4 s   $2.42 (2 of 2 priced)
tasks   178-tasks.artifact-usage-stamping.md   178    1       0.94M / 0.81M / 18.2K                   301.0 s   $1.10 (1 of 1 priced)
Total                                                 3                                                813.4 s   $3.52 (3 of 3 priced)
```

`sq stats slice 178` header addition:

```
recorded spend $3.97 (5 of 5 priced)
artifact spend: design $2.42 (2 of 2 rounds) · tasks $1.10 (1 of 1 rounds)
```

Width handling reuses `cli/columns.py` (`fit_widths`).

## Integration Points

### Provides to Other Slices

- **179 (Staged Effort Estimates and Accuracy):** `artifacts_usage_report` and `ArtifactUsage`, giving per-artifact cost and round count by stage for any slice whose artifacts exist, independent of run retention.
- **Any reader of frontmatter cost:** `record_from_frontmatter` and `RunCost.frontmatter_fields` as the single key definition.

### Consumes from Other Slices

- **175** usage records. When a dispatch has no record, no stamp is written, and nothing is fabricated.
- **176** `sq stats slice` and per-round run state, which stays the per-round source of truth.
- **941** `commit_each_iteration`. Without it, intermediate stamps are still written to the file but not committed per round; the cumulative total is unaffected.

## Success Criteria

### Functional Requirements

- A P4 run that drafts a slice design leaves the review keys, `usageRounds: 1` and `pricedRounds` in the design's frontmatter, and they match that dispatch's `UsageRecord` in run state.
- A design revised in a loop has a total equal to the sum of its rounds' dispatch records in run state (176 D3 rounds), and `usageRounds` equals the number of dispatch rounds.
- A P5 run stamps the task file the same way. A P2 run stamps the architecture document.
- A step with `existing: keep`, a failed dispatch, an implement dispatch, summary and compact stamp nothing.
- A split task breakdown is stamped once, on its first part, for every round.
- An unpriced round increments `usageRounds` and not `pricedRounds`, and leaves `costUsd` unchanged.
- After `sq runs prune` removes the run, `sq stats artifacts --slice N` still reports the slice's design and task spend.
- `sq stats slice N` shows the artifact spend line next to recorded spend and does not sum the two.

### Technical Requirements

- The stamp never changes the dispatch's `success`. Every D6 failure has a test that asserts its log signal.
- Review artifacts render byte-identically after the `RunCost.frontmatter_fields` refactor, and `sq stats reviews` output is unchanged after the reader moves.
- The `dispatch-artifact` tests pass unchanged after path resolution moves into `artifact_paths`.
- The stamp adds one frontmatter read and one write per eligible dispatch, and no state saves (a test asserts there are no `StateManager` writes).
- `ruff format`, `ruff check`, and `pyright` with zero errors.

### Integration Requirements

- 179 can compute per-stage cost from `artifacts_usage_report` with no run state present.
- A project's `events.yaml` can disable `squadron.usage-stamp` through `disable:`, the same as other built-ins.

### Verification Walkthrough

These commands come from the design; `sq stats artifacts` does not exist yet.

1. Run a design phase on a scratch slice: `sq run P4 <slice>`. When it finishes, run `head -30 project-documents/user/slices/<slice>-slice.<name>.md`. The frontmatter ends with the usage keys, `usageRounds: 1` (or the round count if the loop revised), and `pricedRounds`.
2. Compare with run state: `sq stats run <run_id>`. The sum of the dispatch rows for the design step and its loop equals the stamped `costUsd` and tokens.
3. Check per-round commits: `git log -p --follow project-documents/user/slices/<slice>-slice.<name>.md | grep -E 'usageRounds|costUsd'`. Each committed round shows a growing total.
4. Run `sq run P5 <slice>`, then `sq stats artifacts --slice <slice>`. You get a design row, a tasks row and a total.
5. Prune the runs (`sq runs prune --pipeline P4 --yes`, and the same for P5), then repeat step 4. The output is unchanged. `sq stats run <run_id>` now reports the run missing.
6. `sq stats slice <slice>` shows `artifact spend: design … · tasks …` under `recorded spend`.
7. Negative check: set `existing: keep` on the design step and rerun P4. The design's `usageRounds` does not change.

## Risk Assessment

### Technical Risks

- **Agent-edited frontmatter.** The producing agent rewrites the file it is revising and can drop or alter the stamped keys between rounds.
- **Attribution rests on the post-condition's mtime rule.** The stamp trusts that a candidate was written this run (mtime ≥ `run_started_at`). On a resumed run, or when someone edits the file by hand during a run, a dispatch that wrote nothing still passes the post-condition, and its spend is stamped onto the slice's existing artifact. The spend still belongs to producing that artifact, so the slice total stays right; only the attribution to that specific file is unverified. This is the post-condition's existing limit, and this slice does not change it.
- **Every phase dispatch touches its artifact a second time** (risk Med in the plan). A stamp bug could corrupt a design document.

### Mitigation Strategies

- A dropped key restarts the total and its round count together, so the stamp stays a consistent floor. Committed rounds in git keep each prior total.
- All writes go through `update_frontmatter`, the same body-preserving primitive `revision-stamp` already runs on every loop round. Every failure is swallowed with a WARNING (D1), and the binding can be disabled per project.

## Implementation Notes

### Development Approach

1. Refactor without behavior change: `RunCost.frontmatter_fields` and `from_record`, `review/frontmatter_usage.py`, and `artifact_paths.dispatch_artifact_paths`. Existing review, stats and post-condition tests must pass unchanged.
2. `pipeline/artifact_usage.py` (`fold`, read, fields), with unit tests over fold sequences: priced, unpriced, missing and malformed prior.
3. `events/builtin/usage_stamp.py` and its binding. Event-level tests with a temp project: slice design, task file, arch doc, split task files (`-1`, `-2`), keep, failed dispatch, no frontmatter.
4. `stats/artifacts_report.py`, the `artifacts` subcommand, and the `slice` header line. Test fixtures copied from real slice and task frontmatter in this repo (CLAUDE.md parsing rule).
5. Update the wrapper subcommand lists, CHANGELOG bullet, and `140-arch.pipeline-foundation.md`: add `usage_stamp.py` to the `events/builtin/` tree and the stamp to the POST_ACTION ordering note (line 124).

### Special Considerations

- `update_frontmatter` sets `dateUpdated` to today. That is correct here, because the dispatch just edited the file.
- The stamp runs after `revision-stamp`, so a revision round makes two frontmatter writes. Separate bindings keep each one independently disableable, and two writes are not worth merging the actions for.
