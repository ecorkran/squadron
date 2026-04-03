---
docType: tasks
slice: pipeline-executor-and-loops
project: squadron
lld: user/slices/149-slice.pipeline-executor-and-loops.md
dependencies: [147, 148]
projectState: Slices 147 and 148 complete — step types and pipeline loader/validator in place. executor.py does not exist. collection.py is a stub.
dateCreated: 20260403
dateUpdated: 20260403
status: complete
---

## Context Summary

- Working on slice 149: Pipeline Executor and Loops
- Slices 147 (step types) and 148 (pipeline loader) are complete and merged to main
- `src/squadron/pipeline/executor.py` does not exist yet
- `src/squadron/pipeline/steps/collection.py` is a stub (4 lines, comment only)
- All actions (cf-op, commit, devlog, dispatch, review, compact, checkpoint) are registered
- All step types (design, tasks, implement, compact, review, devlog) are registered
- `pytest-asyncio` is already a test dependency
- Next planned slices: 150 (State/Resume), 151 (CLI)

---

## T1 — Test Infrastructure

- [x] Create `tests/pipeline/test_executor.py` with conftest-compatible fixtures:
  - [x] `make_action_result(success, action_type, verdict=None)` fixture helper
  - [x] `make_step_config(step_type, name, config)` fixture helper
  - [x] `make_pipeline(steps, params)` fixture helper returning `PipelineDefinition`
  - [x] `mock_action(results)` helper — returns an async mock Action whose `execute()` yields each result in turn
  - [x] `mock_step_type(actions)` helper — returns a StepType whose `expand()` returns the given `(action_type, config)` pairs
  - [x] Mark all async tests with `@pytest.mark.asyncio`
  - [x] Success: fixtures are importable, helpers build valid dataclass instances

---

## T2 — Result Types and ExecutionStatus

- [x] In `src/squadron/pipeline/executor.py`, define:
  - [x] `ExecutionStatus(StrEnum)` with values: `COMPLETED`, `FAILED`, `PAUSED`, `SKIPPED`
  - [x] `StepResult` dataclass: `step_name: str`, `step_type: str`, `status: ExecutionStatus`, `action_results: list[ActionResult]`, `iteration: int = 0`, `error: str | None = None`
  - [x] `PipelineResult` dataclass: `pipeline_name: str`, `status: ExecutionStatus`, `step_results: list[StepResult]`, `paused_at: str | None = None`, `error: str | None = None`
  - [x] `__all__` exports both dataclasses and `ExecutionStatus`
  - [x] Success: `from squadron.pipeline.executor import ExecutionStatus, StepResult, PipelineResult` imports cleanly; pyright 0 errors

- [x] Tests for result types:
  - [x] `StepResult` can be constructed with minimal args
  - [x] `ExecutionStatus.COMPLETED.value == "completed"` (and each value)
  - [x] `PipelineResult.paused_at` defaults to `None`

---

## T3 — Parameter Resolution

- [x] Implement `resolve_placeholders(config, params) -> dict[str, object]` in `executor.py`:
  - [x] Simple `{name}` — replaces with `str(params[name])`; leaves as-is if name not in params
  - [x] Dotted `{name.field}` — looks up `params[name]` (must be dict), then `dict[field]`; leaves as-is if not resolvable
  - [x] Non-string config values pass through unchanged
  - [x] Nested dicts in config are resolved recursively
  - [x] Lists in config: each string element is resolved; non-strings left alone
  - [x] Export `resolve_placeholders` in `__all__`

- [x] Tests for `resolve_placeholders`:
  - [x] Simple replacement: `{slice}` → `"191"` given `params={"slice": "191"}`
  - [x] Missing param: `{missing}` left as `"{missing}"`
  - [x] Dotted path: `{slice.index}` → `"191"` given `params={"slice": {"index": "191"}}`
  - [x] Non-string value untouched: `{"phase": 4}` → `{"phase": 4}`
  - [x] Nested dict: recursive resolution works
  - [x] Multiple placeholders in one string value

---

## T4 — Loop Condition Grammar

- [x] Implement `LoopCondition(StrEnum)` in `executor.py`:
  - [x] `REVIEW_PASS = "review.pass"`
  - [x] `REVIEW_CONCERNS_OR_BETTER = "review.concerns_or_better"`
  - [x] `ACTION_SUCCESS = "action.success"`

- [x] Implement `evaluate_condition(condition, action_results) -> bool`:
  - [x] `REVIEW_PASS`: find last `ActionResult` with `verdict is not None`; return `verdict == "PASS"`
  - [x] `REVIEW_CONCERNS_OR_BETTER`: same lookup; return `verdict in {"PASS", "CONCERNS"}`
  - [x] `ACTION_SUCCESS`: return `all(r.success for r in action_results)`
  - [x] Returns `False` if no matching results found (e.g., no review action in results)
  - [x] Export both in `__all__`

- [x] Tests for `evaluate_condition`:
  - [x] `REVIEW_PASS` with PASS verdict → True
  - [x] `REVIEW_PASS` with FAIL verdict → False
  - [x] `REVIEW_CONCERNS_OR_BETTER` with CONCERNS → True
  - [x] `REVIEW_CONCERNS_OR_BETTER` with FAIL → False
  - [x] `ACTION_SUCCESS` with all success → True
  - [x] `ACTION_SUCCESS` with one failure → False
  - [x] `REVIEW_PASS` with no review actions in results → False

---

## T5a — Core Executor: Happy Path

- [x] Implement `execute_pipeline(definition, params, *, resolver, cf_client, cwd=None, run_id=None, start_from=None, on_step_complete=None) -> PipelineResult` in `executor.py`:
  - [x] Merge params with definition defaults; validate required params (raise `ValueError` for missing)
  - [x] Auto-generate `run_id` via `uuid.uuid4().hex[:12]` if not provided
  - [x] Default `cwd` to `os.getcwd()` if not provided
  - [x] For each step: resolve placeholders, look up step type, expand to action list
  - [x] For `each` step type: skip expansion (return empty), handle separately in T8
  - [x] For each action: build `ActionContext`, call `action.execute(context)`, accumulate in `prior_outputs`
  - [x] `ActionContext.params` = merged pipeline params + action config (action config keys override)
  - [x] Key `prior_outputs` by `"{action_type}-{index}"` within the step
  - [x] On step success: build `StepResult(status=COMPLETED)`, call `on_step_complete`
  - [x] After all steps: return `PipelineResult(status=COMPLETED)`
  - [x] Import all action and step modules to trigger registration (same pattern as `validate_pipeline`)

- [x] Tests for happy path (use mocked step types and actions):
  - [x] Single step, single action, success → `PipelineResult(status=COMPLETED)`, 1 step result
  - [x] Two steps → both step results present in order
  - [x] `prior_outputs` from step 1 action available in step 2 action context
  - [x] `on_step_complete` called once per completed step
  - [x] Missing required param → `ValueError`

---

## T5b — Core Executor: Error Handling and Skip Logic

- [x] Add `start_from` skip logic to `execute_pipeline()`:
  - [x] Skip steps before the named step (match by `step.name`); raise `ValueError` if name not found in definition

- [x] Add failure and checkpoint handling to `execute_pipeline()`:
  - [x] On checkpoint pause (`outputs.get("checkpoint") == "paused"`): build `StepResult(status=PAUSED)`, `PipelineResult(status=PAUSED, paused_at=step_name)`, call `on_step_complete`, return immediately
  - [x] On action failure (`result.success is False`): build `StepResult(status=FAILED)`, `PipelineResult(status=FAILED)`, call callback, return

- [x] Tests for error handling and skip:
  - [x] `start_from` skips earlier steps; named step executes
  - [x] `start_from` with unknown step name → `ValueError`
  - [x] Action failure → `FAILED`, pipeline stops (step 2 does not execute)
  - [x] Checkpoint pause → `PAUSED`, `paused_at` set to the correct step name

**Commit:** `feat: add pipeline executor core — sequential step execution`

---

## T6 — Retry Loop Execution

- [x] Implement `ExhaustBehavior(StrEnum)` in `executor.py`:
  - [x] `FAIL = "fail"`, `CHECKPOINT = "checkpoint"`, `SKIP = "skip"`

- [x] Implement `LoopConfig` dataclass: `max: int`, `until: LoopCondition | None = None`, `on_exhaust: ExhaustBehavior = ExhaustBehavior.FAIL`, `strategy: str | None = None`

- [x] Parse `loop` dict from step config into `LoopConfig`; raise `ValueError` for invalid `until` or `on_exhaust` values

- [x] Wrap step action execution in loop when `loop` key present in step config:
  - [x] Log warning if `strategy` is set: "Loop strategy '{strategy}' not implemented, falling back to basic max-iteration loop"
  - [x] For each iteration 1..max:
    - Execute full action sequence
    - Evaluate `until` condition if set; break if True
    - On checkpoint pause: return `PAUSED` immediately (checkpoints stop loops)
    - On all-actions failure: continue to next iteration (transient failure)
  - [x] If max exhausted without condition met:
    - `on_exhaust=FAIL` → `StepResult(status=FAILED)`, pipeline stops
    - `on_exhaust=CHECKPOINT` → `StepResult(status=PAUSED)`, `PipelineResult(status=PAUSED, paused_at=step_name)`
    - `on_exhaust=SKIP` → `StepResult(status=SKIPPED)`, pipeline continues to next step
  - [x] `StepResult.iteration` holds the final iteration number

- [x] Tests for retry loops:
  - [x] Loop runs once and condition met → `COMPLETED`, `iteration=1`
  - [x] Loop runs 3 times, condition met on 3rd → `COMPLETED`, `iteration=3`
  - [x] Max=3, condition never met, `on_exhaust=fail` → `FAILED`
  - [x] Max=3, condition never met, `on_exhaust=checkpoint` → `PAUSED`
  - [x] Max=3, condition never met, `on_exhaust=skip` → `SKIPPED`, pipeline continues
  - [x] Checkpoint in iteration 2 → `PAUSED` immediately (loop stops)
  - [x] `strategy` set → warning logged, loop still runs with `max`
  - [x] Invalid `on_exhaust` value → `ValueError`

**Commit:** `feat: add retry loop execution to pipeline executor`

---

## T7 — Collection Step Type (`each`)

- [x] Replace stub `src/squadron/pipeline/steps/collection.py` with `EachStepType`:
  - [x] Class with `step_type = "each"` property
  - [x] `validate(config) -> list[ValidationError]`:
    - Require `source` (str), `as` (str), `steps` (list)
    - Source string must match `r"(\w+)\.(\w+)\([^)]*\)"` pattern (structural check only — registry check is executor-time, not validate-time)
    - Inner `steps` list must be non-empty
    - Return `ValidationError` for each violation
  - [x] `expand(config) -> list[tuple[str, dict[str, object]]]`:
    - Returns empty list — executor handles `each` execution directly
  - [x] Register as `StepTypeName.EACH` at module load
  - [x] Export `EachStepType` from module

- [x] Tests for `EachStepType`:
  - [x] `validate()` returns no errors for valid `design-batch`-style config
  - [x] `validate()` errors on missing `source`, missing `as`, missing `steps`
  - [x] `validate()` errors on malformed source string (no match for the regex pattern)
  - [x] `validate()` errors on empty inner steps list
  - [x] `expand()` returns empty list
  - [x] Step type is registered under `"each"` after import

---

## T8 — Source Registry and `each` Execution

- [x] In `executor.py`, implement source query infrastructure:
  - [x] `SourceFn` type alias: `Callable[[list[str], ContextForgeClient, dict[str, object]], Awaitable[list[dict[str, object]]]]`
  - [x] `_SOURCE_REGISTRY: dict[tuple[str, str], SourceFn]`
  - [x] `_cf_unfinished_slices(args, cf_client, params)`: calls `cf_client.list_slices()`, filters `status != "complete"`, returns list of dicts with keys `index`, `name`, `status`, `design_file`
  - [x] Register `("cf", "unfinished_slices")` in the registry
  - [x] `_parse_source(source_str) -> tuple[str, str, list[str]]`: parses namespace, function, args with regex `r"(\w+)\.(\w+)\(([^)]*)\)"`; raises `ValueError` for unrecognized namespace/function combination (checked against `_SOURCE_REGISTRY`)

- [x] In `execute_pipeline()`, add `each` branch:
  - [x] Detect `step.step_type == "each"` before normal expand path
  - [x] Parse `source`, `as`, `steps` from step config
  - [x] Resolve placeholders in `source` string
  - [x] Call `_parse_source()`, resolve args with placeholders, invoke source function
  - [x] For each item: augment params with `{as_name: item_dict}`, parse inner steps (reuse `PipelineSchema._unpack_steps` or equivalent), recursively call step execution logic
  - [x] On inner step failure or pause: propagate status upward, stop iteration
  - [x] After all items: `StepResult(status=COMPLETED)`, call callback

- [x] Tests for `each` execution:
  - [x] CF client returning 2 unfinished slices → inner steps run twice
  - [x] CF client returning 0 slices → `each` step completes with 0 iterations
  - [x] `{slice.index}` resolves to correct value in inner step config for each item
  - [x] Inner step failure on item 1 → propagates `FAILED`, item 2 not processed
  - [x] Inner step checkpoint on item 2 → propagates `PAUSED`
  - [x] Unrecognized source raises `ValueError`
  - [x] `_cf_unfinished_slices` filters correctly (status == "complete" excluded)

**Commit:** `feat: add each collection loop and source registry to executor`

---

## T9 — Integration Tests

- [x] Create `tests/pipeline/test_executor_integration.py`:
  - [x] Load `slice-lifecycle` via `load_pipeline()`, execute with mocked actions that return success; assert 5 `StepResult`s, all `COMPLETED`
  - [x] Load `review-only`, execute with `template=arch` param, mock review returning PASS; assert COMPLETED
  - [x] Load `design-batch`, execute with mock CF returning 2 slices; assert inner design steps ran twice
  - [x] `on_step_complete` receives each step result in order
  - [x] `start_from="compact-2"` in `slice-lifecycle` skips design-0 and tasks-1 (steps before compact)
  - [x] Missing required param `slice` for `slice-lifecycle` → `ValueError`

- [x] Success: all integration tests pass with mocked actions; real CF not required

---

## T10 — Verification and Cleanup

- [x] Run full test suite: `python -m pytest tests/pipeline/ -v` — all pass
- [x] Run pyright: `pyright src/squadron/pipeline/executor.py src/squadron/pipeline/steps/collection.py` — 0 errors
- [x] Run ruff: `ruff check src/squadron/pipeline/ && ruff format --check src/squadron/pipeline/` — clean
- [x] Confirm `each` is in `StepTypeName` enum (already present in 147 — verify it's wired to `EachStepType`)
- [x] Check `collection.py` is imported somewhere to trigger registration (add to `validate_pipeline` imports in `loader.py` if not already)
- [x] Update slice 149 `status: in_progress → complete` in frontmatter
- [x] Check off slice 149 in `140-slices.pipeline-foundation.md`
- [x] Update `CHANGELOG.md` under `[Unreleased]`
- [x] Write DEVLOG entry

**Commit:** `docs: mark slice 149 pipeline executor complete`
