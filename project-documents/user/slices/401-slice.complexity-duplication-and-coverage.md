---
docType: slice-design
slice: complexity-duplication-and-coverage
project: squadron
parent: ../architecture/400-slices.code-quality-measurement.md
dependencies:
- 400
interfaces:
- 403
dateCreated: 20261022
dateUpdated: 20261024
status: complete
turns: 20
promptTokens: 1310434
cachedTokens: 1200278
cacheWriteTokens: 110124
completionTokens: 34409
durationSeconds: 347.5
costUsd: 1.809705
usageRounds: 1
pricedRounds: 1
---

# Slice Design: Complexity, Duplication and Coverage

## Overview

400 gave `sq metrology snapshot` file length, function length, lint counts and type counts for Python and TypeScript. This slice adds the remaining static metrics to both adapters: cyclomatic complexity per function, duplicated lines per file, and line coverage read from a Cobertura XML report the project already produces. The snapshot still installs nothing and runs no tests.

Complexity is counted on the function walk that already produces function length (stdlib `ast` for Python, tree-sitter for TypeScript), so both metrics cover the same functions. Duplication runs as its own pass over a token stream (`tokenize`, tree-sitter leaves) and leaves 400's metrics untouched. Each counting definition is squadron's own, stated in the tool identity. Coverage comes from one Cobertura reader that each adapter calls and takes its own files from. A report counts only if no tracked file has changed since it was written.

## Value

- **Developer value.** A snapshot now answers "did this get more complex or more duplicated, and is it tested?" alongside size and lint. That's the full static picture 403 reports on and 420 scores against.
- **Contract proof.** The four new metrics land as enum members plus adapter code. `MetrologyRecord`, `CodeSnapshot`, `Measurement`, `LanguageAdapter` and `AdapterContext` are unchanged, which shows that 400's contract holds as its first extension uses it.

## Technical Scope

**Included**
- New `SnapshotMetric` members: `cyclomatic_complexity`, `duplicated_lines`, `covered_lines` and `coverable_lines`.
- New `AbsenceReason` members: `coverage_not_configured`, `report_missing` and `report_stale`.
- Python and TypeScript complexity counting, on the existing function walks.
- Token-window duplication detection that works for any language, fed by a tokenizer from each adapter.
- A Cobertura XML coverage reader, an mtime freshness check, and the `metrology.coverage_report` config key.
- Render lines for the new metrics, plus `docs/COMMANDS.md` and CHANGELOG.

**Excluded**
- Running tests or installing dependencies to produce coverage. This stays in the slice plan's Future Work.
- Branch coverage, and coverage formats other than Cobertura XML.
- More than one coverage report per project (#252), and a coverage rule set (#253).
- A lighter duplication index for repos much larger than squadron (#254).
- A project-declared complexity limit, and per-function complexity rows (D2).
- Duplication across languages, and clone-pair records.
- Non-HEAD commits and reports (403).

## Dependencies

### Prerequisites
- **400 (complete):** `snapshot_models`, the adapter contract, `take_snapshot`'s absent-filling, the length pipeline in `lengths.py`, both adapters, `default_registry()`, and preflight.
- No new runtime dependencies. Complexity and duplication use `ast`, `tokenize` and the tree-sitter grammars 400 already pins. Cobertura parsing uses stdlib `xml.etree.ElementTree`.

### Interfaces Required
- `squadron.review.git_utils.run_git`, to list tracked files for the freshness check.
- `get_config(key, cwd=<measured repo root>)` for the new key, resolved the same way as 400's keys (400 D10).

## Architecture

### Component Structure

| Module | Change |
|---|---|
| `snapshot_models.py` | Four `SnapshotMetric` members and three `AbsenceReason` members. Model and validators unchanged |
| `snapshot/lengths.py` | `FunctionLength` becomes `MeasuredFunction` (adds `complexity`). `measure_length_metrics` becomes `measure_parse_metrics` and also returns the complexity measurement. The read, decode and parse-error handling is unchanged |
| `snapshot/complexity.py` | New. Builds the complexity measurement from `MeasuredFunction`s. Works for any language |
| `snapshot/duplication.py` | New. `measure_duplication(repo_root, files, language, tool, tokenizer, token_errors)`: reads each file, tokenizes it (the tokenizer takes the repo-relative path and the text, since `.tsx` needs a different grammar), and runs the window pass. Works for any language |
| `snapshot/python_complexity.py` | New. Decision-point count for one `ast` function node |
| `snapshot/python_adapter.py` | The extractor sets `complexity`. Adds a `tokenize` tokenizer and calls duplication and coverage |
| `snapshot/typescript_complexity.py` | New. Decision-point count for one tree-sitter function node |
| `snapshot/typescript_length.py` | The extractor sets `complexity`. Adds a leaf-token tokenizer |
| `snapshot/typescript_adapter.py` | Declares the new metrics. Calls duplication and coverage |
| `snapshot/coverage.py` | New. Owns the config key constant and its parser. `read_coverage(repo_root)` checks freshness and parses the report into a reading, an absence or a failure |
| `snapshot/coverage_measurements.py` | New. `coverage_measurements(reading, language, files)` builds the two measurements for one language (split from `coverage.py` to keep both under ~300 lines) |
| `snapshot/preflight.py` | Validates `metrology.coverage_report` through `coverage.py`'s parser |
| `snapshot/render.py` | Summary lines for the new metrics |

`take.py`, `contract.py`, `files.py`, `store.py` and the `MetrologyRecord` envelope don't change.

### Data Flow

```
adapter.measure(ctx, files)
  └─ lengths.measure_parse_metrics(...)          → file_length, function_length, cyclomatic_complexity
  └─ duplication.measure_duplication(...)        → duplicated_lines (own read + tokenize pass)
  └─ lint, types                                 (unchanged)
  └─ coverage.read_coverage(ctx.repo_root)
       report = metrology.coverage_report          unset → absent(coverage_not_configured)
       report exists?                              no → absent(report_missing)
       report newer than every tracked file?       no → absent(report_stale)
       parse Cobertura → {repo-relative path: (coverable lines, covered lines)}, producer version
  └─ coverage.coverage_measurements(reading, language, files) → covered_lines, coverable_lines
```

**One read per adapter, no cache.** Each adapter calls `read_coverage(ctx.repo_root)` itself, so neither `AdapterContext` nor the `LanguageAdapter` protocol changes. A project with both languages reads the report twice, and a coverage warning appears once per language. The report is one file and the freshness check is one `git ls-files`, so a shared cache isn't worth the injected dependency.

**Failure modes:**

| Failure | Handling | Signal |
|---|---|---|
| `tokenize` raises (`TokenError`, `IndentationError`), or a tree-sitter tokenizer fails | The file goes into duplication's `unparsed_files` and contributes no tokens. Function length and complexity are unaffected | WARNING per file |
| A language's total token count passes `DUPLICATION_MAX_TOKENS` (D3), or the pass raises `MemoryError` | `duplicated_lines` is `tool_failed`, the detail naming the token count and the ceiling. The window index isn't built. Other metrics are unaffected | WARNING |
| A complexity walk hits `RecursionError` | It's already one of the adapter's parse errors, so the file is unparsed for function length and complexity, exactly as in 400 | WARNING per file |
| Cobertura XML is malformed, has no `<coverage>` root, has no root `version`, or has a non-integer `number` or `hits` | Both coverage measurements are `tool_failed`, naming the report and the problem | WARNING |
| The report, or a tracked file during the freshness check, can't be read or stat'ed (`OSError`) | `tool_failed` naming the path. Never treated as fresh, never a skipped file | WARNING |
| `git ls-files` for the freshness check hangs, returns `None` or exits non-zero | `run_git`'s bounded timeout turns a hang into `None`. Each case raises `SnapshotIntegrityError`, as every git call in 400 does | ERROR |

### State Management

No new state is persisted. The new measurements live in the existing `code_snapshot` record. Re-snapshotting a commit after producing a coverage report replaces the record (400 D3).

## Technical Decisions

### D1 — Complexity rides 400's function walk; duplication is a separate pass
Status: decided
- Complexity is a field on each `MeasuredFunction`, set by the same walk that measures function length. The two metrics therefore cover exactly the same functions: the same names, nesting rules and exclusions (lambdas, expression-bodied arrows). 403 can join them on (path, qualified name).
- Duplication reads and tokenizes each file in its own pass. A tokenizer failure affects only duplication, so 400's file length and function length results don't change, and their `counting` text stays the same. Reading each file twice costs little next to the lint and type tools.
- The counting is squadron's own, so it's stated in `ToolIdentity.counting`. It changes only with the squadron version, which the tool version already includes (400 D2). The tool names stay `squadron-python-ast` and `squadron-tree-sitter-ts`, with a separate `counting` text per metric.
- Rejected:
  - radon or lizard. Each has its own function definition, so complexity rows would no longer match length rows. Both are also new dependencies.
  - ruff `C901`. It reports only functions over a threshold.
  - jscpd or PMD CPD. They need Node through `npx` (forbidden by 400 D5) or a JVM.

### D2 — Complexity definition and record shape
Status: decided
- Complexity is McCabe: 1 plus the decision points in the function's own body. Decision points inside a nested counted function belong to that function, never to the one it sits in. Decision points inside an uncounted lambda or expression-bodied arrow belong to the enclosing function.
- Python decision points:
  - `if`, `elif`, `for` and `async for`, `while`
  - each `except` handler, and each `case` in a `match`
  - an `if` expression
  - each extra operand of a `BoolOp` (`len(values) - 1`)
  - each `for` and each `if` in a comprehension (so a comprehension with one `if` adds 2)
  - `try`, `with`, `assert` and `else` clauses don't count.
- TypeScript decision points:
  - `if_statement`, `for_statement`, `for_in_statement` (including `for…of`), `while_statement`, `do_statement`
  - each `switch_case` (not `switch_default`), `catch_clause`, and `ternary_expression`
  - each `binary_expression` whose operator is `&&`, `||` or `??`
- The node and operator names were checked against the pinned grammar for both `typescript` and `tsx`; they match the names above exactly.
- Each language's decision-point set is one module constant in its complexity module. Tests and the `counting` text read that constant, so the set is written in one place.
- The values are a `distribution` over functions, with no `per_file`.
- No complexity limit and no `over_limit` rows. `FunctionOverLimit.length` would mean something else for complexity, and the slice plan asks for no limit. Module-level code isn't in any function, so it isn't counted. The `counting` text says so.

### D3 — Duplication definition and bound
Status: decided
- Detection is per language: files are only compared with files of the same language.
- Each file becomes a token stream, with comments and layout dropped.
  - Python uses `tokenize` and drops `COMMENT`, `NL`, `NEWLINE`, `INDENT`, `DEDENT`, `ENCODING` and `ENDMARKER`.
  - TypeScript uses tree-sitter leaf nodes, dropping `comment`.
  - Each dropped-type set is one constant in the module that owns its language.
- Tokens are compared exactly, so these are type-1 clones: renamed identifiers aren't matched.
- A window is `DUPLICATION_WINDOW_TOKENS = 100` consecutive tokens. The constant lives in `duplication.py`, and the `counting` text is built from it. It's part of the counting definition, not a project preference, so it isn't a config key.
- How the pass works:
  - Each token's text is mapped to an integer id, and each file is stored as two `array`s: token ids and line numbers.
  - A rolling hash gives every window's hash in one linear pass.
  - A dict maps each window hash to its first occurrence. A repeat is confirmed by comparing the two id slices, so a hash collision can't make a false clone.
  - Every line under both occurrences is marked duplicated.
- The bound is linear in tokens, for both time and memory.
  - Memory is about 133 bytes per token, measured on 20261023 at squadron's size: 0.95M Python tokens gave 120 MiB.
  - A repo ten times squadron's size needs over 1 GiB.
  - So the pass has a ceiling: `DUPLICATION_MAX_TOKENS = 4_000_000` per language, a constant in `duplication.py` beside the window size (about 530 MiB at the measured rate, four times squadron). Tokens are counted as files are tokenized, and passing the ceiling stops the pass before the window index is built. `duplicated_lines` is then `tool_failed` with a WARNING naming the count and the ceiling. It's absent, never a partial figure. A `MemoryError` is handled the same way.
  - A lighter fingerprint-sampling index for repos past the ceiling is #254.
- Two occurrences in one file whose token ranges overlap don't count as copies of each other.
- `per_file` holds duplicated non-blank lines, only for files with a non-zero count, as lint does. There's no distribution. Duplicated lines are always non-blank lines, so the file-length total over the same files is the denominator.
- Clone pairs aren't stored (coarse records, 400 D1).

### D4 — Coverage comes from a Cobertura XML report, for both languages
Status: decided
- One reader handles both languages. Cobertura is the shared format: coverage.py writes it (`coverage xml`, `pytest --cov-report=xml`), and Istanbul writes it through its `cobertura` reporter, which vitest, jest and c8 expose. Python's usual `.gitignore` already ignores `coverage.xml`.
- Both writers were read on 20261022 (coverage.py `xmlreport.py`, `istanbul-reports/lib/cobertura`):
  - Each puts absolute source roots in `<sources><source>` and file paths relative to a root in `<class filename=…>`.
  - Each writes `<line number=… hits=…/>` per executable line.
  - coverage.py sets the root `version` to its own version. Istanbul always writes `version="0.1"`.
- Only `<line>` elements directly under `<class><lines>` count. They sum to the root `lines-valid` and `lines-covered` in both writers; Istanbul also repeats a function's first line inside `<method>`, which the root totals leave out (confirmed against the captured fixtures).
- Paths map by joining each `<source>` with `filename` and taking the result relative to the repo root. Entries that don't resolve under the repo root are dropped. Line numbers are collected into per-file sets, which settles any repeated entry.
- Two measurements per language, built from the one reading:
  - `coverable_lines`: per file, the lines the report lists.
  - `covered_lines`: per file, those with `hits > 0`.
  - Both have `per_file` for every reported file of the language, zeros included, so that a 0 means "in the report, untested".
  - The language's measured files that the report doesn't list go in `tool_ignored_files` on both measurements. A report with none of a language's files gives an empty `per_file`, with every file in `tool_ignored_files`.
  - There's no distribution. A report computes the rate as the sum of covered over the sum of coverable.
- Two metrics rather than one ratio: `per_file` is integral and the model's validators stay as they are. Keeping both counts lets a rollup compute a weighted rate.
- Tool identity:
  - The name is `cobertura`.
  - The version is the report's root `version` attribute. A missing attribute is `tool_failed`, matching 400 D8's rule that a count without a version has no identity.
  - `counting` names the report path, the freshness rule (D5) and the limit below.
- No rule set is recorded (#253).
- The known limit: Istanbul's fixed `0.1` means a change of coverage provider isn't visible in the identity. The `counting` text says so.
- Rejected:
  - Native formats (coverage.py JSON, Istanbul `coverage-final.json`). That's two parsers for the same numbers.
  - LCOV. It carries no producer version.

### D5 — A coverage report matches the commit when no tracked file is newer than it
Status: decided
- No coverage format records the commit. The rule: the report's mtime must be at or after the newest mtime among all tracked files (`git ls-files` at the repo root). Otherwise both coverage metrics are absent with `report_stale`, and the detail names the newest file.
- This rejects a report after any checkout, pull, stash, revert or edit that changed or added a tracked file. Together with a clean tree at HEAD (400 preflight), that's evidence the report was produced from HEAD's content, but not proof.
- What it can't catch:
  - a report copied in from elsewhere, or `touch`ed
  - a later change that only deletes tracked files
  - The `counting` text states the rule and these gaps.
- The rule errs toward stale: `touch` on a tracked file with no change in content rejects the report. The walkthrough uses this.
- This rule deliberately replaces the architecture's "environment resolved, lockfile hash recorded" rule for report-based coverage. No lockfile hash is attached to coverage, and 403 and 420 must not assume one. The `counting` text also says that coverage depends on the report file and its mtime, so the same commit can read differently in another checkout.
- The report must be gitignored. An untracked report fails preflight's dirty-tree check (400 D9).
- Rejected: hashing sources into the report (the formats have no slot for it), or a squadron-written stamp file (a new artifact the project would have to remember).

### D6 — Coverage config key
Status: decided
- `metrology.coverage_report` (str, default None) is one repo-relative report path. It's project-level through `.squadron.toml`. Unset means both coverage metrics are absent with `coverage_not_configured`. No conventional path is guessed.
- The key name and its path parser are defined once in `coverage.py`. Preflight imports both.
- Preflight validates the value before any tool runs: not absolute, no `..`, not empty. A bad value raises `SnapshotPreflightError`.
- Whether the report exists is checked at measurement time, because a missing report is a per-metric absence (`report_missing`), not a reason to refuse the snapshot.
- The reader resolves the key with `get_config(key, cwd=repo_root)`, the same resolution 400 uses.

### Technology Choices
- stdlib `ast`, `tokenize`, `array` and `xml.etree.ElementTree`, plus the pinned tree-sitter grammars. No new dependency.
- XML from the measured repo is untrusted. On the Python versions squadron supports, `ElementTree` runs on an expat with entity-expansion protection, and the snapshot already executes the repo's own tools and ESLint config (400 Special Considerations). `defusedxml` isn't added.

### Patterns and Conventions
- Node-type, token-type and decision-point sets are module constants in the language module that owns them, as `_FUNCTION_TYPES` is in 400.
- A `MemoryError` raised by a tokenizer is not a per-file parse error: it fails the whole language's `duplicated_lines` (`tool_failed`), so the TypeScript adapter's token errors are `TypeScriptParseError` only.
- Coverage failures are data (`absent`), not exceptions. Only a git failure raises.
- Each absence and fallback logs at WARNING, following 400's `tool_support` builders.

## Implementation Details

### API Contracts

The CLI is unchanged: `sq metrology snapshot [--cwd PATH] [--json]`. The summary gains four lines per language:

```
  coverable_lines: 9120 in 412 file(s); 519 not in report [cobertura 7.x]
  covered_lines: 7804 in 412 file(s); 519 not in report [cobertura 7.x]
  cyclomatic_complexity: 11057 functions, p50 2, p90 6, max 41 [squadron-python-ast …]
  duplicated_lines: 2310 in 188 file(s) [squadron-python-ast …]
```

The numbers are illustrative only. The coverage "not in report" count is `len(tool_ignored_files)`. 400 already renders that field as "skipped by the tool's ignores", so the wording becomes metric-aware.

### Database / Storage Schema

No schema change, and no store change. The new metrics are enum values inside existing `Measurement` rows, and `schema_version` stays 1.

**Compatibility.** The architecture says there's no schema migration, and this slice adds none. That has a consequence, which this slice accepts knowingly: snapshot records written by 400 lack the four metrics, fail `LanguageSnapshot`'s every-metric validation, and are skipped by `_iter_records` with its existing WARNING. Every other record type still loads.
- **Why that's acceptable now.** 401 ships before any consumer of snapshot records exists: 403 and 420 aren't built, and 404 only writes. The only 400 records are the developer's own walkthrough snapshots. Re-snapshotting a commit replaces its record (400 D3).
- **Where users are told.** The CHANGELOG bullet states that snapshots from earlier versions are skipped and must be retaken, and so does `docs/COMMANDS.md`.

## Integration Points

### Provides to Other Slices
- **403:** complexity, duplication and coverage measurements with full identity. Complexity joins function length on (path, qualified name). The coverage rate is the sum of `covered_lines` over the sum of `coverable_lines`, compared only when the tool identity and report path match. 403's exported commits will have no coverage report, so coverage there is absent `report_missing` or `coverage_not_configured`. 403 reads only snapshots taken by 401 or later (Compatibility).
- **420:** the complete static snapshot.
- **404:** no change. The baseline's snapshot gains the metrics automatically.

### Consumes from Other Slices
- **400:** the contract, the absent-filling, the length pipeline, `default_registry()`, `tool_support` and preflight.

## Success Criteria

### Functional Requirements
1. Python and TypeScript snapshots carry present `cyclomatic_complexity` and `duplicated_lines` measurements. Each has a `counting` text giving its definition (D2, D3).
2. Complexity covers exactly the functions function length covers: the same count, and the same (path, qualified name) set.
3. Known fixtures give the expected values:
   - a function with `if`, `elif`, `and`, a comprehension with one `if` and an `except` scores 7 (the comprehension's `for` counts as well as its `if`, per D2)
   - a TypeScript function with `if`, `??`, a ternary and two non-default `case`s scores 6
   - a nested function's decisions don't count toward its parent
4. Two files sharing a block of at least 100 tokens report its lines as duplicated in both. A 99-token block isn't reported. Renamed identifiers aren't reported. A Python block and an identical TypeScript block aren't compared.
5. Coverage absences:
   - with `metrology.coverage_report` unset, both coverage metrics are `coverage_not_configured`
   - with a report path that doesn't exist, they're `report_missing`
   - with a report older than any tracked file, they're `report_stale`, and the detail names that file
6. With a fresh coverage.py Cobertura report, Python `coverable_lines` and `covered_lines` match the report's per-file line counts, and the totals match the report's root `lines-valid` and `lines-covered` for the files in the snapshot. Measured files missing from the report are in `tool_ignored_files`.
7. A fresh Istanbul Cobertura report gives present TypeScript coverage with version `0.1`, and the `counting` text states the provider limit.
8. A malformed report, or one with no root `version`, gives `tool_failed`.
9. A bad `metrology.coverage_report` value (absolute, or containing `..`) fails preflight before any tool runs.
10. A language whose token count passes `DUPLICATION_MAX_TOKENS` gets `duplicated_lines` as `tool_failed` with a WARNING naming the count and the ceiling, and its other metrics are unchanged. A test lowers the constant to trigger it.
11. The snapshot is still read-only (400 criterion 8). It's deterministic (400 criterion 4) for a fixed filesystem state. Coverage alone also depends on the report file and its mtime, so the same commit in a fresh clone gives `coverage_not_configured` or `report_missing`. 403 must read that as an absence, not as noise.
12. 400's file length and function length values are unchanged on the same commit.

### Technical Requirements
- ruff format, ruff check and pyright (zero errors) are clean, and the full suite passes.
- New modules stay at ~300 lines or less.
- Coverage parser tests use real reports: a coverage.py Cobertura file captured from squadron, and an Istanbul Cobertura file captured from a scratch vitest project, each stored as a fixture. This follows the parsing rule in CLAUDE.md.
- Failure-mode tests assert both the signal and the outcome for each row of the failure-mode table.
- 400's length tests pass, adjusted only for the `MeasuredFunction` and `measure_parse_metrics` renames.

### Integration Requirements
- `MetrologyRecord`, `CodeSnapshot`, `Measurement`, `LanguageAdapter`, `AdapterContext`, `take_snapshot` and the store are unchanged. The diff to `snapshot_models.py` is enum members only.
- `docs/COMMANDS.md` documents the new metrics and `metrology.coverage_report`. It and the CHANGELOG bullet both state that snapshots from earlier versions are skipped and must be retaken.

### Verification Walkthrough

The command exists. The metrics and the config key don't yet. Outputs describe structure, not exact numbers.

1. **New metrics on squadron.** On a clean tree, run `sq metrology snapshot`. The `python` section shows `cyclomatic_complexity` (a function count equal to `function_length`'s) and `duplicated_lines`. `covered_lines` and `coverable_lines` show `absent: coverage_not_configured`. `shell` shows all eight metrics as `no_adapter`.
2. **Function sets match.** Run `sq metrology snapshot --json | jq '.languages[] | select(.language=="python") | .measurements[] | select(.metric=="function_length" or .metric=="cyclomatic_complexity") | .distribution.count'`. Both numbers are equal.
3. **Produce a coverage report.** Run `uv run --with pytest-cov pytest --cov=src/squadron --cov-report=xml -q` (a subset such as `tests/metrology` is enough; the report must be written after the last change to any tracked file). This writes `coverage.xml` at the root, which is gitignored, and `git status --porcelain` stays empty. Add `"metrology.coverage_report" = "coverage.xml"` to `.squadron.toml`.
4. **Coverage present.** Run `sq metrology snapshot`. Python `coverable_lines` and `covered_lines` are present with `[cobertura 7.x]`. Files outside `src/squadron`, such as `tests/`, are counted as not in the report. Check the totals against `coverage.xml`: `xmllint --xpath 'string(/coverage/@lines-valid)' coverage.xml` equals the `coverable_lines` total.
5. **Stale report.** Run `touch src/squadron/__init__.py && sq metrology snapshot`. Coverage shows `absent: report_stale`, naming that file, and `git status --porcelain` is still empty because the content didn't change. Re-run step 3 to restore.
6. **Missing report.** Set the key to `nope.xml`. Coverage shows `absent: report_missing`. Restore the key.
7. **Bad key.** Set the key to `/tmp/coverage.xml`. The snapshot exits 1 with a preflight error before any tool runs. Restore the key.
8. **TypeScript.** Run `sq metrology snapshot --cwd ../context-forge`. The `typescript` section shows complexity and duplication from `squadron-tree-sitter-ts`, and coverage shows `absent: coverage_not_configured`, since context-forge has no coverage provider installed. File length and function length match 400's walkthrough on the same commit.
9. **TypeScript coverage.** In a scratch vitest project with `@vitest/coverage-v8`, a committed `.gitignore` for `coverage/`, and `coverage.reporter: ['cobertura']`, run `npx vitest run --coverage` and set `metrology.coverage_report = "coverage/cobertura-coverage.xml"`. Then `sq metrology snapshot --cwd <scratch>` shows TypeScript coverage present with `[cobertura 0.1]`.
10. **Determinism and old records.** Two `--json` runs are identical apart from `measured_at` (compare with `jq -S 'del(.measured_at)'`). `sq metrology list` prints `Skipping unreadable metrology record: <path>` for each snapshot record 400 wrote. Snapshots only measure HEAD, so a 400 record of an older commit can't be re-snapshotted; the warning stops when the stale record file is deleted or when HEAD is the commit it covers.

### Walkthrough Results

Run 20261024 on the slice branch at 06eba343 (all code committed). Tools: ruff 0.15.1, pyright 1.1.408, pytest-cov 7.1.0 with coverage.py 7.17.0, vitest 5.0.5 with `@vitest/coverage-v8` 5.0.5, Python 3.13.7. Squadron's `.squadron.toml` carries limits 300/50 and two exclusions.

| Step | Result |
|---|---|
| 1 | `python` section: `cyclomatic_complexity: 11204 functions, p50 1, p90 4, max 82`, `duplicated_lines: 1693 in 38 file(s)`, both from `squadron-python-ast 0.24.0+python3.13.7`; coverage `absent: coverage_not_configured`; `shell` all eight metrics `no_adapter` |
| 2 | `function_length` and `cyclomatic_complexity` distribution counts: 11204 and 11204 |
| 3 | `pytest --cov=src/squadron --cov-report=xml tests/metrology`: 6 minutes, all pass; `coverage.xml` written, `git status --porcelain` empty |
| 4 | `coverable_lines: 27902 in 393 file(s); 552 not in report [cobertura 7.17.0]`, `covered_lines: 11529 ...`. `xmllint` gives `lines-valid` 27902 and `lines-covered` 11529: equal to the snapshot totals |
| 5 | After `touch src/squadron/__init__.py`: `absent: report_stale (coverage.xml is older than tracked file src/squadron/__init__.py; ...)`; `git status --porcelain` empty |
| 6 | Key `nope.xml`: `absent: report_missing (nope.xml does not exist)` |
| 7 | Key `/tmp/coverage.xml`: `Error: metrology.coverage_report must be relative to the repository root, got '/tmp/coverage.xml'. Fix it with ...`, exit 1 |
| 8 | A clean clone of context-forge (its working tree held another session's uncommitted edits, so the snapshot refused it with the dirty-tree error and nothing was written there): `typescript` with complexity (5417 functions, 17 unparsed) and duplication from `squadron-tree-sitter-ts`; coverage `coverage_not_configured`. The same commit measured by the pre-401 code (`main`) and by this branch gives identical `file_length` and `function_length` measurements (Success Criterion 12) |
| 9 | Scratch vitest project, `coverage/` gitignored, `reporter: ['cobertura']`: `coverable_lines: 4 in 1 file(s); 2 not in report [cobertura 0.1]`, `covered_lines: 1 in 1 file(s)` |
| 10 | Two `--json` runs identical apart from `measured_at`. `sq metrology list` skipped the three 400-written records with `Skipping unreadable metrology record`. The old-commit records can't be re-snapshotted (corrected above) and were left in the store |

Caveats found while running it:
- **Success Criterion 3's Python fixture was 6 but D2 gives 7.** A comprehension always has a `for`, and D2 counts each comprehension `for` and `if`. The criterion text now says so.
- **Istanbul repeats a function's first line inside `<method>`.** Counting every `<line>` would not match the root `lines-valid`; the reader counts only `<class><lines>` entries (D4).
- **The task's "function length unaffected" for an untokenizable Python file can't hold:** `tokenize` and `ast.parse` fail on the same files, so such a file is unparsed for function length too. The tests assert that its file length is still counted.

## Implementation Notes

### Development Approach
1. Enum members.
2. `MeasuredFunction` and complexity: Python, then TypeScript, with fixture tests per decision point and 400's length tests green.
3. Tokenizers for both languages, then `duplication.py`.
4. The coverage key and preflight validation, then `CoverageReader` against captured fixtures, then the freshness check, the per-language measurements and the registry wiring.
5. Render, docs and CHANGELOG. Then the walkthrough.

### Special Considerations
- **Squadron's own coverage.** Squadron doesn't produce coverage today: there's no pytest-cov in `pyproject.toml`. The walkthrough uses `uv run --with pytest-cov`, which adds nothing to the project. Whether squadron's CI should produce a report is a separate decision, outside this slice.
- **Security.** Reading a report runs no code. The XML parsing exposure is noted under Technology Choices.
