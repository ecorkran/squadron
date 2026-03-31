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
status: not_started
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

- [ ] **Add `NOTE` to `Severity` enum in `src/squadron/review/models.py`**
  - [ ] Insert `NOTE = "NOTE"` between `PASS` and `CONCERN` in the `Severity` StrEnum
  - [ ] Verify existing `PASS`, `CONCERN`, `FAIL` values unchanged

- [ ] **Add `category` and `location` fields to `ReviewFinding`**
  - [ ] Add `category: str | None = None` field
  - [ ] Add `location: str | None = None` field
  - [ ] Existing `file_ref` field unchanged (location is the structured counterpart)

- [ ] **Create `StructuredFinding` dataclass in `src/squadron/review/models.py`**
  - [ ] Fields: `id: str`, `severity: str`, `category: str`, `summary: str`, `location: str | None = None`
  - [ ] Docstring: "Machine-readable finding for frontmatter and pipeline consumption."

- [ ] **Add `structured_findings` computed property to `ReviewResult`**
  - [ ] Returns `list[StructuredFinding]` derived from `self.findings`
  - [ ] Auto-assigns IDs as `F001`, `F002`, ... (zero-padded 3-digit counter)
  - [ ] Maps `severity` to lowercase string: `f.severity.value.lower()`
  - [ ] Uses `f.category or "uncategorized"` for category
  - [ ] Uses `f.location or f.file_ref` for location
  - [ ] Uses `f.title` for summary

- [ ] Success: `from squadron.review.models import StructuredFinding, Severity` works; `Severity.NOTE` exists; `ReviewResult.structured_findings` returns a list; `uv run pyright` passes

**Commit:** `feat: add StructuredFinding model and NOTE severity`

---

### T2: Tests for models

- [ ] **Add tests in `tests/review/test_models.py`** (create if needed)
  - [ ] Test `Severity.NOTE` exists and has value `"NOTE"`
  - [ ] Test `Severity` enum ordering: PASS, NOTE, CONCERN, FAIL (all four present)
  - [ ] Test `StructuredFinding` construction with all fields
  - [ ] Test `StructuredFinding` with `location=None`
  - [ ] Test `ReviewFinding` accepts `category` and `location` kwargs
  - [ ] Test `ReviewFinding` defaults `category` and `location` to `None`
  - [ ] Test `ReviewResult.structured_findings` returns correct count
  - [ ] Test `ReviewResult.structured_findings` auto-assigns IDs (`F001`, `F002`)
  - [ ] Test `ReviewResult.structured_findings` maps severity to lowercase
  - [ ] Test `ReviewResult.structured_findings` defaults category to `"uncategorized"` when `None`
  - [ ] Test `ReviewResult.structured_findings` uses `location` over `file_ref` when both present
  - [ ] Test `ReviewResult.structured_findings` falls back to `file_ref` when `location` is `None`

- [ ] Success: `uv run pytest tests/review/test_models.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add structured finding model tests`

---

### T3: Extend parser — NOTE severity and category extraction

- [ ] **Add `NOTE` to parser severity map in `src/squadron/review/parsers.py`**
  - [ ] Add `"NOTE": Severity.NOTE` to `_SEVERITY_MAP`
  - [ ] Update `_FINDING_RE` regex to include `NOTE` in the severity alternation: `PASS|NOTE|CONCERN|FAIL`
  - [ ] Update `_LENIENT_RE` to include `NOTE` in the severity keyword scan

- [ ] **Extract `category:` tag from finding blocks**
  - [ ] After extracting a finding's heading and body, scan the first 3 lines of the body for pattern `^category:\s*(.+)$` (case-insensitive)
  - [ ] If found, set `category` on the `ReviewFinding` and strip the `category:` line from the description
  - [ ] If not found, leave `category` as `None`

- [ ] **Extract location from finding blocks**
  - [ ] Scan body lines for pattern `^location:\s*(.+)$` (case-insensitive)
  - [ ] If found, set `location` on the `ReviewFinding` and strip the line from the description
  - [ ] Also populate `location` from existing `file_ref` extraction if `location` tag not present
  - [ ] If `-> path/to/file.py:123` pattern found (existing `file_ref`), also set `location` to that value

- [ ] Success: Parser handles all four severity levels; `category:` and `location:` tags extracted from body; lines stripped from description; `uv run pyright` passes

**Commit:** `feat: extend parser for NOTE severity, category, and location extraction`

---

### T4: Tests for parser extensions

- [ ] **Add tests in `tests/review/test_parsers.py`** (extend existing file)
  - [ ] Test `NOTE` severity parsed from `### [NOTE] Title` format
  - [ ] Test `NOTE` severity parsed from `### NOTE Title` format (unbracketed)
  - [ ] Test `NOTE` severity parsed from `**[NOTE]** Title` format (bold)
  - [ ] Test `NOTE` severity parsed from `- [NOTE] Title` format (bullet)
  - [ ] Test finding with `category: error-handling` line — category extracted, line stripped from description
  - [ ] Test finding with `category: naming` — different category value
  - [ ] Test finding without `category:` line — category is `None`
  - [ ] Test finding with `location: src/foo.py:45` line — location extracted, line stripped
  - [ ] Test finding without `location:` line — location is `None`
  - [ ] Test finding with both `category:` and `location:` — both extracted
  - [ ] Test `category:` extraction is case-insensitive (`Category:`, `CATEGORY:`)
  - [ ] Test existing finding formats still work (regression: PASS, CONCERN, FAIL unchanged)

- [ ] Success: `uv run pytest tests/review/test_parsers.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add parser tests for NOTE, category, and location extraction`

---

### T5: Extend frontmatter formatter with structured findings

- [ ] **Modify `_format_review_markdown()` in `src/squadron/cli/commands/review.py`**
  - [ ] After existing metadata fields in frontmatter (before `---` closer), insert findings block
  - [ ] Only emit `findings:` block when `result.findings` is non-empty
  - [ ] Each finding as a YAML list item: `id`, `severity`, `category`, `summary` (quoted), optional `location`
  - [ ] Add `_yaml_escape()` helper for summary strings (escape double quotes)
  - [ ] Existing prose body format unchanged

- [ ] Success: Generated frontmatter contains valid YAML with `findings:` array; summary values properly quoted; location omitted when `None`

**Commit:** `feat: emit structured findings in review frontmatter`

---

### T6: Tests for frontmatter formatter

- [ ] **Add tests in `tests/cli/test_review_format.py`** (create if needed)
  - [ ] Test frontmatter contains `findings:` block when findings present
  - [ ] Test each finding has `id`, `severity`, `category`, `summary` fields
  - [ ] Test finding with location includes `location:` field
  - [ ] Test finding without location omits `location:` field
  - [ ] Test summary with double quotes is properly escaped
  - [ ] Test frontmatter is valid YAML (parse with `yaml.safe_load`)
  - [ ] Test no `findings:` block when findings list is empty
  - [ ] Test prose body section unchanged (findings still appear as `### [SEVERITY] Title`)

- [ ] Success: `uv run pytest tests/cli/test_review_format.py -v` — all pass; `uv run pyright` — 0 errors

**Commit:** `test: add frontmatter structured findings formatter tests`

---

### T7: Extend JSON serialization

- [ ] **Extend `ReviewResult.to_dict()` in `src/squadron/review/models.py`**
  - [ ] Add `"structured_findings"` key to the returned dict
  - [ ] Value is a list of dicts, each with `id`, `severity`, `category`, `summary`, `location`
  - [ ] Derived from `self.structured_findings` property

- [ ] **Extend `ReviewFinding` serialization in `to_dict()`**
  - [ ] Add `"category"` and `"location"` to the finding dict in the existing `findings` array

- [ ] Success: `result.to_dict()["structured_findings"]` returns list of dicts; each dict has all expected keys; `uv run pyright` passes

---

### T8: Tests for JSON serialization

- [ ] **Add tests in `tests/review/test_models.py`** (extend)
  - [ ] Test `to_dict()` includes `"structured_findings"` key
  - [ ] Test `structured_findings` array contains correct number of items
  - [ ] Test each structured finding dict has `id`, `severity`, `category`, `summary`, `location`
  - [ ] Test `to_dict()` findings array includes `category` and `location` fields
  - [ ] Test empty findings produces empty `structured_findings` array

- [ ] Success: `uv run pytest tests/review/test_models.py -v` — all pass

**Commit:** `feat: add structured findings to JSON serialization`

(Commit covers T7 + T8)

---

### T9: Prompt enhancement for category tags

- [ ] **Add structured output instructions to review template system**
  - [ ] Determine injection point: review template rendering or prompt builder
  - [ ] Locate where system prompts are assembled for review templates (check `src/squadron/review/templates/` and prompt builder code)
  - [ ] Add instruction block requesting `category:` tags after finding headings
  - [ ] Include valid severity levels: `PASS`, `NOTE`, `CONCERN`, `FAIL`
  - [ ] Instructions should apply to all review types (code, slice, tasks, arch)
  - [ ] Do NOT modify individual template YAML files if a shared injection point exists

- [ ] Success: Running `sq review code --diff main -vv` shows the structured output instructions in the system prompt; instructions appear for all review template types

**Commit:** `feat: add structured output instructions to review prompts`

---

### T10: Full verification and cleanup

- [ ] **Run full test suite**
  - [ ] `uv run pytest` — all tests pass
  - [ ] `uv run pyright` — 0 errors
  - [ ] `uv run ruff check` — clean
  - [ ] `uv run ruff format --check` — clean

- [ ] **Verify existing review tests still pass** (regression check)
  - [ ] `uv run pytest tests/review/ -v` — all pass
  - [ ] `uv run pytest tests/cli/test_review*.py -v` — all pass (if existing)

- [ ] **Update CHANGELOG.md** with slice 143 entries under `[Unreleased]`

- [ ] **Update slice design verification walkthrough** with actual commands and output

- [ ] Success: CI-equivalent checks pass locally; no regressions

**Commit:** `docs: mark slice 143 structured review findings complete`
