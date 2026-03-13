---
docType: task-breakdown
slice: review-workflow-templates
project: squadron
lld: user/slices/105-slice.review-workflow-templates.md
dependencies: [foundation, sdk-agent-provider, cli-foundation]
projectState: >
  Foundation, SDK Agent Provider, and CLI Foundation are complete.
  Slice 104 deferred. This slice (105) is the active work item.
dateCreated: 20260222
dateUpdated: 20260222
---

## Context Summary

- Implementing the `review` CLI subcommand and review workflow engine
- Three built-in review types: `arch`, `tasks`, `code`
- Uses `ClaudeSDKClient` directly (not agent registry); ephemeral sessions per review
- Templates defined as YAML files, loaded into `ReviewTemplate` dataclasses at runtime
- Structured `ReviewResult` output consumed by CLI and future pipeline executor
- Test-with philosophy: tests follow each implementation component immediately
- Commit checkpoints after each stable milestone
- Next planned slice: End-to-End Testing (slice 17) or Automated Dev Pipeline (160)

---

## Tasks

- [x] **T1: Add pyyaml dependency**
  - [x] Add `pyyaml` to `pyproject.toml` under project dependencies
  - [x] Run `uv sync` to install and lock
  - [x] Success: `import yaml` works in the project virtualenv; lock file updated

- [x] **T2: Create test infrastructure for review module**
  - [x] Create `tests/review/__init__.py`
  - [x] Create `tests/review/conftest.py` with shared fixtures:
    - `mock_sdk_client`: patches `ClaudeSDKClient` at import boundary; `receive_response()` returns a configurable async iterator of messages
    - `sample_review_result`: a pre-built `ReviewResult` for output/display tests
    - `builtin_templates_dir`: path to `src/orchestration/review/templates/builtin/`
  - [x] Success: `pytest tests/review/` collects with no errors; fixtures importable

- [x] **T3: Implement result models (`models.py`)**
  - [x] Create `src/orchestration/review/__init__.py`
  - [x] Create `src/orchestration/review/models.py` with:
    - `Verdict(str, Enum)`: `PASS`, `CONCERNS`, `FAIL`, `UNKNOWN`
    - `Severity(str, Enum)`: `PASS`, `CONCERN`, `FAIL`
    - `ReviewFinding` dataclass: `severity`, `title`, `description`, `file_ref: str | None`
    - `ReviewResult` dataclass: `verdict`, `findings`, `raw_output`, `template_name`, `input_files`, `timestamp`; `to_dict()` method; `has_failures` and `concern_count` properties
  - [x] Type-check with mypy/pyright; ruff passes
  - [x] Success: all fields and methods present; `to_dict()` returns JSON-serializable dict

- [x] **T4: Test result models**
  - [x] Create `tests/review/test_models.py`
  - [x] Test `ReviewResult` construction with findings; `to_dict()` serialization; `has_failures` and `concern_count` properties
  - [x] Test `ReviewFinding` with and without `file_ref`
  - [x] Test `Verdict` and `Severity` enum string values
  - [x] Success: `pytest tests/review/test_models.py` passes; zero mypy errors
  - [x] Commit: `feat: add review result models`

- [x] **T5: Implement ReviewTemplate dataclass and InputDef (`templates.py`)**
  - [x] Create `src/orchestration/review/templates.py` with:
    - `InputDef` dataclass: `name`, `description`, `default: str | None`
    - `ReviewTemplate` dataclass: all fields per slice design; `build_prompt(inputs)` method that dispatches to `prompt_builder` or formats `prompt_template`; raises `ValueError` if neither is set
  - [x] Type-check; ruff passes
  - [x] Success: `ReviewTemplate.build_prompt()` returns correct string for both `prompt_template` and `prompt_builder` paths; raises on missing both

- [x] **T6: Implement YAML loader and template registry (`templates.py` continued)**
  - [x] Add `TemplateValidationError` exception to `models.py` (or a dedicated `exceptions.py`)
  - [x] Implement `load_template(path: Path) -> ReviewTemplate`:
    - Validate mutual exclusion of `prompt_template`/`prompt_builder`
    - Resolve `prompt_builder` dotted path via `importlib`
    - Parse `inputs.required` and `inputs.optional` into `InputDef` lists
  - [x] Implement registry: `_TEMPLATES` dict, `register_template()`, `get_template()`, `list_templates()`
  - [x] Implement `load_builtin_templates()`: scans `templates/builtin/*.yaml` relative to `templates.py`
  - [x] Type-check; ruff passes
  - [x] Success: `load_builtin_templates()` loads all three YAMLs without error once they exist

- [x] **T7: Test template loading and registry**
  - [x] Create `tests/review/test_templates.py`
  - [x] Test `load_template()` with a valid inline YAML (using `tmp_path` fixture)
  - [x] Test validation error: both `prompt_template` and `prompt_builder` present
  - [x] Test validation error: neither present
  - [x] Test `prompt_builder` dotted-path resolution (use a real importable function)
  - [x] Test registry: `register_template`, `get_template` hit/miss, `list_templates`
  - [x] Success: `pytest tests/review/test_templates.py` passes
  - [x] Commit: `feat: add ReviewTemplate dataclass, YAML loader, and registry`

- [x] **T8: Create built-in template directory structure**
  - [x] Create `src/orchestration/review/templates/builtin/` directory
  - [x] Create `src/orchestration/review/templates/__init__.py` (empty)
  - [x] Create `src/orchestration/review/builders/__init__.py` (empty)
  - [x] Ensure `templates/builtin/` is included in package data (update `pyproject.toml` if needed)
  - [x] Success: `Path(__file__).parent / "templates" / "builtin"` resolves correctly at runtime

- [x] **T9: Create `arch.yaml` built-in template**
  - [x] Create `src/orchestration/review/templates/builtin/arch.yaml`
  - [x] Include: `name`, `description`, `system_prompt` (alignment criteria per slice design), `allowed_tools: [Read, Glob, Grep]`, `permission_mode: bypassPermissions`, `setting_sources: null`, `inputs` (required: `input`, `against`; optional: `cwd`), `prompt_template`
  - [x] Success: `load_template("arch.yaml")` returns `ReviewTemplate` with name `arch`; `build_prompt({input: "a.md", against: "b.md"})` returns non-empty string with both paths present

- [x] **T10: Test `arch` template prompt construction**
  - [x] Create `tests/review/test_builtin_arch.py`
  - [x] Test `load_template` on `arch.yaml`; verify name, description, allowed_tools, permission_mode
  - [x] Test `build_prompt` with required inputs; assert both paths appear in output
  - [x] Test `build_prompt` with optional `cwd`
  - [x] Success: `pytest tests/review/test_builtin_arch.py` passes

- [x] **T11: Create `tasks.yaml` built-in template**
  - [x] Create `src/orchestration/review/templates/builtin/tasks.yaml`
  - [x] Include: system prompt focused on cross-referencing success criteria, gap detection, sequencing, task granularity (per slice design); `allowed_tools: [Read, Glob, Grep]`; `prompt_template` with `{input}` (task file) and `{against}` (slice design)
  - [x] Success: `load_template("tasks.yaml")` returns `ReviewTemplate` with name `tasks`; `build_prompt` inserts both paths

- [x] **T12: Test `tasks` template prompt construction**
  - [x] Create `tests/review/test_builtin_tasks.py`
  - [x] Test load, field values, and `build_prompt` with required inputs
  - [x] Success: `pytest tests/review/test_builtin_tasks.py` passes

- [x] **T13: Create `code.yaml` built-in template**
  - [x] Create `src/orchestration/review/templates/builtin/code.yaml`
  - [x] Include: system prompt focused on CLAUDE.md conventions, style, test-with pattern, error handling, security; `allowed_tools: [Read, Glob, Grep, Bash]`; `permission_mode: bypassPermissions`; `setting_sources: [project]`; all optional inputs (`cwd`, `files`, `diff`); `prompt_builder: orchestration.review.builders.code.code_review_prompt`
  - [x] Success: `load_template("code.yaml")` returns `ReviewTemplate` with name `code` and `prompt_builder` resolved to callable

- [x] **T14: Implement `code_review_prompt` builder**
  - [x] Create `src/orchestration/review/builders/code.py`
  - [x] Implement `code_review_prompt(inputs: dict[str, str]) -> str`:
    - If `diff` present: instruct agent to run `git diff {diff}` to identify changed files, then review those files
    - If `files` present: scope review to glob pattern
    - If neither: agent surveys project structure via Glob/Grep
    - `cwd` always included in prompt
  - [x] Type-check; ruff passes
  - [x] Success: function returns correct prompt string for each combination of inputs

- [x] **T15: Test `code` template and builder**
  - [x] Create `tests/review/test_builtin_code.py`
  - [x] Test `load_template("code.yaml")`; verify `prompt_builder` is callable
  - [x] Test `code_review_prompt` with `diff` only, `files` only, neither, and both (`diff` + `files`)
  - [x] Success: `pytest tests/review/test_builtin_code.py` passes
  - [x] Commit: `feat: add built-in review templates (arch, tasks, code)`

- [x] **T16: Implement result parser (`parsers.py`)**
  - [x] Create `src/orchestration/review/parsers.py`
  - [x] Implement `parse_review_output(raw_output, template_name, input_files) -> ReviewResult`:
    - `_extract_verdict(text)`: parse `## Summary` section for PASS/CONCERNS/FAIL; return `Verdict.UNKNOWN` on failure
    - `_extract_findings(text)`: parse `### [SEVERITY] Title` blocks into `ReviewFinding` list
    - Fallback: if parsing fails entirely, return `ReviewResult` with `UNKNOWN` verdict and raw text preserved
  - [x] Type-check; ruff passes
  - [x] Success: well-formed agent output parses to correct `ReviewResult`; malformed output returns `UNKNOWN` without raising

- [x] **T17: Test result parser**
  - [x] Create `tests/review/test_parsers.py`
  - [x] Test well-formed markdown with PASS/CONCERNS/FAIL verdicts and multiple findings
  - [x] Test malformed: missing `## Summary`; missing severity prefix; empty output; partial output
  - [x] Test `UNKNOWN` fallback: raw output preserved in result
  - [x] Parametrize verdict extraction across all three verdict strings
  - [x] Success: `pytest tests/review/test_parsers.py` passes
  - [x] Commit: `feat: add review result parser`

- [x] **T18: Implement review runner (`runner.py`)**
  - [x] Create `src/orchestration/review/runner.py`
  - [x] Implement `async def run_review(template: ReviewTemplate, inputs: dict[str, str]) -> ReviewResult`:
    - Build prompt via `template.build_prompt(inputs)`
    - Construct `ClaudeAgentOptions` from template fields
    - Open `ClaudeSDKClient` context manager, call `client.query(prompt)`, iterate `client.receive_response()` to collect `raw_output`
    - Call `parse_review_output(raw_output, template.name, inputs)`
    - Return `ReviewResult`
  - [x] Type-check; ruff passes
  - [x] Success: runner compiles; `run_review` signature matches slice design

- [x] **T19: Test review runner**
  - [x] Create `tests/review/test_runner.py`
  - [x] Use `mock_sdk_client` fixture to inject predefined response
  - [x] Test: `ClaudeAgentOptions` constructed with correct fields from template
  - [x] Test: `ClaudeSDKClient` instantiated with those options
  - [x] Test: `client.query()` called with prompt built from `template.build_prompt(inputs)`
  - [x] Test: `ReviewResult` returned with expected verdict and findings from mock response
  - [x] Success: `pytest tests/review/test_runner.py` passes
  - [x] Commit: `feat: add review runner`

- [x] **T20: Implement CLI `review` subcommand (`cli/commands/review.py`)**
  - [x] Create `src/orchestration/cli/commands/review.py` with Typer app `review_app`
  - [x] Implement `review arch INPUT --against CONTEXT [--cwd DIR] [--output FORMAT]`
  - [x] Implement `review tasks INPUT --against CONTEXT [--cwd DIR] [--output FORMAT]`
  - [x] Implement `review code [--cwd DIR] [--files PATTERN] [--diff REF] [--output FORMAT]`
  - [x] Implement `review list`: loads builtin templates, prints name + description table
  - [x] Implement `display_result(result, output_mode, output_path)`: `terminal` (Rich), `json` (stdout), `file` (JSON to path)
  - [x] Wire `review_app` into the main Typer app in `cli/main.py` (or equivalent entry point)
  - [x] Handle error cases: invalid template name (list available), missing required args (usage error), SDK errors (user-friendly message)
  - [x] Type-check; ruff passes

- [x] **T21: Test CLI review subcommand**
  - [x] Create `tests/review/test_cli_review.py`
  - [x] Use Typer `CliRunner` and `mock_sdk_client` fixture
  - [x] Test `review arch` with required args; assert exit code 0 and output contains verdict
  - [x] Test `review tasks` with required args
  - [x] Test `review code` with no args, `--files`, and `--diff`
  - [x] Test `review list`: output contains all three template names
  - [x] Test missing required arg: non-zero exit, usage message shown
  - [x] Test invalid template name: error lists available templates
  - [x] Test `--output json`: stdout is valid JSON matching `ReviewResult` structure
  - [x] Test `--output file PATH`: file created at path with JSON content
  - [x] Success: `pytest tests/review/test_cli_review.py` passes
  - [x] Commit: `feat: add review CLI subcommand`

- [x] **T22: Full validation pass**
  - [x] Run `pytest tests/review/` — all tests pass
  - [x] Run `mypy src/orchestration/review/` (or pyright) — zero errors
  - [x] Run `ruff check src/orchestration/review/ tests/review/` — zero errors
  - [x] Run `ruff format --check src/orchestration/review/ tests/review/` — no formatting issues
  - [x] Run full project build to confirm nothing is broken
  - [x] Success: all checks pass with no errors; warnings documented if present
  - [x] Commit: `chore: review slice 105 final validation pass`
