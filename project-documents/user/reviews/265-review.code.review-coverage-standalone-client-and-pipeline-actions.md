---
docType: review
layer: project
reviewType: code
slice: review-coverage-standalone-client-and-pipeline-actions
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/265-slice.review-coverage-standalone-client-and-pipeline-actions.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260901
dateUpdated: 20260901
reviewedSha: 414f0c4d7d7692bab9d88a866225f76d3801e7ab
---

# Review: code — slice 265

**Verdict:** CONCERNS
**Model:** claude-sonnet-5

No specific findings.

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
- One value, one source: `os.environ` and the pydantic settings object are
  different sources of truth — `.env` values loaded by settings are NOT in
  `os.environ`. Code that reads configuration must go through the settings
  object; a raw `os.environ.get()` beside a settings-based app silently reads
  a different (often empty) universe and fails without error.

---

---
description: SQL coding standards for PostgreSQL, pgvector, and TimescaleDB. Use when writing queries, migrations, schema definitions, database functions, or any code that connects to a database — including test fixtures and runners. Covers naming, indexing, query optimization, extension-specific patterns, and production-database protection.
paths: 
  - "**/*.sql"
  - "**/*.psql"
  - "**/migrations/**"
  - "**/schema.sql"
  - "**/test/**/*.py"
  - "**/tests/**/*.py"
  - "**/conftest.py"
---

### SQL and PostgreSQL Development Rules

#### Query Style & Formatting

- UPPERCASE SQL keywords: `SELECT`, `FROM`, `WHERE`, not `select`
- Lowercase table and column names with underscores: `user_accounts`
- Indent multi-line queries consistently (2 or 4 spaces)
- One column per line in SELECT for readability
- Leading commas in SELECT lists for easier modification
- Meaningful table aliases, avoid single letters

#### Query Optimization

- Always use EXPLAIN ANALYZE for performance tuning
- Create indexes for WHERE, JOIN, and ORDER BY columns
- Use partial indexes for filtered queries
- Prefer JOIN over subqueries when possible
- LIMIT queries during development testing
- Avoid SELECT * in production code
- Use EXISTS instead of COUNT for existence checks

#### PostgreSQL Best Practices

- Use appropriate data types: JSONB over JSON, TEXT over VARCHAR
- UUID for distributed IDs, SERIAL/BIGSERIAL for single-node
- Check constraints for data validation
- Foreign keys with appropriate CASCADE options
- Use transactions for multi-statement operations
- RETURNING clause to get modified data
- CTEs (WITH clauses) for complex queries

#### Naming & Schema Design

- Singular table names: `user` not `users`
- Primary key as `id` or `table_name_id`
- Foreign keys as `referenced_table_id`
- Boolean columns prefixed with `is_` or `has_`
- Timestamps: `created_at`, `updated_at` with timezone
- Use schemas to organize related tables
- Version control migrations with sequential numbering

#### Security & Safety

- Always use parameterized queries, never string concatenation
- GRANT minimum required privileges
- Use ROW LEVEL SECURITY for multi-tenant apps
- Sanitize all user input
- Prepared statements for repeated queries
- Connection pooling with appropriate limits
- Set statement_timeout for long-running queries

#### Production Database Protection

Distilled from a real production incident (test fixture truncated prod metadata)
and its recovery. These are deterministic-first: prefer a control the server or a
test can enforce over a rule someone must remember.

- **Split connection roles.** The application role gets DML only — no TRUNCATE
  (a separate grantable privilege), no DDL, no ownership, read-only on the
  migration ledger. Migrations and maintenance use a separate role/URL supplied
  only when doing that work. With this split, a test that leaks production
  credentials dies on `permission denied` instead of destroying tables.
- **Tests never read the production URL variable.** Test tiers use a dedicated
  test variable and throwaway databases created by the fixture itself. A fixture
  that issues TRUNCATE/DROP/ALTER/DELETE may only target a database it created.
  "Unit" is a directory name, not a property — nothing stops a file under
  `test/unit/` from opening a connection.
- **Enforce it mechanically, per tier.** A guard test scans every test file for
  reads of the production variable and fails on offenders (ratchet with a
  shrink-only allowlist if legacy readers exist). The scan must be
  multiline-aware — `os.environ.get(\n "VAR")` defeats a per-line grep.
  The absence of a guard in a tier is not evidence of safety.
- **Never inject a whole `.env` into a child process.** Pass an explicit list of
  named variables. A runner built to fix a parsing problem must not widen
  credential scope as a side effect.
- **`TRUNCATE ... CASCADE` destroys the FK closure, not the named tables.**
  Enumerate the closure before any CASCADE against a shared database.
- **Destructive and maintenance tooling** (restore, rechunk, repair) takes its
  DB URL from an explicit caller argument — never from ambient environment
  inside the tool. A restore aimed by an unset variable is the same failure
  mode the tool exists to repair. Refuse to run when the target does not look
  like the database the operation expects (verify signature tables/rows first).
- **Restore-by-replay heals the ledger, not the catalog.** Objects dropped while
  their creating migration is still recorded are invisible to replay. A restore
  tool must diff the live catalog against expectations; and after any incident,
  verify derived objects (matviews, continuous aggregates) by **content parity
  against source**, never by catalog presence — an object created or interrupted
  mid-incident is presumed damaged, and for an empty derived object,
  drop-and-recreate from its migration beats in-place repair.
- **Size backup priority by what cannot be re-derived** from providers or raw
  data, not by the last incident's blast radius.
- **Protect the host from runaway sessions:** `vm.overcommit_memory=2` on
  dedicated Postgres hosts so allocation failure hits the statement, not the
  OOM killer hitting the postmaster. For bulk rebuilds, run a watchdog that
  `pg_cancel_backend`s the working backend when free memory crosses a floor —
  cancellation releases memory instantly; the OOM killer takes the cluster.
  Note `work_mem` does not bound extension-internal allocations (e.g.
  TimescaleDB cagg materialization).
- **After a client-side timeout, `pg_cancel_backend` the server side** before
  running anything else; client disconnect does not cancel the backend.

#### pgvector Specific

- Use `vector` type for embeddings
- Create HNSW or IVFFlat indexes for similarity search
- Normalize vectors before storage when needed
- Use `<->` for L2 distance, `<#>` for inner product
- Batch insert embeddings for performance
- Consider dimension reduction for large vectors

#### TimescaleDB Specific

- Create hypertables for time-series data
- Use appropriate chunk intervals (typically 1 week to 1 month)
- Continuous aggregates for common queries
- Compression policies for older data
- Retention policies to manage data lifecycle
- Use time_bucket() for time-based aggregations
- Data retention policies with drop_chunks()

#### Performance & Monitoring

- Index foreign keys and commonly filtered columns
- VACUUM and ANALYZE regularly
- Monitor pg_stat_statements for slow queries
- Use connection pooling (PgBouncer/pgpool)
- Partition large tables by date or ID range
- Avoid excessive indexes (write performance cost)
- Use COPY for bulk inserts

#### Migrations & Maintenance

- Always reversible migrations when possible
- Test migrations on copy of production data
- Use IF NOT EXISTS for idempotent operations
- Document breaking changes
- Backup before structural changes
- Zero-downtime migrations with careful planning

---

---
description: Testing standards and best practices. Use when writing, modifying, or reviewing tests. Covers test structure, naming, mocking patterns, assertion style, coverage expectations, and database safety in tests.
paths: 
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/*.stories.*"
  - "src/stories/**/*"
  - "**/test_*.py"
  - "**/test/**/*.py"
  - "**/tests/**/*.py"
  - "**/conftest.py"
---

### Testing Rules

#### General Testing Philosophy

- **Write tests as you go** - Create unit tests while completing tasks, not at the end
- **Not strict TDD** - AI development doesn't require test-first, but tests should accompany implementation
- **Focus on value** - Test critical paths, edge cases, and business logic; don't test trivial code

#### JavaScript/TypeScript Testing

##### Test Framework
- **Prefer Vitest** over Jest for new projects (faster, better ESM support, compatible API)
- Use `vitest` for unit and integration tests
- Use `@testing-library/react` for component testing

##### Test Organization
- Use a centralized `tests/` directory at the package level, not colocated `__tests__/` directories inside `src/`.

** Directory Structure Example**:
``` markdown
packages/my-package/
  src/
    index.ts
    services/
      myService.ts
  tests/
    services/
      myService.test.ts
    integration/
      serverLifecycle.test.ts
  package.json
  tsconfig.json
```

*Note: Ensure `tsconfig.json` includes `tests/` for type checking but excludes it from build output.*

##### Test File Naming
- Unit tests: `{module}.test.ts` — mirrors the source file name
- Integration tests: `{feature}.integration.test.ts` or grouped in `tests/integration/`
- Test fixtures: `tests/fixtures/` directory

##### What to Test
- **Critical paths**: User workflows, data transformations, business logic
- **Edge cases**: Null/undefined values, empty arrays, boundary conditions
- **Error states**: How code handles failures, invalid input, network errors
- **Not trivial**: Don't test framework code, getters/setters, or obvious pass-throughs

##### Test Coverage
- Aim for meaningful coverage, not 100% coverage
- Critical business logic: high coverage
- UI components: test interactions and state changes
- Utilities and helpers: comprehensive edge case coverage

#### Python Testing

##### Test Framework
- Use `pytest` (industry standard)
- Place tests in `tests/` directory or `test_*.py` files
- Use fixtures for test data and setup

##### Test Organization
```
project/
├── src/
│   └── module.py
└── tests/
    └── test_module.py
```

##### Assertions
- Use pytest assertions: `assert result == expected`
- Use pytest-parametrize for multiple test cases
- Mock external dependencies at boundaries

#### Database Safety in Tests

Distilled from a real production incident: a test fixture handed production
credentials truncated six prod tables while its suite reported green. The full
rule set lives in `sql.md` ("Production Database Protection"); these are the
test-facing rules:

- **Tests never read the production DB URL variable.** Test code uses a
  dedicated test variable (admin URL for creating throwaway databases) and
  fixtures that create their own database. A fixture that issues
  TRUNCATE/DROP/ALTER/DELETE may only target a database it created itself.
- **"Unit" is a directory name, not a property.** Nothing stops a file under
  `test/unit/` from opening a database connection — DB-safety rules apply to
  every tier, and a scoped `DELETE` in a "unit" fixture can empty a production
  table while the suite passes.
- **Every tier gets a mechanical prod-URL guard test** that scans the tier's
  files for reads of the production variable and fails on offenders (shrink-only
  allowlist if legacy readers exist). The scan must be multiline-aware —
  `os.environ.get(\n "VAR")` defeats a per-line grep. The absence of a guard in
  a tier is not evidence of safety.
- **Never inject a whole `.env` into a test process.** Pass an explicit list of
  named variables; a runner that injects everything hands destructive fixtures
  credentials they were never meant to have.
- **Before running an unfamiliar test tier, read its conftest** for which URL
  its fixtures connect to and what they mutate.

#### Best Practices

##### When to Write Tests
- ✅ **During implementation** - Write tests as you build features
- ✅ **After bug fixes** - Add tests to prevent regression
- ✅ **Before refactoring** - Tests verify behavior stays consistent
- ❌ **Not at the very end** - Waiting until feature is "done" leads to skipped tests

##### Test Quality
- **Arrange-Act-Assert** pattern: Set up → Execute → Verify
- **One concept per test**: Each test should verify one thing
- **Readable test names**: Test name should describe what's being tested
- **Avoid test interdependence**: Tests should run independently in any order

##### Mocking and Stubbing
- Mock external services (APIs, databases, file system)
- Don't mock internal business logic - test it directly
- Use dependency injection to make mocking easier

#### Running Tests

##### Commands
```bash
# JavaScript/TypeScript
pnpm test              # Run all tests
pnpm test:watch        # Watch mode
pnpm test:coverage     # Coverage report

# Python
pytest                 # Run all tests
pytest -v              # Verbose output
pytest --cov           # Coverage report
```

##### CI/CD Integration
- Tests should run automatically on commit/PR
- Build should fail if tests fail
- Don't skip failing tests - fix them or remove them

#### Storybook (Optional)

- **enabled**: false (by default)
- Use Storybook for component documentation and visual testing
- Place stories in `src/stories` with `.stories.tsx` extension
- One story file per component, showing variants and states

### User Prompt

Review code in the project at: /Users/manta/source/repos/manta/squadron

Run `git diff ab7c3616a4756b0be5554ea517b535671c0940fd...265-slice.review-coverage-standalone-client-and-pipeline-actions -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

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
- One value, one source: `os.environ` and the pydantic settings object are
  different sources of truth — `.env` values loaded by settings are NOT in
  `os.environ`. Code that reads configuration must go through the settings
  object; a raw `os.environ.get()` beside a settings-based app silently reads
  a different (often empty) universe and fails without error.

---

---
description: SQL coding standards for PostgreSQL, pgvector, and TimescaleDB. Use when writing queries, migrations, schema definitions, database functions, or any code that connects to a database — including test fixtures and runners. Covers naming, indexing, query optimization, extension-specific patterns, and production-database protection.
paths: 
  - "**/*.sql"
  - "**/*.psql"
  - "**/migrations/**"
  - "**/schema.sql"
  - "**/test/**/*.py"
  - "**/tests/**/*.py"
  - "**/conftest.py"
---

### SQL and PostgreSQL Development Rules

#### Query Style & Formatting

- UPPERCASE SQL keywords: `SELECT`, `FROM`, `WHERE`, not `select`
- Lowercase table and column names with underscores: `user_accounts`
- Indent multi-line queries consistently (2 or 4 spaces)
- One column per line in SELECT for readability
- Leading commas in SELECT lists for easier modification
- Meaningful table aliases, avoid single letters

#### Query Optimization

- Always use EXPLAIN ANALYZE for performance tuning
- Create indexes for WHERE, JOIN, and ORDER BY columns
- Use partial indexes for filtered queries
- Prefer JOIN over subqueries when possible
- LIMIT queries during development testing
- Avoid SELECT * in production code
- Use EXISTS instead of COUNT for existence checks

#### PostgreSQL Best Practices

- Use appropriate data types: JSONB over JSON, TEXT over VARCHAR
- UUID for distributed IDs, SERIAL/BIGSERIAL for single-node
- Check constraints for data validation
- Foreign keys with appropriate CASCADE options
- Use transactions for multi-statement operations
- RETURNING clause to get modified data
- CTEs (WITH clauses) for complex queries

#### Naming & Schema Design

- Singular table names: `user` not `users`
- Primary key as `id` or `table_name_id`
- Foreign keys as `referenced_table_id`
- Boolean columns prefixed with `is_` or `has_`
- Timestamps: `created_at`, `updated_at` with timezone
- Use schemas to organize related tables
- Version control migrations with sequential numbering

#### Security & Safety

- Always use parameterized queries, never string concatenation
- GRANT minimum required privileges
- Use ROW LEVEL SECURITY for multi-tenant apps
- Sanitize all user input
- Prepared statements for repeated queries
- Connection pooling with appropriate limits
- Set statement_timeout for long-running queries

#### Production Database Protection

Distilled from a real production incident (test fixture truncated prod metadata)
and its recovery. These are deterministic-first: prefer a control the server or a
test can enforce over a rule someone must remember.

- **Split connection roles.** The application role gets DML only — no TRUNCATE
  (a separate grantable privilege), no DDL, no ownership, read-only on the
  migration ledger. Migrations and maintenance use a separate role/URL supplied
  only when doing that work. With this split, a test that leaks production
  credentials dies on `permission denied` instead of destroying tables.
- **Tests never read the production URL variable.** Test tiers use a dedicated
  test variable and throwaway databases created by the fixture itself. A fixture
  that issues TRUNCATE/DROP/ALTER/DELETE may only target a database it created.
  "Unit" is a directory name, not a property — nothing stops a file under
  `test/unit/` from opening a connection.
- **Enforce it mechanically, per tier.** A guard test scans every test file for
  reads of the production variable and fails on offenders (ratchet with a
  shrink-only allowlist if legacy readers exist). The scan must be
  multiline-aware — `os.environ.get(\n "VAR")` defeats a per-line grep.
  The absence of a guard in a tier is not evidence of safety.
- **Never inject a whole `.env` into a child process.** Pass an explicit list of
  named variables. A runner built to fix a parsing problem must not widen
  credential scope as a side effect.
- **`TRUNCATE ... CASCADE` destroys the FK closure, not the named tables.**
  Enumerate the closure before any CASCADE against a shared database.
- **Destructive and maintenance tooling** (restore, rechunk, repair) takes its
  DB URL from an explicit caller argument — never from ambient environment
  inside the tool. A restore aimed by an unset variable is the same failure
  mode the tool exists to repair. Refuse to run when the target does not look
  like the database the operation expects (verify signature tables/rows first).
- **Restore-by-replay heals the ledger, not the catalog.** Objects dropped while
  their creating migration is still recorded are invisible to replay. A restore
  tool must diff the live catalog against expectations; and after any incident,
  verify derived objects (matviews, continuous aggregates) by **content parity
  against source**, never by catalog presence — an object created or interrupted
  mid-incident is presumed damaged, and for an empty derived object,
  drop-and-recreate from its migration beats in-place repair.
- **Size backup priority by what cannot be re-derived** from providers or raw
  data, not by the last incident's blast radius.
- **Protect the host from runaway sessions:** `vm.overcommit_memory=2` on
  dedicated Postgres hosts so allocation failure hits the statement, not the
  OOM killer hitting the postmaster. For bulk rebuilds, run a watchdog that
  `pg_cancel_backend`s the working backend when free memory crosses a floor —
  cancellation releases memory instantly; the OOM killer takes the cluster.
  Note `work_mem` does not bound extension-internal allocations (e.g.
  TimescaleDB cagg materialization).
- **After a client-side timeout, `pg_cancel_backend` the server side** before
  running anything else; client disconnect does not cancel the backend.

#### pgvector Specific

- Use `vector` type for embeddings
- Create HNSW or IVFFlat indexes for similarity search
- Normalize vectors before storage when needed
- Use `<->` for L2 distance, `<#>` for inner product
- Batch insert embeddings for performance
- Consider dimension reduction for large vectors

#### TimescaleDB Specific

- Create hypertables for time-series data
- Use appropriate chunk intervals (typically 1 week to 1 month)
- Continuous aggregates for common queries
- Compression policies for older data
- Retention policies to manage data lifecycle
- Use time_bucket() for time-based aggregations
- Data retention policies with drop_chunks()

#### Performance & Monitoring

- Index foreign keys and commonly filtered columns
- VACUUM and ANALYZE regularly
- Monitor pg_stat_statements for slow queries
- Use connection pooling (PgBouncer/pgpool)
- Partition large tables by date or ID range
- Avoid excessive indexes (write performance cost)
- Use COPY for bulk inserts

#### Migrations & Maintenance

- Always reversible migrations when possible
- Test migrations on copy of production data
- Use IF NOT EXISTS for idempotent operations
- Document breaking changes
- Backup before structural changes
- Zero-downtime migrations with careful planning

---

---
description: Testing standards and best practices. Use when writing, modifying, or reviewing tests. Covers test structure, naming, mocking patterns, assertion style, coverage expectations, and database safety in tests.
paths: 
  - "**/*.test.*"
  - "**/*.spec.*"
  - "**/*.stories.*"
  - "src/stories/**/*"
  - "**/test_*.py"
  - "**/test/**/*.py"
  - "**/tests/**/*.py"
  - "**/conftest.py"
---

### Testing Rules

#### General Testing Philosophy

- **Write tests as you go** - Create unit tests while completing tasks, not at the end
- **Not strict TDD** - AI development doesn't require test-first, but tests should accompany implementation
- **Focus on value** - Test critical paths, edge cases, and business logic; don't test trivial code

#### JavaScript/TypeScript Testing

##### Test Framework
- **Prefer Vitest** over Jest for new projects (faster, better ESM support, compatible API)
- Use `vitest` for unit and integration tests
- Use `@testing-library/react` for component testing

##### Test Organization
- Use a centralized `tests/` directory at the package level, not colocated `__tests__/` directories inside `src/`.

** Directory Structure Example**:
``` markdown
packages/my-package/
  src/
    index.ts
    services/
      myService.ts
  tests/
    services/
      myService.test.ts
    integration/
      serverLifecycle.test.ts
  package.json
  tsconfig.json
```

*Note: Ensure `tsconfig.json` includes `tests/` for type checking but excludes it from build output.*

##### Test File Naming
- Unit tests: `{module}.test.ts` — mirrors the source file name
- Integration tests: `{feature}.integration.test.ts` or grouped in `tests/integration/`
- Test fixtures: `tests/fixtures/` directory

##### What to Test
- **Critical paths**: User workflows, data transformations, business logic
- **Edge cases**: Null/undefined values, empty arrays, boundary conditions
- **Error states**: How code handles failures, invalid input, network errors
- **Not trivial**: Don't test framework code, getters/setters, or obvious pass-throughs

##### Test Coverage
- Aim for meaningful coverage, not 100% coverage
- Critical business logic: high coverage
- UI components: test interactions and state changes
- Utilities and helpers: comprehensive edge case coverage

#### Python Testing

##### Test Framework
- Use `pytest` (industry standard)
- Place tests in `tests/` directory or `test_*.py` files
- Use fixtures for test data and setup

##### Test Organization
```
project/
├── src/
│   └── module.py
└── tests/
    └── test_module.py
```

##### Assertions
- Use pytest assertions: `assert result == expected`
- Use pytest-parametrize for multiple test cases
- Mock external dependencies at boundaries

#### Database Safety in Tests

Distilled from a real production incident: a test fixture handed production
credentials truncated six prod tables while its suite reported green. The full
rule set lives in `sql.md` ("Production Database Protection"); these are the
test-facing rules:

- **Tests never read the production DB URL variable.** Test code uses a
  dedicated test variable (admin URL for creating throwaway databases) and
  fixtures that create their own database. A fixture that issues
  TRUNCATE/DROP/ALTER/DELETE may only target a database it created itself.
- **"Unit" is a directory name, not a property.** Nothing stops a file under
  `test/unit/` from opening a database connection — DB-safety rules apply to
  every tier, and a scoped `DELETE` in a "unit" fixture can empty a production
  table while the suite passes.
- **Every tier gets a mechanical prod-URL guard test** that scans the tier's
  files for reads of the production variable and fails on offenders (shrink-only
  allowlist if legacy readers exist). The scan must be multiline-aware —
  `os.environ.get(\n "VAR")` defeats a per-line grep. The absence of a guard in
  a tier is not evidence of safety.
- **Never inject a whole `.env` into a test process.** Pass an explicit list of
  named variables; a runner that injects everything hands destructive fixtures
  credentials they were never meant to have.
- **Before running an unfamiliar test tier, read its conftest** for which URL
  its fixtures connect to and what they mutate.

#### Best Practices

##### When to Write Tests
- ✅ **During implementation** - Write tests as you build features
- ✅ **After bug fixes** - Add tests to prevent regression
- ✅ **Before refactoring** - Tests verify behavior stays consistent
- ❌ **Not at the very end** - Waiting until feature is "done" leads to skipped tests

##### Test Quality
- **Arrange-Act-Assert** pattern: Set up → Execute → Verify
- **One concept per test**: Each test should verify one thing
- **Readable test names**: Test name should describe what's being tested
- **Avoid test interdependence**: Tests should run independently in any order

##### Mocking and Stubbing
- Mock external services (APIs, databases, file system)
- Don't mock internal business logic - test it directly
- Use dependency injection to make mocking easier

#### Running Tests

##### Commands
```bash
# JavaScript/TypeScript
pnpm test              # Run all tests
pnpm test:watch        # Watch mode
pnpm test:coverage     # Coverage report

# Python
pytest                 # Run all tests
pytest -v              # Verbose output
pytest --cov           # Coverage report
```

##### CI/CD Integration
- Tests should run automatically on commit/PR
- Build should fail if tests fail
- Don't skip failing tests - fix them or remove them

#### Storybook (Optional)

- **enabled**: false (by default)
- Use Storybook for component documentation and visual testing
- Place stories in `src/stories` with `.stories.tsx` extension
- One story file per component, showing variants and states

### Raw Response

Good, that file already existed unchanged. Now let's look at the summary_oneshot.py, review_client.py, and models.py diffs.
Good coverage. Let's check the dispatch test coverage for the ValueError/SDK guard, to see if it explicitly documents this exclusion is out-of-scope or if a test exists asserting SDK+allowed_tools still errors even after this slice.
Good, this is well-tested. Let's check `_log_action_result` type-safety around `given` cast comment and confirm `made` type usage doesn't break pyright given `result.metadata.get(...)` returns `object`.
Reasonable. This looks fine. Now let's check the summary.py action's `_execute_summary` more closely, and `cwd` param threading — confirm `context.cwd` exists and is passed correctly.
Good, `cwd` exists on `ActionContext`. Now let's check the `dispatch.py` full remainder and `review.py` action full file for anything else, plus check `summary.py` full diff context around emit/error paths.
Good — matches project's boundary handling rules with a comment justifying the broad except. Let's check the review action's full context around lines 300-330 for correctness of dict construction.
This all looks correct and consistent. I've gathered enough to write the review. Let me do a final check on the `_grep_candidates`/large-file gap by confirming there's truly no size guard anywhere (e.g., in `_resolve_in_jail` or a shared helper), and double check the `list_files` recursive glob has no depth/size cap either (informational, lower severity).
Now I have all the details needed. Let me compile the final review.
## Summary
**CONCERNS**

Reviewed the diff between `ab7c3616` and `265-slice.review-coverage-standalone-client-and-pipeline-actions` (34 files, dispatch/review/summary telemetry threading, new `list_files`/`grep` tools, SDK tool-name translation, and their tests). Overall the slice is well-designed and well-tested — the D1/D3/D4/D5/D8/D9 design decisions referenced in comments are consistently implemented and backed by targeted unit and load tests (`tests/load/test_grep_timeout.py` properly covers the ReDoS/event-loop-starvation failure mode). Four issues found, none blocking but worth addressing:

1. **DRY violation** — `dispatch.py`'s new `one_shot_dispatch_with_telemetry` fully duplicates `one_shot_dispatch` rather than delegating, unlike the parallel refactor in `summary_oneshot.py` which does delegate.
2. **Cross-action inconsistency** — dispatch still hard-rejects `allowed_tools` on SDK profiles via a comment claiming "Slice 265 owns the SDK mapping," even though this slice built and wired that exact mapping for review/summary, leaving dispatch behind and the comment stale.
3. **Failure-mode gap** — `grep`'s wall-clock budget doesn't bound directory traversal or the per-file `read_text()`, only the regex-matching loop; a huge file or tree isn't covered by the existing load test.
4. **Misleading comment** — the telemetry-stamp comment on the tool-less fast path in `openai/agent.py` describes a code path that can't reach that branch anymore.
