---
docType: review
layer: project
reviewType: code
slice: test-suite-machine-state-isolation
targetKind: slice
rulesSource: project
project: squadron
verdict: PASS
verdictSource: stated
sourceDocument: project-documents/user/slices/923-slice.test-suite-machine-state-isolation.md
aiModel: z-ai/glm-5.3-flash
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 2a94ee19d0ad3b3c6d8a1e5b76ed500067efb320
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 5
findings:
  - id: F001
    severity: pass
    category: test-coverage
    summary: "Import-time host reads eliminated mechanically, not just manually"
    location: "tests/test_import_purity.py:61"
  - id: F002
    severity: pass
    category: test-coverage
    summary: "Hermetic fixture ordering contract is stated and honored"
    location: "tests/conftest.py:31"
  - id: F003
    severity: pass
    category: error-handling
    summary: "Hostile-env script handles its own failure modes observably"
    location: "scripts/test-hostile-env:1"
  - id: F004
    severity: note
    category: error-handling
    summary: "tzset is not re-run on fixture teardown"
    location: "tests/conftest.py:60"
  - id: F005
    severity: note
    category: design
    summary: "Scanner's guarantee is narrower than its docstring"
    location: "tests/test_import_purity.py:7"
  - id: F006
    severity: note
    category: test-coverage
    summary: "Module-level mutable test state"
    location: "tests/test_hermetic.py:14"
---

# Review: code — slice 923

**Verdict:** PASS
**Model:** z-ai/glm-5.3-flash

## Findings

### [PASS] Import-time host reads eliminated mechanically, not just manually

The AST scanner (`_module_level_calls` / `_is_forbidden`) correctly handles class bodies, defaults, and decorators, and is itself tested with parametrized positive and negative cases — so the refactor can't silently regress. The choice to convert module constants to zero-arg functions (`_user_manifest()`, `default_receipts_dir()`, etc.) rather than introduce a settings object is the minimal change consistent with the existing per-module design.

### [PASS] Hermetic fixture ordering contract is stated and honored

The docstring documents that a test's own `monkeypatch.setenv` wins over the autouse fixture, and `tests/cli/test_env_file.py` correctly binds the real `_load_env_file` at collection time (before the fixture patches the module attribute), so the one unpatched path is genuinely tested. The `importlib.import_module` comment about the package re-export is accurate per `src/squadron/cli/__init__.py:5`.

### [PASS] Hostile-env script handles its own failure modes observably

Every step funnels through `fail` with a step name, the config probe verifies the hostile state is actually live before the suite runs (rather than trusting the setup), ANSI codes from `FORCE_COLOR` are stripped before parsing, and `PIPESTATUS[0]` preserves pytest's exit code through `tee`. Credential sentinel values are derived from the provider registry rather than duplicated (`DRY`), matching `_hermetic.credential_env_vars()`.

### [NOTE] tzset is not re-run on fixture teardown

`hermetic_environment` calls `time.tzset()` after setting `TZ`, but `monkeypatch` teardown restores the `TZ` env var without a matching `tzset()`. Code running between a test's teardown and the next test's setup (finalizers, conftest code computing local time) sees libc's cached Asia/Kolkata offset while `os.environ["TZ"]` says the original. Impact is negligible in a sequential run since every test re-tzsets, but a `yield`-based fixture that re-runs `tzset()` in the finalizer would make the state transition exact.

### [NOTE] Scanner's guarantee is narrower than its docstring

The module docstring says importing squadron "must not read the home directory or `.env`", but the scanner only detects `Path.home()` and `load_dotenv`. Other import-time host reads (e.g. `os.environ[...]`, `os.getcwd()`, `socket.gethostname()`) would pass. That's an acceptable ratchet starting point, but the docstring could state the narrower contract to avoid implying full coverage.

### [NOTE] Module-level mutable test state

`_homes_seen: list[Path]` is shared across the two parametrized runs of `test_home_is_fresh_per_test`, making that test order- and run-count-dependent (and breaking under pytest-xdist). The per-run uniqueness it checks is valuable; capturing the home per run via a fixture or comparing `Path.home()` against a fixed set at session scope would be more robust. Minor, since the default single-process run is the supported mode.

### Run Digest

- Response length: 3831 chars
- Response is newline-free: no
- Tool calls made: 5
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 8094
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
