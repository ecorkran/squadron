---
docType: slice-design
slice: judge-gated-cycle-conventions
project: squadron
parent: 300-slices.eval-actions-llm-as-judge-scoring.md
dependencies: [302]
interfaces: [304]
dateCreated: 20260706
dateUpdated: 20260707
status: in-progress
---

# Slice Design: Judge-Gated Cycle Conventions

## Overview

This slice delivers the initiative's headline capability: the human-driven
**review → fix → re-review** loop expressed as an unattended pipeline. A judge
scores an artifact, the score-derived verdict gates the loop, the cycle repeats
while the artifact fails to clear its threshold up to a bound, and it escalates
to a human where the score cannot clear.

It introduces **no new step type, action, or engine change.** Every construct it
needs already exists and was verified in the codebase during this design:

- `loop` (`src/squadron/pipeline/steps/loop.py`) with `max`, `until`,
  `on_exhaust` — the bound and the exit/escalation semantics.
- The judge templates from slice 302 (`judge.slice-vs-arch`,
  `judge.tasks-vs-slice`) selected by name in a `review` step.
- `dispatch` (the fix leg) and `checkpoint` (the escalation surface) — both
  pre-existing. (`commit` is a pre-existing action too, but *not* usable as a
  bare loop-body step — see Technical Decisions.)

The deliverable is therefore **the convention, a worked reference pipeline that
proves the machinery composes, and the documentation** that turns "this is
expressible" into "here is how you express it." Slice 302 already ran both judge
templates live and confirmed they produce a score-derived verdict; this slice
wires that verdict into the loop's exit condition.

## Value

**User value.** The routine design-phase gates — does this slice-design satisfy
its arch doc, do these tasks reflect their slice — stop requiring a human at
each turn. A pipeline runs the judge, auto-advances where the score clears the
threshold, drives a fix step and re-judges where it does not, and bubbles the
genuinely hard calls (weak ground truth, or a bound exhausted without clearing)
up to a human. This is the point at which the initiative's "intelligence at the
decision points" (architecture, Design Goals) becomes something a user runs.

## Technical Scope

### What this slice delivers

1. **A documented judge-gated-cycle convention** — how `loop` / `review`
   (judge) / `dispatch` compose to express review→fix→re-review,
   including the two gating modes (auto-advance vs. escalate) and how each is
   configured.

2. **A worked reference pipeline** shipped as a built-in
   (`src/squadron/data/pipelines/judge-cycle.yaml`) that runs the cycle
   end-to-end against a real design-phase artifact using a slice-302 judge
   template. It is the executable proof that the existing machinery drives
   repeated one-shot judges.

3. **Authoring documentation** — a section in the pipeline authoring guide (or a
   companion doc) that a user follows to build their own judge-gated pipeline,
   covering the bound, the exit condition, the escalation path, and the
   advisory-only pattern for weak-ground-truth gates.

### What does NOT change

- No new step type, action, selector, or executor branch. The loop's `until`
  already evaluates against `verdict`, and a judge's verdict is the
  threshold-derived projection of its score (slice 301) — so a judge-gated loop
  is expressible with zero code.
- The judge templates, enforcement layer, parser, and result models — consumed
  as-is from slices 300–302.
- The `checkpoint` action and its `UNKNOWN`-inclusive trigger sets
  (`src/squadron/pipeline/actions/checkpoint.py`) — the escalation surface is
  reused unchanged.

### Explicitly out of scope

- **Gate composition** (combining a judge verdict and a standard review verdict
  into one gate) — slice 304. This slice uses a judge verdict *or* a review
  verdict at a gate, never both together.
- **Multi-sample judging** (fan-out + median to bound score variance) — Future
  Work 1. The reference pipeline runs a single judge per iteration.
- **New `each` sources.** Only `cf.unfinished_slices` is registered today
  (`_SOURCE_REGISTRY`, `executor.py`). The `each`-over-a-collection convention
  is documented against that one real source; this slice does **not** author new
  source functions. A per-slice `each` fan-out that needs a different collection
  is a separate, later concern.
- **A new `sq review` CLI subcommand for judge templates** — out of scope per
  slice 302; judges are reached via the pipeline `review` step.

## Dependencies

### Prerequisites

- **Slice 302 (complete):** `judge.slice-vs-arch` / `judge.tasks-vs-slice`
  templates — the real judges this slice's pipeline selects by name.
- **Slice 301 (complete):** `enforce_judge` / `resolve_thresholds` — supplies the
  threshold-derived verdict the loop's `until` reads, and the step-level `judge:`
  override the advisory-only pattern relies on.
- **Slice 300 (complete):** the `score` field the verdict derives from.

### Interfaces Required (all existing, verified this design)

- `LoopCondition` (`executor.py:215`) — `review.pass`,
  `review.concerns_or_better`, `action.success`. The loop's `until` exit
  condition, evaluated against the last action result carrying a verdict.
- `ExhaustBehavior` (`executor.py:257`) — `fail`, `checkpoint`, `skip`. What the
  loop does when `max` iterations pass without `until` being satisfied.
- The `review` step schema (`steps/review.py`) — already accepts `template`,
  `slice`, a step-level `judge:` override dict, and `checkpoint`.
- `dispatch`, `commit`, `checkpoint` actions — the fix leg, the persist leg, and
  the escalation surface.

## Architecture

### The convention: review → fix → re-review as a bounded loop

The cycle is a `loop` whose body is **[fix, judge]**, exiting when the judge's
score-derived verdict clears the threshold:

```yaml
- loop:
    max: 3                       # the bound — never unbounded
    until: review.pass           # exit when the judge verdict is PASS
    on_exhaust: checkpoint       # escalate to a human if the bound is hit
    steps:
      - dispatch:                # the fix leg — revise the artifact
          prompt: "Address the judge findings in {input}. ..."
      - review:                  # the judge — scores the (revised) artifact
          template: judge.slice-vs-arch
          slice: "{slice}"
```

Each element maps to an architectural commitment:

| Element | Role | Backed by |
|---|---|---|
| `loop.max` | The bound — no unbounded looping | `loop.py` validation (required positive int) |
| `until: review.pass` | Exit when the score clears the pass floor | `LoopCondition.REVIEW_PASS` reads the judge verdict |
| `dispatch` (fix leg) | Revise the artifact toward the findings | pre-existing action |
| `review` (judge) | Re-score the revised artifact each iteration | slice 302 template + slice 301 enforcement |
| `on_exhaust: checkpoint` | Escalate the hard call to a human | `ExhaustBehavior.CHECKPOINT` → `PAUSED` |

The loop iterates: dispatch revises → judge re-scores → `until` checks the fresh
verdict. If `PASS`, the loop exits and the pipeline auto-advances. If not, it
loops again — up to `max`. On the `max`-th failure the loop exhausts and
`on_exhaust` fires.

### Data flow — one iteration

```
loop iteration N
    │
    ▼
dispatch (fix)  ── revises the artifact per prior judge findings
    │            (iteration 1 may skip or seed from an initial review;
    │             see "First-iteration shape" below)
    ▼
review (judge: template: judge.slice-vs-arch, slice: {n})
    │  ReviewAction._review()
    │    resolve_template_inputs → input=design_file, against=arch_file  [302]
    │    run_review_with_profile → score + findings, no verdict emitted
    │    enforce_judge(score, thresholds) → verdict = PASS|CONCERNS|FAIL   [301]
    ▼
ActionResult(verdict=<threshold-derived>, score=..., provenance="judge")
    │
    ▼
loop evaluates until (review.pass):
    evaluate_condition(REVIEW_PASS, action_results)   [executor.py:232]
      → last_with_verdict().verdict == "PASS" ?
         │                              │
        yes → loop exits              no → iterate (if N < max)
        (auto-advance)                    else → on_exhaust: checkpoint
                                              → StepResult(status=PAUSED)
                                              → human escalation, observable
```

The key seam: **the loop's `until` evaluates the *judge's* verdict, which is the
score's projection** — so "gate on the score" needs no score-aware loop
condition. `REVIEW_PASS` already means "the last verdict was PASS," and for a
judge result that verdict *is* `score ≥ pass_floor`.

### Two gating modes

The architecture's "bubble up the hard calls" splits into two configurations of
the same loop, distinguished only by threshold and exit condition:

**1. Auto-advance (strong ground truth, e.g. tasks-vs-slice).** The judge's
default `pass_floor` (78 for `judge.tasks-vs-slice`, slice 302) is clearable by a
good artifact. `until: review.pass` exits the loop when the artifact clears it;
the pipeline proceeds without a human. `on_exhaust: checkpoint` only fires if the
fix leg cannot get the artifact over the floor within `max` tries — a genuine
hard case.

**2. Advisory-only / always-escalate (weak ground truth, e.g. arch-vs-concept).**
Per the architecture: a weak-ground-truth judge is "configured advisory-only (a
floor it effectively cannot clear, forcing escalation)." This is expressed with
the step-level `judge:` override (slice 301) raising `pass_floor` beyond reach:

```yaml
- review:
    template: judge.slice-vs-arch
    slice: "{slice}"
    judge:
      pass_floor: 101      # unreachable — the judge can never emit PASS
```

Because the verdict can never be `PASS`, `until: review.pass` is never
satisfied, the loop always exhausts, and `on_exhaust: checkpoint` always
escalates. The judge's score and findings are still produced and persisted (they
inform the human), but the *decision* is always the human's — advisory, not
gating. This reuses the exact override mechanism slice 301 built; no new
"advisory" flag is invented.

> Note the asymmetry with a `pass_floor` of 0: a floor of 0 would make *every*
> score pass. Advisory-only is the opposite — a floor above 100 so *no* score
> passes. Both are expressed with the same `judge.pass_floor` override; only the
> value differs. This keeps "advisory-only" as data, not a new code path.
>
> **This depends on thresholds staying unclamped.** Verified: `resolve_thresholds`
> does no range validation on threshold values (the 0–100 range check applies to
> the *score*, per slice 301's two-layer split), so `pass_floor: 101` is a
> *sanctioned* value today. The authoring doc must state this explicitly, so a
> future "validate thresholds to 0–100" cleanup does not silently break the
> advisory-only convention — a threshold clamp would need to preserve an
> above-range "never passes" sentinel, or advisory-only would need a different
> expression. The advisory-always-escalates test (Success Criteria) pins the
> current behavior as a regression guard.

### First-iteration shape

The body is `[fix, judge]`, but on the first iteration there are no prior judge
findings to fix. Two documented shapes, both using only existing constructs:

- **Fix-first (recommended for the reference pipeline):** loop `[fix, judge]`
  directly; the first `fix` dispatch is prompted to do an initial pass
  ("produce/improve {input}"), and the first judge scores that. Simpler YAML; the
  fix prompt does double duty. This mirrors `test-loop.yaml`'s precedent
  (dispatch-then-review inside the loop) exactly.
- **Judge-first (informational pre-score):** run an initial `review` (judge)
  step *before* the loop, then loop `[fix, judge]`. The pre-loop judge produces
  an initial score/findings for the log, but — see the executor note below — it
  does **not** short-circuit the loop; iteration 1 still runs the fix leg. Choose
  this only when an initial persisted score before any fix is worth the extra
  step, not to avoid a "wasted" first fix.

> **Executor semantics (verified in `_execute_loop_body`, `executor.py:1109`).**
> The multi-step loop is **post-test**: `until` is evaluated only *after* an
> iteration's inner steps complete, and only against that iteration's own action
> results — `iteration_action_results` is reset to `[]` at the top of each
> iteration (line 1112) and never sees pre-loop or prior-iteration results.
> Consequently a pre-loop judge PASS cannot satisfy `until`; iteration 1 always
> runs `[fix, judge]` in full before `until` can exit. The reference pipeline
> therefore uses **fix-first** and accepts that iteration 1 always fixes once —
> even on an already-passing artifact — because the executor provides no
> loop-entry pre-test to skip it. "Auto-advance when already good" means the loop
> exits after **one** `[fix, judge]` iteration (the judge clears the floor and
> `until` is satisfied), not that the loop is skipped entirely.

### Why no new construct is needed — the verification

`test-loop.yaml` already ships this exact shape with a *standard* review:

```yaml
- loop:
    max: 3
    until: review.pass
    on_exhaust: fail
    steps:
      - dispatch: { prompt: "...", model: haiku }
      - review: { template: code, model: minimax }
```

Swapping `template: code` → `template: judge.slice-vs-arch` and `on_exhaust:
fail` → `on_exhaust: checkpoint` is the entire delta from "review loop" to
"judge-gated escalating cycle." That the delta is *data only* is the slice's
central claim, and `test-loop.yaml`'s existence is its proof-of-concept.

## Technical Decisions

### The loop bound is `max`; there is no unbounded mode

`loop.max` is a required positive integer (validated in `loop.py`). The
convention forbids simulating unboundedness (there is no "loop until pass with no
cap"). A judge cycle that never clears its floor must terminate at `max` and
escalate — this is the "no unbounded looping" success criterion, enforced by the
existing schema, not by new code.

### Escalation is `on_exhaust: checkpoint`, and it is observable

When the bound is hit without clearing, `ExhaustBehavior.CHECKPOINT` produces a
`StepResult` with `status=PAUSED` (`_loop_exhaust_result`, `executor.py:969`).
The pipeline pauses at a human decision point rather than silently failing or
silently passing. This satisfies "the escalation path is observable": a paused
run is a visible state, and the exhaustion carries the accumulated action
results (including the last judge's score and findings) for the human to read.

Contrast with `on_exhaust: fail` (used in `test-loop.yaml`): that terminates the
run as failed. For a *judge* cycle whose purpose is to bubble hard calls to a
human, `checkpoint` is the correct default — the run is not wrong, it is
*undecided*, which is exactly what a checkpoint represents. The convention
documents `fail` as the choice only where an unclearable artifact should abort
the pipeline rather than wait for a human.

### Advisory-only is a threshold value, not a flag

As shown above, "advisory-only" is `pass_floor` set beyond 100 via the existing
step-level `judge:` override. No `advisory: true` field is added — that would be
a second way to express "escalate," fragmenting the mechanism. One knob
(`pass_floor`) spans the whole range from auto-pass (low floor) through normal
gating (default floor) to always-escalate (floor > 100). This is consistent with
slice 301's "thresholds are the single locus" commitment and the project rule
against scattering comparison values.

### Per-iteration `commit` is NOT expressible as a bare loop-body step (verified)

The architecture lists `commit` as part of the composable set, and an earlier
draft of this design proposed an optional `[fix, judge, commit]` loop body.
**That is invalid** — verified against the step registry: `commit` is a
registered *action* (`ActionType.COMMIT`, `actions/commit.py`), **not** a
registered *step type*. The registered step types are `design`, `tasks`,
`implement`, `dispatch`, `compact`, `summary`, `review`, `each`, `fan_out`,
`loop`, `devlog` (`StepTypeName`, `steps/__init__.py`) — no `commit`. A loop's
`steps:` list only accepts registered step types (`inner_steps` /
`unpack_inner_steps`), so writing `- commit: {...}` in a loop body would fail
pipeline validation with `Unknown step type 'commit'`.

`commit` is only emitted as an action *inside* a phase step (`PhaseStepType.expand`
auto-appends it for `design`/`tasks`/`implement`), never as a standalone loop
step. The judge cycle's body is therefore `[fix, judge]` only. Per-iteration
commit is **not** available in this slice's conventions.

This does not affect the slice's core mechanics — `loop` / `review` (judge) /
`dispatch` / `on_exhaust` are all verified and sound. It only removes the
optional-commit example. A user who needs each fix individually persisted must
either commit once after the loop (a `commit`… also not a bare step — so via a
phase step or an out-of-band `git` call), or wait on the Future Work item below.

**Future Work (not this slice):** a standalone `commit` step type, or a way to
reuse the phase-step commit action inside a loop body, would make per-iteration
commit expressible. Adding one here is out of scope and would contradict Success
Criterion #6 ("no new step type introduced"). Logged as a follow-up.

### The reference pipeline gates on a real slice-302 judge, not a synthetic one

Slice 302 verified both judge templates against real in-repo artifact pairs
(`judge.tasks-vs-slice` scored 91, `judge.slice-vs-arch` scored 86). The
reference pipeline targets `judge.slice-vs-arch` with `slice: {slice}` so its
`input`/`against` auto-resolve via `TEMPLATE_INPUTS` (slice 302) — the same path
those verification runs exercised. This keeps the reference pipeline runnable
against any real slice in the repo, not a toy fixture.

## Integration Points

### Provides to Other Slices

- **The judge-gated-cycle convention and reference pipeline** — slice 304 (gate
  composition) builds on the same loop/judge composition when it resolves how a
  judge verdict and a review verdict combine at a single gate. This slice
  deliberately keeps them separate (a gate reads one verdict); 304 is where they
  merge.

### Consumes from Other Slices

- **Slice 302:** the judge templates, by name, unchanged.
- **Slice 301:** `resolve_thresholds` (step-level `judge:` override for the
  advisory pattern) and the score-derived verdict `until` reads.
- **Slice 149/140 (pipeline foundation):** `loop`, `each`, `dispatch`, `commit`,
  `checkpoint`, and the executor's loop/exhaust handling — all consumed as-is.

## Success Criteria

### Functional Requirements

1. A documented convention shows `loop` + a judge `review` step expressing the
   review→fix→re-review cycle, with the body `[fix, judge]` and
   `until: review.pass`. (Per-iteration `commit` is not a bare loop-body step —
   see Technical Decisions; the body is `[fix, judge]` only.)
2. A worked reference pipeline (`judge-cycle.yaml`) runs the cycle unattended
   against a real design-phase artifact: it auto-advances (loop exits) when the
   judge score clears the threshold, and reaches `on_exhaust: checkpoint`
   (PAUSED) when it does not.
3. The cycle is bounded by `loop.max` — no unbounded-loop convention exists or is
   documented. Exhaustion is reached deterministically at `max`.
4. The escalation path is observable: exhaustion produces a `PAUSED` StepResult
   carrying the last judge's score and findings, distinguishable from a normal
   completed run.
5. The advisory-only (always-escalate) mode is expressed purely via a
   step-level `judge.pass_floor` override beyond 100 — no new field, flag, or
   code path.
6. No new step type, action, selector, or executor branch is introduced; the
   entire slice is pipeline data + documentation.

### Technical Requirements

- `judge-cycle.yaml` loads and validates via the existing pipeline loader with
  no new step/action registrations.
- A test loads `judge-cycle.yaml` and asserts its structure (a `loop` with
  `max`, `until: review.pass`, `on_exhaust: checkpoint`, and a body containing a
  `review` step naming a slice-302 judge template).
- A test drives the loop with a mocked judge whose score is forced below the
  floor and asserts the loop exhausts to `PAUSED` (escalation observable) at
  exactly `max` iterations; and a companion test with the score forced above the
  floor asserts the loop exits early (auto-advance) without reaching `max`.
- A test asserts the advisory-only override (`pass_floor > 100`) causes the loop
  to always exhaust to `checkpoint` regardless of a passing raw score, proving
  the escalation is driven by the threshold, not the model.
- No changes to `pyright` strict / `ruff` status. `judge-cycle.yaml` is data; any
  test additions pass the same strict gates as the rest of the suite.

### Integration Requirements

- The reference pipeline runs via the existing `sq run` path (prompt-only or SDK
  executor) with no new CLI surface.
- Slice 304 can extend the same loop/judge composition to gate composition
  without reworking the convention this slice establishes.

## Verification Walkthrough

```bash
# 1. The reference pipeline loads and validates with no engine change.
uv run python - <<'PY'
from squadron.pipeline.loader import load_pipeline   # adjust to actual loader API
p = load_pipeline("judge-cycle")
# find the loop step and assert its judge-gated shape
loop = next(s for s in p.steps if s.step_type == "loop")
assert loop.config["max"] >= 1
assert loop.config["until"] == "review.pass"
assert loop.config["on_exhaust"] == "checkpoint"
body = loop.config["steps"]
review = next(s for s in body if "review" in s)["review"]
assert review["template"].startswith("judge.")
print("PASS: judge-cycle.yaml has the bounded, judge-gated, escalating shape")
PY

# 2. Auto-advance: judge clears the floor → loop exits early, no escalation.
#    (unit test, judge mocked to score above pass_floor)
uv run pytest tests/ -k judge_cycle_auto_advance -v

# 3. Escalation: judge never clears the floor → loop exhausts to PAUSED at max.
#    (unit test, judge mocked to score below concerns_floor)
uv run pytest tests/ -k judge_cycle_escalates -v

# 4. Advisory-only: pass_floor override > 100 → always escalates even on a high
#    raw score. Proves the gate is the threshold, not the model.
uv run pytest tests/ -k judge_cycle_advisory_always_escalates -v

# 5. End-to-end unattended run against a real slice (requires provider access).
#    Mirrors slice 302's live-run caveats: from inside a Claude Code session use
#    profile="openrouter" with an explicit model, and `source .env` first.
set -a && source .env && set +a
uv run sq run judge-cycle --slice 302   # exact flag shape confirmed at impl time
# Expected: the judge scores 302's design vs. its arch doc; if it clears the
# floor the loop exits and the run advances; otherwise the fix leg revises and
# it re-judges up to max, then PAUSES for human review. The paused state and the
# last judge's score/findings are visible in the run output.

# 6. Full regression + static analysis
uv run pytest
uv run pyright
uv run ruff check && uv run ruff format --check
```

> The exact loader API and `sq run` flag shape are confirmed against the current
> surface during implementation (Phase 6); the *intent* — load the reference
> pipeline, drive the loop to both auto-advance and escalation, and prove the
> advisory override forces escalation — is the fixed part of this walkthrough.

## Risk Assessment

### Failure Modes on the Judge-Cycle Path

This slice adds **no new handling code** — every failure mode routes through
machinery slices 149/301/302 already built and tested. Enumerated for this
slice's specific composition:

| Failure mode | Handling | Outcome |
|---|---|---|
| Judge returns `UNKNOWN` (unparseable / missing score / provider down/errored) | `until: review.pass` is not satisfied by `UNKNOWN`; the loop iterates or exhausts | Never a silent pass — loops then escalates via `on_exhaust: checkpoint` |
| Fix leg (`dispatch`) inner step returns FAILED | `_execute_loop_body` treats an inner FAILED step as **transient** (`executor.py:1143`): the judge inner step still runs next, against the un-revised artifact | Judge scores the un-revised artifact → non-`PASS` → `until` not satisfied → iterate/escalate. No silent pass |
| Judge or fix provider call **hangs / exceeds a timeout** mid-iteration | **Gap — no per-call timeout exists** in the review/dispatch action or `run_review_with_profile` path (verified: no `wait_for`/`timeout` there). `loop.max` bounds *iterations*, not wall-clock; a hung call stalls the unattended run indefinitely | **Accepted risk this slice** — see Technical Risks. Not silently *passing* (the run stalls, it never advances), but it does defeat unattended progress. Owner: pipeline-foundation (140); a per-call timeout mapping a `TimeoutError` to `UNKNOWN` is a 140 concern, tracked in Future Work, not authored here |
| Bound exhausted without clearing | `ExhaustBehavior.CHECKPOINT` → `PAUSED` | Observable human escalation |
| Advisory judge (floor > 100) on a high raw score | `enforce_judge` derives non-PASS from `score < pass_floor`; `until` never satisfied | Always escalates — the intended behavior, not a failure |
| Judge emits a rogue verdict despite the template forbidding it | `enforce_judge` ignores `result.verdict` (slice 301); `until` reads the derived verdict | Score-derived verdict wins; rogue verdict never reaches the loop condition |

**No silent pass**: the only way the loop exits without escalation is a genuine
score-derived `PASS`. Every non-clearing outcome — including `UNKNOWN` and a
FAILED fix leg — either iterates (within the bound) or escalates. This is the
architecture's no-silent-pass NFR, and it holds here because the loop's exit
condition reads the same score-derived verdict slices 300–302 established, with no
new gate in between. **The one mode that is not "escalate" is a provider hang**
(row 3): it stalls rather than passes, and its remedy (a per-call timeout) is a
140 concern this slice explicitly does not absorb — named here so the boundary is
not a silent gap.

### Technical Risks

- **The reference pipeline's live behavior depends on the fix leg's prompt
  quality.** Whether the `dispatch` fix step actually improves an artifact enough
  to clear the floor within `max` is a prompt-engineering question observable
  only against a live provider (the same class of risk slice 302 flagged for the
  judge prompt). The unit tests mock the judge score to prove the *control flow*
  (auto-advance vs. escalate) deterministically; the live run validates the
  *prompt* separately. The slice's correctness claim is about the control-flow
  composition, which is fully testable; the fix prompt is tunable data.

- **A hung provider call is not bounded by `loop.max` (accepted, deferred to
  140).** `loop.max` bounds the iteration *count*, not wall-clock time, and the
  review/dispatch path has no per-call timeout today (verified). An unattended
  judge cycle whose provider hangs will stall inside an iteration rather than
  escalate. This slice does **not** add a timeout — introducing one belongs in
  the pipeline-foundation action/client layer (140), where every action (not just
  judges) would benefit, and where a `TimeoutError` can be mapped to a review
  `UNKNOWN` so the existing iterate/escalate flow absorbs it. Recorded as Future
  Work below and surfaced in the failure-mode table so the gap is explicit, not
  discovered mid-run. The judge cycle inherits whatever timeout 140 later adds
  with no change to this slice's convention.

### Mitigation Strategies

- Task breakdown should include (a) deterministic control-flow tests with a
  mocked judge for both auto-advance and escalation, and (b) at least one live
  unattended run against a real slice, treating the first runs' fix-prompt
  behavior as data for tuning, not a one-shot final draft — mirroring slice 302's
  mock-vs-live split.

## Implementation Notes

### Development Approach

Suggested order:

1. Author `judge-cycle.yaml` with the judge-first shape (pre-loop judge, then
   `loop [fix, judge]`, `until: review.pass`, `on_exhaust: checkpoint`), gating
   on `judge.slice-vs-arch` with `slice: {slice}`.
2. Add the structural load/validate test.
3. Add the three control-flow tests (auto-advance, escalate-at-max,
   advisory-always-escalates) with a mocked judge score.
4. Write the authoring-guide section: the convention table, the two gating modes,
   the advisory-only override, and the bound. Note the per-iteration-commit
   limitation (commit is not a bare loop-body step) as a stated constraint.
5. Run one live unattended pass against a real slice to sanity-check the fix
   prompt end-to-end.

### Special Considerations

- Do not introduce an `advisory:` flag or any "always-escalate" field — advisory
  is `pass_floor > 100` via the existing step-level `judge:` override. Adding a
  flag fragments the threshold locus slice 301 committed to.
- Keep the bound (`max`) explicit in the reference pipeline; do not document any
  unbounded pattern.
- The `each`-over-slices fan-out (running the cycle across many slices) is
  documentable only against the one registered source (`cf.unfinished_slices`);
  do not imply other `each` sources exist. A fan-out over an arbitrary collection
  is out of scope until a source for it is registered.
- Reuse `test-loop.yaml`'s proven dispatch-then-review body shape; the delta is
  the judge template name and `on_exhaust: checkpoint`, nothing structural.
- The authoring-guide section must state that `pass_floor > 100` is a *sanctioned*
  advisory-only value — call it out so a later "clamp thresholds to 0–100"
  cleanup does not silently disable the always-escalate convention (see the
  advisory-only Note above).
- Use the **fix-first** body shape in the reference pipeline (`loop [fix, judge]`
  with no pre-loop judge). The executor's loop is post-test with per-iteration
  result reset (`executor.py:1109`), so a pre-loop judge cannot short-circuit the
  first iteration — do not write prose implying it can.
