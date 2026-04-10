---
docType: slice-design
slice: prompt-only-loops
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [153-prompt-only-pipeline-executor]
interfaces: [155-sdk-pipeline-executor]
dateCreated: 20260405
dateUpdated: 20260410
status: complete
---

# Slice Design: Prompt-Only Loops

## Overview

Extend the prompt-only pipeline executor (slice 153) to support collection loops (`each` step type) without requiring the caller to understand loop semantics. When a pipeline contains an `each` step, successive calls to `sq run --prompt-only --next` return successive iteration instructions as if the iterations were sequential steps. Loop state is tracked internally by the executor, making loops transparent to the prompt-only consumer (the `/sq:run` slash command or external callers).

This enables design-batch pipelines and other multi-item workflows to run in interactive/prompt-only mode, using the same `--next` loop that works for sequential steps.

## Value

- **Batch operations in interactive mode**: Run `design-batch` to design multiple slices, with each iteration driven by human prompts via `/sq:run`, without requiring autonomous SDK dispatch.
- **Transparent loop handling**: Callers don't need to know whether a pipeline contains loops. They call `--next` repeatedly and receive step instructions — loops are flattened into the instruction stream.
- **Design validation**: Before committing to automated SDK execution, teams can validate that a batch pipeline produces the right instructions by running it interactively first.

## Technical Scope

### In Scope

1. **Loop iteration tracking in prompt-only mode** — The executor maintains the current loop context (which `each` block is active, which item is current, which inner step is current) across `--next` calls via the `RunState` object.

2. **Step instruction generation for loop iterations** — When generating step instructions via `--next`, the executor expands inner steps within the current `each` iteration with bound item variables resolved (e.g., `{slice.index}` → `152`).

3. **Iteration-level step naming** — Inner steps within an `each` loop are named to reflect their position: `{inner_step_name}-each-{item_index}`, e.g., `design-each-0`, making it clear which item an instruction applies to.

4. **Loop completion detection** — `--next` returns a completion marker when all items in all `each` blocks are exhausted, concluding the instruction stream.

5. **State persistence for loop progress** — The `RunState` JSON includes `loop_context` (current item, iteration index, cached items) so that `--resume` can restart from the correct position within a loop.

6. **Slash command compatibility** — The `/sq:run` command (which already consumes slice 153's prompt-only output) works transparently with loop iterations — no modifications needed.

### Out of Scope

- **Convergence loop strategies** — `loop.strategy` remains slice 160 scope. Prompt-only mode logs a warning and falls back to basic max-iteration behavior (inherited from slice 149).
- **Nested loops** — `each` inside `each` is not explicitly targeted. The architecture should not prevent it, but this slice focuses on single-level loops.
- **Dynamic loop sources** — Collection sources remain limited to `cf.unfinished_slices()`. New sources are slice 160+ scope.
- **Automated model switching** — `/model` commands are informational only in prompt-only mode. The `model_switch` field appears in step instructions for user reference. Automated model switching via `client.set_model()` is slice 155 (SDK executor) scope.

## Architecture

### Component Structure

No new components. The prompt-only handlers in `run.py` and the state model in `state.py` are extended with loop awareness. The pipeline executor (`executor.py`) already supports loops in SDK mode; prompt-only mode surfaces that behavior as an instruction stream.

```
src/squadron/pipeline/
├── executor.py               # EXISTING: _unpack_inner_steps made importable
├── prompt_renderer.py        # MODIFIED: render_each_step_instructions() added
├── state.py                  # MODIFIED: LoopContext model, loop-aware step-done
├── steps/collection.py       # EXISTING: EachStepType (unchanged)
└── ...

src/squadron/cli/commands/
└── run.py                    # MODIFIED: loop-aware init/next/step-done handlers
```

### Data Flow

**Scenario: `design-batch` pipeline with 3 unfinished slices, 1 inner step (design)**

```
Pipeline definition:
  steps:
    - each:
        source: cf.unfinished_slices("{plan}")
        as: slice
        steps:
          - design:
              phase: 4
              slice: "{slice.index}"

User interaction flow:
---
1. sq run design-batch 100 --prompt-only
   → Detect first step is "each"
   → Query cf.unfinished_slices("100") → [slice-151, slice-152, slice-153]
   → Create LoopContext: items=3, item_index=0, inner_step_index=0
   → Unpack inner steps: [design]
   → Bind slice-151 as {slice}
   → Expand "design" step for slice-151
   → Return StepInstructions for "design-each-0"
   → Persist LoopContext to RunState

2. sq run --step-done <run-id> --verdict PASS
   → Load LoopContext from state
   → Record "design-each-0" in completed_steps
   → Advance: inner_step_index → (past end) → item_index=1, inner_step_index=0
   → Persist updated LoopContext

3. sq run --prompt-only --next --resume <run-id>
   → Load LoopContext: item_index=1
   → Bind slice-152 as {slice}
   → Expand "design" step for slice-152
   → Return StepInstructions for "design-each-1"

... repeat for slice-153 (design-each-2) ...

4. After final --step-done:
   → item_index=3 (past end of items)
   → Loop complete: clear LoopContext, mark "each" step as completed
   → Persist

5. sq run --prompt-only --next --resume <run-id>
   → first_unfinished_step() skips the completed "each" step
   → No more steps → return CompletionResult
```

### RunState Extension

The existing `RunState` (Pydantic model in `state.py`, schema v3) gains an optional `loop_context` field:

```python
class LoopContext(BaseModel):
    """Active loop state for prompt-only each-step execution."""
    step_name: str                        # Name of the "each" step
    as_name: str                          # Binding variable name (e.g., "slice")
    items: list[dict[str, object]]        # Cached collection items
    inner_steps: list[dict[str, object]]  # Raw inner step configs from YAML
    current_item_index: int = 0           # 0-based position in items
    current_inner_step_index: int = 0     # 0-based position in inner_steps

class RunState(BaseModel):
    # ... existing fields ...
    loop_context: LoopContext | None = None  # NEW: None when not in a loop
```

No schema version bump required. `loop_context: LoopContext | None = None` is backward compatible — existing v3 state files without the field deserialize with `None`. New state files with `loop_context` populated are still v3.

### Step Instruction Output for Loop Iterations

The `StepInstructions` dataclass gains an optional `loop_context` field in its JSON output:

```json
{
  "run_id": "run-20260410-design-batch-abc12345",
  "step_name": "design-each-0",
  "step_type": "design",
  "step_index": 0,
  "total_steps": 3,
  "loop_context": {
    "each_step": "batch-iterations-0",
    "item_index": 0,
    "item_key": "151",
    "total_items": 3,
    "current_item": {
      "index": "151",
      "name": "Feature Name",
      "status": "in_progress",
      "design_file": ""
    }
  },
  "actions": [
    {
      "action_type": "cf-op",
      "instruction": "Set phase to 4",
      "command": "cf set phase 4"
    },
    ...
  ]
}
```

Key additions:
- **`loop_context`** — Current item data and loop position. Callers can use this for progress display ("Designing slice 151, item 1 of 3").
- **`step_name`** — Includes iteration index (`design-each-0`).
- **`total_steps`** — Reflects the flattened count across all iterations (items × inner_steps), plus any non-loop steps before/after.

## Technical Decisions

### Loop Iterations Are Flattened into Instruction Stream

Rather than returning a "loop step" instruction with all iterations at once, prompt-only mode returns successive iteration instructions as if they were sequential steps. The slash command calls `--next` repeatedly and receives step instructions — unaware of loops.

**Rationale:** Simplicity for the caller. The slash command doesn't need loop-aware logic; it follows a linear instruction stream.

### Collection Items Are Cached in State

When the `each` step is first encountered, the source query (e.g., `cf.unfinished_slices()`) is executed once and the results are cached in `LoopContext.items`. Subsequent `--next` calls use the cached items rather than re-querying.

**Rationale:** Deterministic behavior across resume. If slices are marked complete between `--next` calls, re-querying would change the iteration list mid-loop. Caching ensures the loop processes exactly the items it started with.

### Step Naming Includes Loop Index

Inner steps within a loop are named `{inner_step_name}-each-{item_index}`. This ensures uniqueness across iterations, traceability in state files and logs, and unambiguous resume.

**Rationale:** Without unique names, resuming mid-loop would be ambiguous — which "design" step was paused?

### LoopContext Is a Top-Level RunState Field

Loop context lives on `RunState` directly (not nested inside step results). When `loop_context` is `None`, the run is not inside a loop. When populated, it governs the `--next` / `--step-done` behavior.

**Rationale:** Simpler state schema. Loop context is a runtime positioning concern that spans multiple `--step-done` calls. It doesn't belong on individual step results.

### No Schema Version Bump

The `loop_context` field has a `None` default, making it backward compatible within schema v3. Existing state files deserialize correctly (field absent → `None`). New files include the field when a loop is active.

**Rationale:** Avoids the `SchemaVersionError` upgrade path for a purely additive field.

### Source Resolution Requires CF Client

The `_handle_prompt_only_init` and `_handle_prompt_only_next` handlers already have access to `ContextForgeClient` (via `_check_cf` in the execution path). For prompt-only mode, we construct a CF client to resolve the `each` source query. This is the same pattern used in the SDK executor's `_execute_each_step`.

**Rationale:** Reuse existing source registry (`_SOURCE_REGISTRY`) and resolution logic (`_parse_source`). No new query mechanism needed.

## Implementation Details

### Modified: `src/squadron/pipeline/state.py`

**Add `LoopContext` model:**

```python
class LoopContext(BaseModel):
    """Active loop state for prompt-only each-step execution."""
    step_name: str
    as_name: str
    items: list[dict[str, object]]
    inner_steps: list[dict[str, object]]
    current_item_index: int = 0
    current_inner_step_index: int = 0
```

**Extend `RunState`:**

```python
class RunState(BaseModel):
    # ... existing fields ...
    loop_context: LoopContext | None = None
```

**Add `StateManager.advance_loop` method:**

```python
def advance_loop(self, run_id: str) -> bool:
    """Advance loop context to the next position. Returns True if loop completed."""
    state = self.load(run_id)
    ctx = state.loop_context
    if ctx is None:
        return True  # no loop active

    ctx.current_inner_step_index += 1
    if ctx.current_inner_step_index >= len(ctx.inner_steps):
        ctx.current_inner_step_index = 0
        ctx.current_item_index += 1

    if ctx.current_item_index >= len(ctx.items):
        state.loop_context = None  # loop finished
        self._write_atomic(...)
        return True

    state.updated_at = now
    self._write_atomic(...)
    return False
```

**Add `StateManager.init_loop_context` method:**

```python
def init_loop_context(
    self, run_id: str, step_name: str, as_name: str,
    items: list[dict[str, object]], inner_steps: list[dict[str, object]],
) -> None:
    """Create and persist a LoopContext for an each step."""
```

### Modified: `src/squadron/pipeline/prompt_renderer.py`

**Add `LoopInstructionContext` dataclass:**

```python
@dataclass
class LoopInstructionContext:
    """Loop metadata included in StepInstructions JSON output."""
    each_step: str
    item_index: int
    item_key: str
    total_items: int
    current_item: dict[str, object]
```

**Extend `StepInstructions`:**

```python
@dataclass
class StepInstructions:
    # ... existing fields ...
    loop_context: LoopInstructionContext | None = None
```

**Add `render_each_step_instructions` function:**

New function that handles `each` step rendering. Given the cached items, current position, and inner step config, it:
1. Unpacks the current inner step config (using `_unpack_inner_steps` from executor)
2. Binds the current item as a param (`{as_name: item}`)
3. Calls the existing `render_step_instructions()` on the inner step with bound params
4. Attaches `LoopInstructionContext` to the result
5. Overrides `step_name` with the iteration-indexed name

```python
def render_each_step_instructions(
    *,
    inner_step_raw: dict[str, object],
    inner_step_index: int,
    item: dict[str, object],
    item_index: int,
    total_items: int,
    as_name: str,
    each_step_name: str,
    total_flattened_steps: int,
    flattened_step_index: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
) -> StepInstructions:
```

### Modified: `src/squadron/pipeline/executor.py`

**Make `_unpack_inner_steps` importable:**

Rename from `_unpack_inner_steps` to `unpack_inner_steps` (drop leading underscore) so `prompt_renderer.py` can import it. This function converts raw YAML step dicts to `StepConfig` objects.

### Modified: `src/squadron/cli/commands/run.py`

**`_handle_prompt_only_init`:**

After loading the pipeline, check if the first step is `each`. If so:
1. Construct a `ContextForgeClient`, run the source query via `_parse_source` and `_SOURCE_REGISTRY`
2. Unpack inner steps from the `each` config
3. Create `LoopContext` and persist to state
4. Render the first inner step of the first item via `render_each_step_instructions()`

If the first step is not `each`, the existing behavior is unchanged.

**`_handle_prompt_only_next`:**

After loading state and finding the first unfinished step:
1. If `state.loop_context` is not `None`, the current step is an active loop:
   - Use `loop_context` to determine current item and inner step
   - Render via `render_each_step_instructions()`
2. If the step is `each` but `loop_context` is `None` (loop not yet initialized — happens when a non-loop step completes and the next step is `each`):
   - Initialize loop context (query source, cache items, persist)
   - Render first inner step of first item
3. Otherwise: existing behavior (render the step directly)

**`_handle_step_done`:**

After loading state:
1. If `state.loop_context` is not `None`:
   - Generate the iteration step name: `{inner_step_name}-each-{item_index}`
   - Record it via `record_step_done()` for traceability
   - Call `advance_loop()` to move to next position
   - If `advance_loop()` returns `True` (loop complete), also record the `each` step as completed
2. Otherwise: existing behavior

## Integration Points

### Provides to Other Slices

- **Slice 155 (SDK Executor):** Shared `RunState` schema. State files are compatible across execution modes. Slice 155 uses the real executor's `_execute_each_step` (not prompt-only rendering), but can inspect `loop_context` if resuming a run that was started in prompt-only mode.

### Consumes from Other Slices

- **Slice 153 (Prompt-Only Executor):** Extends the prompt-only init/next/step-done handlers and `StepInstructions` output model.
- **Slice 149 (Executor):** Reuses `_unpack_inner_steps` (renamed), `_parse_source`, and `_SOURCE_REGISTRY` for source resolution and inner step unpacking.
- **Slice 150 (State Manager):** Extends `RunState` with `loop_context`.

## Success Criteria

1. **Loop iteration detection:** When a pipeline contains an `each` step, `sq run <pipeline> --prompt-only` identifies the items from the source query and initializes `loop_context` in the state file.

2. **Successive iteration instructions:** `--next` returns instructions for the first inner step of the first item. After `--step-done`, the next `--next` returns the next unfinished inner step in the same iteration, or the first step of the next item if the current item's inner steps are complete.

3. **Item variable resolution:** Bound item fields like `{slice.index}` resolve correctly in step configs, and the resolved values appear in the instruction output (e.g., `cf set slice 151`).

4. **Progress tracking:** The `total_steps` field reflects the cumulative flattened count across all iterations, so callers can display accurate progress (e.g., "Step 2 of 3").

5. **Loop completion:** After the final inner step of the final item is marked done, `--next` returns a `CompletionResult` (or advances to the next non-loop step in the pipeline).

6. **State persistence:** The `RunState` JSON includes `loop_context` while a loop is active, and clearing it when the loop completes. Resuming with `--resume` restores the loop position correctly.

7. **Slash command compatibility:** `/sq:run design-batch 100` iterates through all items and their steps without modification to the slash command logic.

8. **Step naming clarity:** Step names in state and output follow `{inner_step_name}-each-{item_index}`, making loop iterations unambiguous in logs and state files.

## Verification Walkthrough

*Assumes slice 149 (executor loops) and slice 153 (prompt-only base) are complete. Uses `design-batch` pipeline with `cf.unfinished_slices()` returning 3 items.*

### 1. Initialize Design-Batch in Prompt-Only Mode

```bash
sq run design-batch 100 --prompt-only
```

**Expected output (stdout):** JSON with `step_name: "design-each-0"`, `step_type: "design"`, `loop_context` populated with `item_index: 0`, `total_items: 3`, `current_item` containing the first slice's data.

**Expected stderr:** `run_id=run-20260410-design-batch-xxxxxxxx`

**State file:** `~/.config/squadron/runs/run-...-design-batch-xxx.json` contains `loop_context` with cached items and `current_item_index: 0, current_inner_step_index: 0`.

### 2. Mark First Step Done and Get Next

```bash
sq run --step-done <run-id> --verdict PASS
sq run --prompt-only --next --resume <run-id>
```

**Expected:** Since design-batch has 1 inner step per item (design), completing the first step advances to the next item. JSON output shows `step_name: "design-each-1"` with the second slice's data.

### 3. Complete All Items

Repeat `--step-done` + `--next` for all 3 items. After the third `--step-done`:

```bash
sq run --prompt-only --next --resume <run-id>
```

**Expected:** `CompletionResult` JSON: `{ "status": "completed", "message": "All steps complete" }`.

### 4. Slash Command End-to-End

```
/sq:run design-batch 100
```

**Expected:** The slash command drives the loop via successive `--next` calls. All 3 items are processed in sequence. Run state shows completed with 3 step records (`design-each-0`, `design-each-1`, `design-each-2`).

### 5. State File Inspection

```bash
cat ~/.config/squadron/runs/<run-id>.json | python -m json.tool
```

**Expected:** `loop_context` is `null` (cleared after loop completion). `completed_steps` contains entries with step names `design-each-0`, `design-each-1`, `design-each-2`, plus the `each` step itself.

### 6. Resume Mid-Loop

Interrupt after completing item 0 (kill the slash command or Ctrl-C). Then:

```bash
sq run --prompt-only --next --resume <run-id>
```

**Expected:** `loop_context` restored from state file. Returns instructions for `design-each-1` (the next unfinished iteration).

## Implementation Notes

### Development Approach

1. Add `LoopContext` Pydantic model to `state.py`, extend `RunState`
2. Add `LoopInstructionContext` and extend `StepInstructions` in `prompt_renderer.py`
3. Add `render_each_step_instructions()` to `prompt_renderer.py`
4. Rename `_unpack_inner_steps` to `unpack_inner_steps` in `executor.py`
5. Modify `_handle_prompt_only_init` for `each` first-step detection
6. Modify `_handle_prompt_only_next` for loop-aware rendering
7. Modify `_handle_step_done` for loop advancement
8. Add `StateManager.advance_loop()` and `init_loop_context()` methods
9. Unit tests for loop context lifecycle, item binding, iteration advancement
10. Integration tests with `design-batch` pipeline and mock CF client

### Testing Strategy

- **Loop context tracking:** Mock CF client returning 3 test slices. Simulate `init → step-done → next → step-done → next → ...` cycle. Verify `loop_context` advances correctly and clears on completion.
- **Item variable resolution:** Verify `{slice.index}` in inner step config resolves to the current item's index value in the rendered instructions.
- **State persistence round-trip:** Serialize `RunState` with `LoopContext`, deserialize, verify fields survive.
- **Backward compatibility:** Load an existing v3 state file (without `loop_context`). Verify it deserializes with `loop_context = None`.
- **Step naming:** Verify iteration step names follow `{name}-each-{index}`.
- **Completion detection:** After final `--step-done`, verify `--next` returns `CompletionResult`.
- **Multi-inner-step loops:** Test with a pipeline that has 2+ inner steps per item (e.g., design + tasks). Verify inner step sequencing within each item.

### Effort

2/5 — Extensions to existing slice 153 code. Loop handling is already built in the executor (slice 149); prompt-only mode surfaces it as an instruction stream. Main work: state model extension, loop-aware handlers, test coverage.
