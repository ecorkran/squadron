---
docType: slice-design
slice: loop-step-type-for-multi-step-bodies
project: squadron
parent: user/architecture/180-slices.pipeline-intelligence.md
dependencies: [149]
interfaces: [184, 189]
dateCreated: 20260424
dateUpdated: 20260425
status: complete
---

# Slice Design: Loop Step Type for Multi-Step Bodies

## Overview

Adds a top-level `loop:` step type whose body is a list of inner steps. The
executor re-runs the inner sequence per iteration, evaluating the existing
closed-grammar `until` condition against the iteration's aggregated action
results. This is the multi-step counterpart to the `loop:` sub-field that
already exists on individual steps.

The shape mirrors `each:` — control-flow step type with a `steps:` body,
`expand()` returning empty, executor handling the iteration directly via its
own branch. All loop semantics (`max`, `until`, `on_exhaust`, exhaustion
behavior, checkpoint-stops-loop) are reused unchanged from the existing
`_execute_loop_step` path.

## Value

- **Closes the work-then-review convergence pattern.** Today, looping
  `dispatch:` then `review:` as siblings until the review passes is impossible
  unless both happen to be wrapped inside one phase step (which auto-appends a
  review when its `review:` sub-field is set). For arbitrary work-and-review
  pairs — including `compact:` + `summary: restore: true` triplets, and any
  custom action sequence — the single-step `loop:` sub-field cannot express
  the body.
- **Prerequisite for slice 184.** Weighted-decay convergence is most useful
  when the loop can re-dispatch the *artifact-producing* step on each
  iteration, not just re-ask a review. 184's `ConvergenceStrategy` plugs into
  the same loop machinery that 194 extends to multi-step bodies; without 194,
  184 can only drive single-step loops.
- **No new loop semantics.** This slice does not invent new conditions,
  decay, escalation, or cross-iteration memory. It only generalizes the body
  from "one step" to "a list of steps." That keeps the surface area small and
  defers all judgment-based behavior to 183/184.

## Technical Scope

### Included

- `LoopStepType` — new step type registered as `loop`
- `StepTypeName.LOOP` enum member
- `_execute_loop_body` — executor branch alongside `_execute_each_step` and
  `_execute_fan_out_step`; reuses existing `LoopConfig`, `LoopCondition`,
  `evaluate_condition`, `ExhaustBehavior`
- Validation rules:
  - `max:` required
  - `steps:` required, non-empty list
  - `until:`, `on_exhaust:`, `strategy:` optional, parsed via existing
    `_parse_loop_config`
  - **Nested-loop ban (v1):** validation rejects (a) any inner step that
    carries its own `loop:` sub-field, and (b) any inner step whose
    `step_type` is `loop`
- Registration wiring in `executor.py` (new branch in the step-type dispatch
  block)
- Unit tests for the step type's `validate()` and `expand()` returning empty
- Integration tests against the executor:
  - passes after iteration 1 when `until` is met immediately
  - retries to PASS on iteration N
  - exhausts to each `on_exhaust` mode (`fail`, `checkpoint`, `skip`)
  - inner action failure rolls to next iteration (transient-failure rule
    inherited from existing single-step loop)
  - checkpoint pause inside the body stops the loop
  - validation rejects nested `loop:` sub-field on inner steps
  - validation rejects nested `loop:` step type inside the body
- Authoring example added to `example.yaml` showing the dispatch-then-review
  convergence pattern

### Excluded

- Convergence strategies (`weighted-decay`, `strict`) — slice 184
- Cross-iteration findings memory — slice 183
- Conditional inner-step execution (`when:` clauses) — not in this initiative
- Non-looping `group:` / `block:` step type — explicitly out of scope; if a
  pure grouping construct is wanted later it gets its own slice
- Changes to the existing single-step `loop:` sub-field — unchanged
- Changes to the inline `review:` sub-field on phase steps — unchanged; stays
  as phase-only sugar

## Technical Decisions

### `loop:` is a step type, not a wrapper around an existing one

The alternative considered was a `group:` step type that takes a `loop:`
sub-field (`group: { loop: {...}, steps: [...] }`). Rejected because:

- It forces the word "loop" to appear twice for one concept.
- A non-looping `group:` has no purpose today — there's no `when:` clause, no
  shared params block, no devlog grouping requirement. YAGNI.
- `each:` already establishes the pattern of a control-flow step type owning
  its `steps:` body directly.

If a non-looping wrapper is ever needed, it gets a new step type then. The
two are not mutually exclusive.

### `loop:` as a step type does not collide with `loop:` as a sub-field

Step types are matched by the top-level key in a step dict. The single-step
sub-field form lives one level deeper inside another step's config. The
schema parser already disambiguates by position; no special-case logic is
needed.

```yaml
# Sub-field form — unchanged, single step body
- review:
    template: code
    loop:
      max: 3
      until: review.pass

# Step-type form — new in this slice, multi-step body
- loop:
    max: 3
    until: review.pass
    steps:
      - dispatch: { template: implement-task, model: sonnet }
      - review:   { template: code, model: opus }
```

### Nested-loop ban is enforced at validation, not at runtime

Both forbidden cases are detectable statically by walking the inner-steps
list:

1. Any inner step whose `config` dict contains a `loop:` key fails validation.
2. Any inner step whose `step_type` is `loop` fails validation.

Validation runs at pipeline load time (slice 148), so misuse fails before
any execution begins. The error message names the specific inner step and
the form of nesting that was rejected.

### Iteration semantics inherited unchanged from `_execute_loop_step`

- **`until` evaluation:** runs against the iteration's aggregated
  `action_results` (the concatenation of all inner-step action results in
  iteration order). `evaluate_condition` already accepts a list and walks it
  in reverse to find the latest verdict-bearing result, so multi-step bodies
  work with no change to the condition layer.
- **No-`until` behavior:** if `until` is omitted, the loop completes after
  iteration 1 (matches the existing single-step behavior).
- **Inner failure handling:** an inner step's `FAILED` status is treated as
  transient — the iteration completes, results are aggregated, and the loop
  continues to the next iteration unless `until` is satisfied or `max` is
  reached. This matches the existing single-step rule that "action failure
  is transient in loops." A `PAUSED` (checkpoint) result short-circuits the
  loop and propagates upward, also matching existing behavior.
- **Exhaustion:** identical handling to single-step loop — the latest
  iteration's `action_results` are returned with `FAILED`, `PAUSED`, or
  `SKIPPED` status per `on_exhaust`.

### State across iterations

Same as the existing single-step loop: each iteration sees `prior_outputs`
from before the loop step started. There is no cross-iteration memory in v1.
That is what 183 (Findings Ledger) adds, and 184 will plumb through the
`strategy:` field once the strategy registry is populated.

The `strategy:` field on the new step type is parsed via the existing
`_parse_loop_config` and currently produces the same warning as the
single-step form (`"strategy '%s' not implemented, falling back to basic
max-iteration loop"`). 184 will replace that warning with real behavior,
benefiting both forms simultaneously.

## Component Interactions

```
loader (148)            — accepts `loop:` as a valid top-level step type;
                          schema validator delegates to LoopStepType.validate()
LoopStepType            — validates config; expand() returns empty
executor (149)          — step-type dispatch routes `loop` to
                          _execute_loop_body
_execute_loop_body      — for iteration 1..max:
                            run inner_steps via _execute_step_once each
                            aggregate inner action_results into iteration list
                            check checkpoint pause → propagate
                            evaluate `until` → break on satisfied
                            else continue
                          on exhaust: branch on on_exhaust
LoopConfig / LoopCondition / ExhaustBehavior   — reused unchanged
evaluate_condition      — reused unchanged
```

## YAML Surface

```yaml
- loop:
    max: 4
    until: review.pass            # optional; one of LoopCondition values
    on_exhaust: checkpoint        # optional; default fail
    strategy: weighted-decay      # optional; stubbed until 184
    steps:
      - dispatch:
          template: implement-task
          model: sonnet
      - review:
          template: code
          model: opus
```

Closed grammar — same as single-step `loop:` sub-field:

| Field         | Type                | Required | Notes                                     |
|---------------|---------------------|----------|-------------------------------------------|
| `max`         | int                 | yes      | iteration cap                             |
| `until`       | `LoopCondition`     | no       | `review.pass`, `review.concerns_or_better`, `action.success` |
| `on_exhaust`  | `ExhaustBehavior`   | no       | default `fail`                            |
| `strategy`    | str                 | no       | stubbed; 184 implements                   |
| `steps`       | list of step dicts  | yes      | non-empty; nested-loop ban enforced       |

## Deferred Interactions with 184 / 185 / 188

Slices 184 (weighted-decay convergence), 185 (escalation), and 188
(within-step conversation persistence) are written against the implicit
mental model of a *single-step* loop body — one review step looping against
an unchanged artifact. None of those slices specifies behavior for the
multi-step body shape this slice introduces. To keep 194 strictly additive
and avoid silently re-scoping downstream slices, the cross-product
interactions are explicitly deferred:

- **Convergence strategies (184)** — when 184 lands, its strategies operate
  on the existing single-step `loop:` sub-field exactly as architected.
  Whether and how a strategy applies to a multi-step `loop:` step-type body
  (e.g. which inner step's findings drive the ledger, whether re-dispatching
  a work step resets ledger state) is a decision 184 will make. Until then,
  the `strategy:` field on a multi-step `loop:` body produces the same
  "strategy not implemented, falling back to basic max-iteration loop"
  warning the single-step form already produces. No new behavior, no silent
  divergence.
- **Escalation (185)** — escalation is defined on a single review action
  and re-dispatches that action's model. Applying escalation to a multi-step
  body raises the question "which inner step gets escalated?" 185 answers
  this for single-step loops only. Multi-step escalation semantics are out
  of scope here and will be settled when 185 reviews this slice's existence.
- **Conversation persistence (188)** — persistence preserves a single
  step's conversation across retries. In a multi-step body, persistence
  would need to specify whether each inner step persists independently or
  whether the body has a unified conversation. 188 will answer this when it
  is designed; 194 does not pre-decide.

The principle: 194 adds the multi-step body shape and the executor branch
to run it. It does not pre-commit downstream intelligence slices to any
particular interpretation of how their behaviors compose with multi-step
bodies. Those slices retain authority to define their own multi-step
semantics — or to limit themselves to single-step loops if that is the
right call at the time.

The existing single-step `loop:` sub-field is unchanged. Single-step
convergence loops behave exactly as they do today; 184/185/188 land into
that surface as their authors intended.

## Cross-Slice Dependencies and Interfaces

- **Depends on 149** (executor) for `LoopConfig`, `LoopCondition`,
  `evaluate_condition`, `ExhaustBehavior`, `_execute_step_once`,
  `_unpack_inner_steps`. All reused, no modifications.
- **Interfaces with 184** — the `strategy:` field is the same field 184 will
  populate. 184 needs the strategy registry to dispatch on the strategy name
  and consume/produce a ledger; both forms (sub-field and step-type) gain the
  capability simultaneously when 184 lands.
- **Interfaces with 183** — once 184 plumbs cross-iteration state through the
  `strategy:` hook, the multi-step loop body becomes the natural home for
  ledger-driven re-dispatch. No code in 194 anticipates this; the seam lives
  inside the strategy registry, not in the step type.
- **No interface change for 189** (ensemble review). Ensemble review uses
  fan-out, not loop. Listed as `interfaces` only because 189's convergence
  cycle could in principle wrap a fan-out inside a `loop:`; that is an
  authoring pattern, not a code dependency.

## Success Criteria

1. A pipeline using `- loop:` with a multi-step body parses, validates, and
   executes — re-running the inner sequence each iteration until `until` is
   satisfied or `max` is reached.
2. Validation rejects any inner step that carries its own `loop:` sub-field,
   with an error naming the offending step.
3. Validation rejects any inner step whose `step_type` is `loop`, with an
   error naming the offending step.
4. `on_exhaust: fail | checkpoint | skip` produce the same `StepResult`
   statuses (`FAILED`, `PAUSED`, `SKIPPED`) as the existing single-step
   loop's exhaustion paths.
5. A checkpoint pause inside the body stops the loop and propagates the
   `PAUSED` status upward immediately.
6. An inner action's `FAILED` status within an iteration does not abort the
   loop — the iteration's results aggregate and the loop continues to the
   next iteration (unless `until` is satisfied).
7. The existing single-step `loop:` sub-field continues to work unchanged;
   regression tests pass.
8. The example pipeline added to `example.yaml` demonstrates the
   dispatch-then-review convergence pattern and runs successfully against a
   trivial review template.

## Verification Walkthrough

After implementation, the user can prove the slice works as follows.

**Step 1 — sanity check the existing single-step loop is untouched.**

```bash
uv run pytest tests/pipeline/test_executor_loop.py -v
```

All existing single-step loop tests pass. (Regression gate.)

**Step 2 — author a minimal multi-step loop pipeline.**

Create `/tmp/test-loop.yaml`:

```yaml
name: test-loop
steps:
  - loop:
      max: 3
      until: review.pass
      on_exhaust: fail
      steps:
        - dispatch:
            template: implement-task
            model: sonnet
        - review:
            template: code
            model: opus
```

**Step 3 — run it in prompt-only mode.**

```bash
uv run sq run /tmp/test-loop.yaml --prompt-only --next
```

The first call returns instructions for the inner `dispatch` step. Subsequent
`--next` calls walk through `review`, then loop back to `dispatch` for
iteration 2 if the review verdict is not PASS, and so on.

**Step 4 — confirm the nested-loop ban.**

Create `/tmp/test-loop-bad.yaml` with a nested `loop:` sub-field:

```yaml
name: test-loop-bad
steps:
  - loop:
      max: 2
      steps:
        - review:
            template: code
            loop: { max: 2, until: review.pass }
```

```bash
uv run sq run /tmp/test-loop-bad.yaml --prompt-only --next
```

Loader rejects the pipeline at validation time with an error naming the
inner `review` step and identifying the nested-loop violation.

Repeat with a nested `loop:` *step type*:

```yaml
name: test-loop-bad-2
steps:
  - loop:
      max: 2
      steps:
        - loop:
            max: 2
            steps:
              - review: { template: code }
```

Same outcome — validation rejects with an error naming the inner `loop:`
step type.

**Step 5 — exhaustion behavior.**

Run the multi-step pipeline against a review template that always returns
CONCERNS. With `on_exhaust: fail`, the loop runs `max` iterations, then the
step's final `StepResult` has status `FAILED`. With `on_exhaust: checkpoint`,
status is `PAUSED`. With `on_exhaust: skip`, status is `SKIPPED` and the
pipeline continues to subsequent steps.

**Step 6 — checkpoint propagation.**

Place a checkpoint-inducing step in the body. Confirm the loop stops on the
first iteration that pauses, propagating `PAUSED` upward without consuming
remaining iterations.

## Risks

- **Loop body action-result aggregation order matters for `until` evaluation.**
  `evaluate_condition` walks results in reverse to find the latest verdict.
  In a multi-step body where review is the last step, this is the desired
  behavior. If a future authoring pattern places review *before* a follow-up
  step in the same iteration, the latest verdict would still be the review
  (no other step produces verdicts), so the rule holds. Documented but no
  code mitigation needed.

## Effort

2/5 — the executor's loop machinery, condition layer, and inner-step
unpacking are all reused unchanged. New surface is one step type, one
executor branch, validation rules for the nested-loop ban, and tests.

## Review Response — 20260424

Slice review at
`project-documents/user/reviews/194-review.slice.loop-step-type-for-multi-step-bodies.md`
returned verdict FAIL with three findings. Response by finding:

### F001 — REJECTED

Finding asserts that adding a top-level `loop:` step type, a
`StepTypeName.LOOP` enum member, and an `_execute_loop_body` executor branch
violate the architecture's "no 140 code is modified" and "changes to 140's
pipeline grammar are out of scope" principles.

Rejected on the basis of established precedent. Slice 182 (Fan-Out / Fan-In
Step Type) lives in the same 180 plan, ships a new top-level `fan_out` step
type, adds `StepTypeName.FAN_OUT`, adds `_execute_fan_out_step` as a new
executor branch, and wires registration into `executor.py` — and is shipped
as `status: complete`. The architecture text itself names it as the
ensemble-review enabler. If F001's reading were correct, slice 182 would be
a violation; it is not.

The architecture's "no 140 code is modified" line at
[180-arch.pipeline-intelligence.md:40](../architecture/180-arch.pipeline-intelligence.md)
follows a table of *configuration extensions* (pool prefixes, fields on
existing actions, persistence flags). In context, the rule means "180 does
not break 140's deterministic core or rewrite existing actions." Step-type
registration via the `register_step_type` registry that 140 establishes is
the same registry-mediated extension pattern the architecture's "register
new strategies, new resolver backends, and new action behaviors through the
registries 140 establishes" sentence describes — applied to the step-type
registry instead of the strategy registry.

The architecture's "Out of Scope: Changes to 140's pipeline grammar" line
parenthetically narrows itself to "(only registration of new
strategies/behaviors)." Step-type registration is registration, not core
grammar surgery — same as fan-out.

A separate doc-only finding could reasonably be filed against the
architecture text to make explicit that step-type registration through the
existing registry is a permitted 180-band extension. That is an
architecture-document refinement, not a slice fault.

### F002 — ACCEPTED

Finding correctly identifies that slices 184, 185, and 188 are written
against an implicit single-step loop body model and that introducing a
multi-step body raises real questions about how those downstream behaviors
compose. The finding overstates the architecture's specification (the
architecture is silent on body shape; the single-step assumption is
implicit in examples, not stated as constraint), but the substance of the
concern stands.

Addressed by adding a "Deferred Interactions with 184 / 185 / 188" section
to this slice. The section makes explicit that 184/185/188 retain authority
to define their own semantics for multi-step bodies — or to limit themselves
to single-step loops — and that 194 does not pre-commit any of them. The
existing single-step `loop:` sub-field is unchanged, so single-step
convergence loops behave exactly as those slices' authors intend.

### F003 — ACKNOWLEDGED

PASS finding noted; no action required.
