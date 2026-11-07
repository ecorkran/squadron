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
reviewedSha: 7572a918c572c895b9da1f308e072a65d09368b3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
diffTruncated: false
turns: 5
promptTokens: 503954
cachedTokens: 334664
cacheWriteTokens: 169284
completionTokens: 4671
durationSeconds: 39.9
costUsd: 0.76675
costBasis: provider
runId: run-20261106-p6-c694d0bf
squadronVersion: 0.24.23
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: security-hygiene
    summary: "Dependency install runs with the full harness environment"
    location: "src/squadron/benchmark/python_adapter.py#_install"
  - id: F002
    severity: concern
    category: correctness
    summary: "Concurrent `write_case_set` can silently overwrite a version"
    location: "src/squadron/metrology/benchmark_store.py#write_case_set"
  - id: F003
    severity: concern
    category: error-handling-observability
    summary: "A truncated final report line makes a timed-out run raise instead of returning partial results"
    location: "src/squadron/benchmark/python_suite.py#_read_report"
  - id: F004
    severity: note
    category: security-hygiene
    summary: "Carried credentials are symlinks to the real files"
    location: "src/squadron/benchmark/scrubbed_env.py#_link_carryover"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "`ProcessRunner` protocol gained a parameter that existing fakes do not declare"
    location: "tests/codehost/fake_runner.py:48"
  - id: F006
    severity: note
    category: architectural-decay
    summary: "Duplicated identity-field plumbing in `BenchmarkCase`"
    location: "src/squadron/metrology/benchmark_models.py:127-170"
  - id: F007
    severity: note
    category: consistency-rot
    summary: "Misleading error type for missing `HOME`"
    location: "src/squadron/benchmark/scrubbed_env.py#_require"
  - id: F008
    severity: note
    category: performance-resource
    summary: "Orphan sweep skips siblings whose tree directory is missing"
    location: "src/squadron/replay/sandbox.py#_sweep_directories"
  - id: F009
    severity: pass
    category: test-debt
    summary: "Core design and test coverage"
    location: "src/squadron/benchmark"
---

# Review: code — slice 421

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Dependency install runs with the full harness environment

`uv sync --locked` runs with `ctx.runner.run(INSTALL_ARGV, ...)` and no `replace_env`, so it inherits the whole harness environment (`GH_TOKEN`, `SSH_AUTH_SOCK`, API keys). `uv sync` can run build backends and `setup.py` code from the project at the sandbox commit, so that code sees every harness secret. The scrub is the slice's central guarantee. The comment justifies the choice (uv cache and network settings), but the cost is not mentioned. Pass an explicit allowlist for the install, such as the uv cache and proxy variables, instead of everything. Alternatively, document this as an accepted trust boundary for benchmarked repositories.

### [CONCERN] Concurrent `write_case_set` can silently overwrite a version

The method reads the latest version, computes `latest + 1`, then writes with `write_record`. Two writers racing on the same name both pick the same version, and the second atomically replaces the first with a different `case_ids` list. That breaks the "versions are immutable" contract. Use an exclusive-create write (fail if the record exists) for case-set versions, or retry on collision.

### [CONCERN] A truncated final report line makes a timed-out run raise instead of returning partial results

On timeout the runner kills pytest, which may happen mid-`write` of a JSONL line. `_read_report` then raises `SuiteRunError` and discards every result already recorded. The module docstring promises that the lines written so far are kept. When `timed_out` is true, tolerate an unparseable final line (log a WARNING and drop it). Keep raising for any other malformed line.

### [NOTE] Carried credentials are symlinks to the real files

A producer in the sandbox can write through the symlink and corrupt the user's real `~/.claude/.credentials.json` or `~/.codex/auth.json`. `auth-check` detects replacement of the link, but a write through it goes undetected. This looks like a deliberate trade-off (D8), so it is worth stating explicitly in the docs.

### [NOTE] `ProcessRunner` protocol gained a parameter that existing fakes do not declare

I could not run pyright here, so this is unverified. The fake runners in `tests/codehost/fake_runner.py` and similar files omit `replace_env`. If any is passed where a `ProcessRunner` is expected, strict pyright reports a protocol mismatch.

### [NOTE] Duplicated identity-field plumbing in `BenchmarkCase`

`_identity_id` and `build` both spell out the ten identity fields to call `compute_case_id(**identity: Any)`. `compute_case_id` is untyped (`Any`) at the identity boundary. A frozen identity dataclass would remove the duplication and restore type checking.

### [NOTE] Misleading error type for missing `HOME`

`_require("HOME")` raises `MissingCredentialError`, but `HOME` is not a credential. The message "credential variable HOME not set" is misleading. A distinct error, or a more general name, would be clearer.

### [NOTE] Orphan sweep skips siblings whose tree directory is missing

`.home` and `.out` directories are removed only when the owning tree directory exists. If a crash happens after the lock is written but before the tree is created, the siblings and the lock persist. The lock is also never cleaned up in that case, because the loop iterates only over directories.

### [PASS] Core design and test coverage

Exception handling follows the project's rules: specific types, logged failures, and a justified `noqa: BLE001` at the `_auth-probe` process boundary. The new config keys are centralized, and the adapter seam keeps concrete adapters behind the registry. The extraction of `HistoryFreeSandbox` leaves replay behavior intact. Tests cover real pytest classification, timeouts, scrub shape, the store's tamper detection, and a load test for concurrency. Line lengths are within the configured limit of 104.

### Run Digest

- Response length: 4666 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 503954 / 334664 / 169284 / 4671 / not computed
- Duration: 39.9 s
- Cost: $0.77 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
