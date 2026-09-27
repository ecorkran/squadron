---
docType: review
layer: project
reviewType: slice
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 9fc074eb9dad2cfde1b8ac8f0e8d3c5372f86ee7
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 11
runId: run-20260927-slices-plan-c4a4a608
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Slice fits the maintenance initiative's stated scope exactly"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#Overview"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "All verified code claims in the design are accurate"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#Technical-Scope"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Failure modes for the new I/O path are fully enumerated, not TBD"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#Technical-Decisions"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Dependency direction and layering are correct"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#Patterns-and-Conventions"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "The plan's \"observable timeout\" requirement is honored with a documented refinement"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#D4"
  - id: F006
    severity: note
    category: uncategorized
    summary: "`_remove`'s rmtree fallback after a lock timeout partially defeats serialization, but is deliberately inherited"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#D4"
  - id: F007
    severity: note
    category: uncategorized
    summary: "Locking is per worktree root and therefore serializes unrelated repositories"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md#D2"
---

# Review: slice — slice 929

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Slice fits the maintenance initiative's stated scope exactly

The parent architecture defines this initiative as a container for "non-trivial bugs that don't belong to an active feature slice" and asks for "small and focused" slices. This slice fixes issue #133 (a real race on the PR-review startup path), touches one module boundary (`worktree.py` call sites plus a new helper), and is independently deliverable. The `review_pr.py` error-panel fix (D4) is a narrow, justified rider on the same code path, not scope creep — it is explicitly scoped to wrapping entry only. The `parent:` frontmatter correctly points at the slice plan, not the architecture document.

### [PASS] All verified code claims in the design are accurate

Every load-bearing premise checked out against source: `ScratchWorktree.__enter__` runs `git worktree add` unserialized (worktree.py:333); `sweep_orphans` runs `worktree remove --force` per entry and `worktree prune` (:253, :265); `_remove` runs `worktree remove --force` (:400); `review_pr.py:426` indeed wraps `ScratchWorktree` in a `with` block with no surrounding `except` for `WorktreeError`, while the fetch handler at :355 uses the exact `render_code_host_error` + `typer.Exit(1)` pattern the design says it will mirror; `GIT_QUERY_TIMEOUT_SECONDS = 30` (refs.py:28) makes the `2 × GIT_QUERY_TIMEOUT_SECONDS` = 60s derivation correct; `CodeHostError`/`WorktreeError`/`WorktreeCreationError` hierarchy matches the design's subclassing decision; `sweep_orphans` skips non-directories (worktree.py `entry.is_dir()` check), so the never-deleted lock file is genuinely never swept.

### [PASS] Failure modes for the new I/O path are fully enumerated, not TBD

D3 and D7 give an explicit outcome table for every failure the helper can hit: mkdir/open `OSError` → immediate `MetadataLockError`; `BlockingIOError` → poll until deadline; non-`BlockingIOError` flock error → immediate failure (correctly kept out of the retry loop so it can't masquerade as a timeout); release errors → WARNING with justification. Each of the three call sites has an assigned timeout behavior (raise-as-`WorktreeCreationError`, WARNING-and-skip, WARNING-and-fall-through) consistent with each path's existing never-raise contract, and each `except MetadataLockError` gets the justifying comment the exception-handling rule requires. Hang, timeout, and holder-death are each covered by a named test. No path hangs.

### [PASS] Dependency direction and layering are correct

`MetadataLockError` subclasses `CodeHostError` rather than `WorktreeError` specifically to avoid `metadata_lock.py` importing `worktree.py` — the right direction (the lock is the lower-level component, worktree is the consumer), and it prevents a circular import. The new module depends only on stdlib and the existing `refs` constant; nothing outside `codehost` consumes it. No new dependency is introduced (the `filelock` package was considered and rejected).

### [PASS] The plan's "observable timeout" requirement is honored with a documented refinement

The parent plan entry says the timeout "must be observable as a `WorktreeCreationError`, not a hang." The design deliberately refines this for the two never-raise paths (`sweep_orphans`, `_remove`), and the refinement is argued from each path's existing documented contract rather than from convenience — the correct precedence, since silently breaking a never-raise contract to satisfy a plan sentence would be worse.

### [NOTE] `_remove`'s rmtree fallback after a lock timeout partially defeats serialization, but is deliberately inherited

The design is internally stricter for `sweep_orphans` (lock timeout → WARNING, skip, explicitly must *not* fall through to `rmtree` because that "would delete a directory git still registers") than for `_remove` (lock timeout → WARNING, fall through to the existing `rmtree` fallback). The two situations differ — `_remove` removes its own worktree, while a competing holder of the same path lock is realistically only a sweep that fires on pid recycling — and the design records that it "matches how it handles a git remove timeout today." This is an accepted, pre-existing residual race, not a new one, but the asymmetry in reasoning between the two sites is worth an implementer's attention so the `except MetadataLockError` comments explain the difference rather than reading as accidental.

### [NOTE] Locking is per worktree root and therefore serializes unrelated repositories

D2 consciously chooses a coarse lock (one file under `~/.config/squadron/worktrees/`) over the exact per-common-dir key, trading an extra git subprocess for millisecond holds. The cost is acknowledged in the design and is negligible for real workloads, but it means two `sq review pr` runs against *different* repositories also contend. Acceptable; noted so a future change to the root layout doesn't silently break the lock's coverage assumption (the lock file location and the worktree root are coupled by convention, not derived).

### Run Digest

- Response length: 5867 chars
- Response is newline-free: no
- Tool calls made: 11
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 4638
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
