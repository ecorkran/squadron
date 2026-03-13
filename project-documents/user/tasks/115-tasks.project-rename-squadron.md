---
docType: tasks
slice: project-rename-squadron
project: squadron
lld: user/slices/115-slice.project-rename-squadron.md
dependencies: [auth-strategy-credential-management]
projectState: All slices through 114 complete. 61 .py files in src/orchestration/, 66 in tests/. Package builds and 435 tests pass.
dateCreated: 20260305
dateUpdated: 20260305
status: complete
---

# Tasks: Project Rename — orchestration → squadron

## Context Summary

- Working on slice 115: project-rename-squadron
- Renames the Python package, CLI entry points, config paths, and all references from "orchestration" to "squadron"
- CLI becomes `sq` (primary) / `squadron` (long form)
- Config paths migrate from `~/.config/orchestration/` to `~/.config/squadron/`
- All 127 .py files (61 src + 66 tests) need import updates
- This is a mechanical refactor with one piece of new logic: config migration
- Slice design specifies a single atomic commit
- Dependencies: slice 114 (auth strategy) is complete
- Next planned work: slice 118 (Claude Code commands) depends on this rename

## Tasks

### 1. Rename Source Directory and Update pyproject.toml

- [x] **Rename `src/orchestration/` to `src/squadron/`**
  - [x] `mv src/orchestration src/squadron`
  - [x] In `pyproject.toml`, change `name = "orchestration"` to `name = "squadron"`
  - [x] In `pyproject.toml`, update package directory references from `orchestration` to `squadron`
  - [x] In `pyproject.toml`, replace the `orchestration` script entry point with two entries:
    - `sq = "squadron.cli.app:app"`
    - `squadron = "squadron.cli.app:app"`
  - [x] Run `uv sync` to regenerate `uv.lock`
  - [x] **Success**: `uv sync` completes without errors; `sq --help` prints CLI help

### 2. Update All Python Imports in src/

- [x] **Replace all `from orchestration.` and `import orchestration.` references in `src/squadron/`**
  - [x] Find all Python files under `src/squadron/` containing `orchestration`
  - [x] Replace `from orchestration.` → `from squadron.` in all files
  - [x] Replace `import orchestration.` → `import squadron.` in all files
  - [x] Replace `"orchestration.` → `"squadron.` in string references to module paths (e.g., logger names)
  - [x] **Success**: `grep -r "from orchestration\." src/squadron/` returns zero results; `grep -r "import orchestration\." src/squadron/` returns zero results

### 3. Update All Python Imports in tests/

- [x] **Replace all `from orchestration.` and `import orchestration.` references in `tests/`**
  - [x] Find all Python files under `tests/` containing `orchestration`
  - [x] Replace `from orchestration.` → `from squadron.` in all files
  - [x] Replace `import orchestration.` → `import squadron.` in all files
  - [x] Replace any string references to `orchestration.` module paths
  - [x] **Success**: `grep -r "from orchestration\." tests/` returns zero results; `grep -r "import orchestration\." tests/` returns zero results

### 4. Update Config Paths — User Config Directory

- [x] **Update config path construction from `orchestration` to `squadron`**
  - [x] In `src/squadron/config/manager.py`, change `Path.home() / ".config" / "orchestration"` to `Path.home() / ".config" / "squadron"`
  - [x] **Success**: Config path resolves to `~/.config/squadron/`

### 5. Add Config Migration Logic

- [x] **Add first-run migration from `~/.config/orchestration/` to `~/.config/squadron/`**
  - [x] In the config path resolution function, add migration logic:
    - If `~/.config/squadron/` does not exist AND `~/.config/orchestration/` does exist:
      - Copy contents via `shutil.copytree`
      - Write `MIGRATED.txt` to the old directory with message: `"Config migrated to ~/.config/squadron/\nThis directory can be safely deleted.\n"`
      - Print one-time notice to stderr
  - [x] Old directory is left in place (not deleted)
  - [x] Refer to the slice design's Architecture > Migration Plan section for the reference implementation
  - [x] **Success**: Migration logic exists; if old config dir exists without new dir, contents are copied and notice printed

### 6. Update Config Paths — Project-Level Config

- [x] **Update project-level config filename from `.orchestration.toml` to `.squadron.toml`**
  - [x] In `src/squadron/config/manager.py`, change `.orchestration.toml` reference to `.squadron.toml`
  - [x] Search for any other references to `.orchestration.toml` in src/ and update
  - [x] **Success**: `grep -r "\.orchestration\.toml" src/` returns zero results

### 7. Update Daemon and Server Paths

- [x] **Update daemon socket/PID paths that reference "orchestration"**
  - [x] In `src/squadron/server/daemon.py`, update `_DEFAULT_DIR = Path.home() / ".orchestration"` to use `"squadron"` (or `".squadron"`, matching the project's convention)
  - [x] Search for any other daemon/socket/PID path references to "orchestration" in `src/squadron/server/`
  - [x] Update any `/tmp/orchestration-*` path patterns to use `squadron`
  - [x] **Success**: `grep -r "orchestration" src/squadron/server/` returns only import-related hits (which should already be fixed by Task 2), no path references

### 8. Update Logger Names

- [x] **Replace logger name strings from `orchestration` to `squadron`**
  - [x] Search for `getLogger` calls and logger name strings containing "orchestration" in `src/squadron/`
  - [x] Update all logger names: `"orchestration.*"` → `"squadron.*"`
  - [x] Note: some logger names may have been caught by the import update in Task 2 if they used module-style strings. Verify no stragglers remain.
  - [x] **Success**: `grep -r 'getLogger.*orchestration' src/squadron/` returns zero results

### 9. Update User-Facing Strings and Error Messages

- [x] **Update all user-facing strings that reference "orchestration" as a command or product name**
  - [x] Search `src/squadron/` for remaining string occurrences of `"orchestration"` (quotes included)
  - [x] Update CLI help text, error messages, and user instructions (e.g., `"Use 'orchestration list'"` → `"Use 'sq list'"`)
  - [x] Update any `app_name` or product name constants
  - [x] **Success**: `grep -rn "orchestration" src/squadron/` returns zero results, with the sole exception of migration code that references the old config path

### 10. Update Test Fixtures and Config Path References in Tests

- [x] **Update test fixtures that reference orchestration config paths or command names**
  - [x] Search `tests/` for string references to `"orchestration"` (beyond imports, which were handled in Task 3)
  - [x] Update config path references in test fixtures (e.g., `".config/orchestration"` → `".config/squadron"`)
  - [x] Update any test assertions checking CLI output or error messages that mention "orchestration"
  - [x] Update any test references to `.orchestration.toml` → `.squadron.toml`
  - [x] **Success**: `grep -rn "orchestration" tests/` returns zero results

### 11. Run Tests and Linting

- [x] **Verify all tests pass and code quality checks are clean**
  - [x] Run `pytest` — all tests must pass
  - [x] Run `ruff check src/ tests/` — no errors
  - [x] Run `ruff format --check src/ tests/` — no formatting issues
  - [x] Run `pyright` (if configured) — no type errors
  - [x] **Success**: All checks pass with zero errors

### 12. Update Documentation

- [x] **Update README.md**
  - [x] Replace project name references: "orchestration" → "squadron"
  - [x] Update CLI command examples: `orchestration` → `sq` or `squadron`
  - [x] Update installation instructions if they reference the package name
  - [x] Update any path references (config dirs, etc.)
- [x] **Update CLAUDE.md**
  - [x] Update any project identity references from "orchestration" to "squadron"
- [x] **Search for other .md files in the repo root that reference "orchestration"**
  - [x] Update DEVLOG.md project name in frontmatter if applicable
  - [x] Note: ai-project-guide doc filenames (like `100-arch.orchestration-v2.md`) are explicitly excluded from this rename per the slice design
- [x] **Success**: Documentation accurately reflects the "squadron" name; CLI examples use `sq`

### 13. Final Validation

- [x] **Comprehensive grep to find any remaining "orchestration" references**
  - [x] Run `grep -r "orchestration" src/squadron/` — expect zero results except migration code
  - [x] Run `grep -r "orchestration" tests/` — expect zero results
  - [x] Run `pytest` one final time to confirm everything passes
  - [x] Run `ruff check` and `ruff format --check` one final time
  - [x] **Success**: No stray references; all checks pass

### 14. Commit

- [x] **Create a single atomic commit for the entire rename**
  - [x] Stage all changes: renamed directory, updated files, regenerated lock file
  - [x] Commit with message: `refactor: rename orchestration → squadron`
  - [x] Commit body should summarize: package rename, import updates, config path migration, CLI entry points (sq/squadron), documentation updates
  - [x] **Success**: Clean commit; `git status` shows no uncommitted changes

## Notes

- **Excluded from this slice**: GitHub repo rename, context-forge project references, ai-project-guide doc filenames (e.g., `100-arch.orchestration-v2.md`). See slice design Excluded section.
- **Effort**: Relative effort 2/5 — mechanically straightforward but touches many files. The only new logic is the config migration in Task 5.
- **Risk**: Low. This is a pure rename refactor with clear validation (grep + test suite).
