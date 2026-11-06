---
docType: review
layer: project
reviewType: tasks
slice: benchmark-sandbox-and-case-record
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: d1d9ed4b54f85950c1ad5c39476ff5ff79ded61a
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 20
effort: xhigh
turns: 21
promptTokens: 733773
cachedTokens: 564100
cacheWriteTokens: 169661
completionTokens: 60602
durationSeconds: 256.7
costUsd: 0.337083
costBasis: provider
runId: run-20261106-tasks-plan-711d0fe6
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: testing
    summary: "Task 11 requires the same replay test count after adding tests to that directory"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:128-131"
  - id: F002
    severity: concern
    category: error-handling
    summary: "An empty JSONL file counts as a valid pass at any pytest exit code"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:224"
  - id: F003
    severity: concern
    category: correctness
    summary: "A missing runtime binary in the scrubbed PATH could be recorded as an auth \"no\""
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:110-115"
  - id: F004
    severity: concern
    category: testing
    summary: "`list_case_sets()` has no test"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:160-161"
  - id: F005
    severity: note
    category: documentation
    summary: "Task 9's success criterion cannot be met on the no-alias branch"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:112-115"
  - id: F006
    severity: note
    category: process
    summary: "Task 3's commit bundles Task 2's config key and the design correction"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:48-62"
  - id: F007
    severity: note
    category: documentation
    summary: "Task 14's tamper sentence is missing its verb"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:152"
  - id: F008
    severity: note
    category: testing
    summary: "Task 28 does not name the historical REV"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:271-273"
  - id: F009
    severity: note
    category: task-sizing
    summary: "Task 11 bundles a sweep API change that only Task 25 uses"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:123-131"
  - id: F010
    severity: note
    category: scope
    summary: "Two modules are outside the design's component list"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:200"
  - id: F011
    severity: note
    category: testing
    summary: "The load-test justification leaves out the environment-layer trigger"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:38"
  - id: F012
    severity: pass
    category: coverage
    summary: "Every design success criterion has a task"
    location: "project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md:301-323"
  - id: F013
    severity: pass
    category: correctness
    summary: "The design correction is right and tasked"
    location: "src/squadron/core/process_runner.py:116-118"
  - id: F014
    severity: pass
    category: sequencing
    summary: "Sequencing respects dependencies, and the referenced code exists"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:43-290"
  - id: F015
    severity: pass
    category: process
    summary: "Test-with, checkbox and commit-marker conventions are followed"
    location: "project-documents/user/tasks/421-tasks.benchmark-sandbox-and-case-record.md:62"
---

# Review: tasks — slice 421

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 11 requires the same replay test count after adding tests to that directory

Task 11 adds `tests/replay/test_history_free_sandbox.py` (line 128). Line 130 then says the Task 10 command, which runs all of `tests/replay` (line 120), "passes with the same count." Once the new file exists, the count must rise. Restate the check as "the existing tests keep their baseline count and pass, plus the new file's tests pass."

### [CONCERN] An empty JSONL file counts as a valid pass at any pytest exit code

Line 224 says an existing empty file is valid and gives an empty `all_tests()` result, with no condition on exit code. The plugin truncates the file in `pytest_configure` (line 199). If pytest then exits with 2 (interrupted), 3 (internal error) or 4 (usage error), the file is empty and this rule returns an empty result. Design D10 (line 209) says a run must never come back as an empty pass. Make the empty-file case valid only for exit codes 0 and 5 (no tests collected), and raise `SuiteRunError` for any other code. Add that case to the test on line 228.

### [CONCERN] A missing runtime binary in the scrubbed PATH could be recorded as an auth "no"

Line 113 treats a "command does not exist" probe error as a setup mistake, but only for `sq`. The design's PATH policy (design line 168) leaves out `~/.local/bin`, Homebrew, pipx and uv tool installs. If the `sdk` runtime or the `codex` binary behind `openai-oauth` is found through PATH, a missing-binary error would appear as a `no`, and design lines 186 and 369 send any `no` to the PM. The provider code I searched does not resolve those binaries with `shutil.which`, so whether this happens is unverified. Task 9 should treat any missing-executable error as a setup problem to fix and rerun, and should record the probe's error text.

### [CONCERN] `list_case_sets()` has no test

Task 15 adds `list_case_sets()` (line 160), but none of the tests on lines 161-162 call it. The design lists it in the store contract (design line 284), which 422 consumes (design line 290). The design also does not say whether it returns every version or only the latest per name, so the task should state that before the test is written.

### [NOTE] Task 9's success criterion cannot be met on the no-alias branch

Line 112 says a profile with no alias is recorded in the DEVLOG "instead of an answer," but line 115 requires "a yes or no for each of `sdk` and `openai-oauth`." Reword line 115 as "a yes or no, or a recorded no-alias entry, for each profile."

### [NOTE] Task 3's commit bundles Task 2's config key and the design correction

The marker on line 62 (`feat: let ProcessRunner replace the child environment`) comes after Task 2, which adds a config key, and Task 3 also edits the slice design. Planning-document edits belong in their own `docs:` commit under the commit rules. Split the design correction out, or make the commit message cover the config key.

### [NOTE] Task 14's tamper sentence is missing its verb

"A tampered file never comes back as `None`, `list_cases(project_id)` (skips a mismatching file with a WARNING)" has no verb for `list_cases`. Rewrite it as "A tampered file never comes back as `None` from `get_case`; `list_cases(project_id)` skips it with a WARNING."

### [NOTE] Task 28 does not name the historical REV

The design's walkthrough uses `v0.20.0` as a draft command (design line 337). The tag exists in `.git/refs/tags/`, but I could not confirm that the commit contains `uv.lock`, and Step 2's expected result depends on it. Name the REV in the task, and make `git show $REV:uv.lock` the first action so the step fails clearly if the lock is absent.

### [NOTE] Task 11 bundles a sweep API change that only Task 25 uses

`sweep_orphans` (`src/squadron/replay/sandbox.py:235`) gains `sweep_cf_projects` and `sibling_suffixes` here, and only Task 25 calls it with the new values. Moving those parameters and their tests into Task 25 would keep Task 11 a pure extraction, which is what its "no test edits" check is meant to confirm. D4 places them here, so keep them if you prefer the design's grouping.

### [NOTE] Two modules are outside the design's component list

`reporter_format.py` (Task 20, line 200) and `alias_profile.py` (Task 6, line 86) are not in the design's Component Structure (design lines 74-95). Task 29 (line 285) records them, so the documents agree. `reporter_format.py` holds two constants and a tuple, which could live in `python_failure.py` (it consumes `REPORT_KEYS`) to avoid a module.

### [NOTE] The load-test justification leaves out the environment-layer trigger

The design restates no NFR, so no load-test finding is raised. The project's Python rules, however, require `tests/load/` coverage for "environment-layer paths," and this slice's environment resolution and scrubbed environment may fall under that. Line 38 should say why they do not.

### [PASS] Every design success criterion has a task

Mapped: case round trip and id (Tasks 12, 14); idempotent writes and case sets (14, 15); historical lock hash (18, 25, 28); no-lockfile and stale-lock failures (17, 18); scrubbed-environment allowlist (5, 26); auth-check yes/no/timeout (7, 8, 9); suite `NodeResult` and every `FailureKind`, including timeout (22, 23); ruff, pyright and unchanged replay tests (11, 29); failure-path tests (18, 22); replay behavior (10, 11, 28). Out-of-scope items (422–426 work, the `/sq:benchmark` command) appear in no task.

### [PASS] The design correction is right and tasked

`SubprocessRunner.run` merges `os.environ` under the caller's `env` (`merged_env = {**os.environ, **env}`), so the design's claim that `env=` alone applies the scrub is wrong. Task 3 adds `replace_env` and corrects both design bullets (design lines 64 and 174).

### [PASS] Sequencing respects dependencies, and the referenced code exists

The auth spike (2–9) comes first. Extraction (11) precedes the sweep call (25). Records (12–15) precede the store. Adapter types (16) precede fixtures (17) and the Python adapter (18). The plugin format (20) precedes classification (21). The suite runner (22) precedes the sandbox (25), which precedes the CLI (27). There are no cycles. Code the tasks depend on exists: `MetrologyStoreError` (`metrology/errors.py:35`), `SandboxError` (`replay/sandbox.py:52`), `ProfileName`, `ProviderProfile.api_key_env`, `SourceLanguage`, `CONFIG_KEYS`, `ProcessTimedOutError`, `ProcessNotFoundError`, and `one_shot_dispatch`. `resolve_model_alias` returns `tuple[str, str | None]` (`models/aliases.py:227`), which Task 6 handles. `sandbox.py` is 298 lines, so Task 11's conditional module split is needed.

### [PASS] Test-with, checkbox and commit-marker conventions are followed

Each implementation task is followed by its tests. Every item and sub-item has a checkbox. The ten `**Commit**:` markers (after Tasks 3, 5, 9, 11, 15, 18, 24, 26, 27 and 29) sit at working points, and there is no commit after every task. The file has no merge or push task; Task 1 only creates the branch.

### Run Digest

- Response length: 10252 chars
- Response is newline-free: no
- Tool calls made: 20
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 21
- Tokens — prompt / cached / cache write / completion / reasoning: 733773 / 564100 / 169661 / 60602 / not computed
- Duration: 256.7 s
- Cost: $0.34 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15

## Resolution

- **[concern] Task 11 replay test count:** Task 11's verify step now expects the Task 10 count plus the new tests in `test_history_free_sandbox.py`, and checks that only files were added under `tests/replay`. Task 3, Task 25 and Task 29 now say existing replay tests are unmodified.
- **[concern] Empty JSONL valid at any exit code:** Task 22 accepts an empty file only for exit 5 (`all_tests()`) or exit 4 (`nodes(ids)`, each id `error` / `collection_error`). Any other exit code, including 0, raises `SuiteRunError`. The scripted-runner tests cover each case.
- **[concern] Missing runtime binary recorded as an auth `no`:** Task 7 adds a preflight `sq --version` under the throwaway environment. A binary that cannot start there raises `ProbeStartError` and no row is produced. The Task 8 CLI prints it, and a Task 7 test covers it.
- **[concern] `list_case_sets()` untested:** Task 15 pins it as every version of every set in name-then-version order, and adds a test.
- **[note] Task 9 no-alias branch:** the success criterion now accepts a yes, a no, or `no alias` per profile.
- **[note] Task 3 commit bundling:** Task 2 has its own commit again, and the design correction is a separate bullet with its own `docs:` commit after Task 3's code commit.
- **[note] Task 14 missing verb:** split into two sentences: a tampered file never returns `None`, and `list_cases` skips a mismatching file with a WARNING.
- **[note] Task 28 REV:** Task 28 sets `REV=$(git log --format=%h -n1 v0.20.0)` (checked: `v0.20.0` contains `uv.lock`) and names the stale-lock test and the `no_lockfile` case for step 5.
- **[note] Sweep API change in Task 11:** moved to Task 25 with its tests, the only consumer. Task 25 reruns the replay tests to prove behavior is unchanged.
- **[note] Two modules outside the design's component list:** removed both. `resolve_alias_profile` moves into `auth_check.py` (created in Task 6). The reporter constants move into `python_failure.py` (created in Task 20). Task 29 lists only the new errors and `sweep_benchmark_orphans` for the design update.
- **[note] Load-test justification:** rejected the "no load test" claim. Task 26 now adds `tests/load/test_benchmark_sandbox_concurrency.py` (three concurrent sandboxes sharing the uv cache while the sweep runs), and the Context Summary says why.
- **[pass] Every design success criterion has a task, design correction right and tasked, sequencing, conventions:** no change needed.
