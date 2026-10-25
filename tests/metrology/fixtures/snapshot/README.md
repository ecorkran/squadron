---
docType: reference
layer: project
project: squadron
dateCreated: 20261022
dateUpdated: 20261022
---

# Snapshot tool-output fixtures

Real output captured from the tools the code-snapshot adapters (slice 400) parse. Each
capture is a `<name>.stdout` / `<name>.stderr` pair. The only edit is a path-prefix
substitution: the capture's repo root is replaced by the token `__REPO_ROOT__`, so a
test substitutes its own root. No field was edited, no entry was dropped.

Tool versions: ruff 0.15.1, pyright 1.1.408, uv 0.11.2, ESLint 10.12.0
(`version_*.stdout`). Captured 20261022.

## Captures

| Name | Command (run from the source repo) | Source repo | Exit |
|---|---|---|---|
| `ruff_squadron_clean` | `ruff check --no-cache --exit-zero --output-format json src/squadron/metrology/snapshot` | squadron | 0 |
| `ruff_scratch_findings` | `ruff check --no-cache --exit-zero --output-format json --isolated bad.py` | scratch (unused imports, undefined name) | 0 |
| `pyright_squadron_clean` | `pyright --outputjson src/squadron/metrology/snapshot/lengths.py` | squadron | 0 |
| `pyright_scratch_findings` | `pyright --outputjson mod.py` | scratch, `pyrightconfig.json` `reportUnusedImport: warning`; one warning and one error | 1 |
| `pyright_fatal_config` | `pyright --outputjson mod.py` | scratch, unparseable `pyrightconfig.json` | 3 |
| `uv_in_sync` | `uv sync --check --locked --offline` | squadron | 0 |
| `uv_out_of_sync` | `uv sync --check --locked --offline` | scratch uv project, `six` locked but uninstalled | 1 |
| `eslint_context_forge` | `eslint --format json` on three `src` files and `packages/core/vitest.config.ts` | context-forge | 0 |
| `eslint_context_forge_findings` | `eslint --format json --stdin --stdin-filename packages/core/src/project-defaults.ts`, with `any`, `console.log` and an empty catch on stdin | context-forge config | 1 |
| `eslint_fatal_config` | `eslint --config <scratch>/eslint.config.mjs --format json packages/core/src/adoption/contracts.ts`, scratch config that fails to load | context-forge binary | 2 |

context-forge itself has no lint findings (it gates on ESLint), and the snapshot must
not write there, so the findings capture lints synthetic content on stdin under
context-forge's real config. Nothing in `../context-forge` was written.

## How ESLint 10 reports a file skipped by `ignores`

In `eslint_context_forge.stdout`, `packages/core/vitest.config.ts` (tracked, matched by
`ignores` in `eslint.config.mjs`) appears as a normal result entry with:

- `messages`: one entry with `"ruleId": null`, `"fatal": false`, `"severity": 1` and the
  message `File ignored because of a matching ignore pattern. Use "--no-ignore" to
  disable file ignore settings or use "--no-warn-ignored" to suppress this warning.`
- `warningCount: 1`, `errorCount: 0`

A skipped file is therefore a result entry, not a missing one. Its only message has a null
`ruleId`, `severity` 1, `fatal: false` and no `line`/`column`. The adapter identifies
skipped files by exactly that shape and never counts them as lint findings. The missing
position matters: a real null-`ruleId` warning (for example an unused disable directive)
always carries a line and column.

## Exit-code table

What each tool's exit code means for the adapters. A "findings" exit carries a parseable
JSON report on stdout and is a normal result; "failed" means the tool did not measure.

| Tool | Exit | Meaning | Adapter outcome |
|---|---|---|---|
| ruff (`--exit-zero`) | 0 | findings or none | counted |
| ruff | any other | failed | `tool_failed` |
| pyright | 0 | no errors (JSON report) | counted |
| pyright | 1 | errors found (JSON report) | counted |
| pyright | 3 | config file could not be parsed (stderr message; stdout JSON reports 0 errors) | `tool_failed` |
| pyright | any other | failed | `tool_failed` |
| ESLint | 0 | no error-severity findings (JSON report; warnings may be present) | counted |
| ESLint | 1 | error-severity findings (JSON report) | counted |
| ESLint | 2 | fatal: config failed to load (no stdout, stack trace on stderr) | `tool_failed` |
| ESLint | any other | failed | `tool_failed` |
| uv sync --check | 0 | in sync | type errors measured |
| uv sync --check | 1 | `The environment is outdated` | `environment_unresolved` |
| uv sync --check | any other | uv error | `tool_failed` |

Pyright exit 3 is the case that matters: its stdout still holds a well-formed JSON
report with zero errors, so an adapter that trusts parseable JSON alone would record a
false zero. The exit code decides.

## Cobertura coverage reports (slice 401)

Real Cobertura XML from the two writers the coverage reader (slice 401) parses. Captured
20261024. The only edit is the same substitution as above: the absolute `<source>` root
is replaced by `__REPO_ROOT__`. Nothing else was changed.

| Name | Command | Source | Producer |
|---|---|---|---|
| `cobertura_coveragepy.xml` | `COVERAGE_FILE=<scratch>/.coverage uv run --with pytest-cov pytest --cov=src/squadron/metrology/snapshot --cov-report=xml:<scratch>/coverage.xml -q tests/metrology/snapshot/test_lengths.py tests/metrology/snapshot/test_complexity.py` | squadron | pytest-cov 7.1.0, coverage.py 7.17.0 |
| `cobertura_istanbul.xml` | `npx vitest run --coverage` with `coverage: { provider: 'v8', reporter: ['cobertura'], include: ['src/**/*.ts'], exclude: ['src/**/*.test.ts'] }` | scratch vitest project (two source files, `untested()` never called; not kept) | vitest 5.0.5, @vitest/coverage-v8 5.0.5, Node 22.23.1 |

Facts recorded from the captures, which the reader parses:

- **Root `version`:** coverage.py writes its own version (`7.17.0`). Istanbul writes the
  fixed string `0.1`.
- **`<source>`:** one absolute directory in both. coverage.py writes the measured source
  directory (`.../src/squadron/metrology/snapshot`), so each `filename` is relative to
  that directory (`lengths.py`). Istanbul writes the project root, so each `filename` is
  relative to it (`src/math.ts`). Joining a `<source>` with a `filename` gives the file
  in both cases.
- **Which `<line>` entries count:** only `<line>` elements directly under `<class><lines>`.
  The root `lines-valid` and `lines-covered` are the sums of these. Istanbul also writes
  `<line>` elements inside `<method><lines>` (the function's first line), which are not in
  the root totals; counting them would not match the report. coverage.py writes empty
  `<methods/>`.
- **Istanbul lines:** carry `branch="true|false"` and `condition-coverage` on branch lines;
  only `number` and `hits` are read. The file has a `<!DOCTYPE ... SYSTEM ...>` line.
