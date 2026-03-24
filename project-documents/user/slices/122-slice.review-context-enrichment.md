---
docType: slice-design
slice: review-context-enrichment
project: squadron
parent: 100-slices.orchestration-v2.md
dependencies: [review-provider-model-selection]
interfaces: []
dateCreated: 20260324
dateUpdated: 20260324
status: not_started
---

# Slice Design: Review Context Enrichment

## Overview

Enrich review prompts with contextual rules, strengthen the output format instructions to prevent verdict/findings inconsistency, and auto-detect applicable language rules for code reviews. This slice addresses two observed problems: (1) reviews returning a CONCERNS verdict with zero findings (GitHub issue #5), and (2) code reviews not leveraging available project rules unless manually specified with `--rules`.

The scope is intentionally broader than the original slice plan entry — in addition to rule injection, it fixes the parser/prompt gap that produces empty-findings verdicts. Both problems live in the same code path and share a solution: better prompt structure and post-processing validation.

## User-Provided Concept

From slice plan: "Automatically enrich review prompts with applicable rules and context. Code reviews auto-detect language from the diff/files under review and inject matching rules from the project's `rules/` directory (e.g. Python files → `rules/python.md`). Supports multiple language detection in a single review. Config key `rules_dir` points to the rules directory. The `--rules` CLI flag continues to work as an explicit override/addition. Slice and task reviews can optionally pull review criteria from Context Forge's process guide prompts when available."

Additional PM direction: Fix issue #5 (CONCERNS verdict with empty findings). Extract useful patterns from the legacy code review crawler prompt (`prompt.code-review-crawler.md`) into injected rule segments rather than bloating templates.

---

## Technical Decisions

### 1. Verdict/Findings Consistency — Prompt Hardening + Post-Processing

**Problem:** Models (especially cheaper ones like minimax) sometimes return `CONCERNS` as the verdict but produce no parseable `### [CONCERN] ...` finding blocks. This happens at both `-v` and `-vv`, ruling out a display/truncation issue.

**Root causes (both observed):**
- Model generates CONCERNS verdict but writes findings in a non-standard format the parser can't extract
- Model genuinely writes CONCERNS with no findings block at all

**Solution — two layers:**

**Layer 1: Prompt hardening.** Add explicit output format enforcement to all three template system prompts:

```
CRITICAL: Your verdict and findings MUST be consistent.
- If your verdict is CONCERNS or FAIL, you MUST include at least one finding with that severity.
- If you have no findings of CONCERN or FAIL severity, your verdict MUST be PASS.
- Every finding MUST use the exact format: ### [SEVERITY] Title
```

This goes in each template's `system_prompt`, not in a shared injected block — templates are self-contained by design.

**Layer 2: Fallback parsing in `parsers.py`.** If the structured `_FINDING_RE` regex extracts zero findings but the verdict is CONCERNS or FAIL, the model *did* produce concerns — we just couldn't parse them. Rather than silently dropping them or downgrading the verdict:

- Attempt more lenient parsing: look for bullet-point findings, numbered lists, or paragraph blocks after `## Findings` / `## Summary` that describe issues
- If lenient parsing also finds nothing, synthesize a single finding from the raw text between `## Summary` and the end (or next `##` heading), with severity matching the verdict and title "Unparsed review findings"
- This ensures the user always sees *something* when the model flags concerns — the raw content is surfaced rather than hidden

**Layer 3: Broader regex coverage.** Expand `_FINDING_RE` to also match common model variations:
- `### CONCERN: Title` (colon separator instead of brackets)
- `**[CONCERN]** Title` (bold brackets without heading)
- `- [CONCERN] Title` (bullet-point findings)

This is defense-in-depth. The prompt hardening should get most models to comply, but cheaper models will still drift.

### 2. Auto-Detection of Language Rules for Code Reviews

**Mechanism:** Before executing a code review, detect which languages/frameworks are present in the files under review, then auto-inject matching rules from the project's `rules/` directory.

**Detection strategy:**
- If `diff` input: extract file paths from the diff (lines starting with `+++ b/` or `--- a/`)
- If `files` glob: resolve the glob to file paths
- If neither: skip auto-detection (the SDK agent will survey the project itself)
- Collect file extensions from the resolved paths
- Match extensions against rules files' `paths` frontmatter globs (already present in rules — e.g., `python.md` has `paths: ["**/*.py", "**/pyproject.toml"]`)

**Rules directory resolution (priority order):**
1. `--rules-dir` CLI flag (new, optional)
2. Config key `rules_dir` (new)
3. `{cwd}/rules/` (convention-based default)
4. `{cwd}/.claude/rules/` (Claude Code convention)

**Injection:** Concatenate all matched rules file contents and pass as `rules_content` to the review execution path. This uses the existing `rules_content` parameter — no new injection mechanism needed.

**Interaction with `--rules`:** The existing `--rules` flag specifies a single explicit rules file. When both `--rules` and auto-detected rules are present, concatenate them (explicit first, auto-detected after). The `--rules` flag is an addition, not an override of auto-detection. Add `--no-rules` flag to suppress all rule injection (both explicit and auto).

### 3. Rules for Slice and Task Reviews

Slice and task reviews do not have file-extension-based language detection. Instead:
- Check if a `rules/general.md` or `rules/review.md` exists in the resolved rules directory
- If found, inject as `rules_content`
- This is opt-in by convention: if the project has general review rules, they apply; if not, nothing changes

### 4. Priority-Based Review Criteria from Code Review Crawler

The legacy `prompt.code-review-crawler.md` defines a useful priority framework (P0-P3) that should be available as an optional rule, not baked into templates:

- **P0 (Critical):** Bugs, security vulnerabilities, memory leaks, unhandled edge cases
- **P1 (Quality):** Hard-coded values, code duplication, component structure
- **P2 (Best Practices):** Type safety, framework patterns, hooks optimization
- **P3 (Enhancements):** Accessibility, performance, documentation

**Approach:** Create a new built-in rules file at `src/squadron/review/rules/priorities.md` that extracts the P0-P3 framework in a format suitable for injection. This file is NOT auto-injected — it's available for users to reference with `--rules` or copy into their project's `rules/` directory. The code review template's system prompt will reference the severity-based reporting format but won't mandate P0-P3 categories.

### 5. No Changes to Template Structure

Templates remain self-contained YAML files. Rules injection flows through the existing `rules_content` parameter. No new template fields or loader changes.

---

## Data Flow

### Code Review with Auto-Detection

```
User runs: sq review code --diff HEAD~1

1. CLI resolves --diff → file paths from diff
2. _detect_languages(file_paths) → {"python", "testing"}
3. _resolve_rules_dir(cwd, config) → Path("rules/")
4. _match_rules(detected_langs, rules_dir) → ["rules/python.md", "rules/testing.md"]
5. Concatenate: auto_rules + explicit_rules → combined rules_content
6. Pass rules_content to run_review_with_profile() (existing parameter)
7. System prompt gains: "\n\n## Additional Review Rules\n\n{rules_content}"
8. Model receives enriched prompt
9. Parse output → apply verdict consistency guard → ReviewResult
```

### Slice/Task Review with General Rules

```
User runs: sq review slice 122

1. CLI resolves slice → input/against paths
2. _resolve_rules_dir(cwd, config) → Path("rules/")
3. Check for rules/general.md or rules/review.md → found? inject
4. Pass rules_content to run_review_with_profile()
5. Parse output → apply verdict consistency guard → ReviewResult
```

---

## Component Interactions

**Modified files:**
- `src/squadron/review/parsers.py` — verdict consistency guard
- `src/squadron/review/templates/builtin/slice.yaml` — prompt hardening
- `src/squadron/review/templates/builtin/tasks.yaml` — prompt hardening
- `src/squadron/review/templates/builtin/code.yaml` — prompt hardening
- `src/squadron/cli/commands/review.py` — auto-detection logic, `--rules-dir`, `--no-rules` flags

**New files:**
- `src/squadron/review/rules.py` — rule detection and matching logic (language detection, rules dir resolution, rules file matching)
- `src/squadron/review/rules/priorities.md` — optional P0-P3 priority criteria (user-copyable)

**Unchanged:**
- `src/squadron/review/review_client.py` — already accepts `rules_content`, no changes
- `src/squadron/review/runner.py` — already accepts `rules_content`, no changes
- `src/squadron/review/templates/__init__.py` — no structural changes

---

## Excluded

- Changes to template YAML structure or loader
- Context Forge process guide prompt injection (deferred — the rule-based approach covers the immediate need)
- Auto-detection based on file content analysis (shebang lines, etc.) — extension-based is sufficient
- P0-P3 priority enforcement in the parser (priorities are guidance, not structure)
- Changes to the saved review file format

---

## Success Criteria

1. A code review with `--diff HEAD~1` on a Python project auto-injects `rules/python.md` without `--rules` flag
2. Multiple language detection works: a diff touching `.py` and `.ts` files injects both `python.md` and `typescript.md`
3. `--rules path/to/custom.md` continues to work and combines with auto-detected rules
4. `--no-rules` suppresses all rule injection
5. `rules_dir` config key overrides default rules directory
6. Slice and task reviews inject `rules/general.md` if present
7. A review returning CONCERNS with non-standard finding format still surfaces findings (via lenient parsing or raw fallback)
8. The findings regex handles common format variations (colon separators, bold brackets, bullet points)
9. All three built-in templates include output format enforcement instructions
10. `uv run pytest` — all tests pass; `uv run pyright` — 0 errors

---

### Verification Walkthrough

1. **Findings recovery from non-standard output:**
   ```bash
   # Run review with a model known to produce non-standard finding format
   sq review tasks 208 --model minimax -vv
   # Expect: if model returns CONCERNS, findings are surfaced — either via
   # lenient parsing or raw fallback. No more "CONCERNS / No specific findings."
   ```

2. **Auto-detect Python rules for code review:**
   ```bash
   cd ~/source/repos/manta/squadron
   sq review code --diff HEAD~1 -v
   # Expect: rules/python.md auto-injected (visible in -vv debug or review file)
   ```

3. **Multi-language detection:**
   ```bash
   # In a project with both .py and .ts files changed
   sq review code --diff HEAD~3 -v
   # Expect: both python.md and typescript.md rules injected
   ```

4. **Explicit rules override:**
   ```bash
   sq review code --diff HEAD~1 --rules custom-rules.md -v
   # Expect: custom-rules.md + auto-detected rules both injected
   ```

5. **Suppress rules:**
   ```bash
   sq review code --diff HEAD~1 --no-rules
   # Expect: no rules injected, review runs with template system prompt only
   ```

6. **General rules for slice review:**
   ```bash
   # With rules/general.md present in project
   sq review slice 122 -v
   # Expect: general.md content included in review context
   ```

7. **Tests:**
   ```bash
   uv run pytest tests/review/ -v
   uv run pytest tests/cli/test_cli_review.py -v
   ```

---

## Implementation Notes

### Language Detection Mapping

Extension-to-rule mapping derived from the `paths` frontmatter in rules files. At startup (or on first use), scan the rules directory, parse each file's frontmatter for `paths` globs, and build a lookup: `{".py": "python.md", ".ts": "typescript.md", ...}`. This is dynamic — users adding new rules files with `paths` globs get auto-detection for free.

Fallback for rules files without `paths` frontmatter: match by filename convention (`python.md` → `*.py`, `typescript.md` → `*.ts`). A hardcoded fallback map covers common cases.

### Rules Content Size

Rules injection shares the existing `rules_content` parameter. No size limit is enforced on rules (they're typically small — the Python rules file is ~80 lines). If this becomes a concern, a future slice can add truncation.

### Testing Strategy

- **Unit tests for `rules.py`:** Test language detection from diff output, from file globs, rules directory resolution, rules matching against frontmatter paths
- **Unit tests for parser fallback:** Test lenient parsing (colon separators, bullets, bold brackets), raw fallback when structured parsing fails, standard format still works
- **Integration tests:** Mock reviews verifying rules content reaches the system prompt
- **Existing test regression:** All current review tests must pass unchanged
