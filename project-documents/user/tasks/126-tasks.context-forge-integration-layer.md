---
slice: context-forge-integration-layer
project: squadron
lld: user/slices/126-slice.context-forge-integration-layer.md
dependencies: [cli-foundation]
projectState: Slices 100-121 complete. CF calls via subprocess in review.py (_run_cf, _resolve_slice_number). CF command surface changed (cf slice list → cf list slices). Markdown command files reference old CF commands.
dateCreated: 20260324
dateUpdated: 20260324
status: complete
---

## Context Summary

- Centralizing CF CLI interactions behind `ContextForgeClient` in `src/squadron/integrations/context_forge.py`
- Current CF calls: `_run_cf()` and `_resolve_slice_number()` in `src/squadron/cli/commands/review.py`
- CF command surface changed: `cf slice list --json` → `cf list slices --json`, `cf tasks list --json` → `cf list tasks --json`
- Typed dataclasses replace raw dict parsing: `SliceEntry`, `TaskEntry`, `ProjectInfo`
- Custom exceptions (`ContextForgeNotAvailable`, `ContextForgeError`) replace inline `typer.Exit`
- Markdown command files (`commands/sq/*.md`) need CF command name updates
- Key files: `src/squadron/cli/commands/review.py`, `commands/sq/run-slice.md`, `commands/sq/review-slice.md`, `commands/sq/review-tasks.md`, `commands/sq/review-code.md`

---

## Tasks

### T1: Create integrations package and dataclasses

- [x] Create `src/squadron/integrations/__init__.py` (empty or minimal)
- [x] Create `src/squadron/integrations/context_forge.py`
- [x] Define exception classes:
  - [x] `ContextForgeNotAvailable(Exception)` — raised when `cf` not on PATH
  - [x] `ContextForgeError(Exception)` — raised on CF command failure (includes stderr)
- [x] Define `SliceEntry` dataclass:
  - [x] Fields: `index: int`, `name: str`, `design_file: str | None`, `status: str`
- [x] Define `TaskEntry` dataclass:
  - [x] Fields: `index: int`, `files: list[str]`
- [x] Define `ProjectInfo` dataclass:
  - [x] Fields: `arch_file: str`, `slice_plan: str`, `phase: str`, `slice: str`
- [x] `uv run pyright` and `uv run ruff check` pass

### T2: Implement `ContextForgeClient` core and `is_available()`

- [x] In `context_forge.py`, add `ContextForgeClient` class
- [x] Add private `_run(self, args: list[str]) -> str` method:
  - [x] Runs `subprocess.run(["cf", *args], capture_output=True, text=True, check=True)`
  - [x] `FileNotFoundError` → raise `ContextForgeNotAvailable`
  - [x] `CalledProcessError` → raise `ContextForgeError` with stderr message
  - [x] Returns stdout
- [x] Add private `_run_json(self, args: list[str]) -> Any` method:
  - [x] Calls `_run(args)`, parses stdout as JSON
  - [x] `json.JSONDecodeError` → raise `ContextForgeError` with context
- [x] Add `is_available(self) -> bool` method:
  - [x] Runs `cf --version` via `_run()`
  - [x] Returns `True` on success, `False` on `ContextForgeNotAvailable`
- [x] `uv run pyright` and `uv run ruff check` pass

### T3: Tests for client core and `is_available()`

- [x] Create `tests/integrations/test_context_forge.py`
- [x] `test_is_available_true`: mock subprocess success, verify returns `True`
- [x] `test_is_available_false`: mock `FileNotFoundError`, verify returns `False`
- [x] `test_run_cf_not_installed`: mock `FileNotFoundError`, verify raises `ContextForgeNotAvailable`
- [x] `test_run_cf_command_error`: mock `CalledProcessError`, verify raises `ContextForgeError` with stderr
- [x] `test_run_json_valid`: mock valid JSON stdout, verify parsed correctly
- [x] `test_run_json_invalid`: mock non-JSON stdout, verify raises `ContextForgeError`
- [x] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T4: Implement `list_slices()` method

- [x] Add `list_slices(self) -> list[SliceEntry]` to `ContextForgeClient`
  - [x] Calls `_run_json(["list", "slices", "--json"])` (new CF command surface)
  - [x] Parses response: extract `entries` list, map each to `SliceEntry`
  - [x] Handle missing optional fields (`design_file` may be `None`)
- [x] `uv run pyright` and `uv run ruff check` pass

### T5: Tests for `list_slices()`

- [x] `test_list_slices_parses_entries`: mock CF JSON with multiple entries, verify `SliceEntry` fields
- [x] `test_list_slices_missing_design_file`: mock entry without `designFile`, verify `design_file` is `None`
- [x] `test_list_slices_empty`: mock empty entries list, verify returns `[]`
- [x] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T6: Implement `list_tasks()` method

- [x] Add `list_tasks(self) -> list[TaskEntry]` to `ContextForgeClient`
  - [x] Calls `_run_json(["list", "tasks", "--json"])` (new CF command surface)
  - [x] Parses response: map each entry to `TaskEntry`
  - [x] Handle missing `files` field (default to empty list)
- [x] `uv run pyright` and `uv run ruff check` pass

### T7: Tests for `list_tasks()`

- [x] `test_list_tasks_parses_entries`: mock CF JSON, verify `TaskEntry` fields
- [x] `test_list_tasks_no_files`: mock entry without `files` key, verify `files` is `[]`
- [x] `test_list_tasks_empty`: mock empty response, verify returns `[]`
- [x] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T8: Implement `get_project()` method

- [x] Add `get_project(self) -> ProjectInfo` to `ContextForgeClient`
  - [x] Calls `_run_json(["get", "--json"])`
  - [x] Extracts `fileArch`, `fileSlicePlan`, `phase`, `slice` fields
  - [x] Resolves `arch_file` path: prepend `project-documents/user/architecture/` and `.md` suffix if raw name provided
- [x] `uv run pyright` and `uv run ruff check` pass

### T9: Tests for `get_project()`

- [x] `test_get_project_parses_fields`: mock CF JSON, verify all `ProjectInfo` fields
- [x] `test_get_project_arch_path_resolution`: verify `fileArch` value gets resolved to full path
- [x] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`
- [x] Commit: `feat: add ContextForgeClient with typed methods and tests`

### T10: Migrate `review.py` to use `ContextForgeClient`

- [x] Import `ContextForgeClient` and exceptions in `review.py`
- [x] Replace `_resolve_slice_number()` implementation:
  - [x] Create `ContextForgeClient` instance
  - [x] Call `client.list_slices()` instead of `_run_cf(["slice", "list", "--json"])`
  - [x] Call `client.list_tasks()` instead of `_run_cf(["tasks", "list", "--json"])`
  - [x] Call `client.get_project()` instead of `_run_cf(["get", "--json"])`
  - [x] Map `SliceEntry`/`TaskEntry`/`ProjectInfo` fields to existing `SliceInfo` TypedDict
- [x] Wrap client calls in try/except:
  - [x] `ContextForgeNotAvailable` → `rprint` error + `typer.Exit(code=1)`
  - [x] `ContextForgeError` → `rprint` error + `typer.Exit(code=1)`
- [x] Remove `_run_cf()` function from `review.py`
- [x] Remove `subprocess` import from `review.py` if no longer used
- [x] `uv run pyright` and `uv run ruff check` pass

### T11: Tests for migrated review.py

- [x] Verify existing tests in `tests/review/test_cli_review.py` still pass
- [x] Add `test_review_slice_cf_not_available`: mock `ContextForgeNotAvailable`, verify error message and exit code
- [x] Add `test_review_slice_cf_error`: mock `ContextForgeError`, verify error message and exit code
- [x] Verify no direct `subprocess` calls to `cf` remain in `review.py`:
  - [x] `grep -n "subprocess.*cf\|_run_cf" src/squadron/cli/commands/review.py` returns no matches
- [x] All tests pass: `uv run pytest tests/cli/test_cli_review.py tests/review/ -v`
- [x] Commit: `refactor: migrate review.py to ContextForgeClient`

### T12: Update markdown command files

- [x] Update `commands/sq/run-slice.md`:
  - [x] `cf slice list --json` → `cf list slices --json`
  - [x] `cf task list --json` → `cf list tasks --json`
  - [x] Verify all other CF commands are still current (`cf set`, `cf build`, `cf get`, `cf prompt get`)
- [x] Update `commands/sq/review-slice.md`:
  - [x] `cf slice list --json` → `cf list slices --json`
- [x] Update `commands/sq/review-tasks.md`:
  - [x] `cf slice list --json` → `cf list slices --json`
  - [x] `cf task list --json` → `cf list tasks --json`
- [x] Update `commands/sq/review-code.md`:
  - [x] `cf slice list --json` → `cf list slices --json`
- [x] Commit: `docs: update CF command references to new command surface`

### T13: Full validation pass

- [x] Run full test suite: `uv run pytest`
  - [x] All tests pass
- [x] `uv run pyright` — 0 errors
- [x] `uv run ruff check` — clean
- [x] `uv run ruff format --check` — clean
- [x] Manual verification: `sq review slice 122 --model minimax -v` resolves via client
- [x] Manual verification: `sq review tasks 121 --model minimax -v` resolves via client
- [x] Verify grep: `grep -rn "subprocess.*cf\|\"cf\"" src/squadron/cli/commands/review.py` — no matches
- [x] Commit any remaining changes

### T14: Post-implementation — update slice status

- [x] Mark slice 126 as complete in `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- [x] Mark slice 126 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
  - [x] Change `23. [ ] **(126) Context Forge Integration Layer**` → `23. [x] **(126) Context Forge Integration Layer**`
- [x] Update DEVLOG with completion entry
- [x] Commit: `docs: mark slice 126 (Context Forge Integration Layer) complete`
