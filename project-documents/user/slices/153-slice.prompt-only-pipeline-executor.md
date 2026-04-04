---
docType: slice-design
slice: prompt-only-pipeline-executor
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [151-cli-integration-and-end-to-end-validation]
interfaces: [152-pipeline-documentation]
dateCreated: 20260403
dateUpdated: 20260404
status: complete
---

# Slice Design: Prompt-Only Pipeline Executor

## Overview

Add a `--prompt-only` mode to `sq run` that outputs one step's structured instructions at a time instead of dispatching to LLMs. Each invocation advances the pipeline's state and returns the next step's instructions as structured output. The `/sq:run` slash command is then updated to consume this output — becoming a thin loop that calls `sq run --prompt-only --next`, executes the instructions, and repeats.

This bridges the gap between the automated pipeline executor (which can't yet dispatch to Claude Code) and the `/sq:run` slash command (which reimplements YAML interpretation in a markdown prompt). The YAML pipeline definition becomes the single source of truth consumed by both paths.

## Value

- **Single source of truth**: Pipeline YAML drives both automated and interactive execution — no logic duplication between the slash command and the Python executor.
- **Deterministic step generation**: Python code parses YAML and expands steps, producing consistent instructions regardless of which runtime executes them.
- **Model switching**: In CLI sessions, `/model {alias}` can be issued per step. In the IDE extension it's a no-op but harmless.
- **Incremental path to full automation**: Today the runtime is "you" (Claude in-session). Tomorrow the same `--prompt-only` output could feed external dispatch. The executor doesn't care who consumes it.

## Technical Scope

### In Scope

1. **`--prompt-only` flag on `sq run`** — Suppress action dispatch; emit step instructions to stdout instead.
2. **`--next` flag** — Emit only the next unexecuted step (requires a run to exist). Mutually exclusive with full execution.
3. **Step instruction output format** — Structured output (JSON or YAML) containing everything needed to execute one step.
4. **State tracking across `--next` calls** — Reuse existing `StateManager` to track which steps have been completed.
5. **Step completion feedback** — `sq run --step-done <run-id>` (or similar) to mark the current step complete and record its outcome before requesting the next step.
6. **`/sq:run` slash command update** — Rewrite to consume `sq run --prompt-only` output instead of hardcoding workflow steps.

### Out of Scope

- Automated model switching (sending `/model` commands programmatically from Python) — the slash command handles this manually.
- External LLM dispatch for non-review steps (future slice: "External Model Dispatch").
- Changes to the review action or dispatch action internals.
- Automated `/model` command emission (slash command can issue manually; programmatic switching is slice 154).
- `each`/collection loop support in prompt-only mode (slice 154 — executor already handles loops internally, so `--next` returns successive iteration instructions transparently).

## Architecture

### Step Instruction Output

Each `--next` call produces a JSON object describing one step. The structure varies by action type but follows a common envelope:

```json
{
  "run_id": "run-20260403-slice-abc12345",
  "step_name": "design-0",
  "step_type": "design",
  "step_index": 0,
  "total_steps": 6,
  "actions": [
    {
      "action_type": "cf-op",
      "instruction": "Set phase to 4",
      "command": "cf set phase 4"
    },
    {
      "action_type": "cf-op",
      "instruction": "Build context",
      "command": "cf build"
    },
    {
      "action_type": "dispatch",
      "instruction": "Execute the design work using the context from cf build",
      "model": "opus",
      "model_switch": "/model opus"
    },
    {
      "action_type": "review",
      "instruction": "Review the design output",
      "command": "sq review slice {slice} --model glm5 --template slice -v",
      "model": "glm5",
      "template": "slice"
    },
    {
      "action_type": "checkpoint",
      "instruction": "If review verdict is CONCERNS or worse, pause for user decision",
      "trigger": "on-concerns"
    },
    {
      "action_type": "commit",
      "instruction": "Commit the design artifacts",
      "command": "git add -A && git commit -m 'phase-4: ...'"
    }
  ]
}
```

Key design decisions:
- **`command` field**: Present for actions that map to shell commands (cf-op, review, commit, compact). Absent for actions that require in-session work (dispatch).
- **`model_switch` field**: Present on dispatch actions when a model is specified. The slash command can issue this; in IDE it's informational.
- **`instruction` field**: Human-readable description of what needs to happen. The slash command uses this as its directive.

### Compact Step Output

```json
{
  "action_type": "compact",
  "instruction": "Compact context to free space",
  "command": "/compact [Keep slice design, task breakdown, ...]",
  "template": "minimal",
  "resolved_instructions": "Keep slice design, task breakdown, and any task implementation summaries for slice 152. Keep outline of any related architectural or review discussion."
}
```

The compact action's `render_instructions()` is called at generation time with pipeline params resolved, producing the final instruction text.

### Data Flow

```
User runs: sq run slice 152 --prompt-only

  1. Load pipeline definition (slice.yaml)
  2. Validate pipeline
  3. Init run via StateManager (or find existing)
  4. Return: first step instructions (JSON)

User (or slash command) executes the step...

User runs: sq run --step-done <run-id> [--verdict PASS]

  5. Mark step complete in state
  6. Advance state pointer

User runs: sq run --prompt-only --next --resume <run-id>

  7. Load state, find next unexecuted step
  8. Expand step type → action sequence
  9. Generate instruction objects (resolve models, templates, params)
  10. Return: next step instructions (JSON)

... repeat until all steps complete ...

Final --next call returns:
  { "status": "completed", "message": "All steps complete" }
```

### Integration with `/sq:run`

The slash command becomes:

```
1. Run: sq run slice {N} --prompt-only
   → Get first step JSON
2. Parse JSON, for each action:
   - cf-op: run the command
   - dispatch: issue /model {model}, then do the work
   - review: run the sq review command
   - checkpoint: evaluate verdict, pause if needed
   - commit: run the git command
   - compact: run /compact [instructions]
3. Run: sq run --step-done {run-id} [--verdict {V}]
4. Run: sq run --prompt-only --next --resume {run-id}
   → Get next step JSON
5. Repeat from 2 until status is "completed"
```

### State Manager Integration

Prompt-only mode reuses the existing `StateManager` with one new public method:
- `init_run()` creates the run on first `--prompt-only` invocation
- `record_step_done(run_id, step_name, step_type, verdict=None)` — new public method added to `StateManager` for the `--step-done` CLI path. Internally delegates to `_append_step()` by constructing a minimal `StepResult`. This is needed because the CLI caller doesn't have a full `StepResult` object — it only knows the step name and optional verdict.
- `--next` calls `first_unfinished_step()` to find what's next
- `finalize()` is called when last step is completed

No new state fields in `RunState`. The existing `status` of `"in_progress"` naturally represents a prompt-only run between `--next` calls.

### New CLI Surface

```
sq run <pipeline> <target> --prompt-only     # Init run + emit first step
sq run --prompt-only --next --resume <id>    # Emit next step for existing run  
sq run --step-done <run-id>                  # Mark current step complete
sq run --step-done <run-id> --verdict PASS   # Mark complete with review verdict
```

The `--step-done` subcommand (or flag) accepts optional `--verdict` for review/checkpoint steps. This feeds back into state so the next checkpoint action can evaluate trigger conditions.

## Technical Decisions

### Output Format: JSON

JSON rather than YAML for step instructions because:
- Machine-parseable by the slash command (I can parse JSON from command output)
- No ambiguity with multi-line strings
- Consistent with StateManager's JSON persistence

### Step Expansion at Output Time

Steps are expanded into actions when `--next` is called, not when the run is initialized. This matches how the real executor works — expansion happens just before execution. It also means the pipeline definition can theoretically be updated between steps (though this is not a goal).

### Instruction Generation as a Pure Function

The core new code is a function that takes a step config + pipeline params and returns a list of instruction objects. This function:
- Uses existing step type `expand()` to get the action sequence
- Uses existing `ModelResolver` to resolve model aliases
- Uses existing `render_instructions()` for compact templates
- Constructs command strings for cf-op, review, commit actions
- Does NOT execute anything

This keeps the new code minimal and testable.

### Verdict Feedback

The `--step-done --verdict` mechanism allows the slash command to report review outcomes back to state. This is needed because checkpoint triggers (`on-concerns`, `on-fail`) evaluate the previous review's verdict. Without feedback, the next step's checkpoint wouldn't know whether to pause.

## Implementation Details

### New Module: `src/squadron/pipeline/prompt_renderer.py`

Single-purpose module containing the instruction generation logic:

```python
def render_step_instructions(
    step: StepConfig,
    *,
    step_index: int,
    total_steps: int,
    params: dict[str, object],
    resolver: ModelResolver,
    run_id: str,
) -> StepInstructions:
    """Expand a step into executable instruction objects."""
```

`StepInstructions` is a dataclass containing the step metadata and list of `ActionInstruction` objects. Both are JSON-serializable.

### Changes to `src/squadron/cli/commands/run.py`

- Add `--prompt-only` and `--next` flags to the `run()` command
- Add `--step-done` flag (or make it a separate subcommand if cleaner)
- When `--prompt-only` is set, call `render_step_instructions()` instead of `execute_pipeline()`
- Output JSON to stdout

### Changes to `commands/sq/run.md`

Rewrite the slash command to:
1. Call `sq run <pipeline> <target> --prompt-only` to initialize and get first step
2. Parse JSON output
3. Execute each action based on `action_type`
4. Call `sq run --step-done <run-id>` after completing each step
5. Call `sq run --prompt-only --next --resume <run-id>` for subsequent steps
6. Loop until complete

The slash command prompt shrinks significantly — it no longer needs to know about phases, CF commands, or review templates. It just follows instructions from the JSON.

## Success Criteria

1. `sq run slice 152 --prompt-only` outputs valid JSON describing the first step (design) with correct model (`opus`), review template (`slice`), and review model (`glm5`) from `slice.yaml`.
2. `sq run --step-done <run-id>` marks the step complete in state.
3. `sq run --prompt-only --next --resume <run-id>` returns the next step's instructions.
4. After all steps are marked done, `--next` returns a completion status.
5. Compact step instructions include resolved template text with pipeline params (e.g., `{slice}` → `152`).
6. `/sq:run slice 152` uses the prompt-only executor output and produces the same artifacts as the current hardcoded slash command.
7. Review actions in the output include the correct `--template` and `--model` flags from the pipeline YAML.

## Verification Walkthrough

*Verified 2026-04-04.*

### 1. Prompt-only first step

```bash
sq run slice 152 --prompt-only
```

**Result**: JSON output with `step_name: "design-0"`, 6 actions: cf-op(set_phase 4), cf-op(build), dispatch(model: claude-opus-4-6, model_switch: /model opus), review(template: slice, model: z-ai/glm-5), checkpoint(trigger: on-concerns), commit. Run ID printed to stderr.

### 2. Step completion and next step

```bash
sq run --step-done <run-id> --verdict PASS
sq run --prompt-only --next --resume <run-id>
```

**Result**: `tasks-1` step with dispatch model `claude-sonnet-4-6` (`/model sonnet`), review template `tasks`, review model `minimax/minimax-m2.7`, checkpoint `on-fail`.

### 3. Compact step instructions

```bash
sq run --step-done <run-id>
sq run --prompt-only --next --resume <run-id>
```

**Result**: `compact-2` with `resolved_instructions` containing "slice 152" — `{slice}` placeholder resolved from pipeline params. Template: `minimal`.

### 4. Slash command end-to-end

```
/sq:run slice 152
```

**Result**: Slash command rewritten to consume `sq run --prompt-only` output. Follows JSON-driven loop: init → parse actions → execute → step-done → next → repeat until completion. Not yet end-to-end tested in a live session (requires manual slash command invocation).

### 5. Pipeline state after completion

```bash
sq run --status latest
```

**Result**: Shows completed run with all 6 steps, params `{'slice': '152'}`, status `completed`. State file in `~/.config/squadron/runs/`.

**Caveat**: Model aliases resolve to full model IDs through the alias registry (e.g., `opus` → `claude-opus-4-6`, `glm5` → `z-ai/glm-5`). The exact resolved model IDs depend on the current alias configuration.

## Implementation Notes

### Development Approach

1. Build `prompt_renderer.py` with unit tests — pure function, no I/O
2. Wire `--prompt-only` and `--step-done` into CLI
3. Integration tests: full cycle of init → next → step-done → next → ... → complete
4. Update `/sq:run` slash command to consume prompt-only output
5. End-to-end test: run `/sq:run` against a test slice

### Effort

3/5 — The core rendering logic is straightforward (leverages existing step type expansion and model resolution). The slash command rewrite requires careful prompt engineering to handle JSON parsing and action dispatch correctly.
