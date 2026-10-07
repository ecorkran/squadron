---
docType: review
layer: project
reviewType: code
slice: run-liveness-stall-bounds-pruning-and-readable-listings
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/174-slice.run-liveness-stall-bounds-pruning-and-readable-listings.md
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20261007
dateUpdated: 20261007
reviewedSha: ba637c2e3e62b8437832cd5aff6e92479214f504
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 35
diffTruncated: false
turns: 20
promptTokens: 2456353
cachedTokens: 2159795
completionTokens: 3247
reasoningTokens: 0
durationSeconds: 132.0
squadronVersion: 0.21.0
findings:
  - id: F001
    severity: pass
    category: uncategorized
    summary: "Clean separation of concerns in the heartbeat/observer pattern"
    location: "src/squadron/pipeline/run_heartbeat.py:36-82"
  - id: F002
    severity: pass
    category: uncategorized
    summary: "Failure-mode enumeration is observable"
    location: "src/squadron/pipeline/state.py:412-420"
  - id: F003
    severity: pass
    category: uncategorized
    summary: "Heartbeat interval must be positive, validated at the read seam"
    location: "src/squadron/config/manager.py:143-148"
  - id: F004
    severity: pass
    category: uncategorized
    summary: "Liveness assessment is pure and the process check is injected"
    location: "src/squadron/pipeline/run_liveness.py:73-95"
  - id: F005
    severity: pass
    category: uncategorized
    summary: "`scan_runs` keeps unreadable files observable rather than hiding them"
    location: "src/squadron/pipeline/state.py:662-680"
  - id: F006
    severity: pass
    category: uncategorized
    summary: "Prune protection rule is single-sourced"
    location: "src/squadron/pipeline/run_prune.py:166-170"
  - id: F007
    severity: pass
    category: uncategorized
    summary: "Path-traversal protection in apply_prune"
    location: "src/squadron/pipeline/run_prune.py:236-239"
  - id: F008
    severity: note
    category: uncategorized
    summary: "`init_run` writes the owner in the creating write, but the resume claim still calls `state_mgr.claim(...)` before the heartbeat task starts"
    location: "src/squadron/cli/commands/run.py:230-256"
  - id: F009
    severity: note
    category: uncategorized
    summary: "`None` liveness falls through to the heartbeat rule by design"
    location: "src/squadron/pipeline/run_liveness.py:85-94"
  - id: F010
    severity: note
    category: uncategorized
    summary: "`run_prune.parse_duration` accepts trailing whitespace via the regex's `\\s*` but not internal whitespace"
    location: "src/squadron/pipeline/run_prune.py:257-258"
  - id: F011
    severity: note
    category: uncategorized
    summary: "`active_item.index` is stringified at the observer seam"
    location: "src/squadron/pipeline/executor.py:1623-1629"
  - id: F012
    severity: pass
    category: uncategorized
    summary: "Test naming and structure follow project conventions"
    location: "tests/pipeline/test_run_*.py, tests/cli/test_*.py"
  - id: F013
    severity: pass
    category: uncategorized
    summary: "Linting hooks preserved"
    location: "src/squadron/cli/columns.py:1-20, src/squadron/pipeline/run_liveness.py:1-15"
  - id: F014
    severity: pass
    category: uncategorized
    summary: "Single source of truth for the schema-version constant"
    location: "src/squadron/pipeline/state.py:51-52"
  - id: F015
    severity: pass
    category: uncategorized
    summary: "Configuration keys have one definition and one default"
    location: "src/squadron/config/keys.py:18-19, 130-153"
---

# Review: code — slice 174

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [PASS] Clean separation of concerns in the heartbeat/observer pattern

The `RunHeartbeat` async context manager cleanly isolates the heartbeat loop from the executor. `_report_crash` only logs the unexpected error path; the `__aexit__` correctly swallows both `CancelledError` and the already-logged `Exception` (with the inline comment justifying each). `_beat` is purely a sleep/write loop, and the `interval` parameter is read once on enter.

### [PASS] Failure-mode enumeration is observable

`_write_progress` only catches `STATE_READ_ERRORS` (a narrow, named set); any other exception (a `TypeError` from a serialisation defect, for example) propagates. This is exactly the asymmetry the project's exception-handling rule calls for: expected I/O failures are logged at WARNING and do not kill the run; unexpected defects are not swallowed. There is a test (`test_non_io_error_propagates` in test_state.py) that asserts the propagation.

### [PASS] Heartbeat interval must be positive, validated at the read seam

`get_positive_int_config` raises `ValueError` naming the key. A non-positive value is genuinely a configuration defect (a zero/negative interval would make the run stale immediately), so failing loudly at the read seam rather than at the write seam is correct.

### [PASS] Liveness assessment is pure and the process check is injected

`assess_liveness` takes the process check and `now` as injected parameters, which is what makes the unit tests reliable: a faked `process_alive` makes a same-host orphan testable without real PIDs. The "orphaned wins over stale" precedence is documented and tested.

### [PASS] `scan_runs` keeps unreadable files observable rather than hiding them

Unlike `list_runs`, `scan_runs` returns unreadable files in a separate `unreadable` list with reason and mtime, so `sq runs prune --status unreadable` can act on them. This is the right shape: silently dropping an unreadable file would be a silent failure.

### [PASS] Prune protection rule is single-sourced

`_protection_allows` is the only place the rule is expressed, and it is expressed once as `(categories & PROTECTED_CATEGORIES) <= selected`. No conditionals elsewhere override it; named runs always bypass protection (with a refusal for live ones). The tests exercise both directions.

### [PASS] Path-traversal protection in apply_prune

`apply_prune` resolves `runs_dir` once, and `_delete` refuses any path that is not inside that root. A test (`test_never_deletes_outside_the_runs_dir`) pins this. The refusal is logged at ERROR so the operator can see the path that was rejected.

### [NOTE] `init_run` writes the owner in the creating write, but the resume claim still calls `state_mgr.claim(...)` before the heartbeat task starts

For a new run, `init_run(..., owner=owner)` writes the owner in the same write as the initial `running` record (D13). For a resume, `RunHeartbeat.__aenter__` calls `state_mgr.claim(...)` before spawning the task. If the claim raises (the run is already live on another host), it propagates before any of the executor's bookkeeping is touched, which is the correct "the run was never ours to finalize" invariant. The comment in `run.py:252` names the invariant; the test in `test_cli_integration.py` (`test_claim_refuses_a_live_owned_run` in test_state.py) covers it.

### [NOTE] `None` liveness falls through to the heartbeat rule by design

When the process check returns `None` (unknown — e.g. a non-positive PID, an unexpected `OSError`), the assessment falls through to the heartbeat check rather than being reported as unknown. The test `test_unknown_process_falls_through_to_heartbeat` pins this. The reasoning is that "unknown process liveness" is information about the check, not about the run, and a stale heartbeat is still actionable evidence.

### [NOTE] `run_prune.parse_duration` accepts trailing whitespace via the regex's `\s*` but not internal whitespace

`r"^\s*(\d+)\s*([a-z])\s*$"` accepts ` 2H ` and `30s` but not `2 H` or `7 d`. The test `test_parse_duration_rejects` only checks the unhappy paths. A test like `"2 H"` would document this either way; right now it is implicit. Not a bug, just an under-pinned edge of the grammar.

### [NOTE] `active_item.index` is stringified at the observer seam

The executor normalises `item.get("index")` to a string before handing it to `ActiveItem`. This means a slice number `182` (int) and the string `"182"` round-trip the same way. The test in `test_executor_each.py` exercises the int path; it would be useful to also assert the string path explicitly. No functional issue.

### [PASS] Test naming and structure follow project conventions

`test_*.py` files, `ClassTest` grouping, `pytest.mark.parametrize` for both happy and unhappy paths, real PID fixtures (`exited_pid()`) instead of faked PIDs, and the new `walkthrough_seed.py` lives under `tests/pipeline/` and is documented as a manual walkthrough tool rather than a test.

### [PASS] Linting hooks preserved

Both new files include the `from __future__ import annotations` header, full type hints, no bare `except:`, and explicit logging at WARNING/ERROR levels. The exception-handling in `apply_prune` and `_write_progress` uses narrow types and has justifying comments.

### [PASS] Single source of truth for the schema-version constant

`_SCHEMA_VERSION = 5` and `_SUPPORTED_SCHEMA_VERSIONS = {3, 4, 5}` are module-level constants, not scattered. The test `test_unsupported_schema_raises` is updated to check `6` rather than `5`, so the upgrade is mechanically checked.

### [PASS] Configuration keys have one definition and one default

`FOREGROUND_IDLE_TIMEOUT_KEY` and `RUN_HEARTBEAT_INTERVAL_KEY` are defined once at module top, registered in `CONFIG_KEYS`, and consumed via the named constants. No string-literal scattering. The tests in `test_keys.py` exercise both happy and `ValueError` paths.

### Verdict
The slice is consistent with the project's style, error-handling rules, and software-design principles. Tests are written alongside implementation, failure modes are observable, the SOLID seams are respected, and the protection rules in prune are single-sourced. The observations above are minor and do not meet the threshold of CONCERN.

### Run Digest

- Response length: 7426 chars
- Response is newline-free: no
- Tool calls made: 35
- Tool calls failed: 0
- Stop reason: stop
- Output budget: 512000 tokens
- System prompt: custom
- Settings sources: n/a (non-SDK)
- Reasoning characters: 0
- Effort: backend default
- Turns: 20
- Tokens — prompt / cached / completion / reasoning: 2456353 / 2159795 / 3247 / 0
- Duration: 132.0 s
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 15
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 15
- Finding-shaped matches — surviving validation: 15
