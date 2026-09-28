---
docType: slice-design
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: []
dateCreated: 20260927
dateUpdated: 20260928
status: complete
---

# Slice Design: Serialize Concurrent `git worktree add` on One Checkout

## Overview

Fixes [issue #133](https://github.com/ecorkran/squadron/issues/133). The v0.13.3 tag run failed `tests/load/test_worktree_concurrency.py::test_concurrent_worktree_creation_succeeds_with_non_colliding_paths` with:

```
fatal: failed to read .git/worktrees/github.com-acme-widgets-2-run2/commondir: Success
```

That is git reading a sibling worktree's admin directory (`.git/worktrees/<name>/`) while another git process is halfway through writing or deleting it. Git does not serialize its own worktree metadata across processes. The test is right. `ScratchWorktree` runs three kinds of git metadata mutation against a shared checkout with nothing around them, and two concurrent `sq review pr` runs can hit the same race in real use:

- `git worktree add` in `__enter__` ([worktree.py:333](../../../src/squadron/codehost/worktree.py#L333))
- `git worktree remove --force` and `git worktree prune` in `sweep_orphans` ([:253](../../../src/squadron/codehost/worktree.py#L253), [:266](../../../src/squadron/codehost/worktree.py#L266))
- `git worktree remove --force` in `_remove`, run from `__exit__` ([:400](../../../src/squadron/codehost/worktree.py#L400))

This slice puts an exclusive cross-process lock around each of those calls, and only those calls. The lock waits with a deadline, and a missed deadline is a loud, typed failure.

## Value

- `sq review pr` runs started in parallel against one repository (a batch, two terminals, a CI matrix) stop failing at random during worktree setup.
- The load test goes back to being a real signal. Nobody learns to ignore it, and nobody hides it behind a retry that would also hide the production bug.
- The race is shown to be gone, not just rarer. A deterministic test proves the calls never overlap, and the real-git load test runs enough rounds that the old failure rate would reliably trip it.

## Technical Scope

**Included**
- A new module, `src/squadron/codehost/metadata_lock.py`: an exclusive `fcntl.flock` on a lock file under the worktree root, polled against a deadline.
- The lock wraps exactly four git calls: `worktree add`, the sweep's `worktree remove`, the sweep's `worktree prune`, and `_remove`'s `worktree remove`.
- The lock timeout is observable. In `__enter__` it raises `WorktreeCreationError`. In the never-raise paths (sweep, exit removal) it logs a WARNING and skips that git call.
- `review_pr.py`: render a `WorktreeError` from worktree setup as an error panel, not a traceback (D4).
- `sweep_orphans` reads the claim before the lock, which closes a sweep-deletes-live-worktree race found during the baseline (D8).
- Tests: deterministic no-overlap test, timeout tests for all three call sites, holder-death release test, and the load test repeated in one run.

**Excluded**
- The submodule fetch (`git submodule update --init --recursive`). It is the slow step, it works inside the new worktree's own directory, and it must stay concurrent. It runs outside the lock.
- Non-squadron git processes. An operator's own `git worktree add` on the same repo is not serialized. The lock coordinates squadron with squadron, which is where the concurrency comes from.
- Folding the claim/lock.json liveness scheme into the flock. Claims still cover the window between `add` and the `lock.json` write, which the per-call lock does not span. Merging the two is a separate refactor with no bug behind it.
- Native Windows locking (see D5).
- #88 (metrology suite runtime).

## Dependencies

### Prerequisites
None. Everything this slice touches shipped with slice 382.

### Interfaces Required
- `ProcessRunner.run(argv, cwd=, timeout=)` and `ProcessTimedOutError`: unchanged.
- `GIT_QUERY_TIMEOUT_SECONDS` from `squadron.codehost.refs`: bounds every git call the lock wraps, so it also bounds how long any one holder can keep the lock.

## Architecture

### Component Structure

The lock goes in a new module, `src/squadron/codehost/metadata_lock.py`. `worktree.py` is already 425 lines, past the ~300-line guideline, so adding the helper there would push it further over. The new module holds the lock mechanism only. `worktree.py` changes only at its four call sites.

| Element | Kind | Change |
|---|---|---|
| `metadata_lock._LOCK_FILENAME` | constant | new: name of the lock file under the worktree root |
| `metadata_lock.METADATA_LOCK_TIMEOUT_SECONDS` | constant | new: how long a caller waits for the lock |
| `metadata_lock._POLL_SECONDS` | constant | new: poll interval between non-blocking attempts |
| `metadata_lock.MetadataLockError(CodeHostError)` | exception | new: lock not acquired (deadline passed, `fcntl` unavailable, or a filesystem error; see D7); carries `lock_path` and `detail` |
| `metadata_lock.git_metadata_lock(root)` | context manager | new: acquire, yield, release |
| `sweep_orphans` | function | wraps each `remove` and the `prune` in the lock; catches `MetadataLockError` |
| `ScratchWorktree.__enter__` | method | wraps `add` in the lock; converts a timeout to `WorktreeCreationError` |
| `ScratchWorktree._remove` | method | wraps `remove` in the lock; catches `MetadataLockError` |

### Data Flow

```
__enter__
  sweep_orphans(...)                 per orphan: [lock] git worktree remove [unlock], rmtree
                                     then:       [lock] git worktree prune [unlock]
  write claim
  [lock] git worktree add [unlock]   timeout -> WorktreeCreationError (claim dropped by existing handler)
  write lock.json, drop claim
  git submodule update ...           NOT locked: stays concurrent
__exit__ -> _remove
  [lock] git worktree remove [unlock], then rmtree fallback
```

Each hold covers one git subprocess, so one holder keeps the lock for at most `GIT_QUERY_TIMEOUT_SECONDS`. A normal hold takes milliseconds. The sweep takes and releases the lock once per git call and never holds it across the whole loop, so a backlog of orphans can't starve other runs.

### State Management

The only new state is one empty lock file, `<worktree root>/.git-metadata.flock`. It is created on first use and never deleted. Deleting a lock file that other processes may have open would let two holders lock two different inodes. The kernel owns the lock itself, so a holder that crashes or is killed releases it automatically. Unlike the claim and `lock.json` scheme, there is no stale-lock state to detect or sweep. `sweep_orphans` already skips non-directories, so it never touches the lock file.

## Technical Decisions

**D1: `fcntl.flock`, with a fresh open file per acquisition.** `flock` locks are owned by the open file description, not by the process. So two threads in one process that each `open()` the file conflict just like two processes do. That matters twice: the load test's contenders are threads in one process, and a future in-process batch would be too. Rejected alternatives:
- `fcntl.lockf` / `fcntl.fcntl(F_SETLK)`: POSIX record locks are per process. Threads would never block each other, and the load test would keep failing.
- A `threading.Lock`: covers threads only, not two `sq` processes.
- The `filelock` package: a new dependency for roughly 15 lines of stdlib code.
- `O_CREAT|O_EXCL` lock files: a crashed holder leaves the file behind, which brings back the stale-lock detection problem `flock` avoids.

Because of the per-open-file rule, the helper must never cache or share its file descriptor. Each `with git_metadata_lock(root):` opens the file, locks it, and closes it.

**D2: One lock per worktree root, not per repository.** The race is on a repository's shared git directory (`git rev-parse --git-common-dir`). Linked worktrees of one repo share it: the main checkout and a `cf` worktree running `sq review pr` at the same time would both write the same `.git/worktrees/`. So a lock keyed on the checkout path would be wrong. A lock keyed on the common dir would be exact, but it costs a git subprocess per run plus path resolution. One lock file under the worktree root (`~/.config/squadron/worktrees/`) covers every repo, which serializes unrelated repos too. With holds in the milliseconds, that costs nothing measurable. It needs no git call and nothing to resolve, and it matches where the scratch worktrees already live. Tests that pass `root=` get their own lock under their own root, which is the isolation they need.

**D3: Wait with a deadline, by polling.** `flock` has no timeout, so the helper retries `LOCK_EX | LOCK_NB` every `_METADATA_LOCK_POLL_SECONDS` (0.05) until `METADATA_LOCK_TIMEOUT_SECONDS` runs out, then raises `MetadataLockError`. Only `BlockingIOError` (the lock is held elsewhere) is retried. Any other error fails at once (D7). The poll loop reads `time.monotonic()`.

`METADATA_LOCK_TIMEOUT_SECONDS = 2 * GIT_QUERY_TIMEOUT_SECONDS` (60s). That is a derived constant, defined once. One holder can keep the lock for at most one `GIT_QUERY_TIMEOUT_SECONDS`, and killed holders release instantly. So a waiter only runs out of time behind a live holder that is stopped (`SIGSTOP`, a suspended laptop), or behind a queue of holders each hitting their own git timeout. Both are real faults, and a loud failure is the right result for either. Normal queues of milliseconds per holder never come close.

**D4: How each call site reports a timeout.**
- `__enter__`: the `add` is inside the existing `try` whose `except BaseException` drops the claim. A `MetadataLockError` is logged at ERROR and re-raised as `WorktreeCreationError(path, detail, fix_hint=...)` chained `from` it. The detail carries the lock error's own detail (the seconds waited, the missing platform support, or the OS error). For a timeout, the fix hint says another squadron process is holding the worktree lock and gives the path. For a filesystem error, it names the lock file and the OS error. **Found:** `review_pr.py` does not catch anything from the `with ScratchWorktree(...)` block ([review_pr.py:426](../../../src/squadron/cli/commands/review_pr.py#L426)). Every `WorktreeError` from `__enter__` (an `add` failure, a submodule failure, and now a lock timeout) escapes as a raw traceback. This slice wraps that block's entry in `except WorktreeError` → `render_code_host_error(exc)` → `typer.Exit(1)`, the same pattern as the fetch handler at [:355](../../../src/squadron/cli/commands/review_pr.py#L355). Only entry is wrapped, not the review run inside the block.
- `sweep_orphans`: already documented as never raising. On a timeout it logs a WARNING and skips the entry. It must not fall through to `rmtree`, which would delete a directory git still registers. The next run retries. A timeout on the final `prune` is logged at WARNING, the same as the existing prune `ProcessTimedOutError` branch.
- `_remove`: already never raises (the documented `__exit__` exception). On a timeout it logs a WARNING and falls through to the existing `rmtree` fallback. That matches how it handles a git remove timeout today: the admin directory is left for a later `prune`.

This refines parent plan entry 27's "observable as a `WorktreeCreationError`" on purpose. The sweep and exit paths have documented never-raise contracts, so there the failure is a WARNING, not an exception. Every path still ends without hanging.

Each `except MetadataLockError` gets a comment naming the never-raise contract it serves, per the exception-handling rule.

**Worst-case wait (found in verification, accepted).** The timeout applies per acquisition, not per `__enter__`. Against a wedged holder, `__enter__` waits 60s for each orphan the internal sweep removes, 60s for the sweep's `prune`, and then 60s for `add`. With no orphans, that is about 120s before the error panel. A live holder can't cause this, because each wrapped git call is capped at `GIT_QUERY_TIMEOUT_SECONDS` (30s). Sharing one deadline across the sweep and `add` would restore ~60s at the cost of threading a deadline through `sweep_orphans`. That was not done.

**D5: POSIX only, imported lazily.** `docs/QUICKSTART.md` supports installing `sq` on Windows, and `review_pr.py` imports `worktree` at module level. A top-level `import fcntl` would therefore break the whole CLI on Windows. `fcntl` is imported inside `git_metadata_lock`. The limit adds nothing new: `ScratchWorktree.__enter__` already shells out to `ps -o lstart=` before any git call (`_current_process_start_time`), so the tools path of `sq review pr` already fails on Windows. The limit is documented in the module docstring. If `fcntl` is missing, the helper raises `MetadataLockError` with a detail naming the platform, and every call site handles it exactly like a timeout (D4). Anything that reaches it on Windows fails loudly, not silently unlocked.

**D6: The test proves "gone", not "rare".** A deterministic test proves the property the fix provides: no two wrapped git calls ever overlap. It uses real threads and a `FakeProcessRunner`-style runner that records how many `git worktree` calls are in flight and sleeps briefly inside each one. It asserts the maximum is 1. This fails on the current code every time, independent of git's timing.

The real-git load test stays as the acceptance test. It runs repeated rounds of 8 concurrent creations in one test invocation. The round count comes from a measured pre-fix failure rate (see Implementation Notes), not a guess.

**D7: Filesystem errors in the helper.** The helper does I/O beyond the lock call, and two of its callers must never raise. Each OS-level failure has one assigned outcome:

| Step | Failure | Outcome |
|---|---|---|
| `root.mkdir(parents=True, exist_ok=True)` | `OSError` (read-only config dir, EACCES, ENOSPC) | `MetadataLockError`, detail names the path and `strerror`. No retry. |
| `open(lock_path, "a")` | `OSError` | same as mkdir |
| `flock(LOCK_EX \| LOCK_NB)` | `BlockingIOError` | held elsewhere: sleep, retry until the deadline (D3) |
| `flock(LOCK_EX \| LOCK_NB)` | any other `OSError` (ENOLCK, EBADF; Python already retries EINTR itself) | `MetadataLockError` at once. It never enters the retry loop, so a persistent error can't pass itself off as a 60-second "timeout." |
| release: `flock(LOCK_UN)` then `close()` | `OSError` | WARNING, not raised. Closing the descriptor releases the lock anyway, and a raise here would mask the exception already propagating out of the `with` body. |

Every error the helper can raise is a `MetadataLockError`, so each call site's single `except MetadataLockError` (D4) covers all of them. `sweep_orphans` and `_remove` keep their never-raise contracts without a broad `except OSError`. A failure to acquire is always logged by the call site, at ERROR in `__enter__` and at WARNING in the sweep and exit paths, so none is silent.

**D8: The sweep reads the claim before the lock (found in Task A.1).** The baseline showed a second race, separate from #133. `sweep_orphans` read `lock.json` first and the `.claim` file second, while `__enter__` writes `lock.json` and then unlinks the claim. When that handoff fell between the sweep's two reads, the sweep saw neither file and removed a live worktree. At concurrency 32 this caused 3 of 50 runs to fail (`ProcessCwdNotFoundError`, `Invalid path .git/worktrees/...`, submodule `Unable to read current working directory`). Every failing run logged "Sweeping orphaned worktree ... (no readable/parseable lock)" against a live, same-process worktree, and no passing run swept anything. The metadata lock does not cover this: the sweep decides before any git call, and the handoff happens after `add` returns. The fix reverses the reads to claim first, then lock. The claim exists before the directory does, and `lock.json` exists before the claim is unlinked, so a live worktree always shows at least one of the two. No new locking is needed. A deterministic test injects the handoff between the two reads.

### Patterns and Conventions
- Named constants for the lock filename, timeout, and poll interval, each defined once in `metadata_lock.py`. Tests patch `metadata_lock.METADATA_LOCK_TIMEOUT_SECONDS` down the same way the load test already patches `GIT_FETCH_TIMEOUT_SECONDS`.
- `MetadataLockError` subclasses `CodeHostError`, not `WorktreeError`. That keeps `metadata_lock.py` from importing `worktree.py`, which would be a circular import. It never reaches the CLI raw: `__enter__` converts it to `WorktreeCreationError`, and the other two sites log it.

## Integration Points

### Provides to Other Slices
`git_metadata_lock` and `MetadataLockError` are public in `metadata_lock.py` only so `worktree.py` can import them. Nothing outside `codehost` uses them. Any future code that mutates the scratch worktrees' git metadata should take the same lock.

### Consumes from Other Slices
`sq review pr` ([review_pr.py:426](../../../src/squadron/cli/commands/review_pr.py#L426)) is the only production caller of `ScratchWorktree`. It gets the `WorktreeError` rendering fix from D4.

## Success Criteria

### Functional Requirements
- No two squadron-issued `git worktree add|remove|prune` calls whose worktree root is the same ever run at the same time, across threads or processes.
- `sq review pr` reports a worktree setup failure as an error panel with its fix hint and exit code 1.
- `git submodule update` runs outside the lock. Two runs' submodule fetches still overlap.
- A caller that can't get the lock within `METADATA_LOCK_TIMEOUT_SECONDS`:
  - in `__enter__`: raises `WorktreeCreationError` naming the lock file, and leaves no claim file behind;
  - in `sweep_orphans`: logs one WARNING, leaves the entry on disk, and does not raise;
  - in `_remove`: logs one WARNING, falls through to `rmtree`, and does not raise.
- A holder process killed while holding the lock does not block later callers.
- A lock file that can't be created (read-only worktree root) fails immediately with `MetadataLockError`, not after the deadline. Each call site handles it exactly like a timeout.

### Technical Requirements
- `fcntl` is imported only inside the lock helper. Neither `import squadron.codehost.metadata_lock` nor `import squadron.codehost.worktree` has a POSIX-only top-level import.
- ruff format, ruff check, and pyright are clean. The lock mechanism lives in `metadata_lock.py`, and `worktree.py` grows only by the call-site wrapping.
- Every `OSError` from the helper's mkdir, open, flock, or close is either converted to `MetadataLockError` or logged (D7). None escapes the helper.
- Tests:
  - the deterministic no-overlap test (D6);
  - one timeout test per call site, with the lock held by the test and the timeout patched down;
  - a holder-death test (a `python -c` subprocess takes the lock, gets killed, then the test acquires within the poll interval plus a margin);
  - the repeated-rounds load test.

### Integration Requirements
- `sq review pr` behaves identically for a single successful run. A worktree setup failure renders as a code-host error panel with exit 1, not a traceback. A CLI test covers this with a `ScratchWorktree` whose entry raises `WorktreeCreationError`.
- The existing `tests/codehost/test_worktree.py` suite passes unchanged, apart from the new tests.

### Verification Walkthrough

1. **Reproduce the race before the fix.** On the current `main`, run the load test repeatedly and record the failure count:
   ```bash
   for i in $(seq 1 50); do
     uv run pytest -q tests/load/test_worktree_concurrency.py \
       -k concurrent_worktree_creation 2>&1 | tail -1
   done | sort | uniq -c
   ```
   Expect some `1 failed` lines with the `commondir` fatal. If none show up locally, raise the test's `concurrency` in a scratch copy until they do, and record the setting that reproduces. That number sets the round count in step 4.

   **Actual (20260928, macOS):** the `commondir` fatal never reproduced: `50 1 passed` at concurrency 8, 0 of 50 at 32 once D8 was fixed, 0 of 30 at 64. Before D8 was fixed, concurrency 32 gave `3 1 failed` / `47 1 passed`, and all three were the sweep race D8 describes. The load test is sized on that rate (see its docstring). On Linux CI, #133's own rate is still unmeasured. Scratch copy used:
   ```bash
   sed "s/_CONCURRENCY = 32/_CONCURRENCY = 64/" tests/load/test_worktree_concurrency.py > /tmp/test_wt_c64.py
   uv run pytest -q -p no:cacheprovider /tmp/test_wt_c64.py -k concurrent_worktree_creation
   ```

2. **Deterministic proof.** After the fix:
   ```bash
   uv run pytest -q tests/codehost/test_metadata_lock.py tests/codehost/test_worktree.py -k "overlap or lock"
   ```
   Expected: all pass. Temporarily removing the `with git_metadata_lock(...)` around `add` makes the no-overlap test fail with a max-in-flight above 1. Revert after checking.

3. **Loud timeout.** Hold the lock from a second shell, then start a PR review with the timeout left at its default. It fails with `WorktreeCreationError` naming `~/.config/squadron/worktrees/.git-metadata.flock`. The PR needs an open head branch and at least one non-excluded (code) file changed, or the review is refused before the worktree stage. Use `uv run sq` so the branch's code runs rather than the installed release:
   ```bash
   python3 - <<'EOF' &
   import fcntl, time, pathlib
   p = pathlib.Path.home() / ".config/squadron/worktrees/.git-metadata.flock"
   p.parent.mkdir(parents=True, exist_ok=True)
   f = open(p, "a"); fcntl.flock(f, fcntl.LOCK_EX); time.sleep(300)
   EOF
   uv run sq review pr <number> --model haiku --no-save
   ```
   Expected (actual, 20260928): a WARNING `Could not take the git metadata lock for 'git worktree prune': timed out after 60s`, then an error panel `failed to create worktree at ...: timed out after 60s waiting for the lock` with the fix hint `Another squadron process may be holding the worktree metadata lock (~/.config/squadron/worktrees/.git-metadata.flock)...`. Exit 1, no traceback, **about 120s total, not 60s**: `__enter__`'s internal sweep waits out its own 60s on `prune` before `add` waits 60s, and each swept orphan's `remove` would add another 60s. With the original 120s holder, the second wait outlasted it and the review went through at 153s. Kill the holder (`kill %1`), rerun, and the review proceeds.

4. **Acceptance.** Repeat step 1's loop against the fixed code, plus one full run of the load file:
   ```bash
   uv run pytest -q tests/load/test_worktree_concurrency.py
   ```
   Expected: zero failures across the loop, and the in-file repeated-rounds test passes.

   **Actual (20260928):** `50 1 passed` (each run is 4 rounds of 32, about 12s); the full load file gives `2 passed`.

5. **Real parallel use.** In one repo, start two `sq review pr` runs against different PRs at the same moment (two terminals). Both reach the review phase, and neither reports a `commondir` error.

   **Actual (20260928):** run against two throwaway PRs (#160, #161, since closed), each changing one `.py` line:
   ```bash
   uv run sq review pr 160 --model haiku --no-save & uv run sq review pr 161 --model haiku --no-save & wait
   ```
   Both printed a review verdict panel (exit 0 on CONCERNS, exit 2 on FAIL; the exit code follows the verdict, not an error), with no `commondir` or lock message. Afterwards `~/.config/squadron/worktrees/` held only `.git-metadata.flock`.

## Implementation Notes

### Development Approach
1. Measure the pre-fix failure rate (walkthrough step 1) and write it in the DEVLOG. This is the baseline that shows the fix is doing something.
2. Write the deterministic no-overlap test and watch it fail on current code.
3. Create `metadata_lock.py` with the constants, `MetadataLockError`, and `git_metadata_lock`, including the lazy `fcntl` import and D7's error mapping. Unit-test it directly in `tests/codehost/test_metadata_lock.py`: acquire and release, timeout, a read-only root, and non-`BlockingIOError` flock failure through a patched `fcntl.flock`.
4. Wrap the four git calls (D4) and add the per-site timeout tests and the holder-death test. Add the `except WorktreeError` rendering in `review_pr.py` and its CLI test.
5. Turn the load test's single round into `ROUNDS` rounds of 8 inside the one test function. Pick `ROUNDS` so the measured pre-fix rate would fail the test with high probability. For example, if one round failed 1 run in 20, then 60 rounds fail pre-fix about 95% of the time. Keep the test's added runtime to a few seconds, since `tests/load/` runs on every invocation. If the pre-fix rate is too low to reach that within a few seconds, raise per-round concurrency instead of rounds. Record the chosen numbers and the reasoning in the test's docstring.
6. Update the module docstring to describe the metadata lock and the POSIX limit.

### Special Considerations
- Lock ordering: a thread never holds the metadata lock while waiting on a claim or `lock.json`, and never takes it twice. Every hold is one git call with nothing nested, so there is no deadlock path.
- The load test's `elapsed` budget (`GIT_QUERY_TIMEOUT_SECONDS * BUDGET_TOLERANCE`) still holds. Serialization adds milliseconds per creation, not seconds.
- Effort: 2/5, unchanged from the plan.
