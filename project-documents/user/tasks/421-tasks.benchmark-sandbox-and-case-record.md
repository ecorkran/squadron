---
docType: tasks
slice: benchmark-sandbox-and-case-record
project: squadron
lld: user/slices/421-slice.benchmark-sandbox-and-case-record.md
dependencies:
- 420
- 177
- 320
projectState: v0.24.23 released, main is the target (git.integration_branch unset).
  Slice 420 implemented. Slice 421 design reviewed, findings addressed.
dateCreated: 20261106
dateUpdated: 20261106
status: not_started
turns: 24
promptTokens: 1234565
cachedTokens: 1145200
cacheWriteTokens: 89331
completionTokens: 24961
durationSeconds: 174.7
costUsd: 0.721843
usageRounds: 1
pricedRounds: 1
usageByModel:
  claude-sonnet-5-5:
    rounds: 1
    costUsd: 0.7218425
    completionTokens: 24961
---

## Context Summary
- Working on slice 421: the shared base for the model benchmark (initiative 420). Design: `user/slices/421-slice.benchmark-sandbox-and-case-record.md`; the design's D-numbers (D1–D12) are cited below instead of repeating them.
- Delivers: `BenchmarkCase`/`CaseSet` records in the 320 metrology store; `HistoryFreeSandbox` extracted from `ReplaySandbox`; `BenchmarkSandbox` with uv environment resolution; `ScrubbedEnvironment` and the auth check; the `BenchmarkAdapter` seam with `PythonBenchmarkAdapter` and its pytest suite runner; `sq benchmark auth-check` and `sq benchmark sandbox`.
- Order follows the design's Development Approach: auth spike first (Tasks 2–9; Tasks 2 and 3 are only what the spike needs: its timeout key and the runner mode that makes the scrub real; a "no" must reach the PM before 422 starts, but it does not block the rest of 421), then the 177 extraction, records, adapter, suite runner, sandbox and CLI.
- Design correction (found in review): `SubprocessRunner.run` merges `env` over `os.environ`, so the design's claim that `env=` alone applies the scrub (Interfaces Required, D7) is wrong; GH_TOKEN and the rest would survive. Task 3 adds a replace-the-environment mode to `ProcessRunner` before anything depends on it.
- Nothing here dispatches a producer, builds a case from history or grades. No `/sq:benchmark` slash command until 422 (design, Technical Scope).
- Tests live in `tests/benchmark/` and `tests/metrology/`. Gates before every commit: `ruff format`, `ruff check`, `pyright` (zero errors), and the touched area's tests. Tests needing network carry the existing `network` marker.
- Load test: the sandbox install is a network and environment path and sandboxes can run concurrently, so Task 26 adds one load test (concurrent sandboxes). Nothing else here is on a concurrency or latency-bounded path; every bounded call has a timeout test.
- Next planned slice: 422.

## Tasks

### Task 1: Create the slice branch
- [x] Run `cf config get git.integration_branch`; the target is its value, or `main` when empty
- [x] `git checkout -b 421-slice.benchmark-sandbox-and-case-record <target>` (or switch to it if it exists)
  - [x] Success: `git branch --show-current` prints the slice branch (uncommitted planning files carry over; the tree need not be clean)

### Task 2: Auth-probe timeout config key (D12)
- [x] In `src/squadron/config/keys.py` add `BENCHMARK_AUTH_PROBE_TIMEOUT_KEY` and a `CONFIG_KEYS` entry `benchmark.auth_probe_timeout_s` (default 120), following `CF_CLI_TIMEOUT_KEY`; read it through `get_positive_int_config` (find how `cf.cli_timeout_s` is read and copy that). The install and suite keys are added with their consumers in Tasks 18 and 22
  - [x] Success: the key resolves to its default when unset and to a set value when set
- [x] Tests (existing config tests, or `tests/benchmark/test_config_keys.py`): default and override
  - [x] Success: tests pass

**Commit**: `feat: add benchmark auth-probe timeout config key`

### Task 3: `ProcessRunner` can replace the environment (D7)
- [x] In `core/process_runner.py` add a keyword-only `replace_env: bool` to `ProcessRunner.run` (protocol and `SubprocessRunner`), default `False` so every existing caller is unchanged. When `True`, `env` is required (`None` raises `ValueError`) and is passed to the child exactly, with no merge over `os.environ`. Update the `# Merge over os.environ` comment to say when each applies
  - [x] Existing fake runners in `tests/` are not edited: no existing caller passes the parameter, and existing tests in `tests/replay/` must stay unmodified (Tasks 11, 25 and 29)
  - [x] The executable is found through the replaced `PATH`, so callers pass absolute paths or a `PATH` that has the tool
- [x] Tests (extend the process-runner tests): a real child (`/usr/bin/env`) with `replace_env=True` prints exactly the given variables, and a harness-only variable set with `monkeypatch.setenv` is absent; with `replace_env=False` it is still present; `replace_env=True` with `env=None` raises `ValueError`
  - [x] Success: `tests/core` and `tests/codehost` pass

**Commit**: `feat: let ProcessRunner replace the child environment`

- [x] Correct the slice design: its Interfaces Required bullet for `ProcessRunner` and the last bullet of D7 say `env=` alone applies the scrub; reword both to say callers pass `replace_env=True`
  - [x] Success: neither passage claims `env=` alone applies the scrub

**Commit**: `docs: correct slice 421 design on ProcessRunner environment`

### Task 4: Credential grant and auth carryover table (D7, D8)
- [ ] Create `src/squadron/benchmark/__init__.py` and `auth_carryover.py`: one table from `ProfileName` to home-relative carryover files (`openai-oauth` → `.codex/auth.json`; `sdk` → `.claude/.credentials.json`; API-key profiles → none). Table is keyed by the enum, not by strings
- [ ] Create `CredentialGrant` in `scrubbed_env.py`: `none()` and `for_profiles(profiles)`. For each profile it records the variable named by `ProviderProfile.api_key_env` (read from the profile definition, never hard-coded) and the carryover files from the table
- [ ] Test `tests/benchmark/test_credential_grant.py`
  - [ ] Each `ProfileName` has an explicit table entry (a profile added later without one fails the test)
  - [ ] `none()` grants no variables and no files; `for_profiles` of an API-key profile grants exactly its `api_key_env`; of `sdk`/`openai-oauth` grants the carryover file and no variable

### Task 5: `ScrubbedEnvironment` (D7)
- [ ] In `src/squadron/benchmark/scrubbed_env.py` define `SCRUB_SPEC_VERSION` (int), `SQUADRON_CONFIG_SEED = ("config.toml", "models.toml", "providers.toml")` and `HARNESS_TOOL_ALLOWLIST = ("git", "uv")`
- [ ] `ScrubbedEnvironment(root, sandbox_id, grant, harness_env)`: `harness_env` is an injected mapping (no direct `os.environ` read, so tests control it). Adapter path entries are not known until the environment is installed, after the home exists, so they are an argument of `variables(path_entries)`, not of the constructor
  - [ ] `home` is `<root>/<id>.home`. `prepare()` creates it, seeds `.config/squadron/` with the seed files that exist (and nothing else), writes `.gitconfig` (`user.name=squadron-benchmark`, `user.email=benchmark@squadron.invalid`, `init.defaultBranch=main`; define the two values as constants), creates `bin/` with symlinks to `git` and `uv` as resolved from the harness `PATH`, and symlinks each granted carryover file whose source exists
  - [ ] `variables(path_entries)` returns only: pass-through `LANG`, `LC_ALL`, `LC_CTYPE`, `TERM`, `USER`, `LOGNAME`, `SHELL`, `TMPDIR` (when set in `harness_env`); `HOME`, `TZ=UTC`, `GIT_CONFIG_GLOBAL`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_TERMINAL_PROMPT=0`, `PATH` (`path_entries`, then `<home>/bin`, then `/usr/bin:/bin:/usr/sbin:/sbin`); plus the grant's variables, valued from `harness_env`
  - [ ] A granted variable absent from `harness_env`, or a missing `git`/`uv` on the harness `PATH`, raises a named error (`MissingCredentialError` for the variable; no silent skip)
- [ ] Tests `tests/benchmark/test_scrubbed_env.py` (map level; the real-process test is Task 26)
  - [ ] A harness env containing `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME`, `VIRTUAL_ENV` and an invented `NEW_VAR`: none appear in `variables()`
  - [ ] Seeding copies only the three seed files that exist; `metrology/` and `runs/` in the real home are not copied
  - [ ] `PATH` is exactly the given entries, then `<home>/bin`, then the four system directories, in that order; carried files are symlinks to the source; `CredentialGrant.none()` adds no credential variable
  - [ ] Missing granted variable and missing `uv` each raise with the right message

**Commit**: `feat: add scrubbed producer environment and credential grants`

### Task 6: Hidden `sq benchmark _auth-probe` command (D8)
- [ ] Read `pipeline/actions/dispatch.py::one_shot_dispatch` and `models/aliases.py::resolve_model_alias`. `resolve_model_alias` returns `(name, None)` for an unknown alias and may return a profile that is `None`, so create `src/squadron/benchmark/auth_check.py` here with `resolve_alias_profile(alias) -> (model_id, ProfileName)` (Task 7 extends the file): a `None` profile or a value that is not a `ProfileName` raises `UnresolvedProfileError` naming the alias. The probe and the auth check both use it. The probe sends the constant `PROBE_PROMPT = "Reply with the single word: ok"` through `one_shot_dispatch`, the path a real dispatch uses
- [ ] Create `src/squadron/cli/commands/benchmark.py` with a `benchmark_app` Typer and the hidden `_auth-probe --model ALIAS`: prints the response to stdout and exits 0 when it is non-empty; any failure (including an empty response) prints the error to stderr and exits 1. Register `benchmark_app` in `cli/app.py` beside `replay_app`
- [ ] Test `tests/benchmark/test_auth_probe_command.py` with `one_shot_dispatch` patched at the boundary: non-empty response → exit 0; empty response → exit 1; raised error → exit 1 with the message on stderr; an unknown alias and an alias with no profile → exit 1 naming the alias, with `one_shot_dispatch` never called; the command is hidden from `sq benchmark --help`
  - [ ] Success: tests pass

### Task 7: Auth check orchestration (D8)
- [ ] In `auth_check.py` (created in Task 6): `AuthCheckResult` (profile, alias, answer, exit_code, stderr) where the answer is a `StrEnum` of `yes`, `no`, `yes_carryover_replaced`
- [ ] `run_auth_check(aliases, runner, root, harness_env, sq_path, timeout_s)`: resolve every alias with `resolve_alias_profile` first, so an unknown alias or one with no profile raises `UnresolvedProfileError` before any probe runs; one probe per distinct profile (first alias names the row). For each: build a throwaway `ScrubbedEnvironment` with `CredentialGrant.for_profiles([profile])` and `variables(())`; run `sq_path benchmark _auth-probe --model <alias>` through `ProcessRunner.run(env=..., replace_env=True)` with `benchmark.auth_probe_timeout_s`; always remove the throwaway home
  - [ ] Before each probe, run a preflight `sq_path --version` under the same throwaway environment. A binary that cannot start there (`ProcessNotFoundError`, a timeout, or a non-zero exit such as 126 or 127 from a missing interpreter on the scrubbed `PATH`) raises `ProbeStartError` carrying stderr. It says nothing about auth, so it is never recorded as a `no`
  - [ ] Exit 0 with a non-empty response → `yes`; anything else → `no` with exit code and stderr; a timeout → `no` with reason `timed out`; a `MissingCredentialError` from building the environment (for example `OPENAI_API_KEY` unset) → `no` with reason `credential variable <NAME> not set`, and no probe runs for that profile
  - [ ] After each probe, any carried symlink that is now a regular file turns a `yes` into `yes_carryover_replaced`. A `no` stays `no` (the probe result takes precedence), and the replaced paths are still listed in that row's detail
  - [ ] No fallback to the unscrubbed environment, no added variables
- [ ] `sq_path` is `shutil.which("sq")` on the harness `PATH`, resolved to an absolute path at the CLI layer; a missing `sq` raises a named error. The check prints the path it probed above the table
- [ ] Tests `tests/benchmark/test_auth_check.py` with a scripted `ProcessRunner`: create it in `tests/benchmark/support.py` as `ScriptedRunner`, accepting `replace_env` and recording each call's argv, env and `replace_env` (later tasks reuse it)
  - [ ] Two aliases of one profile → one probe; two profiles → two rows
  - [ ] Probe exit 0 → yes; exit 1 → no with stderr; `ProcessTimedOutError` → `no` / `timed out` (the hung-probe case); a probe that replaces a carried symlink → `yes_carryover_replaced`; a failed probe that also replaced a symlink → `no`, with the path in the detail
  - [ ] A preflight that exits 127, raises `ProcessNotFoundError`, or times out raises `ProbeStartError` and the probe never runs; no row is produced
  - [ ] An unknown alias and an alias with no profile raise `UnresolvedProfileError` and no probe runs; an API-key profile whose variable is absent from `harness_env` → `no` / `credential variable … not set`, runner not called
  - [ ] The runner is called with `replace_env=True`, the env has no `GH_TOKEN` and `HOME` is the throwaway home; the throwaway home is gone afterwards

### Task 8: `sq benchmark auth-check` command
- [ ] In `benchmark.py` add `auth-check --model ALIAS` (repeatable; at least one required, no implicit "all aliases"). Print the table from the design's API Contracts (profile, alias, result, with the first line of stderr on a `no`). Exit 0 only when every row is `yes`; exit 1 otherwise (including `yes_carryover_replaced`, which prints its own explanatory line, and `UnresolvedProfileError`, `ProbeStartError` or a missing `sq`, which print the message)
- [ ] Test `tests/benchmark/test_auth_check_command.py` with `run_auth_check` patched: all yes → exit 0; any no → exit 1 and the error shown; unknown alias → exit 1 naming it; the probed `sq` path is printed; no `--model` → usage error
- [ ] Check `tests/cli/test_command_surface.py` and `tests/cli/test_help.py`; add `benchmark` wherever the command list is asserted
  - [ ] Success: new and existing CLI tests pass

### Task 9: Run the auth check on this machine (design step 1)
- [ ] Use this branch's `sq`, not an older installed release that lacks the probe: run `uv sync`, then `export PATH="$PWD/.venv/bin:$PATH"`; confirm `command -v sq` is `$PWD/.venv/bin/sq` and `sq benchmark --help` lists `auth-check`
- [ ] Find an alias per profile with `sq models --help` and the listing command it names (first alias whose profile is `sdk`, first whose profile is `openai-oauth`). If a profile has no alias, record that in the DEVLOG instead of an answer
- [ ] Run `sq benchmark auth-check --model <sdk alias> --model <openai-oauth alias>`; the printed probed path must be `$PWD/.venv/bin/sq`, and a probe error that says the command does not exist is a setup mistake to fix and rerun, not an answer
- [ ] Add a DEVLOG entry with the answer per profile, the probe error for any `no`, and whether any carried symlink was replaced
  - [ ] Success: DEVLOG records, for each of `sdk` and `openai-oauth`, a yes, a no, or `no alias`. A `no` is a result, not a failure of this task: it is recorded for the PM's decision before 422 starts, and Tasks 10 onward continue

**Commit**: `feat: add sq benchmark auth-check`

### Task 10: Baseline the replay tests before the extraction
- [ ] Run `uv run pytest tests/replay tests/cli/test_replay_run.py -q` on the unmodified code and note the pass count in the DEVLOG entry
  - [ ] Success: all pass; the count is recorded for comparison after Task 11

### Task 11: Extract `HistoryFreeSandbox` (D4)
- [ ] In `src/squadron/replay/sandbox.py` create `HistoryFreeSandbox(start_sha, sandbox_id, repo_root, runner, root)` holding the lock, shallow fetch, checkout, submodule refusal, `path`, `keep()`, context manager and cleanup. It does not create a branch or touch cf
  - [ ] `sandbox.py` is 298 lines now; if the result exceeds ~300 lines move the class to `replay/history_free_sandbox.py` and re-export it from `sandbox.py`
- [ ] `ReplaySandbox` composes it and keeps `_register_with_cf`, `cf_project`, `branch` (created after the repository is built) and its public surface unchanged
- [ ] Tests: add `tests/replay/test_history_free_sandbox.py`: one-commit repository at `start_sha`, no refs to later history, submodule refusal, lock written before the directory, cleanup on every exit path, `keep()`
- [ ] Verify before the marker: rerun the Task 10 command
  - [ ] Success: everything passes; the pass count is the Task 10 count plus the new tests in `test_history_free_sandbox.py`; `git status --short tests/replay tests/cli/test_replay_run.py` shows only added files (no existing test modified)

**Commit**: `refactor: extract HistoryFreeSandbox from ReplaySandbox`

### Task 12: Benchmark record models (D1, D2)
- [ ] Create `src/squadron/metrology/benchmark_models.py` with `StrEnum`s `CaseKind` (`fix`, `slice`) and `GraderCommandKind` (`suite`, `lint`, `typecheck`); frozen models `ConftestFixture` (conftest path, fixture name), `GraderCommand` (kind, argv), `CaseProvenance` (source ref, created_at, built_by), `BenchmarkCase`, `CaseSet` with the fields in the design's Database / Storage Schema
- [ ] `BenchmarkCase.case_id` derivation per D1: `case-` plus the first 16 hex digits of the sha256 of canonical JSON (sorted keys, no whitespace) of the ten identity fields, lists sorted first; provenance excluded. A `model_validator` recomputes it and rejects a mismatch. Provide a `BenchmarkCase.build(...)` factory that computes the id
- [ ] `CaseSet`: `name` validated as a lowercase slug, `version >= 1`, `case_ids` sorted and unique; a helper for the record id `caseset-<sha256(name)[:12]>-v<version>`
- [ ] Tests `tests/metrology/test_benchmark_models.py`
  - [ ] Parametrized over each of the ten identity fields: changing only that field changes `case_id`
  - [ ] Changing provenance alone does not change it; list order does not matter; JSON round trip equals the original
  - [ ] A record with a wrong stored `case_id` fails validation
  - [ ] `CaseSet` rejects a bad slug, version 0, duplicate ids; sorts ids

### Task 13: Store primitives and record envelope (D3)
- [ ] `metrology/models.py`: add `RECORD_TYPE_BENCHMARK_CASE` and `RECORD_TYPE_CASE_SET` constants and optional `benchmark_case` and `case_set` fields on `MetrologyRecord` (extend the docstring that lists record types); `schema_version` unchanged
- [ ] `metrology/store.py`: add public `write_record(record_id, record)` wrapping the atomic write, and `iter_records()` exposing `_iter_records`; existing methods keep their behavior and the file is otherwise not changed
- [ ] Tests (extend the existing store tests): `write_record` then `load_record` round trip; `iter_records` skips a corrupt file with the existing WARNING; a record file written before this change (no new fields) still loads
  - [ ] Success: `tests/metrology/` passes

### Task 14: `BenchmarkRecordStore` cases (D1, D3)
- [ ] `src/squadron/metrology/benchmark_store.py`: `BenchmarkRecordStore(store: MetrologyStore)` with `write_case(case) -> str` (idempotent: an identical case returns the same id and leaves one file), `get_case(case_id)`. It calls `MetrologyStore.load_record` (which raises `FileNotFoundError` for an absent record and a raw pydantic `ValidationError` for a tampered one) and maps the outcomes itself: `FileNotFoundError` → `None`; `ValueError` (which covers `ValidationError`), `SchemaVersionError`, `OSError`, or a record that is not a `benchmark_case` → log at ERROR and raise `MetrologyStoreError` from the cause. A tampered file never comes back as `None`. Also `list_cases(project_id)`, which skips a mismatching file with a WARNING
- [ ] Tests `tests/metrology/test_benchmark_store.py`
  - [ ] Write then get returns an equal case; writing twice leaves one file; an unknown id returns `None`; a case-set record id passed to `get_case` raises `MetrologyStoreError`
  - [ ] Hand-edit a stored file's `task_text`: `get_case` raises `MetrologyStoreError`, `list_cases` logs a WARNING and omits it (assert with `caplog`)
  - [ ] `list_cases` filters by `project_id`

### Task 15: `BenchmarkRecordStore` case sets (D2)
- [ ] Add `write_case_set(name, case_ids) -> CaseSet`: compare to the latest version; equal list returns the existing set, a different list writes latest + 1, a first write is v1; every id must exist in the store or raise `MetrologyStoreError` naming the missing ids
- [ ] Add `get_case_set(name, version=None)` (latest when `None`; `None` when absent) and `list_case_sets()` (every stored version of every set, sorted by name then version)
- [ ] Tests (same file): v1 created; same list (any order) returns v1; changed list creates v2 and v1 is untouched; unknown ids rejected naming each; `get_case_set` latest and by version; `list_case_sets` returns all versions of two names in name-then-version order; two names do not collide
  - [ ] Success: `tests/metrology/` passes

**Commit**: `feat: add benchmark case and case-set records`

### Task 16: Adapter seam types (D6, D9, D11)
- [ ] `src/squadron/benchmark/adapter.py`: `StrEnum`s `EnvironmentFailureReason` (`no_lockfile`, `lockfile_unsupported`, `lock_stale_or_unresolvable`, `install_timeout`, `installer_missing`), `FailureKind` (`collection_error`, `missing_symbol`, `assertion_failure`, `project_exception`, `other_exception`), `NodeOutcome` (`passed`, `failed`, `error`, `skipped`, `xfailed`, `xpassed`, `not_run`); frozen `EnvironmentIdentity` with the D6 fields and `identity_digest` computed from the rest; `NodeResult`; `SuiteSelection` (`all_tests()`, `nodes(ids)`, each with `deselect`); `SuiteRun` (results, `timed_out`); `SandboxContext`; errors `EnvironmentResolutionError(reason, detail)` and `SuiteRunError`; the `BenchmarkAdapter` protocol exactly as in D9
- [ ] Tests `tests/benchmark/test_adapter_types.py`: identity digest changes when any field changes (including `scrub_spec_version`) and is stable otherwise
  - [ ] Success: tests pass; `pyright` is clean

### Task 17: Fixture projects for environment resolution
- [ ] Under `tests/benchmark/fixtures/` create small uv projects, each with `pyproject.toml` (pytest as a dev dependency): `env_ok` (with a committed `uv.lock` generated by `uv lock`), `env_stale_lock` (a valid `uv.lock` plus a `pyproject.toml` dependency added afterwards), `env_no_lock`, `env_poetry_lock` (a `poetry.lock` and no `uv.lock`)
- [ ] Add `tests/benchmark/conftest.py` with `collect_ignore_glob = ["fixtures/*"]`: `pyproject.toml` sets `testpaths = ["tests"]`, so without it the repo's own `pytest` run would collect the fixture projects' deliberately failing tests. If `ruff check` flags the fixtures, add `tests/benchmark/fixtures` to ruff's `extend-exclude`
- [ ] A test helper `tests/benchmark/support.py::git_tree(fixture, tmp_path)` copies a fixture into a one-commit git repository and returns its path
  - [ ] Success: `uv sync --locked` succeeds in `env_ok` and fails in `env_stale_lock`, checked by hand once

### Task 18: `PythonBenchmarkAdapter.resolve_environment` and `path_entries` (D5, D6)
- [ ] `src/squadron/benchmark/python_adapter.py`: `resolve_environment(ctx)` requires `uv.lock` (absent → `no_lockfile`; `poetry.lock` or `requirements*.txt` present instead → `lockfile_unsupported` naming the file). It runs `uv sync --locked --all-extras --dev` with `cwd=ctx.tree`, under the harness environment (not the scrubbed one), bounded by `ctx.install_timeout_s`, through `ctx.runner` (the install uses the default merged environment, not `replace_env`). Add `benchmark.install_timeout_s` (default 900) to `config/keys.py` beside the probe key, with a default and an override test
  - [ ] uv exit non-zero → `lock_stale_or_unresolvable` with uv's stderr; timeout → `install_timeout`; `ProcessNotFoundError` for `uv` → `installer_missing`. Each is logged at ERROR where raised and never retried without the lock
  - [ ] On success write `.venv/` to the tree's `.git/info/exclude` and return `EnvironmentIdentity` (lockfile path and sha256, `.venv/bin/python --version`, `uv --version`, platform, `SCRUB_SPEC_VERSION`, digest)
- [ ] `path_entries(ctx)` returns `(<tree>/.venv/bin,)`
- [ ] Tests `tests/benchmark/test_python_environment.py` (real uv; `network` marker on those that install)
  - [ ] `env_ok`: `lockfile_sha256` equals `hashlib.sha256` of the committed `uv.lock`; `.venv` exists; `git status --porcelain` in the tree shows no `.venv`
  - [ ] `test_stale_lock_fails`: reason `lock_stale_or_unresolvable`, uv's message present, no `.venv` created
  - [ ] `env_no_lock` → `no_lockfile`; `env_poetry_lock` → `lockfile_unsupported` naming `poetry.lock`; neither runs uv
  - [ ] With a scripted runner: timeout → `install_timeout`; missing `uv` → `installer_missing`

**Commit**: `feat: add benchmark adapter seam and python environment resolution`

### Task 19: Fixture project for suite classification
- [ ] Create `tests/benchmark/fixtures/classify_project/` with a committed `uv.lock`, pytest as a dev dependency, `pytest` config `pythonpath = ["src"]`, a package `pkg` (`pkg/core.py` with a function that raises `ZeroDivisionError` and a plain function), and tests covering one node per case:
  - [ ] assertion (`assert 1 == 2`); project-code crash (calls the raising `pkg.core` function); import of a missing name from a project module (`ImportError`/`ModuleNotFoundError` inside the test body); `AttributeError` on a project module (`pkg.core.absent()`); `mock.patch("pkg.core.absent")`; exception raised in test code (`TypeError` in the test); a passing test; a skipped test; an xfail; a parametrized test whose id has brackets
  - [ ] a separate module `test_collect_fails.py` that fails at import
  - [ ] A second fixture, `tests/benchmark/fixtures/sleep_project/`: a copy of `env_ok` (same dependencies, its own `uv.lock` from `uv lock`) with one test that sleeps for 60 seconds. It is a separate project so that no run of `classify_project` can stall; Task 23's timeout test uses it with a `suite_timeout_s` of a few seconds
  - [ ] a `conftest.py` and a test helper in the project (to confirm both are treated as test code, not project source)
  - [ ] Success: `uv sync --locked` works in the fixture; running its tests with the harness's pytest from a `git_tree` copy shows the expected failures by hand; `uv run pytest tests/benchmark --collect-only -q` lists no node under `fixtures/`

### Task 20: The reporter plugin (D10)
- [ ] Create `src/squadron/benchmark/pytest_reporter/squadron_benchmark_reporter.py`, importing only the standard library and `pytest`. Implement `pytest_collectreport` and a `pytest_runtest_makereport` hookwrapper (hooks available since pytest 7.0). The record format is pinned here and consumed by Tasks 21 and 22. One JSONL line per collection failure and per test phase, with exactly these keys: `node_id`; `phase` (`collect`, `setup`, `call`, `teardown`); `outcome` (`passed`, `failed`, `skipped`, `xfailed`, `xpassed`); `exc_type` (qualified name, or null); `exc_module` (module defining the exception class, or null); `named_module_file` (file of the module the exception names: `ImportError.name`, `AttributeError.obj`, or for an `AttributeError` raised inside `unittest/mock.py` the `target` module of the `_patch` object found in the innermost frame; null otherwise); `frame_file` and `frame_line` (innermost traceback frame, or null). The output path comes from the environment variable `SQUADRON_BENCHMARK_REPORT`. The plugin creates (truncates) that file in `pytest_configure`, so a file that exists proves the plugin loaded
- [ ] Create `src/squadron/benchmark/python_failure.py` (Task 21 extends it) holding `REPORT_PATH_ENV = "SQUADRON_BENCHMARK_REPORT"` and `REPORT_KEYS` (the key tuple above) for the harness side; the plugin cannot import it, so it repeats both as module constants
- [ ] Confirm the wheel ships it: `uv build`, then list the wheel contents (`unzip -l`); if hatch omits non-package files, add the needed `pyproject.toml` include. Locate the plugin directory at runtime with `importlib.resources` or `Path(__file__)`, never the cwd
- [ ] Tests `tests/benchmark/test_pytest_reporter.py`: run the harness's pytest with `-p squadron_benchmark_reporter` and `PYTHONPATH` on a `git_tree` copy of `classify_project` (no venv needed) and read the JSONL
  - [ ] Every executed node has a line for each phase; the failing nodes carry exception qualname/module; the mock-patch node records the patched module's file; the collection failure has its own line
  - [ ] Every line has exactly `REPORT_KEYS`; the plugin's own constants equal `REPORT_PATH_ENV` and `REPORT_KEYS` (load the plugin by path with `importlib`); the file exists and is empty after a run that collects no tests
  - [ ] The plugin file imports nothing outside the standard library and `pytest` (assert by AST)
  - [ ] The wheel-content check passes

### Task 21: Fold records and classify failures (D11)
- [ ] In `python_failure.py` add `classify(record, tree)` turns one reporter record into a `FailureKind`, assigned in D11's order (collection_error, missing_symbol, assertion_failure, project_exception, other_exception). "Project source" is a file under `tree`, not under `.venv`, and not `test_*.py`, `*_test.py` or `conftest.py`; a project module is a module whose file is project source
- [ ] `fold_records(records, tree) -> dict[node_id, NodeResult]`: one `NodeResult` per node from its per-phase records, by this precedence. A failed `setup` → `error`, classified from that record. Else a failed `call` → `failed`, classified from it. Else a failed `teardown` → `error`, classified from it. Else the `call` outcome (`passed`, `skipped`, `xfailed`, `xpassed`), or the `setup` outcome when there is no `call` record (a skip in setup). A failed `collect` record → `error` with `collection_error`, under the file's node id
- [ ] Tests `tests/benchmark/test_python_failure.py` (ordering, edge and fold rules on small synthetic records, using `REPORT_KEYS`; real-pytest coverage is Task 23)
  - [ ] An `ImportError` naming a project module → `missing_symbol`; naming a third-party module → `other_exception`
  - [ ] `AttributeError` with project-module `named_module_file` → `missing_symbol`; mock-patch record with a project target → `missing_symbol`; innermost frame in a test helper → `other_exception`
  - [ ] `AssertionError` and pytest `Failed` → `assertion_failure`; `ZeroDivisionError` from a project frame → `project_exception`; a frame under `.venv` → `other_exception`
  - [ ] A collection record → `collection_error` even when its exception is an `ImportError` of a project name (order test)
  - [ ] Fold: failed setup beats a call record; failed call with failed teardown → `failed`; passed call with failed teardown → `error`; setup skip with no call → `skipped`; xfail and xpass map to `xfailed` and `xpassed`

### Task 22: `run_suite` on the Python adapter (D10)
- [ ] Add `benchmark.suite_timeout_s` (default 1800) to `config/keys.py` beside the other benchmark keys, with a default and an override test
- [ ] In `python_adapter.py` implement `run_suite(ctx, selection)`: copy the plugin into `<out>/plugin`, run `<tree>/.venv/bin/python -m pytest -p squadron_benchmark_reporter -p no:cacheprovider` with the selection's node ids or `--deselect` arguments, `cwd=tree`, through `ctx.runner` with `replace_env=True` and `ctx.env.variables(self.path_entries(ctx))` plus `PYTHONPATH=<out>/plugin` and `REPORT_PATH_ENV` pointing into `<out>`, bounded by `ctx.suite_timeout_s`. Read the JSONL, fold it with `fold_records`, and return a `SuiteRun`
  - [ ] The result set: for `nodes(ids)`, one `NodeResult` per requested id; for `all_tests()`, one per node that has a record
  - [ ] A requested id with no record: if its file has a collection failure it takes that error; otherwise it is `error` with `collection_error` (not collected)
  - [ ] Timeout → `SuiteRun(timed_out=True)` built from the lines written so far; every requested node without a result is `not_run`
  - [ ] JSONL file missing (the plugin never loaded), at any pytest exit code, or a line that does not parse → `SuiteRunError` carrying pytest's stderr, logged at ERROR. An existing empty file is valid only for pytest exit 5 (nothing collected: empty result for `all_tests()`) or exit 4 with `nodes(ids)` (the ids were not found: each is `error` / `collection_error`); an empty file at any other exit code, including 0, raises `SuiteRunError`
  - [ ] `.pytest_cache` and the plugin directory do not appear in the tree
- [ ] Tests `tests/benchmark/test_python_suite_runner.py` with a scripted `ProcessRunner`
  - [ ] The command line has the plugin flags, the node ids or `--deselect` arguments, and `replace_env=True`; the env has no credential variable and carries `PYTHONPATH` and the report path
  - [ ] Missing JSONL with exit 0 and with non-zero exit each raise `SuiteRunError`; an unparseable line raises; an empty file with exit 0 and with exit 1 each raise; an empty file with exit 5 and `all_tests()` gives no results; an empty file with exit 4 and `nodes(ids)` gives `error` / `collection_error` per id; a requested id with no record is `error` / `collection_error`
  - [ ] `ProcessTimedOutError` → `timed_out=True`, with the nodes that reported kept and the rest `not_run`

### Task 23: Real-pytest suite tests
- [ ] Tests `tests/benchmark/test_python_suite.py` run real pytest in a module-scoped sandbox of `classify_project` (`network` marker); build it with `git_tree` and `resolve_environment`
  - [ ] One test per kind: assertion, project crash, missing import of a project name, project-module `AttributeError`, `mock.patch` of a missing target, collection error, exception in test code, not-collected node id; and a timeout in a module-scoped sandbox of `sleep_project` with a `suite_timeout_s` of a few seconds
  - [ ] Passed, skipped, xfailed outcomes map correctly; a bracketed parametrized id round-trips exactly
  - [ ] `SuiteSelection.nodes` runs only the given nodes and returns exactly those results; `deselect` removes nodes from an all-tests run
  - [ ] Success: all pass against real pytest, with no synthetic JSONL

### Task 24: Adapter registry (D9)
- [ ] `src/squadron/benchmark/registry.py`: `adapter_for(language: SourceLanguage) -> BenchmarkAdapter` returns `PythonBenchmarkAdapter` for `PYTHON`; any other language raises a named error. It is the only importer of concrete adapters
- [ ] Test `tests/benchmark/test_registry.py`: Python returns the adapter; every other `SourceLanguage` raises
  - [ ] Success: tests pass; `pyright` accepts the adapter as a `BenchmarkAdapter`

**Commit**: `feat: add python suite runner with failure classification`

### Task 25: `BenchmarkSandbox` (D4, D7, design Data Flow)
- [ ] `src/squadron/benchmark/sandbox.py`: `benchmark_root()` returns `~/.config/squadron/benchmark/`. `BenchmarkSandbox(start_sha, sandbox_id, repo_root, runner, adapter, harness_env, install_timeout_s, suite_timeout_s, root=None)` composes `HistoryFreeSandbox` (tree `<root>/<id>/`), a `ScrubbedEnvironment` with `CredentialGrant.none()` (home `<id>.home`), and an output directory `<id>.out`. `__enter__` order: history-free build, `ScrubbedEnvironment.prepare()`, `adapter.resolve_environment`. Expose `tree`, `home`, `output_dir`, `identity`, `keep()`, `run_suite(selection)` and `process_env()` (`environment.variables(adapter.path_entries(ctx))`, the map for any child process in the sandbox)
  - [ ] All four paths (tree, home, out, lock) are removed on exit unless `keep()` was called, and on every failed-enter path (resolution failure leaves nothing)
- [ ] `sweep_orphans(runner, root=None, *, sweep_cf_projects=True, sibling_suffixes=())`: the new keyword-only parameters default to today's behavior, so `sq replay`'s call (`runner.py`) and the existing tests are unchanged. With `sweep_cf_projects=False` no `cf` command runs. Entries whose name ends in a `sibling_suffixes` value (`.home`, `.out`) are skipped when iterating (they have no lock of their own) and removed with their owner's directory when the owner is an orphan
- [ ] `sweep_benchmark_orphans(runner, root=None)` in `benchmark/sandbox.py`: calls `sweep_orphans(runner, root or benchmark_root(), sweep_cf_projects=False, sibling_suffixes=(".home", ".out"))`
- [ ] Tests `tests/benchmark/test_benchmark_sandbox.py` on `env_ok` and `env_no_lock`
  - [ ] Enter, then `identity`, tree, home and out exist; exit removes all four; `keep()` leaves them
  - [ ] `env_no_lock` raises `EnvironmentResolutionError(no_lockfile)` and nothing remains under the root
  - [ ] `sweep_orphans` with `sweep_cf_projects=False` removes an orphaned sandbox and runs no `cf` command; with `sibling_suffixes` it also removes the orphan's siblings and leaves a live owner's alone
  - [ ] Rerun the Task 10 command: it passes with the same count and no existing replay test modified
  - [ ] `sweep_benchmark_orphans` removes an orphan's three directories and lock with a WARNING, ignores a live one, runs no `cf` command, and does not touch a `replays/` sibling root
  - [ ] `run_suite` runs under the scrubbed environment (spot check an env value from inside a test); `process_env()` has the adapter's `.venv/bin` first on `PATH`

### Task 26: Real-process scrub test and concurrency load test (success criteria, Technical Requirements)
- [ ] In `tests/benchmark/test_scrubbed_env.py` add one `network` integration test: build a `BenchmarkSandbox` at the repository's own HEAD commit (it has `uv.lock`) and run through `process_env()`, via `ProcessRunner` with `replace_env=True`, the commands `env`, `command -v sq`, `sq --version` and `git config --get credential.helper`
  - [ ] `GH_TOKEN`, `GITHUB_TOKEN` and `SSH_AUTH_SOCK` are absent (set them with `monkeypatch.setenv` in the test process first, so the test fails if the runner still merges `os.environ`); `HOME` is the scrubbed home
  - [ ] Every `PATH` entry under the real home belongs to the sandbox (`<tree>/.venv/bin`, `<id>.home/bin`)
  - [ ] `command -v sq` is `<tree>/.venv/bin/sq`; `sq --version` matches the version in the tree's `pyproject.toml`; `credential.helper` prints nothing
  - [ ] Success: the test passes on this machine
- [ ] Load test `tests/load/test_benchmark_sandbox_concurrency.py` (`network` marker): enter three `BenchmarkSandbox`es on `env_ok` at once (threads), each in its own root and sharing the uv cache, while `sweep_benchmark_orphans` runs on the shared root
  - [ ] All three resolve their environments within `benchmark.install_timeout_s`, the sweep removes none of them (live locks), and after exit nothing remains under the root

**Commit**: `feat: add benchmark sandbox with scrubbed environment`

### Task 27: `sq benchmark sandbox` command
- [ ] In `benchmark.py` add `sandbox REV [--suite] [--node ID ...] [--keep]`: resolve `REV` in the current project with git, call `sweep_benchmark_orphans` first (this is the sweep's call site, as `sq replay` calls its own at the start of a run), then build `BenchmarkSandbox` with `adapter_for(SourceLanguage.PYTHON)` and the configured install and suite timeouts, print the environment identity; with `--suite` run all tests, with `--node` run only those ids; print counts per outcome and failure kind and each failing node with its kind; `--keep` calls `keep()` and prints the tree, home and out paths. `--suite` with `--node` is a usage error. A resolution failure prints the reason and uv's stderr and exits 1; the CLI imports concrete adapters only through `registry.py`
- [ ] Tests `tests/benchmark/test_sandbox_command.py` with the sandbox patched at the boundary: identity printed; counts and failing node lines for a scripted `SuiteRun`; `--node` passes only those ids; `--keep` prints the paths; the sweep is called once before the sandbox is built; `EnvironmentResolutionError` → exit 1 with reason and stderr; bad `REV` → exit 1
  - [ ] Success: tests pass; `tests/cli` command-surface tests still pass

**Commit**: `feat: add sq benchmark sandbox`

### Task 28: Verification walkthrough (design Verification Walkthrough, steps 2–7)
- [ ] Run steps 2 to 7 of the design's walkthrough on this machine (step 1 was Task 9) and note each result in the DEVLOG entry. Set `REV=$(git log --format=%h -n1 v0.20.0)` first (the design's commit; `v0.20.0` has a `uv.lock`) and use it wherever a step names `$REV`
  - [ ] Step 2: `lockfile_sha256` matches `git show $REV:uv.lock | shasum -a 256`; the kept paths exist
  - [ ] Step 3: `uv run pytest tests/benchmark/test_scrubbed_env.py -v` passes
  - [ ] Step 4: `--suite` prints outcome counts; `--node` with one printed id reports exactly one result
  - [ ] Step 5: `uv run pytest tests/benchmark/test_python_environment.py::test_stale_lock_fails` (and the `no_lockfile` case in the same file) fails with the expected reason, exit 1, no `.venv`
  - [ ] Step 6: `uv run pytest tests/metrology/test_benchmark_store.py -v` passes
  - [ ] Step 7: after a plain run nothing remains under `~/.config/squadron/benchmark/`; kill a run mid-install, run again, and the orphan is swept with a WARNING
  - [ ] `sq replay run` manual check (one run) behaves as before, per Integration Requirements

### Task 29: Final validation, CHANGELOG, DEVLOG
- [ ] Run `ruff format`, `ruff check`, `pyright` (zero errors) and the full test suite once; fix any failure at its cause
  - [ ] Success: all clean; existing `tests/replay/` tests unmodified and passing
- [ ] Confirm no source file exceeds ~300 lines (`benchmark/python_adapter.py`, `cli/commands/benchmark.py` are the likeliest; split by concern if so)
- [ ] Update the slice design's Component Structure and Patterns lists with what the tasks added: `UnresolvedProfileError`, `ProbeStartError`, `MissingCredentialError`, `sweep_benchmark_orphans`
- [ ] CHANGELOG: one short user-facing bullet for `sq benchmark auth-check` and `sq benchmark sandbox`
- [ ] DEVLOG: implementation entry per the Session State Summary guidance (what was done, the auth answers, verification results, next: 422); mark the slice design `status: complete` and tick its slice-plan entry when all tasks are complete
  - [ ] Success: slice design and slice plan reflect completion; every task above is checked, including dropped items marked `[x]` with a note

**Commit**: `feat: complete benchmark sandbox and case record slice`
