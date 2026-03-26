---
docType: tasks
slice: scoped-code-review-prompt-logging
project: squadron
lld: user/slices/127-slice.scoped-code-review-prompt-logging.md
dependencies: [review-context-enrichment]
projectState: Slice 122 complete. review_client.py has _run_non_sdk_review() with -vvv stderr debug output. review.py has review_code() with slice_number resolution, _format_review_markdown(), _save_review_file(). Debug log at ~/.config/squadron/logs/review-debug.jsonl. ReviewResult in models.py with fallback_used field.
dateCreated: 20260325
dateUpdated: 20260325
status: not_started
---

## Context Summary

- **Problem 1:** `sq review code 122` sets `diff = "main"`, producing a diff of the entire working tree against main — not just slice 122's commits
- **Problem 2:** `-vvv` debug output (system prompt, user prompt, rules) prints to stderr and is lost after terminal scrolls
- **Feature 1:** Scoped diff resolution — auto-resolve slice branch or merge commit to diff only the slice's changes
- **Feature 2:** Prompt log persistence — write full prompt to `~/.config/squadron/logs/review-prompt-{ts}.md` at `-vvv`
- **Feature 3:** Debug appendix in saved review file — embed prompt/response in review markdown at `-vv+`
- Key files:
  - `src/squadron/review/review_client.py` — `_run_non_sdk_review()`, `-vvv` stderr output
  - `src/squadron/cli/commands/review.py` — `review_code()`, `_format_review_markdown()`, `_save_review_file()`
  - `src/squadron/review/models.py` — `ReviewResult` dataclass
- New file: `src/squadron/review/git_utils.py` — slice branch/merge-commit resolution

---

## Tasks

### T1: Create `git_utils.py` with `_find_slice_branch()`

- [ ] Create `src/squadron/review/git_utils.py`
- [ ] Implement `_find_slice_branch(slice_number: int, cwd: str) -> str | None`:
  - [ ] Run `git branch --list '{N}-slice.*'` with `subprocess.run(check=False)`
  - [ ] Parse output: strip whitespace, return first match or `None`
  - [ ] Handle `FileNotFoundError`/`OSError` gracefully (return `None`)
- [ ] Success: function returns branch name when it exists, `None` otherwise
- [ ] `uv run pyright` and `uv run ruff check` pass

### T2: Add `_find_merge_commit()` to `git_utils.py`

- [ ] Implement `_find_merge_commit(slice_number: int, cwd: str) -> str | None`:
  - [ ] Run `git log --merges --oneline --grep='{N}-slice' main -1`
  - [ ] Parse commit hash from the first word of output
  - [ ] Return the commit hash or `None` if no match
  - [ ] Handle subprocess errors gracefully (return `None`)
- [ ] Success: function returns merge commit hash when found, `None` otherwise
- [ ] `uv run pyright` and `uv run ruff check` pass

### T3: Add `resolve_slice_diff_range()` to `git_utils.py`

- [ ] Implement `resolve_slice_diff_range(slice_number: int, cwd: str) -> str`:
  - [ ] Call `_find_slice_branch()` first — if found:
    - [ ] Run `git merge-base main {branch}` to get divergence point
    - [ ] Return `{merge_base}...{branch}` (three-dot range)
  - [ ] If no branch, call `_find_merge_commit()` — if found:
    - [ ] Return `{merge_commit}^1..{merge_commit}^2` (branch side of merge)
  - [ ] If neither found, print warning to stderr and return `"main"` (fallback)
- [ ] Success: returns appropriate diff range string for all three cases
- [ ] `uv run pyright` and `uv run ruff check` pass

### T4: Tests for `git_utils.py`

- [ ] Create `tests/review/test_git_utils.py`
- [ ] Test `_find_slice_branch()`:
  - [ ] `test_find_branch_exists` — mock subprocess returning branch name → returns branch
  - [ ] `test_find_branch_not_found` — mock subprocess returning empty → returns `None`
  - [ ] `test_find_branch_subprocess_error` — mock `FileNotFoundError` → returns `None`
- [ ] Test `_find_merge_commit()`:
  - [ ] `test_find_merge_commit_found` — mock subprocess returning `"abc1234 Merge branch '122-slice.foo'"` → returns `"abc1234"`
  - [ ] `test_find_merge_commit_not_found` — mock subprocess returning empty → returns `None`
  - [ ] `test_find_merge_commit_subprocess_error` — mock error → returns `None`
- [ ] Test `resolve_slice_diff_range()`:
  - [ ] `test_resolve_branch_exists` — patch `_find_slice_branch` to return branch, mock `merge-base` → returns `"{hash}...{branch}"`
  - [ ] `test_resolve_merged` — patch `_find_slice_branch` to return `None`, `_find_merge_commit` to return hash → returns `"{hash}^1..{hash}^2"`
  - [ ] `test_resolve_fallback` — both return `None` → returns `"main"`, prints warning to stderr
  - [ ] `test_resolve_merge_base_fails` — branch found but `merge-base` fails → falls back gracefully
- [ ] `uv run pytest tests/review/test_git_utils.py -v` — all pass

**Commit:** `feat: add git_utils.py with scoped slice diff resolution`

### T5: Add prompt capture fields to `ReviewResult`

- [ ] In `src/squadron/review/models.py`, add three fields to `ReviewResult`:
  - [ ] `system_prompt: str | None = None`
  - [ ] `user_prompt: str | None = None`
  - [ ] `rules_content_used: str | None = None`
- [ ] Ensure these fields are excluded from `to_dict()` output (do not include in the dict)
- [ ] Success: `ReviewResult` accepts new fields, `to_dict()` does not include them
- [ ] `uv run pyright` and `uv run ruff check` pass

### T6: Tests for `ReviewResult` prompt fields

- [ ] In `tests/review/test_parsers.py` (or appropriate existing test file), add tests:
  - [ ] `test_review_result_prompt_fields_default_none` — new fields default to `None`
  - [ ] `test_review_result_prompt_fields_populated` — can set all three fields
  - [ ] `test_review_result_to_dict_excludes_prompt_fields` — `to_dict()` output does not contain `system_prompt`, `user_prompt`, `rules_content_used`
- [ ] `uv run pytest` on the relevant test file — all pass

**Commit:** `feat: add prompt capture fields to ReviewResult`

### T7: Implement `_write_prompt_log()` in `review_client.py`

- [ ] In `src/squadron/review/review_client.py`, add `_write_prompt_log()`:
  - [ ] Signature: `_write_prompt_log(system_prompt, user_prompt, rules_content, model, profile, template_name) -> Path`
  - [ ] Create `~/.config/squadron/logs/` directory if it doesn't exist
  - [ ] Generate filename: `review-prompt-{YYYYMMDD-HHmmss}.md`
  - [ ] Write markdown with YAML frontmatter (template, model, profile, timestamp) and sections for system prompt, user prompt, injected rules
  - [ ] Return the file path
- [ ] Success: function creates a well-formed markdown file at the expected path
- [ ] `uv run pyright` and `uv run ruff check` pass

### T8: Tests for `_write_prompt_log()`

- [ ] In `tests/review/test_review_client.py`, add tests:
  - [ ] `test_write_prompt_log_creates_file` — call with sample data, verify file exists and contains expected sections (use `tmp_path` fixture to override log dir)
  - [ ] `test_write_prompt_log_filename_format` — verify filename matches `review-prompt-YYYYMMDD-HHmmss.md` pattern
  - [ ] `test_write_prompt_log_contains_metadata` — verify YAML frontmatter includes template, model, profile
  - [ ] `test_write_prompt_log_no_rules` — when `rules_content` is `None`, rules section shows "None"
- [ ] `uv run pytest tests/review/test_review_client.py -v` — all pass

**Commit:** `feat: add prompt log writer to review_client.py`

### T9: Wire prompt capture and logging into `_run_non_sdk_review()`

- [ ] In `_run_non_sdk_review()` in `review_client.py`:
  - [ ] At verbosity >= 2, populate `result.system_prompt`, `result.user_prompt`, `result.rules_content_used` on the `ReviewResult` before returning
  - [ ] At verbosity >= 3, call `_write_prompt_log()` *before* the API call and print the file path to stderr
- [ ] Success: at `-vv`, result has prompt fields populated; at `-vvv`, prompt log file is written and path printed
- [ ] `uv run pyright` and `uv run ruff check` pass

### T10: Tests for prompt capture and logging wiring

- [ ] In `tests/review/test_review_client.py`, add tests:
  - [ ] `test_verbosity_2_populates_prompt_fields` — call `run_review_with_profile` with `verbosity=2`, verify result has `system_prompt` and `user_prompt` set
  - [ ] `test_verbosity_1_no_prompt_fields` — call with `verbosity=1`, verify `system_prompt` is `None`
  - [ ] `test_verbosity_3_writes_prompt_log` — call with `verbosity=3`, verify `_write_prompt_log` is called (patch it)
  - [ ] `test_verbosity_3_prints_log_path` — call with `verbosity=3`, verify stderr contains the log file path
- [ ] `uv run pytest tests/review/test_review_client.py -v` — all pass

**Commit:** `feat: wire prompt capture and logging into non-SDK review path`

### T11: Wire scoped diff into `review_code()`

- [ ] In `src/squadron/cli/commands/review.py`, in `review_code()`:
  - [ ] Import `resolve_slice_diff_range` from `squadron.review.git_utils`
  - [ ] When `slice_number` is provided and `diff` flag is NOT explicitly set by the user:
    - [ ] Replace `diff = "main"` with `diff = resolve_slice_diff_range(int(slice_number), resolved_cwd)`
  - [ ] When `--diff` is explicitly provided, use that value (override takes precedence)
- [ ] Success: `sq review code 122` uses scoped diff; `sq review code 122 --diff HEAD~3` uses explicit diff
- [ ] `uv run pyright` and `uv run ruff check` pass

### T12: Tests for scoped diff in `review_code()`

- [ ] In `tests/review/test_cli_review.py`, add tests:
  - [ ] `test_review_code_slice_number_calls_resolve_diff` — invoke `review code 122`, verify `resolve_slice_diff_range` is called with `122`
  - [ ] `test_review_code_explicit_diff_overrides_resolution` — invoke `review code 122 --diff HEAD~3`, verify diff is `HEAD~3` and `resolve_slice_diff_range` is NOT called
  - [ ] `test_review_code_no_slice_number_no_resolution` — invoke `review code` without slice number, verify `resolve_slice_diff_range` is NOT called
- [ ] `uv run pytest tests/review/test_cli_review.py -v` — all pass

**Commit:** `feat: wire scoped diff resolution into review code command`

### T13: Add debug appendix to `_format_review_markdown()`

- [ ] In `src/squadron/cli/commands/review.py`, in `_format_review_markdown()`:
  - [ ] After the findings section, check if `result.system_prompt is not None`
  - [ ] If so, append a `## Debug: Prompt & Response` section with:
    - [ ] `### System Prompt` — `result.system_prompt`
    - [ ] `### User Prompt` — `result.user_prompt`
    - [ ] `### Rules Injected` — `result.rules_content_used or "None"`
    - [ ] `### Raw Response` — `result.raw_output`
- [ ] Success: when prompt fields are present, saved review file includes the debug appendix
- [ ] `uv run pyright` and `uv run ruff check` pass

### T14: Tests for debug appendix in review markdown

- [ ] In `tests/review/test_review_file.py`, add tests:
  - [ ] `test_debug_appendix_present_when_prompt_fields_set` — create `ReviewResult` with `system_prompt` set, verify `_format_review_markdown()` output contains `## Debug: Prompt & Response`
  - [ ] `test_debug_appendix_absent_when_prompt_fields_none` — create `ReviewResult` without prompt fields, verify output does NOT contain `## Debug: Prompt & Response`
  - [ ] `test_debug_appendix_shows_rules_none_when_no_rules` — set `system_prompt` but not `rules_content_used`, verify "None" appears in the rules section
  - [ ] `test_debug_appendix_contains_raw_output` — verify raw response is included in the appendix
- [ ] `uv run pytest tests/review/test_review_file.py -v` — all pass

**Commit:** `feat: add debug appendix to saved review markdown at -vv+`

### T15: Full validation pass

- [ ] `uv run pytest` — all tests pass (existing + new)
- [ ] `uv run pyright` — clean
- [ ] `uv run ruff check` — clean
- [ ] `uv run ruff format --check` — clean
- [ ] Verify no unintended changes to existing behavior:
  - [ ] `sq review list` still works
  - [ ] `sq review code --diff main --no-save` still works (no slice number, no resolution)

**Commit:** `chore: slice 127 validation pass`

### T16: Update slice status and documentation

- [ ] Update slice design `127-slice.scoped-code-review-prompt-logging.md`: set `status: complete`, update `dateUpdated`
- [ ] Update verification walkthrough in slice design with actual results
- [ ] Check off slice 127 in `100-slices.orchestration-v2.md`
- [ ] Update CHANGELOG.md with slice 127 changes
- [ ] Update DEVLOG.md with Phase 6 completion entry

**Commit:** `docs: mark slice 127 (Scoped Code Review & Prompt Logging) complete`
