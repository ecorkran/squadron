---
docType: review
layer: project
reviewType: code
slice: judge-gated-cycle-conventions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/303-slice.judge-gated-cycle-conventions.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260714
dateUpdated: 20260714
findings:
  - id: F001
    severity: fail
    category: uncategorized
    summary: "**What's solid:** ruff and pyright are clean on all changed source files; the dispatch-artifact-post-condition logic in "
    location: unverified
  - id: F002
    severity: note
    category: uncategorized
    summary: "2. Minor efficiency note: the run-state file is now re-read from disk on every `_execute_step_once` call for phase steps"
    location: unverified
---

# Review: code — slice 303

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

## Findings

### [FAIL] **What's solid:** ruff and pyright are clean on all changed source files; the dispatch-artifact-post-condition logic in 

### [NOTE] 2. Minor efficiency note: the run-state file is now re-read from disk on every `_execute_step_once` call for phase steps

3. Minor test-fixture staleness: `tests/pipeline/test_judge_cycle.py`'s `_slice_info()` dict doesn't include the newly-required `project` field; harmless today only because the persistence functions are mocked in that test.

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

Using tool: BashUsing tool: BashUsing tool: ReadUsing tool: ReadUsing tool: ReadUsing tool: ReadUsing tool: BashUsing tool: BashUsing tool: ReadUsing tool: BashUsing tool: ReadUsing tool: ReadUsing tool: BashUsing tool: BashUsing tool: BashUsing tool: BashUsing tool: BashUsing tool: BashClean. Now let's run the relevant test suite for these changes.Using tool: BashUsing tool: BashUsing tool: BashGood, this is well tested. Let's check the review_arch fallback path and `ContextForgeClient` test coverage, and `save_review_result` name computation edge cases (arch_name parsing).Using tool: BashGood coverage there too. Now let's check `review_arch` fallback test coverage for the `ContextForgeNotAvailable`/`ContextForgeError` path.Using tool: BashUsing tool: BashUsing tool: BashUsing tool: ReadUsing tool: ReadUsing tool: BashUsing tool: BashConfirmed — no test covers the numeric-index `arch` save path at all (neither before nor after this diff), so the new `ContextForgeClient().get_project()` resolution + fallback logic added in `review_arch` is untested in both branches. Let me double check the executor's `runs_dir` docstring/behavior consistency and then wrap up.Using tool: BashGood, that's consistent. I have enough to write up the findings.Using tool: ReportFindings## Summary
CONCERNS

Reviewed the diff `cbea86b^..7e3458d` covering `sq review` input-file validation (issue #18), the judge-cycle pipeline + verdict-override persistence, the phase-step dispatch artifact post-condition (issue #15), and project-name threading through review frontmatter.

**What's solid:** ruff and pyright are clean on all changed source files; the dispatch-artifact-post-condition logic in `executor.py` is unusually well tested (fresh/stale/absent artifact, unresolvable slice, non-numeric slice param, permission errors, implement-phase bypass, generic-dispatch bypass, and an explicit routing test proving a failed post-condition halts the step rather than silently advancing). `missing_input_files` and the CLI/pipeline hard-fail wiring for issue #18 are thoroughly covered, including cwd-relative resolution. Exception handling in the new code consistently fails closed and logs at WARNING per the failure-mode-enumeration rule. Full changed-file test suite (541 tests) passes.

**Gaps found:**
1. **CONFIRMED** — the new `ContextForgeClient().get_project()` fallback added to `review_arch`'s numeric-index save path (`review.py:505-509`) has no test exercising either branch (success or `ContextForgeNotAvailable`/`ContextForgeError` fallback to `"unknown"`); every existing arch-index test uses `--no-save`, which skips this code entirely.
2. Minor efficiency note: the run-state file is now re-read from disk on every `_execute_step_once` call for phase steps with an artifact kind, including every loop iteration, to fetch an immutable `started_at` — could be hoisted once per run.
3. Minor test-fixture staleness: `tests/pipeline/test_judge_cycle.py`'s `_slice_info()` dict doesn't include the newly-required `project` field; harmless today only because the persistence functions are mocked in that test.
