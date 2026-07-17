---
docType: slice-design
slice: gate-composition
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [302]
interfaces: [140]
dateCreated: 20260716
dateUpdated: 20260717
reviewsAddressed: [304-review.slice.gate-composition]
status: complete
---

# Slice Design: Gate Composition

## Overview

This is the initiative's **integration slice**: it resolves and implements how a
**judge result** and a **standard review result** compose into a single
checkpoint gate. Slice 303 deliberately used a judge verdict *or* a review
verdict at a gate, never both together; this slice closes that gap.

The architecture (300) names this the one place the *Additive over migratory*
principle has a real edge, and it prescribes the decision procedure rather than
the answer:

- **Option (a) — compose upstream of the checkpoint.** Reduce judge + review
  into one verdict *before* the checkpoint sees it. Additive, within 300's
  scope, **preferred**.
- **Option (b) — extend the checkpoint to accept multiple verdicts.** A
  **140 change**, explicitly out of 300's additive scope, to be coordinated as
  a dependency, **not silently absorbed**.

> The slice must pick (a) where possible and escalate (b) as a coordinated 140
> dependency only if (a) proves insufficient.

**This design commits to option (a)** and proves it is sufficient for the
initiative's real cases. The evidence for that commitment — and the precise
boundary at which (b) becomes unavoidable — is established below against the
actual checkpoint machinery, not asserted.

## Value

**Architectural enablement.** This closes the cross-cutting question left open by
the architecture ("whether [judge and review] results combine into one gate,
stay separate, or are chosen per review type is an open slice-design decision")
and completes the initiative's gating story. After this slice, a pipeline author
who wants a gate that reflects *both* a judge's score-derived verdict and a
standard review's independent verdict has one documented, tested way to express
it — a single reduced verdict the existing checkpoint gates on — with no change
to the checkpoint machinery.

## Technical Scope

### The decisive constraint (verified in code)

The checkpoint machinery is **single-verdict-per-step by construction**, and the
reason is mechanical, not incidental:

1. **`prior_outputs` keys collide across steps.** The executor accumulates
   results as `prior_outputs[f"{action_result.action_type}-{idx}"]`, where `idx`
   is the per-step `enumerate` index of that step's action results
   ([executor.py:880-883](../../../src/squadron/pipeline/executor.py)). A
   `review` step expands to exactly one `review` action
   ([steps/review.py:69-76](../../../src/squadron/pipeline/steps/review.py)), so
   **every** standalone review step — judge or standard — writes the same key
   `review-0`. A judge review in an earlier step and a standard review in a
   later step therefore **overwrite each other** in `prior_outputs`; only the
   last survives under `review-0`.

2. **The checkpoint reads the *first* non-`None` verdict in reverse order.**
   `_find_review_verdict` walks `prior_outputs` in reverse insertion order and
   returns the first `result.verdict` that is not `None`
   ([checkpoint.py:28-37](../../../src/squadron/pipeline/actions/checkpoint.py)).
   Both a judge result (verdict = threshold-derived) and a standard review
   result (verdict = model-produced) carry a non-`None` verdict, so the
   checkpoint picks exactly one — whichever ran most recently — and never
   combines two.

**Conclusion.** For the checkpoint to gate on *both* judgments, the two verdicts
must be **reduced to one before they reach the checkpoint**. There is no key
under which both a separate judge step and a separate review step coexist for
`_find_review_verdict` to combine. This is precisely why the architecture flags
option (b) as a 140 change: combining two *separately-stepped* verdicts requires
the checkpoint to look past a single key — new checkpoint plumbing. Option (a)
sidesteps this by producing one verdict upstream.

### What this slice delivers (option a)

A **`gate` reduce action** (new *action*, additive — it registers into the open
action registry exactly as 300's own foundation says actions do) that reads two
named prior results — a judge result and a review result — from
`context.prior_outputs`, reduces their verdicts to a single verdict by a
documented rule, and returns an `ActionResult` carrying that one reduced verdict.
A checkpoint placed after the gate step sees the reduced verdict via the existing
`_find_review_verdict` path, unchanged.

Concretely, the deliverables are:

1. **A `gate` reduce action** (`src/squadron/pipeline/actions/gate.py`) — reads
   two referenced prior results, applies the reduction rule, emits one verdict.
   Registered via `register_action`; no checkpoint or executor change.
2. **A `gate` step type** (`src/squadron/pipeline/steps/gate.py`) — the schema a
   pipeline author writes (naming the two source steps and, optionally, the
   reduction policy and a `checkpoint:` trigger, mirroring the `review` step's
   own optional `checkpoint:`). Expands to `[gate, checkpoint?]`, so the gate's
   reduced verdict and the checkpoint land in the **same step** — the one place
   two related results survive under distinct keys and a checkpoint can read the
   gate's output directly.
3. **The documented reduction rule** — a conservative, most-severe-wins reduction
   (below), with the rationale and the escalation-to-140 boundary stated.
4. **Tests**, including the explicit **escalation-to-140 boundary case** the
   success criteria require.
5. **An authoring-guide section** on composing a judge and a review at one gate.

### The reduction rule: conservative most-severe-wins

The gate reduces the two verdicts by taking the **most severe** of the pair,
consistent with the initiative's "gate toward escalation when uncertain"
principle (architecture, *thresholds*) and the checkpoint's own
`UNKNOWN`-is-non-passing stance:

```
severity order (most severe first):  UNKNOWN  >  FAIL  >  CONCERNS  >  PASS
None verdict  →  normalized to UNKNOWN  (before comparison)
reduced verdict = the more severe of (judge_verdict, review_verdict)
```

- Two `PASS` → `PASS` (the gate advances only when *both* judgments clear).
- Any `FAIL` → `FAIL`; any `UNKNOWN` → `UNKNOWN` (cannot-judge dominates, so a
  broken judge never lets a passing review auto-advance, and vice-versa).
- `PASS` + `CONCERNS` → `CONCERNS`.
- **A `None` source verdict is normalized to `UNKNOWN` before the comparison.**
  A named source step can resolve to an `ActionResult` whose `verdict` is `None`
  — e.g. it ran a non-review action, or a review that produced no verdict. The
  checkpoint's own `_find_review_verdict` *skips* `None` verdicts (it hunts for
  the first non-`None`), but the gate **cannot** skip: a gate source that yielded
  no verdict is a source that could not be judged, and silently dropping it would
  let the *other* leg auto-advance a gate that was supposed to weigh both — the
  exact silent-pass the initiative forbids. So `reduce_verdicts` maps `None →
  UNKNOWN` on each leg *before* ranking, making a verdict-less source dominate
  (most severe) rather than disappear. This is the fail-closed choice, consistent
  with `UNKNOWN`-is-most-severe; it is **not** a fail-fast validation error,
  because a gate source producing no verdict at runtime is an observable
  cannot-judge outcome the checkpoint should gate on, not a pipeline-authoring
  mistake to reject at load. (A *missing or misspelled* source step *name*, by
  contrast, IS an authoring mistake — that is caught by gate-step validation, a
  separate path; see the failure-mode table.) The `None → UNKNOWN` normalization
  is unit-tested as its own case and logged at WARNING+ so a verdict-less gate
  source is never silent.
- **Ties are determinate.** When both legs carry the *same* severity, the reduced
  verdict is that shared value — most-severe-wins is idempotent on equal ranks, so
  `CONCERNS` + `CONCERNS` → `CONCERNS`, `FAIL` + `FAIL` → `FAIL`, etc. There is no
  tie-break to decide because the reduction returns a *severity rank*, not a
  *chosen leg*; which leg "won" is immaterial when both map to the same rank. This
  is a property of the ordered reduction, tested explicitly (the 4×4 cross-product
  includes all four diagonal ties). The raw per-leg verdicts remain on the gate
  result's `metadata` regardless, so a same-rank tie is still auditable (a human
  can see *both* legs said `CONCERNS`, not just the reduced `CONCERNS`).

`UNKNOWN` is ranked **most** severe deliberately: it means "a judgment could not
be rendered," and the architecture's no-silent-pass NFR requires that a
cannot-judge outcome never be masked by the other leg passing. This matches the
checkpoint's existing trigger sets, where `UNKNOWN` fires both `on-concerns` and
`on-fail` ([checkpoint.py:20-25](../../../src/squadron/pipeline/actions/checkpoint.py)).

The severity ranking is defined **once**, as an ordered enum/table in
`gate.py`, and referenced everywhere the reduction needs it — no scattered
comparison values (project rule). The verdict strings themselves are the
existing `PASS | CONCERNS | FAIL | UNKNOWN` set; the gate introduces no new
verdict value.

### Where the two source results come from

The gate references its two inputs **by step name**, not by the colliding
`{action_type}-{idx}` key. Because both source reviews wrote `review-0` and
clobbered each other in the global `prior_outputs`, the gate cannot recover them
from `prior_outputs` alone. Two candidate resolutions, decided here:

- **Chosen: the gate step names its two source steps, and the executor exposes
  per-source results to it.** The gate step config carries `judge_from:` and
  `review_from:` naming the two prior *step names*; the action resolves each to
  that step's review `ActionResult`. This requires the gate to reach
  results keyed by **step**, which the global `prior_outputs` does not preserve
  (it is action-keyed and lossy across same-typed steps).

  → **This is the point where option (a) touches the executor — and this
  executor touch is itself a candidate 140 coordination, not an unambiguously
  in-scope 300 change.** The architecture defines 300's additive scope narrowly
  as "not changing the *checkpoint* machinery"; it does not explicitly bless an
  additive change to the *executor's result accumulation*. Exposing per-step
  results to an action is a small, additive read-path addition (a step-keyed view
  alongside the existing action-keyed `prior_outputs`) that leaves the checkpoint
  and `_find_review_verdict` untouched — so it is *plausibly* within 300's spirit.
  But because it modifies 140-owned executor code (`prior_outputs` lives in the
  executor, slice 149/140), the honest classification is: **this is a 140-adjacent
  change that 300 proposes to make additively, and it must be confirmed with the
  140 owner before it lands, not assumed in-scope.** Two outcomes, both explicit
  rather than silent:

    - **Confirmed pure read-surface addition** (adds a step-keyed *view*, changes
      no existing behavior, touches no checkpoint code): proceed as an additive
      change with 140 sign-off recorded — this is the expected, default path.
    - **Cannot be done without altering `_find_review_verdict`, the checkpoint's
      single-verdict contract, or existing `prior_outputs` semantics**: option (a)
      is insufficient; **(b) is escalated as a coordinated 140 dependency** — see
      *The escalation boundary* below (this is condition 1 there).

  The distinction from prior framing: the executor touch is not merely "in-scope
  unless the downstream escalation conditions fire." It is a **140-adjacent change
  requiring coordination up front**, whose *cheapest* resolution (pure read
  surface) is additive and whose *expensive* resolution is the (b) escalation. The
  slice does not claim unilateral authority to modify executor result
  accumulation under 300's additive banner.

The gate does **not** try to make two separate review steps survive under
distinct keys in the existing `prior_outputs` — that is exactly the collision
that makes (b) necessary, and the gate is designed to avoid depending on it.

### What does NOT change

- **`_find_review_verdict` and the checkpoint's single-verdict contract.** The
  checkpoint still reads one verdict. The gate hands it one. The no-composed-step
  behavior is byte-for-byte identical (success criterion #2).
- **The judge templates, enforcement layer, parser, and result models** (300–302)
  — consumed as-is.
- **The `each`/`loop`/`commit` cycle and `judge-cycle.yaml`** (303) — untouched;
  gate composition is a *sibling* gating shape, not a change to the cycle.

### Explicitly out of scope

- **Checkpoint multi-verdict support (option b).** Not implemented here. It is
  raised as a **coordinated 140 dependency** (Future Work item 3 in the slice
  plan) and is triggered only by the escalation boundary below.
- **Composing more than two results**, or composing across arbitrarily many
  prior steps. The gate reduces exactly two named sources (judge + review); an
  N-way gate is a later concern with no current caller.
- **Per-criterion composition** (combining `criteria` maps). The gate reduces
  *verdicts*; the reserved `criteria` map (300) is passed through on the
  gate result for observability but is not itself reduced.
- **Multi-sample judging** (Future Work 1) — orthogonal, and specifically a
  *fan-in* concern, not a gate one. See the relationship note below.
- **N-sample convergence via fan-out/fan-in** — a different reduction axis
  entirely. See below.

### Relationship to fan-out/fan-in convergence (a different concern, likely to co-evolve)

There is a second, more sophisticated convergence mechanism already in the
codebase — the **`FanInReducer` protocol and registry**
(`src/squadron/pipeline/intelligence/fan_in/reducers.py`, slice 182) — with
built-in `collect` and `first_pass` reducers today and richer ones planned
(`merge_findings`, `unanimous` — slice 189). It is worth stating precisely how
the gate relates to it, because the two *look* similar ("reduce many results to
one verdict") but reduce along **different axes**, and the boundary should be
deliberate, not accidental:

| | **Gate (this slice, 304)** | **Fan-in (182 / 189)** |
|---|---|---|
| Reduces | **2 heterogeneous** judgments of one artifact | **N homogeneous** branch results from a fan-out |
| Sources differ in | *kind* — a judge verdict vs. an independent review verdict | *sample* — the same kind of review run across several models/prompts |
| Answers | "do a judge **and** a review agree this gate should open?" | "does the **consensus/median** of N samples clear the gate?" |
| Mechanism | one `gate` action, most-severe-wins over two named steps | `fan_out` step + a registered `FanInReducer` over N branches |
| Multi-sample judging (300 FW1) | not here | **this is where it lives** — N judge samples → median, via fan-in |

**They are orthogonal today and this slice keeps them so.** A gate composes two
*different* judgments; a fan-in converges N *equivalent* samples. Multi-sample
judging (running one judge N times and reducing by median to bound score
variance — 300 Future Work 1) is a **fan-in** job, not a gate job: it belongs to
the `fan_out`/`FanInReducer` machinery, and the gate should not grow a sample
count.

**But they will likely co-evolve, and the design should not pretend otherwise.**
Both are instances of "reduce a set of `ActionResult`s to one verdict," and as
fan-in gains richer reducers (median score, `unanimous`, majority-vote), the
gate's most-severe rule is arguably a *special case* of the same reducer
abstraction — a two-input, most-severe `FanInReducer`. A plausible future
refactor unifies them: the gate's reduction becomes a registered reducer, and a
"judge-plus-review" gate becomes a fan-out of two heterogeneous branches reduced
by a most-severe reducer. **This slice deliberately does not attempt that
unification** — there is no caller for it yet, and forcing the gate through the
fan-out branch model now would add real complexity (heterogeneous branches,
per-branch template config) to buy an abstraction nothing needs (project rule:
resist complexity until truly necessary). The gate ships as its own small,
purpose-built action. The note is here so a later slice that *does* unify them
does so knowingly — treating the gate's most-severe reduction as one reducer
among several — rather than discovering the overlap after the fact. **Flagged as
a likely future direction, not scheduled work.**

The slice plan requires: *"If option (a) is found insufficient for a required
case, the need for option (b) is raised as an explicit, coordinated 140
dependency — not implemented silently inside 300."* This section names the
exact, checkable condition, so the boundary is a decision rule, not a judgment
call made mid-implementation.

**Option (a) is sufficient — and this slice ships it — as long as the gate can
obtain both source verdicts and reduce them upstream *without modifying the
checkpoint's single-verdict read path.***

Option (a) is declared **insufficient**, and **(b) is escalated to 140**, if and
only if any of these holds in Phase 6:

1. Exposing per-step results to the gate action cannot be done as a pure
   additive read surface — i.e. it forces a change to `_find_review_verdict`'s
   contract, the checkpoint's single-verdict behavior, or existing
   `prior_outputs` semantics. (Note: the read-surface addition itself is
   140-adjacent and requires up-front 140 sign-off regardless — see *Where the
   two source results come from*; this condition is specifically about whether
   that addition can stay *pure*, or must instead change existing behavior and
   thereby become the full (b) escalation.)
2. A required case emerges where the checkpoint itself (not an upstream action)
   must weigh two verdicts — e.g. two *independent* checkpoints, each gating on a
   different one of the two results, that cannot be expressed as one reduced
   gate.
3. The reduction cannot be expressed as a pure function of the two verdicts
   (plus their scores) — e.g. a required policy needs the checkpoint to branch
   on *which* leg produced the severity, information a single reduced verdict
   discards.

If none hold, (a) stands and (b) stays in Future Work. The **boundary case
test** (success criteria) encodes condition (3): it asserts that a policy
requiring the checkpoint to see *both raw verdicts distinctly* is **not**
expressible via the gate and is documented as requiring 140 — proving the slice
recognizes its own edge rather than silently overreaching.

## Dependencies

### Prerequisites

- **Slice 302 (complete):** the judge templates — one leg of the composed gate is
  a real judge result.
- **Slice 301 (complete):** `enforce_judge` / provenance — the gate reads the
  judge leg's `provenance` to label its inputs and (optionally) its score.
- **Slice 300 (complete):** the `score` / `criteria` / `provenance` fields on
  `ActionResult` the gate passes through.
- **Slice 149/140 (pipeline foundation):** the action/step registries, the
  executor's `prior_outputs` accumulation, and the checkpoint — the machinery the
  gate composes with and the boundary it must not cross.

### Coordinated dependencies with 140

Two distinct 140 touch-points, at different confidence levels — both named so
neither is a silent absorption of 140-owned code:

- **Expected (default path): the per-step result read surface.** Even the
  in-scope, additive path modifies 140-owned executor code (`prior_outputs`
  accumulation lives in the executor, slice 149/140). This slice proposes it as a
  *pure read-surface addition* (a step-keyed view, no existing behavior changed,
  no checkpoint code touched) — but that is a change to 140 territory and
  **requires 140 sign-off before it lands**, not a unilateral 300 change. This is
  the expected, default outcome; the coordination is lightweight (confirm the
  addition is purely additive), but it is real and up front, not conditional.

- **Conditional: checkpoint multi-verdict support (Future Work 3).** The heavier
  140 change — extending the checkpoint to weigh multiple verdicts — is consumed
  **only if** the escalation boundary fires (the read surface can't stay pure, or
  a case needs the checkpoint itself to see both raw verdicts). The default
  outcome is that this does *not* fire and the checkpoint stays untouched; it is
  named so its possibility is not a surprise.

## Architecture

### Composition shape

```yaml
# Two independent judgments of the same artifact, reduced to one gate.
- review:                        # leg 1: the judge
    name: judge-slice
    template: judge.slice-vs-arch
    slice: "{slice}"
- review:                        # leg 2: a standard review
    name: review-slice
    template: design
    slice: "{slice}"
- gate:                          # reduce both → one verdict, then gate
    name: compose-gate
    judge_from: judge-slice
    review_from: review-slice
    policy: most-severe          # the documented default rule
    checkpoint: on-concerns      # fires on the REDUCED verdict
```

Data flow:

```
review (judge)  → ActionResult(verdict=<threshold-derived>, provenance=judge, score=..)
                        │  (written to prior_outputs, but review-0 key)
review (design) → ActionResult(verdict=<model-produced>,   provenance=review)
                        │  (overwrites review-0 in the lossy global map)
                        │
gate step ──────────────┴──> gate action resolves BOTH source ActionResults
                             by step name (judge_from / review_from)
                             │
                             reduce_verdicts(most-severe) → one verdict
                             │
                        ActionResult(verdict=<reduced>, provenance=composed,
                                     metadata={judge_verdict, review_verdict})
                             │  (same step) 
checkpoint (on-concerns) ────┴──> _find_review_verdict sees the gate's
                                  reduced verdict (last in this step) → fires or not
```

The checkpoint sits **in the gate step** (the gate step expands to
`[gate, checkpoint]`), so the reduced verdict is the most recent result the
checkpoint's reverse scan encounters — no reliance on cross-step key survival.

### Provenance of a composed result

A gate result is neither a bare judge result nor a bare review result. Per 300's
*A result declares its own provenance*, the gate emits a **new provenance
value** — `composed` — added to the `Provenance` enum
([judge.py:17-21](../../../src/squadron/pipeline/actions/judge.py)). A consumer
(a devlog, a future 320 calibration pass, a human) can then tell a reduced verdict
from a single-source one without knowing the pipeline shape. The two source
verdicts are preserved on the gate result's `metadata` (`judge_verdict`,
`review_verdict`) so the reduction is auditable — this is also what the boundary
test inspects to prove the checkpoint *could* branch on them only via 140.

### Why a `gate` step and not a `review`-step option

Reducing verdicts is a distinct responsibility (SRP): the review step *produces*
one judgment; the gate *combines* two. Overloading `review` with a "also read
another step and reduce" mode would grow its config conditionally (an OCP smell
the project rules call out) and blur the single-judgment contract every existing
pipeline relies on. A separate `gate` step keeps each step single-purpose and
leaves all 300–303 pipelines untouched.

## Integration Points

### Provides

- **The `gate` reduce action + step and the documented reduction rule** — the
  initiative's answer to "how do a judge and a review combine at one gate."
- **The `composed` provenance value** — lets downstream consumers (including
  320) distinguish reduced verdicts.

### Consumes

- **The checkpoint machinery** (`_find_review_verdict`, trigger sets) — unchanged,
  gated on the gate's single reduced verdict.
- **Judge (301) + review results** — the two legs.
- **The action/step registries and executor result accumulation** (140) — the
  gate registers additively; the per-step result read surface is the one
  additive executor touch, escalating to 140 only at the named boundary.

## Success Criteria

### Functional Requirements

1. A judge result and a review result compose into **one** checkpoint gate via an
   upstream reduction (option a): the `gate` action reduces the two verdicts to
   one, and a checkpoint in the same step gates on that reduced verdict. The
   reduction rule (most-severe-wins, `UNKNOWN` most severe) is documented in the
   authoring guide.
2. The existing **single-verdict-per-step checkpoint behavior is unchanged for
   non-composed steps** — `_find_review_verdict` and the checkpoint action are
   not modified; a pipeline with no `gate` step behaves byte-for-byte as before.
3. If option (a) is found insufficient for a required case (per the escalation
   boundary), the need for option (b) is **raised as an explicit, coordinated 140
   dependency** — surfaced in Future Work and the DEVLOG, never implemented
   silently inside 300. The default, shipped outcome is that (a) suffices.
4. Composition behavior is covered by tests, **including the escalation-to-140
   boundary case**: a test that asserts a policy requiring the checkpoint to see
   both raw verdicts distinctly is not expressible via the single reduced gate and
   is documented as a 140 concern.

### Technical Requirements

- The `gate` action and step register via the existing `register_action` /
  `register_step_type` with **no** checkpoint or `_find_review_verdict` change.
- A `gate` step loads and validates via the existing pipeline loader.
- Reduction is a **pure function** of the two verdicts, unit-tested across the
  full 4×4 verdict cross-product (`PASS/CONCERNS/FAIL/UNKNOWN` × the same, all 16
  pairs) with the most-severe result asserted for each pair — including the four
  **diagonal ties**, which must each reduce to their own shared value
  (`CONCERNS`+`CONCERNS` → `CONCERNS`, etc.). No score context is needed to break
  a tie: equal severities reduce to that severity by construction.
- The severity ordering is defined once (single ordered enum/table) and
  referenced everywhere — no scattered comparison literals.
- A test asserts a gate over (judge=PASS, review=CONCERNS) yields a checkpoint
  that **fires** on `on-concerns`, and (judge=PASS, review=PASS) yields one that
  **does not** — proving the reduced verdict, not either raw leg, drives the gate.
- A test asserts (judge=UNKNOWN, review=PASS) reduces to `UNKNOWN` and the
  checkpoint fires — the no-silent-pass NFR under a broken judge leg.
- A test asserts a source leg with `verdict=None` is normalized to `UNKNOWN`
  (not skipped), reduces to `UNKNOWN`, fires the checkpoint, and logs at
  WARNING+ — pinning the fail-closed handling of a verdict-less gate source and
  the divergence from `_find_review_verdict`'s skip-`None` behavior.
- No changes to `pyright` strict / `ruff` status.

### Integration Requirements

- The composed gate runs via the existing `sq run` path with no new CLI surface.
- 303's `judge-cycle.yaml` and every 300–302 pipeline are unaffected.

## Verification Walkthrough

> Confirmed against actual output during Phase 6 implementation (all commands
> run from the project root, on branch `304-slice.gate-composition`).

```bash
# 1. The gate action/step register and a composing pipeline validates.
uv run sq run compose-gate-example --validate
# Actual: Pipeline 'compose-gate-example' is valid.

# 2. Reduction is a pure, exhaustively-tested function.
uv run pytest tests/pipeline/test_gate.py -k reduce -v
# Actual: 31 passed — the full 4x4 verdict cross-product (test_most_severe_wins),
#         diagonal ties, and None-normalization cases (test_none_dominates_every_verdict)
#         plus GateAction's reduce-driven execute cases.

# 3. The reduced verdict — not either raw leg — drives the checkpoint.
# Caveat: the class name, not a "drives_checkpoint" substring, is the filter —
# the actual test class is TestDrivesCheckpoint.
uv run pytest tests/pipeline/test_gate.py -k TestDrivesCheckpoint -v
# Actual: 4 passed — test_pass_and_concerns_fires_on_concerns (fires),
#         test_both_pass_does_not_fire (skips), test_judge_unknown_review_pass_fires
#         (fires, no-silent-pass), test_none_leg_normalizes_and_fires_with_warning
#         (F003 end-to-end None case, fires + WARNING logged).

# 4. No-silent-pass under a broken judge leg.
# Caveat: the actual test name is test_judge_unknown_review_pass_fires, not
# "unknown_dominates" — use the exact name below.
uv run pytest tests/pipeline/test_gate.py -k test_judge_unknown_review_pass_fires -v
# Actual: 1 passed — (judge=UNKNOWN, review=PASS) → reduced UNKNOWN → checkpoint fires.

# 5. The escalation-to-140 boundary is recognized, not overreached.
uv run pytest tests/pipeline/test_gate.py -k boundary_requires_140 -v
# Actual: 1 passed — test_boundary_requires_140 asserts a policy needing the
#         checkpoint to branch on both raw verdicts distinctly is NOT
#         expressible via the single reduced gate (checkpoint reads only
#         .verdict, never .metadata) and is documented as a 140 concern.

# 6. Non-composed pipelines are byte-for-byte unchanged.
uv run pytest tests/pipeline -k checkpoint -v
# Actual: 83 passed — every pre-existing checkpoint test (actions, prompt
#         renderer, sdk integration, state, summary) passes unmodified.

# 7. Full regression + static analysis.
uv run pytest && uv run pyright && uv run ruff check
# Actual: 2198 passed, 2 skipped (pre-existing, unrelated); pyright 0 errors;
#         ruff all checks passed.
```

## Risk Assessment

### Failure Modes on the Composed-Gate Path

| Failure mode | Handling | Outcome |
|---|---|---|
| One leg (judge or review) returns `UNKNOWN` | Reduction ranks `UNKNOWN` most severe | Reduced verdict `UNKNOWN`; checkpoint fires — never a silent pass |
| A named source step exists and succeeded but its `ActionResult.verdict` is `None` (non-review action, or a review that produced no verdict) | `reduce_verdicts` normalizes `None → UNKNOWN` *before* ranking, and logs WARNING+ — unlike `_find_review_verdict`, the gate does **not** skip a `None` leg | Reduced verdict `UNKNOWN`; checkpoint fires — a verdict-less source dominates rather than vanishing, so it can never silently let the other leg advance |
| A `gate` source step name is misspelled / missing | Gate-step *validation* (load-time) requires both `judge_from` / `review_from` name real prior steps → validation error, fail fast. If resolution nonetheless fails at execute time, the gate returns a runtime `UNKNOWN` with a WARNING+ log | Observable failure, non-passing; no gate advances on an unresolved source |
| Both legs `PASS` | Reduction → `PASS` | Gate advances — the only advancing outcome, requiring *both* judgments to clear |
| Per-step result read surface can't be added additively | Escalation boundary condition (1) fires | (b) raised as a coordinated 140 dependency; slice does not force a checkpoint change |
| A required policy needs the checkpoint to see both raw verdicts | Escalation boundary condition (3) fires; boundary test encodes it | Documented as a 140 concern (Future Work 3), not smuggled in |

**No silent pass:** the gate advances only when the reduction yields `PASS`,
which requires *both* legs to be `PASS`. Any non-`PASS` on either leg — including
`UNKNOWN` — produces a non-passing reduced verdict the checkpoint gates on.

### Technical Risks

- **The one executor touch (per-step result read surface) is 140-adjacent and
  needs sign-off up front.** The gate needs source results keyed by step, which
  the lossy action-keyed `prior_outputs` does not preserve. Adding a step-keyed
  read view is the single place this slice reaches into the executor — and
  `prior_outputs` is 140-owned. **This is not assumed in-scope under 300's
  additive banner:** the default path proposes it as a *pure read-surface
  addition* (a step-keyed view, no existing behavior changed, no checkpoint code
  touched) requiring 140 confirmation before it lands — a lightweight but real,
  up-front coordination. **Risk:** if it cannot be done purely additively, option
  (a) is insufficient and the escalation boundary (condition 1) fires.
  **Mitigation:** both outcomes are explicit — confirmed-pure-addition (default,
  proceed with 140 sign-off) or escalate-to-(b) — and the boundary is a stated,
  checkable condition; the slice coordinates with 140 rather than unilaterally
  modifying executor result accumulation or distorting the checkpoint contract.
  This is the architecture's anticipated edge, handled by explicit coordination,
  not a surprise.

## Implementation Notes

### Development Approach

Suggested order:

1. Add `Provenance.COMPOSED`; define the severity ordering once
   (ordered enum/table) with a pure `reduce_verdicts(a, b) -> str`.
2. Unit-test `reduce_verdicts` across the full 4×4 verdict cross-product first
   (it is the slice's core logic and fully testable in isolation).
3. Implement the `gate` action reading two named prior results and emitting the
   reduced verdict + `composed` provenance + both raw verdicts in metadata.
4. Implement the `gate` step (`[gate, checkpoint?]` expansion) and its validation
   (both source names present and resolvable).
5. Add the drives-checkpoint, unknown-dominates, and **boundary-requires-140**
   tests, plus a non-composed-unchanged regression assertion.
6. Write the authoring-guide section: the composition shape, the reduction rule,
   the `UNKNOWN`-most-severe rationale, and — explicitly — when a case needs 140
   instead.
7. If (and only if) the escalation boundary fires in step 3–4, stop, record the
   trigger in the DEVLOG and Future Work 3, and coordinate the 140 dependency
   rather than modifying the checkpoint.

### Special Considerations

- **Do not modify `_find_review_verdict` or the checkpoint.** The whole point of
  option (a) is that the checkpoint stays single-verdict; the gate feeds it one.
  A change to either is the signal to escalate to 140, not to proceed.
- **Define the severity order once.** No scattered `if verdict == "FAIL"` chains
  across the action and step — one ordered table, referenced everywhere (project
  rule; SRP/OCP).
- **`UNKNOWN` is most severe, deliberately.** It is the no-silent-pass guarantee;
  a broken judge leg must dominate a passing review leg. Do not rank it as
  "least informative → ignore."
- **Preserve both raw verdicts on the gate result's metadata.** They are what
  makes the reduction auditable and what the boundary test inspects; discarding
  them would hide exactly the information that distinguishes (a) from (b).
- **The gate reduces exactly two named sources.** Resist generalizing to N-way
  composition with no caller (added complexity the project rules forbid).
