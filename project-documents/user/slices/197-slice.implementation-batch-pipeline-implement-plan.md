---
docType: slice-design
slice: implementation-batch-pipeline-implement-plan
project: squadron
parent: project-documents/user/architecture/180-slices.pipeline-intelligence.md
dependencies: [196]
interfaces: []
dateCreated: 20261004
dateUpdated: 20261004
status: not_started
---

# Slice Design: implementation-batch-pipeline-implement-plan

## Overview

195 runs Phase 4 and Phase 5 over a whole slice plan. 196 added the pieces Phase 6 needs: branch steps, scoped commits, and dependency flags in `each`. This slice composes them into `implement-plan`, a pipeline that implements every ready slice of a plan with no human watching.

For each slice, in dependency order: branch → implement → code review → revise loop → devlog → merge. A slice that ends flagged is left on its unmerged branch, and its dependents are flagged. Independent slices continue. The run ends with one batch report.

It also adds the way back in, the **flag handoff**. (This is a different thing from the architecture's "escalation behaviors", which retry with a stronger model.) Someone (a human now, Amoeba's Judge later) decides, and squadron then reruns that one item of that run, by run ID, without rerunning the batch. Squadron doesn't decide. It reports precisely and acts on a decision.

The single-slice code pipelines (P6, `implement`, P56, P456) move onto the same steps, so a single slice and a whole plan are implemented the same way.

## Value

- **A whole plan can be implemented unattended.** Every slice with reviewed tasks gets implemented, reviewed, revised and merged in dependency order. The PM reads one report at the end.
- **Failure stays contained.** A flagged slice's work sits on its own branch, the target stays clean, and nothing builds on unfinished work.
- **Flags are machine-readable.** The report gets a JSON form with a closed `flagKind`, so Amoeba routes on a value, not on parsing reason text.
- **A decision is cheap to apply.** `sq run --resume <run_id> --item 196 --decision retry --instructions "…"` reruns one slice with the instructions, and keeps whatever work its branch already has. `--decision accept` merges a slice whose review didn't reach the threshold, which is the human override.
- **The single-slice pipelines get a code-review revise loop.** Today P6's implement step checkpoints on a FAIL code review with no revise round.

## Technical Scope

### Included

1. **`implement-plan.yaml`**, a built-in pipeline (D1).
2. **Source `cf.slices_ready_to_implement(plan, accept)`**, which selects open, designed slices and pre-flags the ones that aren't ready (D2). Items come back in dependency order (D3).
3. **`existing: keep` on `implement`.** If the slice branch already has commits ahead of the target, the implement dispatch is skipped and the step goes straight to its code review (D4).
4. **`branch enter` catches an existing branch up to the target** (issue #183). It fast-forwards when the branch has no commits of its own, and otherwise merges the target in. It never rebases or resets (D5).
5. **`branch: { plan: }`** aligns cf to the plan before entering, as phase steps already do (D6).
6. **Structured flags:** a `FlagKind` StrEnum on each flagged record, the failed step's name, the slice branch, and a versioned JSON report beside the Markdown one (D7).
7. **Item resume:** `sq run --resume <run_id> --item <index> --decision retry|accept [--instructions TEXT]`, with a git precondition, distinct exit codes and atomic report writes (D8, D9).
8. **A per-project run lock**, so only one batch or item resume mutates a project at a time (D11).
9. **The single-slice code pipelines refreshed** onto the same implement → loop → devlog → merge steps, with a test that keeps them identical to the batch body (D10).

### Excluded

- Deciding what to do with a flag. That's Amoeba's job (or the PM's).
- Abandoning or deferring a slice. That's a cf status change, made outside squadron. A deferred slice drops out of selection (195 `_EXCLUDED_STATUSES`).
- Running items concurrently (#146).
- Re-entering an item mid-body. An item always reruns its body from the top, and `existing: keep` and `skip_if_met` make the finished parts cheap (#59 stays open for pausing inside `each`).
- Rendering `each` and `loop:` in `--prompt-only` (#145).
- Waiting on an agent's background tasks before a dispatch ends (#163). Implement dispatches are where it hurts most, but it's a dispatch fix with its own issue.
- Pushing, opening PRs, or deleting branches.

## Dependencies

### Prerequisites

- **196** (complete, on `main`): `branch: {op: enter|merge}` (`pipeline/branch_ops.py`), CODE commits with `stage_all` on the slice branch, dependency flags in `each` (`_dependency_flag_reason`), `existing: keep` and `ExistingArtifactPolicy` on phase steps, `_review_flag`, and the review-trust fixes.
- **195** (complete): `each` with `on_item_failure: continue`, `BatchReport`, loop `accept_if` and `skip_if_met`, `dispatch: { feedback: review }`, and `item-reset`.
- **Amoeba:** nothing is required. Amoeba's Runner (its initiative 120) isn't built. This slice defines squadron's half of the handoff. See "Flag handoff contract" under Integration Points.

### Interfaces Required

- `cf list slices {plan} --json` (`status`, `designFile`) and `cf list tasks {plan} --json` (`completed`, `total`, `files`) through `ContextForgeClient`.
- `review/persistence.py`: `slice_review_stem`, `slice_name_for`, `REVIEWS_DIR`.
- `pipeline/git_ops.py`: `read_integration_target`, `verify_git_state`, `slice_branch_name`, `run_git`.
- `pipeline/state.py`: `StateManager` run state (pipeline name, params, status).
- The dispatch action's `override_instructions` param (`actions/dispatch.py` `_apply_override`), already used by checkpoint resolution.

## Architecture

### Component Structure

```
data/pipelines/
  implement-plan.yaml       NEW   the batch (D1)
  P6.yaml, implement.yaml,
  P56.yaml, P456.yaml       CHANGED implement → code-review loop → devlog → merge (D10)
pipeline/
  sources.py                CHANGED cf.slices_ready_to_implement; dependency ordering (D2, D3)
  steps/phase.py            CHANGED existing: keep allowed on implement (D4)
  actions/dispatch.py       CHANGED keep for CODE = slice branch ahead of target (D4)
  branch_ops.py             CHANGED enter catches up an existing branch; failure class in outputs;
                                    restore_target() extracted from the leave-other-branch path (D5, D7, D8)
  steps/branch.py           CHANGED optional plan: → cf-op set_arch before the action (D6)
  batch_report.py           CHANGED FlagKind, ItemDecision, failed_step, branch, decision;
                                    versioned JSON write (atomic) and load (D7)
  executor.py               CHANGED StepResult.exhausted; flag kind from the failed step;
                                    run one item of an each step (D7, D8)
  control_params.py         NEW   reserved param keys (override_instructions, accept_decision) (D8, D9)
  item_resume.py            NEW   ResumeExit, resume_item(): precondition, validate, rerun, rewrite report (D8, D9)
  run_lock.py               NEW   per-project exclusive run lock (D11)
cli/commands/run.py         CHANGED --item, --decision, --instructions on --resume; reserved -p keys rejected (D8)
```

### Data Flow

**A batch run:**

```
sq run implement-plan 180 --model sonnet
each slices ← cf.slices_ready_to_implement("180", "review.concerns_or_better")
  items in dependency order; not-ready slices carry flag_reason
  per item:
    summary item-reset                               fresh session
    branch enter (plan 180, slice N)                 set_arch 180; checkout/create N-slice.*;
                                                     existing branch: merge target into it (D5)
    implement (phase 6, existing: keep)              dispatch skipped if branch is ahead (D4)
      review code → commit "feat: implement slice N (review: …)"
    loop revise (until pass, accept_if concerns_or_better, skip_if_met, on_exhaust: fail)
      dispatch revise (feedback: review) → review code → commit per round
    devlog → commit DEVLOG.md on the slice branch
    branch merge → target; checkout ends on target
  item FAILED anywhere → FLAGGED {flagKind, failedStep, reason, branch}; dependents flagged
report → runs/{run_id}.slices.report.md  +  runs/{run_id}.slices.report.json
```

**Applying a decision:**

```
sq run --resume 3f9c2a1b --item 196 --decision retry --instructions "Use the existing CommitPlan; don't add a second builder."
  take the project run lock (held → exit 2)
  load run state → pipeline implement-plan, params, plan 180
  load report.json → record 196 is FLAGGED (flagKind review_unresolved)
  git precondition: on a flagged slice branch → restore_target(); then on target, clean, verify_git_state
  re-evaluate the source → item 196, fresh flag_reason and dependencies
  dependency check: any in-plan dependency not complete on the target → FLAGGED "dependency N not complete"
  run the each body once for item 196, with override_instructions set on its dispatches
    branch enter → catch up with target → implement kept (branch ahead) → review → loop → devlog → merge
  replace record 196 (decision recorded); rewrite report.md and report.json atomically
  exit 0 resolved | 1 flagged again | 2 rejected, nothing ran | 3 halted (environment / unknown git state)
```

### State Management

- **Run state** is unchanged in shape. Item resume reads the pipeline name and params from it. The run's status stays COMPLETED (a batch with flags is a completed run).
- **The report is the record of item outcomes.** `report.json` is written with the Markdown, and an item resume loads it, replaces one record, and writes both again. Both files are written to a temp file in the same directory and renamed, so a reader never sees a partial file. A resume killed partway through leaves the old record in place, and the next resume's precondition (D8) puts git back on the target. Each resumed record carries `decision` and `resumedAt`, so the report shows which outcomes came from a decision.
- **Git state:** as in 196. A batch ends on the target, unless its last item was flagged after entering its branch. In that case it ends on that slice branch, the same as any item failure (196 D5.4). The next `branch enter` or item resume commits that branch's leftovers and returns to the target. A flagged item's branch stays unmerged, with its work committed.
- **cf state:** the batch moves cf's arch, slice and phase per item, as 195 does. The same rule applies: don't run other cf-consuming commands in the project while a batch runs.

## Technical Decisions

### D1: `implement-plan.yaml`

```yaml
name: implement-plan
description: Implement every slice in a plan whose tasks review is acceptable, in dependency order; flag failures, report at end

params:
  plan: required
  model: sonnet
  review-model: minimax
  max-revisions: "2"
  pass-threshold: review.pass
  accept-threshold: review.concerns_or_better

steps:
  - each:
      name: slices
      source: cf.slices_ready_to_implement("{plan}", "{accept-threshold}")
      as: slice
      on_item_failure: continue
      steps:
        - summary: { template: item-reset, model: "{model}", emit: [rotate] }
        - branch: { op: enter, plan: "{plan}", slice: "{slice.index}" }
        - implement:
            phase: 6
            plan: "{plan}"
            slice: "{slice.index}"
            model: "{model}"
            review: { template: code, model: "{review-model}" }
            checkpoint: never
            existing: keep
        - loop:
            name: revise-code
            max: "{max-revisions}"
            until: "{pass-threshold}"
            accept_if: "{accept-threshold}"
            skip_if_met: true
            commit_each_iteration: true
            on_exhaust: fail
            steps:
              - dispatch: { name: revise, model: "{model}", feedback: review }
              - review: { template: code, model: "{review-model}", slice: "{slice.index}" }
        - devlog: auto
        - branch: { op: merge, slice: "{slice.index}" }
```

- **Thresholds work as in 195.** A pass ends the loop. If the rounds run out, a verdict at or above `accept-threshold` merges and the item is ACCEPTED. Anything below fails the loop, so the item is FLAGGED before devlog and merge, and its branch stays unmerged.
- **`review-model` defaults to `minimax`**, matching P6, the single-slice pipeline this body is shared with (D10). `--model` and `-p review-model=` override it as usual.
- **Loop-round commits** need no new code. The round's review template `code` maps to `CommitSubject.CODE`, which stages everything on the slice branch (196 D1, D3).
- **The revise prompt** is the code review's findings. A code review has no single input file, so the "revise in place" line is absent and the findings' file and line locations carry the context (`_resolve_feedback_prompt`).

### D2: Selection, `cf.slices_ready_to_implement(plan, accept)`

The source returns every open slice (status not `complete` or `deferred`) that has a design file. A slice that isn't ready is still returned, with `flag_reason`, so the report names it and its dependents are flagged.

The `flag_reason` checks, in order (first hit wins):

| Check | Reason |
|---|---|
| design review missing, unreadable or below `accept` | `no design review found`, … (existing `_review_flag`) |
| no task file | `no task file` |
| tasks review missing, unreadable or below `accept` | `no tasks review found`, … (`_review_flag` with `tasks`) |
| every task checked (`completed == total > 0`) but the slice is still open | `all tasks checked but slice not marked complete` |

- **The last row stops a merged slice from being reimplemented.** The Phase 6 agent checks off tasks and marks the slice complete on the slice branch, so both reach the target together at merge. A slice with all tasks checked but an open status was implemented and not closed out. Rerunning it would reimplement from scratch, because its merged branch is no longer ahead of the target (D4). It's flagged for the PM instead. An unmerged flagged branch doesn't trip this check, because its checkmarks aren't on the target yet.
- **Slices with no design file** are not returned. They have no dependencies to read (196 D9), and a plan usually has many of them, which would bury the real flags.
- **Dependencies on slices outside the run.** For each returned item, a dependency that is in the plan, open, and not itself a returned item (in practice, an undesigned slice) sets `flag_reason: dependency {d} not designed`. A dependency outside the plan isn't checked, and a WARNING names it (`slice 197: dependency 927 is outside plan 180; not checked`). Dependencies on returned items are left to `each`'s flag propagation and to the ordering (D3).
- **Rejected: returning only ready slices.** The PM would get no line for a slice that's missing its tasks, and its dependents would run, because their dependency wouldn't be "flagged in this run".

### D3: Dependency order

- `sources.py` gains `order_by_dependencies(items) -> list[dict]`. It's a stable topological sort over dependencies between returned items, with ties broken by plan order. A plan whose slices are already in dependency order comes back unchanged.
- **A cycle fails the source:** `ValueError("dependency cycle in plan 180: 196 → 197 → 196")`. The run fails before any item runs, logged at ERROR, through the existing source-evaluation error path.
- Only `cf.slices_ready_to_implement` orders its items. The other sources keep plan order. A design or task batch doesn't build on its dependencies' output, so order doesn't matter there.
- **Why it matters here:** a dependent's branch forks from the target at its own `branch enter`. If its dependency hasn't merged yet, the dependent is implemented without the code it builds on.

### D4: `existing: keep` on `implement`

- `PhaseStepType._validate_existing` accepts `keep` on the implement phase. Today it allows only design and tasks, the steps with an expected artifact.
- **For CODE, the "existing artifact" is work on the slice branch:** `git rev-list --count --no-merges {target}..{slice_branch}` is greater than 0.
  - Merge commits don't count. A catch-up merge (D5) on a branch with no work of its own must not make it look like it has work, or a retried empty branch would skip implement and fail on an empty diff forever.
  - When the count is greater than 0, the dispatch action skips the model call and returns success with `outputs={"skipped": "branch has work", "ahead": n}`, and logs `implement: step {name} keeps existing work on {branch} ({n} commits ahead of {target})`. The phase step's code review then runs on that work.
- The target comes from `read_integration_target`, the strict reader. A failed or timed-out `rev-list` raises `GitStateUnknownError`. It's never treated as 0, because a guessed 0 would reimplement over existing work.
- **This is the resume behavior.** On a rerun (a whole-batch rerun or an item resume), a flagged slice keeps its implementation. It's re-reviewed, revised with the decision's instructions, and merged. The only way to start over is for the PM to delete or rename the branch, and squadron never deletes branches.
- **A human fix counts as work.** If the PM fixes a flagged slice by hand on its branch and commits, `--decision retry` re-reviews it. If the review passes, `skip_if_met` skips the revise rounds and the item merges.

### D5: `branch enter` catches up an existing branch (#183)

When the slice branch already exists, enter checks it out. If the target has commits the branch lacks (`git rev-list --count {slice_branch}..{target}` > 0), it catches up:

- **No work of its own** (the D4 count, `--no-merges {target}..{slice_branch}`, is 0): `git merge --ff-only {target}`. The branch simply moves to the target, and no merge commit is created.
- **Otherwise:** `git merge --no-ff -m "merge: {target} into slice {n}" {target}`.
- **A conflict** gets 196's D6 treatment. Record the conflicted paths, `git merge --abort`, then run `verify_git_state` with the slice branch as the expected branch.
  - The item fails with `catch-up merge of {target} into {branch} failed: CONFLICT … (conflicted: …); resolve on the branch and retry`. The failure class is `conflict` (D7).
  - **Checkout after the abort:** the clean slice branch, as with every other item failure after enter. The next enter or item resume returns to the target (D8 precondition). Ending on the target would be a second "where a failed item leaves you" rule.
  - If the state check fails, it raises `GitStateUnknownError` and the run ends.
- **Merge, never rebase or reset.** The branch keeps its history, and nothing a human committed on it is rewritten.
- **Without this, a resumed item builds on an old base.** The 196 walkthrough saw it: rerunning `P6 106` after 107 merged produced a branch without 107's code, and the final merge conflicted.
- The code review's diff range is still the slice branch against its merge base with the target, so the catch-up merge doesn't show up as slice work.

### D6: `branch: { plan: }`

- `BranchStepType` accepts an optional `plan:`. It expands to `cf-op(set_arch, plan)` before the branch action, the same order phase steps use (195 D2).
- **Why:** `branch enter` resolves the slice through `resolve_slice_info`, which reads the active slice plan. On a batch's first item, cf may point at another plan, which gives `No slice with index N in the current slice plan` (seen in the 196 walkthrough). The implement step's own `set_arch` comes too late, because enter runs first.
- Merge doesn't need `plan:`, because the implement step has already aligned cf by then.

### D7: Structured flags and `report.json`

`batch_report.py` gains:

```python
class FlagKind(StrEnum):
    NOT_READY = "not_ready"                # source flag_reason (D2), except dependency rows
    DEPENDENCY = "dependency"              # flagged or not-designed dependency
    REVIEW_UNRESOLVED = "review_unresolved"  # loop exhausted below accept-threshold
    BRANCH_CONFLICT = "branch_conflict"    # catch-up or merge stopped on a git conflict
    STEP_FAILED = "step_failed"            # any other failed step (implement dispatch, devlog, …)
    PAUSED = "paused"                      # a checkpoint paused the item (not used by implement-plan)

class ItemDecision(StrEnum):               # defined here, not in item_resume.py, so the import
    RETRY = "retry"                        # runs one way: item_resume → batch_report
    ACCEPT = "accept"
```

- **`BatchItemRecord` gains** `flag_kind: FlagKind | None`, `failed_step: str | None`, `branch: str | None` (the slice branch when one was entered, from the enter action's outputs), `decision: ItemDecision | None` and `resumed_at: str | None`.
- **Where the kind comes from:**
  - A source `flag_reason` is NOT_READY. One the source sets for a dependency is DEPENDENCY.
  - `_dependency_flag_reason` in `each` is DEPENDENCY.
  - A failed step is classified from its `StepResult`:
    - A loop with `exhausted=True` is REVIEW_UNRESOLVED.
    - A branch action reports its failure class in its outputs: `failure: conflict | other`, using a `BranchFailure` StrEnum in `branch_ops.py`. Only `conflict` (the merge or catch-up stopped on conflicted paths) is BRANCH_CONFLICT. Every other branch failure is STEP_FAILED: a refused merge, a missing design file, or a failed `set_arch` cf-op.
    - Anything else is STEP_FAILED.
    - A PAUSED status is PAUSED.
  - Every kind is set where the flag is raised. Nothing is recovered by parsing `reason` text.
- `StepResult` gains `exhausted: bool = False`. The loop sets it when its rounds run out without `until` being met (whether it then accepts, fails, pauses or skips).
- **`report.json`** is written beside the Markdown, from the same records, in the same `finally`:

```json
{
  "docType": "batch-report",
  "schemaVersion": 1,
  "pipeline": "implement-plan",
  "runId": "3f9c2a1b7d10",
  "stepName": "slices",
  "plan": "180",
  "counts": {"passed": 3, "accepted": 1, "flagged": 2},
  "items": [
    {"index": "196", "name": "…", "outcome": "flagged",
     "flagKind": "review_unresolved", "failedStep": "revise-code",
     "reason": "loop exhausted at FAIL (accept: review.concerns_or_better)",
     "finalVerdict": "FAIL", "reviewFile": "project-documents/user/reviews/196-review.code.….md",
     "branch": "196-slice.…", "decision": null, "resumedAt": null}
  ]
}
```

- **Written after every item, not only at the end.** Each finished item's record triggers an atomic rewrite of both files. A batch killed outright (SIGKILL, OOM, machine loss) leaves a report covering every item it finished. The item that was running has no record, and its branch, if any, is on disk. A batch rerun reselects it from repository state (D2 and D4), so nothing is lost. It just isn't reachable by `--item`.
- **`ItemOutcome.NOT_RUN`** (new): when a `GitEnvironmentError` or `GitStateUnknownError` halts the batch, the `finally` records the in-flight item as FLAGGED (`step_failed`, the error as reason). It records every item the batch never reached as `not_run`, with the halt's error as reason. Item resume accepts `not_run` records with `--decision retry`, the same as FLAGGED, so Amoeba gets one signal for every item still owed. The JSON `counts` gain `not_run`.
- `schemaVersion` starts at 1 and goes up whenever the record shape or the `FlagKind` set changes. `BatchReport.load(path)` reads it back for item resume and rejects any other version with a message naming both versions. It never guesses. Keys use camelCase, matching review frontmatter, the format Amoeba already parses.
- The Markdown flagged line gains the kind and branch: `- 196 … — review_unresolved at revise-code; loop exhausted …; branch 196-slice.…; review: …`.
- `sq run` prints the JSON report's path next to the Markdown path on its batch summary line.

### D8: Item resume

```
sq run --resume <run_id> --item <index> --decision retry|accept [--instructions TEXT]
```

- **`ItemDecision`** (D7): `RETRY` and `ACCEPT`. `--decision` is required with `--item`. There's no default decision.
- **Exit codes** come from a `ResumeExit` IntEnum in `item_resume.py`, so an automated caller can tell outcomes apart:

  | Code | Meaning |
  |---|---|
  | 0 `RESOLVED` | the item ended PASSED or ACCEPTED |
  | 1 `FLAGGED` | the decision was applied, and the item was flagged again |
  | 2 `REJECTED` | validation, the precondition, or the run lock refused the request; nothing ran |
  | 3 `HALTED` | a `GitEnvironmentError` or `GitStateUnknownError` ended it mid-item |

  Code 2 lines up with Typer's usage-error code, which is also "nothing ran".
- **Validation** (each failure exits 2 before any git or model work, with a message naming the fact):
  - The run exists, and its pipeline has exactly one `each` step. With more than one, `--item` needs a step name, which no built-in pipeline needs. That's rejected for now with a message.
  - `report.json` exists for that step, and it has a record for `<index>` whose outcome is FLAGGED or NOT_RUN. Resuming a PASSED or ACCEPTED item is an error. `--decision accept` on a NOT_RUN item is rejected, because it has no review to accept.
  - `--decision accept` requires `flagKind: review_unresolved`. Accepting a conflict or a failed implement means nothing.
  - `--instructions` without `--item` is rejected.
- **Git precondition** (after the run lock, before the source is evaluated, because cf reads slice and task status from the working tree):
  1. If the checkout is on a slice branch, call `restore_target()`. This is the leave-other-branch path from 196 D5.4, extracted from `_leave_other_slice_branch` so enter and resume share it: commit leftovers on that branch, then check out the target.
  2. Then require the target (`read_integration_target`), a clean tree, and a passing `verify_git_state(target)`.
  3. On any other branch, or a dirty tree on the target, exit 2 with the 196 messages (`on {branch}, expected {target}…`, `working tree not clean: …`).
  - Without this, a resume started on a flagged branch would read that branch's checkmarks. A dependency could look complete, or the item could trip D2's "all tasks checked" row.
- **Execution:** the run's pipeline and params come from run state, so the same models and thresholds apply. `--model` and `-p` overrides apply on top, as with any resume. Then:
  1. The source is re-evaluated, and the item with `<index>` is taken from it, with a fresh `flag_reason` and dependencies. If the source no longer returns it:
     - **Reconcile:** if the slice is `complete` on the target and its slice branch is an ancestor of the target (`git merge-base --is-ancestor`), the item was merged by an earlier resume that died before rewriting the report. The record is rewritten as PASSED with `reason: "reconciled: merged before the report was updated"`, a WARNING is logged, and the exit is 0. Nothing runs.
     - **Otherwise** (deferred, undesigned, or complete without a merged branch), exit 2 naming the status.
  2. **Dependency check for a single item:** any dependency that is in the plan and not complete on the target flags the item `dependency {d} not complete` (DEPENDENCY), and the body isn't run. In a batch, this is covered by order and propagation. Alone, the target's status is the only evidence.
  3. The `each` body runs once for that item through the executor's existing per-item path (`_run_each_item`), with item isolation unchanged.
  4. `--instructions` sets `override_instructions` in the item's params, so every dispatch in the body (implement, if not kept, and each revise round) starts with the "Instructions from checkpoint resolution" block. That's the existing checkpoint plumbing, not a second carrier.
  5. The record is replaced with the new outcome (plus `decision` and `resumedAt`), and the report is rewritten in both formats, atomically.
- **Reserved param keys.** `override_instructions` and `accept_decision` are defined once, in `pipeline/control_params.py`. The executor's checkpoint path and `_apply_override` import them from there. They are guarded at every place params enter a run:
  - `_assemble_params` rejects either as a `-p` key (`'accept_decision' is reserved; use --decision accept`).
  - `validate_pipeline` rejects either in a pipeline's `params:` block.
  - Item resume strips both keys from the params it loads from run state, and logs a WARNING if any were present (a checkpoint resolution may have stored `override_instructions`). It then sets them from `--decision` and `--instructions` only. An earlier run's instructions never carry into a new decision.
- **Output:** the new record as one line, plus the report path. The exit code is from the table above.
- **Rejected: resuming by rerunning a single-slice pipeline** (`sq run P6 196`). Amoeba keys a squadron block by run ID (its arch 100: "resolution means the Runner issues `sq run --resume <run_id>`"), and a fresh run would lose the batch's params and its report. P6 still works for a human, and it gives the same result because the steps are shared (D10).

### D9: What `accept` does

`--decision accept` runs the same body, with one difference: the item's revise loop counts as met with `accepted=True` and runs no rounds. The executor passes `accept_decision: true` in the item params, and `_execute_loop_step` checks it before round 1, next to `skip_if_met`.

- **Effect:** enter (with catch-up) → implement kept → its code review runs once, recording the current verdict → loop accepted → devlog → merge. The record ends ACCEPTED with `decision: accept`.
- **The review still runs** so the report and the review file show what was accepted. That costs one review, and the slice is merged with its findings on record.
- **A catch-up or merge conflict still flags the item.** Accept overrides the review threshold, not git.
- **Rejected: running only the merge step.** That would skip the catch-up merge and the devlog, and leave the merge's precondition (being on the slice branch with a clean tree) to chance.

### D10: The single-slice pipelines share the body

P6, `implement`, P56 and P456 replace their implement section with the batch body's steps, minus `each` and `item-reset`:

```yaml
  - branch: { op: enter }
  - implement:
      phase: 6
      model: "{model}"
      review: { template: code, model: "{review-model}" }
      checkpoint: never
      existing: keep
  - loop:
      name: revise-code
      max: "{max-revisions}"
      until: "{pass-threshold}"
      accept_if: "{accept-threshold}"
      skip_if_met: true
      commit_each_iteration: true
      on_exhaust: checkpoint
      steps:
        - dispatch: { name: revise, model: "{model}", feedback: review }
        - review: { template: code, model: "{review-model}", slice: "{slice}" }
  - devlog: auto
  - branch: { op: merge }
```

- **One difference from the batch:** `on_exhaust: checkpoint` instead of `fail`. A single-slice run has a human at hand, and P456 and P56 already pause this way on their design and tasks loops.
- P6 and `implement` gain the `max-revisions`, `pass-threshold` and `accept-threshold` params, with the same defaults as P456. `implement.yaml` gains `review-model`, because it has none today. Its review uses the resolver default.
- Model defaults are unchanged per pipeline (P4's design default stays `opus`).
- **Drift test:** `tests/pipeline/test_builtin_pipelines.py` asserts that the implement-through-merge steps of each single-slice pipeline equal the `implement-plan` body from `branch enter` on. The comparison normalizes the `slice:` and `plan:` references and the one `on_exhaust` difference. Changing one file without the others fails the test.
- **Rejected: a sub-pipeline or include step.** That's a new step type, with its own param scoping and resume semantics, to save about 20 lines of YAML in five files. The drift test gets the same guarantee.

### D11: One mutating run per project

Amoeba is an unattended caller and could send decisions for several flagged items at once. Two processes checking out branches and moving cf's slice in one project would interleave. They would also race on `report.json`.

- `pipeline/run_lock.py` provides `project_run_lock(cwd)`. It takes an exclusive, non-blocking `flock` on `{git dir}/squadron-run.flock` (`git rev-parse --git-dir`, which is per worktree). Each registered worktree has its own checkout, cf state and target, so separate worktrees can still run in parallel. Two runs in one checkout can't.
- **Taken by** item resume, and by any `sq run` whose pipeline mutates git or cf state. That's any step that commits or moves cf: a phase step (`design`, `tasks`, `implement`, which run `set_arch`/`set_slice`/`set_phase` and commit), `devlog`, `branch`, or a `loop` with `commit_each_iteration`. The executor finds them by walking the definition, nested steps included. That covers `slices-plan`, `tasks-plan`, `implement-plan` and every P-pipeline. `review` alone and `summary` pipelines don't take the lock.
- **Held:** the run doesn't start. Both item resume and `sq run` exit 2, meaning "nothing ran" (D8's table; for `sq run`, 1 already means a failed run), with `another squadron run holds the project lock ({path}); one mutating run per project at a time`, logged at ERROR. It doesn't wait, so a caller decides when to retry.
- **A killed process** releases its `flock` when the OS closes the file, so no stale lock is left behind.
- POSIX only, imported inside the function, the same as `codehost/metadata_lock.py`. On Windows, taking the lock raises a clear error. It's a separate lock from the worktree metadata lock, which serializes short git calls with a wait, not whole runs.
- The flag handoff contract states the rule: one item resume per project at a time, and a REJECTED exit for a busy lock means try again later.

### D12: Failure modes of the new paths

Every git call goes through `run_git`, which returns `None` on a timeout (196). Every row below has a test that asserts both the outcome and the log record (level and message).

| Path | Failure | Handling | Signal |
|---|---|---|---|
| D4 keep check `rev-list` | non-zero exit or timeout | `GitStateUnknownError`; the run halts (item resume exits 3) | ERROR `cannot count work on {branch}: …` |
| D5 behind check `rev-list` | non-zero exit or timeout | `GitStateUnknownError` | ERROR `cannot compare {branch} with {target}: …` |
| D5 catch-up `merge` / `merge --ff-only` | conflict | abort, state check, item failure `conflict` | WARNING `item N flagged: catch-up merge … conflicted: …` |
| D5 catch-up `merge` | refusal or timeout | abort if `MERGE_HEAD`, state check; passes → item failure `other`, fails → `GitStateUnknownError` | WARNING / ERROR |
| `restore_target()` (D8 precondition) | commit or checkout fails or times out | `GitStateUnknownError`; exit 3 | ERROR, as 196 D5.4 |
| Report temp write or rename | `OSError` (for example ENOSPC) | `logger.exception`, then re-raised; the previous report stays intact because the rename never happened; the run fails (item resume exits 3) | ERROR with the path |
| `report.json` load | missing, unparseable, or wrong `schemaVersion` | exit 2 | ERROR naming the path and the problem |
| Run lock: `rev-parse --git-dir` | non-zero exit or timeout | `GitEnvironmentError`; exit 2, nothing ran | ERROR |
| Run lock: open or `flock` | held | exit 2 | ERROR `another squadron run holds the project lock …` |
| Run lock: open or `flock` | other `OSError` | exit 2 | ERROR with the path |
| Implement dispatch | hangs, or the session drops mid-turn | **not bounded by this slice.** A stalled turn is #165, and work lost to background tasks is #163. A dropped session raises today's dispatch error, so the item is `step_failed`. A hang holds the run lock until the operator kills the run. The kill releases the lock, and the per-item report already covers every finished item. | existing dispatch logging |
| Implement dispatch | ends with no commits | the code review raises `EmptyDiffError`; the item is `step_failed`; a retry runs implement again (D4 counts no work) | WARNING `item N flagged: …` |

### Patterns and Conventions

- New enums (`FlagKind`, `ItemDecision`) are StrEnums, defined once. Routing reads `flagKind`, never `reason`.
- Git calls go through `run_git` and the 196 failure classes. Item failures are `ActionResult(success=False)` with git's text. An unknown state raises `GitStateUnknownError`, logged at ERROR. There's no `--force`, `reset`, rebase or branch deletion.
- Paths and branch names are computed (`slice_branch_name`, `slice_review_stem`), never globbed.

## Implementation Details

### API Contracts

**Pipeline grammar**

```yaml
- branch: { op: enter, plan: "<optional arch index>", slice: "<optional>" }
- implement: { ..., existing: keep }
```

**Source**

```
cf.slices_ready_to_implement("<arch index>", "<LoopCondition value>")
```

Item shape: the 196 slice item (`index`, `name`, `status`, `design_file`, `dependencies`), plus an optional `flag_reason` and `flag_kind` (`not_ready` | `dependency`).

**CLI**

```
sq run implement-plan <plan> [--model M] [-p review-model=R] [-p max-revisions=N]
sq run --resume <run_id> --item <index> --decision retry|accept [--instructions TEXT]
```

**Report files**

`{runs_dir}/{run_id}.{step_name}.report.md` (existing, with the kind and branch added to flagged lines) and `{runs_dir}/{run_id}.{step_name}.report.json` (D7).

## Integration Points

### Provides to Other Slices

- **Flag handoff contract (Amoeba, tracked in amoeba#1).** This is squadron's half, recorded here because Amoeba has no document for it yet. Its Runner (initiative 120) and Judge (140) aren't started.
  - **Event:** a batch run completes, and its `report.json` has items with `outcome: flagged` or `not_run` (a halted batch). Amoeba already matches runs through `runs/*.json` (its `sq_runs` observer). The report sits beside that file as `{run_id}.{step}.report.json`.
  - **Routing input:** `flagKind` (closed set, D7), `failedStep`, `reason` (human text), `finalVerdict`, `reviewFile` (Amoeba's slice 105 parser reads it), and `branch`.
  - **Decision back:** `sq run --resume <run_id> --item <index> --decision retry|accept [--instructions TEXT]`, invoked with non-TTY stdin (Amoeba's rule). A free-text `Resolution.detail` maps to `--instructions`.
  - **Result:** exit 0 means resolved (merged), and 1 means flagged again; the rewritten `report.json` record says why. Exit 2 means rejected and nothing ran (bad request, git precondition, or project lock busy). Exit 3 means halted on the environment or an unknown git state, which needs a human.
  - **Concurrency:** one item resume per checkout at a time (D11). A busy lock is exit 2; retry later.
  - **Versioning:** check `schemaVersion` (currently 1) before reading the items.
  - **Not covered by squadron:** abandoning or deferring (a cf status change), and `not_ready` or `dependency` flags. Those are fixed upstream (design, tasks, or the dependency), then the item is retried or the batch rerun.
  - A copy of this contract goes into `docs/PIPELINES.md` under "Batch reports and the flag handoff", where Amoeba's maintainers can find it.
- **198 and later batches:** `FlagKind`, `report.json` and item resume work for any `each` pipeline. `accept` is limited to items flagged `review_unresolved`, which `slices-plan` and `tasks-plan` also produce, so a design or tasks flag can be accepted the same way.

### Consumes from Other Slices

- **196:** the branch steps, CODE commits, dependency flags, `existing: keep`, and `git_ops`. D4 and D5 extend `branch_ops.py` and the dispatch keep check.
- **195:** `each` isolation and policy, `BatchReport`, loop `accept_if` and `skip_if_met`, and `feedback: review`.
- **cf:** slice status, design files and task progress. A failing cf call fails source evaluation, so the run fails before any item. Nothing degrades to a guess.

## Success Criteria

### Functional Requirements

1. `sq run implement-plan <plan>` implements every ready slice in dependency order: branch, implement, code review, revise rounds as needed, devlog, merge. The checkout ends on the target, with one `merge: slice N — …` commit per merged slice.
2. Slices without a task file, or with a design or tasks review below `accept-threshold`, appear in the report as FLAGGED `not_ready` with the D2 reason, and their bodies don't run. A slice with all tasks checked but an open status is flagged and not reimplemented.
3. A slice whose code review stays below `accept-threshold` after `max-revisions` is FLAGGED `review_unresolved` at `revise-code`. Its branch stays unmerged with all work committed, and the next item starts from a clean target.
4. Dependents of a flagged slice are FLAGGED `dependency`. A dependency on an undesigned slice in the plan flags the dependent `dependency N not designed`. Independent slices run and merge.
5. Items run in dependency order even when the plan lists a dependent first. A dependency cycle fails the run before any item, naming the cycle.
6. `report.json` is written beside `report.md`, after every item and when a `GitEnvironmentError` halts the run. On a halt, the in-flight item is FLAGGED and every unreached item is `not_run`, and `--item N --decision retry` works on a `not_run` item. Every flagged record has `flagKind`, `failedStep` (null for pre-flags), `reason` and `branch` (when a branch was entered).
7. `sq run --resume <id> --item N --decision retry --instructions "…"` on a `review_unresolved` item keeps the branch's implementation (no implement dispatch), re-reviews it, runs revise rounds whose prompts begin with the instructions, and merges on an acceptable verdict. The record is replaced, with `decision: retry`.
8. `--decision accept` on a `review_unresolved` item merges it after one code review and records it ACCEPTED with `decision: accept`. On any other flag kind, it exits 2 before doing anything.
9. Resuming an item whose dependency is still open on the target flags it `dependency N not complete` without running. Resuming a non-flagged item, an unknown index, or a run without `report.json` exits 2 with a message.
10. `branch enter` on an existing branch that's behind the target catches it up:
    - A branch with work gets the target merged in (`merge: main into slice N`).
    - A branch with no commits of its own fast-forwards, and a retry of it runs the implement dispatch instead of skipping it.
    - A conflicting catch-up leaves the branch clean (no `MERGE_HEAD`), the checkout on that branch, and the item flagged `branch_conflict` with the conflicted paths.
11. A batch's first item enters correctly when cf's active plan is a different plan (`branch: { plan: }`).
12. P6, `implement`, P56 and P456 run the code-review revise loop, pausing on exhaust. A second `sq run P6 N` on a slice whose branch has work skips the implement dispatch.
13. Branch failures that aren't conflicts are flagged `step_failed`, not `branch_conflict`: a missing design file, a failed `set_arch`, and a refused merge.
14. An item resume started on a flagged slice branch first commits that branch's leftovers and returns to the target, then evaluates the source. Started on an unrelated branch or a dirty target, it exits 2 with nothing changed.
15. Item resume exits 0, 1, 2 or 3 as D8's table defines. A second item resume, or a code-pipeline `sq run`, started while one holds the project lock is refused with the lock message and changes nothing.
16. `-p accept_decision=true` and `-p override_instructions=…` are rejected as reserved keys.
17. `report.json` carries `schemaVersion: 1`. Loading a report with any other version fails with a message naming both versions. A resume whose slice was merged before the report was rewritten reconciles the record to PASSED and exits 0. `slices-plan` and `tasks-plan` runs take the run lock. Reserved keys are rejected in a pipeline `params:` block and stripped from loaded run state with a WARNING.

### Technical Requirements

- Unit tests:
  - the source: every D2 row, the dependency-not-designed and out-of-plan rows, ordering, and a cycle
  - `order_by_dependencies`: stability and ties
  - `existing: keep` for implement, against a temp repo: ahead, not ahead, merge commits only (not ahead), and a `rev-list` timeout raising
  - the catch-up merge, against a temp repo: behind with work, behind with no work (fast-forward, then implement runs on retry), conflict, abort, and a failed state check
  - `branch: { plan: }` expansion
  - `FlagKind` assignment for each kind, including each `BranchFailure` class
  - the `report.json` round trip, atomic write, and a version mismatch, per-item rewrite, `not_run` on halt, and the post-merge reconcile
  - each D12 row: the outcome plus the asserted log record
  - item resume: validation errors, the git precondition (flagged branch restored, unrelated branch refused), each exit code, retry, accept, the single-item dependency check, and `override_instructions` reaching the dispatch
  - `project_run_lock`: a second holder refused, release on process exit
  - reserved `-p` keys rejected
  - loop `accept_decision`
  - the D10 drift test
- Every git test runs in a temporary repo created by the test.
- `docs/PIPELINES.md` documents `implement-plan`, `existing: keep` on implement, `branch: { plan: }`, the enter catch-up, `report.json`, item resume, and the flag handoff contract.
- ruff format, ruff check, and pyright are clean.

### Integration Requirements

- An Amoeba-like caller can complete the loop using only the CLI and files: run the batch, read `report.json`, choose a decision per flagged item, and call item resume until no flags it can act on remain.
- Item resume works on `slices-plan` and `tasks-plan` runs too (retry, and accept on `review_unresolved`), with no pipeline-specific code.

### Verification Walkthrough

Use the scratch project (`…/scratchpad/sq-scratch`, toy "tally" CLI, plan 100, slices 101–107) with `env -u CLAUDECODE uv run --project <squadron> sq …`. Always pass `--model`. Before starting, run `cf set arch 100`, and give `DEVLOG.md` YAML frontmatter (196 walkthrough caveats).

**Setup.** Add two new slices (108, 109) to plan 100, with designs, tasks, and passing design and tasks reviews: `sq run slices-plan 100` then `sq run tasks-plan 100`. Give 109's design `dependencies: [108]`, and list 109 before 108 in the slice plan. Commit. The tree must be clean.

1. **Batch.**
   ```bash
   sq run implement-plan 100 --model haiku -v
   ```
   Expected:
   - 108 runs before 109 (ordering).
   - Slices 101–107, already implemented and marked complete, aren't selected. Any that are open with all tasks checked are flagged `all tasks checked but slice not marked complete`.
   - Each run item logs `branch enter`, the implement dispatch, a code review with a resolved diff range, rounds of `revise-code` as needed, devlog, and `branch merge`.
   - The summary line prints both report paths.
   ```bash
   git branch --show-current                     # main
   git log --oneline --first-parent -4           # merge: slice 109 — …, merge: slice 108 — …
   jq '.items[] | {index, outcome, flagKind}' ~/.config/squadron/runs/<run_id>.slices.report.json
   ```

2. **A flagged item and its dependent.** Force a flag deterministically with a threshold no review can meet in zero rounds: `-p max-revisions=0 -p pass-threshold=review.pass -p accept-threshold=review.pass`, on a fresh pair of slices (or reset 108 and 109 by reverting their merges). When 108's review isn't PASS:
   - 108 is `review_unresolved` at `revise-code`, with `branch: 108-slice.…`.
   - 109 is `dependency` (`dependency 108 flagged`).
   - `git branch --list '108-slice.*'` exists, and `git log main..108-slice.…` shows the implement commit. `main` doesn't have it.

3. **Retry with instructions.**
   ```bash
   sq run --resume <run_id> --item 108 --decision retry -p max-revisions=2 -p accept-threshold=review.concerns_or_better \
     --instructions "Keep the CLI flags unchanged; fix only what the review lists."
   ```
   The log shows `implement: step … keeps existing work on 108-slice.… (1 commits ahead of main)`, a code review, revise rounds whose dispatch prompt begins with the instructions block (`-vv`), and a merge. It exits 0, and `report.json` now has 108 `accepted` or `passed` with `decision: retry`. 109 is still flagged. Resume it with `--item 109 --decision retry`. Its dependency is now complete on `main`, so it runs.

4. **Accept.** Repeat step 2 to flag an item, then run `sq run --resume <run_id> --item 108 --decision accept`. One code review runs, there are no revise rounds, and the item merges, recorded `accepted` with `decision: accept`. Then `--decision accept` on the dependency-flagged 109 exits 2: `accept requires flagKind review_unresolved; item 109 is dependency`.

5. **Catch-up merge.** With 108 flagged and unmerged, commit an unrelated change on `main`. Run `--item 108 --decision retry`. Enter logs `merge: main into slice 108`, and the code review's diff range doesn't include the unrelated change. To see a conflict, commit on `main` an edit to a line 108's branch also changed, and retry. The item is flagged `branch_conflict`, and the message lists the conflicted path. `git -C . rev-parse -q --verify MERGE_HEAD` prints nothing. The checkout stays on the clean slice branch (D5). A later `--item 108` resume returns to `main` before doing anything (D8 precondition).

6. **Wrong plan active.** `cf set arch 180`, then rerun step 1 on a fresh slice. The first item's enter succeeds (`set_arch 100` runs first).

7. **Single-slice parity.** `sq run P6 <slice> --model haiku` shows the same enter → implement → `revise-code` → devlog → merge sequence. With `-p max-revisions=0 -p accept-threshold=review.pass` and a non-PASS review, it pauses at a checkpoint instead of flagging.

## Risk Assessment

### Technical Risks

- **Unattended code changes merged on a review's say-so.** A weak reviewer at `concerns_or_better` can merge mediocre work into the target.
- **Implement dispatches are long,** and #163 (a dispatch ends while background tasks are still running) loses work there more than anywhere.

### Mitigation Strategies

- The thresholds and the review model are params, visible in the pipeline file. Every merged slice's review file is in the report. Nothing is pushed, so the PM can still revert a merge commit on the target before sharing it.
- An implement dispatch that ends with no commits fails the code review on an empty diff (`EmptyDiffError`), so the item is flagged `step_failed`, not merged. Its work isn't silently accepted. #163 stays its own fix.

## Implementation Notes

### Development Approach

1. **D5 catch-up merge and D6 `branch: { plan: }`.** Both are small `branch_ops`/`steps/branch.py` changes with temp-repo tests, and they close #183.
2. **D4 `existing: keep` on implement.**
3. **D2/D3 source and ordering.**
4. **D7 `FlagKind`, `StepResult.exhausted`, `report.json`.**
5. **D1 `implement-plan.yaml` and D10 single-slice refresh**, plus the drift test.
6. **D11 run lock and `control_params.py`.**
7. **D8/D9 item resume** (`item_resume.py`, `restore_target()`, exit codes, CLI flags, loop `accept_decision`).
8. `docs/PIPELINES.md` (including the flag handoff contract), then the live walkthrough.

### Special Considerations

- `--resume` without `--item` keeps its meaning (resume a paused run). `--item` turns it into an item resume, and works on COMPLETED runs, where a plain resume prints "All steps already completed. Nothing to resume." and exits 0.
- Item resume reuses `_run_each_item`, so per-item isolation, item reset, and failure classification are the same code the batch runs.
- Issue #183 is closed by this slice (D5).
- Effort: 4/5.
