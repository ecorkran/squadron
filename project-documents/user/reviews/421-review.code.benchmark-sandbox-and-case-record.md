---
docType: review
layer: project
reviewType: code
slice: benchmark-sandbox-and-case-record
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/421-slice.benchmark-sandbox-and-case-record.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 1a06605b992563bd40e0f9ab6a4ce36d8386f42d
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 2
diffTruncated: false
turns: 3
promptTokens: 293995
cachedTokens: 28672
cacheWriteTokens: 265319
completionTokens: 3693
durationSeconds: 33.9
costUsd: 1.110933
costBasis: provider
runId: run-20261106-p6-c694d0bf
squadronVersion: 0.24.23
categoriesNormalized: true
findings:
  - id: F001
    severity: pass
    category: correctness
    summary: "Atomic versioned case-set creation and tamper detection"
    location: "src/squadron/metrology/store.py (create_record)"
  - id: F002
    severity: pass
    category: security-hygiene
    summary: "Scrubbed environment and exception handling follow the project rules"
    location: "src/squadron/core/process_runner.py"
  - id: F003
    severity: note
    category: architectural-decay
    summary: "`_stderr_exit` is duplicated across two CLI modules"
    location: "src/squadron/cli/commands/benchmark_sandbox.py:33"
  - id: F004
    severity: note
    category: consistency-rot
    summary: "Reporter constants are duplicated by necessity and guarded by a test"
    location: "src/squadron/benchmark/pytest_reporter/squadron_benchmark_reporter.py:24"
  - id: F005
    severity: note
    category: performance-resource
    summary: "Latest case-set lookup probes versions one file at a time"
    location: "src/squadron/metrology/benchmark_store.py (get_case_set)"
  - id: F006
    severity: note
    category: type-contract-debt
    summary: "`compute_case_id` takes untyped `**identity: Any`"
    location: "src/squadron/metrology/benchmark_models.py:119"
---

# Review: code — slice 421

**Verdict:** PASS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Atomic versioned case-set creation and tamper detection

I read the surrounding store code. `create_record` writes to a uniquely named temp file and publishes it with `os.link`, so a losing concurrent writer gets `FileExistsError` and `write_case_set` re-reads and retries. The temp name (`<id>.json.<hex>.tmp`) doesn't match the `*.json` glob in `_iter_records`, so in-flight writes can't be listed as records. `BenchmarkCase` rejects a stored `case_id` that doesn't match its content, and `_load` surfaces that as `MetrologyStoreError`. Tests cover the race and a hand-edited file.

### [PASS] Scrubbed environment and exception handling follow the project rules

`replace_env=True` requires `env` and passes it unchanged. `ScrubbedEnvironment.variables` builds the child environment from an explicit allowlist, and `MissingCredentialError` fails explicitly with no silent fallback. The one broad catch, `except Exception` with `# noqa: BLE001` in `_auth-probe`, is a documented process-boundary handler. The other handlers catch specific types and either re-raise as a named error or log. Lines stay within the 104-column limit in `pyproject.toml:78`.

### [NOTE] `_stderr_exit` is duplicated across two CLI modules

Identical `_stderr_exit` helpers exist in `benchmark.py` and `benchmark_sandbox.py`. Moving it to a shared CLI helper would give it one definition. This isn't blocking.

### [NOTE] Reporter constants are duplicated by necessity and guarded by a test

`REPORT_KEYS` and `REPORT_PATH_ENV` are repeated in `python_failure.py` because the plugin runs inside the sandboxed project's environment. `test_plugin_constants_match_the_harness` catches drift, and another test confirms the plugin imports only the standard library and pytest. The tradeoff is acceptable.

### [NOTE] Latest case-set lookup probes versions one file at a time

Finding the latest version loads each version file in turn, so it costs O(versions) reads, and a missing version in the middle of the sequence would end the search early. That is fine at the expected scale. If sets accumulate many versions, a directory glob on the name hash would be cheaper.

### [NOTE] `compute_case_id` takes untyped `**identity: Any`

The keyword set is enforced only at runtime, when `_canonical_identity` raises `TypeError` on a mismatch. Both callers build it from `IDENTITY_FIELDS`, and the round-trip and each-field tests cover it. A typed identity dataclass would remove the `Any`.

### Run Digest

- Response length: 3029 chars
- Response is newline-free: no
- Tool calls made: 2
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 3
- Tokens — prompt / cached / cache write / completion / reasoning: 293995 / 28672 / 265319 / 3693 / not computed
- Duration: 33.9 s
- Cost: $1.11 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Responses

- **F003 (fixed):** `stderr_exit` now lives once in `cli/commands/benchmark_common.py`, and both benchmark command modules use it. 422 and later add more benchmark commands, so the duplicate would have grown.
- **F004 (accepted):** The duplication is deliberate (the plugin runs inside the sandboxed project's environment) and a test guards drift. No change.
- **F005 (declined):** Versions are never rewritten or deleted, so the walk cannot hit a gap, and the cost is fine at expected set sizes. No change.
- **F006 (declined):** Both callers build the identity from `IDENTITY_FIELDS` and tests cover the round trip and each field. A typed identity dataclass would add a second definition of the same field list.
