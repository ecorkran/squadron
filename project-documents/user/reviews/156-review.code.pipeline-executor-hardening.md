---
docType: review
layer: project
reviewType: code
slice: pipeline-executor-hardening
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/156-slice.pipeline-executor-hardening.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260415
dateUpdated: 20260415
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Overly broad exception handling masks unrelated errors"
    location: src/squadron/cli/commands/run.py:851-853
  - id: F002
    severity: note
    category: user-experience
    summary: "Checkpoint trigger error message shows hyphenated format instead of enum values"
    location: src/squadron/pipeline/actions/checkpoint.py:96
  - id: F003
    severity: note
    category: code-organization
    summary: "Pipeline name normalization is applied at multiple entry points"
    location: src/squadron/cli/commands/run.py:640, 680, 701, 753, 808
  - id: F004
    severity: note
    category: testing
    summary: "Test file `test_run_pipeline.py` mocks `load_pipeline` to return test fixture"
    location: tests/cli/commands/test_run_pipeline.py
  - id: F005
    severity: pass
    category: code-quality
    summary: "ExecutionMode enum is properly implemented"
    location: src/squadron/pipeline/state.py:43-50
  - id: F006
    severity: pass
    category: data-integrity
    summary: "Schema version incremented appropriately"
    location: src/squadron/pipeline/state.py:34
  - id: F007
    severity: pass
    category: security
    summary: "Fail-fast validation before SDK session connection"
    location: src/squadron/cli/commands/run.py:236-241
  - id: F008
    severity: pass
    category: error-handling
    summary: "Checkpoint invalid trigger returns ActionResult with error details"
    location: src/squadron/pipeline/actions/checkpoint.py:82-99
  - id: F009
    severity: pass
    category: robustness
    summary: "Review action validates required inputs after auto-resolution"
    location: src/squadron/pipeline/actions/review.py:117-126
  - id: F010
    severity: pass
    category: testing
    summary: "Tests cover the core new functionality comprehensively"
    location: tests/cli/commands/test_run_pipeline.py, tests/pipeline/test_state.py
---

# Review: code — slice 156

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Overly broad exception handling masks unrelated errors

```python
except ValueError as exc:
    rprint(f"[red]Error: {exc}[/red]", file=sys.stderr)
    raise typer.Exit(1)
```

The `ValueError` catch block is too broad. It was added to handle validation errors, but `ValueError` can be raised by many unrelated operations (enum conversion, type coercion, Pydantic validation elsewhere, etc.). A generic ValueError from an unexpected location would be caught and presented as a validation error, confusing users.

**Recommendation:** Either catch a more specific exception type (e.g., a custom `PipelineValidationError`) or re-raise with additional context to distinguish validation errors from other ValueErrors.

---

### [NOTE] Checkpoint trigger error message shows hyphenated format instead of enum values

The error message for invalid checkpoint triggers shows:
```
f"Valid values: {valid}"
```

Where `valid = [t.value for t in CheckpointTrigger]`. If the enum uses `ON_CONCERNS` (snake_case), users might be confused seeing `on-concerns` (hyphenated) in the error when the actual valid YAML values use hyphens. This is likely correct, but worth verifying the enum values match what users actually enter in YAML.

---

### [NOTE] Pipeline name normalization is applied at multiple entry points

The `.lower()` call on `pipeline` appears at multiple code paths:
- Line 640: `_handle_prompt_only_init(pipeline.lower(), ...)`
- Line 680: `pipeline = pipeline.lower()` (validate-only branch)
- Line 701: `pipeline = pipeline.lower()` (dry-run branch)
- Line 753: (resume branch - uses `state.pipeline` which is already normalized)
- Line 808: `pipeline = pipeline.lower()` (standard execution)

This is correct behavior (fail-fast at boundary), but creates duplication. Consider extracting a helper function like `_normalize_pipeline_name(pipeline: str) -> str` if this pattern appears in other commands or grows more complex.

---

### [NOTE] Test file `test_run_pipeline.py` mocks `load_pipeline` to return test fixture

The tests in `TestRunPipelineValidation` (lines 128-151) mock `load_pipeline` to return `_make_definition()` (a test fixture), then mock `validate_pipeline` to return errors. This tests the error-handling path but doesn't test actual validation logic. This is acceptable for testing error propagation, but the test naming (`test_invalid_pipeline_raises_value_error`) could be clearer that it's testing the error path, not invalid YAML.

---

### [PASS] ExecutionMode enum is properly implemented

The new `ExecutionMode(StrEnum)` is correctly defined with `SDK` and `PROMPT_ONLY` variants. Using `StrEnum` ensures proper serialization to JSON strings and enables case-insensitive construction from strings.

---

### [PASS] Schema version incremented appropriately

Schema version incremented from 1 to 2 with a test (`test_load_schema_version_1_raises_with_message`) confirming v1 files are rejected. This ensures proper migration handling for the new `execution_mode` field.

---

### [PASS] Fail-fast validation before SDK session connection

The `_run_pipeline_sdk` function validates the pipeline *before* connecting the SDK session, preventing wasted resources on invalid pipelines. This is a good security/resource-efficiency pattern.

---

### [PASS] Checkpoint invalid trigger returns ActionResult with error details

Invalid checkpoint trigger values now return `ActionResult(success=False)` with a helpful error message listing valid values, rather than propagating a `ValueError`. This gracefully handles user misconfiguration.

---

### [PASS] Review action validates required inputs after auto-resolution

The review action now checks for missing required inputs after template auto-resolution and raises a descriptive `KeyError` if any are missing. This prevents confusing failures when a prior step doesn't produce expected files.

---

### [PASS] Tests cover the core new functionality comprehensively

New test file and test cases cover:
- `run_id` parameter threading through `_run_pipeline` and `_run_pipeline_sdk`
- Resume dispatch by `ExecutionMode` (both explicit and implicit)
- Pipeline name normalization
- `execution_mode` display in status output
- `ExecutionMode` enum round-trip and serialization

The tests use appropriate mocking strategies and verify the correct dispatch based on execution mode.

---

## Debug: Prompt & Response

### System Prompt

You are a code reviewer. Review code against Additional Review Rules, known language-specific rules, testing
standards, and project conventions.

Focus areas:
- Additional Review Rules
- Language Rules included in Additional Review Rules
- Software Design Principles (e.g. SOLID, DRY, KISS) included in Additional Review Rules
- Project conventions
- Test coverage patterns (test-with, not test-after)
- Error handling patterns
- Security concerns
- Naming, structure, and documentation quality
- Language-appropriate style and correctness

CRITICAL: Your verdict and findings MUST be consistent.
- If verdict is CONCERNS or FAIL, include at least one finding with that severity.
- If no CONCERN or FAIL findings exist, verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title

Report your findings using severity levels:

## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
Description with specific file and line references.


## Output Structure Requirements

For each finding, include a category tag on the line immediately after the heading:

### [CONCERN] Finding title
category: error-handling

You may also include a location tag:

### [CONCERN] Finding title
category: error-handling
location: src/module.py:45

Valid severity levels: PASS, NOTE, CONCERN, FAIL

Use NOTE for informational observations that don't require action.
Use CONCERN for issues that should be addressed but don't block progress.
Use FAIL for issues that must be fixed before proceeding.


## Additional Review Rules

### Design Principles

#### SOLID

- **Single Responsibility (SRP):** Each class/module should have one reason to change. If a class handles both business logic and persistence, or both data transformation and presentation, flag it. A good test: can you describe what the class does without using "and"?

- **Open/Closed (OCP):** Code should be open for extension, closed for modification. When adding a new variant requires editing a switch/case or if-else chain in existing code rather than adding a new implementation, that's a violation. Look for: growing conditionals, type-checking dispatches, functions that keep accumulating parameters.

- **Liskov Substitution (LSP):** Subtypes must be substitutable for their base types without breaking behavior. Watch for: subclasses that throw NotImplementedError on inherited methods, overrides that silently change return semantics, or isinstance checks that branch on concrete type.

- **Interface Segregation (ISP):** Clients should not depend on methods they don't use. Watch for: large interfaces/protocols where most implementations stub out half the methods, "god objects" that every module imports but each uses a different slice of.

- **Dependency Inversion (DIP):** High-level modules should not depend on low-level modules — both should depend on abstractions. Flag when:
  - A class instantiates its own dependencies (e.g., `self.client = HttpClient()`) instead of accepting them via constructor/parameter
  - Business logic imports concrete infrastructure (database drivers, HTTP clients, file I/O) directly rather than through an interface/protocol
  - Test difficulty is a symptom — if testing requires monkeypatching internals, the dependency graph is inverted

#### Other Principles

- **DRY (Don't Repeat Yourself):** Duplicated logic should be extracted. But note: similar-looking code that changes for different reasons is NOT duplication — premature abstraction is worse than repetition.

- **Composition over Inheritance:** Prefer composing behavior from small, focused objects over deep inheritance hierarchies. Inheritance for code reuse (rather than genuine is-a relationships) creates fragile coupling.

- **Law of Demeter:** Methods should only talk to their immediate collaborators, not reach through chains (`a.b.c.doThing()`). Deep accessor chains indicate missing abstractions.

- **Fail Fast:** Invalid state should be caught at the boundary, not deep in call chains. Validate inputs early, use guard clauses, prefer explicit errors over silent defaults.

---

---
description: Python coding standards and conventions. Use when writing, modifying, or reviewing .py files, pyproject.toml, or requirements files.
paths:
 - "**/*.py"
 - "**/pyproject.toml"
 - "**/requirements*.txt"
---

### Python Rules

#### General
* Target Python 3.12+ for production (stability & ecosystem compatibility).
* Note: Python 3.14+ is acceptable for isolated services needing specific features (e.g., free-threading), but verify ML library support first.

#### Typing & Validation
- Use built-in types: `list`, `dict`, `tuple`, not `List`, `Dict`, `Tuple`
- Use `|` for union types: `str | None` not `Optional[str]` or `Union[str, None]`
- Use `Self` (from `typing`) for return types of fluent methods/factories (3.11+).
- Type hint all function signatures and class attributes
- Use `@dataclass` for internal data transfer objects (DTOs) and configuration.
- Use `Pydantic` for all external boundaries (API inputs/outputs, file parsing, environment variables).
- Import Policy: Keep `from __future__ import annotations` for 3.12/3.13 projects to resolve forward references cleanly. (Remove only once strictly on 3.14+).

#### Code Style & Structure
- Follow PEP 8 with 88-character line length
- Formatter: Use `ruff` for both linting and formatting (replaces Black/Isort/Flake8 due to speed).
- Use descriptive variable names; avoid single letters (except `x`, `i` in short loops/comprehensions).
- Prefer `f-strings` exclusively; avoid `.format()` or `%`.
- Use `pathlib` and its `Path` for all file/path operations, not `os.path.join` or similar
- One class per file for models/services; group related tiny utilities in `utils.py` or specific modules.

#### Functions & Error Handling
- Small, single-purpose functions (max 20 lines preferred)
- Use early returns (`guard clauses`) to flatten nesting.
- Explicit exception handling: catch specific errors (`ValueError`), never bare `except:`.
- Use `try/except` blocks narrowly around the specific line that might fail.
- Use context managers (`with`) for resource management (files, locks, connections).

#### Modern Python Patterns
- Use `match/case` for structural pattern matching (parsing dictionaries, complex conditions).
- Use `walrus operator (:=)` sparingly—only when it significantly reduces duplication.
- Comprehensions over `map`/`filter` when clear
- Use generator expressions `(x for x in y)` for large sequences to save memory.
- Use `itertools` for efficient looping and `functools.partial`/`reduce` where appropriate.
- Use `Enum` (specifically `StrEnum` in 3.11+) for constants/choices.

#### Testing & Quality
- Write tests alongside implementation
- Use `pytest` exclusively.
- Use `conftest.py` for shared fixtures; keep individual test files clean.
- Parametrize tests (`@pytest.mark.parametrize`) to cover edge cases.
- Mock external I/O boundaries; test internal logic with real data.
- Static Analysis: Strict `mypy` or `pyright` (VS Code Pylance “Strict” mode). Zero errors policy.
- Docstrings for public APIs (Google or NumPy style)

#### Dependencies & Imports
* Package Manager: Use `uv` for all projects (replaces Poetry/Pipenv for speed and standard compliance).
- Pin direct dependencies in `pyproject.toml`.
- Group imports: Standard Lib -> Third Party -> Local Application.
- Use absolute imports (`from myapp.services import ...`) over relative (`from ..services import ...`).
- No wildcard imports (`from module import *`).

#### Async & Performance
- Use `async`/`await` for I/O-bound operations (DB, API calls).
- Use `asyncio.TaskGroup` (3.11+) for safer concurrent task management.
- Profile before optimizing (use `py-spy` or `cProfile`).
- Use `functools.cache` or `lru_cache` for expensive pure functions.

#### Security & Best Practices
- Secrets: Never commit secrets. Use `.env` files (loaded via `pydantic-settings`).
- Input: Validate everything entering the system via Pydantic.
- SQL: Always use parameterized queries (never f-string SQL).
- Randomness: Use `secrets` module for security tokens, `random` only for simulations.

### User Prompt

Review code in the project at: /Users/manta/source/repos/manta/squadron

Run `git diff b269c43^1..b269c43^2 -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/src/squadron/cli/commands/run.py b/src/squadron/cli/commands/run.py
index 00e390d..39757c4 100644
--- a/src/squadron/cli/commands/run.py
+++ b/src/squadron/cli/commands/run.py
@@ -35,7 +35,7 @@ from squadron.pipeline.prompt_renderer import (
 )
 from squadron.pipeline.resolver import ModelResolver
 from squadron.pipeline.sdk_session import SDKExecutionSession
-from squadron.pipeline.state import SchemaVersionError, StateManager
+from squadron.pipeline.state import ExecutionMode, SchemaVersionError, StateManager
 
 # ---------------------------------------------------------------------------
 # Status display colours
@@ -104,18 +104,18 @@ def _assemble_params(
     return params
 
 
-def _resolve_execution_mode(prompt_only: bool) -> str:
+def _resolve_execution_mode(prompt_only: bool) -> ExecutionMode:
     """Determine pipeline execution mode from flags and environment.
 
     Returns:
-        ``"prompt-only"`` when ``--prompt-only`` is set.
-        ``"sdk"`` when running from a standard terminal.
+        ``ExecutionMode.PROMPT_ONLY`` when ``--prompt-only`` is set.
+        ``ExecutionMode.SDK`` when running from a standard terminal.
 
     Raises:
         typer.Exit(1): When invoked from inside a Claude Code session.
     """
     if prompt_only:
-        return "prompt-only"
+        return ExecutionMode.PROMPT_ONLY
     if os.environ.get("CLAUDECODE"):
         rprint(
             "[red]Error: SDK pipeline execution cannot run inside a Claude Code "
@@ -123,7 +123,7 @@ def _resolve_execution_mode(prompt_only: bool) -> str:
             "Use [bold]--prompt-only[/bold] mode or run from a standard terminal."
         )
         raise typer.Exit(1)
-    return "sdk"
+    return ExecutionMode.SDK
 
 
 def _check_cf(cf_client: ContextForgeClient) -> None:
@@ -151,6 +151,8 @@ async def _run_pipeline(
     runs_dir: Path | None = None,
     from_step: str | None = None,
     sdk_session: object | None = None,
+    run_id: str | None = None,
+    execution_mode: ExecutionMode = ExecutionMode.SDK,
     _action_registry: dict[str, object] | None = None,
 ) -> PipelineResult:
     """Load, validate, and execute a pipeline end-to-end.
@@ -159,11 +161,19 @@ async def _run_pipeline(
     ``asyncio.run()``.  All dependency construction happens here so that
     integration tests can call this directly.
 
+    When *run_id* is provided the existing state file is reused (resume path);
+    ``init_run`` is skipped so no new state file is created.
+
     Raises ``FileNotFoundError`` when the pipeline cannot be found — the
     caller is responsible for printing the message and exiting.
     """
     definition = load_pipeline(pipeline_name)
 
+    errors = validate_pipeline(definition)
+    if errors:
+        msg = "; ".join(f"{e.field}: {e.message}" for e in errors)
+        raise ValueError(f"Pipeline '{pipeline_name}' has validation errors: {msg}")
+
     resolver = ModelResolver(
         cli_override=model_override,
         pipeline_model=definition.model,
@@ -172,7 +182,10 @@ async def _run_pipeline(
     _check_cf(cf_client)
 
     state_mgr = StateManager(runs_dir=runs_dir)
-    run_id = state_mgr.init_run(pipeline_name, params)
+    if run_id is None:
+        run_id = state_mgr.init_run(
+            pipeline_name, params, execution_mode=execution_mode
+        )
 
     try:
         result = await execute_pipeline(
@@ -207,15 +220,25 @@ async def _run_pipeline_sdk(
     model_override: str | None = None,
     runs_dir: Path | None = None,
     from_step: str | None = None,
+    run_id: str | None = None,
 ) -> PipelineResult:
     """Create an SDK session, run the pipeline, and disconnect on exit.
 
+    When *run_id* is provided the existing run state is reused (resume path).
+
     Raises typer.Exit(1) when running inside a Claude Code session.
     The session is disconnected in a ``finally`` block so cleanup happens
     on success, failure, checkpoint pause, and keyboard interrupt.
     """
     _resolve_execution_mode(prompt_only=False)
 
+    # Validate before connecting the SDK session — fail fast on bad YAML
+    definition = load_pipeline(pipeline_name)
+    errors = validate_pipeline(definition)
+    if errors:
+        msg = "; ".join(f"{e.field}: {e.message}" for e in errors)
+        raise ValueError(f"Pipeline '{pipeline_name}' has validation errors: {msg}")
+
     import claude_agent_sdk
 
     options = claude_agent_sdk.ClaudeAgentOptions(cwd=str(Path.cwd()))
@@ -231,6 +254,8 @@ async def _run_pipeline_sdk(
             runs_dir=runs_dir,
             from_step=from_step,
             sdk_session=session,
+            run_id=run_id,
+            execution_mode=ExecutionMode.SDK,
         )
     finally:
         await session.disconnect()
@@ -256,6 +281,7 @@ def _display_run_status(state: object) -> None:
         f"[bold]Pipeline:[/bold] {state.pipeline}",
         f"[bold]Params:[/bold]   {state.params}",
         f"[bold]Status:[/bold]   [{color}]{state.status}[/{color}]",
+        f"[bold]Mode:[/bold]     {state.execution_mode.value}",
         f"[bold]Started:[/bold]  {state.started_at:%Y-%m-%d %H:%M:%S}",
         f"[bold]Updated:[/bold]  {state.updated_at:%Y-%m-%d %H:%M:%S}",
         f"[bold]Steps:[/bold]    {len(state.completed_steps)} completed",
@@ -328,7 +354,9 @@ def _handle_prompt_only_init(
     )
 
     state_mgr = StateManager()
-    run_id = state_mgr.init_run(pipeline_name, params)
+    run_id = state_mgr.init_run(
+        pipeline_name, params, execution_mode=ExecutionMode.PROMPT_ONLY
+    )
     rprint(f"run_id={run_id}", file=sys.stderr)
 
     # Render first step
@@ -612,7 +640,7 @@ def run(
         if pipeline is None:
             rprint("[red]Error: pipeline argument is required for --prompt-only.[/red]")
             raise typer.Exit(1)
-        _handle_prompt_only_init(pipeline, target, model, param)
+        _handle_prompt_only_init(pipeline.lower(), target, model, param)
         raise typer.Exit(0)
 
     # ---- --list ----
@@ -651,6 +679,7 @@ def run(
     # ---- --validate ----
     if validate_only:
         assert pipeline is not None  # guarded above
+        pipeline = pipeline.lower()
         try:
             definition = load_pipeline(pipeline)
         except FileNotFoundError:
@@ -670,6 +699,7 @@ def run(
     # ---- --dry-run ----
     if dry_run:
         assert pipeline is not None  # guarded above
+        pipeline = pipeline.lower()
         try:
             definition = load_pipeline(pipeline)
         except FileNotFoundError:
@@ -720,37 +750,41 @@ def run(
             if state.params.get("model")
             else model
         )
-        resolver = ModelResolver(
-            cli_override=resume_model,
-            pipeline_model=definition.model,
-        )
-        cf_client = ContextForgeClient()
-        _check_cf(cf_client)
 
         run_id = resume
         try:
-            result = asyncio.run(
-                execute_pipeline(
-                    definition,
-                    dict(state.params),
-                    resolver=resolver,
-                    cf_client=cf_client,
-                    run_id=run_id,
-                    start_from=resume_from,
-                    on_step_complete=state_mgr.make_step_callback(run_id),
-                )
-            )
+            match state.execution_mode:
+                case ExecutionMode.SDK:
+                    result = asyncio.run(
+                        _run_pipeline_sdk(
+                            state.pipeline,
+                            dict(state.params),
+                            model_override=resume_model,
+                            run_id=run_id,
+                            from_step=resume_from,
+                        )
+                    )
+                case ExecutionMode.PROMPT_ONLY:
+                    result = asyncio.run(
+                        _run_pipeline(
+                            state.pipeline,
+                            dict(state.params),
+                            model_override=resume_model,
+                            run_id=run_id,
+                            from_step=resume_from,
+                        )
+                    )
         except KeyboardInterrupt:
             rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
             rprint(f"Resume with: [bold]sq run --resume {run_id}[/bold]")
             raise typer.Exit(1)
 
-        state_mgr.finalize(run_id, result)
         _display_result(result)
         raise typer.Exit(0)
 
     # ---- standard execution ----
     assert pipeline is not None  # guarded above
+    pipeline = pipeline.lower()
 
     try:
         definition = load_pipeline(pipeline)
@@ -773,14 +807,27 @@ def run(
                 )
                 if implicit_from is not None:
                     try:
-                        result = asyncio.run(
-                            _run_pipeline(
-                                pipeline,
-                                params,
-                                model_override=model,
-                                from_step=implicit_from,
-                            )
-                        )
+                        match match.execution_mode:
+                            case ExecutionMode.SDK:
+                                result = asyncio.run(
+                                    _run_pipeline_sdk(
+                                        match.pipeline,
+                                        dict(match.params),
+                                        model_override=model,
+                                        run_id=match.run_id,
+                                        from_step=implicit_from,
+                                    )
+                                )
+                            case ExecutionMode.PROMPT_ONLY:
+                                result = asyncio.run(
+                                    _run_pipeline(
+                                        match.pipeline,
+                                        dict(match.params),
+                                        model_override=model,
+                                        run_id=match.run_id,
+                                        from_step=implicit_from,
+                                    )
+                                )
                     except KeyboardInterrupt:
                         rprint("\n[yellow]Interrupted. Run state saved.[/yellow]")
                         rprint(
@@ -804,6 +851,9 @@ def run(
     except FileNotFoundError:
         # Already printed by _run_pipeline
         raise typer.Exit(1)
+    except ValueError as exc:
+        rprint(f"[red]Error: {exc}[/red]", file=sys.stderr)
+        raise typer.Exit(1)
     except KeyboardInterrupt:
         rprint("\n[yellow]Interrupted. Run state saved as failed.[/yellow]")
         rprint("Resume with: [bold]sq run --resume <run-id>[/bold]")
diff --git a/src/squadron/pipeline/actions/checkpoint.py b/src/squadron/pipeline/actions/checkpoint.py
index 243a44a..40610f4 100644
--- a/src/squadron/pipeline/actions/checkpoint.py
+++ b/src/squadron/pipeline/actions/checkpoint.py
@@ -82,7 +82,20 @@ class CheckpointAction:
     async def execute(self, context: ActionContext) -> ActionResult:
         # Trigger resolution
         trigger_str = str(context.params.get("trigger", CheckpointTrigger.ON_CONCERNS))
-        trigger = CheckpointTrigger(trigger_str)
+        try:
+            trigger = CheckpointTrigger(trigger_str)
+        except ValueError:
+            valid = [t.value for t in CheckpointTrigger]
+            return ActionResult(
+                success=False,
+                action_type=self.action_type,
+                outputs={
+                    "error": (
+                        f"Invalid checkpoint trigger '{trigger_str}'. "
+                        f"Valid values: {valid}"
+                    ),
+                },
+            )
 
         # Prior verdict lookup
         verdict = _find_review_verdict(context.prior_outputs)
diff --git a/src/squadron/pipeline/actions/review.py b/src/squadron/pipeline/actions/review.py
index 335b7aa..400ac7b 100644
--- a/src/squadron/pipeline/actions/review.py
+++ b/src/squadron/pipeline/actions/review.py
@@ -111,6 +111,18 @@ class ReviewAction:
                 template_name, int(str(slice_param)), context.cf_client, inputs
             )
 
+        # Check required inputs are satisfied after auto-resolution
+        missing = [
+            inp.name for inp in template.required_inputs if inp.name not in inputs
+        ]
+        if missing:
+            names = ", ".join(missing)
+            raise KeyError(
+                f"Review template '{template_name}' missing required "
+                f"input(s): {names}. The prior step may not have "
+                f"created the expected file."
+            )
+
         # Rules content
         rules_content: str | None = None
         if "rules_content" in context.params:
diff --git a/src/squadron/pipeline/loader.py b/src/squadron/pipeline/loader.py
index 9cb286f..bf938e5 100644
--- a/src/squadron/pipeline/loader.py
+++ b/src/squadron/pipeline/loader.py
@@ -65,6 +65,9 @@ def load_pipeline(
     if candidate.is_file():
         return _load_yaml(candidate)
 
+    # Normalise name to lowercase for case-insensitive lookup
+    name_or_path = name_or_path.lower()
+
     # Search directories: project (highest priority) → user → built-in
     search_dirs = _search_dirs(project_dir=project_dir, user_dir=user_dir)
     for search_dir in search_dirs:
@@ -135,7 +138,7 @@ def discover_pipelines(
                 with open(yaml_path) as f:
                     raw = yaml.safe_load(f)
                 schema = PipelineSchema.model_validate(raw)
-                pipeline_name = schema.name
+                pipeline_name = schema.name.lower()
                 found[pipeline_name] = PipelineInfo(
                     name=pipeline_name,
                     description=schema.description,
diff --git a/src/squadron/pipeline/state.py b/src/squadron/pipeline/state.py
index f5c8704..adf8ffc 100644
--- a/src/squadron/pipeline/state.py
+++ b/src/squadron/pipeline/state.py
@@ -16,6 +16,7 @@ import re
 import uuid
 from collections.abc import Callable
 from datetime import UTC, datetime
+from enum import StrEnum
 from pathlib import Path
 from typing import TYPE_CHECKING
 
@@ -30,6 +31,7 @@ if TYPE_CHECKING:
 _logger = logging.getLogger(__name__)
 
 __all__ = [
+    "ExecutionMode",
     "StateManager",
     "RunState",
     "StepState",
@@ -37,7 +39,19 @@ __all__ = [
     "SchemaVersionError",
 ]
 
-_SCHEMA_VERSION = 1
+_SCHEMA_VERSION = 2
+
+
+# ---------------------------------------------------------------------------
+# Enums
+# ---------------------------------------------------------------------------
+
+
+class ExecutionMode(StrEnum):
+    """Identifies which runner was used to start a pipeline run."""
+
+    SDK = "sdk"
+    PROMPT_ONLY = "prompt-only"
 
 
 # ---------------------------------------------------------------------------
@@ -86,6 +100,7 @@ class RunState(BaseModel):
     run_id: str
     pipeline: str
     params: dict[str, object]
+    execution_mode: ExecutionMode = ExecutionMode.SDK
     started_at: datetime
     updated_at: datetime
     status: str  # ExecutionStatus string value
@@ -139,18 +154,21 @@ class StateManager:
         pipeline_name: str,
         params: dict[str, object],
         run_id: str | None = None,
+        execution_mode: ExecutionMode = ExecutionMode.SDK,
     ) -> str:
         """Create an initial state file and return the run_id."""
+        pipeline_name = pipeline_name.lower()
         now = datetime.now(UTC)
         if run_id is None:
             date = now.strftime("%Y%m%d")
-            slug = _SLUG_RE.sub("-", pipeline_name.lower()).strip("-")
+            slug = _SLUG_RE.sub("-", pipeline_name).strip("-")
             run_id = f"run-{date}-{slug}-{uuid.uuid4().hex[:8]}"
 
         state = RunState(
             run_id=run_id,
             pipeline=pipeline_name,
             params=params,
+            execution_mode=execution_mode,
             started_at=now,
             updated_at=now,
             status="running",
diff --git a/tests/cli/commands/test_run_pipeline.py b/tests/cli/commands/test_run_pipeline.py
new file mode 100644
index 0000000..495f47e
--- /dev/null
+++ b/tests/cli/commands/test_run_pipeline.py
@@ -0,0 +1,549 @@
+"""Tests for pipeline executor hardening changes in sq run command.
+
+Covers: run_id / execution_mode threading through _run_pipeline and
+_run_pipeline_sdk, --resume dispatch by ExecutionMode, implicit resume
+dispatch, _handle_prompt_only_init recording PROMPT_ONLY, pipeline name
+normalisation at CLI boundary, and _display_run_status execution_mode field.
+"""
+
+from __future__ import annotations
+
+from datetime import UTC, datetime
+from pathlib import Path
+from unittest.mock import AsyncMock, MagicMock, patch
+
+import pytest
+
+from squadron.cli.commands.run import _display_run_status, _handle_prompt_only_init
+from squadron.pipeline.executor import ExecutionStatus, PipelineResult
+from squadron.pipeline.models import PipelineDefinition, StepConfig
+from squadron.pipeline.state import ExecutionMode, RunState, StateManager
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+def _make_definition(
+    name: str = "test-pipeline",
+    params: dict[str, object] | None = None,
+    steps: list[StepConfig] | None = None,
+) -> PipelineDefinition:
+    return PipelineDefinition(
+        name=name,
+        description="Test pipeline",
+        params=params or {},
+        steps=steps or [StepConfig(step_type="phase", name="step1", config={})],
+    )
+
+
+def _make_run_state(
+    run_id: str = "run-test",
+    pipeline: str = "test-pipeline",
+    execution_mode: ExecutionMode = ExecutionMode.SDK,
+    status: str = "paused",
+) -> RunState:
+    now = datetime.now(UTC)
+    return RunState(
+        run_id=run_id,
+        pipeline=pipeline,
+        params={"slice": "1"},
+        execution_mode=execution_mode,
+        started_at=now,
+        updated_at=now,
+        status=status,
+    )
+
+
+# ---------------------------------------------------------------------------
+# T4: _run_pipeline run_id parameter
+# ---------------------------------------------------------------------------
+
+
+class TestRunPipelineRunId:
+    def test_without_run_id_calls_init_run(self, tmp_path: Path) -> None:
+        """When run_id is None, _run_pipeline calls init_run to create a new state."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline
+
+        definition = _make_definition()
+        mock_result = PipelineResult(
+            pipeline_name="test-pipeline",
+            status=ExecutionStatus.COMPLETED,
+            step_results=[],
+        )
+
+        with (
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
+            patch("squadron.cli.commands.run._check_cf"),
+            patch(
+                "squadron.cli.commands.run.execute_pipeline",
+                new_callable=AsyncMock,
+                return_value=mock_result,
+            ),
+        ):
+            mgr = StateManager(runs_dir=tmp_path)
+            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
+                asyncio.run(_run_pipeline("test-pipeline", {}, runs_dir=tmp_path))
+
+        # A new state file should have been created
+        state_files = list(tmp_path.glob("*.json"))
+        assert len(state_files) == 1
+
+    def test_with_run_id_skips_init_run(self, tmp_path: Path) -> None:
+        """When run_id is provided, no new state file is created."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline
+
+        definition = _make_definition()
+        mock_result = PipelineResult(
+            pipeline_name="test-pipeline",
+            status=ExecutionStatus.COMPLETED,
+            step_results=[],
+        )
+
+        # Pre-create a state file for the provided run_id
+        mgr = StateManager(runs_dir=tmp_path)
+        existing_id = mgr.init_run("test-pipeline", {"slice": "1"})
+
+        with (
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
+            patch("squadron.cli.commands.run._check_cf"),
+            patch(
+                "squadron.cli.commands.run.execute_pipeline",
+                new_callable=AsyncMock,
+                return_value=mock_result,
+            ),
+        ):
+            with patch("squadron.cli.commands.run.StateManager", return_value=mgr):
+                asyncio.run(
+                    _run_pipeline(
+                        "test-pipeline",
+                        {"slice": "1"},
+                        run_id=existing_id,
+                        runs_dir=tmp_path,
+                    )
+                )
+
+        # Only the pre-existing state file should exist
+        state_files = list(tmp_path.glob("*.json"))
+        assert len(state_files) == 1
+        assert state_files[0].stem == existing_id
+
+
+# ---------------------------------------------------------------------------
+# _run_pipeline rejects invalid pipelines at validation
+# ---------------------------------------------------------------------------
+
+
+class TestRunPipelineValidation:
+    def test_invalid_pipeline_raises_value_error(self) -> None:
+        """_run_pipeline raises ValueError when validate_pipeline finds errors."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline
+        from squadron.pipeline.models import ValidationError
+
+        definition = _make_definition()
+        errors = [
+            ValidationError(
+                field="checkpoint",
+                message="'concerns' is not a valid checkpoint trigger",
+                action_type="design",
+            )
+        ]
+
+        with (
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=errors),
+        ):
+            with pytest.raises(ValueError, match="validation errors"):
+                asyncio.run(_run_pipeline("test-pipeline", {}))
+
+
+# ---------------------------------------------------------------------------
+# T5: _run_pipeline_sdk run_id parameter
+# ---------------------------------------------------------------------------
+
+
+class TestRunPipelineSdkRunId:
+    def test_sdk_with_explicit_run_id_reuses_state(self, tmp_path: Path) -> None:
+        """_run_pipeline_sdk forwards run_id to _run_pipeline."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline_sdk
+
+        mock_result = PipelineResult(
+            pipeline_name="test-pipeline",
+            status=ExecutionStatus.COMPLETED,
+            step_results=[],
+        )
+
+        with (
+            patch("squadron.cli.commands.run._resolve_execution_mode"),
+            patch(
+                "squadron.cli.commands.run.load_pipeline",
+                return_value=_make_definition(),
+            ),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
+            patch(
+                "squadron.cli.commands.run._run_pipeline",
+                new_callable=AsyncMock,
+                return_value=mock_result,
+            ) as mock_inner,
+            patch("claude_agent_sdk.ClaudeAgentOptions"),
+            patch("claude_agent_sdk.ClaudeSDKClient"),
+            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
+        ):
+            mock_session = AsyncMock()
+            mock_session_cls.return_value = mock_session
+
+            asyncio.run(
+                _run_pipeline_sdk("test-pipeline", {}, run_id="run-existing-123")
+            )
+
+        # run_id must be forwarded
+        call_kwargs = mock_inner.call_args.kwargs
+        assert call_kwargs.get("run_id") == "run-existing-123"
+
+    def test_sdk_without_run_id_passes_none(self, tmp_path: Path) -> None:
+        """When no run_id given, _run_pipeline_sdk passes run_id=None."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline_sdk
+
+        mock_result = PipelineResult(
+            pipeline_name="test-pipeline",
+            status=ExecutionStatus.COMPLETED,
+            step_results=[],
+        )
+
+        with (
+            patch("squadron.cli.commands.run._resolve_execution_mode"),
+            patch(
+                "squadron.cli.commands.run.load_pipeline",
+                return_value=_make_definition(),
+            ),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
+            patch(
+                "squadron.cli.commands.run._run_pipeline",
+                new_callable=AsyncMock,
+                return_value=mock_result,
+            ) as mock_inner,
+            patch("claude_agent_sdk.ClaudeAgentOptions"),
+            patch("claude_agent_sdk.ClaudeSDKClient"),
+            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
+        ):
+            mock_session = AsyncMock()
+            mock_session_cls.return_value = mock_session
+
+            asyncio.run(_run_pipeline_sdk("test-pipeline", {}))
+
+        call_kwargs = mock_inner.call_args.kwargs
+        assert call_kwargs.get("run_id") is None
+
+
+class TestRunPipelineSdkValidation:
+    def test_sdk_rejects_invalid_pipeline_before_connect(self) -> None:
+        """_run_pipeline_sdk raises ValueError before SDK session connects."""
+        import asyncio
+
+        from squadron.cli.commands.run import _run_pipeline_sdk
+        from squadron.pipeline.models import ValidationError
+
+        errors = [
+            ValidationError(
+                field="checkpoint",
+                message="'concerns' is not a valid checkpoint trigger",
+                action_type="design",
+            )
+        ]
+
+        with (
+            patch("squadron.cli.commands.run._resolve_execution_mode"),
+            patch(
+                "squadron.cli.commands.run.load_pipeline",
+                return_value=_make_definition(),
+            ),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=errors),
+            patch("squadron.cli.commands.run.SDKExecutionSession") as mock_session_cls,
+        ):
+            mock_session = AsyncMock()
+            mock_session_cls.return_value = mock_session
+
+            with pytest.raises(ValueError, match="validation errors"):
+                asyncio.run(_run_pipeline_sdk("test-pipeline", {}))
+
+            # Session should never have connected
+            mock_session.connect.assert_not_called()
+
+
+# ---------------------------------------------------------------------------
+# T6/T7: Resume dispatch by ExecutionMode
+# ---------------------------------------------------------------------------
+
+
+class TestResumeDispatch:
+    """Verify --resume dispatches to the correct runner based on execution_mode."""
+
+    def test_explicit_resume_sdk_calls_run_pipeline_sdk(self) -> None:
+        """--resume with SDK state calls _run_pipeline_sdk."""
+        import typer as _typer
+        from typer.testing import CliRunner
+
+        from squadron.cli.app import app
+
+        sdk_state = _make_run_state(run_id="run-sdk", execution_mode=ExecutionMode.SDK)
+        definition = _make_definition()
+        mock_result = MagicMock()
+        mock_result.status.value = "completed"
+        mock_result.pipeline_name = "test-pipeline"
+        mock_result.step_results = []
+
+        with (
+            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
+            patch("squadron.cli.commands.run.typer") as mock_typer,
+        ):
+            mock_typer.Exit = _typer.Exit
+            mock_typer.BadParameter = _typer.BadParameter
+            mock_asyncio.run.return_value = mock_result
+            mock_mgr = MagicMock()
+            mock_mgr.load.return_value = sdk_state
+            mock_mgr.first_unfinished_step.return_value = "step1"
+            mock_mgr_cls.return_value = mock_mgr
+
+            runner = CliRunner()
+            runner.invoke(app, ["run", "--resume", "run-sdk"])
+
+        assert mock_asyncio.run.call_count == 1
+        coroutine_arg = mock_asyncio.run.call_args[0][0]
+        assert coroutine_arg.__qualname__ == "_run_pipeline_sdk"
+
+    def test_explicit_resume_prompt_only_calls_run_pipeline(self) -> None:
+        """--resume with PROMPT_ONLY state calls _run_pipeline, not SDK."""
+        import typer as _typer
+        from typer.testing import CliRunner
+
+        from squadron.cli.app import app
+
+        po_state = _make_run_state(
+            run_id="run-po", execution_mode=ExecutionMode.PROMPT_ONLY
+        )
+        definition = _make_definition()
+        mock_result = MagicMock()
+        mock_result.status.value = "completed"
+        mock_result.pipeline_name = "test-pipeline"
+        mock_result.step_results = []
+
+        with (
+            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
+            patch("squadron.cli.commands.run.typer") as mock_typer,
+        ):
+            mock_typer.Exit = _typer.Exit
+            mock_typer.BadParameter = _typer.BadParameter
+            mock_asyncio.run.return_value = mock_result
+            mock_mgr = MagicMock()
+            mock_mgr.load.return_value = po_state
+            mock_mgr.first_unfinished_step.return_value = "step1"
+            mock_mgr_cls.return_value = mock_mgr
+
+            runner = CliRunner()
+            runner.invoke(app, ["run", "--resume", "run-po"])
+
+        assert mock_asyncio.run.call_count == 1
+        coroutine_arg = mock_asyncio.run.call_args[0][0]
+        assert coroutine_arg.__qualname__ == "_run_pipeline"
+
+    def test_implicit_resume_sdk_calls_run_pipeline_sdk(self) -> None:
+        """Implicit resume with SDK state calls _run_pipeline_sdk."""
+        import typer as _typer
+        from typer.testing import CliRunner
+
+        from squadron.cli.app import app
+
+        sdk_state = _make_run_state(run_id="run-sdk", execution_mode=ExecutionMode.SDK)
+        definition = _make_definition()
+        mock_result = MagicMock()
+        mock_result.status.value = "completed"
+        mock_result.pipeline_name = "test-pipeline"
+        mock_result.step_results = []
+
+        with (
+            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.sys") as mock_sys,
+            patch("squadron.cli.commands.run.typer") as mock_typer,
+            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
+        ):
+            mock_sys.stdin.isatty.return_value = True
+            mock_typer.confirm.return_value = True
+            mock_typer.Exit = _typer.Exit
+            mock_typer.BadParameter = _typer.BadParameter
+            mock_asyncio.run.return_value = mock_result
+            mock_mgr = MagicMock()
+            mock_mgr.find_matching_run.return_value = sdk_state
+            mock_mgr.first_unfinished_step.return_value = "step1"
+            mock_mgr_cls.return_value = mock_mgr
+
+            runner = CliRunner()
+            runner.invoke(app, ["run", "test-pipeline"])
+
+        # asyncio.run should be called with the sdk coroutine
+        assert mock_asyncio.run.call_count == 1
+        coroutine_arg = mock_asyncio.run.call_args[0][0]
+        # The coroutine's function should be _run_pipeline_sdk
+        assert coroutine_arg.__qualname__ == "_run_pipeline_sdk"
+
+    def test_implicit_resume_prompt_only_calls_run_pipeline(self) -> None:
+        """Implicit resume with PROMPT_ONLY state calls _run_pipeline (not SDK)."""
+        import typer as _typer
+        from typer.testing import CliRunner
+
+        from squadron.cli.app import app
+
+        po_state = _make_run_state(
+            run_id="run-po", execution_mode=ExecutionMode.PROMPT_ONLY
+        )
+        definition = _make_definition()
+        mock_result = MagicMock()
+        mock_result.status.value = "completed"
+        mock_result.pipeline_name = "test-pipeline"
+        mock_result.step_results = []
+
+        with (
+            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.sys") as mock_sys,
+            patch("squadron.cli.commands.run.typer") as mock_typer,
+            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
+        ):
+            mock_sys.stdin.isatty.return_value = True
+            mock_typer.confirm.return_value = True
+            mock_typer.Exit = _typer.Exit
+            mock_typer.BadParameter = _typer.BadParameter
+            mock_asyncio.run.return_value = mock_result
+            mock_mgr = MagicMock()
+            mock_mgr.find_matching_run.return_value = po_state
+            mock_mgr.first_unfinished_step.return_value = "step1"
+            mock_mgr_cls.return_value = mock_mgr
+
+            runner = CliRunner()
+            runner.invoke(app, ["run", "test-pipeline"])
+
+        assert mock_asyncio.run.call_count == 1
+        coroutine_arg = mock_asyncio.run.call_args[0][0]
+        # The coroutine's function should be _run_pipeline (not SDK)
+        assert coroutine_arg.__qualname__ == "_run_pipeline"
+
+
+# ---------------------------------------------------------------------------
+# T8: _handle_prompt_only_init records PROMPT_ONLY
+# ---------------------------------------------------------------------------
+
+
+class TestHandlePromptOnlyInit:
+    def test_creates_state_with_prompt_only_mode(self, tmp_path: Path) -> None:
+        """_handle_prompt_only_init stores execution_mode=PROMPT_ONLY."""
+        definition = _make_definition(
+            name="test-pipeline",
+            steps=[StepConfig(step_type="phase", name="step1", config={})],
+        )
+
+        from squadron.pipeline.prompt_renderer import StepInstructions
+
+        mock_instructions = MagicMock(spec=StepInstructions)
+        mock_instructions.to_json.return_value = '{"step": "step1"}'
+
+        state_mgr = StateManager(runs_dir=tmp_path)
+
+        with (
+            patch("squadron.cli.commands.run.load_pipeline", return_value=definition),
+            patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
+            patch(
+                "squadron.cli.commands.run.render_step_instructions",
+                return_value=mock_instructions,
+            ),
+            patch("squadron.cli.commands.run.StateManager", return_value=state_mgr),
+        ):
+            _handle_prompt_only_init("test-pipeline", None, None, None)
+
+        # Find the created run
+        runs = state_mgr.list_runs()
+        assert len(runs) == 1
+        assert runs[0].execution_mode == ExecutionMode.PROMPT_ONLY
+
+
+# ---------------------------------------------------------------------------
+# T11: Pipeline name normalisation at CLI boundary
+# ---------------------------------------------------------------------------
+
+
+class TestPipelineNameNormalisation:
+    def test_mixed_case_pipeline_name_passed_to_load_pipeline(self) -> None:
+        """The CLI normalises pipeline names to lowercase before load_pipeline."""
+        import typer as _typer
+        from typer.testing import CliRunner
+
+        from squadron.cli.app import app
+
+        definition = _make_definition()
+        mock_result = MagicMock()
+        mock_result.status.value = "completed"
+        mock_result.pipeline_name = "test-pipeline"
+        mock_result.step_results = []
+
+        with (
+            patch(
+                "squadron.cli.commands.run.load_pipeline", return_value=definition
+            ) as mock_load,
+            patch("squadron.cli.commands.run.StateManager") as mock_mgr_cls,
+            patch("squadron.cli.commands.run.sys") as mock_sys,
+            patch("squadron.cli.commands.run.typer") as mock_typer,
+            patch("squadron.cli.commands.run.asyncio") as mock_asyncio,
+        ):
+            mock_sys.stdin.isatty.return_value = True
+            mock_typer.Exit = _typer.Exit
+            mock_typer.BadParameter = _typer.BadParameter
+            mock_asyncio.run.return_value = mock_result
+            mock_mgr = MagicMock()
+            mock_mgr.find_matching_run.return_value = None
+            mock_mgr_cls.return_value = mock_mgr
+
+            runner = CliRunner()
+            runner.invoke(app, ["run", "Test-Pipeline"])
+
+        # load_pipeline must receive the lowercase name
+        mock_load.assert_called_once_with("test-pipeline")
+
+
+# ---------------------------------------------------------------------------
+# T12: _display_run_status shows execution_mode
+# ---------------------------------------------------------------------------
+
+
+class TestDisplayRunStatus:
+    def test_sdk_execution_mode_shown(self, capsys: pytest.CaptureFixture[str]) -> None:
+        """_display_run_status output includes 'sdk' for SDK mode."""
+        state = _make_run_state(execution_mode=ExecutionMode.SDK, status="completed")
+        _display_run_status(state)
+        captured = capsys.readouterr()
+        assert "sdk" in captured.out
+
+    def test_prompt_only_execution_mode_shown(
+        self, capsys: pytest.CaptureFixture[str]
+    ) -> None:
+        """_display_run_status output includes 'prompt-only' for PROMPT_ONLY mode."""
+        state = _make_run_state(
+            execution_mode=ExecutionMode.PROMPT_ONLY, status="paused"
+        )
+        _display_run_status(state)
+        captured = capsys.readouterr()
+        assert "prompt-only" in captured.out
diff --git a/tests/pipeline/actions/test_checkpoint.py b/tests/pipeline/actions/test_checkpoint.py
index f6db180..c20ecf5 100644
--- a/tests/pipeline/actions/test_checkpoint.py
+++ b/tests/pipeline/actions/test_checkpoint.py
@@ -220,3 +220,12 @@ class TestCheckpointExecute:
         ctx_skip = _make_context(params={"trigger": "never"})
         assert (await CheckpointAction().execute(ctx_fire)).success is True
         assert (await CheckpointAction().execute(ctx_skip)).success is True
+
+    @pytest.mark.asyncio
+    async def test_invalid_trigger_returns_failure(self) -> None:
+        """Invalid trigger value returns ActionResult(success=False)."""
+        ctx = _make_context(params={"trigger": "concerns"})
+        result = await CheckpointAction().execute(ctx)
+        assert result.success is False
+        assert "concerns" in result.outputs["error"]
+        assert "on-concerns" in result.outputs["error"]
diff --git a/tests/pipeline/actions/test_review_action.py b/tests/pipeline/actions/test_review_action.py
index 5bef699..51bbf32 100644
--- a/tests/pipeline/actions/test_review_action.py
+++ b/tests/pipeline/actions/test_review_action.py
@@ -76,7 +76,10 @@ def _make_review_result(
 
 
 def _mock_template() -> ReviewTemplate:
-    return MagicMock(spec=ReviewTemplate, name="code")
+    mock = MagicMock(spec=ReviewTemplate, name="code")
+    mock.required_inputs = []
+    mock.optional_inputs = []
+    return mock
 
 
 # ---------------------------------------------------------------------------
@@ -408,6 +411,25 @@ class TestReviewErrors:
         assert result.success is False
         assert "not found" in (result.error or "")
 
+    @pytest.mark.asyncio
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_missing_required_input(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+    ) -> None:
+        from squadron.review.templates import InputDef
+
+        mock_tpl = _mock_template()
+        mock_tpl.required_inputs = [InputDef(name="input", description="doc to review")]
+        mock_get_template.return_value = mock_tpl
+
+        result = await ReviewAction().execute(_make_context())
+        assert result.success is False
+        assert "missing required input" in (result.error or "").lower()
+        assert "input" in (result.error or "")
+
     @pytest.mark.asyncio
     @patch(f"{_P}.get_template")
     @patch(f"{_P}.load_all_templates")
diff --git a/tests/pipeline/test_loader.py b/tests/pipeline/test_loader.py
index 028edc0..e72d2f3 100644
--- a/tests/pipeline/test_loader.py
+++ b/tests/pipeline/test_loader.py
@@ -145,3 +145,79 @@ class TestDiscoverPipelines:
         names = [p.name for p in pipelines]
         assert "broken" not in names
         assert "slice" in names
+
+
+# ---------------------------------------------------------------------------
+# T9: load_pipeline case-insensitive name lookup
+# ---------------------------------------------------------------------------
+
+
+class TestLoadPipelineCaseNormalisation:
+    def test_mixed_case_name_finds_lowercase_file(self, tmp_path: Path) -> None:
+        """load_pipeline("Test-Pipeline") finds test-pipeline.yaml."""
+        proj = tmp_path / "project"
+        _write_pipeline_yaml(proj, "test-pipeline")
+        defn = load_pipeline(
+            "Test-Pipeline",
+            project_dir=proj,
+            user_dir=Path("/nonexistent"),
+        )
+        assert defn.name == "test-pipeline"
+
+    def test_uppercase_name_finds_lowercase_file(self, tmp_path: Path) -> None:
+        """load_pipeline("TEST-PIPELINE") also finds test-pipeline.yaml."""
+        proj = tmp_path / "project"
+        _write_pipeline_yaml(proj, "test-pipeline")
+        defn = load_pipeline(
+            "TEST-PIPELINE",
+            project_dir=proj,
+            user_dir=Path("/nonexistent"),
+        )
+        assert defn.name == "test-pipeline"
+
+    def test_direct_file_path_not_normalised(self, tmp_path: Path) -> None:
+        """load_pipeline("/path/to/My-Pipeline.yaml") loads the exact path."""
+        # Write a file with a mixed-case filename; it should be loaded as-is
+        mixed_path = _write_pipeline_yaml(tmp_path, "My-Pipeline")
+        defn = load_pipeline(str(mixed_path))
+        # The name inside the YAML is "My-Pipeline" (as written by the helper)
+        assert defn.name == "My-Pipeline"
+
+
+# ---------------------------------------------------------------------------
+# T10: discover_pipelines lowercase normalisation
+# ---------------------------------------------------------------------------
+
+
+class TestDiscoverPipelinesNormalisation:
+    def _write_yaml_with_name(self, directory: Path, filename: str, name: str) -> None:
+        """Write a pipeline YAML where the 'name' field may differ from filename."""
+        directory.mkdir(parents=True, exist_ok=True)
+        path = directory / filename
+        data = {
+            "name": name,
+            "description": f"test pipeline {name}",
+            "steps": [],
+        }
+        path.write_text(__import__("yaml").dump(data))
+
+    def test_discover_returns_lowercase_name(self, tmp_path: Path) -> None:
+        """discover_pipelines normalises names to lowercase."""
+        import yaml
+
+        proj = tmp_path / "project"
+        proj.mkdir()
+        # Write a valid pipeline YAML with a mixed-case 'name' field
+        data = {
+            "name": "MyPipeline",
+            "description": "test",
+            "steps": [{"design": {"phase": 0}}],
+        }
+        (proj / "mypipeline.yaml").write_text(yaml.dump(data))
+        pipelines = discover_pipelines(
+            project_dir=proj,
+            user_dir=Path("/nonexistent"),
+        )
+        names = [p.name for p in pipelines]
+        assert "mypipeline" in names
+        assert "MyPipeline" not in names
diff --git a/tests/pipeline/test_sdk_wiring.py b/tests/pipeline/test_sdk_wiring.py
index 4a4d900..fe8302e 100644
--- a/tests/pipeline/test_sdk_wiring.py
+++ b/tests/pipeline/test_sdk_wiring.py
@@ -130,6 +130,8 @@ async def test_run_pipeline_sdk_connects_and_disconnects_on_success() -> None:
 
     with (
         patch("squadron.cli.commands.run._resolve_execution_mode"),
+        patch("squadron.cli.commands.run.load_pipeline"),
+        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
         patch(
             "squadron.cli.commands.run._run_pipeline",
             new_callable=AsyncMock,
@@ -160,6 +162,8 @@ async def test_run_pipeline_sdk_disconnects_on_failure() -> None:
 
     with (
         patch("squadron.cli.commands.run._resolve_execution_mode"),
+        patch("squadron.cli.commands.run.load_pipeline"),
+        patch("squadron.cli.commands.run.validate_pipeline", return_value=[]),
         patch(
             "squadron.cli.commands.run._run_pipeline",
             new_callable=AsyncMock,
diff --git a/tests/pipeline/test_state.py b/tests/pipeline/test_state.py
index be49860..fce60ee 100644
--- a/tests/pipeline/test_state.py
+++ b/tests/pipeline/test_state.py
@@ -18,12 +18,32 @@ from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResu
 from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
 from squadron.pipeline.state import (
     CheckpointState,
+    ExecutionMode,
     RunState,
     SchemaVersionError,
     StateManager,
     StepState,
 )
 
+# ---------------------------------------------------------------------------
+# T1: ExecutionMode enum tests
+# ---------------------------------------------------------------------------
+
+
+class TestExecutionMode:
+    def test_sdk_value(self) -> None:
+        assert ExecutionMode.SDK.value == "sdk"
+
+    def test_prompt_only_value(self) -> None:
+        assert ExecutionMode.PROMPT_ONLY.value == "prompt-only"
+
+    def test_round_trip_from_string_sdk(self) -> None:
+        assert ExecutionMode("sdk") == ExecutionMode.SDK
+
+    def test_round_trip_from_string_prompt_only(self) -> None:
+        assert ExecutionMode("prompt-only") == ExecutionMode.PROMPT_ONLY
+
+
 # ---------------------------------------------------------------------------
 # T3: Pydantic model tests
 # ---------------------------------------------------------------------------
@@ -36,6 +56,7 @@ class TestPydanticModels:
             run_id="run-20260403-test-abc12345",
             pipeline="test-pipeline",
             params={"slice": "191"},
+            execution_mode=ExecutionMode.SDK,
             started_at=now,
             updated_at=now,
             status="running",
@@ -47,6 +68,48 @@ class TestPydanticModels:
         assert restored.params == original.params
         assert restored.status == original.status
 
+    def test_run_state_execution_mode_sdk_serialises(self) -> None:
+        now = datetime.now(UTC)
+        state = RunState(
+            run_id="run-x",
+            pipeline="pipe",
+            params={},
+            execution_mode=ExecutionMode.SDK,
+            started_at=now,
+            updated_at=now,
+            status="running",
+        )
+        dumped = state.model_dump(mode="json")
+        assert dumped["execution_mode"] == "sdk"
+
+    def test_run_state_execution_mode_prompt_only_serialises(self) -> None:
+        now = datetime.now(UTC)
+        state = RunState(
+            run_id="run-x",
+            pipeline="pipe",
+            params={},
+            execution_mode=ExecutionMode.PROMPT_ONLY,
+            started_at=now,
+            updated_at=now,
+            status="running",
+        )
+        dumped = state.model_dump(mode="json")
+        assert dumped["execution_mode"] == "prompt-only"
+
+    def test_run_state_missing_execution_mode_defaults_to_sdk(self) -> None:
+        now = datetime.now(UTC)
+        data: dict[str, object] = {
+            "schema_version": 2,
+            "run_id": "run-x",
+            "pipeline": "pipe",
+            "params": {},
+            "started_at": now.isoformat(),
+            "updated_at": now.isoformat(),
+            "status": "running",
+        }
+        state = RunState.model_validate(data)
+        assert state.execution_mode == ExecutionMode.SDK
+
     def test_step_state_defaults(self) -> None:
         now = datetime.now(UTC)
         step = StepState(
@@ -152,6 +215,22 @@ class TestInitRun:
         assert run_id.startswith("run-")
         assert "slice" in run_id
 
+    def test_init_run_stores_execution_mode_prompt_only(
+        self, state_manager: StateManager
+    ) -> None:
+        run_id = state_manager.init_run(
+            "pipe", {}, execution_mode=ExecutionMode.PROMPT_ONLY
+        )
+        state = state_manager.load(run_id)
+        assert state.execution_mode == ExecutionMode.PROMPT_ONLY
+
+    def test_init_run_normalises_pipeline_name_to_lowercase(
+        self, state_manager: StateManager
+    ) -> None:
+        run_id = state_manager.init_run("Test-Pipeline", {})
+        state = state_manager.load(run_id)
+        assert state.pipeline == "test-pipeline"
+
 
 # ---------------------------------------------------------------------------
 # T8: make_step_callback / _append_step tests
@@ -306,6 +385,18 @@ class TestLoad:
         with pytest.raises(SchemaVersionError):
             state_manager.load("run-bad")
 
+    def test_load_schema_version_1_raises_with_message(
+        self, state_manager: StateManager, tmp_path: Path
+    ) -> None:
+        bad = tmp_path / "run-v1.json"
+        bad.write_text(
+            json.dumps({"schema_version": 1, "run_id": "run-v1"}), encoding="utf-8"
+        )
+        with pytest.raises(
+            SchemaVersionError, match="Unsupported state file schema_version"
+        ):
+            state_manager.load("run-v1")
+
     def test_load_schema_version_0_raises(
         self, state_manager: StateManager, tmp_path: Path
     ) -> None:

```

### CLAUDE.md (project conventions)

```
# Project Guidelines for Claude

[//]: # (context-forge:managed)

## Core Principles

- Always resist adding complexity. Ensure it is truly necessary.
- Never use silent fallback values. Fail explicitly with errors or obviously-placeholder values.
- Never use cheap hacks or well-known anti-patterns.
- Never include credentials, API keys, or secrets in source code or comments. Load from environment variables; ensure .env is in .gitignore. Raise an issue if violations are found.
- When debugging a failure, get the actual error message before attempting any fix. Never apply more than one speculative fix without first obtaining concrete evidence (logs, error text, stack trace) that diagnoses the root cause. If you cannot get the evidence yourself, ask the Project Manager for it.

## Code Structure

- Keep source files to ~300 lines, functions to ~50 lines (excluding whitespace) where practical.
- Program to interfaces (contracts).  Maintain clear separation between components.
- Do not duplicate logic.  Respect DRY (don't repeat yourself).
- Provide meaningful but concise comments in relevant places.

- Never scatter comparison values across code. If a value is used in conditionals, switch cases, or lookups, define it once (enum, constant, or config) and reference that definition everywhere. Changing a value should require editing exactly one place.
- Do not hard-code magic defaults.  In the example below, the defaults for model and n are both wrong.  If such defaults are needed they should be centralized at the config level.  This applies in all languages.
```python
  async def _model_start(promt:str) -> str {
    model = self._config.model or "gpt-5.3-codex"
    n = self._config.index or 1234
  }
```
- NEVER use user-accessible labels as logical structure.  They are fragile.


## Source Control and Builds
- Keep commits semantic; build after all changes.
- Git add and commit from project root at least once per task.
- Confirm your current working directory before file/shell commands.

## Parsing & Pattern Matching
- Prefer lenient parsing over strict matching. A regex that silently fails on valid input (e.g. requiring exact whitespace counts or line-ending positions) is a bug. Parse the semantic content, not the formatting.
- When parsing structured text (YAML, key-value pairs, etc.), handle common format variations (compact vs multi-line, varying indent levels, trailing whitespace) rather than requiring one exact layout.
- When writing a parser, the test fixture must include the actual format that parser will consume in production.  A test that only passes on a format the real data never uses only provides false confidence.
- If a parser returns empty/default on bad input, add at least one test using real-world input (e.g. the actual file it will parse) to catch silent failures.
  
## Hallucination traps in prompts
If an instruction tells a reader to retrieve a value from some source, and
that source might return empty, do not place a hardcoded example of an
acceptable value nearby. When the source is empty, a model will reach for
the nearest plausible token — and the example is it. This is a
hallucination trap.

### Bad

    Print the filename (from stderr, e.g. `squadron-P4.md`).

### Good

    Print the filename. The CLI emits it on a line prefixed with
    `Using: ` on stderr. If no such line is present, stop with an error.


## Project Navigation
- Follow `guide.ai-project.process` and its links for workflow.
- Follow `file-naming-conventions` for all document naming and metadata.
- Project guides: `project-documents/ai-project-guide/project-guides/`
- Tool guides: `project-documents/ai-project-guide/tool-guides/`
- Modular rules for specific technologies may exist in 
  `project-guides/rules/`.

## Document Conventions

- All markdown files must include YAML frontmatter as specified in `file-naming-conventions.md`
- Use checklist format for all task files.  Each item and subitem should have a `[ ]` "checkbox".
- After completing a task or subtask, make sure it is checked off in the appropriate file(s).  Use the task-check subagent if available.- Preserve sections titled "## User-Provided Concept" exactly as 
  written — never modify or remove.
- Keep success summaries concise and minimal.

## Git Rules

### Branch Naming
When working on a slice, use a branch named after the slice (without the `.md` extension but with the numeric index prefix).

Before starting implementation work on a slice:
1. verify you are on main or the expected slice branch
2. if the expected slice branch does not exist, create it from `main`: `git checkout -b {branch-name}`
3. If the slice branch already exists, switch to it: `git checkout {branch-name}`
4. Never start slice work from another slice's branch unless explicitly instructed
5. If in doubt, STOP and ask the Project Manager

### Commit Messages
Use semantic commit prefixes. The goal is a readable `git log --oneline`.

Format: `{type}: {short imperative summary}`

Types:
- `feat` — New functionality or capability
- `fix` — Bug fix
- `refactor` — Code restructuring without behavior change
- `test` — Adding or updating tests
- `style` — Formatting, whitespace, linting (no logic change)
- `guides` - Update or addition to project guides (system/project level)
- `docs` — Update or addition to user/ guides or documentation (slices, readme, etc)
- `review` — Code review, design review, or audit documentation
- `package` - Updates related to packaging, npm, package.json, PyPi, etc
- `chore` — Build config, dependencies, tooling, CI

Actions (optional, use if applicable):
- `update`: primarily update/edit to existing information
- `add`: primarily addition of new code or information
- `extract`: primarily used in refactoring
- `reduce`: if primary work involves reduction or streamlining

### Guidelines:
- Summary is imperative mood ("add X" not "added X" or "adds X")
- Keep to ~72 characters
- No period at end
- Scope is optional but useful in monorepos: `feat(core): add template variable resolution`

### Examples:
feat: add context_build MCP tool
fix: update to handle missing template directory gracefully
refactor(core): extract service instantiation into shared helper
docs: add MCP server installation instructions to README
test: add unit tests for prompt_list tool handler
chore: update @modelcontextprotocol/server to v2.1


```

### Rules Injected

### Design Principles

#### SOLID

- **Single Responsibility (SRP):** Each class/module should have one reason to change. If a class handles both business logic and persistence, or both data transformation and presentation, flag it. A good test: can you describe what the class does without using "and"?

- **Open/Closed (OCP):** Code should be open for extension, closed for modification. When adding a new variant requires editing a switch/case or if-else chain in existing code rather than adding a new implementation, that's a violation. Look for: growing conditionals, type-checking dispatches, functions that keep accumulating parameters.

- **Liskov Substitution (LSP):** Subtypes must be substitutable for their base types without breaking behavior. Watch for: subclasses that throw NotImplementedError on inherited methods, overrides that silently change return semantics, or isinstance checks that branch on concrete type.

- **Interface Segregation (ISP):** Clients should not depend on methods they don't use. Watch for: large interfaces/protocols where most implementations stub out half the methods, "god objects" that every module imports but each uses a different slice of.

- **Dependency Inversion (DIP):** High-level modules should not depend on low-level modules — both should depend on abstractions. Flag when:
  - A class instantiates its own dependencies (e.g., `self.client = HttpClient()`) instead of accepting them via constructor/parameter
  - Business logic imports concrete infrastructure (database drivers, HTTP clients, file I/O) directly rather than through an interface/protocol
  - Test difficulty is a symptom — if testing requires monkeypatching internals, the dependency graph is inverted

#### Other Principles

- **DRY (Don't Repeat Yourself):** Duplicated logic should be extracted. But note: similar-looking code that changes for different reasons is NOT duplication — premature abstraction is worse than repetition.

- **Composition over Inheritance:** Prefer composing behavior from small, focused objects over deep inheritance hierarchies. Inheritance for code reuse (rather than genuine is-a relationships) creates fragile coupling.

- **Law of Demeter:** Methods should only talk to their immediate collaborators, not reach through chains (`a.b.c.doThing()`). Deep accessor chains indicate missing abstractions.

- **Fail Fast:** Invalid state should be caught at the boundary, not deep in call chains. Validate inputs early, use guard clauses, prefer explicit errors over silent defaults.

---

---
description: Python coding standards and conventions. Use when writing, modifying, or reviewing .py files, pyproject.toml, or requirements files.
paths:
 - "**/*.py"
 - "**/pyproject.toml"
 - "**/requirements*.txt"
---

### Python Rules

#### General
* Target Python 3.12+ for production (stability & ecosystem compatibility).
* Note: Python 3.14+ is acceptable for isolated services needing specific features (e.g., free-threading), but verify ML library support first.

#### Typing & Validation
- Use built-in types: `list`, `dict`, `tuple`, not `List`, `Dict`, `Tuple`
- Use `|` for union types: `str | None` not `Optional[str]` or `Union[str, None]`
- Use `Self` (from `typing`) for return types of fluent methods/factories (3.11+).
- Type hint all function signatures and class attributes
- Use `@dataclass` for internal data transfer objects (DTOs) and configuration.
- Use `Pydantic` for all external boundaries (API inputs/outputs, file parsing, environment variables).
- Import Policy: Keep `from __future__ import annotations` for 3.12/3.13 projects to resolve forward references cleanly. (Remove only once strictly on 3.14+).

#### Code Style & Structure
- Follow PEP 8 with 88-character line length
- Formatter: Use `ruff` for both linting and formatting (replaces Black/Isort/Flake8 due to speed).
- Use descriptive variable names; avoid single letters (except `x`, `i` in short loops/comprehensions).
- Prefer `f-strings` exclusively; avoid `.format()` or `%`.
- Use `pathlib` and its `Path` for all file/path operations, not `os.path.join` or similar
- One class per file for models/services; group related tiny utilities in `utils.py` or specific modules.

#### Functions & Error Handling
- Small, single-purpose functions (max 20 lines preferred)
- Use early returns (`guard clauses`) to flatten nesting.
- Explicit exception handling: catch specific errors (`ValueError`), never bare `except:`.
- Use `try/except` blocks narrowly around the specific line that might fail.
- Use context managers (`with`) for resource management (files, locks, connections).

#### Modern Python Patterns
- Use `match/case` for structural pattern matching (parsing dictionaries, complex conditions).
- Use `walrus operator (:=)` sparingly—only when it significantly reduces duplication.
- Comprehensions over `map`/`filter` when clear
- Use generator expressions `(x for x in y)` for large sequences to save memory.
- Use `itertools` for efficient looping and `functools.partial`/`reduce` where appropriate.
- Use `Enum` (specifically `StrEnum` in 3.11+) for constants/choices.

#### Testing & Quality
- Write tests alongside implementation
- Use `pytest` exclusively.
- Use `conftest.py` for shared fixtures; keep individual test files clean.
- Parametrize tests (`@pytest.mark.parametrize`) to cover edge cases.
- Mock external I/O boundaries; test internal logic with real data.
- Static Analysis: Strict `mypy` or `pyright` (VS Code Pylance “Strict” mode). Zero errors policy.
- Docstrings for public APIs (Google or NumPy style)

#### Dependencies & Imports
* Package Manager: Use `uv` for all projects (replaces Poetry/Pipenv for speed and standard compliance).
- Pin direct dependencies in `pyproject.toml`.
- Group imports: Standard Lib -> Third Party -> Local Application.
- Use absolute imports (`from myapp.services import ...`) over relative (`from ..services import ...`).
- No wildcard imports (`from module import *`).

#### Async & Performance
- Use `async`/`await` for I/O-bound operations (DB, API calls).
- Use `asyncio.TaskGroup` (3.11+) for safer concurrent task management.
- Profile before optimizing (use `py-spy` or `cProfile`).
- Use `functools.cache` or `lru_cache` for expensive pure functions.

#### Security & Best Practices
- Secrets: Never commit secrets. Use `.env` files (loaded via `pydantic-settings`).
- Input: Validate everything entering the system via Pydantic.
- SQL: Always use parameterized queries (never f-string SQL).
- Randomness: Use `secrets` module for security tokens, `random` only for simulations.

### Raw Response

Let me review the git diff against the project conventions and Python best practices.

## Summary
[CONCERNS]

## Findings

### [CONCERN] Overly broad exception handling masks unrelated errors
category: error-handling
location: src/squadron/cli/commands/run.py:851-853

```python
except ValueError as exc:
    rprint(f"[red]Error: {exc}[/red]", file=sys.stderr)
    raise typer.Exit(1)
```

The `ValueError` catch block is too broad. It was added to handle validation errors, but `ValueError` can be raised by many unrelated operations (enum conversion, type coercion, Pydantic validation elsewhere, etc.). A generic ValueError from an unexpected location would be caught and presented as a validation error, confusing users.

**Recommendation:** Either catch a more specific exception type (e.g., a custom `PipelineValidationError`) or re-raise with additional context to distinguish validation errors from other ValueErrors.

---

### [NOTE] Checkpoint trigger error message shows hyphenated format instead of enum values
category: user-experience
location: src/squadron/pipeline/actions/checkpoint.py:96

The error message for invalid checkpoint triggers shows:
```
f"Valid values: {valid}"
```

Where `valid = [t.value for t in CheckpointTrigger]`. If the enum uses `ON_CONCERNS` (snake_case), users might be confused seeing `on-concerns` (hyphenated) in the error when the actual valid YAML values use hyphens. This is likely correct, but worth verifying the enum values match what users actually enter in YAML.

---

### [NOTE] Pipeline name normalization is applied at multiple entry points
category: code-organization
location: src/squadron/cli/commands/run.py:640, 680, 701, 753, 808

The `.lower()` call on `pipeline` appears at multiple code paths:
- Line 640: `_handle_prompt_only_init(pipeline.lower(), ...)`
- Line 680: `pipeline = pipeline.lower()` (validate-only branch)
- Line 701: `pipeline = pipeline.lower()` (dry-run branch)
- Line 753: (resume branch - uses `state.pipeline` which is already normalized)
- Line 808: `pipeline = pipeline.lower()` (standard execution)

This is correct behavior (fail-fast at boundary), but creates duplication. Consider extracting a helper function like `_normalize_pipeline_name(pipeline: str) -> str` if this pattern appears in other commands or grows more complex.

---

### [NOTE] Test file `test_run_pipeline.py` mocks `load_pipeline` to return test fixture
category: testing
location: tests/cli/commands/test_run_pipeline.py

The tests in `TestRunPipelineValidation` (lines 128-151) mock `load_pipeline` to return `_make_definition()` (a test fixture), then mock `validate_pipeline` to return errors. This tests the error-handling path but doesn't test actual validation logic. This is acceptable for testing error propagation, but the test naming (`test_invalid_pipeline_raises_value_error`) could be clearer that it's testing the error path, not invalid YAML.

---

### [PASS] ExecutionMode enum is properly implemented
category: code-quality
location: src/squadron/pipeline/state.py:43-50

The new `ExecutionMode(StrEnum)` is correctly defined with `SDK` and `PROMPT_ONLY` variants. Using `StrEnum` ensures proper serialization to JSON strings and enables case-insensitive construction from strings.

---

### [PASS] Schema version incremented appropriately
category: data-integrity
location: src/squadron/pipeline/state.py:34

Schema version incremented from 1 to 2 with a test (`test_load_schema_version_1_raises_with_message`) confirming v1 files are rejected. This ensures proper migration handling for the new `execution_mode` field.

---

### [PASS] Fail-fast validation before SDK session connection
category: security
location: src/squadron/cli/commands/run.py:236-241

The `_run_pipeline_sdk` function validates the pipeline *before* connecting the SDK session, preventing wasted resources on invalid pipelines. This is a good security/resource-efficiency pattern.

---

### [PASS] Checkpoint invalid trigger returns ActionResult with error details
category: error-handling
location: src/squadron/pipeline/actions/checkpoint.py:82-99

Invalid checkpoint trigger values now return `ActionResult(success=False)` with a helpful error message listing valid values, rather than propagating a `ValueError`. This gracefully handles user misconfiguration.

---

### [PASS] Review action validates required inputs after auto-resolution
category: robustness
location: src/squadron/pipeline/actions/review.py:117-126

The review action now checks for missing required inputs after template auto-resolution and raises a descriptive `KeyError` if any are missing. This prevents confusing failures when a prior step doesn't produce expected files.

---

### [PASS] Tests cover the core new functionality comprehensively
category: testing
location: tests/cli/commands/test_run_pipeline.py, tests/pipeline/test_state.py

New test file and test cases cover:
- `run_id` parameter threading through `_run_pipeline` and `_run_pipeline_sdk`
- Resume dispatch by `ExecutionMode` (both explicit and implicit)
- Pipeline name normalization
- `execution_mode` display in status output
- `ExecutionMode` enum round-trip and serialization

The tests use appropriate mocking strategies and verify the correct dispatch based on execution mode.
