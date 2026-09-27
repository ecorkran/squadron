---
docType: slice-design
slice: test-suite-machine-state-isolation
project: squadron
parent: project-documents/user/architecture/900-slices.maintenance-and-refactoring.md
dependencies: []
interfaces: [914]
dateCreated: 20260926
dateUpdated: 20260926
status: in_progress
---

# Slice Design: Test Suite Machine-State Isolation

## Overview

Fixes [issue #47](https://github.com/ecorkran/squadron/issues/47): tests that pass only because they inherit the developer's machine. Eight instances so far, each patched alone after CI went red:

| # | Leaked state | Where it was found |
|---|---|---|
| 1 | user config `review.max_file_size_bytes` | #39 |
| 2 | `shutil.which("cf")` on host `PATH` | `test_doctor.py` |
| 3 | terminal width (Rich wrapping a path mid-token) | `test_preemption_cli.py` |
| 4 | live `cf config get git.integration_branch` | #32, `test_git_utils.py` |
| 5 | `refs/squadron/pr/origin/83/*` left by a past live run | 24 tests, `a4d358fe` |
| 6 | hardcoded epoch correct only in Mountain Time | `test_worktree.py`, `21b78861` |
| 7 | bare `git init` assuming `init.defaultBranch=main` | `test_review_pr_worktree.py`, `21b78861` |
| 8 | terminal width again | `test_review_pr.py`, `43416df7` |

Eight instances of one class are the case for fixing the class. This slice makes the test process's environment something the suite sets up itself, not something it inherits, and adds a repeatable hostile run to prove it.

Measuring for this design turned up three more leaks. They are live now but have not bitten yet, and this slice fixes all three:

- **Import-time home paths.** 19 module-level constants in `src/` evaluate `Path.home()` at import, for example `pipeline/state.py:_DEFAULT_RUNS_DIR`, `review/templates:USER_TEMPLATES_DIR` and `skills/manifest.py:USER_MANIFEST`. The list was measured with an AST scan of module-level code. These values are fixed before any fixture runs, so a per-test `HOME` cannot reach them. The fix is in `src/` (D1): make them call-time lookups.
- **Real API keys in the test process.** `squadron/cli/app.py:41` runs `load_dotenv(Path.cwd() / ".env")` at module import. The repo root has a `.env` carrying `OPENROUTER_API_KEY`, `GEMINI_API_KEY` and `OPENAI_API_KEY`, so once collection imports the CLI, every test has the developer's real provider keys. CI has no `.env`. A test that assumes a key is absent behaves differently here, and a test that slips a mock would spend real money. The fix is in `src/` plus one test seam (D6).
- **`CLAUDECODE=1`.** It is set whenever an agent runs the suite, and `cli/commands/run.py:150` branches on it, so agent-run suites take a path CI never does. The product check is correct: refusing SDK execution inside Claude Code is intended. So the fix is test-side only, a per-test scrub (D6).

## Value

- **A local green run means something again.** A test that passes here passes in CI and on a contributor's machine, because every one of them sees the same environment.
- **Hidden host-dependent tests fail everywhere, right away.** The pinned values (a non-`main` default branch, a non-UTC timezone) are chosen so that hidden assumptions fail on every machine, not only on the one that happens to lack them.
- **Importing squadron no longer reads the home directory or `.env`.** Paths are resolved when used and `.env` is loaded when the CLI runs. This is also correct product behavior for library use and for the MCP server.
- **The class is closed, not the next instance.** New tests get isolation without opting in, and the hostile CI job catches the next kind of leak.
- **Unblocks 914.** 914 types the conftest fixtures once, after this slice has finished moving them.

## Technical Scope

**Included**

- **Part A** covers the root-level test isolation:
  - a per-test home
  - git global and system config
  - `TZ`
  - `COLUMNS` and the color variables
  - a scrub of the credential and squadron env vars

  It also includes the two `src/` fixes: call-time home paths (D1) and loading `.env` from the CLI callback instead of at import (D6). Per-directory fixtures made redundant by these are consolidated.
- **Part B** adds the `host_cf` opt-out marker and the sweep for tests that run git or `cf` against the project checkout.
- **Part C** adds the hostile-environment script, its negative control against the pre-slice commit, and a CI job.

**Excluded**

- `_pinned_diff_base` in `tests/review/conftest.py`. It pins `cf`'s *project* config, which is read from the checkout, not from `HOME`. It stays where it is.
- `CLAUDECODE` detection in `run.py`. It is correct product behavior; only the tests are isolated from it.
- Typing the fixtures. That is 914's job.

## Dependencies

### Prerequisites

- None. `GIT_CONFIG_GLOBAL` needs git 2.32 or later; local is 2.50.1, and CI runners are newer than 2.32.

### Interfaces Required

- Built-in provider profiles in `squadron.providers.profiles` (their `api_key_env` fields) and the `OPENAI_API_KEY` fallback in `providers/auth.py`. The credential scrub list is derived from these (D6).
- `sq config get`, which the hostile script uses to prove its hostile config is live (D9).

## Architecture

### Component Structure

| Component | Location | Role |
|---|---|---|
| Home-path functions | the 19 `src/` modules | Each import-time constant becomes a zero-argument function that resolves `Path.home()` when called. |
| `.env` loader | `src/squadron/cli/app.py` | `_load_env_file()` is called from the root `@app.callback`, not at import. |
| Import-purity guard | `tests/test_import_purity.py` (new) | AST scan that fails if module-level code in `src/` calls `Path.home()` or `load_dotenv`. |
| `_hermetic` module | `tests/_hermetic.py` (new) | Each pinned value defined once. Also writes the git config file and holds the scrub logic. |
| Root conftest | `tests/conftest.py` | Per-test autouse isolation fixture, a session fixture that writes the git config, and the `host_cf` opt-out. |
| Hermetic self-test | `tests/test_hermetic.py` (new) | Asserts the environment a test actually sees. |
| Review / metrology conftests | `tests/review/`, `tests/metrology/` | Redundant isolation fixtures deleted or simplified (D7). |
| Hostile script | `scripts/test-hostile-env` (new) | Clean clone plus hostile machine state, then pytest. |
| CI job | `.github/workflows/ci.yml` | New `hermetic` job. |

### Data Flow

How a test gets its environment:

```
session start (autouse, session scope)
  └─ tmp_path_factory → hermetic.gitconfig written once (pinned values from _hermetic)
per test (autouse, function scope, via monkeypatch)
  ├─ HOME            → tmp_path/"home"          ← every Path.home() in src/ is now call-time, so this reaches all of them
  ├─ GIT_CONFIG_GLOBAL → session gitconfig; GIT_CONFIG_NOSYSTEM=1
  ├─ TZ              → PINNED_TZ; time.tzset()
  ├─ COLUMNS         → PINNED_COLUMNS; delenv FORCE_COLOR, NO_COLOR
  ├─ delenv          credential vars, ORCH_*, SQUADRON_*, CLAUDECODE, GH_CONFIG_DIR
  ├─ patch           squadron.cli.app._load_env_file → no-op   ← CliRunner invocations can't read the checkout's .env
  └─ if marked host_cf: HOME → the real home instead
```

Because the `src/` fixes remove every import-time read of the environment, all isolation happens per test through `monkeypatch` and is undone after each one. No setup runs before pytest's fixture system, and no module has to be imported in a particular order.

### State Management

- Per-test state lives in `tmp_path` and is undone by `monkeypatch`.
- Session state is only the git config file, under `tmp_path_factory`.
- The real home path is captured once by `_hermetic` (`Path.home()` at its import). It is used only by the `host_cf` opt-out.

## Technical Decisions

### D1 — Import-time home paths become call-time functions

Each of the 19 constants becomes a private zero-argument function that returns the same path, for example `_DEFAULT_RUNS_DIR` → `_default_runs_dir()`. Callers call it. The path each one resolves to in production is unchanged. Several modules already follow this shape (`_config_dir()`, `models_toml_path()`, `worktree.py:102`, `reviews_dir.py:73`), so the change brings the stragglers into line.

The 19 sites:

- `cli/commands/`: `doctor_checks.py:32`, `skills.py:23`, `summary_instructions.py:25`
- `client/http.py:12`
- `codehost/github_config.py:24`
- `events/manifest.py:29`
- `metrology/store.py:41`
- `pipeline/`: `compaction_templates.py:20`, `emit.py:28`, `loader.py:25`, `state.py:162`
- `providers/codex/auth.py:16`
- `review/`: `parsers.py:122`, `review_client.py:547`, `templates/__init__.py:189`
- `server/pid.py:10`
- `skills/`: `manifest.py:11`, `receipts.py:16`, `resolver.py:11`

Where a constant was a default parameter value, for example `DEFAULT_RECEIPTS_DIR`, the parameter becomes `Path | None = None` and is resolved in the body. A path computed at definition time is the same bug.

**Guard.** `tests/test_import_purity.py` walks the AST of every `src/` module and fails on any `Path.home()` or `load_dotenv` call in module-level code. That covers top-level statements, class bodies and default argument values. The 20th import-time site then fails in review instead of leaking into tests. This replaces the earlier plan of redirecting `HOME` before import, which depended on import order and could guard only one sample constant.

About 44 references across 13 test files currently patch these constants by name. Each either switches to the function or, more often, drops the patch because the per-test home now covers it.

### D2 — `host_cf` marker: the only way back to the real home

Some tests run the real `cf` and need its project registry, which lives at `~/.config/context-forge/projects.json` (verified). They are marked `@pytest.mark.host_cf`, and the per-test fixture sets `HOME` to the real home for them. The marker is registered in `pyproject.toml` next to `network`.

Membership starts from the four files known to depend on this: `test_schema_drift.py`, `test_pr_review_frontmatter.py`, `test_cf_contract_live.py` and `test_cli_review.py`. It is then confirmed test by test in the Part C run: a test gets the marker only if it fails under isolation *because* it needs cf's registry. The marker is not a place to park failing tests. The script prints the marked count so growth is visible.

### D3 — Git config pinned, host config removed

`GIT_CONFIG_GLOBAL` points to the session file. `GIT_CONFIG_NOSYSTEM=1` removes the system file; Apple git ships one with `credential.helper=osxkeychain`. The pinned file sets:

- `init.defaultBranch = hermetic-default`. This is deliberately *not* `main`. A fixture that runs bare `git init` and then assumes `main` now fails on every machine, instead of only where the host's default differs (instance 7). The fix is always the explicit form most fixtures already use: `git init -b main`.
- `user.name` and `user.email`, so fixture commits never need the host's identity.
- `commit.gpgsign = false` and `tag.gpgsign = false`. On a host that signs commits, fixture commits would otherwise prompt or fail.

### D4 — `TZ` pinned to a non-UTC, non-DST zone

`TZ = "Asia/Kolkata"` (UTC+05:30, no DST), followed by `time.tzset()`.

- Not UTC, so a test that silently assumes UTC fails everywhere.
- Not the developer's zone, so instance 6's shape (a literal that only works in one zone) fails everywhere too.
- The half-hour offset also catches arithmetic that assumes whole-hour offsets.

Tests that exercise other zones on purpose keep setting `TZ` themselves with `monkeypatch` and `tzset`; the explicit value wins.

### D5 — `COLUMNS` pinned to 80; color variables removed

This settles #47's open question, and instance 8 is what justifies a global pin.

Rich asks the real terminal for its size (`os.get_terminal_size` on stdin, stdout and stderr, `rich/console.py:1027-1030`) and then lets `COLUMNS` override it (`:1036`). A test run in a wide local terminal renders long paths on one line. CI has no terminal and renders at 80, wrapping the same path mid-token. `COLUMNS = "80"` makes every run wrap where CI wraps.

`FORCE_COLOR` and `NO_COLOR` are removed, since a host with `FORCE_COLOR` set puts ANSI codes into every `CliRunner` capture. Tests that pass an explicit width or `force_terminal` (such as `test_verbosity.py`) are unaffected. The existing unwrap helpers stay.

### D6 — `.env` loaded when the CLI runs; per-test env scrub

**`src/` fix.** `cli/app.py` moves `load_dotenv(dotenv_path=Path.cwd() / ".env")` into `_load_env_file()`, which is called from the root `@app.callback`. Importing `squadron.cli.app` no longer touches the environment. Running `sq` still loads `.env` from the current directory, as today.

**Test seam.** `CliRunner` invocations run the callback with cwd at the repo root, so they would still read the checkout's `.env`. The per-test fixture patches `squadron.cli.app._load_env_file` to a no-op, and one unit test calls the real `_load_env_file()` against a temp `.env`. This is a single named seam, not a mock of dotenv internals.

**Scrub.** The per-test fixture runs `delenv(..., raising=False)` on:
- Credential vars: every `api_key_env` among the built-in provider profiles, plus the auth fallback `OPENAI_API_KEY`. The list is computed from `squadron.providers.profiles` when the fixture runs, not hand-listed, so a new provider is covered without editing tests.
- Every var with the prefix `ORCH_` (the `Settings` env prefix) or `SQUADRON_`.
- `CLAUDECODE` and `GH_CONFIG_DIR`.

Tests that need one of these set it with `monkeypatch.setenv`. Autouse fixtures run before the test body, so the explicit value wins.

### D7 — Consolidate per-directory fixtures

D1 makes every home-derived path call-time, so the per-test home covers them all:

- Delete from `tests/review/conftest.py`:
  - `_isolated_user_config`
  - `_isolated_model_registry`
  - `_isolated_user_templates` (`USER_TEMPLATES_DIR` is no longer import-time)
- Delete from `tests/conftest.py`: `isolate_review_debug_log`, since `_DEBUG_LOG_PATH` becomes call-time and lands in the per-test home.
- Keep `_pinned_diff_base` (see Technical Scope) and the root `patch_config_paths`, which also redirects *project* config.
- Metrology's `isolated_user_config` stays opt-in, as the plan requires, because some tests need the path returned. It now creates and returns `Path.home() / ".config/squadron/config.toml"` under the per-test home instead of patching `user_config_path`.

### D8 — Part B: host probes proven by running the tests, not by reading them

Measured: all five `shutil.which` caller files (`test_doctor.py`, `test_doctor_checks.py`, `test_setup.py`, `test_setup_install.py`, `test_resolver.py`) already patch it, and none call it bare. The only bare call is `test_frontmatter_gate.py:415`, the deliberate real-`cf` test, which falls under D2. `pr_create_support.py` runs git only in a fixture repo.

Rereading the code adds no evidence. The hostile run (D9) proves it directly:
- Its `PATH` leaves out `cf`, `codex`, `claude` and `npm`.
- Its clone has no `refs/squadron/**`.

Anything still depending on either fails there. Fix each failure where it surfaces:
- stub presence or absence of the binary
- move the test onto a fixture repo
- if the test meets D2, mark it `host_cf`

### D9 — Hostile-environment script

`scripts/test-hostile-env [ref]` is a bash script; `ref` defaults to `HEAD`.

1. Run `git clone --no-local` into a temp dir, then `checkout --detach <ref>`. This gives full history, so the history-dependent tests still work, and no `refs/squadron/**`, because clone copies only branches and tags.
2. Build a hostile `HOME`:
   - `.config/squadron/config.toml` with **flat quoted top-level keys**, e.g. `"review.max_file_size_bytes" = 1`. A nested `[review]` table is rejected with a warning and would test nothing.
   - `models.toml` defining aliases that collide with names the tests treat as unknown, e.g. `llama-3-70b`.
   - A user template override that sets `profile:`.
   - `.gitconfig` with `init.defaultBranch = trunk`, `commit.gpgsign = true` and `gpg.program = /nonexistent`, so any commit that escapes D3 fails loudly.
3. Write a hostile `.env` into the clone root. Export sentinel credential values, `CLAUDECODE=1`, `FORCE_COLOR=1`, `COLUMNS=20` and `TZ=Pacific/Chatham` (UTC+12:45).
4. Set `PATH` to the venv `bin`, then `/usr/bin` and `/bin` only. **Precondition:** `command -v cf` must fail. If `cf` is still visible, stop with an error.
5. **Precondition:** run `sq config get review.max_file_size_bytes` under the hostile `HOME`. It must return the hostile value; if not, stop with an error. A mis-written probe cannot pass silently.
6. Resolve `UV_CACHE_DIR` from the real home *before* swapping `HOME`, so `uv sync --frozen` in the clone reuses the cache.
7. Run `pytest -m "not host_cf"`. Print passed, skipped and failed counts plus the deselected `host_cf` count. Exit non-zero on any failure.

The hostile values deliberately differ from the D3 to D5 pins. The run passes only if the pins win every time.

**Failure handling.** The script runs under `set -euo pipefail`. Each setup step (clone, checkout, `uv sync --frozen`, both preconditions) prints a labeled `hostile-env: <step> failed` line on stderr before it exits non-zero. A failed setup can therefore never go on to run pytest against a half-built tree. Its CI log also names the step that failed, which distinguishes it from a test failure. The clone is local (`--no-local` copies objects from disk), so only `uv sync` can touch the network, and only on a cache miss. Hangs are bounded by the CI job's `timeout-minutes` (D10).

**Negative control.** Run the script once against the parent of this slice's first commit and record the failures in DEVLOG. This is the measurement #47 never finished, and it proves the hostile environment actually bites. The `ref` argument selects the unisolated tree, so no feature flag is needed.

### D10 — CI job, not a documented pre-release step

Add a `hermetic` job to `ci.yml` that runs `scripts/test-hostile-env` on one Python version, with a `timeout-minutes` bound so a hang fails the job instead of stalling it. It runs alongside the existing test job, so wall-clock time stays the same. All eight instances were found only by CI, and a manual pre-release step is exactly the step that gets skipped. `host_cf` tests stay covered by the main job, which runs `cf init --lite` against the real checkout.

## Implementation Details

### Migration Plan

- **Moved (`src/`):**
  - 19 import-time path constants become call-time functions, with their in-module and cross-module callers updated (D1).
  - `load_dotenv` moves from module import into the root CLI callback (D6).
  - Production paths and CLI behavior are unchanged.
- **Moved (tests):**
  - Isolation leaves `tests/review/conftest.py` and the root `isolate_review_debug_log`; the per-test home replaces them (D7).
  - About 44 patch references to the old constants, across 13 test files, switch to the function or are deleted.
- **Reimplemented:** metrology `isolated_user_config`. Its consumers (`repo_with_remote`, `repo_no_remote`, `non_repo_dir`, `second_audited_repo`, and direct users) keep the same fixture name and `Path` return type.
- **Behavior preserved:**
  - Passed and skipped counts must equal the baseline recorded before the first change. The only allowed difference is accidental passes that get fixed, and the passed count must not fall.
  - `sq` still loads `.env` from the current directory when run: verified manually with a temp `.env` and `sq config list` or a provider auth check.

## Integration Points

### Provides to Other Slices

- **914** gets a stable root conftest and `tests/_hermetic.py` to type. 914's fixture-typing work starts after this merges.
- **Every future test** gets isolation by default. Only `host_cf` is opt-*out*.
- **Library and MCP-server consumers of squadron:** importing a module no longer reads `HOME` or `.env`.

### Consumes from Other Slices

- None.

## Success Criteria

### Functional Requirements

1. With a hostile `~/.config/squadron/config.toml`, `models.toml` and user templates in the developer's *real* home, the full suite's results are unchanged.
2. No module-level code in `src/` calls `Path.home()` or `load_dotenv`. `tests/test_import_purity.py` enforces this and fails when either is reintroduced.
3. In every test that is not marked `host_cf`, all of the following hold unless the test set them itself:
   - `Path.home()` is a fresh, empty, pytest-owned directory (created beside `tmp_path`, not inside it, so tests that list `tmp_path` never see it).
   - `git config init.defaultBranch` returns `hermetic-default`.
   - `TZ` is `Asia/Kolkata` and `COLUMNS` is `80`.
   - No credential, `ORCH_*`, `SQUADRON_*`, `CLAUDECODE` or `GH_CONFIG_DIR` variable is set.
4. `sq` still loads `.env` from the current directory at runtime.
5. `scripts/test-hostile-env` passes on the slice's final commit with zero failures.
6. The same script against the pre-slice parent commit fails, and the failures are recorded in DEVLOG (negative control).
7. The `hermetic` CI job is green on a pull-request run against `main` —
   the workflow's triggers (`push`/`pull_request` on `main` only) do not
   fire on a plain slice-branch push or on a merge into a non-`main`
   integration branch, so a PR run is the only trigger that produces this
   evidence.

### Technical Requirements

1. Each pinned value (`TZ`, `COLUMNS`, default branch name, git identity) is defined once, in `tests/_hermetic.py`.
2. `host_cf` is registered in `pyproject.toml`, and every marked test carries a one-line comment naming what it needs from the host.
3. Suite passed and skipped counts are at or above the baseline. `ruff format`, `ruff check` and `pyright` report zero errors.

### Integration Requirements

1. After merge, 914 does not need to move or rename any conftest fixture.

### Verification Walkthrough

Verified in Phase 6 (20260926), macOS, git 2.50.1, Python 3.13. Each full run takes about 8 minutes (no xdist).

1. **Baseline, before any change** (at `2f2c5d60`):
   ```bash
   uv run pytest -q 2>&1 | tail -1
   # actual: 4461 passed, 4 skipped
   ```
2. **Negative control.** Hostile script against the pre-slice tree:
   ```bash
   scripts/test-hostile-env 2f2c5d60
   # actual: preconditions pass, then 139 failed, 4124 passed, 8 skipped, 184 errors
   ```
   Caveat found while building the script: the hostile `COLUMNS=20` wraps `sq config get` output and `FORCE_COLOR=1` adds ANSI codes. So the config probe runs with `COLUMNS=1000` and strips escape codes before it reads the value.
3. **Import purity:**
   ```bash
   uv run pytest tests/test_import_purity.py -v     # 12 passed
   env -u OPENROUTER_API_KEY uv run python -c "import squadron.cli.app, os; print('OPENROUTER_API_KEY' in os.environ)"
   # actual: False
   ```
   Run against the pre-slice source, the scanner flags exactly the 19 D1 sites plus `cli/app.py:41` `load_dotenv`.
4. **Runtime `.env` still works.** Compare against a directory without the file:
   ```bash
   cd "$(mktemp -d)" && printf 'OPENROUTER_API_KEY=probe\n' > .env && env -u OPENROUTER_API_KEY sq auth status
   # actual: openrouter │ api_key │ ✓ authenticated
   # same command in an empty temp dir: ✗ not authenticated │ Set OPENROUTER_API_KEY
   ```
5. **Environment inside a test.** Sentinels are set in the outer env:
   ```bash
   OPENAI_API_KEY=sentinel CLAUDECODE=1 FORCE_COLOR=1 TZ=Pacific/Chatham COLUMNS=20 \
     uv run pytest tests/test_hermetic.py -v
   # actual: 7 passed
   ```
   The 7 are: fresh home ×2, git config, TZ/COLUMNS, scrub, credential list, and `host_cf` real home.
6. **Hostile script on the slice tip:**
   ```bash
   scripts/test-hostile-env
   # actual: 4461 passed, 8 skipped, 6 deselected (host_cf), 0 failed
   ```
   It has 4 more skips than a local run because tests that need `cf` on `PATH` skip under the hostile `PATH`.
7. **Real-home hostility.** Change the value with `sq config set`. Appending with `>>` creates a duplicate TOML key when the config already sets it. That makes the file invalid rather than hostile, and pytest then aborts at collection in `test_cf_contract_live.py`, whose module-level live probe reads the host config.
   ```bash
   cp ~/.config/squadron/config.toml /tmp/cfg.bak
   sq config set review.max_file_size_bytes 1
   uv run pytest -q 2>&1 | tail -1          # actual: 4481 passed, 4 skipped (same as clean)
   cp /tmp/cfg.bak ~/.config/squadron/config.toml
   ```
8. **CI:** open a PR from the slice branch against `main` (see Functional criterion 7). The `hermetic` job and the main `test` job must both be green. The job runs `git checkout -B hermetic-under-test` first, because the PR merge commit is on no branch and the script's clone copies only branches and tags.

## Risk Assessment

### Technical Risks

- **The pins expose many failures at once.** The non-`main` default branch and non-UTC `TZ` are *meant* to break hidden assumptions, and the count is unknown until Part A lands.
- **`host_cf` becomes a dumping ground.** It is the only escape hatch, so it is the easy way out of a hard failure.

### Mitigation Strategies

- Land the pins before fixing anything, record the failure list, then fix each at its cause. Usually that means `-b main`, or deriving a time from its source string.
- For `host_cf`: D2's membership rule, the required one-line justification on each marked test, and the marked count the script prints.

## Implementation Notes

### Development Approach

1. Record the baseline (walkthrough step 1). Write `scripts/test-hostile-env` and run the negative control (step 2), so the #47 evidence exists before any fix.
2. **`src/` fixes:** D1 (19 sites plus `test_import_purity.py`) and D6's `_load_env_file`. Update the test patch references in the same commit so the suite stays green.
3. **Part A:** add `tests/_hermetic.py`, the per-test fixture, the session git-config fixture and `tests/test_hermetic.py`. Run the suite and record what the pins expose.
4. **Part B:** fix each exposed failure at its cause, and classify real-`cf` dependents under D2.
5. **D7 consolidation:** delete the redundant fixtures and rerun.
6. Get the hostile script to zero failures, then add the CI job.

### Special Considerations

- The hostile `.env` and sentinel keys are fake values written into a temp clone. The script never reads or copies the real `.env`.
- D1 touches 19 production modules, but each change is a local rename to a function call, with the resolved path unchanged. Step 2 is the part of this slice to review with the most care.
