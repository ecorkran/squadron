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
reviewedSha: 4a293a065a383d089e93903d91c8d0e83ce93ef3
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 180043
cachedTokens: 85854
cacheWriteTokens: 94183
completionTokens: 5939
durationSeconds: 53.4
costUsd: 0.445451
costBasis: provider
runId: run-20261023-slices-plan-3d287756
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: pass
    category: architecture-alignment
    summary: "Contract holds and metric identity is stated"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Architecture"
  - id: F002
    severity: concern
    category: scope-creep
    summary: "Store back-fill on read goes beyond the slice plan's \"enum members only\" and is cuttable"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Database / Storage Schema"
  - id: F003
    severity: concern
    category: correctness
    summary: "Freshness rule cannot detect deleted tracked files, so D5's \"proves produced from HEAD\" claim is overstated"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D5"
  - id: F004
    severity: concern
    category: error-handling
    summary: "Failure-mode table omits several I/O cases on the new coverage and git paths"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Architecture (Failure modes table)"
  - id: F005
    severity: concern
    category: proportionality
    summary: "Proportionality: multi-report merging and some defensive mechanisms serve cases the slice does not have"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D4, #D6"
  - id: F006
    severity: note
    category: behavior-change
    summary: "Refactor couples function-length results to tokenizer success"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#Failure modes, D7"
  - id: F007
    severity: note
    category: code-structure
    summary: "Hard-coded comparison values should live in one place"
    location: "project-documents/user/slices/401-slice.complexity-duplication-and-coverage.md#D3, #D6"
---

# Review: slice — slice 401

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [PASS] Contract holds and metric identity is stated

The new metrics are enum members plus adapter code. Each carries a `counting` text covering the arch's "each adapter must state how it counts" (D1–D4). Complexity and function length share function identity (D1), so 403 can join them on (path, qualified name). Complexity has no limit and no per-function rows, which matches the arch rule that per-function rows exist only for functions over a project-declared limit. Dependency direction is sound: the adapters and preflight depend on `coverage.py`, and `complexity.py` and `duplication.py` are language-agnostic.

### [CONCERN] Store back-fill on read goes beyond the slice plan's "enum members only" and is cuttable

The slice plan's 401 criterion is "no change to the record envelope or adapter contract beyond new enum members". The arch says "no schema migration". This slice adds a read-path shim in 320's store, which the arch says is reused as is. The shim exists to preserve a handful of developer-run 400 records, such as the walkthrough commit 71674382. Re-snapshotting replaces a record (400 D3), so regenerating those records costs one command each. Two options meet the requirement:
- **Cut the shim.** Regenerate the old records and drop the store change, the fixture test and the Risk section. Silent skipping of invalid records is existing 400 behavior, so the slice should at least log at WARNING when `_iter_records` skips a `code_snapshot`.
- **Keep the shim.** State why it is needed, for example that 400 records exist outside the developer's machine. As written, the Integration Requirements say the "one non-adapter change" is acceptable but do not justify it.

### [CONCERN] Freshness rule cannot detect deleted tracked files, so D5's "proves produced from HEAD" claim is overstated

The check compares the report's mtime to the newest mtime among files in `git ls-files`. A checkout or revert that only deletes tracked files leaves no mtime on any remaining file. A report from the previous tree is then accepted as fresh, although its covered lines include files that no longer exist. D5's "What it can't catch" lists copying and `touch` but not this case. Either add the case to the list and the `counting` text, or also compare against the directory mtimes of the deleted paths. A second option is to fail the check when the report lists a file that no longer exists in the tree. That check is cheap, because the reader already maps `filename` to repo paths.

Related: the determinism criterion (criterion 10) holds for a fixed filesystem state, but coverage presence on the same commit now depends on mtimes. A fresh clone of a commit always yields `report_missing`. Say so in the determinism criterion so 403 does not read it as noise.

### [CONCERN] Failure-mode table omits several I/O cases on the new coverage and git paths

The table covers malformed XML, bad `hits`, git failure and `OSError` on the report. It does not enumerate:
- **`stat` failure during the freshness check.** A tracked symlink whose target is missing, or a submodule path, makes `stat` raise `OSError` or `FileNotFoundError`. The design does not say whether that is `tool_failed`, a skipped file, or an error.
- **Hang or timeout on `git ls-files` or on parsing a very large report.** It does not say whether `run_git`'s timeout applies, nor whether the report is parsed whole or streamed (`iterparse`). Cobertura files for large repos can be tens of MB.
- **Wrong absence reason.** A report that exists and parses but lists none of this language's files maps to `report_missing` (Data Flow). A Python-only report in a Python+TS repo then tells TypeScript the report is missing, when the report exists and TypeScript is not in it. Add a distinct reason, or at least a detail string that distinguishes the two, so 403 does not misreport it.
Each case needs an explicit handling strategy and an observable signal at WARNING or above, per the failure-mode rule.

### [CONCERN] Proportionality: multi-report merging and some defensive mechanisms serve cases the slice does not have

Squadron is a single-package Python repo, and the TypeScript target in the walkthrough is context-forge, a separate repo. Several mechanisms in D4 and D6 handle cases neither repo has:
- **Several reports in one list.** This brings merging across reports and across `<class>` entries (union of coverable lines, any-hit covered), joined versions in sorted order, and the "any stale report makes all absent" rule. A single `metrology.coverage_reports` path per project covers both repos. Multiple reports can be added when a monorepo needs them, since the config value stays comma-parseable.
- **Hashing `[tool.coverage]` or `.coveragerc` for the rule set.** This parallels lint and is consistent with 400, but it is optional. `tool-defaults` for both languages would meet "coverage recorded or absent with reason", and the rule-set hash can be deferred.
- **64-bit token hashing in duplication.** Memory-bounded hashing is reasonable. The slice should state the target repo size that justifies it, or use the simpler hash-of-token-text tuple approach until a measured repo needs more.
Cutting multi-report support alone removes the largest block of D4 and D5 logic and several tests.

### [NOTE] Refactor couples function-length results to tokenizer success

A file that `ast` parses but `tokenize` rejects is moved to `unparsed_files` for function length too. Previously function length would have counted it. This is rare and is chosen deliberately so the function sets match (criterion 2). D7 says 400's length tests pass unchanged, so add one test that records the behavior change.

### [NOTE] Hard-coded comparison values should live in one place

`DUPLICATION_WINDOW_TOKENS = 100` appears in the `counting` text as well as the constant, and the token-type and node-type sets are spread across modules. Build the `counting` text from the constant so the two cannot drift. The arch requires the definition difference to be part of the tool identity, so this matters for identity as well as for DRY.

### Run Digest

- Response length: 7492 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 180043 / 85854 / 94183 / 5939 / not computed
- Duration: 53.4 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 7
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 7
- Finding-shaped matches — surviving validation: 7
