---
slice: m1-polish-and-publish
project: squadron
lld: user/slices/106-slice.m1-polish-and-publish.md
dependencies: [foundation, sdk-agent-provider, cli-foundation, review-workflow-templates]
projectState: >
  Slices 100-105 complete. Review CLI works end-to-end with arch, tasks, and
  code templates. 232 tests passing, 0 pyright/ruff errors. Branch
  105-slice.review-workflow-templates is current.
dateCreated: 20260222
dateUpdated: 20260222
docType: tasks
status: complete
---

## Context Summary

- Working on m1-polish-and-publish slice (106)
- Polishes the M1 deliverable for external adoption: config persistence, verbosity levels, text color improvements, `--rules` flag, and documentation
- All prerequisite slices (100-105) are complete; the review CLI is functional
- Dependencies: `tomli-w` for TOML writing (Python 3.11+ has `tomllib` for reading)
- Next planned work: M2

---

## Tasks

### T1 — Add `tomli-w` dependency
- [x] Add `tomli-w>=1.0` to `pyproject.toml` dependencies
- [x] Run `uv sync` to install
  - [x] SC: `uv pip list` shows `tomli-w` installed
  - [x] SC: `uv run python -c "import tomli_w"` succeeds

### T2 — Config module: key definitions and defaults
- [x] Create `src/orchestration/config/__init__.py` (module docstring only)
- [x] Create `src/orchestration/config/keys.py`
  - [x] Define `ConfigKey` dataclass: `name: str`, `type_: type`, `default: object`, `description: str`
  - [x] Define `CONFIG_KEYS: dict[str, ConfigKey]` with initial keys from slice design:
    - `cwd` (str, default `"."`)
    - `verbosity` (int, default `0`)
    - `default_rules` (str | None, default `None`)
  - [x] Helper `get_default(key: str) -> object` that returns the default for a key, raises `KeyError` for unknown keys
  - [x] SC: All three keys defined with correct types and defaults
  - [x] SC: `ruff check` and `pyright` pass

### T3 — Config module: manager (load, merge, persist)
- [x] Create `src/orchestration/config/manager.py`
  - [x] `user_config_path() -> Path` — returns `~/.config/orchestration/config.toml`
  - [x] `project_config_path(cwd: str = ".") -> Path` — returns `{cwd}/.orchestration.toml`
  - [x] `load_config(cwd: str = ".") -> dict[str, object]` — loads user config, overlays project config, fills defaults. Missing files are silently skipped (all keys have defaults).
  - [x] `get_config(key: str, cwd: str = ".") -> object` — convenience for a single key
  - [x] `set_config(key: str, value: str, project: bool = False, cwd: str = ".") -> None` — writes to the appropriate TOML file. Creates file/directories if needed. Validates key name against `CONFIG_KEYS`. Coerces string value to the key's declared type.
  - [x] `resolve_config_source(key: str, cwd: str = ".") -> str` — returns `"project"`, `"user"`, or `"default"` indicating where the resolved value comes from
  - [x] Use `tomllib` (stdlib) for reading, `tomli_w` for writing
  - [x] SC: `ruff check` and `pyright` pass
  - [x] SC: No silent fallback values — unknown keys raise `KeyError`

### T4 — Config manager tests
- [x] Create `tests/config/__init__.py`
- [x] Create `tests/config/conftest.py` with `tmp_path`-based fixtures for user and project config files
- [x] Create `tests/config/test_manager.py`
  - [x] Test: `load_config` returns defaults when no config files exist
  - [x] Test: user config file overrides defaults
  - [x] Test: project config file overrides user config
  - [x] Test: precedence chain — project > user > default
  - [x] Test: `get_config` returns single key value
  - [x] Test: `set_config` creates user config file and directories
  - [x] Test: `set_config` with `project=True` writes to project config
  - [x] Test: `set_config` coerces string value to int for `verbosity`
  - [x] Test: `set_config` raises `KeyError` for unknown key
  - [x] Test: `resolve_config_source` returns correct source label
  - [x] SC: All tests pass
  - [x] SC: `ruff check` passes

### T5 — Config CLI commands
- [x] Create `src/orchestration/cli/commands/config.py`
  - [x] `config_app = typer.Typer(name="config", ...)`
  - [x] `config set KEY VALUE [--project]` — calls `set_config`, prints confirmation with source
  - [x] `config get KEY [--cwd DIR]` — calls `get_config` and `resolve_config_source`, prints value and source
  - [x] `config list [--cwd DIR]` — iterates `CONFIG_KEYS`, prints each key's resolved value and source in aligned columns
  - [x] `config path` — prints both config file paths with existence status
- [x] Register `config_app` in `src/orchestration/cli/app.py` via `app.add_typer(config_app, name="config")`
  - [x] SC: `orchestration config --help` works
  - [x] SC: `ruff check` and `pyright` pass

### T6 — Config CLI tests
- [x] Create `tests/config/test_cli_config.py`
  - [x] Test: `config set KEY VALUE` writes to user config
  - [x] Test: `config set KEY VALUE --project` writes to project config
  - [x] Test: `config get KEY` displays resolved value and source
  - [x] Test: `config list` shows all keys with values and sources
  - [x] Test: `config path` shows both file paths
  - [x] Test: unknown key produces error message and non-zero exit
  - [x] SC: All tests pass
  - [x] SC: `ruff check` passes

### T7 — Commit: config system
- [x] `git add` and commit config module, CLI commands, and tests
  - [x] SC: All tests pass before commit

### T8 — Verbosity levels in display_result
- [x] Modify `_display_terminal` in `src/orchestration/cli/commands/review.py`
  - [x] Accept `verbosity: int` parameter (default `0`)
  - [x] Verbosity 0: verdict badge + finding headings with severity (no descriptions)
  - [x] Verbosity 1: above + full finding descriptions
  - [x] Verbosity 2: above + raw_output (tool usage details are embedded in agent output)
  - [x] Update `display_result` signature to accept `verbosity`
  - [x] Update `_run_review_command` to accept and pass through `verbosity`
- [x] Add `-v` / `--verbose` flag to `review_arch`, `review_tasks`, `review_code` commands
  - [x] `-v` sets verbosity 1, `-vv` sets verbosity 2 (use `typer.Option` count or explicit int)
  - [x] If no flag, read default from config via `get_config("verbosity")`
- [x] SC: `ruff check` and `pyright` pass

### T9 — Text color improvements
- [x] Modify `_display_terminal` in `src/orchestration/cli/commands/review.py`
  - [x] Severity badges: keep bright green (PASS), yellow/amber (CONCERN), red (FAIL)
  - [x] Finding headings: use `bold white` (high luminance, readable on any background)
  - [x] Body text (descriptions): use default terminal foreground (no explicit color style) instead of `dim`
  - [x] File paths and code references: use `cyan`
  - [x] All styling via Rich markup — no raw ANSI escape codes
- [x] SC: Output is readable on both dark and light terminal backgrounds
- [x] SC: `ruff check` passes

### T10 — Verbosity and display tests
- [x] Update `tests/review/test_cli_review.py` (or create separate `test_verbosity.py` if cleaner)
  - [x] Test: verbosity 0 shows verdict and finding headings but NOT descriptions
  - [x] Test: verbosity 1 shows verdict, headings, AND descriptions
  - [x] Test: verbosity 2 includes raw output
  - [x] Test: `-v` flag sets verbosity 1
  - [x] Test: config-based default verbosity is respected when no flag given
  - [x] SC: All tests pass
  - [x] SC: `ruff check` passes

### T11 — Commit: verbosity and text colors
- [x] `git add` and commit review display changes and tests
  - [x] SC: All tests pass before commit

### T12 — `--rules` flag on `review code`
- [x] Modify `review_code` command in `src/orchestration/cli/commands/review.py`
  - [x] Add `--rules PATH` option (default: `None`)
  - [x] If no `--rules` flag, fall back to `get_config("default_rules")`
  - [x] If rules path is set, read file content at CLI level
  - [x] Pass rules content to `_run_review_command` as part of inputs or as separate parameter
- [x] Modify `_execute_review` (or `run_review` in runner) to accept optional rules content
  - [x] When rules content is provided, append to template's system prompt as `\n\n## Additional Review Rules\n\n{rules_content}`
  - [x] The modification happens on a copy of the template's system_prompt, not the template itself
- [x] SC: `ruff check` and `pyright` pass

### T13 — `--rules` flag tests
- [x] Add tests to `tests/review/test_cli_review.py` (or new `test_rules.py`)
  - [x] Test: `--rules path/to/file` reads the file and appends content to system prompt
  - [x] Test: config-based `default_rules` is used when no `--rules` flag
  - [x] Test: `--rules` flag overrides config-based default_rules
  - [x] Test: missing rules file produces error and non-zero exit
  - [x] SC: All tests pass
  - [x] SC: `ruff check` passes

### T14 — Config integration for `--cwd` in review commands
- [x] Modify review commands (`review_arch`, `review_tasks`, `review_code`) to read `cwd` from config when `--cwd` flag is not explicitly provided
  - [x] CLI `--cwd` flag overrides config value
  - [x] Config `cwd` overrides default `"."`
- [x] Add tests for config-based cwd resolution
  - [x] Test: review command uses config cwd when no `--cwd` flag
  - [x] Test: `--cwd` flag overrides config value
  - [x] SC: All tests pass

### T15 — Commit: rules flag and config integration
- [x] `git add` and commit rules flag, config integration, and tests
  - [x] SC: All tests pass before commit

### T16 — Full validation pass
- [x] Run full test suite: `uv run pytest`
- [x] Run type checker: `uv run pyright`
- [x] Run linter/formatter: `uv run ruff check` and `uv run ruff format --check`
  - [x] SC: All tests pass
  - [x] SC: Zero pyright errors
  - [x] SC: Zero ruff errors

### T17 — README.md
- [x] Create `docs/README.md` (primary documentation for external users)
  - [x] Hero section: one sentence, install command, one example
  - [x] Quickstart: clone → install → configure credentials → run first review (target: 5 minutes)
  - [x] Command reference: all commands with examples (review arch/tasks/code/list, config set/get/list/path)
  - [x] Configuration: user vs project config, all keys, examples
  - [x] Review templates: what each template does, when to use it
  - [x] Architecture: brief overview for contributors
- [x] SC: README enables a new user to install and run first review in under 5 minutes
- [x] SC: All commands documented with examples

### T18 — COMMANDS.md
- [x] Create `docs/COMMANDS.md` (full command reference)
  - [x] Every command and subcommand with all flags, types, defaults
  - [x] Usage examples for each command
  - [x] Exit codes documented
  - [x] SC: Every CLI command is represented

### T19 — TEMPLATES.md
- [x] Create `docs/TEMPLATES.md` (template authoring guide for future user-defined templates)
  - [x] YAML schema reference with all fields
  - [x] Example template (annotated)
  - [x] Explanation of `prompt_template` vs `prompt_builder`
  - [x] Input definitions (required/optional)
  - [x] How to register a custom template
  - [x] Noted as future capability — not yet implemented for end users
  - [x] SC: A developer can understand how to create a custom template from this guide

### T20 — Commit: documentation
- [x] `git add` and commit all docs
  - [x] SC: Documentation is committed

### T21 — Final build and validation
- [x] Run full test suite: `uv run pytest`
- [x] Run type checker: `uv run pyright`
- [x] Run linter/formatter: `uv run ruff check` and `uv run ruff format --check`
  - [x] SC: All tests pass
  - [x] SC: Zero pyright errors
  - [x] SC: Zero ruff errors

### T22 — DEVLOG entry
- [x] Write session summary to DEVLOG.md per prompt.ai-project.system.md guidance
  - [x] SC: DEVLOG entry captures slice 106 completion, commit hashes, test counts
