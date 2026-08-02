---
docType: tasks
slice: findings-addressed-gate
project: squadron
lld: user/slices/305-slice.findings-addressed-gate.md
dependencies: [911, 910, 304]
projectState: >
  Phase 5 task breakdown for slice 305 (initiative 300, eval-actions /
  LLM-as-judge). Slice 911 is merged: per-iteration commits
  (commit_each_iteration), revision_number stamping, and the clean-regeneration
  round contract all shipped. Slice 910 is merged: findings feedback into the
  retry dispatch, and the one-verdict-per-loop-body guard. Slice 304 is merged:
  the gate step/action, reduce_verdicts, and VALID_GATE_POLICIES. Phase 6 has
  not started; no branch exists for 305. This is file 1 of 2 (Parts A–C,
  T1–T11); Parts D–G continue in 305-tasks.findings-addressed-gate-2.md.
dateCreated: 20260802
dateUpdated: 20260802
status: not_started
---

## Context Summary

- Working on the **findings-addressed-gate** slice (305) under initiative 300.
  It adds `findings-addressed` as the second entry in `VALID_GATE_POLICIES`
  (`pipeline/actions/gate.py:14-15`) — the first model-capable gate policy —
  so a loop can require both *fresh eyes are satisfied* and *the prior round's
  CONCERN+ findings are accounted for*.
- The governing shape is `gate = where the decision happens`, `judge = the role
  a model plays`. No new step type, no new action type, no new user-facing
  vocabulary. The judge call happens **inside** gate execution, so loop verdict
  accounting is untouched.
- The decision procedure is layered: deterministic screens first (zero tokens),
  a judge only over the residue, and a **derivation rule** that computes the
  verdict from per-finding statuses — the judge's own opinion of the outcome is
  discarded (`enforce_judge` precedent, `pipeline/actions/judge.py`).
- Read the slice design before starting. The Technical Decisions section (1–8)
  is binding, especially decision 8: `UNKNOWN` means *the check could not run
  and the system stops*. It is never the disposition for a state whose right
  action is knowable — config errors are rejected at validation time, known
  runtime states resolve to their known verdicts.

### Design deltas discovered during breakdown — read this first

Three of the design's evidence-availability claims do not hold at the point the
gate actually executes. Verified on disk; each is a Phase 6 task in **Part A**.

1. **`step_outputs` is never populated for steps inside a loop body.** The only
   writer is `executor.py:959`, in the top-level step walk.
   `_execute_loop_body` passes `step_outputs` through to `_execute_step_once`
   (`executor.py:1382`) but never writes to it. A gate inside a loop body
   therefore cannot resolve `review_from` at all today — it would take the
   `step_outputs.get(...) is None` path and emit `UNKNOWN` every round. This
   blocks the target loop shape for *any* policy, not just this one.
2. **The prior round's review result is not in `prior_outputs` at gate time.**
   `running_prior` keys are `f"{inner_step_index}-{action_type}-{action_index}"`
   (`executor.py:1400-1402`) and are overwritten every iteration. Iteration N's
   review overwrites iteration N-1's *before* the gate runs, because the gate is
   later in the body. 910's findings-feedback works only because dispatch runs
   **first** in the body and reads the key before it is overwritten. The design's
   "no git archaeology needed for findings" intent is correct; the mechanism it
   named is not.
3. **Round N's commit SHA does not exist at gate time.** `commit_each_iteration`
   appends its commit *after* all inner steps (`executor.py:1417-1440`), so at
   gate time round N is uncommitted and `HEAD` is round N-1's commit. The
   design's Screen 1 signal (`committed: False` from `prior_outputs`) describes
   round N-1 vs N-2 — one round stale. The correct at-gate-time detection is a
   working-tree diff against `HEAD`, which needs no SHA plumbing and is exactly
   round N's changes.

The corrected mechanism (Part A + Task D3) is strictly simpler than the design's
and preserves every stated principle. It does add `pipeline/executor.py` and
`pipeline/models.py` to the design's "Files touched" table. **Flag this to the
Project Manager before Part D begins; do not widen it further on your own
initiative.**

### Facts established by inspection (do not re-derive)

- `ActionResult.findings` is `list[object]`, populated by the review action as
  `[sf.__dict__ for sf in result.structured_findings]`
  (`pipeline/actions/review.py:297`). Each dict has keys `id`, `severity`,
  `category`, `summary`, `location` (`review/models.py:33-40`).
- `Severity` values are `PASS | NOTE | CONCERN | FAIL` (`review/models.py:19-25`).
  "CONCERN+" in this slice means `CONCERN` or `FAIL`.
- Review files are **overwritten** each iteration — `save_review_result` names
  them `{index}-review.{type}.{slice_name}.md` with no revision segment
  (`review/persistence.py:290-295`); `revision_number` lands in frontmatter only.
  The prior round's review file survives only inside the prior round's commit.
- `CommitAction` returns `outputs={"committed": False}` on a clean tree and
  `{"committed": True, "sha": ..., "message": ...}` otherwise
  (`pipeline/actions/commit.py:57-59, 112-120`).
- `_validate_gate_references` (`pipeline/loader.py:280-307`) walks
  `definition.steps` only — it does **not** descend into loop bodies.
- `discover_judge_results` (`metrology/discovery.py:44-57`) globs `*-review.*`
  under `project-documents/user/reviews` and keeps anything whose `reviewType`
  resolves to an `is_judge` template. This is the live consumer the gate-evidence
  artifact must never collide with.
- `ReviewTemplate.is_judge` (`review/templates/__init__.py:48`) is derived from
  the presence of a `judge:` block in the template YAML.
- `run_review_with_profile` (`review/review_client.py:54-62`) is the transport;
  it returns a `ReviewResult` whose `raw_output` carries the unparsed model text.

### Out of scope — do not touch

- The generic judge-over-results gate (`results_from:`) — Future Work item 6 in
  `300-slices`, deliberately deferred.
- Reviewer error rate / review scoring against later ground truth.
- The `on_exhaust: skip` fall-through hole deferred by 910.
- Renaming existing `judge.*` templates.
- Fan-out / fan-in behavior.
- `GateAction`'s existing execute-time fallback for an unknown policy
  (`actions/gate.py:87-93`). It warns rather than failing silently and its
  behavior is pinned by tests; leave it alone.

---

## Part A — Loop-Body Evidence Plumbing

Prerequisite for everything after it: without A1 the target shape cannot resolve
`review_from`, and without A2 the policy has no prior round to compare against.

- [ ] **T1. Populate `step_outputs` for loop-body inner steps** (effort 2)
  - [ ] In `src/squadron/pipeline/executor.py`, inside `_execute_loop_body`'s
    inner-step loop (after `running_prior` is updated, ~line 1403), write the
    inner step's verdict-bearing result into `step_outputs` using the same
    `_last_with_verdict` rule the top-level walk uses at `executor.py:956-959`.
    Do not invent a second rule — call the same helper.
  - [ ] Guard on `step_outputs is not None` (the parameter is optional,
    `executor.py:1326`).
  - [ ] Add a comment stating why: a `gate` inside a loop body resolves
    `review_from` through `step_outputs`, and the top-level walk never sees
    inner steps.
  - [ ] Success: a gate inside a loop body resolves a named inner review step;
    `most-severe` gates at top level are unaffected.

- [ ] **T2. Carry the prior iteration's step outputs into `ActionContext`** (effort 2)
  - [ ] In `src/squadron/pipeline/models.py`, add
    `prior_iteration_step_outputs: dict[str, ActionResult]` to `ActionContext`
    with a `field(default_factory=...)` default, placed after `iteration`
    (`models.py:64`). Document the sentinel in a comment: an **empty** dict means
    "no prior iteration" — outside a loop, and on iteration 1.
  - [ ] In `_execute_loop_body`, keep a per-iteration
    `iteration_step_outputs: dict[str, ActionResult]` populated alongside T1's
    write, and at the top of each iteration set the previous iteration's dict as
    the value passed down. Scope it to the loop body's own steps — do not
    snapshot `step_outputs` wholesale, which would leak pre-loop steps into what
    the policy reads as "the prior round".
  - [ ] Thread the new field through the `ActionContext(...)` construction in
    `_execute_step_once` (`executor.py:1105-1118`) via a new keyword-only
    parameter with an empty-dict default, so no other caller changes.
  - [ ] Success: `pyright` strict passes; every existing test still passes; no
    action outside this slice reads the new field.

- [ ] **T3. Tests for Part A** (test-with — must pass before Part B starts) (effort 2)
  - [ ] In `tests/pipeline/test_executor_loop_body.py`: a loop body whose inner
    review step is named `fresh-review` puts that step's verdict-bearing result
    into `step_outputs` under that name, on every iteration.
  - [ ] An inner step that produces no verdict-bearing result does not create a
    `step_outputs` entry.
  - [ ] On iteration 1 the action receives an **empty**
    `prior_iteration_step_outputs`; on iteration 2 it receives iteration 1's
    entries, with iteration 1's findings intact (not iteration 2's).
  - [ ] A step executed outside any loop receives an empty
    `prior_iteration_step_outputs`.
  - [ ] Success: all four pass; full `tests/pipeline/` suite green.

---

## Part B — Loop Validation Refinement

- [ ] **T4. Unconsumed-verdict rule in `_validate_verdict_count`** (effort 2)
  - [ ] In `src/squadron/pipeline/steps/loop.py:208-242`, change the count from
    "verdict-bearing actions" to "**unconsumed** verdict-bearing actions": an
    inner step named by a gate's `judge_from` / `review_from` in the same body is
    *consumed* and does not count toward the total.
  - [ ] Collect the consumed names by reading each inner gate step's config
    (`inner.config`) for whichever reference fields that gate's policy declares —
    reuse the per-policy field list defined in Task T6, do not duplicate the
    literal field names here.
  - [ ] Update the docstring to state the rule and why: the gate is the decider,
    its legs are inputs to that decision, and `_last_with_verdict`
    (`executor.py:414-418`) lands on the gate by construction.
  - [ ] Leave the error message and its wording unchanged — 910 Part B's
    motivating rejection must fail with the same text.
  - [ ] Success: `[dispatch, review, gate]` validates; `[review, review]` with no
    gate still rejects with the existing message.

- [ ] **T5. Tests for the unconsumed-verdict rule** (effort 2)
  - [ ] In `tests/pipeline/test_loop_validation.py`: body of
    `dispatch + review(name=fresh-review) + gate(review_from=fresh-review,
    policy=findings-addressed)` validates clean.
  - [ ] Body of two `review:` steps with no gate still rejects, asserting on the
    existing message text (910 Part B regression pin).
  - [ ] Body of `review + review + gate` naming **one** of them still rejects —
    the unnamed review is unconsumed and the gate's verdict makes two.
  - [ ] Body of `review + gate` where the gate names a step that is **not** in
    the body still rejects (the reference is unresolvable, so nothing is
    consumed).
  - [ ] Success: all four pass; existing loop-validation tests unchanged.

---

## Part C — Policy Config Surface

- [ ] **T6. Gate policy enum and per-policy reference fields** (effort 2)
  - [ ] In `src/squadron/pipeline/actions/gate.py`, replace the bare string
    constants (`:14-15`) with a `GatePolicy(StrEnum)` carrying `MOST_SEVERE` and
    `FINDINGS_ADDRESSED`. Derive `DEFAULT_GATE_POLICY` and `VALID_GATE_POLICIES`
    from the enum so both keep their current names and import sites
    (`steps/gate.py:6`) compile unchanged.
  - [ ] Define, once, a mapping from policy → the reference fields that policy
    requires and forbids (`most-severe`: both `judge_from` and `review_from`
    required; `findings-addressed`: `review_from` required, `judge_from`
    forbidden). This mapping is the single source consumed by `steps/gate.py`,
    `loader.py`, and `steps/loop.py` — none of them may restate the field names.
  - [ ] Success: `pyright` strict passes; existing gate tests green with no
    edits.

- [ ] **T7. Policy dispatch in `GateAction.execute`** (effort 2)
  - [ ] In `actions/gate.py`, dispatch on the resolved policy to a policy
    implementation rather than falling through to `reduce_verdicts`
    unconditionally (`:123-127`). Register the two policies in a small registry
    keyed by `GatePolicy`; no `if policy == "..."` chains.
  - [ ] The `most-severe` implementation is the existing body, moved verbatim —
    same outputs, same metadata keys, same log lines.
  - [ ] The `findings-addressed` implementation delegates to the new module from
    Part D. Import it lazily inside the call if a circular import appears,
    following the precedent at `metrology/discovery.py:38-40`.
  - [ ] Success: `tests/pipeline/test_gate_action.py`,
    `test_gate_reduce.py`, `test_gate_executor.py`, and `test_gate_step.py` pass
    unmodified.

- [ ] **T8. Policy-dependent step validation and expansion** (effort 3)
  - [ ] In `src/squadron/pipeline/steps/gate.py:23-74`, drive the
    required/forbidden reference-field checks from T6's mapping instead of the
    hard-coded `("judge_from", "review_from")` tuple. A `judge_from` on a
    `findings-addressed` gate is an error naming the policy and the field.
  - [ ] Validate the optional `judge:` block: must be a mapping; only `model:`
    is accepted; `model:` must be a string. Reject a `judge:` block on a
    `most-severe` gate — that policy has no model layer.
  - [ ] In `expand` (`steps/gate.py:76-93`), build the action dict from the
    fields the policy actually declares. It currently does `cfg["judge_from"]`
    unconditionally and would `KeyError` on a valid `findings-addressed` step.
  - [ ] Pass the `judge:` block through into the gate action's params when
    present.
  - [ ] Success: a `findings-addressed` gate step with only `review_from`
    validates and expands to `[gate]` or `[gate, checkpoint]`; a `most-severe`
    gate step expands byte-identically to today.

- [ ] **T9. Loader reference resolution per policy** (effort 2)
  - [ ] In `src/squadron/pipeline/loader.py:280-307`, resolve which fields to
    check from T6's mapping rather than the hard-coded tuple, so a
    `findings-addressed` gate is not silently unchecked.
  - [ ] Leave the top-level-only walk as is. Loop-body gates are validated in
    T10, which is where the body is in scope — do **not** add loop descent to
    the loader.
  - [ ] Success: a top-level `findings-addressed` gate whose `review_from` names
    a non-prior step fails at load time with the existing message shape.

- [ ] **T10. Loop-scoped validation for `findings-addressed`** (effort 3)
  - [ ] In `src/squadron/pipeline/steps/loop.py`, add a validation pass over the
    body (reuse `_walk_valid_inner_action_types`, `:182-206`) that, when the body
    contains a gate step whose `policy` is `findings-addressed`:
    - [ ] rejects the loop when there is **no per-round commit source** — that
      is, neither `commit_each_iteration: true` nor an inner step that expands to
      a `commit` action. The message must name the policy, say the evidence
      source is absent by configuration, and state the fix
      (`commit_each_iteration: true`). This is design decision 8 in force: a
      knowable config error resolves at validation time, never as a runtime
      `UNKNOWN`.
    - [ ] rejects the loop when `review_from` does not name an inner step that
      appears **earlier** in the same body. The loader cannot see inside the
      body (established above), so without this a typo degrades to a fail-closed
      `UNKNOWN` every round instead of failing fast at load time — the same
      reasoning `_validate_gate_references` already documents
      (`loader.py:285-291`).
  - [ ] A `findings-addressed` gate **outside** a loop is not rejected: it is a
    legitimate no-prior-round case that Screen 0 handles observably. Add a
    comment saying so, so a later reader does not "fix" it.
  - [ ] Success: the target loop shape validates; the same shape without
    `commit_each_iteration` is rejected at load time with an actionable message.

- [ ] **T11. Tests for the policy config surface** (effort 3)
  - [ ] In `tests/pipeline/test_gate_step.py`: `findings-addressed` with only
    `review_from` validates; with `judge_from` present it errors naming the
    policy; `most-severe` missing `judge_from` still errors as today.
  - [ ] `judge:` block cases — well-formed passes; non-mapping, unknown key, and
    non-string `model:` each error; a `judge:` block on `most-severe` errors.
  - [ ] `expand()` for `findings-addressed` emits no `judge_from` key and does
    not raise; `expand()` for `most-severe` is unchanged.
  - [ ] In `tests/pipeline/test_loader.py`: a top-level `findings-addressed`
    gate with a forward/misspelled `review_from` fails validation.
  - [ ] In `tests/pipeline/test_loop_validation.py`: the target shape without
    `commit_each_iteration` is rejected; with it, accepted; a body whose gate
    names a non-existent inner step is rejected; a phase-bodied loop (which
    commits on its own) satisfies the commit-source requirement.
  - [ ] Success: all pass; no existing gate/loader test edited.

---

**Continued in `305-tasks.findings-addressed-gate-2.md`** — Part D
(deterministic screens), Part E (judge over the residue), Part F (gate evidence
artifact), and Part G (integration, documentation, close-out), tasks T12–T30.
