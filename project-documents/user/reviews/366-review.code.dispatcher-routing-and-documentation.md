---
docType: review
layer: project
reviewType: code
slice: dispatcher-routing-and-documentation
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/366-slice.dispatcher-routing-and-documentation.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261020
dateUpdated: 20261020
reviewedSha: bb9f64954ba5f418b31a28b3c17bd8893e6cf6b1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 1
diffTruncated: false
turns: 2
promptTokens: 168642
cachedTokens: 124347
cacheWriteTokens: 44291
completionTokens: 2595
durationSeconds: 22.5
costUsd: 0.218016
costBasis: provider
squadronVersion: 0.23.5
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Malformed plugin entries crash the probe instead of reporting null"
    location: "src/squadron/probe/surfaces.py:105-125"
  - id: F002
    severity: concern
    category: testing
    summary: "Unreadable-file test depends on file permissions"
    location: "tests/probe/test_surfaces.py:69-78"
  - id: F003
    severity: note
    category: error-handling
    summary: "Warnings reach stderr only if logging is configured"
    location: "tests/cli/test_probe.py:48-58"
  - id: F004
    severity: note
    category: correctness
    summary: "Import-time assert is stripped under `python -O`"
    location: "src/squadron/probe/surfaces.py:152"
  - id: F005
    severity: note
    category: style
    summary: "Missing `from __future__ import annotations` in new modules"
    location: "src/squadron/probe/__init__.py:1"
  - id: F006
    severity: note
    category: error-handling
    summary: "`project_root` silently falls back to `cwd`"
    location: "src/squadron/probe/graph.py:26-30"
  - id: F007
    severity: pass
    category: design
    summary: "Design, exception handling and test coverage"
    location: "src/squadron/cli/commands/probe.py:20-33"
---

# Review: code — slice 366

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Malformed plugin entries crash the probe instead of reporting null

`_claude_plugin_installed` checks that each `plugins` value is a list. It does not check that the list items are dicts. `_plugin_entry_applies` then calls `entry.get(...)` on each item. A registry like `{"plugins": {"understand-anything@m": ["x"]}}` raises `AttributeError`. The CLI turns that into exit 1. The contract and docstring say fields the probe cannot determine are null with a warning. The `cast(dict[str, list[dict[str, object]]], ...)` hides the unchecked assumption. The parametrized "unexpected shape" test does not cover a list of non-dicts. Validate the entry type (`isinstance(entry, dict)`) in the shape check, and add a test case for it.

### [CONCERN] Unreadable-file test depends on file permissions

`chmod(0o000)` does not make a file unreadable when the suite runs as root, which is common in CI containers. It also does nothing on Windows. In those cases `read_text` succeeds, the result is `True`, and the test fails for an environmental reason. Skip the test when `os.geteuid() == 0`, or simulate the failure by monkeypatching `Path.read_text` to raise `OSError`.

### [NOTE] Warnings reach stderr only if logging is configured

The `probe` docstring promises a warning on stderr. The warnings are emitted through `logging`, and the test checks them with `caplog`. Nothing asserts they reach stderr, so this relies on Python's last-resort handler or the CLI's logging setup. A test that checks `result.stderr` would confirm the promise and the "stdout stays pure JSON" guarantee.

### [NOTE] Import-time assert is stripped under `python -O`

The coverage check `assert set(SURFACES) == set(CommandTarget)` disappears when Python runs with `-O`. `tests/probe/test_surfaces.py::test_every_target_has_a_surface_with_contract_keys` already covers the same condition, so this is low risk. A plain `if ...: raise RuntimeError` would be more robust, or the assert could be dropped as redundant.

### [NOTE] Missing `from __future__ import annotations` in new modules

`cli/commands/probe.py` has `from __future__ import annotations`, but the new `probe/*` and `skills/dispatcher.py` modules do not. The Python rules ask for it on 3.12/3.13 projects. The modules use no forward references, so nothing breaks today.

### [NOTE] `project_root` silently falls back to `cwd`

When `git rev-parse --show-toplevel` fails (not a repo, or git missing), `project_root` returns `cwd` with no log. The later `commits_behind unknown` warning only fires if a graph is present. If there is no graph, nothing records that git failed. This is acceptable for a probe, but a DEBUG or WARNING log would make the failure observable.

### [PASS] Design, exception handling and test coverage

The broad `except Exception` carries a `noqa: BLE001` and sits at a process boundary. It reports on stderr and exits 1, which matches rule (c). Contract strings live only in `SurfaceSpec`. `dispatcher_skills` is shared between the probe and the drift test, which avoids duplication. The contract test compares the output against the real contract document. Plugin detection is tested against a real-format fixture. Lines fit the project's configured 104-character limit.

## Response (20261020)

All six findings were checked against the code. F001, F002 and F005 are fixed; F003 was verified and needs no change; F004 and F006 are declined.

- **F001: accepted.** The plugin-registry shape check now also requires every list item to be an object, so `{"plugins": {"understand-anything@m": ["x"]}}` yields `null` with a WARNING instead of an `AttributeError` and exit 1. New test case `entry-not-an-object`.
- **F002: accepted.** `test_unreadable_dispatcher_is_unknown` no longer relies on `chmod`; it patches `Path.read_text` to raise `PermissionError` for the dispatcher file, so it behaves the same as root and on Windows.
- **F003: no change.** Run from the real CLI in a directory with a malformed `meta.json`, the warning reaches stderr and stdout is a single parseable JSON line, exit 0. Python's last-resort handler delivers it because the CLI does not configure logging. A test that pins this would assert Python's default, not squadron behaviour; the `caplog` tests already assert the warning is emitted.
- **F004: declined.** The `assert` mirrors the existing `DELIVERIES` assert in `skills/targets.py`, which the task specified, and `test_every_target_has_a_surface_with_contract_keys` covers the same condition regardless of `-O`.
- **F005: accepted.** `from __future__ import annotations` added to the four `squadron.probe` modules and `skills/dispatcher.py`, per `python.md`.
- **F006: declined.** Running outside a git repository is an expected state, not a fault, and every probe from `/tmp` would log a warning. The case that matters is already observable: with a graph present, the failed git call produces a `commits_behind unknown` WARNING, and the commit is null otherwise.

### Run Digest

- Response length: 3735 chars
- Response is newline-free: no
- Tool calls made: 1
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 2
- Tokens — prompt / cached / cache write / completion / reasoning: 168642 / 124347 / 44291 / 2595 / not computed
- Duration: 22.5 s
- Cost: $0.22 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
