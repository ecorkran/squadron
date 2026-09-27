---
docType: tasks
slice: test-suite-machine-state-isolation
project: squadron
lldReference: project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
projectState: Design complete and reviewed (verdict CONCERNS, resolved). No code changes yet.
status: not_started
dateCreated: 20260926
dateUpdated: 20260926
---

# Tasks: Test Suite Machine-State Isolation

## Context Summary

Fixes [issue #47](https://github.com/ecorkran/squadron/issues/47): eight known
instances of tests that pass only because they inherit the developer's
machine (user config, host `PATH`, terminal width, live `cf config`, leftover
git refs, a timezone-only-correct epoch, an assumed git default branch).
Measuring for the design also turned up three live-but-not-yet-biting leaks,
which this slice fixes in `src/` per explicit instruction: 19 module-level
`Path.home()` calls at import time, `load_dotenv` at import in
`cli/app.py`, and `CLAUDECODE=1` branching that only needs test-side
isolation.

Full rationale is in the design
([923-slice.test-suite-machine-state-isolation.md](project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md))
— read D1–D10 before implementing. In particular:

- **D1**: 19 import-time `Path.home()` constants become call-time functions.
  Exact site list is in the design's D1 section. A new
  `tests/test_import_purity.py` AST-scans `src/` and fails on any future
  module-level `Path.home()` or `load_dotenv` call.
- **D2**: `host_cf` is the *only* opt-out back to the real `$HOME`.
  Membership starts from four named files and must be confirmed empirically
  (a test earns the marker only if it fails under isolation because it needs
  cf's real project registry) — do not add it preemptively.
- **D3–D5**: git config, `TZ`, `COLUMNS`/color vars are each pinned once in
  a new `tests/_hermetic.py`, to values chosen so hidden host assumptions
  fail everywhere, not just on one machine.
- **D6**: `.env` loading moves from module import into the CLI's root
  callback; per-test scrub of credential/`ORCH_*`/`SQUADRON_*`/`CLAUDECODE`/
  `GH_CONFIG_DIR` vars, with the credential list derived live from
  `squadron.providers.profiles`.
- **D8**: measured — all five `shutil.which` callers already stub it; only
  `test_frontmatter_gate.py:415` calls it bare, and that one is the D2
  real-`cf` case, not a new fix.
- **D9/D10**: `scripts/test-hostile-env` proves isolation by running a
  hostile clone through the suite, including a negative control against the
  pre-slice commit. A new `hermetic` CI job runs it with a `timeout-minutes`
  bound.

**Current project state:** design complete, reviewed, and responded to
(verdict CONCERNS, both accepted findings resolved in the design). No code
changes exist yet. Effort for the whole slice: 4/5 per the design (raised
from 3/5 when the `src/` scope was added).

**Dependencies:** none. This slice unblocks 914 (which types the conftest
fixtures this slice creates/moves) — 914's Phase 5 stays blocked until this
slice merges.

**Next planned slice:** 914 (test suite type coverage), resumed after this
merges.

---

## Part A — Baseline and negative control

### Task A.1 — Record the pre-change baseline

- [ ] Effort: 1/5
- [ ] Run `uv run pytest -q 2>&1 | tail -1` on the current tree (before any
      change in this slice) and record the passed/skipped/failed counts.
- [ ] Write the counts into a scratch note (not committed) — later tasks in
      this file compare against this baseline per the design's Behavior
      Preserved requirement: passed/skipped counts must not fall, only rise
      via accidental-pass fixes.

### Task A.2 — Write `scripts/test-hostile-env`

- [ ] Effort: 4/5
- [ ] Create `scripts/test-hostile-env`, a bash script per design D9,
      taking an optional `ref` argument (default `HEAD`):
      1. `set -euo pipefail`.
      2. `git clone --no-local` the repo into a fresh temp dir, then
         `git checkout --detach <ref>`.
      3. Build a hostile `HOME` under the temp dir:
         - `.config/squadron/config.toml` with flat quoted top-level keys,
           e.g. `"review.max_file_size_bytes" = 1`.
         - `models.toml` defining an alias that collides with a name tests
           treat as unknown, e.g. `llama-3-70b`.
         - a user template override setting `profile:`.
         - `.gitconfig` with `init.defaultBranch = trunk`,
           `commit.gpgsign = true`, `gpg.program = /nonexistent`.
      4. Write a hostile `.env` into the clone root: sentinel credential
         values, `CLAUDECODE=1`, `FORCE_COLOR=1`, `COLUMNS=20`,
         `TZ=Pacific/Chatham`.
      5. Resolve `UV_CACHE_DIR` from the real home **before** swapping
         `HOME`, so `uv sync --frozen` reuses the cache.
      6. Set `PATH` to the venv `bin`, then `/usr/bin` and `/bin` only.
      7. **Precondition:** `command -v cf` must fail; if it succeeds, print
         a labeled `hostile-env: cf-still-visible failed` line to stderr
         and exit non-zero.
      8. **Precondition:** run `sq config get review.max_file_size_bytes`
         under the hostile `HOME`; it must equal the hostile value (`1`);
         otherwise print `hostile-env: hostile-config-probe failed` and
         exit non-zero.
      9. Run `pytest -m "not host_cf"`. Print passed/skipped/failed counts
         and the deselected `host_cf` count. Exit non-zero on any failure.
- [ ] Every setup step (clone, checkout, `uv sync --frozen`, both
      preconditions) prints a labeled `hostile-env: <step> failed` line on
      stderr before exiting non-zero on failure — per the design's F004
      review fix, no step may fail silently into a half-built tree.
- [ ] Script is executable (`chmod +x`) and has no dependency on the
      invoking shell's existing `HOME` or `PATH` beyond what it explicitly
      captures in step 5.

### Task A.3 — Negative control run

- [ ] Effort: 1/5
- [ ] Identify the pre-slice parent commit (the commit immediately before
      Task A.2's commit lands).
- [ ] Run `scripts/test-hostile-env <pre-slice-sha>`.
- [ ] Confirm both preconditions pass (cf hidden, hostile config read back)
      and the run then reports a non-zero failure count — this is the #47
      evidence that was never completed before.
- [ ] Record the exact failure count and a one-line summary of what failed
      in `DEVLOG.md` under a new entry for this slice.
- [ ] Commit `scripts/test-hostile-env` and the DEVLOG entry together.

---

## Part B — `src/` fixes (D1, D6)

### Task B.1 — Convert import-time home paths to call-time functions

- [ ] Effort: 4/5
- [ ] For each of the 19 sites listed in the design's D1 section
      (`cli/commands/doctor_checks.py:32`, `cli/commands/skills.py:23`,
      `cli/commands/summary_instructions.py:25`, `client/http.py:12`,
      `codehost/github_config.py:24`, `events/manifest.py:29`,
      `metrology/store.py:41`, `pipeline/compaction_templates.py:20`,
      `pipeline/emit.py:28`, `pipeline/loader.py:25`,
      `pipeline/state.py:162`, `providers/codex/auth.py:16`,
      `review/parsers.py:122`, `review/review_client.py:547`,
      `review/templates/__init__.py:189`, `server/pid.py:10`,
      `skills/manifest.py:11`, `skills/receipts.py:16`,
      `skills/resolver.py:11`), convert the module-level constant into a
      private zero-argument function that resolves `Path.home()` when
      called (e.g. `_DEFAULT_RUNS_DIR` → `_default_runs_dir()`).
- [ ] Where the constant was used as a default parameter value, change the
      parameter to `Path | None = None` and resolve the function call in
      the body instead.
- [ ] Update every in-module and cross-module caller of each renamed
      constant to call the function instead.
- [ ] The resolved path in production is unchanged for all 19 — this is a
      mechanical rename, not a behavior change. Confirm by inspection for
      each site (no test yet — Task B.3 covers verification).
- [ ] Do not touch `_config_dir()`, `models_toml_path()`,
      `worktree.py:102`, or `reviews_dir.py:73` — these already resolve at
      call time per the design.

### Task B.2 — Move `.env` loading into the CLI callback

- [ ] Effort: 2/5
- [ ] In [src/squadron/cli/app.py](src/squadron/cli/app.py), remove the
      module-level `load_dotenv(dotenv_path=Path.cwd() / ".env")` call
      (line 41).
- [ ] Add a `_load_env_file()` function that performs the same
      `load_dotenv` call, and invoke it from the root Typer
      `@app.callback` function body (not at import time).
- [ ] Confirm `sq` still loads `.env` from the current working directory
      when run normally — this is the one behavior this task must not
      change.

### Task B.3 — Retarget the ~44 existing test patch references

- [ ] Effort: 3/5
- [ ] Search all 13 test files that patch the 19 renamed constants by name
      (per the design's D1 count: ~44 references). For every reference,
      switch the patch target to the new function name (e.g. patch
      `squadron.skills.manifest._user_manifest` instead of
      `squadron.skills.manifest.USER_MANIFEST`). Do **not** drop any patch
      in this task, even one that looks redundant — the per-test home does
      not exist until Task C.3, so a dropped patch here would leak the
      developer's real `HOME` with no isolation net yet to catch it.
- [ ] Run `uv run pytest -q 2>&1 | tail -1` and confirm the suite is still
      green (same or better than Task A.1's baseline) before moving on.
- [ ] Commit Tasks B.1–B.3 together (`src/` changes and their direct test
      patch retargets land as one buildable checkpoint).

### Task B.4 — Add the import-purity guard

- [ ] Effort: 3/5
- [ ] Create `tests/test_import_purity.py`. Walk the AST of every module
      under `src/squadron/` and fail if any module-level statement (top-level
      statements, class bodies, or default argument values — not function
      bodies) calls `Path.home()` or `load_dotenv`.
- [ ] Run it against the current tree post-B.1/B.2; it must pass with zero
      violations.
- [ ] Add one deliberately-broken fixture module (or an inline AST sample
      built in the test itself) asserting the scanner actually flags a
      module-level `Path.home()` call — the guard must be shown to fail
      before it's trusted to pass.
- [ ] Run the design's walkthrough step 3 import-cleanliness check
      directly, not just via the AST guard: `uv run python -c "import
      squadron.cli.app, os; print('OPENROUTER_API_KEY' in os.environ)"`
      with the shell not exporting that var, and confirm it prints
      `False`. The AST guard only catches a literal module-level
      `Path.home()`/`load_dotenv` call; this confirms Task B.2's
      `_load_env_file()` isn't itself invoked at import time, which the
      guard cannot detect on its own.
- [ ] Commit as its own checkpoint.

---

## Part C — Root hermetic fixtures (D2–D6)

### Task C.1 — Create `tests/_hermetic.py`

- [ ] Effort: 3/5
- [ ] Create `tests/_hermetic.py` defining, each exactly once:
      - `PINNED_TZ = "Asia/Kolkata"`
      - `PINNED_COLUMNS = "80"`
      - `PINNED_DEFAULT_BRANCH = "hermetic-default"`
      - a function that writes the session git-config file content per D3
        (`init.defaultBranch`, `user.name`, `user.email`,
        `commit.gpgsign = false`, `tag.gpgsign = false`)
      - a function returning the credential env var names to scrub,
        computed live from `squadron.providers.profiles` (`api_key_env`
        fields) plus the `OPENAI_API_KEY` auth fallback — not a hand-typed
        list
      - the real home path, captured once at this module's import (for
        `host_cf` use only)
- [ ] No test yet — this module is pure data/helpers, exercised by
      Task C.3's self-test.

### Task C.2 — Register the `host_cf` marker

- [ ] Effort: 1/5
- [ ] In `pyproject.toml`, register `host_cf` as a pytest marker next to
      the existing `network` marker, with a one-line description matching
      D2 ("test needs cf's real project registry under the host's home").

### Task C.3 — Add the per-test autouse fixture and session git-config fixture

- [ ] Effort: 4/5
- [ ] In `tests/conftest.py`, add:
      - a session-scoped autouse fixture (via `tmp_path_factory`) that
        writes the hermetic git-config file once per session using
        `tests/_hermetic.py`'s writer function;
      - a function-scoped autouse fixture that, via `monkeypatch`:
        - sets `HOME` to a fresh `tmp_path / "home"`, unless the test is
          marked `host_cf`, in which case `HOME` is set to the real home
          captured in `tests/_hermetic.py`;
        - sets `GIT_CONFIG_GLOBAL` to the session git-config file and
          `GIT_CONFIG_NOSYSTEM=1`;
        - sets `TZ` to `PINNED_TZ` and calls `time.tzset()`;
        - sets `COLUMNS` to `PINNED_COLUMNS` and deletes `FORCE_COLOR`,
          `NO_COLOR`;
        - deletes (via `delenv(..., raising=False)`) every credential var
          from `tests/_hermetic.py`'s live-derived list, every var
          prefixed `ORCH_` or `SQUADRON_`, plus `CLAUDECODE` and
          `GH_CONFIG_DIR`;
        - patches `squadron.cli.app._load_env_file` to a no-op.
- [ ] Every pinned value is read from `tests/_hermetic.py` — no value is
      duplicated inline in `conftest.py`.

### Task C.4 — Hermetic self-test

- [ ] Effort: 2/5
- [ ] Create `tests/test_hermetic.py` asserting, for a normal (non-
      `host_cf`) test:
      - `Path.home()` is under the test's `tmp_path`
      - `git config init.defaultBranch` (run via subprocess with the
        test's env) returns `hermetic-default`
      - `TZ` is `Asia/Kolkata` and `COLUMNS` is `80`
      - none of the scrubbed vars are set
- [ ] Add a second test marked `host_cf` asserting `Path.home()` equals the
      real captured home from `tests/_hermetic.py`.
- [ ] Run this file directly with sentinels set in the outer shell env
      (`OPENAI_API_KEY=sentinel CLAUDECODE=1 FORCE_COLOR=1 uv run pytest
      tests/test_hermetic.py -v`) and confirm it still passes — proves the
      fixture overrides the outer environment rather than merely matching
      an already-clean one.
- [ ] Commit Tasks C.1–C.4 together as one checkpoint.

### Task C.5 — One unit test for the real `_load_env_file`

- [ ] Effort: 1/5
- [ ] Add a test (in `tests/cli/` alongside existing app/CLI tests) that
      calls the real `squadron.cli.app._load_env_file()` (not the patched
      no-op) against a temp directory containing a `.env` file, and
      asserts the variable it defines is present in `os.environ`
      afterward. Clean up the env var at the end of the test.
- [ ] This is the only test in the suite that exercises the unpached
      loader — everywhere else the autouse fixture's no-op patch applies.
- [ ] Commit: rides with Task C.1–C.4's checkpoint (same commit, added
      before that commit lands).

---

## Part D — Run the pins, fix what they expose (D7, D8, D2)

### Task D.1 — Run the full suite under isolation and record failures

- [ ] Effort: 2/5
- [ ] Run `uv run pytest -q 2>&1 | tail -1` with Parts A–C's changes in
      place (host `HOME`/config/etc. now unreachable from any non-
      `host_cf` test).
- [ ] Record the full list of newly-failing tests in a scratch note (not
      committed as a permanent doc, but do capture it in the commit
      message or a DEVLOG addendum) — this is the "count is unknown until
      Part A lands" risk called out in the design, now measured.

### Task D.2 — Fix failures caused by the non-`main` default branch

- [ ] Effort: 3/5
- [ ] For every failure from Task D.1 caused by a fixture running bare
      `git init` and then assuming a `main` branch exists, change the
      fixture to the explicit form: `git init -b main`.
- [ ] Do not change `PINNED_DEFAULT_BRANCH` itself to `main` — the pin is
      deliberately hostile per D3; the fix is always on the fixture side.

### Task D.3 — Fix failures caused by `TZ`/timezone assumptions

- [ ] Effort: 2/5
- [ ] For every failure from Task D.1 caused by a hardcoded epoch or
      timestamp that assumed a specific timezone, derive the expected
      value from its source string/data instead of a literal, or have the
      test explicitly `monkeypatch.setenv("TZ", ...)` and call `tzset()`
      if it intentionally exercises a different zone.

### Task D.4 — Fix remaining failures from Task D.1

- [ ] Effort: 3/5
- [ ] Address any remaining failures not covered by Tasks D.2/D.3 (e.g.
      `COLUMNS`-dependent output assertions, leftover credential-var
      assumptions) at their cause, following the same pattern: adjust the
      test to not depend on machine state, or set the state explicitly via
      `monkeypatch` if the test intentionally needs a non-default value.
- [ ] Confirm `uv run pytest -q 2>&1 | tail -1` now shows passed/skipped
      counts at or above Task A.1's baseline, zero unexplained failures.
- [ ] Commit Tasks D.1–D.4 together as one checkpoint.

### Task D.5 — Classify real-`cf` dependents under `host_cf` (D2)

- [ ] Effort: 2/5
- [ ] Starting from the four named files (`test_schema_drift.py`,
      `test_pr_review_frontmatter.py`, `test_cf_contract_live.py`,
      `test_cli_review.py`), run each under isolation. For every test that
      fails specifically because it needs cf's real project registry at
      `~/.config/context-forge/projects.json`, add `@pytest.mark.host_cf`
      with a one-line comment naming what it needs from the host.
- [ ] Do not mark any test `host_cf` that fails for a different reason —
      fix that failure per Task D.4's pattern instead.
- [ ] Confirm no test outside these four files needed the marker; if one
      does, add it here with the same justification comment.
- [ ] Commit: its own checkpoint, separate from D.1–D.4 (marker additions
      are easy to revert independently if a marking judgment turns out
      wrong).

### Task D.6 — Confirm the `shutil.which`/git host-probe sweep (D8)

- [ ] Effort: 1/5
- [ ] Run the five files that call `shutil.which`
      (`tests/cli/test_setup.py`, `tests/cli/test_setup_install.py`,
      `tests/cli/test_doctor.py`, `tests/cli/test_doctor_checks.py`,
      `tests/skills/test_resolver.py`) under isolation and confirm all
      pass — the design measured that each already stubs `shutil.which`.
- [ ] Confirm `tests/events/builtin/test_frontmatter_gate.py:415`'s bare
      call is the one covered by Task D.5's `host_cf` marker on
      `test_frontmatter_gate.py` (or add it there if not already covered).
- [ ] No code change expected in this task — it is a verification step.
      If a failure surfaces, route it to Task D.4 or D.5 as appropriate.
- [ ] Commit: none expected (verification-only); if a fix is needed, it
      commits under whichever of D.4/D.5's checkpoints it was routed to.

### Task D.7 — Consolidate redundant per-directory fixtures, drop redundant patches

- [ ] Effort: 3/5
- [ ] Delete `_isolated_user_config`, `_isolated_model_registry`, and
      `_isolated_user_templates` from `tests/review/conftest.py` — the
      per-test home from Task C.3 now covers all three since Task B.1 made
      their underlying paths call-time.
- [ ] Delete the same duplicated fixtures from `tests/cli/conftest.py`:
      `_isolated_model_registry` (patches
      `squadron.models.aliases.models_toml_path`, ~line 24) and
      `_isolated_user_templates` (patches
      `squadron.review.templates.USER_TEMPLATES_DIR`, ~line 41) — both are
      now redundant with the per-test home for the same reason as their
      `tests/review/conftest.py` copies. Leave `isolate_reviews_dir` (or
      equivalently-named fixture) in that file untouched if it patches the
      repo-relative `REVIEWS_DIR` — that path is not home-derived and the
      per-test home does not cover it.
- [ ] Delete `isolate_review_debug_log` from `tests/conftest.py` for the
      same reason.
- [ ] Keep `_pinned_diff_base` (pins `cf`'s *project* config, read from the
      checkout, not `HOME`) and the root `patch_config_paths` fixture
      unchanged.
- [ ] Reimplement metrology's `isolated_user_config` (stays opt-in) to
      create and return `Path.home() / ".config/squadron/config.toml"`
      under the per-test home, instead of patching `user_config_path`
      directly. Its consumers (`repo_with_remote`, `repo_no_remote`,
      `non_repo_dir`, `second_audited_repo`, and direct users) keep the
      same fixture name and `Path` return type — no consumer call sites
      change.
- [ ] Sweep the ~44 patch references retargeted (not dropped) in Task B.3:
      for each one, if the per-test home now makes the patch redundant
      (i.e. the patch exists only to redirect a path under `HOME` that the
      autouse fixture from Task C.3 already redirects), delete the patch
      entirely. This is the "drop the patch" step B.3 deferred — it is
      only safe now that Task C.3's per-test home exists to catch a test
      that turns out to still depend on the real value.
- [ ] Run `uv run pytest -q 2>&1 | tail -1`; confirm counts unchanged from
      Task D.4's checkpoint.
- [ ] Commit as its own checkpoint.

---

## Part E — Hostile script to green, CI job

### Task E.1 — Get the hostile script to zero failures

- [ ] Effort: 2/5
- [ ] Run `scripts/test-hostile-env` (no `ref`, defaults to current tip).
- [ ] If it reports any failure, route the fix through Task D.4's pattern
      (fix at cause) or Task D.5 (mark `host_cf` if genuinely a real-cf
      dependency) — do not add ad hoc skips.
- [ ] Confirm the run reports zero failures, with passed/skipped counts
      consistent with Task D.7's checkpoint, plus a nonzero deselected
      `host_cf` count matching Task D.5's marked tests.
- [ ] Commit: none expected if the script is already green; if a fix was
      needed, it commits under whichever of D.4/D.5's checkpoints applies,
      same as Task D.6.

### Task E.2 — Real-home hostility walkthrough

- [ ] Effort: 1/5
- [ ] Manually append a hostile key to the real
      `~/.config/squadron/config.toml` (back it up first), run
      `uv run pytest -q 2>&1 | tail -1`, confirm identical counts to a
      clean run, then restore the backup.
- [ ] This is a manual verification step (per the design's Verification
      Walkthrough step 7) — no code changes; record the result in the
      commit message of the next task.

### Task E.3 — Add the `hermetic` CI job

- [ ] Effort: 2/5
- [ ] In `.github/workflows/ci.yml`, add a `hermetic` job that runs
      `scripts/test-hostile-env` on one Python version, alongside the
      existing test job (not blocking it).
- [ ] Set a `timeout-minutes` bound on the job so a hang fails the job
      instead of stalling the workflow.
- [ ] The workflow's current triggers are `push: branches: [main]` and
      `pull_request: branches: [main]` — pushing this slice branch (or
      merging into the project's configured integration branch, which is
      not `main`) fires nothing. The only trigger that runs the new job is
      a pull request targeting `main`. Open a PR from this slice branch
      against `main` (draft is fine; it does not need to merge yet) and
      confirm the `hermetic` job goes green there, alongside the existing
      `test` job.
- [ ] Commit the CI change; this is the slice's final checkpoint.

---

## Part F — Closeout

### Task F.1 — Full verification pass

- [ ] Effort: 1/5
- [ ] Run `ruff format`, `ruff check`, and `pyright` across the repo;
      confirm zero errors from all three (per project-wide gate).
- [ ] Confirm `sq config list` (or a provider auth check) still reads
      `.env` correctly when run from a directory with a temp `.env` —
      re-run the design's Verification Walkthrough step 4.
- [ ] Confirm the suite's passed/skipped counts are at or above Task
      A.1's original baseline.

### Task F.2 — DEVLOG entry and slice closeout

- [ ] Effort: 1/5
- [ ] Write a DEVLOG entry summarizing: the negative-control failure count
      from Task A.3, the number of tests fixed under Part D, the final
      `host_cf` marked-test count, and confirmation the `hermetic` CI job
      is green.
- [ ] Delegate to `task-checker` to mark all checklist items in this file
      complete, and update the slice design's frontmatter `status` to
      `complete`.
- [ ] Update `project-documents/user/architecture/900-slices.maintenance-and-refactoring.md`
      entry 21 to reflect the slice is complete.
