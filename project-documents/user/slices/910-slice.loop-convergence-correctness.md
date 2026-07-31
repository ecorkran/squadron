---
docType: slice-design
slice: loop-convergence-correctness
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [911]
dateCreated: 20260731
dateUpdated: 20260731
status: not_started
---

# Slice Design: Loop Convergence Correctness

## Overview

Three defects on the multi-step `loop:` execution path, fixing [issue #42](https://github.com/ecorkran/squadron/issues/42),
[issue #43](https://github.com/ecorkran/squadron/issues/43), and
[issue #45](https://github.com/ecorkran/squadron/issues/45). Bundled into one
slice because Parts A and B share a single function
(`_execute_loop_body`, [executor.py:1249-1360](src/squadron/pipeline/executor.py#L1249-L1360))
and one test file (`tests/pipeline/test_executor_loop_body.py`). Together, #42
and #43 make "the loop fixes the findings and re-reviews" false for any
pipeline using `loop:` today — the mechanism runs the right number of times
but does not converge.

Each part is small because the machinery it needs already exists elsewhere in
the codebase; this slice is wiring, not new architecture.

[Issue #44](https://github.com/ecorkran/squadron/issues/44) was scoped into
this slice initially and split out to slice 911 (Loop Iteration Versioning and
Review Evidence), which is sequenced immediately after this one.

## Value

Developer-facing correctness for the pipeline's primary quality-gate
construct. A `loop:` step is squadron's only built-in mechanism for "keep
retrying until a review passes" — every design-until-pass or
implement-until-code-review-passes pattern depends on it. Right now that
pattern silently doesn't work: each retry re-sends an identical prompt (Part
A), and a loop body with more than one review can report success while a real
failure is buried inside it (Part B). Fixing both makes `loop:` do what its
own documentation and the `until:` grammar already promise. Part C is a
smaller but related trust gap: `--dry-run` is supposed to let a user preview
execution before spending model calls, and today it hides the single most
consequential and expensive-to-get-wrong construct in the pipeline grammar.

## Technical Scope

**Included:**
- Part A: thread each iteration's own action results into the `prior_outputs`
  seen by the *next* iteration's actions, so `DispatchAction`'s
  findings-feedback path actually receives them.
- Part B: validation-time rejection of a loop body that contains more than one
  verdict-bearing action when `until:` is set.
- Part C: `--dry-run` output expands a `loop:` step's body, `max`, `until`,
  and `on_exhaust`.

**Excluded:**
- Any change to `evaluate_condition` / `LoopCondition` semantics — Part B
  makes the ambiguous case a validation error instead of resolving it, so the
  runtime condition-evaluation logic is untouched.
- The `on_exhaust: skip` gap noted below (deferred, out of scope for all three
  parts — see Known Issue).
- Loop strategies (`strategy:` field) — already a documented no-op
  (`_execute_loop_body` warns and falls back to max-iteration looping); not
  touched here.
- Everything in slice 911 (commits between iterations, artifact versioning,
  review-evidence carryforward) — that slice assumes this one is done.

## Target Loop Shape (context for Parts A and B)

These fixes assume — and Part B enforces — **one dispatch plus one review per
loop body**, with sequential loops used for multi-phase work. The motivating
shape is an app-creation pipeline: concept, then architecture review until
pass, then per-slice `design → review until pass`, `task breakdown → review
until pass`, `implementation → code review until pass`. Every loop in that
sketch is one-dispatch-one-review, which is what makes
`DispatchAction._resolve_prompt_from_prior_review`'s "most recent REVIEW
action in `prior_outputs`" lookup unambiguous — there is only ever one review
to find.

The existing pipeline `p45b.yaml` already uses this two-loop-sequence pattern.
It was arrived at by splitting an earlier single-loop design to work around
the #43 ambiguity, and the split is treated here as the recommended shape, not
a workaround forced by a bug — an all-verdicts-must-pass alternative was
considered for Part B and rejected (see Part B below).

## Known Issue — Deferred, Out of Scope

**`on_exhaust: skip` does not stop the pipeline run.** Verified during scoping
(20260731): the pipeline run loop returns early on `ExecutionStatus.FAILED`
([executor.py:881](src/squadron/pipeline/executor.py#L881)) and on `PAUSED`
([executor.py:873](src/squadron/pipeline/executor.py#L873)), so `on_exhaust:
fail` and `on_exhaust: checkpoint` both correctly block the next phase from
running against a failed one. `on_exhaust: skip` returns `SKIPPED`
(`_loop_exhaust_result`), and `ExecutionStatus.SKIPPED` appears nowhere in the
run loop's early-return checks — execution falls through and the next phase
runs regardless. This is latent, not active: no shipped pipeline uses `skip`
today (`judge-cycle.yaml` uses `checkpoint`, `test-loop.yaml` uses `fail`),
and the target loop shape above works correctly as long as each loop uses
`fail` or `checkpoint`.

None of the three parts below change this behavior. It is recorded here as an
explicit deferred decision: `skip` currently has no way to distinguish "this
phase was optional, keep going" from "this phase failed and everything
downstream is now meaningless," and the mode name doesn't warn a pipeline
author about the gap. Resolve later as a guard (block downstream phases
regardless), a rename (clarify the mode does not mean "safe to ignore"), or
documented intent (require an explicit acknowledgment in the pipeline YAML).

## Part A — Findings Feedback Between Iterations (#42)

### Problem

`_execute_loop_body` ([executor.py:1298-1321](src/squadron/pipeline/executor.py#L1298-L1321))
passes the *outer* `prior_outputs` parameter — captured once at loop entry —
into every `_execute_step_once` call across every iteration, and never
updates it. `iteration_action_results` is reset to `[]` at the top of each
round (line 1299) and only used for the `until:` check; it is discarded
before the next iteration starts. Iteration N+1 therefore builds its
`ActionContext` from exactly the same `prior_outputs` iteration 1 saw — the
loop re-runs an identical prompt every round rather than converging toward a
passing review.

The consumer that should receive this is already correct and already
shipped: `DispatchAction._resolve_prompt_from_prior_review`
([dispatch.py:258-291](src/squadron/pipeline/actions/dispatch.py#L258-L291))
walks `context.prior_outputs` in reverse, finds the most recent `REVIEW`
result, formats its findings into a "fix these" prompt, and even handles the
empty-findings case (a clean prior pass gets a generic "do an initial
improvement pass" prompt instead of an empty list). This method is simply
never fed real iteration data — it only ever sees whatever was in
`prior_outputs` before the loop began.

### Fix

Accumulate each iteration's results into a per-iteration copy of
`prior_outputs`, and pass that copy into the next iteration instead of the
original.

```python
# _execute_loop_body, sketch — not final implementation
running_prior = dict(prior_outputs)  # snapshot at loop entry

for iteration in range(1, loop_config.max + 1):
    iteration_action_results = []

    for inner_step in inner_steps:
        inner_result = await _execute_step_once(
            ...,
            prior_outputs=running_prior,
            ...,
        )
        iteration_action_results.extend(inner_result.action_results)
        for idx, result in enumerate(inner_result.action_results):
            running_prior[f"{inner_step.step_type}-{iteration}-{idx}"] = result
        ...
```

This mirrors the existing `step_prior = dict(prior_outputs)` snapshot pattern
already used one level down inside `_execute_step_once`
([executor.py:1030](src/squadron/pipeline/executor.py#L1030)) — same idea,
applied at the loop-iteration level instead of the action level.

**Key naming.** `step_prior` inside `_execute_step_once` keys results as
`f"{action_type}-{action_index}"` — stable only within one step's action
list. A per-iteration accumulation needs keys that stay unique across
iterations too (an iteration-1 `review-0` and an iteration-2 `review-0` must
not collide and silently overwrite each other, since `_resolve_prompt_from_
prior_review` walks in reverse and wants the *latest* one to win, not an
arbitrary one). Confirm during implementation whether the iteration number
needs to be folded into the key, or whether dict insertion order (Python
dicts preserve it) combined with `reversed()` is sufficient because a later
`review-0` write naturally overwrites the earlier one at the same key and
still lands last in iteration order. Recommend keeping the existing
`{action_type}-{action_index}` key (letting same-key overwrites happen) since
`_resolve_prompt_from_prior_review` only wants the most recent REVIEW, not a
full history — full history is slice 911's concern, not this one's.

**Verify during implementation** (flagged in the slice plan entry as the one
place effort could rise): how `step_outputs` — a second, separately-threaded
dict passed alongside `prior_outputs` into `_execute_step_once` — interacts
with this change. `step_outputs` is used by `GateAction` for `judge_from`/
`review_from` lookups scoped to the *whole step* (including loop-external
steps), not just within-loop iteration. Confirm this fix does not need to
touch `step_outputs` — the working assumption is that `step_outputs` already
receives fresh entries every call because callers pass a shared mutable dict
by reference (unlike `prior_outputs`, which is snapshotted), so it likely
requires no change. If that assumption is wrong, Part A's scope grows to
cover it.

### Effort: 1/5

## Part B — Ambiguous `until:` With Multiple Verdict-Bearing Actions (#43)

### Problem

`_last_with_verdict` ([executor.py:356-360](src/squadron/pipeline/executor.py#L356-L360))
walks a loop iteration's `action_results` **backward** and returns the first
result carrying a non-`None` `verdict`. `evaluate_condition` uses only this
one result to decide whether `until: review.pass` (or `review.concerns_or_
better`) is satisfied. If a loop body contains two verdict-bearing actions —
for example a `design` review followed later in the same body by a `tasks`
review — only the **last** one gates the loop. A body where the design review
FAILs but the tasks review PASSes exits the loop successfully, silently
discarding the design failure.

Two step types produce a verdict-bearing `ActionResult`: the `review` step
type ([review.py](src/squadron/pipeline/steps/review.py), and any step whose
`expand()` appends a `review` action from an inline `review:` sub-field, e.g.
`phase` steps ([phase.py:156-169](src/squadron/pipeline/steps/phase.py#L156-L169))
— and the `gate` step type ([gate.py](src/squadron/pipeline/actions/gate.py)),
which reduces a judge and/or review verdict to one composed verdict. A
correct count of "verdict-bearing actions in this loop body" must inspect
**expanded actions**, not step-type names at the YAML level — a loop body
with two `phase:` steps, each carrying an inline `review:`, is exactly the
ambiguous case even though neither inner step is literally type `review`.

### Fix: Reject the Ambiguity, Don't Resolve It

A loop body with more than one verdict-bearing action **and** an `until:`
condition set fails at validation time with an actionable message — it does
not run and silently pick one verdict.

**Alternative considered and rejected:** an all-verdicts-must-pass
composition (loop only exits when every verdict-bearing action in the body
passes). Rejected because it solves a problem that shouldn't exist for the
target loop shape: running task-breakdown against a design that already
failed its own review is wasted model spend, not a correctness gap to paper
over with a composite gate. The correct decomposition is one dispatch + one
review per loop, sequenced across multiple loops for multi-phase work — see
Target Loop Shape above. An all-must-pass gate would convert a silent wrong
answer into a correct-but-wasteful one; rejecting the shape outright is
strictly better for the shapes this codebase actually needs.

This means: **no change to `evaluate_condition` or `LoopCondition`.** Both
stay exactly as they are — correct for the single-verdict-per-body shape the
rejection above enforces.

### Where the Check Lives

`LoopStepType.validate()` ([loop.py:30-115](src/squadron/pipeline/steps/loop.py#L30-L115))
already validates `max`, `until`, `on_exhaust`, `strategy`, and inner-step
shape (including the existing nested-loop ban in `_validate_inner_steps`,
[loop.py:117-159](src/squadron/pipeline/steps/loop.py#L117-L159)). Add the
new check alongside the nested-loop ban, gated on `until_val is not None`:

1. Convert the raw `steps:` list to `StepConfig` objects via the existing
   `unpack_inner_steps` helper (already imported in `loop.py`).
2. For each inner `StepConfig`, look up its registered step type
   (`get_step_type`) and call `.expand(inner_step)` to get its action list —
   mirroring what `_execute_loop_body` does at runtime
   ([executor.py:1300-1302](src/squadron/pipeline/executor.py#L1300-L1302),
   which calls `resolve_placeholders` then relies on the step type's own
   `expand()` indirectly through `_execute_step_once`).
3. Count actions of type `"review"` or `"gate"` (the two verdict-producing
   action types, confirmed above) across the full expanded body.
4. If `until_val is not None` and the count is `> 1`, append a
   `ValidationError` naming the offending inner steps, with a message
   suggesting the fix: split into sequential loops, one review per loop.

**Note on validation-time expansion:** `expand()` for `dispatch`/`phase`-like
step types is expected to be side-effect-free (pure function of config to
action tuples) — confirm this holds for every step type reachable inside a
loop body before relying on calling `expand()` during validation. If any
inner step type's `expand()` is not pure, count verdict-bearing actions by
inspecting each inner step's raw config for `step_type == "review"` or a
truthy `review:` sub-field instead, without calling `expand()`.

### Sequencing

Land Part B before Part A. Its validation error establishes "one
verdict-bearing action per loop body" as an enforced invariant, which is the
shape Part A's tests should assert against — Part A's fix only needs to track
a single "most recent review" per loop, not reconcile multiple.

### Effort: 1/5

## Part C — `--dry-run` Does Not Expand Loop Bodies (#45)

### Problem

`sq run --dry-run` renders each step as one line:
`rprint(f"  {step.name} ({step.step_type})")`
([run.py:983](src/squadron/cli/commands/run.py#L983)). For a `loop:` step
this produces exactly `loop-0 (loop)` — no body steps, no `max`, no `until`,
no `on_exhaust`. `loop:` is the construct with the most surprising execution
shape (it can run its body up to `max` times) and the highest cost when
wrong (repeated dispatch calls against a real model), and it's the one
`--dry-run` describes least. Parsing is already correct — `--validate`
reports these pipelines valid — so this is a display-only gap.

### Fix

In the `--dry-run` rendering loop ([run.py:982-983](src/squadron/cli/commands/run.py#L982-L983)),
special-case `step.step_type == "loop"`:

- Print the loop step's own line as today.
- Print `max`, `until` (or "no until — completes after first iteration"), and
  `on_exhaust` from `step.config`.
- Expand and print each inner step on an indented line, in the same
  `name (step_type)` format used for top-level steps, via the existing
  `unpack_inner_steps` helper on `step.config.get("steps", [])`.

Example target output for a loop step with two inner steps:

```
  design-review-loop (loop)
    max: 3, until: review.pass, on_exhaust: checkpoint
    design (phase)
    review-design (review)
```

No new step-type-specific rendering abstraction — this is a single `if`
branch in the existing render loop, matching the minimal-machinery bar the
other two parts hold to. If a future slice needs the same
expand-and-indent behavior for `each`/`fan_out` dry-run output, that is a
generalization to consider then, not preemptively here.

### Effort: 1/5

## Dependencies

### Prerequisites
None.

### Interfaces Required
None — this slice touches only `executor.py`, `steps/loop.py`, and
`cli/commands/run.py`, all already in the codebase.

## Integration Points

### Provides to Other Slices
Slice 911 (Loop Iteration Versioning and Review Evidence) depends on this
slice's Part A: 911 needs a well-defined notion of "what one iteration
produced" to attach commits and version metadata to, which only exists once
findings actually flow between iterations.

### Consumes from Other Slices
None.

## Success Criteria

### Functional Requirements
- A `loop:` body of `dispatch → review` run for 2+ iterations against a
  failing review produces a **different** prompt on iteration 2 than
  iteration 1 — specifically, one that includes the iteration-1 review's
  findings (verified via a test double / fake provider capturing the actual
  prompt text sent, not just that `_resolve_prompt_from_prior_review`
  returns non-`None`).
- A loop body containing two verdict-bearing actions (e.g. two `review` steps,
  or a `phase` with inline `review:` followed by a bare `review` step) with
  `until:` set fails `sq run --validate` (and `--dry-run`, which validates
  first) with a message identifying both offending steps and suggesting the
  sequential-loop split.
- The same shape **without** `until:` set continues to validate successfully
  — the check is scoped to the ambiguous case only, not a general "one review
  per loop" ban.
- `sq run --dry-run` on a pipeline containing a `loop:` step prints the body's
  inner steps, `max`, `until`, and `on_exhaust` — verified against at least
  one real shipped pipeline using `loop:` (e.g. `p45b.yaml`).

### Technical Requirements
- No change to `evaluate_condition`, `LoopCondition`, or any existing
  passing test for single-verdict loop bodies.
- New/updated tests land in `tests/pipeline/test_executor_loop_body.py`
  (Part A), `tests/pipeline/test_loop_validation.py` and/or
  `tests/pipeline/steps/test_loop.py` (Part B), and a CLI-level test for
  `--dry-run` output (Part C) — following existing file organization rather
  than introducing new test files.
- Ruff and pyright clean on all touched files, per project standard.

### Verification Walkthrough

1. **Part A — findings actually feed back.**
   Run (or write a focused test around) a `loop:` pipeline with `max: 2` whose
   body is `dispatch → review`, where the review is rigged (via a fake/mock
   provider) to FAIL on iteration 1 with a specific finding and PASS on
   iteration 2. Capture the prompt text sent to the dispatch action on
   iteration 2 and confirm it contains the iteration-1 finding's summary text
   — proving the loop is now feeding results forward instead of re-sending an
   identical prompt.

2. **Part B — ambiguous loops rejected, unambiguous loops unaffected.**
   ```
   sq run --validate path/to/pipeline-with-two-reviews-and-until.yaml
   ```
   Expect a non-zero exit and a validation error naming both verdict-bearing
   steps. Then:
   ```
   sq run --validate p45b.yaml
   ```
   Expect success (0 exit) — `p45b.yaml` already uses the one-review-per-loop
   shape this slice's rejection enforces, so the existing pipeline must
   continue to validate cleanly.

3. **Part C — dry-run shows the loop body.**
   ```
   sq run --dry-run p45b.yaml
   ```
   Expect the `loop:` step(s) in the output to show `max`/`until`/
   `on_exhaust` and each inner step by name and type, not a single opaque
   `loop-N (loop)` line.

## Risk Assessment

### Technical Risks
- Part A: the `step_outputs` interaction noted above is the one place this
  slice's effort could rise past the current 1/5 estimate if the assumption
  that it's already shared-by-reference turns out to be wrong.
- Part B: if any step type's `expand()` used inside loop bodies turns out not
  to be side-effect-free, the validation-time approach needs to fall back to
  raw-config inspection (documented as the fallback above) rather than
  calling `expand()` directly.

### Mitigation Strategies
Both risks have a documented fallback already written into the relevant
Part's design above — implementation should confirm the primary approach
works before falling back, not assume the fallback is needed.

## Implementation Notes

### Development Approach
Sequence: **Part B, then Part A, then Part C.** Part B establishes the
one-verdict-per-loop-body invariant that Part A's tests assert against. Part
C is fully independent of both and can land in any order, including in
parallel with the others if convenient.

### Special Considerations
None beyond what's captured in Risk Assessment.
