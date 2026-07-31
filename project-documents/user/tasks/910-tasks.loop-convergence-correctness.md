---
docType: tasks
slice: loop-convergence-correctness
project: squadron
lld: user/slices/910-slice.loop-convergence-correctness.md
dependencies: []
projectState: >
  Slice 910 design complete, review-addressed (CONCERNS resolved: key-naming,
  step_outputs interaction, and expand() purity all traced and resolved in
  the design rather than deferred to implementation). Three independent
  defects on the loop: execution path: Part B ambiguous multi-review until:
  gating (#43), Part A findings-feedback gap (#42), Part C --dry-run loop-body
  expansion (#45). Not yet branched.
dateCreated: 20260731
dateUpdated: 20260731
status: not_started
---

## Context Summary

- Working on the **loop-convergence-correctness** slice (910), a maintenance
  slice fixing three defects on the `loop:` execution path, all sharing
  `_execute_loop_body` (`executor.py:1249-1360`) and/or one test file
  (`tests/pipeline/test_executor_loop_body.py`). Parent:
  `900-slices.maintenance-and-refactoring.md`.
- **Part B (#43, High):** `_last_with_verdict` gates a loop's `until:` on
  whichever verdict-bearing action is *last* in the body, so a loop with two
  reviews can exit successfully while an earlier review actually failed. Fix:
  reject the ambiguous shape at validation time — never resolve it — since
  the correct pattern is one dispatch + one review per loop body.
- **Part A (#42, High):** loop iterations never see each other's results —
  `_execute_loop_body` passes the same outer `prior_outputs` into every
  iteration, so `DispatchAction._resolve_prompt_from_prior_review` (already
  correct and shipped) never receives real findings to feed back. Fix:
  accumulate each iteration's results into a running `prior_outputs` copy.
- **Part C (#45, Low):** `sq run --dry-run` renders a `loop:` step as one
  opaque line with no body, `max`, `until`, or `on_exhaust`. Fix: expand it,
  matching the `unpack_inner_steps` + indented-listing approach.
- **Order: B → A → C.** Part B establishes the one-verdict-per-body invariant
  Part A's tests assert against. Part C is fully independent and could move
  anywhere, but follows the same B→A precedent for consistency.
- **`p45b.yaml`** (referenced throughout the design's Success Criteria and
  Verification Walkthrough) is a real pipeline, confirmed present at
  `~/.config/squadron/pipelines/p45b.yaml` — squadron's user pipeline
  directory (`loader.py:23`, `_USER_DIR`), which `load_pipeline`/`sq run`
  discover automatically. No task in this file creates or moves it; it is
  used as-is by its bare name (`p45b.yaml`) in Part B/C tasks exactly as the
  design's walkthrough specifies. It uses two sequential single-review loops
  (design→review, then tasks→review) — the shape Part B's rejection is
  designed to require.
- **Known deferred issue (`on_exhaust: skip` fall-through)** is documented in
  the slice design as explicitly out of scope for all three parts below — no
  task in this file addresses it.

---

## Part B — Ambiguous `until:` With Multiple Verdict-Bearing Actions (#43, do first)

- [x] **T1. Add the multi-verdict validation check to `LoopStepType.validate()`**
  - [x] In `src/squadron/pipeline/steps/loop.py`, add a new private helper
    (e.g. `_validate_verdict_count`) called from `validate()` alongside the
    existing `_validate_inner_steps` call, gated on `until_val is not None`
    and `steps_val` being a valid non-empty list (i.e. only run this check
    when the existing shape checks above it already passed).
  - [x] Convert the raw `steps:` list to `StepConfig` objects via the
    already-imported `unpack_inner_steps` helper (mirrors `inner_steps()`,
    loop.py:161-166).
  - [x] For each inner `StepConfig`, resolve its step type via
    `get_step_type(inner.step_type)` and call `.expand(inner)` to get its
    `(action_type, config)` list — this mirrors what the executor does at
    runtime (`_execute_loop_body`, executor.py:1300-1302) and is confirmed
    safe: every `expand()` reachable inside a loop body (`compact`,
    `devlog`, `dispatch`, `gate`, `phase`, `review`, `summary`) is a pure
    dict transform with no I/O (see slice design, Part B "purity confirmed").
  - [x] Count actions with `action_type in ("review", "gate")` across the
    full expanded body (these are the two verdict-producing action types;
    confirmed in the design's Part B "Problem" section).
  - [x] If the count is `> 1`, append one `ValidationError` naming every
    offending inner step (by name and index) and suggesting the fix in the
    message text: split into sequential loops, one review/gate per loop body.
  - [x] If the count is `0` or `1`, no error — this check must not affect any
    currently-valid single-verdict loop body, with or without `until:`.
  - [x] **Success:** a loop body with `until:` set and two verdict-bearing
    inner steps produces exactly one `ValidationError` naming both steps; a
    loop body with `until:` set and exactly one verdict-bearing inner step
    (the existing shape, e.g. `judge-cycle.yaml`, `test-loop.yaml`) produces
    no new errors; a loop body with **no** `until:` and two verdict-bearing
    inner steps also produces no error from this check (scoped to the
    ambiguous case only, per the design).
  - Effort: 3/5

- [x] **T2. Test the multi-verdict validation check** *(test-with T1)*
  - [x] Add tests to `tests/pipeline/steps/test_loop.py`, following the
    existing `test_*_produces_error` naming pattern used for the other
    `LoopStepType.validate()` checks in that file: (a) two `review:` inner
    steps + `until: review.pass` → error naming both; (b) one `phase:` step
    with inline `review:` followed by a bare `review:` step + `until:` set →
    error (proves the check inspects expanded actions, not step-type names —
    this is the case the design calls out explicitly); (c) two verdict
    inner steps but **no** `until:` set → no error; (d) exactly one
    verdict-bearing inner step + `until:` set → no error (regression guard
    for the existing single-review shape).
  - [x] Add one test to `tests/pipeline/test_loop_validation.py` (which
    exercises the full `validate_pipeline()` path, not just
    `LoopStepType.validate()` directly, per that file's existing pattern) —
    a pipeline containing a `loop:` step with two reviews and `until:` set
    fails `validate_pipeline()` with a message naming both steps.
  - [x] **Success:** all cases pass; case (b) specifically proves the check
    is not a step-type-name match.
  - Effort: 2/5

- [x] **T3. Validate `p45b.yaml` against the new check**
  - [x] Run `sq run --validate p45b.yaml` against the real pipeline at
    `~/.config/squadron/pipelines/p45b.yaml` (two sequential single-review
    loops — see Context Summary). Confirm it **passes** validation — the new
    check must not produce a false positive on this already-correct shape.
  - [x] This is a manual confirmation step, not a new automated test (the
    automated regression coverage for "one verdict-bearing action passes" is
    already T2d); record the actual command output in the commit message or
    task notes.
  - [x] **Success:** `sq run --validate p45b.yaml` exits 0.
  - Effort: 1/5

- [x] **T4. Commit Part B**
  - [x] `ruff format`, run Part B tests (T2), then commit
    (`fix: reject loop bodies with ambiguous multi-review until: gating`).
  - [x] Reference issue #43 in the commit body.
  - Effort: 1/5

---

## Part A — Findings Feedback Between Iterations (#42)

- [x] **T5. Accumulate per-iteration `prior_outputs` in `_execute_loop_body`**
  - [x] In `src/squadron/pipeline/executor.py`, in `_execute_loop_body`
    (~line 1298), introduce a `running_prior = dict(prior_outputs)` snapshot
    before the `for iteration in range(...)` loop, mirroring the existing
    `step_prior = dict(prior_outputs)` pattern in `_execute_step_once`
    (executor.py:1030).
  - [x] Pass `running_prior` (not the original `prior_outputs` parameter)
    into each `_execute_step_once` call inside the iteration loop.
  - [x] After each inner step's call returns, update `running_prior` from
    that call's `inner_result.action_results`, keyed exactly as
    `_execute_step_once` already keys its own `step_prior`:
    `f"{action_type}-{action_index}"`, where `action_index` is the result's
    position within that one inner step's own action list (not a running
    counter across the whole iteration). Confirmed safe to let same-key
    writes overwrite across iterations — see design's Part A "Key naming —
    resolved" for why no iteration-number qualifier is needed, made possible
    by Part B (T1-T4) already landing and banning the one shape that would
    make this collide within a single iteration.
  - [x] Do **not** modify `step_outputs` handling in this task — traced and
    confirmed disjoint from `prior_outputs` in the design (Part A
    "`step_outputs` interaction — resolved"); no change needed here.
  - [x] **Success:** iteration 2's `ActionContext.prior_outputs` (as seen by
    its `dispatch` action) contains the `review` result from iteration 1,
    not just whatever was in `prior_outputs` before the loop started.
  - Effort: 2/5

- [x] **T6. Test findings-feedback across iterations** *(test-with T5)*
  - [x] Add a test to `tests/pipeline/test_executor_loop_body.py`, following
    the existing helpers in that file (`_action_result`, `_mock_action`,
    `_mock_step_type`, `_loop_step`, `_pipeline`, `execute_pipeline(...,
    _action_registry=...)`): construct a loop body of `dispatch` + `review`
    where the `dispatch` mock's `execute` is an `AsyncMock` capturing its
    `ActionContext` argument (via `side_effect` or by inspecting
    `call_args_list` after the run), and the `review` mock returns FAIL with
    a specific finding on iteration 1, PASS on iteration 2.
  - [x] Assert the dispatch action's `ActionContext.prior_outputs` on the
    **second** call contains the iteration-1 review's `ActionResult`
    (matching on `action_type == "review"` and the finding content), proving
    the loop is feeding results forward — not merely that the loop completed
    in 2 iterations (which the existing `test_loop_body_retries_to_pass_on_
    iteration_3` already covers and does not by itself prove this fix).
  - [x] **Success:** the new test fails against pre-fix code (i.e. confirm it
    would have caught the original bug — run it against a stashed/reverted
    `_execute_loop_body` if convenient, or reason through why the assertion
    depends on the fix) and passes after T5.
  - Effort: 2/5

- [x] **T7. Verify `DispatchAction` findings-feedback end-to-end with a real prompt**
  - [x] Extend or add to the T6 test (or a adjacent one in the same file) to
    assert on the **prompt text** actually resolved for iteration 2's
    dispatch — i.e. that `DispatchAction._resolve_prompt_from_prior_review`
    (already-shipped code, unchanged by this slice) produces a prompt
    containing the iteration-1 finding's `summary` text. This closes the gap
    between "prior_outputs contains the result" (T6) and "the consumer
    actually turns it into the right prompt" (this task) — both are called
    out separately in the design's Success Criteria and Verification
    Walkthrough.
  - [x] **Success:** the resolved prompt string for iteration 2 contains the
    iteration-1 finding's summary text; iteration 1's prompt does not
    (nothing to feed back yet).
  - Effort: 1/5

- [x] **T8. Commit Part A**
  - [x] `ruff format`, run Part A tests (T6, T7), then commit
    (`fix: feed loop iteration findings into next iteration's prior_outputs`).
  - [x] Reference issue #42 in the commit body.
  - Effort: 1/5

---

## Part C — `--dry-run` Loop-Body Expansion (#45)

- [ ] **T9. Expand `loop:` steps in `--dry-run` output**
  - [ ] In `src/squadron/cli/commands/run.py`, in the `--dry-run` rendering
    loop (~lines 982-983), add a branch for `step.step_type == "loop"`:
    after printing the loop step's own `name (loop)` line, print `max`,
    `until` (or an explicit "no until — completes after first iteration"
    string when absent), and `on_exhaust` read from `step.config`.
  - [ ] Expand the loop's inner steps via the existing `unpack_inner_steps`
    helper on `step.config.get("steps", [])` and print each on an indented
    line in the same `name (step_type)` format used for top-level steps —
    matching the example format in the slice design's Part C section.
  - [ ] No new abstraction: this is a single `if` branch inside the existing
    render loop, not a new rendering function or class, per the design's
    explicit "no new step-type-specific rendering abstraction" note.
  - [ ] **Success:** `sq run --dry-run` on a pipeline with a `loop:` step
    shows the body's inner steps, `max`, `until`, and `on_exhaust`, indented
    under the loop step's own line.
  - Effort: 2/5

- [ ] **T10. Test `--dry-run` loop expansion** *(test-with T9)*
  - [ ] Add a test to `tests/cli/commands/test_run.py`, following the
    existing `test_dry_run_via_cli_produces_no_state` pattern (patch
    `squadron.cli.commands.run.load_pipeline` and `validate_pipeline`,
    invoke via `runner.invoke(app, ["run", "--dry-run", ...])`, assert on
    `result.output`): construct a `PipelineDefinition` with a `loop:` step
    whose config includes `max`, `until`, `on_exhaust`, and a `steps:` body
    of 2+ inner steps. Assert the CLI output contains each inner step's name
    and type, plus the `max`/`until`/`on_exhaust` values — not just the bare
    `loop-N (loop)` line.
  - [ ] **Success:** the test fails against pre-fix code and passes after T9.
  - Effort: 1/5

- [ ] **T11. Verify `--dry-run` against the real `p45b.yaml`**
  - [ ] Run `sq run --dry-run p45b.yaml` (the same real pipeline used in T3)
    and confirm both `loop:` steps show their bodies (`design`/`tasks`
    phase steps with inline `review:`), `max: 3`, `until: review.pass`, and
    `on_exhaust: checkpoint` — not opaque `loop-N (loop)` lines. Manual
    confirmation, not a new automated test (T10 already covers automated
    regression); record output in the commit message or task notes.
  - [ ] **Success:** `sq run --dry-run p45b.yaml` output shows both loop
    bodies expanded.
  - Effort: 1/5

- [ ] **T12. Commit Part C**
  - [ ] `ruff format`, run Part C tests (T10), then commit
    (`feat: expand loop: step bodies in sq run --dry-run output`).
  - [ ] Reference issue #45 in the commit body.
  - Effort: 1/5

---

## Final validation

- [ ] **T13. Full validation gate + verification walkthrough**
  - [ ] Run the full test suite + `ruff format` + pyright strict; zero
    errors.
  - [ ] Execute the design's Verification Walkthrough for all three parts:
    Part B (T3's `sq run --validate p45b.yaml` plus a deliberately ambiguous
    fixture pipeline failing validation), Part A (T6/T7's iteration-2 prompt
    assertion), Part C (T11's `sq run --dry-run p45b.yaml`).
  - [ ] Close issues #42, #43, #45 on merge; mark slice 910 complete in the
    slice plan (`900-slices.maintenance-and-refactoring.md`) and slice design
    frontmatter (`status: complete`).
  - [ ] Write the Phase 6 DEVLOG entry.
  - Effort: 2/5
