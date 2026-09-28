---
docType: tasks
slice: serialize-concurrent-git-worktree-add-on-one-checkout
project: squadron
lld: user/slices/929-slice.serialize-concurrent-git-worktree-add-on-one-checkout.md
parent: user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design complete, not yet reviewed. No code changes yet.
dateCreated: 20260927
dateUpdated: 20260928
status: not_started
---

# Tasks: Serialize Concurrent `git worktree add` on One Checkout (2 of 2)

## Context Summary

Part 2 of two. Part 1
(`929-tasks.serialize-concurrent-git-worktree-add-on-one-checkout-1.md`) must be
complete first: it recorded the pre-fix failure rate (Task A.1, needed by Task
E.1), added the failing no-overlap test (Part B), and created
`src/squadron/codehost/metadata_lock.py` with `git_metadata_lock`,
`MetadataLockError`, and `METADATA_LOCK_TIMEOUT_SECONDS` (Part C). Part 1's
Context Summary lists the design decisions D1–D7 — read it before starting here.

This file wires the lock into the four `git worktree` call sites, fixes
`review_pr.py`'s traceback on `WorktreeError`, extends the load test, updates
docs, runs full verification, and closes the slice (Parts D–G).

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
- [ ] Run: `pytest tests/codehost/test_worktree.py -k lock_timeout -x` — **not** bare
      `-k timeout`, which would also pick up the pre-existing
      `test_submodule_timeout_raises_and_removes_worktree` (a different timeout
      this slice doesn't touch); all four new names above end in `lock_timeout`.

### Task D.5 — Confirm the deterministic no-overlap test now passes

- [ ] Effort: 1/5
- [ ] Run: `pytest tests/codehost/test_worktree.py -k overlap -x`. It must now pass
      — Part B recorded it failing against unwrapped call sites; this confirms the
      wiring in Tasks D.1–D.3 is what fixed it.
- [ ] Temporarily remove the `with git_metadata_lock(...)` around just the `add`
      call (Task D.1) and re-run — confirm the test fails again with a max
      in-flight above 1 (per the design's Verification Walkthrough step 2). Revert
      immediately after checking; do not leave this reverted.

### Task D.6 — Confirm submodule fetches are excluded from the lock

Success Criteria states: "`git submodule update` runs outside the lock. Two
runs' submodule fetches still overlap." Tasks D.1–D.3 only ever wrapped `git
worktree add|remove|prune` — never `_init_submodules`'s `git submodule update`
call — but that scope decision needs its own proof, not just an absence of a
`with git_metadata_lock(...)` line around it that a future edit could add by
accident without any test catching it.

A sleep-and-measure-the-max approach (like Task B.1's fake) would make this
**timing-dependent** in the wrong direction: two threads merely being scheduled
to overlap under a short sleep is a matter of luck, not proof, and the slice's
whole point (D6 in the design) is to stop relying on luck. Use a
`threading.Barrier` instead — it makes "these calls can run concurrently" a
hard pass/fail rather than a probability.

- [ ] Effort: 2/5
- [ ] In `tests/codehost/test_worktree.py`, add a fake `ProcessRunner` (or extend
      Task B.1's, gated so only this test constructs it with the barrier
      installed) whose `("git", "submodule")` branch does the following on every
      call: `barrier.wait(timeout=5.0)` against a `threading.Barrier(N)` shared
      by the test, where `N` is exactly the number of concurrent
      `ScratchWorktree` threads the test spawns. Catch
      `threading.BrokenBarrierError` from `barrier.wait(...)` inside each thread
      and record it (e.g. append to a shared, lock-guarded list) rather than
      letting it propagate — a broken barrier must fail the *test's assertion*,
      not crash a worker thread silently. Return a canned success
      `ProcessResult` after the barrier releases (or after catching the broken-
      barrier error).
- [ ] Add **`test_submodule_fetch_calls_still_overlap_unlike_worktree_metadata_calls`**:
      spawn exactly `N` (e.g. 3) concurrent `ScratchWorktree(...).__enter__()` /
      `.__exit__()` cycles (distinct `run_id`s, one shared `root`/runner), join
      with a bounded timeout, then assert **no thread recorded a
      `BrokenBarrierError`** — i.e., all `N` threads really did reach the
      submodule call at the same time and the barrier released them together.
      This is the deterministic version of "still overlap": if the metadata lock
      ever accidentally grew to cover the submodule call too, the threads could
      only reach the barrier one at a time, `barrier.wait`'s 5s timeout would
      expire before all `N` arrived, and every waiting thread would raise
      `BrokenBarrierError` — a hard failure, not a flaky one.
- [ ] Run against the fully-wired code from Tasks D.1–D.3 (not before) — the
      point is confirming the lock's scope stayed correctly narrow after wiring,
      not proving something that was never at risk.
- [ ] Run: `pytest tests/codehost/test_worktree.py -k "submodule and overlap" -x`
      (both words appear in the test's own name — `-k` accepts this boolean form
      directly).

### Task D.7 — `review_pr.py`: render `WorktreeError` as an error panel

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

### Task D.8 — CLI test: worktree creation failure renders as a panel, not a traceback

- [ ] Effort: 2/5
- [ ] In `tests/cli/test_review_pr.py`, add
      `from squadron.codehost.worktree import ScratchWorktree, WorktreeCreationError`
      to the file's imports (`Path` is already imported at line 12; neither
      `ScratchWorktree` nor `WorktreeCreationError` is imported yet).
- [ ] Add
      **`test_worktree_creation_failure_renders_as_an_error_panel_not_a_traceback`**,
      following the existing pattern
      `test_discussion_fetch_failure_renders_as_an_adapter_error_not_a_traceback`
      (same file): `monkeypatch.setattr(ScratchWorktree, "__enter__", ...)` to
      raise `WorktreeCreationError(Path("/tmp/fake"), "boom")`, invoke
      `CliRunner().invoke(app, ["review", "pr", "83"])` against the `patched_host`
      fixture (armed via `_arm`), and assert `result.exit_code == 1` and
      `result.exception is None or isinstance(result.exception, SystemExit)` — the
      same "not an unhandled traceback" assertion the existing test uses. Also
      assert `"boom"` appears in **`result.stderr`**, not `result.output` —
      `render_code_host_error` writes to `Console(stderr=True)`, and whether
      `result.output` includes stderr content at all is a `CliRunner`
      implementation detail that has changed across Click versions (Click 8.2
      dropped the constructor's `mix_stderr` parameter); `result.stderr` is
      Click's own dedicated accessor for exactly this stream and stays correct
      regardless.
- [ ] Run: `pytest tests/cli/test_review_pr.py -k worktree_creation_failure -x`.

### Task D.9 — Commit Part D

- [ ] Effort: 1/5
- [ ] Confirm current working directory is the squadron project root.
- [ ] Run the full existing `tests/codehost/test_worktree.py` suite (not just the
      new tests) and confirm it still passes unchanged (Integration Requirements).
- [ ] Also run `pytest tests/cli/test_review_pr.py -x` — Task D.8's CLI test lands
      in this same commit and has not been run as part of any prior commit's
      verification step; do not commit Part D on the strength of the codehost
      suite alone.
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
- [ ] Keep the existing `started`/`elapsed` budget assertion **per round**: reset
      `started` at the top of each round and assert `elapsed < GIT_QUERY_TIMEOUT_SECONDS
      * BUDGET_TOLERANCE` at the end of each round. Do not wrap the timer around the
      whole `ROUNDS` loop — the budget was calibrated for one round of 8 creations.
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

Per `.claude/rules/python.md`: "CI must gate load
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
- [ ] **If and only if** you changed `.github/workflows/ci.yml`: `git add
      .github/workflows/ci.yml` and commit it now, before moving to Task G.2 —
      do not carry a CI-file change forward uncommitted into the rest of Part G.
      Suggested message: `chore: gate the worktree-concurrency load test in CI`.
      If nothing needed changing, there is nothing to commit for this task.

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

- [ ] Mark `status:` as `complete` in the frontmatter of both task files (`-1` and
      `-2`) once all parts are done (or delegate to `task-checker`).
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
- [ ] Commit the four edits above together, from the squadron project root, as
      one final commit **before** this branch merges into the target — none of
      Parts A–G's commits touch this task file's own frontmatter, the slice
      design's frontmatter, the slice plan checkbox, or DEVLOG.md, so without
      this step they would merge as uncommitted or get silently folded into
      whatever commit happens next.
      Suggested message: `docs: close slice 929 — serialize concurrent git worktree add`.
