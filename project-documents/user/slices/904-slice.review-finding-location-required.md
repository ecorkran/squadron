---
docType: slice-design
slice: review-finding-location-required
project: squadron
parent: user/architecture/900-arch.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260427
dateUpdated: 20260427
status: complete
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

Reproduces the slice's behavior end-to-end. All steps verified on
20260427 against branch `904-review-finding-location-required`.

### Automated (steps 1–6)

Run with the full review test suite:

```bash
uv run pytest tests/review/ -q
```

Expected: `315 passed`. The new behavior is covered by:

- `tests/review/test_parsers.py::TestLocationSoftFail` — 11 tests:
  missing-location warning, no-warning regression on cited locations,
  non-code template safety (arch-style doc paths pass through
  unchanged), placeholder normalization (parametrized over
  `'-'`/`'global'`/`'GLOBAL'`/`' '`/`''`/`'n/a'`/`'None'`), and explicit
  `unverified` passthrough without warning.
- `tests/review/test_parsers.py::TestLocationDiffMembershipAndPathExistence` —
  6 tests: diff-member-and-existing passes silently, nonexistent path
  fires both WARNINGs, existing-but-not-in-diff fires diff-membership
  only, arch nonexistent fires path-existence, arch existing passes
  silently, `unverified` skips both checks.
- Template schema (step 1): `uv run pytest tests/review/test_templates.py -v`
  → `20 passed` (covers all four updated templates).

### Manual end-to-end (step 7 — code template)

Command (uses any reachable provider profile + a fast model; the
default `sdk` profile cannot run inside Claude Code, use `openrouter`):

```bash
uv run sq review code 902 --diff a4679b6^ \
  --model minimax/minimax-m2.7 --profile openrouter -v
```

Expected: review emits `## Summary` + per-finding `### [SEVERITY] Title`
blocks with a `location:` line on each finding (PASS included). The
saved file [project-documents/user/reviews/902-review.code.pipeline-verbosity-passthrough-v-vv.md](../reviews/902-review.code.pipeline-verbosity-passthrough-v-vv.md)
should have a `findings:` array in frontmatter where every entry has a
non-null `location` value.

Recorded outcome (20260427):

- 8 PASS findings, 8/8 with `location:` populated as real
  `path:start-end` values (e.g. `src/squadron/pipeline/steps/__init__.py:65-92`).
- 0 `unverified` (the model never reached for the escape token because
  every finding could be pinned).
- 0 parser WARNINGs (no soft-fail, no diff-miss, no path-miss).
- Note: `category:` is not requested by the code prompt, so all
  findings fall back to `category: uncategorized` in structured output.
  Pre-existing behavior, unchanged by slice 904.

### Manual end-to-end (step 8 — arch template)

Command:

```bash
uv run sq review arch \
  project-documents/user/architecture/900-arch.maintenance-and-refactoring.md \
  --model minimax/minimax-m2.7 --profile openrouter -v
```

Expected: review emits findings with `location:` populated; if the model
elides directory prefixes the path-existence check WARNs to stderr.

Recorded outcome (20260427):

- 5 findings (3 CONCERN, 2 NOTE), 5/5 with `location:` populated.
- Each WARNING line on stderr was of the form
  `Finding F### (...) in arch review cites '<path>' which does not
  exist on disk (relative to project-documents/user).` — the model
  emitted bare filenames (`900-arch.maintenance-and-refactoring.md`)
  without the `project-documents/user/architecture/` directory prefix.
  This is the slice's intended surfacing: the path-existence check
  does its job; tightening the arch prompt to require project-relative
  paths is a follow-up if the false-positive rate proves useful.

### Step 9 — full gate

```bash
uv run pytest -q && uv run ruff check && uv run ruff format --check && uv run pyright
```

Expected (verified 20260427): `1742 passed`, `All checks passed!` (ruff
check), `5 files would be left unchanged` (ruff format --check), and
`0 errors, 0 warnings, 0 informations` (pyright).
