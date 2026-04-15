---
docType: slice-design
slice: review-code-slice-impl
project: squadron
parent: 140-slices.pipeline-foundation.md
dependencies: [167-per-action-model-override-convention]
interfaces: []
dateCreated: 20260414
dateUpdated: 20260414
status: not_started
---

# Slice Design: `sq review code` — Slice Implementation Review

## Overview

`sq review code 181` should review the code that changed while
implementing slice 181. Today it resolves the slice number to a
`SliceInfo` (for context) and attempts to find a diff range, but the
diff resolution fails for any slice whose branch was not preserved
after merge: `resolve_slice_diff_range` tries branch lookup then merge
commit lookup, then falls back to `--diff main` — which diffs all of
main rather than the slice's commits.

The common case is direct commits to main with the slice number in the
message. That signal is reliable enough to resolve a useful diff range.
This slice adds commit-message-based diff resolution as the third path
in `resolve_slice_diff_range`, making `sq review code <N>` work for the
majority of slices whether or not a branch survived.

Bulk / sweep review (fan-out, aggregation, embedding-based finding
clustering) is explicitly out of scope — those depend on slice 182
(fan-out/fan-in) and slice 183 (findings ledger). This slice is the
common single-slice case.

## User-Provided Concept

The most frequent code review use case: "review the implementation for
slice 181" — whatever code changed to make that thing, review that.
Branches are not always preserved. Commit messages are consistent
enough to serve as the primary diff signal for merged slices.

Markdown and doc files should be excluded from the diff before it
reaches the reviewer, not by filtering which commits to find but by
stripping those paths from the diff. The review template's existing
`diff_exclude_patterns` already handles this.

## Diff Resolution

`resolve_slice_diff_range` in `src/squadron/review/git_utils.py`
gains a third resolution path between the existing merge-commit check
and the fallback:

**Resolution order:**

1. **Local branch** `{N}-slice.*` exists → `{merge_base}...{branch}`
   (existing behavior)
2. **Merge commit** grepping `{N}-slice` on main → `{sha}^1..{sha}^2`
   (existing behavior)
3. **Commit range from message grep** → scan `git log` for commits
   whose message matches `\b{N}\b`, take the oldest and newest,
   return `{oldest}^..{newest}` (new)
4. **Fallback** → `main` with warning (existing behavior, unchanged)

**Grep pattern for step 3:**

```
git log --oneline --all --grep="\b{N}\b"
```

No type filtering — include feat, fix, docs, chore, etc. The diff
exclude patterns on the review template strip `.md`, task files, and
other non-code paths before the diff reaches the reviewer. Broad
commit capture is correct; narrow diff is the filter layer.

**Edge case — false positives:** a commit mentioning "181" that is
unrelated to slice 181 (e.g., a port number, a line count). Accept
this in v1. The number namespace is small enough in practice, and the
diff exclude patterns limit blast radius. A future refinement could
weight messages that also contain "slice" or the slice name.

**What the diff covers:** `git diff {oldest}^..{newest}` includes all
changed files across all matched commits. The review template's
`diff_exclude_patterns` then strips non-code files (`.md`, task files,
architecture docs, etc.) before the diff is sent to the reviewer.

## Scope

### In Scope

- `resolve_slice_diff_range` step 3: commit-message grep resolution.
- Tests for the new resolution path: branch found, merge commit found,
  commit grep found, none found (fallback).
- `--fan N` flag on `sq review code` — accepted and stored but prints
  "fan-out not yet supported; ignored" and proceeds as single review.
  Placeholder for slice 182 integration. Easy to type, signals the
  future direction.
- Update `review_code` docstring to describe the slice-number behavior
  accurately.

### Out of Scope

- Fan-out execution (slice 182 dependency).
- Aggregated roll-up across multiple batches (slice 182/183).
- Embedding/clustering of findings (post 183).
- `sq review sweep` or any new subcommand — the single subcommand
  `sq review code <N>` covers the common case.
- Caching or incremental review.

## CLI Surface

No new subcommand. `sq review code` gains one new flag:

```
sq review code [SLICE_NUMBER]
  --fan N          # Fan-out width (not yet functional; reserved for slice 182)
  [all existing flags unchanged]
```

Usage:

```bash
sq review code 181                          # review slice 181's implementation
sq review code 181 --model opus             # with model override
sq review code 181 --param review_model=sonnet  # after slice 167
sq review code 181 --fan 3                  # accepted, warned, ignored for now
sq review code --files "src/squadron/review/**/*.py"  # existing, unchanged
sq review code --diff main~5                # existing, unchanged
```

## Dependencies

- **Slice 167** (per-action model override convention) — soft dependency.
  `sq review code 181` works without it; `--param review_model=X`
  becomes available after 167 ships.
- **Slice 182** (fan-out/fan-in) — `--fan` becomes functional after 182.

## Success Criteria

- `sq review code 181` resolves a non-empty diff via commit grep for a
  slice whose branch is gone and has no surviving merge commit.
- The diff excludes `.md` and other doc files via `diff_exclude_patterns`.
- `--fan N` is accepted without error; a warning is emitted and the
  review proceeds as a single-shot review.
- All existing `sq review code` behavior (files glob, explicit diff ref,
  no slice number) is unchanged.
- Resolution path tests cover all four cases (branch, merge commit,
  commit grep, fallback).
