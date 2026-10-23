---
docType: review
layer: project
reviewType: slice
slice: complexity-duplication-and-coverage
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: 9472fe1555c7e94be3b3d35f47bd6e6162d1ccca
revision_number: 2
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 7
turns: 8
promptTokens: 409120
cachedTokens: 321602
cacheWriteTokens: 87506
completionTokens: 4176
durationSeconds: 36.3
costUsd: 0.424698
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: error-handling
    summary: "Duplication memory bound has no failure handling"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D3 — Duplication definition and bound"
  - id: F002
    severity: concern
    category: scope
    summary: "Design weight that can be cut or deferred"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Component Structure"
  - id: F003
    severity: note
    category: architecture-alignment
    summary: "Coverage is not tied to the environment identity the architecture describes"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D4 — Coverage comes from a Cobertura XML report, for both languages"
  - id: F004
    severity: note
    category: architecture-alignment
    summary: "Determinism design goal is partly relaxed for coverage"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Functional Requirements"
  - id: F005
    severity: pass
    category: architecture-alignment
    summary: "Contract and boundary preservation"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Integration Requirements"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Absent-is-not-zero, measure-never-gate and coarse records"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D4 — Coverage comes from a Cobertura XML report, for both languages"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated for the new I/O paths"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Architecture"
  - id: F008
    severity: pass
    category: architecture-alignment
    summary: "Compatibility consequence is stated and bounded"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Database / Storage Schema"
---

# Review: slice — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Duplication memory bound has no failure handling

The slice states that duplication memory is linear in tokens, at about 133 bytes per token. It says a repo ten times squadron's size needs over 1 GiB. The failure-mode table does not cover the duplication pass running out of memory (`MemoryError`, or the OS killing the process). The architecture's "Cheap to start measuring" goal and the brownfield use (440) make a large repo likely. As written, the outcome would be a crash with no observable signal, or a lost snapshot.
- Name the handling. For example, a token-count ceiling checked before the pass makes `duplicated_lines` `tool_failed`, with a WARNING naming the count.
- Or state explicitly that the process fails loudly. Either way, add a row to the failure-mode table and a test.
- #254 defers a lighter index. It does not specify what happens in the meantime.

### [CONCERN] Design weight that can be cut or deferred

Several parts are heavier than the slice plan's success criteria need:
- **`CoverageReader` registry cache.** Criterion 10 (one parse and one freshness check per snapshot) drives a constructor-injected, repo-root-keyed cache. That adds a stateful object, new wiring in `registry.py` and a fake-reader test seam. The cost it saves is one XML parse plus one `git ls-files` call. A plain function that returns a reading, called once per adapter, would meet the plan's "recorded when the report exists and matches the commit" criterion. If the cache stays, justify it by measured cost.
- **Narrative restated from other documents.** The Value section, the Provides/Consumes lists and the long Technology Choices note on XML parsing repeat 400 or the architecture.
- **Per-file maximum complexity.** The `per_file` maximum-complexity values go beyond the plan's "complexity measured and counting stated". Consider shipping the distribution only.
- **`MeasuredFunction` and `measure_parse_metrics` renames.** These touch every 400 length test (Technical Requirements). They are churn that a new field alone would not need.
- The plan assigns all of complexity, duplication and coverage to 401. No assigned scope is dropped.

### [NOTE] Coverage is not tied to the environment identity the architecture describes

The architecture says coverage is "measured only when the project's environment is resolved, and the snapshot records the environment's identity (lockfile hash)." The slice replaces that with an mtime freshness rule. This matches the slice plan's "report exists and matches the commit" criterion and the architecture's note that reading an existing report is the cheaper starting point. Dependency installation stays in Future Work. The slice should say in one line that the environment/lockfile rule is deliberately replaced by D5 for report-based coverage. That way 403 and 420 do not assume a lockfile hash is attached to coverage.

### [NOTE] Determinism design goal is partly relaxed for coverage

The architecture's goal is the same value on the same commit with the same tool versions and environment. Coverage also depends on the report file and its mtime. Criterion 11 states this openly and tells 403 to treat the result as an absence rather than noise. That is the right handling, and no change is needed. The `counting` text should carry the caveat so a report reader sees it.

### [PASS] Contract and boundary preservation

`MetrologyRecord`, `CodeSnapshot`, `Measurement`, `LanguageAdapter`, `AdapterContext`, `take_snapshot` and the store are unchanged. Only enum members are added, and the reader is injected through adapter constructors. This meets the slice plan's criterion that no envelope or contract change is needed beyond new enum members. Dependency direction is correct: adapters depend on the coverage reader, not the reverse.

### [PASS] Absent-is-not-zero, measure-never-gate and coarse records

- **Absence reasons.** `coverage_not_configured`, `report_missing`, `report_stale` and `tool_failed` are all explicit.
- **Zeros.** Zeros in `per_file` mean "in the report, untested", and unlisted files go to `tool_ignored_files`.
- **No gates.** There are no complexity limits and no over-limit rows.
- **Coarse records.** There are no per-function rows and no clone-pair records, consistent with the coarse-records principle.
- **Counting definitions.** Each metric's counting definition is stated in the tool identity, as the architecture's Technical Considerations require.

### [PASS] Failure modes are enumerated for the new I/O paths

The table covers the following, each with handling, a signal and a test requirement:
- tokenizer failures
- recursion errors
- malformed XML
- `OSError` on the report or tracked files
- a git hang, `None` result or non-zero exit

The only gap is the memory case raised above. The architecture states no numeric NFR for these paths, so nothing needs restating.

### [PASS] Compatibility consequence is stated and bounded

Records written by 400 fail the every-metric validation and are skipped with a WARNING. The slice accepts this because no consumer exists yet. It records the reason and tells users in the CHANGELOG and `docs/COMMANDS.md`. This still satisfies "no schema migration, existing record types still load", since other record types are unaffected.

### Run Digest

- Response length: 6968 chars
- Response is newline-free: no
- Tool calls made: 7
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 8
- Tokens — prompt / cached / cache write / completion / reasoning: 409120 / 321602 / 87506 / 4176 / not computed
- Duration: 36.3 s
- Cost: $0.42 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8

## Response

Applied to the design on 20261023.

- **Duplication memory (CONCERN): fixed.** D3 adds `DUPLICATION_MAX_TOKENS = 4_000_000` per language. Passing it, or a `MemoryError`, makes `duplicated_lines` `tool_failed` with a WARNING naming the count and ceiling. The failure-mode table has the row, and criterion 10 requires a test that lowers the constant.
- **Design weight (CONCERN): partly applied.**
  - `CoverageReader` cache: cut. Each adapter calls `read_coverage(repo_root)`; a two-language project reads the report twice. Registry wiring and the fake-reader seam are gone, and the one-parse criterion is dropped.
  - Per-file maximum complexity: cut. Complexity is a distribution only.
  - `MeasuredFunction` / `measure_parse_metrics` renames: kept. Adding a complexity field to a type named `FunctionLength` would be a misleading name, and the churn is a mechanical rename in 400's length tests.
  - Restated narrative: left. The text is short and each restatement orients a reader of this document alone.
- **Environment identity (NOTE): done.** D5 states that the mtime rule deliberately replaces the lockfile rule for coverage.
- **Determinism (NOTE): done.** D5 says the `counting` text carries the caveat.
