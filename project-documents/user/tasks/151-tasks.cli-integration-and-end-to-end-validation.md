---
docType: tasks
slice: cli-integration-and-end-to-end-validation
project: squadron
parent: project-documents/user/slices/151-slice.cli-integration-and-end-to-end-validation.md
dependencies: [148, 149, 150]
dateCreated: 20260403
dateUpdated: 20260403
status: complete
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
- `sq run <pipeline> <target>` — positional target maps to first required param
- Sync Typer function → `asyncio.run()` → async `_run_pipeline()` helper
- `StateManager(runs_dir=tmp_path)` in all tests — never touches real `~/.config`
- `_action_registry=...` injected into `execute_pipeline` for integration tests
- `--status latest` sentinel for most-recent-run shorthand

---

## Tasks

### T1: Create command file skeleton

- [x] Create `src/squadron/cli/commands/run.py` with:
  - Module docstring
  - `from __future__ import annotations`
  - All required imports (asyncio, Path, typer, rich components, pipeline layer)
  - Empty `run()` Typer function with all option/argument declarations
  - Empty async `_run_pipeline()` helper stub
- [x] Verify file is importable: `python -c "from squadron.cli.commands.run import run"`

### T2: Register command in app.py

- [x] In `src/squadron/cli/app.py`, add:
  ```python
  from squadron.cli.commands.run import run
  app.command("run")(run)
  ```
- [x] Verify `sq run --help` shows the command (run `uv run sq run --help`)

### T3: Define Typer argument and option signatures

- [x] Define all parameters in `run()`:
  - `pipeline: str | None = typer.Argument(None, help="Pipeline name or path.")`
  - `target: str | None = typer.Argument(None, help="Target for pipeline's primary required param.")`
  - `model: str | None = typer.Option(None, "--model", "-m")`
  - `param: list[str] | None = typer.Option(None, "--param", "-p", help="Additional param as key=value.")`
  - `from_step: str | None = typer.Option(None, "--from")`
  - `resume: str | None = typer.Option(None, "--resume", "-r")`
  - `dry_run: bool = typer.Option(False, "--dry-run")`
  - `validate_only: bool = typer.Option(False, "--validate")`
  - `list_pipelines: bool = typer.Option(False, "--list", "-l")`
  - `status: str | None = typer.Option(None, "--status")`
- [x] Add return type annotation `-> None`
- [x] Verify `sq run --help` lists all options with descriptions

### T4: Implement mutual exclusivity validation

- [x] At the top of `run()`, validate option combinations and call
  `raise typer.BadParameter(...)` or `typer.echo(...); raise typer.Exit(1)` for:
  - `--resume` + `--from` together
  - `--list` + any other meaningful option (pipeline, slice, model, etc.)
  - `--status` + pipeline argument or execution options
  - Missing pipeline argument when not using `--list`, `--status`, or `--resume`
- [x] Write unit tests in `tests/cli/commands/test_run.py`:
  - [x] Test `--resume` + `--from` exits with error
  - [x] Test `--list` with pipeline arg exits with error
  - [x] Test missing pipeline arg (no --list/--status/--resume) exits with error
  - [x] Test valid combinations do not error at validation stage

**Commit:** `feat: add sq run command skeleton with argument definitions`

### T5: Implement `--list`

- [x] In `run()`, when `list_pipelines` is True:
  - Call `discover_pipelines()`
  - Build Rich `Table` with columns: Name, Description, Source
  - Print table and `raise typer.Exit(0)`
- [x] Write unit tests:
  - [x] Mock `discover_pipelines` returning 2 `PipelineInfo` objects
  - [x] Assert table output contains pipeline names and sources
  - [x] Assert exits with code 0

### T6: Implement `--validate`

- [x] When `validate_only` is True (and pipeline arg is present):
  - Call `load_pipeline(pipeline)`; handle `FileNotFoundError` → print error, exit 1
  - Call `validate_pipeline(definition)`
  - If no errors: print success message, exit 0
  - If errors: print each error's field and message, exit 1
- [x] Write unit tests:
  - [x] Mock `load_pipeline` + `validate_pipeline` returning empty list → exit 0
  - [x] Mock `validate_pipeline` returning 2 errors → exit 1, both errors printed
  - [x] Mock `load_pipeline` raising `FileNotFoundError` → exit 1

### T7: Implement `--status`

- [x] When `status` is not None:
  - If `status == "latest"`: call `StateManager().list_runs()`, take first result;
    if empty, print "No runs found." and exit 0
  - Else: call `StateManager().load(status)`; handle `FileNotFoundError` and
    `SchemaVersionError` with clear messages, exit 1
  - Display Rich Panel with: run_id, pipeline, params, status, started_at,
    updated_at, completed step count, checkpoint info (if paused)
  - Exit 0
- [x] Write unit tests:
  - [x] `--status latest` with mocked `list_runs` returning one run → panel shown
  - [x] `--status latest` with empty list → "No runs found." message
  - [x] `--status <run-id>` with valid state → panel shown
  - [x] `--status <run-id>` with `FileNotFoundError` → error, exit 1

**Commit:** `feat: implement sq run --list, --validate, --status`

### T8: Implement target resolution and parameter assembly

- [x] Implement `_resolve_target(definition, target) -> tuple[str, str] | None`:
  - Iterate `definition.params`; find first param where value is `"required"`
  - If found and `target` is not None: return `(param_name, target)`
  - If found and `target` is None: raise `typer.BadParameter` with message
    naming the missing param
  - If no required param found: return `None`
- [x] Implement `_assemble_params(definition, target, model, param_list) -> dict[str, object]`:
  - Call `_resolve_target` to bind positional target to first required param
  - Parse `--param key=value` entries from `param_list`
  - Add `model` to params if not None (for state-file recording)
  - Return assembled dict
- [x] Write unit tests:
  - [x] `_resolve_target` with `slice: required` and target `"191"` → `("slice", "191")`
  - [x] `_resolve_target` with `plan: required` and target `"140"` → `("plan", "140")`
  - [x] `_resolve_target` with required param and `target=None` → `BadParameter`
  - [x] `_resolve_target` with no required params → `None`
  - [x] `_assemble_params` with target + model + `--param template=arch` → correct dict
  - [x] `_assemble_params` with no target, no model → `{}`

### T9: Implement `--dry-run`

- [x] When `dry_run` is True (and pipeline arg present):
  - Call `load_pipeline(pipeline)`; handle `FileNotFoundError` → print error with
    searched directories, exit 1
  - Call `validate_pipeline(definition)`
  - Call `_assemble_params(definition, target, model, param)` for resolved params
  - Print pipeline name, description, and resolved params
  - Print each step: name, type, config model (if any)
  - Do NOT create any state file
  - Exit 0
- [x] Write unit tests:
  - [x] Dry-run output contains pipeline name and step names
  - [x] No state file created in `tmp_path`

### T10: Implement CF pre-flight check helper

- [x] Extract `_check_cf(cf_client: ContextForgeClient) -> None` function:
  - Calls `cf_client.get_project()` (or `list_slices()` as availability probe)
  - On `ContextForgeNotAvailable`: prints error message, raises `typer.Exit(1)`
  - On `ContextForgeError`: prints error with detail, raises `typer.Exit(1)`
- [x] Write unit tests:
  - [x] CF available → no exception raised
  - [x] `ContextForgeNotAvailable` → exits 1 with install message
  - [x] `ContextForgeError` → exits 1 with error detail

### T11: Implement core execution flow

- [x] Implement the async `_run_pipeline()` helper with signature:
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
- [x] Implementation:
  - Load definition via `load_pipeline(pipeline_name)`; on `FileNotFoundError`,
    print a clear message that includes the searched directories and re-raise so
    the sync `run()` caller can exit 1 (covers SC12)
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
- [x] In the sync `run()` function, call `asyncio.run(_run_pipeline(...))`;
  catch `FileNotFoundError` → print message, `raise typer.Exit(1)`
- [x] Display final summary: status (with color), step count, verdicts
- [x] Write unit tests for `_run_pipeline`:
  - [x] `FileNotFoundError` from `load_pipeline` propagates and triggers exit 1
  - [x] Successful call returns `PipelineResult` and finalizes state

### T12: Integration test — full execution

- [x] In `tests/pipeline/test_cli_integration.py`, create `TestCliIntegration` class
- [x] Test: `_run_pipeline("slice-lifecycle", {"slice": "191"}, ...)` with success
  registry:
  - Returns `PipelineResult` with `status=COMPLETED`
  - State file in `tmp_path` has `status="completed"` and 5 completed steps
- [x] Test: state file exists after run and is loadable via `StateManager.load()`

### T13: Integration test — resume from paused

- [x] Test: first `_run_pipeline` call pauses (using `_paused_checkpoint_registry`):
  - Returns `status=PAUSED`
  - State file `status="paused"`
- [x] Second `_run_pipeline` call with `resume_id`:
  - Returns `status=COMPLETED`
  - Final state file has all 5 steps

**Commit:** `feat: implement sq run core execution flow`

### T14: Implement `--resume` flow

- [x] When `resume` is provided:
  - Call `StateManager().load(resume)`; handle errors → exit 1
  - Call `load_pipeline(state.pipeline)`
  - Call `state_mgr.first_unfinished_step(run_id, definition)`
  - Call `state_mgr.load_prior_outputs(run_id)`
  - Construct `ModelResolver` using `state.params.get("model")` as pipeline default
    (CLI `--model` still overrides as level 1 if provided)
  - Call `execute_pipeline` with `start_from=next_step`, `run_id=resume`,
    same state callback
  - Finalize and display summary
- [x] Write unit tests:
  - [x] `--resume` with valid paused state → calls `first_unfinished_step`
  - [x] `--resume` with missing run-id → exit 1 with FileNotFoundError message
  - [x] `--resume` + `--from` → exits 1 (mutual exclusivity — already in T4)

### T15: Implement implicit resume detection

- [x] After loading the pipeline and assembling params (standard execution path),
  before calling `init_run`:
  - Call `state_mgr.find_matching_run(pipeline_name, params, status="paused")`
  - If match found: call `typer.confirm("Found a paused run. Resume?", default=True)`
    - If confirmed: redirect to resume flow (reuse `_run_pipeline` resume path)
    - If declined: proceed with fresh `init_run`
  - If stdin is not a TTY: skip prompt, proceed with fresh run
- [x] Write unit tests:
  - [x] Matching paused run found + user confirms → resume executed
  - [x] Matching paused run found + user declines → fresh run executed
  - [x] No matching run → proceeds to fresh run without prompt

### T16: Implement `--from` (mid-process adoption)

- [x] When `from_step` is provided (without `--resume`):
  - Load pipeline, assemble params
  - Call `_run_pipeline(..., from_step=from_step)` (passes through as `start_from`)
  - State file created normally via `init_run`
- [x] Write unit tests:
  - [x] `--from implement` → `execute_pipeline` called with `start_from="implement"`
  - [x] `--from` + `--resume` → mutual exclusivity error (already in T4)

### T17: Implement keyboard interrupt handling

- [x] Wrap the `asyncio.run(_run_pipeline(...))` call in `run()` with:
  ```python
  try:
      result = asyncio.run(_run_pipeline(...))
  except KeyboardInterrupt:
      typer.echo("\nInterrupted. Run state saved as failed.")
      typer.echo(f"Resume with: sq run --resume {run_id}")
      raise typer.Exit(1)
  ```
- [x] Note: `_run_pipeline` finalizes with `failed` status in its `finally` block;
  the CLI layer adds the resume instructions
- [x] Write unit tests:
  - [x] Simulate `KeyboardInterrupt` → resume instructions printed, exit 1

**Commit:** `feat: implement sq run --resume, --from, implicit resume, interrupt handling`

### T18: Integration test — `--from` mid-process adoption

- [x] Test: `_run_pipeline("slice-lifecycle", {"slice": "191"}, from_step="implement-3",
  _action_registry=success_registry)`:
  - Only steps from `implement-3` onward appear in completed_steps
  - Status is `COMPLETED`

### T19: Integration test — dry-run produces no state file

- [x] Test: invoke dry-run path (mock `load_pipeline` + `validate_pipeline`):
  - Assert no `*.json` file created in `tmp_path`

**Commit:** `test: add CLI integration tests for sq run`

### T20: Exports, type annotations, and lint

- [x] Ensure `run.py` exports only `run` (other names are internal `_` prefixed)
- [x] Run `pyright` on `src/squadron/cli/commands/run.py`; fix all errors
- [x] Run `ruff check src/squadron/cli/commands/run.py`; fix all issues
- [x] Run `ruff format src/squadron/cli/commands/run.py`
- [x] Run full test suite: `uv run pytest tests/cli/ tests/pipeline/test_cli_integration.py -v`
- [x] Confirm zero failures

### T21: Verification and closeout

- [x] Manual smoke test: `sq run --help` shows all options
- [x] Manual smoke test: `sq run --list` shows built-in pipelines
- [x] Manual smoke test: `sq run --validate slice-lifecycle` passes validation
- [x] Manual smoke test: `sq run --dry-run slice-lifecycle 191` shows plan
- [x] Update `dateUpdated` in `151-slice.cli-integration-and-end-to-end-validation.md`
  and set `status: complete`
- [x] Mark slice 151 `[x]` in `140-slices.pipeline-foundation.md`
- [x] Update `CHANGELOG.md` with slice 151 entry
- [x] Update `DEVLOG.md` with Phase 6 completion entry

**Commit:** `feat: complete slice 151 — sq run CLI integration`
