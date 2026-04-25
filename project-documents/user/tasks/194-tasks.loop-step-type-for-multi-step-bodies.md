---
docType: tasks
slice: loop-step-type-for-multi-step-bodies
project: squadron
lld: user/slices/194-slice.loop-step-type-for-multi-step-bodies.md
dependencies: [149]
projectState: >
  Slice 149 (executor) is shipped and stable. The single-step `loop:`
  sub-field is in production, with `LoopConfig`, `LoopCondition`,
  `evaluate_condition`, `ExhaustBehavior`, `_parse_loop_config`,
  `_execute_step_once`, `_unpack_inner_steps` all available for reuse.
  Slice 182 (fan_out) established the precedent for adding a top-level
  control-flow step type with a `steps:` body in the 180-band — same
  registration pattern this slice mirrors. Slice 194 is the prerequisite
  for slice 184 (weighted-decay convergence) to drive realistic
  dispatch-then-review loops rather than re-asking a review against an
  unchanged artifact.
dateCreated: 20260424
dateUpdated: 20260425
status: complete
---

## Context Summary

- Adding top-level `loop:` step type with a `steps:` body — multi-step
  counterpart to the existing single-step `loop:` sub-field
- Mirrors the `each:` / `fan_out:` pattern: `expand()` returns `[]`,
  executor owns iteration via a dedicated branch
- Reuses 149's loop machinery unchanged: `LoopConfig`, `LoopCondition`,
  `evaluate_condition`, `ExhaustBehavior`, `_parse_loop_config`,
  `_execute_step_once`, `_unpack_inner_steps`
- v1 nested-loop ban enforced at validation: (a) inner step with its own
  `loop:` sub-field rejected; (b) inner step whose `step_type` is `loop`
  rejected
- New step module: `src/squadron/pipeline/steps/loop.py`
- Executor changes: new dispatch branch + `_execute_loop_body` function
- Convergence strategy field is parsed but stubbed (same warning as the
  existing single-step loop) — slice 184 will implement strategies for both
  forms simultaneously
- Authoring example added to `example.yaml` demonstrating
  dispatch-then-review pattern

---

## Task 1 — Add `LOOP` to `StepTypeName` enum

- [x] Open `src/squadron/pipeline/steps/__init__.py`
  - [x] Add `LOOP = "loop"` to `StepTypeName` (after `FAN_OUT`, alphabetical order within control-flow types)
  - [x] **Success:** `StepTypeName.LOOP` resolves to the string `"loop"`; all existing enum members unchanged; `ruff` and `pyright` pass

---

## Task 2 — Create test infrastructure for the loop step type

- [x] Create `tests/pipeline/steps/test_loop.py` (empty stub)
  - [x] Add module docstring; import pytest and any fixtures already used in `tests/pipeline/steps/`
- [x] Confirm `conftest.py` fixtures for step/executor tests are accessible from new test path
  - [x] **Success:** `pytest tests/pipeline/steps/test_loop.py` collects 0 tests with no errors

---

## Task 3 — Implement `LoopStepType` (validation + expand)

- [x] Create `src/squadron/pipeline/steps/loop.py`
  - [x] Import `StepConfig`, `ValidationError` from `squadron.pipeline.models`
  - [x] Import `StepTypeName`, `register_step_type` from `squadron.pipeline.steps`
  - [x] Define `class LoopStepType` with:
    - [x] `step_type` property returning `StepTypeName.LOOP`
    - [x] `validate(config)` returning `list[ValidationError]` per Task 4 rules
    - [x] `expand(config)` returning `[]` (executor owns execution)
  - [x] Register via `register_step_type(StepTypeName.LOOP, LoopStepType())` at module bottom
  - [x] **Success:** Module imports cleanly; `pyright` and `ruff` pass; `from squadron.pipeline.steps.loop import LoopStepType` succeeds

---

## Task 4 — Implement `LoopStepType.validate()` rules

- [x] In `src/squadron/pipeline/steps/loop.py`, implement the following validation checks. For each, append a `ValidationError` with `action_type=StepTypeName.LOOP` and a clear message naming the offending field:
  - [x] `max` is required, must be a positive integer (delegate to `_parse_loop_config` shape — *don't* call `_parse_loop_config` here; it raises, which is the wrong contract for validate. Just check the structural shape: present, int, > 0)
  - [x] `until` if present must be one of `LoopCondition` values (`review.pass`, `review.concerns_or_better`, `action.success`)
  - [x] `on_exhaust` if present must be one of `ExhaustBehavior` values (`fail`, `checkpoint`, `skip`)
  - [x] `strategy` if present must be a string (no further validation — 184 will register strategies)
  - [x] `steps` is required, must be a list, must be non-empty
  - [x] **Nested-loop ban (a):** for each inner step in `steps`, if the inner step's config dict contains a `loop:` key, append a `ValidationError` naming the inner step and the violation: `"inner step '<name>' may not carry a 'loop:' sub-field; nested loops are not supported in v1"`
  - [x] **Nested-loop ban (b):** for each inner step in `steps`, if the inner step's `step_type` (the single top-level key of the step dict) equals `"loop"`, append a `ValidationError` naming the inner step and the violation: `"inner step '<name>' may not be of type 'loop'; nested loops are not supported in v1"`
  - [x] **Success:** Each validation rule produces a distinct, well-formed error message; `pyright` and `ruff` pass

---

## Task 5 — Test `LoopStepType` validation rules

- [x] In `tests/pipeline/steps/test_loop.py`, add tests covering each validation rule:
  - [x] Missing `max` → error on `max` field
  - [x] `max` not an int (e.g. `"3"`) → error on `max` field
  - [x] `max` zero or negative → error on `max` field
  - [x] Invalid `until` value (e.g. `"never"`) → error on `until` field; valid values listed in message
  - [x] Invalid `on_exhaust` value → error on `on_exhaust` field
  - [x] `strategy` not a string → error on `strategy` field
  - [x] Missing `steps` → error on `steps` field
  - [x] `steps` not a list → error on `steps` field
  - [x] `steps` empty list → error on `steps` field
  - [x] Inner step with `loop:` sub-field → nested-loop error (case a) naming the inner step
  - [x] Inner step with `step_type == "loop"` → nested-loop error (case b) naming the inner step
  - [x] **Negative test:** Valid config (`max`, `until`, `steps` with non-loop inner) produces zero errors
  - [x] **Negative test:** Valid config with optional `on_exhaust` and `strategy` produces zero errors
  - [x] **Success:** All tests pass; coverage hits every branch in `validate()`

---

## Task 6 — Test `LoopStepType.expand()` and registration

- [x] In `tests/pipeline/steps/test_loop.py`:
  - [x] Test `LoopStepType().expand(any_config)` returns `[]`
  - [x] Test `get_step_type("loop")` returns a `LoopStepType` instance after import
  - [x] **Success:** Both tests pass

---

## Task 7 — Implement `_execute_loop_body` in executor

- [x] In `src/squadron/pipeline/executor.py`, add `_execute_loop_body` analogous to `_execute_each_step` and `_execute_fan_out_step`
  - [x] Signature mirrors `_execute_each_step` (same kwargs)
  - [x] Parse loop config from `resolved_config` via existing `_parse_loop_config` (passing the dict with `steps:` removed for clarity, or passing the full dict — `_parse_loop_config` ignores unknown keys)
  - [x] Extract `steps:` list, unpack via existing `_unpack_inner_steps`
  - [x] If `loop_config.strategy is not None`, log the existing "strategy not implemented, falling back to basic max-iteration loop" warning (same warning the single-step path emits)
  - [x] For iteration in `1..loop_config.max`:
    - [x] Initialize `iteration_action_results: list[ActionResult] = []`
    - [x] For each inner step, call `_execute_step_once` with the inner step's resolved config
    - [x] Aggregate `inner_result.action_results` into `iteration_action_results`
    - [x] If any inner result has status `PAUSED` (checkpoint), return `StepResult` with `status=PAUSED` and `iteration_action_results` immediately
    - [x] An inner step's `FAILED` status does *not* abort the iteration — continue executing remaining inner steps in the iteration; failure is transient (matches existing single-step rule)
    - [x] After all inner steps in the iteration complete, evaluate `until`:
      - [x] If `loop_config.until is not None` and `evaluate_condition(loop_config.until, iteration_action_results)` returns `True`, return `StepResult(status=COMPLETED, action_results=iteration_action_results, iteration=N)` and break
      - [x] If `loop_config.until is None`, return `StepResult(status=COMPLETED, ...)` after iteration 1 (matches existing single-step "no until" behavior)
  - [x] On exhaustion (loop falls through `max` iterations without satisfying `until`):
    - [x] Use `last_results = iteration_action_results` from the final iteration
    - [x] `match loop_config.on_exhaust`:
      - [x] `FAIL` → return `StepResult(status=FAILED, action_results=last_results, iteration=loop_config.max)`
      - [x] `CHECKPOINT` → return `StepResult(status=PAUSED, ...)`
      - [x] `SKIP` → return `StepResult(status=SKIPPED, ...)`
  - [x] **Success:** Function compiles, `pyright` and `ruff` pass; no new public exports required

---

## Task 8 — Wire `loop` into executor dispatch

- [x] In `src/squadron/pipeline/executor.py`, in the step-type dispatch block (currently `if step.step_type == "each"` / `elif step.step_type == StepTypeName.FAN_OUT`):
  - [x] Add `elif step.step_type == StepTypeName.LOOP:` branch dispatching to `_execute_loop_body` with the same kwargs as the `_execute_each_step` and `_execute_fan_out_step` branches
  - [x] Confirm placement — the new branch must be checked *before* the fall-through `else` that handles single-step `loop:` sub-field — so the step-type form takes precedence over the sub-field form when both could apply (in practice they don't overlap: step-type form is the top-level key; sub-field form is nested in another step's config)
  - [x] **Success:** `pyright` and `ruff` pass; existing tests in `tests/pipeline/test_executor*.py` continue to pass (regression gate)

---

## Task 9 — Trigger `LoopStepType` registration via import

- [x] Confirm `src/squadron/pipeline/steps/loop.py` is imported wherever `each.py` and `fan_out.py` are imported so `register_step_type` runs at module load
  - [x] Check `src/squadron/pipeline/steps/__init__.py` — if it imports `each` and `fan_out`, add `loop` alongside; if it relies on lazy import elsewhere, follow that pattern
  - [x] Check `src/squadron/pipeline/executor.py` for any module-level import of step type modules and add `loop` if needed
  - [x] **Success:** After a clean Python import of `squadron.pipeline.executor`, `get_step_type("loop")` returns the registered `LoopStepType` instance without manual import

---

## Task 10 — Integration test: passes after iteration 1

- [x] In `tests/pipeline/test_executor_loop.py` (or a new `test_executor_loop_body.py` if cleaner — match repo convention), add an integration test:
  - [x] Pipeline with one `loop:` step containing a body of `[stub_dispatch_action_returning_pass_review]`
  - [x] `until: review.pass`, `max: 3`
  - [x] Run via the executor; assert step status `COMPLETED`, iteration count `1`, action results contain the PASS verdict
  - [x] **Success:** Test passes

---

## Task 11 — Integration test: retries to PASS on iteration N

- [x] In the same test file, add a test where the body's review action returns `CONCERNS` for iterations 1..2 and `PASS` for iteration 3
  - [x] `until: review.pass`, `max: 5`
  - [x] Assert status `COMPLETED`, iteration count `3`
  - [x] Assert `action_results` contain the final iteration's results only (matches single-step contract)
  - [x] **Success:** Test passes

---

## Task 12 — Integration test: exhaustion modes

- [x] In the same test file, add three tests where the review never returns PASS and `max: 2`:
  - [x] `on_exhaust: fail` → status `FAILED`, iteration `2`
  - [x] `on_exhaust: checkpoint` → status `PAUSED`, iteration `2`
  - [x] `on_exhaust: skip` → status `SKIPPED`, iteration `2`
  - [x] **Success:** All three tests pass

---

## Task 13 — Integration test: inner failure is transient

- [x] In the same test file, add a test where the body has two inner steps; the first fails on iteration 1 but the second still runs and produces a PASS verdict
  - [x] `until: review.pass`, `max: 3`
  - [x] Assert status `COMPLETED`, iteration `1`, both inner action results captured
  - [x] **Success:** Test passes — confirms `FAILED` status on an inner step does not abort the iteration

---

## Task 14 — Integration test: checkpoint pause stops the loop

- [x] In the same test file, add a test where an inner step pauses on a checkpoint during iteration 1
  - [x] `max: 5`
  - [x] Assert status `PAUSED`, iteration `1`, action results from iteration 1 only
  - [x] **Success:** Test passes — confirms `PAUSED` short-circuits the loop and propagates upward

---

## Task 15 — Integration test: nested-loop ban (sub-field form)

- [x] In `tests/pipeline/test_loader.py` or a new `test_loop_validation.py` file, add a test:
  - [x] Pipeline YAML defines a `loop:` step whose body contains an inner step (e.g. `review:`) that *itself* carries a `loop:` sub-field
  - [x] Assert pipeline load fails with a `ValidationError` whose message names the inner step and identifies the nested-loop violation
  - [x] **Success:** Test passes

---

## Task 16 — Integration test: nested-loop ban (step-type form)

- [x] In the same test file, add a test:
  - [x] Pipeline YAML defines a `loop:` step whose body contains an inner `loop:` step
  - [x] Assert pipeline load fails with a `ValidationError` whose message names the inner step and identifies the nested-loop violation
  - [x] **Success:** Test passes

---

## Task 17 — Regression test: existing single-step `loop:` sub-field unchanged

- [x] Run the full existing executor-loop test suite without modification:
  - [x] `uv run pytest tests/pipeline/test_executor_loop.py -v`
  - [x] **Success:** All existing single-step loop tests pass without changes

---

## Task 18 — Add authoring example to `example.yaml`

- [x] In `src/squadron/data/pipelines/example.yaml`, add a documented example of the multi-step loop pattern:
  - [x] Inline-comment block introducing the `loop:` step type as the multi-step counterpart to the single-step `loop:` sub-field
  - [x] Concrete example showing dispatch + review wrapped in a `loop:` with `max`, `until: review.pass`, `on_exhaust: checkpoint`
  - [x] Note that nested loops are not supported in v1 and reference the slice 194 design
  - [x] **Success:** `example.yaml` loads and validates cleanly via `sq pipelines validate` (or the equivalent loader entrypoint); the new example block is syntactically valid YAML

---

## Task 19 — Schema/loader smoke test for the new step type

- [x] Run schema/loader validation against all built-in pipelines (`slice.yaml`, `tasks.yaml`, `app.yaml`, `P6.yaml`, `example.yaml`):
  - [x] `uv run pytest tests/pipeline/test_loader.py tests/pipeline/test_schema.py -v`
  - [x] **Success:** All built-in pipelines (including the updated `example.yaml`) parse and validate; no regressions

---

## Task 20 — Final check: full test suite + lint + types

- [x] Run:
  - [x] `uv run ruff format .`
  - [x] `uv run ruff check .`
  - [x] `uv run pyright`
  - [x] `uv run pytest`
  - [x] **Success:** All four pass with zero errors; ready for review and Phase 6 implementation completion sign-off

---

## Task 21 — Mark slice complete and write DEVLOG entry

- [x] Update `user/slices/194-slice.loop-step-type-for-multi-step-bodies.md` frontmatter:
  - [x] `status: complete`
  - [x] `dateUpdated: <today YYYYMMDD>`
- [x] Update `user/architecture/180-slices.pipeline-intelligence.md`:
  - [x] Mark slice 194 entry checkbox as `[x]`
  - [x] Bump `dateUpdated` in frontmatter
- [x] Append DEVLOG entry under today's date describing the implementation outcome (one paragraph: what shipped, what was reused, what was deferred)
- [x] **Success:** All three artifacts updated and consistent
