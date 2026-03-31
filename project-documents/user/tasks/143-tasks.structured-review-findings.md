---
docType: tasks
slice: structured-review-findings
project: squadron
lld: ../slices/143-slice.structured-review-findings.md
dependencies:
  - 142-pipeline-core-models-and-action-protocol (complete)
  - review-system 105/128 (complete)
projectState: "Slice 142 complete. Pipeline package exists at src/squadron/pipeline/. Review system operational with ReviewResult, ReviewFinding, Verdict, Severity models in src/squadron/review/models.py. Parser in src/squadron/review/parsers.py. Formatter in src/squadron/cli/commands/review.py."
dateCreated: 20260330
dateUpdated: 20260330
status: complete
---

# Tasks: Structured Review Findings (143)

## Context

**Working on:** Extending review output with machine-readable structured findings in YAML frontmatter. Adds `StructuredFinding` dataclass, `NOTE` severity level, parser extensions for category/location extraction, prompt enhancement for review templates, and structured findings in frontmatter and JSON output.

**Current state:** Review system produces `ReviewResult` with `ReviewFinding` instances (severity, title, description, file_ref). Parser extracts findings from agent markdown. Formatter writes review files with YAML frontmatter (metadata only, no findings index). Pipeline `ActionResult` has `findings: list[object]` ready to receive structured findings.

**Dependencies:** Slice 142 (complete), Review System 105/128 (complete).

**Deliverables:** `StructuredFinding` dataclass, `NOTE` severity, extended parser, structured frontmatter output, extended JSON serialization, prompt enhancement for category tags.

**Next slice:** 146 (Review and Checkpoint Actions) consumes structured findings.

---

## Tasks

### T1: Add NOTE severity and StructuredFinding model

- [x] **Add `NOTE` to `Severity` enum in `src/squadron/review/models.py`**
  - [x] Insert `NOTE = "NOTE"` between `PASS` and `CONCERN` in the `Severity` StrEnum
  - [x] Verify existing `PASS`, `CONCERN`, `FAIL` values unchanged

- [x] **Add `category` and `location` fields to `ReviewFinding`**
  - [x] Add `category: str | None = None` field
  - [x] Add `location: str | None = None` field
  - [x] Existing `file_ref` field unchanged (location is the structured counterpart)

- [x] **Create `StructuredFinding` dataclass in `src/squadron/review/models.py`**
  - [x] Fields: `id: str`, `severity: str`, `category: str`, `summary: str`, `location: str | None = None`
  - [x] Docstring: "Machine-readable finding for frontmatter and pipeline consumption."

- [x] **Add `structured_findings` computed property to `ReviewResult`**
  - [x] Returns `list[StructuredFinding]` derived from `self.findings`
  - [x] Auto-assigns IDs as `F001`, `F002`, ... (zero-padded 3-digit counter)
  - [x] Maps `severity` to lowercase string: `f.severity.value.lower()`
  - [x] Uses `f.category or "uncategorized"` for category
  - [x] Uses `f.location or f.file_ref` for location
  - [x] Uses `f.title` for summary

- [x] Success: `from squadron.review.models import StructuredFinding, Severity` works; `Severity.NOTE` exists; `ReviewResult.structured_findings` returns a list; `uv run pyright` passes

**Commit:** `feat: add StructuredFinding model and NOTE severity`

---

### T2: Tests for models

- [x] **Add tests in `tests/review/test_models.py`** (create if needed)
  - [x] Test `Severity.NOTE` exists and has value `"NOTE"`
  - [x] Test `Severity` enum ordering: PASS, NOTE, CONCERN, FAIL (all four present)
  - [x] Test `StructuredFinding` construction with all fields
  - [x] Test `StructuredFinding` with `location=None`
  - [x] Test `ReviewFinding` accepts `category` and `location` kwargs
  - [x] Test `ReviewFinding` defaults `category` and `location` to `None`
  - [x] Test `ReviewResult.structured_findings` returns correct count
  - [x] Test `ReviewResult.structured_findings` auto-assigns IDs (`F001`, `F002`)
  - [x] Test `ReviewResult.structured_findings` maps severity to lowercase
  - [x] Test `ReviewResult.structured_findings` defaults category to `"uncategorized"` when `None`
  - [x] Test `ReviewResult.structured_findings` uses `location` over `file_ref` when both present
  - [x] Test `ReviewResult.structured_findings` falls back to `file_ref` when `location` is `None`

- [x] Success: `uv run pytest tests/review/test_models.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add structured finding model tests`

---

### T3: Extend parser — NOTE severity and category extraction

- [x] **Add `NOTE` to parser severity map in `src/squadron/review/parsers.py`**
  - [x] Add `"NOTE": Severity.NOTE` to `_SEVERITY_MAP`
  - [x] Update `_FINDING_RE` regex to include `NOTE` in the severity alternation: `PASS|NOTE|CONCERN|FAIL`
  - [x] Update `_LENIENT_RE` to include `NOTE` in the severity keyword scan

- [x] **Extract `category:` tag from finding blocks**
  - [x] After extracting a finding's heading and body, scan the first 3 lines of the body for pattern `^category:\s*(.+)$` (case-insensitive)
  - [x] If found, set `category` on the `ReviewFinding` and strip the `category:` line from the description
  - [x] If not found, leave `category` as `None`

- [x] **Extract location from finding blocks**
  - [x] Scan body lines for pattern `^location:\s*(.+)$` (case-insensitive)
  - [x] If found, set `location` on the `ReviewFinding` and strip the line from the description
  - [x] Also populate `location` from existing `file_ref` extraction if `location` tag not present
  - [x] If `-> path/to/file.py:123` pattern found (existing `file_ref`), also set `location` to that value

- [x] Success: Parser handles all four severity levels; `category:` and `location:` tags extracted from body; lines stripped from description; `uv run pyright` passes

**Commit:** `feat: extend parser for NOTE severity, category, and location extraction`

---

### T4: Tests for parser extensions

- [x] **Add tests in `tests/review/test_parsers.py`** (extend existing file)
  - [x] Test `NOTE` severity parsed from `### [NOTE] Title` format
  - [x] Test `NOTE` severity parsed from `### NOTE Title` format (unbracketed)
  - [x] Test `NOTE` severity parsed from `**[NOTE]** Title` format (bold)
  - [x] Test `NOTE` severity parsed from `- [NOTE] Title` format (bullet)
  - [x] Test finding with `category: error-handling` line — category extracted, line stripped from description
  - [x] Test finding with `category: naming` — different category value
  - [x] Test finding without `category:` line — category is `None`
  - [x] Test finding with `location: src/foo.py:45` line — location extracted, line stripped
  - [x] Test finding without `location:` line — location is `None`
  - [x] Test finding with both `category:` and `location:` — both extracted
  - [x] Test `category:` extraction is case-insensitive (`Category:`, `CATEGORY:`)
  - [x] Test existing finding formats still work (regression: PASS, CONCERN, FAIL unchanged)

- [x] Success: `uv run pytest tests/review/test_parsers.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add parser tests for NOTE, category, and location extraction`

---

### T5: Extend frontmatter formatter with structured findings

- [x] **Modify `_format_review_markdown()` in `src/squadron/cli/commands/review.py`**
  - [x] After existing metadata fields in frontmatter (before `---` closer), insert findings block
  - [x] Only emit `findings:` block when `result.findings` is non-empty
  - [x] Each finding as a YAML list item: `id`, `severity`, `category`, `summary` (quoted), optional `location`
  - [x] Add `_yaml_escape()` helper for summary strings (escape double quotes)
  - [x] Existing prose body format unchanged

- [x] Success: Generated frontmatter contains valid YAML with `findings:` array; summary values properly quoted; location omitted when `None`

**Commit:** `feat: emit structured findings in review frontmatter`

---

### T6: Tests for frontmatter formatter

- [x] **Add tests in `tests/cli/test_review_format.py`** (create if needed)
  - [x] Test frontmatter contains `findings:` block when findings present
  - [x] Test each finding has `id`, `severity`, `category`, `summary` fields
  - [x] Test finding with location includes `location:` field
  - [x] Test finding without location omits `location:` field
  - [x] Test summary with double quotes is properly escaped
  - [x] Test frontmatter is valid YAML (parse with `yaml.safe_load`)
  - [x] Test no `findings:` block when findings list is empty
  - [x] Test prose body section unchanged (findings still appear as `### [SEVERITY] Title`)

- [x] Success: `uv run pytest tests/cli/test_review_format.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add frontmatter structured findings formatter tests`

---

### T7: Extend JSON serialization

- [x] **Extend `ReviewResult.to_dict()` in `src/squadron/review/models.py`**
  - [x] Add `"structured_findings"` key to the returned dict
  - [x] Value is a list of dicts, each with `id`, `severity`, `category`, `summary`, `location`
  - [x] Derived from `self.structured_findings` property

- [x] **Extend `ReviewFinding` serialization in `to_dict()`**
  - [x] Add `"category"` and `"location"` to the finding dict in the existing `findings` array

- [x] Success: `result.to_dict()["structured_findings"]` returns list of dicts; each dict has all expected keys; `uv run pyright` passes

---

### T8: Tests for JSON serialization

- [x] **Add tests in `tests/review/test_models.py`** (extend)
  - [x] Test `to_dict()` includes `"structured_findings"` key
  - [x] Test `structured_findings` array contains correct number of items
  - [x] Test each structured finding dict has `id`, `severity`, `category`, `summary`, `location`
  - [x] Test `to_dict()` findings array includes `category` and `location` fields
  - [x] Test empty findings produces empty `structured_findings` array

- [x] Success: `uv run pytest tests/review/test_models.py -v` — all pass

**Commit:** `feat: add structured findings to JSON serialization`

(Commit covers T7 + T8)

---

### T9: Prompt enhancement for category tags

- [x] **Add structured output instructions to review template system**
  - [x] Determine injection point: review template rendering or prompt builder
  - [x] Locate where system prompts are assembled for review templates (check `src/squadron/review/templates/` and prompt builder code)
  - [x] Add instruction block requesting `category:` tags after finding headings
  - [x] Include valid severity levels: `PASS`, `NOTE`, `CONCERN`, `FAIL`
  - [x] Instructions should apply to all review types (code, slice, tasks, arch)
  - [x] Do NOT modify individual template YAML files if a shared injection point exists

- [x] Success: Running `sq review code --diff main -vv` shows the structured output instructions in the system prompt; instructions appear for all review template types

**Commit:** `feat: add structured output instructions to review prompts`

---

### T10: Full verification and cleanup

- [x] **Run full test suite**
  - [x] `uv run pytest` — all tests pass
  - [x] `uv run pyright` — 0 errors
  - [x] `uv run ruff check` — clean
  - [x] `uv run ruff format --check` — clean

- [x] **Verify existing review tests still pass** (regression check)
  - [x] `uv run pytest tests/review/ -v` — all pass
  - [x] `uv run pytest tests/cli/test_review*.py -v` — all pass (if existing)

- [x] **Update CHANGELOG.md** with slice 143 entries under `[Unreleased]`

- [x] **Update slice design verification walkthrough** with actual commands and output

- [x] Success: CI-equivalent checks pass locally; no regressions

**Commit:** `docs: mark slice 143 structured review findings complete`
