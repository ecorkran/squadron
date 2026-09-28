---
docType: review
layer: project
reviewType: code
slice: serialize-concurrent-git-worktree-add-on-one-checkout
targetKind: slice
rulesSource: project
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
aiModel: claude-sonnet-5-5
status: complete
dateCreated: 20260928
dateUpdated: 20260928
reviewedSha: 95966c3cf1a76f0373cc7f712dad5be3144165b9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
diffTruncated: false
squadronVersion: 0.15.0
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Lock-failure fix_hint is wrong for most lock failures"
    location: "src/squadron/codehost/worktree.py:372-382"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Sweep can stall for minutes when the lock is held"
    location: "src/squadron/codehost/worktree.py:258-290"
  - id: F003
    severity: concern
    category: design
    summary: "Hand-called `__enter__`/`__exit__` is a known anti-pattern"
    location: "src/squadron/cli/commands/review_pr.py:426-438"
  - id: F004
    severity: concern
    category: testing
    summary: "Tests import `fcntl` at module level, contradicting the Windows design"
    location: "tests/codehost/test_worktree.py:9"
  - id: F005
    severity: note
    category: consistency
    summary: "Sweep and `_remove` handle a lock failure differently"
    location: "src/squadron/codehost/worktree.py:262-280"
  - id: F006
    severity: note
    category: design
    summary: "One lock per worktree root, not per repository"
    location: "src/squadron/codehost/metadata_lock.py:16-17"
  - id: F007
    severity: note
    category: testing
    summary: "Timing-sensitive test assertions"
    location: "tests/codehost/test_metadata_lock.py:52"
  - id: F008
    severity: note
    category: testing
    summary: "Load test catches the real race only some of the time"
    location: "tests/load/test_worktree_concurrency.py:85-104"
  - id: F009
    severity: pass
    category: correctness
    summary: "Lock implementation and exception handling"
    location: "src/squadron/codehost/metadata_lock.py"
  - id: F010
    severity: pass
    category: correctness
    summary: "Claim-first sweep ordering fixes the handoff race"
    location: "src/squadron/codehost/worktree.py:241-251"
---

# Review: code — slice 929

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Lock-failure fix_hint is wrong for most lock failures

`__enter__` converts every `MetadataLockError` into a `WorktreeCreationError` whose `fix_hint` always says "Another squadron process may be holding the worktree metadata lock… Wait for it to finish". `MetadataLockError` has three other causes: `fcntl` unavailable on Windows, an unwritable worktree root, and a persistent `flock` OSError such as `ENOLCK`. In those cases waiting never helps, and on Windows every `sq review pr` fails with this misleading advice. The hint should be chosen from the failure kind, or `MetadataLockError` could carry a timeout flag or subclass so only the timeout case gets the "wait" advice. The tests only cover the timeout case, so nothing catches this.

### [CONCERN] Sweep can stall for minutes when the lock is held

`sweep_orphans` takes the lock separately for each orphan and once more for the prune, each with a 60s timeout. If the lock is held by a hung or slow holder, N orphans plus the prune can block `__enter__` for up to (N+1)×60s before `__enter__` tries its own 60s wait. A timeout on one entry almost certainly means the next will time out too, and the log warning only appears after each wait. Consider abandoning the rest of the sweep after the first `MetadataLockError`, or acquiring the lock once for the whole sweep.

### [CONCERN] Hand-called `__enter__`/`__exit__` is a known anti-pattern

The project rules ban well-known anti-patterns. Calling `scratch.__enter__()` and `scratch.__exit__(None, None, None)` directly discards the real exception info and hand-rolls what `contextlib.ExitStack` does. Use `with ExitStack() as stack:` and wrap only `stack.enter_context(scratch)` in the `try/except WorktreeError`. That keeps setup failures separate from review failures and leaves the cleanup semantics to the standard library.

### [CONCERN] Tests import `fcntl` at module level, contradicting the Windows design

`metadata_lock.py` deliberately imports `fcntl` lazily so `worktree` still imports on Windows (D5). Both `tests/codehost/test_metadata_lock.py` and `tests/codehost/test_worktree.py` import `fcntl` at the top. On Windows, collection of the whole `test_worktree.py` file fails, including the many tests that never need the lock. Use `pytest.importorskip("fcntl")` or a skip marker for the lock-holding helpers, and keep the non-lock tests importable.

### [NOTE] Sweep and `_remove` handle a lock failure differently

When the lock can't be taken, the sweep skips the entry, claiming that deleting the directory would "corrupt" git metadata. `_remove` in the same file falls through to `_rmtree` in the same situation, as it does on a git timeout. `git worktree prune` normally cleans up a deleted worktree directory, so the "corrupt" claim looks overstated. Either way the two paths should follow one stated policy, and the comment should say why they differ.

### [NOTE] One lock per worktree root, not per repository

D2 uses one lock file per worktree root, so unrelated repositories serialize against each other. It is also ineffective for two processes that use different `root` values against the same checkout. This is acceptable for a scratch root that is constant in practice, but it is worth keeping documented.

### [NOTE] Timing-sensitive test assertions

`patched_timeout <= elapsed < patched_timeout + 1.0` and the `< 1.0` and `< 0.5` bounds in the other lock tests could flake on a loaded CI runner. The margins are reasonable, but they are wall-clock dependent.

### [NOTE] Load test catches the real race only some of the time

The docstring states the load test detects the measured sweep race only about 22% of the time per run. The deterministic tests, including the claim-then-lock handoff test, carry the actual proof. That is honest and adequate, but the load test is a weak backstop. It also still asserts correctness rather than latency or throughput bounds.

### [PASS] Lock implementation and exception handling

The lock is opened fresh per acquisition so `flock` serializes threads as well as processes. Only `BlockingIOError` is retried and other OSErrors fail immediately. Release and close never raise or mask a body exception, and the timeout is read at call time so tests can patch it. Each swallow has a justifying comment, and `MetadataLockError` is caught before `BaseException` in `__enter__`. Tests cover timeout, immediate failure, missing `fcntl`, release failure, and a killed holder.

### [PASS] Claim-first sweep ordering fixes the handoff race

Reading the claim before the lock matches the creator's write-lock-then-unlink-claim order, so a live worktree always shows at least one of the two. The new `test_sweep_spares_a_worktree_whose_claim_hands_off_to_its_lock_mid_sweep` injects the handoff between the two reads and would fail against the old ordering.

## Response (20260928)

All four concerns were checked against the code and are valid. All four are fixed.

- **F001: accepted.** `MetadataLockError` now carries `timed_out`, set only by the deadline path in `_acquire`. `__enter__` picks its hint through `_metadata_lock_fix_hint`. A timeout keeps the "another squadron process… wait" advice. Missing `fcntl`, an unwritable root, or a persistent flock error now say that waiting will not help, name the POSIX/writable requirement, and point to `--no-tools`. New test: `test_enter_gives_a_no_wait_fix_hint_when_the_lock_fails_without_timing_out`.
- **F002: accepted.** The first lock failure on an orphan's `remove` now abandons the rest of the sweep, prune included. Against a wedged holder, `__enter__` now waits about 120s at most, however many orphans there are. The test was replaced by `test_sweep_orphans_abandons_the_sweep_on_first_remove_lock_timeout`: two orphans, one wait, both left intact, one WARNING. The design's D4 was updated.
- **F003: accepted.** `review_pr.py` uses `ExitStack`, and only `stack.enter_context(scratch)` sits inside `except WorktreeError`. Cleanup now receives the real exception info. The existing CLI test still passes.
- **F004: accepted.** `test_worktree.py` imports `fcntl` inside `_metadata_lock_held_elsewhere` only. `test_metadata_lock.py` gates the file with `pytest.importorskip("fcntl")`.
- **F005: accepted in part.** The "corrupt" wording was overstated, since `prune` does clean up a deleted directory. The policies differ on purpose, and the comment now says why: an orphan has no deadline and is left whole for the next sweep, while `_remove` must clean up the worktree its own run created. Recorded in D4.
- **F006: no change.** It is already documented as D2's trade-off. Callers pass a custom `root` only in tests.
- **F007: no change.** The bounds are loose on purpose: a 1s margin on a 0.2s patched timeout, and an "immediate" limit of 0.5s against the real 60s. A failure would mean a real regression, not jitter.
- **F008: no change.** Recorded honestly in the test docstring and approved by the PM. The test does assert a per-round latency budget (`elapsed < GIT_QUERY_TIMEOUT_SECONDS * BUDGET_TOLERANCE`), not only correctness.

### Run Digest

- Response length: 5717 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- Reasoning characters: 0
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
