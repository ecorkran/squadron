---
docType: tasks
slice: prompt-only-loops
project: squadron
lld: user/slices/154-slice.prompt-only-loops.md
dependencies: [153-prompt-only-pipeline-executor]
projectState: "Pipeline foundation complete (140-153). sq run --prompt-only executes single-step sequential pipelines via StepInstructions JSON. /sq:run slash command consumes prompt-only output. StateManager has record_step_done, first_unfinished_step. executor.py runs each loops in SDK mode. Prompt-only mode has no loop awareness yet."
dateCreated: 20260410
dateUpdated: 20260410
status: not_started
---

# Tasks: Prompt-Only Loops

## Context

Extending the prompt-only executor (slice 153) to handle `each` loop steps transparently. When a pipeline's next step is `each`, successive `--next` calls return individual iteration instructions as if they were sequential steps. Loop state is tracked in a new `LoopContext` model on `RunState`. Callers (including `/sq:run`) see a flat instruction stream — no loop-awareness required.

Files modified:
- `src/squadron/pipeline/state.py` — `LoopContext` model, `RunState` extension, new `StateManager` methods
- `src/squadron/pipeline/prompt_renderer.py` — `LoopInstructionContext`, `StepInstructions` extension, `render_each_step_instructions()`
- `src/squadron/pipeline/executor.py` — rename `_unpack_inner_steps` → `unpack_inner_steps`
- `src/squadron/cli/commands/run.py` — loop-aware `_handle_prompt_only_init`, `_handle_prompt_only_next`, `_handle_step_done`

No new components. No schema version bump (additive `None`-default field).

---

## T1: `LoopContext` Model and `RunState` Extension

- [ ] In `src/squadron/pipeline/state.py`, add `LoopContext` Pydantic model above `RunState`:
  - [ ] Fields: `step_name: str`, `as_name: str`, `items: list[dict[str, object]]`, `inner_steps: list[dict[str, object]]`, `current_item_index: int = 0`, `current_inner_step_index: int = 0`
  - [ ] Docstring: `"Active loop state for prompt-only each-step execution."`
- [ ] Add `loop_context: LoopContext | None = None` field to `RunState` (after existing fields)
- [ ] Success: `LoopContext` model instantiates correctly; `RunState` round-trips through JSON with `loop_context` both absent (→ `None`) and populated

**Commit**: `feat: add LoopContext model and loop_context field to RunState`

---

## T2: Unit Tests — `LoopContext` and `RunState`

- [ ] In `tests/pipeline/test_state.py` (or `tests/pipeline/test_loop_state.py` if the former is too large), add tests:
  - [ ] `LoopContext` round-trips through `model_dump()` / `model_validate()` with all fields
  - [ ] `RunState` with `loop_context=None` serializes to JSON without the field (or with `null`) and deserializes back to `None`
  - [ ] `RunState` with a populated `LoopContext` serializes and deserializes all loop fields correctly
  - [ ] Existing v3 state JSON file (without `loop_context` key) deserializes with `loop_context = None` (backward compatibility)
- [ ] Success: all new tests pass, no regressions in existing state tests

---

## T3: `StateManager.init_loop_context()` Method

- [ ] Add `init_loop_context(self, run_id: str, step_name: str, as_name: str, items: list[dict[str, object]], inner_steps: list[dict[str, object]]) -> None` to `StateManager`
  - [ ] Load state, create `LoopContext` with provided values, assign to `state.loop_context`
  - [ ] Update `state.updated_at` and persist via `_write_atomic`
- [ ] Success: after call, `load(run_id).loop_context` has correct fields and indexes default to 0

---

## T4: `StateManager.advance_loop()` Method

- [ ] Add `advance_loop(self, run_id: str) -> bool` to `StateManager`
  - [ ] Return `True` immediately if `state.loop_context is None` (no active loop)
  - [ ] Increment `current_inner_step_index`
  - [ ] If past end of `inner_steps`: reset `current_inner_step_index = 0`, increment `current_item_index`
  - [ ] If `current_item_index >= len(items)`: set `state.loop_context = None`, persist, return `True` (loop complete)
  - [ ] Otherwise: persist updated context, return `False`
- [ ] Success: loop advances correctly through inner steps and items; returns `True` only when all items exhausted

**Commit**: `feat: add StateManager.init_loop_context and advance_loop methods`

---

## T5: Unit Tests — `StateManager` Loop Methods

- [ ] Add to loop state test file:
  - [ ] `init_loop_context` persists `LoopContext` readable on reload
  - [ ] `advance_loop` with 2 items × 1 inner step: sequences through `(0,0)` → `(1,0)` → complete (returns `True`)
  - [ ] `advance_loop` with 1 item × 2 inner steps: sequences `(0,0)` → `(0,1)` → complete
  - [ ] `advance_loop` when `loop_context is None`: returns `True` without error
  - [ ] After `advance_loop` returns `True`, `load().loop_context` is `None`
- [ ] Success: all tests pass

---

## T6: `LoopInstructionContext` and `StepInstructions` Extension

- [ ] In `src/squadron/pipeline/prompt_renderer.py`, add `LoopInstructionContext` dataclass:
  - [ ] Fields: `each_step: str`, `item_index: int`, `item_key: str`, `total_items: int`, `current_item: dict[str, object]`
  - [ ] Must be JSON-serializable via `dataclasses.asdict()`
- [ ] Add `loop_context: LoopInstructionContext | None = None` field to `StepInstructions` dataclass
- [ ] Success: `StepInstructions.to_json()` includes `loop_context` when populated; field is `null` when absent

---

## T7: Unit Tests — `LoopInstructionContext` Serialization

- [ ] In `tests/pipeline/test_prompt_renderer.py`, add:
  - [ ] `LoopInstructionContext` round-trips through `asdict()` → JSON with all fields
  - [ ] `StepInstructions` with `loop_context=None` serializes `loop_context` as `null`
  - [ ] `StepInstructions` with populated `LoopInstructionContext` serializes all nested fields
- [ ] Success: all tests pass

---

## T8: Rename `_unpack_inner_steps` in `executor.py`

- [ ] In `src/squadron/pipeline/executor.py`, rename `_unpack_inner_steps` → `unpack_inner_steps` (remove leading underscore)
- [ ] Update all internal callers of `_unpack_inner_steps` within `executor.py` to use new name
- [ ] Verify no other files reference `_unpack_inner_steps` (grep check)
- [ ] Success: `from squadron.pipeline.executor import unpack_inner_steps` works; all existing tests still pass

**Commit**: `refactor: make unpack_inner_steps importable (drop leading underscore)`

---

## T9: `render_each_step_instructions()` Function

- [ ] In `src/squadron/pipeline/prompt_renderer.py`, add `render_each_step_instructions()`:
  - [ ] Parameters: `inner_step_raw: dict[str, object]`, `inner_step_index: int`, `item: dict[str, object]`, `item_index: int`, `total_items: int`, `as_name: str`, `each_step_name: str`, `total_flattened_steps: int`, `flattened_step_index: int`, `params: dict[str, object]`, `resolver: ModelResolver`, `run_id: str`
  - [ ] Import `unpack_inner_steps` from `executor`
  - [ ] Call `unpack_inner_steps([inner_step_raw])` to get `StepConfig`
  - [ ] Merge `{as_name: item}` into `params` for placeholder resolution
  - [ ] Call existing `render_step_instructions()` with bound params and `step_index=flattened_step_index`, `total_steps=total_flattened_steps`
  - [ ] Build `LoopInstructionContext` from item data and attach to result
  - [ ] Override `result.step_name` with `f"{inner_step_name}-each-{item_index}"`
- [ ] Success: given a `design` inner step and an item with `index: "151"`, produces `StepInstructions` with `step_name="design-each-0"` and `loop_context` populated with `item_index=0` and `current_item` containing the item dict

---

## T10: Unit Tests — `render_each_step_instructions()`

- [ ] Add to `tests/pipeline/test_prompt_renderer.py`:
  - [ ] Step name follows `{inner_step_name}-each-{item_index}` pattern
  - [ ] `{slice.index}` in inner step config resolves to the item's `index` value
  - [ ] `loop_context` on result has correct `item_index`, `total_items`, `item_key`, `current_item`
  - [ ] `step_index` and `total_steps` on result match `flattened_step_index` and `total_flattened_steps`
  - [ ] Second item (index 1) produces `step_name="design-each-1"` with correct item binding
- [ ] Success: all tests pass

**Commit**: `feat: add render_each_step_instructions for prompt-only loop rendering`

---

## T11: `_handle_prompt_only_init` — Loop Detection

- [ ] In `src/squadron/cli/commands/run.py`, modify `_handle_prompt_only_init`:
  - [ ] After pipeline load, check if first step is `each` type
  - [ ] If `each`: construct `ContextForgeClient`, resolve source via `_parse_source` and `_SOURCE_REGISTRY`, unpack items
  - [ ] Call `state_manager.init_loop_context(run_id, step_name, as_name, items, inner_steps)`
  - [ ] Compute `total_flattened_steps = len(items) × len(inner_steps)` (plus any non-loop steps)
  - [ ] Call `render_each_step_instructions()` for item 0, inner step 0
  - [ ] Output the resulting `StepInstructions` JSON; print run_id to stderr
  - [ ] If first step is not `each`: existing behavior unchanged
- [ ] Success: `sq run design-batch 100 --prompt-only` outputs JSON with `step_name="design-each-0"` and `loop_context` populated

---

## T12: Unit Tests — `_handle_prompt_only_init` with Loop

- [ ] In `tests/pipeline/test_prompt_only_integration.py` (or new `test_loop_init.py`):
  - [ ] Mock CF client returning 3 test slices; verify `step_name="design-each-0"` in output
  - [ ] State file after init has `loop_context` with `current_item_index=0`, `current_inner_step_index=0`, `len(items)=3`
  - [ ] Non-loop pipeline: init still returns first step unchanged (no regression)
- [ ] Success: all tests pass

---

## T13: `_handle_prompt_only_next` — Loop-Aware Rendering

- [ ] Modify `_handle_prompt_only_next` in `run.py`:
  - [ ] Load state; check `state.loop_context`
  - [ ] Case A — `loop_context` is populated: use context to get current item and inner step; call `render_each_step_instructions()`
  - [ ] Case B — next unfinished step is `each` but `loop_context is None` (loop not yet started, preceded by non-loop steps): initialize loop context (query source, cache items), then render first inner step of first item
  - [ ] Case C — not in a loop: existing `render_step_instructions()` behavior unchanged
  - [ ] When all items exhausted (`advance_loop` returns `True` and no more steps): return `CompletionResult`
- [ ] Success: successive `--next` calls after `--step-done` return `design-each-1`, `design-each-2`, then completion

---

## T14: Unit Tests — `_handle_prompt_only_next` with Loop

- [ ] Add tests:
  - [ ] Full 3-item sequence: init → step-done × 3 → next × 3 → completion; verify step names in order
  - [ ] Case B (loop follows non-loop step): verify `--next` initializes loop context on demand
  - [ ] Resume mid-loop: write state with `current_item_index=1`; verify `--next` returns `design-each-1`
  - [ ] Non-loop pipeline: `--next` still returns sequential steps unchanged
- [ ] Success: all tests pass

**Commit**: `feat: add loop-aware _handle_prompt_only_next`

---

## T15: `_handle_step_done` — Loop Advancement

- [ ] Modify `_handle_step_done` in `run.py`:
  - [ ] If `state.loop_context` is not `None`:
    - [ ] Derive iteration step name: `f"{inner_step_name}-each-{current_item_index}"`
    - [ ] Call `state_manager.record_step_done(run_id, iteration_step_name, step_type, verdict)`
    - [ ] Call `state_manager.advance_loop(run_id)` and capture return value
    - [ ] If loop complete (`True`): call `record_step_done` for the `each` step itself
  - [ ] Otherwise: existing `record_step_done` behavior unchanged
- [ ] Success: after `--step-done` on item 0, state shows `design-each-0` completed and `current_item_index=1`

---

## T16: Unit Tests — `_handle_step_done` with Loop

- [ ] Add tests:
  - [ ] `--step-done` when `loop_context` active: records `design-each-0` in state, advances to item 1
  - [ ] `--step-done` on final item: records `design-each-2` and `each` step as completed; `loop_context` is `None` after
  - [ ] Verdict is stored on the iteration step record
  - [ ] Non-loop `--step-done`: no regression in existing behavior
- [ ] Success: all tests pass

**Commit**: `feat: add loop advancement in _handle_step_done`

---

## T17: Integration Test — Full Design-Batch Loop Cycle

- [ ] Add test in `tests/pipeline/test_prompt_only_integration.py`:
  - [ ] Use `design-batch` pipeline (or equivalent with `each` step + 3 mock CF items)
  - [ ] Init with `--prompt-only`: verify `design-each-0` output
  - [ ] `--step-done` × 1, `--next` × 1: verify `design-each-1`
  - [ ] `--step-done` × 1, `--next` × 1: verify `design-each-2`
  - [ ] `--step-done` × 1, `--next` × 1: verify `CompletionResult`
  - [ ] State file: `loop_context` is `null`, `completed_steps` has `design-each-0`, `design-each-1`, `design-each-2`, and the `each` step
  - [ ] Multi-inner-step test: pipeline with 2 inner steps per item (e.g., design + tasks); verify inner step sequencing within each item before advancing to next item
- [ ] Success: full loop cycle from init through completion works end-to-end

**Commit**: `test: add design-batch prompt-only loop integration test`

---

## T18: Lint, Type Check, and Final Verification

- [ ] Run `ruff check src/squadron/pipeline/state.py src/squadron/pipeline/prompt_renderer.py src/squadron/pipeline/executor.py src/squadron/cli/commands/run.py` — clean
- [ ] Run `ruff format` on all modified files
- [ ] Run `pyright` — zero errors on new and modified code
- [ ] Run full test suite: `pytest tests/` — no regressions, all new tests pass
- [ ] Run the Verification Walkthrough from the slice design document (sections 1–6)
  - [ ] Section 1: `sq run design-batch 100 --prompt-only` — JSON with `design-each-0`, `loop_context` populated
  - [ ] Section 2: `--step-done` + `--next` — returns `design-each-1`
  - [ ] Section 3: full completion — `CompletionResult` after third item
  - [ ] Section 5: state file inspection — `loop_context: null`, 3 iteration entries in `completed_steps`
  - [ ] Section 6: resume mid-loop — `--next` after mid-run `--resume` returns correct next iteration

**Commit**: `chore: lint and verify prompt-only loops`

---

## T19: Closeout

- [ ] Update `user/slices/154-slice.prompt-only-loops.md` status to `complete`
- [ ] Update slice plan entry in `140-slices.pipeline-foundation.md` for slice 154 to `[x]`
- [ ] Write DEVLOG entry summarizing implementation, any deviations from design, and final test results

**Commit**: `docs: mark slice 154 prompt-only loops complete`
