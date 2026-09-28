---
docType: review
layer: project
reviewType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
verdict: CONCERNS
verdictSource: stated
recoveryTurn: true
sourceDocument: project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 04bc5ce5c841b1de8c0a0e6dde8a2dcd41119c64
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 81
runId: run-20260927-tasks-plan-1e76e648
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: test-coverage
    summary: "Every success criterion maps to at least one task"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:281-449"
  - id: F002
    severity: pass
    category: error-handling
    summary: "Sequencing respects dependencies; no circular dependencies"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:62-555"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Task granularity is appropriate — nothing too large or too granular"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:159-278"
  - id: F004
    severity: pass
    category: error-handling
    summary: "Commit checkpoints are distributed throughout, not batched at end"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:146-513"
  - id: F005
    severity: pass
    category: test-coverage
    summary: "Test tasks immediately follow their implementation tasks"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:346-437"
  - id: F006
    severity: pass
    category: test-coverage
    summary: "The parent slice's NFR has a load test task in tests/load/"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:450-491"
  - id: F007
    severity: concern
    category: error-handling
    summary: "CI gating of the load test is left implicit at the task level"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:516-524"
  - id: F008
    severity: concern
    category: error-handling
    summary: "Task D.7 omits the WorktreeCreationError import its own test body requires"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:425-437"
  - id: F009
    severity: note
    category: error-handling
    summary: "The _METADATA_LOCK_POLL_SECONDS disambiguation is a justified, explicitly-reasoned deviation from the design's own table"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:34-40"
  - id: F010
    severity: note
    category: test-coverage
    summary: "Part B's intentionally-red suite state is documented, not accidental"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md:146-157"
---

# Review: tasks — slice 929

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash
**Recovery turn:** used — the first reply ended without a review, and this review came from one follow-up prompt

## Findings

### [PASS] Every success criterion maps to at least one task

Cross-referencing each slice-design criterion against tasks: "no two … git worktree add|remove|prune calls … ever run at the same time" → B.1/B.2 (deterministic proof, fail-first) and D.1–D.3 (wiring); "reports a worktree setup failure as an error panel … exit code 1" → D.6/D.7; "submodule update runs outside the lock" → the design's Excluded section, and B.1 scripts `("git", "submodule")` as an unlocked no-op, consistent with that exclusion; the three per-call-site timeout behaviors → D.1–D.3 (implementation) and D.4 (one timeout test per call site — four tests for the four call sites at worktree.py:333, 253, 265, 400); holder-death release → C.4; read-only root fails immediately → C.3; lazy `fcntl` import → C.2 plus G.1's grep check; `MetadataLockError` for every helper failure → C.2 (D7's five-row table is reproduced step by step); ruff/pyright → G.1; existing `tests/codehost/test_worktree.py` passing unchanged → D.8. All five Verification Walkthrough steps are also covered: step 1 → A.1, step 2 → B.2 + D.5 (including the negative re-check with immediate revert), step 3 and step 5 → G.2, step 4 → E.2. No criterion is left without a task.

### [PASS] Sequencing respects dependencies; no circular dependencies

The ordering is strictly causal: A.1 measures the pre-fix rate before any fix exists (correct — the measurement is only meaningful against unwrapped code); B.1–B.2 add the failing proof before C creates the lock (so the red state genuinely demonstrates the bug); C.1–C.4 build `metadata_lock.py` before D wraps any call site (D.1 imports from a module that exists by then); D.4's timeout tests follow the D.1–D.3 wiring they exercise; D.5 confirms the B.2 test flips to green only after the wiring; E.1 derives `ROUNDS` from A.1's recorded baseline, which precedes it; G runs last against everything committed. No task depends on work that comes after it, and no cycle exists. The frontmatter's `dependencies: []` is consistent with the design's "Prerequisites: None."

### [PASS] Task granularity is appropriate — nothing too large or too granular

The largest tasks (B.2, C.2, C.3, D.1, D.2, D.4 at 3/5) each have exactly one deliverable: B.2 one test, C.2 one function, C.3 one test file with five named cases, D.1 one call site, D.2 one function's two calls, D.4 one test file addition. C.2's seven-step behavior specification is detailed but describes a single ~30-line function — splitting it would separate steps that must be written together to satisfy D7's error mapping. At the other end, the 1/5 tasks (A.1, B.3, C.5, E.2, E.3, F.1, F.2, G.1, G.3) are each a single command or single commit — small, but each is independently verifiable and several (the commit tasks) exist to enforce the per-part commit convention, so merging them would weaken that structure. Part F's split (F.1 docstring edit, F.2 commit) is at the granular end but acceptable, since it keeps the docs change reviewable separately from code.

### [PASS] Commit checkpoints are distributed throughout, not batched at end

Commit tasks exist at B.3 (:146), C.5 (:271), D.8 (:439), E.3 (:483), and F.2 (:505) — one per part — each with a semantic commit message matching the project's commit-type conventions (`test:`, `feat:`, `fix:`, `test:`, `docs:`). A.1 (:80) explicitly states "No commit for this task — nothing in the working tree changes," which correctly excludes a measurement-only task. G.3 (:544) verifies the accumulated history reads as one coherent story. This satisfies the CLAUDE.md rule "Git add and commit from project root at least once per task" at part granularity and leaves nothing batched to the end.

### [PASS] Test tasks immediately follow their implementation tasks

The test-with pattern holds everywhere: B.1 (fake runner) → B.2 (the test that uses it); C.1/C.2 (the lock module) → C.3 (its unit tests) → C.4 (the holder-death test, same file); D.1–D.3 (the three wirings) → D.4 (their timeout tests) → D.5 (the no-overlap test's confirmation); D.6 (the CLI restructure) → D.7 (its CLI test). Each test task names the file and the `-k` filter it runs under, and each asserts the specific behavior its implementation task just added — including D.5's negative check that re-breaking the `add` wiring makes the test fail again.

### [PASS] The parent slice's NFR has a load test task in tests/load/

The parent plan entry (900-slices.maintenance-and-refactoring.md:459) restates the NFR — concurrent `sq review pr` runs on one checkout must not hit the `commondir` race — and names `tests/load/test_worktree_concurrency.py` as the signal. The breakdown's Part E (E.1/E.2) works directly in that file, turning its single round into `ROUNDS` rounds sized from A.1's measured rate, and E.2 runs both the full file and the 50-iteration loop. The load test is not merely preserved; it is strengthened to the sensitivity the design's worked example requires, with the chosen numbers and reasoning recorded in the test's own docstring per the design's Development Approach step 5.

### [CONCERN] CI gating of the load test is left implicit at the task level

The CI gating itself already exists and is correct: `.github/workflows/ci.yml:38` runs plain `uv run pytest`, and `pyproject.toml:81-84` sets `testpaths = ["tests"]` with no marker exclusion, so `tests/load/` is collected on every CI run today. The gap is that no task in the breakdown verifies this holds for this slice's changes — Part G checks the suite locally (G.1), runs the manual walkthrough (G.2), and inspects git history (G.3), but never confirms the CI invocation picks up the new `tests/load/` code (the repeated-rounds test, the new `tests/codehost/` files). Because the collection rules that make this true live in `pyproject.toml` rather than in any task's success criteria, a future change to `testpaths` or marker filters would silently drop the load test from CI with nothing in this slice's checklist to catch it. Adding one bullet to G.1 (e.g., confirming the plain `pytest` invocation that CI runs collects the new tests, and that no marker excludes `tests/load/`) closes this without a new task.

### [CONCERN] Task D.7 omits the WorktreeCreationError import its own test body requires

D.7 instructs the implementer to monkeypatch `ScratchWorktree.__enter__` to raise `WorktreeCreationError(Path("/tmp/fake"), "boom")`, but no bullet adds `from squadron.codehost.worktree import WorktreeCreationError` to `tests/cli/test_review_pr.py`. The existing test the task names as the pattern (`test_discussion_fetch_failure_renders_as_an_adapter_error_not_a_traceback`, tests/cli/test_review_pr.py:176) raises an adapter error, not a worktree one, so its import line cannot be copied verbatim — the implementer must author a new import, and nothing in the task tells them to. D.1 imports the name into `worktree.py`, not into the CLI test file, so no earlier task covers it either. A literal-minded implementer hits a `NameError` at test-authoring time. The fix is one bullet: add the `WorktreeCreationError` import alongside the existing `ScratchWorktree` import D.6 already touches.

### [NOTE] The _METADATA_LOCK_POLL_SECONDS disambiguation is a justified, explicitly-reasoned deviation from the design's own table

The design is internally inconsistent on this constant's name: its component table (slice design line 72) says `_POLL_SECONDS` while its D3 prose (slice design line 111) says `_METADATA_LOCK_POLL_SECONDS`. The task file resolves this explicitly, states which source it treats as authoritative and why (the prose is the more specific source), and instructs the implementer to use that name — turning a latent ambiguity that would otherwise surface as a review comment into a documented decision. This is the breakdown working as intended, not a defect.

### [NOTE] Part B's intentionally-red suite state is documented, not accidental

B.3 commits Part B while the suite has one known-failing test, and instructs the implementer to note that in the commit body so it is not mistaken for an accident later. C.5 (:271) re-states that the test is still failing at that point and why (`metadata_lock.py` exists but nothing calls it yet). Committing a red state is normally a defect; here it is the design's D6 point — the test must fail on today's code to prove the race exists — and the breakdown documents the redness at both commit points, so the history stays interpretable.

### Run Digest

- Response length: 10541 chars
- Response is newline-free: no
- Tool calls made: 81
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 68841
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
- Recovery turn used: yes (the follow-up reply is included below)
