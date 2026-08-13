---
docType: tasks
slice: loop-checkpoint-pause-resume-correctness
project: squadron
lldReference: project-documents/user/slices/915-slice.loop-checkpoint-pause-resume-correctness.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: [910, 911]
status: not_started
dateCreated: 20260813
dateUpdated: 20260813
---

# Tasks: Loop Checkpoint-Pause Resume Correctness

## Context Summary

Fixes [issue #48](https://github.com/ecorkran/squadron/issues/48). A `checkpoint`
firing **inside** a `loop:` body pauses the run mid-iteration, the loop step is
recorded as completed anyway, and resume skips the loop — abandoning every
remaining round silently.

Three parts, sequenced **A → C → B** per the design's Implementation Notes:

- **Part A** — a paused (or failed) step is not a completed step, so
  `first_unfinished_step` returns *to* it rather than past it.
- **Part C** — the abandonment is observable (WARNING at pause, INFO at re-entry).
- **Part B** — re-entry at the recorded round: `execute_pipeline` accepts a
  resume iteration and the loop starts there instead of round 1.

Part A lands and commits alone (design Risk Assessment: it changes resume for
every pipeline, so a bisect must be able to separate it from B/C).

### Verified code anchors (traced on `ec6f4e7`, 20260813)

| Anchor | Location |
|---|---|
| `first_unfinished_step` — presence-only predicate | [state.py:438-445](src/squadron/pipeline/state.py#L438-L445) |
| `_append_step` writes `iteration` (no reader today) | [state.py:301](src/squadron/pipeline/state.py#L301) |
| `StepState.iteration` field | [state.py:89](src/squadron/pipeline/state.py#L89) |
| `execute_pipeline` signature | [executor.py:497](src/squadron/pipeline/executor.py#L497) |
| `_execute_loop_step` (single-step body) | [executor.py:1077](src/squadron/pipeline/executor.py#L1077) |
| `_execute_loop_body` (multi-step body) | [executor.py:1165](src/squadron/pipeline/executor.py#L1165) |
| Hardcoded round ranges — **both** loop paths | [executor.py:1114](src/squadron/pipeline/executor.py#L1114), [executor.py:1229](src/squadron/pipeline/executor.py#L1229) |
| Inner-`PAUSED` silent short-circuit | [executor.py:1283-1290](src/squadron/pipeline/executor.py#L1283-L1290) |

### Deviation from the design document

The design states `first_unfinished_step` has **two** callers. It has **four**:

- [run.py:653](src/squadron/cli/commands/run.py#L653) — `--status` / completion finalize path
- [run.py:799](src/squadron/cli/commands/run.py#L799) — "next step" display path
- [run.py:1102](src/squadron/cli/commands/run.py#L1102) — explicit `--resume`
- [run.py:1159](src/squadron/cli/commands/run.py#L1159) — implicit paused-run detection

The two display/finalize callers were not in the design's Component Structure.
Task 1.5 audits them explicitly — the predicate change alters what they report,
and the 653 caller *finalizes a run as COMPLETED* when the predicate returns
`None`, which is a correctness-relevant path, not cosmetic.

Similarly, the design's Part B names only `_execute_loop_body`; the single-step
`_execute_loop_step` path has the identical hardcoded range and is included.

---

## Part A — A Paused Step Is Not a Completed Step

### Task 1.1 — Add `_RESUMABLE_STATUSES` and filter `first_unfinished_step` on status

- [ ] Effort: 1/5
- [ ] In [state.py](src/squadron/pipeline/state.py), define a module-level
      `_RESUMABLE_STATUSES` built from `ExecutionStatus` members — **not** string
      literals — containing `PAUSED` and `FAILED`.
- [ ] `StepState.status` is a `str` holding the serialized `.value`, so the set
      must hold `.value` strings produced from the enum members at that one site.
- [ ] Change `first_unfinished_step` ([state.py:441](src/squadron/pipeline/state.py#L441))
      so `completed` excludes any `StepState` whose `status` is in
      `_RESUMABLE_STATUSES`.
- [ ] Add a short comment stating why `FAILED` is included: the top-level walk
      returns on `FAILED` after the same unconditional `_append_step`, so a failed
      step is recorded complete by the identical mechanism (design D2).

**Success criteria:** a run whose loop step recorded `status="paused"` causes
`first_unfinished_step` to return that loop step's name. A run whose steps all
recorded `completed` still returns `None`. No string status literal appears at a
comparison site.

### Task 1.2 — Test the Part A predicate

- [ ] Effort: 1/5
- [ ] Add tests to [tests/pipeline/test_state.py](tests/pipeline/test_state.py)
      following that file's existing state-construction pattern.
- [ ] Case: step recorded `PAUSED` → predicate returns that step's name, not its
      successor.
- [ ] Case: step recorded `FAILED` → predicate returns that step's name.
- [ ] Case: all steps recorded `COMPLETED` → predicate returns `None`
      (guards the "All steps already completed. Nothing to resume." regression
      named in the design's Success Criteria).
- [ ] Case: a paused step followed by later completed steps → predicate returns
      the *paused* step, proving it does not merely return the last gap.

**Success criteria:** all four cases pass; each fails if the Task 1.1 filter is
reverted.

### Task 1.3 — Add `resume_iteration_for` to `StateManager`

- [ ] Effort: 1/5
- [ ] Add `resume_iteration_for(run_id: str, step_name: str) -> int` to
      `StateManager` in [state.py](src/squadron/pipeline/state.py).
- [ ] Return the recorded `iteration` for the named step from
      `state.completed_steps`; return `0` when the step is absent or its recorded
      iteration is `0`. `0` is the established "not in a loop" sentinel
      (`ActionContext.iteration`, `_execute_step_once`).
- [ ] If a step name appears more than once in `completed_steps`, return the
      **last** occurrence's iteration — that is the most recent record.
- [ ] Docstring notes this is the first reader of `StepState.iteration`
      ([state.py:89](src/squadron/pipeline/state.py#L89)).

**Success criteria:** returns the persisted round for a paused loop step; returns
`0` for an unknown step name and for a non-loop step.

### Task 1.4 — Test `resume_iteration_for`

- [ ] Effort: 1/5
- [ ] Add tests to [tests/pipeline/test_state.py](tests/pipeline/test_state.py),
      following the Task 1.2 pattern in that file.
- [ ] Case: a paused loop step recorded at iteration 2 → returns `2`.
- [ ] Case: unknown step name → returns `0`.
- [ ] Case: a non-loop step (recorded iteration `0`) → returns `0`.
- [ ] Case: the same step name appearing twice in `completed_steps` → returns the
      **last** occurrence's iteration, not the first.

**Success criteria:** each branch of Task 1.3's contract is asserted directly.
The end-to-end test in Task 3.6 exercises only the happy path, so this unit test
is what catches a first-vs-last or absent-vs-zero regression.

### Task 1.5 — Audit the two non-resume `first_unfinished_step` callers

- [ ] Effort: 1/5
- [ ] Read [run.py:653](src/squadron/cli/commands/run.py#L653) (finalize-on-`None`)
      and [run.py:799](src/squadron/cli/commands/run.py#L799) (next-step display).
- [ ] Confirm the 653 path does **not** now finalize a run as `COMPLETED` that
      contains a paused or failed step. Before Task 1.1 the predicate returned
      `None` for such a run; after it, it returns the paused step, so the
      finalize branch is no longer reached — verify this is the case and not
      merely assumed.
- [ ] Confirm the 799 display path reports the paused step as "next" rather than
      its successor, and that its surrounding copy still reads correctly.
- [ ] If either path needs an adjustment, make the minimal one and note it here.
      If neither does, record that finding in the task checklist.

**Success criteria:** both callers are read and their post-change behavior is
stated explicitly — no caller of the changed predicate is left unexamined.

### Task 1.6 — Test the non-resume callers at CLI level

- [ ] Effort: 2/5
- [ ] Add a test covering the 653 finalize path: a run state containing a paused
      step must not be finalized as `COMPLETED`.
- [ ] Add a test covering the 799 display path: the reported next step is the
      paused step.
- [ ] Place these with the existing CLI-level run tests, following current file
      organization.

**Success criteria:** both tests fail against pre-Task-1.1 behavior and pass after.

### Task 1.7 — Verify, format, and commit Part A alone

- [ ] Effort: 1/5
- [ ] Run `ruff format .`, then `ruff check .`, then strict `pyright` — all clean.
- [ ] Run the full test suite; no regressions.
- [ ] Commit Part A on its own (design Risk Assessment: a bisect must separate
      "resume returns to paused steps" from "loops re-enter at a round").
- [ ] Suggested message: `fix: return resume to paused and failed steps`

**Success criteria:** Part A is a standalone commit on the slice branch with a
green suite.

---

## Part C — The Abandonment Is Never Silent

### Task 2.1 — WARNING when a multi-step loop body short-circuits on inner pause

- [ ] Effort: 1/5
- [ ] At the inner-`PAUSED` short-circuit in `_execute_loop_body`
      ([executor.py:1283-1290](src/squadron/pipeline/executor.py#L1283-L1290)),
      log at WARNING before returning.
- [ ] The message must name: pipeline name, loop step name, the paused iteration,
      and the number of rounds not run (`loop_config.max - iteration`).
- [ ] Use the module logger and lazy `%s` formatting, matching the file's existing
      logging style.

**Success criteria:** pausing inside a multi-step loop body emits one WARNING
carrying all four fields.

### Task 2.2 — Same WARNING for the single-step loop path

- [ ] Effort: 1/5
- [ ] `_execute_loop_step` ([executor.py:1077](src/squadron/pipeline/executor.py#L1077))
      is the single-step-body sibling and has its own inner-pause handling.
      Locate its short-circuit and give it the same WARNING.
- [ ] Do not duplicate the message string at two sites — extract one small helper
      (or one shared constant) used by both paths, per the project's
      no-scattered-values rule.

**Success criteria:** both loop shapes emit the identical, single-sourced WARNING
on inner-pause abandonment.

### Task 2.3 — Test the pause-time WARNING

- [ ] Effort: 2/5
- [ ] Add tests to
      [tests/pipeline/test_executor_loop_body.py](tests/pipeline/test_executor_loop_body.py)
      using `caplog`.
- [ ] Case: multi-step body pauses at round 1 of `max: 3` → exactly one WARNING,
      containing the step name, `1`, and a rounds-not-run count of `2`.
- [ ] Case: single-step body pauses → the same WARNING is emitted.
- [ ] Case: a loop that converges normally emits **no** such WARNING.

**Success criteria:** the observable signal is asserted, not just the return
status (`.claude/rules/review-code.md`, failure-mode enumeration).

### Task 2.4 — Format and commit Part C

- [ ] Effort: 1/5
- [ ] `ruff format .`, `ruff check .`, strict `pyright` clean; suite green.
- [ ] Commit. Suggested message: `fix: warn when a loop abandons rounds on pause`

**Success criteria:** Part C is committed before Part B begins, so manual runs
during Part B narrate what they abandon.

---

## Part B — Re-Entry at the Recorded Iteration

### Task 3.1 — Thread `start_iteration` through both loop executors

- [ ] Effort: 2/5
- [ ] Add `start_iteration: int = 1` to `_execute_loop_body`
      ([executor.py:1165](src/squadron/pipeline/executor.py#L1165)) and to
      `_execute_loop_step` ([executor.py:1077](src/squadron/pipeline/executor.py#L1077)).
- [ ] Change **both** hardcoded ranges — [executor.py:1114](src/squadron/pipeline/executor.py#L1114)
      and [executor.py:1229](src/squadron/pipeline/executor.py#L1229) — from
      `range(1, loop_config.max + 1)` to `range(start_iteration, loop_config.max + 1)`.
- [ ] Nothing inside a round changes. `prior_iteration_step_outputs` starts empty
      on a resumed round — that is the documented "no prior iteration" sentinel
      ([models.py:65-70](src/squadron/pipeline/models.py#L65-L70)), per design D3.

**Success criteria:** `start_iteration=2` with `max: 3` runs rounds 2 and 3 only;
the default `1` reproduces today's behavior exactly for both loop shapes.

### Task 3.2 — Test the `start_iteration` range on both loop paths

- [ ] Effort: 2/5
- [ ] In [tests/pipeline/test_executor_loop_body.py](tests/pipeline/test_executor_loop_body.py):
      `start_iteration=2`, `max: 3` → exactly two rounds execute, numbered 2 and 3.
- [ ] `start_iteration=1` (default) → unchanged from current behavior.
- [ ] `start_iteration == max` → exactly one round runs.
- [ ] `start_iteration > max` → zero rounds run. This is only reachable from
      malformed resume state (a recorded iteration above the loop's `max:`).
      Do **not** let the status fall out of an empty range: treat it as a
      **failure**, not a silent success — returning `COMPLETED` for a loop that
      ran no rounds would re-create the exact class of bug this slice fixes
      (a loop reporting doneness it never reached). Log at WARNING naming the
      step, the requested iteration, and `max:`.
- [ ] Assert both the returned status and the WARNING for that case.
- [ ] Cover the single-step (`_execute_loop_step`) path as well as the multi-step
      one.

**Success criteria:** round numbers observed in the results match the requested
range on both paths.

### Task 3.3 — Add `start_from_iteration` to `execute_pipeline`

- [ ] Effort: 2/5
- [ ] Add `start_from_iteration: int = 0` to `execute_pipeline`
      ([executor.py:497](src/squadron/pipeline/executor.py#L497)) — additive with a
      non-breaking default.
- [ ] It applies to the `start_from` step **only**; every other step uses the
      normal start.
- [ ] When the target step is a loop: clamp to `>= 1` before passing as
      `start_iteration`.
- [ ] When the target step is **not** a loop: ignore it and log at DEBUG that it
      was ignored, naming the step (design D3).
- [ ] Emit the resume-time INFO when re-entering a loop at iteration > 1, naming
      the step and the round (design D4 signal 2).

**Success criteria:** a non-loop `start_from` behaves exactly as today; a loop
`start_from` with an iteration re-enters at that round and says so at INFO.

### Task 3.4 — Test `execute_pipeline` iteration threading

- [ ] Effort: 2/5
- [ ] Add tests to
      [tests/pipeline/test_executor_loop_body.py](tests/pipeline/test_executor_loop_body.py).
      That file already imports and drives `execute_pipeline` directly and is the
      loop-focused suite, so `start_from_iteration` coverage belongs there rather
      than in the general `test_executor.py`.
- [ ] Case: `start_from` a loop step with `start_from_iteration=2` → the loop runs
      rounds 2+ and an INFO naming step and round is emitted.
- [ ] Case: `start_from` a non-loop step with a non-zero iteration → behavior
      identical to `start_from_iteration=0`, and a DEBUG "ignored" line is logged.
- [ ] Case: `start_from_iteration=0` on a loop step → clamps to round 1.
- [ ] Case: steps before `start_from` are still skipped, unchanged.

**Success criteria:** each branch of the D3 rule (clamp, ignore-with-DEBUG,
apply-to-target-only) has an assertion on its observable signal.

### Task 3.5 — Wire both resume paths in `run.py`

- [ ] Effort: 2/5
- [ ] Explicit `--resume` ([run.py:1102](src/squadron/cli/commands/run.py#L1102)):
      after `first_unfinished_step` returns the step name, call
      `resume_iteration_for` (Task 1.3) for that step and pass the result as
      `start_from_iteration` to `execute_pipeline`.
- [ ] Implicit paused-run detection ([run.py:1159](src/squadron/cli/commands/run.py#L1159)):
      the identical treatment.
- [ ] Do not duplicate the lookup logic between the two paths — both read the
      iteration the same way from one helper.

**Success criteria:** both resume entry points supply the recorded round; neither
carries its own copy of the lookup.

### Task 3.6 — End-to-end CLI resume test

- [ ] Effort: 3/5
- [ ] Add a CLI-level test: a pipeline whose loop body is `[dispatch, review]`
      with `checkpoint: on-concerns` and `max: 3`, against a review returning
      CONCERNS on round 1.
- [ ] Assert the run pauses at the loop step and the persisted `StepState` records
      `status="paused"` with the correct `iteration`.
- [ ] Assert that resume **re-enters the loop** rather than proceeding to the next
      step.
- [ ] Assert the `max:` counting rule: a loop paused at round 2 of 3 resumes at
      round 2 and runs at most rounds 2–3 — resume neither restarts the count nor
      grants extra rounds (design Success Criteria).
- [ ] Assert the clean-run regression: a fully completed run still reports
      "All steps already completed. Nothing to resume."

**Success criteria:** the end-to-end contract from the design's Success Criteria
is asserted at CLI level, not just at unit level.

### Task 3.7 — Format and commit Part B

- [ ] Effort: 1/5
- [ ] `ruff format .`, `ruff check .`, strict `pyright` clean; full suite green.
- [ ] Commit. Suggested message: `fix: resume re-enters a paused loop at its round`

**Success criteria:** all three parts are on the slice branch as separable commits.

---

## Verification and Close-Out

### Task 4.1 — Execute the design's Verification Walkthrough

- [ ] Effort: 3/5
- [ ] Run all **eight** steps of the Verification Walkthrough in the slice design
      (§ Verification Walkthrough), which is marked *draft — to be executed and
      corrected during Phase 6*. Steps 6–8 were added 20260813 to cover the
      finalize caller, the single-step loop shape, and the `FAILED` resume path.
- [ ] Step 1 requires reproducing the bug **before** the fix. If Part A is already
      committed, reproduce against the pre-fix commit rather than skipping the
      step — 910's practice was to prove the tests would have caught the original
      bug.
- [ ] Step 6 must be confirmed against the **persisted state file**, not console
      output alone — it is the only check in this slice covering a changed stored
      outcome.
- [ ] Correct the walkthrough text in the design document wherever reality differs
      from the draft. Do not leave a walkthrough that was never run.
- [ ] Verify the design's corrected claims still hold against the code as
      implemented: the four `first_unfinished_step` callers, and both loop paths
      carrying the round range and the inner-pause short-circuit. If Phase 6 moves
      any of these, update the design's Verified Current Behavior, Component
      Structure, and Risk Assessment rather than leaving cited lines stale.

**Success criteria:** all eight steps executed; the design's walkthrough section
reflects what actually happened; no cited line number in the design points
somewhere else by the end of the slice.

### Task 4.2 — Document resume semantics in `docs/PIPELINES.md`

- [ ] Effort: 1/5
- [ ] Document that a checkpoint pausing inside a loop body resumes **into** that
      loop at the paused round.
- [ ] Document the `max:` counting rule: rounds are counted per loop, not per
      invocation — resume does not restart the count and does not grant extra rounds.
- [ ] Document the round contract on re-entry: `prior_iteration_step_outputs` is
      empty for a resumed round (design D3), so a resumed round cannot read the
      previous round's outputs.
- [ ] Document the known limitation: `each:` / `fan_out:` steps resume by
      **restart**, not re-entry.

**Success criteria:** the semantics a pipeline author needs are written down, not
only encoded in the executor.

### Task 4.3 — File the `each:` / `fan_out:` follow-up issue

- [ ] Effort: 1/5
- [ ] File a GitHub issue for per-branch re-entry of paused `each:` / `fan_out:`
      steps, citing [executor.py:1424-1430](src/squadron/pipeline/executor.py#L1424-L1430)
      (these return `StepResult` without an `iteration`, so no resume coordinate
      exists).
- [ ] Note that slice 915 Part A improved these from *silently skipped* to
      *restarted from the top*, and that re-entry needs a per-branch completion
      record — a larger data-model change.
- [ ] Reference issue #48 and this slice.

**Success criteria:** the known limitation is tracked, not just described in a
design document.

### Task 4.4 — DEVLOG, CHANGELOG, and slice close-out

- [ ] Effort: 1/5
- [ ] Write a DEVLOG entry per `prompt.ai-project.system.md` § Session State Summary.
- [ ] Add a short user-facing CHANGELOG bullet (technical detail belongs in DEVLOG).
- [ ] Close [issue #48](https://github.com/ecorkran/squadron/issues/48) with a
      comment naming the fixing commits.
- [ ] Mark slice 915 complete in the slice design and in
      `900-slices.maintenance-and-refactoring.md`.
- [ ] Merge the slice branch into the integration target
      (`cf config get git.integration_branch`, or `main` if unset).

**Success criteria:** the slice is closed in the plan, the issue is closed, and
the branch is merged into the correct target.
