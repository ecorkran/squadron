---
docType: slice-design
slice: fan-out-fan-in-step-type
project: squadron
parent: user/architecture/180-slices.pipeline-intelligence.md
dependencies: [149, 181]
interfaces: [189]
dateCreated: 20260415
dateUpdated: 20260415
status: complete
---

# Slice Design: Fan-Out / Fan-In Step Type

## Overview

Adds a `fan_out` step type to the pipeline system. A `fan_out` step dispatches
N copies of an inner step configuration concurrently — each with its own
resolved model — waits for all via `asyncio.gather`, then passes the collected
results through a configurable **reducer** (`fan_in`).

This is the general-purpose parallel branch infrastructure that ensemble review
(slice 189) depends on. It is also the first consumer of pool-based model lists
where one `fan_out` step can draw N distinct models from a pool and run them
simultaneously.

## Value

- **Architectural enabler:** Unblocks slice 189 (Ensemble Review) which requires
  multi-model parallel dispatch.
- **General purpose:** Any pipeline that wants to run the same prompt against
  several models simultaneously — for comparison, consensus, or coverage — can
  now do so without custom orchestration code.
- **Pool integration:** When `models` is a `pool:` reference, the pool resolver
  selects N models (with replacement or without, configurable) and passes them
  as the branch list, making fan-out pool-transparent.

## Technical Scope

### Included

- `FanOutStepType` — new step type registered as `fan_out`
- `StepTypeName.FAN_OUT` enum member
- `_execute_fan_out_step` — executor branch analogous to `_execute_each_step`
- `FanInReducer` protocol and two built-in reducers: `collect` and `first_pass`
- Pool expansion logic: when `models` is `pool:<name>`, resolve N distinct
  aliases from the pool rather than a single selection
- Registration wiring in `executor.py`
- Unit and integration tests

### Excluded

- `unanimous` convergence strategy (slice 189)
- Finding merge logic (slice 183/189)
- Convergence loop integration (slices 183/184/189)
- Any UI or CLI surface (fan-out is a pipeline YAML feature only)

---

## Dependencies

### Prerequisites

- **Slice 149 (Executor)** — `_execute_step_once`, `_execute_each_step`, and
  the step-type registration pattern that `fan_out` mirrors.
- **Slice 181 (Pool Resolver Integration)** — full pool support requires the
  pool resolver to expand `pool:<name>` into a list of N aliases. Without 181,
  `fan_out` works only with explicit model lists; a `pool:` `models` value raises
  `ModelPoolNotImplemented`.

### Interfaces Required

- `ModelResolver.resolve(action_model, step_model)` — called once per branch to
  resolve each model alias independently.
- `PoolBackend.select_n(pool_name, n, context)` — new method on `PoolBackend`
  needed to draw N models from a pool. This method is added as part of this
  slice (not deferred to 181) because no earlier slice needed multi-select. If
  181's `PoolBackend` already exposes this, we use it; otherwise we add it here.
- `_execute_step_once` — reused as-is; each branch is an independent step
  execution.
- `StepConfig` / `ActionContext` / `ActionResult` — existing pipeline models,
  unchanged.

---

## Architecture

### Component Structure

```
src/squadron/pipeline/
├── steps/
│   ├── __init__.py          ← add FAN_OUT to StepTypeName
│   └── fan_out.py           ← FanOutStepType (validate + expand → empty)
├── intelligence/
│   └── fan_in/
│       ├── __init__.py
│       ├── protocol.py      ← FanInReducer protocol
│       └── reducers.py      ← collect, first_pass built-ins
└── executor.py              ← _execute_fan_out_step + dispatch branch
```

The pattern mirrors `each`: the step type's `expand()` returns an empty list,
and the executor handles the step directly via its own dedicated branch.

### Data Flow

```
Pipeline YAML
  fan_out:
    models: [opus, sonnet, minimax2.7]   # or pool:review
    n: 3                                 # required when models is a pool ref
    inner:
      dispatch:
        prompt: "{context}"
    fan_in: collect                      # reducer name

         │
         ▼
FanOutStepType.validate()
         │
         ▼  (executor dispatches to _execute_fan_out_step)
         │
  ┌──────┴──────────────────────────────────────┐
  │   resolve model list                         │
  │   (explicit list OR pool_backend.select_n)   │
  └──────┬──────────────────────────────────────┘
         │
  ┌──────┴──────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
  │  branch 0            │  │  branch 1            │  │  branch N-1          │
  │  _execute_step_once  │  │  _execute_step_once  │  │  _execute_step_once  │
  │  model=opus          │  │  model=sonnet        │  │  model=minimax2.7    │
  └──────┬───────────────┘  └──────┬──────────────┘  └──────┬───────────────┘
         └──────────────────────────┴─────────────────────────┘
                                   │  asyncio.gather
                                   ▼
                         FanInReducer.reduce(branch_results)
                                   │
                                   ▼
                            StepResult (fan_out)
```

### Branch Isolation

Each branch gets its own copy of `merged_params` with `_fan_out_branch_index`
and `_fan_out_model` injected so that prompts can vary by branch if needed
(e.g., `"Branch {_fan_out_branch_index}: {context}"`). The inner step's
`step_type` is parsed from the `inner:` block — it may be any registered step
type except `fan_out` itself (no nesting).

### Fan-In Reducers

```python
class FanInReducer(Protocol):
    """Merges branch results into a single ActionResult."""

    def reduce(
        self,
        branch_results: list[StepResult],
        config: dict[str, object],
    ) -> ActionResult:
        ...
```

Built-in reducers registered by name in a module-level dict
(`_REDUCER_REGISTRY`):

| Name | Behavior |
|------|----------|
| `collect` | `outputs["branches"]` = list of each branch's action results (as dicts). `success` = True if all branches succeeded. Default. |
| `first_pass` | Returns the first branch result whose review verdict is `PASS`. Falls back to the last branch result if none pass. Useful for "stop at first model that approves". |

Slice 189 will register a third reducer (`merge_findings`) that merges
`ReviewFinding` lists for ensemble use; that is out of scope here.

---

## Technical Decisions

### Pool Multi-Select

`ModelResolver.resolve()` returns a single model. Fan-out needs N models.
Two options:

1. Call `resolver.resolve()` N times with the same `pool:name` — the pool
   backend's strategy (random, round-robin) produces N selections naturally.
2. Add `PoolBackend.select_n(pool_name, n, context)` for atomic N-selection.

**Decision: option 1** — call `resolver.resolve()` N times. This reuses the
existing resolver path without new methods, and the pool backend's strategy
already handles multiple calls correctly (round-robin increments each call,
random draws independently). If 181's backend exposes `select_n` it can be
used as an optimization later. No new method on `PoolBackend` is needed from
this slice.

This means the `n` parameter in the YAML config is used only when `models` is
a `pool:` reference — it tells the executor how many branches to create.

### Inner Step Parsing

The `inner:` block uses the same single-key dict format as the YAML step list.
`_unpack_inner_steps` (already in `executor.py`) parses it. The `fan_out` step
type's `validate()` checks that `inner:` is present and contains exactly one
parseable step entry.

### Failure Semantics

`asyncio.gather` is called with `return_exceptions=False` so the first branch
exception propagates immediately (fast-fail). Branches that return a
`StepResult(status=FAILED)` are gathered normally; the reducer or the executor
decides how to handle mixed success/failure.

Default behavior: if any branch fails, `_execute_fan_out_step` returns a
`StepResult(status=FAILED)` without calling the reducer. This is explicit and
avoids the reducer receiving incomplete data. A future `on_branch_fail` config
key could change this, but is not in scope here.

### No Nested Fan-Out

`fan_out` inside `fan_out` is rejected at validation time. The complexity of
tracking nested `asyncio.gather` plus the absence of a concrete use case makes
nesting undesirable.

---

## Implementation Details

### YAML Configuration

```yaml
# Explicit model list
- fan_out:
    name: multi-model-review
    models: [opus, sonnet, minimax2.7]
    inner:
      dispatch:
        prompt: "{context}"
    fan_in: collect

# Pool-based (requires slice 181)
- fan_out:
    name: pool-review
    models: pool:review
    n: 3
    inner:
      dispatch:
        prompt: "{context}"
    fan_in: first_pass
```

Config keys:

| Key | Required | Type | Description |
|-----|----------|------|-------------|
| `models` | yes | `list[str]` or `pool:<name>` | Model aliases or pool reference |
| `n` | if pool | `int` | Number of branches when `models` is a pool ref |
| `inner` | yes | single-key dict | Inner step to run per branch |
| `fan_in` | no | `str` | Reducer name; default `collect` |

### FanOutStepType

```python
class FanOutStepType:
    @property
    def step_type(self) -> str:
        return StepTypeName.FAN_OUT

    def validate(self, config: StepConfig) -> list[ValidationError]:
        # Check: models present, inner present, inner not fan_out,
        # n required if models is pool ref, fan_in is registered name
        ...

    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
        return []  # executor handles fan_out directly
```

### `_execute_fan_out_step` in `executor.py`

```python
async def _execute_fan_out_step(*, step, resolved_config, ...) -> StepResult:
    models_raw = resolved_config["models"]
    fan_in_name = str(resolved_config.get("fan_in", "collect"))
    inner_raw = resolved_config["inner"]  # single-key dict

    # 1. Build model list
    if isinstance(models_raw, str) and models_raw.startswith("pool:"):
        n = int(resolved_config.get("n", 1))
        pool_name = models_raw.removeprefix("pool:")
        model_list = [
            resolver.resolve(f"pool:{pool_name}")[0] for _ in range(n)
        ]
    else:
        model_list = [resolver.resolve(str(m))[0] for m in models_raw]

    # 2. Parse inner step
    inner_steps = _unpack_inner_steps([inner_raw])
    if not inner_steps:
        raise ValueError(f"fan_out step '{step.name}': invalid inner step")
    inner_step = inner_steps[0]

    # 3. Build branch coroutines
    async def run_branch(idx: int, model_id: str) -> StepResult:
        branch_params = {
            **merged_params,
            "_fan_out_branch_index": idx,
            "_fan_out_model": model_id,
            "model": model_id,   # overrides model for inner step actions
        }
        inner_resolved = resolve_placeholders(inner_step.config, branch_params)
        return await _execute_step_once(
            step=inner_step,
            resolved_config=inner_resolved,
            merged_params=branch_params,
            ...
        )

    # 4. Gather
    branch_results: list[StepResult] = await asyncio.gather(
        *(run_branch(i, m) for i, m in enumerate(model_list))
    )

    # 5. Check failures
    failed = [r for r in branch_results if r.status == ExecutionStatus.FAILED]
    if failed:
        return StepResult(status=FAILED, ...)

    # 6. Reduce
    reducer = get_reducer(fan_in_name)
    action_result = reducer.reduce(branch_results, resolved_config)

    return StepResult(
        step_name=step.name,
        step_type=step.step_type,
        status=ExecutionStatus.COMPLETED,
        action_results=[action_result],
    )
```

### Executor Registration

In `execute_pipeline()`, add the `fan_out` detection block alongside the
existing `each` branch:

```python
elif step.step_type == StepTypeName.FAN_OUT:
    step_result = await _execute_fan_out_step(...)
```

And add the import trigger:

```python
import squadron.pipeline.steps.fan_out as _s_fan_out  # noqa: F401
```

---

## Integration Points

### Provides to Other Slices

- **Slice 189 (Ensemble Review)** — consumes `fan_out` directly. The ensemble
  reducer (`merge_findings`) will register itself in `_REDUCER_REGISTRY` at
  import time; no changes to fan-out infrastructure needed.
- Any future pipeline that needs parallel multi-model dispatch.

### Consumes from Other Slices

- **Slice 149 (Executor)** — `_execute_step_once`, `_unpack_inner_steps`,
  `resolve_placeholders`, `StepConfig`, `ActionResult`.
- **Slice 181 (Pool Resolver)** — `ModelResolver.resolve()` called N times for
  pool references. Without 181, `pool:` in `models` raises
  `ModelPoolNotImplemented` (same error the resolver already raises).

---

## Success Criteria

### Functional Requirements

- `fan_out` step type is registered and recognized by the pipeline executor.
- A pipeline YAML with an explicit `models` list runs N branches concurrently
  and collects results via the `collect` reducer.
- A pipeline YAML with `models: pool:<name>` and `n: N` draws N models from the
  pool and runs N branches (requires 181; raises `ModelPoolNotImplemented`
  otherwise with a clear error message).
- Branch failure causes the step to fail fast; reducer is not called on partial
  failure.
- `first_pass` reducer returns the first PASS branch result, or the last branch
  result if none pass.
- Validation rejects: missing `models`, missing `inner`, nested `fan_out`,
  unregistered `fan_in` name, `pool:` without `n`.

### Technical Requirements

- No new public APIs beyond the step type, reducers, and `_execute_fan_out_step`.
- `_execute_fan_out_step` uses `asyncio.gather` — branches run concurrently, not
  sequentially.
- All new code passes `ruff` and type-checking (mypy/pyright strict).
- Tests cover: explicit list dispatch, pool dispatch (mocked resolver), branch
  failure propagation, `collect` reducer, `first_pass` reducer, validation
  errors.

### Verification Walkthrough

**1. Unit tests (verified during implementation)**

```bash
pytest tests/pipeline/steps/test_fan_out.py tests/pipeline/intelligence/fan_in/test_reducers.py -v
```

Expected: 29 tests collected, all pass. Covers all walkthrough scenarios below
via mocked dispatch, including smoke test, failure propagation, `first_pass`,
pool reference, and validation errors.

**2. Full regression suite — no regressions introduced:**

```bash
pytest -q
# 1635 passed, 9 warnings
```

**3. Live `sq run` smoke test (requires live model credentials)**

```yaml
# test-fan-out.yaml
name: fan-out-smoke
steps:
  - fan_out:
      name: multi-dispatch
      models: [sonnet, haiku]
      inner:
        dispatch:
          prompt: "Respond with: branch {_fan_out_branch_index}"
      fan_in: collect
```

```bash
sq run test-fan-out.yaml
```

Expected: pipeline completes; step result contains `outputs["branches"]` with
two entries, one per model. Not run during implementation (no live model creds
in CI); unit tests cover this path with mocked actions.

**4. Step type registration:**

```python
import squadron.pipeline.steps.fan_out
from squadron.pipeline.steps import list_step_types
assert "fan_out" in list_step_types()
```

Verified: `fan_out` appears in `list_step_types()`.

**5. Reducer registry:**

```python
from squadron.pipeline.intelligence.fan_in.reducers import get_reducer
get_reducer("collect")   # → CollectReducer
get_reducer("first_pass")  # → FirstPassReducer
```

Verified: both resolve without error.

**6. Pool reference (requires slice 181 pool backend configured):**

Covered by `test_pool_reference_calls_resolver_n_times` (mocked resolver).
Live pool test deferred to slice 189 integration.

**7. Validation errors — covered by Tasks 10 tests:**

- Missing `models` → error on field `models`
- Missing `inner` → error on field `inner`
- Nested `fan_out` → error on field `inner`
- `pool:` without `n` → error on field `n`
- Unregistered `fan_in` → error on field `fan_in`

---

## Risk Assessment

### Technical Risks

**asyncio task isolation** — branches share the underlying event loop and
`sdk_session`. If `sdk_session` is stateful (it is: it wraps a persistent Claude
CLI process), concurrent branches that all use `_dispatch_via_session` will
interleave their messages on the same session. This is incorrect.

**Mitigation:** When `sdk_session` is not None, `_execute_fan_out_step` must
either:
- Route each branch to `_dispatch_via_agent` (the one-shot path), ignoring the
  session for the duration of the fan-out step, OR
- Raise an explicit error: `"fan_out is not supported inside an SDK session step; use profile-based dispatch"`.

**Decision:** Raise an explicit error in the first implementation. Fan-out is
primarily a review/analysis pattern (used from CLI / non-session pipelines).
Session support can be added later if needed.

---

## Implementation Notes

### Development Approach

1. Add `FAN_OUT = "fan_out"` to `StepTypeName`.
2. Implement `FanInReducer` protocol and `collect` / `first_pass` reducers in
   `src/squadron/pipeline/intelligence/fan_in/`.
3. Implement `FanOutStepType` in `src/squadron/pipeline/steps/fan_out.py`.
4. Implement `_execute_fan_out_step` in `executor.py` and wire into the step
   dispatch branch.
5. Add import trigger for `fan_out` module in `execute_pipeline()`.
6. Write unit tests for reducers, step type validation, and executor branch.
7. Write integration test (mocked actions) for concurrent execution and failure
   propagation.

### Special Considerations

- **`asyncio.gather` and exceptions:** Use `return_exceptions=False` so the
  first branch exception is re-raised immediately. Do not swallow exceptions in
  branches; they propagate to the gather and become the step failure reason.
- **Branch parameter injection:** `_fan_out_branch_index` and `_fan_out_model`
  are injected into `merged_params` for each branch. These are prefixed with
  `_fan_out_` to avoid clashing with pipeline-defined params.
- **Reducer registry:** Module-level dict in `fan_in/reducers.py`. Reducers
  register at import time, same pattern as actions and step types.
