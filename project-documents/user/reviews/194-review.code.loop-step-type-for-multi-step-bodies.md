---
docType: review
layer: project
reviewType: code
slice: loop-step-type-for-multi-step-bodies
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/194-slice.loop-step-type-for-multi-step-bodies.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260425
dateUpdated: 20260425
findings:
  - id: F001
    severity: concern
    category: documentation
    summary: "Missing docstrings on public methods"
    location: src/squadron/pipeline/steps/loop.py
  - id: F002
    severity: concern
    category: dry
    summary: "Code duplication in exhaustion handling"
    location: src/squadron/pipeline/executor.py:1033-1058
  - id: F003
    severity: concern
    category: style
    summary: "Import inside function body"
    location: src/squadron/pipeline/executor.py:987
  - id: F004
    severity: concern
    category: maintainability
    summary: "Variable reassignment in loop may cause confusion"
    location: src/squadron/pipeline/executor.py:1003
  - id: F005
    severity: pass
    category: testing
    summary: "Test coverage is comprehensive"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Nested loop ban validation is thorough"
  - id: F007
    severity: pass
    category: typing
    summary: "Type safety maintained throughout"
  - id: F008
    severity: pass
    category: testing
    summary: "Test file assertions correctly updated"
---

# Review: code — slice 194

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Missing docstrings on public methods

The `LoopStepType` class lacks docstrings on its public methods (`validate`, `expand`, `_validate_inner_steps`). While the module has a docstring, individual public API methods should document their purpose, parameters, and return values per project conventions. Other step types in this codebase (e.g., `ReviewStepType`) include method-level docstrings.

---

### [CONCERN] Code duplication in exhaustion handling

The `match` block handling `loop_config.on_exhaust` (lines 1033-1058) is structurally identical to the same logic in `_execute_loop_step` (lines ~989-1009). This violates DRY - the pattern should be extracted to a shared helper function that both code paths call.

---

### [CONCERN] Import inside function body

The `from typing import cast` import is placed inside the function body `_execute_loop_body` rather than at the top of the file. This is non-standard and reduces readability. Python style guidelines recommend module-level imports. While this pattern exists elsewhere in the codebase (e.g., `_execute_loop_step`), it should not be replicated in new code.

---

### [CONCERN] Variable reassignment in loop may cause confusion

The variable `iteration_action_results` is initialized before the outer `for` loop (line 999) but then immediately reassigned inside the loop on line 1003. The pre-loop assignment is unused, making the intent unclear. Consider either initializing it as `[]` and only appending, or remove the pre-loop assignment entirely:

```python
for iteration in range(1, loop_config.max + 1):
    iteration_action_results: list[ActionResult] = []  # Move inside loop only
```

---

### [PASS] Test coverage is comprehensive

The new test files provide excellent coverage:
- `test_loop.py`: 15 unit tests covering all validation rules including edge cases (bool for max, empty steps, nested loop bans)
- `test_executor_loop_body.py`: 8 integration tests covering all acceptance criteria (iteration behavior, exhaustion modes, transient failures, checkpoint pausing)
- `test_loop_validation.py`: 2 tests verifying nested-loop bans surface through `validate_pipeline()`

---

### [PASS] Nested loop ban validation is thorough

The `_validate_inner_steps` method correctly detects both forms of nested loops:
- Ban (a): inner step config carrying a `loop:` sub-field
- Ban (b): inner step type being `loop`

This prevents the complexity of recursive loop execution that the implementation doesn't support.

---

### [PASS] Type safety maintained throughout

All function signatures use proper type hints, including the complex `_execute_loop_body` function with its 13 parameters. The use of `cast(dict[str, object], ...)` for type safety is appropriate given the dynamic nature of the step configuration system.

---

### [PASS] Test file assertions correctly updated

Test files that assert on step counts correctly reflect the new pipeline structure (6 → 10 steps) with additional `summary` steps inserted between other step types. Step indices used in `test_from_step_skips_earlier_steps` and similar tests are appropriately updated to match the new pipeline layout.

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

Run `git diff 4c95519^..4346264 -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/src/squadron/pipeline/executor.py b/src/squadron/pipeline/executor.py
index 80d7f9e..bcbaa36 100644
--- a/src/squadron/pipeline/executor.py
+++ b/src/squadron/pipeline/executor.py
@@ -520,6 +520,7 @@ async def execute_pipeline(
     import squadron.pipeline.steps.devlog as _s_devlog  # noqa: F401
     import squadron.pipeline.steps.dispatch as _s_dispatch  # noqa: F401
     import squadron.pipeline.steps.fan_out as _s_fan_out  # noqa: F401
+    import squadron.pipeline.steps.loop as _s_loop  # noqa: F401
     import squadron.pipeline.steps.phase as _s_phase  # noqa: F401
     import squadron.pipeline.steps.review as _s_review  # noqa: F401
     import squadron.pipeline.steps.summary as _s_summary  # noqa: F401
@@ -539,6 +540,7 @@ async def execute_pipeline(
         _s_devlog,
         _s_dispatch,
         _s_fan_out,
+        _s_loop,
         _s_phase,
         _s_review,
         _s_summary,
@@ -656,6 +658,24 @@ async def execute_pipeline(
                 if _action_registry
                 else get_action,
             )
+        elif step.step_type == StepTypeName.LOOP:
+            step_result = await _execute_loop_body(
+                step=step,
+                resolved_config=resolved_config,
+                step_index=step_index,
+                merged_params=merged_params,
+                prior_outputs=prior_outputs,
+                pipeline_name=definition.name,
+                run_id=effective_run_id,
+                cwd=effective_cwd,
+                resolver=resolver,
+                cf_client=cf_client,
+                sdk_session=sdk_session,
+                get_step_type_fn=get_step_type,
+                get_action_fn=_action_registry.__getitem__
+                if _action_registry
+                else get_action,
+            )
         else:
             # Check for loop config
             loop_raw = resolved_config.get("loop")
@@ -952,6 +972,134 @@ async def _execute_loop_step(
             )
 
 
+async def _execute_loop_body(
+    *,
+    step: Any,
+    resolved_config: dict[str, object],
+    step_index: int,
+    merged_params: dict[str, object],
+    prior_outputs: dict[str, ActionResult],
+    pipeline_name: str,
+    run_id: str,
+    cwd: str,
+    resolver: Any,
+    cf_client: Any,
+    sdk_session: SDKExecutionSession | None = None,
+    get_step_type_fn: Any,
+    get_action_fn: Any,
+) -> StepResult:
+    """Execute a ``loop:`` step type with a multi-step body.
+
+    Mirrors ``_execute_loop_step`` semantics but iterates over a ``steps:``
+    body rather than a single action.  ``_parse_loop_config`` ignores the
+    ``steps`` key, so ``resolved_config`` is passed through unchanged.
+    """
+    loop_config = _parse_loop_config(resolved_config)
+
+    if loop_config.strategy is not None:
+        _logger.warning(
+            "Loop strategy '%s' not implemented, "
+            "falling back to basic max-iteration loop",
+            loop_config.strategy,
+        )
+
+    from typing import cast
+
+    inner_steps_raw = resolved_config.get("steps", [])
+    if isinstance(inner_steps_raw, list):
+        raw_list: list[dict[str, object]] = [
+            cast(dict[str, object], s)
+            for s in inner_steps_raw  # type: ignore[union-attr]
+            if isinstance(s, dict)
+        ]
+    else:
+        raw_list = []
+    inner_steps = _unpack_inner_steps(raw_list)
+
+    iteration_action_results: list[ActionResult] = []
+
+    for iteration in range(1, loop_config.max + 1):
+        iteration_action_results = []
+
+        for inner_step in inner_steps:
+            inner_resolved = resolve_placeholders(inner_step.config, merged_params)
+            inner_result = await _execute_step_once(
+                step=inner_step,
+                resolved_config=inner_resolved,
+                step_index=step_index,
+                merged_params=merged_params,
+                prior_outputs=prior_outputs,
+                pipeline_name=pipeline_name,
+                run_id=run_id,
+                cwd=cwd,
+                resolver=resolver,
+                cf_client=cf_client,
+                sdk_session=sdk_session,
+                get_step_type_fn=get_step_type_fn,
+                get_action_fn=get_action_fn,
+                iteration=iteration,
+            )
+            iteration_action_results.extend(inner_result.action_results)
+
+            # Checkpoint pause short-circuits the loop immediately
+            if inner_result.status == ExecutionStatus.PAUSED:
+                return StepResult(
+                    step_name=step.name,
+                    step_type=step.step_type,
+                    status=ExecutionStatus.PAUSED,
+                    action_results=iteration_action_results,
+                    iteration=iteration,
+                )
+            # FAILED is transient — continue executing remaining inner steps
+
+        # Evaluate until condition after all inner steps complete
+        if loop_config.until is not None:
+            if evaluate_condition(loop_config.until, iteration_action_results):
+                return StepResult(
+                    step_name=step.name,
+                    step_type=step.step_type,
+                    status=ExecutionStatus.COMPLETED,
+                    action_results=iteration_action_results,
+                    iteration=iteration,
+                )
+        else:
+            # No until condition — complete after first full iteration
+            return StepResult(
+                step_name=step.name,
+                step_type=step.step_type,
+                status=ExecutionStatus.COMPLETED,
+                action_results=iteration_action_results,
+                iteration=iteration,
+            )
+
+    # Max iterations exhausted
+    match loop_config.on_exhaust:
+        case ExhaustBehavior.FAIL:
+            return StepResult(
+                step_name=step.name,
+                step_type=step.step_type,
+                status=ExecutionStatus.FAILED,
+                action_results=iteration_action_results,
+                iteration=loop_config.max,
+            )
+        case ExhaustBehavior.CHECKPOINT:
+            return StepResult(
+                step_name=step.name,
+                step_type=step.step_type,
+                status=ExecutionStatus.PAUSED,
+                action_results=iteration_action_results,
+                iteration=loop_config.max,
+            )
+        case ExhaustBehavior.SKIP:
+            return StepResult(
+                step_name=step.name,
+                step_type=step.step_type,
+                status=ExecutionStatus.SKIPPED,
+                action_results=iteration_action_results,
+                iteration=loop_config.max,
+            )
+
+
 def _unpack_inner_steps(raw_steps: list[dict[str, object]]) -> list[Any]:
     """Convert raw YAML step list to StepConfig objects.
 
diff --git a/src/squadron/pipeline/steps/__init__.py b/src/squadron/pipeline/steps/__init__.py
index 203891e..51b1b81 100644
--- a/src/squadron/pipeline/steps/__init__.py
+++ b/src/squadron/pipeline/steps/__init__.py
@@ -30,6 +30,7 @@ class StepTypeName(StrEnum):
     REVIEW = "review"
     EACH = "each"
     FAN_OUT = "fan_out"
+    LOOP = "loop"
     DEVLOG = "devlog"
 
 
diff --git a/src/squadron/pipeline/steps/loop.py b/src/squadron/pipeline/steps/loop.py
new file mode 100644
index 0000000..c6a1bbf
--- /dev/null
+++ b/src/squadron/pipeline/steps/loop.py
@@ -0,0 +1,170 @@
+"""LoopStepType — multi-step loop body with configurable retry semantics.
+
+expand() returns [] — the executor handles iteration directly via
+_execute_loop_body, mirroring the each and fan_out step patterns.
+"""
+
+from __future__ import annotations
+
+from typing import cast
+
+from squadron.pipeline.executor import ExhaustBehavior, LoopCondition
+from squadron.pipeline.models import StepConfig, ValidationError
+from squadron.pipeline.steps import StepTypeName, register_step_type
+
+
+class LoopStepType:
+    """Step type for multi-step loop bodies with retry semantics.
+
+    The ``steps`` body is executed per iteration; the ``until`` condition is
+    evaluated against the aggregated action results of each iteration.
+    Nested loop: steps are banned at validation time.
+    """
+
+    @property
+    def step_type(self) -> str:
+        return StepTypeName.LOOP
+
+    def validate(self, config: StepConfig) -> list[ValidationError]:  # noqa: C901
+        errors: list[ValidationError] = []
+        cfg = config.config
+        step_type = self.step_type
+
+        # max: required positive integer (bool is a subclass of int — reject it)
+        max_val = cfg.get("max")
+        if isinstance(max_val, bool) or not isinstance(max_val, int) or max_val < 1:
+            errors.append(
+                ValidationError(
+                    field="max",
+                    message="'max' is required and must be a positive integer",
+                    action_type=step_type,
+                )
+            )
+
+        # until: optional, must be a valid LoopCondition value
+        until_val = cfg.get("until")
+        if until_val is not None:
+            valid_until = [c.value for c in LoopCondition]
+            if until_val not in valid_until:
+                errors.append(
+                    ValidationError(
+                        field="until",
+                        message=(
+                            f"'until' must be one of {valid_until}, got: {until_val!r}"
+                        ),
+                        action_type=step_type,
+                    )
+                )
+
+        # on_exhaust: optional, must be a valid ExhaustBehavior value
+        on_exhaust_val = cfg.get("on_exhaust")
+        if on_exhaust_val is not None:
+            valid_exhaust = [b.value for b in ExhaustBehavior]
+            if on_exhaust_val not in valid_exhaust:
+                errors.append(
+                    ValidationError(
+                        field="on_exhaust",
+                        message=(
+                            f"'on_exhaust' must be one of {valid_exhaust}, "
+                            f"got: {on_exhaust_val!r}"
+                        ),
+                        action_type=step_type,
+                    )
+                )
+
+        # strategy: optional, must be a string (strategies implemented in slice 184)
+        strategy_val = cfg.get("strategy")
+        if strategy_val is not None and not isinstance(strategy_val, str):
+            errors.append(
+                ValidationError(
+                    field="strategy",
+                    message="'strategy' must be a string",
+                    action_type=step_type,
+                )
+            )
+
+        # steps: required, non-empty list
+        steps_val = cfg.get("steps")
+        if steps_val is None:
+            errors.append(
+                ValidationError(
+                    field="steps",
+                    message="'steps' is required",
+                    action_type=step_type,
+                )
+            )
+        elif not isinstance(steps_val, list):
+            errors.append(
+                ValidationError(
+                    field="steps",
+                    message="'steps' must be a list",
+                    action_type=step_type,
+                )
+            )
+        elif not steps_val:
+            errors.append(
+                ValidationError(
+                    field="steps",
+                    message="'steps' must be a non-empty list",
+                    action_type=step_type,
+                )
+            )
+        else:
+            errors.extend(
+                self._validate_inner_steps(cast(list[object], steps_val), step_type)
+            )
+
+        return errors
+
+    def _validate_inner_steps(
+        self,
+        steps: list[object],
+        step_type: str,
+    ) -> list[ValidationError]:
+        """Check nested-loop ban on each inner step."""
+        errors: list[ValidationError] = []
+        for idx, raw_inner in enumerate(steps):
+            if not isinstance(raw_inner, dict) or len(raw_inner) != 1:  # type: ignore[arg-type]
+                continue
+            inner_step = cast(dict[str, object], raw_inner)
+            inner_type = str(next(iter(inner_step)))
+            inner_cfg = inner_step[inner_type]
+            if isinstance(inner_cfg, dict):
+                inner_cfg_typed = cast(dict[str, object], inner_cfg)
+                inner_name = str(inner_cfg_typed.get("name", f"{inner_type}-{idx}"))
+            else:
+                inner_name = f"{inner_type}-{idx}"
+            # Ban (a): inner step config carries a loop: sub-field
+            if isinstance(inner_cfg, dict) and "loop" in cast(
+                dict[str, object], inner_cfg
+            ):
+                errors.append(
+                    ValidationError(
+                        field="steps",
+                        message=(
+                            f"inner step '{inner_name}' may not carry a 'loop:' "
+                            f"sub-field; nested loops are not supported in v1"
+                        ),
+                        action_type=step_type,
+                    )
+                )
+            # Ban (b): inner step type is loop
+            if inner_type == StepTypeName.LOOP:
+                errors.append(
+                    ValidationError(
+                        field="steps",
+                        message=(
+                            f"inner step '{inner_name}' may not be of type 'loop'; "
+                            f"nested loops are not supported in v1"
+                        ),
+                        action_type=step_type,
+                    )
+                )
+        return errors
+
+    def expand(self, config: StepConfig) -> list[tuple[str, dict[str, object]]]:
+        """Return empty — executor handles iteration via _execute_loop_body."""
+        return []
+
+
+register_step_type(StepTypeName.LOOP, LoopStepType())
diff --git a/tests/pipeline/steps/test_loop.py b/tests/pipeline/steps/test_loop.py
new file mode 100644
index 0000000..6cc3e4e
--- /dev/null
+++ b/tests/pipeline/steps/test_loop.py
@@ -0,0 +1,155 @@
+"""Unit tests for LoopStepType — validation, expand, and registration."""
+
+from __future__ import annotations
+
+import squadron.pipeline.steps.loop  # noqa: F401 — trigger registration
+from squadron.pipeline.models import StepConfig
+from squadron.pipeline.steps import get_step_type
+from squadron.pipeline.steps.loop import LoopStepType
+
+# ---------------------------------------------------------------------------
+# Helpers
+# ---------------------------------------------------------------------------
+
+
+def _step(config: dict[str, object]) -> StepConfig:
+    return StepConfig(step_type="loop", name="test-loop", config=config)
+
+
+def _make() -> LoopStepType:
+    return LoopStepType()
+
+
+def _fields(errors: list) -> list[str]:
+    return [e.field for e in errors]
+
+
+def _messages(errors: list) -> list[str]:
+    return [e.message for e in errors]
+
+
+# ---------------------------------------------------------------------------
+# Task 5 — Validation rules
+# ---------------------------------------------------------------------------
+
+
+def test_missing_max_produces_error() -> None:
+    errors = _make().validate(_step({"steps": [{"review": {}}]}))
+    assert "max" in _fields(errors)
+
+
+def test_max_not_int_produces_error() -> None:
+    errors = _make().validate(_step({"max": "3", "steps": [{"review": {}}]}))
+    assert "max" in _fields(errors)
+
+
+def test_max_zero_produces_error() -> None:
+    errors = _make().validate(_step({"max": 0, "steps": [{"review": {}}]}))
+    assert "max" in _fields(errors)
+
+
+def test_max_negative_produces_error() -> None:
+    errors = _make().validate(_step({"max": -1, "steps": [{"review": {}}]}))
+    assert "max" in _fields(errors)
+
+
+def test_invalid_until_value_produces_error() -> None:
+    errors = _make().validate(
+        _step({"max": 3, "until": "never", "steps": [{"review": {}}]})
+    )
+    assert "until" in _fields(errors)
+    assert any("never" in m for m in _messages(errors))
+
+
+def test_invalid_on_exhaust_value_produces_error() -> None:
+    errors = _make().validate(
+        _step({"max": 3, "on_exhaust": "retry", "steps": [{"review": {}}]})
+    )
+    assert "on_exhaust" in _fields(errors)
+
+
+def test_strategy_not_string_produces_error() -> None:
+    errors = _make().validate(
+        _step({"max": 3, "strategy": 42, "steps": [{"review": {}}]})
+    )
+    assert "strategy" in _fields(errors)
+
+
+def test_missing_steps_produces_error() -> None:
+    errors = _make().validate(_step({"max": 3}))
+    assert "steps" in _fields(errors)
+
+
+def test_steps_not_list_produces_error() -> None:
+    errors = _make().validate(_step({"max": 3, "steps": "bad"}))
+    assert "steps" in _fields(errors)
+
+
+def test_steps_empty_list_produces_error() -> None:
+    errors = _make().validate(_step({"max": 3, "steps": []}))
+    assert "steps" in _fields(errors)
+
+
+def test_inner_step_with_loop_subfield_produces_nested_loop_error() -> None:
+    """Ban (a): inner step config carries a loop: sub-field."""
+    errors = _make().validate(
+        _step(
+            {
+                "max": 3,
+                "steps": [{"review": {"loop": {"max": 2}}}],
+            }
+        )
+    )
+    assert "steps" in _fields(errors)
+    assert any("loop:" in m and "sub-field" in m for m in _messages(errors))
+
+
+def test_inner_step_with_loop_type_produces_nested_loop_error() -> None:
+    """Ban (b): inner step type is loop."""
+    errors = _make().validate(
+        _step(
+            {
+                "max": 3,
+                "steps": [{"loop": {"max": 2, "steps": [{"review": {}}]}}],
+            }
+        )
+    )
+    assert "steps" in _fields(errors)
+    assert any("type 'loop'" in m for m in _messages(errors))
+
+
+def test_valid_config_no_errors() -> None:
+    """Minimal valid config — max, steps, no optional fields."""
+    errors = _make().validate(_step({"max": 3, "steps": [{"review": {}}]}))
+    assert errors == []
+
+
+def test_valid_config_with_all_options_no_errors() -> None:
+    """All optional fields with valid values produce zero errors."""
+    errors = _make().validate(
+        _step(
+            {
+                "max": 5,
+                "until": "review.pass",
+                "on_exhaust": "checkpoint",
+                "strategy": "weighted-decay",
+                "steps": [{"dispatch": {}}, {"review": {}}],
+            }
+        )
+    )
+    assert errors == []
+
+
+# ---------------------------------------------------------------------------
+# Task 6 — expand() and registration
+# ---------------------------------------------------------------------------
+
+
+def test_expand_returns_empty_list() -> None:
+    result = _make().expand(_step({"max": 3, "steps": [{"review": {}}]}))
+    assert result == []
+
+
+def test_get_step_type_returns_loop_step_type_instance() -> None:
+    impl = get_step_type("loop")
+    assert isinstance(impl, LoopStepType)
diff --git a/tests/pipeline/test_cli_integration.py b/tests/pipeline/test_cli_integration.py
index 4cd9c76..a94e1dd 100644
--- a/tests/pipeline/test_cli_integration.py
+++ b/tests/pipeline/test_cli_integration.py
@@ -117,14 +117,14 @@ class TestCliIntegration:
             )
 
         assert result.status == ExecutionStatus.COMPLETED
-        assert len(result.step_results) == 6
+        assert len(result.step_results) == 10
 
         # State file should be loadable
         mgr = StateManager(runs_dir=tmp_path)
         runs = mgr.list_runs()
         assert len(runs) == 1
         assert runs[0].status == "completed"
-        assert len(runs[0].completed_steps) == 6
+        assert len(runs[0].completed_steps) == 10
 
     @pytest.mark.asyncio
     async def test_state_file_loadable_after_run(self, tmp_path: Path) -> None:
@@ -187,7 +187,7 @@ class TestCliIntegration:
 
         final = mgr.load(run_id)
         assert final.status == "completed"
-        assert len(final.completed_steps) == 6
+        assert len(final.completed_steps) == 10
 
     # -------------------------------------------------------------------
     # T18: --from mid-process adoption
@@ -195,22 +195,21 @@ class TestCliIntegration:
 
     @pytest.mark.asyncio
     async def test_from_step_skips_earlier_steps(self, tmp_path: Path) -> None:
-        """Starting from 'implement-3' skips design/tasks/compact."""
+        """Starting from 'implement-5' skips design/tasks/summary/compact/summary."""
         with patch("squadron.cli.commands.run._check_cf"):
             result = await _run_pipeline(
                 "slice",
                 {"slice": "191"},
                 runs_dir=tmp_path,
-                from_step="implement-3",
+                from_step="implement-5",
                 _action_registry=_success_registry(),
             )
 
         assert result.status == ExecutionStatus.COMPLETED
         completed_names = [sr.step_name for sr in result.step_results]
-        # Only implement-3 and devlog-4 should be in results
         assert "design-0" not in completed_names
         assert "tasks-1" not in completed_names
-        assert "implement-3" in completed_names
+        assert "implement-5" in completed_names
 
     # -------------------------------------------------------------------
     # T19: Dry-run produces no state file
diff --git a/tests/pipeline/test_executor_integration.py b/tests/pipeline/test_executor_integration.py
index 6738ff2..4f4f489 100644
--- a/tests/pipeline/test_executor_integration.py
+++ b/tests/pipeline/test_executor_integration.py
@@ -68,7 +68,7 @@ class TestSliceLifecycleIntegration:
         )
 
         assert result.status == ExecutionStatus.COMPLETED
-        assert len(result.step_results) == 6
+        assert len(result.step_results) == 10
         assert all(sr.status == ExecutionStatus.COMPLETED for sr in result.step_results)
 
     @pytest.mark.asyncio
@@ -86,9 +86,8 @@ class TestSliceLifecycleIntegration:
             _action_registry=registry,
         )
 
-        assert len(received) == 6
+        assert len(received) == 10
         step_names = [sr.step_name for sr in received]
-        # All 5 lifecycle steps should appear in order
         assert step_names[0].startswith("design")
         assert step_names[-1].startswith("devlog")
 
@@ -97,20 +96,21 @@ class TestSliceLifecycleIntegration:
         definition = _no_project_pipeline("slice")
         registry = _success_registry()
 
-        # compact-2 is the third step (0-indexed)
+        # compact-3 is the fourth step (0-indexed)
         result = await execute_pipeline(
             definition,
             {"slice": "149"},
             resolver=MagicMock(),
             cf_client=MagicMock(),
-            start_from="compact-2",
+            start_from="compact-3",
             _action_registry=registry,
         )
 
         assert result.status == ExecutionStatus.COMPLETED
-        # Should only have 4 steps: compact, implement, compact, devlog
-        assert len(result.step_results) == 4
-        assert result.step_results[0].step_name == "compact-2"
+        # Should have 7 steps: compact-3, summary-4, implement-5, summary-6,
+        # compact-7, summary-8, devlog-9
+        assert len(result.step_results) == 7
+        assert result.step_results[0].step_name == "compact-3"
 
     @pytest.mark.asyncio
     async def test_missing_required_param_slice(self) -> None:
diff --git a/tests/pipeline/test_executor_loop_body.py b/tests/pipeline/test_executor_loop_body.py
new file mode 100644
index 0000000..7f77cfa
--- /dev/null
+++ b/tests/pipeline/test_executor_loop_body.py
@@ -0,0 +1,365 @@
+"""Integration tests for _execute_loop_body — multi-step loop: step type."""
+
+from __future__ import annotations
+
+from unittest.mock import AsyncMock, MagicMock
+
+import pytest
+
+import squadron.pipeline.steps.loop  # noqa: F401 — trigger LoopStepType registration
+from squadron.pipeline.executor import ExecutionStatus, execute_pipeline
+from squadron.pipeline.models import ActionResult, PipelineDefinition, StepConfig
+from squadron.pipeline.steps import register_step_type
+
+# ---------------------------------------------------------------------------
+# Test helpers
+# ---------------------------------------------------------------------------
+
+
+def _action_result(
+    success: bool,
+    action_type: str,
+    verdict: str | None = None,
+    paused: bool = False,
+) -> ActionResult:
+    outputs: dict[str, object] = {}
+    if paused:
+        outputs["checkpoint"] = "paused"
+    return ActionResult(
+        success=success,
+        action_type=action_type,
+        outputs=outputs,
+        verdict=verdict,
+    )
+
+
+def _mock_action(results: list[ActionResult]) -> MagicMock:
+    action = MagicMock()
+    action.execute = AsyncMock(side_effect=results)
+    return action
+
+
+def _mock_step_type(
+    action_pairs: list[tuple[str, dict[str, object]]],
+) -> MagicMock:
+    st = MagicMock()
+    st.expand.return_value = action_pairs
+    return st
+
+
+def _loop_step(name: str, config: dict[str, object]) -> StepConfig:
+    return StepConfig(step_type="loop", name=name, config=config)
+
+
+def _pipeline(steps: list[StepConfig]) -> PipelineDefinition:
+    return PipelineDefinition(
+        name="test-loop-body",
+        description="test",
+        params={},
+        steps=steps,
+    )
+
+
+# ---------------------------------------------------------------------------
+# Task 10 — passes after iteration 1
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_loop_body_completes_on_iteration_1() -> None:
+    """Body containing one inner step; PASS review exits on iteration 1."""
+    pass_result = _action_result(True, "review", verdict="PASS")
+    review_action = _mock_action([pass_result])
+
+    inner_st = _mock_step_type([("review", {})])
+    register_step_type("_lb_inner_t10", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "my-loop",
+                {
+                    "max": 3,
+                    "until": "review.pass",
+                    "steps": [{"_lb_inner_t10": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"review": review_action},
+    )
+
+    assert result.status == ExecutionStatus.COMPLETED
+    step_result = result.step_results[0]
+    assert step_result.iteration == 1
+    assert any(ar.verdict == "PASS" for ar in step_result.action_results)
+
+
+# ---------------------------------------------------------------------------
+# Task 11 — retries to PASS on iteration N
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_loop_body_retries_to_pass_on_iteration_3() -> None:
+    """Body retries until PASS on iteration 3; earlier iterations return CONCERNS."""
+    results = [
+        _action_result(True, "review", verdict="CONCERNS"),
+        _action_result(True, "review", verdict="CONCERNS"),
+        _action_result(True, "review", verdict="PASS"),
+    ]
+    review_action = _mock_action(results)
+
+    inner_st = _mock_step_type([("review", {})])
+    register_step_type("_lb_inner_t11", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "my-loop",
+                {
+                    "max": 5,
+                    "until": "review.pass",
+                    "steps": [{"_lb_inner_t11": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"review": review_action},
+    )
+
+    assert result.status == ExecutionStatus.COMPLETED
+    step_result = result.step_results[0]
+    assert step_result.iteration == 3
+    # Final iteration's results only
+    assert any(ar.verdict == "PASS" for ar in step_result.action_results)
+
+
+# ---------------------------------------------------------------------------
+# Task 12 — exhaustion modes
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_loop_body_exhaustion_fail() -> None:
+    """Never reaches PASS with max=2 and on_exhaust=fail → FAILED."""
+    results = [
+        _action_result(True, "review", verdict="CONCERNS"),
+        _action_result(True, "review", verdict="CONCERNS"),
+    ]
+    review_action = _mock_action(results)
+
+    inner_st = _mock_step_type([("review", {})])
+    register_step_type("_lb_inner_t12_fail", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "exhaust-fail",
+                {
+                    "max": 2,
+                    "until": "review.pass",
+                    "on_exhaust": "fail",
+                    "steps": [{"_lb_inner_t12_fail": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"review": review_action},
+    )
+
+    assert result.status == ExecutionStatus.FAILED
+    assert result.step_results[0].iteration == 2
+
+
+@pytest.mark.asyncio
+async def test_loop_body_exhaustion_checkpoint() -> None:
+    """Never reaches PASS with max=2 and on_exhaust=checkpoint → PAUSED."""
+    results = [
+        _action_result(True, "review", verdict="CONCERNS"),
+        _action_result(True, "review", verdict="CONCERNS"),
+    ]
+    review_action = _mock_action(results)
+
+    inner_st = _mock_step_type([("review", {})])
+    register_step_type("_lb_inner_t12_ckpt", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "exhaust-ckpt",
+                {
+                    "max": 2,
+                    "until": "review.pass",
+                    "on_exhaust": "checkpoint",
+                    "steps": [{"_lb_inner_t12_ckpt": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"review": review_action},
+    )
+
+    assert result.status == ExecutionStatus.PAUSED
+    assert result.step_results[0].iteration == 2
+
+
+@pytest.mark.asyncio
+async def test_loop_body_exhaustion_skip() -> None:
+    """Never reaches PASS with max=2 and on_exhaust=skip → SKIPPED."""
+    results = [
+        _action_result(True, "review", verdict="CONCERNS"),
+        _action_result(True, "review", verdict="CONCERNS"),
+    ]
+    review_action = _mock_action(results)
+
+    inner_st = _mock_step_type([("review", {})])
+    register_step_type("_lb_inner_t12_skip", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "exhaust-skip",
+                {
+                    "max": 2,
+                    "until": "review.pass",
+                    "on_exhaust": "skip",
+                    "steps": [{"_lb_inner_t12_skip": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"review": review_action},
+    )
+
+    # SKIPPED steps do not abort the pipeline — pipeline result is COMPLETED
+    assert result.status == ExecutionStatus.COMPLETED
+    assert result.step_results[0].status == ExecutionStatus.SKIPPED
+    assert result.step_results[0].iteration == 2
+
+
+# ---------------------------------------------------------------------------
+# Task 13 — inner failure is transient
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_inner_failure_is_transient_second_step_still_runs() -> None:
+    """First inner step fails on iteration 1; second still runs and produces PASS.
+
+    FAILED status on an inner step does not abort the iteration — execution
+    continues to the next inner step so the until condition can be evaluated.
+    """
+    fail_result = _action_result(False, "dispatch")
+    pass_result = _action_result(True, "review", verdict="PASS")
+
+    dispatch_action = _mock_action([fail_result])
+    review_action = _mock_action([pass_result])
+
+    failing_inner = _mock_step_type([("dispatch", {})])
+    passing_inner = _mock_step_type([("review", {})])
+
+    register_step_type("_lb_failing_inner_t13", failing_inner)
+    register_step_type("_lb_passing_inner_t13", passing_inner)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "transient-fail",
+                {
+                    "max": 3,
+                    "until": "review.pass",
+                    "steps": [
+                        {"_lb_failing_inner_t13": {}},
+                        {"_lb_passing_inner_t13": {}},
+                    ],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={
+            "dispatch": dispatch_action,
+            "review": review_action,
+        },
+    )
+
+    assert result.status == ExecutionStatus.COMPLETED
+    step_result = result.step_results[0]
+    assert step_result.iteration == 1
+    # Both inner action results captured
+    assert len(step_result.action_results) == 2
+
+
+# ---------------------------------------------------------------------------
+# Task 14 — checkpoint pause short-circuits the loop
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_checkpoint_pause_stops_loop_body() -> None:
+    """An inner step that pauses on a checkpoint stops the loop immediately."""
+    ckpt_result = _action_result(True, "checkpoint", paused=True)
+    ckpt_action = _mock_action([ckpt_result])
+
+    inner_st = _mock_step_type([("checkpoint", {})])
+    register_step_type("_lb_ckpt_inner_t14", inner_st)
+
+    pipeline = _pipeline(
+        [
+            _loop_step(
+                "pause-loop",
+                {
+                    "max": 5,
+                    "steps": [{"_lb_ckpt_inner_t14": {}}],
+                },
+            )
+        ]
+    )
+
+    result = await execute_pipeline(
+        pipeline,
+        {},
+        resolver=MagicMock(),
+        cf_client=MagicMock(),
+        _action_registry={"checkpoint": ckpt_action},
+    )
+
+    assert result.status == ExecutionStatus.PAUSED
+    step_result = result.step_results[0]
+    assert step_result.iteration == 1
diff --git a/tests/pipeline/test_loader.py b/tests/pipeline/test_loader.py
index 0c88942..0d93b39 100644
--- a/tests/pipeline/test_loader.py
+++ b/tests/pipeline/test_loader.py
@@ -35,7 +35,7 @@ class TestLoadPipelineBuiltIn:
         )
         assert isinstance(defn, PipelineDefinition)
         assert defn.name == "slice"
-        assert len(defn.steps) == 6
+        assert len(defn.steps) == 10
 
     def test_unknown_name_raises(self) -> None:
         with pytest.raises(FileNotFoundError, match="no-such-pipeline"):
diff --git a/tests/pipeline/test_loader_integration.py b/tests/pipeline/test_loader_integration.py
index fadd734..f4b2a41 100644
--- a/tests/pipeline/test_loader_integration.py
+++ b/tests/pipeline/test_loader_integration.py
@@ -49,14 +49,18 @@ class TestBuiltInPipelineStructure:
             project_dir=_NONEXISTENT,
             user_dir=_NONEXISTENT,
         )
-        assert len(defn.steps) == 6
+        assert len(defn.steps) == 10
         step_types = [s.step_type for s in defn.steps]
         assert step_types == [
             "design",
             "tasks",
+            "summary",
             "compact",
+            "summary",
             "implement",
+            "summary",
             "compact",
+            "summary",
             "devlog",
         ]
 
diff --git a/tests/pipeline/test_loop_validation.py b/tests/pipeline/test_loop_validation.py
new file mode 100644
index 0000000..979112c
--- /dev/null
+++ b/tests/pipeline/test_loop_validation.py
@@ -0,0 +1,86 @@
+"""Integration tests for loop: nested-loop validation via validate_pipeline.
+
+Tasks 15-16: verify the nested-loop ban surfaces through the full
+validate_pipeline() path, not just through LoopStepType.validate() directly.
+"""
+
+from __future__ import annotations
+
+import squadron.pipeline.steps.loop  # noqa: F401 — trigger registration
+from squadron.pipeline.loader import validate_pipeline
+from squadron.pipeline.models import PipelineDefinition, StepConfig
+
+
+def _pipeline_with_loop(loop_cfg: dict[str, object]) -> PipelineDefinition:
+    return PipelineDefinition(
+        name="test",
+        description="test",
+        params={},
+        steps=[StepConfig(step_type="loop", name="outer-loop", config=loop_cfg)],
+    )
+
+
+# ---------------------------------------------------------------------------
+# Task 15 — nested-loop ban: sub-field form
+# ---------------------------------------------------------------------------
+
+
+def test_inner_step_with_loop_subfield_fails_validation() -> None:
+    """loop: body containing an inner step with loop: sub-field → ValidationError.
+
+    The inner step (review:) carries a loop: sub-field. validate_pipeline()
+    must return an error naming the inner step and the violation.
+    """
+    pipeline = _pipeline_with_loop(
+        {
+            "max": 3,
+            "until": "review.pass",
+            "steps": [
+                {"review": {"loop": {"max": 2, "until": "review.pass"}}},
+            ],
+        }
+    )
+
+    errors = validate_pipeline(pipeline)
+
+    assert errors, "expected at least one validation error"
+    messages = [e.message for e in errors]
+    assert any("sub-field" in m and "nested" in m for m in messages), (
+        f"expected nested-loop sub-field error, got: {messages}"
+    )
+
+
+# ---------------------------------------------------------------------------
+# Task 16 — nested-loop ban: step-type form
+# ---------------------------------------------------------------------------
+
+
+def test_inner_loop_step_type_fails_validation() -> None:
+    """loop: body containing an inner loop: step type → ValidationError.
+
+    The inner step is itself a loop: type. validate_pipeline() must return
+    an error naming the inner step and identifying the type violation.
+    """
+    pipeline = _pipeline_with_loop(
+        {
+            "max": 3,
+            "until": "review.pass",
+            "steps": [
+                {
+                    "loop": {
+                        "max": 2,
+                        "until": "review.pass",
+                        "steps": [{"review": {}}],
+                    }
+                },
+            ],
+        }
+    )
+
+    errors = validate_pipeline(pipeline)
+
+    assert errors, "expected at least one validation error"
+    messages = [e.message for e in errors]
+    assert any("type 'loop'" in m and "nested" in m for m in messages), (
+        f"expected nested-loop type error, got: {messages}"
+    )
diff --git a/tests/pipeline/test_prompt_only_integration.py b/tests/pipeline/test_prompt_only_integration.py
index ece6adc..d7c4598 100644
--- a/tests/pipeline/test_prompt_only_integration.py
+++ b/tests/pipeline/test_prompt_only_integration.py
@@ -76,7 +76,7 @@ class TestPromptOnlyFullCycle:
             )
 
         # ---- Verify all steps were visited ----
-        assert len(step_names) == 6
+        assert len(step_names) == 10
 
         # ---- Verify next step returns None (all done) ----
         next_step = state_mgr.first_unfinished_step(run_id, definition)
@@ -84,16 +84,20 @@ class TestPromptOnlyFullCycle:
 
         # ---- Verify state file ----
         state = state_mgr.load(run_id)
-        assert len(state.completed_steps) == 6
+        assert len(state.completed_steps) == 10
 
         # Verify step types are in expected order
         step_types = [s.step_type for s in state.completed_steps]
         assert step_types == [
             "design",
             "tasks",
+            "summary",
             "compact",
+            "summary",
             "implement",
+            "summary",
             "compact",
+            "summary",
             "devlog",
         ]
 
@@ -151,14 +155,14 @@ class TestPromptOnlyFullCycle:
         resolver = ModelResolver(pipeline_model="sonnet")
         params: dict[str, object] = {"slice": "152"}
 
-        # compact is step index 2
-        compact_step = definition.steps[2]
+        # compact is step index 3 (preceded by design, tasks, summary)
+        compact_step = definition.steps[3]
         assert compact_step.step_type == "compact"
 
         instructions = render_step_instructions(
             compact_step,
-            step_index=2,
-            total_steps=6,
+            step_index=3,
+            total_steps=10,
             params=params,
             resolver=resolver,
             run_id="run-test",
diff --git a/tests/pipeline/test_state_integration.py b/tests/pipeline/test_state_integration.py
index cb229b9..fb5f50c 100644
--- a/tests/pipeline/test_state_integration.py
+++ b/tests/pipeline/test_state_integration.py
@@ -113,7 +113,7 @@ class TestStateIntegration:
 
         state = mgr.load(run_id)
         assert state.status == "completed"
-        assert len(state.completed_steps) == 6
+        assert len(state.completed_steps) == 10
         step_names = [s.step_name for s in state.completed_steps]
         assert any("design" in n for n in step_names)
         assert any("devlog" in n for n in step_names)
@@ -161,6 +161,6 @@ class TestStateIntegration:
 
         final = mgr.load(run_id)
         assert final.status == "completed"
-        # All 5 steps should be in completed_steps across both segments
-        assert len(final.completed_steps) == 6
+        # All 10 steps should be in completed_steps across both segments
+        assert len(final.completed_steps) == 10
         _ = prior_outputs  # consumed by executor internally

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
When working on a slice, use a branch named after the slice (without the `.md` extension but with the numeric index prefix).

Before starting implementation work on a slice:
1. verify you are on main or the expected slice branch
2. if the expected slice branch does not exist, create it from `main`: `git checkout -b {branch-name}`
3. If the slice branch already exists, switch to it: `git checkout {branch-name}`
4. Never start slice work from another slice's branch unless explicitly instructed
5. If in doubt, STOP and ask the Project Manager

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
[overall assessment: CONCERNS]

## Findings

### [CONCERN] Missing docstrings on public methods
category: documentation
location: src/squadron/pipeline/steps/loop.py

The `LoopStepType` class lacks docstrings on its public methods (`validate`, `expand`, `_validate_inner_steps`). While the module has a docstring, individual public API methods should document their purpose, parameters, and return values per project conventions. Other step types in this codebase (e.g., `ReviewStepType`) include method-level docstrings.

---

### [CONCERN] Code duplication in exhaustion handling
category: dry
location: src/squadron/pipeline/executor.py:1033-1058

The `match` block handling `loop_config.on_exhaust` (lines 1033-1058) is structurally identical to the same logic in `_execute_loop_step` (lines ~989-1009). This violates DRY - the pattern should be extracted to a shared helper function that both code paths call.

---

### [CONCERN] Import inside function body
category: style
location: src/squadron/pipeline/executor.py:987

The `from typing import cast` import is placed inside the function body `_execute_loop_body` rather than at the top of the file. This is non-standard and reduces readability. Python style guidelines recommend module-level imports. While this pattern exists elsewhere in the codebase (e.g., `_execute_loop_step`), it should not be replicated in new code.

---

### [CONCERN] Variable reassignment in loop may cause confusion
category: maintainability
location: src/squadron/pipeline/executor.py:1003

The variable `iteration_action_results` is initialized before the outer `for` loop (line 999) but then immediately reassigned inside the loop on line 1003. The pre-loop assignment is unused, making the intent unclear. Consider either initializing it as `[]` and only appending, or remove the pre-loop assignment entirely:

```python
for iteration in range(1, loop_config.max + 1):
    iteration_action_results: list[ActionResult] = []  # Move inside loop only
```

---

### [PASS] Test coverage is comprehensive
category: testing

The new test files provide excellent coverage:
- `test_loop.py`: 15 unit tests covering all validation rules including edge cases (bool for max, empty steps, nested loop bans)
- `test_executor_loop_body.py`: 8 integration tests covering all acceptance criteria (iteration behavior, exhaustion modes, transient failures, checkpoint pausing)
- `test_loop_validation.py`: 2 tests verifying nested-loop bans surface through `validate_pipeline()`

---

### [PASS] Nested loop ban validation is thorough
category: error-handling

The `_validate_inner_steps` method correctly detects both forms of nested loops:
- Ban (a): inner step config carrying a `loop:` sub-field
- Ban (b): inner step type being `loop`

This prevents the complexity of recursive loop execution that the implementation doesn't support.

---

### [PASS] Type safety maintained throughout
category: typing

All function signatures use proper type hints, including the complex `_execute_loop_body` function with its 13 parameters. The use of `cast(dict[str, object], ...)` for type safety is appropriate given the dynamic nature of the step configuration system.

---

### [PASS] Test file assertions correctly updated
category: testing

Test files that assert on step counts correctly reflect the new pipeline structure (6 → 10 steps) with additional `summary` steps inserted between other step types. Step indices used in `test_from_step_skips_earlier_steps` and similar tests are appropriately updated to match the new pipeline layout.
