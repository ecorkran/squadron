---
docType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
lld: user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design complete, not yet reviewed. No code changes yet.
dateCreated: 20260927
dateUpdated: 20260927
status: not_started
---

# Tasks: Serialize Concurrent `git worktree add` on One Checkout

## Context Summary

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

- [ ] Effort: 1/5
- [ ] From the squadron repo root, run the design's Verification Walkthrough step 1:
      ```bash
      for i in $(seq 1 50); do
        uv run pytest -q tests/load/test_worktree_concurrency.py \
          -k concurrent_worktree_creation 2>&1 | tail -1
      done | sort | uniq -c
      ```
- [ ] Record the exact `uniq -c` output (pass count, fail count) as a note under this
      task item. This is the baseline Part E's `ROUNDS` calculation depends on — do
      not skip or guess it.
- [ ] If zero failures show up in 50 runs, raise the load test's `concurrency` in a
      **scratch copy** (do not commit this change) until failures appear, and record
      the concurrency value that reproduces the race alongside the failure rate.
- [ ] No commit for this task — nothing in the working tree changes.

---

## Part B — Deterministic no-overlap test (must fail on today's code)

### Task B.1 — Add a thread-safe, overlap-tracking fake `ProcessRunner`

- [ ] Effort: 2/5
- [ ] In `tests/codehost/test_worktree.py`, add a small class (e.g.
      `_OverlapTrackingRunner`) implementing the `ProcessRunner` protocol
      ([src/squadron/core/process_runner.py](src/squadron/core/process_runner.py),
      `class ProcessRunner(Protocol)`), distinct from the existing `FakeProcessRunner`
      (that one mutates a list without a lock and is not safe to call from multiple
      threads at once).
- [ ] Behavior of `.run(argv, cwd=, timeout=, env=None, stdin=None)`:
      - If `argv[:2] == ("git", "worktree")`: under a `threading.Lock`, increment an
        in-flight counter and update a running max; release the lock; `time.sleep`
        a short fixed duration (e.g. 0.02s — long enough to make an unserialized
        overlap essentially certain, short enough to keep the test fast); reacquire
        the lock to decrement the counter; return a canned success `ProcessResult`
        (reuse `_worktree_add_ok()`'s shape — `returncode=0`, empty `stdout`/`stderr`).
      - If `argv[:1] == ("ps",)`: return `_ps_ok()` immediately (already defined in
        this file) — no counting, no sleep.
      - If `argv[:2] == ("git", "submodule")`: return a canned success immediately —
        no counting, no sleep. (`_init_submodules` runs during `__enter__`; this
        keeps it a no-op for this test.)
      - Anything else: raise (reuse `UnscriptedCallError` from
        `tests/codehost/fake_runner.py`, or a local equivalent) — an unscripted call
        here means the test's assumptions about what `ScratchWorktree`/`sweep_orphans`
        invoke are wrong, and that must fail loudly, not silently pass.
      - Expose the recorded max in-flight count as a public attribute or method.
- [ ] Do not add real git process spawning here — this stays a pure fake, is what
      makes the test deterministic and fast rather than timing-dependent, unlike
      `tests/load/test_worktree_concurrency.py`.

### Task B.2 — Write the no-overlap test; confirm it fails on today's code

- [ ] Effort: 3/5
- [ ] In the same file, add
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
- [ ] Run: `pytest tests/codehost/test_worktree.py -k overlap -x`. **Confirm it
      fails** against today's code (no lock exists yet) — this is the point: it
      proves the race exists before recording it as fixed. Do not proceed to Part C
      until you've seen this fail.
- [ ] Do not commit `metadata_lock.py` or any wiring yet — this task only adds the
      test and its fake runner, and confirms the failure.

### Task B.3 — Commit Part B

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] `git add` and commit Part B's changes. The suite is expected to have one new
      failing test at this point — note that in the commit body so it isn't mistaken
      for an accident later.
      Suggested message: `test: add failing deterministic no-overlap test for worktree metadata races`.

---

## Part C — `metadata_lock.py`: the lock module and its unit tests

### Task C.1 — Create `metadata_lock.py`: constants and `MetadataLockError`

- [ ] Effort: 1/5
- [ ] Create `src/squadron/codehost/metadata_lock.py` with a module docstring
      describing: the race this serializes (per the Overview), that it is POSIX-only
      (D5), and where the lock file lives (D2).
- [ ] Define, each with a short comment stating its purpose:
      - `_LOCK_FILENAME = ".git-metadata.flock"`
      - `_METADATA_LOCK_POLL_SECONDS = 0.05`
      - `METADATA_LOCK_TIMEOUT_SECONDS = 2 * GIT_QUERY_TIMEOUT_SECONDS` — import
        `GIT_QUERY_TIMEOUT_SECONDS` from
        [src/squadron/codehost/refs.py](src/squadron/codehost/refs.py). Comment
        states this is derived, not independently chosen (D3).
- [ ] Define `MetadataLockError(CodeHostError)` (import `CodeHostError` from
      [src/squadron/codehost/errors.py](src/squadron/codehost/errors.py) — **not**
      from `worktree.py`, which would create a circular import per the design's
      Patterns section). Constructor takes `lock_path: Path` and `detail: str`,
      stores both as attributes, and builds the exception message from them.

### Task C.2 — Implement `git_metadata_lock(root)`

- [ ] Effort: 3/5
- [ ] Implement `git_metadata_lock(root: Path) -> ContextManager[None]` (a
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
           the behavior Task C.4's test pins.
      5. `yield` once the lock is held.
      6. On exit (`finally`): `fcntl.flock(f, fcntl.LOCK_UN)` then `f.close()`. On
         `OSError` here, log at WARNING and do **not** raise — closing the
         descriptor releases the lock regardless, and raising here would mask
         whatever exception is already propagating out of the `with` body (D7 row
         5).
- [ ] Every raised exception from this function must be a `MetadataLockError` — no
      bare `OSError`/`ImportError`/`BlockingIOError` escapes it (Technical
      Requirements).
- [ ] Never cache or share the open file descriptor across acquisitions (D1) — each
      call to `git_metadata_lock` opens, locks, and closes its own file.

### Task C.3 — Unit tests: acquire/release, mutual exclusion, timeout

- [ ] Effort: 3/5
- [ ] Create `tests/codehost/test_metadata_lock.py`. Tests (name each so `-k lock`
      matches the file, per the walkthrough):
      - **Acquire and release**: `with git_metadata_lock(root): pass` succeeds; a
        second `with git_metadata_lock(root): pass` immediately afterward also
        succeeds (lock was released, not leaked).
      - **Mutual exclusion**: from the test's own process, `open()` +
        `fcntl.flock(f, fcntl.LOCK_EX)` the same lock file path
        (`root / ".git-metadata.flock"`) directly, so the test itself holds it.
        Then call `git_metadata_lock(root)` with
        `METADATA_LOCK_TIMEOUT_SECONDS` monkeypatched down (e.g. to `0.2`) and
        assert it raises `MetadataLockError` after roughly that patched timeout
        (assert elapsed is close to the patched value, not the real 60s default —
        a hung test here means the patch didn't take).
      - **Read-only root**: `os.chmod` a real `tmp_path` subdirectory to remove
        write permission (e.g. `0o500`), then call `git_metadata_lock` targeting a
        lock file inside it; assert `MetadataLockError` is raised **immediately**
        (assert elapsed is small, well under the timeout — proving D7's "fails at
        once, not after the deadline"). Skip this test if
        `hasattr(os, "getuid") and os.getuid() == 0` — root bypasses permission
        checks, which would make the test silently pass for the wrong reason.
      - **Non-`BlockingIOError` flock failure**: `monkeypatch.setattr(fcntl,
        "flock", ...)` (import `fcntl` in the test module) so the first call raises
        e.g. `OSError(errno.ENOLCK, "no locks available")`. Assert
        `MetadataLockError` is raised immediately (elapsed small, no retry loop
        entered) — this is the test that pins D7 row 4's "must not enter the retry
        loop" behavior; a bug here would otherwise silently retry for the full 60s
        before failing.
      - **Fcntl unavailable**: `monkeypatch.setitem(sys.modules, "fcntl", None)` —
        this makes any subsequent `import fcntl` raise `ImportError` (a documented
        `sys.modules` trick, not real platform unavailability). Assert
        `MetadataLockError` is raised and its `detail` names the platform/import
        failure.
- [ ] Run: `pytest tests/codehost/test_metadata_lock.py -x`.

### Task C.4 — Holder-death test

- [ ] Effort: 2/5
- [ ] In the same file, add a test proving a killed holder does not block later
      callers (Success Criteria: "A holder process killed while holding the lock
      does not block later callers"):
      - Launch a real subprocess (`subprocess.Popen`) running a short inline
        Python script (`python -c ...`) that opens the same lock file path this
        test will use, calls `fcntl.flock(f, fcntl.LOCK_EX)` (blocking — no
        `LOCK_NB`), then sleeps for a long duration (e.g. 60s) so it would still be
        holding the lock if not killed.
      - Poll (with a short bounded loop, not a fixed sleep) until you can confirm
        the subprocess actually holds the lock — e.g. attempt a non-blocking
        `flock` from the test process and expect `BlockingIOError` — before
        proceeding, so the test doesn't race its own subprocess's startup.
      - `proc.kill()`, then `proc.wait()`.
      - Call `git_metadata_lock(root)` from the test and assert it acquires within
        `_METADATA_LOCK_POLL_SECONDS` plus a generous margin (e.g. under 1 second)
        — proving the kernel released the lock automatically, not that the test
        happened to wait out a full timeout.
- [ ] Run: `pytest tests/codehost/test_metadata_lock.py -k holder -x`.

### Task C.5 — Commit Part C

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] `git add` and commit Part C's changes. Part B's failing test is still failing
      at this point — `metadata_lock.py` exists but nothing calls it yet.
      Suggested message: `feat: add cross-process metadata_lock for git worktree metadata calls`.

---

## Part D — Wire the four call sites and fix `review_pr.py`'s error handling

### Task D.1 — Wrap `ScratchWorktree.__enter__`'s `git worktree add`

- [ ] Effort: 3/5
- [ ] In [src/squadron/codehost/worktree.py](src/squadron/codehost/worktree.py),
      import `git_metadata_lock` and `MetadataLockError` from the new
      `squadron.codehost.metadata_lock` module.
- [ ] Wrap the `self._runner.run(["git", "worktree", "add", ...])` call (currently
      lines 332–336) in `with git_metadata_lock(self._root):`.
- [ ] Add `except MetadataLockError as exc:` **before** the existing
      `except BaseException:` clause (currently lines 346–350) — order matters,
      since `MetadataLockError` also matches `BaseException` and Python takes the
      first matching clause. The new clause must:
      - Log at ERROR (mirrors the existing `_logger.error("git worktree add
        failed...")` pattern just above it).
      - Call `_unlink_claim(claim_path)` — same as the `BaseException` clause does,
        so a lock timeout leaves no claim behind (Success Criteria).
      - Raise `WorktreeCreationError(path, exc.detail, fix_hint=...) from exc`. The
        `fix_hint` must name `exc.lock_path` and state that another squadron
        process may be holding the worktree metadata lock (D4) — exact wording is
        not prescribed, but both the path and "another squadron process" must
        appear in it.
      - Add a one-line comment above this clause naming which never-raise contract
        it does *not* need to honor here (`__enter__` is allowed to raise) — per
        the exception-handling rule, every `except MetadataLockError` needs a
        comment stating its contract, even a permissive one.

### Task D.2 — Wrap `sweep_orphans`'s two lock-guarded calls

- [ ] Effort: 3/5
- [ ] In the same file, wrap the per-orphan `git worktree remove --force` call
      (currently lines 251–256, inside the existing
      `try: ... except ProcessTimedOutError:` block) in
      `with git_metadata_lock(worktree_root):`.
- [ ] Add `except MetadataLockError:` as a sibling to the existing
      `except ProcessTimedOutError:` clause (same `try` statement, two `except`
      clauses). On this branch: log a WARNING (mirrors the existing
      `_logger.warning("Timed out removing orphaned worktree %s...")` wording and
      tone) and **do not** call `_rmtree(entry)` afterward for this iteration —
      `continue` to the next loop entry instead. Comment states this serves the
      documented "sweep_orphans never raises" contract, and that skipping
      `_rmtree` here is required: git still registers this entry, and deleting the
      directory out from under it would corrupt git's own worktree metadata (per
      the design's sweep-path behavior in D4).
- [ ] Wrap the final `git worktree prune` call (currently lines 264–267) in
      `with git_metadata_lock(worktree_root):`, and add `except MetadataLockError:`
      alongside the existing `except ProcessTimedOutError:` clause there too,
      logging at WARNING with the same comment convention.

### Task D.3 — Wrap `_remove`'s `git worktree remove`

- [ ] Effort: 2/5
- [ ] In the same file, wrap `_remove`'s `git worktree remove --force` call
      (currently lines 398–403) in `with git_metadata_lock(self._root):` — use
      `self._root`, not `self._checkout_cwd` (the lock is keyed on the worktree
      root per D2, not the git checkout).
- [ ] Add `except MetadataLockError:` alongside the existing
      `except ProcessTimedOutError:` clause. Log at WARNING (mirror the existing
      `_logger.warning("Timed out removing worktree %s...")` wording), and let
      execution fall through to the existing `if path.exists(): _rmtree(path)`
      below exactly as the current `ProcessTimedOutError` branch already does —
      this matches how `_remove` already handles a git-side timeout (D4). Comment
      states this serves `_remove`'s documented never-raise contract.

### Task D.4 — Per-call-site timeout tests

- [ ] Effort: 3/5
- [ ] In `tests/codehost/test_worktree.py`, add a small helper (fixture or plain
      function) that, given a `root: Path`, opens and `flock`s the real lock file
      at `root / ".git-metadata.flock"` from the test process itself (real
      `fcntl`, real file) — simulating "another process holds it" without threads,
      since only one call site executes per test here. Release it in a `finally`
      or fixture teardown.
- [ ] With `metadata_lock.METADATA_LOCK_TIMEOUT_SECONDS` monkeypatched down (e.g.
      to `0.2`) and the lock held via the helper above, add:
      - `test_enter_raises_worktree_creation_error_on_lock_timeout`: calling
        `ScratchWorktree(...).  __enter__()` (via `FakeProcessRunner`, scripted for
        `ps` only — the `git worktree add` call must never actually run, since the
        lock times out before it) raises `WorktreeCreationError`, whose message or
        `fix_hint` names the lock path. Assert the claim file
        (`_claim_path(path)`) does not exist afterward.
      - `test_sweep_orphans_logs_warning_and_skips_entry_on_remove_lock_timeout`:
        with one orphaned entry present (no lock, no live claim), `sweep_orphans`
        does not raise, logs a WARNING (use `caplog`), and the orphan directory is
        still present afterward (not removed).
      - `test_sweep_orphans_logs_warning_on_prune_lock_timeout`: an empty orphan
        root (`sweep_orphans` returns early — check the code) is the wrong shape
        for reaching the `prune` call under a lock timeout; construct the case so
        the per-entry loop has nothing to sweep but `prune` still runs and hits
        the lock timeout you've set up (i.e., an empty *directory* with no
        entries, so the loop body never executes but `prune` still fires). Assert
        no raise, one WARNING logged.
      - `test_remove_logs_warning_and_falls_through_to_rmtree_on_lock_timeout`:
        `ScratchWorktree._remove(path)` with a real directory present at `path`
        (`path.mkdir()`) does not raise, logs a WARNING, and the directory is gone
        afterward (the `rmtree` fallback ran).
- [ ] Run: `pytest tests/codehost/test_worktree.py -k timeout -x`.

### Task D.5 — Confirm the deterministic no-overlap test now passes

- [ ] Effort: 1/5
- [ ] Run: `pytest tests/codehost/test_worktree.py -k overlap -x`. It must now pass
      — Part B recorded it failing against unwrapped call sites; this confirms the
      wiring in Tasks D.1–D.3 is what fixed it.
- [ ] Temporarily remove the `with git_metadata_lock(...)` around just the `add`
      call (Task D.1) and re-run — confirm the test fails again with a max
      in-flight above 1 (per the design's Verification Walkthrough step 2). Revert
      immediately after checking; do not leave this reverted.

### Task D.6 — `review_pr.py`: render `WorktreeError` as an error panel

- [ ] Effort: 3/5
- [ ] In [src/squadron/cli/commands/review_pr.py](src/squadron/cli/commands/review_pr.py),
      import `WorktreeError` alongside the existing `ScratchWorktree` import
      (currently line 32: `from squadron.codehost.worktree import ScratchWorktree`).
- [ ] Restructure the `with ScratchWorktree(...) as worktree:` block (currently
      lines 425–429) so **only entry** (`__enter__`) is inside a
      `try: ... except WorktreeError:` — the review run inside the block
      (`_run(...)`, currently line 429) must stay outside that `except`, per D4
      ("Only entry is wrapped, not the review run inside the block"). This
      requires calling `.__enter__()`/`.__exit__()` manually instead of a bare
      `with` statement — a `with` statement cannot catch an exception from only
      its own `__enter__` separately from its body. Shape:
      ```python
      scratch = ScratchWorktree(host.runner, resolved.record, fetched.head_ref, run_id, checkout_cwd)
      try:
          worktree = scratch.__enter__()
      except WorktreeError as exc:
          render_code_host_error(exc)
          raise typer.Exit(code=1) from exc
      try:
          worktree_path = worktree.path
          result = _run(str(worktree.path), checkout_cwd)
      finally:
          scratch.__exit__(None, None, None)
      ```
      This is the same pattern the file already uses at line 355
      (`except CodeHostError as exc: render_code_host_error(exc); raise
      typer.Exit(code=1) from exc`) — reuse `render_code_host_error`, don't
      reimplement it.
- [ ] Verify `no_tools` behavior (the `if no_tools:` branch just above, currently
      line 419) is untouched — this restructuring only affects the `else` branch.

### Task D.7 — CLI test: worktree creation failure renders as a panel, not a traceback

- [ ] Effort: 2/5
- [ ] In `tests/cli/test_review_pr.py`, add
      `from squadron.codehost.worktree import ScratchWorktree, WorktreeCreationError`
      to the file's imports (`Path` is already imported at line 12; neither
      `ScratchWorktree` nor `WorktreeCreationError` is imported yet).
- [ ] Add a test following the existing pattern
      `test_discussion_fetch_failure_renders_as_an_adapter_error_not_a_traceback`
      (same file): `monkeypatch.setattr(ScratchWorktree, "__enter__", ...)` to
      raise `WorktreeCreationError(Path("/tmp/fake"), "boom")`, invoke
      `CliRunner().invoke(app, ["review", "pr", "83"])` against the `patched_host`
      fixture (armed via `_arm`), and assert `result.exit_code == 1` and
      `result.exception is None or isinstance(result.exception, SystemExit)` — the
      same "not an unhandled traceback" assertion the existing test uses. Also
      assert the printed stderr/output contains the error message text (`"boom"`).
- [ ] Run: `pytest tests/cli/test_review_pr.py -k worktree -x`.

### Task D.8 — Commit Part D

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] Run the full existing `tests/codehost/test_worktree.py` suite (not just the
      new tests) and confirm it still passes unchanged (Integration Requirements).
- [ ] `git add` and commit Part D's changes.
      Suggested message: `fix: serialize git worktree metadata calls and render WorktreeError as a panel`.

---

## Part E — Load test: repeated rounds (acceptance test)

### Task E.1 — Turn the single-round load test into `ROUNDS` rounds

- [ ] Effort: 2/5
- [ ] In
      [tests/load/test_worktree_concurrency.py](tests/load/test_worktree_concurrency.py),
      change `test_concurrent_worktree_creation_succeeds_with_non_colliding_paths`
      to repeat its existing 8-concurrent-creation body `ROUNDS` times within the
      one test function, each round using a fresh `worktrees_root` subdirectory
      (or otherwise ensuring rounds don't collide with each other's paths).
- [ ] Pick `ROUNDS` from Task A.1's measured pre-fix failure rate so the test would
      have caught the original bug with high probability (design's own worked
      example: a rate of 1-in-20 per round needs ~60 rounds for ~95% pre-fix
      failure probability — recompute for **your** measured rate, don't reuse that
      example's numbers unless your measurement happens to match it).
- [ ] Keep the test's added runtime to a few seconds — `tests/load/` runs on every
      invocation. If your `ROUNDS` value (real git subprocesses × 8 concurrent ×
      `ROUNDS`) would exceed that, raise per-round `concurrency` instead of
      `ROUNDS` (the design explicitly allows this trade — record which one you
      chose and why).
- [ ] Record the chosen `ROUNDS` (and/or `concurrency`) value and the reasoning
      behind it in the test's own docstring, per the design's Development Approach
      step 5 — a future reader must be able to see why this number, not just what
      it is.

### Task E.2 — Run the full load-test acceptance pass

- [ ] Effort: 1/5
- [ ] Run: `uv run pytest -q tests/load/test_worktree_concurrency.py`. All pass.
- [ ] Repeat Task A.1's 50-iteration loop against the now-fixed code (Verification
      Walkthrough step 4). Confirm zero failures across the loop.

### Task E.3 — Commit Part E

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] `git add` and commit Part E's changes.
      Suggested message: `test: repeat worktree concurrency load test across measured rounds`.

---

## Part F — Documentation

### Task F.1 — Update `worktree.py`'s module docstring

- [ ] Effort: 1/5
- [ ] In [src/squadron/codehost/worktree.py](src/squadron/codehost/worktree.py),
      update the module docstring (currently lines 1–11) to mention the new
      cross-process metadata lock this module now takes around its four git
      worktree-metadata calls, that it lives in `metadata_lock.py` (not here, to
      avoid growing this already-over-guideline-length file further), and the
      POSIX-only limitation (D5) — a future reader hitting a `MetadataLockError` on
      Windows should be able to find the explanation starting from this docstring.

### Task F.2 — Commit Part F

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] `git add` and commit Part F's changes.
      Suggested message: `docs: describe the metadata lock in worktree.py's module docstring`.

---

## Part G — Full verification

### Task G.1 — Confirm CI actually gates the load test tier

Per `.claude/rules/testing.md` / `.claude/rules/python.md`: "CI must gate load
tests for slices touching these paths" — this slice's concurrency fix is exactly
that path, so confirm it explicitly rather than assuming `pytest` in CI already
covers it.

- [ ] Effort: 1/5
- [ ] Read [.github/workflows/ci.yml](.github/workflows/ci.yml)'s `test` job. Confirm
      its `uv run pytest` step (currently the last step of that job) has no `-m`
      marker deselect and no path argument that would exclude `tests/load/` —
      `[tool.pytest.ini_options]` in `pyproject.toml` sets `testpaths = ["tests"]`
      with no load-excluding marker defined, so a bare `pytest` invocation already
      collects `tests/load/test_worktree_concurrency.py`.
- [ ] State the outcome explicitly in this checklist item (do not just check the
      box): either "confirmed — CI's `test` job runs `tests/load/` unfiltered on
      every push/PR to `main`, no change needed" or, if you find a marker/path
      exclusion that skips it, fix `.github/workflows/ci.yml` so the load tier is
      gated and note that fix here.
- [ ] This is a one-time confirmation for this slice's new/changed load-test
      content (Task E.1's `ROUNDS` change) — it does not require a new CI job.

### Task G.2 — Full suite, lint, typecheck

- [ ] Effort: 1/5
- [ ] From the squadron repo root: `ruff format && ruff check && pyright`. Zero
      pyright errors — merge blocker per project rules.
- [ ] Confirm `fcntl` is imported only inside `git_metadata_lock` — grep for
      `import fcntl` across `src/` and confirm the only hit is inside that
      function body (Technical Requirements).
- [ ] Run the full test suite: `pytest`. All green.

### Task G.3 — Manual verification walkthrough

- [ ] Effort: 2/5
- [ ] Follow the design's Verification Walkthrough steps 3 and 5 exactly (design
      doc, "Verification Walkthrough"):
      - **Step 3 (loud timeout)**: hold the lock from a second shell (the design
        gives the exact `python -` snippet), then run `sq review pr <number>
        --model opus` against a real PR with the timeout left at its default.
        Confirm it fails after ~60s with a `WorktreeCreationError` error panel
        naming `~/.config/squadron/worktrees/.git-metadata.flock`, not a hang and
        not a traceback. Kill the holder, rerun, confirm the review proceeds.
      - **Step 5 (real parallel use)**: in one repo, start two `sq review pr` runs
        against different PRs at the same moment (two terminals). Both reach the
        review phase; neither reports a `commondir` error.
- [ ] Note any deviation from the design's expected output as a finding, not a
      silent adjustment — if something doesn't match, stop and report before
      proceeding.

### Task G.4 — Confirm everything landed

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] `git status` — working tree clean (Parts A–F already committed per-part;
      nothing outstanding except this task file's own completion-marking edits
      below).
- [ ] `git log --oneline` over this slice's commits reads as one coherent story
      (failing proof → lock module → wiring + CLI fix → acceptance rounds → docs)
      — this closes issue #133.

---

## Completion

- [ ] Mark this task file's `status:` as `complete` in frontmatter once all parts
      are done (or delegate to `task-checker`).
- [ ] Mark the slice design's `status:` as `complete` in
      [929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md](project-documents/user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md)
      frontmatter.
- [ ] Update the slice plan entry
      (`900-slices.maintenance-and-refactoring.md`, entry 27 / index 929,
      line ~459) checkbox to `[x]`.
- [ ] Write a DEVLOG entry per `prompt.ai-project.system.md`, Session State Summary
      guidance, dated the actual completion date, noting the slice closed issue
      #133, the measured pre-fix failure rate (Task A.1), and the chosen `ROUNDS`
      value (Task E.1) with its reasoning.
