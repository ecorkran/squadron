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
reviewedSha: 5ff41c17611b4f2c9d3d6792606de88377edb34c
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 176206
cachedTokens: 88601
cacheWriteTokens: 87599
completionTokens: 2990
durationSeconds: 26.3
costUsd: 0.389898
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: proportionality
    summary: "Slice is heavier than the plan entry requires: three coverage-freshness mechanisms and a pipeline refactor"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D5"
  - id: F002
    severity: concern
    category: proportionality
    summary: "Duplication token-window design is the heaviest option and stores every token in memory"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D3"
  - id: F003
    severity: concern
    category: boundaries
    summary: "Per-metric freshness check duplicates git/filesystem work per adapter and puts coverage I/O in the adapter layer"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Data-Flow"
  - id: F004
    severity: concern
    category: scope
    summary: "Behavior change to 400's function length is bundled into this slice"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D7"
  - id: F005
    severity: concern
    category: integration
    summary: "Old-record handling relies on a WARNING skip rather than an explicit compatibility statement against the architecture's \"no schema migration\" principle"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Database--Storage-Schema"
  - id: F006
    severity: pass
    category: architecture-alignment
    summary: "Contract boundaries and dependency direction hold"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Component-Structure"
  - id: F007
    severity: pass
    category: error-handling
    summary: "Failure modes are enumerated with handling and observable signals"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Data-Flow"
  - id: F008
    severity: note
    category: nfr
    summary: "No NFR in the parent architecture applies to this path"
    location: "project-documents/user/architecture/400-arch.code-quality-measurement.md"
---

# Review: slice — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Slice is heavier than the plan entry requires: three coverage-freshness mechanisms and a pipeline refactor

The plan entry (effort 3/5) asks for three things. Complexity and duplication must be measured for both languages, each with a stated counting rule. Coverage must be recorded when a report exists and "matches the commit", and otherwise be absent with a reason. Enum members alone must suffice, with no contract change. The design meets these, but it adds more than that. These items could be cut or deferred:

- **The deleted-files check (D5 check 2).** It adds a `git ls-files` comparison against every reported path and the `report_stale` detail. The design admits it still misses a deleted file the report never listed. The mtime check against all tracked files already rejects a report written before any checkout or edit. The extra check covers a narrow case (a report plus a later pure deletion). Cut it, or defer it until someone hits that case.
- **The `language_not_in_report` absence reason and the "file listed twice means `tool_failed`" rule.** Neither writer ever produces a duplicate entry. The design says so itself. A defensive failure mode for a case that doesn't occur is scope the slice doesn't need. `language_not_in_report` can be folded into "all files in `tool_ignored_files`".
- **The large-report INFO line and its test row.** The design says the report is parsed whole, in-process, "same as 400's parsers". A message that exists only to trace a hypothetical stall is speculative.
- **The `lstat`/symlink failure row.** It is thin enough to merge with the generic `OSError` row.

### [CONCERN] Duplication token-window design is the heaviest option and stores every token in memory

D3 keeps full token text for every file, hashes 100-token windows at every offset, and verifies collisions token for token. It marks every line under every occurrence. It also adds rules for overlapping same-file ranges. The memory sizing rests on one data point ("931 Python files, nothing measured needs a more compact form"). The architecture's goals are "cheap" and "works on code squadron didn't write". Brownfield repos larger than squadron are the stated target (440).

Rolling hashes with collision verification, or a suffix-based approach, are lighter options. At minimum, state a memory and time bound for the window pass on a larger repo. Without one, an unbounded in-process pass is a hidden NFR risk on exactly the repos this feature is aimed at. The architecture does not set a numeric NFR here, so this stays a CONCERN.

### [CONCERN] Per-metric freshness check duplicates git/filesystem work per adapter and puts coverage I/O in the adapter layer

Each adapter calls `coverage.measure_coverage` independently. The freshness check (`git ls-files` plus `lstat` of every tracked file) and the full Cobertura parse therefore run once per language, and the design accepts this ("twice on a project with both languages"). The report is one project-level file and its freshness is language-independent. Only the path filtering is per-language.

Hoisting the freshness check and parse into a single project-level step would remove the duplicated I/O and the duplicated warnings and failure rows. It would also make a git failure surface once. This needs a way to pass the result to adapters without touching `AdapterContext`, which the design promises to keep unchanged. Say how the design reconciles those two things. As written, the per-adapter structure is the cost of that constraint rather than a choice made on the merits.

### [CONCERN] Behavior change to 400's function length is bundled into this slice

D7 changes 400's function-length results. A Python file that `ast` parses but `tokenize` rejects now drops out of function length. The design justifies it as keeping the function sets equal (criterion 2). Dropping already-measured data from a shipped metric to simplify a new one reverses the direction of the dependency. It also silently changes comparability with 400-era snapshots on the same commit.

The design already requires all records written by 400 to be retaken. It states the tool version includes the squadron version, but it does not say that this specific counting change is recorded in the function-length `counting` text. Either record the change in the function-length identity, or keep function length independent of the token stream, so complexity and duplication are the only metrics that drop such a file.

### [CONCERN] Old-record handling relies on a WARNING skip rather than an explicit compatibility statement against the architecture's "no schema migration" principle

The architecture says "no new store, no schema migration", and the plan requires that existing record types still load. This slice makes every 400 snapshot record fail validation and get skipped with a WARNING. The reason given is that the only such records are the developer's own walkthrough snapshots. That is a reasonable justification for now, but it is a stated assumption. Nothing in the slice or the plan checks it, and the architecture's consumers (403, 420) read these records.

State the dependency explicitly: 401 must not release before 403 consumers exist, or old records are knowingly dropped. Alternatively, record the assumption in the CHANGELOG. This is cheap to fix and only needs a sentence.

### [PASS] Contract boundaries and dependency direction hold

New metrics land as enum members plus adapter code. The envelope, `Measurement`, `LanguageAdapter` and `AdapterContext` are unchanged, which matches the plan's success criterion. Complexity and duplication are in-process and need no installed tools or environment, so the architecture's "type counts and coverage need the environment" constraint is respected. Reading an existing report is the cheaper path the architecture recommended. Absent-with-reason is applied to every coverage case, so "absent is not zero" holds. Counting definitions sit in `ToolIdentity.counting`, which meets the architecture's requirement that a definition difference be part of the identity. Measure-never-gate is untouched.

### [PASS] Failure modes are enumerated with handling and observable signals

The failure-mode table covers each new I/O path: report read, XML parse, git ls-files hang or non-zero exit, and lstat. Each has an explicit outcome and a log level. Technical Requirements require a test per row asserting both signal and outcome. Git failures raise and are never treated as fresh. Coverage failures are data rather than exceptions, which fits CLAUDE.md's fail-explicitly rule.

### [NOTE] No NFR in the parent architecture applies to this path

The architecture states no latency or throughput targets for snapshot paths, so nothing needs restating. The only quantitative statement is the 931-file note in D3. See the duplication finding above if a bound on larger repos is wanted.

### Run Digest

- Response length: 7902 chars
- Response is newline-free: no
- Tool calls made: 3
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 4
- Tokens — prompt / cached / cache write / completion / reasoning: 176206 / 88601 / 87599 / 2990 / not computed
- Duration: 26.3 s
- Cost: $0.39 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 8
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 8
- Finding-shaped matches — surviving validation: 8
