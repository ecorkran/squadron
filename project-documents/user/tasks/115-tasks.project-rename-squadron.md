---
docType: tasks
slice: project-rename-squadron
project: orchestration
lld: user/slices/115-slice.project-rename-squadron.md
dependencies: [auth-strategy-credential-management]
projectState: All slices through 114 complete. 61 .py files in src/orchestration/, 66 in tests/. Package builds and 435 tests pass.
dateCreated: 20260305
dateUpdated: 20260305
status: not_started
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

- [ ] **Rename `src/orchestration/` to `src/squadron/`**
  - [ ] `mv src/orchestration src/squadron`
  - [ ] In `pyproject.toml`, change `name = "orchestration"` to `name = "squadron"`
  - [ ] In `pyproject.toml`, update package directory references from `orchestration` to `squadron`
  - [ ] In `pyproject.toml`, replace the `orchestration` script entry point with two entries:
    - `sq = "squadron.cli.app:app"`
    - `squadron = "squadron.cli.app:app"`
  - [ ] Run `uv sync` to regenerate `uv.lock`
  - [ ] **Success**: `uv sync` completes without errors; `sq --help` prints CLI help

### 2. Update All Python Imports in src/

- [ ] **Replace all `from orchestration.` and `import orchestration.` references in `src/squadron/`**
  - [ ] Find all Python files under `src/squadron/` containing `orchestration`
  - [ ] Replace `from orchestration.` → `from squadron.` in all files
  - [ ] Replace `import orchestration.` → `import squadron.` in all files
  - [ ] Replace `"orchestration.` → `"squadron.` in string references to module paths (e.g., logger names)
  - [ ] **Success**: `grep -r "from orchestration\." src/squadron/` returns zero results; `grep -r "import orchestration\." src/squadron/` returns zero results

### 3. Update All Python Imports in tests/

- [ ] **Replace all `from orchestration.` and `import orchestration.` references in `tests/`**
  - [ ] Find all Python files under `tests/` containing `orchestration`
  - [ ] Replace `from orchestration.` → `from squadron.` in all files
  - [ ] Replace `import orchestration.` → `import squadron.` in all files
  - [ ] Replace any string references to `orchestration.` module paths
  - [ ] **Success**: `grep -r "from orchestration\." tests/` returns zero results; `grep -r "import orchestration\." tests/` returns zero results

### 4. Update Config Paths — User Config Directory

- [ ] **Update config path construction from `orchestration` to `squadron`**
  - [ ] In `src/squadron/config/manager.py`, change `Path.home() / ".config" / "orchestration"` to `Path.home() / ".config" / "squadron"`
  - [ ] **Success**: Config path resolves to `~/.config/squadron/`

### 5. Add Config Migration Logic

- [ ] **Add first-run migration from `~/.config/orchestration/` to `~/.config/squadron/`**
  - [ ] In the config path resolution function, add migration logic:
    - If `~/.config/squadron/` does not exist AND `~/.config/orchestration/` does exist:
      - Copy contents via `shutil.copytree`
      - Write `MIGRATED.txt` to the old directory with message: `"Config migrated to ~/.config/squadron/\nThis directory can be safely deleted.\n"`
      - Print one-time notice to stderr
  - [ ] Old directory is left in place (not deleted)
  - [ ] Refer to the slice design's Architecture > Migration Plan section for the reference implementation
  - [ ] **Success**: Migration logic exists; if old config dir exists without new dir, contents are copied and notice printed

### 6. Update Config Paths — Project-Level Config

- [ ] **Update project-level config filename from `.orchestration.toml` to `.squadron.toml`**
  - [ ] In `src/squadron/config/manager.py`, change `.orchestration.toml` reference to `.squadron.toml`
  - [ ] Search for any other references to `.orchestration.toml` in src/ and update
  - [ ] **Success**: `grep -r "\.orchestration\.toml" src/` returns zero results

### 7. Update Daemon and Server Paths

- [ ] **Update daemon socket/PID paths that reference "orchestration"**
  - [ ] In `src/squadron/server/daemon.py`, update `_DEFAULT_DIR = Path.home() / ".orchestration"` to use `"squadron"` (or `".squadron"`, matching the project's convention)
  - [ ] Search for any other daemon/socket/PID path references to "orchestration" in `src/squadron/server/`
  - [ ] Update any `/tmp/orchestration-*` path patterns to use `squadron`
  - [ ] **Success**: `grep -r "orchestration" src/squadron/server/` returns only import-related hits (which should already be fixed by Task 2), no path references

### 8. Update Logger Names

- [ ] **Replace logger name strings from `orchestration` to `squadron`**
  - [ ] Search for `getLogger` calls and logger name strings containing "orchestration" in `src/squadron/`
  - [ ] Update all logger names: `"orchestration.*"` → `"squadron.*"`
  - [ ] Note: some logger names may have been caught by the import update in Task 2 if they used module-style strings. Verify no stragglers remain.
  - [ ] **Success**: `grep -r 'getLogger.*orchestration' src/squadron/` returns zero results

### 9. Update User-Facing Strings and Error Messages

- [ ] **Update all user-facing strings that reference "orchestration" as a command or product name**
  - [ ] Search `src/squadron/` for remaining string occurrences of `"orchestration"` (quotes included)
  - [ ] Update CLI help text, error messages, and user instructions (e.g., `"Use 'orchestration list'"` → `"Use 'sq list'"`)
  - [ ] Update any `app_name` or product name constants
  - [ ] **Success**: `grep -rn "orchestration" src/squadron/` returns zero results, with the sole exception of migration code that references the old config path

### 10. Update Test Fixtures and Config Path References in Tests

- [ ] **Update test fixtures that reference orchestration config paths or command names**
  - [ ] Search `tests/` for string references to `"orchestration"` (beyond imports, which were handled in Task 3)
  - [ ] Update config path references in test fixtures (e.g., `".config/orchestration"` → `".config/squadron"`)
  - [ ] Update any test assertions checking CLI output or error messages that mention "orchestration"
  - [ ] Update any test references to `.orchestration.toml` → `.squadron.toml`
  - [ ] **Success**: `grep -rn "orchestration" tests/` returns zero results

### 11. Run Tests and Linting

- [ ] **Verify all tests pass and code quality checks are clean**
  - [ ] Run `pytest` — all tests must pass
  - [ ] Run `ruff check src/ tests/` — no errors
  - [ ] Run `ruff format --check src/ tests/` — no formatting issues
  - [ ] Run `pyright` (if configured) — no type errors
  - [ ] **Success**: All checks pass with zero errors

### 12. Update Documentation

- [ ] **Update README.md**
  - [ ] Replace project name references: "orchestration" → "squadron"
  - [ ] Update CLI command examples: `orchestration` → `sq` or `squadron`
  - [ ] Update installation instructions if they reference the package name
  - [ ] Update any path references (config dirs, etc.)
- [ ] **Update CLAUDE.md**
  - [ ] Update any project identity references from "orchestration" to "squadron"
- [ ] **Search for other .md files in the repo root that reference "orchestration"**
  - [ ] Update DEVLOG.md project name in frontmatter if applicable
  - [ ] Note: ai-project-guide doc filenames (like `100-arch.orchestration-v2.md`) are explicitly excluded from this rename per the slice design
- [ ] **Success**: Documentation accurately reflects the "squadron" name; CLI examples use `sq`

### 13. Final Validation

- [ ] **Comprehensive grep to find any remaining "orchestration" references**
  - [ ] Run `grep -r "orchestration" src/squadron/` — expect zero results except migration code
  - [ ] Run `grep -r "orchestration" tests/` — expect zero results
  - [ ] Run `pytest` one final time to confirm everything passes
  - [ ] Run `ruff check` and `ruff format --check` one final time
  - [ ] **Success**: No stray references; all checks pass

### 14. Commit

- [ ] **Create a single atomic commit for the entire rename**
  - [ ] Stage all changes: renamed directory, updated files, regenerated lock file
  - [ ] Commit with message: `refactor: rename orchestration → squadron`
  - [ ] Commit body should summarize: package rename, import updates, config path migration, CLI entry points (sq/squadron), documentation updates
  - [ ] **Success**: Clean commit; `git status` shows no uncommitted changes

## Notes

- **Excluded from this slice**: GitHub repo rename, context-forge project references, ai-project-guide doc filenames (e.g., `100-arch.orchestration-v2.md`). See slice design Excluded section.
- **Effort**: Relative effort 2/5 — mechanically straightforward but touches many files. The only new logic is the config migration in Task 5.
- **Risk**: Low. This is a pure rename refactor with clear validation (grep + test suite).
