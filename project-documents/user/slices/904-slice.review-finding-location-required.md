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

Four coordinated changes:

1. **Update all four review-template prompts** ([code.yaml](src/squadron/data/templates/code.yaml),
   [slice.yaml](src/squadron/data/templates/slice.yaml),
   [arch.yaml](src/squadron/data/templates/arch.yaml),
   [tasks.yaml](src/squadron/data/templates/tasks.yaml))
   to require `location:` on **every** finding (PASS included), with a
   precedence ladder per template type. **`unverified` is the explicit
   "I don't know" token** — instruct the model to use it rather than
   guess. Hallucinated locations are worse than `unverified` because
   they look authoritative.

2. **Soft-fail validation in the parser**
   ([parsers.py](src/squadron/review/parsers.py)). Findings missing
   `location` get `location: unverified` auto-filled and a WARNING is
   logged. The parser also normalizes `-`, `global`, and empty values
   to `unverified` so downstream tooling sees one consistent token.

3. **Diff-membership check (code reviews only)**. When the finding's
   `location` cites a `path:...` and the review has a diff, verify the
   path appears in the diff. WARNING-only. Skipped for arch/slice/tasks
   reviews (no diff).

4. **Path-existence check (all template types)**. When the finding's
   `location` cites a path and is not `unverified`, verify the path
   exists in the repo via `Path.exists()`. WARNING-only. This is the
   primary defense against hallucinated filenames in arch/slice/tasks
   reviews where there is no diff to check against. Cheap: one
   `Path.exists()` per finding.

## Hallucination defense

The risk: model interprets the new requirement and starts hallucinating
fake locations to satisfy it — worse than no location, because they look
authoritative.

Three layers of mitigation:

- **Prompt (`unverified` token)**: explicit "I don't know" escape hatch
  that's self-documenting in the rendered review. Humans see
  `location: unverified` and know the model couldn't pin it down.
- **Path-existence check (all templates)**: catches the most common
  hallucination — made-up filenames — across every template type.
- **Diff-membership check (code only)**: stricter check for code
  reviews, where we have an authoritative set of files under review.

All three are WARNING-only. Hard-rejection deferred until we have
real-world false-positive data.

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
| code     | `path:line` / `path:start-end` | `path#symbol`, `path` | `unverified` |
| slice    | `path:line` (slice doc)  | `path#section-heading`, `path` | `unverified` |
| arch     | `path` (whole-doc), `path#section-heading` | `path:line` | `unverified` (common for missing-coverage findings) |
| tasks    | code `path:line` (where the issue lives) | `path#symbol`, `path` | `unverified` |

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
   missing `location:`; assert `ReviewFinding.location == "unverified"`
   and a WARNING log message names the finding ID.
3. **Normalization.** Findings with `location: -`, `location: global`,
   or empty all normalize to `unverified` with WARNING.
4. **Diff-membership WARNING (code).** Feed a synthetic code review
   where one finding cites `src/nonexistent.py:42` and the diff covers
   only `src/squadron/foo.py`. Assert WARNING logged, finding parsed.
5. **Path-existence WARNING (arch).** Feed a synthetic arch review
   citing `project-documents/nonexistent.md`. Assert WARNING logged.
6. **`unverified` skips checks.** Findings with
   `location: unverified` produce no diff-membership or path-existence
   WARNING.
7. **End-to-end (code).** `uv run sq review code <slice>` produces a
   review where every finding has a `location:` field. Note the
   `unverified` count and any hallucinated paths flagged by T8/T9.
8. **End-to-end (arch).** `uv run sq review arch <slice>` produces a
   review where every finding has a `location:` field; cross-cutting
   findings use `unverified` with prose justification.
9. **Full gate.** `uv run pytest -q && uv run ruff check && uv run pyright`.
