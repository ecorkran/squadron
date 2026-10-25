---
docType: slice-design
slice: code-review-normalization-and-ingest
project: squadron
parent: ../architecture/400-slices.code-quality-measurement.md
dependencies:
- 320
- 323
interfaces:
- 403
dateCreated: 20261022
dateUpdated: 20261025
status: complete
turns: 38
promptTokens: 2796590
cachedTokens: 2695294
cacheWriteTokens: 101222
completionTokens: 30681
durationSeconds: 305.6
costUsd: 1.963098
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Code-Review Normalization and Ingest

## Overview

`sq review code` findings carry whatever category string the model picks. The 116 code reviews in squadron's own reviews directory use 70 distinct strings (`error-handling`, `design`, `testing`, `dry`, `failure-mode-enumeration/error-handling`, ...), and 113 findings say `uncategorized`. Nothing counts them. 323's audit findings use a closed ten-value vocabulary (`AuditCategory`) and are counted, with a noise floor.

This slice puts code-review findings into the same buckets. The `code` template asks for a category from the audit vocabulary plus one review-only value, `correctness`. The review client normalizes what comes back against that closed set and keeps the model's raw string when it differs. A new `sq metrology ingest-reviews` command reads code-review files into 320's metrology store, one record per review file with findings inline. Reviews written before this slice are mapped read-side through a fixed alias table, and their records say so. Arch, slice and tasks reviews are not touched.

## Value

- **Developer value.** Review findings become countable next to audit findings for the first time. "error-handling-observability: 4 from review, 2 from audit" is answerable without a translation step.
- **Architectural enablement.** 403's rollup reports read the review record this slice writes. 420 reads it to score implementation replays.

## Technical Scope

**Included**
- `ReviewCategory`: a closed enum, the ten `AuditCategory` values plus `correctness`, in a new leaf module beside `AuditCategory` (moved there, re-exported from its current homes).
- The `code` template: a required `category:` tag, the vocabulary with a one-line definition per value, and a template flag that turns on write-time normalization.
- Write-time normalization in the review client for templates that set the flag. A raw string outside the set becomes `other` with the raw string kept. The frontmatter and JSON output carry the raw string and a file-level marker that the categories were normalized.
- The extended sync test: enum, audit skill and `code` template stay in step, and drift fails CI.
- The review record type in the metrology store (`code_review`), with store write and list methods.
- The read-side alias table for historical reviews.
- `sq metrology ingest-reviews`: reads code-review files, resolves project, commit and slice, writes one record per file, and can be re-run safely.

**Excluded**
- Arch, slice and tasks templates, their vocabularies and their output. They don't set the flag, so the shared parser's behavior for them is unchanged.
- The tech-debt-audit skill. Its vocabulary is reused as it stands.
- Any mapping between review severity and audit severity.
- Reports, rollups, trends and `other`-share reporting. These belong to 403.
- Ingesting earlier rounds from a review file's git history. Ingest reads the file as it is now.
- Ingest during `sq review` or a pipeline step. There is no pipeline hook, per the architecture. Records arrive only through the ingest command.

## Dependencies

### Prerequisites
- **320 (complete):** the metrology store, the `MetrologyRecord` envelope and `ProjectId` derivation.
- **323 (complete):** `AuditCategory`, `AuditSeverity`, `tests/metrology/test_audit_skill_sync.py` and the disjoint-severity test in `tests/metrology/test_audit_models.py`.
- No dependency on 400 or 401, and no code from either is imported. This slice follows two established patterns that predate it: optional sibling payloads on `MetrologyRecord` (322, 323, 177, and 400's `code_snapshot`), and sub-command modules mounted onto `metrology_app` from `cli/commands/metrology.py` (`audit delta`, `snapshot`). The mount point is `metrology_app`, which 320 owns.

### Interfaces Required
- `squadron.metrology.identity.derive_project_id(cwd)` for the record's project key.
- `squadron.documents.frontmatter.parse_frontmatter(text)` to parse frontmatter from the text read once per file (D5, failure-mode table).
- `squadron.review.reviews_dir.resolve_reviews_dir(...)` for the default ingest location. It also needs host, owner and repository, which ingest takes from the project id (`host/owner/.../repository`); a project id with fewer than three segments fails with a message asking for `PATHS`.
- `ReviewTemplate` loading in `squadron/review/templates/__init__.py`, which gets one new optional field.
- The parse closure in `squadron/review/review_client.py`, the only call site of `parse_review_output`.

## Architecture

### Component Structure

| Component | Location | Role |
|---|---|---|
| Vocabulary leaf | `squadron/core/finding_categories.py` (new) | `AuditCategory` (moved), `ReviewCategory` (new). No imports beyond `enum`. |
| Write-time normalizer | `squadron/review/categories.py` (new) | `normalize_category(raw) -> NormalizedCategory`. Applied to parsed findings when the template sets the flag. |
| Template flag | `squadron/review/templates/__init__.py`, `data/templates/code.yaml` | `normalize_categories: bool`, false by default. Set only in `code.yaml`. |
| Finding and result fields | `squadron/review/models.py` | `ReviewFinding.raw_category`, `StructuredFinding.raw_category`, `ReviewResult.categories_normalized`. |
| Frontmatter writer | `squadron/review/persistence.py` | `categoriesNormalized: true` at file level, and `rawCategory:` per finding when set. |
| Review record models | `squadron/metrology/review_models.py` (new) | `CodeReviewRecord`, `CodeReviewFinding`. |
| Read-side alias table | `squadron/metrology/review_category_map.py` (new) | A fixed `dict[str, ReviewCategory]` and `map_historical_category(raw)`. |
| Ingest | `squadron/metrology/review_ingest.py` (new) | Discovers files, parses frontmatter, builds records, writes them through the store. Returns the counts the CLI prints. |
| Store | `squadron/metrology/store.py` | `write_code_review`, `list_code_reviews`, `code_review_record_id`. |
| CLI | `squadron/cli/commands/metrology_review_ingest.py` (new) | A thin Typer shell mounted onto `metrology_app`, following the `metrology_snapshot.py` pattern. |

The vocabulary sits in `core` because both `review` (write time) and `metrology` (ingest) need it, and `metrology.models` already imports `review.models`. Putting `ReviewCategory` in `metrology.models` would make the review client import the metrology package at parse time.

### Data Flow

**Write time (new code reviews):**
```
model output
  → parse_review_output (shared parser, unchanged: category is the raw string or None)
  → review_client parse closure: template.normalize_categories?
      yes → normalize_category per finding:
              raw None            → category None, raw None        (frontmatter: uncategorized)
              raw ∈ ReviewCategory → category = member, raw None    (canonical spelling)
              casefold/trim match → category = member, raw = string as emitted
              otherwise           → category = other, raw = string as emitted
            result.categories_normalized = True
      no  → unchanged (arch, slice, tasks, judge templates)
  → persistence: frontmatter category = normalized value; rawCategory when set;
                 categoriesNormalized: true at file level
```

**Ingest:**
```
sq metrology ingest-reviews [PATHS] [--cwd]
  → project_id = derive_project_id(cwd)
  → files = PATHS (files or directories) or resolve_reviews_dir(cwd); *.md
  → for each file (read once; frontmatter parsed from those bytes):
      frontmatter unreadable              → failed (listed), continue
      reviewType != code                  → skipped: not-code-review
      verdict UNKNOWN                     → skipped: unknown-verdict
      else build CodeReviewRecord:
        commit   = reviewedSha, or None
        slice    = index from sourceDocument basename ({n}-slice. or {n}-tasks.), else None
        read_side_mapped = not categoriesNormalized
        findings: severity → review Severity (unrecognized → unnormalized_count)
                  category `uncategorized` or absent → None
                  WRITE_TIME → stored values validated against ReviewCategory
                  READ_SIDE_MAPPED → map_historical_category(raw)
      store.write_code_review(record)   (replaces a record with the same id)
  → print the counted summary; exit 1 if any file failed
```

**Ingest failure modes.** Each one is logged and changes the exit code. None of them is silent.

| Failure | Behavior |
|---|---|
| A `PATHS` argument doesn't exist | Error naming the path, exit 1, before anything is written. |
| Default reviews directory missing | Error naming the resolved directory, exit 1. |
| No `*.md` files found | `Ingested 0` and a WARNING naming the directory, exit 0. |
| Frontmatter unreadable (including a file that isn't valid UTF-8), or `reviewType`/`verdict` missing | WARNING with the path, listed under `Failed`, the run continues, exit 1. |
| Store write fails (`MetrologyStoreError`) | The run aborts. It prints what was written so far and the error, then exits 1. Re-running is safe because writes replace by id. |
**Write-time failure mode.** When a template sets `normalize_categories` and the model returns findings but not one carries a `category:` tag, the prompt change didn't take. The review client logs a WARNING naming the template and the finding count, and the review is still written, with every category `uncategorized`. A review with no findings doesn't trigger it, and a review with at least one tagged finding doesn't either. A review-client test with a canned response with no tags asserts the WARNING (`caplog`) and that no category becomes `other`.

### State Management
The only persisted state is the `code_review` records in the user-level metrology store (`~/.config/squadron/metrology/`). The review files stay the source. A record is a derived copy keyed on the review's content (D5). Re-ingesting re-derives it and replaces it in place, and a genuine re-review adds a new record. Nothing else in squadron reads these records in this slice.

## Technical Decisions

### D1 — A separate review-side enum, kept identical to the audit vocabulary by test
Status: decided
- `ReviewCategory` is its own `StrEnum`: the ten `AuditCategory` members with the same names and values, plus `CORRECTNESS = "correctness"`. A test asserts `{ReviewCategory} == {AuditCategory} ∪ {"correctness"}`.
- `correctness` is review-only because audit findings come from a tech-debt taxonomy with no slot for "this behaves wrong", which is a code review's main output (49 historical findings already use that exact string). `AuditCategory` doesn't gain it, so the audit's parser and noise floor are unchanged.
- Rejected: adding `correctness` to `AuditCategory`, which changes the audit vocabulary the architecture excludes.

### D2 — The vocabulary moves to a leaf module
Status: decided
- `AuditCategory` moves to `squadron/core/finding_categories.py` beside `ReviewCategory`. `metrology/models.py` and `metrology/audit_models.py` re-export it, so every existing import keeps working and serialized values don't change.
- This is the smallest change that lets the review client import the vocabulary without importing the metrology package (see Component Structure).

### D3 — Normalization is opt-in per template, after the shared parser
Status: decided
- `ReviewTemplate` gains `normalize_categories: bool = False`, read from YAML. Only `code.yaml` sets it. User overrides of `code.yaml` in `~/.config/squadron/templates/` without the key aren't normalized, and their frontmatter has no `categoriesNormalized` marker, so ingest maps them read-side. That's correct, because nobody prompted them with the vocabulary.
- Normalization runs in the review client's parse closure, which already holds the template. `parse_review_output` stays template-agnostic, so arch, slice and tasks output can't change.
- Rejected: keying on `template.name == "code"`. That's a label used as logic. Rejected: injecting the vocabulary into the prompt from the enum at build time. It would remove the third copy, but the prompt text would then live in two places, and the template file would stop being the reviewable prompt.

### D4 — Write-time matching is strict; the alias table is read-side only
Status: decided
- Write time matches the emitted string to a `ReviewCategory` value after only casefold, trimming, stripping backticks and quotes, and converting spaces and underscores to hyphens. Anything else becomes `other` with the raw string kept.
- The historical alias table (D7) is not applied at write time. A model that was prompted with the vocabulary and still emits `error-handling` is an out-of-vocabulary result, and that's useful evidence of vocabulary fit. Quietly fixing it would hide that. This follows 323's audit normalization.
- `raw_category` is set only when the emitted string differs from the canonical value, so in-vocabulary findings don't repeat themselves. A missing category stays missing: `None` in memory and the existing `uncategorized` sentinel in frontmatter, for consumer compatibility. It is never mapped to `other`.

### D5 — One record per review file, keyed on project and path
Status: decided
- Record id: `codereview-{sha256(project_id)[:12]}-{sha256(review_path)[:12]}`, the same shape as `snapshot_record_id`. Ingest always writes, so the new record replaces any existing record with that id. Re-ingesting is safe, and a fix to the D7 alias table reaches every record on the next run.
- A re-review that rewrites the same file replaces the earlier round's record. That's the architecture's "one review record per review file", and it keeps the store's record count at one per file. No consumer needs earlier rounds, and ingesting history is excluded.
- Rejected: keying on the file's content. That keeps a record per round, which nothing requires, and makes 403 deduplicate by path.

### D6 — Ingest skips what it can't count honestly
Status: decided
- Files with `reviewType` other than `code` are skipped and counted as `not-code-review`. Arch, slice and tasks reviews are never ingested.
- `verdict: UNKNOWN` files are skipped as `unknown-verdict`. An unparsed review with an empty findings list would count as zero findings, which reads as a clean review. That's the "absent is not zero" rule.
- A missing `reviewedSha` (37 historical files) doesn't block ingest. The record has `commit_sha = None`. That is the only reason a commit can be absent, so no reason field is stored. The commit is never inferred from the review file's own git history, because that's a later commit than the one reviewed.
- A slice index is resolved only from the `sourceDocument` basename (`{n}-slice.*` or `{n}-tasks.*`). PR reviews, blank `sourceDocument` and anything else leave it `None`, and 403 rolls those up at project level only. The review filename's index prefix isn't used: historical files include `0-review.code.review-1.md` with `slice: unknown`, which is the fabricated "slice 0" that persistence has since stopped writing. The pattern is the project's document-naming convention. It is defined once, as a module constant in `review_ingest.py`, and its test covers a slice source, a tasks source, a PR URL and the blank `sourceDocument` of `0-review.code.review-1.md`. A change to the naming scheme then fails that test instead of silently producing `None` slices.
- A finding severity outside `review.models.Severity` is counted in `unnormalized_count` and dropped from `findings`, never guessed (the `AuditRun` precedent).
- A file whose frontmatter can't be read is listed as failed. The other files are still ingested, and the command exits 1.

### D7 — The read-side alias table
Status: decided
- A fixed module-level dict from a lenient-normalized string (same rules as D4) to `ReviewCategory`. Compound strings such as `design/typing` aren't split. There are 9 compound findings in the corpus, and they go to `other` like any other string with no entry. Strings with no entry map to `other` with the raw string kept. `uncategorized` maps to missing.
- An entry exists only when the string is frequent and its historical meaning clearly matches the audit dimension. The threshold is four or more findings in the corpus (counted on 20261023), which covers the bulk of the historical findings in 16 strings. Everything else goes to `other` with the raw string kept, and the table can be extended later without migration, because ingest re-derives every record. The table:

| `ReviewCategory` | Historical strings |
|---|---|
| `error-handling-observability` | error-handling, observability |
| `test-debt` | testing, test-coverage |
| `architectural-decay` | design, design-principles, structure |
| `consistency-rot` | dry, project-conventions, consistency |
| `type-contract-debt` | typing |
| `performance-resource` | performance |
| `security-hygiene` | security |
| `documentation-drift` | documentation |
| `correctness` | correctness, concurrency |
| `other` (by design) | every string not listed, including `style` and `code-quality` |

- Every record built through this table has `read_side_mapped = true`, including an exact match like `correctness`. Reports can then always separate prompted categories from inferred ones.

### D8 — Sync test covers three copies
Status: decided
- A new `tests/metrology/test_review_category_sync.py`, next to 323's test. It asserts:
  1. `ReviewCategory` = `AuditCategory` ∪ {`correctness`} (D1).
  2. The backticked values in `code.yaml`'s category-vocabulary block equal `ReviewCategory` in both directions. The block is located by delimiter lines in the prompt (`Category vocabulary:` through the next blank-line-separated heading), using the same lenient backtick matching as the audit sync test.
  3. `code.yaml` sets `normalize_categories: true`, and `arch.yaml`, `slice.yaml` and `tasks.yaml` don't.
- 323's skill-to-enum test is unchanged, so skill to `AuditCategory` to `ReviewCategory` to template forms a chain. The disjoint-severity test is unchanged and still passes.

### D9 — Command name and placement
Status: decided
- `sq metrology ingest-reviews`, a flat command like `snapshot`.

### Technology Choices
No new dependencies. Pydantic for record models, PyYAML through `parse_frontmatter`, and Typer for the command, all already in use.

### Patterns and Conventions
- Envelope extension the way 322, 323, 177 and 400 did it: a new `RECORD_TYPE_CODE_REVIEW = "code_review"` constant and an optional sibling payload field. `schema_version` doesn't move.
- `ReviewCategory` is the only new enum. Skip reasons are counters, not stored values.
- Errors: see the ingest failure-mode table under Data Flow. `MetrologyIdentityError` (no project id) fails the command with exit 1 before anything is written.

## Implementation Details

### API Contracts

**CLI**
```
sq metrology ingest-reviews [PATHS]... [--cwd DIR]
```
- `PATHS`: review files or directories. When omitted, the resolved reviews directory for `--cwd`.
- Output: counts, followed by each failed path with its reason:
```
Ingested <n> code reviews into <store dir> (<n> replaced)
Skipped: <n> not code reviews, <n> unknown verdict
Failed: <n>
```
- A `Dropped: <n> findings with a severity outside the review scale` line follows the skipped line when any finding was dropped (each drop also logs a WARNING with the file and finding id). Relative `PATHS` are relative to the shell's current directory, not `--cwd`.
- Exit codes are in the failure-mode table under Data Flow.

**Review output additions**
- Frontmatter: `categoriesNormalized: true` at file level, written only when normalized. `rawCategory: "<string>"` per finding, written only when set and quoted with `yaml_escape`.
- `ReviewResult.to_dict()`: `categories_normalized` is always present (bool). `raw_category` is present per finding, null when not set.

### Database / Storage Schema

```python
class CodeReviewFinding(BaseModel):
    finding_id: str                      # F001... as written
    severity: Severity                   # review.models.Severity, never AuditSeverity
    category: ReviewCategory | None      # None = missing (uncategorized / absent)
    raw_category: str | None = None
    location: str | None
    summary: str

class CodeReviewRecord(BaseModel):
    record_id: str
    project_id: ProjectId
    review_path: str                     # relative to the repo root when inside it, else absolute
    commit_sha: str | None               # None = the file has no reviewedSha
    slice_index: int | None
    verdict: Verdict                     # never UNKNOWN (D6, validator)
    read_side_mapped: bool               # categories came from the D7 table
    reviewed_at: date                    # dateCreated
    ingested_at: datetime
    findings: list[CodeReviewFinding]
    unnormalized_count: int = 0
```
- Envelope: `MetrologyRecord.code_review: CodeReviewRecord | None = None`.
- Store: `write_code_review(record) -> str` checks that `record.record_id` matches the derived id and replaces any existing record with that id, as `write_snapshot` does. `list_code_reviews(project_id) -> list[CodeReviewRecord]` returns newest `reviewed_at` first and skips unreadable siblings with a WARNING, like the other list methods.
- Existing record types load unchanged, because the new field is optional and absent from old files.

## Integration Points

### Provides to Other Slices
- **403:** `CodeReviewRecord` via `MetrologyStore.list_code_reviews`. The contract: a `None` category is missing, not `other`. Records with `read_side_mapped` are labeled as such in any report. `commit_sha is None` or `slice_index is None` records roll up at project level only. Severity is reported on the review scale only.
- **403 and 420:** `ReviewCategory` from `squadron.core.finding_categories`, the review-side category set.

### Consumes from Other Slices
- **320:** store, envelope, `derive_project_id`. If project identity can't be derived, the command fails with the existing `MetrologyIdentityError` and writes nothing.
- **323:** `AuditCategory` (moved, values unchanged) and both existing sync and disjoint tests, unchanged.
- **Review persistence (existing):** the frontmatter fields `reviewType`, `verdict`, `reviewedSha`, `sourceDocument`, `dateCreated` and `findings`. Missing optional fields resolve to `None` or a reason. A missing `reviewType` or `verdict` makes the file fail ingest, never default.

## Success Criteria

### Functional Requirements
1. A new `sq review code` run produces frontmatter in which every finding's `category` is a `ReviewCategory` value or `uncategorized`, the file carries `categoriesNormalized: true`, and any finding whose emitted string wasn't canonical carries `rawCategory`.
2. An out-of-vocabulary emitted category is written as `other` with the raw string kept. A missing category is written as `uncategorized`, never `other`.
3. `sq metrology ingest-reviews` writes one `code_review` record per code-review file, keyed on project and path, with the commit when `reviewedSha` exists and the slice when `sourceDocument` names a slice or tasks file.
4. A second run over the same files, including after a re-review rewrote one, replaces the existing records and adds none.
5. Non-code reviews and `UNKNOWN`-verdict reviews are skipped with their reason. Every failure mode in the Data Flow table behaves as stated.
6. Historical files map through the D7 table, and their records carry `read_side_mapped = true`. `uncategorized` becomes a missing category.
7. Arch, slice and tasks review output is unchanged: same categories, no `rawCategory`, no `categoriesNormalized`.

### Technical Requirements
- The sync test (D8) fails if any one of enum, skill or template changes alone.
- The disjoint-severity test passes unchanged, and no code maps review severity to audit severity.
- Existing metrology record types load, and existing `AuditCategory` imports resolve.
- Unit tests for `normalize_category`, `map_historical_category`, the record validator (no UNKNOWN verdict), store write and list, and ingest over a fixture directory. The fixture contains real frontmatter copied from squadron reviews: one historical file without `reviewedSha` or `targetKind`, one `947-review.code.*` file with `targetKind: slice`, the PR review, `0-review.code.review-1.md`, and an arch review. It also has an `UNKNOWN`-verdict code review and a file with malformed frontmatter.
- Failure-mode tests. The malformed file is listed under `Failed`, logs a WARNING with its path (asserted with `caplog`), and makes the exit code 1 while the other files are still written. A nonexistent `PATHS` argument exits 1 and writes nothing. A store write error aborts with exit 1. Re-ingesting the 947 file after its findings change replaces its record, so there is still one record for that path. A file that isn't valid UTF-8 is listed under `Failed`.
- A review-client test with a canned model response proves normalization runs for the `code` template and not for `arch`. A second canned response with no `category:` tags proves the write-time WARNING.
- `ruff format`, `ruff check`, and `pyright` with zero errors.
- CHANGELOG bullet for the new command and the categorized code reviews.

### Integration Requirements
- 403 can list a project's code-review records by slice and count findings per `ReviewCategory`, separating write-time records from read-side-mapped ones, with no further change to this slice's record.
- The findings-addressed screen (`pipeline/actions/findings_addressed/screens.py`) matches a re-found finding on exact `(location, category)`. When round 1 was written before this slice, with a free-form category such as `error-handling`, and round 2 after, with `error-handling-observability`, the keys differ. That finding isn't screened as re-found, so it falls through to the judge, which is the existing behavior for any mismatch. A test with such a mixed pair asserts the screen doesn't settle it as re-found and doesn't raise.

### Verification Walkthrough

Run from the squadron repo root.

1. **The vocabulary stays in sync.** `uv run pytest tests/metrology/test_review_category_sync.py tests/metrology/test_audit_skill_sync.py tests/metrology/test_audit_models.py -q` passes. Delete `` `correctness` `` from `code.yaml`'s vocabulary block and the sync test fails, naming the missing value. Revert the edit.

2. **Ingest historical reviews.** `uv run sq metrology ingest-reviews`. Every `*review.code*` file is either ingested as `read-side mapped` or skipped with a reason. Run it again: the same count, all of them replaced, and no new records in the store directory.

3. **Inspect a record.** Open the store record for `947-review.code.*`. It has `record_type: code_review` and `slice_index: 947`. `commit_sha` equals the file's `reviewedSha`, `error-handling` is mapped to `error-handling-observability`, and `read_side_mapped` is true.

4. **A new code review is categorized at write time.** Once the slice is implemented, run `sq review code 402 --model <alias>` with a model alias from the Project Manager's configuration. The frontmatter has `categoriesNormalized: true`, and every finding `category` is one of the eleven values or `uncategorized`. Ingest again and open the new record: `read_side_mapped` is false.

### Walkthrough Results

Run 20261025 on the slice branch.

| Step | Result |
|---|---|
| 1 | `test_review_category_sync.py`, `test_audit_skill_sync.py` and `test_audit_models.py`: 18 passed. With the `correctness` line deleted from `code.yaml`'s vocabulary block: `AssertionError: ReviewCategory values missing from code.yaml: ['correctness']`. Reverted |
| 2 | `sq metrology ingest-reviews`: `Ingested 89 code reviews ... (0 replaced)`, `Skipped: 289 not code reviews, 7 unknown verdict`, `Failed: 1`. The failure was a tasks review with the verdict `RESOLVED`, checked before its review type; fixed so a non-code review is skipped whatever its verdict. Second run: `Ingested 89 ... (89 replaced)`, `Failed: 0`, and 89 `codereview-*` files in the store before and after |
| 3 | The 947 record: `record_type: code_review`, `slice_index: 947`, `commit_sha` equal to the file's `reviewedSha`, `error-handling` mapped to `error-handling-observability` (raw kept), `read_side_mapped: true`. Across all 89 records: 591 findings, 102 `other`, 113 missing, 55 `correctness`, 99 `error-handling-observability` |
| 4 | `sq review code 402 --model sonnet`: frontmatter has `categoriesNormalized: true` and every finding category is a `ReviewCategory` value. After ingest the 402 record has `read_side_mapped: false` and `commit_sha` of the reviewed commit |

Caveats found while running it:
- **The corpus changed since the design.** `103-review.code.cli-foundation.md`, `0-review.code.review-1.md` and the PR review now have verdict `UNKNOWN`, so they are skipped. The ingest fixtures use `156-review.code.pipeline-executor-hardening.md` for the no-`reviewedSha` case and a synthetic PR review with a known verdict.
- **`resolve_reviews_dir` needs host, owner and repository** (see Interfaces Required).
- **The saved structured findings gained a null `raw_category` key** (pipeline `findings` output), so one golden test was updated. The review file itself is unchanged for non-normalizing templates.
- **A review file deleted or renamed leaves its record behind.** Ingest never prunes; documented in `docs/COMMANDS.md`.

## Risk Assessment

### Technical Risks
- **The prompt change shifts code-review output.** Adding a required tag and an eleven-value list to a heavily used template could change finding counts or verdict consistency in ways tests don't see.
- **`other` dominates write-time findings.** If the model routinely picks `other`, the vocabulary doesn't fit code review. The architecture treats that as evidence to report (403), not something this slice tunes.

### Mitigation Strategies
- The vocabulary block reuses the arch template's proven `category:` tag pattern and sits before the output structure block. The structure block's fill slot is a placeholder (`<one value from the category vocabulary>`), never a concrete category, so a model that misses the vocabulary can't copy an example (the hallucination-trap rule).
- The walkthrough's step 4 is the live check. The parser is unchanged, so any regression is confined to what the model writes, and the raw string is always kept.

## Implementation Notes

### Development Approach
1. Leaf module: move `AuditCategory`, add `ReviewCategory`, add re-exports. Existing tests pass unchanged.
2. Template flag, `code.yaml` vocabulary block, and the sync test (D8).
3. `normalize_category`, the client hook, model fields, frontmatter, JSON and verbose output, and the review-client tests.
4. Record models, envelope field and store methods, with tests.
5. Alias table and `map_historical_category`, with tests against the corpus strings.
6. Ingest module and CLI, fixture-directory tests, then the walkthrough steps 1–4 against the real reviews directory.
7. CHANGELOG, then the walkthrough's step 4 (live review).
