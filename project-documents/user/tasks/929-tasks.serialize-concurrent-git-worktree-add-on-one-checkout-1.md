---
docType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
lld: user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Implementation complete. Slice 929 closed.
dateCreated: 20260927
dateUpdated: 20260928
status: complete
---

# Tasks: Serialize Concurrent `git worktree add` on One Checkout (1 of 2)

## Context Summary

Part 1 of two: baseline measurement, the failing no-overlap test, and the
`metadata_lock.py` module (Parts A–C). Part 2
(`929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-2.md`) wires the
lock into the call sites, fixes `review_pr.py`, and covers the load test, docs,
verification, and slice completion (Parts D–G).

Fixes [issue #133](https://github.com/ecorkran/squadron/issues/133). Two concurrent
`sq review pr` runs against one checkout can hit
`fatal: failed to read .git/worktrees/<sibling>/commondir` — git reading a sibling
worktree's admin directory mid-write. This slice adds an exclusive cross-process
`fcntl.flock` around the four git calls that touch worktree metadata
(`git worktree add`, `git worktree remove` ×2 call sites, `git worktree prune`), and
fixes `sq review pr` letting a `WorktreeError` escape as a raw traceback.

Full rationale is in the design
([929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md](project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md)) —
read D1–D7 before implementing. In particular:

- **D1**: `fcntl.flock`, a fresh open file per acquisition (never cache or share the
  file descriptor) — this is what makes threads serialize against each other, not
  just processes.
- **D2**: one lock file per worktree root (`~/.config/squadron/worktrees/`), not per
  repository. No git call needed to key it.
- **D3**: poll `LOCK_EX | LOCK_NB` every `_METADATA_LOCK_POLL_SECONDS` (0.05s) until
  `METADATA_LOCK_TIMEOUT_SECONDS` (`2 * GIT_QUERY_TIMEOUT_SECONDS` = 60s) runs out.
  The design table names this constant `_POLL_SECONDS`; its own D3 prose names it
  `_METADATA_LOCK_POLL_SECONDS`. **This task file picks `_METADATA_LOCK_POLL_SECONDS`**
  (D3's prose is the more specific source) — use that name, not the table's shorter
  form.
- **D4**: each of the three methods reports a lock timeout differently — `__enter__`
  raises `WorktreeCreationError`; `sweep_orphans` and `_remove` log a WARNING and never
  raise (their existing documented contracts).
- **D5**: POSIX only. `import fcntl` lives inside `git_metadata_lock`, never at module
  level — `review_pr.py` imports `worktree` at module level and must not break on
  Windows.
- **D6**: the deterministic no-overlap test must fail against today's code, before any
  of this slice's fix lands.
- **D7**: every filesystem error the lock helper can hit maps to exactly one outcome
  (table in the design) — memorize that table before writing `metadata_lock.py`.

**Current project state:** design only, no code changes. Effort for the whole slice:
2/5 per the design.

**Dependencies:** none. Everything this slice touches shipped with slice 382.

**Next planned slice:** none specific — general maintenance backlog per
[900-slices.maintenance-and-refactoring.md](project-documents/user/architecture/900-slices.maintenance-and-refactoring.md).

---

## Part A — Baseline measurement

### Task A.1 — Reproduce the race and record the pre-fix failure rate

- [x] Effort: 1/5
- [x] From the squadron repo root, run the design's Verification Walkthrough step 1:
      ```bash
      for i in $(seq 1 50); do
        uv run pytest -q tests/load/test_worktree_concurrency.py \
          -k concurrent_worktree_creation 2>&1 | tail -1
      done | sort | uniq -c
      ```
- [x] Record the exact `uniq -c` output (pass count, fail count) as a note under this
      task item. This is the baseline Part E's `ROUNDS` calculation depends on — do
      not skip or guess it.
- [x] If zero failures show up in 50 runs, raise the load test's `concurrency` in a
      **scratch copy** (do not commit this change) until failures appear, and record
      the concurrency value that reproduces the race alongside the failure rate.
- [x] No commit for this task — nothing in the working tree changes.
- **Result (20260928, macOS, Darwin 25.5.0):** concurrency 8: `50 1 passed`.
  Concurrency 32 (scratch copy): `3 1 failed` / `47 1 passed`. None of the three
  failures was the #133 `commondir` error. All three were the sweep race in Task A.2.

### Task A.2 — Sweep reads the claim before the lock (design D8)

- [x] Effort: 2/5
- [x] Added after Task A.1's baseline: the elevated-concurrency failures were
      `sweep_orphans` removing live worktrees, not the #133 metadata race. See D8.
- [x] Add `test_sweep_spares_a_worktree_whose_claim_hands_off_to_its_lock_mid_sweep`
      to `tests/codehost/test_worktree.py`: seed an entry directory plus a live
      claim, and wrap `worktree._read_lock` so that right after its first call it
      performs `__enter__`'s handoff (write `lock.json`, unlink the claim). Assert
      the entry still exists and no `git worktree remove` was issued. Confirm it
      fails on the current code.
- [x] In `sweep_orphans`, read and check the claim first, then the lock. An entry
      is swept only when neither names a live owner.
- [x] Run: `pytest tests/codehost/test_worktree.py -x` (existing sweep tests stay green).
- [x] Re-run Task A.1's concurrency-32 scratch measurement (50 runs) and record
      the result under this task. It is the baseline Part E's `ROUNDS` uses.
- **Result (20260928, macOS):** after the fix, concurrency 32: `50 1 passed`;
  concurrency 64: `30 1 passed`. The #133 `commondir` race did not reproduce locally
  at any concurrency tried. Its only observed occurrence is the v0.13.3 tag CI run.
- [x] **Commit**: `fix: read worktree claim before lock in orphan sweep`

---

## Part B — Deterministic no-overlap test (must fail on today's code)

### Task B.1 — Add a thread-safe, overlap-tracking fake `ProcessRunner`

- [x] Effort: 2/5
- [x] In `tests/codehost/test_worktree.py`, add a small class (e.g.
      `_OverlapTrackingRunner`) implementing the `ProcessRunner` protocol
      ([src/squadron/core/process_runner.py](src/squadron/core/process_runner.py),
      `class ProcessRunner(Protocol)`), distinct from the existing `FakeProcessRunner`
      (that one mutates a list without a lock and is not safe to call from multiple
      threads at once).
- [x] Behavior of `.run(argv, cwd=, timeout=, env=None, stdin=None)`:
      - [x] First line of `.run`: `argv = tuple(argv)`. Callers pass lists, and a list
        slice never equals a tuple literal, so without this every branch below
        misses and falls through to the raise. Same idiom as
        `tests/codehost/fake_runner.py`'s `argv_tuple = tuple(argv)`.
      - [x] If `argv[:2] == ("git", "worktree")`: under a `threading.Lock`, increment an
        in-flight counter and update a running max; release the lock; `time.sleep`
        a short fixed duration (e.g. 0.02s — long enough to make an unserialized
        overlap essentially certain, short enough to keep the test fast); reacquire
        the lock to decrement the counter.
        - [x] **If `argv[2] == "add"`** (shape `["git", "worktree", "add", "--detach",
          str(path), head_ref]` — the path is `argv[4]`): **create the target
          directory** (`Path(argv[4]).mkdir(parents=True)`) before returning
          success. This is not optional: production code writes the lock file
          straight to `path / "lock.json"` immediately after a successful `add`
          returns (`worktree.py`, right after the `add` call), with no git call in
          between — a fake that returns success without creating the directory
          makes that write raise `FileNotFoundError`, and the test fails on that
          error instead of on the overlap assertion it exists to check.
        - [x] If `argv[2] == "remove"` or `argv[2] == "prune"`: no directory side
          effect needed — `sweep_orphans` and `_remove` both already fall back to
          `shutil.rmtree` themselves once the (faked) git call returns, so the
          fake doesn't need to delete anything to keep the test's end state clean.
        - [x] Return a canned success `ProcessResult` in every case (reuse
          `_worktree_add_ok()`'s shape — `returncode=0`, empty `stdout`/`stderr`).
      - [x] If `argv[:1] == ("ps",)`: return `_ps_ok()` immediately (already defined in
        this file) — no counting, no sleep.
      - [x] If `argv[:2] == ("git", "submodule")`: return a canned success immediately —
        no counting, no sleep. (`_init_submodules` runs during `__enter__`, with
        `cwd=str(path)` — since `path` was created by the `add` branch above,
        this call needs no directory side effect of its own.)
      - [x] Anything else: raise (reuse `UnscriptedCallError` from
        `tests/codehost/fake_runner.py`, or a local equivalent) — an unscripted call
        here means the test's assumptions about what `ScratchWorktree`/`sweep_orphans`
        invoke are wrong, and that must fail loudly, not silently pass.
      - [x] Expose the recorded max in-flight count as a public attribute or method.
- [x] Do not add real git process spawning here — this stays a pure fake, is what
      makes the test deterministic and fast rather than timing-dependent, unlike
      `tests/load/test_worktree_concurrency.py`.

### Task B.2 — Write the no-overlap test; confirm it fails on today's code

- [x] Effort: 3/5
- [x] In the same file, add
      `test_concurrent_call_sites_never_overlap_a_metadata_git_call` (name must
      contain "overlap" — the walkthrough's `-k "overlap or lock"` filter selects on
      it):
      - Use one shared `_OverlapTrackingRunner` instance and one shared `tmp_path`
        as `root`.
      - Before starting any threads, seed `root` with one bogus, lock-less,
        claim-less directory (e.g. `root / "stale-entry"`, containing no
        `lock.json`) so `sweep_orphans` treats it as an orphan and actually issues
        its `git worktree remove` + `git worktree prune` calls, rather than
        short-circuiting on an empty directory.
      - Start several threads (e.g. 6) concurrently:
        - At least one thread calls `sweep_orphans(runner, CHECKOUT_CWD, root)`.
        - The rest each run one full `ScratchWorktree(...).__enter__()` /
          `.__exit__()` cycle, each with a distinct `run_id` (so paths don't
          collide) but the same `root` and `runner`.
      - Join all threads with a bounded timeout (fail the test, don't hang, if a
        thread doesn't finish).
      - Assert the runner's recorded max in-flight `git worktree` count is exactly
        `1`.
- [x] Run: `pytest tests/codehost/test_worktree.py -k overlap -x`. **Confirm it
      fails** against today's code (no lock exists yet) — this is the point: it
      proves the race exists before recording it as fixed. Do not proceed to Part C
      until you've seen this fail.
- [x] Do not commit `metadata_lock.py` or any wiring yet — this task only adds the
      test and its fake runner, and confirms the failure.

### Task B.3 — Commit Part B

- [x] Effort: 1/5
- [x] Confirm current working directory is the squadron project root.
- [x] `git add` and commit Part B's changes. The suite is expected to have one new
      failing test at this point — note that in the commit body so it isn't mistaken
      for an accident later. Branch CI will show red on this commit and on Part C's
      commit (Task C.5) too, since nothing wires the new lock in until Part D's
      commit (Task D.9) — expected, not a regression to chase down mid-slice.
      Suggested message: `test: add failing deterministic no-overlap test for worktree metadata races`.

---

## Part C — `metadata_lock.py`: the lock module and its unit tests

### Task C.1 — Create `metadata_lock.py`: constants and `MetadataLockError`

- [x] Effort: 1/5
- [x] Create `src/squadron/codehost/metadata_lock.py` with a module docstring
      describing: the race this serializes (per the Overview), that it is POSIX-only
      (D5), and where the lock file lives (D2).
- [x] Define, each with a short comment stating its purpose:
      - `_LOCK_FILENAME = ".git-metadata.flock"`
      - `_METADATA_LOCK_POLL_SECONDS = 0.05`
      - `METADATA_LOCK_TIMEOUT_SECONDS = 2 * GIT_QUERY_TIMEOUT_SECONDS` — import
        `GIT_QUERY_TIMEOUT_SECONDS` from
        [src/squadron/codehost/refs.py](src/squadron/codehost/refs.py). Comment
        states this is derived, not independently chosen (D3).
- [x] Define `MetadataLockError(CodeHostError)` (import `CodeHostError` from
      [src/squadron/codehost/errors.py](src/squadron/codehost/errors.py) — **not**
      from `worktree.py`, which would create a circular import per the design's
      Patterns section). Constructor takes `lock_path: Path` and `detail: str`,
      stores both as attributes, and builds the exception message from them.

### Task C.2 — Implement `git_metadata_lock(root)`

- [x] Effort: 3/5
- [x] Implement `git_metadata_lock(root: Path) -> ContextManager[None]` (a
      `@contextlib.contextmanager` generator function is the natural shape here).
      Behavior per D3/D7, in order:
      1. `import fcntl` **inside this function** (D5) — catch the case where it's
         unavailable and raise `MetadataLockError` naming the platform in `detail`,
         per D5. (`try: import fcntl / except ImportError as exc: raise
         MetadataLockError(...) from exc`.)
      2. `root.mkdir(parents=True, exist_ok=True)` — on `OSError`, raise
         `MetadataLockError` at once (`lock_path` = the would-be lock file path,
         `detail` names the path and `exc.strerror`). No retry (D7 row 1).
      3. `open(lock_path, "a")` — on `OSError`, same outcome as step 2 (D7 row 2).
      4. Poll loop: `fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)` using
         `time.monotonic()` against a deadline `start + METADATA_LOCK_TIMEOUT_SECONDS`.
         - `BlockingIOError`: sleep `_METADATA_LOCK_POLL_SECONDS`, retry, until the
           deadline passes — then raise `MetadataLockError` (detail states the
           seconds waited) (D7 row 3).
         - Any other `OSError` (e.g. `ENOLCK`, `EBADF`): raise `MetadataLockError`
           immediately — it must **not** enter the retry loop (D7 row 4). This is
           the behavior Task C.3b's test pins.
      5. `yield` once the lock is held.
      6. On exit (`finally`): `fcntl.flock(f, fcntl.LOCK_UN)` then `f.close()`. On
         `OSError` here, log at WARNING and do **not** raise — closing the
         descriptor releases the lock regardless, and raising here would mask
         whatever exception is already propagating out of the `with` body (D7 row
         5).
- [x] Every raised exception from this function must be a `MetadataLockError` — no
      bare `OSError`/`ImportError`/`BlockingIOError` escapes it (Technical
      Requirements).
- [x] Never cache or share the open file descriptor across acquisitions (D1) — each
      call to `git_metadata_lock` opens, locks, and closes its own file.

### Task C.3a — Unit tests: acquire/release and timeout

- [x] Effort: 2/5
- [x] Create `tests/codehost/test_metadata_lock.py`. Every test name in Tasks
      C.3a–C.3c starts with `test_lock_` so `-k lock` (per the walkthrough) matches
      all of them:
      - [x] **`test_lock_is_acquired_and_released_for_reuse`**: `with
        git_metadata_lock(root): pass` succeeds; a second
        `with git_metadata_lock(root): pass` immediately afterward also succeeds
        (lock was released, not leaked).
      - [x] **`test_lock_blocks_a_second_acquirer_until_timeout`**: from the test's own
        process, `open()` + `fcntl.flock(f, fcntl.LOCK_EX)` the same lock file path
        (`root / ".git-metadata.flock"`) directly, so the test itself holds it.
        Then call `git_metadata_lock(root)` with
        `METADATA_LOCK_TIMEOUT_SECONDS` monkeypatched down (e.g. to `0.2`) and
        assert it raises `MetadataLockError` after roughly that patched timeout
        (assert elapsed is close to the patched value, not the real 60s default —
        a hung test here means the patch didn't take).
- [x] Run: `pytest tests/codehost/test_metadata_lock.py -x`.

### Task C.3b — Unit tests: D7 immediate-failure mapping

- [x] Effort: 2/5
- [x] In the same file, add:
      - [x] **`test_lock_fails_immediately_on_a_read_only_root`**: `os.chmod` a real
        `tmp_path` subdirectory to remove write permission (e.g. `0o500`), then
        call `git_metadata_lock` targeting a lock file inside it; assert
        `MetadataLockError` is raised **immediately** (assert elapsed is small,
        well under the timeout — proving D7's "fails at once, not after the
        deadline"). Skip this test if `hasattr(os, "getuid") and os.getuid() == 0`
        — root bypasses permission checks, which would make the test silently
        pass for the wrong reason.
      - [x] **`test_lock_fails_immediately_on_non_blocking_io_flock_error`**:
        `monkeypatch.setattr(fcntl, "flock", ...)` (import `fcntl` in the test
        module) so the first call raises e.g. `OSError(errno.ENOLCK, "no locks
        available")`. Assert `MetadataLockError` is raised immediately (elapsed
        small, no retry loop entered) — this is the test that pins D7 row 4's
        "must not enter the retry loop" behavior; a bug here would otherwise
        silently retry for the full 60s before failing.
      - [x] **`test_lock_fails_with_detail_when_fcntl_is_unavailable`**:
        `monkeypatch.setitem(sys.modules, "fcntl", None)` — this makes any
        subsequent `import fcntl` raise `ImportError` (a documented
        `sys.modules` trick, not real platform unavailability). Assert
        `MetadataLockError` is raised and its `detail` names the platform/import
        failure.
- [x] Run: `pytest tests/codehost/test_metadata_lock.py -x`.

### Task C.3c — Unit tests: release failure (D7 row 5)

- [x] Effort: 2/5
- [x] In the same file, add:
      - [x] **`test_lock_release_failure_logs_warning_and_does_not_raise`** (D7 row
        5): `monkeypatch.setattr(fcntl, "flock", ...)` with a stateful fake that
        succeeds on the acquire call (`LOCK_EX | LOCK_NB`) but raises `OSError` on
        the release call (`LOCK_UN`) — distinguish the two by the `operation`
        argument the fake receives. Run a normal, exception-free
        `with git_metadata_lock(root): pass` body. Assert: no exception
        propagates out of the `with` block, and a WARNING was logged (`caplog`).
      - [x] **`test_lock_release_failure_does_not_mask_a_body_exception`** (D7 row 5,
        the other half): same release-failure setup as above, but this time the
        `with` block's own body raises a distinct exception (e.g. a local
        `class _BodyError(Exception)`). Assert that **`_BodyError`** propagates
        out of the `with` statement — not an `OSError` and not a
        `MetadataLockError` — proving the release-path failure is logged and
        swallowed rather than replacing whatever the body was already raising.
- [x] Run: `pytest tests/codehost/test_metadata_lock.py -x`.

### Task C.4 — Holder-death test

- [x] Effort: 2/5
- [x] In the same file, add
      **`test_a_killed_holder_does_not_block_a_later_acquirer`** (name contains
      "holder" — the `-k holder` filter below selects on it), proving a killed
      holder does not block later callers (Success Criteria: "A holder process
      killed while holding the lock does not block later callers"):
      - Launch a real subprocess (`subprocess.Popen([sys.executable, "-c", ...])`
        — use `sys.executable`, not a bare `"python"` string; many systems only
        have `python3` on `PATH`, and the subprocess must run under the same
        interpreter this test itself runs under) running a short inline Python
        script that opens the same lock file path this test will use, calls
        `fcntl.flock(f, fcntl.LOCK_EX)` (blocking — no `LOCK_NB`), then sleeps for
        a long duration (e.g. 60s) so it would still be holding the lock if not
        killed.
      - Poll (with a short bounded loop, not a fixed sleep) until you can confirm
        the subprocess actually holds the lock — e.g. attempt a non-blocking
        `flock` from the test process and expect `BlockingIOError` — before
        proceeding, so the test doesn't race its own subprocess's startup.
      - `proc.kill()`, then `proc.wait()`.
      - Call `git_metadata_lock(root)` from the test and assert it acquires within
        `_METADATA_LOCK_POLL_SECONDS` plus a generous margin (e.g. under 1 second)
        — proving the kernel released the lock automatically, not that the test
        happened to wait out a full timeout.
- [x] Run: `pytest tests/codehost/test_metadata_lock.py -k holder -x`.

### Task C.5 — Commit Part C

- [x] Effort: 1/5
- [x] Confirm current working directory is the squadron project root.
- [x] `git add` and commit Part C's changes. Part B's failing test is still failing
      at this point — `metadata_lock.py` exists but nothing calls it yet.
      Suggested message: `feat: add cross-process metadata_lock for git worktree metadata calls`.

---

Continue with Part D in `929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-2.md`.
