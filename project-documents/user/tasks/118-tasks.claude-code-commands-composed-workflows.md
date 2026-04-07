---
slice: claude-code-commands-composed-workflows
project: squadron
lld: user/slices/118-slice.claude-code-commands-composed-workflows.md
dependencies: [sq-slash-command]
projectState: Slice 116 complete. Eight sq/ command files working. Install/uninstall mechanism in place. Wheel bundles commands via force-include. Context-Forge CLI available (cf get, cf set, cf build). No composed workflow commands exist yet.
dateCreated: 20260317
dateUpdated: 20260320
status: complete
docType: tasks
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

- [x] Update `commands/sq/review-tasks.md` to support bare slice number input
  - [x] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` and `cf task list --json` to resolve file paths
  - [x] Extract `designFile` and tasks file from JSON entries matching the given index
  - [x] Fall back to existing behavior when full paths are provided
  - [x] After running `sq review tasks`, save review output to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md`
  - [x] Review file includes YAML frontmatter: `docType: review`, `reviewType: tasks`, `slice`, `project`, `verdict`, `dateCreated`, `dateUpdated`
  - [x] Re-reviews overwrite the review file
  - [x] Fail explicitly if slice number not found in `cf slice list` output
  - [x] Fail explicitly if tasks file is null/missing for the given slice

### T2: Update `review-code.md` — number shorthand + review persistence

- [x] Update `commands/sq/review-code.md` to support bare slice number input
  - [x] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` to resolve the slice name
  - [x] When given a number, run `sq review code --diff main` (default to diffing against main)
  - [x] Save review output to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`
  - [x] Review file includes same YAML frontmatter pattern with `reviewType: code`
  - [x] Existing flag-based invocations (`--diff`, `--files`, etc.) continue to work unchanged
  - [x] Fail explicitly if slice number not found

### T3: Update `review-arch.md` — number shorthand + holistic review + persistence

- [x] Update `commands/sq/review-arch.md` to support bare slice number input
  - [x] Add path resolution block: if `$ARGUMENTS` starts with a number, run `cf slice list --json` to resolve `designFile` and slice plan entry name
  - [x] Use `cf get` to resolve Architecture field for `--against` argument
  - [x] Perform holistic review: slice design vs. both architecture doc and slice plan entry (one review answering "does this slice design effectively cover what it's supposed to?")
  - [x] Save review output to `project-documents/user/reviews/{nnn}-review.arch.{slice-name}.md`
  - [x] Review file includes same YAML frontmatter pattern with `reviewType: arch`
  - [x] Existing path-based invocations continue to work unchanged
  - [x] Fail explicitly if slice number not found or `designFile` is null

### T4: Create the `run-slice.md` command file

- [x] Create `commands/sq/run-slice.md` with the full pipeline prompt
  - [x] Content matches the Command File Specification in the slice design (section "Command File Specification")
  - [x] Includes Step 0 (Validate): `cf get` to confirm slice plan is set, read slice plan, verify slice exists
  - [x] Includes Step 1 (Phase 4): `cf set phase 4`, `cf set slice`, `cf build` → design work
  - [x] Includes Step 2 (Phase 5): `cf set phase 5`, `cf build` → task breakdown, then `sq review tasks` with review gate
  - [x] Task review output saved to `project-documents/user/reviews/{nnn}-review.tasks.{slice-name}.md`
  - [x] Review file includes YAML frontmatter: `docType: review`, `reviewType: tasks`, `slice`, `project`, `verdict`, `dateCreated`, `dateUpdated`
  - [x] Includes Step 3 (Compact): `/compact` with keep instructions for slice summaries
  - [x] Includes Step 4 (Phase 6): `cf set phase 6`, `cf build` → implementation, then `sq review code --diff main` with review gate
  - [x] Code review output saved to `project-documents/user/reviews/{nnn}-review.code.{slice-name}.md`
  - [x] Review file includes same YAML frontmatter pattern with `reviewType: code`
  - [x] Re-reviews overwrite the review file (git handles version history)
  - [x] Review files committed at each gate (with the work they gate)
  - [x] Includes Step 5 (DEVLOG Entry): use `cf prompt get session-state-summary` template to write summary to project root `DEVLOG.md`
  - [x] Includes Completion section: summary of paths (including review file paths), commits, review verdicts
  - [x] Review gate logic: PASS → commit review + proceed, minor CONCERNS → commit review + proceed with note, significant CONCERNS/FAIL → fix + re-review once (overwrite file), then commit review + stop for human if still failing
  - [x] TODO comments for future enhancement: smarter review loop, human signaling
  - [x] `$ARGUMENTS` used for slice identifier input
  - [x] Handles missing arguments (asks user which slice)
  - [x] Handles missing `cf` (explicit error, no silent fallback)
  - [x] File is valid markdown, no syntax errors

### T5: Commit — command file changes

- [x] Commit T1-T4 work
  - [x] Message: `feat: add /sq:run-slice command, update review commands with number shorthand`
  - [x] Stage `commands/sq/run-slice.md`, `commands/sq/review-tasks.md`, `commands/sq/review-code.md`, `commands/sq/review-arch.md`

### T6: Update install tests for new command count

- [x] Update `tests/cli/test_install_commands.py` to expect 9 command files instead of 8
  - [x] Add `"run-slice.md"` to the `EXPECTED_FILES` set
  - [x] Update `test_install_creates_directories` assertion: `len(...)  == 9`
  - [x] Update `test_target_flag_overrides_default` assertion: `len(...) == 9`
  - [x] Update `test_get_commands_source_returns_valid_dir` assertion: `len(...) == 9`
  - [x] Update `test_install_copies_files` docstring if it mentions "8"
  - [x] Update `test_all_command_files_exist_in_source` docstring if it mentions "8"
  - [x] Add `"run-slice.md": "cf get"` (or similar representative string) to `EXPECTED_COMMANDS` dict
  - [x] `uv run pytest tests/cli/test_install_commands.py` — all tests pass

### T7: Validation pass

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass
  - [x] `commands/sq/run-slice.md` exists and is non-empty
  - [x] All three updated review command files are non-empty
  - [x] `sq install-commands --target /tmp/test-commands` installs 9 files
  - [x] Verify run-slice.md is present in installed files: `ls /tmp/test-commands/sq/run-slice.md`
  - [x] Clean up: `rm -rf /tmp/test-commands`

### T8: Commit — tests and validation

- [x] Commit T6-T7 work
  - [x] Message: `test: update install tests for 9 command files`
  - [x] Skip commit if no changes needed

### T9: Verify wheel bundling

- [x] Build wheel and verify `run-slice.md` is included
  - [x] Run `uv build`
  - [x] `unzip -l dist/*.whl | grep run-slice` — confirm `squadron/commands/sq/run-slice.md` appears
  - [x] Clean up `dist/`

### T10: Add `_resolve_slice_number` helper to `review.py`

- [x] Add helper function `_resolve_slice_number(num: str) -> dict` in `src/squadron/cli/commands/review.py`
  - [x] Shells out to `cf slice list --json` via `subprocess.run`, captures stdout
  - [x] Parses JSON, finds entry where `index` matches `int(num)`
  - [x] Returns dict with keys: `index`, `name`, `slice_name` (kebab-case from designFile path), `design_file`, `task_file` (from `cf task list --json`)
  - [x] Raises `typer.Exit(code=1)` with clear error if: `cf` not found, slice number not found, `designFile` is null (where needed)
  - [x] Also shells out to `cf task list --json` to get task file path

### T11: Wire number shorthand into review commands

- [x] Update `review_arch` command
  - [x] Detect `input_file.isdigit()` — if true, call `_resolve_slice_number`
  - [x] Set `input_file` to resolved `design_file`, `against` to architecture doc (from `cf get` or config)
  - [x] Architecture doc resolution: shell out to `cf get --json` or parse `cf get` output for Architecture field
  - [x] Existing path-based invocations unchanged
- [x] Update `review_tasks` command
  - [x] Detect `input_file.isdigit()` — if true, call `_resolve_slice_number`
  - [x] Set `input_file` to resolved task file, `against` to resolved design file
  - [x] Fail explicitly if task file is null/missing
  - [x] Existing path-based invocations unchanged
- [x] Update `review_code` command
  - [x] Add optional positional argument for slice number (default `None`)
  - [x] If positional arg is provided and is a digit, call `_resolve_slice_number` for context (slice name for output/logging)
  - [x] Default to `--diff main` when invoked with a number
  - [x] Existing flag-based invocations unchanged

### T12: Tests for CLI number shorthand

- [x] Add tests in `tests/cli/test_review_resolve.py`
  - [x] Test `_resolve_slice_number` with mocked subprocess output (valid slice)
  - [x] Test `_resolve_slice_number` with no matching index (exits with error)
  - [x] Test `_resolve_slice_number` with null designFile (exits with error)
  - [x] Test `_resolve_slice_number` when `cf` is not installed (exits with error)
  - [x] Test `review_tasks` with digit input routes through resolver (mock resolver, verify inputs dict)
  - [x] Test `review_arch` with digit input routes through resolver
  - [x] `uv run pytest tests/cli/test_review_resolve.py` — all tests pass

### T13: Commit — CLI number shorthand

- [x] Commit T10-T12 work
  - [x] Message: `feat: add bare number shorthand to sq review CLI commands`
  - [x] Stage `src/squadron/cli/commands/review.py` and `tests/cli/test_review_resolve.py`

### T14: Validation pass — full suite after CLI changes

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass

### T15: Add `_save_review_file` helper and wire auto-save into review commands

- [x] Add `_save_review_file(result, review_type, slice_info, as_json)` helper in `review.py`
  - [x] Writes markdown file to `project-documents/user/reviews/{nnn}-review.{type}.{slice-name}.md`
  - [x] Markdown file includes YAML frontmatter: `docType: review`, `reviewType`, `slice`, `project`, `verdict`, `dateCreated`, `dateUpdated`
  - [x] Body contains the formatted review output (findings with descriptions)
  - [x] When `as_json=True`, writes `.json` file instead using `result.to_dict()`
  - [x] Overwrites existing file on re-review
  - [x] Creates `project-documents/user/reviews/` directory if it doesn't exist
- [x] Add `--no-save` flag to `review_arch`, `review_tasks`, `review_code`
  - [x] Default: save review file when invoked with a slice number
  - [x] `--no-save`: suppress file save
  - [x] `--json` flag: save as JSON instead of markdown
- [x] Wire auto-save: after `_run_review_command` returns, if slice number was provided and `--no-save` not set, call `_save_review_file`
- [x] Thread `slice_info` through so save helper has access to index, slice_name, review type
- [x] Print confirmation message: `Saved review to {path}`

### T16: Tests for review file auto-save

- [x] Add tests in `tests/cli/test_review_save.py`
  - [x] Test `_save_review_file` writes markdown with correct frontmatter
  - [x] Test `_save_review_file` writes JSON when `as_json=True`
  - [x] Test `_save_review_file` overwrites existing file
  - [x] Test `_save_review_file` creates reviews directory if missing
  - [x] Test `--no-save` flag prevents file creation
  - [x] `uv run pytest tests/cli/test_review_save.py` — all tests pass

### T17: Update slash commands for parity

- [x] Update `commands/sq/review-tasks.md`, `review-code.md`, `review-arch.md`
  - [x] Remove explicit "save the review output" instructions (CLI now does this automatically)
  - [x] Note that review file is auto-saved by the CLI
  - [x] Document `--no-save` and `--json` flags

### T18: Commit — review file auto-save

- [x] Commit T15-T17 work
  - [x] Message: `feat: auto-save review files when using slice number shorthand`

### T19: Validation pass

- [x] Full project validation
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean
  - [x] `uv run pyright` — zero errors
  - [x] `uv run pytest` — all tests pass

---

## Post-Implementation (Manual — Project Manager)

These are not AI-automatable tasks. They are documented here for the PM's reference.

- [x] **Live test**: Run `/sq:review-tasks 191` (or similar) to verify number shorthand resolves paths correctly and saves review file
- [x] **Iterate on prompt**: Adjust `run-slice.md` prompt based on real-world behavior — especially review gate sensitivity and compact keep instructions
- **Deferred**: `/sq:run-slice` live test deferred until "pickup" enhancement is added (ability to resume at current phase rather than always starting from phase 4). Will test with a fresh slice at that point.
