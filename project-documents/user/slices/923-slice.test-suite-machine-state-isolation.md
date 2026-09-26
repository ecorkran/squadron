---
docType: slice-design
slice: test-suite-machine-state-isolation
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [914]
dateCreated: 20260926
dateUpdated: 20260926
status: not_started
---

# Slice Design: Test Suite Machine-State Isolation

## Overview

Fixes [issue #47](https://github.com/ecorkran/squadron/issues/47). Right now some tests pass only because they pick up state from the developer's machine. Eight instances have been found so far, and each was fixed alone after CI went red:

| # | Leaked state | Where it was found |
|---|---|---|
| 1 | user config `review.max_file_size_bytes` | #39 |
| 2 | `shutil.which("cf")` on host `PATH` | `test_doctor.py` |
| 3 | terminal width (Rich wraps a path mid-token) | `test_preemption_cli.py` |
| 4 | live `cf config get git.integration_branch` | #32, `test_git_utils.py` |
| 5 | `refs/squadron/pr/origin/83/*` left by a past live run | 24 tests, `a4d358fe` |
| 6 | hardcoded epoch that was only correct in Mountain Time | `test_worktree.py`, `21b78861` |
| 7 | bare `git init`, which assumes `init.defaultBranch=main` | `test_review_pr_worktree.py`, `21b78861` |
| 8 | terminal width again | `test_review_pr.py`, `43416df7` |

Eight cases of one class make the argument for fixing the class. This slice makes the test process's environment something the suite sets up itself, not something it inherits. It also adds a repeatable hostile run that proves the isolation holds.

Measuring for this design found three leaks that are live now but have not bitten yet. The design covers all three:

- **Import-time home paths.** 25 module-level constants in `src/` evaluate `Path.home()` at import, for example `pipeline/state.py:_DEFAULT_RUNS_DIR`, `review/templates:USER_TEMPLATES_DIR`, and `skills/manifest.py:USER_MANIFEST`. A per-test `HOME` monkeypatch cannot reach them, because they are fixed before any fixture runs. So the plan's premise that "`HOME` is the lever" holds only for paths computed at call time.
- **Real API keys in the test process.** `squadron/cli/app.py:41` runs `load_dotenv(Path.cwd() / ".env")` at import, and the repo root has a `.env` with `OPENROUTER_API_KEY`, `GEMINI_API_KEY`, and `OPENAI_API_KEY`. So once test collection imports the CLI, every test runs with the developer's real provider keys. CI has no `.env`. Any test that assumes a key is absent behaves differently on a developer machine, and a test that slips past a mock would spend real money.
- **`CLAUDECODE=1`.** This variable is set whenever an agent runs the suite, and `cli/commands/run.py:150` branches on it. Agent-run suites therefore take a code path that CI never takes.

## Value

- **A local green run becomes evidence again.** A test that passes here passes in CI and on a contributor's machine, because the environment it sees is the same everywhere.
- **Latent host-dependent tests fail everywhere, right away.** The pinned values (a non-`main` default branch, a non-UTC timezone) are chosen to make hidden assumptions fail on every machine, not only on the one that lacks them.
- **The whole class is closed, not one more instance.** New tests get isolation without opting in, and the hostile CI job catches the next kind of leak.
- **Unblocks 914.** 914 types the conftest fixtures once, after this slice has finished moving them.

## Technical Scope

**Included**

- Part A: root-level isolation of home paths (both import time and call time), git global/system config, `TZ`, `COLUMNS` and color variables, and a scrub of the credential and squadron env vars. Per-directory fixtures made redundant by this are consolidated.
- Part B: an explicit opt-out marker for the few tests that must use the host's `cf` registry, and the sweep for tests that run git or `cf` against the project checkout.
- Part C: a hostile-environment script, a negative-control run of it against the pre-slice commit, and a CI job that runs it on every push.

**Excluded**

- Product-code changes. `load_dotenv` at CLI import is intended product behavior; the tests neutralize its effect and do not change it.
- `_pinned_diff_base` in `tests/review/conftest.py`. It pins `cf`'s *project* config, which is read from the checkout, not from `HOME`. It stays where it is.
- Cross-test isolation beyond what already exists. The session-level fake home is shared by all tests in a process. It keeps the machine out; it does not keep tests apart from each other. Existing per-test fixtures that give per-test separation stay.
- Typing the fixtures. That is 914's job.

## Dependencies

### Prerequisites

- None. git ≥ 2.32 is required for `GIT_CONFIG_GLOBAL`; local is 2.50.1, and the CI runners are newer than 2.32.

### Interfaces Required

- `squadron.providers.profiles` built-in profiles (`api_key_env`) and the `OPENAI_API_KEY` fallback in `providers/auth.py`. The credential scrub list is derived from these, not written out by hand (D6).
- The `sq config get` command. The hostile script uses it to prove that its hostile config is actually loaded (D9).

## Architecture

### Component Structure

| Component | Location | Role |
|---|---|---|
| `_hermetic` module | `tests/_hermetic.py` (new) | Defines each pinned value exactly once. Builds the session fake home and git config. Holds the env-scrub logic. |
| Root conftest | `tests/conftest.py` | Imports `_hermetic` before any `squadron` import. Adds the per-test autouse fixture, the session-start guard, and the `host_cf` opt-out. |
| Review conftest | `tests/review/conftest.py` | Loses the two call-time isolation fixtures that are now redundant. |
| Metrology conftest | `tests/metrology/conftest.py` | `isolated_user_config` stays opt-in and returns the per-test home's config path. |
| Hostile script | `scripts/test-hostile-env` (new) | Clean clone plus hostile machine state, then runs pytest. |
| CI job | `.github/workflows/ci.yml` | New `hermetic` job that runs the script. |

### Data Flow

How a test process gets its environment:

```
pytest starts
  └─ imports tests/conftest.py
       └─ first statement: import tests._hermetic
            ├─ capture REAL_HOME (needed only by the host_cf opt-out)
            ├─ mkdtemp → SESSION_HOME; os.environ["HOME"] = SESSION_HOME
            ├─ write SESSION_HOME/.gitconfig-hermetic; set GIT_CONFIG_GLOBAL, GIT_CONFIG_NOSYSTEM=1
            ├─ os.environ["TZ"] = PINNED_TZ; time.tzset()
            └─ os.environ["COLUMNS"] = PINNED_COLUMNS; drop FORCE_COLOR / NO_COLOR
       └─ then: from squadron... imports   ← import-time Path.home() now resolves under SESSION_HOME
  └─ collection imports test modules      ← cli.app's load_dotenv runs here and pulls in real keys
  └─ session-start guard                   ← fails if an import-time constant escaped SESSION_HOME
  └─ per test (autouse):
       ├─ monkeypatch HOME → tmp_path/"home"   ← call-time Path.home() gets a per-test home
       ├─ delenv: credential vars, ORCH_*, SQUADRON_*, CLAUDECODE, GH_CONFIG_DIR
       └─ if marked host_cf: set HOME back to REAL_HOME instead
```

The two layers are deliberate. Import-time constants can only be redirected before import, so they go to one shared session home. Call-time lookups get a fresh per-test home. Neither layer ever resolves to the developer's real home.

### State Management

- `SESSION_HOME` is created with `tempfile.mkdtemp` (pytest's `tmp_path_factory` does not exist yet at conftest import) and removed in `pytest_unconfigure`.
- All env changes made per test go through `monkeypatch`, so they are undone after each test. The process-wide values set at import are never restored during the run; they *are* the suite's environment.

## Technical Decisions

### D1 — Two-layer HOME redirection, guarded

The session layer is `os.environ["HOME"]`, set in `tests/_hermetic.py`, which `tests/conftest.py` imports as its first statement, before any `squadron` import. The per-test layer is an autouse fixture that sets `HOME` to `tmp_path / "home"` through `monkeypatch`.

The guard is a session-scoped autouse fixture that asserts `squadron.pipeline.state._DEFAULT_RUNS_DIR` is under `SESSION_HOME`. That constant is import-time and is imported by most suites. If an import-order change ever lets `squadron` load first, the suite fails at session start instead of quietly leaking again.

Rejected alternative: patching each of the 25 constants. It repeats their definitions in the tests, and the 26th constant would be missed.

### D2 — `host_cf` marker: the only way back to the real home

Tests that run the real `cf` and need its project registry (`~/.config/context-forge/projects.json`, verified) are marked `@pytest.mark.host_cf`. For those tests the per-test fixture sets `HOME` to `REAL_HOME` instead of a temp home. The marker is registered in `pyproject.toml` next to `network`.

Membership starts from the four files known to depend on this (`test_schema_drift.py`, `test_pr_review_frontmatter.py`, `test_cf_contract_live.py`, `test_cli_review.py`). It is then confirmed test by test from the Part C run: a test gets the marker only if it fails under isolation *because* it needs cf's registry. The marker is not a place to park any failing test. The script prints the marked count so that growth is visible.

### D3 — Git config pinned, host config removed

`GIT_CONFIG_GLOBAL` points to a session file that `_hermetic` writes. `GIT_CONFIG_NOSYSTEM=1` removes the system file; Apple git ships one with `credential.helper=osxkeychain`. The pinned file sets:

- `init.defaultBranch = hermetic-default`. This is deliberately *not* `main`, so a fixture that runs bare `git init` and then assumes `main` fails on every machine, not only on hosts whose default differs (instance 7). Fix any fixture this exposes by passing `-b main` explicitly, the form most fixtures already use.
- `user.name` and `user.email`, so fixture commits never need host identity.
- `commit.gpgsign = false` and `tag.gpgsign = false`. A signing host would otherwise prompt or fail inside fixtures.

### D4 — `TZ` pinned to a non-UTC, non-DST zone

`TZ = "Asia/Kolkata"` (UTC+05:30, no DST), applied with `time.tzset()` at `_hermetic` import. The zone is non-UTC so that a test which quietly assumes UTC fails everywhere, and not the developer's zone so that instance 6's shape fails everywhere too. The half-hour offset also catches arithmetic that rounds offsets to whole hours. Tests that deliberately exercise other zones keep using `monkeypatch.setenv("TZ", ...)` plus `tzset`, as `test_worktree.py` was verified.

### D5 — `COLUMNS` pinned to 80; color variables dropped

This settles #47's open question. With instance 8, a global pin is justified.

`COLUMNS = "80"` is Rich's width for a non-terminal. That is the width the CI failures showed, so a local run wraps where CI wraps. Because every environment now wraps the same way, a width-sensitive assertion fails locally as well as in CI.

`FORCE_COLOR` and `NO_COLOR` are removed, because a host that sets `FORCE_COLOR` puts ANSI codes into every `CliRunner` capture. Tests that force a terminal (`test_verbosity.py` builds `Console(force_terminal=True, width=120)`) are unaffected, since their explicit arguments win. The existing unwrap helpers stay.

### D6 — Per-test env scrub, list derived from its sources

The per-test fixture runs `delenv(..., raising=False)` on:

- **credential vars:** every `api_key_env` among the built-in provider profiles, plus the auth fallback `OPENAI_API_KEY`. The list is computed from `squadron.providers.profiles` when the fixture runs, so a new provider is covered without editing tests. It is not a hand-written list.
- **every var with prefix `ORCH_`** (the `Settings` env prefix) **or `SQUADRON_`** (`SQUADRON_APP_NAME`, `SQUADRON_NO_INTERACTIVE`).
- **`CLAUDECODE`** and **`GH_CONFIG_DIR`**. With `GH_CONFIG_DIR` gone, `codehost/github_config.py` falls back to its import-time default, which is under `SESSION_HOME`.

The scrub has to run per test rather than once at import. `load_dotenv` runs during collection, after `_hermetic` has already run, and puts the `.env` keys back. Tests that need a variable set it with `monkeypatch.setenv`. Autouse fixtures run before the test body, so the explicit value wins.

### D7 — Consolidate per-directory fixtures

Delete a per-directory fixture only when D1 fully covers what it guarded:

- **Delete** `_isolated_user_config` and `_isolated_model_registry` from `tests/review/conftest.py`. `user_config_path()` and `models_toml_path()` resolve `Path.home()` at call time, so the per-test home covers both.
- **Keep** `_isolated_user_templates`. `USER_TEMPLATES_DIR` is an import-time constant, so it resolves to the *shared* session home, and this fixture keeps review tests from seeing each other's template writes.
- **Keep** `_pinned_diff_base` (out of scope; see Technical Scope), the root `patch_config_paths` (it also redirects *project* config), and `isolate_review_debug_log` (per-test separation).
- **Metrology** `isolated_user_config` stays opt-in (the plan's requirement: some tests need the path returned). It now creates and returns `Path.home() / ".config/squadron/config.toml` under the per-test home and no longer patches `user_config_path`.

### D8 — Part B: host probes are proven by running, not by reading

Static audit, measured: all five `shutil.which` caller files (`test_doctor.py`, `test_doctor_checks.py`, `test_setup.py`, `test_setup_install.py`, `test_resolver.py`) already patch it, and none call it bare. #47's fixes landed. The only bare call is `test_frontmatter_gate.py:415`, the deliberate real-`cf` test, which falls under D2. `pr_create_support.py` runs git only in a fixture repo.

Reading the code again would not add evidence. The hostile run (D9) shows it directly: its `PATH` leaves out `cf`, `codex`, `claude`, and `npm`, and its clone has no `refs/squadron/**`. Any test that still depends on a host binary or on checkout refs fails there. Fix each one where it surfaces, by stubbing presence or absence or by moving it onto a fixture repo, or give it the `host_cf` marker if it meets D2.

### D9 — Hostile-environment script

`scripts/test-hostile-env [ref]` (bash, default `HEAD`):

1. `git clone --no-local` of the current repo into a temp dir, then `checkout --detach <ref>`. This gives full history (the history-dependent tests still work) and no `refs/squadron/**`, because clone copies only branches and tags.
2. Build a hostile `HOME`:
   - `.config/squadron/config.toml` with **flat quoted top-level keys**, for example `"review.max_file_size_bytes" = 1`. A nested `[review]` table is rejected with a warning and would test nothing.
   - `models.toml` defining aliases that collide with names the tests use as unknown, for example `llama-3-70b`.
   - a user template override that sets `profile:`.
   - `.gitconfig` with `init.defaultBranch = trunk`, `commit.gpgsign = true`, and `gpg.program = /nonexistent`, so any commit that escapes D3 fails loudly.
3. Write a hostile `.env` into the clone root. Export sentinel credential values, `CLAUDECODE=1`, `FORCE_COLOR=1`, `COLUMNS=20`, and `TZ=Pacific/Chatham` (UTC+12:45).
4. Set `PATH` to the venv's `bin`, then `/usr/bin` and `/bin` only. **Precondition:** `command -v cf` must fail; if `cf` is still visible, stop with an error.
5. **Precondition:** read `review.max_file_size_bytes` back with `sq config get` under the hostile `HOME`. It must return the hostile value; otherwise stop with an error. This check exists so a mis-written probe cannot pass silently.
6. `UV_CACHE_DIR` is resolved from the real home *before* the swap, so `uv sync --frozen` in the clone does not download everything again.
7. Run `pytest -m "not host_cf"`. Print passed, skipped, and failed counts plus the count of deselected `host_cf` tests. Exit non-zero on any failure.

The hostile values are deliberately different from the D3 to D5 pins. The run passes only if the pins override the hostile host every time.

**Negative control.** Run the script once against the parent of this slice's first commit and record the failures in DEVLOG. This is the measurement #47 never finished, and it shows the hostile environment actually bites. No feature flag is needed: the `ref` argument selects the unisolated tree.

### D10 — CI job, not a documented pre-release step

Add a `hermetic` job to `ci.yml` that runs `scripts/test-hostile-env` on one Python version. It runs alongside the existing test job, so wall-clock time stays the same. All eight instances were found only by CI, and a manual pre-release step is exactly the step that gets skipped.

`host_cf` tests are still covered by the main job, which runs `cf init --lite` against the real checkout.

## Implementation Details

### Migration Plan

- **Moved:** user-config and model-registry isolation leave `tests/review/conftest.py`. The root per-test `HOME` replaces them (D7).
- **Reimplemented:** metrology `isolated_user_config`. Its consumers (`repo_with_remote`, `repo_no_remote`, `non_repo_dir`, `second_audited_repo`, and direct users) keep the same fixture name and return type (`Path`).
- **Behavior preserved:** passed and skipped counts must equal the pre-slice baseline recorded in Part A step 1. There are two allowed differences. Tests that were passing by accident and get fixed may change, but the passed count must not fall. `host_cf` tests run in the main job exactly as before.

## Integration Points

### Provides to Other Slices

- **914:** a stable root conftest and `tests/_hermetic.py` to type. 914's fixture-typing work starts after this slice merges.
- **Every future test:** isolation by default. A new test needs no opt-in; only `host_cf` is opt-*out*.

### Consumes from Other Slices

- None. The provider profile registry and `sq config get` already exist.

## Success Criteria

### Functional Requirements

1. With a hostile `~/.config/squadron/config.toml`, `models.toml`, and user templates in the developer's *real* home, the full suite results are unchanged.
2. The session-start guard fails the run if an import-time `Path.home()` constant resolves outside `SESSION_HOME`. To verify, temporarily move the `_hermetic` import below a `squadron` import and see the guard fire.
3. Inside every test, `git config init.defaultBranch` returns `hermetic-default`, `TZ` is `Asia/Kolkata`, `COLUMNS` is `80`, and no credential, `ORCH_*`, `SQUADRON_*`, `CLAUDECODE`, or `GH_CONFIG_DIR` variable is set unless the test set it itself.
4. `scripts/test-hostile-env` passes on the slice's final commit and prints zero failures.
5. The same script, run against the pre-slice parent commit, fails, and the failures are recorded in DEVLOG (the negative control).
6. The `hermetic` CI job is green on the slice branch's push.

### Technical Requirements

1. Each pinned value (`TZ`, `COLUMNS`, default branch name, git identity) is defined once, in `tests/_hermetic.py`.
2. `host_cf` is registered in `pyproject.toml`. Every marked test has a one-line comment naming what it needs from the host.
3. Full suite passed/skipped counts are at or above the Part A baseline. `ruff format`, `ruff check`, and `pyright` report zero errors.
4. `tests/conftest.py` stays under ~300 lines. Env setup lives in `_hermetic`.

### Integration Requirements

1. 914's fixture typing can start: after this slice merges, 914 does not need to move or rename any conftest fixture.

### Verification Walkthrough

These are draft commands; they are refined after Phase 6. `scripts/test-hostile-env` does not exist yet.

1. **Baseline, before any change:**
   ```bash
   uv run pytest -q 2>&1 | tail -1          # record passed/skipped
   ```
2. **Negative control.** Run the hostile script against the pre-slice tree:
   ```bash
   scripts/test-hostile-env <pre-slice-sha>
   # expect: preconditions pass (cf hidden, hostile config readable),
   #         then a non-zero failure count — the leaks, measured
   ```
3. **After Part A and Part B, run the hostile script on the slice tip:**
   ```bash
   scripts/test-hostile-env
   # expect: N passed, M skipped, 0 failed; K deselected (host_cf)
   ```
4. **Real-home hostility.** This proves the developer's own machine cannot leak in:
   ```bash
   cp ~/.config/squadron/config.toml /tmp/cfg.bak
   printf '"review.max_file_size_bytes" = 1\n' >> ~/.config/squadron/config.toml
   uv run pytest -q 2>&1 | tail -1          # same counts as step 3's normal run
   cp /tmp/cfg.bak ~/.config/squadron/config.toml
   ```
5. **Environment inside a test.** `tests/test_hermetic.py` (new) asserts Functional criterion 3 directly. It covers the pins, the scrubbed variables (after setting sentinels in the outer env), a bare `git init` landing on `hermetic-default`, and `host_cf` restoring the real home:
   ```bash
   OPENAI_API_KEY=sentinel CLAUDECODE=1 uv run pytest tests/test_hermetic.py -v
   ```
6. **Guard fires.** Temporarily reorder the imports in `tests/conftest.py` and run: session start fails with the guard's message. Revert.
7. **CI:** push the slice branch and confirm that the `hermetic` and main test jobs are both green.

## Risk Assessment

### Technical Risks

- **Pins expose many failures at once.** The non-`main` default branch and non-UTC `TZ` are *meant* to fail hidden assumptions, and the count is unknown until Part A lands. This is the expected Low-Medium risk the plan names.
- **`host_cf` turns into a dumping ground.** It is the only escape hatch, so the easy fix for a hard failure is to mark the test.

### Mitigation Strategies

- Land the pins before fixing anything, record the failure list, and then fix each failure at its cause (usually by passing `-b main` or deriving the time from its source string).
- D2's membership rule, the one-line justification required on each marked test, and the marked count the script prints.

## Implementation Notes

### Development Approach

1. Record the baseline (walkthrough step 1). Write `scripts/test-hostile-env` first and run the negative control (step 2). This gives the evidence #47 lacks before any fix goes in.
2. Part A: add `tests/_hermetic.py`, the root per-test fixture, and the guard. Run the suite and record what the pins expose.
3. Part B: fix each exposed failure at its cause. Classify real-`cf` dependents under D2 and add the marker.
4. D7 consolidation: delete the redundant review fixtures and reimplement the metrology fixture. Run the suite again.
5. Run the hostile script until it shows zero failures, then add the CI job.

### Special Considerations

- `tempfile.mkdtemp` at import is the one piece of setup that runs outside pytest's fixture system. It has to, because D1's session layer must exist before collection imports `squadron`. Remove it in `pytest_unconfigure`.
- The hostile `.env` and sentinel keys are fake values written into a temp clone. The script never reads or copies the real `.env`.
