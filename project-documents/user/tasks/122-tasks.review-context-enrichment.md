---
slice: review-context-enrichment
project: squadron
lld: user/slices/122-slice.review-context-enrichment.md
dependencies: [review-provider-model-selection]
projectState: Slice 126 complete. Parser in parsers.py uses _FINDING_RE and _SUMMARY_RE. review_client.py has _run_non_sdk_review() with rules_content injection. Three built-in templates (slice.yaml, tasks.yaml, code.yaml). review.py has _format_review_markdown() and _save_review_file().
dateCreated: 20260325
dateUpdated: 20260325
status: not_started
---

## Context Summary

- **Problem 1:** Reviews return CONCERNS/FAIL verdict with zero findings (issue #5) — parser drops non-standard finding formats
- **Problem 2:** Code reviews don't auto-inject applicable project rules (e.g. `rules/python.md`)
- **New features:** YAML alignment for review files, prompt debug output (`-vvv`), template-specific rule injection
- Key files:
  - `src/squadron/review/parsers.py` — `_FINDING_RE`, `_SUMMARY_RE`, `parse_review_output()`
  - `src/squadron/review/review_client.py` — `_run_non_sdk_review()`, rules injection at line 74
  - `src/squadron/review/templates/builtin/` — `slice.yaml`, `tasks.yaml`, `code.yaml`
  - `src/squadron/cli/commands/review.py` — `_format_review_markdown()`, `_save_review_file()`, `_run_review_command()`
- New file: `src/squadron/review/rules.py` — language detection and rules matching

---

## Tasks

### T1: Expand `_FINDING_RE` for broader format coverage

- [ ] In `src/squadron/review/parsers.py`, extend `_FINDING_RE` to also match:
  - [ ] `### CONCERN: Title` (colon separator, no brackets)
  - [ ] `**[CONCERN]** Title` (bold brackets, no heading marker)
  - [ ] `- [CONCERN] Title` (bullet-point findings)
- [ ] Keep existing `### [SEVERITY] Title` and `### SEVERITY Title` patterns
- [ ] Success: regex matches all five format variants without false positives
- [ ] `uv run pyright` and `uv run ruff check` pass

### T2: Tests for expanded `_FINDING_RE`

- [ ] In `tests/review/test_parsers.py` (create if not exists), add tests:
  - [ ] `test_finding_colon_separator` — `### CONCERN: My title` parses to CONCERN finding
  - [ ] `test_finding_bold_brackets` — `**[FAIL]** My title` parses to FAIL finding
  - [ ] `test_finding_bullet_point` — `- [CONCERN] My title` parses to CONCERN finding
  - [ ] `test_finding_standard_brackets` — existing format still parses correctly
  - [ ] `test_finding_standard_no_brackets` — `### CONCERN My title` still parses correctly
- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass

### T3: Add lenient fallback parsing to `parse_review_output()`

- [ ] In `parsers.py`, after `_extract_findings()` returns zero results and verdict is CONCERNS or FAIL:
  - [ ] Attempt lenient extraction: scan for lines containing severity keywords in paragraph context
  - [ ] If lenient parsing finds content, create findings from those blocks
  - [ ] If lenient parsing also finds nothing, synthesize a single finding:
    - [ ] Extract text between `## Summary` and next `##` heading (or end of string)
    - [ ] Create `ReviewFinding(severity=<matches verdict>, title="Unparsed review findings", description=<extracted text>)`
  - [ ] Track whether fallback was used: add `fallback_used: bool` to `ReviewResult` (default `False`)
- [ ] `uv run pyright` and `uv run ruff check` pass

### T4: Tests for fallback parsing

- [ ] Add to `tests/review/test_parsers.py`:
  - [ ] `test_fallback_synthesizes_finding` — CONCERNS verdict + no parseable findings → single synthesized finding
  - [ ] `test_fallback_not_triggered_on_pass` — PASS with no findings → no fallback, no synthesized finding
  - [ ] `test_fallback_used_flag` — `result.fallback_used` is `True` when fallback triggered
  - [ ] `test_lenient_finds_paragraph_findings` — CONCERNS with findings in paragraph format → lenient path recovers them
- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass

### T5: Add diagnostic logging for verdict/findings mismatches

- [ ] In `parsers.py`, add `_write_debug_log()` helper:
  - [ ] Writes to `~/.config/squadron/logs/review-debug.jsonl` (create dir on first write)
  - [ ] Called when: verdict is CONCERNS/FAIL AND structured parsing found zero findings (before fallback)
  - [ ] Called when: fallback parsing was triggered
  - [ ] JSON line fields: `ts`, `template`, `model`, `verdict`, `findings_parsed`, `fallback_used`, `raw_output`
  - [ ] Append-only; no rotation
- [ ] `uv run pyright` and `uv run ruff check` pass

### T6: Tests for diagnostic logging

- [ ] Add to `tests/review/test_parsers.py`:
  - [ ] `test_debug_log_written_on_mismatch` — CONCERNS + empty findings → log file written
  - [ ] `test_debug_log_not_written_on_clean_pass` — PASS with findings → no log write
  - [ ] Use `tmp_path` fixture to mock the log directory
- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass
- [ ] **Commit:** `fix: add lenient parsing, fallback findings, and debug logging for verdict mismatches`

### T7: Harden system prompts in all three templates

- [ ] In `src/squadron/review/templates/builtin/slice.yaml`, add to `system_prompt`:
  ```
  CRITICAL: Your verdict and findings MUST be consistent.
  - If verdict is CONCERNS or FAIL, include at least one finding with that severity.
  - If no CONCERN or FAIL findings exist, verdict MUST be PASS.
  - Every finding MUST use the exact format: ### [SEVERITY] Title
  ```
- [ ] Apply identical hardening to `tasks.yaml`
- [ ] Apply identical hardening to `code.yaml`
- [ ] `uv run ruff check` passes (YAML not checked, but verify files are valid YAML)

### T8: Test prompt hardening is present

- [ ] In `tests/review/test_templates.py` (create if not exists):
  - [ ] `test_slice_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
  - [ ] `test_tasks_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
  - [ ] `test_code_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
- [ ] `uv run pytest tests/review/test_templates.py -v` — all pass
- [ ] **Commit:** `feat: harden review template prompts for verdict/findings consistency`

### T9: Create `src/squadron/review/rules.py`

- [ ] Create `src/squadron/review/rules.py` with:
  - [ ] `resolve_rules_dir(cwd: str, config_rules_dir: str | None, cli_rules_dir: str | None) -> Path | None` — priority: CLI flag > config > `{cwd}/rules/` > `{cwd}/.claude/rules/` > None
  - [ ] `load_rules_frontmatter(rules_dir: Path) -> dict[str, list[str]]` — scan dir, parse YAML frontmatter `paths` field from each `.md` file; return `{filename: [glob_patterns]}`; files without `paths` use filename-based fallback (e.g. `python.md` → `["**/*.py"]`)
  - [ ] `detect_languages_from_paths(file_paths: list[str]) -> set[str]` — extract extensions from paths, return set of extension strings (e.g. `{".py", ".ts"}`)
  - [ ] `match_rules_files(extensions: set[str], rules_dir: Path, frontmatter: dict[str, list[str]]) -> list[Path]` — match extensions against glob patterns, return sorted list of matching rules file paths
  - [ ] `load_rules_content(rules_files: list[Path]) -> str` — read and concatenate content of each file with `\n\n---\n\n` separator
  - [ ] `get_template_rules(template_name: str, rules_dir: Path) -> str | None` — check for `review.md` and `review-{template_name}.md` in rules_dir; return concatenated content or None
- [ ] `uv run pyright` and `uv run ruff check` pass

### T10: Tests for `rules.py`

- [ ] Create `tests/review/test_rules.py`:
  - [ ] `test_resolve_rules_dir_cli_flag_wins` — CLI flag overrides all others
  - [ ] `test_resolve_rules_dir_config_wins_over_default` — config beats cwd default
  - [ ] `test_resolve_rules_dir_falls_back_to_cwd_rules` — uses `{cwd}/rules/` when it exists
  - [ ] `test_resolve_rules_dir_claude_rules_fallback` — uses `.claude/rules/` when `rules/` absent
  - [ ] `test_resolve_rules_dir_returns_none_when_none_exist` — returns None when no dir found
  - [ ] `test_detect_languages_from_diff_paths` — extracts `.py`, `.ts` from mixed path list
  - [ ] `test_match_rules_files_by_extension` — `.py` extension matches `python.md` (frontmatter paths `["**/*.py"]`)
  - [ ] `test_match_rules_files_filename_fallback` — `python.md` with no frontmatter paths matches `.py`
  - [ ] `test_get_template_rules_both_files` — general + template-specific both concatenated
  - [ ] `test_get_template_rules_general_only` — only `review.md` present → returned alone
  - [ ] `test_get_template_rules_none_present` → returns None
- [ ] `uv run pytest tests/review/test_rules.py -v` — all pass

### T11: Wire auto-detection into `review_code` command

- [ ] In `review.py`, in `review_code()`:
  - [ ] Import `resolve_rules_dir`, `detect_languages_from_paths`, `match_rules_files`, `load_rules_content`, `load_rules_frontmatter` from `squadron.review.rules`
  - [ ] After resolving `cwd` and existing `rules_path`, resolve `rules_dir` via `resolve_rules_dir()`
  - [ ] Extract file paths from `diff` input (parse `+++ b/` lines from `git diff` output) or `files` glob, or do shallow cwd scan if neither provided
  - [ ] Detect extensions → match rules files → concatenate auto-detected rules content
  - [ ] Combine: explicit `rules_content` (from `--rules`) + auto-detected content
  - [ ] Add `--rules-dir` CLI option: `typer.Option(None, "--rules-dir", help="Rules directory override")`
  - [ ] Add `--no-rules` CLI flag: `typer.Option(False, "--no-rules", help="Suppress all rule injection")`
  - [ ] When `--no-rules`: skip both explicit and auto-detected rules
- [ ] `uv run pyright` and `uv run ruff check` pass

### T12: Wire template-specific rules into all review commands

- [ ] In `review.py`, in `_run_review_command()`:
  - [ ] After existing rules_content resolution, call `get_template_rules(template_name, rules_dir)` if rules_dir resolved
  - [ ] Prepend template rules to any existing `rules_content` (template rules first, then explicit/auto-detected)
  - [ ] Thread `rules_dir` as parameter from callers to `_run_review_command()`
- [ ] Add `--rules-dir` option to `review_slice()` and `review_tasks()` commands (same as `review_code`)
- [ ] `uv run pyright` and `uv run ruff check` pass

### T13: Tests for rules wiring in review commands

- [ ] In `tests/cli/test_cli_review.py`:
  - [ ] `test_review_code_auto_detects_rules` — mock rules dir with `python.md`, run with `--diff`, verify rules_content passed to review
  - [ ] `test_review_code_no_rules_flag` — `--no-rules` suppresses all injection
  - [ ] `test_review_slice_template_rules_injected` — `rules/review-slice.md` present → injected
  - [ ] `test_review_code_explicit_and_auto_combined` — `--rules custom.md` + auto-detected both present
- [ ] `uv run pytest tests/cli/test_cli_review.py -v` — all pass
- [ ] **Commit:** `feat: add auto-detect language rules and template-specific rule injection`

### T14: Align review file YAML with file-naming-conventions

- [ ] In `review.py`, update `_format_review_markdown()`:
  - [ ] Add `layer: project` field
  - [ ] Add `sourceDocument: {input_file}` — use the primary input file path (first non-cwd input)
  - [ ] Add `aiModel: {model}` — use `result.model` (resolved model ID, not alias)
  - [ ] Add `status: complete`
  - [ ] Keep existing `slice`, `verdict` fields as squadron extensions
- [ ] Update `SliceInfo` usage to pass `input_file` through to `_format_review_markdown()`
- [ ] `uv run pyright` and `uv run ruff check` pass

### T15: Tests for review file YAML alignment

- [ ] In `tests/review/test_review_file.py` (create if not exists):
  - [ ] `test_format_review_markdown_has_layer` — output contains `layer: project`
  - [ ] `test_format_review_markdown_has_source_document` — output contains `sourceDocument:`
  - [ ] `test_format_review_markdown_has_ai_model` — `aiModel:` contains resolved model ID
  - [ ] `test_format_review_markdown_has_status` — output contains `status: complete`
- [ ] `uv run pytest tests/review/test_review_file.py -v` — all pass

### T16: Add prompt debug output (`-vvv`)

- [ ] In `review_client.py`, update `run_review_with_profile()` signature to accept `verbosity: int = 0`
- [ ] In `_run_non_sdk_review()`, at verbosity >= 3, before API call:
  - [ ] Print `[DEBUG] System Prompt:` followed by system_prompt to stderr
  - [ ] Print `[DEBUG] User Prompt:` followed by prompt to stderr
  - [ ] If rules_content: print `[DEBUG] Injected Rules:` followed by rules_content to stderr
- [ ] Thread `verbosity` from `_run_review_command()` → `_execute_review()` → `run_review_with_profile()`
- [ ] `uv run pyright` and `uv run ruff check` pass

### T17: Tests for prompt debug output

- [ ] In `tests/review/test_review_client.py` (create if not exists):
  - [ ] `test_debug_output_at_verbosity_3` — verbosity=3 → system prompt printed to stderr
  - [ ] `test_no_debug_output_at_verbosity_2` — verbosity=2 → nothing extra printed
  - [ ] `test_debug_rules_shown_when_present` — rules_content non-empty + verbosity=3 → rules section printed
- [ ] `uv run pytest tests/review/ -v` — all pass
- [ ] **Commit:** `feat: add -vvv prompt debug output and review file YAML alignment`

### T18: Full validation pass

- [ ] `uv run pytest` — all tests pass (0 failures)
- [ ] `uv run pyright` — 0 errors
- [ ] `uv run ruff check` — clean
- [ ] `uv run ruff format --check` — clean
- [ ] Verify grep: `grep -r "CRITICAL" src/squadron/review/templates/builtin/` — all three templates
- [ ] Manual: `sq review slice 122 --model minimax -vvv` — system prompt and user prompt displayed
- [ ] Manual: inspect saved review file — confirm `layer`, `sourceDocument`, `aiModel`, `status` present
- [ ] **Commit:** `chore: slice 122 validation pass`

### T19: Post-implementation — update slice status

- [ ] Mark slice 122 as complete in `project-documents/user/slices/122-slice.review-context-enrichment.md`
- [ ] Mark slice 122 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
- [ ] Update DEVLOG with completion entry
- [ ] **Commit:** `docs: mark slice 122 (Review Context Enrichment) complete`
