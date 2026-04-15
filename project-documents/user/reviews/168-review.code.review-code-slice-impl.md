---
docType: review
layer: project
reviewType: code
slice: review-code-slice-impl
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/168-slice.review-code-slice-impl.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260415
dateUpdated: 20260415
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Implementation adds robust diff range resolution via commit grep"
    location: src/squadron/review/git_utils.py:62-101, src/squadron/cli/commands/review.py:745-760, tests/review/test_git_utils.py:181-298
---

# Review: code — slice 168

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Implementation adds robust diff range resolution via commit grep

The new `_find_commit_range` function and its integration into `resolve_slice_diff_range` adds a valuable fallback mechanism (step 3) for resolving slice diffs when no branch or merge commit exists. The implementation is clean and well-tested:

**Code quality:**
- Uses subprocess.run with `capture_output=True` and `check=False` appropriately
- Handles `FileNotFoundError` and `OSError` explicitly (not bare `except`)
- Function stays under 50 lines and has a single clear responsibility
- Word boundary regex (`\b`) correctly prevents partial slice number matches
- Type hints use modern Python syntax (`str | None`)
- Docstring clearly documents return value formats

**Test coverage:**
- Tests cover all code paths: multiple commits, single commit, no commits, subprocess errors, non-zero return codes
- Integration tests verify the commit grep path is used correctly in the precedence chain
- Tests confirm merge commit path takes priority (commit grep is skipped when merge found)
- Fallback warning behavior verified

**CLI addition:**
- The `--fan` option is correctly reserved for future use with a clear warning message
- Proper `typer.Option` usage with helpful description

---

## Debug: Prompt & Response

### System Prompt

You are a code reviewer. Review code against language-specific rules, testing
standards, and project conventions loaded from CLAUDE.md.

Focus areas:
- Project conventions (from CLAUDE.md)
- Language-appropriate style and correctness
- Test coverage patterns (test-with, not test-after)
- Error handling patterns
- Security concerns
- Naming, structure, and documentation quality

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

---
description: Design principles for code reviews. Injected when running sq review code.
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

Run `git diff dcb7dc8^..bf49fd8 -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/src/squadron/cli/commands/review.py b/src/squadron/cli/commands/review.py
index 729bf97..1b5a6fe 100644
--- a/src/squadron/cli/commands/review.py
+++ b/src/squadron/cli/commands/review.py
@@ -742,8 +742,19 @@ def review_code(
         False, "--json", help="Output and save as JSON instead of markdown"
     ),
     no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
+    fan: int | None = typer.Option(
+        None,
+        "--fan",
+        help="Fan-out width (reserved for slice 182; not yet functional)",
+    ),
 ) -> None:
     """Run a code review."""
+    if fan is not None:
+        rprint(
+            "[yellow]--fan is reserved for future fan-out support "
+            "(slice 182); ignored.[/yellow]"
+        )
+
     # Load template early to access diff_exclude_patterns
     load_all_templates()
     code_template = get_template("code")
diff --git a/src/squadron/review/git_utils.py b/src/squadron/review/git_utils.py
index e562dcc..9f96ef6 100644
--- a/src/squadron/review/git_utils.py
+++ b/src/squadron/review/git_utils.py
@@ -59,6 +59,46 @@ def _find_merge_commit(slice_number: int, cwd: str) -> str | None:
         return None
 
 
+def _find_commit_range(slice_number: int, cwd: str) -> str | None:
+    """Find a diff range by grepping commit messages for the slice number.
+
+    Runs ``git log --oneline --all --grep=r"\\b{N}\\b"`` and collects all
+    matching commit hashes.  Returns:
+
+    - ``"{oldest}^!"``: if exactly one commit matched (single-commit diff)
+    - ``"{oldest}^..{newest}"``: if two or more commits matched
+    - ``None``: if no commits matched or git failed
+    """
+    try:
+        result = subprocess.run(
+            [
+                "git",
+                "log",
+                "--oneline",
+                "--all",
+                f"--grep=\\b{slice_number}\\b",
+            ],
+            capture_output=True,
+            text=True,
+            cwd=cwd,
+            check=False,
+        )
+        if result.returncode != 0 or not result.stdout.strip():
+            return None
+        hashes = [
+            line.split()[0] for line in result.stdout.splitlines() if line.strip()
+        ]
+        if not hashes:
+            return None
+        if len(hashes) == 1:
+            return f"{hashes[0]}^!"
+        # git log outputs newest-first; oldest is last
+        newest, oldest = hashes[0], hashes[-1]
+        return f"{oldest}^..{newest}"
+    except (FileNotFoundError, OSError):
+        return None
+
+
 def _resolve_rev(ref: str, cwd: str) -> str | None:
     """Resolve a git ref to its full SHA. Returns None on failure."""
     try:
@@ -82,7 +122,8 @@ def resolve_slice_diff_range(slice_number: int, cwd: str) -> str:
     Precedence:
     1. Local branch exists → merge-base three-dot diff
     2. Merge commit found on main → parent diff of merge
-    3. Fallback → 'main' with warning
+    3. Commit-message grep → oldest-to-newest range across matched commits
+    4. Fallback → 'main' with warning
 
     Returns a diff range string suitable for ``git diff <range>``.
     """
@@ -113,6 +154,10 @@ def resolve_slice_diff_range(slice_number: int, cwd: str) -> str:
     if merge_commit is not None:
         return f"{merge_commit}^1..{merge_commit}^2"
 
+    commit_range = _find_commit_range(slice_number, cwd)
+    if commit_range is not None:
+        return commit_range
+
     print(
         f"[WARNING] Could not resolve diff range for slice {slice_number}. "
         "Falling back to --diff main.",
diff --git a/tests/review/test_git_utils.py b/tests/review/test_git_utils.py
index a008b4b..ab07cdf 100644
--- a/tests/review/test_git_utils.py
+++ b/tests/review/test_git_utils.py
@@ -6,6 +6,7 @@ from io import StringIO
 from unittest.mock import MagicMock, patch
 
 from squadron.review.git_utils import (
+    _find_commit_range,
     _find_merge_commit,
     _find_slice_branch,
     resolve_slice_diff_range,
@@ -177,3 +178,121 @@ class TestResolveSliceDiffRange:
         ):
             result = resolve_slice_diff_range(122, ".")
         assert result == "def5678^1..def5678^2"
+
+
+class TestFindCommitRange:
+    """Tests for _find_commit_range()."""
+
+    def test_multiple_commits(self) -> None:
+        """Multiple commits matched — return oldest^..newest."""
+        mock_result = MagicMock()
+        mock_result.returncode = 0
+        # git log outputs newest-first
+        mock_result.stdout = (
+            "aaa1111 feat: slice 181 thing\n"
+            "bbb2222 fix: resolve slice 181 edge case\n"
+            "ccc3333 docs: add slice 181 task file\n"
+        )
+        with patch(
+            "squadron.review.git_utils.subprocess.run", return_value=mock_result
+        ):
+            result = _find_commit_range(181, ".")
+        assert result == "ccc3333^..aaa1111"
+
+    def test_single_commit(self) -> None:
+        """Exactly one commit matched — return {sha}^! syntax."""
+        mock_result = MagicMock()
+        mock_result.returncode = 0
+        mock_result.stdout = "abc1234 feat: implement slice 181\n"
+        with patch(
+            "squadron.review.git_utils.subprocess.run", return_value=mock_result
+        ):
+            result = _find_commit_range(181, ".")
+        assert result == "abc1234^!"
+
+    def test_no_commits(self) -> None:
+        """No commits matched — return None."""
+        mock_result = MagicMock()
+        mock_result.returncode = 0
+        mock_result.stdout = ""
+        with patch(
+            "squadron.review.git_utils.subprocess.run", return_value=mock_result
+        ):
+            result = _find_commit_range(999, ".")
+        assert result is None
+
+    def test_subprocess_error(self) -> None:
+        """Git failure — return None."""
+        with patch(
+            "squadron.review.git_utils.subprocess.run",
+            side_effect=FileNotFoundError("git not found"),
+        ):
+            result = _find_commit_range(181, ".")
+        assert result is None
+
+    def test_nonzero_returncode(self) -> None:
+        """Non-zero exit — return None."""
+        mock_result = MagicMock()
+        mock_result.returncode = 128
+        mock_result.stdout = ""
+        with patch(
+            "squadron.review.git_utils.subprocess.run", return_value=mock_result
+        ):
+            result = _find_commit_range(181, ".")
+        assert result is None
+
+
+class TestResolveSliceDiffRangeWithCommitGrep:
+    """Tests for resolve_slice_diff_range() step-3 commit-grep path."""
+
+    def test_commit_grep_used_when_branch_and_merge_missing(self) -> None:
+        """No branch, no merge commit → commit grep resolves range."""
+        with (
+            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
+            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
+            patch(
+                "squadron.review.git_utils._find_commit_range",
+                return_value="ccc3333^..aaa1111",
+            ),
+        ):
+            result = resolve_slice_diff_range(181, ".")
+        assert result == "ccc3333^..aaa1111"
+
+    def test_commit_grep_single_commit(self) -> None:
+        """Single matched commit → {sha}^! range returned."""
+        with (
+            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
+            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
+            patch(
+                "squadron.review.git_utils._find_commit_range",
+                return_value="abc1234^!",
+            ),
+        ):
+            result = resolve_slice_diff_range(181, ".")
+        assert result == "abc1234^!"
+
+    def test_commit_grep_not_tried_when_merge_commit_found(self) -> None:
+        """Merge commit found → commit grep is never called."""
+        with (
+            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
+            patch(
+                "squadron.review.git_utils._find_merge_commit",
+                return_value="merge999",
+            ),
+            patch("squadron.review.git_utils._find_commit_range") as mock_grep,
+        ):
+            result = resolve_slice_diff_range(181, ".")
+        assert result == "merge999^1..merge999^2"
+        mock_grep.assert_not_called()
+
+    def test_fallback_fires_when_all_three_fail(self) -> None:
+        """All three resolution paths fail → warning + 'main'."""
+        with (
+            patch("squadron.review.git_utils._find_slice_branch", return_value=None),
+            patch("squadron.review.git_utils._find_merge_commit", return_value=None),
+            patch("squadron.review.git_utils._find_commit_range", return_value=None),
+            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
+        ):
+            result = resolve_slice_diff_range(999, ".")
+        assert result == "main"
+        assert "WARNING" in mock_stderr.getvalue()

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

---
description: Design principles for code reviews. Injected when running sq review code.
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

## Summary
**PASS**

## Findings

### [PASS] Implementation adds robust diff range resolution via commit grep
location: src/squadron/review/git_utils.py:62-101, src/squadron/cli/commands/review.py:745-760, tests/review/test_git_utils.py:181-298

The new `_find_commit_range` function and its integration into `resolve_slice_diff_range` adds a valuable fallback mechanism (step 3) for resolving slice diffs when no branch or merge commit exists. The implementation is clean and well-tested:

**Code quality:**
- Uses subprocess.run with `capture_output=True` and `check=False` appropriately
- Handles `FileNotFoundError` and `OSError` explicitly (not bare `except`)
- Function stays under 50 lines and has a single clear responsibility
- Word boundary regex (`\b`) correctly prevents partial slice number matches
- Type hints use modern Python syntax (`str | None`)
- Docstring clearly documents return value formats

**Test coverage:**
- Tests cover all code paths: multiple commits, single commit, no commits, subprocess errors, non-zero return codes
- Integration tests verify the commit grep path is used correctly in the precedence chain
- Tests confirm merge commit path takes priority (commit grep is skipped when merge found)
- Fallback warning behavior verified

**CLI addition:**
- The `--fan` option is correctly reserved for future use with a clear warning message
- Proper `typer.Option` usage with helpful description
