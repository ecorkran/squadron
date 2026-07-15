---
docType: review
layer: project
reviewType: code
slice: judge-gated-cycle-conventions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md
aiModel: moonshotai/kimi-k2.6
status: complete
dateCreated: 20260714
dateUpdated: 20260714
findings:
  - id: F001
    severity: concern
    category: design
    summary: "Executor couples concretely to PhaseStepType for artifact post-condition"
    location: src/squadron/pipeline/executor.py:33
  - id: F002
    severity: concern
    category: design
    summary: "ActionResult mutated in place after action execution"
    location: src/squadron/pipeline/executor.py:1055
  - id: F003
    severity: concern
    category: project-conventions
    summary: "Magic fallback string \"unknown\" hardcoded in multiple modules"
    location: src/squadron/integrations/context_forge.py:172
  - id: F004
    severity: concern
    category: error-handling
    summary: "Unchecked assumption that RunState.started_at is timezone-aware"
    location: src/squadron/pipeline/executor.py:997
  - id: F005
    severity: pass
    category: error-handling
    summary: "Comprehensive fail-fast guards and failure-mode enumeration for missing inputs and artifacts"
    location: src/squadron/cli/commands/review.py:315
---

# Review: code — slice 303

**Verdict:** CONCERNS
**Model:** moonshotai/kimi-k2.6

## Findings

### [CONCERN] Executor couples concretely to PhaseStepType for artifact post-condition

The generic executor imports `PhaseStepType` and performs an `isinstance(step_type_impl, PhaseStepType)` check inside `_execute_step_once` to decide whether to validate dispatch artifacts. This violates Open/Closed and Dependency Inversion: adding a new step type that produces artifacts would require editing the executor. Prefer a structural check (e.g., `getattr(step_type_impl, "expected_artifact_kind", None)`) or a small protocol so any step type can opt into post-condition validation without the executor knowing its concrete class.

### [CONCERN] ActionResult mutated in place after action execution

In `_execute_step_once`, when a dispatch artifact post-condition fails, the code mutates the returned `ActionResult` in place (`result.success = False; result.error = artifact_error`). This assumes the result object is mutable and breaks the expectation that a returned result is a.snapshot. If `ActionResult` ever becomes frozen or adds validation logic, this will raise at runtime. Prefer constructing a new `ActionResult` with the error state instead of mutating the action's return value.

### [CONCERN] Magic fallback string "unknown" hardcoded in multiple modules

The placeholder string `"unknown"` is duplicated as a fallback in `context_forge.py` (line ~172), `cli/commands/review.py` (line ~506), and `review/persistence.py` (line ~132). Per CLAUDE.md conventions, values used as defaults should not be hard-coded in multiple places. Extract a single constant (e.g., `UNKNOWN_PROJECT = "unknown"`) or centralize unknown-state handling so the placeholder is defined once and referenced everywhere.

### [CONCERN] Unchecked assumption that RunState.started_at is timezone-aware

Inside `_execute_step_once`, `run_started_at` is loaded from `StateManager.load(run_id).started_at` and later compared against `datetime.fromtimestamp(full_path.stat().st_mtime, tz=UTC)` in `_check_dispatch_artifact_written`. If `StateManager` ever yields a naive datetime, this comparison raises an uncaught `TypeError`. The executor should normalize `run_started_at` to UTC explicitly or guard against naive datetimes before comparison to prevent latent crashes if the state serialization format changes.

### [PASS] Comprehensive fail-fast guards and failure-mode enumeration for missing inputs and artifacts

Both issue #18 (file-existence validation via `missing_input_files`) and issue #15 (dispatch artifact post-conditions via `_check_dispatch_artifact_written`) are implemented with early failure, distinct warning-logged error messages for every identified failure mode, and extensive unit tests covering missing files, stale artifacts, unresolvable slices, permission errors, and non-numeric parameters. This is exactly the kind of observable, fail-fast behavior the standards require.

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
- Every finding MUST include a `location:` tag on its own line immediately
  after the title. This applies to PASS findings too.

Choosing the `location:` value (use the most specific form you can verify):
1. `path:line` or `path:start-end` — preferred when you can pin the issue
   to a specific line or range in a file under review.
2. `path#symbol` — when the issue is at a named function/class/method but
   a precise line is awkward.
3. `path` — when the issue spans the whole file.
4. `unverified` — the explicit "I don't know" token. Use this when you
   cannot pin the finding to a specific path you are certain exists in
   the code under review. **A hallucinated path is worse than
   `unverified`** because it looks authoritative; the parser will normalize
   missing/blank/`-`/`global` to `unverified` automatically.

For multi-file findings: cite the primary location in `location:` and
describe the others in the prose body. The `location:` field is the
primary anchor for deduplication, not a complete listing.

Report your findings using severity levels:

## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
location: <path:line | path:start-end | path#symbol | path | unverified>
Description with specific file and line references in prose.


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

- **Failure-Mode Enumeration:** For each new I/O path or message type, the author must be able to answer: "What if this hangs? What if it times out? What if the peer disconnects mid-send?" — explicitly, not implicitly. Each identified failure mode must be *observable* (log at WARNING+ or metric increment), not silent. At least one test should assert the failure mode produces the expected observable signal. Silent failure paths are bugs in waiting.

---

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

- **Failure-Mode Enumeration:** For each new I/O path or message type, the author must be able to answer: "What if this hangs? What if it times out? What if the peer disconnects mid-send?" — explicitly, not implicitly. Each identified failure mode must be *observable* (log at WARNING+ or metric increment), not silent. At least one test should assert the failure mode produces the expected observable signal. Silent failure paths are bugs in waiting.

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
* When starting or auditing a Python project, verify the required tooling configuration blocks defined in this guide (ruff, pyright) are present in `pyproject.toml`. If missing, add them before proceeding with substantive work. Mechanical enforcement is what makes these rules real; prose without config is aspirational.

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
- Required ruff configuration: every project MUST have a `[tool.ruff.lint]` block in `pyproject.toml` selecting at minimum `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`. `BLE` (blind-except) and `ASYNC` (async correctness) mechanically enforce the exception-handling and event-loop-discipline rules elsewhere in this guide. Copy-paste baseline:

    ```toml
    [tool.ruff]
    line-length = 88

    [tool.ruff.lint]
    select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]
    ```

- Use descriptive variable names; avoid single letters (except `x`, `i` in short loops/comprehensions).
- Prefer `f-strings` exclusively; avoid `.format()` or `%`.
- Use `pathlib` and its `Path` for all file/path operations, not `os.path.join` or similar
- One class per file for models/services; group related tiny utilities in `utils.py` or specific modules.

#### Functions & Error Handling
- Small, single-purpose functions (max 20 lines preferred)
- Use early returns (`guard clauses`) to flatten nesting.
- Explicit exception handling: catch specific exception types (`ValueError`, `KeyError`), never bare `except:` and never `except Exception: pass`. Every `try/except` must either (a) re-raise after logging at ERROR level via `logger.exception`, (b) handle a specific exception type with an inline comment justifying why swallowing is correct (e.g., `except ConnectionClosed: pass` for normal socket teardown), or (c) be a documented top-level handler at a process boundary. Swallowed exceptions are bugs by default; the `BLE` ruff rule set enforces this mechanically.
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
- Load-test tier (`tests/load/`): any code on the simulation, network, concurrency, or environment-layer paths requires at least one load test exercising a realistic configuration. Load tests assert on latency, throughput, or resource bounds — not just functional correctness. Unit and integration tests cannot catch event-loop starvation, contention, or budget overruns; load tests can. CI must gate load tests for slices touching these paths.
- Static Analysis: Strict `pyright` (preferred) or `mypy` — zero errors is a merge blocker, not a TODO. Required `[tool.pyright]` configuration:

    ```toml
    [tool.pyright]
    include = ["src", "tests"]
    pythonVersion = "3.12"
    typeCheckingMode = "strict"
    reportMissingImports = true
    reportMissingTypeStubs = false
    ```

    Test code is included in strict checking because bugs in tests can mask bugs in code. Adjust `pythonVersion` to match the project target.
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
- Any async def function that calls synchronous code must guarantee that the synchronous code runs in <1ms in the worst case. Anything CPU-bound must use run_in_executor, a dedicated thread, or a subprocess. Violating this blocks ALL I/O on the loop. Reviewers MUST verify this for any code that runs inside await-able functions.

#### Concurrency & Shared State
- Identify every access to shared mutable state. No read-during-mutate races between coroutines or between coroutines and executor threads.
- When state is published across thread or process boundaries, document the publication mechanism (`asyncio.Event`, sequence number, lock-free buffer, queue, etc.). Implicit publication via attribute assignment is not acceptable across boundaries.
- Introducing an executor (`run_in_executor`, `ProcessPoolExecutor`, threads) requires explicit review of every piece of state the executed code touches.

#### Security & Best Practices
- Secrets: Never commit secrets. Use `.env` files (loaded via `pydantic-settings`).
- Input: Validate everything entering the system via Pydantic.
- SQL: Always use parameterized queries (never f-string SQL).
- Randomness: Use `secrets` module for security tokens, `random` only for simulations.

### User Prompt

Review code in the project at: /Users/manta/source/repos/manta/squadron

Run `git diff cbea86b^..7e3458d -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/project-documents/ai-project-guide b/project-documents/ai-project-guide
index 798f51a..67d0df2 160000
--- a/project-documents/ai-project-guide
+++ b/project-documents/ai-project-guide
@@ -1 +1 @@
-Subproject commit 798f51a5dde6e4e0d3d1aa33fff90a04b51d1b83
+Subproject commit 67d0df229427321f2eccb3277f2784dddd849589
diff --git a/src/squadron/cli/commands/review.py b/src/squadron/cli/commands/review.py
index eaca054..72ef951 100644
--- a/src/squadron/cli/commands/review.py
+++ b/src/squadron/cli/commands/review.py
@@ -4,6 +4,7 @@ from __future__ import annotations
 
 import asyncio
 import json
+import logging
 from pathlib import Path
 
 import typer
@@ -23,6 +24,7 @@ from squadron.models.aliases import resolve_model_alias
 from squadron.review.git_utils import find_git_root, resolve_slice_diff_range
 from squadron.review.models import ReviewResult, Severity, Verdict
 from squadron.review.persistence import (
+    TASKS_DIR,
     SliceInfo,
     resolve_slice_info,
     save_review_result,
@@ -33,6 +35,7 @@ from squadron.review.rules import (
     load_review_rules,
     resolve_rules_dir,
 )
+from squadron.review.template_inputs import missing_input_files
 from squadron.review.templates import (
     ReviewTemplate,
     get_template,
@@ -40,6 +43,8 @@ from squadron.review.templates import (
     load_all_templates,
 )
 
+_logger = logging.getLogger(__name__)
+
 review_app = typer.Typer(
     name="review",
     help="Run review workflows using built-in templates.",
@@ -307,6 +312,13 @@ def _run_review_command(
             )
             raise typer.Exit(code=1)
 
+    # input/against must name real files — a stale or mistyped path would
+    # otherwise reach the model with its content silently absent, and the
+    # model reviews a document it never saw (issue #18).
+    for key, value in missing_input_files(inputs):
+        rprint(f"[red]Error: {key} file not found: {value}[/red]")
+        raise typer.Exit(code=1)
+
     # Prepend template-specific rules (review.md / review-{template}.md).
     # Language auto-detection is handled by the caller (review_code) where
     # file paths are known; _run_review_command only sees the template.
@@ -490,6 +502,11 @@ def review_arch(
             if "." in Path(input_file).stem
             else Path(input_file).stem
         )
+        try:
+            project_name = ContextForgeClient().get_project().name
+        except (ContextForgeNotAvailable, ContextForgeError) as exc:
+            _logger.warning("Could not resolve project name from ContextForge: %s", exc)
+            project_name = "unknown"
         arch_slice_info = SliceInfo(
             index=arch_index,
             name=arch_name,
@@ -497,6 +514,7 @@ def review_arch(
             design_file=None,
             task_files=[],
             arch_file=input_file,
+            project=project_name,
         )
         path = save_review_result(
             result, "arch", arch_slice_info, as_json=use_json, input_file=input_file
@@ -543,7 +561,7 @@ def review_tasks(
         if not slice_info["design_file"]:
             rprint(f"[red]Error: No design file for slice {slice_info['index']}.[/red]")
             raise typer.Exit(code=1)
-        task_file_paths = [f"project-documents/user/tasks/{f}" for f in slice_info["task_files"]]
+        task_file_paths = [str(TASKS_DIR / f) for f in slice_info["task_files"]]
         against = slice_info["design_file"]
     else:
         task_file_paths = [input_file]
@@ -644,6 +662,16 @@ def review_code(
             resolved_cwd_for_diff = _resolve_cwd(cwd)
             diff = resolve_slice_diff_range(int(slice_number), resolved_cwd_for_diff)
 
+    if not slice_info and not diff and not files:
+        if slice_number is not None:
+            rprint(
+                f"[red]Error: slice number '{slice_number}' is not numeric; "
+                "provide a numeric slice, --diff, or --files.[/red]"
+            )
+        else:
+            rprint("[red]Error: provide a slice number, --diff, or --files.[/red]")
+        raise typer.Exit(code=1)
+
     if use_json:
         output = "json"
 
diff --git a/src/squadron/cli/commands/run.py b/src/squadron/cli/commands/run.py
index f1708da..754c21d 100644
--- a/src/squadron/cli/commands/run.py
+++ b/src/squadron/cli/commands/run.py
@@ -223,6 +223,7 @@ async def _run_pipeline(
             sdk_session=sdk_session,  # type: ignore[arg-type]
             pool_policy=pool_policy,
             on_step_complete=state_mgr.make_step_callback(run_id),
+            runs_dir=runs_dir,
             _action_registry=_action_registry,
         )
     except BaseException:
diff --git a/src/squadron/integrations/context_forge.py b/src/squadron/integrations/context_forge.py
index 0b8d5ae..070872e 100644
--- a/src/squadron/integrations/context_forge.py
+++ b/src/squadron/integrations/context_forge.py
@@ -56,6 +56,7 @@ class ProjectInfo:
     slice_plan: str
     phase: str
     slice: str
+    name: str
 
 
 # ---------------------------------------------------------------------------
@@ -167,4 +168,5 @@ class ContextForgeClient:
             slice_plan=str(data.get("fileSlicePlan", "")),
             phase=str(data.get("developmentPhase", "")),
             slice=slice_index,
+            name=str(data.get("name") or "unknown"),
         )
diff --git a/src/squadron/pipeline/actions/review.py b/src/squadron/pipeline/actions/review.py
index e1dbf20..f97c79d 100644
--- a/src/squadron/pipeline/actions/review.py
+++ b/src/squadron/pipeline/actions/review.py
@@ -24,7 +24,7 @@ from squadron.review.rules import (
     load_review_rules,
     resolve_rules_dir,
 )
-from squadron.review.template_inputs import resolve_template_inputs
+from squadron.review.template_inputs import missing_input_files, resolve_template_inputs
 from squadron.review.templates import ReviewTemplate, get_template, load_all_templates
 
 _logger = logging.getLogger(__name__)
@@ -108,10 +108,21 @@ class ReviewAction:
         if template is None:
             raise KeyError(f"Review template '{template_name}' not found")
 
-        # Model resolution — same pattern as dispatch
+        # Model resolution — same pattern as dispatch, with one addition: when
+        # the standard cascade (CLI/action/step/pipeline/config) is entirely
+        # empty, fall back to the template's own `model:` default — the same
+        # fallback `sq review` already applies via its CLI-side cascade
+        # (cli/commands/review.py:_resolve_model). Without this, a judge
+        # template's declared default model is silently unreachable from any
+        # pipeline `review:` step.
         action_model = str(context.params["model"]) if "model" in context.params else None
         step_model = str(context.params["step_model"]) if "step_model" in context.params else None
-        model_id, alias_profile = context.resolver.resolve(action_model, step_model)
+        try:
+            model_id, alias_profile = context.resolver.resolve(action_model, step_model)
+        except ModelResolutionError:
+            if template.model is None:
+                raise
+            model_id, alias_profile = context.resolver.resolve(template.model, step_model)
 
         # Profile resolution — explicit param → alias-derived → SDK default
         profile_name = (
@@ -147,6 +158,18 @@ class ReviewAction:
                 f"created the expected file."
             )
 
+        # input/against must name real files — a stale path would otherwise
+        # reach the model with its content silently absent, and the model
+        # reviews a document it never saw (issue #18).
+        not_found = missing_input_files(inputs)
+        if not_found:
+            details = ", ".join(f"{key}={value}" for key, value in not_found)
+            raise KeyError(
+                f"Review template '{template_name}' input file(s) not "
+                f"found: {details}. The prior step may not have created "
+                f"the expected file."
+            )
+
         # Rules content — mirror CLI: template rules + language auto-detection,
         # layered on any explicit rules_content passed in via params.
         manual_rules = (
@@ -182,6 +205,23 @@ class ReviewAction:
             rules_content=rules_content,
         )
 
+        # Judge enforcement runs before persistence: judge templates instruct
+        # the model to omit a verdict line (score is the source of truth), so
+        # result.verdict is always UNKNOWN for them. The persisted file must
+        # show the threshold-derived verdict instead, not the always-empty
+        # raw parse.
+        if template.is_judge:
+            judge_override = context.params.get("judge")
+            step_override = (
+                cast(dict[str, object], judge_override) if isinstance(judge_override, dict) else None
+            )
+            thresholds = resolve_thresholds(template.judge, step_override)
+            verdict, provenance = enforce_judge(result, thresholds, template_name, _logger)
+            verdict_override = verdict
+        else:
+            verdict, provenance = result.verdict.value, Provenance.REVIEW
+            verdict_override = None
+
         # File persistence (non-fatal).
         # When slice_info is available, use save_review_result for correct
         # naming (e.g. 154-review.slice.prompt-only-loops.md). Otherwise
@@ -195,11 +235,15 @@ class ReviewAction:
                         template_name,
                         slice_info,
                         input_file=inputs.get("input"),
+                        verdict_override=verdict_override,
                     )
                 )
             else:
                 md_content = format_review_markdown(
-                    result, template_name, source_document=inputs.get("input")
+                    result,
+                    template_name,
+                    source_document=inputs.get("input"),
+                    verdict_override=verdict_override,
                 )
                 path = save_review_file(
                     md_content,
@@ -221,16 +265,6 @@ class ReviewAction:
         if review_file_path is not None:
             outputs["review_file"] = review_file_path
 
-        if template.is_judge:
-            judge_override = context.params.get("judge")
-            step_override = (
-                cast(dict[str, object], judge_override) if isinstance(judge_override, dict) else None
-            )
-            thresholds = resolve_thresholds(template.judge, step_override)
-            verdict, provenance = enforce_judge(result, thresholds, template_name, _logger)
-        else:
-            verdict, provenance = result.verdict.value, Provenance.REVIEW
-
         return ActionResult(
             success=True,
             action_type=self.action_type,
diff --git a/src/squadron/pipeline/executor.py b/src/squadron/pipeline/executor.py
index 411618d..3a6f562 100644
--- a/src/squadron/pipeline/executor.py
+++ b/src/squadron/pipeline/executor.py
@@ -17,7 +17,9 @@ import sys
 import uuid
 from collections.abc import Awaitable, Callable
 from dataclasses import dataclass
+from datetime import UTC, datetime
 from enum import StrEnum
+from pathlib import Path
 from typing import TYPE_CHECKING, Any, cast
 
 from squadron.pipeline.classification import (
@@ -26,8 +28,10 @@ from squadron.pipeline.classification import (
 )
 from squadron.pipeline.models import ActionContext, ActionResult, PipelineDefinition
 from squadron.pipeline.steps import StepTypeName
+from squadron.pipeline.steps.phase import ArtifactKind, PhaseStepType
 from squadron.pipeline.steps.utils import unpack_inner_steps
 from squadron.pipeline.summary_render import gather_cf_params
+from squadron.review.persistence import TASKS_DIR, CfClientProtocol, resolve_slice_info
 
 if TYPE_CHECKING:
     from squadron.integrations.context_forge import ContextForgeClient
@@ -102,6 +106,113 @@ def _log_action_result(action_type: str, result: ActionResult) -> None:
     _logger.debug("    outputs=%s metadata=%s", result.outputs, result.metadata)
 
 
+def _expected_artifact_paths(
+    kind: ArtifactKind, slice_index: int, cf_client: CfClientProtocol
+) -> list[str]:
+    """Resolve the expected artifact path(s) for a phase's artifact kind.
+
+    Raises:
+        ValueError, TypeError: If the slice cannot be resolved via CF —
+            propagated to the caller, which treats it as "path unresolvable".
+    """
+    info = resolve_slice_info(cf_client, slice_index)
+    if kind is ArtifactKind.DESIGN:
+        return [info["design_file"]] if info["design_file"] else []
+    return [str(TASKS_DIR / f) for f in info["task_files"]]
+
+
+def _check_dispatch_artifact_written(
+    *,
+    kind: ArtifactKind,
+    slice_index: int,
+    cf_client: CfClientProtocol,
+    cwd: str,
+    run_started_at: datetime,
+) -> str | None:
+    """Verify a phase-step dispatch wrote its expected artifact this run.
+
+    Returns None if the post-condition is satisfied, else an error message
+    naming the failure mode. Every failure mode fails closed (returns a
+    message) and is logged at WARNING — never a silent pass.
+    """
+    try:
+        paths = _expected_artifact_paths(kind, slice_index, cf_client)
+    except (ValueError, TypeError) as exc:
+        msg = f"could not resolve expected {kind.value} artifact path for slice {slice_index}: {exc}"
+        _logger.warning("dispatch post-condition: %s", msg)
+        return msg
+
+    if not paths:
+        msg = f"no {kind.value} artifact path registered for slice {slice_index}"
+        _logger.warning("dispatch post-condition: %s", msg)
+        return msg
+
+    base_dir = Path(cwd) if cwd else Path(".")
+    for rel_path in paths:
+        full_path = base_dir / rel_path
+        try:
+            if not full_path.exists():
+                continue
+            mtime = datetime.fromtimestamp(full_path.stat().st_mtime, tz=UTC)
+            if mtime >= run_started_at:
+                return None
+        except OSError as exc:
+            msg = f"could not verify {kind.value} artifact at {rel_path}: {exc}"
+            _logger.warning("dispatch post-condition: %s", msg)
+            return msg
+
+    msg = (
+        f"phase dispatch completed but no {kind.value} artifact was written "
+        f"for slice {slice_index} (expected one of: {', '.join(paths)})"
+    )
+    _logger.warning("dispatch post-condition: %s", msg)
+    return msg
+
+
+def _dispatch_artifact_post_condition_error(
+    *,
+    kind: ArtifactKind,
+    slice_param: object,
+    cf_client: CfClientProtocol,
+    cwd: str,
+    run_started_at: datetime | None,
+    run_state_error: str | None,
+) -> str | None:
+    """Resolve the dispatch artifact post-condition for one dispatch action.
+
+    Returns None if satisfied, else the failure message. Every branch fails
+    closed and is logged at WARNING (see docstrings on the helpers it calls).
+    """
+    if run_state_error is not None:
+        return run_state_error
+    if run_started_at is None:
+        # Only reachable if a future caller sets expected_kind without also
+        # resolving run_started_at/run_state_error — guards the invariant.
+        msg = "run start time unavailable"
+        _logger.warning("dispatch post-condition: %s", msg)
+        return msg
+    if slice_param is None:
+        msg = f"could not resolve expected {kind.value} artifact path: no 'slice' param in scope"
+        _logger.warning("dispatch post-condition: %s", msg)
+        return msg
+    try:
+        slice_index = int(str(slice_param))
+    except ValueError:
+        msg = (
+            f"could not resolve expected {kind.value} artifact path: "
+            f"'slice' param {slice_param!r} is not a numeric index"
+        )
+        _logger.warning("dispatch post-condition: %s", msg)
+        return msg
+    return _check_dispatch_artifact_written(
+        kind=kind,
+        slice_index=slice_index,
+        cf_client=cf_client,
+        cwd=cwd,
+        run_started_at=run_started_at,
+    )
+
+
 # ---------------------------------------------------------------------------
 # Result types and exceptions
 # ---------------------------------------------------------------------------
@@ -498,6 +609,7 @@ async def execute_pipeline(
     sdk_session: SDKExecutionSession | None = None,
     pool_policy: PoolClassificationPolicy = PoolClassificationPolicy.LAZY,
     on_step_complete: Callable[[StepResult], None] | None = None,
+    runs_dir: Path | None = None,
     _action_registry: dict[str, object] | None = None,
 ) -> PipelineResult:
     """Execute *definition* with the given *params*.
@@ -528,6 +640,12 @@ async def execute_pipeline(
         pipeline whose classification returned ``needs_persistent_session``.
     on_step_complete:
         Optional observer called after each step completes (any status).
+    runs_dir:
+        Directory where run state files live; forwarded to any internal
+        ``StateManager`` lookups (SDK-resume seeding, dispatch artifact
+        post-condition). Defaults to ``StateManager``'s own default location
+        when not provided — must match the ``runs_dir`` used to create
+        *run_id*'s state file, or those lookups will not find it.
     _action_registry:
         Internal override for testing; uses the global action registry by default.
     """
@@ -602,7 +720,7 @@ async def execute_pipeline(
         try:
             from squadron.pipeline.state import StateManager
 
-            _state_mgr = StateManager()
+            _state_mgr = StateManager(runs_dir=runs_dir)
             _run_state = _state_mgr.load(effective_run_id)
             _start_idx = next(
                 (i for i, s in enumerate(definition.steps) if s.name == start_from),
@@ -660,6 +778,7 @@ async def execute_pipeline(
                 sdk_session=sdk_session,
                 get_step_type_fn=get_step_type,
                 get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
+                runs_dir=runs_dir,
             )
         elif step.step_type == StepTypeName.FAN_OUT:
             step_result = await _execute_fan_out_step(
@@ -676,6 +795,7 @@ async def execute_pipeline(
                 sdk_session=sdk_session,
                 get_step_type_fn=get_step_type,
                 get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
+                runs_dir=runs_dir,
             )
         elif step.step_type == StepTypeName.LOOP:
             step_result = await _execute_loop_body(
@@ -692,6 +812,7 @@ async def execute_pipeline(
                 sdk_session=sdk_session,
                 get_step_type_fn=get_step_type,
                 get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
+                runs_dir=runs_dir,
             )
         else:
             # Check for loop config
@@ -716,6 +837,7 @@ async def execute_pipeline(
                     sdk_session=sdk_session,
                     get_step_type_fn=get_step_type,
                     get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
+                    runs_dir=runs_dir,
                 )
             else:
                 step_result = await _execute_step_once(
@@ -732,6 +854,7 @@ async def execute_pipeline(
                     sdk_session=sdk_session,
                     get_step_type_fn=get_step_type,
                     get_action_fn=_action_registry.__getitem__ if _action_registry else get_action,
+                    runs_dir=runs_dir,
                 )
 
         step_results.append(step_result)
@@ -853,6 +976,7 @@ async def _execute_step_once(
     get_step_type_fn: Any,
     get_action_fn: Any,
     iteration: int = 0,
+    runs_dir: Path | None = None,
 ) -> StepResult:
     """Execute a single step's action sequence once. Returns a StepResult."""
     step_type_impl = get_step_type_fn(step.step_type)
@@ -865,6 +989,26 @@ async def _execute_step_once(
         len(actions),
     )
 
+    # Loaded once per step (not per-action) — only needed when this step is a
+    # PhaseStepType with a non-None expected_artifact_kind, checked below.
+    # A missing/corrupt state file is itself a "cannot confirm" condition
+    # (fails closed below, at the dispatch post-condition check) rather than
+    # an uncaught crash — e.g. execute_pipeline invoked directly without a
+    # prior StateManager().init_run() (as some tests and tooling do).
+    run_started_at: datetime | None = None
+    run_state_error: str | None = None
+    expected_kind = (
+        step_type_impl.expected_artifact_kind if isinstance(step_type_impl, PhaseStepType) else None
+    )
+    if expected_kind is not None:
+        from squadron.pipeline.state import StateManager
+
+        try:
+            run_started_at = StateManager(runs_dir=runs_dir).load(run_id).started_at
+        except (FileNotFoundError, ValueError) as exc:
+            run_state_error = f"could not load run state for run_id={run_id!r}: {exc}"
+            _logger.warning("dispatch post-condition: %s", run_state_error)
+
     action_results: list[ActionResult] = []
     step_prior = dict(prior_outputs)  # snapshot; updated within step
 
@@ -899,6 +1043,25 @@ async def _execute_step_once(
 
         _log_action_result(action_type, result)
 
+        # Dispatch artifact post-condition (Part A, issue #15): a phase-step
+        # dispatch that completes without writing its expected artifact is
+        # not a success, regardless of what DispatchAction reported. Scoped
+        # to PhaseStepType steps with a non-None expected_artifact_kind;
+        # generic dispatch and no-artifact phases (e.g. implement) pass
+        # through unchecked.
+        if action_type == "dispatch" and result.success and expected_kind is not None:
+            artifact_error = _dispatch_artifact_post_condition_error(
+                kind=expected_kind,
+                slice_param=ctx.params.get("slice"),
+                cf_client=cf_client,
+                cwd=cwd,
+                run_started_at=run_started_at,
+                run_state_error=run_state_error,
+            )
+            if artifact_error is not None:
+                result.success = False
+                result.error = artifact_error
+
         # Update step_prior for next action in same step
         key = f"{action_type}-{action_index}"
         step_prior[key] = result
@@ -995,6 +1158,7 @@ async def _execute_loop_step(
     sdk_session: SDKExecutionSession | None = None,
     get_step_type_fn: Any,
     get_action_fn: Any,
+    runs_dir: Path | None = None,
 ) -> StepResult:
     """Execute a step with loop configuration."""
     if loop_config.strategy is not None:
@@ -1030,6 +1194,7 @@ async def _execute_loop_step(
             get_step_type_fn=get_step_type_fn,
             get_action_fn=get_action_fn,
             iteration=iteration,
+            runs_dir=runs_dir,
         )
         last_result = result
 
@@ -1078,6 +1243,7 @@ async def _execute_loop_body(
     sdk_session: SDKExecutionSession | None = None,
     get_step_type_fn: Any,
     get_action_fn: Any,
+    runs_dir: Path | None = None,
 ) -> StepResult:
     """Execute a ``loop:`` step type with a multi-step body.
 
@@ -1128,6 +1294,7 @@ async def _execute_loop_body(
                 get_step_type_fn=get_step_type_fn,
                 get_action_fn=get_action_fn,
                 iteration=iteration,
+                runs_dir=runs_dir,
             )
             iteration_action_results.extend(inner_result.action_results)
 
@@ -1186,6 +1353,7 @@ async def _execute_each_step(
     sdk_session: SDKExecutionSession | None = None,
     get_step_type_fn: Any,
     get_action_fn: Any,
+    runs_dir: Path | None = None,
 ) -> StepResult:
     """Execute an `each` collection step."""
     source_str = str(resolved_config.get("source", ""))
@@ -1233,6 +1401,7 @@ async def _execute_each_step(
                 sdk_session=sdk_session,
                 get_step_type_fn=get_step_type_fn,
                 get_action_fn=get_action_fn,
+                runs_dir=runs_dir,
             )
             all_action_results.extend(inner_result.action_results)
 
@@ -1274,6 +1443,7 @@ async def _execute_fan_out_step(
     sdk_session: SDKExecutionSession | None = None,
     get_step_type_fn: Any,
     get_action_fn: Any,
+    runs_dir: Path | None = None,
 ) -> StepResult:
     """Execute a ``fan_out`` step: dispatch N branches concurrently, then reduce.
 
@@ -1339,6 +1509,7 @@ async def _execute_fan_out_step(
             sdk_session=None,  # never propagate session into branches
             get_step_type_fn=get_step_type_fn,
             get_action_fn=get_action_fn,
+            runs_dir=runs_dir,
         )
 
     # 4. Gather branches — return_exceptions=False for fast-fail on exception.
diff --git a/src/squadron/pipeline/steps/phase.py b/src/squadron/pipeline/steps/phase.py
index 88498db..ace35ee 100644
--- a/src/squadron/pipeline/steps/phase.py
+++ b/src/squadron/pipeline/steps/phase.py
@@ -2,6 +2,7 @@
 
 from __future__ import annotations
 
+from enum import StrEnum
 from typing import cast
 
 from squadron.pipeline.actions.checkpoint import CheckpointTrigger
@@ -9,6 +10,20 @@ from squadron.pipeline.models import StepConfig, ValidationError
 from squadron.pipeline.steps import StepTypeName, register_step_type
 
 
+class ArtifactKind(StrEnum):
+    """The kind of artifact a phase step's dispatch is expected to write."""
+
+    DESIGN = "design"
+    TASKS = "tasks"
+
+
+_EXPECTED_ARTIFACT_KIND: dict[str, ArtifactKind | None] = {
+    StepTypeName.DESIGN: ArtifactKind.DESIGN,
+    StepTypeName.TASKS: ArtifactKind.TASKS,
+    StepTypeName.IMPLEMENT: None,
+}
+
+
 class PhaseStepType:
     """Step type for design, tasks, and implement phases.
 
@@ -24,6 +39,16 @@ class PhaseStepType:
     def step_type(self) -> str:
         return self._phase_name
 
+    @property
+    def expected_artifact_kind(self) -> ArtifactKind | None:
+        """The artifact kind this phase's dispatch is expected to write.
+
+        ``None`` means the phase has no single deterministic artifact (e.g.
+        ``implement``, which mutates arbitrary source) — the dispatch
+        artifact post-condition does not apply.
+        """
+        return _EXPECTED_ARTIFACT_KIND.get(self._phase_name)
+
     def validate(self, config: StepConfig) -> list[ValidationError]:
         errors: list[ValidationError] = []
         cfg = config.config
@@ -97,18 +122,24 @@ class PhaseStepType:
         cfg = config.config
         phase = cfg["phase"]
         model = cfg.get("model")
+        # Step config may set its own "slice" placeholder (e.g. "{slice.index}"
+        # inside an each-loop, where the loop's "as" variable binds a whole
+        # record rather than a scalar index). Prefer it over the bare
+        # "{slice}" default so per-action placeholder resolution reaches the
+        # loop item's .index field instead of stringifying the whole record.
+        slice_ref = cfg.get("slice", "{slice}")
 
         actions: list[tuple[str, dict[str, object]]] = [
             ("cf-op", {"operation": "set_phase", "phase": phase}),
-            ("cf-op", {"operation": "set_slice", "slice": "{slice}"}),
+            ("cf-op", {"operation": "set_slice", "slice": slice_ref}),
             ("cf-op", {"operation": "build_context"}),
-            ("dispatch", {"model": model}),
+            ("dispatch", {"model": model, "slice": slice_ref}),
         ]
 
         review = cfg.get("review")
         if review is not None:
             if isinstance(review, str):
-                actions.append(("review", {"template": review, "model": None, "slice": "{slice}"}))
+                actions.append(("review", {"template": review, "model": None, "slice": slice_ref}))
             elif isinstance(review, dict):
                 review_dict = cast(dict[str, object], review)
                 actions.append(
@@ -117,7 +148,7 @@ class PhaseStepType:
                         {
                             "template": review_dict["template"],
                             "model": review_dict.get("model"),
-                            "slice": "{slice}",
+                            "slice": slice_ref,
                         },
                     )
                 )
@@ -125,7 +156,7 @@ class PhaseStepType:
             checkpoint = cfg.get("checkpoint", CheckpointTrigger.NEVER)
             actions.append(("checkpoint", {"trigger": checkpoint}))
 
-        actions.append(("commit", {"message_prefix": f"phase-{phase}"}))
+        actions.append(("commit", {"message_prefix": f"phase-{phase}", "slice": slice_ref}))
 
         return actions
 
diff --git a/src/squadron/review/persistence.py b/src/squadron/review/persistence.py
index dad2b32..aa8019b 100644
--- a/src/squadron/review/persistence.py
+++ b/src/squadron/review/persistence.py
@@ -16,6 +16,11 @@ _logger = logging.getLogger(__name__)
 
 _REVIEWS_DIR = Path("project-documents/user/reviews")
 
+#: Directory prefix for task-breakdown files, relative to project root.
+#: SliceInfo["task_files"] entries are bare filenames — join with this to
+#: get the full relative path (mirrors _REVIEWS_DIR's role for reviews).
+TASKS_DIR = Path("project-documents/user/tasks")
+
 
 class SliceInfo(TypedDict):
     """Resolved slice metadata from Context-Forge."""
@@ -26,6 +31,7 @@ class SliceInfo(TypedDict):
     design_file: str | None
     task_files: list[str]
     arch_file: str
+    project: str
 
 
 class CfClientProtocol(Protocol):
@@ -73,6 +79,7 @@ def resolve_slice_info(cf_client: CfClientProtocol, index: int) -> SliceInfo:
         design_file=design_file,
         task_files=task_files,
         arch_file=arch_file,
+        project=project.name,
     )
 
 
@@ -87,6 +94,7 @@ def format_review_markdown(
     slice_info: SliceInfo | None = None,
     source_document: str | None = None,
     model: str | None = None,
+    verdict_override: str | None = None,
 ) -> str:
     """Format a ReviewResult as markdown with YAML frontmatter.
 
@@ -97,9 +105,17 @@ def format_review_markdown(
         source_document: Explicit source document path; falls back to
             ``slice_info["design_file"]`` when not provided.
         model: Explicit model name; falls back to ``result.model``.
+        verdict_override: Explicit verdict string; falls back to
+            ``result.verdict.value``. Judge templates deliberately omit a
+            verdict line from their raw output (the score is the source of
+            truth), so ``result.verdict`` is always ``UNKNOWN`` for them —
+            callers that have already derived a threshold-based verdict
+            (``enforce_judge``) pass it here so the persisted file shows the
+            real gating decision instead of the always-empty raw parse.
     """
     today = result.timestamp.strftime("%Y%m%d")
     resolved_model = model or result.model or "unknown"
+    resolved_verdict = verdict_override or result.verdict.value
 
     # Source document resolution
     if source_document is None and slice_info is not None:
@@ -109,6 +125,7 @@ def format_review_markdown(
     # Slice-derived fields
     slice_name = slice_info["slice_name"] if slice_info else "unknown"
     slice_index = slice_info["index"] if slice_info else 0
+    project_name = slice_info["project"] if slice_info else "unknown"
 
     lines = [
         "---",
@@ -116,8 +133,8 @@ def format_review_markdown(
         "layer: project",
         f"reviewType: {review_type}",
         f"slice: {slice_name}",
-        "project: squadron",
-        f"verdict: {result.verdict.value}",
+        f"project: {project_name}",
+        f"verdict: {resolved_verdict}",
         f"sourceDocument: {source_doc}",
         f"aiModel: {resolved_model}",
         "status: complete",
@@ -149,7 +166,7 @@ def format_review_markdown(
     lines.append("")
     lines.append(f"# Review: {review_type} — slice {slice_index}")
     lines.append("")
-    lines.append(f"**Verdict:** {result.verdict.value}")
+    lines.append(f"**Verdict:** {resolved_verdict}")
     lines.append(f"**Model:** {resolved_model}")
     lines.append("")
 
@@ -239,6 +256,7 @@ def save_review_result(
     reviews_dir: Path | None = None,
     input_file: str | None = None,
     name_suffix: str | None = None,
+    verdict_override: str | None = None,
 ) -> Path:
     """Save a ReviewResult to the reviews directory (CLI compatibility).
 
@@ -251,6 +269,10 @@ def save_review_result(
     ``-1.md`` / ``-2.md`` each get their own review). For example,
     passing ``name_suffix="part-1"`` yields
     ``161-review.tasks.summary-step.part-1.md``.
+
+    ``verdict_override`` is forwarded to ``format_review_markdown`` — see
+    its docstring. Ignored for ``as_json`` output, which persists the raw
+    ``ReviewResult`` unchanged.
     """
     target = reviews_dir or _REVIEWS_DIR
     target.mkdir(parents=True, exist_ok=True)
@@ -265,7 +287,13 @@ def save_review_result(
     else:
         path = target / f"{base}.md"
         path.write_text(
-            format_review_markdown(result, review_type, slice_info, source_document=input_file)
+            format_review_markdown(
+                result,
+                review_type,
+                slice_info,
+                source_document=input_file,
+                verdict_override=verdict_override,
+            )
         )
 
     return path
diff --git a/src/squadron/review/review_client.py b/src/squadron/review/review_client.py
index eeaf752..9b6f9b6 100644
--- a/src/squadron/review/review_client.py
+++ b/src/squadron/review/review_client.py
@@ -21,6 +21,7 @@ from squadron.providers.profiles import get_profile
 from squadron.providers.registry import get_provider
 from squadron.review.models import ReviewResult
 from squadron.review.parsers import parse_review_output
+from squadron.review.template_inputs import FILE_INPUT_KEYS
 from squadron.review.templates import ReviewTemplate
 
 _logger = logging.getLogger(__name__)
@@ -248,6 +249,16 @@ def _inject_file_contents(
 
         path = Path(value)
         if not path.is_file():
+            # input/against are always document paths; skipping one means
+            # the model reviews a document it never saw (issue #18). The
+            # CLI/pipeline boundaries hard-fail first — this is the last
+            # observable signal for direct callers that bypass them.
+            if key in FILE_INPUT_KEYS:
+                _logger.warning(
+                    "Review input '%s' file not found, content not injected: %s",
+                    key,
+                    value,
+                )
             continue
 
         try:
diff --git a/src/squadron/review/template_inputs.py b/src/squadron/review/template_inputs.py
index b4f4fdb..7cd4751 100644
--- a/src/squadron/review/template_inputs.py
+++ b/src/squadron/review/template_inputs.py
@@ -10,9 +10,15 @@ from __future__ import annotations
 
 from collections.abc import Callable
 from dataclasses import dataclass
+from pathlib import Path
 
 from squadron.review.git_utils import resolve_slice_diff_range
-from squadron.review.persistence import SliceInfo
+from squadron.review.persistence import TASKS_DIR, SliceInfo
+
+#: Review input keys whose values are document paths that must exist on disk
+#: for the review to be grounded. Other keys (diff refs, file globs, cwd)
+#: have their own resolution logic and are not plain file paths.
+FILE_INPUT_KEYS = ("input", "against")
 
 
 @dataclass(frozen=True)
@@ -34,7 +40,7 @@ def _arch_file(info: SliceInfo, _cwd: str) -> str | None:
 def _tasks_input(info: SliceInfo, _cwd: str) -> str | None:
     if not info["task_files"]:
         return None
-    return f"project-documents/user/tasks/{info['task_files'][0]}"
+    return str(TASKS_DIR / info["task_files"][0])
 
 
 def _diff_range(info: SliceInfo, cwd: str) -> str | None:
@@ -67,6 +73,27 @@ TEMPLATE_INPUTS: dict[str, list[TemplateInputSpec]] = {
 }
 
 
+def missing_input_files(inputs: dict[str, str]) -> list[tuple[str, str]]:
+    """Return (key, path) pairs for ``FILE_INPUT_KEYS`` that name no real file.
+
+    A path counts as present when it resolves relative to the process cwd
+    (how content injection reads it) or relative to ``inputs["cwd"]`` (how
+    SDK review agents read it). Callers treat a non-empty result as a hard
+    error: a review whose input document is silently absent from the prompt
+    produces a fabricated verdict instead of a failure (issue #18).
+    """
+    cwd = Path(inputs.get("cwd", "."))
+    missing: list[tuple[str, str]] = []
+    for key in FILE_INPUT_KEYS:
+        value = inputs.get(key)
+        if value is None:
+            continue
+        if Path(value).is_file() or (cwd / value).is_file():
+            continue
+        missing.append((key, value))
+    return missing
+
+
 def resolve_template_inputs(
     template_name: str,
     info: SliceInfo,
diff --git a/tests/cli/test_review_format.py b/tests/cli/test_review_format.py
index 9b20770..fc268c3 100644
--- a/tests/cli/test_review_format.py
+++ b/tests/cli/test_review_format.py
@@ -25,6 +25,7 @@ SLICE_INFO: SliceInfo = {
     "design_file": ("project-documents/user/slices/143-slice.structured-review-findings.md"),
     "task_files": ["143-tasks.structured-review-findings.md"],
     "arch_file": ("project-documents/user/architecture/140-arch.pipeline-foundation.md"),
+    "project": "squadron",
 }
 
 
diff --git a/tests/cli/test_review_profile.py b/tests/cli/test_review_profile.py
index 6482f45..e16f302 100644
--- a/tests/cli/test_review_profile.py
+++ b/tests/cli/test_review_profile.py
@@ -2,6 +2,8 @@
 
 from __future__ import annotations
 
+from pathlib import Path
+
 import pytest
 
 from squadron.cli.commands.review import _resolve_profile
@@ -25,6 +27,14 @@ def _make_template(profile: str | None = None, model: str | None = None) -> Revi
     )
 
 
+@pytest.fixture
+def doc_inputs(tmp_path: Path) -> dict[str, str]:
+    """Real input/against docs for _run_review_command (issue #18 guard)."""
+    (tmp_path / "f.md").write_text("# f\n")
+    (tmp_path / "a.md").write_text("# a\n")
+    return {"input": "f.md", "against": "a.md", "cwd": str(tmp_path)}
+
+
 class TestResolveProfile:
     """Test _resolve_profile() resolution chain."""
 
@@ -81,7 +91,7 @@ class TestCLIProfileFlag:
     """Test --profile flag wiring through CLI commands."""
 
     def test_run_review_command_passes_profile_to_execute(
-        self, monkeypatch: pytest.MonkeyPatch
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
     ) -> None:
         """Verify _run_review_command passes profile through."""
         from unittest.mock import AsyncMock, patch
@@ -119,7 +129,7 @@ class TestCLIProfileFlag:
         ) as mock_exec:
             _run_review_command(
                 "arch",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
@@ -131,7 +141,9 @@ class TestCLIProfileFlag:
         call_args = mock_exec.call_args
         assert call_args[1].get("profile") or call_args[0][4] == "openrouter"
 
-    def test_run_review_command_defaults_to_sdk(self, monkeypatch: pytest.MonkeyPatch) -> None:
+    def test_run_review_command_defaults_to_sdk(
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
+    ) -> None:
         """Without --profile, profile defaults to sdk."""
         from unittest.mock import AsyncMock, patch
 
@@ -167,7 +179,7 @@ class TestCLIProfileFlag:
         ) as mock_exec:
             _run_review_command(
                 "arch",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
@@ -177,7 +189,9 @@ class TestCLIProfileFlag:
         call_args = mock_exec.call_args
         assert call_args[0][4] == "sdk"
 
-    def test_profile_and_model_passed_together(self, monkeypatch: pytest.MonkeyPatch) -> None:
+    def test_profile_and_model_passed_together(
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
+    ) -> None:
         """--profile and --model should both be forwarded."""
         from unittest.mock import AsyncMock, patch
 
@@ -213,7 +227,7 @@ class TestCLIProfileFlag:
         ) as mock_exec:
             _run_review_command(
                 "arch",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
@@ -230,7 +244,9 @@ class TestCLIProfileFlag:
 class TestAliasWiring:
     """Test alias resolution wiring in _run_review_command()."""
 
-    def test_alias_resolves_model_and_profile(self, monkeypatch: pytest.MonkeyPatch) -> None:
+    def test_alias_resolves_model_and_profile(
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
+    ) -> None:
         """gpt54-nano alias resolves to gpt-5.4-nano on openai."""
         from unittest.mock import AsyncMock, patch
 
@@ -260,7 +276,7 @@ class TestAliasWiring:
         ) as mock_exec:
             _run_review_command(
                 "slice",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
@@ -271,7 +287,9 @@ class TestAliasWiring:
         assert call_args[0][3] == "gpt-5.4-nano"  # resolved model
         assert call_args[0][4] == "openai"  # resolved profile
 
-    def test_unknown_model_passes_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
+    def test_unknown_model_passes_through(
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
+    ) -> None:
         """Unknown model passes through unchanged, profile falls to sdk."""
         from unittest.mock import AsyncMock, patch
 
@@ -301,7 +319,7 @@ class TestAliasWiring:
         ) as mock_exec:
             _run_review_command(
                 "slice",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
@@ -312,7 +330,9 @@ class TestAliasWiring:
         assert call_args[0][3] == "llama-3-70b"  # unchanged
         assert call_args[0][4] == "sdk"  # default fallback
 
-    def test_explicit_profile_overrides_alias(self, monkeypatch: pytest.MonkeyPatch) -> None:
+    def test_explicit_profile_overrides_alias(
+        self, monkeypatch: pytest.MonkeyPatch, doc_inputs: dict[str, str]
+    ) -> None:
         """Explicit --profile flag overrides alias-inferred profile."""
         from unittest.mock import AsyncMock, patch
 
@@ -342,7 +362,7 @@ class TestAliasWiring:
         ) as mock_exec:
             _run_review_command(
                 "slice",
-                {"input": "f.md", "against": "a.md", "cwd": "."},
+                doc_inputs,
                 "terminal",
                 None,
                 0,
diff --git a/tests/cli/test_review_resolve.py b/tests/cli/test_review_resolve.py
index 951db9f..64f1743 100644
--- a/tests/cli/test_review_resolve.py
+++ b/tests/cli/test_review_resolve.py
@@ -43,6 +43,7 @@ PROJECT_INFO = ProjectInfo(
     slice_plan="100-slices.orchestration-v2",
     phase="Phase 6: Implementation",
     slice="118-slice.composed-workflows",
+    name="squadron",
 )
 
 
diff --git a/tests/cli/test_review_save.py b/tests/cli/test_review_save.py
index 8306623..93aa5a6 100644
--- a/tests/cli/test_review_save.py
+++ b/tests/cli/test_review_save.py
@@ -54,6 +54,7 @@ SLICE_INFO: SliceInfo = {
     "design_file": ("project-documents/user/slices/118-slice.composed-workflows.md"),
     "task_files": ["118-tasks.composed-workflows.md"],
     "arch_file": ("project-documents/user/architecture/100-arch.orchestration-v2.md"),
+    "project": "squadron",
 }
 
 
diff --git a/tests/integrations/test_context_forge.py b/tests/integrations/test_context_forge.py
index 4e9d04c..3c7f2ac 100644
--- a/tests/integrations/test_context_forge.py
+++ b/tests/integrations/test_context_forge.py
@@ -149,6 +149,7 @@ class TestListTasks:
 # ---------------------------------------------------------------------------
 
 _PROJECT_JSON = {
+    "name": "squadron",
     "fileArch": "100-arch.orchestration-v2",
     "fileSlicePlan": "100-slices.orchestration-v2",
     "developmentPhase": "Phase 6: Implementation",
@@ -205,3 +206,20 @@ class TestGetProject:
         ):
             info = ContextForgeClient().get_project()
             assert info.arch_file == "custom/path/arch.md"
+
+    def test_get_project_name_populated(self) -> None:
+        with patch(
+            "subprocess.run",
+            return_value=_mock_completed(json.dumps(_PROJECT_JSON)),
+        ):
+            info = ContextForgeClient().get_project()
+            assert info.name == "squadron"
+
+    def test_get_project_name_falls_back_to_unknown_when_absent(self) -> None:
+        data = {k: v for k, v in _PROJECT_JSON.items() if k != "name"}
+        with patch(
+            "subprocess.run",
+            return_value=_mock_completed(json.dumps(data)),
+        ):
+            info = ContextForgeClient().get_project()
+            assert info.name == "unknown"
diff --git a/tests/pipeline/actions/test_review_action.py b/tests/pipeline/actions/test_review_action.py
index dbea7c6..fc0e388 100644
--- a/tests/pipeline/actions/test_review_action.py
+++ b/tests/pipeline/actions/test_review_action.py
@@ -85,6 +85,7 @@ def _mock_template() -> ReviewTemplate:
     mock.optional_inputs = []
     mock.judge = None
     mock.is_judge = False
+    mock.model = None
     return mock
 
 
@@ -358,6 +359,40 @@ class TestReviewModelResolution:
         result = await ReviewAction().execute(ctx)
         assert result.metadata["profile"] == ProfileName.SDK
 
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_template_model_rescues_empty_cascade(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        """A judge template's own `model:` default (e.g. judge.slice-vs-arch's
+        `opus`) must be reachable when no pipeline/CLI/config level supplies
+        one — mirrors the fallback `sq review` already applies via its
+        CLI-side cascade (cli/commands/review.py:_resolve_model)."""
+        mock_tpl = _mock_template()
+        mock_tpl.model = "opus"
+        mock_get_template.return_value = mock_tpl
+        mock_run_review.return_value = _make_review_result()
+
+        ctx = _make_context(params={"template": "judge.slice-vs-arch"})
+        ctx.resolver.resolve.side_effect = [
+            ModelResolutionError("no model"),
+            ("claude-opus-4-8", None),
+        ]
+
+        result = await ReviewAction().execute(ctx)
+        assert result.success is True
+        assert ctx.resolver.resolve.call_count == 2
+        ctx.resolver.resolve.assert_called_with("opus", None)
+
 
 # ---------------------------------------------------------------------------
 # Execute — template inputs passthrough
@@ -378,16 +413,21 @@ class TestReviewInputPassthrough:
         mock_run_review: MagicMock,
         mock_format: MagicMock,
         mock_save: MagicMock,
+        tmp_path: Path,
     ) -> None:
         mock_get_template.return_value = _mock_template()
         mock_run_review.return_value = _make_review_result()
 
+        # against must name a real file (issue #18 existence guard)
+        against_doc = tmp_path / "arch.md"
+        against_doc.write_text("# arch\n")
+
         ctx = _make_context(
             params={
                 "template": "code",
                 "diff": "main",
                 "files": "src/**/*.py",
-                "against": "arch.md",
+                "against": str(against_doc),
             }
         )
         await ReviewAction().execute(ctx)
@@ -396,7 +436,7 @@ class TestReviewInputPassthrough:
         inputs = call_args[0][1]
         assert inputs["diff"] == "main"
         assert inputs["files"] == "src/**/*.py"
-        assert inputs["against"] == "arch.md"
+        assert inputs["against"] == str(against_doc)
         assert inputs["cwd"] == "/tmp/test"
 
 
@@ -486,6 +526,33 @@ class TestReviewErrors:
         assert "missing required input" in (result.error or "").lower()
         assert "input" in (result.error or "")
 
+    @pytest.mark.asyncio
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_nonexistent_input_file_fails_before_review(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        tmp_path: Path,
+    ) -> None:
+        """A resolved input path that names no real file must fail the action
+        before the model is called (issue #18) — previously the review ran
+        with the document silently absent and fabricated a verdict."""
+        mock_tpl = _mock_template()
+        mock_tpl.required_inputs = [InputDef(name="input", description="")]
+        mock_get_template.return_value = mock_tpl
+
+        missing = str(tmp_path / "never-written-tasks.md")
+        ctx = _make_context(params={"template": "tasks", "input": missing})
+        result = await ReviewAction().execute(ctx)
+
+        assert result.success is False
+        assert "not found" in (result.error or "")
+        assert "never-written-tasks.md" in (result.error or "")
+        mock_run_review.assert_not_called()
+
     @pytest.mark.asyncio
     @patch(f"{_P}.get_template")
     @patch(f"{_P}.load_all_templates")
@@ -503,6 +570,27 @@ class TestReviewErrors:
         assert result.success is False
         assert "no model" in (result.error or "")
 
+    @pytest.mark.asyncio
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_model_resolution_error_with_no_template_default_still_fails(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+    ) -> None:
+        """A template with no `model:` default must not mask the resolver error."""
+        mock_tpl = _mock_template()
+        mock_tpl.model = None
+        mock_get_template.return_value = mock_tpl
+
+        ctx = _make_context()
+        ctx.resolver.resolve.side_effect = ModelResolutionError("no model")
+
+        result = await ReviewAction().execute(ctx)
+        assert result.success is False
+        assert "no model" in (result.error or "")
+        ctx.resolver.resolve.assert_called_once()
+
     @pytest.mark.asyncio
     @patch(f"{_P}.run_review_with_profile", side_effect=RuntimeError("API down"))
     @patch(f"{_P}.get_template")
@@ -723,6 +811,54 @@ class TestJudgeEnforcement:
         assert result.provenance == "judge"
         assert any(r.levelno >= 30 for r in caplog.records)
 
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=Path("/tmp/reviews/review.md"))
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_persisted_file_receives_derived_verdict_not_raw_unknown(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        """Judge templates omit a verdict line by design (result.verdict is
+        always UNKNOWN), so the persisted file must receive the
+        threshold-derived verdict via verdict_override — otherwise a human
+        reading the file sees UNKNOWN next to a clearly-passing score."""
+        mock_get_template.return_value = _mock_judge_template()
+        mock_run_review.return_value = _make_review_result(Verdict.UNKNOWN, score=90.0)
+
+        result = await ReviewAction().execute(_make_context())
+
+        assert result.verdict == "PASS"
+        mock_format.assert_called_once()
+        assert mock_format.call_args.kwargs["verdict_override"] == "PASS"
+
+    @pytest.mark.asyncio
+    @patch(f"{_P}.save_review_file", return_value=None)
+    @patch(f"{_P}.format_review_markdown", return_value="# Review")
+    @patch(f"{_P}.run_review_with_profile")
+    @patch(f"{_P}.get_template")
+    @patch(f"{_P}.load_all_templates")
+    async def test_non_judge_persistence_receives_no_verdict_override(
+        self,
+        mock_load: MagicMock,
+        mock_get_template: MagicMock,
+        mock_run_review: MagicMock,
+        mock_format: MagicMock,
+        mock_save: MagicMock,
+    ) -> None:
+        mock_get_template.return_value = _mock_template()
+        mock_run_review.return_value = _make_review_result(Verdict.CONCERNS)
+
+        await ReviewAction().execute(_make_context())
+
+        assert mock_format.call_args.kwargs["verdict_override"] is None
+
 
 # ---------------------------------------------------------------------------
 # Execute — metadata
diff --git a/tests/pipeline/conftest.py b/tests/pipeline/conftest.py
index df02e61..07c8064 100644
--- a/tests/pipeline/conftest.py
+++ b/tests/pipeline/conftest.py
@@ -2,6 +2,9 @@
 
 from __future__ import annotations
 
+from pathlib import Path
+from unittest.mock import MagicMock
+
 import pytest
 
 from squadron.pipeline.executor import ExecutionStatus, PipelineResult, StepResult
@@ -15,6 +18,53 @@ def state_manager(tmp_path):  # type: ignore[no-untyped-def]
     return StateManager(runs_dir=tmp_path)
 
 
+def phase_artifact_cf_client(slice_index: int, design_file: str, task_file: str) -> MagicMock:
+    """A CF client mock that resolves a slice with real design/task filenames.
+
+    Needed because design/tasks steps (PhaseStepType) require
+    resolve_slice_info() to succeed and their dispatch to write the resolved
+    artifact — see the dispatch artifact post-condition (issue #15).
+    """
+    from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
+
+    cf_client = MagicMock()
+    cf_client.list_slices.return_value = [
+        SliceEntry(index=slice_index, name="stub", design_file=design_file, status="in_progress"),
+    ]
+    cf_client.list_tasks.return_value = [
+        TaskEntry(index=slice_index, files=[task_file]),
+    ]
+    cf_client.get_project.return_value = ProjectInfo(
+        arch_file="project-documents/user/architecture/100-arch.md",
+        slice_plan="100-slices.md",
+        phase="4",
+        slice=str(slice_index),
+        name="squadron",
+    )
+    return cf_client
+
+
+def artifact_writing_action(cwd: Path, slice_index: int) -> MagicMock:
+    """A dispatch-style mock action that writes the expected phase artifact.
+
+    Paths must match phase_artifact_cf_client's design_file/task_file:
+    the design path is used verbatim (no prefix); the task path gets the
+    project-documents/user/tasks/ prefix applied by resolve_slice_info.
+    """
+    design_path = cwd / f"{slice_index}-slice.stub.md"
+    task_path = cwd / f"project-documents/user/tasks/{slice_index}-tasks.stub.md"
+
+    async def dispatch_execute(ctx: object) -> ActionResult:
+        design_path.write_text("# stub design")
+        task_path.parent.mkdir(parents=True, exist_ok=True)
+        task_path.write_text("# stub tasks")
+        return ActionResult(success=True, action_type="dispatch", outputs={})
+
+    dispatch_mock = MagicMock()
+    dispatch_mock.execute = dispatch_execute
+    return dispatch_mock
+
+
 @pytest.fixture
 def completed_pipeline_result() -> PipelineResult:
     """A PipelineResult with status=COMPLETED and one dummy StepResult."""
diff --git a/tests/pipeline/steps/test_phase.py b/tests/pipeline/steps/test_phase.py
index 8f1aeff..c6b56c8 100644
--- a/tests/pipeline/steps/test_phase.py
+++ b/tests/pipeline/steps/test_phase.py
@@ -5,7 +5,7 @@ from __future__ import annotations
 import pytest
 
 from squadron.pipeline.models import StepConfig
-from squadron.pipeline.steps.phase import PhaseStepType
+from squadron.pipeline.steps.phase import ArtifactKind, PhaseStepType
 
 
 @pytest.fixture
@@ -42,6 +42,26 @@ def test_step_type_implement(implement_step: PhaseStepType) -> None:
     assert implement_step.step_type == "implement"
 
 
+# --- expected_artifact_kind property ---
+
+
+@pytest.mark.parametrize(
+    ("phase_name", "expected"),
+    [
+        ("design", ArtifactKind.DESIGN),
+        ("tasks", ArtifactKind.TASKS),
+        ("implement", None),
+    ],
+)
+def test_expected_artifact_kind_mapping(phase_name: str, expected: ArtifactKind | None) -> None:
+    assert PhaseStepType(phase_name).expected_artifact_kind == expected
+
+
+def test_expected_artifact_kind_unmapped_phase_defaults_to_none() -> None:
+    """A hypothetical future phase with no registered kind must not raise."""
+    assert PhaseStepType("some-future-phase").expected_artifact_kind is None
+
+
 # --- validate() ---
 
 
@@ -119,13 +139,13 @@ def test_expand_full_config(design_step: PhaseStepType) -> None:
     assert actions[0] == ("cf-op", {"operation": "set_phase", "phase": 4})
     assert actions[1] == ("cf-op", {"operation": "set_slice", "slice": "{slice}"})
     assert actions[2] == ("cf-op", {"operation": "build_context"})
-    assert actions[3] == ("dispatch", {"model": "opus"})
+    assert actions[3] == ("dispatch", {"model": "opus", "slice": "{slice}"})
     assert actions[4] == (
         "review",
         {"template": "slice", "model": None, "slice": "{slice}"},
     )
     assert actions[5] == ("checkpoint", {"trigger": "on-concerns"})
-    assert actions[6] == ("commit", {"message_prefix": "phase-4"})
+    assert actions[6] == ("commit", {"message_prefix": "phase-4", "slice": "{slice}"})
 
 
 def test_expand_review_as_dict(design_step: PhaseStepType) -> None:
@@ -168,19 +188,32 @@ def test_expand_review_no_checkpoint(design_step: PhaseStepType) -> None:
 def test_expand_dispatch_model_from_config(design_step: PhaseStepType) -> None:
     actions = design_step.expand(_make_config({"phase": 4, "model": "opus"}))
     dispatch = actions[3]
-    assert dispatch == ("dispatch", {"model": "opus"})
+    assert dispatch == ("dispatch", {"model": "opus", "slice": "{slice}"})
 
 
 def test_expand_dispatch_model_none(design_step: PhaseStepType) -> None:
     actions = design_step.expand(_make_config({"phase": 4}))
     dispatch = actions[3]
-    assert dispatch == ("dispatch", {"model": None})
+    assert dispatch == ("dispatch", {"model": None, "slice": "{slice}"})
 
 
 def test_expand_commit_prefix_includes_phase(design_step: PhaseStepType) -> None:
     actions = design_step.expand(_make_config({"phase": 7}))
     commit = actions[-1]
-    assert commit == ("commit", {"message_prefix": "phase-7"})
+    assert commit == ("commit", {"message_prefix": "phase-7", "slice": "{slice}"})
+
+
+def test_expand_uses_step_config_slice_when_present(design_step: PhaseStepType) -> None:
+    """A step-level 'slice' override (e.g. '{slice.index}' in an each-loop)
+    propagates into every action tuple that carries a slice reference,
+    instead of the bare '{slice}' default."""
+    actions = design_step.expand(_make_config({"phase": 4, "slice": "{slice.index}"}))
+    dispatch = next(a for a in actions if a[0] == "dispatch")
+    set_slice = next(a for a in actions if a[0] == "cf-op" and a[1].get("operation") == "set_slice")
+    commit = actions[-1]
+    assert dispatch[1]["slice"] == "{slice.index}"
+    assert set_slice[1]["slice"] == "{slice.index}"
+    assert commit[1]["slice"] == "{slice.index}"
 
 
 def test_expand_review_includes_slice_placeholder(design_step: PhaseStepType) -> None:
diff --git a/tests/pipeline/test_cli_integration.py b/tests/pipeline/test_cli_integration.py
index a94e1dd..6bcdf5f 100644
--- a/tests/pipeline/test_cli_integration.py
+++ b/tests/pipeline/test_cli_integration.py
@@ -16,6 +16,7 @@ from squadron.pipeline.executor import ExecutionStatus
 from squadron.pipeline.loader import load_pipeline
 from squadron.pipeline.models import ActionResult
 from squadron.pipeline.state import StateManager
+from tests.pipeline.conftest import artifact_writing_action, phase_artifact_cf_client
 
 # ---------------------------------------------------------------------------
 # Helpers (shared with test_state_integration.py)
@@ -43,12 +44,12 @@ def _mock_action(success: bool = True, verdict: str | None = None) -> MagicMock:
     return action
 
 
-def _success_registry() -> dict[str, object]:
+def _success_registry(dispatch_action: MagicMock | None = None) -> dict[str, object]:
     """Registry where all actions return success."""
     action = _mock_action(success=True)
     return {
         "cf-op": action,
-        "dispatch": action,
+        "dispatch": dispatch_action or action,
         "review": _mock_action(success=True, verdict="PASS"),
         "checkpoint": _mock_action(success=True),
         "commit": action,
@@ -60,6 +61,7 @@ def _success_registry() -> dict[str, object]:
 
 def _paused_checkpoint_registry(
     pause_on_step: int = 2,
+    dispatch_action: MagicMock | None = None,
 ) -> dict[str, object]:
     """Registry where the checkpoint action pauses on the Nth call."""
     call_count = [0]
@@ -90,7 +92,7 @@ def _paused_checkpoint_registry(
 
     return {
         "cf-op": normal_action,
-        "dispatch": normal_action,
+        "dispatch": dispatch_action or normal_action,
         "review": review_action,
         "checkpoint": checkpoint_mock,
         "commit": normal_action,
@@ -106,14 +108,22 @@ def _paused_checkpoint_registry(
 
 class TestCliIntegration:
     @pytest.mark.asyncio
-    async def test_run_pipeline_completes_successfully(self, tmp_path: Path) -> None:
+    async def test_run_pipeline_completes_successfully(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
         """_run_pipeline returns COMPLETED and persists state."""
-        with patch("squadron.cli.commands.run._check_cf"):
+        monkeypatch.chdir(tmp_path)
+        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
+        dispatch_action = artifact_writing_action(tmp_path, 191)
+        with (
+            patch("squadron.cli.commands.run._check_cf"),
+            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
+        ):
             result = await _run_pipeline(
                 "slice",
                 {"slice": "191"},
                 runs_dir=tmp_path,
-                _action_registry=_success_registry(),
+                _action_registry=_success_registry(dispatch_action=dispatch_action),
             )
 
         assert result.status == ExecutionStatus.COMPLETED
@@ -127,14 +137,22 @@ class TestCliIntegration:
         assert len(runs[0].completed_steps) == 10
 
     @pytest.mark.asyncio
-    async def test_state_file_loadable_after_run(self, tmp_path: Path) -> None:
+    async def test_state_file_loadable_after_run(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
         """State file is persisted and loadable via StateManager."""
-        with patch("squadron.cli.commands.run._check_cf"):
+        monkeypatch.chdir(tmp_path)
+        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
+        dispatch_action = artifact_writing_action(tmp_path, 191)
+        with (
+            patch("squadron.cli.commands.run._check_cf"),
+            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
+        ):
             await _run_pipeline(
                 "slice",
                 {"slice": "191"},
                 runs_dir=tmp_path,
-                _action_registry=_success_registry(),
+                _action_registry=_success_registry(dispatch_action=dispatch_action),
             )
 
         mgr = StateManager(runs_dir=tmp_path)
@@ -148,14 +166,24 @@ class TestCliIntegration:
     # -------------------------------------------------------------------
 
     @pytest.mark.asyncio
-    async def test_resume_from_paused_completes(self, tmp_path: Path) -> None:
+    async def test_resume_from_paused_completes(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
         """First run pauses; second run resumes and completes all steps."""
-        with patch("squadron.cli.commands.run._check_cf"):
+        monkeypatch.chdir(tmp_path)
+        cf_client = phase_artifact_cf_client(191, "191-slice.stub.md", "191-tasks.stub.md")
+        dispatch_action = artifact_writing_action(tmp_path, 191)
+        with (
+            patch("squadron.cli.commands.run._check_cf"),
+            patch("squadron.cli.commands.run.ContextForgeClient", return_value=cf_client),
+        ):
             result1 = await _run_pipeline(
                 "slice",
                 {"slice": "191"},
                 runs_dir=tmp_path,
-                _action_registry=_paused_checkpoint_registry(pause_on_step=2),
+                _action_registry=_paused_checkpoint_registry(
+                    pause_on_step=2, dispatch_action=dispatch_action
+                ),
             )
 
         assert result1.status == ExecutionStatus.PAUSED
@@ -177,11 +205,13 @@ class TestCliIntegration:
                 definition,
                 {"slice": "191"},
                 resolver=MagicMock(),
-                cf_client=MagicMock(),
+                cf_client=cf_client,
+                cwd=str(tmp_path),
                 run_id=run_id,
+                runs_dir=tmp_path,
                 start_from=next_step,
                 on_step_complete=mgr.make_step_callback(run_id),
-                _action_registry=_success_registry(),
+                _action_registry=_success_registry(dispatch_action=dispatch_action),
             )
         mgr.finalize(run_id, result2)
 
diff --git a/tests/pipeline/test_executor.py b/tests/pipeline/test_executor.py
index 303faa3..a0e8e61 100644
--- a/tests/pipeline/test_executor.py
+++ b/tests/pipeline/test_executor.py
@@ -4,6 +4,7 @@ evaluate_condition, retry loops, and core executor logic.
 
 from __future__ import annotations
 
+from pathlib import Path
 from unittest.mock import AsyncMock, MagicMock
 
 import pytest
@@ -631,6 +632,326 @@ class TestExecutePipelineErrorHandling:
         assert captured["findings"] == review_findings
 
 
+# ---------------------------------------------------------------------------
+# Part A (909, issue #15) — Dispatch artifact post-condition
+# ---------------------------------------------------------------------------
+
+
+class TestDispatchArtifactPostCondition:
+    """PhaseStepType dispatch must fail closed when its expected artifact
+    (design/tasks file) wasn't written by the current run."""
+
+    def _cf_client(self, slice_index: int, design_file: str, task_file: str) -> MagicMock:
+        from tests.pipeline.conftest import phase_artifact_cf_client
+
+        return phase_artifact_cf_client(slice_index, design_file, task_file)
+
+    def _init_run(self, tmp_path: Path, slice_index: int) -> str:
+        from squadron.pipeline.state import StateManager
+
+        state_mgr = StateManager(runs_dir=tmp_path)
+        return state_mgr.init_run("slice", {"slice": str(slice_index)})
+
+    def _pipeline(self, phase_step_type: str) -> PipelineDefinition:
+        return make_pipeline(
+            [make_step_config(phase_step_type, "design-0", {"phase": 4, "model": "opus"})]
+        )
+
+    def _registry(self, dispatch_mock: object) -> dict[str, object]:
+        """Full action registry for a PhaseStepType.expand() sequence:
+        cf-op(set_phase) -> cf-op(set_slice) -> cf-op(build_context)
+        -> dispatch -> commit (no review/checkpoint since these test
+        configs omit "review")."""
+        cf_op_mock = MagicMock()
+        cf_op_mock.execute = AsyncMock(return_value=make_action_result(True, "cf-op"))
+        commit_mock = mock_action([make_action_result(True, "commit")])
+        return {"cf-op": cf_op_mock, "dispatch": dispatch_mock, "commit": commit_mock}
+
+    @pytest.mark.asyncio
+    async def test_fresh_artifact_passes(self, tmp_path: Path) -> None:
+        """(a) Artifact present with mtime >= run start -> step completes."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 200)
+        cf_client = self._cf_client(200, "200-slice.stub.md", "200-tasks.stub.md")
+
+        async def dispatch_execute(ctx: object) -> ActionResult:
+            (tmp_path / "200-slice.stub.md").write_text("# design")
+            return make_action_result(True, "dispatch")
+
+        dispatch_mock = MagicMock()
+        dispatch_mock.execute = dispatch_execute
+
+        result = await execute_pipeline(
+            self._pipeline("design"),
+            {"slice": "200"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.COMPLETED
+
+    @pytest.mark.asyncio
+    async def test_absent_artifact_fails(self, tmp_path: Path) -> None:
+        """(b) Dispatch reports success but writes nothing -> step fails."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 201)
+        cf_client = self._cf_client(201, "201-slice.stub.md", "201-tasks.stub.md")
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        result = await execute_pipeline(
+            self._pipeline("design"),
+            {"slice": "201"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.FAILED
+        assert "201" in (result.step_results[0].action_results[-1].error or "")
+
+    @pytest.mark.asyncio
+    async def test_stale_artifact_fails(self, tmp_path: Path) -> None:
+        """(c) Artifact exists but predates run start -> treated as no-artifact."""
+        import time
+
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        stale_path = tmp_path / "202-slice.stub.md"
+        stale_path.write_text("# leftover from a prior run")
+        old_time = time.time() - 3600
+        import os as _os
+
+        _os.utime(stale_path, (old_time, old_time))
+
+        run_id = self._init_run(tmp_path, 202)
+        cf_client = self._cf_client(202, "202-slice.stub.md", "202-tasks.stub.md")
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        result = await execute_pipeline(
+            self._pipeline("design"),
+            {"slice": "202"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.FAILED
+
+    @pytest.mark.asyncio
+    async def test_unresolvable_slice_fails_with_distinct_message(self, tmp_path: Path) -> None:
+        """(d) Slice not found in the plan -> fails with a resolution-specific message."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 999)
+        cf_client = MagicMock()
+        cf_client.list_slices.return_value = []  # no slice 999 registered
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        result = await execute_pipeline(
+            self._pipeline("design"),
+            {"slice": "999"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.FAILED
+        error = result.step_results[0].action_results[-1].error or ""
+        assert "could not resolve" in error
+
+    @pytest.mark.asyncio
+    async def test_non_numeric_slice_param_fails_closed(self, tmp_path: Path) -> None:
+        """A non-numeric 'slice' param (e.g. an unresolved '{slice.index}'
+        placeholder reaching the check) must fail closed, not raise ValueError."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 206)
+        cf_client = self._cf_client(206, "206-slice.stub.md", "206-tasks.stub.md")
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        # Step config's own "slice" value is left unresolved (simulates a
+        # loop context where the placeholder never got substituted).
+        pipeline = make_pipeline(
+            [
+                make_step_config(
+                    "design",
+                    "design-0",
+                    {"phase": 4, "model": "opus", "slice": "{slice.index}"},
+                )
+            ]
+        )
+
+        result = await execute_pipeline(
+            pipeline,
+            {"slice": "206"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.FAILED
+        error = result.step_results[0].action_results[-1].error or ""
+        assert "not a numeric index" in error
+
+    @pytest.mark.asyncio
+    async def test_permission_error_on_check_fails_and_logs(
+        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
+    ) -> None:
+        """(e) OSError while checking the artifact -> fails, logged, not swallowed."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 203)
+        cf_client = self._cf_client(203, "locked/203-slice.stub.md", "203-tasks.stub.md")
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        # Real permission error: unreadable parent directory means the
+        # artifact-check's .exists()/.stat() on the file inside it raises
+        # OSError, without disturbing StateManager's own file access.
+        artifact_dir = tmp_path / "locked"
+        artifact_dir.mkdir()
+        artifact_path = artifact_dir / "203-slice.stub.md"
+        artifact_path.write_text("# design")
+        artifact_dir.chmod(0o000)
+
+        try:
+            with caplog.at_level("WARNING"):
+                result = await execute_pipeline(
+                    self._pipeline("design"),
+                    {"slice": "203"},
+                    resolver=MagicMock(),
+                    cf_client=cf_client,
+                    cwd=str(tmp_path),
+                    run_id=run_id,
+                    runs_dir=tmp_path,
+                    _action_registry=self._registry(dispatch_mock),
+                )
+        finally:
+            artifact_dir.chmod(0o755)
+
+        assert result.status == ExecutionStatus.FAILED
+        assert any("dispatch post-condition" in rec.message for rec in caplog.records)
+
+    @pytest.mark.asyncio
+    async def test_implement_phase_skips_post_condition(self, tmp_path: Path) -> None:
+        """(f) implement phase (kind None) -> post-condition not applied at all."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 204)
+        cf_client = MagicMock()  # never consulted — no artifact check for implement
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        result = await execute_pipeline(
+            self._pipeline("implement"),
+            {"slice": "204"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry=self._registry(dispatch_mock),
+        )
+
+        assert result.status == ExecutionStatus.COMPLETED
+        cf_client.list_slices.assert_not_called()
+
+    @pytest.mark.asyncio
+    async def test_generic_dispatch_step_unaffected(self, tmp_path: Path) -> None:
+        """A bare (non-PhaseStepType) dispatch step that writes nothing still succeeds."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+        from squadron.pipeline.steps import register_step_type
+
+        step = mock_step_type([("dispatch", {})])
+        register_step_type("_test_bare_dispatch", step)
+
+        pipeline = make_pipeline([make_step_config("_test_bare_dispatch", "step-1", {})])
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])
+
+        result = await execute_pipeline(
+            pipeline,
+            {},
+            resolver=MagicMock(),
+            cf_client=MagicMock(),
+            _action_registry={"dispatch": dispatch_mock},
+        )
+
+        assert result.status == ExecutionStatus.COMPLETED
+
+    @pytest.mark.asyncio
+    async def test_no_artifact_routes_through_on_fail_not_silent_advance(self, tmp_path: Path) -> None:
+        """SC-A2: a phase step configured with checkpoint/review still halts at
+        the dispatch step on no-artifact — it must not reach review/checkpoint
+        or advance to a downstream step. This is the end-to-end routing
+        consequence; test_absent_artifact_fails only covers the failed
+        *marking*, not this *routing* guarantee."""
+        from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+
+        run_id = self._init_run(tmp_path, 205)
+        cf_client = self._cf_client(205, "205-slice.stub.md", "205-tasks.stub.md")
+        dispatch_mock = mock_action([make_action_result(True, "dispatch")])  # writes nothing
+
+        review_mock = MagicMock()
+        review_mock.execute = AsyncMock()
+        checkpoint_mock = MagicMock()
+        checkpoint_mock.execute = AsyncMock()
+
+        pipeline = make_pipeline(
+            [
+                make_step_config(
+                    "design",
+                    "design-0",
+                    {
+                        "phase": 4,
+                        "model": "opus",
+                        "review": "slice",
+                        "checkpoint": "on-fail",
+                    },
+                ),
+                make_step_config("design", "design-1", {"phase": 4, "model": "opus"}),
+            ]
+        )
+
+        result = await execute_pipeline(
+            pipeline,
+            {"slice": "205"},
+            resolver=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
+            _action_registry={
+                **self._registry(dispatch_mock),
+                "review": review_mock,
+                "checkpoint": checkpoint_mock,
+            },
+        )
+
+        # Halts at the dispatch step itself — not a downstream review/checkpoint
+        # verdict, and not a silent advance to design-1.
+        assert result.status == ExecutionStatus.FAILED
+        assert len(result.step_results) == 1
+        assert result.step_results[0].step_name == "design-0"
+        review_mock.execute.assert_not_called()
+        checkpoint_mock.execute.assert_not_called()
+
+
 # ---------------------------------------------------------------------------
 # T6 — Retry loop execution
 # ---------------------------------------------------------------------------
diff --git a/tests/pipeline/test_executor_integration.py b/tests/pipeline/test_executor_integration.py
index 4f4f489..ed9c8b1 100644
--- a/tests/pipeline/test_executor_integration.py
+++ b/tests/pipeline/test_executor_integration.py
@@ -14,6 +14,7 @@ import pytest
 from squadron.pipeline.executor import ExecutionStatus, StepResult, execute_pipeline
 from squadron.pipeline.loader import load_pipeline
 from squadron.pipeline.models import ActionResult
+from tests.pipeline.conftest import artifact_writing_action, phase_artifact_cf_client
 
 
 def _mock_action_fn(success: bool = True, verdict: str | None = None) -> MagicMock:
@@ -53,17 +54,45 @@ def _success_registry() -> dict[str, object]:
     }
 
 
+def _artifact_writing_success_registry(cwd: Path, slice_index: int) -> dict[str, object]:
+    """Success registry whose dispatch mock writes the expected phase artifact.
+
+    Mirrors _success_registry but the "dispatch" action writes to whichever
+    path the current call's params/expected kind requires, satisfying the
+    dispatch artifact post-condition for design/tasks phase steps.
+    """
+    action = _mock_action_fn(success=True)
+    return {
+        "cf-op": action,
+        "dispatch": artifact_writing_action(cwd, slice_index),
+        "review": _mock_action_fn(success=True, verdict="PASS"),
+        "checkpoint": _mock_action_fn(success=True),
+        "commit": action,
+        "compact": action,
+        "summary": action,
+        "devlog": action,
+    }
+
+
 class TestSliceLifecycleIntegration:
     @pytest.mark.asyncio
-    async def test_all_steps_completed(self) -> None:
+    async def test_all_steps_completed(self, tmp_path: Path) -> None:
+        from squadron.pipeline.state import StateManager
+
         definition = _no_project_pipeline("slice")
-        registry = _success_registry()
+        registry = _artifact_writing_success_registry(tmp_path, 149)
+        cf_client = phase_artifact_cf_client(149, "149-slice.stub.md", "149-tasks.stub.md")
+        state_mgr = StateManager(runs_dir=tmp_path)
+        run_id = state_mgr.init_run("slice", {"slice": "149"})
 
         result = await execute_pipeline(
             definition,
             {"slice": "149"},
             resolver=MagicMock(),
-            cf_client=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
             _action_registry=registry,
         )
 
@@ -72,16 +101,24 @@ class TestSliceLifecycleIntegration:
         assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)
 
     @pytest.mark.asyncio
-    async def test_on_step_complete_called_in_order(self) -> None:
+    async def test_on_step_complete_called_in_order(self, tmp_path: Path) -> None:
+        from squadron.pipeline.state import StateManager
+
         definition = _no_project_pipeline("slice")
-        registry = _success_registry()
+        registry = _artifact_writing_success_registry(tmp_path, 149)
+        cf_client = phase_artifact_cf_client(149, "149-slice.stub.md", "149-tasks.stub.md")
+        state_mgr = StateManager(runs_dir=tmp_path)
+        run_id = state_mgr.init_run("slice", {"slice": "149"})
         received: list[StepResult] = []
 
         await execute_pipeline(
             definition,
             {"slice": "149"},
             resolver=MagicMock(),
-            cf_client=MagicMock(),
+            cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
             on_step_complete=received.append,
             _action_registry=registry,
         )
@@ -145,16 +182,28 @@ class TestReviewOnlyIntegration:
 
 class TestDesignBatchIntegration:
     @pytest.mark.asyncio
-    async def test_two_slices_inner_steps_run_twice(self) -> None:
-        from squadron.integrations.context_forge import SliceEntry
+    async def test_two_slices_inner_steps_run_twice(self, tmp_path: Path) -> None:
+        from squadron.integrations.context_forge import ProjectInfo, SliceEntry, TaskEntry
+        from squadron.pipeline.state import StateManager
 
         definition = _no_project_pipeline("design-batch")
 
         cf_client = MagicMock()
         cf_client.list_slices.return_value = [
-            SliceEntry(index=10, name="sl-a", design_file=None, status="not_started"),
-            SliceEntry(index=11, name="sl-b", design_file=None, status="in_progress"),
+            SliceEntry(index=10, name="sl-a", design_file="10-slice.sl-a.md", status="not_started"),
+            SliceEntry(index=11, name="sl-b", design_file="11-slice.sl-b.md", status="in_progress"),
         ]
+        cf_client.list_tasks.return_value = [
+            TaskEntry(index=10, files=[]),
+            TaskEntry(index=11, files=[]),
+        ]
+        cf_client.get_project.return_value = ProjectInfo(
+            arch_file="project-documents/user/architecture/100-arch.md",
+            slice_plan="100-slices.md",
+            phase="4",
+            slice="10",
+            name="squadron",
+        )
 
         call_count = 0
 
@@ -168,21 +217,38 @@ class TestDesignBatchIntegration:
                 verdict="PASS",
             )
 
+        async def dispatch_execute(ctx: object) -> ActionResult:
+            nonlocal call_count
+            call_count += 1
+            slice_index = ctx.params["slice"]  # type: ignore[attr-defined]
+            suffix = "a" if str(slice_index) == "10" else "b"
+            design_path = tmp_path / f"{slice_index}-slice.sl-{suffix}.md"
+            design_path.write_text("# stub design")
+            return ActionResult(success=True, action_type="dispatch", outputs={})
+
         action = MagicMock()
         action.execute = counting_execute
+        dispatch_mock = MagicMock()
+        dispatch_mock.execute = dispatch_execute
         registry: dict[str, object] = {
             "cf-op": action,
-            "dispatch": action,
+            "dispatch": dispatch_mock,
             "review": action,
             "checkpoint": action,
             "commit": action,
         }
 
+        state_mgr = StateManager(runs_dir=tmp_path)
+        run_id = state_mgr.init_run("design-batch", {"plan": "my-plan"})
+
         result = await execute_pipeline(
             definition,
             {"plan": "my-plan"},
             resolver=MagicMock(),
             cf_client=cf_client,
+            cwd=str(tmp_path),
+            run_id=run_id,
+            runs_dir=tmp_path,
             _action_registry=registry,
         )
 
diff --git a/tests/pipeline/test_judge_cycle.py b/tests/pipeline/test_judge_cycle.py
new file mode 100644
index 0000000..704d36d
--- /dev/null
+++ b/tests/pipeline/test_judge_cycle.py
@@ -0,0 +1,155 @@
+"""Control-flow tests for the judge-cycle built-in pipeline.
+
+Loads the real `judge-cycle.yaml` shipped artifact and drives it through
+`execute_pipeline` with a real `ReviewAction` (only `run_review_with_profile`
+and persistence are mocked) and a mocked `dispatch` action. `resolve_thresholds`
+and `enforce_judge` run for real, so these tests prove control flow — score
+in, derived verdict, loop exit/exhaust — not model behavior.
+"""
+
+from __future__ import annotations
+
+from datetime import datetime
+from pathlib import Path
+from unittest.mock import AsyncMock, MagicMock, patch
+
+import pytest
+
+from squadron.pipeline.actions.review import ReviewAction
+from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+from squadron.pipeline.loader import load_pipeline
+from squadron.pipeline.models import ActionResult
+from squadron.pipeline.steps import bootstrap_step_types
+from squadron.review.models import ReviewResult, Verdict
+
+_P = "squadron.pipeline.actions.review"
+_NONEXISTENT = Path("/nonexistent")
+
+
+def _make_review_result(score: float) -> ReviewResult:
+    return ReviewResult(
+        verdict=Verdict.CONCERNS,
+        findings=[],
+        raw_output="## Review\n",
+        template_name="judge.slice-vs-arch",
+        input_files={"cwd": "/tmp/test"},
+        timestamp=datetime(2026, 7, 14, 12, 0, 0),
+        model="claude-sonnet-4-20250514",
+        score=score,
+        criteria=None,
+    )
+
+
+def _slice_info(design_file: str, arch_file: str) -> dict[str, object]:
+    return {
+        "index": 303,
+        "name": "judge-gated-cycle-conventions",
+        "slice_name": "judge-gated-cycle-conventions",
+        "design_file": design_file,
+        "task_files": ["303-tasks.judge-gated-cycle-conventions.md"],
+        "arch_file": arch_file,
+    }
+
+
+async def _run_judge_cycle(
+    dispatch_mock: MagicMock,
+    tmp_path: Path,
+    score: float,
+    judge_override: dict[str, object] | None = None,
+) -> object:
+    """Load the real judge-cycle definition and execute it with a forced score.
+
+    Returns the PipelineResult. Real design/arch tmp files satisfy the
+    issue-#18 missing-input hard-fail; `resolve_slice_info` is mocked only to
+    point at them, not to fabricate the judge verdict path. `judge_override`,
+    when given, is injected into the loop body's review step config — the
+    exact step-level `judge:` override a user would write.
+    """
+    bootstrap_step_types()
+
+    definition = load_pipeline("judge-cycle", project_dir=_NONEXISTENT, user_dir=_NONEXISTENT)
+    if judge_override is not None:
+        loop_config = definition.steps[0].config
+        loop_config["steps"][1]["review"]["judge"] = judge_override
+
+    design_file = tmp_path / "303-slice.md"
+    design_file.write_text("# slice design\n")
+    arch_file = tmp_path / "100-arch.md"
+    arch_file.write_text("# architecture\n")
+
+    resolver = MagicMock()
+    resolver.resolve.return_value = ("claude-sonnet-4-20250514", None)
+
+    with (
+        patch(f"{_P}.resolve_slice_info", return_value=_slice_info(str(design_file), str(arch_file))),
+        patch(f"{_P}.run_review_with_profile", return_value=_make_review_result(score)),
+        patch(f"{_P}.save_review_file", return_value=None),
+        patch(f"{_P}.format_review_markdown", return_value="# Review"),
+    ):
+        return await execute_pipeline(
+            definition,
+            {"slice": "303"},
+            resolver=resolver,
+            cf_client=MagicMock(),
+            cwd=str(tmp_path),
+            _action_registry={"dispatch": dispatch_mock, "review": ReviewAction()},
+        )
+
+
+def _dispatch_mock() -> MagicMock:
+    action = MagicMock()
+    action.execute = AsyncMock(
+        return_value=ActionResult(success=True, action_type="dispatch", outputs={})
+    )
+    return action
+
+
+class TestJudgeCycleAutoAdvance:
+    @pytest.mark.asyncio
+    async def test_judge_cycle_auto_advance(self, tmp_path: Path) -> None:
+        dispatch_mock = _dispatch_mock()
+        # 90 clears judge.slice-vs-arch's default pass_floor (82).
+        result = await _run_judge_cycle(dispatch_mock, tmp_path, score=90.0)
+
+        assert result.status == ExecutionStatus.COMPLETED
+        loop_result = result.step_results[0]
+        assert loop_result.iteration == 1
+        assert dispatch_mock.execute.await_count == 1
+
+
+class TestJudgeCycleEscalates:
+    @pytest.mark.asyncio
+    async def test_judge_cycle_escalates(self, tmp_path: Path) -> None:
+        dispatch_mock = _dispatch_mock()
+        # 40 is below judge.slice-vs-arch's default concerns_floor (60) —
+        # FAIL on every iteration, never clears `until: review.pass`.
+        result = await _run_judge_cycle(dispatch_mock, tmp_path, score=40.0)
+
+        assert result.status == ExecutionStatus.PAUSED
+        loop_result = result.step_results[0]
+        assert loop_result.status == ExecutionStatus.PAUSED
+        assert dispatch_mock.execute.await_count == 3
+
+        last_review = loop_result.action_results[-1]
+        assert last_review.action_type == "review"
+        assert last_review.score == 40.0
+
+
+class TestJudgeCycleAdvisoryAlwaysEscalates:
+    @pytest.mark.asyncio
+    async def test_judge_cycle_advisory_always_escalates(self, tmp_path: Path) -> None:
+        dispatch_mock = _dispatch_mock()
+        # 95 is well above the default pass_floor (82) but below the
+        # step-level advisory override (101) — the gate is the threshold,
+        # not the model, and pass_floor > 100 is a sanctioned unclamped value.
+        result = await _run_judge_cycle(
+            dispatch_mock,
+            tmp_path,
+            score=95.0,
+            judge_override={"pass_floor": 101},
+        )
+
+        assert result.status == ExecutionStatus.PAUSED
+        loop_result = result.step_results[0]
+        assert loop_result.status == ExecutionStatus.PAUSED
+        assert dispatch_mock.execute.await_count == 3
diff --git a/tests/pipeline/test_loader_integration.py b/tests/pipeline/test_loader_integration.py
index 427b6f7..765438f 100644
--- a/tests/pipeline/test_loader_integration.py
+++ b/tests/pipeline/test_loader_integration.py
@@ -15,6 +15,7 @@ _BUILTIN_NAMES = [
     "implement",
     "design-batch",
     "tasks",
+    "judge-cycle",
 ]
 
 _NONEXISTENT = Path("/nonexistent")
@@ -79,3 +80,22 @@ class TestBuiltInPipelineStructure:
         )
         assert len(defn.steps) == 1
         assert defn.steps[0].step_type == "each"
+
+    def test_judge_cycle_shape(self) -> None:
+        defn = load_pipeline(
+            "judge-cycle",
+            project_dir=_NONEXISTENT,
+            user_dir=_NONEXISTENT,
+        )
+        assert len(defn.steps) == 1
+        loop_step = defn.steps[0]
+        assert loop_step.step_type == "loop"
+        assert loop_step.config["max"] >= 1
+        assert loop_step.config["until"] == "review.pass"
+        assert loop_step.config["on_exhaust"] == "checkpoint"
+
+        body = loop_step.config["steps"]
+        assert len(body) == 2
+        assert next(iter(body[0])) == "dispatch"
+        assert next(iter(body[1])) == "review"
+        assert body[1]["review"]["template"] == "judge.slice-vs-arch"
diff --git a/tests/pipeline/test_sdk_integration.py b/tests/pipeline/test_sdk_integration.py
index 6cdbcfc..ed67b2b 100644
--- a/tests/pipeline/test_sdk_integration.py
+++ b/tests/pipeline/test_sdk_integration.py
@@ -6,6 +6,7 @@ to verify the execution flow end-to-end without real LLM calls.
 
 from __future__ import annotations
 
+from pathlib import Path
 from unittest.mock import AsyncMock, MagicMock
 
 import pytest
@@ -14,12 +15,25 @@ from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
 from squadron.pipeline.loader import load_pipeline
 from squadron.pipeline.models import ActionContext, ActionResult
 from squadron.pipeline.sdk_session import SDKExecutionSession
+from tests.pipeline.conftest import phase_artifact_cf_client
 
 # ---------------------------------------------------------------------------
 # Helpers
 # ---------------------------------------------------------------------------
 
 
+def _init_run_state(tmp_path: Path, pipeline_name: str, params: dict[str, object]) -> str:
+    """Create a real state file under tmp_path and return its run_id.
+
+    The dispatch artifact post-condition loads RunState.started_at via
+    StateManager(runs_dir=...); execute_pipeline needs a real state file
+    to find (via the runs_dir/run_id pair) or it fails closed.
+    """
+    from squadron.pipeline.state import StateManager
+
+    return StateManager(runs_dir=tmp_path).init_run(pipeline_name, params)
+
+
 def _make_mock_session() -> AsyncMock:
     session = AsyncMock(spec=SDKExecutionSession)
     session.set_model = AsyncMock()
@@ -61,8 +75,25 @@ def _pass_review() -> ActionResult:
     )
 
 
+def _write_phase_artifacts(tmp_path: Path, slice_index: int) -> None:
+    """Write both the design and task stub artifacts for slice_index.
+
+    test-pipeline.yaml dispatches design/tasks phase steps multiple times
+    for the same slice, so writing both upfront (idempotent, mtime updates
+    each call) satisfies the dispatch artifact post-condition regardless of
+    which phase is currently running.
+    """
+    design_path = tmp_path / f"{slice_index}-slice.stub.md"
+    task_path = tmp_path / f"project-documents/user/tasks/{slice_index}-tasks.stub.md"
+    design_path.write_text("# stub design")
+    task_path.parent.mkdir(parents=True, exist_ok=True)
+    task_path.write_text("# stub tasks")
+
+
 def _make_full_registry(
     *,
+    tmp_path: Path,
+    slice_index: int = 154,
     dispatch_fn: AsyncMock | None = None,
     review_fn: AsyncMock | None = None,
     summary_fn: AsyncMock | None = None,
@@ -100,9 +131,10 @@ def _make_full_registry(
     if dispatch_fn is not None:
         registry["dispatch"] = _make_with_fn("dispatch", dispatch_fn)
     else:
-        registry["dispatch"] = _make(
-            "dispatch",
-            ActionResult(
+
+        async def _default_dispatch(ctx: ActionContext) -> ActionResult:
+            _write_phase_artifacts(tmp_path, slice_index)
+            return ActionResult(
                 success=True,
                 action_type="dispatch",
                 outputs={"response": "design output"},
@@ -110,8 +142,9 @@ def _make_full_registry(
                     "model": "claude-haiku-4-5-20251001",
                     "profile": "sdk-session",
                 },
-            ),
-        )
+            )
+
+        registry["dispatch"] = _make_with_fn("dispatch", _default_dispatch)
 
     if review_fn is not None:
         registry["review"] = _make_with_fn("review", review_fn)
@@ -151,18 +184,23 @@ def _make_full_registry(
 
 
 @pytest.mark.asyncio
-async def test_full_pipeline_cycle_completes() -> None:
+async def test_full_pipeline_cycle_completes(tmp_path: Path) -> None:
     """Full pipeline runs to completion with mock session."""
     session = _make_mock_session()
     definition = load_pipeline("test-pipeline")
+    cf_client = phase_artifact_cf_client(154, "154-slice.stub.md", "154-tasks.stub.md")
+    run_id = _init_run_state(tmp_path, "test-pipeline", {"slice": "154"})
 
     result = await execute_pipeline(
         definition,
         {"slice": "154"},
         resolver=_make_resolver(),
-        cf_client=MagicMock(),
+        cf_client=cf_client,
+        cwd=str(tmp_path),
+        run_id=run_id,
+        runs_dir=tmp_path,
         sdk_session=session,
-        _action_registry=_make_full_registry(),
+        _action_registry=_make_full_registry(tmp_path=tmp_path, slice_index=154),
     )
 
     assert result.status == ExecutionStatus.COMPLETED
@@ -170,15 +208,18 @@ async def test_full_pipeline_cycle_completes() -> None:
 
 
 @pytest.mark.asyncio
-async def test_sdk_session_propagated_to_all_dispatch_contexts() -> None:
+async def test_sdk_session_propagated_to_all_dispatch_contexts(tmp_path: Path) -> None:
     """Session is in ActionContext for all dispatch actions."""
     session = _make_mock_session()
     definition = load_pipeline("test-pipeline")
+    cf_client = phase_artifact_cf_client(154, "154-slice.stub.md", "154-tasks.stub.md")
+    run_id = _init_run_state(tmp_path, "test-pipeline", {"slice": "154"})
 
     captured: list[ActionContext] = []
 
     async def _capture(ctx: ActionContext) -> ActionResult:
         captured.append(ctx)
+        _write_phase_artifacts(tmp_path, 154)
         return ActionResult(
             success=True,
             action_type="dispatch",
@@ -190,9 +231,12 @@ async def test_sdk_session_propagated_to_all_dispatch_contexts() -> None:
         definition,
         {"slice": "154"},
         resolver=_make_resolver(),
-        cf_client=Mag

[truncated at 100KB — file too large for API review]
```

### CLAUDE.md (project conventions)

```
### Project Guidelines for Claude

[//]: # (context-forge:managed)

#### Core Principles

- Always resist adding complexity. Ensure it is truly necessary.
- Never use silent fallback values. Fail explicitly with errors or obviously-placeholder values.
- Never use cheap hacks or well-known anti-patterns.
- Never include credentials, API keys, or secrets in source code or comments. Load from environment variables; ensure .env is in .gitignore. Raise an issue if violations are found.
- When debugging a failure, get the actual error message before attempting any fix. Never apply more than one speculative fix without first obtaining concrete evidence (logs, error text, stack trace) that diagnoses the root cause. If you cannot get the evidence yourself, ask the Project Manager for it.

#### Code Structure

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

##### Exception Handling
- Every try/except must either: (a) re-raise after logging at ERROR level with logger.exception, (b) handle a specific exception with a comment explaining why swallowing is correct (e.g., ConnectionClosed: pass for normal teardown), or (c) be a top-level handler at a process boundary. Bare except: and except Exception: pass are bugs by definition.

#### Source Control and Builds
- Keep commits semantic; build after all changes.
- Git add and commit from project root at least once per task.
- Confirm your current working directory before file/shell commands.

#### Parsing & Pattern Matching
- Prefer lenient parsing over strict matching. A regex that silently fails on valid input (e.g. requiring exact whitespace counts or line-ending positions) is a bug. Parse the semantic content, not the formatting.
- When parsing structured text (YAML, key-value pairs, etc.), handle common format variations (compact vs multi-line, varying indent levels, trailing whitespace) rather than requiring one exact layout.
- When writing a parser, the test fixture must include the actual format that parser will consume in production.  A test that only passes on a format the real data never uses only provides false confidence.
- If a parser returns empty/default on bad input, add at least one test using real-world input (e.g. the actual file it will parse) to catch silent failures.
  
#### Hallucination traps in prompts
If an instruction tells a reader to retrieve a value from some source, and
that source might return empty, do not place a hardcoded example of an
acceptable value nearby. When the source is empty, a model will reach for
the nearest plausible token — and the example is it. This is a
hallucination trap.

##### Bad

    Print the filename (from stderr, e.g. `squadron-P4.md`).

##### Good

    Print the filename. The CLI emits it on a line prefixed with
    `Using: ` on stderr. If no such line is present, stop with an error.


#### Project Navigation
- Follow `guide.ai-project.process` and its links for workflow.
- Follow `file-naming-conventions` for all document naming and metadata.
- Project guides: `project-documents/ai-project-guide/project-guides/`
- Tool guides: `project-documents/ai-project-guide/tool-guides/`
- Modular rules for specific technologies may exist in 
  `project-guides/rules/`.

#### Document Conventions

- All markdown files must include YAML frontmatter as specified in `file-naming-conventions.md`
- Use checklist format for all task files.  Each item and subitem should have a `[ ]` "checkbox".
- After completing a task or subtask, delegate checklist updates to the `task-checker` agent rather than editing task files inline. This keeps the main agent's context focused on implementation. If task-checker is unavailable, check off tasks directly.
- Preserve sections titled "## User-Provided Concept" exactly as 
  written — never modify or remove.
- Keep success summaries concise and minimal.

#### Git Rules

##### Branch Naming
A branch corresponds to one unit of work: slice implementation (Phase 6). Planning work (Phases 0–5: concept, initiative plan, architecture, slice plan, slice design, task breakdown, and reviews of those artifacts) does not get its own branch — it commits directly to the current integration target (see below).

- **Slice work** → `{index}-slice.{name}`, where `{index}` is the slice's index and `{name}` is the document name without the `.md` extension.

###### Integration branch
A project may configure an **optional** integration branch that work forks from and merges into, instead of `main`. Read it with `cf config get git.integration_branch`. This key is optional and defaults to empty:

- **Unset (default):** no change from plain historical behavior. Work branches fork from `main` and merge into `main`, named exactly `{index}-{type}.{name}` — no prefix.
- **Set** (e.g. `dev/erik`):
  - Work branches are named the same as when unset — `{index}-{type}.{name}` (e.g. `910-slice.foo`), with no prefix.
  - Work branches fork **from** `{integration_branch}`, not `main`.
  - Work branches merge **into** `{integration_branch}`, not `main`.
  - **Hard rule: never merge to `main` when `integration_branch` is set.** Syncing `{integration_branch}` from `main`, and eventually merging `{integration_branch}` into `main`, are PM-only actions outside automation scope — never perform either as part of normal slice/planning workflow, only if the Project Manager explicitly instructs it as a standalone action.

The integration branch affects **git topology only** (fork point and merge target) — not the branch name. It does not move documents or change where artifacts resolve — the `project-documents/user/...` layout under the branch is unchanged. The configured value is relative and contained (never absolute, never `..`, no trailing slash, no Windows drive/`\`); `cf` rejects invalid values when the key is set.

Before starting work on a slice, or before committing planning work:
1. read `cf config get git.integration_branch`; call its value (or `main` if empty) the **target**
2. for slice work, determine the branch name per the rules above (no prefix, regardless of target)
3. verify you are on the target or the expected slice branch
4. if the expected slice branch does not exist, create it from the target: `git checkout -b {branch-name} {target}`
5. if the branch already exists, switch to it: `git checkout {branch-name}`
6. never start work from another unit's branch unless explicitly instructed
7. if in doubt, STOP and ask the Project Manager

A slice branch merges into the target when its implementation is done. Do not hold a branch open across units. Do not delete branches unless specifically instructed to do so.

##### Commit Messages
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

##### Guidelines:
- Summary is imperative mood ("add X" not "added X" or "adds X")
- Keep to ~72 characters
- No period at end
- Scope is optional but useful in monorepos: `feat(core): add template variable resolution`

##### Examples:
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

- **Failure-Mode Enumeration:** For each new I/O path or message type, the author must be able to answer: "What if this hangs? What if it times out? What if the peer disconnects mid-send?" — explicitly, not implicitly. Each identified failure mode must be *observable* (log at WARNING+ or metric increment), not silent. At least one test should assert the failure mode produces the expected observable signal. Silent failure paths are bugs in waiting.

---

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

- **Failure-Mode Enumeration:** For each new I/O path or message type, the author must be able to answer: "What if this hangs? What if it times out? What if the peer disconnects mid-send?" — explicitly, not implicitly. Each identified failure mode must be *observable* (log at WARNING+ or metric increment), not silent. At least one test should assert the failure mode produces the expected observable signal. Silent failure paths are bugs in waiting.

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
* When starting or auditing a Python project, verify the required tooling configuration blocks defined in this guide (ruff, pyright) are present in `pyproject.toml`. If missing, add them before proceeding with substantive work. Mechanical enforcement is what makes these rules real; prose without config is aspirational.

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
- Required ruff configuration: every project MUST have a `[tool.ruff.lint]` block in `pyproject.toml` selecting at minimum `["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]`. `BLE` (blind-except) and `ASYNC` (async correctness) mechanically enforce the exception-handling and event-loop-discipline rules elsewhere in this guide. Copy-paste baseline:

    ```toml
    [tool.ruff]
    line-length = 88

    [tool.ruff.lint]
    select = ["E", "F", "W", "I", "UP", "BLE", "ASYNC", "B"]
    ```

- Use descriptive variable names; avoid single letters (except `x`, `i` in short loops/comprehensions).
- Prefer `f-strings` exclusively; avoid `.format()` or `%`.
- Use `pathlib` and its `Path` for all file/path operations, not `os.path.join` or similar
- One class per file for models/services; group related tiny utilities in `utils.py` or specific modules.

#### Functions & Error Handling
- Small, single-purpose functions (max 20 lines preferred)
- Use early returns (`guard clauses`) to flatten nesting.
- Explicit exception handling: catch specific exception types (`ValueError`, `KeyError`), never bare `except:` and never `except Exception: pass`. Every `try/except` must either (a) re-raise after logging at ERROR level via `logger.exception`, (b) handle a specific exception type with an inline comment justifying why swallowing is correct (e.g., `except ConnectionClosed: pass` for normal socket teardown), or (c) be a documented top-level handler at a process boundary. Swallowed exceptions are bugs by default; the `BLE` ruff rule set enforces this mechanically.
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
- Load-test tier (`tests/load/`): any code on the simulation, network, concurrency, or environment-layer paths requires at least one load test exercising a realistic configuration. Load tests assert on latency, throughput, or resource bounds — not just functional correctness. Unit and integration tests cannot catch event-loop starvation, contention, or budget overruns; load tests can. CI must gate load tests for slices touching these paths.
- Static Analysis: Strict `pyright` (preferred) or `mypy` — zero errors is a merge blocker, not a TODO. Required `[tool.pyright]` configuration:

    ```toml
    [tool.pyright]
    include = ["src", "tests"]
    pythonVersion = "3.12"
    typeCheckingMode = "strict"
    reportMissingImports = true
    reportMissingTypeStubs = false
    ```

    Test code is included in strict checking because bugs in tests can mask bugs in code. Adjust `pythonVersion` to match the project target.
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
- Any async def function that calls synchronous code must guarantee that the synchronous code runs in <1ms in the worst case. Anything CPU-bound must use run_in_executor, a dedicated thread, or a subprocess. Violating this blocks ALL I/O on the loop. Reviewers MUST verify this for any code that runs inside await-able functions.

#### Concurrency & Shared State
- Identify every access to shared mutable state. No read-during-mutate races between coroutines or between coroutines and executor threads.
- When state is published across thread or process boundaries, document the publication mechanism (`asyncio.Event`, sequence number, lock-free buffer, queue, etc.). Implicit publication via attribute assignment is not acceptable across boundaries.
- Introducing an executor (`run_in_executor`, `ProcessPoolExecutor`, threads) requires explicit review of every piece of state the executed code touches.

#### Security & Best Practices
- Secrets: Never commit secrets. Use `.env` files (loaded via `pydantic-settings`).
- Input: Validate everything entering the system via Pydantic.
- SQL: Always use parameterized queries (never f-string SQL).
- Randomness: Use `secrets` module for security tokens, `random` only for simulations.

### Raw Response

 ## Summary
CONCERNS

The changes correctly address issue #18 (missing input file guards) and issue #15 (dispatch artifact post-conditions) with strong fail-fast behavior and excellent test coverage. However, several design and convention concerns remain: the executor acquires a concrete dependency on `PhaseStepType`, result objects are mutated after return, and a fallback string is hardcoded in multiple places.

## Findings

### [CONCERN] Executor couples concretely to PhaseStepType for artifact post-condition
category: design
location: src/squadron/pipeline/executor.py:33
The generic executor imports `PhaseStepType` and performs an `isinstance(step_type_impl, PhaseStepType)` check inside `_execute_step_once` to decide whether to validate dispatch artifacts. This violates Open/Closed and Dependency Inversion: adding a new step type that produces artifacts would require editing the executor. Prefer a structural check (e.g., `getattr(step_type_impl, "expected_artifact_kind", None)`) or a small protocol so any step type can opt into post-condition validation without the executor knowing its concrete class.

### [CONCERN] ActionResult mutated in place after action execution
category: design
location: src/squadron/pipeline/executor.py:1055
In `_execute_step_once`, when a dispatch artifact post-condition fails, the code mutates the returned `ActionResult` in place (`result.success = False; result.error = artifact_error`). This assumes the result object is mutable and breaks the expectation that a returned result is a.snapshot. If `ActionResult` ever becomes frozen or adds validation logic, this will raise at runtime. Prefer constructing a new `ActionResult` with the error state instead of mutating the action's return value.

### [CONCERN] Magic fallback string "unknown" hardcoded in multiple modules
category: project-conventions
location: src/squadron/integrations/context_forge.py:172
The placeholder string `"unknown"` is duplicated as a fallback in `context_forge.py` (line ~172), `cli/commands/review.py` (line ~506), and `review/persistence.py` (line ~132). Per CLAUDE.md conventions, values used as defaults should not be hard-coded in multiple places. Extract a single constant (e.g., `UNKNOWN_PROJECT = "unknown"`) or centralize unknown-state handling so the placeholder is defined once and referenced everywhere.

### [CONCERN] Unchecked assumption that RunState.started_at is timezone-aware
category: error-handling
location: src/squadron/pipeline/executor.py:997
Inside `_execute_step_once`, `run_started_at` is loaded from `StateManager.load(run_id).started_at` and later compared against `datetime.fromtimestamp(full_path.stat().st_mtime, tz=UTC)` in `_check_dispatch_artifact_written`. If `StateManager` ever yields a naive datetime, this comparison raises an uncaught `TypeError`. The executor should normalize `run_started_at` to UTC explicitly or guard against naive datetimes before comparison to prevent latent crashes if the state serialization format changes.

### [PASS] Comprehensive fail-fast guards and failure-mode enumeration for missing inputs and artifacts
category: error-handling
location: src/squadron/cli/commands/review.py:315
Both issue #18 (file-existence validation via `missing_input_files`) and issue #15 (dispatch artifact post-conditions via `_check_dispatch_artifact_written`) are implemented with early failure, distinct warning-logged error messages for every identified failure mode, and extensive unit tests covering missing files, stale artifacts, unresolvable slices, permission errors, and non-numeric parameters. This is exactly the kind of observable, fail-fast behavior the standards require.
