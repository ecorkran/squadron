---
docType: tasks
slice: pipeline-executor-and-loops
project: squadron
lld: user/slices/149-slice.pipeline-executor-and-loops.md
dependencies: [147, 148]
projectState: Slices 147 and 148 complete — step types and pipeline loader/validator in place. executor.py does not exist. collection.py is a stub.
dateCreated: 20260403
dateUpdated: 20260403
status: not_started
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

- [ ] Create `tests/pipeline/test_executor.py` with conftest-compatible fixtures:
  - [ ] `make_action_result(success, action_type, verdict=None)` fixture helper
  - [ ] `make_step_config(step_type, name, config)` fixture helper
  - [ ] `make_pipeline(steps, params)` fixture helper returning `PipelineDefinition`
  - [ ] `mock_action(results)` helper — returns an async mock Action whose `execute()` yields each result in turn
  - [ ] `mock_step_type(actions)` helper — returns a StepType whose `expand()` returns the given `(action_type, config)` pairs
  - [ ] Mark all async tests with `@pytest.mark.asyncio`
  - [ ] Success: fixtures are importable, helpers build valid dataclass instances

---

## T2 — Result Types and ExecutionStatus

- [ ] In `src/squadron/pipeline/executor.py`, define:
  - [ ] `ExecutionStatus(StrEnum)` with values: `COMPLETED`, `FAILED`, `PAUSED`, `SKIPPED`
  - [ ] `StepResult` dataclass: `step_name: str`, `step_type: str`, `status: ExecutionStatus`, `action_results: list[ActionResult]`, `iteration: int = 0`, `error: str | None = None`
  - [ ] `PipelineResult` dataclass: `pipeline_name: str`, `status: ExecutionStatus`, `step_results: list[StepResult]`, `paused_at: str | None = None`, `error: str | None = None`
  - [ ] `__all__` exports both dataclasses and `ExecutionStatus`
  - [ ] Success: `from squadron.pipeline.executor import ExecutionStatus, StepResult, PipelineResult` imports cleanly; pyright 0 errors

- [ ] Tests for result types:
  - [ ] `StepResult` can be constructed with minimal args
  - [ ] `ExecutionStatus.COMPLETED.value == "completed"` (and each value)
  - [ ] `PipelineResult.paused_at` defaults to `None`

---

## T3 — Parameter Resolution

- [ ] Implement `resolve_placeholders(config, params) -> dict[str, object]` in `executor.py`:
  - [ ] Simple `{name}` — replaces with `str(params[name])`; leaves as-is if name not in params
  - [ ] Dotted `{name.field}` — looks up `params[name]` (must be dict), then `dict[field]`; leaves as-is if not resolvable
  - [ ] Non-string config values pass through unchanged
  - [ ] Nested dicts in config are resolved recursively
  - [ ] Lists in config: each string element is resolved; non-strings left alone
  - [ ] Export `resolve_placeholders` in `__all__`

- [ ] Tests for `resolve_placeholders`:
  - [ ] Simple replacement: `{slice}` → `"191"` given `params={"slice": "191"}`
  - [ ] Missing param: `{missing}` left as `"{missing}"`
  - [ ] Dotted path: `{slice.index}` → `"191"` given `params={"slice": {"index": "191"}}`
  - [ ] Non-string value untouched: `{"phase": 4}` → `{"phase": 4}`
  - [ ] Nested dict: recursive resolution works
  - [ ] Multiple placeholders in one string value

---

## T4 — Loop Condition Grammar

- [ ] Implement `LoopCondition(StrEnum)` in `executor.py`:
  - [ ] `REVIEW_PASS = "review.pass"`
  - [ ] `REVIEW_CONCERNS_OR_BETTER = "review.concerns_or_better"`
  - [ ] `ACTION_SUCCESS = "action.success"`

- [ ] Implement `evaluate_condition(condition, action_results) -> bool`:
  - [ ] `REVIEW_PASS`: find last `ActionResult` with `verdict is not None`; return `verdict == "PASS"`
  - [ ] `REVIEW_CONCERNS_OR_BETTER`: same lookup; return `verdict in {"PASS", "CONCERNS"}`
  - [ ] `ACTION_SUCCESS`: return `all(r.success for r in action_results)`
  - [ ] Returns `False` if no matching results found (e.g., no review action in results)
  - [ ] Export both in `__all__`

- [ ] Tests for `evaluate_condition`:
  - [ ] `REVIEW_PASS` with PASS verdict → True
  - [ ] `REVIEW_PASS` with FAIL verdict → False
  - [ ] `REVIEW_CONCERNS_OR_BETTER` with CONCERNS → True
  - [ ] `REVIEW_CONCERNS_OR_BETTER` with FAIL → False
  - [ ] `ACTION_SUCCESS` with all success → True
  - [ ] `ACTION_SUCCESS` with one failure → False
  - [ ] `REVIEW_PASS` with no review actions in results → False

---

## T5a — Core Executor: Happy Path

- [ ] Implement `execute_pipeline(definition, params, *, resolver, cf_client, cwd=None, run_id=None, start_from=None, on_step_complete=None) -> PipelineResult` in `executor.py`:
  - [ ] Merge params with definition defaults; validate required params (raise `ValueError` for missing)
  - [ ] Auto-generate `run_id` via `uuid.uuid4().hex[:12]` if not provided
  - [ ] Default `cwd` to `os.getcwd()` if not provided
  - [ ] For each step: resolve placeholders, look up step type, expand to action list
  - [ ] For `each` step type: skip expansion (return empty), handle separately in T8
  - [ ] For each action: build `ActionContext`, call `action.execute(context)`, accumulate in `prior_outputs`
  - [ ] `ActionContext.params` = merged pipeline params + action config (action config keys override)
  - [ ] Key `prior_outputs` by `"{action_type}-{index}"` within the step
  - [ ] On step success: build `StepResult(status=COMPLETED)`, call `on_step_complete`
  - [ ] After all steps: return `PipelineResult(status=COMPLETED)`
  - [ ] Import all action and step modules to trigger registration (same pattern as `validate_pipeline`)

- [ ] Tests for happy path (use mocked step types and actions):
  - [ ] Single step, single action, success → `PipelineResult(status=COMPLETED)`, 1 step result
  - [ ] Two steps → both step results present in order
  - [ ] `prior_outputs` from step 1 action available in step 2 action context
  - [ ] `on_step_complete` called once per completed step
  - [ ] Missing required param → `ValueError`

---

## T5b — Core Executor: Error Handling and Skip Logic

- [ ] Add `start_from` skip logic to `execute_pipeline()`:
  - [ ] Skip steps before the named step (match by `step.name`); raise `ValueError` if name not found in definition

- [ ] Add failure and checkpoint handling to `execute_pipeline()`:
  - [ ] On checkpoint pause (`outputs.get("checkpoint") == "paused"`): build `StepResult(status=PAUSED)`, `PipelineResult(status=PAUSED, paused_at=step_name)`, call `on_step_complete`, return immediately
  - [ ] On action failure (`result.success is False`): build `StepResult(status=FAILED)`, `PipelineResult(status=FAILED)`, call callback, return

- [ ] Tests for error handling and skip:
  - [ ] `start_from` skips earlier steps; named step executes
  - [ ] `start_from` with unknown step name → `ValueError`
  - [ ] Action failure → `FAILED`, pipeline stops (step 2 does not execute)
  - [ ] Checkpoint pause → `PAUSED`, `paused_at` set to the correct step name

**Commit:** `feat: add pipeline executor core — sequential step execution`

---

## T6 — Retry Loop Execution

- [ ] Implement `ExhaustBehavior(StrEnum)` in `executor.py`:
  - [ ] `FAIL = "fail"`, `CHECKPOINT = "checkpoint"`, `SKIP = "skip"`

- [ ] Implement `LoopConfig` dataclass: `max: int`, `until: LoopCondition | None = None`, `on_exhaust: ExhaustBehavior = ExhaustBehavior.FAIL`, `strategy: str | None = None`

- [ ] Parse `loop` dict from step config into `LoopConfig`; raise `ValueError` for invalid `until` or `on_exhaust` values

- [ ] Wrap step action execution in loop when `loop` key present in step config:
  - [ ] Log warning if `strategy` is set: "Loop strategy '{strategy}' not implemented, falling back to basic max-iteration loop"
  - [ ] For each iteration 1..max:
    - Execute full action sequence
    - Evaluate `until` condition if set; break if True
    - On checkpoint pause: return `PAUSED` immediately (checkpoints stop loops)
    - On all-actions failure: continue to next iteration (transient failure)
  - [ ] If max exhausted without condition met:
    - `on_exhaust=FAIL` → `StepResult(status=FAILED)`, pipeline stops
    - `on_exhaust=CHECKPOINT` → `StepResult(status=PAUSED)`, `PipelineResult(status=PAUSED, paused_at=step_name)`
    - `on_exhaust=SKIP` → `StepResult(status=SKIPPED)`, pipeline continues to next step
  - [ ] `StepResult.iteration` holds the final iteration number

- [ ] Tests for retry loops:
  - [ ] Loop runs once and condition met → `COMPLETED`, `iteration=1`
  - [ ] Loop runs 3 times, condition met on 3rd → `COMPLETED`, `iteration=3`
  - [ ] Max=3, condition never met, `on_exhaust=fail` → `FAILED`
  - [ ] Max=3, condition never met, `on_exhaust=checkpoint` → `PAUSED`
  - [ ] Max=3, condition never met, `on_exhaust=skip` → `SKIPPED`, pipeline continues
  - [ ] Checkpoint in iteration 2 → `PAUSED` immediately (loop stops)
  - [ ] `strategy` set → warning logged, loop still runs with `max`
  - [ ] Invalid `on_exhaust` value → `ValueError`

**Commit:** `feat: add retry loop execution to pipeline executor`

---

## T7 — Collection Step Type (`each`)

- [ ] Replace stub `src/squadron/pipeline/steps/collection.py` with `EachStepType`:
  - [ ] Class with `step_type = "each"` property
  - [ ] `validate(config) -> list[ValidationError]`:
    - Require `source` (str), `as` (str), `steps` (list)
    - Source string must match `r"(\w+)\.(\w+)\([^)]*\)"` pattern (structural check only — registry check is executor-time, not validate-time)
    - Inner `steps` list must be non-empty
    - Return `ValidationError` for each violation
  - [ ] `expand(config) -> list[tuple[str, dict[str, object]]]`:
    - Returns empty list — executor handles `each` execution directly
  - [ ] Register as `StepTypeName.EACH` at module load
  - [ ] Export `EachStepType` from module

- [ ] Tests for `EachStepType`:
  - [ ] `validate()` returns no errors for valid `design-batch`-style config
  - [ ] `validate()` errors on missing `source`, missing `as`, missing `steps`
  - [ ] `validate()` errors on malformed source string (no match for the regex pattern)
  - [ ] `validate()` errors on empty inner steps list
  - [ ] `expand()` returns empty list
  - [ ] Step type is registered under `"each"` after import

---

## T8 — Source Registry and `each` Execution

- [ ] In `executor.py`, implement source query infrastructure:
  - [ ] `SourceFn` type alias: `Callable[[list[str], ContextForgeClient, dict[str, object]], Awaitable[list[dict[str, object]]]]`
  - [ ] `_SOURCE_REGISTRY: dict[tuple[str, str], SourceFn]`
  - [ ] `_cf_unfinished_slices(args, cf_client, params)`: calls `cf_client.list_slices()`, filters `status != "complete"`, returns list of dicts with keys `index`, `name`, `status`, `design_file`
  - [ ] Register `("cf", "unfinished_slices")` in the registry
  - [ ] `_parse_source(source_str) -> tuple[str, str, list[str]]`: parses namespace, function, args with regex `r"(\w+)\.(\w+)\(([^)]*)\)"`; raises `ValueError` for unrecognized namespace/function combination (checked against `_SOURCE_REGISTRY`)

- [ ] In `execute_pipeline()`, add `each` branch:
  - [ ] Detect `step.step_type == "each"` before normal expand path
  - [ ] Parse `source`, `as`, `steps` from step config
  - [ ] Resolve placeholders in `source` string
  - [ ] Call `_parse_source()`, resolve args with placeholders, invoke source function
  - [ ] For each item: augment params with `{as_name: item_dict}`, parse inner steps (reuse `PipelineSchema._unpack_steps` or equivalent), recursively call step execution logic
  - [ ] On inner step failure or pause: propagate status upward, stop iteration
  - [ ] After all items: `StepResult(status=COMPLETED)`, call callback

- [ ] Tests for `each` execution:
  - [ ] CF client returning 2 unfinished slices → inner steps run twice
  - [ ] CF client returning 0 slices → `each` step completes with 0 iterations
  - [ ] `{slice.index}` resolves to correct value in inner step config for each item
  - [ ] Inner step failure on item 1 → propagates `FAILED`, item 2 not processed
  - [ ] Inner step checkpoint on item 2 → propagates `PAUSED`
  - [ ] Unrecognized source raises `ValueError`
  - [ ] `_cf_unfinished_slices` filters correctly (status == "complete" excluded)

**Commit:** `feat: add each collection loop and source registry to executor`

---

## T9 — Integration Tests

- [ ] Create `tests/pipeline/test_executor_integration.py`:
  - [ ] Load `slice-lifecycle` via `load_pipeline()`, execute with mocked actions that return success; assert 5 `StepResult`s, all `COMPLETED`
  - [ ] Load `review-only`, execute with `template=arch` param, mock review returning PASS; assert COMPLETED
  - [ ] Load `design-batch`, execute with mock CF returning 2 slices; assert inner design steps ran twice
  - [ ] `on_step_complete` receives each step result in order
  - [ ] `start_from="compact-2"` in `slice-lifecycle` skips design-0 and tasks-1 (steps before compact)
  - [ ] Missing required param `slice` for `slice-lifecycle` → `ValueError`

- [ ] Success: all integration tests pass with mocked actions; real CF not required

---

## T10 — Verification and Cleanup

- [ ] Run full test suite: `python -m pytest tests/pipeline/ -v` — all pass
- [ ] Run pyright: `pyright src/squadron/pipeline/executor.py src/squadron/pipeline/steps/collection.py` — 0 errors
- [ ] Run ruff: `ruff check src/squadron/pipeline/ && ruff format --check src/squadron/pipeline/` — clean
- [ ] Confirm `each` is in `StepTypeName` enum (already present in 147 — verify it's wired to `EachStepType`)
- [ ] Check `collection.py` is imported somewhere to trigger registration (add to `validate_pipeline` imports in `loader.py` if not already)
- [ ] Update slice 149 `status: in_progress → complete` in frontmatter
- [ ] Check off slice 149 in `140-slices.pipeline-foundation.md`
- [ ] Update `CHANGELOG.md` under `[Unreleased]`
- [ ] Write DEVLOG entry

**Commit:** `docs: mark slice 149 pipeline executor complete`
