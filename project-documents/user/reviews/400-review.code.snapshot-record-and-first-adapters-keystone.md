---
docType: review
layer: project
reviewType: code
slice: snapshot-record-and-first-adapters-keystone
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 4e644a35a1cdb8ccef659cd489f4b029cc0145b9
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 126492
cachedTokens: 3232
cacheWriteTokens: 123258
completionTokens: 2846
durationSeconds: 25.9
costUsd: 0.574889
costBasis: provider
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: dry
    summary: "Tool-run/timeout/exit/parse loop is triplicated across the three tool adapters"
    location: "src/squadron/metrology/snapshot/python_lint.py:measure_ruff_lint"
  - id: F002
    severity: concern
    category: security
    summary: "CLI security warning covers only ESLint, but ruff and pyright are also taken from the measured repo"
    location: "src/squadron/cli/commands/metrology_snapshot.py:55-59"
  - id: F003
    severity: note
    category: design
    summary: "`_measure_source` mutates three caller-owned collections"
    location: "src/squadron/metrology/snapshot/lengths.py:_measure_source"
  - id: F004
    severity: note
    category: style
    summary: "Unused logger in `python_lint.py`"
    location: "src/squadron/metrology/snapshot/python_lint.py:36"
  - id: F005
    severity: note
    category: error-handling
    summary: "`check_integrity` exempts `.squadron.toml` even after measuring"
    location: "src/squadron/metrology/snapshot/preflight.py:check_integrity"
  - id: F006
    severity: note
    category: testing
    summary: "Cross-test-module import of `FakeAdapter`"
    location: "tests/metrology/snapshot/test_snapshot_cli.py:20"
---

# Review: code — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Tool-run/timeout/exit/parse loop is triplicated across the three tool adapters

`measure_ruff_lint`, `measure_pyright_types` (`python_types.py`) and `measure_eslint_lint` (`typescript_lint.py`) each repeat the same sequence. They chunk the files, run the tool, and check `timed_out`. They then check the exit code against an allowed set, parse the output, and fold per-file counts, returning `tool_failed` on each failure branch. They differ only in the argv, the allowed exits and the parser. This is the kind of duplication that makes the failure-mode handling drift. `lengths.measure_length_metrics` already shows the shared-helper pattern. A `run_chunked(ctx, tool_path, build_argv, ok_exits, parse)` helper in `tool_support.py` would also bring all three functions under the ~50-line guideline. At the moment each is 55–70 lines.

### [CONCERN] CLI security warning covers only ESLint, but ruff and pyright are also taken from the measured repo

The help text says snapshotting executes the repository's own `node_modules/.bin/eslint` and its JS config. `resolve_tool` for ruff and pyright also prefers `<repo>/.venv/bin/<tool>` before `PATH`, and the code runs `<repo>/.venv/bin/python --version`. All of these are repo-controlled executables. `SubprocessToolRunner` also passes the full parent environment to them, so any secrets in the environment are exposed to that code. The warning should name all of these. Consider either passing an explicit minimal environment to the subprocess, or stating in the docs that the full environment is inherited.

### [NOTE] `_measure_source` mutates three caller-owned collections

It takes seven parameters, three of them out-parameters (`per_file`, `functions`, `unparsed`). Returning a small result dataclass would be clearer and easier to test.

### [NOTE] Unused logger in `python_lint.py`

`_logger` and `import logging` are defined but never used. Logging happens in `tool_support`.

### [NOTE] `check_integrity` exempts `.squadron.toml` even after measuring

The post-run check reuses `_dirty_paths`, so a tool that writes or creates `.squadron.toml` goes unnoticed. This is low risk. The post-run check could be strict, or at least compare the file's hash before and after.

### [NOTE] Cross-test-module import of `FakeAdapter`

It is imported from `test_take`. Moving it to `builders.py` or `conftest.py` avoids coupling between test modules.

### Run Digest

- Response length: 3203 chars
- Response is newline-free: no
- Tool calls made: 0
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 1
- Tokens — prompt / cached / cache write / completion / reasoning: 126492 / 3232 / 123258 / 2846 / not computed
- Duration: 25.9 s
- Cost: $0.57 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6

## Response

- **F001** accepted: `run_chunked` and `probe_or_failure` in `tool_support.py` now carry the chunk, timeout, exit-code and parse handling for ruff, pyright and ESLint. Each tool supplies its argv, allowed exit codes and parser only.
- **F002** accepted: the help text, `docs/COMMANDS.md` and the slice design name every repo-controlled executable (`.venv/bin/ruff`, `.venv/bin/pyright`, `.venv/bin/python`, `node_modules/.bin/eslint`, the JavaScript config) and state that the full environment is inherited. The environment stays inherited on purpose: node, uv and the venv interpreter need `PATH` and `HOME`, and the repository is already trusted to run code.
- **F003** declined: three out-parameters in a private helper whose only caller is `measure_length_metrics`; a result dataclass adds a type for no second caller.
- **F004** accepted: removed.
- **F005** declined: a tool writing `.squadron.toml` can't change a measurement, since squadron reads it before any tool runs and records its values on the snapshot.
- **F006** accepted: `FakeAdapter` and `present` moved to `tests/metrology/snapshot/builders.py`.
