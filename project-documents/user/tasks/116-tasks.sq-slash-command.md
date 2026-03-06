---
docType: task-breakdown
slice: sq-slash-command
project: squadron
lld: user/slices/116-slice.sq-slash-command.md
dependencies: [project-rename]
projectState: >
  Slices 100-115 complete. Project renamed from orchestration to squadron.
  CLI entry point is `sq`. This slice (116) is the active work item.
dateCreated: 20260305
dateUpdated: 20260306
status: in_progress
---

## Context Summary

- Implementing Claude Code slash commands that wrap `sq` CLI capabilities
- Eight command files in `commands/sq/` become `/sq:spawn`, `/sq:task`, etc.
- Install/uninstall CLI commands copy files to `~/.claude/commands/`
- Command files bundled in package wheel for distribution
- Test-with philosophy: tests follow each implementation component
- Commit checkpoints after each stable milestone
- Next planned slice: 117 (Composed Workflows)

---

## Tasks

- [x] **T1: Create command source directory**
  - [x] Create `commands/sq/` directory at the repo root
  - [x] Success: directory exists; `ls commands/sq/` runs without error

- [x] **T2: Write `spawn.md` command file**
  - [x] Create `commands/sq/spawn.md` per the specification in the slice design
  - [x] Include `$ARGUMENTS` pass-through, common flags, and help fallback
  - [x] Success: file exists and is non-empty; content references `sq spawn`

- [x] **T3: Write `task.md` command file**
  - [x] Create `commands/sq/task.md` per the slice design
  - [x] Include format guidance: `sq task AGENT_NAME "prompt text"`
  - [x] Success: file exists; content references `sq task`

- [x] **T4: Write `list.md` command file**
  - [x] Create `commands/sq/list.md` per the slice design
  - [x] Include optional flags documentation
  - [x] Success: file exists; content references `sq list`

- [x] **T5: Write `shutdown.md` command file**
  - [x] Create `commands/sq/shutdown.md` per the slice design
  - [x] Include both single-agent and `--all` usage
  - [x] Success: file exists; content references `sq shutdown`

- [x] **T6: Write `review-arch.md` command file**
  - [x] Create `commands/sq/review-arch.md` per the slice design
  - [x] Include required arguments, optional flags, and usage example
  - [x] Success: file exists; content references `sq review arch`

- [x] **T7: Write `review-tasks.md` command file**
  - [x] Create `commands/sq/review-tasks.md` per the slice design
  - [x] Include required arguments, optional flags, and usage example
  - [x] Success: file exists; content references `sq review tasks`

- [x] **T8: Write `review-code.md` command file**
  - [x] Create `commands/sq/review-code.md` per the slice design
  - [x] Include all optional flags and usage examples
  - [x] Success: file exists; content references `sq review code`

- [x] **T9: Write `auth-status.md` command file**
  - [x] Create `commands/sq/auth-status.md` per the slice design
  - [x] Success: file exists; content references `sq auth status`
  - [x] Commit: `feat: add Claude Code slash command files`

- [x] **T10: Update `pyproject.toml` for command file bundling**
  - [x] Add `force-include` entry under `[tool.hatch.build.targets.wheel]` to include `commands/` in the wheel as `squadron/commands/`
  - [x] Verify `importlib.resources` can locate the bundled files: create a small script or test that calls `files("squadron") / "commands"` and confirms the path exists
  - [x] Success: `uv build` succeeds; bundled commands are present in the wheel
  - [x] Commit: `chore: bundle command files in package wheel`

- [ ] **T11: Implement `install-commands` CLI command**
  - [ ] Create `src/squadron/cli/commands/install.py`
  - [ ] Implement `install_commands(target: str)`:
    - Resolve `~` in target path
    - Locate bundled commands via `importlib.resources`
    - Create target directory and `sq/` subdirectory if needed
    - Copy each `.md` file from bundled `commands/sq/` to `{target}/sq/`
    - Overwrite existing files
    - Report what was installed
  - [ ] Wire `install-commands` into the main Typer app in `cli/app.py`
  - [ ] Type-check; ruff passes
  - [ ] Success: `sq install-commands` copies all 8 files to `~/.claude/commands/sq/`

- [ ] **T12: Implement `uninstall-commands` CLI command**
  - [ ] Add `uninstall_commands(target: str)` to `install.py`:
    - Remove `{target}/sq/` directory and contents
    - Do not touch other files in the target directory
    - Report what was removed or that nothing was found
  - [ ] Wire `uninstall-commands` into the main Typer app in `cli/app.py`
  - [ ] Type-check; ruff passes
  - [ ] Success: `sq uninstall-commands` removes only the `sq/` subdirectory

- [ ] **T13: Test install and uninstall commands**
  - [ ] Create `tests/cli/test_install_commands.py`
  - [ ] Test install: files copied to target directory, correct file count (8 files)
  - [ ] Test install creates directories if they don't exist
  - [ ] Test install overwrites existing files
  - [ ] Test uninstall: `sq/` directory removed, other files in target untouched
  - [ ] Test uninstall when nothing is installed: graceful report, no error
  - [ ] Test `--target` flag overrides default path
  - [ ] Use `tmp_path` fixture for all file operations
  - [ ] Success: `pytest tests/cli/test_install_commands.py` passes
  - [ ] Commit: `feat: add install-commands and uninstall-commands CLI`

- [ ] **T14: Source file verification test**
  - [ ] Add a test (can be in `test_install_commands.py` or a new file) that verifies:
    - All 8 expected command files exist in `commands/sq/`
    - Each file is non-empty
    - Each file contains the expected `sq` subcommand string
  - [ ] Success: test passes; catches accidental file deletion or corruption

- [ ] **T15: Full validation pass**
  - [ ] Run `pytest tests/cli/test_install_commands.py` — all tests pass
  - [ ] Run `pyright src/squadron/cli/commands/install.py` — zero errors
  - [ ] Run `ruff check` and `ruff format --check` on new files — clean
  - [ ] Run full project test suite to confirm nothing is broken
  - [ ] Success: all checks pass
  - [ ] Commit: `chore: slice 116 validation pass`
