---
slice: context-forge-integration-layer
project: squadron
lld: user/slices/126-slice.context-forge-integration-layer.md
dependencies: [cli-foundation]
projectState: Slices 100-121 complete. CF calls via subprocess in review.py (_run_cf, _resolve_slice_number). CF command surface changed (cf slice list → cf list slices). Markdown command files reference old CF commands.
dateCreated: 20260324
dateUpdated: 20260324
status: not_started
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

- [ ] Create `src/squadron/integrations/__init__.py` (empty or minimal)
- [ ] Create `src/squadron/integrations/context_forge.py`
- [ ] Define exception classes:
  - [ ] `ContextForgeNotAvailable(Exception)` — raised when `cf` not on PATH
  - [ ] `ContextForgeError(Exception)` — raised on CF command failure (includes stderr)
- [ ] Define `SliceEntry` dataclass:
  - [ ] Fields: `index: int`, `name: str`, `design_file: str | None`, `status: str`
- [ ] Define `TaskEntry` dataclass:
  - [ ] Fields: `index: int`, `files: list[str]`
- [ ] Define `ProjectInfo` dataclass:
  - [ ] Fields: `arch_file: str`, `slice_plan: str`, `phase: str`, `slice: str`
- [ ] `uv run pyright` and `uv run ruff check` pass

### T2: Implement `ContextForgeClient` core and `is_available()`

- [ ] In `context_forge.py`, add `ContextForgeClient` class
- [ ] Add private `_run(self, args: list[str]) -> str` method:
  - [ ] Runs `subprocess.run(["cf", *args], capture_output=True, text=True, check=True)`
  - [ ] `FileNotFoundError` → raise `ContextForgeNotAvailable`
  - [ ] `CalledProcessError` → raise `ContextForgeError` with stderr message
  - [ ] Returns stdout
- [ ] Add private `_run_json(self, args: list[str]) -> Any` method:
  - [ ] Calls `_run(args)`, parses stdout as JSON
  - [ ] `json.JSONDecodeError` → raise `ContextForgeError` with context
- [ ] Add `is_available(self) -> bool` method:
  - [ ] Runs `cf --version` via `_run()`
  - [ ] Returns `True` on success, `False` on `ContextForgeNotAvailable`
- [ ] `uv run pyright` and `uv run ruff check` pass

### T3: Tests for client core and `is_available()`

- [ ] Create `tests/integrations/test_context_forge.py`
- [ ] `test_is_available_true`: mock subprocess success, verify returns `True`
- [ ] `test_is_available_false`: mock `FileNotFoundError`, verify returns `False`
- [ ] `test_run_cf_not_installed`: mock `FileNotFoundError`, verify raises `ContextForgeNotAvailable`
- [ ] `test_run_cf_command_error`: mock `CalledProcessError`, verify raises `ContextForgeError` with stderr
- [ ] `test_run_json_valid`: mock valid JSON stdout, verify parsed correctly
- [ ] `test_run_json_invalid`: mock non-JSON stdout, verify raises `ContextForgeError`
- [ ] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T4: Implement `list_slices()` method

- [ ] Add `list_slices(self) -> list[SliceEntry]` to `ContextForgeClient`
  - [ ] Calls `_run_json(["list", "slices", "--json"])` (new CF command surface)
  - [ ] Parses response: extract `entries` list, map each to `SliceEntry`
  - [ ] Handle missing optional fields (`design_file` may be `None`)
- [ ] `uv run pyright` and `uv run ruff check` pass

### T5: Tests for `list_slices()`

- [ ] `test_list_slices_parses_entries`: mock CF JSON with multiple entries, verify `SliceEntry` fields
- [ ] `test_list_slices_missing_design_file`: mock entry without `designFile`, verify `design_file` is `None`
- [ ] `test_list_slices_empty`: mock empty entries list, verify returns `[]`
- [ ] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T6: Implement `list_tasks()` method

- [ ] Add `list_tasks(self) -> list[TaskEntry]` to `ContextForgeClient`
  - [ ] Calls `_run_json(["list", "tasks", "--json"])` (new CF command surface)
  - [ ] Parses response: map each entry to `TaskEntry`
  - [ ] Handle missing `files` field (default to empty list)
- [ ] `uv run pyright` and `uv run ruff check` pass

### T7: Tests for `list_tasks()`

- [ ] `test_list_tasks_parses_entries`: mock CF JSON, verify `TaskEntry` fields
- [ ] `test_list_tasks_no_files`: mock entry without `files` key, verify `files` is `[]`
- [ ] `test_list_tasks_empty`: mock empty response, verify returns `[]`
- [ ] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`

### T8: Implement `get_project()` method

- [ ] Add `get_project(self) -> ProjectInfo` to `ContextForgeClient`
  - [ ] Calls `_run_json(["get", "--json"])`
  - [ ] Extracts `fileArch`, `fileSlicePlan`, `phase`, `slice` fields
  - [ ] Resolves `arch_file` path: prepend `project-documents/user/architecture/` and `.md` suffix if raw name provided
- [ ] `uv run pyright` and `uv run ruff check` pass

### T9: Tests for `get_project()`

- [ ] `test_get_project_parses_fields`: mock CF JSON, verify all `ProjectInfo` fields
- [ ] `test_get_project_arch_path_resolution`: verify `fileArch` value gets resolved to full path
- [ ] All tests pass: `uv run pytest tests/integrations/test_context_forge.py -v`
- [ ] Commit: `feat: add ContextForgeClient with typed methods and tests`

### T10: Migrate `review.py` to use `ContextForgeClient`

- [ ] Import `ContextForgeClient` and exceptions in `review.py`
- [ ] Replace `_resolve_slice_number()` implementation:
  - [ ] Create `ContextForgeClient` instance
  - [ ] Call `client.list_slices()` instead of `_run_cf(["slice", "list", "--json"])`
  - [ ] Call `client.list_tasks()` instead of `_run_cf(["tasks", "list", "--json"])`
  - [ ] Call `client.get_project()` instead of `_run_cf(["get", "--json"])`
  - [ ] Map `SliceEntry`/`TaskEntry`/`ProjectInfo` fields to existing `SliceInfo` TypedDict
- [ ] Wrap client calls in try/except:
  - [ ] `ContextForgeNotAvailable` → `rprint` error + `typer.Exit(code=1)`
  - [ ] `ContextForgeError` → `rprint` error + `typer.Exit(code=1)`
- [ ] Remove `_run_cf()` function from `review.py`
- [ ] Remove `subprocess` import from `review.py` if no longer used
- [ ] `uv run pyright` and `uv run ruff check` pass

### T11: Tests for migrated review.py

- [ ] Verify existing tests in `tests/review/test_cli_review.py` still pass
- [ ] Add `test_review_slice_cf_not_available`: mock `ContextForgeNotAvailable`, verify error message and exit code
- [ ] Add `test_review_slice_cf_error`: mock `ContextForgeError`, verify error message and exit code
- [ ] Verify no direct `subprocess` calls to `cf` remain in `review.py`:
  - [ ] `grep -n "subprocess.*cf\|_run_cf" src/squadron/cli/commands/review.py` returns no matches
- [ ] All tests pass: `uv run pytest tests/cli/test_cli_review.py tests/review/ -v`
- [ ] Commit: `refactor: migrate review.py to ContextForgeClient`

### T12: Update markdown command files

- [ ] Update `commands/sq/run-slice.md`:
  - [ ] `cf slice list --json` → `cf list slices --json`
  - [ ] `cf task list --json` → `cf list tasks --json`
  - [ ] Verify all other CF commands are still current (`cf set`, `cf build`, `cf get`, `cf prompt get`)
- [ ] Update `commands/sq/review-slice.md`:
  - [ ] `cf slice list --json` → `cf list slices --json`
- [ ] Update `commands/sq/review-tasks.md`:
  - [ ] `cf slice list --json` → `cf list slices --json`
  - [ ] `cf task list --json` → `cf list tasks --json`
- [ ] Update `commands/sq/review-code.md`:
  - [ ] `cf slice list --json` → `cf list slices --json`
- [ ] Commit: `docs: update CF command references to new command surface`

### T13: Full validation pass

- [ ] Run full test suite: `uv run pytest`
  - [ ] All tests pass
- [ ] `uv run pyright` — 0 errors
- [ ] `uv run ruff check` — clean
- [ ] `uv run ruff format --check` — clean
- [ ] Manual verification: `sq review slice 122 --model minimax -v` resolves via client
- [ ] Manual verification: `sq review tasks 121 --model minimax -v` resolves via client
- [ ] Verify grep: `grep -rn "subprocess.*cf\|\"cf\"" src/squadron/cli/commands/review.py` — no matches
- [ ] Commit any remaining changes

### T14: Post-implementation — update slice status

- [ ] Mark slice 126 as complete in `project-documents/user/slices/126-slice.context-forge-integration-layer.md`
- [ ] Mark slice 126 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
  - [ ] Change `23. [ ] **(126) Context Forge Integration Layer**` → `23. [x] **(126) Context Forge Integration Layer**`
- [ ] Update DEVLOG with completion entry
- [ ] Commit: `docs: mark slice 126 (Context Forge Integration Layer) complete`
