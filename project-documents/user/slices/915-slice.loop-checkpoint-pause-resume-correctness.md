---
docType: slice-design
slice: loop-checkpoint-pause-resume-correctness
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [910, 911]
interfaces: []
dateCreated: 20260812
dateUpdated: 20260813
status: not_started
---

# Slice Design: Loop Checkpoint-Pause Resume Correctness

## Overview

Fixes [issue #48](https://github.com/ecorkran/squadron/issues/48): a `checkpoint`
that fires **inside** a `loop:` body pauses the run mid-iteration, the loop step
is recorded as **completed** anyway, and resume skips the loop entirely —
abandoning every remaining iteration with no warning.

Slice 910 made a loop *converge*. Slice 911 made an iteration *legible*. This
slice makes a paused loop *resumable* — or, failing that, makes the abandonment
loud. Right now it is neither: the run reports `PAUSED`, the human resolves the
checkpoint, resumes, and the pipeline proceeds past the loop as though it had
converged.

The issue left one question open — whether a checkpoint-paused loop *should* be
re-enterable at all. Per 910/911 precedent (resolve deferred questions in the
design, do not defer them twice), that question is answered below in
Technical Decisions, not carried into implementation.

## Value

Correctness of the resume contract for the pipeline's quality-gate construct.

`on-concerns` fires on CONCERNS, FAIL, and UNKNOWN
([actions/checkpoint.py:21-26](src/squadron/pipeline/actions/checkpoint.py#L21-L26)),
so a retry loop configured to pause for human review hits this on its **first
non-passing round** — exactly the case the checkpoint exists to serve. A `loop:`
with `max: 3` can therefore exit after one incomplete iteration, silently, and
the artifacts on disk claim convergence that never happened.

This is a trust defect, not a convenience one. Every downstream guarantee built
on `until: review.pass` — 911's `revision_number:`, 305's findings-addressed
gate — assumes a loop that exits did so because its condition was met. A loop
skipped by resume violates that assumption without recording anything.

## Verified Current Behavior

Traced against `main` at `0b4087a` (20260812). The issue's line citations have
drifted (slices 305 and 173 landed since it was filed); the mechanism is
unchanged and re-confirmed at current lines:

1. **The inner checkpoint pauses the step.** A checkpoint action returns
   `PAUSED`, and `_execute_step_once` propagates it.

2. **The loop short-circuits, preserving the round number.**
   `_execute_loop_body` returns immediately on an inner `PAUSED`
   ([executor.py:1283-1290](src/squadron/pipeline/executor.py#L1283-L1290)),
   abandoning the remaining iterations. Notably it **does** set
   `iteration=iteration` on the returned `StepResult` — the paused round number
   survives.

3. **The top-level walk records the step as complete before checking status.**
   `on_step_complete(step_result)` is called at
   [executor.py:769-770](src/squadron/pipeline/executor.py#L769-L770); the
   `PAUSED` early-return is at
   [executor.py:772](src/squadron/pipeline/executor.py#L772) — two lines *after*.
   `_append_step` appends to `completed_steps` unconditionally
   ([state.py:304](src/squadron/pipeline/state.py#L304)), storing the real status
   (`"paused"`) and the iteration
   ([state.py:296-301](src/squadron/pipeline/state.py#L296-L301)).

4. **Resume treats presence as doneness.** `first_unfinished_step` builds
   `completed = {s.step_name for s in state.completed_steps}` and never inspects
   `StepState.status`
   ([state.py:438-446](src/squadron/pipeline/state.py#L438-L446)). The paused
   loop is in that set, so resume returns the step *after* it.

### Two facts that shape the fix

**`StepState.iteration` is written and never read.** A repo-wide search for
`.iteration` finds the write at [state.py:301](src/squadron/pipeline/state.py#L301)
and no reader anywhere. The state needed to re-enter a loop at the right round
is already persisted — it is simply unused. This slice gives it its first
consumer.

**`start_from` is step-name granular only.** Both resume paths — explicit
`--resume` ([run.py:1102](src/squadron/cli/commands/run.py#L1102)) and implicit
paused-run detection ([run.py:1159](src/squadron/cli/commands/run.py#L1159)) —
funnel through `first_unfinished_step` into `execute_pipeline(start_from=...)`,
which skips whole steps by name
([executor.py:644-650](src/squadron/pipeline/executor.py#L644-L650)). There is no
existing notion of "resume *into* step X at iteration N." That absence is why
re-entry is a design decision rather than a one-line predicate change.

**`first_unfinished_step` has two further callers beyond the resume paths.**
*(Corrected 20260813 during Phase 5 task breakdown; the original draft accounted
for the two resume callers only.)* It is also called at
[run.py:653](src/squadron/cli/commands/run.py#L653) — which **finalizes the run as
`COMPLETED`** when the predicate returns `None` — and at
[run.py:799](src/squadron/cli/commands/run.py#L799), the next-step display path.
The 653 caller is correctness-relevant, not cosmetic: pre-fix, a run containing a
paused step could be finalized as complete by that path. Part A therefore changes
what all four callers observe, and each is audited and tested (tasks 1.5, 1.6).

**`CheckpointState` is write-only.** It is set at
[state.py:310](src/squadron/pipeline/state.py#L310) and read only for display
([run.py:537-539](src/squadron/cli/commands/run.py#L537-L539)). Nothing steers
resume from it.

### Which loops are affected

Any loop whose body contains a checkpoint:

- **Phase-bodied loops** — `PhaseStepType.expand` appends a `checkpoint` action
  unconditionally (defaulting to `never`, commonly configured `on-fail` /
  `on-concerns`). `p45b.yaml` is this shape.
- **Gate-bearing bodies** — `GateStepType.expand` emits `[gate, checkpoint]`
  when `checkpoint:` is set. This is slice 305's target loop shape.
- **`review:` steps carrying their own `checkpoint:`** inside a loop body.

## Technical Scope

**Included:**

- **Part A — a paused step is not a completed step.** `first_unfinished_step`
  distinguishes `PAUSED` from `COMPLETED` so resume returns to the paused step
  rather than past it.
- **Part B — re-entry at the recorded iteration.** `execute_pipeline` accepts a
  resume iteration for the step it starts at, and `_execute_loop_body` begins
  from that round instead of round 1.
- **Part C — the abandonment is observable.** A loop that short-circuits on an
  inner pause logs at WARNING naming the pipeline, step, paused round, and the
  number of rounds not run.

**Excluded:**

- **`on_exhaust: skip` fall-through.** Deferred by 910, still deferred, untouched.
- **Re-entering a paused `each:` / `fan_out:` step at a specific branch.** Those
  paths return a `StepResult` **without** `iteration`
  ([executor.py:1424-1430](src/squadron/pipeline/executor.py#L1424-L1430)), so
  they carry no re-entry coordinate. Part A still fixes their *skipping* (they
  stop being treated as complete); resuming them restarts the step. Recorded as
  a known limitation below rather than silently conflated with the loop case.
- **Changing checkpoint semantics.** What pauses, and on which verdicts, is
  unchanged.
- **Multi-level loop nesting.** Nested `loop:` is already banned by
  `LoopStepType._validate_inner_steps`, so a single resume coordinate is
  sufficient by construction.

## Technical Decisions

### D1 — A checkpoint-paused loop **is** re-enterable (the open question, answered)

The issue framed this as genuinely open: a checkpoint may legitimately mean "a
human is taking over from here," in which case skipping the rest of the loop is
arguably correct.

**Decision: resume re-enters the loop and continues from the paused round.**

Rationale, in the order that decided it:

1. **The `until:` condition is the loop's contract, and a pause is not a verdict.**
   A loop exits for exactly one legitimate reason — `until:` was satisfied — or
   it exhausts and takes its `on_exhaust:` branch. "A human answered a checkpoint
   prompt" is neither. Treating a pause as an exit invents a third exit path
   that no pipeline author declared and no `on_exhaust:` mode describes.

2. **`checkpoint: continue` already means "keep going."** The checkpoint action's
   own resolution vocabulary distinguishes continuing from exiting. A human who
   chose `Continue` at an in-loop checkpoint has said, in the pipeline's own
   language, that the run should proceed — and "proceed" for a loop with rounds
   remaining means the next round, not the next step. The current behavior
   silently overrides an explicit human answer.

3. **"A human is taking over" already has a spelling: `Exit`.** Choosing `Exit`
   at the checkpoint ends the run. That is the escape hatch for the
   human-takes-over reading, and it is unambiguous. Re-entry on resume does not
   remove it.

4. **The alternative cannot be made safe, only loud.** If a pause legitimately
   ended the loop, the honest implementation would still have to record *why*
   the remaining rounds were dropped, and every consumer of `revision_number:`
   and the findings-addressed gate would need to distinguish "converged" from
   "abandoned at round 2 of 3." That is strictly more machinery than resuming,
   for a behavior nobody asked for.

**Consequence for `max:`.** Rounds are counted per loop, not per invocation: a
loop paused at round 2 of `max: 3` resumes at round 2 and may still run rounds 2
and 3. Resume does not grant extra rounds, and it does not restart the count.

*Rejected: make it configurable* (`on_pause: resume | exit` on the loop). Adding
a knob to avoid deciding is the wrong trade at this size — it doubles the
resume-path test surface to serve a mode with no requested use case. If one
appears, the seam is a loop-config field and this decision is its default.

### D2 — Part A: `first_unfinished_step` filters on status, not presence

The predicate becomes "present **and** in a terminal-complete status" rather than
"present." A step whose recorded status is `PAUSED` is unfinished.

```python
# state.py — sketch, not final
_RESUMABLE_STATUSES = {ExecutionStatus.PAUSED.value, ExecutionStatus.FAILED.value}

completed = {
    s.step_name for s in state.completed_steps
    if s.status not in _RESUMABLE_STATUSES
}
```

**`FAILED` is included deliberately.** The top-level walk returns on `FAILED`
([executor.py:780](src/squadron/pipeline/executor.py#L780)) after the same
unconditional append, so a failed step is recorded as complete by the identical
mechanism and resume skips it too — the same bug wearing a different status.
Fixing one and not the other would leave a matched pair half-repaired.

**Status strings are compared against `ExecutionStatus` members, never literals**,
per the project rule on scattered comparison values. `StepState.status` is a
`str` (the serialized `.value`), so the set is built from enum members at one
site.

**No new persisted field.** Status is already stored per step; this reads what
`_append_step` has always written.

*Rejected: stop appending paused steps in `_append_step`.* Tempting — it makes
`completed_steps` honest — but `_append_step` is also what persists the
checkpoint reason, the action results, and the iteration. Dropping the append
would discard the very evidence resume needs. The record is correct; the
*query* was wrong.

*Rejected: reorder `on_step_complete` after the PAUSED check.* Same objection,
plus it would stop persisting the pause for every consumer including
`find_matching_run`'s `status="paused"` lookup, which implicit resume depends on.

### D3 — Part B: one resume coordinate, threaded to the loop only

`execute_pipeline` gains `start_from_iteration: int = 0` alongside the existing
`start_from`. It applies to the `start_from` step **only** — the step resume
re-enters — and is `0` (the established "not in a loop" sentinel from
`ActionContext.iteration` and `_execute_step_once`) everywhere else.

Flow:

```
run.py (--resume / implicit)
  ├─ first_unfinished_step  -> "design-loop"          (Part A: now returns the paused step)
  └─ resume_iteration_for   -> 2                       (new: StepState.iteration, first reader)
       └─ execute_pipeline(start_from="design-loop", start_from_iteration=2)
            └─ _execute_loop_step / _execute_loop_body(start_iteration=2)
                 └─ for iteration in range(start_iteration, max + 1)   # was range(1, max+1)
```

The loop's iteration range is the only behavior change; everything inside a round
is untouched. `start_from_iteration` is clamped to `>= 1` when the target step is
a loop, and ignored (with a DEBUG log) when the target step is not a loop — a
non-loop step has no rounds to re-enter, and an `each`/`fan_out` step records no
iteration to resume from (see Known Limitation).

**Why the coordinate is passed in rather than re-read inside the loop.**
`_execute_loop_body` has no run-state access and should not acquire one for this;
it already receives everything it needs as parameters. Reading state in the CLI
and passing an integer keeps the executor a pure function of its arguments, which
is what makes the existing loop tests constructible without a state file.

**`prior_iteration_step_outputs` on re-entry is empty.** Round *N* resumed from
state does not reconstruct round *N-1*'s in-memory outputs — those live in the
paused run's `action_results`, and rehydrating them is 911/305 territory, not
this slice's. An empty dict is the documented sentinel for "no prior iteration"
([models.py:65-70](src/squadron/pipeline/models.py#L65-L70)), which is exactly
what a resumed round can honestly claim. This is stated in the round contract
(Part C docs), not left to be discovered.

### D4 — Part C: an abandoned round is never silent

Two observable signals, both required, per `.claude/rules/review-code.md`
(failure-mode enumeration):

1. **At pause time** — when a loop short-circuits on an inner `PAUSED`, log at
   WARNING: pipeline, step name, paused iteration, and how many rounds were not
   run (`max - iteration`). Today this returns silently. This applies to **both**
   loop shapes — `_execute_loop_body` (multi-step) and `_execute_loop_step`
   (single-step) — from one shared message source, not two copies.
2. **At resume time** — when resume re-enters a loop at iteration > 1, log at
   INFO naming the step and round, so the run log shows the loop was re-entered
   rather than re-run from scratch.

The pause-time WARNING is the one that matters: it is the signal that would have
made #48 self-reporting instead of silent, and it stays correct even if a future
change to D1 makes abandonment intentional.

## Component Structure

| Component | Change |
|---|---|
| `pipeline/state.py` — `first_unfinished_step` | Filter on status, not presence (Part A) |
| `pipeline/state.py` — `resume_iteration_for` **(new)** | Return the recorded `iteration` for a named step; first reader of `StepState.iteration` (Part B) |
| `pipeline/executor.py` — `execute_pipeline` | New `start_from_iteration: int = 0`; thread to the `start_from` step (Part B) |
| `pipeline/executor.py` — `_execute_loop_step` / `_execute_loop_body` | New `start_iteration: int = 1`; iterate `range(start_iteration, max + 1)` (Part B) |
| `pipeline/executor.py` — `_execute_loop_step` / `_execute_loop_body` | WARNING on inner-pause short-circuit, single-sourced across both paths (Part C) |
| `pipeline/state.py` — `resume_iteration_for` unit tests | Direct coverage of the new reader (Part A) |
| `cli/commands/run.py` | Both resume paths read the iteration and pass it through (Parts A/B); the two display/finalize callers of `first_unfinished_step` are audited (Part A) |
| `docs/PIPELINES.md` | Document checkpoint-in-loop resume semantics and the `max:` counting rule |

## Success Criteria

### Functional Requirements

- A loop with `max: 3` whose body checkpoints on round 1 pauses; on resume, the
  run **re-enters that loop** and continues from round 1 rather than proceeding
  to the next step.
- A loop paused at round 2 of 3 resumes at round 2 and runs at most rounds 2–3 —
  resume neither restarts the count at 1 nor grants extra rounds.
- `first_unfinished_step` returns the paused step itself, not its successor; the
  same holds for a `FAILED` step.
- A loop that short-circuits on an inner pause logs a WARNING naming pipeline,
  step, paused iteration, and rounds not run.
- Resuming a paused **non-loop** step behaves exactly as today (no iteration
  semantics introduced where none existed).
- A run whose steps all completed normally still reports "All steps already
  completed. Nothing to resume." — the Part A predicate must not make finished
  runs look resumable.
- A run containing a paused or failed step is **not** finalized as `COMPLETED` by
  the [run.py:653](src/squadron/cli/commands/run.py#L653) path.
- A resume request for an iteration above the loop's `max:` (only reachable from
  malformed state) **fails loudly** with a WARNING naming step, requested
  iteration, and `max:` — it does not report `COMPLETED` for a loop that ran zero
  rounds, which would re-create the defect class this slice fixes.

### Technical Requirements

- Status comparisons route through `ExecutionStatus` members, never string
  literals scattered at comparison sites.
- New/updated tests in `tests/pipeline/test_state.py` (Part A predicate,
  `resume_iteration_for`), `tests/pipeline/test_executor_loop_body.py`
  (`start_iteration` range, pause WARNING), and a CLI-level resume test
  (end-to-end re-entry) — following existing file organization.
- Each new failure path has a test asserting its observable signal.
- `ruff format --check .`, `ruff check .`, and strict `pyright` clean.

## Verification Walkthrough

*Draft — to be executed and corrected during Phase 6, per 910/911 practice.*

**1. Reproduce the bug before fixing it.** A throwaway pipeline whose loop body
is `[dispatch, review]` with `checkpoint: on-concerns` and `max: 3`, against a
review that returns CONCERNS on round 1:

```bash
sq run <fixture> 999
# pauses at the loop step
sq run --resume <run-id>
```

Pre-fix expectation: resume reports the step *after* the loop and the run
completes, having executed one incomplete round. Confirm this fails as described
before changing code — the same `git stash` discipline 910 used to prove its
tests would have caught the original bug.

**2. Part A — resume returns to the paused step.**

```bash
sq run --status <run-id>
```

The loop step shows status `paused`; resume now names the loop step itself as its
starting point rather than the following step.

**3. Part B — re-entry at the recorded round.** With the checkpoint configured to
fire on round 2, resume and confirm from the run log that the loop re-enters at
iteration 2 (INFO line) and that rounds 2–3 execute — not rounds 1–3, and not
zero rounds.

**4. Part C — the abandonment is loud.** Inspect the run log at the moment of the
original pause: a WARNING naming the pipeline, the loop step, the paused round,
and the count of rounds not run.

**5. Regression — a clean run is unaffected.** A pipeline with no in-loop
checkpoint, run to completion, then `sq run --resume <run-id>`, must still report
"All steps already completed. Nothing to resume."

**6. The finalizer does not mark a paused run complete.** *(Added 20260813 —
covers the [run.py:653](src/squadron/cli/commands/run.py#L653) caller the original
draft did not account for.)* With the run from step 1 still paused, exercise the
status/finalize path and confirm the run is **not** written to state as
`COMPLETED`. Pre-fix, the predicate returned `None` for that run and the finalize
branch was reachable; post-fix it returns the paused loop step and the branch is
not taken. Confirm against the persisted state file, not only the console output —
this is the one hazard in this slice that changes a stored outcome.

**7. The single-step loop shape behaves identically.** Steps 1–4 use a multi-step
loop body (`[dispatch, review]`, exercising `_execute_loop_body`). Repeat the
pause, the WARNING check, and the re-entry check against a **single-step** loop
body, which routes through `_execute_loop_step` instead. Both paths carry their
own round range and their own inner-pause short-circuit, so a fix verified on only
one shape is verified on half the surface.

**8. A failed step resumes too.** Part A treats `FAILED` and `PAUSED` alike
(design D2). Run a pipeline to a step failure, then `sq run --resume <run-id>`,
and confirm resume returns to the failed step rather than past it. This path has
no checkpoint involved and is easy to leave untested precisely because #48 was
reported as a pause bug.

## Known Limitation

**`each:` / `fan_out:` steps resume by restart, not re-entry.** Those paths return
their `StepResult` without an `iteration`
([executor.py:1424-1430](src/squadron/pipeline/executor.py#L1424-L1430)), so no
per-branch resume coordinate is recorded. Part A stops them from being *skipped*
(a strict improvement over today's silent skip); Part B cannot re-enter them
mid-fan-out, so a resumed `each:` step re-runs its branches from the start.

This is recorded rather than fixed because re-entering a fan-out needs a
per-branch completion record, which is a different and larger data-model change
than a single iteration integer. Worth a follow-up issue if a pipeline puts a
checkpoint inside an `each:` body; no shipped pipeline does today.

## Risk Assessment

**Changing `first_unfinished_step` changes resume for every pipeline, not just
looping ones.** It is the single predicate behind both resume paths — and behind
two further callers (see Verified Current Behavior): the next-step display at
[run.py:799](src/squadron/cli/commands/run.py#L799) and the run finalizer at
[run.py:653](src/squadron/cli/commands/run.py#L653). The blast radius is four
call sites, not two.

Two distinct hazards:

1. A run that previously reported "nothing to resume" now offers to re-run a
   failed step. That is the intended fix, but it is a behavior change visible to
   anyone with paused runs on disk, bounded by the regression test in
   Verification step 5.
2. The 653 finalizer stops marking runs `COMPLETED` when a paused or failed step
   is present. This is also the intended fix — such runs were never complete —
   but it changes a *persisted* outcome, not just a displayed one, so it is
   audited and tested explicitly rather than assumed benign.

**Mitigation:** land Part A with its own tests and commit before Parts B/C, so a
bisect can separate "resume returns to paused steps" from "loops re-enter at a
round."

## Implementation Notes

### Development Approach

Sequence: **A → C → B.**

- **A first** — the predicate fix is independently correct and independently
  valuable: without it, no amount of iteration threading is reachable, because
  resume never returns to the loop at all.
- **C second** — the WARNING is two lines and makes the bug self-reporting during
  the rest of the work; having it in place while building Part B means every
  manual run narrates what it abandoned.
- **B last** — the largest change and the only one that touches the executor's
  signature.

Effort: Part A 1/5, Part B 2/5, Part C 1/5. Overall **2/5**.
