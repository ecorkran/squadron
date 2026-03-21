---
slice: claude-code-commands-composed-workflows
project: squadron
lld: user/slices/118-slice.claude-code-commands-composed-workflows.md
dependencies: [sq-slash-command]
projectState: Slice 116 complete. Eight sq/ command files working. Install/uninstall mechanism in place. Wheel bundles commands via force-include. Context-Forge CLI available (cf get, cf set, cf build). No composed workflow commands exist yet.
dateCreated: 20260317
dateUpdated: 20260320
status: not_started
---

## Context Summary

- Working on `claude-code-commands-composed-workflows` slice
- Slice 116 (sq Wrappers) is complete; `commands/sq/` has 8 command files, install/uninstall works
- This slice adds one new command file (`run-slice.md`) and updates three existing review commands
- **`run-slice.md`**: Automates the full slice lifecycle: phase 4 (design) → phase 5 (tasks + review) → compact → phase 6 (implement + code review) → DEVLOG entry
- **Review command updates** (`review-tasks.md`, `review-code.md`, `review-arch.md`): Add bare number shorthand (e.g., `/sq:review-tasks 191`) with path resolution via `cf slice list --json` / `cf task list --json`, plus review file persistence to `project-documents/user/reviews/`
- **`review-arch`** performs holistic check when given a number: slice design vs. architecture doc + slice plan entry
- No Python code changes needed — all changes are markdown command files
- Existing tests expect 8 files — must update to 9 (one new file added, three updated)
- Path resolution uses CF list commands (not hardcoded globs) — worktree-aware, CF owns conventions

---

## Tasks

### T1: Update `review-tasks.md` — number shorthand + review persistence

- [ ] Update `commands/sq/review-tasks.md` to support bare slice number input
  - [ ] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` and `cf task list --json` to resolve file paths
  - [ ] Extract `designFile` and tasks file from JSON entries matching the given index
  - [ ] Fall back to existing behavior when full paths are provided
  - [ ] After running `sq review tasks`, save review output to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md`
  - [ ] Review file includes YAML frontmatter: `docType: review`, `reviewType: tasks`, `slice`, `project`, `verdict`, `dateCreated`, `dateUpdated`
  - [ ] Re-reviews overwrite the review file
  - [ ] Fail explicitly if slice number not found in `cf slice list` output
  - [ ] Fail explicitly if tasks file is null/missing for the given slice

### T2: Update `review-code.md` — number shorthand + review persistence

- [ ] Update `commands/sq/review-code.md` to support bare slice number input
  - [ ] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` to resolve the slice name
  - [ ] When given a number, run `sq review code --diff main` (default to diffing against main)
  - [ ] Save review output to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`
  - [ ] Review file includes same YAML frontmatter pattern with `reviewType: code`
  - [ ] Existing flag-based invocations (`--diff`, `--files`, etc.) continue to work unchanged
  - [ ] Fail explicitly if slice number not found

### T3: Update `review-arch.md` — number shorthand + holistic review + persistence

- [ ] Update `commands/sq/review-arch.md` to support bare slice number input
  - [ ] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` to resolve `designFile` and slice plan entry name
  - [ ] Use `cf get` to resolve Architecture field for `--against` argument
  - [ ] Perform holistic review: slice design vs. both architecture doc and slice plan entry (one review answering "does this slice design effectively cover what it's supposed to?")
  - [ ] Save review output to `project-documents/user/reviews/{nnn}-review.arch.{slice-name}.md`
  - [ ] Review file includes same YAML frontmatter pattern with `reviewType: arch`
  - [ ] Existing path-based invocations continue to work unchanged
  - [ ] Fail explicitly if slice number not found or `designFile` is null

### T4: Create the `run-slice.md` command file

- [ ] Create `commands/sq/run-slice.md` with the full pipeline prompt
  - [ ] Content matches the Command File Specification in the slice design (section "Command File Specification")
  - [ ] Includes Step 0 (Validate): `cf get` to confirm slice plan is set, read slice plan, verify slice exists
  - [ ] Includes Step 1 (Phase 4): `cf set phase 4`, `cf set slice`, `cf build` → design work
  - [ ] Includes Step 2 (Phase 5): `cf set phase 5`, `cf build` → task breakdown, then `sq review tasks` with review gate
  - [ ] Task review output saved to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md`
  - [ ] Review file includes YAML frontmatter: `docType: review`, `reviewType: tasks`, `slice`, `project`, `verdict`, `dateCreated`, `dateUpdated`
  - [ ] Includes Step 3 (Compact): `/compact` with keep instructions for slice summaries
  - [ ] Includes Step 4 (Phase 6): `cf set phase 6`, `cf build` → implementation, then `sq review code --diff main` with review gate
  - [ ] Code review output saved to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`
  - [ ] Review file includes same YAML frontmatter pattern with `reviewType: code`
  - [ ] Re-reviews overwrite the review file (git handles version history)
  - [ ] Review files committed at each gate (with the work they gate)
  - [ ] Includes Step 5 (DEVLOG Entry): use `cf prompt get session-state-summary` template to write summary to project root `DEVLOG.md`
  - [ ] Includes Completion section: summary of paths (including review file paths), commits, review verdicts
  - [ ] Review gate logic: PASS → commit review + proceed, minor CONCERNS → commit review + proceed with note, significant CONCERNS/FAIL → fix + re-review once (overwrite file), then commit review + stop for human if still failing
  - [ ] TODO comments for future enhancement: smarter review loop, human signaling
  - [ ] `$ARGUMENTS` used for slice identifier input
  - [ ] Handles missing arguments (asks user which slice)
  - [ ] Handles missing `cf` (explicit error, no silent fallback)
  - [ ] File is valid markdown, no syntax errors

### T5: Commit — command file changes

- [ ] Commit T1-T4 work
  - [ ] Message: `feat: add /sq:run-slice command, update review commands with number shorthand`
  - [ ] Stage `commands/sq/run-slice.md`, `commands/sq/review-tasks.md`, `commands/sq/review-code.md`, `commands/sq/review-arch.md`

### T6: Update install tests for new command count

- [ ] Update `tests/cli/test_install_commands.py` to expect 9 command files instead of 8
  - [ ] Add `"run-slice.md"` to the `EXPECTED_FILES` set
  - [ ] Update `test_install_creates_directories` assertion: `len(...)  == 9`
  - [ ] Update `test_target_flag_overrides_default` assertion: `len(...) == 9`
  - [ ] Update `test_get_commands_source_returns_valid_dir` assertion: `len(...) == 9`
  - [ ] Update `test_install_copies_files` docstring if it mentions "8"
  - [ ] Update `test_all_command_files_exist_in_source` docstring if it mentions "8"
  - [ ] Add `"run-slice.md": "cf get"` (or similar representative string) to `EXPECTED_COMMANDS` dict
  - [ ] `uv run pytest tests/cli/test_install_commands.py` — all tests pass

### T7: Validation pass

- [ ] Full project validation
  - [ ] `uv run ruff check` — clean
  - [ ] `uv run ruff format --check` — clean
  - [ ] `uv run pyright` — zero errors
  - [ ] `uv run pytest` — all tests pass
  - [ ] `commands/sq/run-slice.md` exists and is non-empty
  - [ ] All three updated review command files are non-empty
  - [ ] `sq install-commands --target /tmp/test-commands` installs 9 files
  - [ ] Verify run-slice.md is present in installed files: `ls /tmp/test-commands/sq/run-slice.md`
  - [ ] Clean up: `rm -rf /tmp/test-commands`

### T8: Commit — tests and validation

- [ ] Commit T6-T7 work
  - [ ] Message: `test: update install tests for 9 command files`
  - [ ] Skip commit if no changes needed

### T9: Verify wheel bundling

- [ ] Build wheel and verify `run-slice.md` is included
  - [ ] Run `uv build`
  - [ ] `unzip -l dist/*.whl | grep run-slice` — confirm `squadron/commands/sq/run-slice.md` appears
  - [ ] Clean up `dist/`

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [ ] **Live test**: Run `/sq:run-slice` on a real upcoming slice to verify the full pipeline (design → tasks → review → compact → implement → review) works end-to-end in Claude Code
- [ ] **Live test**: Run `/sq:review-tasks 191` (or similar) to verify number shorthand resolves paths correctly and saves review file
- [ ] **Iterate on prompt**: Adjust `run-slice.md` prompt based on real-world behavior — especially review gate sensitivity and compact keep instructions
