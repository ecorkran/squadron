---
docType: review
layer: project
reviewType: tasks
slice: benchmark-sandbox-and-case-record
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: FAIL
verdictSource: stated
sourceDocument: project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: eaec27a8ae16c9263f695fd8e07313c9c4eb79d2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 15
effort: xhigh
turns: 16
promptTokens: 809522
cachedTokens: 654667
cacheWriteTokens: 154841
completionTokens: 59306
durationSeconds: 258.5
costUsd: 0.321364
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: fail
    category: correctness
    summary: "ProcessRunner merges the harness environment, so the scrub allowlist is not enforced"
    location: "src/squadron/core/process_runner.py:118"
  - id: F002
    severity: fail
    category: completeness
    summary: "Fixture tests are collected by the repo's root pytest run"
    location: "pyproject.toml:89"
  - id: F003
    severity: concern
    category: sequencing
    summary: "Task 2 precedes the auth spike the design says must come first"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:46"
  - id: F004
    severity: concern
    category: correctness
    summary: "Task 4 points at the wrong task and asserts a PATH rule its own home path breaks"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:68"
  - id: F005
    severity: concern
    category: sequencing
    summary: "`ScrubbedEnvironment` needs path entries that Task 22 only has after the home is built"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:64"
  - id: F006
    severity: concern
    category: interface
    summary: "The reporter record format and env var name are not pinned across Tasks 19–21"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:185"
  - id: F007
    severity: concern
    category: completeness
    summary: "No rule folds per-phase reporter records into one outcome per node"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:208"
  - id: F008
    severity: concern
    category: error-handling
    summary: "A run with no JSONL and a zero exit is not covered by the error rule"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:204"
  - id: F009
    severity: concern
    category: correctness
    summary: "`get_case` cannot tell absent from tampered with the existing load path"
    location: "src/squadron/metrology/store.py:560"
  - id: F010
    severity: concern
    category: error-handling
    summary: "Auth-check alias resolution has no defined behavior for a missing or unknown profile"
    location: "src/squadron/models/aliases.py:227"
  - id: F011
    severity: concern
    category: correctness
    summary: "The auth check does not pin which `sq` gets probed"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:101"
  - id: F012
    severity: concern
    category: scope
    summary: "Task 21 is the largest task and bundles separable work"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:200"
  - id: F013
    severity: note
    category: completeness
    summary: "Probe result precedence is unstated when a probe fails and a symlink was replaced"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:85"
  - id: F014
    severity: pass
    category: completeness
    summary: "Success criteria, commit markers and test placement are sound"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:1"
---

# Review: tasks — slice 421

**Verdict:** FAIL
**Model:** claude-haiku-5-5

## Findings

### [FAIL] ProcessRunner merges the harness environment, so the scrub allowlist is not enforced

`ProcessRunner.run` builds the child environment as `{**os.environ, **env}` and passes it to Popen (line 128). A scrubbed map only overrides the keys it names. `GH_TOKEN`, `GITHUB_TOKEN`, `SSH_AUTH_SOCK`, `CLAUDE_CONFIG_DIR`, `CODEX_HOME` and `VIRTUAL_ENV` from the harness therefore reach every child. The design treats `ProcessRunner.run(env=...)` as already sufficient (Interfaces Required; D7 "Every child process ... receives `ScrubbedEnvironment.variables()`"), and D7 forbids building the allowlist by deleting from `os.environ`. No task changes the runner.

Task 4 and Task 6 test the map passed to a scripted runner, which cannot see the merge. Only Task 23 checks the real child environment, and it runs after Tasks 5–22 have been built on the wrong assumption.

Recommendation: add a task before Task 5 that gives `ProcessRunner.run` an explicit whole-environment mode. The default stays the merge, because existing callers depend on it (the comment at lines 116–117). Add a test that a variable set in the parent's `os.environ` is absent from the child. Confirm the mode name with the PM, since the runner is shared.

### [FAIL] Fixture tests are collected by the repo's root pytest run

`[tool.pytest.ini_options]` sets `testpaths = ["tests"]` with no `norecursedirs`. Task 18 puts test modules under `tests/benchmark/fixtures/classify_project/`, so a root `uv run pytest` collects them. `test_collect_fails.py` raises at import, which pytest reports as a collection error that stops the session by default. The sleep test would also run in every full run, and the intentional assertion and crash tests would show as failures. `[tool.ruff]` has no exclude either, so fixture files are linted and formatted. Pyright is not affected, because `include = ["src"]`.

Task 26 runs the full suite, so the gate fails once Task 18 lands. Add a step to Task 16, before any fixture test file is committed, that excludes the fixture tree from root collection. Use a path-scoped pattern such as a `benchmark/fixtures` entry in `norecursedirs`, or `collect_ignore` in `tests/benchmark/conftest.py`. Do not use a bare `fixtures` pattern: `tests/fixtures/test_cf_adoption_fixtures.py` already exists and would drop out. Confirm with `uv run pytest --collect-only -q`.

### [CONCERN] Task 2 precedes the auth spike the design says must come first

The design's Development Approach step 1 and Mitigation Strategies both say the auth check is built before any other code. Task 2 (install, suite and probe timeout keys) comes ahead of the spike. Only `benchmark.auth_probe_timeout_s` is needed by Tasks 5–8. The install and suite keys are first read in Tasks 17 and 21. Move Task 2 after Task 8, or split the probe key into the spike. The Context Summary says "auth spike first," and this contradicts it.

### [CONCERN] Task 4 points at the wrong task and asserts a PATH rule its own home path breaks

Line 68 says the real-process test "comes in Task 21." Task 21 is `run_suite`. The real-process scrub test is Task 23.

Line 71 requires "no entry under the real home other than the adapter entries." The scrubbed home is `<root>/<id>.home`, and Task 22 sets the root to `~/.config/squadron/benchmark/`. So `<id>.home/bin`, which Task 4 itself builds, is under the real home and fails that rule. Task 23 states the correct rule: entries under the real home must belong to the sandbox. Rewrite Task 4's assertion to match, and fix the cross-reference.

### [CONCERN] `ScrubbedEnvironment` needs path entries that Task 22 only has after the home is built

Task 4's constructor takes `path_entries`. Task 22's `__enter__` order creates the scrubbed home at step 2, calls `resolve_environment` at step 3, and gets `path_entries` only at step 4. The entries do not exist at step 2, so the object cannot be built in the stated order. Either build it after `resolve_environment` (the install runs under the harness environment and does not need the home), or make the entries a late input to `variables()`. Pick one in Task 22, and fix design Data Flow step 3, which creates the home before resolution.

### [CONCERN] The reporter record format and env var name are not pinned across Tasks 19–21

Task 19 lists what each JSONL line holds but gives no key names. It takes the output path "from an environment variable" without naming it. Task 21 refers to "the JSONL path variable" with no name. Task 20's `classify(line, tree)` does not say what `line` is. These three tasks share one interface, and nothing pins it.

The design says the plugin imports only the standard library and pytest. So define the env var name and the record keys as module-level constants in the plugin file. The runner and classifier can import them from there, because the runner lives in the package, while the plugin copied to `<out>/plugin` stays self-contained.

### [CONCERN] No rule folds per-phase reporter records into one outcome per node

The reporter writes one line per phase (setup, call, teardown). Task 21 must return one `NodeResult` per requested node, but no task says how the phases combine. Cases that need a rule include: an error in setup with no call record, a failure in call followed by a teardown error, a skip in setup, and xfail or xpass from the call phase. The test bullet on line 208 asserts that passed, skipped and xfailed "map correctly" without giving the mapping.

Add the fold rule to Task 21. For example: an error in setup or teardown beats a call result, otherwise the call phase decides, and a skip in setup is `skipped`. Also say which phase supplies `phase` and `exception_type` on `NodeResult`, using the fields D11 lists.

### [CONCERN] A run with no JSONL and a zero exit is not covered by the error rule

Line 204 raises `SuiteRunError` for missing or unparseable JSONL only when pytest exits non-zero. The design (D10, and Special Considerations) requires that a missing JSONL never comes back as an empty pass, and that a pytest without the reporter hooks fails with `SuiteRunError`. A run that exits 0 without writing the file is the likely shape of a hook-less pytest run where every test passes. As written, it falls through to "every requested node is `not_run`" and returns a result nobody can explain.

Make a run that is not timed out and produces no JSONL raise `SuiteRunError`, whatever the exit code. Add a scripted-runner test for that case.

### [CONCERN] `get_case` cannot tell absent from tampered with the existing load path

`load_record` raises `FileNotFoundError` for a missing file. For a corrupt one, `_load_raw` (lines 192–201) lets through `SchemaVersionError` or a pydantic validation error, which is a `ValueError`. Task 13 requires `get_case` to return `None` when absent and raise `MetrologyStoreError` for a tampered file, never `None`. It names neither the mapping nor the exceptions.

Specify the mapping in Task 13: catch `FileNotFoundError` and return `None`; catch `(OSError, ValueError, SchemaVersionError)` and raise `MetrologyStoreError(...) from exc`. The slice-ranges read at store.py:552–555 already does the second half. The tamper test should also check that the failure is the content mismatch, not some other validation error.

### [CONCERN] Auth-check alias resolution has no defined behavior for a missing or unknown profile

`resolve_model_alias` returns `(model, profile)`, where `profile` is a plain `str | None`. A name that is not an alias returns `None` for the profile, which is how a literal model id comes back. Task 6 says "resolve each alias to its profile" and does not say what happens when the profile is `None`. It also does not cover a profile name that is not a `ProfileName` member. User profiles from `load_user_profiles` (providers/profiles.py:101) can have names the enum does not contain, and Task 3's carryover table is keyed by the enum.

Specify in Task 6 that both cases raise a named error before any probe runs. A probe with an empty grant would produce a `no` for the wrong reason. Add a test for each.

### [CONCERN] The auth check does not pin which `sq` gets probed

Task 8 says "Run `sq benchmark auth-check`" without saying which install. Task 6 resolves the probe's `sq` with `shutil.which` on the harness PATH. If the `sq` on PATH is a global install that predates `benchmark`, every probe fails with an unknown-command error, and the table reports `no` for both profiles. The PM would then get a false answer, which the design routes to a decision before 422.

Specify in Task 8 that the check runs as `uv run sq benchmark auth-check ...`, and that `uv run sq benchmark --help` lists `auth-check` first. Have the DEVLOG entry record the resolved probe path.

### [CONCERN] Task 21 is the largest task and bundles separable work

Task 21 holds `run_suite` (plugin copy, pytest subprocess, timeout handling, JSONL read, the `not_run` fill, not-collected handling, the missing-JSONL path, the cache-directory check), nine real-pytest cases, four scripted cases, the `SuiteSelection` behavior, and the registry with its own test. Split it into two steps. The first covers the `run_suite` mechanics (timeout, `not_run`, JSONL errors, cache directory) with scripted-runner tests. The second covers the real-pytest per-kind tests. Move the registry into its own step after Task 21. Line 211 already says the registry comes "now that `PythonBenchmarkAdapter` satisfies the protocol," so the split keeps that ordering.

### [NOTE] Probe result precedence is unstated when a probe fails and a symlink was replaced

Task 6 lists `no` and `yes_carryover_replaced` as separate rules, and does not say which wins when a probe fails and a carried symlink was also replaced. D8 treats a replaced link as the important finding, because the user's real token may be stale. Specify that the row shows `no` and also records the replacement.

### [PASS] Success criteria, commit markers and test placement are sound

- Functional criteria map to tasks: record round trip and identity (11, 13); case-set versions (13, 14); historical sandbox (17, 24, 25); no-lockfile and stale-lock failures (16, 17); scrubbed environment (4, 22, 23); auth check (5–8); suite runner per kind (18, 21).
- Technical requirements have tasks: each failure path has a test (17, 21); the replay suite is checked before and after the extraction (9, 10); the integration test is in Task 23.
- Walkthrough steps 1–7 are covered by Tasks 8 and 25.
- Commit markers sit at 2, 4, 8, 10, 14, 17, 21, 23, 24 and 26, each after a working, tested point.
- Each implementation task is followed by its tests.
- No task merges or pushes.
- The design restates no performance NFR, so no load-test task is required.
- Claims verified against code: `sandbox.py` is 298 lines (Task 10's premise). `CF_CLI_TIMEOUT_KEY` (config/keys.py:21), `get_positive_int_config` (config/manager.py:145), `one_shot_dispatch` (pipeline/actions/dispatch.py:125), `ProcessNotFoundError` and `ProcessTimedOutError` (core/process_runner.py:42, 64), `MetrologyStoreError` (metrology/errors.py:35), `replay_app` (cli/commands/replay.py:43) and the CLI surface tests all exist.

### Run Digest

- Response length: 14460 chars
- Response is newline-free: no
- Tool calls made: 15
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 16
- Tokens — prompt / cached / cache write / completion / reasoning: 809522 / 654667 / 154841 / 59306 / not computed
- Duration: 258.5 s
- Cost: $0.32 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 14
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 14
- Finding-shaped matches — surviving validation: 14
