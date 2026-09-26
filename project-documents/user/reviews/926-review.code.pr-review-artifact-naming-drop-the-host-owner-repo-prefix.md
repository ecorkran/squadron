---
docType: review
layer: project
reviewType: code
slice: pr-review-artifact-naming-drop-the-host-owner-repo-prefix
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/926-slice.pr-review-artifact-naming-drop-the-host-owner-repo-prefix.md
aiModel: claude-sonnet-5
status: complete
dateCreated: 20260925
dateUpdated: 20260925
reviewedSha: 9f200487b11de999ad92be676b093402fdac1924
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 21
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Filename qualification correctly derived from a single source of truth"
    location: "src/squadron/review/reviews_dir.py:45-62"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "`path_key` divergence is documented and consumer set is now accurate"
    location: "src/squadron/codehost/models.py:56-69"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Test coverage matches the new branching (qualify=True/False) at every layer"
    location: "tests/cli/test_review_pr_persistence.py:43-121"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Discovery glob claim verified against actual code"
    location: "src/squadron/pr/inputs.py:147"
  - id: F005
    severity: note
    category: design
    summary: "`resolve_reviews_dir` now runs unconditionally, including `--no-save` runs"
    location: "src/squadron/cli/commands/review_pr.py:444-450"
---

# Review: code — slice 926

**Verdict:** PASS
**Model:** claude-sonnet-5

## Findings

### [PASS] Filename qualification correctly derived from a single source of truth

`ReviewsDirRule.repository_scoped` centralizes the scoping decision in one place, uses exhaustive `match`/`case` with `assert_never` as a guard against a future enum member being added without an explicit scoping decision, and is well justified against `select_remote`'s actual behavior (`src/squadron/codehost/remotes.py:141-173`, which does refuse any repository without a matching local remote for the `PROJECT` case).

### [PASS] `path_key` divergence is documented and consumer set is now accurate

The updated docstring claims `path_key` has exactly one consumer (`ScratchWorktree.__enter__`). Verified via grep: the only production use is `src/squadron/codehost/worktree.py:320`; the PR artifact path now goes through `PrTarget.filename_stem`, which no longer touches `path_key`. Docstring and code agree.

### [PASS] Test coverage matches the new branching (qualify=True/False) at every layer

Unit tests cover both `qualify` states plus the "never uses `path_key`" invariant and the numeric-prefix guarantee; `tests/cli/test_review_pr.py:363-420` drives the wiring end-to-end for all four `ReviewsDirRule` values (not just a couple), which would catch a bug that special-cased on `rule == FLAG` instead of using `repository_scoped`. This matches the "test-with, not test-after" and parametrization conventions.

### [PASS] Discovery glob claim verified against actual code

The new test (`tests/pr/test_inputs.py`) asserts the existing glob `*-review.*.md` already matches all three name forms (old `github.com-...`, new unqualified `pr-...`, new qualified `pr-....owner-repo`) without a source change. Confirmed by reading the glob directly — this is accurately documented rather than asserted on faith.

### [NOTE] `resolve_reviews_dir` now runs unconditionally, including `--no-save` runs

Moving the call out of `_save_pr` so `rule.repository_scoped` can feed `PrTarget(..., qualify=...)` means `resolve_reviews_dir` (a `get_config` read plus a `Path.is_dir()` stat) now executes even when `--no-save` is passed, since Python evaluates the `target=PrTarget(...)` argument before `_resolve_save_outcome` checks `no_save`. The accompanying comment correctly notes this is side-effect-free, and it's a reasonable tradeoff to get `qualify` right, so this isn't a defect — just worth knowing if `--no-save` performance/hermeticity for this path is ever revisited.

## Response (20260925)

- **F005: accepted, no change.** This is the ordering the design chose (Data Flow: "moved earlier, still side-effect free"). The resolver reads config and stats a path; it creates nothing (pinned by `test_the_resolver_creates_nothing`), so a `--no-save` run gains one cheap read and no writes.

### Run Digest

- Response length: 4383 chars
- Response is newline-free: no
- Tool calls made: 21
- Tool calls failed: 0
- Stop reason: end_turn
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
