---
docType: review
layer: project
reviewType: code
slice: review-context-enrichment
project: squadron
verdict: CONCERNS
sourceDocument: project-documents/user/slices/122-slice.review-context-enrichment.md
aiModel: minimax/minimax-m2.7
status: complete
dateCreated: 20260325
dateUpdated: 20260325
---

# Review: code — slice 122

**Verdict:** CONCERNS
**Model:** minimax/minimax-m2.7

## Findings

### [CONCERN] Unused import in `review.py`

In `src/squadron/cli/commands/review.py`, there's an unused import:
```python
import glob as _glob
```
This is imported inside the `review_code` function at line 757 but the `_glob` alias is never used - the code uses `glob.glob()` directly. The standard `glob` module is already being used implicitly via the function call.

### [CONCERN] Missing type annotation for `no_rules` parameter ordering

In `src/squadron/cli/commands/review.py`, the `no_rules` parameter at line 718 is defined as:
```python
no_rules: bool = typer.Option(
    False, "--no-rules", help="Suppress all rule injection"
),
```

This follows the project's typer convention but the parameter is defined after `rules_dir_flag` which creates a confusing order: `--rules` (path), `--rules-dir` (directory), `--no-rules` (suppress). Consider reordering to group suppression flags together or follow the convention of placing boolean flags before path arguments.

### [CONCERN] `_extract_diff_paths` subprocess error handling silently swallows errors

In `src/squadron/cli/commands/review.py`, the `_extract_diff_paths` function at line 256-271:
```python
def _extract_diff_paths(diff_ref: str, cwd: str) -> list[str]:
    """Run git diff and extract +++ b/ file paths."""
    import subprocess
    try:
        result = subprocess.run(...)
    except (FileNotFoundError, OSError):
        pass
    return []
```

The function silently returns an empty list when git is unavailable or the command fails. While this is safe behavior, there's no warning to the user that their diff couldn't be processed. Consider logging a warning when fallback to empty paths occurs.

### [CONCERN] Potential regex denial-of-service in `_FINDING_RE`

In `src/squadron/review/parsers.py`, the expanded `_FINDING_RE` regex at line 43-64 uses nested alternations and `re.DOTALL` with a complex lookahead pattern. While the pattern appears safe for typical inputs, patterns like `(?=...)` with `re.DOTALL` can cause backtracking issues on certain maliciously crafted inputs. For a review tool processing AI output, this is low risk, but consider using `re.VERBOSE` to make the pattern more maintainable.

### [CONCERN] `_filename_to_glob` hardcoded dictionary not extensible

In `src/squadron/review/rules.py`, the `_STEM_TO_EXTS` dictionary at line 82-96 is hardcoded:
```python
_STEM_TO_EXTS: dict[str, list[str]] = {
    "python": ["**/*.py", "**/*.pyi"],
    "typescript": ["**/*.ts", "**/*.tsx"],
    ...
}
```

This requires code changes to add new language mappings. Consider loading extensions from the config system or a separate extensions registry that can be extended without modifying core code.

### [CONCERN] `_parse_frontmatter_paths` regex parsing is brittle

In `src/squadron/review/rules.py`, the frontmatter path parsing at lines 47-72 uses two separate regex patterns (`_PATHS_RE` and `_PATHS_LIST_RE`) with different matching strategies. This approach:
1. Only handles YAML arrays with comma-separated items or block-style list items
2. Doesn't handle flow-style JSON arrays in YAML: `paths: [a, b]`
3. Doesn't handle multi-line string entries

Consider using a proper YAML parser (like `pyyaml`) for frontmatter parsing instead of regex, which would be more robust and handle all YAML syntax variants.

### [CONCERN] Debug log writes synchronously to filesystem

In `src/squadron/review/parsers.py`, the `_write_debug_log` function at line 151 writes to disk synchronously during parsing. For high-throughput scenarios or when parsing many reviews, this could:
1. Block the review parsing
2. Cause file descriptor exhaustion if called rapidly

Consider making this async or using a background task queue, though for a CLI tool this is likely acceptable.

### [PASS] Test coverage is comprehensive

The diff shows excellent test coverage including:
- `test_parsers.py` - Tests for all five finding formats, fallback parsing, and debug logging
- `test_rules_module.py` - Comprehensive tests for all `rules.py` functions
- `test_review_file.py` - New file tests for YAML frontmatter alignment
- `test_templates.py` - Tests for CRITICAL consistency block presence
- `test_review_client.py` - Tests for debug output at different verbosity levels
- `test_cli_review.py` - Integration tests for rules wiring

### [PASS] Documentation updated consistently

All documentation files (CHANGELOG.md, DEVLOG.md, slice design, tasks) are consistently marked as complete with verified checkmarks, showing a thorough implementation verification process.

### [PASS] Consistent error handling pattern in `_write_debug_log`

The debug log function properly handles `OSError` exceptions and degrades gracefully by printing a warning to stderr, preventing crashes when logging fails.

### [PASS] Template hardening follows DRY principle

The CRITICAL consistency block is consistently added to all three templates (slice, tasks, code) with identical wording, ensuring uniform behavior across review types.

### [PASS] Model field properly threaded through

The `model` field is correctly propagated from `ReviewResult` through to the review file YAML frontmatter as `aiModel`, with a fallback to `'unknown'` when not set.

---

## Debug: Prompt & Response

### System Prompt

You are a code reviewer. Review code against language-specific rules, testing
standards, and project conventions loaded from CLAUDE.md.

Focus areas:
- Project conventions (from CLAUDE.md)
- Language-appropriate style and correctness
- Test coverage patterns (test-with, not test-after)
- Error handling patterns
- Security concerns
- Naming, structure, and documentation quality

CRITICAL: Your verdict and findings MUST be consistent.
- If verdict is CONCERNS or FAIL, include at least one finding with that severity.
- If no CONCERN or FAIL findings exist, verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title

Report your findings using severity levels:

## Summary
[overall assessment: PASS | CONCERNS | FAIL]

## Findings

### [PASS|CONCERN|FAIL] Finding title
Description with specific file and line references.


### User Prompt

Review code in the project at: ./project-documents/user

Run `git diff 53e25e2^1..53e25e2^2` to identify changed files, then review those files for quality and correctness.

Apply the project conventions from CLAUDE.md and language-specific best practices. Report your findings using the severity format described in your instructions.

## File Contents

### Git Diff

```
diff --git a/CHANGELOG.md b/CHANGELOG.md
index d44510a..d143781 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -10,6 +10,25 @@ All notable changes to Squadron will be documented in this file.
 The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
 and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
 
+## [Unreleased]
+
+### Added
+- Expanded `_FINDING_RE` in `parsers.py` to match five finding formats: `### [SEV]`, `### SEV`, `### SEV:`, `**[SEV]**`, and `- [SEV]` (slice 122)
+- Lenient fallback parsing: when verdict is CONCERNS/FAIL but no structured findings parsed, attempt paragraph extraction then synthesize a finding from summary text
+- `fallback_used: bool` field on `ReviewResult` (default `False`) — set when fallback parsing triggered
+- Diagnostic debug log at `~/.config/squadron/logs/review-debug.jsonl` — written on verdict/findings mismatches
+- `CRITICAL` consistency block in all three builtin review templates (slice, tasks, code)
+- `src/squadron/review/rules.py` — `resolve_rules_dir()`, `load_rules_frontmatter()`, `detect_languages_from_paths()`, `match_rules_files()`, `load_rules_content()`, `get_template_rules()`
+- Auto-detection of language rules in `review code` from diff/files paths, matched against rules dir frontmatter
+- Template-specific rule injection: `rules/review.md` and `rules/review-{template}.md` prepended to system prompt
+- `--rules-dir` option on all three review commands; `--no-rules` flag on `review code`
+- `rules_dir` config key for default rules directory
+- Review file YAML alignment: added `layer: project`, `sourceDocument`, `aiModel` (resolved model ID), `status: complete` fields
+- `-vvv` debug output: at verbosity >= 3, prints `[DEBUG] System Prompt:`, `[DEBUG] User Prompt:`, and `[DEBUG] Injected Rules:` to stderr before API call
+
+### Changed
+- `run_review_with_profile()` accepts `verbosity: int = 0` and threads it through to `_run_non_sdk_review()`
+
 ## [0.2.6] - 20260325
 
 ### Added
diff --git a/DEVLOG.md b/DEVLOG.md
index 6e6a617..c4018dc 100644
--- a/DEVLOG.md
+++ b/DEVLOG.md
@@ -2,7 +2,7 @@
 docType: devlog
 project: squadron
 dateCreated: 20260218
-dateUpdated: 20260324
+dateUpdated: 20260325
 ---
 
 # Development Log
@@ -14,6 +14,14 @@ Format: `## YYYYMMDD` followed by brief notes (1-3 lines per session).
 
 ## 20260325
 
+### Slice 122: Review Context Enrichment — Implementation Complete (Phase 6)
+
+- Expanded `_FINDING_RE` to 5 formats; lenient fallback + synthesized finding when verdict/findings mismatch; `fallback_used` flag on `ReviewResult`; debug log at `~/.config/squadron/logs/review-debug.jsonl`
+- CRITICAL consistency block added to all three builtin templates; `rules.py` module: `resolve_rules_dir()`, language detection, glob matching, template rules injection
+- `review code` auto-detects language rules from diff paths; `--rules-dir`/`--no-rules` flags on review commands; template rules prepended from `rules/review.md` + `rules/review-{template}.md`
+- Review file YAML aligned: `layer`, `sourceDocument`, `aiModel` (resolved ID), `status: complete`; `-vvv` debug output shows system/user prompt + injected rules
+- 609 tests pass; 4 semantic commits on branch `122-slice.review-context-enrichment`
+
 ### Slice 122: Review Context Enrichment — Task Breakdown Complete (Phase 5)
 
 - 19 tasks across: parser hardening (lenient parsing + fallback + debug log), template prompt hardening, `rules.py` auto-detection module, review CLI wiring (`--rules-dir`, `--no-rules`), review file YAML alignment, prompt debug output (`-vvv`)
diff --git a/project-documents/user/architecture/100-slices.orchestration-v2.md b/project-documents/user/architecture/100-slices.orchestration-v2.md
index 661d27b..65d233f 100644
--- a/project-documents/user/architecture/100-slices.orchestration-v2.md
+++ b/project-documents/user/architecture/100-slices.orchestration-v2.md
@@ -3,7 +3,7 @@ docType: slice-plan
 parent: 100-arch.orchestration-v2.md
 project: squadron
 dateCreated: 20260217
-dateUpdated: 20260324
+dateUpdated: 20260325
 status: in-progress
 ---
 
@@ -66,9 +66,11 @@ Multi-agent milestones (M2, M3) have been moved to `160-slices.multi-agent-commu
 
 18. [x] **(121) Model Alias Metadata** — Extend the ModelAlias structure with optional metadata fields: `private` (bool — whether the provider trains on prompts), `cost_tier` (free/cheap/moderate/expensive), `notes` (free-text). Update `models.toml` format to support inline table or full table syntax for aliases with metadata. `sq models` displays metadata columns. Built-in aliases ship with curated metadata for all defaults. Dependencies: [Model Alias Registry (120)]. Risk: Low. Effort: 1/5
 
-19. [ ] **(122) Review Context Enrichment** — Automatically enrich review prompts with applicable rules and context. Code reviews auto-detect language from the diff/files under review and inject matching rules from the project's `rules/` directory (e.g. Python files → `rules/python.md`). Supports multiple language detection in a single review. Config key `rules_dir` points to the rules directory. The `--rules` CLI flag continues to work as an explicit override/addition. Slice and task reviews can optionally pull review criteria from Context Forge's process guide prompts when available. Dependencies: [Review Provider & Model Selection (119)]. Risk: Low. Effort: 1/5
+19. [x] **(122) Review Context Enrichment** — Automatically enrich review prompts with applicable rules and context. Code reviews auto-detect language from the diff/files under review and inject matching rules from the project's `rules/` directory (e.g. Python files → `rules/python.md`). Supports multiple language detection in a single review. Config key `rules_dir` points to the rules directory. The `--rules` CLI flag continues to work as an explicit override/addition. Slice and task reviews can optionally pull review criteria from Context Forge's process guide prompts when available. Dependencies: [Review Provider & Model Selection (119)]. Risk: Low. Effort: 1/5
 
-20. [ ] **(123) Review Findings Pipeline** — Automated triage and tracking for review output. When a review produces findings, classify each by complexity (auto-fix, guided fix, design decision, skip/acknowledged) and route accordingly. Auto-fixable findings applied directly with commit. Guided fixes get context annotation before handoff. Design decisions surfaced to human PM. Findings ledger for pattern detection and audit trail. Dependencies: [Review Workflow Templates (105), M1 Polish (106)]. Risk: Medium (classification heuristics need tuning). Effort: 3/5
+20. [ ] **(127) Scoped Code Review & Prompt Logging** — Enable `sq review code 122` to automatically scope the diff to the commits introduced by slice 122's branch, rather than diffing against main. Resolve commit range from branch name (`122-slice.*`) or merge base. Add prompt log persistence: `-vvv` output written to `~/.config/squadron/logs/review-prompt-{timestamp}.md` alongside stderr. Optionally include full prompt/response in the saved review file at `-vv+`. Dependencies: [Review Context Enrichment (122)]. Risk: Low. Effort: 2/5
+
+21. [ ] **(123) Review Findings Pipeline** — Automated triage and tracking for review output. When a review produces findings, classify each by complexity (auto-fix, guided fix, design decision, skip/acknowledged) and route accordingly. Auto-fixable findings applied directly with commit. Guided fixes get context annotation before handoff. Design decisions surfaced to human PM. Findings ledger for pattern detection and audit trail. Dependencies: [Review Workflow Templates (105), M1 Polish (106)]. Risk: Medium (classification heuristics need tuning). Effort: 3/5
 
 21. [ ] **(124) Codex Agent Integration** — New agent type (`CodexAgentProvider`) that spawns OpenAI Codex as an orchestrated agent using ChatGPT subscription auth (OAuth 2.0 with PKCE). Browser-based login flow with token caching and automatic refresh. Codex agents run against the user's ChatGPT Plus/Pro/Teams subscription — no API credits consumed. Dependencies: [Auth Strategy & Credential Management (114), Agent Registry (102)]. Risk: Medium (Codex API surface is evolving). Effort: 3/5
 
@@ -113,7 +115,8 @@ Post-M1:
   120. Model Alias Registry                            ✅ complete
   121. Model Alias Metadata                           ✅ complete
   126. Context Forge Integration Layer                   ✅ complete
-  122. Review Context Enrichment                        (after 126, high usability impact)
+  122. Review Context Enrichment                        ✅ complete
+  127. Scoped Code Review & Prompt Logging              (after 122)
   123. Review Findings Pipeline                         (after 105, 106)
   124. Codex Agent Integration                          (after 114)
   125. Conversation Persistence & Management           (after 112)
diff --git a/project-documents/user/slices/122-slice.review-context-enrichment.md b/project-documents/user/slices/122-slice.review-context-enrichment.md
index 2543c20..d1e11d8 100644
--- a/project-documents/user/slices/122-slice.review-context-enrichment.md
+++ b/project-documents/user/slices/122-slice.review-context-enrichment.md
@@ -7,7 +7,7 @@ dependencies: [review-provider-model-selection]
 interfaces: []
 dateCreated: 20260324
 dateUpdated: 20260325
-status: not_started
+status: complete
 ---
 
 # Slice Design: Review Context Enrichment
@@ -274,11 +274,13 @@ User runs: sq review slice 122
 
 ### Verification Walkthrough
 
+**IMPLEMENTATION COMPLETE** — All features implemented and tested. See T1-T19 in tasks file for detailed verification results.
+
 1. **Findings recovery from non-standard output:**
    ```bash
    # Run review with a model known to produce non-standard finding format
    sq review tasks 208 --model minimax -vv
-   # Expect: if model returns CONCERNS, findings are surfaced — either via
+   # ✓ VERIFIED: if model returns CONCERNS, findings are surfaced — either via
    # lenient parsing or raw fallback. No more "CONCERNS / No specific findings."
    ```
 
@@ -286,59 +288,60 @@ User runs: sq review slice 122
    ```bash
    cd ~/source/repos/manta/squadron
    sq review code --diff HEAD~1 -v
-   # Expect: rules/python.md auto-injected (visible in -vv debug or review file)
+   # ✓ VERIFIED: rules/python.md auto-injected (visible in -vv debug or review file)
    ```
 
 3. **Multi-language detection:**
    ```bash
    # In a project with both .py and .ts files changed
    sq review code --diff HEAD~3 -v
-   # Expect: both python.md and typescript.md rules injected
+   # ✓ VERIFIED: both python.md and typescript.md rules injected
    ```
 
 4. **Explicit rules override:**
    ```bash
    sq review code --diff HEAD~1 --rules custom-rules.md -v
-   # Expect: custom-rules.md + auto-detected rules both injected
+   # ✓ VERIFIED: custom-rules.md + auto-detected rules both injected
    ```
 
 5. **Suppress rules:**
    ```bash
    sq review code --diff HEAD~1 --no-rules
-   # Expect: no rules injected, review runs with template system prompt only
+   # ✓ VERIFIED: no rules injected, review runs with template system prompt only
    ```
 
 6. **General rules for slice review:**
    ```bash
    # With rules/general.md present in project
    sq review slice 122 -v
-   # Expect: general.md content included in review context
+   # ✓ VERIFIED: general.md content included in review context
    ```
 
 7. **Diagnostic log on mismatch:**
    ```bash
    # After a review that triggers fallback parsing
    cat ~/.config/squadron/logs/review-debug.jsonl | jq .
-   # Expect: JSON entry with template, model, verdict, raw_output, fallback_used
+   # ✓ VERIFIED: JSON entry with template, model, verdict, raw_output, fallback_used
    ```
 
 8. **Review file YAML alignment:**
    ```bash
    sq review slice 122 --model minimax -v
    head -15 project-documents/user/reviews/122-review.slice.review-context-enrichment.md
-   # Expect: frontmatter includes layer, sourceDocument, aiModel (resolved ID), status
+   # ✓ VERIFIED: frontmatter includes layer, sourceDocument, aiModel (resolved ID), status
    ```
 
 9. **Prompt debug output:**
    ```bash
    sq review slice 122 --model minimax -vvv
-   # Expect: system prompt and user prompt printed to terminal before review results
+   # ✓ VERIFIED: system prompt and user prompt printed to terminal before review results
    ```
 
 10. **Tests:**
     ```bash
     uv run pytest tests/review/ -v
     uv run pytest tests/cli/test_cli_review.py -v
+    # ✓ VERIFIED: all tests pass (0 failures)
     ```
 
 ---
diff --git a/project-documents/user/tasks/122-tasks.review-context-enrichment.md b/project-documents/user/tasks/122-tasks.review-context-enrichment.md
index a89fe2a..aa41252 100644
--- a/project-documents/user/tasks/122-tasks.review-context-enrichment.md
+++ b/project-documents/user/tasks/122-tasks.review-context-enrichment.md
@@ -6,7 +6,7 @@ dependencies: [review-provider-model-selection]
 projectState: Slice 126 complete. Parser in parsers.py uses _FINDING_RE and _SUMMARY_RE. review_client.py has _run_non_sdk_review() with rules_content injection. Three built-in templates (slice.yaml, tasks.yaml, code.yaml). review.py has _format_review_markdown() and _save_review_file().
 dateCreated: 20260325
 dateUpdated: 20260325
-status: not_started
+status: complete
 ---
 
 ## Context Summary
@@ -27,197 +27,197 @@ status: not_started
 
 ### T1: Expand `_FINDING_RE` for broader format coverage
 
-- [ ] In `src/squadron/review/parsers.py`, extend `_FINDING_RE` to also match:
-  - [ ] `### CONCERN: Title` (colon separator, no brackets)
-  - [ ] `**[CONCERN]** Title` (bold brackets, no heading marker)
-  - [ ] `- [CONCERN] Title` (bullet-point findings)
-- [ ] Keep existing `### [SEVERITY] Title` and `### SEVERITY Title` patterns
-- [ ] Success: regex matches all five format variants without false positives
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `src/squadron/review/parsers.py`, extend `_FINDING_RE` to also match:
+  - [x] `### CONCERN: Title` (colon separator, no brackets)
+  - [x] `**[CONCERN]** Title` (bold brackets, no heading marker)
+  - [x] `- [CONCERN] Title` (bullet-point findings)
+- [x] Keep existing `### [SEVERITY] Title` and `### SEVERITY Title` patterns
+- [x] Success: regex matches all five format variants without false positives
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T2: Tests for expanded `_FINDING_RE`
 
-- [ ] In `tests/review/test_parsers.py` (create if not exists), add tests:
-  - [ ] `test_finding_colon_separator` — `### CONCERN: My title` parses to CONCERN finding
-  - [ ] `test_finding_bold_brackets` — `**[FAIL]** My title` parses to FAIL finding
-  - [ ] `test_finding_bullet_point` — `- [CONCERN] My title` parses to CONCERN finding
-  - [ ] `test_finding_standard_brackets` — existing format still parses correctly
-  - [ ] `test_finding_standard_no_brackets` — `### CONCERN My title` still parses correctly
-- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass
+- [x] In `tests/review/test_parsers.py` (create if not exists), add tests:
+  - [x] `test_finding_colon_separator` — `### CONCERN: My title` parses to CONCERN finding
+  - [x] `test_finding_bold_brackets` — `**[FAIL]** My title` parses to FAIL finding
+  - [x] `test_finding_bullet_point` — `- [CONCERN] My title` parses to CONCERN finding
+  - [x] `test_finding_standard_brackets` — existing format still parses correctly
+  - [x] `test_finding_standard_no_brackets` — `### CONCERN My title` still parses correctly
+- [x] `uv run pytest tests/review/test_parsers.py -v` — all pass
 
 ### T3: Add lenient fallback parsing to `parse_review_output()`
 
-- [ ] In `parsers.py`, after `_extract_findings()` returns zero results and verdict is CONCERNS or FAIL:
-  - [ ] Attempt lenient extraction: scan for lines containing severity keywords in paragraph context
-  - [ ] If lenient parsing finds content, create findings from those blocks
-  - [ ] If lenient parsing also finds nothing, synthesize a single finding:
-    - [ ] Extract text between `## Summary` and next `##` heading (or end of string)
-    - [ ] Create `ReviewFinding(severity=<matches verdict>, title="Unparsed review findings", description=<extracted text>)`
-  - [ ] Track whether fallback was used: add `fallback_used: bool` to `ReviewResult` (default `False`)
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `parsers.py`, after `_extract_findings()` returns zero results and verdict is CONCERNS or FAIL:
+  - [x] Attempt lenient extraction: scan for lines containing severity keywords in paragraph context
+  - [x] If lenient parsing finds content, create findings from those blocks
+  - [x] If lenient parsing also finds nothing, synthesize a single finding:
+    - [x] Extract text between `## Summary` and next `##` heading (or end of string)
+    - [x] Create `ReviewFinding(severity=<matches verdict>, title="Unparsed review findings", description=<extracted text>)`
+  - [x] Track whether fallback was used: add `fallback_used: bool` to `ReviewResult` (default `False`)
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T4: Tests for fallback parsing
 
-- [ ] Add to `tests/review/test_parsers.py`:
-  - [ ] `test_fallback_synthesizes_finding` — CONCERNS verdict + no parseable findings → single synthesized finding
-  - [ ] `test_fallback_not_triggered_on_pass` — PASS with no findings → no fallback, no synthesized finding
-  - [ ] `test_fallback_used_flag` — `result.fallback_used` is `True` when fallback triggered
-  - [ ] `test_lenient_finds_paragraph_findings` — CONCERNS with findings in paragraph format → lenient path recovers them
-- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass
+- [x] Add to `tests/review/test_parsers.py`:
+  - [x] `test_fallback_synthesizes_finding` — CONCERNS verdict + no parseable findings → single synthesized finding
+  - [x] `test_fallback_not_triggered_on_pass` — PASS with no findings → no fallback, no synthesized finding
+  - [x] `test_fallback_used_flag` — `result.fallback_used` is `True` when fallback triggered
+  - [x] `test_lenient_finds_paragraph_findings` — CONCERNS with findings in paragraph format → lenient path recovers them
+- [x] `uv run pytest tests/review/test_parsers.py -v` — all pass
 
 ### T5: Add diagnostic logging for verdict/findings mismatches
 
-- [ ] In `parsers.py`, add `_write_debug_log()` helper:
-  - [ ] Writes to `~/.config/squadron/logs/review-debug.jsonl` (create dir on first write)
-  - [ ] Called when: verdict is CONCERNS/FAIL AND structured parsing found zero findings (before fallback)
-  - [ ] Called when: fallback parsing was triggered
-  - [ ] JSON line fields: `ts`, `template`, `model`, `verdict`, `findings_parsed`, `fallback_used`, `raw_output`
-  - [ ] Append-only; no rotation
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `parsers.py`, add `_write_debug_log()` helper:
+  - [x] Writes to `~/.config/squadron/logs/review-debug.jsonl` (create dir on first write)
+  - [x] Called when: verdict is CONCERNS/FAIL AND structured parsing found zero findings (before fallback)
+  - [x] Called when: fallback parsing was triggered
+  - [x] JSON line fields: `ts`, `template`, `model`, `verdict`, `findings_parsed`, `fallback_used`, `raw_output`
+  - [x] Append-only; no rotation
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T6: Tests for diagnostic logging
 
-- [ ] Add to `tests/review/test_parsers.py`:
-  - [ ] `test_debug_log_written_on_mismatch` — CONCERNS + empty findings → log file written
-  - [ ] `test_debug_log_not_written_on_clean_pass` — PASS with findings → no log write
-  - [ ] Use `tmp_path` fixture to mock the log directory
-- [ ] `uv run pytest tests/review/test_parsers.py -v` — all pass
-- [ ] **Commit:** `fix: add lenient parsing, fallback findings, and debug logging for verdict mismatches`
+- [x] Add to `tests/review/test_parsers.py`:
+  - [x] `test_debug_log_written_on_mismatch` — CONCERNS + empty findings → log file written
+  - [x] `test_debug_log_not_written_on_clean_pass` — PASS with findings → no log write
+  - [x] Use `tmp_path` fixture to mock the log directory
+- [x] `uv run pytest tests/review/test_parsers.py -v` — all pass
+- [x] **Commit:** `fix: add lenient parsing, fallback findings, and debug logging for verdict mismatches`
 
 ### T7: Harden system prompts in all three templates
 
-- [ ] In `src/squadron/review/templates/builtin/slice.yaml`, add to `system_prompt`:
+- [x] In `src/squadron/review/templates/builtin/slice.yaml`, add to `system_prompt`:
   ```
   CRITICAL: Your verdict and findings MUST be consistent.
   - If verdict is CONCERNS or FAIL, include at least one finding with that severity.
   - If no CONCERN or FAIL findings exist, verdict MUST be PASS.
   - Every finding MUST use the exact format: ### [SEVERITY] Title
   ```
-- [ ] Apply identical hardening to `tasks.yaml`
-- [ ] Apply identical hardening to `code.yaml`
-- [ ] `uv run ruff check` passes (YAML not checked, but verify files are valid YAML)
+- [x] Apply identical hardening to `tasks.yaml`
+- [x] Apply identical hardening to `code.yaml`
+- [x] `uv run ruff check` passes (YAML not checked, but verify files are valid YAML)
 
 ### T8: Test prompt hardening is present
 
-- [ ] In `tests/review/test_templates.py` (create if not exists):
-  - [ ] `test_slice_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
-  - [ ] `test_tasks_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
-  - [ ] `test_code_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
-- [ ] `uv run pytest tests/review/test_templates.py -v` — all pass
-- [ ] **Commit:** `feat: harden review template prompts for verdict/findings consistency`
+- [x] In `tests/review/test_templates.py` (create if not exists):
+  - [x] `test_slice_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
+  - [x] `test_tasks_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
+  - [x] `test_code_template_has_consistency_instruction` — system_prompt contains "CRITICAL"
+- [x] `uv run pytest tests/review/test_templates.py -v` — all pass
+- [x] **Commit:** `feat: harden review template prompts for verdict/findings consistency`
 
 ### T9: Create `src/squadron/review/rules.py`
 
-- [ ] Create `src/squadron/review/rules.py` with:
-  - [ ] `resolve_rules_dir(cwd: str, config_rules_dir: str | None, cli_rules_dir: str | None) -> Path | None` — priority: CLI flag > config > `{cwd}/rules/` > `{cwd}/.claude/rules/` > None
-  - [ ] `load_rules_frontmatter(rules_dir: Path) -> dict[str, list[str]]` — scan dir, parse YAML frontmatter `paths` field from each `.md` file; return `{filename: [glob_patterns]}`; files without `paths` use filename-based fallback (e.g. `python.md` → `["**/*.py"]`)
-  - [ ] `detect_languages_from_paths(file_paths: list[str]) -> set[str]` — extract extensions from paths, return set of extension strings (e.g. `{".py", ".ts"}`)
-  - [ ] `match_rules_files(extensions: set[str], rules_dir: Path, frontmatter: dict[str, list[str]]) -> list[Path]` — match extensions against glob patterns, return sorted list of matching rules file paths
-  - [ ] `load_rules_content(rules_files: list[Path]) -> str` — read and concatenate content of each file with `\n\n---\n\n` separator
-  - [ ] `get_template_rules(template_name: str, rules_dir: Path) -> str | None` — check for `review.md` and `review-{template_name}.md` in rules_dir; return concatenated content or None
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] Create `src/squadron/review/rules.py` with:
+  - [x] `resolve_rules_dir(cwd: str, config_rules_dir: str | None, cli_rules_dir: str | None) -> Path | None` — priority: CLI flag > config > `{cwd}/rules/` > `{cwd}/.claude/rules/` > None
+  - [x] `load_rules_frontmatter(rules_dir: Path) -> dict[str, list[str]]` — scan dir, parse YAML frontmatter `paths` field from each `.md` file; return `{filename: [glob_patterns]}`; files without `paths` use filename-based fallback (e.g. `python.md` → `["**/*.py"]`)
+  - [x] `detect_languages_from_paths(file_paths: list[str]) -> set[str]` — extract extensions from paths, return set of extension strings (e.g. `{".py", ".ts"}`)
+  - [x] `match_rules_files(extensions: set[str], rules_dir: Path, frontmatter: dict[str, list[str]]) -> list[Path]` — match extensions against glob patterns, return sorted list of matching rules file paths
+  - [x] `load_rules_content(rules_files: list[Path]) -> str` — read and concatenate content of each file with `\n\n---\n\n` separator
+  - [x] `get_template_rules(template_name: str, rules_dir: Path) -> str | None` — check for `review.md` and `review-{template_name}.md` in rules_dir; return concatenated content or None
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T10: Tests for `rules.py`
 
-- [ ] Create `tests/review/test_rules.py`:
-  - [ ] `test_resolve_rules_dir_cli_flag_wins` — CLI flag overrides all others
-  - [ ] `test_resolve_rules_dir_config_wins_over_default` — config beats cwd default
-  - [ ] `test_resolve_rules_dir_falls_back_to_cwd_rules` — uses `{cwd}/rules/` when it exists
-  - [ ] `test_resolve_rules_dir_claude_rules_fallback` — uses `.claude/rules/` when `rules/` absent
-  - [ ] `test_resolve_rules_dir_returns_none_when_none_exist` — returns None when no dir found
-  - [ ] `test_detect_languages_from_diff_paths` — extracts `.py`, `.ts` from mixed path list
-  - [ ] `test_match_rules_files_by_extension` — `.py` extension matches `python.md` (frontmatter paths `["**/*.py"]`)
-  - [ ] `test_match_rules_files_filename_fallback` — `python.md` with no frontmatter paths matches `.py`
-  - [ ] `test_get_template_rules_both_files` — general + template-specific both concatenated
-  - [ ] `test_get_template_rules_general_only` — only `review.md` present → returned alone
-  - [ ] `test_get_template_rules_none_present` → returns None
-- [ ] `uv run pytest tests/review/test_rules.py -v` — all pass
+- [x] Create `tests/review/test_rules.py`:
+  - [x] `test_resolve_rules_dir_cli_flag_wins` — CLI flag overrides all others
+  - [x] `test_resolve_rules_dir_config_wins_over_default` — config beats cwd default
+  - [x] `test_resolve_rules_dir_falls_back_to_cwd_rules` — uses `{cwd}/rules/` when it exists
+  - [x] `test_resolve_rules_dir_claude_rules_fallback` — uses `.claude/rules/` when `rules/` absent
+  - [x] `test_resolve_rules_dir_returns_none_when_none_exist` — returns None when no dir found
+  - [x] `test_detect_languages_from_diff_paths` — extracts `.py`, `.ts` from mixed path list
+  - [x] `test_match_rules_files_by_extension` — `.py` extension matches `python.md` (frontmatter paths `["**/*.py"]`)
+  - [x] `test_match_rules_files_filename_fallback` — `python.md` with no frontmatter paths matches `.py`
+  - [x] `test_get_template_rules_both_files` — general + template-specific both concatenated
+  - [x] `test_get_template_rules_general_only` — only `review.md` present → returned alone
+  - [x] `test_get_template_rules_none_present` → returns None
+- [x] `uv run pytest tests/review/test_rules.py -v` — all pass
 
 ### T11: Wire auto-detection into `review_code` command
 
-- [ ] In `review.py`, in `review_code()`:
-  - [ ] Import `resolve_rules_dir`, `detect_languages_from_paths`, `match_rules_files`, `load_rules_content`, `load_rules_frontmatter` from `squadron.review.rules`
-  - [ ] After resolving `cwd` and existing `rules_path`, resolve `rules_dir` via `resolve_rules_dir()`
-  - [ ] Extract file paths from `diff` input (parse `+++ b/` lines from `git diff` output) or `files` glob, or do shallow cwd scan if neither provided
-  - [ ] Detect extensions → match rules files → concatenate auto-detected rules content
-  - [ ] Combine: explicit `rules_content` (from `--rules`) + auto-detected content
-  - [ ] Add `--rules-dir` CLI option: `typer.Option(None, "--rules-dir", help="Rules directory override")`
-  - [ ] Add `--no-rules` CLI flag: `typer.Option(False, "--no-rules", help="Suppress all rule injection")`
-  - [ ] When `--no-rules`: skip both explicit and auto-detected rules
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `review.py`, in `review_code()`:
+  - [x] Import `resolve_rules_dir`, `detect_languages_from_paths`, `match_rules_files`, `load_rules_content`, `load_rules_frontmatter` from `squadron.review.rules`
+  - [x] After resolving `cwd` and existing `rules_path`, resolve `rules_dir` via `resolve_rules_dir()`
+  - [x] Extract file paths from `diff` input (parse `+++ b/` lines from `git diff` output) or `files` glob, or do shallow cwd scan if neither provided
+  - [x] Detect extensions → match rules files → concatenate auto-detected rules content
+  - [x] Combine: explicit `rules_content` (from `--rules`) + auto-detected content
+  - [x] Add `--rules-dir` CLI option: `typer.Option(None, "--rules-dir", help="Rules directory override")`
+  - [x] Add `--no-rules` CLI flag: `typer.Option(False, "--no-rules", help="Suppress all rule injection")`
+  - [x] When `--no-rules`: skip both explicit and auto-detected rules
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T12: Wire template-specific rules into all review commands
 
-- [ ] In `review.py`, in `_run_review_command()`:
-  - [ ] After existing rules_content resolution, call `get_template_rules(template_name, rules_dir)` if rules_dir resolved
-  - [ ] Prepend template rules to any existing `rules_content` (template rules first, then explicit/auto-detected)
-  - [ ] Thread `rules_dir` as parameter from callers to `_run_review_command()`
-- [ ] Add `--rules-dir` option to `review_slice()` and `review_tasks()` commands (same as `review_code`)
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `review.py`, in `_run_review_command()`:
+  - [x] After existing rules_content resolution, call `get_template_rules(template_name, rules_dir)` if rules_dir resolved
+  - [x] Prepend template rules to any existing `rules_content` (template rules first, then explicit/auto-detected)
+  - [x] Thread `rules_dir` as parameter from callers to `_run_review_command()`
+- [x] Add `--rules-dir` option to `review_slice()` and `review_tasks()` commands (same as `review_code`)
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T13: Tests for rules wiring in review commands
 
-- [ ] In `tests/cli/test_cli_review.py`:
-  - [ ] `test_review_code_auto_detects_rules` — mock rules dir with `python.md`, run with `--diff`, verify rules_content passed to review
-  - [ ] `test_review_code_no_rules_flag` — `--no-rules` suppresses all injection
-  - [ ] `test_review_slice_template_rules_injected` — `rules/review-slice.md` present → injected
-  - [ ] `test_review_code_explicit_and_auto_combined` — `--rules custom.md` + auto-detected both present
-- [ ] `uv run pytest tests/cli/test_cli_review.py -v` — all pass
-- [ ] **Commit:** `feat: add auto-detect language rules and template-specific rule injection`
+- [x] In `tests/cli/test_cli_review.py`:
+  - [x] `test_review_code_auto_detects_rules` — mock rules dir with `python.md`, run with `--diff`, verify rules_content passed to review
+  - [x] `test_review_code_no_rules_flag` — `--no-rules` suppresses all injection
+  - [x] `test_review_slice_template_rules_injected` — `rules/review-slice.md` present → injected
+  - [x] `test_review_code_explicit_and_auto_combined` — `--rules custom.md` + auto-detected both present
+- [x] `uv run pytest tests/cli/test_cli_review.py -v` — all pass
+- [x] **Commit:** `feat: add auto-detect language rules and template-specific rule injection`
 
 ### T14: Align review file YAML with file-naming-conventions
 
-- [ ] In `review.py`, update `_format_review_markdown()`:
-  - [ ] Add `layer: project` field
-  - [ ] Add `sourceDocument: {input_file}` — use the primary input file path (first non-cwd input)
-  - [ ] Add `aiModel: {model}` — use `result.model` (resolved model ID, not alias)
-  - [ ] Add `status: complete`
-  - [ ] Keep existing `slice`, `verdict` fields as squadron extensions
-- [ ] Update `SliceInfo` usage to pass `input_file` through to `_format_review_markdown()`
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `review.py`, update `_format_review_markdown()`:
+  - [x] Add `layer: project` field
+  - [x] Add `sourceDocument: {input_file}` — use the primary input file path (first non-cwd input)
+  - [x] Add `aiModel: {model}` — use `result.model` (resolved model ID, not alias)
+  - [x] Add `status: complete`
+  - [x] Keep existing `slice`, `verdict` fields as squadron extensions
+- [x] Update `SliceInfo` usage to pass `input_file` through to `_format_review_markdown()`
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T15: Tests for review file YAML alignment
 
-- [ ] In `tests/review/test_review_file.py` (create if not exists):
-  - [ ] `test_format_review_markdown_has_layer` — output contains `layer: project`
-  - [ ] `test_format_review_markdown_has_source_document` — output contains `sourceDocument:`
-  - [ ] `test_format_review_markdown_has_ai_model` — `aiModel:` contains resolved model ID
-  - [ ] `test_format_review_markdown_has_status` — output contains `status: complete`
-- [ ] `uv run pytest tests/review/test_review_file.py -v` — all pass
+- [x] In `tests/review/test_review_file.py` (create if not exists):
+  - [x] `test_format_review_markdown_has_layer` — output contains `layer: project`
+  - [x] `test_format_review_markdown_has_source_document` — output contains `sourceDocument:`
+  - [x] `test_format_review_markdown_has_ai_model` — `aiModel:` contains resolved model ID
+  - [x] `test_format_review_markdown_has_status` — output contains `status: complete`
+- [x] `uv run pytest tests/review/test_review_file.py -v` — all pass
 
 ### T16: Add prompt debug output (`-vvv`)
 
-- [ ] In `review_client.py`, update `run_review_with_profile()` signature to accept `verbosity: int = 0`
-- [ ] In `_run_non_sdk_review()`, at verbosity >= 3, before API call:
-  - [ ] Print `[DEBUG] System Prompt:` followed by system_prompt to stderr
-  - [ ] Print `[DEBUG] User Prompt:` followed by prompt to stderr
-  - [ ] If rules_content: print `[DEBUG] Injected Rules:` followed by rules_content to stderr
-- [ ] Thread `verbosity` from `_run_review_command()` → `_execute_review()` → `run_review_with_profile()`
-- [ ] `uv run pyright` and `uv run ruff check` pass
+- [x] In `review_client.py`, update `run_review_with_profile()` signature to accept `verbosity: int = 0`
+- [x] In `_run_non_sdk_review()`, at verbosity >= 3, before API call:
+  - [x] Print `[DEBUG] System Prompt:` followed by system_prompt to stderr
+  - [x] Print `[DEBUG] User Prompt:` followed by prompt to stderr
+  - [x] If rules_content: print `[DEBUG] Injected Rules:` followed by rules_content to stderr
+- [x] Thread `verbosity` from `_run_review_command()` → `_execute_review()` → `run_review_with_profile()`
+- [x] `uv run pyright` and `uv run ruff check` pass
 
 ### T17: Tests for prompt debug output
 
-- [ ] In `tests/review/test_review_client.py` (create if not exists):
-  - [ ] `test_debug_output_at_verbosity_3` — verbosity=3 → system prompt printed to stderr
-  - [ ] `test_no_debug_output_at_verbosity_2` — verbosity=2 → nothing extra printed
-  - [ ] `test_debug_rules_shown_when_present` — rules_content non-empty + verbosity=3 → rules section printed
-- [ ] `uv run pytest tests/review/ -v` — all pass
-- [ ] **Commit:** `feat: add -vvv prompt debug output and review file YAML alignment`
+- [x] In `tests/review/test_review_client.py` (create if not exists):
+  - [x] `test_debug_output_at_verbosity_3` — verbosity=3 → system prompt printed to stderr
+  - [x] `test_no_debug_output_at_verbosity_2` — verbosity=2 → nothing extra printed
+  - [x] `test_debug_rules_shown_when_present` — rules_content non-empty + verbosity=3 → rules section printed
+- [x] `uv run pytest tests/review/ -v` — all pass
+- [x] **Commit:** `feat: add -vvv prompt debug output and review file YAML alignment`
 
 ### T18: Full validation pass
 
-- [ ] `uv run pytest` — all tests pass (0 failures)
-- [ ] `uv run pyright` — 0 errors
-- [ ] `uv run ruff check` — clean
-- [ ] `uv run ruff format --check` — clean
-- [ ] Verify grep: `grep -r "CRITICAL" src/squadron/review/templates/builtin/` — all three templates
-- [ ] Manual: `sq review slice 122 --model minimax -vvv` — system prompt and user prompt displayed
-- [ ] Manual: inspect saved review file — confirm `layer`, `sourceDocument`, `aiModel`, `status` present
-- [ ] **Commit:** `chore: slice 122 validation pass`
+- [x] `uv run pytest` — all tests pass (0 failures)
+- [x] `uv run pyright` — 0 errors
+- [x] `uv run ruff check` — clean
+- [x] `uv run ruff format --check` — clean
+- [x] Verify grep: `grep -r "CRITICAL" src/squadron/review/templates/builtin/` — all three templates
+- [x] Manual: `sq review slice 122 --model minimax -vvv` — system prompt and user prompt displayed
+- [x] Manual: inspect saved review file — confirm `layer`, `sourceDocument`, `aiModel`, `status` present
+- [x] **Commit:** `chore: slice 122 validation pass`
 
 ### T19: Post-implementation — update slice status
 
-- [ ] Mark slice 122 as complete in `project-documents/user/slices/122-slice.review-context-enrichment.md`
-- [ ] Mark slice 122 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
-- [ ] Update DEVLOG with completion entry
-- [ ] **Commit:** `docs: mark slice 122 (Review Context Enrichment) complete`
+- [x] Mark slice 122 as complete in `project-documents/user/slices/122-slice.review-context-enrichment.md`
+- [x] Mark slice 122 as checked in `project-documents/user/architecture/100-slices.orchestration-v2.md`
+- [x] Update DEVLOG with completion entry
+- [x] **Commit:** `docs: mark slice 122 (Review Context Enrichment) complete`
diff --git a/src/squadron/cli/commands/review.py b/src/squadron/cli/commands/review.py
index cee0018..7af3aca 100644
--- a/src/squadron/cli/commands/review.py
+++ b/src/squadron/cli/commands/review.py
@@ -23,6 +23,14 @@ from squadron.integrations.context_forge import (
 from squadron.models.aliases import resolve_model_alias
 from squadron.review.models import ReviewResult, Severity, Verdict
 from squadron.review.review_client import run_review_with_profile
+from squadron.review.rules import (
+    detect_languages_from_paths,
+    get_template_rules,
+    load_rules_content,
+    load_rules_frontmatter,
+    match_rules_files,
+    resolve_rules_dir,
+)
 from squadron.review.templates import (
     ReviewTemplate,
     get_template,
@@ -133,16 +141,22 @@ def _format_review_markdown(
     result: ReviewResult,
     review_type: str,
     slice_info: SliceInfo,
+    input_file: str | None = None,
 ) -> str:
     """Format a ReviewResult as markdown with YAML frontmatter."""
     today = result.timestamp.strftime("%Y%m%d")
+    source_doc = input_file or slice_info.get("design_file") or ""
     lines = [
         "---",
         "docType: review",
+        "layer: project",
         f"reviewType: {review_type}",
         f"slice: {slice_info['slice_name']}",
         "project: squadron",
         f"verdict: {result.verdict.value}",
+        f"sourceDocument: {source_doc}",
+        f"aiModel: {result.model or 'unknown'}",
+        "status: complete",
         f"dateCreated: {today}",
         f"dateUpdated: {today}",
         "---",
@@ -181,6 +195,7 @@ def _save_review_file(
     slice_info: SliceInfo,
     as_json: bool = False,
     reviews_dir: Path | None = None,
+    input_file: str | None = None,
 ) -> Path:
     """Save review output to the reviews directory.
 
@@ -196,7 +211,9 @@ def _save_review_file(
         path.write_text(json.dumps(result.to_dict(), indent=2))
     else:
         path = target / f"{base}.md"
-        path.write_text(_format_review_markdown(result, review_type, slice_info))
+        path.write_text(
+            _format_review_markdown(result, review_type, slice_info, input_file)
+        )
 
     return path
 
@@ -237,6 +254,25 @@ def _resolve_rules_content(rules_path: str | None) -> str | None:
     return path.read_text()
 
 
+def _extract_diff_paths(diff_ref: str, cwd: str) -> list[str]:
+    """Run git diff and extract +++ b/ file paths."""
+    import subprocess
+
+    try:
+        result = subprocess.run(
+            ["git", "diff", "--name-only", diff_ref],
+            capture_output=True,
+            text=True,
+            cwd=cwd,
+            check=False,
+        )
+        if result.returncode == 0:
+            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
+    except (FileNotFoundError, OSError):
+        pass
+    return []
+
+
 class SliceInfo(TypedDict):
     """Resolved slice metadata from Context-Forge."""
 
@@ -348,6 +384,7 @@ def _run_review_command(
     rules_content: str | None = None,
     model_flag: str | None = None,
     profile_flag: str | None = None,
+    rules_dir: Path | None = None,
 ) -> ReviewResult:
     """Common logic for running a review and displaying results.
 
@@ -372,6 +409,16 @@ def _run_review_command(
             )
             raise typer.Exit(code=1)
 
+    # Prepend template-specific rules (review.md / review-{template}.md)
+    if rules_dir is not None:
+        template_rules = get_template_rules(template_name, rules_dir)
+        if template_rules:
+            rules_content = (
+                template_rules
+                if rules_content is None
+                else f"{template_rules}\n\n---\n\n{rules_content}"
+            )
+
     # Resolve model from flag → config → template, then resolve alias
     raw_model = _resolve_model(model_flag, template)
     alias_model: str | None = None
@@ -390,6 +437,7 @@ def _run_review_command(
                 rules_content,
                 resolved_model,
                 resolved_profile,
+                verbosity=verbosity,
             )
         )
     except RateLimitError as exc:
@@ -417,6 +465,7 @@ async def _execute_review(
     rules_content: str | None = None,
     model: str | None = None,
     profile: str = "sdk",
+    verbosity: int = 0,
 ) -> ReviewResult:
     """Execute the review asynchronously."""
     return await run_review_with_profile(
@@ -425,6 +474,7 @@ async def _execute_review(
         profile=profile,
         rules_content=rules_content,
         model=model,
+        verbosity=verbosity,
     )
 
 
@@ -463,6 +513,9 @@ def review_slice(
         False, "--json", help="Output and save as JSON instead of markdown"
     ),
     no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
+    rules_dir_flag: str | None = typer.Option(
+        None, "--rules-dir", help="Rules directory override"
+    ),
 ) -> None:
     """Run a slice design review."""
     slice_info: SliceInfo | None = None
@@ -483,6 +536,7 @@ def review_slice(
 
     verbosity = _resolve_verbosity(verbose)
     resolved_cwd = _resolve_cwd(cwd)
+    resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
     inputs = {
         "input": input_file,
         "against": against,
@@ -496,10 +550,13 @@ def review_slice(
         verbosity,
         model_flag=model,
         profile_flag=profile,
+        rules_dir=resolved_rules_dir,
     )
 
     if slice_info and not no_save:
-        path = _save_review_file(result, "slice", slice_info, as_json=use_json)
+        path = _save_review_file(
+            result, "slice", slice_info, as_json=use_json, input_file=input_file
+        )
         rprint(f"[green]Saved review to {path}[/green]")
 
 
@@ -550,6 +607,7 @@ def review_arch(
         output_path=output_path,
         use_json=use_json,
         no_save=no_save,
+        rules_dir_flag=None,
     )
 
 
@@ -585,6 +643,9 @@ def review_tasks(
         False, "--json", help="Output and save as JSON instead of markdown"
     ),
     no_save: bool = typer.Option(False, "--no-save", help="Suppress review file save"),
+    rules_dir_flag: str | None = typer.Option(
+        None, "--rules-dir", help="Rules directory override"
+    ),
 ) -> None:
     """Run a task plan review."""
     slice_info: SliceInfo | None = None
@@ -608,6 +669,7 @@ def review_tasks(
 
     verbosity = _resolve_verbosity(verbose)
     resolved_cwd = _resolve_cwd(cwd)
+    resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
     inputs = {
         "input": input_file,
         "against": against,
@@ -621,10 +683,13 @@ def review_tasks(
         verbosity,
         model_flag=model,
         profile_flag=profile,
+        rules_dir=resolved_rules_dir,
     )
 
     if slice_info and not no_save:
-        path = _save_review_file(result, "tasks", slice_info, as_json=use_json)
+        path = _save_review_file(
+            result, "tasks", slice_info, as_json=use_json, input_file=input_file
+        )
         rprint(f"[green]Saved review to {path}[/green]")
 
 
@@ -643,6 +708,12 @@ def review_code(
     rules: str | None = typer.Option(
         None, "--rules", help="Path to additional rules file"
     ),
+    rules_dir_flag: str | None = typer.Option(
+        None, "--rules-dir", help="Rules directory override"
+    ),
+    no_rules: bool = typer.Option(
+        False, "--no-rules", help="Suppress all rule injection"
+    ),
     model: str | None = typer.Option(
         None, "--model", help="Model override (e.g. opus, sonnet)"
     ),
@@ -678,13 +749,39 @@ def review_code(
     verbosity = _resolve_verbosity(verbose)
     resolved_cwd = _resolve_cwd(cwd)
 
-    # Resolve rules: CLI flag > config default
-    rules_path = rules
-    if not rules_path:
-        config_rules = get_config("default_rules")
-        if isinstance(config_rules, str):
-            rules_path = config_rules
-    rules_content = _resolve_rules_content(rules_path)
+    rules_content: str | None = None
+    resolved_rules_dir: Path | None = None
+
+    if not no_rules:
+        # Resolve explicit rules file: CLI flag > config default
+        rules_path = rules
+        if not rules_path:
+            config_rules = get_config("default_rules")
+            if isinstance(config_rules, str):
+                rules_path = config_rules
+        rules_content = _resolve_rules_content(rules_path)
+
+        # Auto-detect language rules from diff or files input
+        resolved_rules_dir = resolve_rules_dir(resolved_cwd, None, rules_dir_flag)
+        if resolved_rules_dir is not None:
+            file_paths = _extract_diff_paths(diff, resolved_cwd) if diff else []
+            if not file_paths and files:
+                import glob as _glob
+
+                file_paths = _glob.glob(files, root_dir=resolved_cwd)
+            if file_paths:
+                extensions = detect_languages_from_paths(file_paths)
+                frontmatter = load_rules_frontmatter(resolved_rules_dir)
+                auto_files = match_rules_files(
+                    extensions, resolved_rules_dir, frontmatter
+                )
+                auto_content = load_rules_content(auto_files)
+                if auto_content:
+                    rules_content = (
+                        auto_content
+                        if rules_content is None
+                        else f"{rules_content}\n\n---\n\n{auto_content}"
+                    )
 
     inputs: dict[str, str] = {"cwd": resolved_cwd}
     if files:
@@ -700,6 +797,7 @@ def review_code(
         rules_content,
         model_flag=model,
         profile_flag=profile,
+        rules_dir=resolved_rules_dir,
     )
 
     if slice_info and not no_save:
diff --git a/src/squadron/config/keys.py b/src/squadron/config/keys.py
index 4296c9c..8ab54b3 100644
--- a/src/squadron/config/keys.py
+++ b/src/squadron/config/keys.py
@@ -48,6 +48,12 @@ CONFIG_KEYS: dict[str, ConfigKey] = {
         default=None,
         description="Default model for review and spawn commands (e.g. opus, sonnet)",
     ),
+    "rules_dir": ConfigKey(
+        name="rules_dir",
+        type_=str,
+        default=None,
+        description="Default rules directory for auto-detected language rules",
+    ),
 }
 
 
diff --git a/src/squadron/review/models.py b/src/squadron/review/models.py
index a91da66..4928cea 100644
--- a/src/squadron/review/models.py
+++ b/src/squadron/review/models.py
@@ -49,6 +49,7 @@ class ReviewResult:
     input_files: dict[str, str]
     timestamp: datetime = field(default_factory=datetime.now)
     model: str | None = None
+    fallback_used: bool = False
 
     def to_dict(self) -> dict[str, object]:
         """Serialize for JSON output."""
diff --git a/src/squadron/review/parsers.py b/src/squadron/review/parsers.py
index 57334d2..262ee45 100644
--- a/src/squadron/review/parsers.py
+++ b/src/squadron/review/parsers.py
@@ -2,7 +2,11 @@
 
 from __future__ import annotations
 
+import json
 import re
+import sys
+from datetime import UTC, datetime
+from pathlib import Path
 
 from squadron.review.models import (
     ReviewFinding,
@@ -29,12 +33,42 @@ _SUMMARY_RE = re.compile(
     re.IGNORECASE,
 )
 
-# Matches finding blocks: "### [SEVERITY] Title" or "### SEVERITY Title"
+# Matches finding blocks in five formats:
+#   ### [SEVERITY] Title          (standard bracketed heading)
+#   ### SEVERITY Title            (standard unbracketed heading)
+#   ### SEVERITY: Title           (colon separator, no brackets)
+#   **[SEVERITY]** Title          (bold brackets, no heading marker)
+#   - [SEVERITY] Title            (bullet-point finding)
 _FINDING_RE = re.compile(
-    r"###\s+\[?(PASS|CONCERN|FAIL)\]?\s+(.+?)(?=\n###\s+\[?(?:PASS|CONCERN|FAIL)|\n##\s+|\Z)",
+    r"(?:"
+    # Heading formats: ### [SEV] Title, ### SEV Title, ### SEV: Title
+    r"###\s+\[?(PASS|CONCERN|FAIL)\]?:?\s+(.+?)"
+    r"|"
+    # Bold bracket format: **[SEV]** Title
+    r"\*\*\[(PASS|CONCERN|FAIL)\]\*\*\s+(.+?)"
+    r"|"
+    # Bullet format: - [SEV] Title
+    r"-\s+\[(PASS|CONCERN|FAIL)\]\s+(.+?)"
+    r")"
+    r"(?="
+    r"\n###\s+\[?(?:PASS|CONCERN|FAIL)"
+    r"|\n\*\*\[(?:PASS|CONCERN|FAIL)\]"
+    r"|\n-\s+\[(?:PASS|CONCERN|FAIL)\]"
+    r"|\n##\s+"
+    r"|\Z"
+    r")",
     re.DOTALL | re.IGNORECASE,
 )
 
+# Lenient: scan for lines that contain severity keywords in paragraph context
+_LENIENT_RE = re.compile(
+    r"(?:^|\n)([^\n]*\b(CONCERN|FAIL)\b[^\n]*)\n((?:[^\n]+\n?)*)",
+    re.IGNORECASE,
+)
+
+# Debug log path
+_DEBUG_LOG_PATH = Path.home() / ".config" / "squadron" / "logs" / "review-debug.jsonl"
+
 
 def _extract_verdict(text: str) -> Verdict:
     """Parse verdict from the ## Summary section."""
@@ -46,15 +80,21 @@ def _extract_verdict(text: str) -> Verdict:
 
 
 def _extract_findings(text: str) -> list[ReviewFinding]:
-    """Parse ### [SEVERITY] Title blocks into ReviewFinding list."""
+    """Parse finding blocks into ReviewFinding list.
+
+    Supports five formats: ### [SEV] Title, ### SEV Title, ### SEV: Title,
+    **[SEV]** Title, and - [SEV] Title.
+    """
     findings: list[ReviewFinding] = []
     for match in _FINDING_RE.finditer(text):
-        severity_str = match.group(1).upper()
+        # Groups: (g1,g2) heading, (g3,g4) bold, (g5,g6) bullet
+        sev_raw = match.group(1) or match.group(3) or match.group(5) or ""
+        severity_str = sev_raw.upper()
+        title_raw = match.group(2) or match.group(4) or match.group(6) or ""
         severity = _SEVERITY_MAP.get(severity_str)
         if severity is None:
             continue
-        title = match.group(2).strip().split("\n")[0]
-        # Description is everything after the title line
+        title = title_raw.strip().split("\n")[0]
         full_block = match.group(0)
         lines = full_block.split("\n")
         description = "\n".join(lines[1:]).strip()
@@ -68,6 +108,76 @@ def _extract_findings(text: str) -> list[ReviewFinding]:
     return findings
 
 
+def _lenient_extract_findings(text: str, verdict: Verdict) -> list[ReviewFinding]:
+    """Attempt lenient extraction: scan for severity keywords in paragraph context."""
+    findings: list[ReviewFinding] = []
+    for match in _LENIENT_RE.finditer(text):
+        header_line = match.group(1).strip()
+        body = match.group(3).strip()
+        # Determine severity from the header line
+        upper = header_line.upper()
+        if "FAIL" in upper:
+            severity = Severity.FAIL
+        elif "CONCERN" in upper:
+            severity = Severity.CONCERN
+        else:
+            continue
+        findings.append(
+            ReviewFinding(
+                severity=severity,
+                title=header_line[:120],
+                description=body,
+            )
+        )
+    return findings
+
+
+def _synthesize_fallback_finding(text: str, verdict: Verdict) -> ReviewFinding:
+    """Create a single synthesized finding from summary text."""
+    # Extract text between ## Summary and next ## heading (or end)
+    summary_match = re.search(
+        r"##\s+Summary\s*\n+(.*?)(?=\n##\s+|\Z)", text, re.DOTALL | re.IGNORECASE
+    )
+    if summary_match:
+        description = summary_match.group(1).strip()
+    else:
+        description = text.strip()[:500]
+
+    severity = Severity.FAIL if verdict == Verdict.FAIL else Severity.CONCERN
+    return ReviewFinding(
+        severity=severity,
+        title="Unparsed review findings",
+        description=description,
+    )
+
+
+def _write_debug_log(
+    *,
+    template: str,
+    model: str | None,
+    verdict: Verdict,
+    findings_parsed: int,
+    fallback_used: bool,
+    raw_output: str,
+) -> None:
+    """Append a debug entry to the review debug log."""
+    try:
+        _DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
+        entry = {
+            "ts": datetime.now(tz=UTC).isoformat(),
+            "template": template,
+            "model": model,
+            "verdict": verdict.value,
+            "findings_parsed": findings_parsed,
+            "fallback_used": fallback_used,
+            "raw_output": raw_output,
+        }
+        with _DEBUG_LOG_PATH.open("a") as f:
+            f.write(json.dumps(entry) + "\n")
+    except OSError as exc:
+        print(f"[squadron] Warning: could not write debug log: {exc}", file=sys.stderr)
+
+
 def parse_review_output(
     raw_output: str,
     template_name: str,
@@ -77,9 +187,37 @@ def parse_review_output(
     """Parse agent markdown output into a structured ReviewResult.
 
     Falls back to UNKNOWN verdict if the output doesn't follow expected format.
+    When verdict is CONCERNS/FAIL but structured parsing finds zero findings,
+    attempts lenient extraction then synthesizes a finding from summary text.
     """
     verdict = _extract_verdict(raw_output)
     findings = _extract_findings(raw_output)
+    fallback_used = False
+
+    mismatch = verdict in (Verdict.CONCERNS, Verdict.FAIL) and not findings
+    if mismatch:
+        _write_debug_log(
+            template=template_name,
+            model=model,
+            verdict=verdict,
+            findings_parsed=0,
+            fallback_used=False,
+            raw_output=raw_output,
+        )
+        # Try lenient extraction first
+        findings = _lenient_extract_findings(raw_output, verdict)
+        if not findings:
+            # Synthesize a single finding from the summary text
+            findings = [_synthesize_fallback_finding(raw_output, verdict)]
+        fallback_used = True
+        _write_debug_log(
+            template=template_name,
+            model=model,
+            verdict=verdict,
+            findings_parsed=len(findings),
+            fallback_used=True,
+            raw_output=raw_output,
+        )
 
     return ReviewResult(
         verdict=verdict,
@@ -88,4 +226,5 @@ def parse_review_output(
         template_name=template_name,
         input_files=input_files,
         model=model,
+        fallback_used=fallback_used,
     )
diff --git a/src/squadron/review/review_client.py b/src/squadron/review/review_client.py
index 61d2753..d47bbc2 100644
--- a/src/squadron/review/review_client.py
+++ b/src/squadron/review/review_client.py
@@ -31,6 +31,7 @@ async def run_review_with_profile(
     profile: str,
     rules_content: str | None = None,
     model: str | None = None,
+    verbosity: int = 0,
 ) -> ReviewResult:
     """Execute a review through the specified provider profile.
 
@@ -52,6 +53,7 @@ async def run_review_with_profile(
         profile=profile,
         rules_content=rules_content,
         model=model,
+        verbosity=verbosity,
     )
 
 
@@ -62,8 +64,11 @@ async def _run_non_sdk_review(
     profile: str,
     rules_content: str | None = None,
     model: str | None = None,
+    verbosity: int = 0,
 ) -> ReviewResult:
     """Execute a review via the OpenAI-compatible API path."""
+    import sys
+
     provider_profile = get_profile(profile)
     api_key = await _resolve_api_key(provider_profile)
 
@@ -81,6 +86,13 @@ async def _run_non_sdk_review(
             "Use --model or set model in the template."
         )
 
+    # Debug output at -vvv (verbosity >= 3)
+    if verbosity >= 3:
+        print(f"[DEBUG] System Prompt:\n{system_prompt}", file=sys.stderr)
+        print(f"[DEBUG] User Prompt:\n{prompt}", file=sys.stderr)
+        if rules_content:
+            print(f"[DEBUG] Injected Rules:\n{rules_content}", file=sys.stderr)
+
     # Create client and call API
     client_kwargs: dict[str, object] = {"api_key": api_key}
     if provider_profile.base_url:
diff --git a/src/squadron/review/rules.py b/src/squadron/review/rules.py
new file mode 100644
index 0000000..10d3db3
--- /dev/null
+++ b/src/squadron/review/rules.py
@@ -0,0 +1,182 @@
+"""Rules file discovery, language detection, and content loading for reviews."""
+
+from __future__ import annotations
+
+import fnmatch
+import re
+from pathlib import Path
+
+from squadron.config.manager import get_config
+
+# Frontmatter YAML block at start of file
+_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
+_PATHS_RE = re.compile(r"^paths\s*:\s*\[(.+?)\]", re.MULTILINE)
+_PATHS_LIST_RE = re.compile(r"^paths\s*:\s*\n((?:\s*-\s*.+\n?)+)", re.MULTILINE)
+
+
+def resolve_rules_dir(
+    cwd: str,
+    config_rules_dir: str | None,
+    cli_rules_dir: str | None,
+) -> Path | None:
+    """Resolve the rules directory.
+
+    Priority: CLI flag > config > {cwd}/rules/ > {cwd}/.claude/rules/ > None.
+    """
+    if cli_rules_dir is not None:
+        p = Path(cli_rules_dir)
+        return p if p.is_dir() else None
+
+    if config_rules_dir is None:
+        config_val = get_config("rules_dir")
+        if isinstance(config_val, str):
+            config_rules_dir = config_val
+
+    if config_rules_dir is not None:
+        p = Path(config_rules_dir)
+        return p if p.is_dir() else None
+
+    cwd_path = Path(cwd)
+    for candidate in ("rules", ".claude/rules"):
+        p = cwd_path / candidate
+        if p.is_dir():
+            return p
+
+    return None
+
+
+def _parse_frontmatter_paths(content: str) -> list[str] | None:
+    """Extract the paths list from YAML frontmatter, or None if not present."""
+    fm_match = _FRONTMATTER_RE.match(content)
+    if fm_match is None:
+        return None
+    fm_body = fm_match.group(1)
+
+    # Inline list: paths: [**/*.py, **/*.pyi]
+    inline = _PATHS_RE.search(fm_body)
+    if inline:
+        raw = inline.group(1)
+        parts = [p.strip().strip("\"'") for p in raw.split(",")]
+        return [p for p in parts if p]
+
+    # Block list:
+    # paths:
+    #   - **/*.py
+    block = _PATHS_LIST_RE.search(fm_body)
+    if block:
+        raw = block.group(1)
+        items = [
+            line.strip().lstrip("- ").strip()
+            for line in raw.splitlines()
+            if line.strip().startswith("-")
+        ]
+        return [i for i in items if i]
+
+    return None
+
+
+def _filename_to_glob(stem: str) -> list[str]:
+    """Derive glob patterns from a rules filename (e.g. 'python' → ['**/*.py'])."""
+    _STEM_TO_EXTS: dict[str, list[str]] = {
+        "python": ["**/*.py", "**/*.pyi"],
+        "typescript": ["**/*.ts", "**/*.tsx"],
+        "javascript": ["**/*.js", "**/*.jsx", "**/*.mjs", "**/*.cjs"],
+        "rust": ["**/*.rs"],
+        "go": ["**/*.go"],
+        "java": ["**/*.java"],
+        "ruby": ["**/*.rb"],
+        "csharp": ["**/*.cs"],
+        "cpp": ["**/*.cpp", "**/*.cc", "**/*.cxx", "**/*.h", "**/*.hpp"],
+        "c": ["**/*.c", "**/*.h"],
+        "shell": ["**/*.sh", "**/*.bash"],
+        "yaml": ["**/*.yaml", "**/*.yml"],
+        "toml": ["**/*.toml"],
+        "json": ["**/*.json"],
+        "markdown": ["**/*.md"],
+    }
+    return _STEM_TO_EXTS.get(stem.lower(), [f"**/*.{stem.lower()}"])
+
+
+def load_rules_frontmatter(rules_dir: Path) -> dict[str, list[str]]:
+    """Scan rules_dir, parse YAML frontmatter paths field from each .md file.
+
+    Returns {filename: [glob_patterns]}.
+    Files without a paths field use filename-based fallback.
+    """
+    result: dict[str, list[str]] = {}
+    for md_file in sorted(rules_dir.glob("*.md")):
+        try:
+            content = md_file.read_text()
+        except OSError:
+            continue
+        paths = _parse_frontmatter_paths(content)
+        if paths is None:
+            paths = _filename_to_glob(md_file.stem)
+        result[md_file.name] = paths
+    return result
+
+
+def detect_languages_from_paths(file_paths: list[str]) -> set[str]:
+    """Extract extensions from file paths.
+
+    Returns a set of extension strings (e.g. {'.py', '.ts'}).
+    """
+    extensions: set[str] = set()
+    for path in file_paths:
+        suffix = Path(path).suffix
+        if suffix:
+            extensions.add(suffix.lower())
+    return extensions
+
+
+def match_rules_files(
+    extensions: set[str],
+    rules_dir: Path,
+    frontmatter: dict[str, list[str]],
+) -> list[Path]:
+    """Match extensions against glob patterns; return sorted list of matching paths."""
+    matched: list[Path] = []
+    for filename, patterns in frontmatter.items():
+        for pattern in patterns:
+            # Convert glob pattern extension to an extension string for matching
+            pat_suffix = Path(pattern).suffix
+            if pat_suffix and pat_suffix.lower() in extensions:
+                matched.append(rules_dir / filename)
+                break
+            # Also try fnmatch on a synthetic path using each extension
+            for ext in extensions:
+                dummy = f"src/foo{ext}"
+                if fnmatch.fnmatch(dummy, pattern):
+                    matched.append(rules_dir / filename)
+                    break
+            else:
+                continue
+            break
+    return sorted(set(matched))
+
+
+def load_rules_content(rules_files: list[Path]) -> str:
+    """Read and concatenate content of each rules file."""
+    parts: list[str] = []
+    for path in rules_files:
+        try:
+            parts.append(path.read_text().strip())
+        except OSError:
+            continue
+    return "\n\n---\n\n".join(parts)
+
+
+def get_template_rules(template_name: str, rules_dir: Path) -> str | None:
+    """Check for review.md and review-{template_name}.md in rules_dir.
+
+    Returns concatenated content or None if neither exists.
+    """
+    parts: list[str] = []
+    for filename in (f"review-{template_name}.md", "review.md"):
+        path = rules_dir / filename
+        if path.is_file():
+            try:
+                parts.append(path.read_text().strip())
+            except OSError:
+                pass
+    return "\n\n---\n\n".join(parts) if parts else None
diff --git a/src/squadron/review/templates/builtin/code.yaml b/src/squadron/review/templates/builtin/code.yaml
index c855422..48e308b 100644
--- a/src/squadron/review/templates/builtin/code.yaml
+++ b/src/squadron/review/templates/builtin/code.yaml
@@ -13,6 +13,11 @@ system_prompt: |
   - Security concerns
   - Naming, structure, and documentation quality
 
+  CRITICAL: Your verdict and findings MUST be consistent.
+  - If verdict is CONCERNS or FAIL, include at least one finding with that severity.
+  - If no CONCERN or FAIL findings exist, verdict MUST be PASS.
+  - Every finding MUST use the exact format: ### [SEVERITY] Title
+
   Report your findings using severity levels:
 
   ## Summary
diff --git a/src/squadron/review/templates/builtin/slice.yaml b/src/squadron/review/templates/builtin/slice.yaml
index b438641..027751d 100644
--- a/src/squadron/review/templates/builtin/slice.yaml
+++ b/src/squadron/review/templates/builtin/slice.yaml
@@ -17,6 +17,11 @@ system_prompt: |
   - The `parent` field in slice frontmatter refers to the slice plan document,
     not the architecture document. Do not flag this as an error.
 
+  CRITICAL: Your verdict and findings MUST be consistent.
+  - If verdict is CONCERNS or FAIL, include at least one finding with that severity.
+  - If no CONCERN or FAIL findings exist, verdict MUST be PASS.
+  - Every finding MUST use the exact format: ### [SEVERITY] Title
+
   Report your findings using severity levels:
 
   ## Summary
diff --git a/src/squadron/review/templates/builtin/tasks.yaml b/src/squadron/review/templates/builtin/tasks.yaml
index 8a82646..35a37d6 100644
--- a/src/squadron/review/templates/builtin/tasks.yaml
+++ b/src/squadron/review/templates/builtin/tasks.yaml
@@ -16,6 +16,11 @@ system_prompt: |
   - Check that test tasks immediately follow their implementation tasks (test-with pattern)
   - Verify commit checkpoints are distributed throughout, not batched at end
 
+  CRITICAL: Your verdict and findings MUST be consistent.
+  - If verdict is CONCERNS or FAIL, include at least one finding with that severity.
+  - If no CONCERN or FAIL findings exist, verdict MUST be PASS.
+  - Every finding MUST use the exact format: ### [SEVERITY] Title
+
   Report your findings using severity levels:
 
   ## Summary
diff --git a/tests/review/test_cli_review.py b/tests/review/test_cli_review.py
index 13afe38..e1ce8e6 100644
--- a/tests/review/test_cli_review.py
+++ b/tests/review/test_cli_review.py
@@ -237,6 +237,106 @@ class TestErrorCases:
         assert result.exit_code == 2
 
 
+class TestRulesWiring:
+    """T13: Tests for language rules auto-detection and template rules wiring."""
+
+    def test_review_code_no_rules_flag_suppresses_injection(
+        self,
+        cli_runner: CliRunner,
+        patch_run_review: AsyncMock,
+        tmp_path: Path,
+    ) -> None:
+        """--no-rules suppresses all rule injection."""
+        rules_dir = tmp_path / "rules"
+        rules_dir.mkdir()
+        (rules_dir / "python.md").write_text("Python rules content.")
+
+        with patch("squadron.cli.commands.review.get_config", return_value=None):
+            result = cli_runner.invoke(
+                app,
+                [
+                    "review",
+                    "code",
+                    "--no-rules",
+                    "--rules-dir",
+                    str(rules_dir),
+                    "--diff",
+                    "main",
+                ],
+            )
+        assert result.exit_code == 0
+        call_kwargs = patch_run_review.call_args.kwargs
+        assert call_kwargs["rules_content"] is None
+
+    def test_review_slice_template_rules_injected(
+        self,
+        cli_runner: CliRunner,
+        patch_run_review: AsyncMock,
+        tmp_path: Path,
+    ) -> None:
+        """rules/review-slice.md present → injected into slice review."""
+        rules_dir = tmp_path / "rules"
+        rules_dir.mkdir()
+        (rules_dir / "review-slice.md").write_text("Slice-specific review guidance.")
+
+        result = cli_runner.invoke(
+            app,
+            [
+                "review",
+                "slice",
+                "slice.md",
+                "--against",
+                "arch.md",
+                "--rules-dir",
+                str(rules_dir),
+            ],
+        )
+        assert result.exit_code == 0
+        call_kwargs = patch_run_review.call_args.kwargs
+        assert call_kwargs["rules_content"] is not None
+        assert "Slice-specific review guidance." in call_kwargs["rules_content"]
+
+    def test_review_code_explicit_and_auto_combined(
+        self,
+        cli_runner: CliRunner,
+        patch_run_review: AsyncMock,
+        tmp_path: Path,
+    ) -> None:
+        """--rules custom.md + auto-detected rules both present in rules_content."""
+        rules_dir = tmp_path / "rules"
+        rules_dir.mkdir()
+        (rules_dir / "python.md").write_text(
+            "---\npaths: [**/*.py]\n---\nPython auto rules."
+        )
+        explicit_rules = tmp_path / "custom.md"
+        explicit_rules.write_text("Explicit custom rules.")
+
+        # Patch git diff to return a .py file
+        with patch(
+            "squadron.cli.commands.review._extract_diff_paths",
+            return_value=["src/foo.py"],
+        ):
+            result = cli_runner.invoke(
+                app,
+                [
+                    "review",
+                    "code",
+                    "--rules",
+                    str(explicit_rules),
+                    "--rules-dir",
+                    str(rules_dir),
+                    "--diff",
+                    "main",
+                ],
+            )
+        assert result.exit_code == 0
+        call_kwargs = patch_run_review.call_args.kwargs
+        rc = call_kwargs["rules_content"]
+        assert rc is not None
+        assert "Explicit custom rules." in rc
+        assert "Python auto rules." in rc
+
+
 class TestContextForgeErrors:
     """Test error handling when CF is unavailable or fails."""
 
diff --git a/tests/review/test_parsers.py b/tests/review/test_parsers.py
index f6a7283..b05d598 100644
--- a/tests/review/test_parsers.py
+++ b/tests/review/test_parsers.py
@@ -2,6 +2,8 @@
 
 from __future__ import annotations
 
+from pathlib import Path
+
 import pytest
 
 from squadron.review.models import Severity, Verdict
@@ -203,3 +205,138 @@ class TestUnknownFallback:
         assert result.template_name == "arch"
         assert result.input_files == {"input": "a.md", "against": "b.md"}
         assert result.raw_output == WELL_FORMED_PASS
+
+
+# ---------------------------------------------------------------------------
+# T2: Expanded _FINDING_RE format variants
+# ---------------------------------------------------------------------------
+
+
+class TestExpandedFindingFormats:
+    """Test the five finding format variants supported by _FINDING_RE."""
+
+    def test_finding_colon_separator(self) -> None:
+        """### CONCERN: My title parses to CONCERN finding."""
+        text = "## Summary\nCONCERNS\n\n### CONCERN: My title\nSome detail.\n"
+        result = parse_review_output(text, "slice", {})
+        assert len(result.findings) == 1
+        assert result.findings[0].severity == Severity.CONCERN
+        assert result.findings[0].title == "My title"
+
+    def test_finding_bold_brackets(self) -> None:
+        """**[FAIL]** My title parses to FAIL finding."""
+        text = "## Summary\nFAIL\n\n**[FAIL]** My title\nSome detail.\n"
+        result = parse_review_output(text, "code", {})
+        assert len(result.findings) == 1
+        assert result.findings[0].severity == Severity.FAIL
+        assert result.findings[0].title == "My title"
+
+    def test_finding_bullet_point(self) -> None:
+        """- [CONCERN] My title parses to CONCERN finding."""
+        text = "## Summary\nCONCERNS\n\n- [CONCERN] My title\nSome detail.\n"
+        result = parse_review_output(text, "tasks", {})
+        assert len(result.findings) == 1
+        assert result.findings[0].severity == Severity.CONCERN
+        assert result.findings[0].title == "My title"
+
+    def test_finding_standard_brackets(self) -> None:
+        """### [CONCERN] Title — existing format still parses correctly."""
+        text = "## Summary\nCONCERNS\n\n### [CONCERN] Standard brackets\nDetail.\n"
+        result = parse_review_output(text, "slice", {})
+        assert len(result.findings) == 1
+        assert result.findings[0].severity == Severity.CONCERN
+
+    def test_finding_standard_no_brackets(self) -> None:
+        """### CONCERN Title — existing no-brackets format still parses correctly."""
+        text = "## Summary\nCONCERNS\n\n### CONCERN No brackets\nDetail.\n"
+        result = parse_review_output(text, "slice", {})
+        assert len(result.findings) == 1
+        assert result.findings[0].severity == Severity.CONCERN
+
+
+# ---------------------------------------------------------------------------
+# T4: Fallback parsing
+# ---------------------------------------------------------------------------
+
+
+class TestFallbackParsing:
+    """Test fallback parsing for verdict/findings mismatches."""
+
+    def test_fallback_synthesizes_finding(self) -> None:
+        """CONCERNS verdict + no parseable findings → single synthesized finding."""
+        text = (
+            "## Summary\nCONCERNS\n\nThis review has some issues but unclear format.\n"
+        )
+        result = parse_review_output(text, "slice", {})
+        assert result.verdict == Verdict.CONCERNS
+        assert len(result.findings) == 1
+        assert result.findings[0].title == "Unparsed review findings"
+        assert result.findings[0].severity == Severity.CONCERN
+
+    def test_fallback_not_triggered_on_pass(self) -> None:
+        """PASS with no findings → no fallback, findings list stays empty."""
+        text = "## Summary\nPASS\n\nLooks good overall.\n"
+        result = parse_review_output(text, "slice", {})
+        assert result.verdict == Verdict.PASS
+        assert result.findings == []
+        assert result.fallback_used is False
+
+    def test_fallback_used_flag_true_when_triggered(self) -> None:
+        """result.fallback_used is True when fallback triggered."""
+        text = "## Summary\nFAIL\n\nCritical issues found.\n"
+        result = parse_review_output(text, "code", {})
+        assert result.fallback_used is True
+
+    def test_fallback_used_flag_false_on_clean_parse(self) -> None:
+        """result.fallback_used is False when standard parsing succeeds."""
+        text = "## Summary\nCONCERNS\n\n### [CONCERN] Missing tests\nNo tests.\n"
+        result = parse_review_output(text, "slice", {})
+        assert result.fallback_used is False
+
+    def test_lenient_finds_paragraph_findings(self) -> None:
+        """CONCERNS verdict with findings in paragraph format → lenient path."""
+        text = (
+            "## Summary\nCONCERNS\n\n"
+            "CONCERN: Input validation is missing\n"
+            "The handler does not validate user input.\n"
+        )
+        result = parse_review_output(text, "slice", {})
+        assert result.verdict == Verdict.CONCERNS
+        assert len(result.findings) >= 1
+        assert result.fallback_used is True
+
+
+# ---------------------------------------------------------------------------
+# T6: Diagnostic logging
+# ---------------------------------------------------------------------------
+
+
+class TestDiagnosticLogging:
+    """Test debug log written on verdict/findings mismatches."""
+
+    def test_debug_log_written_on_mismatch(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        """CONCERNS + empty findings → log file written."""
+        log_file = tmp_path / "review-debug.jsonl"
+        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)
+        text = "## Summary\nCONCERNS\n\nSome unstructured content.\n"
+        parse_review_output(text, "slice", {}, model="minimax")
+        assert log_file.exists()
+        import json
+
+        entries = [json.loads(line) for line in log_file.read_text().splitlines()]
+        assert len(entries) >= 1
+        assert entries[0]["verdict"] == "CONCERNS"
+        assert entries[0]["template"] == "slice"
+        assert entries[0]["model"] == "minimax"
+
+    def test_debug_log_not_written_on_clean_pass(
+        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
+    ) -> None:
+        """PASS with findings → no log write."""
+        log_file = tmp_path / "review-debug.jsonl"
+        monkeypatch.setattr("squadron.review.parsers._DEBUG_LOG_PATH", log_file)
+        text = "## Summary\nPASS\n\n### [PASS] Clean code\nLooks good.\n"
+        parse_review_output(text, "code", {})
+        assert not log_file.exists()
diff --git a/tests/review/test_review_client.py b/tests/review/test_review_client.py
index 276fde1..0e41268 100644
--- a/tests/review/test_review_client.py
+++ b/tests/review/test_review_client.py
@@ -246,6 +246,144 @@ class TestNonSDKPath:
                     model="gpt-4o",
                 )
 
+    @pytest.mark.asyncio
+    async def test_debug_output_at_verbosity_3(
+        self, capsys: pytest.CaptureFixture[str]
+    ) -> None:
+        """verbosity=3 → system prompt printed to stderr."""
+        template = _make_template(model="test-model")
+        inputs = {"input": "file.md"}
+
+        mock_response = MagicMock()
+        mock_response.choices = [MagicMock()]
+        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT
+
+        mock_client = AsyncMock()
+        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
+
+        with (
+            patch("squadron.review.review_client.get_profile") as mock_get_profile,
+            patch(
+                "squadron.review.review_client.AsyncOpenAI",
+                return_value=mock_client,
+            ),
+            patch(
+                "squadron.review.review_client._resolve_api_key",
+                new_callable=AsyncMock,
+                return_value="test-key",
+            ),
+        ):
+            from squadron.providers.profiles import ProviderProfile
+
+            mock_get_profile.return_value = ProviderProfile(
+                name="openai",
+                provider="openai",
+                api_key_env="OPENAI_API_KEY",
+            )
+            await run_review_with_profile(
+                template,
+                inputs,
+                profile="openai",
+                model="test-model",
+                verbosity=3,
+            )
+
+        captured = capsys.readouterr()
+        assert "[DEBUG] System Prompt:" in captured.err
+        assert "[DEBUG] User Prompt:" in captured.err
+
+    @pytest.mark.asyncio
+    async def test_no_debug_output_at_verbosity_2(
+        self, capsys: pytest.CaptureFixture[str]
+    ) -> None:
+        """verbosity=2 → nothing extra printed."""
+        template = _make_template(model="test-model")
+        inputs = {"input": "file.md"}
+
+        mock_response = MagicMock()
+        mock_response.choices = [MagicMock()]
+        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT
+
+        mock_client = AsyncMock()
+        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
+
+        with (
+            patch("squadron.review.review_client.get_profile") as mock_get_profile,
+            patch(
+                "squadron.review.review_client.AsyncOpenAI",
+                return_value=mock_client,
+            ),
+            patch(
+                "squadron.review.review_client._resolve_api_key",
+                new_callable=AsyncMock,
+                return_value="test-key",
+            ),
+        ):
+            from squadron.providers.profiles import ProviderProfile
+
+            mock_get_profile.return_value = ProviderProfile(
+                name="openai",
+                provider="openai",
+                api_key_env="OPENAI_API_KEY",
+            )
+            await run_review_with_profile(
+                template,
+                inputs,
+                profile="openai",
+                model="test-model",
+                verbosity=2,
+            )
+
+        captured = capsys.readouterr()
+        assert "[DEBUG]" not in captured.err
+
+    @pytest.mark.asyncio
+    async def test_debug_rules_shown_when_present(
+        self, capsys: pytest.CaptureFixture[str]
+    ) -> None:
+        """rules_content non-empty + verbosity=3 → rules section printed."""
+        template = _make_template(model="test-model")
+        inputs = {"input": "file.md"}
+
+        mock_response = MagicMock()
+        mock_response.choices = [MagicMock()]
+        mock_response.choices[0].message.content = _SAMPLE_REVIEW_OUTPUT
+
+        mock_client = AsyncMock()
+        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
+
+        with (
+            patch("squadron.review.review_client.get_profile") as mock_get_profile,
+            patch(
+                "squadron.review.review_client.AsyncOpenAI",
+                return_value=mock_client,
+            ),
+            patch(
+                "squadron.review.review_client._resolve_api_key",
+                new_callable=AsyncMock,
+                return_value="test-key",
+            ),
+        ):
+            from squadron.providers.profiles import ProviderProfile
+
+            mock_get_profile.return_value = ProviderProfile(
+                name="openai",
+                provider="openai",
+                api_key_env="OPENAI_API_KEY",
+            )
+            await run_review_with_profile(
+                template,
+                inputs,
+                profile="openai",
+                model="test-model",
+                verbosity=3,
+                rules_content="Always check for SQL injection.",
+            )
+
+        captured = capsys.readouterr()
+        assert "[DEBUG] Injected Rules:" in captured.err
+        assert "SQL injection" in captured.err
+
     @pytest.mark.asyncio
     async def test_no_model_raises_error(self) -> None:
         """Non-SDK path requires an explicit model."""
diff --git a/tests/review/test_review_file.py b/tests/review/test_review_file.py
new file mode 100644
index 0000000..bdb4cf1
--- /dev/null
+++ b/tests/review/test_review_file.py
@@ -0,0 +1,71 @@
+"""Tests for _format_review_markdown YAML frontmatter alignment (T14/T15)."""
+
+from __future__ import annotations
+
+from squadron.cli.commands.review import SliceInfo, _format_review_markdown
+from squadron.review.models import ReviewResult, Verdict
+
+
+def _make_result(model: str | None = "claude-opus-4-5") -> ReviewResult:
+    return ReviewResult(
+        verdict=Verdict.PASS,
+        findings=[],
+        raw_output="## Summary\nPASS\n",
+        template_name="slice",
+        input_files={"input": "design.md"},
+        model=model,
+    )
+
+
+def _make_slice_info() -> SliceInfo:
+    return SliceInfo(
+        index=122,
+        name="review-context-enrichment",
+        slice_name="review-context-enrichment",
+        design_file="project-documents/user/slices/122-slice.md",
+        task_files=["122-tasks.review-context-enrichment.md"],
+        arch_file="project-documents/user/architecture/100-arch.md",
+    )
+
+
+class TestFormatReviewMarkdown:
+    """Test YAML frontmatter fields in _format_review_markdown."""
+
+    def test_has_layer_field(self) -> None:
+        output = _format_review_markdown(_make_result(), "slice", _make_slice_info())
+        assert "layer: project" in output
+
+    def test_has_source_document(self) -> None:
+        output = _format_review_markdown(
+            _make_result(),
+            "slice",
+            _make_slice_info(),
+            input_file="project-documents/user/slices/122-slice.md",
+        )
+        assert "sourceDocument:" in output
+        assert "122-slice.md" in output
+
+    def test_has_ai_model(self) -> None:
+        output = _format_review_markdown(
+            _make_result(model="claude-opus-4-5"),
+            "slice",
+            _make_slice_info(),
+        )
+        assert "aiModel: claude-opus-4-5" in output
+
+    def test_has_status(self) -> None:
+        output = _format_review_markdown(_make_result(), "slice", _make_slice_info())
+        assert "status: complete" in output
+
+    def test_model_unknown_when_none(self) -> None:
+        output = _format_review_markdown(
+            _make_result(model=None), "slice", _make_slice_info()
+        )
+        assert "aiModel: unknown" in output
+
+    def test_source_document_falls_back_to_design_file(self) -> None:
+        """When input_file not provided, uses slice_info design_file."""
+        output = _format_review_markdown(
+            _make_result(), "slice", _make_slice_info(), input_file=None
+        )
+        assert "sourceDocument:" in output
diff --git a/tests/review/test_rules_module.py b/tests/review/test_rules_module.py
new file mode 100644
index 0000000..d86f97f
--- /dev/null
+++ b/tests/review/test_rules_module.py
@@ -0,0 +1,259 @@
+"""Tests for src/squadron/review/rules.py — language detection and rules matching."""
+
+from __future__ import annotations
+
+from pathlib import Path
+from unittest.mock import patch
+
+from squadron.review.rules import (
+    detect_languages_from_paths,
+    get_template_rules,
+    load_rules_content,
+    load_rules_frontmatter,
+    match_rules_files,
+    resolve_rules_dir,
+)
+
+# ---------------------------------------------------------------------------
+# resolve_rules_dir
+# ---------------------------------------------------------------------------
+
+
+class TestResolveRulesDir:
+    """Test rules directory resolution priority."""
+
+    def test_cli_flag_wins(self, tmp_path: Path) -> None:
+        """CLI flag overrides all others."""
+        cli_dir = tmp_path / "cli-rules"
+        cli_dir.mkdir()
+        config_dir = tmp_path / "config-rules"
+        config_dir.mkdir()
+
+        result = resolve_rules_dir(str(tmp_path), str(config_dir), str(cli_dir))
+        assert result == cli_dir
+
+    def test_config_wins_over_default(self, tmp_path: Path) -> None:
+        """Config beats cwd default."""
+        config_dir = tmp_path / "config-rules"
+        config_dir.mkdir()
+        # create cwd/rules too — should be ignored since config present
+        (tmp_path / "rules").mkdir()
+
+        with patch("squadron.review.rules.get_config", return_value=str(config_dir)):
+            result = resolve_rules_dir(str(tmp_path), None, None)
+        assert result == config_dir
+
+    def test_falls_back_to_cwd_rules(self, tmp_path: Path) -> None:
+        """Uses {cwd}/rules/ when it exists."""
+        rules_dir = tmp_path / "rules"
+        rules_dir.mkdir()
+
+        with patch("squadron.review.rules.get_config", return_value=None):
+            result = resolve_rules_dir(str(tmp_path), None, None)
+        assert result == rules_dir
+
+    def test_claude_rules_fallback(self, tmp_path: Path) -> None:
+        """Uses .claude/rules/ when rules/ is absent."""
+        claude_rules = tmp_path / ".claude" / "rules"
+        claude_rules.mkdir(parents=True)
+
+        with patch("squadron.review.rules.get_config", return_value=None):
+            result = resolve_rules_dir(str(tmp_path), None, None)
+        assert result == claude_rules
+
+    def test_returns_none_when_none_exist(self, tmp_path: Path) -> None:
+        """Returns None when no rules dir found."""
+        with patch("squadron.review.rules.get_config", return_value=None):
+            result = resolve_rules_dir(str(tmp_path), None, None)
+        assert result is None
+
+    def test_cli_flag_nonexistent_returns_none(self, tmp_path: Path) -> None:
+        """CLI flag pointing to non-existent dir returns None."""
+        result = resolve_rules_dir(str(tmp_path), None, str(tmp_path / "nope"))
+        assert result is None
+
+
+# ---------------------------------------------------------------------------
+# detect_languages_from_paths
+# ---------------------------------------------------------------------------
+
+
+class TestDetectLanguages:
+    """Test extension extraction from diff paths."""
+
+    def test_extracts_py_and_ts(self) -> None:
+        paths = [
+            "+++ b/src/main.py",
+            "+++ b/frontend/app.ts",
+            "+++ b/package.json",
+        ]
+        exts = detect_languages_from_paths(paths)
+        assert ".py" in exts
+        assert ".ts" in exts
+        assert ".json" in exts
+
+    def test_empty_list(self) -> None:
+        assert detect_languages_from_paths([]) == set()
+
+    def test_paths_without_extensions(self) -> None:
+        exts = detect_languages_from_paths(["Makefile", "LICENSE"])
+        assert exts == set()
+
+    def test_lowercase_normalization(self) -> None:
+        exts = detect_languages_from_paths(["src/foo.PY"])
+        assert ".py" in exts
+
+
+# ---------------------------------------------------------------------------
+# load_rules_frontmatter
+# ---------------------------------------------------------------------------
+
+
+class TestLoadRulesFrontmatter:
+    """Test frontmatter parsing and filename-based fallback."""
+
+    def test_frontmatter_inline_paths(self, tmp_path: Path) -> None:
+        """Parses inline-list paths from frontmatter."""
+        (tmp_path / "python.md").write_text(
+            "---\npaths: [**/*.py, **/*.pyi]\n---\nPython rules.\n"
+        )
+        result = load_rules_frontmatter(tmp_path)
+        assert "python.md" in result
+        assert "**/*.py" in result["python.md"]
+
+    def test_frontmatter_block_paths(self, tmp_path: Path) -> None:
+        """Parses block-list paths from frontmatter."""
+        (tmp_path / "ts.md").write_text(
+            "---\npaths:\n  - **/*.ts\n  - **/*.tsx\n---\nTS rules.\n"
+        )
+        result = load_rules_frontmatter(tmp_path)
+        assert "ts.md" in result
+        assert "**/*.ts" in result["ts.md"]
+
+    def test_filename_fallback_python(self, tmp_path: Path) -> None:
+        """python.md with no frontmatter paths falls back to **/*.py."""
+        (tmp_path / "python.md").write_text("Python rules.\n")
+        result = load_rules_frontmatter(tmp_path)
+        assert "python.md" in result
+        assert "**/*.py" in result["python.md"]
+
+    def test_skips_non_md(self, tmp_path: Path) -> None:
+        """Non-.md files are ignored."""
+        (tmp_path / "python.txt").write_text("not a rules file")
+        result = load_rules_frontmatter(tmp_path)
+        assert "python.txt" not in result
+
+
+# ---------------------------------------------------------------------------
+# match_rules_files
+# ---------------------------------------------------------------------------
+
+
+class TestMatchRulesFiles:
+    """Test extension-to-rules-file matching."""
+
+    def test_match_by_extension(self, tmp_path: Path) -> None:
+        """'.py' extension matches python.md with frontmatter paths [**/*.py]."""
+        py_file = tmp_path / "python.md"
+        py_file.write_text("Python rules.")
+        frontmatter = {"python.md": ["**/*.py"]}
+
+        matched = match_rules_files({".py"}, tmp_path, frontmatter)
+        assert py_file in matched
+
+    def test_no_match_for_unrelated_extension(self, tmp_path: Path) -> None:
+        """'.rs' does not match python.md."""
+        (tmp_path / "python.md").write_text("Python rules.")
+        frontmatter = {"python.md": ["**/*.py"]}
+
+        matched = match_rules_files({".rs"}, tmp_path, frontmatter)
+        assert matched == []
+
+    def test_filename_fallback_match(self, tmp_path: Path) -> None:
+        """python.md with no frontmatter paths falls back — should match .py."""
+        py_file = tmp_path / "python.md"
+        py_file.write_text("Python rules.")
+        # simulate filename-derived patterns
+        frontmatter = {"python.md": ["**/*.py", "**/*.pyi"]}
+
+        matched = match_rules_files({".py"}, tmp_path, frontmatter)
+        assert py_file in matched
+
+    def test_result_is_sorted(self, tmp_path: Path) -> None:
+        """Returned list is sorted."""
+        for name in ("z_rules.md", "a_rules.md"):
+            (tmp_path / name).write_text("rules")
+        frontmatter = {
+            "z_rules.md": ["**/*.py"],
+            "a_rules.md": ["**/*.py"],
+        }
+        matched = match_rules_files({".py"}, tmp_path, frontmatter)
+        assert matched == sorted(matched)
+
+
+# ---------------------------------------------------------------------------
+# get_template_rules
+# ---------------------------------------------------------------------------
+
+
+class TestGetTemplateRules:
+    """Test template-specific rules file discovery."""
+
+    def test_both_files_concatenated(self, tmp_path: Path) -> None:
+        """review.md and review-slice.md both present → concatenated."""
+        (tmp_path / "review.md").write_text("General review rules.")
+        (tmp_path / "review-slice.md").write_text("Slice-specific rules.")
+
+        result = get_template_rules("slice", tmp_path)
+        assert result is not None
+        assert "General review rules." in result
+        assert "Slice-specific rules." in result
+
+    def test_general_only(self, tmp_path: Path) -> None:
+        """Only review.md present → returned alone."""
+        (tmp_path / "review.md").write_text("General review rules.")
+
+        result = get_template_rules("code", tmp_path)
+        assert result == "General review rules."
+
+    def test_none_present(self, tmp_path: Path) -> None:
+        """Neither file present → returns None."""
+        result = get_template_rules("tasks", tmp_path)
+        assert result is None
+
+    def test_template_specific_only(self, tmp_path: Path) -> None:
+        """Only review-code.md present → returned alone."""
+        (tmp_path / "review-code.md").write_text("Code rules.")
+
+        result = get_template_rules("code", tmp_path)
+        assert result == "Code rules."
+
+
+# ---------------------------------------------------------------------------
+# load_rules_content
+# ---------------------------------------------------------------------------
+
+
+class TestLoadRulesContent:
+    """Test reading and concatenating rules file content."""
+
+    def test_concatenates_with_separator(self, tmp_path: Path) -> None:
+        f1 = tmp_path / "a.md"
+        f2 = tmp_path / "b.md"
+        f1.write_text("Rule A.")
+        f2.write_text("Rule B.")
+
+        content = load_rules_content([f1, f2])
+        assert "Rule A." in content
+        assert "Rule B." in content
+        assert "---" in content
+
+    def test_empty_list(self) -> None:
+        assert load_rules_content([]) == ""
+
+    def test_skips_unreadable(self, tmp_path: Path) -> None:
+        """Non-existent file is silently skipped."""
+        f1 = tmp_path / "a.md"
+        f1.write_text("Rule A.")
+        content = load_rules_content([f1, tmp_path / "nonexistent.md"])
+        assert "Rule A." in content
diff --git a/tests/review/test_templates.py b/tests/review/test_templates.py
index 91cb012..e57b103 100644
--- a/tests/review/test_templates.py
+++ b/tests/review/test_templates.py
@@ -271,3 +271,35 @@ class TestInputDef:
     def test_without_default(self) -> None:
         i = InputDef(name="input", description="File to review")
         assert i.default is None
+
+
+# ---------------------------------------------------------------------------
+# T8: Prompt hardening present in all three builtin templates
+# ---------------------------------------------------------------------------
+
+
+class TestBuiltinTemplateHardening:
+    """Test that all three builtin templates have the CRITICAL consistency block."""
+
+    @pytest.fixture(autouse=True)
+    def _load(self) -> None:
+        from squadron.review.templates import load_all_templates
+
+        load_all_templates()
+
+    def _get(self, name: str) -> ReviewTemplate:
+        t = get_template(name)
+        assert t is not None, f"Template '{name}' not found"
+        return t
+
+    def test_slice_template_has_consistency_instruction(self) -> None:
+        t = self._get("slice")
+        assert "CRITICAL" in t.system_prompt
+
+    def test_tasks_template_has_consistency_instruction(self) -> None:
+        t = self._get("tasks")
+        assert "CRITICAL" in t.system_prompt
+
+    def test_code_template_has_consistency_instruction(self) -> None:
+        t = self._get("code")
+        assert "CRITICAL" in t.system_prompt
diff --git a/uv.lock b/uv.lock
index 561d123..be4d9ed 100644
--- a/uv.lock
+++ b/uv.lock
@@ -2259,7 +2259,7 @@ wheels = [
 
 [[package]]
 name = "squadron-ai"
-version = "0.2.5"
+version = "0.2.6"
 source = { editable = "." }
 dependencies = [
     { name = "anthropic" },

```

### Rules Injected

None

### Raw Response

I'll review the code changes from this git diff. Let me first check for the CLAUDE.md conventions and then examine the key implementation files.

## Summary
[CONCERNS]

## Findings

### [CONCERN] Unused import in `review.py`
In `src/squadron/cli/commands/review.py`, there's an unused import:
```python
import glob as _glob
```
This is imported inside the `review_code` function at line 757 but the `_glob` alias is never used - the code uses `glob.glob()` directly. The standard `glob` module is already being used implicitly via the function call.

### [CONCERN] Missing type annotation for `no_rules` parameter ordering
In `src/squadron/cli/commands/review.py`, the `no_rules` parameter at line 718 is defined as:
```python
no_rules: bool = typer.Option(
    False, "--no-rules", help="Suppress all rule injection"
),
```

This follows the project's typer convention but the parameter is defined after `rules_dir_flag` which creates a confusing order: `--rules` (path), `--rules-dir` (directory), `--no-rules` (suppress). Consider reordering to group suppression flags together or follow the convention of placing boolean flags before path arguments.

### [CONCERN] `_extract_diff_paths` subprocess error handling silently swallows errors
In `src/squadron/cli/commands/review.py`, the `_extract_diff_paths` function at line 256-271:
```python
def _extract_diff_paths(diff_ref: str, cwd: str) -> list[str]:
    """Run git diff and extract +++ b/ file paths."""
    import subprocess
    try:
        result = subprocess.run(...)
    except (FileNotFoundError, OSError):
        pass
    return []
```

The function silently returns an empty list when git is unavailable or the command fails. While this is safe behavior, there's no warning to the user that their diff couldn't be processed. Consider logging a warning when fallback to empty paths occurs.

### [CONCERN] Potential regex denial-of-service in `_FINDING_RE`
In `src/squadron/review/parsers.py`, the expanded `_FINDING_RE` regex at line 43-64 uses nested alternations and `re.DOTALL` with a complex lookahead pattern. While the pattern appears safe for typical inputs, patterns like `(?=...)` with `re.DOTALL` can cause backtracking issues on certain maliciously crafted inputs. For a review tool processing AI output, this is low risk, but consider using `re.VERBOSE` to make the pattern more maintainable.

### [CONCERN] `_filename_to_glob` hardcoded dictionary not extensible
In `src/squadron/review/rules.py`, the `_STEM_TO_EXTS` dictionary at line 82-96 is hardcoded:
```python
_STEM_TO_EXTS: dict[str, list[str]] = {
    "python": ["**/*.py", "**/*.pyi"],
    "typescript": ["**/*.ts", "**/*.tsx"],
    ...
}
```

This requires code changes to add new language mappings. Consider loading extensions from the config system or a separate extensions registry that can be extended without modifying core code.

### [CONCERN] `_parse_frontmatter_paths` regex parsing is brittle
In `src/squadron/review/rules.py`, the frontmatter path parsing at lines 47-72 uses two separate regex patterns (`_PATHS_RE` and `_PATHS_LIST_RE`) with different matching strategies. This approach:
1. Only handles YAML arrays with comma-separated items or block-style list items
2. Doesn't handle flow-style JSON arrays in YAML: `paths: [a, b]`
3. Doesn't handle multi-line string entries

Consider using a proper YAML parser (like `pyyaml`) for frontmatter parsing instead of regex, which would be more robust and handle all YAML syntax variants.

### [CONCERN] Debug log writes synchronously to filesystem
In `src/squadron/review/parsers.py`, the `_write_debug_log` function at line 151 writes to disk synchronously during parsing. For high-throughput scenarios or when parsing many reviews, this could:
1. Block the review parsing
2. Cause file descriptor exhaustion if called rapidly

Consider making this async or using a background task queue, though for a CLI tool this is likely acceptable.

### [PASS] Test coverage is comprehensive
The diff shows excellent test coverage including:
- `test_parsers.py` - Tests for all five finding formats, fallback parsing, and debug logging
- `test_rules_module.py` - Comprehensive tests for all `rules.py` functions
- `test_review_file.py` - New file tests for YAML frontmatter alignment
- `test_templates.py` - Tests for CRITICAL consistency block presence
- `test_review_client.py` - Tests for debug output at different verbosity levels
- `test_cli_review.py` - Integration tests for rules wiring

### [PASS] Documentation updated consistently
All documentation files (CHANGELOG.md, DEVLOG.md, slice design, tasks) are consistently marked as complete with verified checkmarks, showing a thorough implementation verification process.

### [PASS] Consistent error handling pattern in `_write_debug_log`
The debug log function properly handles `OSError` exceptions and degrades gracefully by printing a warning to stderr, preventing crashes when logging fails.

### [PASS] Template hardening follows DRY principle
The CRITICAL consistency block is consistently added to all three templates (slice, tasks, code) with identical wording, ensuring uniform behavior across review types.

### [PASS] Model field properly threaded through
The `model` field is correctly propagated from `ReviewResult` through to the review file YAML frontmatter as `aiModel`, with a fallback to `'unknown'` when not set.
