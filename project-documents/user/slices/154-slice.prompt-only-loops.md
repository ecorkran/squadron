---
docType: slice-design
slice: prompt-only-loops
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [153-prompt-only-pipeline-executor]
interfaces: [155-sdk-pipeline-executor]
dateCreated: 20260405
dateUpdated: 20260405
status: complete
---

# Slice Design: Prompt-Only Loops

## Overview

Extend the prompt-only pipeline executor (slice 153) to support collection loops (`each` step type) without requiring the caller to understand loop semantics. When a pipeline contains an `each` step, successive calls to `sq run --prompt-only --next` return successive iteration instructions as if the iterations were sequential steps. The loop state is tracked internally by the executor, making loops transparent to the prompt-only consumer (the `/sq:run` slash command or external callers).

This enables design-batch pipelines and other multi-item workflows to run in interactive/prompt-only mode, using the same `--next` loop that works for sequential steps.

## User Value

- **Batch operations in interactive mode**: Run `design-batch` to design multiple slices, with each iteration driven by human prompts (the `/sq:run` slash command), rather than requiring autonomous SDK-based dispatch.
- **Transparent loop handling**: Callers don't need to know whether a pipeline contains loops. They call `--next` repeatedly and receive step instructions — loops are flattened into the instruction stream.
- **Design validation**: Before committing to automated (SDK) execution, teams can validate that a batch pipeline produces the right instructions by running it interactively first.

## Technical Scope

### In Scope

1. **Loop iteration tracking in prompt-only mode** — The executor maintains the current loop context (which `each` block is active, which item is current, iteration index) across `--next` calls via the `RunState` object.

2. **Step instruction generation for loop iterations** — When generating step instructions via `--next`, the executor expands inner steps within the current `each` iteration with the bound item variables resolved (e.g., `{slice.index}` → `152`).

3. **Iteration-level step naming** — Inner steps within an `each` loop are named to reflect their position: `step-name-each-{item_key}` or similar, making it clear which item an instruction applies to.

4. **Loop completion detection** — `--next` returns a completion marker when all items in all `each` blocks are exhausted, naturally concluding the instruction stream.

5. **State persistence for loop progress** — The `RunState` JSON includes loop context (current item, iteration index, completed items) so that `--resume` can restart from the correct position within a loop.

6. **Slash command compatibility** — The `/sq:run` command (which already consumes slice 153's prompt-only output) works transparently with loop iterations — it doesn't need modifications.

### Out of Scope

- **Convergence loop strategies** — `loop.strategy` (weighted decay, etc.) remains as slice 160 scope. Prompt-only mode acknowledges the field but executes basic max-iteration fallback (inherited from slice 149).
- **Nested loops** — Support for `each` inside `each` is not explicitly targeted in this slice. The architecture should not *prevent* it, but this slice focuses on single-level loops.
- **Dynamic loop sources** — Collection sources remain limited to `cf.unfinished_slices()`. New sources are slice 160+ scope.
- **Automated model switching** — `/model` commands are manual only in prompt-only mode. Automated model switching via `client.set_model()` is slice 155 (SDK executor) scope.
- **Loop convergence in prompt-only** — Convergence strategies that require observing all iteration outputs simultaneously are out of scope; that's SDK-executor territory.

## Architecture

### Component Structure

No new components required. The prompt-only executor (slice 153's `prompt_renderer.py`) is extended with loop awareness. The pipeline executor (slice 149) already supports loops; prompt-only mode just needs to expose those iterations as instruction steps.

```
src/squadron/pipeline/
├── executor.py                  # EXISTING: Executor with loop support
├── prompt_renderer.py           # MODIFIED: Add loop iteration tracking
├── models.py                    # EXISTING: ActionContext, ActionResult, RunState
├── loader.py                    # EXISTING: Pipeline loader
└── ...
```

### Data Flow

**Scenario: A pipeline with an `each` step iterating over 3 slices**

```
Pipeline definition:
- name: design-batch
  steps:
    - each:
        source: cf.unfinished_slices("{plan}")
        as: slice
        steps:
          - design:
              phase: 4
              slice: "{slice.index}"
          - tasks:
              phase: 5
              slice: "{slice.index}"

User interaction flow:
---
1. sq run design-batch 100 --prompt-only
   ↓
   Executor init run, start traversal at step 0 (the "each" step)
   ↓
   Discover: "each" with 3 items (slices 151, 152, 153)
   ↓
   Expand inner steps for item 1 (slice 151):
     - design-each-0 (design step, slice=151)
     - tasks-each-0 (tasks step, slice=151)
   ↓
   Return instructions for "design-each-0" (first step)
   Output: JSON with step_name="design-each-0", slice.index resolved to "151"

2. sq run --step-done <run-id> [--verdict PASS]
   ↓
   Mark "design-each-0" complete, record verdict if any

3. sq run --prompt-only --next --resume <run-id>
   ↓
   Find next unfinished step in current iteration: "tasks-each-0"
   ↓
   Expand inner step with same item (slice 151) bound
   ↓
   Return instructions for "tasks-each-0"

4. sq run --step-done <run-id>
   ↓
   Mark "tasks-each-0" complete
   ↓
   Both inner steps done for item 1

5. sq run --prompt-only --next --resume <run-id>
   ↓
   Move to item 2 (slice 152)
   ↓
   Expand inner steps for item 2: design-each-1, tasks-each-1
   ↓
   Return instructions for "design-each-1"

... repeat for item 2 and item 3 ...

Final --next call after item 3's last step:
   ↓
   { "status": "completed", "message": "All steps complete" }
```

### RunState Extensions for Loop Tracking

The existing `RunState` JSON schema (from slice 150) needs loop context fields:

```python
@dataclass
class LoopContext:
    """Current position within a collection loop."""
    step_name: str               # Name of the "each" step
    item_index: int              # Which item (0-based)
    item_key: str                # Identifier for this item (slice index, etc.)
    completed_items: list[str]   # Item keys completed so far
    total_items: int             # Total items in this source

@dataclass
class RunState:
    # EXISTING FIELDS
    run_id: str
    pipeline_name: str
    params: dict[str, object]
    completed_steps: list[StepResult]
    status: str                  # "in_progress" | "completed" | "failed" | "paused"

    # NEW IN SLICE 154
    loop_context: LoopContext | None = None  # None if not in a loop
```

When not in a loop, `loop_context` is `None`. When inside an `each` block, `loop_context` tracks current position and allows resume to restore the exact iteration state.

### Step Instruction Output for Loop Iterations

When an instruction is for a loop iteration, the step name includes loop context:

```json
{
  "run_id": "run-20260405-batch-xyz",
  "step_name": "design-each-0",
  "step_type": "design",
  "loop_context": {
    "each_step": "batch-iterations-0",
    "item_index": 0,
    "item_key": "151",
    "total_items": 3,
    "current_item": {
      "index": "151",
      "name": "Feature: Database Optimization",
      "status": "in_progress",
      "design_file": "user/slices/151-slice.db-optimization.md"
    }
  },
  "step_index": 0,
  "total_steps": 6,  # 3 items × 2 inner steps each
  "actions": [
    {
      "action_type": "cf-op",
      "instruction": "Set phase to 4",
      "command": "cf set phase 4"
    },
    {
      "action_type": "dispatch",
      "instruction": "Design slice 151",
      "model": "opus",
      "model_switch": "/model opus"
    },
    ...
  ]
}
```

Key additions:
- **`loop_context`** — Provides the bound item's data and loop position. The slash command can use this for logging ("Designing slice 151 of 3") or context.
- **`step_name`** — Includes loop iteration index (e.g., `design-each-0` for the first item's design step).
- **`total_steps`** — Reflects the total instruction count across all iterations, so progress bar / step display can show "Step 3 of 6" accurately.

### State Persistence with Loop Context

The `RunState` JSON includes loop context:

```json
{
  "run_id": "run-20260405-batch-xyz",
  "pipeline_name": "design-batch",
  "params": { "plan": "100" },
  "status": "in_progress",
  "completed_steps": [
    { "step_name": "design-each-0", "step_type": "design", "verdict": "PASS", ... }
  ],
  "loop_context": {
    "step_name": "batch-iterations-0",
    "item_index": 0,
    "item_key": "151",
    "completed_items": ["151"],
    "total_items": 3
  }
}
```

When resuming with `--resume <run-id>`, the executor restores `loop_context` and continues from the next unfinished step within the current item (or the first step of the next item if the current item is done).

## Technical Decisions

### Loop Iterations Are Flattened into Instruction Stream

Rather than returning a "loop step" instruction with all iterations at once, prompt-only mode returns successive iteration instructions as if they were sequential steps. This keeps the slash command logic unchanged — it calls `--next` repeatedly and executes instructions, unaware of loops.

**Rationale:** Simplicity for the caller. The slash command doesn't need loop-aware logic; it just follows a linear instruction stream.

### Item Binding Variables Are Available in Instruction Output

When a loop iteration is active, the bound item's fields are serialized in `loop_context.current_item` in the JSON output. This allows external consumers (dashboards, logging tools) to be loop-aware without parsing YAML or re-running the query.

**Rationale:** Better observability and debugging. Callers can log which slice is being designed without duplicating the query logic.

### Step Naming Includes Loop Index

Inner steps within a loop are named `{inner_step_name}-each-{item_index}`, e.g., `design-each-0`, `tasks-each-1`. This ensures:
- **Uniqueness:** Each iteration's steps have distinct names in the instruction stream.
- **Traceability:** Step results and state can reference exactly which item and iteration a step belongs to.
- **Clarity:** Logs show "design-each-2 completed" rather than "design completed" twice.

**Rationale:** Without unique names, resuming mid-loop would be ambiguous — which "design" step was paused?

### RunState Loop Context Replaces Per-Step Loop Tracking

Rather than storing loop metadata in each `StepResult`, we track loop context as a top-level field in `RunState`. When `loop_context.item_index` advances, it implicitly applies to all subsequent steps until a new `each` block starts or the current one ends.

**Rationale:** Simpler state schema. Loop context is a runtime concern, not an artifact of step execution. A paused checkpoint within a loop doesn't need loop metadata on the checkpoint `StepResult`; the `RunState` context is sufficient.

### Convergence Strategies Not Supported in Prompt-Only

If a step has `loop.strategy`, prompt-only mode (like the base executor in slice 149) logs a warning and falls back to basic max-iteration behavior. Convergence strategies require observing all iteration results simultaneously and making intelligent routing decisions — not compatible with "return one instruction at a time."

**Rationale:** Convergence is an advanced feature requiring full pipeline autonomy. Prompt-only mode is for human-in-the-loop workflows where convergence doesn't apply.

## Implementation Details

### Modified: `src/squadron/pipeline/prompt_renderer.py`

The `render_step_instructions()` function gains loop awareness:

```python
def render_step_instructions(
    step: StepConfig,
    *,
    step_index: int,
    total_steps: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
    loop_context: LoopContext | None = None,  # NEW
) -> StepInstructions:
    """Render instructions for one step, with loop context if applicable."""
```

If `step.step_type == "each"` and `loop_context is None` (not currently in a loop):
- Resolve the source query (same as executor does)
- Initialize `loop_context` with the first item
- Expand inner steps for that item
- Return instructions for the first inner step with `loop_context` attached

If `loop_context is not None` (already in a loop):
- Check if current iteration is complete (all inner steps done)
- If yes, advance to next item or finish if all items done
- If no, return instructions for next unfinished inner step in current iteration

### Modified: `src/squadron/pipeline/models.py`

Add `LoopContext` dataclass:

```python
@dataclass
class LoopContext:
    """Current position within a collection loop."""
    step_name: str               # Name of the "each" step (e.g., "batch-0")
    item_index: int              # Which item (0-based)
    item_key: str                # Identifier for this item
    current_item: dict[str, object]  # Full item dict with resolved fields
    completed_items: list[str]   # Item keys completed so far
    total_items: int             # Total items queried
```

Extend `RunState` with `loop_context: LoopContext | None = None`.

Extend `StepInstructions` with `loop_context: LoopContext | None = None` so the JSON output includes it.

### Modified: `src/squadron/cli/commands/run.py`

The `--prompt-only` and `--next` paths use the extended `render_step_instructions()` signature. No major logic changes — the loop handling is delegated to `render_step_instructions()`.

State manager integration: When `StateManager.record_step_done()` is called, check if the step name matches an iteration pattern (`*-each-*`). If yes, and if all inner steps for that iteration are done, update `loop_context.completed_items`.

### State File Schema Update (RunState)

The JSON state file version increments (if versioned). Existing v1 state files have `loop_context: null`. New runs use v2 with `loop_context` populated only when inside a loop.

For resume compatibility:
- If resuming a v1 state file (pre-loop), behavior is unchanged.
- If resuming a v2 state file with `loop_context`, the executor restores the loop context and continues.

## Integration Points

### Provides to Other Slices

- **Slice 155 (SDK Executor):** No direct interaction; slice 155 uses the real executor (slice 149), not prompt-only. Both paths share the same `RunState` schema, so state files are compatible across modes.

### Consumes from Other Slices

- **Slice 153 (Prompt-Only Executor):** Extends the `render_step_instructions()` function and state model.
- **Slice 149 (Executor):** The loop implementation in the real executor is the reference for how loops work. Prompt-only mode mirrors that behavior in the instruction-generation layer.
- **Slice 150 (State Manager):** Uses the extended `RunState` schema with `loop_context`.

## Success Criteria

1. **Loop iteration detection:** When a pipeline contains an `each` step, `sq run <pipeline> --prompt-only` correctly identifies the items from the source query and initializes `loop_context` in the state.

2. **Successive iteration instructions:** `--next` returns instructions for the first inner step of the first item. After `--step-done`, the next `--next` returns instructions for the next unfinished inner step in the same iteration or the first step of the next item if the current item is complete.

3. **Item variable resolution:** Bound item fields like `{slice.index}` resolve correctly in step configs, and the resolved value appears in the instruction output.

4. **Progress tracking:** The `total_steps` field in the instruction output reflects the cumulative count across all iterations, so a caller can display accurate progress (e.g., "Step 2 of 6").

5. **Loop completion detection:** After the final inner step of the final item is marked done, `--next` returns a completion status.

6. **State persistence:** The `RunState` JSON includes `loop_context`, and resuming with `--resume <run-id>` correctly restores the loop position.

7. **Slash command compatibility:** The `/sq:run` slash command (which was updated in slice 153 and consumes prompt-only output) works transparently with loops. Running `/sq:run design-batch 100` iterates through all items and their steps without modification to the slash command logic.

8. **Loop naming clarity:** Step names in state and output follow the `{step_name}-each-{index}` pattern, making loop iterations unambiguous.

## Verification Walkthrough

*This walkthrough assumes slice 149 (loops in the real executor) is complete and slice 153 (prompt-only output) is complete.*

### 1. Design-Batch Pipeline Initialization

```bash
sq run design-batch 100 --prompt-only
```

**Expected Output:**
- JSON with `step_name: "design-each-0"`, `loop_context: { item_index: 0, item_key: "151", total_items: 3, current_item: {...} }`
- 6 total steps (3 items × 2 inner steps: design, tasks)
- `step_index: 0` in the output

### 2. Completion and Next Step

```bash
sq run --step-done <run-id> --verdict PASS
sq run --prompt-only --next --resume <run-id>
```

**Expected Output (next step):**
- JSON with `step_name: "tasks-each-0"`, same item (slice 151)
- `step_index: 1`, `total_steps: 6`

### 3. Advance to Next Item

After marking all steps for item 1 complete:

```bash
sq run --step-done <run-id>
sq run --prompt-only --next --resume <run-id>
```

**Expected Output:**
- JSON with `step_name: "design-each-1"`, new item (slice 152)
- `loop_context.item_index: 1`
- `step_index: 2`, `total_steps: 6`

### 4. Complete All Items

After marking the final step complete:

```bash
sq run --step-done <run-id>
sq run --prompt-only --next --resume <run-id>
```

**Expected Output:**
- Completion JSON: `{ "status": "completed", "message": "All iterations complete" }`

### 5. Slash Command End-to-End

```bash
/sq:run design-batch 100
```

**Expected Outcome:**
- Slash command drives the loop via successive `--next` calls
- All 3 items and 6 total steps are executed in sequence
- Run state shows completed status with all steps recorded
- No changes to the slash command implementation needed (it already consumes slice 153's output)

### 6. Resume Mid-Iteration

If a checkpoint pauses mid-loop:

```bash
sq run --prompt-only --next --resume <run-id>
```

**Expected Output:**
- Correct item and step context restored
- Loop continues from the paused checkpoint

### 7. State File Inspection

```bash
cat ~/.config/squadron/runs/design-batch-<run-id>.json
```

**Expected Content:**
- `loop_context` field with `item_index`, `completed_items`, `total_items`
- Completed steps list includes steps named `design-each-0`, `tasks-each-0`, `design-each-1`, etc.

## Implementation Notes

### Development Approach

1. **Extend `LoopContext` and `RunState`** — Add dataclass definitions with JSON serialization support.
2. **Update `StepInstructions` output model** — Include `loop_context` in the JSON schema.
3. **Modify `render_step_instructions()` for loop awareness** — Detect `each` steps, resolve source queries, expand inner steps, handle iteration progression.
4. **Extend `StateManager.record_step_done()`** — Detect iteration-pattern step names and update `loop_context.completed_items`.
5. **State file schema versioning** — Ensure v1 state files (pre-loop) are handled gracefully.
6. **Unit tests** — Test `render_step_instructions()` with mock loop sources, test item binding variable resolution, test iteration progression.
7. **Integration tests** — Load `design-batch` pipeline, simulate successive `--next` calls, verify step ordering and loop progression.

### Testing Strategy

- **Loop context tracking:** Mock CF client returning 3 test slices. Call `render_step_instructions()` 6 times (2 steps × 3 items). Verify `loop_context` advances correctly.
- **Item variable resolution:** Test that `{slice.index}` in step config is replaced with the current item's index value. Test that non-matching placeholders are left as-is.
- **State persistence:** Serialize and deserialize `RunState` with loop context. Verify JSON schema is valid.
- **Step naming:** Verify iteration-pattern step names follow `{name}-each-{index}`.
- **Completion detection:** After the final step's `--step-done`, verify `--next` returns completion status.

### Effort

2/5 — The changes are extensions to existing slice 153 code. Loop handling in the executor (slice 149) is already built; prompt-only mode just needs to expose it as an instruction stream. Main work is:
- Updating the `RunState` schema with loop context
- Extending `render_step_instructions()` for loop logic
- Testing iteration progression

### Dependencies and Risks

- **Low risk:** Loops are already implemented in slice 149. Prompt-only mode is slicing that behavior into instructions. No fundamental new logic.
- **State schema change:** Existing v1 state files will have `loop_context: null`, which is backward compatible. New v2 files include loop context. Migration path is implicit (null context = not in a loop).

### Backward Compatibility

- **Pipelines without loops** continue to work unchanged. `loop_context` is `None`, and instruction generation proceeds as in slice 153.
- **Resuming pre-loop state files** works if they don't contain loop context. The executor treats absence of `loop_context` as "not in a loop."
- **Slash command compatibility** is automatic — `/sq:run` doesn't need modifications because it already consumes the instruction JSON from slice 153.

