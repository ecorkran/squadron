---
docType: tasks
slice: cli-integration-and-end-to-end-validation
project: squadron
parent: project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md
dependencies: [148, 149, 150]
dateCreated: 20260403
dateUpdated: 20260403
status: not_started
---

# Tasks: CLI Integration and End-to-End Validation (Slice 151)

## Context Summary

Wire the pipeline executor, state manager, and pipeline loader into a working
`sq run` Typer command. This is the presentation layer — no new actions, step
types, or pipelines are created. All underlying machinery (slices 142-150) is
complete.

**New file:** `src/squadron/cli/commands/run.py`  
**Modified file:** `src/squadron/cli/app.py` (register command)  
**Test files:** `tests/cli/commands/test_run.py`, `tests/pipeline/test_cli_integration.py`

Key patterns:
- Sync Typer function → `asyncio.run()` → async `_run_pipeline()` helper
- `StateManager(runs_dir=tmp_path)` in all tests — never touches real `~/.config`
- `_action_registry=...` injected into `execute_pipeline` for integration tests
- `--status latest` sentinel for most-recent-run shorthand

---

## Tasks

### T1: Create command file skeleton

- [ ] Create `src/squadron/cli/commands/run.py` with:
  - Module docstring
  - `from __future__ import annotations`
  - All required imports (asyncio, Path, typer, rich components, pipeline layer)
  - Empty `run()` Typer function with all option/argument declarations
  - Empty async `_run_pipeline()` helper stub
- [ ] Verify file is importable: `python -c "from squadron.cli.commands.run import run"`

### T2: Register command in app.py

- [ ] In `src/squadron/cli/app.py`, add:
  ```python
  from squadron.cli.commands.run import run
  app.command("run")(run)
  ```
- [ ] Verify `sq run --help` shows the command (run `uv run sq run --help`)

### T3: Define Typer argument and option signatures

- [ ] Define all parameters in `run()`:
  - `pipeline: str | None = typer.Argument(None, help="Pipeline name or path.")`
  - `slice_param: str | None = typer.Option(None, "--slice", "-s")`
  - `model: str | None = typer.Option(None, "--model", "-m")`
  - `from_step: str | None = typer.Option(None, "--from")`
  - `resume: str | None = typer.Option(None, "--resume", "-r")`
  - `dry_run: bool = typer.Option(False, "--dry-run")`
  - `validate_only: bool = typer.Option(False, "--validate")`
  - `list_pipelines: bool = typer.Option(False, "--list", "-l")`
  - `status: str | None = typer.Option(None, "--status")`
- [ ] Add return type annotation `-> None`
- [ ] Verify `sq run --help` lists all options with descriptions

### T4: Implement mutual exclusivity validation

- [ ] At the top of `run()`, validate option combinations and call
  `raise typer.BadParameter(...)` or `typer.echo(...); raise typer.Exit(1)` for:
  - `--resume` + `--from` together
  - `--list` + any other meaningful option (pipeline, slice, model, etc.)
  - `--status` + pipeline argument or execution options
  - Missing pipeline argument when not using `--list`, `--status`, or `--resume`
- [ ] Write unit tests in `tests/cli/commands/test_run.py`:
  - [ ] Test `--resume` + `--from` exits with error
  - [ ] Test `--list` with pipeline arg exits with error
  - [ ] Test missing pipeline arg (no --list/--status/--resume) exits with error
  - [ ] Test valid combinations do not error at validation stage

**Commit:** `feat: add sq run command skeleton with argument definitions`

### T5: Implement `--list`

- [ ] In `run()`, when `list_pipelines` is True:
  - Call `discover_pipelines()`
  - Build Rich `Table` with columns: Name, Description, Source
  - Print table and `raise typer.Exit(0)`
- [ ] Write unit tests:
  - [ ] Mock `discover_pipelines` returning 2 `PipelineInfo` objects
  - [ ] Assert table output contains pipeline names and sources
  - [ ] Assert exits with code 0

### T6: Implement `--validate`

- [ ] When `validate_only` is True (and pipeline arg is present):
  - Call `load_pipeline(pipeline)`; handle `FileNotFoundError` → print error, exit 1
  - Call `validate_pipeline(definition)`
  - If no errors: print success message, exit 0
  - If errors: print each error's field and message, exit 1
- [ ] Write unit tests:
  - [ ] Mock `load_pipeline` + `validate_pipeline` returning empty list → exit 0
  - [ ] Mock `validate_pipeline` returning 2 errors → exit 1, both errors printed
  - [ ] Mock `load_pipeline` raising `FileNotFoundError` → exit 1

### T7: Implement `--status`

- [ ] When `status` is not None:
  - If `status == "latest"`: call `StateManager().list_runs()`, take first result;
    if empty, print "No runs found." and exit 0
  - Else: call `StateManager().load(status)`; handle `FileNotFoundError` and
    `SchemaVersionError` with clear messages, exit 1
  - Display Rich Panel with: run_id, pipeline, params, status, started_at,
    updated_at, completed step count, checkpoint info (if paused)
  - Exit 0
- [ ] Write unit tests:
  - [ ] `--status latest` with mocked `list_runs` returning one run → panel shown
  - [ ] `--status latest` with empty list → "No runs found." message
  - [ ] `--status <run-id>` with valid state → panel shown
  - [ ] `--status <run-id>` with `FileNotFoundError` → error, exit 1

**Commit:** `feat: implement sq run --list, --validate, --status`

### T8: Implement `--dry-run`

- [ ] When `dry_run` is True (and pipeline arg present):
  - Call `load_pipeline(pipeline)` + `validate_pipeline()`
  - Assemble `params` dict from `slice_param` and `model`
  - Print pipeline name, description, and resolved params
  - Print each step: name, type, config model (if any)
  - Do NOT create any state file
  - Exit 0
- [ ] Write unit tests:
  - [ ] Dry-run output contains pipeline name and step names
  - [ ] No state file created in `tmp_path`

### T9: Implement parameter assembly helper

- [ ] Extract `_assemble_params(slice_param, model) -> dict[str, object]` function:
  - Adds `"slice"` key if `slice_param` is not None
  - Adds `"model"` key if `model` is not None (for state-file recording)
- [ ] Write unit tests:
  - [ ] `slice_param="191", model="opus"` → `{"slice": "191", "model": "opus"}`
  - [ ] `slice_param=None, model=None` → `{}`
  - [ ] `slice_param="191", model=None` → `{"slice": "191"}`

### T10: Implement CF pre-flight check helper

- [ ] Extract `_check_cf(cf_client: ContextForgeClient) -> None` function:
  - Calls `cf_client.get_project()` (or `list_slices()` as availability probe)
  - On `ContextForgeNotAvailable`: prints error message, raises `typer.Exit(1)`
  - On `ContextForgeError`: prints error with detail, raises `typer.Exit(1)`
- [ ] Write unit tests:
  - [ ] CF available → no exception raised
  - [ ] `ContextForgeNotAvailable` → exits 1 with install message
  - [ ] `ContextForgeError` → exits 1 with error detail

### T11: Implement core execution flow

- [ ] Implement the async `_run_pipeline()` helper with signature:
  ```python
  async def _run_pipeline(
      pipeline_name: str,
      params: dict[str, object],
      model_override: str | None = None,
      runs_dir: Path | None = None,
      from_step: str | None = None,
      _action_registry: dict[str, object] | None = None,
  ) -> PipelineResult:
  ```
- [ ] Implementation:
  - Load definition via `load_pipeline(pipeline_name)`
  - Construct `ModelResolver(cli_override=model_override, pipeline_model=definition.model)`
  - Construct `ContextForgeClient()`; call `_check_cf(cf_client)`
  - Construct `StateManager(runs_dir=runs_dir)`
  - Call `state_mgr.init_run(pipeline_name, params)` to get `run_id`
  - Call `execute_pipeline(definition, params, resolver=..., cf_client=...,
      run_id=run_id, start_from=from_step,
      on_step_complete=state_mgr.make_step_callback(run_id),
      _action_registry=_action_registry)`
  - Call `state_mgr.finalize(run_id, result)` in a `finally` block
  - Return `result`
- [ ] In the sync `run()` function, call:
  ```python
  result = asyncio.run(_run_pipeline(...))
  ```
- [ ] Display final summary: status (with color), step count, verdicts

**Commit:** `feat: implement sq run core execution flow`

### T12: Implement `--resume` flow

- [ ] When `resume` is provided:
  - Call `StateManager().load(resume)`; handle errors → exit 1
  - Call `load_pipeline(state.pipeline)`
  - Call `state_mgr.first_unfinished_step(run_id, definition)`
  - Call `state_mgr.load_prior_outputs(run_id)`
  - Construct `ModelResolver` using `state.params.get("model")` as pipeline default
    (CLI `--model` still overrides as level 1 if provided)
  - Call `execute_pipeline` with `start_from=next_step`, `run_id=resume`,
    same state callback
  - Finalize and display summary
- [ ] Write unit tests:
  - [ ] `--resume` with valid paused state → calls `first_unfinished_step`
  - [ ] `--resume` with missing run-id → exit 1 with FileNotFoundError message
  - [ ] `--resume` + `--from` → exits 1 (mutual exclusivity — already in T4)

### T13: Implement implicit resume detection

- [ ] After loading the pipeline and assembling params (standard execution path),
  before calling `init_run`:
  - Call `state_mgr.find_matching_run(pipeline_name, params, status="paused")`
  - If match found: call `typer.confirm("Found a paused run. Resume?", default=True)`
    - If confirmed: redirect to resume flow (reuse `_run_pipeline` resume path)
    - If declined: proceed with fresh `init_run`
  - If stdin is not a TTY: skip prompt, proceed with fresh run
- [ ] Write unit tests:
  - [ ] Matching paused run found + user confirms → resume executed
  - [ ] Matching paused run found + user declines → fresh run executed
  - [ ] No matching run → proceeds to fresh run without prompt

### T14: Implement `--from` (mid-process adoption)

- [ ] When `from_step` is provided (without `--resume`):
  - Load pipeline, assemble params
  - Call `_run_pipeline(..., from_step=from_step)` (passes through as `start_from`)
  - State file created normally via `init_run`
- [ ] Write unit tests:
  - [ ] `--from implement` → `execute_pipeline` called with `start_from="implement"`
  - [ ] `--from` + `--resume` → mutual exclusivity error (already in T4)

### T15: Implement keyboard interrupt handling

- [ ] Wrap the `asyncio.run(_run_pipeline(...))` call in `run()` with:
  ```python
  try:
      result = asyncio.run(_run_pipeline(...))
  except KeyboardInterrupt:
      typer.echo("\nInterrupted. Run state saved as failed.")
      typer.echo(f"Resume with: sq run --resume {run_id}")
      raise typer.Exit(1)
  ```
- [ ] Note: `_run_pipeline` finalizes with `failed` status in its `finally` block;
  the CLI layer adds the resume instructions
- [ ] Write unit tests:
  - [ ] Simulate `KeyboardInterrupt` → resume instructions printed, exit 1

**Commit:** `feat: implement sq run --resume, --from, implicit resume, interrupt handling`

### T16: Integration test — full execution

- [ ] In `tests/pipeline/test_cli_integration.py`, create `TestCliIntegration` class
- [ ] Test: `_run_pipeline("slice-lifecycle", {"slice": "191"}, ...)` with success
  registry:
  - Returns `PipelineResult` with `status=COMPLETED`
  - State file in `tmp_path` has `status="completed"` and 5 completed steps
- [ ] Test: state file exists after run and is loadable via `StateManager.load()`

### T17: Integration test — resume from paused

- [ ] Test: first `_run_pipeline` call pauses (using `_paused_checkpoint_registry`):
  - Returns `status=PAUSED`
  - State file `status="paused"`
- [ ] Second `_run_pipeline` call with `resume_id`:
  - Returns `status=COMPLETED`
  - Final state file has all 5 steps

### T18: Integration test — `--from` mid-process adoption

- [ ] Test: `_run_pipeline("slice-lifecycle", {"slice": "191"}, from_step="implement-3",
  _action_registry=success_registry)`:
  - Only steps from `implement-3` onward appear in completed_steps
  - Status is `COMPLETED`

### T19: Integration test — dry-run produces no state file

- [ ] Test: invoke dry-run path (mock `load_pipeline` + `validate_pipeline`):
  - Assert no `*.json` file created in `tmp_path`

**Commit:** `test: add CLI integration tests for sq run`

### T20: Exports, type annotations, and lint

- [ ] Ensure `run.py` exports only `run` (other names are internal `_` prefixed)
- [ ] Run `pyright` on `src/squadron/cli/commands/run.py`; fix all errors
- [ ] Run `ruff check src/squadron/cli/commands/run.py`; fix all issues
- [ ] Run `ruff format src/squadron/cli/commands/run.py`
- [ ] Run full test suite: `uv run pytest tests/cli/ tests/pipeline/test_cli_integration.py -v`
- [ ] Confirm zero failures

### T21: Verification and closeout

- [ ] Manual smoke test: `sq run --help` shows all options
- [ ] Manual smoke test: `sq run --list` shows built-in pipelines
- [ ] Manual smoke test: `sq run --validate slice-lifecycle` passes validation
- [ ] Manual smoke test: `sq run --dry-run slice-lifecycle --slice 191` shows plan
- [ ] Update `dateUpdated` in `151-slice.cli-integration-and-end-to-end-validation.md`
  and set `status: complete`
- [ ] Mark slice 151 `[x]` in `140-slices.pipeline-foundation.md`
- [ ] Update `CHANGELOG.md` with slice 151 entry
- [ ] Update `DEVLOG.md` with Phase 6 completion entry

**Commit:** `feat: complete slice 151 — sq run CLI integration`
