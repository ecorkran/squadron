---
docType: review
layer: project
reviewType: slice
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 5d919bc3814fd02abda2942359908b7a7e0a3c0c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 19
runId: run-20260927-slices-plan-c4a4a608
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Filesystem failures inside the lock helper are unenumerated and collide with two call sites' never-raise contracts"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:95-97"
  - id: F002
    severity: note
    category: plan-alignment
    summary: "The plan's \"timeout must be observable as a WorktreeCreationError\" is deliberately refined, not violated — recorded for traceability"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:115-118"
  - id: F003
    severity: note
    category: design-clarity
    summary: "Technical requirement \"worktree.py stays within the file-size guideline\" starts from a premise that doesn't hold"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:154"
  - id: F004
    severity: pass
    category: scope-alignment
    summary: "Slice belongs in the 900 maintenance container and satisfies its guidelines"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:1-16"
  - id: F005
    severity: pass
    category: integration
    summary: "Integration-point claims verify against source"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:131-133"
  - id: F006
    severity: pass
    category: error-handling
    summary: "Failure-mode coverage for the new lock path is nearly complete and matches the project's exception policy"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:115-122"
---

# Review: slice — slice 929

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [CONCERN] Filesystem failures inside the lock helper are unenumerated and collide with two call sites' never-raise contracts

`WorktreeLockError` is defined to cover exactly two modes: "lock not acquired (deadline passed, or `fcntl` unavailable)" (line 73, D3 line 113, D5 line 122). But the I/O path the helper adds also includes creating the lock file ("created on first use," State Management, line 97) — an `open()` that can raise `OSError` (read-only config dir, EACCES, ENOSPC), plus `flock()` itself and the release path, none of which the design assigns handling to. Two of the four call sites have hard never-raise contracts: `sweep_orphans` is documented "Never raises" (`worktree.py:214`) and is called first in `__enter__` outside any try, and `_remove` runs from `__exit__` where the module's own comment says cleanup must not mask the already-propagating exception (`worktree.py:392-396`). An escaping `OSError` would (a) turn `sq review pr` startup into a raw traceback — the exact failure class this slice's own D4 fix removes for `WorktreeError` — and (b) in `_remove`, replace the original exception with the cleanup failure. A poll loop that catches all `OSError` as "retry" would also turn a persistent flock error into a misleading 60-second stall ending in a fake "timeout." D5 already demonstrates the right pattern for this shape (missing capability → `WorktreeLockError` → handled like a timeout at every site); the same treatment needs specifying for `OSError` from open/mkdir/flock/release — or an explicit statement that it propagates by design. As written, the spec is exhaustive over the two named modes and silent on the third.

### [NOTE] The plan's "timeout must be observable as a WorktreeCreationError" is deliberately refined, not violated — recorded for traceability

Parent plan entry 27 says the lock timeout "must be observable as a `WorktreeCreationError`, not a hang." The design raises `WorktreeCreationError` only in `__enter__` and downgrades the sweep/`_remove` timeouts to WARNING-and-skip / WARNING-and-rmtree-fallback. This is a justified refinement, not a drift: both sites are documented never-raise in the module contract, the plan delegates the design ("Design picks the lock … and its timeout"), the "not a hang" requirement is met everywhere (skip + retry next run; fall-through to the existing rmtree path), and the loud requirement is met on the user-facing startup path. No action needed; recorded so the literal divergence from the plan's wording reads as deliberate.

### [NOTE] Technical requirement "worktree.py stays within the file-size guideline" starts from a premise that doesn't hold

`worktree.py` is ~437 lines today, already past the ~300-line guideline (the sibling `review_pr.py` docstring openly acknowledges the same about `review.py`). The escape hatch ("or the lock helper moves to `codehost/metadata_lock.py` if it doesn't") resolves the practical question, but "stays within the file-size guideline" implies a starting state that is already false. Restate as: the helper moves to its own module if the addition pushes the module further past the guideline it already exceeds — or state plainly that the module is already over and the split is the plan.

### [PASS] Slice belongs in the 900 maintenance container and satisfies its guidelines

The parent architecture defines initiative 900 as the home for "Non-trivial bugs that don't belong to an active feature slice" and requires slices be "small and focused" and "independently deliverable." This is one root-caused race fix confined to one module plus one CLI error-rendering addition, with `dependencies: []` in frontmatter — accurate, since everything touched shipped with slice 382 (confirmed by `worktree.py`'s own module docstring). No new capability, no milestone targets, no scope creep beyond the parent plan's entry (the `review_pr` traceback fix it adds was ratified in plan entry 27's closing line).

### [PASS] Integration-point claims verify against source

Every cross-reference checked is true. `review_pr.py:426` is the `with ScratchWorktree(` statement and sits outside any `try`/`except`, so D4's "Found:" claim (every `WorktreeError` from `__enter__` — add failure, submodule failure, and the new lock timeout — escapes as a raw traceback) is accurate for today's code. The fetch-handler pattern cited at `review_pr.py:355` exists; `render_code_host_error` renders `fix_hint` (`pr.py:95-105`), so the fix-hint path the design relies on is real; `GIT_QUERY_TIMEOUT_SECONDS = 30` (`refs.py`) makes the derived 60 s deadline correct; the four cited git calls (add ~333, sweep remove ~253, prune ~266, `_remove` ~400) are at the cited lines; `sq review pr` is the only production caller of `ScratchWorktree`; and the load test exists under the referenced name, patches `worktree.GIT_FETCH_TIMEOUT_SECONDS` at module level exactly as the design's test plan assumes, and joins threads against the `GIT_QUERY_TIMEOUT_SECONDS * BUDGET_TOLERANCE` budget the design's Special Considerations restates.

### [PASS] Failure-mode coverage for the new lock path is nearly complete and matches the project's exception policy

D4 enumerates a differentiated, explicit strategy per call site: raise chained `WorktreeCreationError` in `__enter__` with the claim dropped by the existing handler; WARNING-and-skip in the sweep with an explicit prohibition on falling through to `rmtree` (which would delete a directory git still registers); WARNING-and-rmtree-fallback in `_remove` matching how it handles a git remove timeout today. Holder death is covered by kernel-owned flock semantics plus a dedicated test; the deadline is bounded by `time.monotonic()` so there is no hang path; the missing-`fcntl` platform case maps to the same handling at every site rather than failing silently unlocked. Every planned `except WorktreeLockError` carries the justifying comment CLAUDE.md's exception-handling rule requires. The D3 queue analysis (2× holder budget, stopped-holder and hung-holder-queue cases) is sound, and D6's rounds math (1-in-20 per round × 60 rounds ≈ 95% pre-fix failure) is correct. The one remaining mode is the CONCERN above.

### Run Digest

- Response length: 8120 chars
- Response is newline-free: no
- Tool calls made: 19
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 55396
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
