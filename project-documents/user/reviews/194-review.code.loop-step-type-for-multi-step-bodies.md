---
docType: review
layer: project
reviewType: code
slice: loop-step-type-for-multi-step-bodies
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md
aiModel: claude-sonnet-4-6
status: complete
dateCreated: 20260426
dateUpdated: 20260426
findings:
  - id: F001
    severity: pass
    category: testing
    summary: "Test coverage for new execution path"
  - id: F002
    severity: pass
    category: design
    summary: "`_loop_exhaust_result` DRY extraction"
  - id: F003
    severity: concern
    category: correctness
    summary: "`_loop_exhaust_result` — `status` is unbound after the `match` block"
    location: src/squadron/pipeline/executor.py:886
  - id: F004
    severity: concern
    category: error-handling
    summary: "Silent runtime drop of malformed inner step dicts is untested and undocumented"
    location: src/squadron/pipeline/steps/loop.py:129 / src/squadron/pipeline/executor.py:1105
  - id: F005
    severity: concern
    category: design
    summary: "OCP: `execute_pipeline` dispatch chain extended again"
    location: src/squadron/pipeline/executor.py:661
  - id: F006
    severity: note
    category: design
    summary: "`prior_outputs` is not propagated across inner steps within a loop body iteration"
    location: src/squadron/pipeline/executor.py:1036
  - id: F007
    severity: note
    category: correctness
    summary: "`_parse_loop_config` does not reject `bool` for `max`"
    location: src/squadron/pipeline/executor.py:366
---

# Review: code — slice 194

**Verdict:** CONCERNS
**Model:** claude-sonnet-4-6

## Findings

### [PASS] Test coverage for new execution path

`test_executor_loop_body.py` covers: first-iteration completion, multi-iteration retry, all three exhaustion modes (`fail` / `checkpoint` / `skip`), inner-step failure as transient, and checkpoint pause short-circuit. The validation unit tests in `test_loop.py` and the integration path in `test_loop_validation.py` are equally complete. Test-with rather than test-after — good.

---

### [PASS] `_loop_exhaust_result` DRY extraction

Extracting the repeated match/return block into `_loop_exhaust_result` and sharing it between `_execute_loop_step` and `_execute_loop_body` is exactly right. The old code in `_execute_loop_step` had three structurally identical `StepResult(...)` constructions; a single shared helper is the correct fix.

---

### [CONCERN] `_loop_exhaust_result` — `status` is unbound after the `match` block

```python
match on_exhaust:
    case ExhaustBehavior.FAIL:
        status = ExecutionStatus.FAILED
    case ExhaustBehavior.CHECKPOINT:
        status = ExecutionStatus.PAUSED
    case ExhaustBehavior.SKIP:
        status = ExecutionStatus.SKIPPED
return StepResult(..., status=status, ...)   # ← potentially unbound
```

Pyright strict (the project's configured mode, a stated merge blocker) does not perform exhaustiveness proofs on `StrEnum` matches without a `case _:` arm, so `status` is flagged as possibly unbound. The analogous `evaluate_condition()` function at line 209 has the same shape and presumably passes today only because it is within a return path. This function is not — there is an unconditional return after the block.

Fix: add `case _: raise AssertionError(f"Unhandled ExhaustBehavior: {on_exhaust!r}")` as the final case.

---

### [CONCERN] Silent runtime drop of malformed inner step dicts is untested and undocumented

`_validate_inner_steps` silently skips inner steps that are not a single-key dict:

```python
if not isinstance(raw_inner, dict) or len(raw_inner) != 1:
    continue   # ← no ValidationError produced
```

`_unpack_inner_steps` mirrors this (`if len(raw_step) != 1: continue`). Validation checks that `steps` is a non-empty list, but does not check the structure of individual entries. A user who writes a two-key YAML mapping under one list item (`review: {} \n dispatch: {}` collapsed into the same node) produces a list whose length is 1, passes the non-empty check, but then has that entry silently dropped at runtime, leaving an empty inner body. If no `until` is set, the loop completes after one vacuous iteration with an empty `action_results` list — no warning, no error.

The project CLAUDE.md states: *"If a parser returns empty/default on bad input, add at least one test using real-world input to catch silent failures."* No such test exists here.

Minimum fix: add a `ValidationError` in `_validate_inner_steps` for entries that are not a single-key dict, and a test that exercises a two-key-entry list.

---

### [CONCERN] OCP: `execute_pipeline` dispatch chain extended again

The `EACH` / `FAN_OUT` / `LOOP` special-cases are dispatched through a growing `elif step.step_type == StepTypeName.X:` chain (lines ~610, ~643, ~661). Each new step type requiring a custom executor requires editing the body of `execute_pipeline`. This is an OCP violation — the function must be modified rather than extended.

This is pre-existing debt, but this slice adds a third entry to the chain. A straightforward remedy is a `_BODY_EXECUTORS: dict[StepTypeName, Callable[..., Awaitable[StepResult]]]` registry populated alongside `register_step_type`. That keeps `execute_pipeline` closed to modification for future step types.

This should be tracked even if not fixed in this slice.

---

### [NOTE] `prior_outputs` is not propagated across inner steps within a loop body iteration

Each inner step in `_execute_loop_body` receives the same `prior_outputs` snapshot from the outer pipeline. Results from one inner step are not added to `prior_outputs` before the next inner step runs within the same iteration. This mirrors `_execute_each_step` (line 1173) so it is consistent, but it is undocumented. If the intended semantics are that inner steps are isolated from one another's outputs, a comment to that effect would prevent future confusion or a misguided "fix."

---

### [NOTE] `_parse_loop_config` does not reject `bool` for `max`

`LoopStepType.validate()` explicitly rejects booleans at line 37 (`isinstance(max_val, bool)` check). `_parse_loop_config` uses only `isinstance(max_iter, int)`, which accepts `bool` subclasses (`True == 1` passes the `>= 1` check). The inconsistency is harmless for the `loop:` step type since `validate()` runs first, but the single-step `loop:` sub-field path (line 684) calls `_parse_loop_config` directly. A YAML `max: true` on a single-step loop would silently run exactly one iteration.
