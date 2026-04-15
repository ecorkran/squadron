---
docType: review
layer: project
reviewType: code
slice: profile-aware-summary-model-routing
project: squadron
verdict: PASS
sourceDocument: project-documents/user/slices/164-slice.profile-aware-summary-model-routing.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260415
dateUpdated: 20260415
findings:
  - id: F001
    severity: pass
    category: typing
    summary: "Type safety and forward reference handling"
    location: src/squadron/cli/commands/summary_run.py:1
  - id: F002
    severity: pass
    category: security
    summary: "Shell parameter escaping"
    location: src/squadron/pipeline/prompt_renderer.py:280
  - id: F003
    severity: pass
    category: error-handling
    summary: "Specific exception handling"
    location: src/squadron/cli/commands/summary_run.py:38-43
  - id: F004
    severity: pass
    category: error-handling
    summary: "Fail-fast validation for incompatible features"
    location: src/squadron/pipeline/actions/summary.py:140-153
  - id: F005
    severity: pass
    category: design
    summary: "Open/Closed via profile branching"
    location: src/squadron/pipeline/summary_oneshot.py:45-86
  - id: F006
    severity: pass
    category: testing
    summary: "Comprehensive test coverage"
  - id: F007
    severity: pass
    category: testing
    summary: "Test isolation improvement"
    location: tests/review/test_rules.py:54-58
  - id: F008
    severity: pass
    category: error-handling
    summary: "Async cleanup via try/finally"
    location: src/squadron/pipeline/summary_oneshot.py:82-86
  - id: F009
    severity: pass
    category: documentation
    summary: "Docstring completeness"
    location: src/squadron/pipeline/summary_oneshot.py:1-12, src/squadron/cli/commands/summary_run.py:1-7
---

# Review: code — slice 164

**Verdict:** PASS
**Model:** minimax/minimax-m2.7

## Findings

### [PASS] Type safety and forward reference handling

The file correctly uses `from __future__ import annotations` for Python 3.12+ compatibility, ensuring clean forward reference resolution. Union types use the modern `str | None` syntax.

### [PASS] Shell parameter escaping

The code correctly uses `shlex.quote(str(value))` when constructing the `_summary-run` command with user-provided pipeline parameters. This prevents shell injection vulnerabilities when values contain spaces or special characters. The corresponding test `test_non_sdk_profile_quotes_params` in `tests/pipeline/test_prompt_renderer.py` validates this behavior correctly.

### [PASS] Specific exception handling

The error handling in `summary_run` is well-structured:
- `FileNotFoundError` is caught explicitly when loading templates
- Parameter parsing validates format before use with a clear error message
- Generic exception handling wraps provider failures with informative output

### [PASS] Fail-fast validation for incompatible features

The validation for ROTATE emit with non-SDK profiles follows the "fail fast" principle. Invalid state combinations are caught early at the boundary before any provider call, returning explicit `ActionResult` with descriptive errors rather than proceeding to a likely failure deeper in the call stack.

### [PASS] Open/Closed via profile branching

The `capture_summary_via_profile()` function follows the existing pattern from `run_review_with_profile()` and provides a clean extension point for adding new provider profiles without modifying existing code. The `is_sdk_profile()` predicate acts as a proper abstraction boundary.

### [PASS] Comprehensive test coverage

The test additions provide good coverage for the new functionality:
- `tests/cli/commands/test_summary_run.py` covers CLI invocation, parameter parsing, error cases
- `tests/pipeline/test_summary_oneshot.py` tests the core profile routing logic with parametrized tests
- `tests/pipeline/actions/test_summary.py` validates the SDK vs non-SDK branching in the summary action

### [PASS] Test isolation improvement

The change to isolate the filesystem-dependent test by patching `resolve_rules_dir` demonstrates good testing discipline—tests should not depend on external state unless that's specifically what they're testing.

### [PASS] Async cleanup via try/finally

The `capture_summary_via_profile` function uses `try/finally` to ensure `agent.shutdown()` is called even when the provider raises an exception, preventing resource leaks. The corresponding test `test_capture_summary_shutdown_called_on_exception` validates this behavior.

### [PASS] Docstring completeness

Both new modules include module-level docstrings explaining their purpose and the architectural pattern they implement. The hidden command docstring correctly notes its use case for the prompt-only pipeline rendering scenario.

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

Run `git diff d3588d3^..5bb4803 -- . ':!*.md' ':!*.yaml' ':!*.yml' ':!*.toml' ':!*.json' ':!*.txt' ':!*.lock' ':!*.csv' ':!*.svg' ':!*.png' ':!*.jpg' ':!*.gif' ':!*.ico'` to identify changed source files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/src/squadron/cli/app.py b/src/squadron/cli/app.py
index f65c5f9..4ae823e 100644
--- a/src/squadron/cli/app.py
+++ b/src/squadron/cli/app.py
@@ -21,6 +21,7 @@ from squadron.cli.commands.serve import serve
 from squadron.cli.commands.shutdown import shutdown
 from squadron.cli.commands.spawn import spawn
 from squadron.cli.commands.summary_instructions import summary_instructions
+from squadron.cli.commands.summary_run import summary_run
 from squadron.cli.commands.task import task
 
 load_dotenv(dotenv_path=Path.cwd() / ".env")
@@ -46,6 +47,7 @@ app.command("run")(run_command)
 app.command("install-commands")(install_commands)
 app.command("uninstall-commands")(uninstall_commands)
 app.command("_summary-instructions", hidden=True)(summary_instructions)
+app.command("_summary-run", hidden=True)(summary_run)
 
 
 def version_callback(value: bool) -> None:
diff --git a/src/squadron/cli/commands/summary_run.py b/src/squadron/cli/commands/summary_run.py
new file mode 100644
index 0000000..f67608a
--- /dev/null
+++ b/src/squadron/cli/commands/summary_run.py
@@ -0,0 +1,71 @@
+"""[hidden] Execute a one-shot summary via a non-SDK provider profile.
+
+Used by prompt-only pipeline rendering when a summary step is configured
+with a non-SDK model alias.  The harness invokes this command to perform
+the actual summary call and print the result to stdout.
+"""
+
+from __future__ import annotations
+
+import asyncio
+import sys
+
+import typer
+
+from squadron.pipeline.actions.compact import (
+    load_compaction_template,
+    render_instructions,
+)
+from squadron.pipeline.summary_oneshot import capture_summary_via_profile
+
+
+def summary_run(
+    template: str = typer.Option(..., "--template", help="Compaction template name."),
+    profile: str = typer.Option(..., "--profile", help="Provider profile name."),
+    model: str = typer.Option(..., "--model", help="Resolved model ID."),
+    param: list[str] = typer.Option(
+        [],
+        "--param",
+        "-p",
+        help="key=value pipeline parameters (repeatable).",
+    ),
+) -> None:
+    """[hidden] Run a one-shot summary via a non-SDK provider profile."""
+    # Parse --param flags into a dict.
+    params: dict[str, object] = {}
+    for entry in param:
+        if "=" not in entry:
+            print(
+                f"Error: --param value {entry!r} is missing '=' (expected key=value).",
+                file=sys.stderr,
+            )
+            raise typer.Exit(code=1)
+        key, _, value = entry.partition("=")
+        params[key] = value
+
+    # Load and render the compaction template.
+    try:
+        tmpl = load_compaction_template(template)
+    except FileNotFoundError:
+        print(f"Error: template {template!r} not found.", file=sys.stderr)
+        raise typer.Exit(code=1)
+
+    instructions = render_instructions(tmpl, pipeline_params=params)
+
+    # Execute the one-shot summary.
+    try:
+        result = asyncio.run(
+            capture_summary_via_profile(
+                instructions=instructions,
+                model_id=model,
+                profile=profile,
+            )
+        )
+    except KeyError as exc:
+        print(f"Error: unknown profile — {exc}", file=sys.stderr)
+        raise typer.Exit(code=1)
+    except Exception as exc:
+        print(f"Error: provider failure — {exc}", file=sys.stderr)
+        raise typer.Exit(code=1)
+
+    print(result)
diff --git a/src/squadron/pipeline/actions/summary.py b/src/squadron/pipeline/actions/summary.py
index dc6d4cf..08a4080 100644
--- a/src/squadron/pipeline/actions/summary.py
+++ b/src/squadron/pipeline/actions/summary.py
@@ -7,6 +7,10 @@ import logging
 from squadron.pipeline.actions import ActionType, register_action
 from squadron.pipeline.emit import EmitDestination, EmitKind, get_emit, parse_emit_list
 from squadron.pipeline.models import ActionContext, ActionResult, ValidationError
+from squadron.pipeline.summary_oneshot import (
+    capture_summary_via_profile,
+    is_sdk_profile,
+)
 
 _logger = logging.getLogger(__name__)
 
@@ -117,30 +121,66 @@ async def _execute_summary(
 
     Non-rotate emit failures log a warning but do not fail the action.
     A rotate emit failure halts the action with success=False.
+
+    Branches on profile:
+    - SDK profile (or None): uses sdk_session.capture_summary()
+    - Non-SDK profile: uses capture_summary_via_profile() via the provider registry
     """
-    if context.sdk_session is None:
+    # Resolve model alias and profile.
+    model_id: str | None = None
+    profile: str | None = None
+    if summary_model_alias:
+        model_id, profile = context.resolver.resolve(
+            action_model=summary_model_alias, step_model=None
+        )
+
+    # Validate: rotate emit is incompatible with non-SDK profiles.
+    has_rotate = any(d.kind is EmitKind.ROTATE for d in emit_destinations)
+    if has_rotate and not is_sdk_profile(profile):
         return ActionResult(
             success=False,
             action_type=action_type,
             outputs={},
-            error="summary action requires SDK execution mode",
+            error=(
+                f"rotate emit is incompatible with non-SDK summary profile {profile!r}"
+            ),
         )
 
-    # Resolve model alias if provided.
-    model_id: str | None = None
-    if summary_model_alias:
-        model_id, _ = context.resolver.resolve(
-            action_model=summary_model_alias, step_model=None
+    # Guard: SDK profile requires an active SDK session.
+    if is_sdk_profile(profile) and context.sdk_session is None:
+        return ActionResult(
+            success=False,
+            action_type=action_type,
+            outputs={},
+            error="summary action requires SDK execution mode for SDK-profile models",
         )
 
-    restore_model = context.sdk_session.current_model
+    # Guard: rotate emit also requires an SDK session (belt-and-suspenders —
+    # already blocked above for non-SDK, but also catches SDK + missing session).
+    if has_rotate and context.sdk_session is None:
+        return ActionResult(
+            success=False,
+            action_type=action_type,
+            outputs={},
+            error="rotate emit requires an SDK session",
+        )
 
     try:
-        summary = await context.sdk_session.capture_summary(
-            instructions=instructions,
-            summary_model=model_id,
-            restore_model=restore_model,
-        )
+        if is_sdk_profile(profile):
+            assert context.sdk_session is not None  # narrowed above
+            restore_model = context.sdk_session.current_model
+            summary = await context.sdk_session.capture_summary(
+                instructions=instructions,
+                summary_model=model_id,
+                restore_model=restore_model,
+            )
+        else:
+            assert profile is not None  # narrowed by is_sdk_profile False
+            summary = await capture_summary_via_profile(
+                instructions=instructions,
+                model_id=model_id,
+                profile=profile,
+            )
     except Exception as exc:
         return ActionResult(
             success=False,
diff --git a/src/squadron/pipeline/prompt_renderer.py b/src/squadron/pipeline/prompt_renderer.py
index 133caa0..ed7e71e 100644
--- a/src/squadron/pipeline/prompt_renderer.py
+++ b/src/squadron/pipeline/prompt_renderer.py
@@ -9,8 +9,9 @@ from __future__ import annotations
 
 import json
 import logging
+import shlex
 from dataclasses import asdict, dataclass
-from typing import TYPE_CHECKING
+from typing import TYPE_CHECKING, cast
 
 from squadron.pipeline.actions import ActionType
 from squadron.pipeline.actions.compact import (
@@ -19,6 +20,7 @@ from squadron.pipeline.actions.compact import (
 )
 from squadron.pipeline.executor import resolve_placeholders
 from squadron.pipeline.steps import get_step_type
+from squadron.pipeline.summary_oneshot import is_sdk_profile
 
 if TYPE_CHECKING:
     from squadron.pipeline.models import StepConfig
@@ -244,20 +246,46 @@ def _render_summary(
     params: dict[str, object],
     resolver: ModelResolver,
 ) -> ActionInstruction:
-    """Build instruction for a summary action."""
+    """Build instruction for a summary action.
+
+    SDK profiles (or no model alias) emit a ``model_switch`` directive.
+    Non-SDK profiles emit a ``command`` with a runnable ``sq _summary-run …``
+    invocation.  No path emits both.
+    """
     template_name = str(config.get("template", "default"))
     model_raw = config.get("model")
     emit_raw = config.get("emit")
 
     model_id: str | None = None
+    profile: str | None = None
     model_switch: str | None = None
+    command: str | None = None
+
     if model_raw is not None:
         alias = str(model_raw)
         try:
-            model_id, _ = resolver.resolve(alias)
+            model_id, profile = resolver.resolve(alias)
         except Exception:
             model_id = alias
-        model_switch = f"/model {alias}"
+            profile = None
+
+        if is_sdk_profile(profile):
+            model_switch = f"/model {alias}"
+        else:
+            # Non-SDK: build a runnable sq _summary-run command.
+            cmd_parts = [
+                "sq",
+                "_summary-run",
+                "--template",
+                template_name,
+                "--profile",
+                profile or "",
+                "--model",
+                model_id or alias,
+            ]
+            for key, value in params.items():
+                cmd_parts.extend(["--param", f"{key}={shlex.quote(str(value))}"])
+            command = " ".join(cmd_parts)
 
     try:
         template = load_compaction_template(template_name)
@@ -267,11 +295,13 @@ def _render_summary(
 
     emit_destinations: list[str] | None = None
     if isinstance(emit_raw, list):
-        emit_destinations = [str(e) for e in emit_raw] or None
+        emit_list = cast(list[object], emit_raw)
+        emit_destinations = [str(e) for e in emit_list] or None
 
     return ActionInstruction(
         action_type=ActionType.SUMMARY,
         instruction="Generate a session summary following the resolved instructions",
+        command=command,
         model=model_id,
         model_switch=model_switch,
         template=template_name,
diff --git a/src/squadron/pipeline/summary_oneshot.py b/src/squadron/pipeline/summary_oneshot.py
new file mode 100644
index 0000000..772942d
--- /dev/null
+++ b/src/squadron/pipeline/summary_oneshot.py
@@ -0,0 +1,91 @@
+"""One-shot summary execution for non-SDK provider profiles.
+
+Provides `capture_summary_via_profile()` (mirrors the pattern from
+`run_review_with_profile()`) and the `is_sdk_profile()` predicate used
+to route summary actions at execution time.
+"""
+
+from __future__ import annotations
+
+import logging
+
+from squadron.providers.base import ProfileName
+
+_logger = logging.getLogger(__name__)
+
+__all__ = ["is_sdk_profile", "capture_summary_via_profile"]
+
+
+def is_sdk_profile(profile: str | None) -> bool:
+    """Return True when the profile routes through the Claude Code SDK session.
+
+    None and 'sdk' both route through the SDK session.
+    """
+    return profile is None or profile == ProfileName.SDK
+
+
+async def capture_summary_via_profile(
+    *,
+    instructions: str,
+    model_id: str | None,
+    profile: str,
+) -> str:
+    """Execute a one-shot summary call through the specified provider profile.
+
+    Mirrors the shape of `run_review_with_profile()` with review-specific
+    branches removed: no structured-output injection, no rules, no file
+    injection, no parsing — returns the raw concatenated response string.
+    """
+    from squadron.core.models import SDK_RESULT_TYPE, AgentConfig, Message, MessageType
+    from squadron.providers.loader import ensure_provider_loaded
+    from squadron.providers.profiles import get_profile
+    from squadron.providers.registry import get_provider
+
+    provider_profile = get_profile(profile)
+    ensure_provider_loaded(provider_profile.provider)
+    provider = get_provider(provider_profile.provider)
+
+    config = AgentConfig(
+        name="summary-oneshot",
+        agent_type=provider_profile.provider,
+        provider=provider_profile.provider,
+        model=model_id,
+        instructions="",
+        api_key=None,
+        base_url=provider_profile.base_url,
+        cwd=None,
+        allowed_tools=[],
+        permission_mode="default",
+        setting_sources=[],
+        credentials={
+            "api_key_env": provider_profile.api_key_env,
+            "default_headers": provider_profile.default_headers,
+            "hooks": [],
+            "mode": "client",
+        },
+    )
+
+    _logger.info(
+        "Summary via %s (provider=%s, model=%s)",
+        profile,
+        provider_profile.provider,
+        model_id or "(default)",
+    )
+
+    agent = await provider.create_agent(config)
+    raw_output = ""
+    try:
+        message = Message(
+            sender="summary-system",
+            recipients=[config.name],
+            content=instructions,
+            message_type=MessageType.chat,
+        )
+        async for response in agent.handle_message(message):
+            if response.metadata.get("sdk_type") == SDK_RESULT_TYPE:
+                continue
+            raw_output += response.content
+    finally:
+        await agent.shutdown()
+
+    return raw_output
diff --git a/tests/cli/commands/test_run.py b/tests/cli/commands/test_run.py
index 1fd4f77..c0774c6 100644
--- a/tests/cli/commands/test_run.py
+++ b/tests/cli/commands/test_run.py
@@ -139,7 +139,8 @@ class TestAssembleParams:
     def test_no_target_no_model(self) -> None:
         defn = _make_definition(params={"model": "opus"})
         result = _assemble_params(defn, None, None, None)
-        assert result == {}
+        # Pipeline defaults (non-"required" values) are seeded into params
+        assert result == {"model": "opus"}
 
     def test_multiple_extra_params(self) -> None:
         defn = _make_definition(params={"slice": "required"})
diff --git a/tests/cli/commands/test_summary_run.py b/tests/cli/commands/test_summary_run.py
new file mode 100644
index 0000000..2618d0d
--- /dev/null
+++ b/tests/cli/commands/test_summary_run.py
@@ -0,0 +1,163 @@
+"""Tests for the sq _summary-run hidden subcommand (T10)."""
+
+from __future__ import annotations
+
+from unittest.mock import AsyncMock, patch
+
+from typer.testing import CliRunner
+
+from squadron.cli.app import app
+
+_runner = CliRunner()
+
+
+def _invoke(*args: str) -> object:
+    return _runner.invoke(app, ["_summary-run", *args])
+
+
+class TestSummaryRunHappyPath:
+    def test_happy_path_prints_summary_and_exits_0(self) -> None:
+        """Mocked provider returns text; command prints it to stdout."""
+        with (
+            patch(
+                "squadron.cli.commands.summary_run.capture_summary_via_profile",
+                new=AsyncMock(return_value="SUMMARY OUTPUT"),
+            ),
+            patch(
+                "squadron.cli.commands.summary_run.load_compaction_template"
+            ) as mock_load,
+            patch(
+                "squadron.cli.commands.summary_run.render_instructions",
+                return_value="rendered instructions",
+            ),
+        ):
+            from squadron.pipeline.actions.compact import CompactionTemplate
+
+            mock_load.return_value = CompactionTemplate(
+                name="minimal",
+                description="d",
+                instructions="summarize",
+            )
+            result = _invoke(
+                "--template",
+                "minimal",
+                "--profile",
+                "openrouter",
+                "--model",
+                "minimax-01",
+            )
+
+        assert result.exit_code == 0
+        assert "SUMMARY OUTPUT" in (result.output or "")
+
+    def test_params_passed_to_render(self) -> None:
+        """--param flags are parsed and forwarded to render_instructions."""
+        render_calls: list[dict[str, object]] = []
+
+        def _fake_render(template: object, **kwargs: object) -> str:
+            render_calls.append(dict(kwargs))
+            return "rendered"
+
+        with (
+            patch(
+                "squadron.cli.commands.summary_run.capture_summary_via_profile",
+                new=AsyncMock(return_value="OK"),
+            ),
+            patch(
+                "squadron.cli.commands.summary_run.load_compaction_template"
+            ) as mock_load,
+            patch(
+                "squadron.cli.commands.summary_run.render_instructions",
+                side_effect=_fake_render,
+            ),
+        ):
+            from squadron.pipeline.actions.compact import CompactionTemplate
+
+            mock_load.return_value = CompactionTemplate(
+                name="minimal",
+                description="d",
+                instructions="summarize",
+            )
+            result = _invoke(
+                "--template",
+                "minimal",
+                "--profile",
+                "openrouter",
+                "--model",
+                "minimax-01",
+                "--param",
+                "slice=164",
+                "--param",
+                "phase=6",
+            )
+
+        assert result.exit_code == 0
+        assert render_calls
+        params = render_calls[0].get("pipeline_params", {})
+        assert params == {"slice": "164", "phase": "6"}  # type: ignore[comparison-overlap]
+
+
+class TestSummaryRunErrorCases:
+    def test_bad_param_format_exits_1(self) -> None:
+        """--param value without '=' produces exit code 1 with stderr message."""
+        result = _invoke(
+            "--template",
+            "minimal",
+            "--profile",
+            "openrouter",
+            "--model",
+            "minimax-01",
+            "--param",
+            "badvalue",
+        )
+
+        assert result.exit_code == 1
+        assert "badvalue" in (result.output or "")
+
+    def test_missing_template_exits_1(self) -> None:
+        """Non-existent template produces exit code 1."""
+        result = _invoke(
+            "--template",
+            "does-not-exist",
+            "--profile",
+            "openrouter",
+            "--model",
+            "minimax-01",
+        )
+
+        assert result.exit_code == 1
+        assert "does-not-exist" in (result.output or "")
+
+    def test_provider_raises_exits_1(self) -> None:
+        """Provider exception is caught and reported as exit 1."""
+        with (
+            patch(
+                "squadron.cli.commands.summary_run.capture_summary_via_profile",
+                new=AsyncMock(side_effect=RuntimeError("network failed")),
+            ),
+            patch(
+                "squadron.cli.commands.summary_run.load_compaction_template"
+            ) as mock_load,
+            patch(
+                "squadron.cli.commands.summary_run.render_instructions",
+                return_value="rendered",
+            ),
+        ):
+            from squadron.pipeline.actions.compact import CompactionTemplate
+
+            mock_load.return_value = CompactionTemplate(
+                name="minimal",
+                description="d",
+                instructions="summarize",
+            )
+            result = _invoke(
+                "--template",
+                "minimal",
+                "--profile",
+                "openrouter",
+                "--model",
+                "minimax-01",
+            )
+
+        assert result.exit_code == 1
+        assert "network failed" in (result.output or "")
diff --git a/tests/pipeline/actions/test_compact.py b/tests/pipeline/actions/test_compact.py
index b41163d..5eb5b17 100644
--- a/tests/pipeline/actions/test_compact.py
+++ b/tests/pipeline/actions/test_compact.py
@@ -222,3 +222,84 @@ async def test_execute_missing_template(
 
     assert result.success is False
     assert "not found" in str(result.error)
+
+
+# ---------------------------------------------------------------------------
+# T13 (slice 164) — compact-via-summary inheritance
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_compact_non_sdk_profile_non_rotate_emit_succeeds(
+    action: CompactAction,
+    mock_context: ActionContext,
+) -> None:
+    """Compact with SDK session + non-SDK model + non-rotate emit delegates to
+    _execute_summary which uses the non-SDK provider path — no compact-specific
+    code is needed."""
+    from unittest.mock import AsyncMock, patch
+
+    from squadron.pipeline.models import ActionResult
+
+    mock_context.sdk_session = MagicMock()  # type: ignore[attr-defined]
+    mock_context.params = {"model": "minimax"}
+
+    fake_result = ActionResult(
+        success=True,
+        action_type="compact",
+        outputs={"summary": "COMPACT SUMMARY"},
+    )
+
+    # compact imports _execute_summary from summary at call time — patch there
+    with patch(
+        "squadron.pipeline.actions.summary._execute_summary",
+        new=AsyncMock(return_value=fake_result),
+    ) as mock_execute:
+        result = await action.execute(mock_context)
+
+    assert result.success is True
+    mock_execute.assert_called_once()
+    # Confirm compact passes action_type="compact" (not "summary")
+    call_kwargs = mock_execute.call_args.kwargs
+    assert call_kwargs["action_type"] == "compact"
+
+
+@pytest.mark.asyncio
+async def test_compact_non_sdk_profile_with_rotate_fails(
+    action: CompactAction,
+    mock_context: ActionContext,
+) -> None:
+    """_execute_summary validation: non-SDK profile + ROTATE fails with 'rotate' error.
+
+    Compact always passes EmitKind.ROTATE to _execute_summary.  This test
+    calls _execute_summary directly (the shared helper) to verify the error
+    message shape when a non-SDK profile is paired with ROTATE.
+    """
+    from unittest.mock import AsyncMock, patch
+
+    from squadron.pipeline.actions.summary import _execute_summary
+    from squadron.pipeline.emit import EmitDestination, EmitKind
+
+    ctx = MagicMock()
+    ctx.sdk_session = MagicMock()
+    ctx.resolver = MagicMock()
+    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")
+    ctx.step_index = 0
+    ctx.step_name = "compact-step"
+
+    with patch(
+        "squadron.pipeline.actions.summary.capture_summary_via_profile",
+        new=AsyncMock(return_value="SHOULD NOT REACH"),
+    ) as mock_oneshot:
+        result = await _execute_summary(
+            context=ctx,
+            instructions="summarize",
+            summary_model_alias="minimax",
+            emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
+            action_type="compact",
+        )
+
+    assert result.success is False
+    assert result.error is not None
+    assert "rotate" in result.error.lower()
+    mock_oneshot.assert_not_called()
diff --git a/tests/pipeline/actions/test_summary.py b/tests/pipeline/actions/test_summary.py
index aeec7fb..f8c3d8b 100644
--- a/tests/pipeline/actions/test_summary.py
+++ b/tests/pipeline/actions/test_summary.py
@@ -152,10 +152,12 @@ async def test_execute_summary_multiple_emits_in_order() -> None:
 
 
 @pytest.mark.asyncio
-async def test_execute_summary_no_sdk_session_returns_failure() -> None:
+async def test_execute_summary_sdk_profile_without_session_fails() -> None:
+    """SDK profile (alias=None → profile=None) without a session fails."""
     from squadron.pipeline.actions.summary import _execute_summary
 
     ctx = _make_context(sdk_session=None)
+    # alias=None means profile=None, which is_sdk_profile treats as SDK
     result = await _execute_summary(
         context=ctx,
         instructions="x",
@@ -438,3 +440,127 @@ async def test_execute_invalid_emit_param_returns_failure() -> None:
     assert result.success is False
     assert result.error is not None
     assert "banana" in result.error
+
+
+# ---------------------------------------------------------------------------
+# T7 (slice 164) — profile branching tests
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.asyncio
+async def test_execute_summary_routes_non_sdk_profile_via_oneshot() -> None:
+    """Non-SDK profile routes through capture_summary_via_profile, not sdk_session."""
+    from unittest.mock import patch
+
+    from squadron.pipeline.actions.summary import _execute_summary
+
+    ctx = _make_context(sdk_session=None)
+    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")
+
+    with patch(
+        "squadron.pipeline.actions.summary.capture_summary_via_profile",
+        new=AsyncMock(return_value="ONESHOT SUMMARY"),
+    ) as mock_oneshot:
+        with patch(
+            "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
+        ):
+            result = await _execute_summary(
+                context=ctx,
+                instructions="summarize",
+                summary_model_alias="minimax",
+                emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
+                action_type="summary",
+            )
+
+    assert result.success is True
+    assert result.outputs.get("summary") == "ONESHOT SUMMARY"
+    mock_oneshot.assert_called_once_with(
+        instructions="summarize",
+        model_id="minimax-01",
+        profile="openrouter",
+    )
+
+
+@pytest.mark.asyncio
+async def test_execute_summary_non_sdk_profile_with_rotate_fails() -> None:
+    """Rotate emit + non-SDK profile fails before any provider call."""
+    from unittest.mock import patch
+
+    from squadron.pipeline.actions.summary import _execute_summary
+
+    ctx = _make_context(sdk_session=None)
+    ctx.resolver.resolve.return_value = ("minimax-01", "openrouter")
+
+    with patch(
+        "squadron.pipeline.actions.summary.capture_summary_via_profile",
+        new=AsyncMock(return_value="SHOULD NOT REACH"),
+    ) as mock_oneshot:
+        result = await _execute_summary(
+            context=ctx,
+            instructions="summarize",
+            summary_model_alias="minimax",
+            emit_destinations=[EmitDestination(kind=EmitKind.ROTATE)],
+            action_type="summary",
+        )
+
+    assert result.success is False
+    assert result.error is not None
+    assert "rotate" in result.error.lower()
+    assert "non-SDK" in result.error or "openrouter" in result.error
+    mock_oneshot.assert_not_called()
+
+
+@pytest.mark.asyncio
+async def test_execute_summary_sdk_profile_path_unchanged() -> None:
+    """SDK profile still calls sdk_session.capture_summary as before."""
+    from squadron.pipeline.actions.summary import _execute_summary
+
+    session = AsyncMock()
+    session.current_model = "sonnet-id"
+    session.capture_summary = AsyncMock(return_value="SDK SUMMARY")
+    ctx = _make_context(sdk_session=session)
+    ctx.resolver.resolve.return_value = ("haiku-resolved", "sdk")
+
+    with patch(
+        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
+    ):
+        result = await _execute_summary(
+            context=ctx,
+            instructions="summarize",
+            summary_model_alias="haiku",
+            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
+            action_type="summary",
+        )
+
+    assert result.success is True
+    session.capture_summary.assert_called_once()
+    assert session.capture_summary.call_args.kwargs["summary_model"] == "haiku-resolved"
+
+
+@pytest.mark.asyncio
+async def test_execute_summary_unannotated_alias_uses_sdk_path() -> None:
+    """Resolver returning profile=None (unannotated alias) uses the SDK path."""
+    from squadron.pipeline.actions.summary import _execute_summary
+
+    session = AsyncMock()
+    session.current_model = "sonnet-id"
+    session.capture_summary = AsyncMock(return_value="SDK SUMMARY")
+    ctx = _make_context(sdk_session=session)
+    ctx.resolver.resolve.return_value = ("some-resolved-id", None)
+
+    with patch(
+        "squadron.pipeline.actions.summary.get_emit", return_value=_fake_emit_ok
+    ):
+        result = await _execute_summary(
+            context=ctx,
+            instructions="summarize",
+            summary_model_alias="some-alias",
+            emit_destinations=[EmitDestination(kind=EmitKind.STDOUT)],
+            action_type="summary",
+        )
+
+    assert result.success is True
+    session.capture_summary.assert_called_once()
+    assert (
+        session.capture_summary.call_args.kwargs["summary_model"] == "some-resolved-id"
+    )
diff --git a/tests/pipeline/test_prompt_renderer.py b/tests/pipeline/test_prompt_renderer.py
index f956577..13f89e9 100644
--- a/tests/pipeline/test_prompt_renderer.py
+++ b/tests/pipeline/test_prompt_renderer.py
@@ -311,6 +311,88 @@ class TestRenderSummary:
         )
         assert result.emit == ["rotate"]
 
+    # T12 — profile branching tests
+
+    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
+    @patch("squadron.pipeline.prompt_renderer.render_instructions")
+    def test_sdk_profile_emits_model_switch(
+        self, mock_render: MagicMock, mock_load: MagicMock
+    ) -> None:
+        """SDK profile alias → model_switch set, command is None."""
+        mock_load.return_value = MagicMock()
+        mock_render.return_value = "instructions"
+        resolver = MagicMock()
+        resolver.resolve.return_value = ("haiku-model-id", "sdk")
+
+        result = _render_summary({"model": "haiku"}, {}, resolver)
+
+        assert result.model_switch == "/model haiku"
+        assert result.command is None
+
+    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
+    @patch("squadron.pipeline.prompt_renderer.render_instructions")
+    def test_unannotated_alias_emits_model_switch(
+        self, mock_render: MagicMock, mock_load: MagicMock
+    ) -> None:
+        """profile=None (unannotated alias) is treated as SDK → model_switch."""
+        mock_load.return_value = MagicMock()
+        mock_render.return_value = "instructions"
+        resolver = MagicMock()
+        resolver.resolve.return_value = ("some-id", None)
+
+        result = _render_summary({"model": "some-alias"}, {}, resolver)
+
+        assert result.model_switch == "/model some-alias"
+        assert result.command is None
+
+    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
+    @patch("squadron.pipeline.prompt_renderer.render_instructions")
+    def test_non_sdk_profile_emits_command(
+        self, mock_render: MagicMock, mock_load: MagicMock
+    ) -> None:
+        """Non-SDK profile → command set with sq _summary-run, model_switch is None."""
+        mock_load.return_value = MagicMock()
+        mock_render.return_value = "instructions"
+        resolver = MagicMock()
+        resolver.resolve.return_value = ("minimax-01", "openrouter")
+
+        result = _render_summary(
+            {"model": "minimax", "template": "minimal-sdk"}, {}, resolver
+        )
+
+        assert result.model_switch is None
+        assert result.command is not None
+        assert result.command.startswith("sq _summary-run")
+        assert "--template" in result.command
+        assert "--profile openrouter" in result.command
+        assert "--model minimax-01" in result.command
+
+    @patch("squadron.pipeline.prompt_renderer.load_compaction_template")
+    @patch("squadron.pipeline.prompt_renderer.render_instructions")
+    def test_non_sdk_profile_quotes_params(
+        self, mock_render: MagicMock, mock_load: MagicMock
+    ) -> None:
+        """Shell-special param values are quoted so shlex.split recovers them."""
+        import shlex
+
+        mock_load.return_value = MagicMock()
+        mock_render.return_value = "instructions"
+        resolver = MagicMock()
+        resolver.resolve.return_value = ("minimax-01", "openrouter")
+
+        result = _render_summary(
+            {"model": "minimax"},
+            {"slice": "a slice with spaces"},
+            resolver,
+        )
+
+        assert result.command is not None
+        # shlex.split must recover the param value intact
+        parsed = shlex.split(result.command)
+        param_idx = parsed.index("--param")
+        kv = parsed[param_idx + 1]
+        assert kv == "slice=a slice with spaces"
+
 
 class TestFallbackUnknownAction:
     def test_unknown_type_returns_generic_instruction(self) -> None:
diff --git a/tests/pipeline/test_summary_oneshot.py b/tests/pipeline/test_summary_oneshot.py
new file mode 100644
index 0000000..c73d7c9
--- /dev/null
+++ b/tests/pipeline/test_summary_oneshot.py
@@ -0,0 +1,200 @@
+"""Tests for squadron.pipeline.summary_oneshot."""
+
+from __future__ import annotations
+
+from collections.abc import AsyncIterator
+from unittest.mock import AsyncMock, MagicMock
+
+import pytest
+
+from squadron.core.models import SDK_RESULT_TYPE, Message
+from squadron.pipeline.summary_oneshot import (
+    capture_summary_via_profile,
+    is_sdk_profile,
+)
+from squadron.providers.base import AgentProvider, ProviderCapabilities
+
+# ---------------------------------------------------------------------------
+# T3 — is_sdk_profile predicate
+# ---------------------------------------------------------------------------
+
+
+@pytest.mark.parametrize(
+    "profile,expected",
+    [
+        (None, True),
+        ("sdk", True),
+        ("openrouter", False),
+        ("openai", False),
+        ("gemini", False),
+        ("local", False),
+        ("openai-oauth", False),
+        ("unknown-future", False),
+    ],
+)
+def test_is_sdk_profile(profile: str | None, expected: bool) -> None:
+    assert is_sdk_profile(profile) is expected
+
+
+# ---------------------------------------------------------------------------
+# T5 — capture_summary_via_profile with stub provider
+# ---------------------------------------------------------------------------
+
+_FAKE_PROFILE = "fake-oneshot"
+_FAKE_PROVIDER_TYPE = "fake-oneshot-provider"
+
+
+def _make_fake_message(content: str, sdk_type: str | None = None) -> Message:
+    msg = MagicMock(spec=Message)
+    msg.content = content
+    msg.metadata = {"sdk_type": sdk_type} if sdk_type else {}
+    return msg
+
+
+def _make_fake_agent(
+    messages: list[Message], *, raises: Exception | None = None
+) -> MagicMock:
+    """Return a fake Agent that yields *messages* from handle_message()."""
+
+    async def _handle(message: Message) -> AsyncIterator[Message]:
+        if raises is not None:
+            raise raises
+        for m in messages:
+            yield m
+
+    agent = MagicMock()
+    agent.handle_message = _handle
+    agent.shutdown = AsyncMock()
+    return agent
+
+
+def _make_fake_provider(agent: MagicMock) -> AgentProvider:
+    provider = MagicMock(spec=AgentProvider)
+    provider.provider_type = _FAKE_PROVIDER_TYPE
+    provider.capabilities = ProviderCapabilities()
+    provider.create_agent = AsyncMock(return_value=agent)
+    return provider
+
+
+@pytest.fixture()
+def fake_provider_env(monkeypatch: pytest.MonkeyPatch) -> None:
+    """Register a fake profile and provider for the duration of the test."""
+    from squadron.providers import profiles as profiles_mod
+    from squadron.providers import registry as registry_mod
+    from squadron.providers.profiles import ProviderProfile
+
+    fake_profile = ProviderProfile(
+        name=_FAKE_PROFILE,
+        provider=_FAKE_PROVIDER_TYPE,
+        api_key_env=None,
+        description="Fake profile for unit tests",
+    )
+
+    original_get_all = profiles_mod.get_all_profiles
+    monkeypatch.setattr(
+        profiles_mod,
+        "get_all_profiles",
+        lambda: {**original_get_all(), _FAKE_PROFILE: fake_profile},
+    )
+
+    original_registry = dict(registry_mod._REGISTRY)
+
+    def _restore() -> None:
+        registry_mod._REGISTRY.clear()
+        registry_mod._REGISTRY.update(original_registry)
+
+    monkeypatch.setattr(
+        registry_mod,
+        "ensure_provider_loaded",
+        lambda name: None,  # type: ignore[attr-defined]
+        raising=False,
+    )
+
+    yield  # type: ignore[misc]
+    _restore()
+
+
+@pytest.mark.asyncio
+async def test_capture_summary_happy_path(
+    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
+) -> None:
+    from squadron.providers import registry as registry_mod
+
+    agent = _make_fake_agent([_make_fake_message("SUMMARY OUTPUT")])
+    provider = _make_fake_provider(agent)
+    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider
+
+    result = await capture_summary_via_profile(
+        instructions="summarize this",
+        model_id="model-x",
+        profile=_FAKE_PROFILE,
+    )
+
+    assert result == "SUMMARY OUTPUT"
+    agent.shutdown.assert_called_once()
+
+
+@pytest.mark.asyncio
+async def test_capture_summary_multi_chunk(
+    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
+) -> None:
+    from squadron.providers import registry as registry_mod
+
+    msgs = [_make_fake_message("Part A"), _make_fake_message(" Part B")]
+    agent = _make_fake_agent(msgs)
+    provider = _make_fake_provider(agent)
+    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider
+
+    result = await capture_summary_via_profile(
+        instructions="summarize",
+        model_id=None,
+        profile=_FAKE_PROFILE,
+    )
+
+    assert result == "Part A Part B"
+    agent.shutdown.assert_called_once()
+
+
+@pytest.mark.asyncio
+async def test_capture_summary_filters_sdk_result_type(
+    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
+) -> None:
+    from squadron.providers import registry as registry_mod
+
+    msgs = [
+        _make_fake_message("REAL CONTENT"),
+        _make_fake_message("REAL CONTENT", sdk_type=SDK_RESULT_TYPE),
+    ]
+    agent = _make_fake_agent(msgs)
+    provider = _make_fake_provider(agent)
+    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider
+
+    result = await capture_summary_via_profile(
+        instructions="summarize",
+        model_id=None,
+        profile=_FAKE_PROFILE,
+    )
+
+    # Duplicate ResultMessage must be filtered — content appears only once
+    assert result == "REAL CONTENT"
+    agent.shutdown.assert_called_once()
+
+
+@pytest.mark.asyncio
+async def test_capture_summary_shutdown_called_on_exception(
+    monkeypatch: pytest.MonkeyPatch, fake_provider_env: None
+) -> None:
+    from squadron.providers import registry as registry_mod
+
+    agent = _make_fake_agent([], raises=RuntimeError("provider exploded"))
+    provider = _make_fake_provider(agent)
+    registry_mod._REGISTRY[_FAKE_PROVIDER_TYPE] = provider
+
+    with pytest.raises(RuntimeError, match="provider exploded"):
+        await capture_summary_via_profile(
+            instructions="summarize",
+            model_id=None,
+            profile=_FAKE_PROFILE,
+        )
+
+    agent.shutdown.assert_called_once()
diff --git a/tests/review/test_rules.py b/tests/review/test_rules.py
index 956432b..52d6784 100644
--- a/tests/review/test_rules.py
+++ b/tests/review/test_rules.py
@@ -51,7 +51,12 @@ class TestRulesFlag:
         rules_file = tmp_path / "rules.md"
         rules_file.write_text("Always check for null pointers.")
 
-        result = cli_runner.invoke(app, ["review", "code", "--rules", str(rules_file)])
+        # Isolate from filesystem: suppress auto-template-rules resolution so
+        # we only test that the explicit --rules file content reaches the runner.
+        with patch("squadron.cli.commands.review.resolve_rules_dir", return_value=None):
+            result = cli_runner.invoke(
+                app, ["review", "code", "--rules", str(rules_file)]
+            )
         assert result.exit_code == 0
 
         # run_review was called with rules_content keyword

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

Let me review the code changes from this git diff against the project's conventions and language-specific best practices.

## Summary
[overall assessment: PASS]

## Findings

### [PASS] Type safety and forward reference handling
category: typing
location: src/squadron/cli/commands/summary_run.py:1

The file correctly uses `from __future__ import annotations` for Python 3.12+ compatibility, ensuring clean forward reference resolution. Union types use the modern `str | None` syntax.

### [PASS] Shell parameter escaping
category: security
location: src/squadron/pipeline/prompt_renderer.py:280

The code correctly uses `shlex.quote(str(value))` when constructing the `_summary-run` command with user-provided pipeline parameters. This prevents shell injection vulnerabilities when values contain spaces or special characters. The corresponding test `test_non_sdk_profile_quotes_params` in `tests/pipeline/test_prompt_renderer.py` validates this behavior correctly.

### [PASS] Specific exception handling
category: error-handling
location: src/squadron/cli/commands/summary_run.py:38-43

The error handling in `summary_run` is well-structured:
- `FileNotFoundError` is caught explicitly when loading templates
- Parameter parsing validates format before use with a clear error message
- Generic exception handling wraps provider failures with informative output

### [PASS] Fail-fast validation for incompatible features
category: error-handling
location: src/squadron/pipeline/actions/summary.py:140-153

The validation for ROTATE emit with non-SDK profiles follows the "fail fast" principle. Invalid state combinations are caught early at the boundary before any provider call, returning explicit `ActionResult` with descriptive errors rather than proceeding to a likely failure deeper in the call stack.

### [PASS] Open/Closed via profile branching
category: design
location: src/squadron/pipeline/summary_oneshot.py:45-86

The `capture_summary_via_profile()` function follows the existing pattern from `run_review_with_profile()` and provides a clean extension point for adding new provider profiles without modifying existing code. The `is_sdk_profile()` predicate acts as a proper abstraction boundary.

### [PASS] Comprehensive test coverage
category: testing

The test additions provide good coverage for the new functionality:
- `tests/cli/commands/test_summary_run.py` covers CLI invocation, parameter parsing, error cases
- `tests/pipeline/test_summary_oneshot.py` tests the core profile routing logic with parametrized tests
- `tests/pipeline/actions/test_summary.py` validates the SDK vs non-SDK branching in the summary action

### [PASS] Test isolation improvement
category: testing
location: tests/review/test_rules.py:54-58

The change to isolate the filesystem-dependent test by patching `resolve_rules_dir` demonstrates good testing discipline—tests should not depend on external state unless that's specifically what they're testing.

### [PASS] Async cleanup via try/finally
category: error-handling
location: src/squadron/pipeline/summary_oneshot.py:82-86

The `capture_summary_via_profile` function uses `try/finally` to ensure `agent.shutdown()` is called even when the provider raises an exception, preventing resource leaks. The corresponding test `test_capture_summary_shutdown_called_on_exception` validates this behavior.

### [PASS] Docstring completeness
category: documentation
location: src/squadron/pipeline/summary_oneshot.py:1-12, src/squadron/cli/commands/summary_run.py:1-7

Both new modules include module-level docstrings explaining their purpose and the architectural pattern they implement. The hidden command docstring correctly notes its use case for the prompt-only pipeline rendering scenario.
