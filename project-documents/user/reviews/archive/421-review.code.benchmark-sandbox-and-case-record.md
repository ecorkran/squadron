---
docType: review
layer: project
reviewType: code
slice: benchmark-sandbox-and-case-record
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 179e9eabb99998118817484b1024d126db6e3319
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
diffTruncated: false
turns: 4
promptTokens: 472266
cachedTokens: 193471
cacheWriteTokens: 278789
completionTokens: 2752
durationSeconds: 25.9
costUsd: 1.171843
costBasis: provider
runId: run-20261106-p6-c694d0bf
squadronVersion: 0.24.23
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "`sq benchmark sandbox` leaks a traceback for missing HOME or git/uv"
    location: "src/squadron/cli/commands/benchmark_sandbox.py:90-102"
  - id: F002
    severity: note
    category: correctness
    summary: "Runtime checks in the reporter plugin use `assert`"
    location: "src/squadron/benchmark/pytest_reporter/squadron_benchmark_reporter.py:46-48"
  - id: F003
    severity: note
    category: consistency-rot
    summary: "Venv path duplicated outside the adapter's constant"
    location: "src/squadron/benchmark/python_suite.py:150"
  - id: F004
    severity: note
    category: error-handling-observability
    summary: "Auth-probe boundary catch is justified"
    location: "src/squadron/cli/commands/benchmark.py:56"
  - id: F005
    severity: pass
    category: other
    summary: "Sandbox lifecycle, scrubbing and record store"
    location: "src/squadron/benchmark/sandbox.py"
---

# Review: code — slice 421

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] `sq benchmark sandbox` leaks a traceback for missing HOME or git/uv

`BenchmarkSandbox.__enter__` calls `ScrubbedEnvironment.prepare()`. That raises `MissingHarnessHomeError` when HOME is unset and `MissingHarnessToolError` when `git` or `uv` is not on the harness PATH (`scrubbed_env.py:110-117`). `__enter__` cleans up and re-raises both. `sandbox_command` only catches `EnvironmentResolutionError`, `SandboxError` and `SuiteRunError`, so a user missing `uv` gets a raw Python traceback instead of a clean exit 1. The sibling `auth_check` command does catch both errors. `_git()` also does not translate `ProcessNotFoundError` or `ProcessTimedOutError`, so a missing `git` produces a traceback too. Add these exceptions to the `except` tuple, as `auth_check` does, and add a test for the missing-tool path. No existing test covers it.

### [NOTE] Runtime checks in the reporter plugin use `assert`

`_write` relies on `assert _report_path is not None` and `assert tuple(record) == REPORT_KEYS`. These run inside the sandboxed project's interpreter, so `python -O` or `PYTHONOPTIMIZE` would strip them silently. A `None` path would then fail with a confusing `TypeError` in `open()`. This is low risk because the harness controls the argv. Explicit `raise` statements would be sturdier.

### [NOTE] Venv path duplicated outside the adapter's constant

`python_suite.py` hardcodes `ctx.tree / ".venv" / "bin" / "python"`. `python_adapter.py` defines `VENV_DIR` and `_python()`, and `python_failure.py` has its own `_VENV_DIR`. Three definitions of `.venv` can drift apart. The project's "define a value once" rule suggests exporting one constant or helper.

### [NOTE] Auth-probe boundary catch is justified

`except Exception: # noqa: BLE001` in `_auth-probe` is a process-boundary handler. It re-raises as exit 1 with the exception type and message on stderr, which matches rule (c). Nothing needs to change.

### [PASS] Sandbox lifecycle, scrubbing and record store

- `BenchmarkSandbox.__enter__` cleans up all four paths on any failed enter, and exit honors `keep()`.
- The orphan sweep handles siblings whose owner directory is gone.
- `replace_env` is opt-in, validated, and tested at the runner level.
- The scrubbed environment is built from an allowlist, and missing credentials fail explicitly.
- `BenchmarkCase` ids are content-addressed and verified on read.
- `create_record` publishes via `os.link` to avoid version races, and a test covers the race.
- The tests include real-pytest classification and a load test, and they meet the project's testing and load-tier rules.

### Run Digest

- Response length: 3070 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 472266 / 193471 / 278789 / 2752 / not computed
- Duration: 25.9 s
- Cost: $1.17 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 5
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 5
- Finding-shaped matches — surviving validation: 5
