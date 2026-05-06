---
docType: tasks
slice: auth-classification-diagnostics-cli
project: squadron
lld: user/slices/246-slice.auth-classification-diagnostics-cli.md
dependencies:
  - 243-resolution-pre-scan
  - 244-conditional-persistent-session-construction
  - 245-pool-resolution-classification-policy-and-mid-run-session-construction
projectState: >
  Slices 241–245 complete. PipelineClassification, classify_pipeline, and PoolClassificationPolicy
  all stable in squadron.pipeline.classification. run.py already imports and uses them via
  _run_pipeline_sdk. No --explain flag exists yet.
dateCreated: 20260506
dateUpdated: 20260506
dateCompleted: 20260506
status: complete
---

## Context Summary

- Implementing `sq run --explain <pipeline>` on top of the completed classification infrastructure
  from slice 243.
- All changes are confined to `src/squadron/cli/commands/run.py`.
- No new module; no changes to `classification.py`, `executor.py`, or any other module.
- The explain path reuses the same resolver-construction pattern already present in
  `_run_pipeline_sdk`; tests go in `tests/cli/commands/test_run.py` (existing file).
- Dependencies 243–245 are complete; all required interfaces (`classify_pipeline`,
  `PipelineClassification`, `StepClassification`, `PipelineShape`, `StepClass`,
  `PoolClassificationPolicy`, `ClassificationError`) are importable and stable.
- Next planned slice: 247 (Documentation and Pipeline Authoring Guide Updates).

---

## Tasks

### T1 — Add `--explain` flag to `run()` typer signature

- [x] In `src/squadron/cli/commands/run.py`, add `explain: bool` to the `run()` function
  signature as a Typer option:
  - [x] Position it near the other non-execution inspect flags (`--validate`, `--dry-run`).
  - [x] Use: `explain: bool = typer.Option(False, "--explain", help="Print pipeline classification and exit without executing.")`
  - [x] No logic in this task — flag only.
  - [x] **Success:** `uv run sq run --help` shows `--explain` in the option list with the correct
    description. No other behavior changes.

### T2 — Add mutual-exclusivity guard for `--explain`

- [x] In the mutual-exclusivity block at the top of `run()` (after the existing guards), add a
  check that rejects `--explain` when combined with execution options.
  - [x] Execution options that conflict: `--resume`, `--from`, `--dry-run`, `--prompt-only`,
    `--validate`.
  - [x] `--model`, `--param`, `--strict`, and `--verbose` are compatible with `--explain`.
  - [x] Error message format: `"[red]Error: --explain cannot be combined with --{option}.[/red]"`
  - [x] Each conflicting flag gets its own guard clause (same pattern as existing guards).
  - [x] **Success:** Each incompatible combination prints the appropriate error and exits 1.

### T3 — Tests: mutual-exclusivity for `--explain`

- [x] In `tests/cli/commands/test_run.py`, add a test class `TestExplainMutualExclusivity`.
  - [x] One test per incompatible option: `--resume`, `--from`, `--dry-run`, `--prompt-only`,
    `--validate`. Each test invokes `runner.invoke(app, ["run", "p", "--explain", "--<flag>", ...])`.
  - [x] Each test asserts `result.exit_code == 1` and the error text contains `"--explain"`.
  - [x] **Success:** All five tests pass; `uv run pytest tests/cli/commands/test_run.py -v -k
    "TestExplainMutualExclusivity"` is green.

### T4 — Implement `_render_explain`

- [x] Add a new private function `_render_explain(classification: PipelineClassification) -> None`
  in `run.py`, above `_handle_explain`.
  - [x] Renders a Rich `Table` with columns: Step, Action, Alias, Model ID, Profile,
    Classification, Rationale. Print with `rprint`.
  - [x] One row per entry in `classification.steps`. Use `step.step_name`, `step.action_type`,
    `step.resolved_alias or "—"`, `step.resolved_model_id or "—"`, `step.profile or "—"`,
    `step.classification.value`, `step.rationale`.
  - [x] Color per classification value:
    - `sdk_required` → `"[yellow]{value}[/yellow]"`
    - `non_sdk` → `"[green]{value}[/green]"`
    - `pool_uncertain` → `"[magenta]{value}[/magenta]"`
  - [x] After the table, print a summary block (plain `rprint` lines or a `Panel`) with:
    - Pipeline shape label (map `PipelineShape` values to human strings per slice design §Output Design).
    - Pool policy: `"lazy (default)"` or `"strict"`.
    - `Needs persistent session: yes/no`
    - `Needs one-shot Claude: yes/no`
  - [x] Shape label mapping (use a local dict constant, not inline strings):
    - `CLAUDE_REQUIRED_PERSISTENT` → `"Claude-required (persistent)"`
    - `CLAUDE_REQUIRED_ONE_SHOT` → `"Claude-required (one-shot only)"`
    - `CLAUDE_FREE` → `"Claude-free"`
  - [x] **Success:** Function is ≤40 lines; calling it with a synthetic `PipelineClassification`
    in a REPL prints a table and summary without error.

### T5 — Implement `_handle_explain`

- [x] Add a new private function
  `_handle_explain(pipeline_name: str, model_override: str | None, param: list[str] | None, strict: bool) -> None`
  in `run.py`, above `_render_explain`.
  - [x] Load pipeline: `load_pipeline(pipeline_name.lower())`. On `FileNotFoundError`, print
    `"[red]Error: Pipeline '{name}' not found.[/red]"` and `raise typer.Exit(1)`.
  - [x] Validate: `validate_pipeline(definition)`. On errors, print each `{e.field}: {e.message}`
    and `raise typer.Exit(1)`.
  - [x] Extract effective model override from `model_override` and `param` (same logic used in
    `_assemble_params` for `--model` and `--param model=<value>`):
    - [x] `model_override` (from `--model`) takes precedence.
    - [x] Otherwise scan `param` list for an entry `"model=<value>"` and use its value.
    - [x] Result is `cli_override: str | None`.
  - [x] Resolve effective policy (identical to `_run_pipeline_sdk`):
    ```
    policy = PoolClassificationPolicy.LAZY
    if definition.auth_policy == PoolClassificationPolicy.STRICT: policy = STRICT
    if strict: policy = STRICT
    ```
  - [x] Build pool backend: `pool_backend = DefaultPoolBackend()`.
  - [x] Build resolver: `ModelResolver(cli_override=cli_override, pipeline_model=definition.model, pool_backend=pool_backend)`.
  - [x] Call `classify_pipeline(definition, resolver, pool_backend, policy=policy)`.
    On `ClassificationError`, print `"[red]Error: Classification failed — {exc}[/red]"` and
    `raise typer.Exit(1)`.
  - [x] Call `_render_explain(classification)`.
  - [x] Function is ≤40 lines of substantive logic (excluding blank lines and comments).
  - [x] **Success:** `_handle_explain("test-compact-compose", None, None, False)` (or equivalent
    available pipeline) prints a table and summary, exits normally.

### T6 — Wire `--explain` dispatch branch in `run()`

- [x] In the `run()` command body, add a dispatch branch for `--explain` placed after the
  `--validate` branch and before `--dry-run`.
  - [x] Guard: `if explain:`
  - [x] Inside: require `pipeline is not None` (same pattern as `--validate`).
  - [x] Call `_handle_explain(pipeline.lower(), model, param, strict)`.
  - [x] `raise typer.Exit(0)` after the call.
  - [x] **Success:** `uv run sq run test-compact-compose --explain` prints the classification and
    exits 0 without executing any step (no run-state file created).

### T7 — Tests: `_handle_explain` — happy paths

- [x] In `tests/cli/commands/test_run.py`, add a test class `TestExplainCommand`.
  - [x] **T7a — All-SDK pipeline:** Mock `load_pipeline`, `validate_pipeline`,
    `DefaultPoolBackend`, `ModelResolver`, and `classify_pipeline` to return a
    `PipelineClassification` with all `SDK_REQUIRED` dispatch steps. Invoke via
    `runner.invoke(app, ["run", "my-pipeline", "--explain"])`. Assert: exit code 0, output
    contains `"sdk_required"` and `"Claude-required (persistent)"`.
  - [x] **T7b — Claude-free pipeline:** Same structure but `PipelineClassification` with all
    `NON_SDK` steps. Assert: output contains `"non_sdk"` and `"Claude-free"`,
    `"needs persistent session: no"`.
  - [x] **T7c — One-shot-only pipeline:** `PipelineClassification` with SDK review step,
    `needs_persistent_session=False`. Assert: output contains `"Claude-required (one-shot only)"`.
  - [x] **T7d — Model override honored:** Invoke with `["run", "p", "--explain", "--param",
    "model=minimax"]`. Assert the `ModelResolver` was constructed with `cli_override="minimax"`.
  - [x] **T7e — `--strict` flag:** Invoke with `["run", "p", "--explain", "--strict"]`.
    Assert the `classify_pipeline` was called with `policy=PoolClassificationPolicy.STRICT`.
  - [x] **Success:** All five sub-tests pass; `uv run pytest tests/cli/commands/test_run.py -v -k
    "TestExplainCommand"` is green.

### T8 — Tests: `_handle_explain` — error paths

- [x] In the same `TestExplainCommand` class (or a sibling `TestExplainErrors`):
  - [x] **T8a — Pipeline not found:** Mock `load_pipeline` to raise `FileNotFoundError`. Assert:
    exit code 1, output contains `"not found"`.
  - [x] **T8b — Validation errors:** Mock `validate_pipeline` to return a non-empty error list.
    Assert: exit code 1, output contains the field and message from the error.
  - [x] **T8c — ClassificationError:** Mock `classify_pipeline` to raise `ClassificationError`.
    Assert: exit code 1, output contains `"Classification failed"`.
  - [x] **Success:** All three error-path tests pass; full `TestExplainCommand` suite green.

### T9 — Quality gates and commit

- [x] Run `uv run ruff format src/ tests/` — zero changes (already formatted) or apply and
  re-check.
- [x] Run `uv run ruff check src/ tests/` — zero errors.
- [x] Run `uv run pyright` — zero errors.
- [x] Run `uv run pytest` — full suite green (no regressions).
- [x] Confirm no run-state file is created by an `--explain` invocation (manual sanity check or
  test assertion).
- [x] Commit: `feat: add sq run --explain for pipeline auth classification display`
- [x] **Success:** All quality gates pass; commit exists on the `246-slice.auth-classification-diagnostics-cli` branch.
