---
docType: tasks
slice: prompt-only-pipeline-executor
project: squadron
lld: user/slices/153-slice.prompt-only-pipeline-executor.md
dependencies: [151-cli-integration-and-end-to-end-validation]
projectState: "Pipeline foundation complete (140-151). sq run CLI working with full executor, state manager, and loader. Built-in pipelines (slice, review, implement) validated. Slash command /sq:run exists but hardcodes workflow steps in markdown."
dateCreated: 20260403
dateUpdated: 20260403
status: complete
dateUpdated: 20260404
---

# Tasks: Prompt-Only Pipeline Executor

## Context

Working on slice 153 (Prompt-Only Pipeline Executor) in project squadron. This slice adds `--prompt-only` mode to `sq run` that outputs structured JSON instructions for one step at a time, and updates the `/sq:run` slash command to consume that output instead of hardcoding workflow logic. The pipeline YAML becomes the single source of truth for both automated and interactive execution.

Key dependencies already in place:
- Pipeline executor with step expansion, model resolution, state management (slices 142-151)
- Step types: phase (design/tasks/implement), compact, review, devlog — each with `expand()` methods
- `StateManager` with `init_run`, `first_unfinished_step`, `finalize`, `_append_step`
- `ModelResolver` with 5-level cascade
- Compact action with `render_instructions()` and pipeline param resolution
- `sq run` Typer command with `--resume`, `--from`, `--status`, `--list`, `--validate`, `--dry-run`

Next slice: 154 (Prompt-Only Loops and Model Switching).

---

## T1: Data Models — `StepInstructions` and `ActionInstruction`

- [x] Create `src/squadron/pipeline/prompt_renderer.py` with dataclass definitions
  - [x] `ActionInstruction` dataclass: `action_type: str`, `instruction: str`, `command: str | None`, `model: str | None`, `model_switch: str | None`, `template: str | None`, `trigger: str | None`, `resolved_instructions: str | None`
  - [x] `StepInstructions` dataclass: `run_id: str`, `step_name: str`, `step_type: str`, `step_index: int`, `total_steps: int`, `actions: list[ActionInstruction]`
  - [x] Both dataclasses must be JSON-serializable via `dataclasses.asdict()` (no custom types)
  - [x] `StepInstructions.to_json() -> str` convenience method using `json.dumps(asdict(self), indent=2)`
  - [x] Add `CompletionResult` dataclass: `status: str`, `message: str`, `run_id: str` — returned when no more steps remain
- [x] Success: module imports cleanly, `asdict()` produces valid JSON for both types

**Commit**: `feat: add StepInstructions and ActionInstruction data models`

---

## T2: Unit Tests — Data Models

- [x] Create `tests/pipeline/test_prompt_renderer.py`
  - [x] Test `ActionInstruction` round-trips through `asdict()` → JSON → dict
  - [x] Test `StepInstructions.to_json()` produces valid JSON with all fields
  - [x] Test optional fields (`command`, `model`, etc.) serialize as `null` when `None`
  - [x] Test `CompletionResult` serializes correctly
- [x] Success: all tests pass, `pytest tests/pipeline/test_prompt_renderer.py` clean

---

## T3: Action Instruction Builders — Per-Action-Type Rendering

- [x] In `prompt_renderer.py`, add builder functions that convert an `(action_type, action_config)` tuple into an `ActionInstruction`
  - [x] `_render_cf_op(config, params)` — generates `command` field (`cf set phase N` or `cf build`), human-readable `instruction`
  - [x] `_render_dispatch(config, params, resolver)` — generates `model` and `model_switch` fields (e.g., `/model opus`), `instruction` describing the work. No `command` (dispatch is in-session work)
  - [x] `_render_review(config, params, resolver)` — generates `command` field (`sq review {template} ... --model {model} --template {template} -v`), `model`, `template` fields
  - [x] `_render_checkpoint(config, params)` — generates `trigger` field, `instruction` describing the pause condition
  - [x] `_render_commit(config, params)` — generates `command` field (`git add -A && git commit -m '...'`), `instruction`
  - [x] `_render_compact(config, params)` — loads template via `load_compaction_template()`, calls `render_instructions()` with pipeline params, sets `command` to `/compact [{resolved_instructions}]`, `resolved_instructions`, `template` fields
  - [x] `_render_devlog(config, params)` — generates `instruction` for devlog entry, appropriate `command`
  - [x] Fallback for unknown action types: `ActionInstruction` with `instruction` only
- [x] Success: each builder returns a well-formed `ActionInstruction` with correct fields populated

---

## T4: Unit Tests — Action Instruction Builders

- [x] Test `_render_cf_op` for `set_phase` (command includes phase number) and `build_context`
- [x] Test `_render_dispatch` with model specified (includes `model_switch`) and without model (no `model_switch`)
- [x] Test `_render_review` includes `--template` and `--model` in command string
- [x] Test `_render_checkpoint` for each trigger type (`on-concerns`, `on-fail`, `always`, `never`)
- [x] Test `_render_commit` produces git command with message prefix
- [x] Test `_render_compact` resolves pipeline params in template (e.g., `{slice}` → `152`). Mock `load_compaction_template` to avoid filesystem dependency
- [x] Test `_render_devlog` produces appropriate instruction
- [x] Test fallback for unrecognized action type
- [x] Success: all tests pass

**Commit**: `feat: add action instruction builders for prompt-only renderer`

---

## T5: `render_step_instructions()` — Main Entry Point

- [x] Implement `render_step_instructions()` in `prompt_renderer.py`
  - [x] Accept `step: StepConfig`, `step_index: int`, `total_steps: int`, `params: dict`, `resolver: ModelResolver`, `run_id: str`
  - [x] Call `get_step_type_fn(step.step_type)` to get step type implementation
  - [x] Call `step_type.expand(step)` to get `list[tuple[str, dict]]` action sequence
  - [x] For each `(action_type, action_config)`: resolve placeholders in config, call the appropriate builder function
  - [x] Return `StepInstructions` with step metadata and action list
- [x] Success: given a `StepConfig` from `slice.yaml`, produces correct `StepInstructions` with all actions expanded

---

## T6: Unit Tests — `render_step_instructions()`

- [x] Test with a design phase step config (phase 4, model opus, review with template slice and model glm5, checkpoint on-concerns)
  - [x] Verify 6 actions produced: cf-op(set_phase), cf-op(build), dispatch, review, checkpoint, commit
  - [x] Verify dispatch has `model: opus`, `model_switch: /model opus`
  - [x] Verify review has `template: slice`, `model: glm5`
  - [x] Verify checkpoint has `trigger: on-concerns`
- [x] Test with a compact step config (template: minimal, slice param = "152")
  - [x] Verify 1 action: compact with resolved instructions containing "152"
- [x] Test with a devlog step config (mode: auto)
  - [x] Verify 1 action: devlog
- [x] Test with a step that has no review configured (should omit review and checkpoint actions)
- [x] Success: all tests pass, covering the main step types in `slice.yaml`

**Commit**: `feat: add render_step_instructions entry point`

---

## T7: `StateManager.record_step_done()` — Public Method

- [x] Add `record_step_done(run_id, step_name, step_type, verdict=None)` to `StateManager`
  - [x] Construct a minimal `StepResult` internally (status=COMPLETED, step_name, step_type)
  - [x] Delegate to existing `_append_step()` to persist
  - [x] If verdict is provided, include it so checkpoint evaluation can access it
- [x] Success: method persists step completion and is loadable via `load()`

---

## T8: Unit Tests — `record_step_done()`

- [x] Test basic step completion: call `record_step_done`, verify step appears in `load().completed_steps`
- [x] Test with verdict: call with `verdict="PASS"`, verify verdict is stored in step state
- [x] Test sequential steps: record two steps, verify both appear in order
- [x] Test with invalid run_id: raises appropriate error
- [x] Success: all tests pass

**Commit**: `feat: add StateManager.record_step_done public method`

---

## T9: CLI — `--prompt-only` Flag and Init Flow

- [x] Add `--prompt-only` option to `run()` command in `src/squadron/cli/commands/run.py`
  - [x] Mutually exclusive with `--dry-run` (both suppress execution but serve different purposes)
  - [x] When `--prompt-only` is set without `--resume`/`--next`: load pipeline, validate, init run via `StateManager`, render first step, output JSON to stdout
  - [x] Print run_id to stderr (so it can be captured separately from JSON on stdout)
- [x] Add `--next` flag — requires `--prompt-only` and `--resume`, loads existing run, finds next unfinished step, renders it
  - [x] When all steps are done, output `CompletionResult` JSON and finalize the run
- [x] Success: `sq run slice 152 --prompt-only` outputs valid JSON for design step

---

## T10: Unit Tests — `--prompt-only` CLI Flow

- [x] Test `--prompt-only` with pipeline and target: outputs valid JSON with correct step_name
- [x] Test `--prompt-only` creates a state file (run is initialized)
- [x] Test `--prompt-only --next --resume <id>`: outputs next step after first is marked done
- [x] Test `--prompt-only --next` when all steps done: outputs completion JSON
- [x] Test `--prompt-only` mutual exclusivity with `--dry-run`
- [x] Test `--next` without `--resume` produces error
- [x] Success: all tests pass

**Commit**: `feat: add --prompt-only and --next CLI flags`

---

## T11: CLI — `--step-done` Flag

- [x] Add `--step-done` option to `run()` command
  - [x] Accepts a run_id value
  - [x] Optional `--verdict` flag (PASS, CONCERNS, FAIL)
  - [x] Calls `StateManager.record_step_done()` with the current step info
  - [x] Determines current step from state (first unfinished step in the pipeline definition)
  - [x] Outputs confirmation to stdout (brief JSON or text)
  - [x] Mutually exclusive with `--prompt-only`, `--dry-run`, normal execution
- [x] Success: `sq run --step-done <run-id> --verdict PASS` marks step complete in state

---

## T12: Unit Tests — `--step-done` CLI Flow

- [x] Test `--step-done` marks step complete: init run with `--prompt-only`, then `--step-done`, verify state
- [x] Test `--step-done --verdict PASS` stores verdict
- [x] Test `--step-done` when no run exists: produces error
- [x] Test `--step-done` when all steps already done: produces appropriate message
- [x] Test mutual exclusivity with other execution flags
- [x] Success: all tests pass

**Commit**: `feat: add --step-done CLI flag for prompt-only feedback`

---

## T13: Integration Test — Full Prompt-Only Cycle

- [x] Create integration test in `tests/pipeline/test_prompt_only_integration.py`
  - [x] Load `slice` pipeline definition
  - [x] Call `--prompt-only` to init and get first step
  - [x] Verify JSON structure: run_id, step_name, actions list
  - [x] Call `--step-done` with run_id
  - [x] Call `--prompt-only --next --resume` to get second step
  - [x] Repeat for all 6 steps of slice pipeline
  - [x] Verify final `--next` returns completion status
  - [x] Verify state file shows all 6 steps completed
- [x] Success: full cycle from init through completion works correctly

**Commit**: `test: add prompt-only full cycle integration test`

---

## T14: Slash Command Update — `/sq:run`

- [x] Rewrite `commands/sq/run.md` to consume `sq run --prompt-only` output
  - [x] Step 0 (Validate): Run `sq run <pipeline> <target> --prompt-only`, capture JSON
  - [x] Main loop: parse JSON, execute each action by type:
    - [x] `cf-op`: run the `command` field via Bash
    - [x] `dispatch`: note `model_switch` (informational), execute the work described in `instruction`
    - [x] `review`: run the `command` field via Bash, capture output
    - [x] `checkpoint`: evaluate based on `trigger` and previous review verdict — if triggered, pause and present to user
    - [x] `commit`: run the `command` field via Bash
    - [x] `compact`: run the `command` field (which is a `/compact [...]` invocation)
    - [x] `devlog`: execute the `instruction`
  - [x] After each step: run `sq run --step-done <run-id>` (with `--verdict` if review step)
  - [x] Get next step: run `sq run --prompt-only --next --resume <run-id>`
  - [x] Loop until completion JSON received
  - [x] Completion summary: list artifacts, review verdicts, commits
- [x] Success: `/sq:run slice 152` follows the executor-driven flow rather than hardcoded phases

---

## T15: Slash Command — Error Handling and Edge Cases

- [x] Handle `sq run --prompt-only` failure (invalid pipeline, missing params) — show error and stop
- [x] Handle `--step-done` failure — show error but don't lose progress
- [x] Handle checkpoint pause — present findings to user, ask for decision (continue/abort)
- [x] Handle review verdict FAIL with `on-fail` checkpoint — stop and present, don't silently continue
- [x] Preserve existing slash command features: CF pre-flight validation, review file persistence
- [x] Success: slash command handles errors gracefully without losing state

**Commit**: `feat: update /sq:run slash command to consume prompt-only executor`

---

## T16: Exports, Lint, and Verification

- [x] Add public exports from `prompt_renderer.py` to `squadron.pipeline` package `__init__.py` if appropriate
- [x] Run `ruff check src/squadron/pipeline/prompt_renderer.py` — clean
- [x] Run `ruff format` on all modified files
- [x] Run `pyright` — zero errors on new code
- [x] Run full test suite: `pytest tests/pipeline/test_prompt_renderer.py tests/pipeline/test_prompt_only_integration.py tests/pipeline/test_state.py` — all pass
- [x] Verify existing tests still pass: `pytest tests/` — no regressions
- [x] Success: all linting, type checking, and tests pass

**Commit**: `chore: lint and verify prompt-only pipeline executor`

---

## T17: Verification Walkthrough and Closeout

- [x] Run through the Verification Walkthrough in the slice design document
  - [x] `sq run slice 152 --prompt-only` — verify JSON output structure
  - [x] `sq run --step-done <run-id> --verdict PASS` — verify state update
  - [x] `sq run --prompt-only --next --resume <run-id>` — verify next step
  - [x] Compact step — verify resolved instructions contain slice number
  - [x] `sq run --status latest` — verify state display
- [x] Update Verification Walkthrough with actual output and any corrections
- [x] Update slice design status to `complete`
- [x] Update slice plan entry to `[x]`
- [x] Update CHANGELOG.md
- [x] Write DEVLOG entry

**Commit**: `docs: mark slice 153 prompt-only pipeline executor complete`
