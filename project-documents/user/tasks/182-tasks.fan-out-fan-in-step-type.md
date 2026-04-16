---
docType: tasks
slice: fan-out-fan-in-step-type
project: squadron
lld: user/slices/182-slice.fan-out-fan-in-step-type.md
dependencies: [149, 181]
projectState: >
  Slices 180 (model pool infra) and 181 (pool resolver integration) complete.
  Pipeline executor, step-type registry, and action registry are stable.
  Fan-out is the next infrastructure slice before ensemble review (189).
dateCreated: 20260415
dateUpdated: 20260415
dateCompleted: 20260415
status: complete
---

## Context Summary

- Implementing `fan_out` step type: parallel multi-model branch dispatch with fan-in reduction
- Mirrors the `each` step pattern — `expand()` returns `[]`, executor owns execution
- New package: `src/squadron/pipeline/intelligence/fan_in/` (protocol + reducers)
- New step module: `src/squadron/pipeline/steps/fan_out.py`
- Executor changes: `_execute_fan_out_step` + dispatch branch + import trigger
- SDK session guard: raise explicit error (non-SDK / agent-path is the target)
- Pool support: call `resolver.resolve()` N times (no new PoolBackend method)
- Direct dependency: slice 149 (executor), slice 181 (pool resolver)
- Next slice: 189 (Ensemble Review) — registers `merge_findings` reducer, no fan-out changes

---

## Task 1 — Add `FAN_OUT` to `StepTypeName` enum

- [x] Open `src/squadron/pipeline/steps/__init__.py`
  - [x] Add `FAN_OUT = "fan_out"` to `StepTypeName` (after `EACH`, before `DEVLOG`)
  - [x] **Success:** `StepTypeName.FAN_OUT` resolves to the string `"fan_out"`; all existing enum members unchanged; `ruff` and pyright pass

---

## Task 2 — Create test infrastructure for fan-out

- [x] Create `tests/pipeline/steps/test_fan_out.py` (empty stub)
  - [x] Add module docstring; import pytest and any fixtures already used in `tests/pipeline/steps/`
- [x] Create `tests/pipeline/intelligence/fan_in/` directory with `__init__.py`
- [x] Create `tests/pipeline/intelligence/fan_in/test_reducers.py` (empty stub)
  - [x] Add module docstring; import pytest
- [x] Confirm `conftest.py` fixtures for step/executor tests are accessible from new test paths
  - [x] **Success:** `pytest tests/pipeline/steps/test_fan_out.py tests/pipeline/intelligence/fan_in/test_reducers.py` collects 0 tests with no errors

---

## Task 3 — Implement `FanInReducer` protocol

- [x] Create `src/squadron/pipeline/intelligence/fan_in/__init__.py` (empty)
- [x] Create `src/squadron/pipeline/intelligence/fan_in/protocol.py`
  - [x] Define `FanInReducer` protocol with `reduce(branch_results, config) -> ActionResult`
    - `branch_results: list[StepResult]`, `config: dict[str, object]`
  - [x] Export `FanInReducer` from `__init__.py`
  - [x] **Success:** Protocol is `runtime_checkable`; pyright reports no errors

---

## Task 4 — Test `FanInReducer` protocol

- [x] In `tests/pipeline/intelligence/fan_in/test_reducers.py`
  - [x] Test that a class implementing `reduce(branch_results, config)` satisfies `isinstance(obj, FanInReducer)`
  - [x] Test that a class missing `reduce` does not satisfy the protocol check
  - [x] **Success:** Both tests pass

---

## Task 5 — Implement `collect` reducer

- [x] Create `src/squadron/pipeline/intelligence/fan_in/reducers.py`
  - [x] Define `_REDUCER_REGISTRY: dict[str, FanInReducer]`
  - [x] Implement `CollectReducer`:
    - `success = True` if all branches succeeded; `False` otherwise
    - `outputs["branches"]` = list of dicts, one per branch: `{"step_name", "status", "action_results"}` where `action_results` is a list of `{"action_type", "success", "outputs", "verdict"}` dicts
    - `action_type = "fan_out"`
  - [x] Register as `"collect"` in `_REDUCER_REGISTRY`
  - [x] Implement `get_reducer(name: str) -> FanInReducer` — raises `KeyError` with registered names on miss
  - [x] Export `get_reducer` and `_REDUCER_REGISTRY` from `__init__.py`
  - [x] **Success:** `CollectReducer` satisfies `FanInReducer` protocol; pyright clean

---

## Task 6 — Test `collect` reducer

- [x] In `test_reducers.py`, add tests for `CollectReducer`:
  - [x] All branches succeed → `result.success is True`, `outputs["branches"]` has correct length
  - [x] One branch fails → `result.success is False`
  - [x] `outputs["branches"]` contains expected keys for each branch
  - [x] `get_reducer("collect")` returns a `CollectReducer` instance
  - [x] `get_reducer("nonexistent")` raises `KeyError`
  - [x] **Success:** All tests pass

---

## Task 7 — Implement `first_pass` reducer

- [x] In `reducers.py`, add `FirstPassReducer`:
  - [x] Iterate `branch_results`; return the `ActionResult` from the first branch where any action result has `verdict == "PASS"`
  - [x] If no branch passes, return the `ActionResult` from the last branch
  - [x] `action_type = "fan_out"`; `success = True` in both cases (reducer succeeded; caller inspects verdict)
  - [x] Register as `"first_pass"` in `_REDUCER_REGISTRY`
  - [x] **Success:** Reducer registered; pyright clean

---

## Task 8 — Test `first_pass` reducer

- [x] In `test_reducers.py`, add tests for `FirstPassReducer`:
  - [x] First branch has PASS verdict → that branch's data is returned
  - [x] Second branch has PASS, first does not → second branch returned
  - [x] No branch passes → last branch returned
  - [x] `get_reducer("first_pass")` returns a `FirstPassReducer` instance
  - [x] **Success:** All tests pass; commit `feat: add FanInReducer protocol and collect/first_pass reducers`

---

## Task 9 — Implement `FanOutStepType`

- [x] Create `src/squadron/pipeline/steps/fan_out.py`
  - [x] Implement `FanOutStepType` satisfying the `StepType` protocol
  - [x] `step_type` property returns `StepTypeName.FAN_OUT`
  - [x] `expand()` returns `[]`
  - [x] `validate()` checks (each violation appends a `ValidationError`):
    1. `models` is present
    2. `inner` is present and parseable as a single-key step dict
    3. Inner step type is not `"fan_out"` (no nesting)
    4. If `models` is a string starting with `"pool:"`, `n` must be a positive integer
    5. If `fan_in` is present, it must be a registered reducer name (use `get_reducer`)
  - [x] Call `register_step_type(StepTypeName.FAN_OUT, FanOutStepType())` at module level
  - [x] **Success:** Module imports without error; `get_step_type("fan_out")` returns the instance; pyright clean

---

## Task 10 — Test `FanOutStepType` validation

- [x] In `test_fan_out.py`, add validation tests:
  - [x] Missing `models` → error on field `models`
  - [x] Missing `inner` → error on field `inner`
  - [x] Nested `fan_out` inner step → error on field `inner`
  - [x] `models: "pool:review"` without `n` → error on field `n`
  - [x] `models: "pool:review"` with `n: 3` → no error for that field
  - [x] Unregistered `fan_in` name → error on field `fan_in`
  - [x] Valid config (explicit list, no `fan_in`) → empty error list
  - [x] **Success:** All tests pass; commit `feat: add FanOutStepType with validation`

---

## Task 11 — Implement `_execute_fan_out_step` in executor

- [x] Open `src/squadron/pipeline/executor.py`
- [x] Add `async def _execute_fan_out_step(*, step, resolved_config, step_index, merged_params, prior_outputs, pipeline_name, run_id, cwd, resolver, cf_client, sdk_session, get_step_type_fn, get_action_fn) -> StepResult`
  - [x] **Guard:** if `sdk_session is not None`, return `StepResult(status=FAILED, error="fan_out is not supported inside an SDK session step; use profile-based dispatch")` (wording must match the slice design exactly — this is a user-facing contract)
  - [x] Build model list:
    - If `models` is a `str` starting with `"pool:"`: call `resolver.resolve(f"pool:{pool_name}")` `n` times to get `model_list`
    - Else: call `resolver.resolve(str(m))` for each entry in the list
  - [x] Parse inner step via `_unpack_inner_steps([inner_raw])`; raise `ValueError` if result is empty
  - [x] Build branch coroutines: for each `(idx, model_id)` in `enumerate(model_list)`, create branch params with `_fan_out_branch_index`, `_fan_out_model`, and `model` set; call `_execute_step_once` with those params
  - [x] Gather with `asyncio.gather(*coroutines)` (no `return_exceptions`)
  - [x] If any branch result has `status == FAILED`, return `StepResult(status=FAILED)` without calling reducer
  - [x] Look up reducer via `get_reducer(fan_in_name)`; call `reducer.reduce(branch_results, resolved_config)`
  - [x] Return `StepResult(status=COMPLETED, action_results=[action_result])`
  - [x] **Success:** Function exists, type-checks clean, no circular imports

---

## Task 12 — Wire fan-out into `execute_pipeline`

- [x] In `execute_pipeline()`:
  - [x] Add import trigger: `import squadron.pipeline.steps.fan_out as _s_fan_out  # noqa: F401` alongside existing step imports; include in the `_ = (...)` tuple
  - [x] Add `fan_in` import trigger: `import squadron.pipeline.intelligence.fan_in.reducers as _fan_in_reducers  # noqa: F401`
  - [x] Add dispatch branch in the step loop (after `each` check, before `else`):
    ```python
    elif step.step_type == StepTypeName.FAN_OUT:
        step_result = await _execute_fan_out_step(...)
    ```
  - [x] Import `StepTypeName` at top of executor (if not already imported)
  - [x] **Success:** A pipeline YAML with a `fan_out` step is dispatched to `_execute_fan_out_step`; existing step types unaffected; pyright clean

---

## Task 13 — Executor integration tests

- [x] In `test_fan_out.py`, add integration tests using mocked actions:
  - [x] Explicit model list (2 models): both branches execute, `collect` reducer merges results, `StepResult.status == COMPLETED`
  - [x] `fan_in` omitted from config: default `collect` reducer is used (covers FR default wiring)
  - [x] One branch action returns `success=False`: `StepResult.status == FAILED`, reducer not called
  - [x] One branch coroutine raises an exception: `asyncio.gather` propagates it, step returns `FAILED`, reducer not called (covers the fast-fail path)
  - [x] `fan_in: "first_pass"` with one PASS branch: returned action result reflects PASS branch
  - [x] `sdk_session` is not None: step returns `FAILED` with the session guard error message (assert exact string match)
  - [x] Pool reference (`models: "pool:review"`, `n: 2`): resolver called twice; two branches execute (mock the resolver)
  - [x] Pool reference where the mocked resolver raises `ModelPoolNotImplemented`: step returns `FAILED`, error message propagates clearly (covers FR3 error path for the 181-not-available case)
  - [x] **Success:** All integration tests pass; commit `feat: add fan_out step type and executor branch`

---

## Task 14 — Full validation pass

- [x] Run `pytest` — all existing tests pass, new tests pass
- [x] Run `ruff check src/ tests/` and `ruff format src/ tests/` — no errors
- [x] Run pyright — zero new errors
- [x] Verify `StepTypeName.FAN_OUT` appears in `list_step_types()` output
- [x] Verify `get_reducer("collect")` and `get_reducer("first_pass")` resolve without error
- [x] **Success:** All checks pass; commit `chore: fan-out validation pass — ruff + pyright clean`
