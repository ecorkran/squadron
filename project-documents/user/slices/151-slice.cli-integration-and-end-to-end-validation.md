---
docType: slice-design
slice: cli-integration-and-end-to-end-validation
project: squadron
parent: project-documents/user/architecture/140-slices.pipeline-foundation.md
dependencies: [148, 149, 150]
interfaces: [152]
dateCreated: 20260403
dateUpdated: 20260403
status: complete
---

# Slice Design: CLI Integration and End-to-End Validation

## Overview

Wire the pipeline executor, state manager, and pipeline loader into a Typer
`sq run` command surface. This slice is the presentation layer that connects all
pipeline foundation work (slices 142-150) to the user. After this slice,
`sq run slice-lifecycle 191` is a working replacement for the markdown-based
`/sq:run slice` command.

This is the final feature slice in the Pipeline Foundation initiative (140).

---

## Value

- **`sq run` becomes real.** The command surface described in the architecture
  document materializes as a working CLI command.
- **Pipeline discoverability.** `sq run --list` shows available pipelines from
  built-in, user, and project directories. `sq run --validate` catches errors
  before execution.
- **Resume workflow.** `sq run --resume <run-id>` and `sq run --status` give
  users control over long-running and paused pipelines.
- **Replaces `/sq:run slice`.** The markdown slash command is superseded by a
  proper CLI command with state persistence, resume, and structured output.

---

## Technical Scope

### Included

1. **`sq run` Typer command** — Top-level command registered on the main app.
   Accepts a pipeline name or path as the primary argument.

2. **Positional target argument:** `sq run <pipeline> <target>` where `<target>`
   maps to the pipeline's first `required` param. This keeps the CLI natural —
   `sq run slice-lifecycle 191`, `sq run design-batch 140` — because the
   pipeline name already implies what the target means. Pipelines without
   required params (or with multiple required params) can omit the positional
   or use `--param key=value` for additional params.

3. **Runtime options:**
   - `--model <alias>` — CLI-level model override (cascade level 1)
   - `--from <step>` — start at a specific step (mid-process adoption)
   - `--resume <run-id>` — resume a paused or interrupted run
   - `--dry-run` — show execution plan without running
   - `--validate` — validate pipeline definition and exit
   - `--param key=value` — pass additional pipeline params beyond the
     positional target (e.g. `--param template=arch` for review-only)

4. **Informational options:**
   - `--list` — discover and display available pipelines
   - `--status [run-id]` — show status of a specific run or most recent run

5. **Execution flow:**
   - Load pipeline via `load_pipeline()`
   - Optionally validate via `validate_pipeline()`
   - Construct `ModelResolver` with CLI override and pipeline default
   - Construct `ContextForgeClient`
   - Initialize or resume run via `StateManager`
   - Call `execute_pipeline()` with state callback
   - Finalize run state
   - Display results

6. **Implicit resume detection** — When `sq run <pipeline> <target>` matches
   an existing paused run (same pipeline + params), prompt the user: "Found a
   paused run. Resume? [Y/n]". Configurable: prompt (default), auto-resume,
   or fresh-start.

7. **Rich terminal output** — Progress display showing current step, elapsed
   time, and step completion status. Review verdicts displayed with color
   coding (same palette as `sq review`).

8. **Integration tests** — End-to-end tests using mock action registries
   against built-in pipeline definitions, verifying the full path from CLI
   argument parsing through execution and state persistence.

### Excluded

- **New pipeline definitions** — built-in pipelines already exist (slice 148).
- **New actions or step types** — all exist from slices 144-147.
- **Convergence strategies, model pools** — 160 scope.
- **Interactive checkpoint UX beyond basic prompt** — checkpoint action (146)
  handles the interaction; this slice only wires the pause/resume flow.
- **`sq run phase` subcommand** — deferred to future work (see slice plan).

---

## Dependencies

### Prerequisites

- **Slice 148** (Pipeline Definitions and Loader) — `load_pipeline()`,
  `discover_pipelines()`, `validate_pipeline()`, `PipelineInfo`.
- **Slice 149** (Pipeline Executor and Loops) — `execute_pipeline()`,
  `PipelineResult`, `StepResult`, `ExecutionStatus`.
- **Slice 150** (Pipeline State and Resume) — `StateManager`, `RunState`,
  `SchemaVersionError`.

### Interfaces Required

- `load_pipeline(name_or_path, project_dir=, user_dir=) -> PipelineDefinition`
- `discover_pipelines(project_dir=, user_dir=) -> list[PipelineInfo]`
- `validate_pipeline(definition) -> list[ValidationError]`
- `execute_pipeline(definition, params, resolver=, cf_client=, cwd=, run_id=,
  start_from=, on_step_complete=) -> PipelineResult`
- `ModelResolver(cli_override=, pipeline_model=, config_default=)`
- `ContextForgeClient()` (no-arg construction, uses CWD for project resolution)
- `StateManager(runs_dir=)` — default `~/.config/squadron/runs/`
- `StateManager.init_run()`, `.make_step_callback()`, `.finalize()`, `.load()`,
  `.load_prior_outputs()`, `.first_unfinished_step()`, `.list_runs()`,
  `.find_matching_run()`

---

## Architecture

### Component Structure

```
src/squadron/cli/commands/
├── run.py                  # NEW: sq run command implementation
└── ...                     # existing commands

src/squadron/cli/
├── app.py                  # MODIFIED: register run command
└── ...
```

### Command Registration

The `run` command is registered as a top-level command on the main app (not a
subcommand group), matching the architecture's `sq run <pipeline>` surface:

```python
# In app.py
from squadron.cli.commands.run import run
app.command("run")(run)
```

### Data Flow

**Standard execution:**
```
sq run slice-lifecycle 191 --model opus
  │
  ├─ load_pipeline("slice-lifecycle")
  ├─ validate_pipeline(definition)  # optional, always on first run
  ├─ params = {"slice": "191", "model": "opus"}  # "191" mapped to first required param
  ├─ StateManager().find_matching_run("slice-lifecycle", params)
  │   └─ if paused match found → prompt user for resume
  ├─ StateManager().init_run("slice-lifecycle", params)
  ├─ ModelResolver(cli_override="opus", pipeline_model=definition.model)
  ├─ ContextForgeClient()
  ├─ execute_pipeline(
  │     definition, params,
  │     resolver=resolver, cf_client=cf_client,  # resolver is authoritative
  │     run_id=run_id,
  │     on_step_complete=state_mgr.make_step_callback(run_id),
  │   )
  ├─ StateManager().finalize(run_id, result)
  └─ display result summary
```

**Resume flow:**
```
sq run --resume run-20260403-slice-lifecycle-a3f7b21c
  │
  ├─ StateManager().load(run_id)
  ├─ load_pipeline(state.pipeline)
  ├─ StateManager().first_unfinished_step(run_id, definition)
  ├─ StateManager().load_prior_outputs(run_id)
  ├─ ModelResolver(cli_override=model_param, pipeline_model=definition.model)
  ├─ ContextForgeClient()
  ├─ execute_pipeline(
  │     definition, state.params,
  │     resolver=resolver, cf_client=cf_client,
  │     run_id=run_id, start_from=next_step,
  │     on_step_complete=state_mgr.make_step_callback(run_id),
  │   )
  ├─ StateManager().finalize(run_id, result)
  └─ display result summary
```

**Dry-run flow:**
```
sq run slice-lifecycle 191 --dry-run
  │
  ├─ load_pipeline("slice-lifecycle")
  ├─ validate_pipeline(definition)
  ├─ display: pipeline name, description, resolved params
  ├─ for each step: display step name, type, model, actions
  └─ exit (no execution, no state file)
```

### CLI Argument Design

The command uses two positional arguments: the pipeline name and an optional
target. The target maps to the pipeline's first `required` param, letting users
write `sq run slice-lifecycle 191` instead of `sq run slice-lifecycle 191`.

```python
def run(
    pipeline: str | None = typer.Argument(
        None,
        help="Pipeline name or path to YAML definition.",
    ),
    target: str | None = typer.Argument(
        None,
        help="Target for the pipeline's primary required param (e.g. slice index).",
    ),
    model: str | None = typer.Option(
        None, "--model", "-m",
        help="Model alias override (highest cascade priority).",
    ),
    param: list[str] | None = typer.Option(
        None, "--param", "-p",
        help="Additional pipeline param as key=value (repeatable).",
    ),
    from_step: str | None = typer.Option(
        None, "--from",
        help="Start at a specific step (mid-process adoption).",
    ),
    resume: str | None = typer.Option(
        None, "--resume", "-r",
        help="Resume a paused or interrupted run by run-id.",
    ),
    dry_run: bool = typer.Option(
        False, "--dry-run",
        help="Show execution plan without running.",
    ),
    validate_only: bool = typer.Option(
        False, "--validate",
        help="Validate pipeline definition and exit.",
    ),
    list_pipelines: bool = typer.Option(
        False, "--list", "-l",
        help="List available pipelines.",
    ),
    status: str | None = typer.Option(
        None, "--status",
        help="Show run status. Pass 'latest' or omit value for most recent.",
    ),
) -> None:
```

### Positional Target Resolution

The `target` positional argument is mapped to the pipeline's first `required`
param by inspecting `definition.params`:

```python
def _resolve_target(
    definition: PipelineDefinition,
    target: str | None,
) -> tuple[str, str] | None:
    """Find the first required param name and bind target to it.

    Returns (param_name, target_value) or None if no required param exists.
    """
    for name, default in definition.params.items():
        if default == "required":
            if target is None:
                raise typer.BadParameter(
                    f"Pipeline '{definition.name}' requires a '{name}' argument."
                )
            return (name, target)
    return None  # no required param — target is ignored
```

This means:
- `sq run slice-lifecycle 191` → `params["slice"] = "191"` (first required = `slice`)
- `sq run design-batch 140` → `params["plan"] = "140"` (first required = `plan`)
- `sq run review-only 191 --param template=arch` → `params["slice"] = "191"`,
  `params["template"] = "arch"`

Pipelines with multiple required params use `--param` for all beyond the first.
`--model` remains a dedicated flag because it serves a dual purpose (cascade
override + state recording).

### Mutual Exclusivity

Several options are mutually exclusive. The command validates at entry:

- `--list` is standalone (ignores pipeline argument and all other options)
- `--status` is standalone (ignores pipeline argument)
- `--resume` requires no pipeline argument (loads from state file)
- `--validate` and `--dry-run` skip execution
- `--from` and `--resume` are mutually exclusive (resume derives start_from
  from state; `--from` is for fresh runs)

Invalid combinations produce a clear error message and exit.

### `--status` Optional Value Handling

Typer string options require a value when the flag is present, so
`sq run --status` (no value) would raise a parse error. To support the
"most recent run" shorthand, `--status` accepts an explicit `"latest"`
sentinel value. The user invokes either:

- `sq run --status latest` — show most recent run
- `sq run --status <run-id>` — show a specific run

The implementation checks for `"latest"` and calls
`StateManager.list_runs()[0]` to resolve the most recent run. This avoids
Click-level `nargs` customization while keeping the UX clean. A future
enhancement could add a `--recent` boolean flag as a pure shorthand.

### Parameter Assembly

The `params` dict passed to `execute_pipeline` is assembled from three sources:

1. **Positional target** → bound to first required param name via `_resolve_target`
2. **`--param key=value`** → parsed and merged (additional required/optional params)
3. **`--model`** → added as `params["model"]` for state-file recording

```python
params: dict[str, object] = {}
# 1. Positional target
binding = _resolve_target(definition, target)
if binding is not None:
    params[binding[0]] = binding[1]
# 2. --param key=value entries
if param:
    for entry in param:
        key, _, value = entry.partition("=")
        params[key] = value
# 3. Model for state recording
if model is not None:
    params["model"] = model
```

The pipeline definition's `params` section declares required and default
parameters. The executor merges CLI params over definition defaults. Missing
required params raise an error before execution begins.

**Model in `params` vs `ModelResolver`:** The `model` value appears in two
places — `ModelResolver(cli_override=model)` and `params["model"]`. These
serve different purposes. The `ModelResolver` is authoritative for dispatch
(cascade level 1). The `params["model"]` entry is recorded in the state file
for resume fidelity — when resuming, the CLI reconstructs `ModelResolver`
from `state.params["model"]` so the same override applies. The executor does
not read `params["model"]` for model resolution; it uses the resolver
exclusively. Pipeline definitions that declare `model` as a param default
(e.g. `params: { model: opus }`) populate cascade level 4 via
`ModelResolver(pipeline_model=definition.model)`, not via `params`.

---

## Technical Decisions

### Sync Wrapper for Async Executor

The pipeline executor is async (`execute_pipeline` is an `async def`). Typer
commands are synchronous. The run command uses `asyncio.run()` to bridge, same
pattern as `sq review`:

```python
def run(...) -> None:
    # ... validation and setup ...
    result = asyncio.run(_run_pipeline(...))
    # ... display results ...
```

The async helper `_run_pipeline()` contains the actual orchestration logic.

### Rich Output

Use Rich for terminal output, consistent with `sq review`. Key displays:

- **Pipeline list** (`--list`): Table with name, description, source columns.
- **Validation results** (`--validate`): Error list with field and message.
- **Dry-run** (`--dry-run`): Step sequence with types and resolved models.
- **Execution progress**: Step-by-step status updates as steps complete.
- **Run status** (`--status`): Panel showing run metadata, completed steps,
  and checkpoint info if paused.
- **Final summary**: Status, step count, elapsed time, review verdicts.

### Error Handling

- **Pipeline not found:** Clear message listing searched directories.
- **Validation errors:** Display all errors, exit with code 1.
- **ContextForge not available:** Message directing user to install CF.
- **Schema version mismatch:** Message explaining the state file is from a
  newer version and suggesting upgrade.
- **Execution failures:** Display the failing step and error, finalize state
  as `failed`, exit with code 1.
- **Keyboard interrupt:** Finalize state as `failed` with error="interrupted",
  display resume instructions.

### ContextForge Client Construction

`ContextForgeClient()` is constructed with no arguments. It resolves the
project from CWD. If CF is not available, the command exits with a clear error
before attempting execution.

A pre-flight check calls `cf_client.get_project()` (or equivalent) to verify
CF is operational before initializing the run state. This avoids creating
orphan state files for runs that can never execute.

---

## Integration Points

### Provides to Slice 152 (Documentation)

- Working `sq run` command with all documented options
- Example invocations and expected output for documentation

### Consumes from Prior Slices

| Component | Source | Import Path |
|-----------|--------|-------------|
| `load_pipeline` | 148 | `squadron.pipeline.loader` |
| `discover_pipelines` | 148 | `squadron.pipeline.loader` |
| `validate_pipeline` | 148 | `squadron.pipeline.loader` |
| `PipelineInfo` | 148 | `squadron.pipeline.loader` |
| `execute_pipeline` | 149 | `squadron.pipeline.executor` |
| `PipelineResult` | 149 | `squadron.pipeline.executor` |
| `StepResult` | 149 | `squadron.pipeline.executor` |
| `ExecutionStatus` | 149 | `squadron.pipeline.executor` |
| `StateManager` | 150 | `squadron.pipeline.state` |
| `RunState` | 150 | `squadron.pipeline.state` |
| `SchemaVersionError` | 150 | `squadron.pipeline.state` |
| `ModelResolver` | 142 | `squadron.pipeline.resolver` |
| `ContextForgeClient` | 126 | `squadron.integrations.context_forge` |
| `get_config` | 100-band | `squadron.config.manager` |

---

## Success Criteria

### Functional Requirements

1. `sq run slice-lifecycle 191` loads the pipeline, creates a run,
   executes all steps, finalizes state, and displays a summary.
2. `sq run --list` displays all available pipelines (built-in, user, project)
   in a formatted table.
3. `sq run --validate slice-lifecycle` checks the pipeline definition and
   reports any errors without executing.
4. `sq run --dry-run slice-lifecycle --slice 191` displays the execution plan
   (steps, types, models) without creating a run or executing.
5. `sq run --resume <run-id>` loads an existing paused run, resolves the next
   step, reconstructs prior outputs, and resumes execution.
6. `sq run --status <run-id>` displays run metadata, completed steps, and
   checkpoint info.
7. `sq run --status latest` displays the most recent run's status.
8. `sq run slice-lifecycle 191` when a paused run exists for the same
   pipeline+params prompts the user to resume or start fresh.
9. `sq run slice-lifecycle 191 --from implement` starts execution at
   the `implement` step, skipping earlier steps.
10. `sq run slice-lifecycle 191 --model opus` applies the model
    override as cascade level 1.
11. Keyboard interrupt during execution finalizes the run as failed and
    displays resume instructions.
12. Missing or invalid pipeline name produces a clear error with search paths.

### Technical Requirements

- Command module at `src/squadron/cli/commands/run.py`.
- Registered on the main app in `app.py`.
- All functions type-annotated; pyright strict, zero errors.
- `ruff` clean.
- Rich output for all display modes (list, validate, dry-run, status, results).
- Test coverage: unit tests for argument validation, parameter assembly,
  mutual exclusivity checks. Integration tests using mock action registries.

### Integration Requirements

- Full pipeline execution with `StateManager` persistence produces a valid
  state file that can be loaded and resumed.
- `sq run --list` discovers built-in pipelines from `src/squadron/data/pipelines/`.
- `sq run --validate` calls `validate_pipeline()` and reports all errors.

---

## Verification Walkthrough

Verified during Phase 6 implementation (2026-04-03).

**1. List available pipelines:**

```bash
$ sq run --list
# Output: Rich table showing slice-lifecycle, review-only,
# implementation-only, design-batch — all built-in source.
```

**2. Validate a pipeline:**

```bash
$ sq run --validate slice-lifecycle
# Output: Pipeline 'slice-lifecycle' is valid.
```

**3. Dry-run a pipeline:**

```bash
$ sq run --dry-run slice-lifecycle 191
# Output:
#   Pipeline: slice-lifecycle
#   Description: Full slice lifecycle — design through implementation
#   Params: {'slice': '191'}
#   Steps:
#     design-0 (design)
#     tasks-1 (tasks)
#     compact-2 (compact)
#     implement-3 (implement)
#     devlog-4 (devlog)
```

**Caveat:** Step names include auto-generated index suffixes (e.g. `design-0`,
`implement-3`). The `--from` flag must use these full names.

**4. Execute a pipeline (integration test with mocks):**

```python
# In pytest — tests/pipeline/test_cli_integration.py
result = await _run_pipeline(
    "slice-lifecycle", {"slice": "191"},
    runs_dir=tmp_path,
    _action_registry=success_registry,
)
assert result.status == ExecutionStatus.COMPLETED
# State file exists with 5 completed steps
```

**5. Resume a paused run (integration test):**

```python
# First run pauses (checkpoint action returns pause signal)
result1 = await _run_pipeline(...)  # status=PAUSED
# Resume via executor with start_from
result2 = await execute_pipeline(..., start_from=next_step)
# Final state: completed, 5 steps
```

**6. Check run status:**

```bash
$ sq run --status latest
# Output: Rich panel with run_id, pipeline, params, status, timestamps,
# step count, and checkpoint info if paused.
```

**7. Mutual exclusivity enforcement:**

```bash
$ sq run --resume run-abc --from implement
# Error: --resume and --from cannot be used together.

$ sq run --list --validate slice-lifecycle
# Error: --list cannot be combined with other options.
```

All 43 unit and integration tests pass (`tests/cli/commands/test_run.py`,
`tests/pipeline/test_cli_integration.py`).

---

## Implementation Notes

### Development Approach

1. Create `src/squadron/cli/commands/run.py` with the Typer command function
   and argument definitions.
2. Implement `--list` (simplest path — no execution, just discovery).
3. Implement `--validate` (loads pipeline, runs validator, displays results).
4. Implement `--dry-run` (loads pipeline, resolves params, displays plan).
5. Implement `--status` (loads state file, displays formatted info).
6. Implement core execution flow (load → init_run → execute → finalize →
   display).
7. Implement `--resume` flow (load state → derive start_from → execute).
8. Implement implicit resume detection (find_matching_run → prompt).
9. Implement `--from` (mid-process adoption).
10. Implement keyboard interrupt handling.
11. Register command in `app.py`.
12. Write unit tests for argument validation and parameter assembly.
13. Write integration tests with mock action registries for full execution paths.

### Testing Strategy

**Unit tests** (`tests/cli/test_run.py` or `tests/cli/commands/test_run.py`):
- Argument mutual exclusivity validation
- Parameter assembly from CLI options
- Dry-run output formatting
- Status display formatting
- Error message generation (pipeline not found, validation errors)

**Integration tests** (`tests/pipeline/test_cli_integration.py`):
- Full execution with mock action registry → state file reflects all steps
- Resume from paused state → completes successfully
- Implicit resume detection with matching paused run
- `--from` mid-process adoption
- Keyboard interrupt → state finalized as failed

Integration tests use `StateManager(runs_dir=tmp_path)` and mock action
registries (same pattern as `tests/pipeline/test_state_integration.py`).
They do NOT invoke the Typer CLI runner — they call the async helper directly,
keeping tests fast and avoiding Typer's process model.

**Scope note on "real CF project structure":** The slice plan mentions
"integration testing of built-in pipelines against a real CF project
structure." This slice interprets that as testing the full wiring path
(CLI args → loader → executor → state manager) with mock action registries
substituted at the action boundary. Tests validate that built-in pipeline
definitions load correctly and that the executor processes their step
sequences end-to-end. Actual CF subprocess calls are not exercised in
automated tests — CF availability is environment-dependent and would make
tests flaky. The pre-flight CF check is tested in isolation (mock subprocess).
Manual verification against a real CF project is covered in the Verification
Walkthrough.

### Special Considerations

- **ContextForge availability:** Pre-flight check before creating state. If CF
  is not available, exit cleanly without orphan state files.
- **`--status` without run-id:** Uses `StateManager.list_runs()` sorted by
  `started_at` descending, takes the first result.
- **Implicit resume prompt:** Uses `typer.confirm()` for the "Resume? [Y/n]"
  prompt. In non-interactive environments (piped stdin), defaults to
  fresh-start to avoid hanging.
