---
docType: review
layer: project
reviewType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 88195ab9a7f994e6c32381cbcef4265ba09e3bf2
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 31
runId: run-20260927-tasks-plan-1e76e648
squadronVersion: 0.14.0
findings:
  - id: F001
    severity: pass
    category: coverage
    summary: "All success criteria trace to tasks, and sequencing/dependencies are correct"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md"
  - id: F002
    severity: pass
    category: coverage
    summary: "Load-test NFR is covered by a `tests/load/` task and explicit CI gating, with a verified premise"
    location: ".github/workflows/ci.yml:38"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Task B.1's fake runner spec omits the directory-creation side effect, so B.2 fails for the wrong reason and D.5 cannot pass"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md#Task-B.1"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "The \"submodule update runs outside the lock / still overlaps\" success criterion has no verifying task"
    location: "project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md:159"
  - id: F005
    severity: concern
    category: test-coverage
    summary: "The D7 release-path outcome (LOCK_UN/close `OSError` → WARNING, never raised) is untested"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md#Task-C.3"
  - id: F006
    severity: note
    category: test-coverage
    summary: "Several `-k` filter commands depend on test names that the tasks never pin"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md"
  - id: F007
    severity: note
    category: documentation
    summary: "Minor line-number drift in Task D.6's anchors (all `worktree.py` citations are accurate)"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md#Task-D.6"
  - id: F008
    severity: note
    category: process
    summary: "Commits B.3 and C.5 land a known-failing test; branch CI will be red until D.8"
    location: "project-documents/user/tasks/929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout.md#Task-B.3"
---

# Review: tasks — slice 929

**Verdict:** CONCERNS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] All success criteria trace to tasks, and sequencing/dependencies are correct

Cross-reference result: no-overlap (SC 1) → B.1/B.2 + D.1–D.3 + D.5; error panel with fix hint and exit 1 (SC 2, integration) → D.6/D.7; per-site timeout behavior (SC 4's three sub-cases, plus prune) → D.1–D.3 wiring + D.4's four tests; holder death → C.4; read-only root fails fast → C.3; lazy `fcntl` import → C.2 + G.2's grep check; lint/typecheck → G.2; repeated-rounds load test → E.1/E.2; existing suite unchanged → D.8. Walkthrough steps 1–5 map to A.1, D.5, G.3, E.2, G.3 respectively, and E.1 explicitly depends on A.1's recorded measurement. The B.2 red step is correctly sequenced before C, with D.5 confirming the green step and a re-break check. Commit checkpoints exist per part (B.3, C.5, D.8, E.3, F.2) with G.4 as final sweep. No scope creep found: A.1 (measurement-only), G.1 (CI confirmation), G.3 (manual walkthrough), and F.1 (docstring) all trace to the design's walkthrough/Development Approach; excluded items (claim/lock.json folding, Windows locking, #88) are not tasked. Task sizes are reasonable — D.4's four tests share one helper and one file, C.2 is one ~50-line function.

### [PASS] Load-test NFR is covered by a `tests/load/` task and explicit CI gating, with a verified premise

Task E.1 keeps the acceptance test in `tests/load/test_worktree_concurrency.py` per `.claude/rules/python.md:64` ("CI must gate load tests for slices touching these paths"), and Task G.1 makes the gating explicit instead of implicit. G.1's factual premise checks out: `ci.yml:38` is a bare `run: uv run pytest` (no `-m` deselect, no path argument), `pyproject.toml:83` sets `testpaths = ["tests"]`, and the only markers defined (`network`, `host_cf`, at `pyproject.toml:84-87`) are opt-out markers not applied by default — so `tests/load/` is collected and run. G.1 also correctly requires the outcome to be stated rather than silently checked.

### [CONCERN] Task B.1's fake runner spec omits the directory-creation side effect, so B.2 fails for the wrong reason and D.5 cannot pass

`ScratchWorktree.__enter__` writes the lock file into the just-"created" worktree directory after a successful `add` (`src/squadron/codehost/worktree.py:343`). Real `git worktree add` creates that directory; a canned `ProcessResult` does not. The existing suite hit exactly this and solved it with `_FakeRunnerCreatingWorktreeDir` (`tests/codehost/test_worktree.py:309-323`), whose docstring says the fake "must make that side effect real" — but Task B.1's `_OverlapTrackingRunner` spec returns `_worktree_add_ok()`'s shape with no such side effect, and B.2 never pre-creates the per-thread target paths. As specified, every thread's `__enter__` raises `FileNotFoundError` from the `lock.json` write inside `__enter__`'s try block, which is re-raised and swallowed by the thread. Consequences: B.2's mandatory "confirm it fails" step fails for the wrong reason (proving nothing about the race), and even after wiring D.1–D.3, `__enter__` never completes so `__exit__`/`_remove` never run in the overlap test — D.5's "it must now pass" only passes vacuously while the remove path goes unexercised. Fix: amend B.1 to have the fake create the target directory on an `add` call (mirroring `_FakeRunnerCreatingWorktreeDir`), or amend B.2 to pre-create each thread's distinct target directory before starting threads.

### [CONCERN] The "submodule update runs outside the lock / still overlaps" success criterion has no verifying task

No task verifies this functional requirement, and the planned tests cannot catch a violation. B.1 explicitly makes `git submodule` calls in the fake "no counting, no sleep" — so if an implementer wrongly wraps the submodule call in `git_metadata_lock` (the design's Excluded list and the Data Flow diagram both forbid it), the no-overlap test still passes (max in-flight `git worktree` stays 1), and D.4's enter-timeout test also passes (the held lock makes a wrapped submodule call time out into the same `WorktreeCreationError` at the same assertion). A cheap pin exists: have the fake's submodule handler attempt a non-blocking `flock` of the same lock file and record whether it succeeded, then assert in B.2 that it was free during at least one in-flight submodule call — or simply assert the fake observed two submodule calls while no lock was held. Add this as an item to B.1/B.2 or D.4.

### [CONCERN] The D7 release-path outcome (LOCK_UN/close `OSError` → WARNING, never raised) is untested

The technical requirement "Every `OSError` from the helper's mkdir, open, flock, or close is either converted to `MetadataLockError` or logged (D7). None escapes the helper" includes the release path, and D7 row 5 assigns it a specific outcome chosen precisely so a raise there cannot mask the `with` body's exception — exactly the failure mode the project's exception-handling rule warns about. C.3's five tests cover mkdir/open (read-only root), flock (non-`BlockingIOError`), the deadline, and `fcntl` unavailability, but nothing exercises the `finally` release path failing. One additional test (patched `fcntl.flock` raising `OSError` on `LOCK_UN` only, plus a sentinel exception through the `with` body to assert it isn't masked) would pin it; add it to C.3's list.

### [NOTE] Several `-k` filter commands depend on test names that the tasks never pin

B.2 does this correctly ("name must contain 'overlap'"), but C.4's `-k holder` and D.7's `-k worktree` filters require the new tests' names to contain those substrings, and neither task specifies a name or the constraint. If the junior names them otherwise, `-k` selects nothing and the run exits vacuously. One sentence each ("name must contain 'holder'"/"'worktree'") closes it. Relatedly, D.4's sweep-remove timeout test will see two WARNINGs (the lock is held for the whole call, so both the per-entry `remove` and the final `prune` time out), while the design says "logs one WARNING" — the task should say to assert on the message naming the orphan entry (as the existing `test_sweep_orphans_removes_dead_owner_with_one_warning` does via `str(entry) in ...`) rather than on the count, or a junior mirroring that count assertion will chase a phantom failure against correct code.

### [NOTE] Minor line-number drift in Task D.6's anchors (all `worktree.py` citations are accurate)

D.6 cites the `with ScratchWorktree(...)` block as "currently lines 425–429" and `_run(...)` as "line 429", and the `no_tools` branch as "line 419"; the verified positions are 426–430, `_run` at 430, and `if no_tools:` at 418. Every citation into `worktree.py` (add at 333, `except BaseException` at 346, sweep remove at 251–256, prune at 264–267, `_remove` at 398–403, docstring 1–11) and into `test_review_pr.py` (Path at line 12, `patched_host` at 77, `_arm` at 232) verified accurate, so this is drift only on one file; the code quotes are unambiguous. Worth correcting so a junior following line numbers literally doesn't hesitate at the boundary.

### [NOTE] Commits B.3 and C.5 land a known-failing test; branch CI will be red until D.8

This is deliberate TDD sequencing and the task file already requires the failure to be noted in the commit body, so it is not a defect — but note that CI runs on every push (`on: pull_request` / `push: [main]`, `.github/workflows/ci.yml:3-7`), so the Part B and Part C commits will show red runs on the slice branch. If branch CI is watched by anything automated, consider an explicit note in the task that this is expected until D.8.

### Run Digest

- Response length: 9679 chars
- Response is newline-free: no
- Tool calls made: 31
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 128000 tokens
- Reasoning characters: 72942
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
