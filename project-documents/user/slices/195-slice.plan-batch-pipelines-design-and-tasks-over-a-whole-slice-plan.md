---
docType: slice-design
slice: plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan
project: squadron
parent: project-documents/user/architecture/180-slices.pipeline-intelligence.md
dependencies: [194, 181]
interfaces: []
dateCreated: 20260926
dateUpdated: 20260926
status: not_started
---

# Slice Design: plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan

## Overview

Two unattended batch pipelines that walk a whole slice plan. `design-plan` designs and reviews every slice that has no design yet. `tasks-plan` breaks every designed slice into tasks, provided its design review was acceptable. A slice that can't reach an acceptable review goes on a flag list, and the run moves on. The run ends with one report for the PM: passed, accepted at CONCERNS, and flagged with reasons.

The engine changes are general, so each batch is a YAML file:

- slice-selection sources that honor their plan argument
- `each` that records a failed item and continues
- a `loop` nested inside `each`
- a second threshold on `loop`
- a dispatch that revises against the prior review's findings
- an end-of-run report

The slice also fixes issue #139, so every review a batch writes can be traced back to its run.

Sources: issue #136 and its Phase 5 addendum comment, and issue #139.

## Value

- **For the PM:** this replaces the most repeated manual routine in daily use, which is running P4 or P5 by hand for each slice or driving them from a `/loop` prompt. One command covers a plan, and one report says what needs a human.
- **For automation (Amoeba):** each review artifact records the run that wrote it and the squadron version, and it marks provider failures in its frontmatter. `--output json` stdout becomes parseable (#139).
- **Architectural:** `each` + `loop` composition, per-item isolation, and the report are reusable. A later Phase 6 batch or any other per-item pipeline builds on them without another engine change.

## Technical Scope

### Included

1. **Plan-aware slice sources.** `cf.undesigned_slices(plan)`, `cf.untasked_slices(plan, accept)`, and a fix so `cf.unfinished_slices(plan)` actually uses its `plan` argument.
2. **Plan alignment.** A new cf-op `set_arch` runs `cf set arch` with the plan's parent architecture document, which switches the initiative and sets the plan. It's emitted by the phase step when that step carries a `plan:` key.
3. **Unified step dispatch.** One `_execute_step()` routes every step type (once, loop sub-field, `loop:` body, `each`, `fan_out`). The top level, `each` bodies, and `loop:` bodies all call it. This makes `loop:` inside `each` actually run.
4. **`each` inner-step validation.** `each` validates its body with each inner step type's own `validate()`, and bans nested `each`.
5. **Per-item isolation in `each`:**
   - Each item gets its own copy of the prior outputs and step outputs.
   - `on_item_failure: stop | continue`.
   - A source can mark an item as flagged before its body runs.
6. **Loop additions:**
   - `accept_if` sets the second threshold, applied when the loop runs out of rounds.
   - `skip_if_met` skips the loop when the verdict already in scope meets `until`.
   - `max`, `until`, and `accept_if` can come from pipeline params.
7. **Revise dispatch.** `dispatch: { feedback: review }` appends the most recent in-scope review's findings and the path of the file that was reviewed. The review action adds `input_file` to its outputs.
8. **Batch report.** Each `each` step records per-item outcomes. At the end it writes a Markdown report next to the run state file and prints a summary on stdout.
9. **Pipelines.** `design-plan.yaml` (new; replaces `design-batch.yaml`, which is deleted) and `tasks-plan.yaml` (new).
10. **Issue #139:**
    - `runId` and `squadronVersion` in the frontmatter, plus `run_id` and `squadron_version` in JSON.
    - `providerFailure: true` on provider-failure artifacts.
    - The "Saved review to" line goes to stderr under `--output json`.
    - `to_dict()` gains `location_verified` per structured finding and the finding-scan counts.
11. **Docs.** `docs/PIPELINES.md` covers the sources, `each` options, loop options, `feedback: review`, the report, and the two pipelines. CHANGELOG and DEVLOG entries.

### Excluded

- A Phase 6 batch. Each slice needs its own branch created and merged, so a failed slice has git consequences. That needs its own design.
- Judge nodes that decide which findings are valid before revising. The `findings-addressed` gate exists and can be added to the loop body later without engine work.
- `--prompt-only` rendering of `each` and `loop:` steps. The prompt renderer handles neither today, and that predates this slice. It's issue #145.
- Running inside a Claude Code session. `sq run` refuses there (#144), and these pipelines dispatch through an SDK session, so #144's proposal would refuse them too. They run from a terminal.
- Nested `each`, and `each` inside a `loop:` body. Both are rejected by validation in v1.

## Dependencies

### Prerequisites

- **194 (Loop Step Type for Multi-Step Bodies)**: complete. It provides the `loop:` step with `steps:`, `until`, `on_exhaust`, and `commit_each_iteration`.
- **181 (Pool Resolver Integration)**: complete. `review-model: pool:review` resolves through `ModelResolver.resolve`, which the review action already calls ([review.py:174](../../../src/squadron/pipeline/actions/review.py#L174)).
- **909 dispatch-artifact post-condition**: complete. A `design:` or `tasks:` step whose dispatch writes no artifact fails. That is what turns an empty design into a flagged item instead of a silent success.
- **Context Forge CLI**: `cf list slices {archIndex} --json` and `cf list tasks {archIndex} --json` read a plan other than the active one without changing any state. Both are verified against cf as installed.

### Interfaces Required

- `ContextForgeClient` ([context_forge.py](../../../src/squadron/integrations/context_forge.py)): `list_slices()` and `list_tasks()` gain an optional `plan` argument (an arch index), passed through as the positional `archIndex`.
- `squadron.documents.frontmatter.split_document` and `squadron.review.models.Verdict`: reading the design review's verdict (Phase 5 selection).
- The review save target's `filename_stem("slice")` ([save_target.py:47](../../../src/squadron/review/save_target.py#L47)): computes the exact path of a slice's design review. There is no prefix search, which avoids the cf#90 failure mode.
- `squadron.__version__`: the version recorded in review artifacts.

## Architecture

### Component Structure

```
pipeline/
  executor.py        _execute_step()           NEW   single step router (extracted)
                     _execute_each_step()      CHANGED per-item isolation, failure policy, records
                     _execute_loop_body()      CHANGED skip_if_met, accept_if; inner steps via _execute_step
                     _parse_loop_config()      CHANGED accept_if, skip_if_met, numeric-string max
                     LoopCondition             CHANGED met_by_verdict() — single threshold source
  sources.py         NEW   source registry + cf.* sources (moved out of executor.py)
  batch_report.py    NEW   ItemOutcome, BatchItemRecord, BatchReport, render + write
  steps/collection.py      CHANGED validate inner steps, on_item_failure, nested-each ban
  steps/loop.py            CHANGED accept_if / skip_if_met validation, placeholder tolerance
  steps/phase.py           CHANGED optional plan: key → cf-op set_arch; order becomes arch → slice → phase
  actions/cf_op.py         CHANGED CfOperation.SET_ARCH
  actions/dispatch.py      CHANGED feedback: review
  actions/review.py        CHANGED outputs["input_file"], run_id onto ReviewResult
data/pipelines/
  design-plan.yaml         NEW   (design-batch.yaml deleted)
  tasks-plan.yaml          NEW
integrations/context_forge.py  CHANGED list_slices(plan) / list_tasks(plan)
review/models.py               CHANGED run_id field; to_dict() gains 139 keys
review/persistence.py          CHANGED frontmatter runId / squadronVersion / providerFailure
cli/commands/review.py         CHANGED "Saved review to" → stderr under --output json
cli/commands/run.py            CHANGED print batch summary + report path
```

`executor.py` is already 1704 lines. The source registry moves to `pipeline/sources.py` because this slice adds two sources to it. New per-item bookkeeping lives in `batch_report.py`, not the executor.

### Data Flow

`design-plan` on plan 900:

```
sq run design-plan 900
  step slices        each source=cf.undesigned_slices("900"), on_item_failure=continue
    per item (slice record {index,name,status,design_file[,flag_reason]}):
      fresh item scope: prior_outputs copy, step_outputs copy
      design:  set_arch (plan 900's parent: → cf set arch, which sets the plan)
               → set_slice {index} → set_phase 4 → build_context → dispatch → review(slice) → commit
               (FAILED here — no design written, provider failure — → item FLAGGED, next item)
      loop:    skip_if_met → until met by design's review? → 0 rounds, done
               else up to {max-tries} rounds:
                 dispatch feedback=review  (findings + reviewed file path → revise in place)
                 review(slice, slice={index})
                 commit (commit_each_iteration)
               until met → PASSED
               exhausted: accept_if met → ACCEPTED; else FAILED → item FLAGGED
    item record appended
  report  → {runs_dir}/{run_id}.slices.report.md + stdout summary
```

`tasks-plan` is identical in shape, with three differences:

- The source is `cf.untasked_slices("{plan}", "{accept-threshold}")`.
- The phase is `tasks:` (phase 5).
- The review template is `tasks`.

The source marks a slice with a `flag_reason` when its design review is missing or below the accept threshold. `each` records that slice as FLAGGED without running its body.

### State Management

- **cf project state is changed deliberately.** `set_arch` changes the active arch and, through cf, the plan. `set_slice` and `set_phase` change the phase and slice on every item, as P4 and P5 already do today. After the run, cf points at the batch's plan, at the last item's slice, and at the batch's phase. The run doesn't restore the previous state. The report's header records the plan the batch ran over.
- **Item scope is discarded after each item.** Item N+1 never sees item N's review. Without isolation, slice 924's revise dispatch would take its findings from slice 923's review.
- **Resume.** An interrupted run is rerun, not resumed mid-item. Selection is by artifact presence (a design file or a task file), so a rerun picks only what's left. A slice flagged after a design file was written is not re-selected by `design-plan`. `tasks-plan` then flags it again for "design review below threshold", so it keeps showing up in reports and never drops out silently. `sq run --resume` of a paused batch restarts the `each` step from the top, which has the same effect.
- **Report.** One Markdown file per `each` step per run: `{runs_dir}/{run_id}.{step_name}.report.md`, next to `{run_id}.json`.

## Technical Decisions

### D1: Selection sources

The status exclusion set is `{complete, deferred}`, defined once as a `CfSliceStatus` StrEnum (`COMPLETE`, `DEFERRED`) in `sources.py`. No string literals are scattered.

| Source | Selects | Per-item flag |
|---|---|---|
| `cf.undesigned_slices(plan)` | status ∉ excluded **and** `designFile` is null | — |
| `cf.untasked_slices(plan, accept)` | status ∉ excluded **and** `designFile` set **and** index absent from `cf list tasks {plan}` | `flag_reason` when the design review is missing, has no parseable verdict, or has a verdict that fails `accept` |
| `cf.unfinished_slices(plan)` | status ≠ complete (unchanged meaning) | — |

- **`plan` is the arch index** (`900`), passed to cf as `archIndex`. A value that isn't all digits raises `ValueError("plan must be an architecture index, got …")` when the source runs. The existing `unfinished_slices` bug (it ignores `plan` and reads the active plan) is fixed in the same way. `app.yaml` keeps working.
- **The design review path is computed, never searched:** `reviews_dir / f"{SliceTarget.filename_stem('slice')}.md"`, built from the same slice info the save path uses. Archived predecessors (`archive_existing_review`) are never read.
- **The verdict comes from frontmatter** via `split_document` + `yaml.safe_load`, validated against `Verdict`. The three failure reasons are distinct strings in the report: "no design review found", "design review verdict unreadable", and "design review below threshold (CONCERNS < PASS)".
- **Rejected: a filter parameter on `unfinished_slices`.** It would change the meaning of an existing source that `app.yaml` depends on, and a string filter language is more surface than two named sources.

### D2: Plan alignment is an explicit, state-changing cf-op

Review input resolution (`resolve_slice_info`) reads the active plan's slices and the active arch file. `cf set slice` only accepts a slice in the current initiative and plan. A batch over a non-active plan therefore has to switch the initiative first, or its dispatches and reviews run against the wrong documents.

The cf switching sequence is fixed:

1. `cf set arch {arch}` switches the initiative and sets the plan automatically.
2. `cf set slice {slice}`, which must be in that plan.
3. `cf set phase {phase}`, always after the slice.
4. `cf build` with no parameter overrides. It renders from the state set above.

`cf set plan` and `cf build --slice/--phase` are not used for switching.

- `CfOperation.SET_ARCH` with a `plan` (arch index) param:
  1. Resolve the plan's filename from `cf list slices {plan} --json` → `slicePlan`.
  2. Read that plan file's frontmatter `parent:` (the arch document).
  3. Run `cf set arch {parent stem}`.
  4. If the plan has no `parent:`, fail with an error that names the file.
- **Where it runs.** There is no top-level `cf-op` step type (the `StepTypeName` members are design, tasks, implement, dispatch, compact, summary, review, each, fan_out, loop, devlog, and gate). The phase step (`design:`, `tasks:`, `implement:`) gains an optional `plan:` key. When it's present, `PhaseStepType.expand()` emits `cf-op set_arch` first. Initiative switching then sits beside the slice and phase setting the phase step already does, with no new step type.
  - It runs once per item. It's idempotent and costs a few cf calls, which is small next to a dispatch.
  - The loop's review, later in the same item, resolves against the plan the design step set.
- **Order fix.** `PhaseStepType.expand()` emits `set_phase` before `set_slice` today (phase.py:156-157). This slice flips it to `set_arch` (when `plan:` is present) → `set_slice` → `set_phase` → `build_context`, and updates the exact-equality `expand()` tests to match. This applies to every phase step, not just batch pipelines.
- It's a state change like the `set_phase` and `set_slice` P4 already performs.
- **Rejected: requiring the plan to already be active.** It makes `plan` a redundant assertion, and it's a manual step in an unattended flow.
- **Rejected: a new `cf-op` step type.** It adds a step type for one operation, which the phase step can carry.

### D3: One step router

`execute_pipeline`'s type branch (`each` / `fan_out` / `loop` / loop sub-field / once, executor.py:680-792) is extracted to `_execute_step(step, resolved_config, …) -> StepResult`. The top level, `_execute_each_step`, and `_execute_loop_body` all call it.

- This fixes a latent silent no-op. Today a `loop:` inside `each` goes to `_execute_step_once`, whose `LoopStepType.expand()` returns `[]`. The step "completes" with zero actions.
- Nesting stays governed by validation, not by the router:
  - `loop:` inside `loop:` is banned (existing, 194).
  - `each` inside `each` is banned (new).
  - `each` inside a `loop:` body is banned (new, in `LoopStepType._validate_inner_steps`).

### D4: Per-item isolation in `each`

Per item, `_execute_each_step` builds `item_prior = dict(prior_outputs)` and `item_step_outputs = dict(step_outputs)`. It accumulates the item's inner-step results into both, using the same keying `_execute_loop_body` uses, and discards both when the item ends. The run-wide `prior_outputs` and `step_outputs` never receive item results. This matches the loop body's isolation of rounds from each other.

### D5: `each` failure policy and pre-flagged items

- `on_item_failure`: an `ItemFailurePolicy` StrEnum with `STOP` (default, today's behavior) and `CONTINUE`.
- Under `CONTINUE`:
  - An inner step returning `FAILED` ends that item. It's recorded as FLAGGED, using the step's `error`, or else the first failed action's `error`, or else `"step {name} failed"`. The next item starts.
  - The `each` step completes with status COMPLETED, and the report carries the flags.
- `PAUSED` stops the run under both policies. A pause is a human's Exit at a checkpoint, and resume depends on it. Batch pipelines use `checkpoint: never`, so they don't pause.
- An item carrying `flag_reason` is recorded as FLAGGED with that reason, and its body is not run, under both policies. It's a failed precondition, not an execution failure.

### D6: Loop additions

- **`accept_if: <LoopCondition>`** (optional). When the loop runs out of rounds, if `accept_if` is met by the final round's results, the step is COMPLETED with `StepResult.accepted = True`. Otherwise `on_exhaust` applies as today. Validation rejects `accept_if` without `until`.
- **`skip_if_met: true`** (optional, default false). Before round 1, `until` is evaluated against `prior_outputs` in insertion order (the item scope's results so far). If it's met, the step completes with `iteration=0` and no rounds. This lets the design step's own review settle a slice without a wasted revise round. Validation rejects `skip_if_met` without `until`.
- **Param-sourced values.** Placeholders resolve to strings, so `_parse_loop_config` accepts `max` as an int or a decimal digit string. `LoopStepType.validate` skips `max`/`until`/`accept_if` values that contain `{`, the same convention `_validate_model_alias` uses. `_parse_loop_config` validates the resolved values when the step runs, and its existing `ValueError` names the field.
- `StepResult` gains `accepted: bool = False`.

### D7: One threshold vocabulary

Thresholds are the existing `LoopCondition` values: `review.pass` and `review.concerns_or_better`. A new `LoopCondition.met_by_verdict(verdict: str) -> bool` is the single definition of the verdict sets. `evaluate_condition` and `cf.untasked_slices` both call it. `action.success` has no verdict meaning, so `met_by_verdict` raises `ValueError` for it, and the source rejects it as a threshold.

- **Rejected: bare `PASS` / `CONCERNS` spellings.** They would be a second spelling of the same thresholds.

### D8: `dispatch: { feedback: review }`

- A new `DispatchFeedback` StrEnum with one member, `REVIEW`. When `feedback: review` is set, the dispatch prompt is the step's `prompt` (if any), followed by a findings block built from the most recent in-scope `review` result. That's the existing `_resolve_prompt_from_prior_review` body, which gets reused, not duplicated.
- The block names the reviewed file from the review's new `outputs["input_file"]`: "Revise `{input_file}` in place; do not create a new file."
- With no in-scope review result, the action fails: `"feedback: review but no prior review in scope"`.
- This option is needed because, without a `prompt`, `_resolve_prompt` prefers the most recent `build_context` output over a review. Inside an item scope, that's the design step's original "create a design" prompt, so the revise round would redesign from scratch.
- A clean PASS with no findings never reaches a revise round, because `until` has already been met. The existing "no actionable findings" text stays for the other callers.

### D9: Batch report

Lives in `batch_report.py`.

- `ItemOutcome` StrEnum: `PASSED`, `ACCEPTED`, `FLAGGED`.
- `BatchItemRecord`: `index`, `name`, `outcome`, `reason: str | None`, `final_verdict: str | None`, `review_file: str | None`.
  - `index` and `name` come from the item's `index` and `name` keys. An item without them is labeled by its position.
  - `final_verdict` and `review_file` come from the last verdict-bearing result and the last `review_file` output in the item's results.
- **Outcome:**
  - A `flag_reason`, a FAILED status, or a PAUSED status → FLAGGED.
  - Otherwise, if any of the item's step results has `accepted` set → ACCEPTED.
  - Otherwise → PASSED.
- **The file** is `{runs_dir}/{run_id}.{step_name}.report.md`. It has YAML frontmatter (`docType: batch-report`, `pipeline`, `runId`, `plan` when the source had one, `passed`, `accepted`, `flagged`), then three sections. Flagged items come first, each with its reason and review file.
- **stdout:** `StepResult` gains `batch_report: BatchReport | None`. `sq run` prints one line of counts, the flagged items, and the report path after the run.
- Every `each` step produces a report, including `app.yaml`'s. That's one behavior with no opt-in flag.

### D10: Commits

The design (or tasks) step commits its own round via the phase step's existing commit. The loop sets `commit_each_iteration: true`, so every revise round commits design plus review. Flagged slices' artifacts are committed as well, since they're what the PM reads. The batch commits on the current branch. Planning work belongs on the integration target (project git rules), and the operator runs the batch there. The batch never creates or switches branches.

### D11: Pipelines

`design-plan.yaml`:

```yaml
name: design-plan
description: Design and review every undesigned slice in a plan; flag failures, report at end

params:
  plan: required
  model: sonnet
  review-model: minimax
  max-tries: 3
  pass-threshold: review.pass
  accept-threshold: review.concerns_or_better

steps:
  - each:
      name: slices
      source: cf.undesigned_slices("{plan}")
      as: slice
      on_item_failure: continue
      steps:
        - design:
            phase: 4
            plan: "{plan}"
            slice: "{slice.index}"
            model: "{model}"
            review: { template: slice, model: "{review-model}" }
            checkpoint: never
        - loop:
            max: "{max-tries}"
            until: "{pass-threshold}"
            accept_if: "{accept-threshold}"
            skip_if_met: true
            commit_each_iteration: true
            steps:
              - dispatch: { name: revise, model: "{model}", feedback: review }
              - review: { template: slice, model: "{review-model}", slice: "{slice.index}" }
```

- The model defaults match P4 and P5 (`sonnet` / `minimax`). This fixes #136 item 2, where `design-batch` declared `model: opus` and never passed it.
- `tasks-plan.yaml` is the same file with three changes: the source is `cf.untasked_slices("{plan}", "{accept-threshold}")`, the step is `tasks:` with `phase: 5`, and both review templates are `tasks`.
- `design-batch.yaml` is deleted, and its references are updated: `tests/pipeline/test_loader.py:108`, `tests/pipeline/test_loader_integration.py:16,77`, and `docs/PIPELINES.md:662`. Two near-duplicate pipelines don't ship.

### D12: Issue #139, review traceability

- **Run id.**
  - `ReviewResult.run_id: str | None = None`. The review action sets it from `ActionContext.run_id`, and the CLI leaves it `None`.
  - Frontmatter: `runId` only when set.
  - JSON: `run_id` always present, `null` on the CLI.
- **Squadron version.**
  - Frontmatter: `squadronVersion` on every artifact, including provider-failure artifacts.
  - JSON: `squadron_version` always present.
  - `_review_frontmatter_lines` takes it as a parameter, defaulting to `squadron.__version__` at the call sites. Snapshot tests (`clean_pass_artifact.md`) pass a fixed value so a version bump doesn't break them. The fixture is regenerated once for the new key.
- **Provider failure.** `format_provider_failure_markdown` adds `providerFailure: true` to the frontmatter. Other artifacts omit the key.
- **Pure JSON stdout.** In `_save_and_report` ([review.py:396](../../../src/squadron/cli/commands/review.py#L396)), "Saved review to {path}" prints to stderr when `--output json`, and to stdout otherwise, as today.
- **`to_dict()` gaps.** `structured_findings[].location_verified` is added, and so is `finding_scan`: the `FindingScanCounts` fields as an object, `null` when absent.
- **Key placement in frontmatter:** `providerFailure` directly after `verdict`, then `runId` and `squadronVersion` at the end of the block, after `diffTruncated`.

### Patterns and Conventions

- Every new comparison value is a StrEnum: `CfSliceStatus`, `ItemFailurePolicy`, `ItemOutcome`, `DispatchFeedback`, and `CfOperation.SET_ARCH`. Nothing branches on display strings.
- Every new failure is observable. A flagged item logs at WARNING with its reason and appears in the report. A source failure (cf error, bad plan argument) fails the step with the cf error text. A `set_arch` on a plan without `parent:` fails, and the error names the file.
- Placeholder tolerance in validation follows the existing `_validate_model_alias` convention: skip at load time if the value contains `{`, and validate at run time.

## Implementation Details

### API Contracts

Source call signatures (YAML):

```
cf.undesigned_slices("<arch index>")
cf.untasked_slices("<arch index>", "<LoopCondition value>")
cf.unfinished_slices("<arch index>")
```

Source item shape (dict, bound to the `as:` name):

```
{index: "923", name: "…", status: "not_started", design_file: "" | "path", flag_reason?: "…"}
```

`each` config: `source`, `as`, `steps`, and the optional `on_item_failure: stop | continue`.

`loop:` config: `max`, `until`, `on_exhaust`, `strategy`, `commit_each_iteration`, plus the optional `accept_if` and `skip_if_met`.

`dispatch` config: the optional `feedback: review`.

Report file (abridged):

```markdown
---
docType: batch-report
pipeline: design-plan
runId: 3f9c2a1b7d10
plan: "900"
passed: 2
accepted: 1
flagged: 1
---

# Batch report: design-plan (plan 900)

## Flagged for PM
- 929 Codex parity … — loop exhausted at FAIL (accept: review.concerns_or_better); review: project-documents/user/reviews/929-review.slice.….md

## Accepted at CONCERNS
- 924 …

## Passed
- 923 …
- 928 …
```

## Integration Points

### Provides to Other Slices

- `loop:` inside `each`, per-item isolation, `on_item_failure: continue`, and the batch report. These are the building blocks a future Phase 6 batch or any per-item pipeline composes.
- `accept_if`, `skip_if_met`, and `feedback: review` are usable by any loop, including `judge-cycle` and `findings-addressed-cycle`.
- The 184 convergence strategies plug into the same `loop:` config and aren't affected.
- Review artifacts carry `runId`, `squadronVersion`, and `providerFailure` for Amoeba ingestion (#139).

### Consumes from Other Slices

- A review's verdict and findings via `ActionResult` (existing contract).
- 909's post-condition failure for a design/tasks dispatch that writes nothing. It surfaces as a FAILED design step and becomes a FLAGGED item.
- If cf is unavailable, the source raises `ContextForgeNotAvailable`, and the `each` step fails with that message. There's no per-item fallback, because nothing can be selected.

## Success Criteria

### Functional Requirements

1. `cf.undesigned_slices("900")` returns 923, 924, 928, and 929 on today's 900 plan. It excludes 907 (deferred) and 914 (designed).
2. `cf.untasked_slices("900", "review.concerns_or_better")` returns 914 with `flag_reason: "no design review found"`, and nothing else, on today's 900 plan.
3. `cf.unfinished_slices("900")` reads plan 900 while the active plan is 180.
4. `set_arch` leaves `cf get` reporting `fileArch` from the plan's `parent:` and `fileSlicePlan` for the requested plan. A phase step's expanded actions run in the order `set_arch` → `set_slice` → `set_phase` → `build_context`.
5. A `loop:` inside `each` runs its rounds. The pre-slice behavior (zero actions, COMPLETED) is pinned as fixed by a test.
6. With `on_item_failure: continue`:
   - A FAILED item is recorded as FLAGGED, and the next item runs.
   - A PAUSED item stops the run.
   - With `stop` (default), today's behavior is unchanged.
7. Item N+1's revise dispatch never sees item N's review. Tested with two items whose reviews carry distinct findings.
8. Loop outcomes:
   - `skip_if_met` with a passing pre-loop review → the loop runs 0 rounds.
   - `accept_if` met on exhaust → COMPLETED with `accepted`.
   - `accept_if` not met → `on_exhaust` applies.
9. `feedback: review` prompts contain the prior review's findings and its `input_file`. Without a prior review in scope, the dispatch fails with the stated message.
10. Every `each` step writes `{run_id}.{step_name}.report.md` with the counts in frontmatter, and `sq run` prints the summary and path.
11. `design-batch` is gone, and `design-plan` and `tasks-plan` load and pass `sq run --validate`.
12. Issue #139:
    - Pipeline reviews have `runId`, and CLI reviews don't.
    - All reviews have `squadronVersion`.
    - Provider-failure artifacts have `providerFailure: true`.
    - `sq review … --output json | python -m json.tool` succeeds.
    - `to_dict()` has `run_id`, `squadron_version`, `location_verified`, and `finding_scan`.

### Technical Requirements

- `ruff format`, `ruff check`, and `pyright` are clean with zero errors. The full test suite passes.
- New modules (`sources.py`, `batch_report.py`) stay near ~300 lines. `executor.py` does not grow on net: the router extraction and the move of the source registry offset the additions.
- Test fixtures for the sources use real `cf list slices --json` and `cf list tasks --json` output shapes, including `designFile: null` and `status: deferred`. A design-review fixture uses a real review artifact's frontmatter.

### Integration Requirements

- `app.yaml`, P4, P5, `judge-cycle`, `findings-addressed-cycle`, and `test-loop` load and validate unchanged.
- The CLI and pipeline review paths write identical frontmatter apart from `runId`.

### Verification Walkthrough

Run from a terminal, not inside Claude Code (#144). Use `uv run sq` so the local code runs. Expected values reflect the 900 plan on 20260926. Re-read `cf list slices 900 --json` before running, because the plan changes.

1. **The pipelines load.**
   ```bash
   uv run sq run design-plan --validate
   uv run sq run tasks-plan --validate
   uv run sq run --list          # design-plan and tasks-plan listed; design-batch absent
   ```

2. **Selection matches the plan.** Cross-check what the batch should pick:
   ```bash
   cf list slices 900 --json | jq -r '.entries[] | select(.status!="complete" and .status!="deferred" and .designFile==null) | .index'
   # expect: 923 924 928 929
   ```

3. **The design batch runs over a non-active plan.** With the active plan set to 180:
   ```bash
   cf get --json | jq -r .fileSlicePlan        # 180-slices.pipeline-intelligence
   uv run sq run design-plan 900 -p max-tries=2 -v
   cf get --json | jq -r '.fileSlicePlan, .fileArch'
   # 900-slices.maintenance-and-refactoring / 900-arch.maintenance-and-refactoring
   ```
   - Expect one design file per selected slice under `project-documents/user/slices/`.
   - Expect a slice review under `project-documents/user/reviews/` for each slice.
   - Expect one commit per design step, plus one per revise round (`git log --oneline`).

4. **Read the report.**
   ```bash
   ls ~/.config/squadron/runs/*.slices.report.md | tail -1
   ```
   - The frontmatter counts add up to 4.
   - Every flagged item names a reason and a review file.
   - stdout ended with the same counts and the path.

5. **A failure doesn't stop the batch.** Force one: run with `-p review-model=<an alias whose provider has no credit>` (the `openai` profile returned `insufficient_quota` during the 927 walkthrough). Every item is FLAGGED with the provider error as its reason, and the run completes with status COMPLETED. Restore normal models afterwards.

6. **Rerunning picks only what's left.** Rerun step 3. Slices designed in step 3 are not selected. The report lists only the remainder, or reports zero items.

7. **The tasks batch chains safely.**
   ```bash
   uv run sq run tasks-plan 900 -v
   ```
   - 914 (designed, no design review) is FLAGGED with "no design review found", and its body doesn't run.
   - Slices designed in step 3 whose review met CONCERNS or better get a task file and a tasks review.
   - A slice flagged in step 3 for a verdict below threshold is FLAGGED here with "design review below threshold".

8. **Issue #139.**
   ```bash
   head -20 project-documents/user/reviews/923-review.slice.*.md   # runId, squadronVersion present
   uv run sq review slice 923 --output json | python -m json.tool >/dev/null && echo pure-json
   uv run sq review slice 923 --output json | jq '.run_id, .squadron_version, .finding_scan'
   # null, "<version>", {…}
   ```
   A provider-failure artifact from step 5 carries `providerFailure: true` in its frontmatter.

9. **Restore cf state** if needed: `cf set arch 180-arch.pipeline-intelligence`, then `cf set slice` and `cf set phase` back to their prior values.

## Risk Assessment

### Technical Risks

- **Router extraction touches every step path.** `_execute_step` replaces the dispatch branch that every pipeline goes through.
- **Unattended cost.** A batch over a large plan with `max-tries: 3` can run many design and review calls with no human watching.

### Mitigation Strategies

- **Router:** extract it first, as a pure refactor commit with no behavior change, and gate it on the full existing suite before any feature work lands on top.
- **Cost:** `max-tries` is a param with a small default (3), visible in the pipeline file and overridable with `-p`. The report is written even when every item flags. Selection by artifact presence means a stopped run doesn't redo finished slices.

## Implementation Notes

### Development Approach

Each part is its own commit, so any one of them can be reverted:

1. **Router extraction.** `_execute_step` is extracted, with top-level, `each`, and `loop` bodies routed through it. Refactor only, and the full suite stays green.
2. **Source module.** Move the registry to `sources.py`. Add `list_slices(plan)` and `list_tasks(plan)`. Fix `unfinished_slices`. Add `undesigned_slices`, `untasked_slices`, and `LoopCondition.met_by_verdict`.
3. **`set_arch` cf-op,** plus the phase step's `plan:` key and the arch → slice → phase order fix.
4. **`each` changes:** inner-step validation, nested-each ban, per-item isolation, `on_item_failure`, `flag_reason`, and the pinning test for the old loop-in-each no-op.
5. **Loop options:** `accept_if`, `skip_if_met`, param-sourced values, and `StepResult.accepted`.
6. **`feedback: review`** and the review action's `input_file` output.
7. **Batch report,** plus the `sq run` summary.
8. **Pipelines:** `design-plan.yaml` and `tasks-plan.yaml`. Delete `design-batch.yaml` and update its references.
9. **Issue #139,** as independent commits. It touches only the review package and the review CLI.
10. **Docs:** `docs/PIPELINES.md`, CHANGELOG, DEVLOG.

Testing strategy:

- Executor behavior is tested with the existing fake action registry (`_action_registry`), so no model calls are needed. That covers isolation, failure policy, loop options, the router, and the report.
- Sources are tested against a stub `ContextForgeClient` that returns real cf JSON shapes.
- Issue #139 is tested through the existing persistence and CLI format tests.
- The only live verification is the walkthrough.

### Special Considerations

- **Follow-up issue.** `--prompt-only` doesn't render `each` or `loop:` steps. This is logged as #145 and is out of scope here.
- **Branch.** Implementation happens on `195-slice.plan-batch-pipelines-design-and-tasks-over-a-whole-slice-plan`, forked from and merged back into the integration target (currently `main`). Batch *runs* commit planning artifacts to whatever branch is checked out. The operator runs them on the target.
