---
docType: slice-design
slice: structured-review-findings
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies:
  - 142-pipeline-core-models-and-action-protocol
  - review-system (105/128)
interfaces:
  - 146-review-and-checkpoint-actions
  - 160-pipeline-intelligence (cross-iteration matching)
dateCreated: 20260330
dateUpdated: 20260330
status: complete
---

# Slice 143: Structured Review Findings

## Overview

Extend review output so that machine-readable structured findings appear in the YAML frontmatter of saved review files, alongside the existing prose body. This creates a single-file format where the frontmatter is the programmatic index and the markdown body is the human-readable detail.

This slice absorbs the scope of former 100-band slice 123 (Review Findings Pipeline), refocused for pipeline consumption. Automated triage and routing are deferred to the pipeline executor.

## Value

**Standalone value (before pipelines exist):** Every `sq review` command produces a review file with machine-readable structured findings in frontmatter. Scripts and tools can parse the YAML header without parsing markdown. `sq review code --diff main` immediately gains a structured output surface.

**Pipeline value:** The review action (slice 146) will consume structured findings from `ActionResult.findings` as typed data. The convergence loop (slice 160) will use `category + location` fingerprints for cross-iteration identity matching.

## Technical Scope

### What changes

1. **New model: `StructuredFinding`** — Typed dataclass in `review/models.py` with fields: `id`, `severity`, `category`, `summary`, `location`. This is the structured counterpart to the prose `ReviewFinding`.

2. **Extend `ReviewFinding`** — Add optional `category: str | None` and `location: str | None` fields (in addition to existing `file_ref`). The parser populates these when the agent output includes them.

3. **Extend `ReviewResult`** — Add `structured_findings: list[StructuredFinding]` property that derives structured findings from the parsed `findings` list. This is a computed property, not a separate parse path — one source of truth.

4. **Extend review parser** — Enhance `parsers.py` to extract `category` tags from agent output. Location is already partially captured via `file_ref`. The parser looks for `category: <tag>` lines within finding blocks.

5. **Extend frontmatter formatter** — `_format_review_markdown()` in `cli/commands/review.py` emits structured findings in the YAML frontmatter, matching the architecture spec format.

6. **Extend `to_dict()`** — Include structured findings in JSON output.

7. **Prompt enhancement** — Add instructions to review templates asking the agent to include `category:` and location tags in finding output, making structured extraction reliable.

### What does NOT change

- The prose markdown body format (unchanged, backward compatible)
- The `Verdict` / `Severity` enums
- The parser's existing regex-based finding extraction (extended, not replaced)
- The review execution flow in `review_client.py`
- The terminal display (Rich output) — it continues to use `ReviewFinding` fields
- The pipeline `ActionResult` model — its `verdict: str | None` and `findings: list[object]` fields are already designed to accept these types

## Dependencies

- **Slice 142 (complete):** Pipeline core models — `ActionResult.findings` typed as `list[object]`, ready to receive `StructuredFinding` instances
- **Review System (105/128, complete):** `ReviewResult`, `ReviewFinding`, parser, formatter, review client

## Architecture

### Data Flow

```
Agent output (markdown)
    │
    ▼
parsers.py: parse_review_output()
    │  extracts verdict, findings (existing)
    │  NEW: extracts category + location from finding blocks
    │
    ▼
ReviewResult
    │  .findings: list[ReviewFinding]  (existing, extended with category/location)
    │  .structured_findings: list[StructuredFinding]  (NEW, computed property)
    │
    ├──▶ Terminal display (Rich) — uses .findings (unchanged)
    │
    ├──▶ JSON output — uses .to_dict() (extended with structured_findings)
    │
    └──▶ Markdown file — frontmatter includes structured findings index
                          body includes prose findings (unchanged)
```

### StructuredFinding Model

```python
@dataclass
class StructuredFinding:
    """Machine-readable finding for frontmatter index and pipeline consumption."""
    id: str              # e.g. "F001", auto-assigned if not in agent output
    severity: str        # "concern" | "fail" | "note" | "pass"
    category: str        # structural tag: "error-handling", "naming", etc.
    summary: str         # one-line description
    location: str | None # file:line reference, e.g. "src/foo.py:45"
```

### Severity Mapping

The existing `Severity` enum has three values: PASS, CONCERN, FAIL. The architecture spec adds `note` as a fourth level. Design decision:

- **Add `NOTE` to the `Severity` enum** — `NOTE` is lower severity than `CONCERN`. It represents informational findings that don't warrant concern.
- Mapping for structured output: `PASS` → `"pass"`, `NOTE` → `"note"`, `CONCERN` → `"concern"`, `FAIL` → `"fail"`
- The parser maps case-insensitively: `note`, `NOTE`, `Note` all resolve to `Severity.NOTE`

### Enhanced Frontmatter Format

Current frontmatter:
```yaml
---
docType: review
verdict: CONCERNS
aiModel: claude-sonnet-4-6
# ... other metadata
---
```

Enhanced frontmatter (additive):
```yaml
---
docType: review
verdict: CONCERNS
aiModel: claude-sonnet-4-6
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Missing error handling in parse_config"
    location: src/squadron/pipeline/executor.py:45
  - id: F002
    severity: note
    category: naming
    summary: "Variable name 'x' is unclear"
    location: src/squadron/pipeline/actions/dispatch.py:12
# ... other metadata
---
```

### Category Extraction Strategy

The agent's prose output doesn't naturally include structured category tags. Two approaches work together:

1. **Prompt-driven:** Add instructions to review template system prompts asking the agent to emit `category: <tag>` on the line following a finding heading. This is the primary mechanism.

2. **Parser inference:** When `category:` is missing from agent output, the parser assigns `"uncategorized"`. No guessing — explicit is better than inferred.

Template prompt addition (appended to system prompts):
```
For each finding, include a category tag on the line immediately after the heading:
### [CONCERN] Missing error handling
category: error-handling
```

### Finding ID Assignment

Finding IDs (`F001`, `F002`, ...) are auto-assigned during structured finding construction, not extracted from agent output. This keeps ID assignment deterministic and decoupled from agent behavior. The ID is a sequential counter within a single review result, not a persistent identifier.

For cross-iteration identity matching (slice 160), the identity key is `(category, location)`, not `id`.

## Implementation Details

### 1. Model Changes (`review/models.py`)

```python
class Severity(StrEnum):
    PASS = "PASS"
    NOTE = "NOTE"        # NEW
    CONCERN = "CONCERN"
    FAIL = "FAIL"

@dataclass
class ReviewFinding:
    severity: Severity
    title: str
    description: str
    file_ref: str | None = None
    category: str | None = None    # NEW
    location: str | None = None    # NEW

@dataclass
class StructuredFinding:
    """Machine-readable finding for frontmatter and pipeline consumption."""
    id: str
    severity: str
    category: str
    summary: str
    location: str | None = None
```

`ReviewResult` gains a computed property:

```python
@property
def structured_findings(self) -> list[StructuredFinding]:
    """Derive structured findings from parsed findings list."""
    result: list[StructuredFinding] = []
    for i, f in enumerate(self.findings, 1):
        result.append(StructuredFinding(
            id=f"F{i:03d}",
            severity=f.severity.value.lower(),
            category=f.category or "uncategorized",
            summary=f.title,
            location=f.location or f.file_ref,
        ))
    return result
```

### 2. Parser Changes (`review/parsers.py`)

Extend `_extract_findings()` to capture `category:` and location from finding blocks:

- After extracting the finding heading and body, scan the first few lines of the body for `category: <value>` pattern
- Extract location from `file_ref` pattern (already supported) or from explicit `location:` tag
- Strip the `category:` line from the description so it doesn't appear as prose

Add `NOTE` to `_SEVERITY_MAP`:
```python
_SEVERITY_MAP["NOTE"] = Severity.NOTE
```

Update `_FINDING_RE` to include `NOTE` as a valid severity keyword.

### 3. Formatter Changes (`cli/commands/review.py`)

Extend `_format_review_markdown()` to emit structured findings in frontmatter:

```python
if result.findings:
    lines.append("findings:")
    for sf in result.structured_findings:
        lines.append(f"  - id: {sf.id}")
        lines.append(f"    severity: {sf.severity}")
        lines.append(f"    category: {sf.category}")
        lines.append(f'    summary: "{_yaml_escape(sf.summary)}"')
        if sf.location:
            lines.append(f"    location: {sf.location}")
```

This block is inserted into the frontmatter between the existing metadata fields and the closing `---`.

### 4. Template Prompt Enhancement

Add a structured output instruction block to the review template system. This should be injected into all review template system prompts via the template rendering pipeline, not hardcoded per template.

Location: Add to the prompt builder or template base, so all review types (code, slice, tasks, arch) get the instruction.

Content:
```
## Output Structure Requirements

For each finding, include a category tag on the line immediately after the heading:

### [CONCERN] Finding title
category: error-handling

Valid severity levels: PASS, NOTE, CONCERN, FAIL

Use NOTE for informational observations that don't require action.
Use CONCERN for issues that should be addressed but don't block progress.
Use FAIL for issues that must be fixed before proceeding.
```

### 5. Serialization Changes

Extend `ReviewResult.to_dict()`:
```python
def to_dict(self) -> dict[str, object]:
    return {
        # ... existing fields ...
        "structured_findings": [
            {
                "id": sf.id,
                "severity": sf.severity,
                "category": sf.category,
                "summary": sf.summary,
                "location": sf.location,
            }
            for sf in self.structured_findings
        ],
    }
```

## Integration Points

### Slice 146 (Review and Checkpoint Actions)
The review action will access `ReviewResult.structured_findings` and populate `ActionResult.findings` with `StructuredFinding` instances. This is the typed bridge between the review system and the pipeline.

### Slice 160 (Pipeline Intelligence — Convergence)
Cross-iteration identity matching uses `(category, location)` as the finding fingerprint. A finding at the same category and location across iterations is "persisting" (full weight in convergence scoring). A finding at a new category or location is "novel" (decayed weight).

### Backward Compatibility
- Review files without `findings:` in frontmatter continue to work — the parser already handles missing frontmatter fields
- The `NOTE` severity is additive — existing `PASS`/`CONCERN`/`FAIL` handling is unchanged
- Terminal display uses `ReviewFinding` fields, which are extended but not changed

## Success Criteria

1. `sq review code --diff main` produces a review file with structured findings in YAML frontmatter
2. Each finding in frontmatter has `id`, `severity`, `category`, `summary`, and optional `location`
3. `StructuredFinding` dataclass is importable from `squadron.review.models`
4. `ReviewResult.structured_findings` returns a list derived from parsed findings
5. JSON output (`--output json`) includes `structured_findings` array
6. `NOTE` severity is supported in parser, models, and output
7. Category extraction works when agent includes `category:` tag; defaults to `"uncategorized"` when absent
8. Existing review tests continue to pass (backward compatible)
9. All new code passes pyright strict and ruff checks

## Verification Walkthrough

```bash
# 1. Verify StructuredFinding is importable
uv run python -c "from squadron.review.models import StructuredFinding; print(StructuredFinding.__dataclass_fields__.keys())"
# Actual: dict_keys(['id', 'severity', 'category', 'summary', 'location'])

# 2. Verify NOTE severity
uv run python -c "from squadron.review.models import Severity; print(list(Severity))"
# Actual: [<Severity.PASS: 'PASS'>, <Severity.NOTE: 'NOTE'>, <Severity.CONCERN: 'CONCERN'>, <Severity.FAIL: 'FAIL'>]

# 3. Run all tests
uv run pytest
# Actual: 761 passed

# 4. Type check
uv run pyright
# Actual: 0 errors, 0 warnings, 0 informations

# 5. Lint and format
uv run ruff check && uv run ruff format --check
# Actual: All checks passed! 185 files already formatted

# 6. Run a code review to verify end-to-end (manual)
# sq review code --diff main -v
# Expected: review file in project-documents/user/reviews/ with findings: array in frontmatter
# Caveat: requires active API credentials; automated tests cover formatter output
```

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agent doesn't include `category:` tags despite prompt instruction | Medium | Low | Parser defaults to `"uncategorized"` — output is still structured, just less specific. Prompt tuning over time improves category coverage. |
| Parser regex changes break existing finding extraction | Low | High | Existing parser tests serve as regression gate. New patterns are additive — `NOTE` joins the existing `PASS\|CONCERN\|FAIL` alternation. |
| YAML frontmatter with findings becomes too long | Low | Low | Findings are compact one-liners. A review with 20 findings adds ~100 lines to frontmatter — acceptable. |

## Effort

3/5 — Model additions are straightforward. Parser extension requires careful regex work with existing patterns. Prompt enhancement and testing across review types add integration effort.
