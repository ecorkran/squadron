---
docType: tasks
slice: pipeline-phase-step-correctness
project: squadron
lld: user/slices/909-slice.pipeline-phase-step-correctness.md
dependencies: [149]
projectState: >
  Slice 909 design complete and review-addressed (CONCERNS resolved:
  expected_artifact_kind mapping + I/O failure-mode enumeration). Three
  independent bugs bundled: Part A dispatch artifact post-condition (#15),
  Part B review-frontmatter project name (#16), Part C review-code scope
  guard (#17). On branch 909-slice.pipeline-phase-step-correctness.
dateCreated: 20260709
dateUpdated: 20260709
status: not_started
---

## Context Summary

- Working on the **pipeline-phase-step-correctness** slice (909), a maintenance
  slice fixing three independent correctness bugs, all sharing a silent-success
  failure signature. Parent: `900-slices.maintenance-and-refactoring.md`.
- **Part A (#15, Medium):** phase-step `dispatch` returns `success=True` even
  when the agent wrote no artifact; the failure surfaces one step later as a
  misleading review error.
- **Part B (#16, Low):** review frontmatter hardcodes `project: squadron`.
- **Part C (#17, Medium):** `sq review code` with a missing/malformed slice
  index silently runs an unscoped, hallucination-prone review.
- **Suggested order: C → B → A** (cheapest/most-isolated first). Each part is
  independently committable and testable; a stall on A does not block B/C. If A
  stalls, promote it to its own slice per the design's split-out fallback.

### Grounding note carried into Part A (important — read before Part A tasks)

An execution-flow trace refined the design's Part A mechanics. The design said
"the phase step verifies after dispatch completes," but in code:
- `PhaseStepType.expand()` returns a flat action list and is **never consulted
  again** — the phase step gets no post-expansion runtime hook.
- The only seam that runs right after a phase step's `dispatch` action is the
  per-action tail of `_execute_step_once` (`executor.py` ~lines 898-943).
- Therefore: `expected_artifact_kind` is a **property on `PhaseStepType`** (the
  declaration of what artifact the phase owns), but the **check runs in the
  executor**, keyed on `action_type == "dispatch"`, reading that property from
  the step type.
- Run-start time is **not** in `ActionContext`; it lives in
  `RunState.started_at`, loadable via `StateManager().load(run_id).started_at`
  (precedent: `executor.py:603-606`).
- Expected path is resolved via
  `resolve_slice_info(context.cf_client, int(slice)).task_files` /
  `.design_file` (same call the review action uses at `review.py:264`).

---

## Part C — Review-code scope guard (do first)

- [ ] **T1. Add a scope guard to `review_code`**
  - [ ] In `src/squadron/cli/commands/review.py`, in `review_code`, after the
    slice/diff resolution block (after ~line 645) and before `inputs` is built,
    add a guard: if none of {resolved `slice_info`, `diff`, `files`} is present,
    `rprint` a clear error and `raise typer.Exit(code=1)`.
  - [ ] Mirror the existing pattern in `review_slice` (review.py:408-410) /
    `review_tasks` (review.py:551-553); do not invent a new validation style.
  - [ ] Distinguish the malformed case: when `slice_number is not None` but
    `not slice_number.isdigit()`, the message should say the slice number is
    non-numeric (e.g. `"slice number 'abc' is not numeric; provide a numeric
    slice, --diff, or --files"`). The missing case says
    `"provide a slice number, --diff, or --files"`.
  - [ ] **Success:** with no scope, the guard exits before any model call; a
    valid slice number, `--diff`, or `--files` still proceeds normally.
  - Effort: 2/5

- [ ] **T2. Test the scope guard** *(test-with T1)*
  - [ ] Add CLI tests (invoke `review_code` via the typer test runner / direct
    call) asserting: (a) no args → exit code 1 and no review executed;
    (b) malformed non-digit arg (`"abc"`) → exit code 1; (c) valid slice number
    still reaches review execution; (d) `--diff` alone and `--files` alone each
    proceed. Assert the model/review client is **not** invoked in cases (a)/(b)
    — e.g. patch the review client and assert not-called.
  - [ ] **Success:** all four cases pass; the not-called assertion proves no
    fabricated-review path remains for missing/malformed scope.
  - Effort: 2/5

- [ ] **T3. Commit Part C**
  - [ ] `ruff format`, run the Part C tests, then commit
    (`fix: guard sq review code against missing/malformed slice scope`).
  - [ ] Reference issue #17 in the commit body.
  - Effort: 1/5

---

## Part B — Review frontmatter project name

- [ ] **T4. Add `name` to `ProjectInfo` and populate it**
  - [ ] In `src/squadron/integrations/context_forge.py`, add `name: str` to the
    `ProjectInfo` dataclass (~line 52).
  - [ ] In `get_project` (~line 165), populate it from `data.get("name")`
    (verified: `cf get --json` returns a `name` field). Use a non-silent
    fallback of `"unknown"` if the key is absent — never `"squadron"`.
  - [ ] **Success:** `get_project().name` returns the real project name;
    `ProjectInfo` construction still type-checks (pyright strict).
  - Effort: 1/5

- [ ] **T5. Test `ProjectInfo.name` population** *(test-with T4)*
  - [ ] Add/extend a test for `get_project` using a **real-shaped** `cf get
    --json` response fixture (must include `name`, `fileArch`, `fileSlice`,
    `fileSlicePlan`, `developmentPhase`). Assert `name` is threaded through, and
    a fixture missing `name` yields `"unknown"` (not `"squadron"`).
  - [ ] **Success:** both cases pass; fixture matches the actual CLI shape.
  - Effort: 1/5

- [ ] **T6. Thread `project` through `SliceInfo` / `resolve_slice_info`**
  - [ ] In `src/squadron/review/persistence.py`, add `project: str` to the
    `SliceInfo` TypedDict (~line 20).
  - [ ] In `resolve_slice_info` (~line 66, which already calls
    `cf_client.get_project()`), set `project=project.name` in the returned
    `SliceInfo`.
  - [ ] **Success:** `resolve_slice_info(...)["project"]` returns the real name;
    existing callers still type-check.
  - Effort: 1/5

- [ ] **T7. Replace the hardcoded `project: squadron` literal**
  - [ ] In `format_review_markdown` (persistence.py ~line 119), replace the
    `"project: squadron"` literal with `f"project: {slice_info['project']}"`
    when `slice_info` is present, falling back to `"unknown"` when `slice_info`
    is `None` — mirroring the adjacent `slice_name`/`slice_index` fallback
    pattern. Never emit `"squadron"` as a literal default.
  - [ ] **Success:** the review file's `project:` field reflects the actual
    project; a `None` `slice_info` yields `project: unknown`.
  - Effort: 1/5

- [ ] **T8. Test the frontmatter project field (both write paths)** *(test-with T6/T7)*
  - [ ] Test `format_review_markdown` directly: with a `SliceInfo` carrying
    `project="context-forge"` → frontmatter contains `project: context-forge`;
    with `slice_info=None` → `project: unknown`; assert `"project: squadron"`
    never appears unless the real project is squadron.
  - [ ] Interface-parity assertion: since both the pipeline path
    (`save_review_result` → `actions/review.py:193`) and CLI path
    (persistence.py:268) call `format_review_markdown`, one test on that seam
    covers both — add a comment asserting this convergence, and if a
    lightweight test of `save_review_result` exists, assert it emits the same
    `project:` value.
  - [ ] **Success:** all cases pass; no path emits a hardcoded `squadron`.
  - Effort: 2/5

- [ ] **T9. Commit Part B**
  - [ ] `ruff format`, run Part B tests, commit
    (`fix: derive review frontmatter project from cf, not hardcoded squadron`).
  - [ ] Reference issue #16 in the commit body.
  - Effort: 1/5

---

## Part A — Dispatch artifact post-condition (do last; genuine design depth)

- [ ] **T10. Add `expected_artifact_kind` to `PhaseStepType`**
  - [ ] In `src/squadron/pipeline/steps/phase.py`, add an `expected_artifact_kind`
    property/attribute on `PhaseStepType` returning an enum/constant per phase:
    `design` → design-file kind, `tasks` → task-file kind, `implement` → `None`.
    Define the kinds as a single enum/constant (not scattered strings), per the
    "define comparison values once" rule.
  - [ ] The three registrations (design/tasks/implement, phase.py:133-135) must
    each resolve to the correct kind; `implement` is `None` (no single
    deterministic artifact → post-condition does not apply).
  - [ ] **Success:** `PhaseStepType("tasks").expected_artifact_kind` is the
    task-file kind; `PhaseStepType("implement").expected_artifact_kind` is
    `None`.
  - Effort: 2/5

- [ ] **T11. Test `expected_artifact_kind` mapping** *(test-with T10)*
  - [ ] Parametrized test over the three phases asserting the exact kind for
    each, including `implement` → `None`.
  - [ ] **Success:** mapping test passes; adding a hypothetical new phase with
    no kind would default to `None` (assert the property does not raise for an
    unmapped phase name).
  - Effort: 1/5

- [ ] **T12. Add a run-start timestamp accessor for the executor**
  - [ ] Confirm `RunState.started_at` (`state.py:126`) and that the executor
    can load it via `StateManager().load(run_id).started_at` (precedent:
    `executor.py:603-606`). The post-condition needs the run-start time to
    reject stale prior-run artifacts by mtime.
  - [ ] Decide the anchor: prefer loading `started_at` once per step (or reuse
    an already-loaded `RunState` if the executor has one in scope) rather than
    per-action, to avoid repeated state loads. Document the chosen anchor inline.
  - [ ] **Success:** the executor has access to a UTC run-start timestamp at the
    point the post-condition runs, without adding a field to `ActionContext`.
  - Effort: 2/5

- [ ] **T13. Implement the artifact post-condition in the executor**
  - [ ] In `_execute_step_once` (`executor.py`), in the per-action tail after a
    `dispatch` result (~lines 898-943), when the current step is a
    `PhaseStepType` whose `expected_artifact_kind` is non-`None`:
    1. Resolve the expected path(s) via
       `resolve_slice_info(context.cf_client, int(slice)).task_files` (tasks) or
       `.design_file` (design), using the slice from `context.params`.
    2. Verify at least one expected artifact **exists** and its **mtime ≥
       run-start**. If so, continue.
    3. Otherwise mark the step result as **failed** with a message naming the
       phase, expected artifact, and slice.
  - [ ] Enumerate every failure mode from the design's table with an observable
    outcome (fail closed + WARNING-level log): artifact absent; path
    unresolvable; permission/`OSError` on the check; stale mtime; race-delete.
    No mode may silently pass. Catch `OSError` narrowly around the filesystem
    calls only.
  - [ ] Do **not** modify generic `DispatchAction` — the check is executor-owned
    and scoped to phase steps with a non-`None` kind; bare `dispatch` steps and
    `implement` phases are untouched.
  - [ ] **Success:** a phase-step dispatch that writes no artifact yields a
    failed step (not `success=True`) at the dispatch point, with a clear
    message; a normal run that writes the artifact passes unchanged.
  - Effort: 4/5

- [ ] **T14. Test the artifact post-condition** *(test-with T13)*
  - [ ] Unit/integration tests over the executor seam: (a) artifact present with
    fresh mtime → step passes; (b) artifact absent → step fails with the
    phase/artifact/slice message; (c) artifact present but mtime predates run
    start → step fails (stale); (d) unresolvable path → step fails with the
    distinct message + WARNING log; (e) `OSError` on the check → step fails,
    logged, not swallowed; (f) an `implement` phase (kind `None`) → post-condition
    skipped entirely (no failure when no single artifact is written).
  - [ ] Assert generic `dispatch` (non-phase) is unaffected — a bare dispatch
    step that writes nothing still succeeds.
  - [ ] **Success:** all six cases pass; each failure mode produces its expected
    observable signal (failed step + log).
  - Effort: 3/5

- [ ] **T15. Route the no-artifact outcome to checkpoint/escalation**
  - [ ] Ensure the failed-step outcome from T13 flows into the existing
    checkpoint/on-fail machinery so an unattended run stops observably rather
    than proceeding to a downstream step. Reuse existing failure routing (do not
    add a parallel mechanism). The contract is: no-artifact ⇒ not success ⇒
    existing on-fail path; the "detect a trailing question" heuristic is out of
    scope for this task (the artifact check already catches the no-file case).
  - [ ] **Success:** in a pipeline with `on_fail`/checkpoint configured, a
    no-artifact phase step triggers the configured failure behavior instead of
    silently advancing.
  - Effort: 2/5

- [ ] **T16. Commit Part A**
  - [ ] `ruff format`, run Part A tests, commit
    (`fix: fail phase step when dispatch writes no expected artifact`).
  - [ ] Reference issue #15 in the commit body.
  - Effort: 1/5

---

## Final validation

- [ ] **T17. Full validation gate + verification walkthrough**
  - [ ] Run the full test suite + `ruff format` + pyright strict; zero errors.
  - [ ] Execute the design's Verification Walkthrough for all three parts:
    Part C (`sq review code` with no/malformed/valid scope), Part B (grep
    `project:` in a review file — must be the real project, tested by unit
    fixture since a non-squadron repo may be unavailable), Part A (a pipeline
    whose dispatch writes no artifact fails at the dispatch step, not one step
    later).
  - [ ] Close issues #15, #16, #17 on merge; mark slice 909 complete in the
    slice plan and slice design if all parts land. If Part A was split out,
    mark only A/B and reflect the split.
  - [ ] Write the Phase 6 DEVLOG entry.
  - Effort: 2/5
