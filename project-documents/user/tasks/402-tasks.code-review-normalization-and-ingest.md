---
docType: tasks
slice: code-review-normalization-and-ingest
project: squadron
lld: user/slices/402-slice.code-review-normalization-and-ingest.md
dependencies:
- 320
- 323
projectState: 0.24.1 released with slice 401 merged; slice 402 design complete, all
  decisions decided
dateCreated: 20261024
dateUpdated: 20261024
status: not_started
---

# Tasks: Code-Review Normalization and Ingest

## Context Summary
- Slice 402 puts `sq review code` findings into the audit category buckets. The `code` template asks for a category from a closed vocabulary (`ReviewCategory`: the ten `AuditCategory` values plus `correctness`), the review client normalizes what comes back, and a new `sq metrology ingest-reviews` command writes one `code_review` record per code-review file into the metrology store. Historical reviews are mapped read-side through a fixed alias table.
- All decisions live in the slice design (the `lld` above), D1–D9. Each task cites its decision. Read it before starting the task. The module table is under Architecture → Component Structure, the data flow and the ingest failure-mode table are under Data Flow, and the record schema is under Database / Storage Schema.
- Prerequisites on `main`: `AuditCategory` in `metrology/models.py` (re-exported by `metrology/audit_models.py`), `tests/metrology/test_audit_skill_sync.py`, the disjoint-severity test in `tests/metrology/test_audit_models.py`, `MetrologyStore` with `write_snapshot` / `snapshot_record_id` as the replace-by-id pattern, and `cli/commands/metrology_snapshot.py` as the sub-command pattern.
- Contract freeze: `parse_review_output` doesn't change. Arch, slice, tasks and judge templates and their output don't change. `AuditCategory` values, the audit parser and the tech-debt-audit skill don't change. `schema_version` doesn't move.
- Branch: `402-slice.code-review-normalization-and-ingest`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`.
- New modules stay at ~300 lines or less. Live runs (ingest over squadron's reviews directory, one live `sq review code`) are pre-authorized.
- Next slices: 403 (rollups, reads `list_code_reviews`) and 420 (scores implementation replays).

## Task 1: Slice branch — Effort 1
- [ ] Create `402-slice.code-review-normalization-and-ingest` from the target
- [ ] Success: `git branch --show-current` prints the slice branch

## Task 2: Vocabulary leaf module (D1, D2) — Effort 2
- [ ] Create `src/squadron/core/finding_categories.py`. It imports only `enum`
- [ ] Move `AuditCategory` there from `metrology/models.py`, unchanged: same members, values, docstring
- [ ] Add `ReviewCategory(StrEnum)` in the same module: the ten `AuditCategory` members with identical names and values, plus `CORRECTNESS = "correctness"`. Docstring states why `correctness` is review-only (D1)
- [ ] `metrology/models.py` imports `AuditCategory` from the leaf and keeps it importable from there (and in `__all__` if the module has one). `metrology/audit_models.py` keeps its existing re-export working
- [ ] Success: `grep -rn "class AuditCategory" src/` finds only the leaf module
- [ ] Success: the full `tests/metrology/` suite and `tests/pipeline/actions/test_dispatch_pre_emption.py` pass with no test edits
- [ ] Commit: `refactor(core): move AuditCategory to a finding_categories leaf module`

## Task 3: Template flag (D3) — Effort 2
- [ ] Add `normalize_categories: bool = False` to `ReviewTemplate` in `squadron/review/templates/__init__.py`, read from the YAML key `normalize_categories`. An absent key is `False`. A non-bool value fails template loading with the existing validation error, never a coerced value
- [ ] Set `normalize_categories: true` in `data/templates/code.yaml` only. Don't touch `arch.yaml`, `slice.yaml`, `tasks.yaml` or the judge templates
- [ ] Success: `tests/review/test_templates.py` and `tests/review/test_user_templates.py` pass

## Task 4: Template flag tests — Effort 1
- [ ] In `tests/review/test_templates.py`: the built-in `code` template loads with `normalize_categories is True`; `arch`, `slice`, `tasks` load with `False`; a YAML without the key loads `False`; a YAML with `normalize_categories: "yes"` fails to load
- [ ] Success: tests pass

## Task 5: `code.yaml` category vocabulary block (D3, Mitigation Strategies) — Effort 2
- [ ] Add a block to the `code.yaml` prompt, placed before the output structure block, that starts with a line `Category vocabulary:` and lists all eleven `ReviewCategory` values, each backticked with a one-line definition. Take the ten audit definitions from the tech-debt-audit skill that `test_audit_skill_sync.py` reads. `correctness`: the code behaves wrongly (wrong result, broken contract, crash)
- [ ] Make the per-finding `category:` tag required in the prompt, following the arch template's `category:` tag pattern
- [ ] The output structure block's category fill slot is the placeholder `<one value from the category vocabulary>`. No concrete category value appears in or near any fill slot (CLAUDE.md "Hallucination traps")
- [ ] Success: `tests/review/test_builtin_code.py` passes; fix any assertion that pinned the old prompt text only where the prompt text itself changed

## Task 6: Review category sync test (D8) — Effort 2
- [ ] Create `tests/metrology/test_review_category_sync.py` asserting:
  1. `{m.value for m in ReviewCategory} == {m.value for m in AuditCategory} | {"correctness"}`
  2. The backticked values in `code.yaml`'s vocabulary block equal the `ReviewCategory` values in both directions. Locate the block from the `Category vocabulary:` line through the next blank-line-separated heading. Reuse the lenient backtick matching from `test_audit_skill_sync.py` (import or extract a shared helper; don't copy it). Failure messages name the missing and the extra values
  3. `code.yaml` sets `normalize_categories: true`; `arch.yaml`, `slice.yaml`, `tasks.yaml` don't
- [ ] `test_audit_skill_sync.py` and the disjoint-severity test stay unchanged, apart from a helper extraction if item 2 needs one
- [ ] Success: deleting `` `correctness` `` from `code.yaml` makes the test fail naming `correctness`; revert, and it passes
- [ ] Success: `tests/metrology/test_review_category_sync.py tests/metrology/test_audit_skill_sync.py tests/metrology/test_audit_models.py` pass
- [ ] Commit: `feat(review): add category vocabulary and normalization flag to code template`

## Task 7: `normalize_category` (D4) — Effort 2
- [ ] Create `squadron/review/categories.py` with a frozen dataclass `NormalizedCategory(category: ReviewCategory | None, raw_category: str | None)` and `normalize_category(raw: str | None) -> NormalizedCategory`
- [ ] Rules, per the Data Flow write-time block:
  - [ ] `None` or blank → `(None, None)`. Never `other`
  - [ ] exact `ReviewCategory` value → `(member, None)`
  - [ ] matches after lenient normalization (casefold, trim, strip backticks and quotes, spaces and underscores to hyphens) → `(member, raw as emitted)`
  - [ ] anything else → `(OTHER, raw as emitted)`
- [ ] Expose the lenient-normalization step as a public function (`lenient_category_key(raw) -> str`) so Task 15 reuses it. No alias table here (D4)
- [ ] Success: module imports only stdlib and `squadron.core.finding_categories`

## Task 8: `normalize_category` tests — Effort 1
- [ ] Create `tests/review/test_categories.py`, parametrized over: `None`, `""`, every `ReviewCategory` value, `` `Correctness` ``, `"Test Debt"`, `"test_debt"`, `'"security-hygiene"'`, `"error-handling"` (→ `other`, raw kept, D4: the alias table is read-side only), `"design/typing"` (→ `other`)
- [ ] Assert `raw_category is None` exactly when the input was already canonical or missing
- [ ] Success: tests pass

## Task 9: Finding and result fields — Effort 2
- [ ] In `squadron/review/models.py` add `raw_category: str | None = None` to `ReviewFinding` and `StructuredFinding`, and `categories_normalized: bool = False` to `ReviewResult`
- [ ] `ReviewResult.to_dict()`: `categories_normalized` always present (bool); `raw_category` present per finding and per structured finding, `None` when not set (API Contracts → Review output additions)
- [ ] Where `models.py` builds `StructuredFinding` from `ReviewFinding` (the `category=f.category or "uncategorized"` site), carry `raw_category` across
- [ ] Success: `tests/review/test_models.py` passes

## Task 10: Client normalization hook and write-time WARNING — Effort 3
- [ ] In the parse closure in `squadron/review/review_client.py` (the only `parse_review_output` call site), when `template.normalize_categories` is true: replace each finding's `category` with `normalize_category(...).category` (its value, or `None`), set its `raw_category`, and set `result.categories_normalized = True`. When false, change nothing
- [ ] Write-time failure mode (Data Flow): when the flag is set, the result has at least one finding, and no finding carried a `category:` tag, log a WARNING naming the template and the finding count. The review is still produced, every category stays `None` (`uncategorized`), none becomes `other`
- [ ] Keep the hook a small helper function (in `categories.py` or the client), not inline growth of the closure
- [ ] Verbose finding display shows the normalized category through the existing field; add no new verbose output
- [ ] Success: `tests/review/test_review_client.py` passes unchanged

## Task 11: Frontmatter writer — Effort 2
- [ ] In `squadron/review/persistence.py`: write `categoriesNormalized: true` at file level only when `result.categories_normalized` is true; write `rawCategory: "<yaml_escape(raw)>"` under a finding only when `raw_category` is set. Finding `category` keeps the existing `uncategorized` sentinel for `None`
- [ ] Success: `tests/review/test_persistence.py` and `tests/review/test_persistence_migration.py` pass unchanged

## Task 12: Write-time tests — Effort 3
- [ ] `tests/review/test_models.py`: `to_dict()` carries `categories_normalized` and per-finding `raw_category` (null and set)
- [ ] `tests/review/test_persistence.py`: a normalized result writes `categoriesNormalized: true` and a quoted `rawCategory` only on the finding that has one; a result with a raw string containing a quote round-trips through `parse_frontmatter`; a non-normalized result writes neither key
- [ ] `tests/review/test_review_client.py`, using a canned model response with one canonical, one non-canonical (`Test Debt`), one out-of-vocabulary (`error-handling`) and one untagged finding:
  - [ ] with the `code` template: categories are `test-debt`, `test-debt` (raw `Test Debt`), `other` (raw `error-handling`), `None`; `categories_normalized` is true
  - [ ] with the `arch` template: categories are exactly the raw strings, no `raw_category`, `categories_normalized` false (Functional Requirement 7)
- [ ] A second canned response with findings and no `category:` tags, `code` template: `caplog` has the WARNING naming the template and count, and no category is `other`. A response with zero findings logs no WARNING
- [ ] Success: `tests/review/` passes
- [ ] Commit: `feat(review): normalize code-review finding categories at write time`

## Task 13: Findings-addressed mixed-round test (Integration Requirements) — Effort 1
- [ ] In `tests/pipeline/test_findings_addressed.py`, add a test with a round-1 finding categorized `error-handling` and a round-2 finding at the same location categorized `error-handling-observability`. Assert the screen in `pipeline/actions/findings_addressed/screens.py` doesn't settle it as re-found and doesn't raise. No production change
- [ ] Success: test passes
- [ ] Commit: `test(pipeline): cover mixed pre- and post-normalization finding categories`

## Task 14: Review record models (Storage Schema, D6) — Effort 2
- [ ] Create `squadron/metrology/review_models.py` with `CodeReviewFinding` and `CodeReviewRecord` exactly as in Database / Storage Schema. `severity` is `review.models.Severity`; `category` is `ReviewCategory | None`; `verdict` is `review.models.Verdict`
- [ ] A validator rejects `verdict == UNKNOWN` (D6)
- [ ] Success: module imports `ReviewCategory` from `squadron.core.finding_categories`, not from metrology

## Task 15: Envelope and store methods (D5, Patterns and Conventions) — Effort 3
- [ ] Add `RECORD_TYPE_CODE_REVIEW = "code_review"` beside the other record-type constants and `code_review: CodeReviewRecord | None = None` on `MetrologyRecord`
- [ ] In `store.py` add `code_review_record_id(project_id, review_path) -> str` returning `codereview-{sha256(project_id)[:12]}-{sha256(review_path)[:12]}`, the same shape as `snapshot_record_id`
- [ ] `write_code_review(record) -> str`: raises `MetrologyStoreError` if `record.record_id` doesn't equal the derived id; otherwise writes atomically, replacing any record with that id, as `write_snapshot` does
- [ ] `list_code_reviews(project_id) -> list[CodeReviewRecord]`: only that project's `code_review` records, newest `reviewed_at` first, unreadable siblings skipped with a WARNING like the other list methods
- [ ] Success: `tests/metrology/test_store.py` and `tests/metrology/test_models.py` pass unchanged (existing record types load)

## Task 16: Record and store tests — Effort 2
- [ ] Create `tests/metrology/test_review_models.py`: a valid record round-trips through JSON; `UNKNOWN` verdict is rejected; a `None` category serializes as null, not `other`
- [ ] Create `tests/metrology/test_review_store.py`: id derivation is stable and differs by path and by project; writing twice with the same id leaves one file and the second content; a mismatched id raises `MetrologyStoreError`; listing filters by project, sorts newest first, and skips a corrupt sibling with a WARNING (`caplog`); an existing sample record still loads beside a code-review record
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): add code_review record type and store methods`

## Task 17: Read-side alias table (D7) — Effort 2
- [ ] Create `squadron/metrology/review_category_map.py` with a module-level `dict[str, ReviewCategory]` holding exactly the D7 table rows, keyed by `lenient_category_key` of each historical string
- [ ] `map_historical_category(raw: str | None) -> NormalizedCategory`:
  - [ ] `None`, blank or `uncategorized` → `(None, None)`
  - [ ] key in the table → `(member, raw)`, with `raw` set only when it differs from the member value
  - [ ] otherwise → `(OTHER, raw)`. Compound strings like `design/typing` aren't split
- [ ] Success: the table has 16 historical strings plus no others

## Task 18: Alias table tests — Effort 1
- [ ] Create `tests/metrology/test_review_category_map.py`, parametrized over every D7 string (including `correctness` → `correctness`), `Error Handling` (lenient key), `uncategorized` → `None`, `None`, `style` and `code-quality` → `other`, `design/typing` → `other` with raw kept
- [ ] Assert every table value is a `ReviewCategory` member and every key is already in lenient form
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): add read-side category map for historical code reviews`

## Task 19: Ingest fixture directory (Technical Requirements) — Effort 2
- [ ] Create `tests/metrology/fixtures/review_ingest/` with frontmatter copied verbatim from `project-documents/user/reviews/` (body may be truncated to one line):
  - [ ] `103-review.code.cli-foundation.md` (no `reviewedSha`, no `targetKind`)
  - [ ] `947-review.code.unattended-pipelines-cost-cap-no-invented-gates-blocked-tasks-background-shells.md` (`targetKind: slice`)
  - [ ] `github.com-ecorkran-squadron-116-review.code.md` (PR review)
  - [ ] `0-review.code.review-1.md` (blank `sourceDocument`, `slice: unknown`)
  - [ ] one arch review of your choice
- [ ] Add synthetic files, each named for what it tests: a code review with `verdict: UNKNOWN`, a file with malformed frontmatter, a code review missing `verdict`, and a code review written in the new format (`categoriesNormalized: true`, one finding with `rawCategory`)
- [ ] The non-UTF-8 file is created at test time in `tmp_path`, not committed
- [ ] Success: files exist; nothing outside `tests/` changes

## Task 20: Ingest module (Data Flow, D5, D6) — Effort 4
- [ ] Create `squadron/metrology/review_ingest.py` with a function that takes the project id, repo root, the list of file paths and the store, and returns a result dataclass with `ingested`, `replaced`, `skipped_not_code`, `skipped_unknown_verdict`, and `failed: list[tuple[Path, str]]`
- [ ] A separate function resolves inputs: each `PATHS` entry is a file or a directory (its `*.md`); a nonexistent entry raises an error naming it before anything is written. With no `PATHS`, use `resolve_reviews_dir(cwd)`; a missing directory raises naming the resolved path
- [ ] Per file, read the bytes once and parse frontmatter with `parse_frontmatter` from that text. Unreadable, not UTF-8, no frontmatter, or missing `reviewType` / `verdict` → WARNING with the path, appended to `failed`, continue
- [ ] `reviewType != code` → `skipped_not_code`; `verdict: UNKNOWN` → `skipped_unknown_verdict`
- [ ] Build the record:
  - [ ] `review_path`: posix path relative to the repo root when inside it, else absolute
  - [ ] `commit_sha` = `reviewedSha` or `None`; `reviewed_at` = `dateCreated`
  - [ ] `slice_index` from the `sourceDocument` basename only, matched by one module constant pattern for `{n}-slice.` / `{n}-tasks.` (D6). The review filename is never used
  - [ ] `read_side_mapped = not categoriesNormalized`
  - [ ] findings: severity outside `Severity` → `unnormalized_count += 1`, dropped. Write-time files: `uncategorized`/absent → `None`, else the stored value must be a `ReviewCategory` value (a value that isn't → the file fails, listed under `failed`), `rawCategory` carried. Read-side files: `map_historical_category`
- [ ] Count `replaced` when a record with that id already existed. `MetrologyStoreError` propagates to the caller (the CLI aborts)
- [ ] Success: module ≤ ~300 lines, functions ≤ ~50 lines

## Task 21: Ingest tests — Effort 3
- [ ] Create `tests/metrology/test_review_ingest.py` over the Task 19 fixtures with a `MetrologyStore` in `tmp_path`:
  - [ ] the four real code reviews and the new-format file are ingested; the arch review is `not-code-review`; the UNKNOWN file is `unknown-verdict`
  - [ ] malformed and missing-`verdict` files are in `failed`, each logs a WARNING with its path (`caplog`), and the other files are still written
  - [ ] the 947 record has `slice_index == 947`, `commit_sha` equal to the file's `reviewedSha`, `error-handling` mapped to `error-handling-observability`, `read_side_mapped` true
  - [ ] the 103 record has `commit_sha is None`; the PR and `0-review` records have `slice_index is None`
  - [ ] the new-format record has `read_side_mapped` false and keeps `raw_category`
  - [ ] a non-UTF-8 file in `tmp_path` is in `failed`
  - [ ] re-ingesting after editing the 947 copy's findings in `tmp_path` leaves one record for that path with the new findings, and `replaced` counts it
  - [ ] a nonexistent path raises and writes nothing
- [ ] Parametrized slice-index test: a `{n}-slice.` source, a `{n}-tasks.` source, a PR URL, and the blank `sourceDocument` of `0-review.code.review-1.md`
- [ ] Success: tests pass
- [ ] Commit: `feat(metrology): ingest code-review files into the metrology store`

## Task 22: `ingest-reviews` command (D9, API Contracts) — Effort 2
- [ ] Create `squadron/cli/commands/metrology_review_ingest.py` with `register_review_ingest_command(metrology_app)`, following `metrology_snapshot.py`: `PATHS` arguments (optional, multiple) and `--cwd`
- [ ] Mount it in `cli/commands/metrology.py` beside `register_snapshot_command`
- [ ] Derive the project id first; `MetrologyIdentityError` → error, exit 1, nothing written
- [ ] Print the three summary lines from API Contracts, then each failed path with its reason. Zero files found → `Ingested 0`, a WARNING naming the directory, exit 0
- [ ] Exit codes per the Data Flow failure-mode table. On `MetrologyStoreError`, print what was written so far and the error, exit 1
- [ ] Success: `sq metrology ingest-reviews --help` lists `PATHS` and `--cwd`

## Task 23: Command tests — Effort 2
- [ ] Create `tests/metrology/test_review_ingest_cli.py` with Typer's `CliRunner` and the store directory redirected to `tmp_path`:
  - [ ] fixture directory: summary counts match, exit 1 because of the failed files
  - [ ] only good files: exit 0
  - [ ] nonexistent `PATHS` entry: exit 1, store empty
  - [ ] missing default reviews directory: exit 1, message names it
  - [ ] empty directory: `Ingested 0`, WARNING, exit 0
  - [ ] store write error (store stub raising `MetrologyStoreError`): exit 1, partial count printed
  - [ ] identity failure: exit 1, store empty
- [ ] Success: tests pass
- [ ] Commit: `feat(cli): add sq metrology ingest-reviews`

## Task 24: Walkthrough steps 1–3 (Verification Walkthrough) — Effort 2
- [ ] Run steps 1–3 from the repo root against the real reviews directory, in order. Step 3 reads the record file under `~/.config/squadron/metrology/`
- [ ] Success: step 1 passes and fails as described; step 2 reports every `*review.code*` file as ingested (`read-side mapped`) or skipped with a reason, and a second run reports the same count, all replaced, with no new record files; step 3's record matches every stated field
- [ ] A defect found here is fixed with a test before checking this off

## Task 25: CHANGELOG and full validation — Effort 1
- [ ] Add `[Unreleased]` bullets: the new `sq metrology ingest-reviews` command, and code reviews now categorized into the audit vocabulary. User-facing, short
- [ ] Run `ruff format`, `ruff check`, `pyright` (zero errors) and the full `tests/` suite
- [ ] Success: all pass
- [ ] Commit: `docs: add CHANGELOG entries for code-review categories and ingest`

## Task 26: Walkthrough step 4, live review — Effort 2
- [ ] Pick a model alias from `sq models list` and run `sq review code 402 --model <alias>`
- [ ] Success: the review file has `categoriesNormalized: true`, every finding `category` is a `ReviewCategory` value or `uncategorized`, and any non-canonical emitted category carries `rawCategory`
- [ ] Run `sq metrology ingest-reviews` again; the new 402 record has `read_side_mapped` false
- [ ] Commit the review file: `review: add slice 402 code review from live verification`
