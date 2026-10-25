---
docType: review
layer: project
reviewType: tasks
slice: code-review-normalization-and-ingest
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: df5485be677355545407258fc2e81be6ef8a748c
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 3
turns: 4
promptTokens: 188169
cachedTokens: 91403
cacheWriteTokens: 96760
completionTokens: 5591
durationSeconds: 44.7
costUsd: 0.452837
costBasis: provider
runId: run-20261025-p5-b605399d
squadronVersion: 0.24.1
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "Partial-progress reporting conflicts with the ingest return design"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:181"
  - id: F002
    severity: concern
    category: completeness
    summary: "`replaced` count has no source in the store API"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:135"
  - id: F003
    severity: concern
    category: test-coverage
    summary: "Ingest behaviors in the design have no test in Task 21"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:185-195"
  - id: F004
    severity: concern
    category: sequencing
    summary: "Stale cross-reference in Task 7"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:87"
  - id: F005
    severity: concern
    category: task-sizing
    summary: "Task 20 is oversized"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:170-182"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Test-with pattern is batched for Tasks 9–11"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:95-112"
  - id: F007
    severity: note
    category: proportionality
    summary: "Overlap between Task 4 and Task 6 item 3"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:61"
  - id: F008
    severity: note
    category: task-format
    summary: "Task 26 mixes a step with success criteria"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md:232"
  - id: F009
    severity: pass
    category: coverage
    summary: "Coverage of success criteria"
    location: "project-documents/user/tasks/402-tasks.code-review-normalization-and-ingest.md"
---

# Review: tasks — slice 402

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Partial-progress reporting conflicts with the ingest return design

Task 20 returns a result dataclass only on completion, and `MetrologyStoreError` propagates. Task 22 requires that on `MetrologyStoreError` the CLI "print what was written so far". Task 23 tests that the partial count is printed. Once the exception propagates, the counts accumulated inside the ingest function are gone, so Task 22 cannot meet this. Task 20 needs a mechanism, for example a caller-supplied result object that is mutated as it goes, or an exception that carries the partial result. A junior would otherwise have to invent one.

### [CONCERN] `replaced` count has no source in the store API

Task 20 counts `replaced` when "a record with that id already existed". Task 15's `write_code_review(record) -> str` does not say what it returns or how existence is reported. Ingest could list existing records first, but no task says to. Specify one mechanism. For example, have `write_code_review` report whether it replaced a record, or have ingest read the project's existing ids once before the loop. Task 16 should then test it.

### [CONCERN] Ingest behaviors in the design have no test in Task 21

Two behaviors that Task 20 implements are untested:
- Dropping a finding whose severity is outside `Severity` and counting it in `unnormalized_count` (D6).
- A write-time file whose stored category isn't a `ReviewCategory` value, which must fail the file.

Task 19 has no fixture for either. Add a synthetic fixture for each and one assertion each in Task 21.

### [CONCERN] Stale cross-reference in Task 7

Task 7 says `lenient_category_key` is exposed "so Task 15 reuses it". Task 15 is the envelope and store task. The alias table in Task 17 is the consumer. A junior following the pointer would look in the wrong place. Change it to Task 17.

### [CONCERN] Task 20 is oversized

Task 20 is rated Effort 4 and bundles input resolution, per-file parsing and failure collection, skip classification, slice-index extraction, severity and category handling for two file formats, and replace counting. It must also stay within the ~50-line function limit. Split it into two tasks:
- Path and directory resolution, plus the per-file read, parse and classify step.
- Record building: slice index, findings, categories and the replace count.

Both would sit under the existing Task 21 test checkpoint.

### [CONCERN] Test-with pattern is batched for Tasks 9–11

Tasks 9, 10 and 11 are three implementation tasks. Their tests all land in Task 12, with no verification between them except the existing suites. Task 12 is Effort 3 and covers models, persistence and the client. Move the model and persistence tests next to Tasks 9 and 11. Keep the client tests with Task 10. Each task then follows the test-with pattern.

### [NOTE] Overlap between Task 4 and Task 6 item 3

Task 4 asserts that the built-in `code` template loads with the flag true and `arch`/`slice`/`tasks` load with it false. Task 6 item 3 asserts the same facts from the YAML files. Keep the absent-key and non-bool cases in Task 4 and drop the built-in assertions. Task 6 already covers them and also fails on drift.

### [NOTE] Task 26 mixes a step with success criteria

The "ingest again; `read_side_mapped` is false" item is written as an action line. It is really a success criterion from the walkthrough. Mark it as `Success:`.

### [PASS] Coverage of success criteria

- FR1 and FR2: Tasks 5, 10, 11, 12 and 26.
- FR3 and FR4: Tasks 20–23.
- FR5: Tasks 21 and 23 (failure-mode table).
- FR6: Tasks 17, 18 and 21.
- FR7: the `arch` case in Task 12 and the flag tests in Tasks 4 and 6.
- Integration requirement: the findings-addressed test in Task 13.
- Sync test: Task 6.
- Walkthrough steps 1–4: Tasks 24 and 26.
- CHANGELOG and validation: Task 25.

No task is scope creep. The slice states no NFR, so no load test or CI-gating task is needed. The four fixture files that Task 19 copies exist under `project-documents/user/reviews/`.

### Run Digest

- Response length: 5327 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 188169 / 91403 / 96760 / 5591 / not computed
- Duration: 44.7 s
- Cost: $0.45 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
