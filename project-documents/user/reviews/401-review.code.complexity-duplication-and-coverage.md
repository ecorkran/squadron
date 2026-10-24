---
docType: review
layer: project
reviewType: code
slice: complexity-duplication-and-coverage
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: 5ef7fc58295f697385d6b905b36a2f7c494e7f2a
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 135178
cachedTokens: 0
cacheWriteTokens: 135176
completionTokens: 4378
durationSeconds: 38.8
costUsd: 0.591866
costBasis: provider
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: performance
    summary: "Coverage report is re-read, re-checked and re-parsed once per language"
    location: "src/squadron/metrology/snapshot/coverage.py#read_coverage"
  - id: F002
    severity: concern
    category: security
    summary: "Stdlib `xml.etree` parses a file with a `DOCTYPE` and no entity-expansion guard"
    location: "src/squadron/metrology/snapshot/coverage.py#read_cobertura"
  - id: F003
    severity: concern
    category: design
    summary: "TypeScript tokenizer re-parses every file and duplicates the parse and error-check logic"
    location: "src/squadron/metrology/snapshot/typescript_length.py#_tokenize"
  - id: F004
    severity: concern
    category: design
    summary: "`tool_ignored_files` is reused to mean \"not in report\", and the renderer must special-case it"
    location: "src/squadron/metrology/snapshot/render.py:21-23"
  - id: F005
    severity: concern
    category: correctness
    summary: "A hash collision can hide a real clone"
    location: "src/squadron/metrology/snapshot/duplication.py#_find_repeats"
  - id: F006
    severity: note
    category: style
    summary: "Minor test and style nits"
    location: "tests/metrology/snapshot/test_duplication.py#test_tokenizer_error_and_unreadable_file_leave_the_other_files_compared"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Exception handling, failure observability and test coverage"
    location: "src/squadron/metrology/snapshot/duplication.py#_tokenize_file"
---

# Review: code — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Coverage report is re-read, re-checked and re-parsed once per language

`PythonAdapter.measure` and `TypeScriptAdapter.measure` each call `read_coverage(ctx.repo_root)`, and nothing caches the result. A single snapshot therefore runs `git ls-files -z`, an `lstat` of every tracked file and a full XML parse once per language. Each warning is also logged once per language, and `test_missing_report_is_report_missing_with_one_warning_per_language` asserts that duplicated log line. The module docstring says "each adapter builds its own measurements from one reading", but the code does not do that. On a large repo the `lstat` loop is the dominant cost. Read the report once in the orchestrator, or cache it per `(repo_root, mtime)`. Pass the reading to the adapters through `AdapterContext`.

### [CONCERN] Stdlib `xml.etree` parses a file with a `DOCTYPE` and no entity-expansion guard

`ElementTree.parse` is vulnerable to entity-expansion attacks (billion laughs). The Istanbul fixture carries a `<!DOCTYPE>`, so these reports can contain DTD declarations. The report is a project-local, gitignored file, so the risk is low. Still, a checked-out PR or third-party artifact could supply it. Use `defusedxml`, or reject any report containing `<!ENTITY`, and add a test.

### [CONCERN] TypeScript tokenizer re-parses every file and duplicates the parse and error-check logic

`_tokenize` repeats the parser selection, `.parse(...)` call and `has_error` raise from `_extract_functions`. Each file is parsed twice per snapshot, once for length and complexity and once for duplication. Extract a shared `_parse_checked(path, text)` helper at minimum. `typescript_length.py` now also holds duplication tokenization (`measure_typescript_duplication`), which no longer matches the module name or its single responsibility. A `typescript_duplication.py` sibling would match how `python_complexity.py` and `typescript_complexity.py` are split.

### [CONCERN] `tool_ignored_files` is reused to mean "not in report", and the renderer must special-case it

For coverage metrics, `tool_ignored_files` holds files the report does not mention. `render._REPORT_METRICS` then compensates by relabelling the text. This overloads one field with two meanings, selected by metric identity. It will grow another branch with every new report-based metric (OCP). `_per_file_measurement` also branches on `metric is COVERABLE_LINES`. A dedicated field, such as `not_in_report_files`, or a per-metric value extractor would keep the semantics explicit.

### [CONCERN] A hash collision can hide a real clone

`first_seen.setdefault` keeps only the first window for each hash. If two different windows collide, the second one is never recorded. A true later copy of that second window is compared against the first window, fails the id comparison, and is missed. The comment "a hash collision must never make a clone" covers false positives only. At a 61-bit modulus the chance is very low, but the result is a silent undercount. Either store a list per hash or document the limit in `DUPLICATION_COUNTING`.

### [NOTE] Minor test and style nits

The test calls `run(...)` and then immediately overwrites `measured` with a second `measure_duplication` call, so the first assignment is dead. In `coverage.py`, `_COVERAGE_ROOT_TAG` is declared mid-module between functions. The mtime-based freshness tests depend on filesystem timestamp granularity. They use 5 to 10 second offsets, which is fine, but `test_report_with_the_same_mtime...` relies on exact-ns `utime` support.

### [PASS] Exception handling, failure observability and test coverage

Swallowed exceptions are specific types and are logged at WARNING. `MemoryError` is re-raised and then turned into a `tool_failed` measurement with a message. The `git ls-files` failure logs at ERROR and raises. Every absence and failure reason has a test asserting the logged signal. Python and TypeScript complexity have per-node parametrized cases, and the Cobertura reader is tested against real coverage.py and Istanbul fixtures, as the parsing rules require.

## Response

Addressed 20261024.

- **F001 (report read once per language): not changed.** Slice design "One read per adapter, no cache" (Data Flow) decides this: the `git ls-files` and `lstat` cost was weighed against injecting a shared reading through `AdapterContext`, and `AdapterContext` is frozen by the slice's contract. The docstring is accurate: one reading per adapter.
- **F002 (XML entity expansion): not changed.** Slice design, Technology Choices, accepts this: supported Pythons ship an expat with entity-expansion protection, and the snapshot already executes the repository's own tools. The report is a local gitignored file.
- **F003 (TypeScript tokenizer): fixed.** `parse_checked` in `typescript_length.py` is the one parse-and-error-check, used by both the function walk and the tokenizer. The duplication code moved to `typescript_duplication.py`, beside `typescript_complexity.py`. Parsing each file twice is kept (slice design D1: costs little next to the lint tools).
- **F004 (`tool_ignored_files` meaning): not changed.** Slice design D4 puts files the report doesn't list in `tool_ignored_files`, and the `Measurement` model is frozen by the slice's contract. The renderer's wording is one constant (`_REPORT_METRICS`).
- **F005 (hash collision hides a clone): fixed.** `_find_repeats` now keeps every distinct window seen per hash, and a collision adds an entry. Regression test: `test_a_hash_collision_does_not_hide_a_later_real_clone`.
- **F006 (nits): fixed.** The dead assignment in the duplication test is gone, and `_COVERAGE_ROOT_TAG` is with the other module constants. The `os.utime` nanosecond timestamps work on the supported filesystems; the tests use 5 to 10 second offsets.

### Run Digest

- Response length: 4800 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 135178 / 0 / 135176 / 4378 / not computed
- Duration: 38.8 s
- Cost: $0.59 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
