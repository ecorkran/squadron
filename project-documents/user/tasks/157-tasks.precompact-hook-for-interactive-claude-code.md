---
docType: slice-tasks
slice: precompact-hook-for-interactive-claude-code
project: squadron
lld: 157-slice.precompact-hook-for-interactive-claude-code.md
dependencies: [141-configuration-externalization]
dateCreated: 20260407
dateUpdated: 20260407
status: complete
---

# Tasks: PreCompact Hook for Interactive Claude Code

## Context Summary

- Ships a `.claude/settings.json` `PreCompact` hook for interactive Claude Code sessions (VS Code extension, CLI Claude Code).
- Independent of SDK mode / Agent SDK `ClaudeAgentOptions.hooks`. Slice 158 handles SDK-mode compaction separately; the two share only the existing compaction template loader.
- Core pieces:
  1. Two new config keys: `compact.template` (default `minimal`), `compact.instructions` (literal override; wins when both set).
  2. Hidden `sq _precompact-hook` Typer subcommand that reads config, loads the YAML template (or the literal), renders `{slice}`, `{phase}`, `{project}` via the existing `_LenientDict` helper, and emits the `PreCompact` hook JSON payload on stdout. Never errors; always exits 0.
  3. Extension of `sq install-commands` / `sq uninstall-commands` to write/remove a squadron-managed `PreCompact` entry in project-local `./.claude/settings.json`, non-destructively merging with any third-party hooks (identified via a `_managed_by: "squadron"` marker).
- Params sourced from `ContextForgeClient.get_project()` — CF unavailability is silently absorbed; the `_LenientDict` leaves placeholders intact.
- Reuses: `load_compaction_template` and `_LenientDict` from `src/squadron/pipeline/actions/compact.py`. Small extraction to make `_LenientDict` + format-vars rendering importable without cross-package coupling.

**Files to change / add:**
- `src/squadron/config/keys.py` — register two new keys
- `src/squadron/pipeline/compact_render.py` (new) — shared `_LenientDict` + `render_with_params` helper
- `src/squadron/pipeline/actions/compact.py` — import from the new module
- `src/squadron/cli/commands/precompact_hook.py` (new) — hidden subcommand
- `src/squadron/cli/commands/install_settings.py` (new) — settings.json merge helpers
- `src/squadron/cli/commands/install.py` — call settings writer/remover; add `--hook-target`
- `src/squadron/cli/main.py` (or wherever the Typer app is assembled) — register hidden subcommand
- `README.md` — short "Interactive `/compact`" section
- Tests mirroring each implementation module

---

## Tasks

### T1 — Register `compact.template` and `compact.instructions` config keys

- [x] Open `src/squadron/config/keys.py`
- [x] Add `compact.template` entry: `type_=str`, `default="minimal"`, description per slice design Architecture § Config Keys
- [x] Add `compact.instructions` entry: `type_=str`, `default=None`, description per slice design
- [x] Both keys go in the existing `CONFIG_KEYS` dict; no manager-layer changes
- [x] Verify no existing key collides with the dotted names (`compact.template`, `compact.instructions`)

**Test T1** — `tests/config/test_keys.py`

- [x] Add test: `CONFIG_KEYS["compact.template"]` exists with default `"minimal"`
- [x] Add test: `CONFIG_KEYS["compact.instructions"]` exists with default `None`
- [x] Add test: `get_default("compact.template") == "minimal"`
- [x] Add test: `get_default("compact.instructions") is None`
- [x] If an existing `test_config_manager` test sets/gets arbitrary keys, add a parametrized case for the two new keys

**Commit:** `feat: add compact.template and compact.instructions config keys`

---

### T2 — Extract `_LenientDict` + render helper into a shared module

- [x] Create `src/squadron/pipeline/compact_render.py`
- [x] Move `_LenientDict` class from `src/squadron/pipeline/actions/compact.py` into the new module, rename to public `LenientDict` (keep the docstring)
- [x] Add a small public helper: `render_with_params(instructions: str, params: dict[str, object]) -> str` that wraps `instructions.format_map(LenientDict(params))`
- [x] In `src/squadron/pipeline/actions/compact.py`, import `LenientDict` and `render_with_params` from the new module
- [x] Update `render_instructions` in `actions/compact.py` to use `render_with_params` (or keep its richer signature and delegate to the helper internally — whichever changes fewer lines)
- [x] No behavior change expected in the compact action

**Test T2** — `tests/pipeline/test_compact_render.py`

- [x] Test `LenientDict` returns `"{missing}"` for a missing key (matching current behavior)
- [x] Test `render_with_params("Hello {name}", {"name": "world"}) == "Hello world"`
- [x] Test `render_with_params("Slice {slice}", {}) == "Slice {slice}"` (placeholder preserved)
- [x] Verify existing `tests/pipeline/actions/test_compact_action.py` still passes without changes

**Commit:** `refactor: extract LenientDict and render_with_params to compact_render module`

---

### T3 — Implement `_resolve_instructions` helper in the hook module

- [x] Create `src/squadron/cli/commands/precompact_hook.py`
- [x] Add `from __future__ import annotations`
- [x] Implement `_resolve_instructions(cwd: str) -> str` with this precedence:
  1. `get_config("compact.instructions", cwd=cwd)` — if truthy non-empty string, return it verbatim (param rendering happens later)
  2. Else `template_name = get_config("compact.template", cwd=cwd)` (default `"minimal"`)
  3. Call `load_compaction_template(template_name)` and return `template.instructions`
- [x] Wrap template loading in `try/except (FileNotFoundError, ValueError)` — on failure return empty string (hook must never break `/compact`)
- [x] Do **not** raise on `KeyError` from `get_config` — a missing key means "use default", which for `compact.template` gives `"minimal"`

**Test T3** — `tests/cli/commands/test_precompact_hook.py` (new)

- [x] Test: with `compact.instructions` set to `"literal text"`, `_resolve_instructions` returns `"literal text"`
- [x] Test: with only `compact.template` set to `"minimal"`, returns the contents of `minimal.yaml`'s `instructions` field
- [x] Test: with both set, returns the literal (literal wins)
- [x] Test: with `compact.template` set to a nonexistent template name, returns `""` (does not raise)
- [x] Use a temp config directory via a fixture; do not mutate the real user config

**Commit:** `feat: add _resolve_instructions helper for PreCompact hook`

---

### T4 — Implement `_gather_params` helper in the hook module

- [x] In `src/squadron/cli/commands/precompact_hook.py`, implement `_gather_params(cwd: str) -> dict[str, str]`
- [x] Instantiate `ContextForgeClient(cwd=cwd)` and call `get_project()` inside a `try/except`
- [x] On success, return `{"slice": info.slice or "", "phase": info.phase or "", "project": Path(cwd).resolve().name}`
- [x] On any of `ContextForgeError`, `FileNotFoundError`, `OSError` — return `{}`
- [x] Do not catch bare `Exception` — keep exception list explicit per project rules

**Test T4** — extend `tests/cli/commands/test_precompact_hook.py`

- [x] Test: when `ContextForgeClient.get_project` returns `ProjectInfo(slice="157", phase="5", ...)`, `_gather_params` returns dict with those values and `project` set to the cwd folder name
- [x] Test: when `ContextForgeClient.get_project` raises `ContextForgeError`, `_gather_params` returns `{}`
- [x] Test: when `ContextForgeClient(cwd=...)` itself raises `FileNotFoundError` (CF not installed), `_gather_params` returns `{}`
- [x] Mock the CF client; do not shell out to a real `cf`

**Commit:** `feat: add _gather_params helper for PreCompact hook`

---

### T5 — Implement the hook Typer command

- [x] In `src/squadron/cli/commands/precompact_hook.py`, implement the top-level function:
  ```python
  def precompact_hook(cwd: str = typer.Option(".", "--cwd", hidden=True)) -> None: ...
  ```
- [x] Body:
  1. Call `_resolve_instructions(cwd)` (wrap in try/except to swallow anything unexpected → empty string)
  2. Call `_gather_params(cwd)` (already safe)
  3. Call `render_with_params(instructions, params)` from `squadron.pipeline.compact_render`
  4. Build payload dict: `{"hookSpecificOutput": {"hookEventName": "PreCompact", "additionalContext": rendered}}`
  5. `print(json.dumps(payload))`
  6. Return normally (exit 0). Never `raise typer.Exit` with a non-zero code.
- [x] The outer try/except should be tight: one `try` wrapping steps 1–3, with `except Exception` that sets `rendered = ""` and still prints a valid payload. This is the one place in squadron where a bare `Exception` catch is justified, because the hook's contract is "never break `/compact`". Include a comment explaining why.

**Test T5** — extend `tests/cli/commands/test_precompact_hook.py`

- [x] Use Typer's `CliRunner` (or direct function invocation) to call `precompact_hook`
- [x] Test: with a mocked `_resolve_instructions` returning `"Keep slice {slice}."` and mocked `_gather_params` returning `{"slice": "157"}`, stdout is valid JSON with `additionalContext == "Keep slice 157."`
- [x] Test: with `_resolve_instructions` raising `RuntimeError` (simulated unexpected failure), stdout is still valid JSON with `additionalContext == ""` and exit code is 0
- [x] Test: JSON output is a single line (one `print(json.dumps(...))` call)
- [x] Test: `hookEventName` key equals `"PreCompact"`

**Commit:** `feat: implement _precompact-hook Typer command`

---

### T6 — Register the hidden subcommand on the `sq` Typer app

- [x] Locate the top-level `sq` Typer app assembly (likely `src/squadron/cli/main.py` — confirm by searching for `typer.Typer(` at module level and `app.command(`)
- [x] Import the new `precompact_hook` function
- [x] Register it with:
  ```python
  app.command(name="_precompact-hook", hidden=True)(precompact_hook)
  ```
- [x] Verify the underscore-prefixed name is acceptable to Typer (it is — names are passed through to Click)

**Test T6** — `tests/cli/test_main.py` (or wherever CLI wiring tests live)

- [x] Test: running `sq --help` via `CliRunner` does not include `_precompact-hook` in the output (Typer should hide it)
- [x] Test: running `sq _precompact-hook --help` succeeds (Typer still lets hidden commands be invoked directly)
- [x] Test: running `sq _precompact-hook` from a temp directory with no config succeeds with exit code 0 and valid JSON on stdout

**Commit:** `feat: register hidden _precompact-hook subcommand on sq app`

---

### T7 — Implement `install_settings.py` settings.json helpers

- [x] Create `src/squadron/cli/commands/install_settings.py`
- [x] Add `from __future__ import annotations`
- [x] Implement `_settings_json_path(target_root: Path) -> Path` returning `target_root / ".claude" / "settings.json"`
- [x] Implement `_load_settings(path: Path) -> dict[str, object]`:
  - If file does not exist, return `{}`
  - Else read and `json.loads`; on `json.JSONDecodeError`, raise a descriptive `RuntimeError` (caller surfaces as install failure — we do NOT silently overwrite corrupt files)
- [x] Implement `_save_settings(path: Path, data: dict[str, object]) -> None`:
  - Ensure parent dir exists (`path.parent.mkdir(parents=True, exist_ok=True)`)
  - Write with `json.dumps(data, indent=2)` + trailing newline

**Test T7** — `tests/cli/commands/test_install_settings.py` (new)

- [x] Test: `_settings_json_path(tmp_path) == tmp_path / ".claude" / "settings.json"`
- [x] Test: `_load_settings` on nonexistent file returns `{}`
- [x] Test: `_load_settings` on valid JSON returns the parsed dict
- [x] Test: `_load_settings` on corrupt JSON raises `RuntimeError` (not `JSONDecodeError`)
- [x] Test: `_save_settings` creates parent directories and writes indented JSON

**Commit:** `feat: add settings.json load/save helpers for hook install`

---

### T8 — Implement `_write_precompact_hook` merge logic

- [x] In `install_settings.py`, implement `_write_precompact_hook(settings_path: Path) -> None`
- [x] Behavior:
  1. Call `_load_settings(settings_path)` → `data`
  2. Ensure `data.setdefault("hooks", {}).setdefault("PreCompact", [])` exists
  3. Build the squadron entry:
     ```python
     sq_entry = {
         "matcher": "",
         "hooks": [
             {
                 "type": "command",
                 "command": "sq _precompact-hook",
                 "_managed_by": "squadron",
             }
         ],
     }
     ```
  4. Walk `data["hooks"]["PreCompact"]`: if any entry has a nested `hooks[*]` where `_managed_by == "squadron"`, replace that entry in place (preserve list position). Else append `sq_entry`.
  5. Call `_save_settings(settings_path, data)`
- [x] Add a helper `_is_squadron_entry(entry: dict) -> bool` that checks for the marker safely (handles missing keys, non-list shapes)

**Test T8** — extend `tests/cli/commands/test_install_settings.py`

- [x] Test: write to nonexistent settings.json creates the file with one squadron entry under `hooks.PreCompact`
- [x] Test: write to settings.json with no `hooks` key adds `hooks.PreCompact` without touching other top-level keys
- [x] Test: write to settings.json with an existing non-squadron `PreCompact` entry appends (does not replace) — result has 2 entries, non-squadron one unchanged
- [x] Test: write to settings.json with an existing squadron `PreCompact` entry replaces it in place (result has 1 entry, at the same list position)
- [x] Test: write preserves unrelated top-level keys in settings.json (e.g. `"theme": "dark"` survives)
- [x] Test: write preserves other hook event names (e.g. `hooks.PostToolUse` survives)
- [x] Test: running `_write_precompact_hook` twice in a row is idempotent (final file identical after second call)

**Commit:** `feat: implement _write_precompact_hook with non-destructive merge`

---

### T9 — Implement `_remove_precompact_hook` logic

- [x] In `install_settings.py`, implement `_remove_precompact_hook(settings_path: Path) -> bool`
- [x] Returns `True` if an entry was removed, `False` otherwise
- [x] Behavior:
  1. If settings file does not exist → return `False`
  2. Load settings (surface corrupt-JSON error like `_write_precompact_hook` does)
  3. If no `hooks.PreCompact` → return `False`
  4. Filter out any entry where `_is_squadron_entry(entry)` is true
  5. If `hooks.PreCompact` ends up empty, delete the key; if `hooks` ends up empty, delete it too (tidy cleanup)
  6. Save back
  7. Return whether anything was actually removed

**Test T9** — extend `tests/cli/commands/test_install_settings.py`

- [x] Test: remove on nonexistent settings.json returns `False`, does not create the file
- [x] Test: remove on settings.json with no squadron entry returns `False`, file unchanged
- [x] Test: remove on settings.json with only a squadron entry empties `hooks.PreCompact` (key deleted), returns `True`
- [x] Test: remove on settings.json with squadron entry + third-party entry keeps the third-party one, returns `True`
- [x] Test: remove preserves unrelated top-level keys
- [x] Test: after remove, if `hooks` becomes empty, the `hooks` key is removed too

**Commit:** `feat: implement _remove_precompact_hook preserving third-party hooks`

---

### T10 — Wire hook writer into `sq install-commands`

- [x] Open `src/squadron/cli/commands/install.py`
- [x] Add a new `--hook-target` Typer option to `install_commands`:
  ```python
  hook_target: str = typer.Option(
      "./.claude/settings.json",
      "--hook-target",
      help="Target settings.json for the PreCompact hook entry",
  )
  ```
- [x] At the end of `install_commands` (after the slash-command copy loop, before the summary `rprint`s), call `_write_precompact_hook(Path(hook_target).expanduser())`
- [x] On `RuntimeError` from corrupt settings.json, print a red error via `rprint` and `raise typer.Exit(code=1)`
- [x] Add a line to the success rprint: `[green]Installed PreCompact hook to <path>[/green]`
- [x] Keep the existing slash-command install behavior unchanged

**Test T10** — `tests/cli/commands/test_install_commands.py` (extend or create)

- [x] Test: `install_commands(--target=<tmp>, --hook-target=<tmp>/settings.json)` creates settings.json with the squadron entry
- [x] Test: running install twice is idempotent (settings.json has exactly one squadron entry)
- [x] Test: if `--hook-target` points to a file with corrupt JSON, install exits non-zero and leaves the file unchanged
- [x] Test: existing slash-command copy behavior still works (at least one `.md` file installed under `--target/sq/`)

**Commit:** `feat: install PreCompact hook entry during sq install-commands`

---

### T11 — Wire hook remover into `sq uninstall-commands`

- [x] In `src/squadron/cli/commands/install.py`, add matching `--hook-target` option to `uninstall_commands` (default `./.claude/settings.json`)
- [x] Before (or after) the slash-command removal, call `_remove_precompact_hook(Path(hook_target).expanduser())`
- [x] Capture the return value; if `True`, add `[green]Removed PreCompact hook from <path>[/green]` to output; if `False`, stay silent (no noise when there's nothing to remove)
- [x] Preserve the existing "nothing to remove" messaging for slash commands

**Test T11** — extend `tests/cli/commands/test_install_commands.py`

- [x] Test: uninstall removes the squadron PreCompact entry from a settings.json previously created by install
- [x] Test: uninstall on a settings.json with a third-party PreCompact entry leaves that entry intact
- [x] Test: uninstall when settings.json does not exist is a no-op success (does not error, does not create the file)
- [x] Test: running install → uninstall → verify settings.json is either absent (if nothing else was in it) or has `hooks` / `hooks.PreCompact` cleanly removed

**Commit:** `feat: remove PreCompact hook entry during sq uninstall-commands`

---

### T12 — README update

- [x] Add a short "Interactive `/compact` for Claude Code" section to `README.md` (after the existing install-commands section)
- [x] Cover: what the hook does, `sq install-commands` installs it automatically, how to switch templates (`sq config set compact.template <name>`), how to use literal instructions (`sq config set compact.instructions "..."`), and the `--project` flag
- [x] Keep it under ~25 lines — terse, example-led

**Test T12** — no automated test; verify by reading

- [x] Re-read the new section and confirm examples are correct

**Commit:** `docs: document PreCompact hook and compact config keys`

---

### T13 — Lint, type-check, full test suite

- [x] Run `ruff format src tests`
- [x] Run `ruff check src tests`
- [x] Run `mypy src` (or whichever type checker the project uses — check `pyproject.toml`)
- [x] Run full `pytest` — all tests green
- [x] Fix any issues found

**Commit:** (only if fixes needed) `chore: lint and typing fixes for precompact hook slice`

---

### T14 — Manual end-to-end smoke test

- [x] In a real squadron project working copy:
  - [x] `sq install-commands`
  - [x] Inspect `.claude/settings.json`: confirm the `PreCompact` entry is present with `_managed_by: "squadron"`
  - [x] `sq _precompact-hook | jq .` — confirm valid JSON with populated `additionalContext` reflecting `{slice}` from CF state
- [x] Open the project in VS Code with Claude Code extension (or run interactive `claude` from the project directory)
- [x] Have a brief conversation referencing the current slice
- [x] Type `/compact`
- [x] After compaction, confirm the summary still reflects the slice context (i.e. the squadron instructions reached the summarizer)
- [x] **If the hook payload schema turns out to differ from `hookSpecificOutput.additionalContext`**: open the corresponding test in T5 and the payload builder in the hook command, adjust both, re-run tests
- [x] `sq uninstall-commands` and confirm the entry is gone from settings.json

**Commit:** (only if fixes needed) `fix: adjust PreCompact hook payload to match Claude Code schema`

---

### T15 — Slice closeout

- [x] Mark all T1–T14 tasks complete in this file
- [x] Set `status: complete` and update `dateUpdated` in this task file's frontmatter
- [x] Set `status: complete` and update `dateUpdated` in `157-slice.precompact-hook-for-interactive-claude-code.md`
- [x] In `140-slices.pipeline-foundation.md`, check off slice 157 (`[x]`) and update `dateUpdated`
- [x] Add DEVLOG entry summarizing the implementation per `prompt.ai-project.system.md` Session State Summary format
- [x] Add CHANGELOG entries: `### Added` (interactive PreCompact hook, `compact.template` and `compact.instructions` config keys, `sq install-commands` hook install)
- [x] Final commit

**Commit:** `docs: mark slice 157 PreCompact hook for interactive Claude Code complete`

---

## Notes

- **Hook payload schema (T5, T14)**: the design uses `{"hookSpecificOutput": {"hookEventName": "PreCompact", "additionalContext": "..."}}` based on Claude Code's documented hook contract. T14 includes a verification step against live Claude Code behavior. If the SDK's expected field name differs, T5's payload builder is the single point to fix.
- **Bare `except Exception` in T5**: this is the one place in squadron where a bare `Exception` catch is justified, because the hook's contract is "never break the user's `/compact`". The catch is tight (wraps only the render pipeline), and the docstring/comment must explain the rationale to satisfy the project's "explicit exception handling" rule.
- **Settings.json merge (T8/T9)**: the non-destructive merge logic is the highest-risk piece of the slice. The test matrix in T8/T9 is intentionally exhaustive — each of the branches (fresh, existing-squadron, existing-third-party, both, empty-file, no-hooks-key, no-PreCompact-key, corrupt-JSON) must have a dedicated test.
- **No new dependencies**: everything uses stdlib (`json`, `pathlib`) + existing squadron modules. `pyyaml` is already pulled in via the compaction template loader.
- **`sq` on PATH at hook invocation**: Claude Code runs hooks under a non-interactive shell which may have a reduced PATH. If T14 reveals this is a problem, a follow-up tweak writes `shutil.which("sq")` (absolute path) into the settings.json entry at install time instead of the bare `sq` name. Not worth doing preemptively.
- **File length check**: at the time of writing, this file is under the 450-line target; no split needed.
