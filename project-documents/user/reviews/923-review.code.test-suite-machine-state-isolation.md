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
aiModel: minimax/minimax-m3
status: complete
dateCreated: 20260927
dateUpdated: 20260927
reviewedSha: 036e148927841b097bef678c8636c54c1ab4a939
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 41
findings:
  - id: F001
    severity: note
    category: uncategorized
    summary: "Module-level → call-time conversions are consistent across 17 sites"
    location: "src/squadron/cli/commands/skills.py:23"
  - id: F002
    severity: note
    category: uncategorized
    summary: "`DaemonClient.socket_path` default now swallows empty string"
    location: "src/squadron/client/http.py:31"
  - id: F003
    severity: note
    category: uncategorized
    summary: "`test_env_file.py` imports the loader at collection time to bypass the autouse patch"
    location: "tests/cli/test_env_file.py:15"
  - id: F004
    severity: note
    category: uncategorized
    summary: "Hostile-env script writes a `.env` that nothing in the suite reads"
    location: "scripts/test-hostile-env:78"
  - id: F005
    severity: note
    category: uncategorized
    summary: "`host_cf` marker is applied across files but never registered in pytest config"
    location: "tests/documents/test_pr_review_frontmatter.py:143"
  - id: F006
    severity: note
    category: uncategorized
    summary: "`tests/conftest.py` `_load_env_file` patch uses dotted-name import to reach the module"
    location: "tests/conftest.py:59"
  - id: F007
    severity: note
    category: uncategorized
    summary: "`hermetic_environment` runs `time.tzset()` which mutates process-global state"
    location: "tests/conftest.py:43"
  - id: F008
    severity: note
    category: uncategorized
    summary: "`_hermetic.py` `REAL_HOME` is captured at import, not at first use"
    location: "tests/_hermetic.py:32"
  - id: F009
    severity: note
    category: uncategorized
    summary: "`_load_env_file` is now called from the Typer root callback, after parsing"
    location: "src/squadron/cli/app.py:79"
  - id: F010
    severity: note
    category: uncategorized
    summary: "`test_import_purity.py` scanner is intentionally narrow"
    location: "tests/test_import_purity.py:65"
---

# Review: code — slice 923

**Verdict:** PASS
**Model:** minimax/minimax-m3

## Findings

### [NOTE] Module-level → call-time conversions are consistent across 17 sites

Every previously-module-level `_FOO = Path.home() / "..."` constant was converted to a `_foo()` function whose body is the same `Path.home() / "..."` expression. This is the right shape for test-time substitution (the autouse fixture patches `HOME` via `monkeypatch.setenv`, which `Path.home()` reads at call time). `_default_commands_dir()` is duplicated verbatim between `cli/commands/skills.py` and `cli/commands/doctor_checks.py`; the comment in `doctor_checks.py` ("keep the pure check layer free of CLI coupling") is the right rationale, but it is a small DRY violation worth flagging.

### [NOTE] `DaemonClient.socket_path` default now swallows empty string

The previous default `socket_path: str = _DEFAULT_SOCKET` resolved to a non-empty module-level path. The new `socket_path: str | None = None` with `self._socket_path = socket_path or str(Path.home() / ...)` means an explicit `socket_path=""` argument silently falls back to the home default rather than to the empty path. Empty string is not a valid socket path on any platform, so this is unlikely to break a real caller, but it is a quiet semantic change.

### [NOTE] `test_env_file.py` imports the loader at collection time to bypass the autouse patch

The autouse fixture patches `_load_env_file` to a no-op on the module so `.env` reading cannot leak credentials into a test. `test_env_file.py` therefore imports the real function at module top-level (`from squadron.cli.app import _load_env_file`) — before any fixture runs — so its local binding escapes the patch. The structure works because monkeypatch.setattr replaces the module attribute, not the name in the test module's globals, but it does rely on import order (the import statement runs at collection, before fixtures). Worth a follow-up note to anyone tempted to "helpfully" defer the import.

### [NOTE] Hostile-env script writes a `.env` that nothing in the suite reads

The script plants hostile credential values into `$clone/.env` and passes the same values via `env -i`. The autouse hermetic fixture patches `_load_env_file` to a no-op, so the on-disk `.env` is never read by the test suite. The `.env` write is defensive (a future test or plugin that does its own dotenv load would still see hostile values) but is currently dead weight relative to the `env -i` injection. Not a bug — just a slight misdirection about what is doing the work.

### [NOTE] `host_cf` marker is applied across files but never registered in pytest config

`@pytest.mark.host_cf` is used in four test files and selected against by `scripts/test-hostile-env` (`-m "not host_cf"`). Pytest accepts the marker because the tests apply it, so the `-m` filter resolves, but a `pytest --strict-markers` configuration would fail. If strict markers are added later, the marker must be registered in `pyproject.toml` or the suite's pytest config.

### [NOTE] `tests/conftest.py` `_load_env_file` patch uses dotted-name import to reach the module

The comment explains the rationale well: `squadron.cli.app` as an attribute is the Typer object the package re-exports, not the module, so `monkeypatch.setattr("squadron.cli.app", "_load_env_file", ...)` would patch the Typer object. `importlib.import_module("squadron.cli.app")` reaches the module directly. The fix is correct and the inline comment prevents the next reader from "simplifying" it back into a silent bug.

### [NOTE] `hermetic_environment` runs `time.tzset()` which mutates process-global state

Setting `TZ=Asia/Kolkata` then calling `time.tzset()` forces every subsequent C-level localtime (including stdlib `datetime.datetime.fromtimestamp(...)` without `tz=UTC`) to read Kolkata. This is the test's intent, and the pinned TZ (`Asia/Kolkata`, half-hour offset, non-UTC) is deliberate per the docstring so a hidden localtime assumption fails on every machine. The mutation is process-wide and is not reverted, but subsequent tests see the same pinned TZ so there is no cross-test pollution.

### [NOTE] `_hermetic.py` `REAL_HOME` is captured at import, not at first use

`REAL_HOME = Path.home()` runs when pytest imports the module — before any test mutates HOME — so the value is the developer's actual home. Any future change that delays the import past a HOME mutation (e.g. importing `_hermetic` lazily inside a fixture) would record the wrong value and silently leak hostile state into `host_cf`-marked tests. Worth a one-line note pointing at the import-order dependency.

### [NOTE] `_load_env_file` is now called from the Typer root callback, after parsing

`load_dotenv(dotenv_path=Path.cwd() / ".env")` now runs inside `main()` rather than at module import, which is the right fix for "importing squadron must not read the working directory's credentials". One consequence worth knowing: env vars set in `.env` are visible to the Typer-parse step (since the callback runs after parsing). For any future option that needs an `.env` value to drive its default, the default has to be resolved inside the command body, not as a Typer parameter default.

### [NOTE] `test_import_purity.py` scanner is intentionally narrow

The scanner catches `Path.home()` (and `pathlib.Path.home()`) and any callable whose name or attribute name is `load_dotenv`, including inside class bodies, function defaults, and decorators. It deliberately does not walk into function bodies. The parametrised truth-table tests (`test_scanner_flags_import_time_calls`, `test_scanner_allows_call_time_calls`) lock the contract in both directions. Two intentional limits: `from dotenv import main; main()` would slip through, and a `@functools.cache`-wrapped function whose body calls `Path.home()` is treated as call-time. Both are acceptable scope choices; if either becomes a real risk, the scanner is the single place to extend.

### Run Digest

- Response length: 7029 chars
- Response is newline-free: no
- Tool calls made: 41
- Tool calls failed: 0
- Stop reason: stop
- Reasoning characters: 32266
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 10
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 10
- Finding-shaped matches — surviving validation: 10
