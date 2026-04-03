---
docType: slice-design
slice: pipeline-executor-and-loops
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [147, 148]
interfaces: [150, 151]
dateCreated: 20260403
dateUpdated: 20260403
status: not_started
---

# Slice 149: Pipeline Executor and Loops

## Overview

Implement the pipeline executor — the runtime engine that takes a validated `PipelineDefinition`, expands step types into action sequences, resolves parameters, and executes actions in order. This slice also implements basic retry loops (`loop:` on steps) and the `each` collection loop step type for batch operations. The executor is the bridge between declarative YAML definitions (slice 148) and the action implementations (slices 144–147).

## Value

- **`sq run` becomes functional.** After this slice, a pipeline definition can actually execute — step types expand, actions run, results flow between steps. The end-to-end path from YAML to execution is complete.
- **Retry loops reduce human babysitting.** A step with `loop: {max: 3, until: review.pass}` retries automatically, only pausing when the condition is met or iterations are exhausted.
- **Batch operations across slices.** The `each` step type enables `design-batch` — run a phase across every unfinished slice in a plan without manually invoking each one.
- **Parameter resolution.** `{slice}`, `{model}`, `{template}` placeholders in step configs resolve to actual values at execution time.

## Technical Scope

### Included

1. **Pipeline executor** (`src/squadron/pipeline/executor.py`) — Core execution engine. Takes a `PipelineDefinition` and a `params` dict, expands steps, executes actions sequentially, threads `ActionContext` with cumulative `prior_outputs`, handles checkpoint pauses and action failures.

2. **Parameter resolution** — Resolves `{param_name}` placeholders in step configs against the pipeline's params dict at execution time. Simple string interpolation — not a template engine.

3. **Basic retry loops** — `loop:` config on any step: `max` (iteration cap), `until` (termination condition), `on_exhaust` (behavior when max reached without condition met). Executes the step's full action sequence per iteration.

4. **Loop condition grammar** — Simple dot-path conditions evaluated against the step's `ActionResult` outputs. `review.pass` means "the most recent review action in this step returned verdict PASS". Formal grammar defined below.

5. **`each` step type** (`src/squadron/pipeline/steps/collection.py`) — Iterates over items from a source query. Binds each item to a variable name. Expands inner steps per item. Initial source: `cf.unfinished_slices("{plan}")` via `ContextForgeClient.list_slices()`.

6. **Item binding** — Inside an `each` block, `{varname.field}` references resolve to fields on the current iteration item. The item is a flat dict (matching `SliceEntry` fields: `index`, `name`, `status`, `design_file`).

7. **Convergence loop stub** — If a step has `loop.strategy`, the executor logs a warning and falls back to basic `max`-iteration behavior. The strategy field is parsed and stored but not interpreted. This is the 160 extension point.

### Excluded

- **State persistence / resume** — Slice 150. The executor emits events that 150's state manager will consume, but this slice does not persist state to disk.
- **CLI integration** — Slice 151. The executor is a library API; 151 wires it into `sq run`.
- **Convergence strategies** — Slice 160. This slice acknowledges `loop.strategy` but does not implement weighted-review or other strategies.
- **Conversation persistence** — Slice 160. Each action dispatch uses a fresh agent.
- **Dry-run mode** — Slice 151. The executor exposes enough structure for dry-run, but the presentation is CLI scope.

## Dependencies

### Prerequisites

- **Slice 147** (Step Types) — All step types registered: design, tasks, implement, compact, review, devlog. Their `expand()` methods return action sequences.
- **Slice 148** (Pipeline Definitions & Loader) — `load_pipeline()` returns validated `PipelineDefinition` with `StepConfig` list. `validate_pipeline()` catches structural issues before execution.
- **Action implementations** (Slices 144–146) — All actions registered: cf-op, commit, devlog, dispatch, review, compact, checkpoint.

### Interfaces Required

- `squadron.pipeline.steps.get_step_type()` — Look up step type by name, get `expand()` result.
- `squadron.pipeline.actions.get_action()` — Look up action by type name, call `execute()`.
- `squadron.pipeline.resolver.ModelResolver` — Passed through `ActionContext` for model resolution during dispatch.
- `squadron.pipeline.models.ActionContext` — Context struct for action execution.
- `squadron.pipeline.models.ActionResult` — Result from action execution, inspected for loop conditions and checkpoint pauses.
- `squadron.integrations.context_forge.ContextForgeClient` — Used by `each` step type for collection queries (`list_slices()`).

## Architecture

### Component Structure

```
src/squadron/pipeline/
├── executor.py          # NEW: Pipeline executor engine
├── steps/
│   └── collection.py    # REPLACE STUB: `each` step type implementation
├── models.py            # EXISTING: ActionContext, ActionResult (unchanged)
├── loader.py            # EXISTING: load_pipeline (consumed, unchanged)
├── resolver.py          # EXISTING: ModelResolver (consumed, unchanged)
├── actions/             # EXISTING: All action implementations (consumed)
└── steps/               # EXISTING: All step type implementations (consumed)
```

### Data Flow

```
PipelineDefinition + params dict
  │
  ▼
Executor.run()
  │
  ├─ For each StepConfig:
  │    │
  │    ├─ Resolve {param} placeholders in step config
  │    │
  │    ├─ Look up StepType via registry
  │    │
  │    ├─ step_type.expand(config) → list[(action_type, action_config)]
  │    │
  │    ├─ If step has loop config:
  │    │    │
  │    │    └─ Loop: execute action sequence, check until condition, repeat or exit
  │    │
  │    ├─ For each (action_type, action_config):
  │    │    │
  │    │    ├─ Look up Action via registry
  │    │    │
  │    │    ├─ Build ActionContext (merge action_config into params, carry prior_outputs)
  │    │    │
  │    │    └─ action.execute(context) → ActionResult
  │    │         │
  │    │         ├─ On checkpoint "paused": return StepResult with paused status
  │    │         └─ On failure: return StepResult with failed status
  │    │
  │    └─ Accumulate step results
  │
  └─ Return PipelineResult (all step results, final status)
```

### Executor Result Types

```python
@dataclass
class StepResult:
    """Result of executing one pipeline step."""
    step_name: str
    step_type: str
    status: ExecutionStatus  # completed | failed | paused | skipped
    action_results: list[ActionResult]
    iteration: int = 0       # which loop iteration (0 for non-looped)
    error: str | None = None

@dataclass
class PipelineResult:
    """Result of executing a full pipeline."""
    pipeline_name: str
    status: ExecutionStatus
    step_results: list[StepResult]
    paused_at: str | None = None  # step name where pipeline paused
    error: str | None = None

class ExecutionStatus(StrEnum):
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    SKIPPED = "skipped"
```

These result types live in `executor.py` — they are executor output, not pipeline model input.

## Technical Decisions

### Executor is Async, Actions are Async

The executor is an `async` function. All action `execute()` methods are already `async`. This allows I/O-bound actions (dispatch, review, CF ops) to run without blocking. The executor itself runs actions within a step **sequentially** — parallelism within a step is not supported (actions depend on prior outputs).

### Parameter Resolution is String Interpolation

`{param_name}` placeholders in step config string values are resolved via `str.replace()` against the params dict. This is not a template engine — no expressions, no filters, no conditionals. A config value of `"{slice}"` with params `{"slice": "191"}` becomes `"191"`.

Non-string config values are not interpolated. Placeholders that don't match a declared param are left as-is (they may be loop variable references like `{slice.index}` that resolve at a different scope).

### Loop Condition Grammar

Loop conditions use a simple, closed grammar — not arbitrary expressions:

```
condition := "review.pass" | "review.concerns_or_better" | "action.success"
```

| Condition | Meaning | Evaluates Against |
|-----------|---------|-------------------|
| `review.pass` | Most recent review verdict is PASS | Last ActionResult with verdict != None |
| `review.concerns_or_better` | Verdict is PASS or CONCERNS (not FAIL) | Same |
| `action.success` | All actions in the step succeeded | All ActionResults in current iteration |

This is a closed enum, not a field-path expression parser. Adding new conditions is a code change (add to the enum and evaluator), not a grammar extension. This avoids the complexity of parsing arbitrary field paths into `ActionResult.outputs` while covering the actual use cases.

**Rationale:** The architecture doc's `until: review.pass` syntax is illustrative. A general-purpose expression language (`outputs.review.findings[0].severity < 3`) would be complex to implement, validate, and explain. The three conditions above cover: retry-until-pass (primary use case), retry-until-acceptable (CONCERNS is OK), and retry-until-no-errors (generic). If more conditions are needed, they can be added as named conditions to the enum.

### Checkpoint Pausing Stops the Executor

When a checkpoint action returns `outputs.checkpoint == "paused"`, the executor stops executing further actions in the step and returns a `PipelineResult` with status `PAUSED` and `paused_at` set to the current step name. The state manager (slice 150) will persist this state. Resume (also 150) will restart from the paused step.

The executor does **not** implement interactive checkpoint handling (wait for user input). It simply reports the pause. The CLI (slice 151) or state manager (slice 150) handles the interaction.

### Action Failure Stops the Step

If any action returns `ActionResult(success=False)`, the executor stops executing further actions in that step and marks the step as `FAILED`. The pipeline also stops — sequential steps don't continue past a failure.

Exception: Within a loop, a failed iteration increments the iteration counter and the loop continues (the failure may be transient). If `max` iterations are exhausted with all failures, the step is marked `FAILED`.

### Each Step Type: Source Query Dispatch

The `each` step type's `source` field uses a `namespace.function(args)` syntax. Initial implementation supports one source:

| Source | Parsed As | Implementation |
|--------|-----------|----------------|
| `cf.unfinished_slices("{plan}")` | namespace=`cf`, function=`unfinished_slices`, args=`["{plan}"]` | `ContextForgeClient.list_slices()` filtered by status != "complete" |

Source parsing is a simple regex, not a general expression parser. Unknown namespaces or functions raise a validation error. New sources are added by extending the source registry (a dict mapping `(namespace, function)` to a callable).

### Each Step Type is Not a Regular StepType

The `each` step is structurally different from other step types — it contains nested steps and iterates. It does **not** implement the `StepType.expand()` protocol in the normal sense (expand returns a flat action list, but `each` needs to expand inner steps per item). Instead:

- The `each` step type's `expand()` returns an empty list (no direct actions).
- The executor has explicit handling for `step_type == "each"`: it reads `source`, `as`, and `steps` from the config, resolves the source query, iterates items, and for each item recursively executes the inner steps with the bound variable added to params.

This is the simplest approach that avoids forcing the `StepType` protocol to handle recursive step expansion.

### Item Binding via Params Augmentation

Inside an `each` block, the bound variable (e.g., `as: slice`) is added to the params dict with the item's fields as nested values. For param resolution, `{slice.index}` is resolved by:

1. Splitting on `.` → `["slice", "index"]`
2. Looking up `slice` in params → gets the item dict
3. Looking up `index` in the item dict → gets the value

This reuses the parameter resolution mechanism with one extension: dot-path traversal for nested dicts. The item dict has string keys and string/int values matching `SliceEntry` fields.

### Convergence Loop Stub

If `loop.strategy` is present in a step config, the executor:
1. Logs a warning: "Loop strategy '{strategy}' is not implemented (requires Pipeline Intelligence initiative). Falling back to basic max-iteration loop."
2. Executes the step as a basic loop using `max` and `until` (if present).

This preserves forward compatibility — `design-batch.yaml` or custom pipelines with `loop.strategy` won't crash, they just won't apply the strategy.

## Implementation Details

### Executor API (`executor.py`)

```python
async def execute_pipeline(
    definition: PipelineDefinition,
    params: dict[str, object],
    *,
    resolver: ModelResolver,
    cf_client: ContextForgeClient,
    cwd: str | None = None,
    run_id: str | None = None,
    start_from: str | None = None,
    on_step_complete: Callable[[StepResult], None] | None = None,
) -> PipelineResult:
    """Execute a pipeline definition with the given parameters.

    Args:
        definition: Validated pipeline definition.
        params: Caller-supplied parameter values, merged with defaults.
        resolver: Model resolver for dispatch actions.
        cf_client: Context Forge client for CF operations.
        cwd: Working directory (defaults to os.getcwd()).
        run_id: Unique run identifier (auto-generated if not provided).
        start_from: Step name to start from (skip earlier steps).
        on_step_complete: Optional callback after each step completes.
    """
```

The executor is a module-level async function, not a class. There's no executor state beyond the current run — state persistence is slice 150's job.

**`on_step_complete` callback:** Enables the state manager (150) and CLI (151) to observe progress without the executor depending on them. The executor calls this after each step completes (or fails/pauses). The callback receives the `StepResult`.

### Parameter Merging

Pipeline params have defaults declared in the definition (`params: {model: opus}`). Caller-supplied params override defaults. The merge happens at the top of `execute_pipeline()`:

```python
merged = dict(definition.params)  # defaults
merged.update(params)              # caller overrides

# Validate required params are provided
for name, default in definition.params.items():
    if default == "required" and name not in params:
        raise ValueError(f"Required param '{name}' not provided")
```

### Step Execution Flow

For each step in the definition (or from `start_from`):

1. **Resolve placeholders** in step config values using merged params.
2. **Look up step type** from registry.
3. **Check for `each` step type** — if so, branch to collection loop handling.
4. **Expand step** via `step_type.expand(config)` → action list.
5. **Check for loop config** — if present, wrap execution in retry loop.
6. **Execute actions** sequentially, building `ActionContext` for each:
   - `prior_outputs` accumulates results keyed by `{action_type}-{index}` within the step.
   - `params` merges the action config with step-level and pipeline-level params.
   - `step_name`, `step_index`, `pipeline_name`, `run_id` come from the executor state.
7. **Check for checkpoint pause** — if a checkpoint action returned `"paused"`, stop.
8. **Check for action failure** — if any action failed, stop (unless in a loop).
9. **Call `on_step_complete`** with the `StepResult`.

### Retry Loop Execution

When a step has a `loop` config:

```yaml
- implement:
    phase: 6
    review: code
    loop:
      max: 3
      until: review.pass
      on_exhaust: checkpoint  # or "fail" or "skip"
```

The executor:

1. Parses `loop` config: `max` (int, required), `until` (LoopCondition, optional), `on_exhaust` (ExhaustBehavior, optional, default `"fail"`).
2. For iteration 1..max:
   a. Execute the full action sequence for this step.
   b. Evaluate the `until` condition against the action results.
   c. If condition met → break, mark step completed.
   d. If any action failed and this is a retryable failure → continue to next iteration.
   e. If checkpoint paused → return paused (checkpoints always stop, even in loops).
3. If max reached without condition met:
   - `on_exhaust: "checkpoint"` → return paused.
   - `on_exhaust: "fail"` → mark step failed.
   - `on_exhaust: "skip"` → mark step skipped, continue pipeline.

### Collection Loop Execution (each)

When the step type is `each`:

1. Parse config: `source` (str), `as` (str), `steps` (list of step configs).
2. Resolve the `source` query (see Source Query Dispatch below).
3. For each item in the result:
   a. Bind the item to params under the `as` name (e.g., `params["slice"] = item_dict`).
   b. Parse inner step configs (they're raw dicts, need to go through the same schema unpacking — reuse `PipelineSchema._unpack_steps` logic or a shared helper).
   c. Execute inner steps sequentially, same as top-level steps.
   d. If any inner step pauses or fails → stop the `each` loop and propagate status.
4. After all items → mark `each` step completed.

### Source Query Dispatch

```python
# Source registry: (namespace, function) -> callable
_SOURCE_REGISTRY: dict[tuple[str, str], SourceFn] = {
    ("cf", "unfinished_slices"): _cf_unfinished_slices,
}

async def _cf_unfinished_slices(
    args: list[str],
    cf_client: ContextForgeClient,
    params: dict[str, object],
) -> list[dict[str, object]]:
    """Query CF for unfinished slices, return as list of dicts."""
    slices = cf_client.list_slices()
    return [
        {"index": str(s.index), "name": s.name,
         "status": s.status, "design_file": s.design_file or ""}
        for s in slices if s.status != "complete"
    ]
```

The source string `cf.unfinished_slices("{plan}")` is parsed with regex: `r"(\w+)\.(\w+)\(([^)]*)\)"`. Args are split on `,` and stripped. Placeholder resolution runs on args before the query.

### Placeholder Resolution

```python
def resolve_placeholders(
    config: dict[str, object],
    params: dict[str, object],
) -> dict[str, object]:
    """Resolve {param} placeholders in string config values."""
```

For each string value in `config`:
1. Find all `{name}` or `{name.field}` patterns.
2. For simple `{name}`: replace with `str(params[name])` if present.
3. For dotted `{name.field}`: look up `params[name]` (must be a dict), then `dict[field]`.
4. Non-matching placeholders are left as-is.

Non-string values pass through unchanged. Nested dicts are resolved recursively.

## Integration Points

### Provides to Other Slices

- **Slice 150 (State/Resume):** `execute_pipeline()` with `on_step_complete` callback for state persistence. `PipelineResult` and `StepResult` for state serialization. `start_from` parameter for resume.
- **Slice 151 (CLI):** `execute_pipeline()` is the entry point for `sq run`. `PipelineResult` provides status for display. Step-by-step progress via `on_step_complete`.

### Consumes from Other Slices

- **Step type registry (147):** `get_step_type()` for expanding steps.
- **Action registry (142–147):** `get_action()` for executing actions.
- **Model resolver (142):** Passed through `ActionContext`.
- **Pipeline loader (148):** `load_pipeline()` produces the `PipelineDefinition` consumed here.
- **CF client (126):** Passed through `ActionContext`; used directly by `each` source queries.

## Success Criteria

### Functional Requirements

- [ ] Executor runs a simple pipeline (single step, no loops) end-to-end
- [ ] Step types expand correctly and actions execute in sequence
- [ ] Parameter placeholders resolve in step configs
- [ ] Required params that are missing raise a clear error
- [ ] Checkpoint action pausing stops the executor and returns `PAUSED` status
- [ ] Action failure stops the step and returns `FAILED` status
- [ ] Basic retry loop executes up to `max` iterations
- [ ] `until: review.pass` condition terminates the loop on PASS verdict
- [ ] `on_exhaust` behavior fires when max iterations reached without condition met
- [ ] `each` step type iterates over CF query results
- [ ] Item binding (`{slice.index}`) resolves inside `each` inner steps
- [ ] `on_step_complete` callback fires after each step
- [ ] `start_from` parameter skips steps before the named step
- [ ] `loop.strategy` field logs a warning and falls back to basic loop

### Technical Requirements

- [ ] All tests pass (`pytest`), pyright clean, ruff clean
- [ ] Executor is fully async
- [ ] No direct I/O in the executor — all I/O is delegated to actions and source queries
- [ ] Result types are plain dataclasses
- [ ] `each` source registry is extensible (dict-based, not if/elif chains)

### Verification Walkthrough

1. **Execute a minimal pipeline programmatically:**
   ```python
   from squadron.pipeline.executor import execute_pipeline, PipelineResult
   from squadron.pipeline.models import PipelineDefinition, StepConfig
   from squadron.pipeline.resolver import ModelResolver
   from unittest.mock import MagicMock

   # Minimal pipeline with a single devlog step
   defn = PipelineDefinition(
       name="test", description="", params={"slice": "191"},
       steps=[StepConfig(step_type="devlog", name="devlog-0", config={"mode": "auto"})],
   )
   resolver = ModelResolver(config_default="sonnet")
   cf = MagicMock()
   result = await execute_pipeline(defn, {"slice": "191"}, resolver=resolver, cf_client=cf)
   assert result.status.value == "completed"  # or check enum
   assert len(result.step_results) == 1
   ```

2. **Parameter resolution:**
   ```python
   from squadron.pipeline.executor import resolve_placeholders
   config = {"template": "{template}", "phase": 4}
   resolved = resolve_placeholders(config, {"template": "arch"})
   assert resolved["template"] == "arch"
   assert resolved["phase"] == 4  # non-string untouched
   ```

3. **Loop condition evaluation:**
   ```python
   from squadron.pipeline.executor import evaluate_condition, LoopCondition
   from squadron.pipeline.models import ActionResult
   results = [ActionResult(success=True, action_type="review", outputs={}, verdict="PASS")]
   assert evaluate_condition(LoopCondition.REVIEW_PASS, results) is True
   ```

4. **Run tests:**
   ```bash
   cd /Users/manta/source/repos/manta/squadron
   python -m pytest tests/pipeline/test_executor.py -v
   pyright src/squadron/pipeline/executor.py src/squadron/pipeline/steps/collection.py
   ruff check src/squadron/pipeline/
   ```

## Implementation Notes

### Development Approach

Suggested implementation order:

1. **Result types and placeholder resolution** — `ExecutionStatus`, `StepResult`, `PipelineResult`, `resolve_placeholders()`. Unit tests for placeholder resolution.
2. **Core executor** — `execute_pipeline()` with sequential step expansion and action execution. No loops yet. Unit tests with mocked actions.
3. **Loop condition grammar** — `LoopCondition` enum and `evaluate_condition()`. Unit tests.
4. **Retry loop execution** — Loop wrapper around step execution. Unit tests.
5. **`each` step type** — Source query parsing, source registry, item binding, collection loop execution. Unit tests.
6. **Integration tests** — Load built-in pipelines, execute with mocked actions, verify step expansion and parameter flow.

### Testing Strategy

- **Unit tests:** Placeholder resolution (simple, dotted, missing, non-string), loop condition evaluation, source query parsing, parameter merging, `start_from` skipping.
- **Executor tests with mocked actions:** Mock `get_action()` and `get_step_type()` to return test doubles. Verify step ordering, prior_outputs threading, checkpoint pausing, failure handling.
- **Loop tests:** Mock action that returns FAIL N times then PASS. Verify iteration count and termination. Verify `on_exhaust` behaviors.
- **`each` tests:** Mock CF client returning test slices. Verify iteration over items, variable binding, inner step execution.
- **Integration tests:** Load `slice-lifecycle` definition, execute with mocked actions, verify all 5 steps expand and execute in order.

Actions are async, so tests use `pytest-asyncio` (already in test dependencies).
