---
docType: tasks
slice: optional-dependency-split-serve-and-codex-extras
project: squadron
lldReference: user/slices/907-slice.optional-dependency-split-serve-and-codex-extras.md
dependencies: []
status: not_started
dateCreated: 20260518
dateUpdated: 20260519
---

# Tasks: Optional Dependency Split — `serve` and `codex` Extras

## Context Summary

Move `fastapi` and `uvicorn` from mandatory dependencies to a `[serve]` optional extra. Add an empty `[codex]` extra with a comment carrying the GitHub install command. To make `sq serve --status` and `--stop` work without the extra, PID/config helpers must be extracted from `daemon.py` (which imports uvicorn at module level) into a new `pid.py` module. Add a fast-fail guard to `_start_daemon()`. Add an early binary check to `CodexProvider.create_agent()` raising `ProviderError`. No behavior change for users with the full install.

**Files touched:**
- `pyproject.toml`
- `.github/workflows/ci.yml`
- `src/squadron/server/pid.py` (new)
- `src/squadron/server/daemon.py`
- `src/squadron/cli/commands/serve.py`
- `src/squadron/providers/codex/provider.py`
- `tests/server/test_daemon.py` (import update + new test)
- `tests/providers/codex/test_provider.py` (new test for binary guard)
- `tests/server/conftest.py` (verify — no change expected)

---

## Tasks

### T1 — Branch Setup

- [ ] **T1.1** Confirm current branch is `main` and working tree is clean (`git status`)
- [ ] **T1.2** Create and switch to branch: `git checkout -b 907-optional-dependency-split`

---

### T2 — `pyproject.toml` Restructure

- [ ] **T2.1** Remove `fastapi>=0.115.0` from `[project.dependencies]`
- [ ] **T2.2** Remove `uvicorn[standard]>=0.30.0` from `[project.dependencies]`
- [ ] **T2.3** Add `[serve]` entry to `[project.optional-dependencies]` with `fastapi>=0.115.0` and `uvicorn[standard]>=0.30.0`
- [ ] **T2.4** Add empty `[codex]` entry to `[project.optional-dependencies]` with a comment block carrying the manual install command:
  ```toml
  # Codex SDK requires manual install from GitHub — PyPI rejects direct URL refs:
  #   pip install 'codex-app-server-sdk @ git+https://github.com/openai/codex.git#subdirectory=sdk/python'
  codex = []
  ```
- [ ] **T2.5** Verify `pyproject.toml` parses cleanly: `python -c "import tomllib; tomllib.load(open('pyproject.toml','rb'))"`

**Test T2:**
- [ ] **T2.6** In current (full) venv, confirm package still installs: `uv pip install -e ".[dev,serve]"`
- [ ] **T2.7** `pip show fastapi` and `pip show uvicorn` still show installed (they're in the env from `[serve]`)

---

### T2b — Update CI Workflow

CI uses `uv sync --dev` (test job) and `uv sync` (build job). `uv sync` does not install optional extras from `[project.optional-dependencies]`; `--extra serve` must be added explicitly so server tests can import fastapi/uvicorn.

- [ ] **T2b.1** In `.github/workflows/ci.yml`, update the test job install step from `uv sync --dev` to `uv sync --dev --extra serve`
- [ ] **T2b.2** Verify the build job (`uv sync` → `uv build`) does not need `--extra serve` (build only needs the package itself; confirm no server imports at build time)

---

### T3 — Extract `src/squadron/server/pid.py`

- [ ] **T3.1** Create `src/squadron/server/pid.py` with the following from `daemon.py`:
  - Module docstring
  - `from __future__ import annotations`
  - Stdlib imports only: `errno`, `os`, `signal` (if needed), `dataclasses`, `pathlib`
  - `_DEFAULT_DIR` path constant (copy from `daemon.py`)
  - `DaemonConfig` dataclass
  - `write_pid_file()`
  - `remove_pid_file()`
  - `read_pid_file()`
  - `is_daemon_running()`

- [ ] **T3.2** Verify `pid.py` has zero imports of `fastapi`, `uvicorn`, or any `squadron.server.app`/`daemon`

- [ ] **T3.3** In `daemon.py`, replace the local definitions of `DaemonConfig`, `write_pid_file`, `remove_pid_file`, `read_pid_file`, `is_daemon_running` with imports from `squadron.server.pid`:
  ```python
  from squadron.server.pid import (
      DaemonConfig,
      is_daemon_running,
      read_pid_file,
      remove_pid_file,
      write_pid_file,
  )
  ```
  Remove the now-redundant local definitions and `_DEFAULT_DIR` from `daemon.py` (it moves to `pid.py`).

**Test T3:**
- [ ] **T3.4** Update `tests/server/test_daemon.py`: change import source from `squadron.server.daemon` to `squadron.server.pid` for `is_daemon_running`, `read_pid_file`, `remove_pid_file`, `write_pid_file`
- [ ] **T3.5** Run `pytest tests/server/test_daemon.py -v` — all existing tests pass
- [ ] **T3.6** Run `pyright src/squadron/server/pid.py src/squadron/server/daemon.py` — zero errors

---

### T4 — Update `serve.py` Imports and Add Guard

- [ ] **T4.1** In `serve.py`, change top-level daemon import to use `pid.py`:
  ```python
  from squadron.server.pid import DaemonConfig, is_daemon_running, read_pid_file
  ```
  Remove `start_server` from top-level imports entirely.

- [ ] **T4.2** Remove top-level `from squadron.server.engine import SquadronEngine` import.

- [ ] **T4.3** In `_start_daemon()`, add the import guard as the first statement (before any server module access):
  ```python
  try:
      import fastapi  # noqa: F401
      import uvicorn  # noqa: F401
  except ImportError:
      rprint(
          "[red]Error:[/red] 'sq serve' requires the [serve] extra.\n"
          "  pip install 'squadron-ai[serve]'"
      )
      raise typer.Exit(code=1)
  ```

- [ ] **T4.4** After the guard in `_start_daemon()`, add deferred imports:
  ```python
  from squadron.server.daemon import start_server
  from squadron.server.engine import SquadronEngine
  ```

**Test T4:**
- [ ] **T4.5** Run `pytest tests/cli/ -v` — existing CLI tests pass
- [ ] **T4.6** Run `pyright src/squadron/cli/commands/serve.py` — zero errors
- [ ] **T4.7** Manually confirm `sq serve --help` works (imports `serve.py` at module level without triggering guard)

---

### T5 — Codex Binary Guard in `provider.py`

- [ ] **T5.1** In `src/squadron/providers/codex/provider.py`, ensure `ProviderError` is imported (it should already be via `squadron.providers.errors`)
- [ ] **T5.2** In `create_agent()`, after the `OAuthFileStrategy` check, add:
  ```python
  from squadron.providers.codex.agent import resolve_codex_binary
  if resolve_codex_binary() is None:
      raise ProviderError(
          "Codex CLI binary not found on PATH.\n"
          "  npm i -g @openai/codex"
      )
  ```

**Test T5:**
- [ ] **T5.3** Add a new test to `tests/providers/codex/test_provider.py` (or nearest codex test file) that:
  - Mocks `squadron.providers.codex.provider.resolve_codex_binary` to return `None`
  - Mocks `OAuthFileStrategy.is_valid` to return `True` (so auth check passes)
  - Calls `await provider.create_agent(config)` and asserts `ProviderError` is raised
  - Asserts the error message contains `npm i -g @openai/codex`
- [ ] **T5.4** Run `pytest tests/providers/ -v -k codex` — all tests pass (existing + new)
- [ ] **T5.5** Run `pyright src/squadron/providers/codex/provider.py` — zero errors

---

### T6 — Full Test Suite and Static Analysis

- [ ] **T6.1** Run `ruff format src/ tests/` — no changes (or apply and re-verify)
- [ ] **T6.2** Run `ruff check src/ tests/` — zero errors
- [ ] **T6.3** Run `pyright src/` — zero errors
- [ ] **T6.4** Run `pytest` — all tests pass (baseline: 1904 passing, 2 skipped)

---

### T7 — Clean-Venv Verification

- [ ] **T7.1** Create a clean venv: `python -m venv /tmp/sq-907-venv`
- [ ] **T7.2** Install base only: `/tmp/sq-907-venv/bin/pip install -e .`
- [ ] **T7.3** Confirm fastapi/uvicorn absent: `pip show fastapi` → "not found"; same for uvicorn
- [ ] **T7.4** `sq doctor` runs without error
- [ ] **T7.4a** `sq run --help` exits 0 (no ImportError from server modules)
- [ ] **T7.4b** `sq review --help` exits 0 (no ImportError from server modules)
- [ ] **T7.5** `sq serve` (start mode) → prints actionable error, exits 1
- [ ] **T7.6** `sq serve --status` → "Daemon is not running." (no ImportError)
- [ ] **T7.6a** `sq serve --stop` → "Daemon is not running." error, no ImportError (verifies `--stop` path reads only PID file)
- [ ] **T7.7** Install serve extra: `/tmp/sq-907-venv/bin/pip install -e ".[serve]"`
- [ ] **T7.8** `sq serve --status` → "Daemon is not running." (daemon not started)
- [ ] **T7.9** Clean up: `rm -rf /tmp/sq-907-venv`

---

### T8 — Commits

Two commits: one for the pure refactor (no behavior change), one for the guards and dependency restructure.

- [ ] **T8.1** Run `ruff format src/ tests/` before first commit
- [ ] **T8.2** Stage refactor files: `src/squadron/server/pid.py`, `src/squadron/server/daemon.py`, `tests/server/test_daemon.py`
- [ ] **T8.3** Commit: `refactor: extract PID helpers from daemon.py into server/pid.py`
- [ ] **T8.4** Stage remaining files: `pyproject.toml`, `.github/workflows/ci.yml`, `src/squadron/cli/commands/serve.py`, `src/squadron/providers/codex/provider.py`, and any new test files
- [ ] **T8.5** Commit: `feat: move fastapi/uvicorn to [serve] extra, add serve and codex guards`
