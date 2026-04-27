---
docType: slice-design
slice: review-finding-location-required
project: squadron
parent: user/architecture/900-arch.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260427
dateUpdated: 20260427
status: design complete
relatedIssues: [10]
---

# Slice Design: Required Code-Location Citation on Every Review Finding

## Overview

Fixes [issue #10](https://github.com/ecorkran/squadron/issues/10). Review
findings inconsistently cite a code location: some are `path:line-range`,
some are `path` only, some have nothing. PASS findings almost never cite
a location. This is felt at response time (re-discovering what the reviewer
was looking at) and is load-bearing for upcoming ensemble-review work
(slices 182, 189) where deduplication relies on location as the key.

Three coordinated changes:

1. **Update all four review-template prompts** ([code.yaml](src/squadron/data/templates/code.yaml),
   [slice.yaml](src/squadron/data/templates/slice.yaml),
   [arch.yaml](src/squadron/data/templates/arch.yaml),
   [tasks.yaml](src/squadron/data/templates/tasks.yaml))
   to require `location:` on **every** finding (PASS included), with a
   precedence ladder per template type.

2. **Soft-fail validation in the parser**
   ([parsers.py](src/squadron/review/parsers.py)). Findings missing
   `location` get `location: -` auto-filled, tagged `missing-location`,
   and a WARNING is logged. Counts surface in the structured output
   so downstream tooling can flag low-quality reviews.

3. **Path-membership check (code reviews only)**. When the finding's
   `location` cites a `path:...` and the review has a diff, verify the
   path appears in the diff. WARNING-only — do not reject. Skipped for
   arch/slice/tasks reviews (no diff).

## Open questions (resolved)

1. **Hard-fail vs. soft-fail.** Soft-fail. Hard-fail penalizes
   otherwise-good model output and compounds the existing parser-drops-
   findings bug.
2. **Path validation strictness.** Diff-membership WARNING for code
   reviews. Promote to hard-reject later once we have real-world data.
3. **Standalone or part of finding-schema slice.** Standalone — small,
   well-scoped, doesn't need to wait.

## Per-template location guidance

The precedence ladder is the same everywhere; the **preferred** rung
shifts by template type because the artifact under review differs.

| Template | Preferred form           | Fallback        | Last resort |
|----------|--------------------------|-----------------|-------------|
| code     | `path:line` / `path:start-end` | `path#symbol`, `path` | `-` / `global` (justify) |
| slice    | `path:line` (slice doc) or code `path:line` | `path#section`, `path` | `-` / `global` (justify) |
| arch     | `path` (whole-doc), `path#section-heading` | `path:line` | `-` / `global` (justify, common for missing-coverage findings) |
| tasks    | code `path:line` (where the issue lives) | `path#symbol`, `path` | `-` / `global` (justify) |

For **multi-file** findings: cite a single primary location in
`location:`, mention the others in the prose body. The location field
is the *primary* anchor for dedup, not a complete listing.

## Future work (not in scope)

- **`task_ref` field.** For tasks reviews and ensemble review (slice
  189), an optional `task_ref:` (e.g. `T7` or
  `902-tasks.pipeline-verbosity#T7`) would let merged reviews answer
  "did three reviewers all flag T5?". Defer to a later slice — `location`
  must land first because it's the dedup key.
- **Promote diff-membership WARNING to hard-reject.** Once we've seen
  real-world false-positive rates.

## Verification walkthrough

Run after implementation; fill outputs into this section before closing
the slice.

1. **Schema validation.** Loading each of the four templates does not
   fail. (`uv run pytest tests/review/test_templates.py -v`)
2. **Parser soft-fail.** Feed a synthetic review body with a finding
   missing `location:`; assert `ReviewFinding.location == "-"` and a
   WARNING log message names the finding ID.
3. **Path-membership WARNING.** Feed a synthetic code review where one
   finding cites `src/nonexistent.py:42` and the diff covers only
   `src/squadron/foo.py`. Assert WARNING logged, finding still parsed.
4. **End-to-end (code).** `uv run sq review code <slice>` produces a
   review where every finding has a non-`-` `location:` field.
5. **End-to-end (arch).** `uv run sq review arch <slice>` produces a
   review where every finding has a `location:` field; cross-cutting
   findings use `-` with prose justification.
6. **Full gate.** `uv run pytest -q && uv run ruff check && uv run pyright`.
