---
slice: claude-code-commands-composed-workflows
project: squadron
lld: user/slices/118-slice.claude-code-commands-composed-workflows.md
dependencies: [sq-slash-command]
projectState: Slice 116 complete. Eight sq/ command files working. Install/uninstall mechanism in place. Wheel bundles commands via force-include. Context-Forge CLI available (cf get, cf set, cf build). No composed workflow commands exist yet.
dateCreated: 20260317
dateUpdated: 20260317
status: not_started
---

## Context Summary

- Working on `claude-code-commands-composed-workflows` slice — add `/sq:run-slice` command
- Slice 116 (sq Wrappers) is complete; `commands/sq/` has 8 command files, install/uninstall works
- This slice adds one command file: `commands/sq/run-slice.md`
- The command automates the full slice lifecycle: phase 4 (design) → phase 5 (tasks + review) → compact → phase 6 (implement + code review)
- No Python code changes needed for install (file goes in existing `sq/` directory)
- Uninstall currently only removes `sq/` — no change needed since file is in `sq/`
- Existing tests expect 8 files — must update to 9
- Next planned slice: 119 (Conversation Persistence & Management)

---

## Tasks

### T1: Create the `run-slice.md` command file

- [ ] Create `commands/sq/run-slice.md` with the full pipeline prompt
  - [ ] Content matches the Command File Specification in the slice design (section "Command File Specification")
  - [ ] Includes Step 0 (Validate): `cf get` to confirm slice plan is set, read slice plan, verify slice exists
  - [ ] Includes Step 1 (Phase 4): `cf set phase 4`, `cf set slice`, `cf build` → design work
  - [ ] Includes Step 2 (Phase 5): `cf set phase 5`, `cf build` → task breakdown, then `sq review tasks` with review gate
  - [ ] Includes Step 3 (Compact): `/compact` with keep instructions for slice summaries
  - [ ] Includes Step 4 (Phase 6): `cf set phase 6`, `cf build` → implementation, then `sq review code --diff main` with review gate
  - [ ] Includes Completion section: summary of paths, commits, review verdicts
  - [ ] Review gate logic: PASS → proceed, minor CONCERNS → proceed with note, significant CONCERNS/FAIL → fix + re-review once, then stop for human if still failing
  - [ ] TODO comments for future enhancement: smarter review loop, human signaling
  - [ ] `$ARGUMENTS` used for slice identifier input
  - [ ] Handles missing arguments (asks user which slice)
  - [ ] Handles missing `cf` (explicit error, no silent fallback)
  - [ ] File is valid markdown, no syntax errors

### T2: Update install tests for new command count

- [ ] Update `tests/cli/test_install_commands.py` to expect 9 command files instead of 8
  - [ ] Add `"run-slice.md"` to the `EXPECTED_FILES` set
  - [ ] Update `test_install_creates_directories` assertion: `len(...)  == 9`
  - [ ] Update `test_target_flag_overrides_default` assertion: `len(...) == 9`
  - [ ] Update `test_get_commands_source_returns_valid_dir` assertion: `len(...) == 9`
  - [ ] Update `test_install_copies_files` docstring if it mentions "8"
  - [ ] Update `test_all_command_files_exist_in_source` docstring if it mentions "8"
  - [ ] Add `"run-slice.md": "cf get"` (or similar representative string) to `EXPECTED_COMMANDS` dict
  - [ ] `uv run pytest tests/cli/test_install_commands.py` — all tests pass

### T3: Commit — command file and test updates

- [ ] Commit T1-T2 work
  - [ ] Message: `feat: add /sq:run-slice composed workflow command`
  - [ ] Stage `commands/sq/run-slice.md` and `tests/cli/test_install_commands.py`

### T4: Validation pass

- [ ] Full project validation
  - [ ] `uv run ruff check` — clean
  - [ ] `uv run ruff format --check` — clean
  - [ ] `uv run pyright` — zero errors
  - [ ] `uv run pytest` — all tests pass
  - [ ] `commands/sq/run-slice.md` exists and is non-empty
  - [ ] `sq install-commands --target /tmp/test-commands` installs 9 files
  - [ ] Verify run-slice.md is present in installed files: `ls /tmp/test-commands/sq/run-slice.md`
  - [ ] Clean up: `rm -rf /tmp/test-commands`

### T5: Commit — validation pass

- [ ] Commit any fixes from T4
  - [ ] Message: `chore: slice 118 validation pass`
  - [ ] Skip commit if no changes needed

### T6: Verify wheel bundling

- [ ] Build wheel and verify `run-slice.md` is included
  - [ ] Run `uv build`
  - [ ] `unzip -l dist/*.whl | grep run-slice` — confirm `squadron/commands/sq/run-slice.md` appears
  - [ ] Clean up `dist/`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [ ] **Live test**: Run `/sq:run-slice` on a real upcoming slice to verify the full pipeline (design → tasks → review → compact → implement → review) works end-to-end in Claude Code
- [ ] **Iterate on prompt**: Adjust `run-slice.md` prompt based on real-world behavior — especially review gate sensitivity and compact keep instructions
