---
docType: tasks
slice: complexity-duplication-and-coverage
project: squadron
lld: user/slices/401-slice.complexity-duplication-and-coverage.md
dependencies:
- 400
projectState: 0.24.0 released with slice 400 (sq metrology snapshot); slice 401 design
  complete, all decisions decided
dateCreated: 20261023
dateUpdated: 20261024
status: not_started
turns: 13
promptTokens: 877165
cachedTokens: 789673
cacheWriteTokens: 87466
completionTokens: 18241
durationSeconds: 191.4
costUsd: 1.222891
usageRounds: 1
pricedRounds: 1
---

# Tasks: Complexity, Duplication and Coverage

## Context Summary
- Slice 401 adds four metrics to both 400 adapters: `cyclomatic_complexity`, `duplicated_lines`, `covered_lines` and `coverable_lines`. Coverage is read from a Cobertura XML report the project already produces. The snapshot still installs nothing and runs no tests.
- All decisions live in the slice design (the `lld` above), D1–D6. Each task cites its decision. Read it before starting the task. The module table is under Architecture → Component Structure, and the failure modes are in the table under Data Flow.
- Prerequisites, all on `main` from slice 400: `snapshot_models.py`, `snapshot/contract.py`, `snapshot/lengths.py`, `snapshot/tool_support.py` (`absent`, `tool_failed`, `repo_relative`), both adapters, `default_registry()`, preflight, and the test helpers in `tests/metrology/snapshot/` (`conftest.py`, `builders.py`).
- Contract freeze: `MetrologyRecord`, `CodeSnapshot`, `Measurement`, `LanguageAdapter`, `AdapterContext`, `take_snapshot` and the store don't change. The only diff to `snapshot_models.py` is enum members.
- Branch: `401-slice.complexity-duplication-and-coverage`, forked from the target (`cf config get git.integration_branch`, or `main` if empty).
- Every commit: `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors project-wide), and the tests for the touched area. Don't use `pytest -n`.
- Tests build throwaway git repos under `tmp_path` with `snapshot_git_repo`. New modules stay at ~300 lines or less.
- Live runs (pytest-cov over squadron, a scratch vitest project, snapshots of `../context-forge`) are pre-authorized.
- Next slices: 403 (diffs and rollups) and 420 consume these measurements; 404 gets them automatically.

## Task 1: Slice branch — Effort 1
- [ ] Create `401-slice.complexity-duplication-and-coverage` from the target
- [ ] Success: `git branch --show-current` prints the slice branch

## Task 2: Enum members (Technical Scope) — Effort 2
- [ ] In `snapshot_models.py`, add `SnapshotMetric` members `cyclomatic_complexity`, `duplicated_lines`, `covered_lines`, `coverable_lines`, and `AbsenceReason` members `coverage_not_configured`, `report_missing`, `report_stale`. Nothing else in the file changes
- [ ] `PythonAdapter.metrics` is `frozenset(SnapshotMetric)` today, so it would claim the new metrics and `take_snapshot` would raise. Replace it with the explicit set of the four 400 metrics. Later tasks add each new metric as it's measured
- [ ] Success: the full `tests/metrology/` suite passes unchanged; a snapshot of a `snapshot_git_repo` repo shows the four new metrics as `metric_unsupported` for both languages (add this as one test in `test_take.py`)
- [ ] Commit: `feat(metrology): add complexity, duplication and coverage metric enums`

## Task 3: Python decision-point count (D2) — Effort 2
- [ ] Create `snapshot/python_complexity.py` with one public function: the McCabe complexity of one `ast.FunctionDef` / `ast.AsyncFunctionDef` node (1 plus its decision points)
- [ ] The decision-point node types are one module constant. Decision points, per D2:
  - [ ] `If` (which covers `elif`), `For`, `AsyncFor`, `While`, `IfExp`
  - [ ] each `ExceptHandler`, each `match_case`
  - [ ] a `BoolOp` adds `len(values) - 1`
  - [ ] a comprehension adds 1 per `for` (`comprehension` node) plus 1 per `if` in it
  - [ ] `Try`, `With`, `Assert` and `else` clauses add nothing
- [ ] The walk doesn't descend into a nested `FunctionDef` / `AsyncFunctionDef` (that function is scored on its own). It does descend into `Lambda`, whose decisions belong to the enclosing function
- [ ] Export a short text built from the constant, for the `counting` text in Task 5
- [ ] Success: module imports nothing from `lengths.py` or the adapter

## Task 4: Python complexity tests — Effort 2
- [ ] `tests/metrology/snapshot/test_python_complexity.py`, parsing source strings with `ast`:
  - [ ] a body with no decisions scores 1
  - [ ] one test per decision point listed in Task 3, each scoring 2 (or 3 for a three-operand `and`)
  - [ ] `try`/`else`, `with` and `assert` each score 1
  - [ ] the Success Criterion 3 fixture (`if`, `elif`, `and`, a comprehension `if`, an `except`) scores 6
  - [ ] a nested `def` with two `if`s leaves its parent at 1; an `if` expression inside a lambda counts toward the enclosing function
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add Python cyclomatic complexity counting`

## Task 5: TypeScript decision-point count (D2) — Effort 2
- [ ] Create `snapshot/typescript_complexity.py` with one public function: the complexity of one tree-sitter function node. It takes the "is this node a counted function" predicate as a parameter (`typescript_length._is_counted` is passed in by Task 6), so the two modules don't import each other
- [ ] The decision-point node types are one module constant: `if_statement`, `for_statement`, `for_in_statement`, `while_statement`, `do_statement`, `switch_case`, `catch_clause`, `ternary_expression`. `switch_default` is not in it
- [ ] The short-circuit operators `&&`, `||`, `??` are a second constant; a `binary_expression` counts when its `operator` field is one of them
- [ ] The walk doesn't descend into a nested counted function; it does descend into an expression-bodied arrow (not counted, so its decisions belong to the parent)
- [ ] Before writing the constant, confirm each node type name exists in the pinned grammar for both the `typescript` and `tsx` languages (parse a sample containing each construct and inspect node types). Record any difference from D2's names in the slice design's D2 and use the grammar's name
- [ ] Export a short text built from the constants, for the `counting` text in Task 6

## Task 6: TypeScript complexity tests — Effort 2
- [ ] `tests/metrology/snapshot/test_typescript_complexity.py`, parsing source strings with the grammar (use `typescript_length`'s parser helper):
  - [ ] a body with no decisions scores 1
  - [ ] one test per decision node type and per operator, each scoring 2; `for…of` counts through `for_in_statement`
  - [ ] `switch` with two `case`s and a `default` scores 3
  - [ ] the Success Criterion 3 fixture (`if`, `??`, a ternary, two non-default `case`s) scores 6
  - [ ] a nested block-bodied arrow's `if` doesn't count toward its parent; an expression-bodied arrow's ternary does
  - [ ] a `.tsx` sample with a ternary inside JSX scores 2
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add TypeScript cyclomatic complexity counting`

## Task 7: `MeasuredFunction` and the complexity measurement (D1, D2) — Effort 3
- [ ] In `lengths.py`, rename `FunctionLength` to `MeasuredFunction` and add `complexity: int`. Rename `measure_length_metrics` to `measure_parse_metrics`. Read, decode and parse-error handling stay as they are
- [ ] Create `snapshot/complexity.py`: a measurement builder taking language, tool, the `MeasuredFunction`s and the unparsed files. `distribution` over function complexities; no `per_file`, no `limit`, no `over_limit`; `unparsed_files` identical to function length's
- [ ] `measure_parse_metrics` takes a second `ToolIdentity` for complexity and returns file length, function length and cyclomatic complexity
- [ ] Python: `python_adapter._collect_functions` sets `complexity` from Task 3. A complexity tool identity has the same name and version as `ast_tool_identity()` and its own `counting`: Task 3's decision-point text, plus "module-level code is not in any function and is not counted"
- [ ] TypeScript: `typescript_length._extract_functions` sets `complexity` from Task 5, passing `_is_counted`. Same identity pattern beside `tree_sitter_tool_identity()`
- [ ] Add `cyclomatic_complexity` to `PythonAdapter.metrics` and `TypeScriptAdapter.metrics`
- [ ] Function length's `counting` text and values don't change (D1)
- [ ] Success: 400's length tests pass, edited only for the two renames

## Task 8: Complexity integration tests — Effort 2
- [ ] Add to `test_python_length.py` and `test_typescript_length.py` (or a new `test_complexity.py`):
  - [ ] for a multi-file repo with methods, nested functions and lambdas (Python) and arrows and methods (TypeScript), complexity and function length have the same `distribution.count` and the same (path, qualified name, start line) set (Success Criterion 2)
  - [ ] a file with a parse error is in both measurements' `unparsed_files` and nowhere else; a `RecursionError` from deeply nested source is handled the same way (failure-mode table)
  - [ ] complexity's `tool.name` equals function length's; the `counting` texts differ
  - [ ] `per_file` is empty and `limit` is `None` even when `metrology.max_function_lines` is set
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): record cyclomatic complexity on the function walk`

## Task 9: Duplication pass (D3) — Effort 4
- [ ] Create `snapshot/duplication.py` with module constants `DUPLICATION_WINDOW_TOKENS = 100` and `DUPLICATION_MAX_TOKENS = 4_000_000`
- [ ] Define a `Tokenizer` type: file text in, ordered (token text, line number) pairs out. Comment and layout tokens are already dropped by the tokenizer
- [ ] `measure_duplication(repo_root, files, language, tool, tokenizer, token_errors)` returns one `duplicated_lines` measurement:
  - [ ] read and decode each file with a helper extracted from `lengths._measure_source` and used by both (length behavior unchanged; never a copy). An `OSError`, a `UnicodeDecodeError` or one of `token_errors` puts the file in `unparsed_files` with a WARNING per file, and it contributes no tokens
  - [ ] map each token text to an integer id; store each file as two `array`s (ids and lines)
  - [ ] keep a running token total; when it passes `DUPLICATION_MAX_TOKENS`, stop before building the window index and return `tool_failed` (via `tool_support.tool_failed`) naming the count and the ceiling. A `MemoryError` during the pass is handled the same way. Never a partial figure
  - [ ] a rolling hash gives every window's hash in one pass; a dict maps hash to first occurrence (file, start index); a repeat is confirmed by comparing the two id slices, so a collision is never a clone
  - [ ] a confirmed repeat marks every line under both windows; two windows in one file whose token ranges overlap don't count as copies of each other
  - [ ] `per_file` holds the count of distinct duplicated lines, only for files with a non-zero count; no `distribution`
  - [ ] `tool.counting` is built from the window constant: per-language, exact token match (type-1), comments and layout dropped, window size, the ceiling
- [ ] Keep the hash step in a small module-level function so a test can force collisions
- [ ] Success: module has no language-specific logic; under ~300 lines

## Task 10: Duplication tests — Effort 3
- [ ] `tests/metrology/snapshot/test_duplication.py`, using a whitespace-splitting test tokenizer over files written to `tmp_path`:
  - [ ] two files sharing a 100-token block report its lines in both; a 99-token block reports nothing (Success Criterion 4)
  - [ ] a block repeated in one file without overlap counts; a run of one repeated token (overlapping windows) doesn't
  - [ ] the same block with one renamed token reports nothing
  - [ ] files with no duplication are absent from `per_file`
  - [ ] with the hash step patched to a constant, distinct windows report nothing
  - [ ] with `DUPLICATION_MAX_TOKENS` lowered by `monkeypatch`, the result is `tool_failed` with a WARNING naming the count and the ceiling (Success Criterion 10)
  - [ ] a tokenizer that raises `MemoryError` gives `tool_failed` with a WARNING
  - [ ] a tokenizer error and undecodable bytes each put the file in `unparsed_files` with a WARNING; the other files are still compared
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add token-window duplication detection`

## Task 11: Python tokenizer and duplication wiring (D3) — Effort 2
- [ ] In `python_adapter.py`, add a tokenizer over `tokenize.generate_tokens`. The dropped token types (`COMMENT`, `NL`, `NEWLINE`, `INDENT`, `DEDENT`, `ENCODING`, `ENDMARKER`) are one module constant
- [ ] Token errors are `tokenize.TokenError` and `SyntaxError` (which covers `IndentationError`)
- [ ] `PythonAdapter.measure` calls `measure_duplication` with a duplication tool identity: same name and version as the ast identity, `counting` from Task 9
- [ ] Add `duplicated_lines` to `PythonAdapter.metrics`
- [ ] Success: `python_adapter.py` stays under ~300 lines; if it would exceed, move the tokenizer into a new `snapshot/python_tokens.py` and update the slice design's module table

## Task 12: Python duplication tests — Effort 2
- [ ] Add to `test_duplication.py` (or `test_python_duplication.py`), through `PythonAdapter` on a `snapshot_git_repo` repo:
  - [ ] two files with an identical function of over 100 tokens but different comments and blank lines report the function's lines in both
  - [ ] a file with an unterminated triple-quoted string and one with bad indentation are each in duplication's `unparsed_files` with a WARNING, while their function length is unaffected
  - [ ] file length and function length values are identical to a run without duplication on the same repo (Success Criterion 12)
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): measure duplicated lines for Python`

## Task 13: TypeScript tokenizer and duplication wiring (D3) — Effort 2
- [ ] In `typescript_length.py`, add a tokenizer over tree-sitter leaf nodes (no children), dropping types in a one-member module constant (`comment`). Line is the leaf's start row plus 1
- [ ] An error-root tree raises `TypeScriptParseError`, as `_extract_functions` does, so a file unparsed for length is unparsed for duplication. Token errors are `TypeScriptParseError` and `MemoryError`
- [ ] `TypeScriptAdapter.measure` calls `measure_duplication` with a duplication identity beside `tree_sitter_tool_identity()`
- [ ] Add `duplicated_lines` to `TypeScriptAdapter.metrics`

## Task 14: TypeScript duplication tests — Effort 2
- [ ] Through `TypeScriptAdapter` on a `snapshot_git_repo` repo:
  - [ ] two `.ts` files sharing a block of over 100 tokens, with different comments, report its lines in both; a `.tsx` file with a shared JSX block does too
  - [ ] a syntax-error file is in duplication's `unparsed_files` with a WARNING
  - [ ] a repo holding a Python file and a TypeScript file with the same token text reports no duplication in either language (Success Criterion 4, last clause)
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): measure duplicated lines for TypeScript`

## Task 15: Coverage config key and preflight validation (D6) — Effort 2
- [ ] Add `metrology.coverage_report` (str, default None) to `CONFIG_KEYS` in `src/squadron/config/keys.py`, following the existing `metrology.*` entries
- [ ] Create `snapshot/coverage.py` holding the key name constant and a path parser: rejects an empty value, an absolute path and any `..` segment, raising `SnapshotPreflightError` naming the value and the fix; returns the repo-relative path, or `None` when unset
- [ ] `preflight.py` reads the key with `get_config(key, cwd=str(repo_root))` and calls the parser, importing both from `coverage.py`. The parsed value isn't added to `PreflightResult`; the reader resolves the key again at measurement time (D6)
- [ ] Success: the key name string appears once in source, in `coverage.py`, apart from `CONFIG_KEYS`

## Task 16: Config and preflight tests — Effort 1
- [ ] Add to `test_preflight.py`: unset passes; `coverage.xml` and `build/cov.xml` pass; `/tmp/coverage.xml`, `../coverage.xml`, `a/../../x.xml` and an empty string each raise `SnapshotPreflightError` before any tool runs (Success Criterion 9); a path to a file that doesn't exist passes
- [ ] The new `CONFIG_KEYS` entry has type str and default None
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add metrology.coverage_report key and preflight check`

## Task 17: Capture real Cobertura reports (Technical Requirements) — Effort 2
- [ ] Store under `tests/metrology/fixtures/snapshot/` and add to its `README.md`, per file, the exact command, tool versions and source
- [ ] coverage.py: in squadron, `uv run --with pytest-cov pytest --cov=src/squadron --cov-report=xml -q` on a small test subset (for example `tests/metrology/snapshot/`), keeping the report as it was written. The absolute `<source>` path is replaced with the existing `FIXTURE_ROOT_TOKEN` used by `read_fixture`, and the README says so
- [ ] Istanbul: in a scratch directory outside squadron, create a vitest project with `@vitest/coverage-v8`, two `.ts` source files (one partly untested) and `coverage.reporter: ['cobertura']`; run `npx vitest run --coverage`; keep `coverage/cobertura-coverage.xml` with the same root-token substitution
- [ ] Record in the README, from the captures: the root `version` of each, and how each writes `<source>` and `filename`. Task 18 parses what is recorded here
- [ ] Success: squadron's tree is clean apart from the new fixtures; the scratch project is removed
- [ ] Commit: `test(metrology): add real Cobertura report fixtures`

## Task 18: Cobertura reader (D4) — Effort 3
- [ ] In `coverage.py`, add a reading type: per repo-relative path, the set of coverable line numbers and the set with `hits > 0`; plus the report's root `version` and the report path
- [ ] Parse with `xml.etree.ElementTree`:
  - [ ] each `<class filename=…>` is joined with each `<source>` and taken relative to the repo root with `tool_support.repo_relative`; entries that resolve outside the repo are dropped
  - [ ] `<line number=… hits=…/>` values collect into per-file sets, so a repeated entry is counted once
- [ ] Each problem returns a failure (not an exception) naming the report and the problem: malformed XML, a root other than `<coverage>`, no root `version`, a non-integer `number` or `hits`, an `OSError` reading the file
- [ ] Success: no fallback version; a missing `version` is always a failure (D4)

## Task 19: Cobertura reader tests — Effort 2
- [ ] `tests/metrology/snapshot/test_coverage.py`, with the Task 17 fixtures rooted at a `tmp_path` repo:
  - [ ] coverage.py fixture: per-file coverable and covered counts match the report, and their totals equal the root `lines-valid` and `lines-covered` (Success Criterion 6)
  - [ ] Istanbul fixture: present, version `0.1`
  - [ ] a duplicated `<line>` entry is counted once; a `<source>` outside the repo drops its classes
  - [ ] malformed XML, a wrong root, no `version`, `hits="x"`, and an unreadable report each give a failure naming the problem (Success Criterion 8)
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add Cobertura coverage report reader`

## Task 20: Freshness check and `read_coverage` (D5, D6) — Effort 3
- [ ] `read_coverage(repo_root)` in `coverage.py`, in this order:
  - [ ] key unset → `coverage_not_configured`
  - [ ] report file doesn't exist → `report_missing`, detail naming the path
  - [ ] `git ls-files -z` at the repo root via `run_git`; `None` or non-zero logs ERROR and raises `SnapshotIntegrityError` naming the call, as 400's git calls do
  - [ ] stat the report and every tracked file; an `OSError` on either is a failure naming the path, never fresh, never skipped
  - [ ] report mtime earlier than the newest tracked mtime → `report_stale`, detail naming the newest file
  - [ ] otherwise parse with Task 18
- [ ] The result is either a reading or an absence (reason, detail); it holds no language. Each absence and failure logs at WARNING
- [ ] Success: the only exception `read_coverage` raises is `SnapshotIntegrityError`

## Task 21: Freshness tests — Effort 2
- [ ] Add to `test_coverage.py`, on `snapshot_git_repo` repos with a gitignored report:
  - [ ] unset key → `coverage_not_configured`; key set to a missing file → `report_missing` (Success Criterion 5)
  - [ ] report written after the commit is fresh; `os.utime` setting one tracked file newer than the report → `report_stale`, detail naming that file
  - [ ] a report with an mtime equal to the newest tracked file is fresh
  - [ ] `run_git` patched to return `None`, and to a non-zero result, each raise `SnapshotIntegrityError` and log ERROR
  - [ ] a stat `OSError` on a tracked file (patched) gives a failure naming the path and logs WARNING
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): add coverage report freshness check`

## Task 22: Per-language coverage measurements (D4, D5) — Effort 2
- [ ] `coverage_measurements(reading, language, files)` returns `coverable_lines` and `covered_lines`:
  - [ ] an absence becomes both metrics absent with that reason and detail; a failure becomes both `tool_failed` via `tool_support.tool_failed`
  - [ ] `per_file` for every reported file in `files`, zeros included; files in `files` not in the report go in `tool_ignored_files` on both; report entries not in `files` are ignored
  - [ ] no `distribution`
  - [ ] `ToolIdentity`: name `cobertura` (a module constant), version from the report, `counting` naming the report path, the D5 freshness rule and its gaps, that coverage depends on the report file and its mtime, and that Istanbul's fixed `0.1` hides a change of provider
- [ ] Success: one reading builds both languages' measurements without re-reading the file

## Task 23: Coverage measurement tests — Effort 2
- [ ] Add to `test_coverage.py`:
  - [ ] a reading covering some of `files` puts the rest in `tool_ignored_files` on both; a reported file with no hits has `0` in `covered_lines` and a non-zero `coverable_lines`
  - [ ] a reading with none of the language's files gives empty `per_file` and every file in `tool_ignored_files`
  - [ ] each absence reason reaches both metrics; a failure gives `tool_failed` on both with a WARNING
  - [ ] the Istanbul fixture's `counting` states the provider limit (Success Criterion 7)
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): build per-language coverage measurements`

## Task 24: Adapter wiring for coverage — Effort 2
- [ ] `PythonAdapter.measure` and `TypeScriptAdapter.measure` each call `read_coverage(ctx.repo_root)` and `coverage_measurements(...)` with their own language and files. No cache, no change to `AdapterContext` (Data Flow)
- [ ] Add `covered_lines` and `coverable_lines` to both adapters' `metrics`. `PythonAdapter.metrics` now equals the full `SnapshotMetric` set; keep it written out explicitly
- [ ] Success: `registry.py`, `take.py` and `contract.py` are unchanged

## Task 25: Snapshot-level tests — Effort 2
- [ ] Add to `test_take.py` (real adapters, `FakeToolRunner` scripted as 400's tests do, repos from `snapshot_git_repo`):
  - [ ] a Python+TypeScript repo with a fresh report covering files of both languages gives present coverage for each
  - [ ] a missing report gives `report_missing` on both languages, with its WARNING logged once per language
  - [ ] a stale report gives `report_stale` on both languages
  - [ ] two runs on one commit give identical JSON apart from `measured_at` (Success Criterion 11)
  - [ ] every language section holds all eight metrics
- [ ] Success: tests pass; full `tests/metrology/` passes; ruff and pyright clean
- [ ] Commit: `feat(metrology): measure coverage in the Python and TypeScript adapters`

## Task 26: Render lines (API Contracts) — Effort 2
- [ ] In `render.py`:
  - [ ] `cyclomatic_complexity` uses `_spread(..., 'function')` plus unparsed and tool text, like function length
  - [ ] `duplicated_lines`, `covered_lines`, `coverable_lines` use the existing "N in M file(s)" form
  - [ ] the `tool_ignored_files` wording becomes metric-aware: "not in report" for the two coverage metrics, "skipped by the tool's ignores" otherwise. The coverage metric set is one constant
- [ ] Tests in `test_render.py`: each new line's shape matches the API Contracts example; lint's "skipped by the tool's ignores" text is unchanged
- [ ] Success: tests pass; ruff and pyright clean
- [ ] Commit: `feat(metrology): render complexity, duplication and coverage lines`

## Task 27: Docs and CHANGELOG — Effort 1
- [ ] `docs/COMMANDS.md`: under `sq metrology snapshot`, the four new metrics with their definitions (one line each, pointing at `counting`), and `metrology.coverage_report` in the metrology config table, including that the report must be gitignored and fresh
- [ ] `docs/COMMANDS.md` and the CHANGELOG bullet under Unreleased both state that snapshots from earlier versions are skipped and must be retaken
- [ ] Commit: `docs: document snapshot complexity, duplication and coverage`

## Task 28: Verification walkthrough — Effort 3
- [ ] Run walkthrough steps 1–10 from the slice design against squadron, `../context-forge` and a scratch vitest project. Record each step's actual output summary in the slice design under a "Walkthrough Results" heading
- [ ] Step 10 needs a 400-written snapshot in the store; if none exists, record that in the results and run the rest of the step
- [ ] Any step that fails is a bug in this slice: fix it, add a regression test, rerun the step
- [ ] Success: all steps match their expected structure; `git -C ../context-forge status --porcelain` empty afterwards; squadron's `.squadron.toml` key restored after steps 6 and 7; scratch project removed
- [ ] Commit: `docs: record slice 401 walkthrough results`

## Task 29: Final validation — Effort 1
- [ ] `.venv/bin/ruff format`, `.venv/bin/ruff check`, `.venv/bin/pyright` (zero errors), and the full test suite pass
- [ ] Every new module is at ~300 lines or less (`wc -l src/squadron/metrology/snapshot/*.py`)
- [ ] `git diff main -- src/squadron/metrology/snapshot_models.py` shows enum members only; `take.py`, `contract.py`, `files.py` and `store.py` show no diff
- [ ] Every Success Criterion (Functional 1–12, Technical, Integration) maps to a passing test or a recorded walkthrough step
- [ ] Commit any remaining changes on the slice branch
