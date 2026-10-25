---
docType: review
layer: project
reviewType: code
slice: code-review-normalization-and-ingest
targetKind: slice
rulesSource: project
conventionsSource: AGENTS.md
projectRules: [python.md, sql.md, testing.md]
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/slices/402-slice.code-review-normalization-and-ingest.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261024
dateUpdated: 20261024
reviewedSha: ff99da8d689b1bdd39603d8c6a4ebba8313d0b6f
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 0
diffTruncated: false
turns: 1
promptTokens: 63453
cachedTokens: 2921
cacheWriteTokens: 60530
completionTokens: 3108
durationSeconds: 26.5
costUsd: 0.306417
costBasis: provider
squadronVersion: 0.24.1
categoriesNormalized: true
findings:
  - id: F001
    severity: concern
    category: error-handling-observability
    summary: "Findings with an unrecognized severity are dropped without a warning or a summary count"
    location: "src/squadron/metrology/review_ingest.py#_finding"
  - id: F002
    severity: note
    category: consistency-rot
    summary: "Relative `PATHS` resolve against the process directory, not `--cwd`"
    location: "src/squadron/cli/commands/metrology_review_ingest.py#ingest_reviews_command"
  - id: F003
    severity: note
    category: architectural-decay
    summary: "Duplicated record-id hashing"
    location: "src/squadron/metrology/store.py#code_review_record_id"
  - id: F004
    severity: note
    category: other
    summary: "Re-ingest never prunes records for deleted review files"
    location: "src/squadron/metrology/review_ingest.py#ingest_reviews"
  - id: F005
    severity: note
    category: type-contract-debt
    summary: "Test helper `record_for` lacks a return annotation"
    location: "tests/metrology/test_review_store.py:28"
  - id: F006
    severity: pass
    category: other
    summary: "Design, exception handling and test coverage"
    location: "src/squadron/review/categories.py"
---

# Review: code — slice 402

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] Findings with an unrecognized severity are dropped without a warning or a summary count

`_finding` returns `None` when a finding's severity isn't on the review scale. `_findings` counts the drop in `unnormalized_count`. Nothing logs it at WARNING or higher, and `_echo_summary` in `src/squadron/cli/commands/metrology_review_ingest.py` doesn't report it. The count is visible only by reading the stored JSON, so a review can lose findings and still show as ingested cleanly. That undercounts findings, and the project's failure-mode rule says each failure must be observable. Log a warning with the file path and finding id. Also add the dropped count to the CLI summary line. The existing test `test_an_unrecognized_severity_is_counted_and_dropped` should then assert the log.

### [NOTE] Relative `PATHS` resolve against the process directory, not `--cwd`

`--cwd` is documented as the "Project root", but relative `PATHS` are used as given, so they resolve against the shell's current directory. `_review_path` resolves them the same way before computing the repo-relative key. Running `sq metrology ingest-reviews reviews --cwd /other/project` therefore finds the wrong directory, or stores absolute paths and so different record ids. Either resolve relative paths against `repo_root` or document that they are relative to the shell.

### [NOTE] Duplicated record-id hashing

`code_review_record_id` repeats the project-digest and path-digest pattern of `snapshot_record_id`. Two uses are tolerable. If a third deterministic id appears, extract a shared `_digest(value)` helper.

### [NOTE] Re-ingest never prunes records for deleted review files

A record is keyed on project and path, so a review file that was deleted or renamed leaves a stale `code_review` record behind. Renamed files produce duplicates. This is acceptable for now, but note it as a limit if the records feed baseline counts.

### [NOTE] Test helper `record_for` lacks a return annotation

`record_for` has no return type. The Python rules put tests under strict pyright and require hints on all signatures. Annotate it as `-> CodeReviewRecord`.

### [PASS] Design, exception handling and test coverage

The shared vocabulary lives in a leaf module, and sync tests guard the vocabulary across the enums and the `code` template. Strict write-time matching is kept separate from the read-side historical map. Exception handling follows the rules: `_FileProblem` is raised narrowly and reported with a WARNING, and store errors surface the partial result at the CLI process boundary. Tests cover the fixture classification, the re-ingest replacement, the partial-write failure and the CLI exit codes.

## Response

Addressed 20261025.

- **F001 (unrecognized severity dropped silently): fixed.** Each drop now logs a WARNING with the file and finding id, `IngestResult.dropped_findings` totals them, and the CLI prints a `Dropped:` line when it is non-zero. The ingest test asserts the log and the count.
- **F002 (relative `PATHS` vs `--cwd`): documented.** Relative paths are relative to the shell's current directory, which is the usual CLI meaning, and record ids are computed from the resolved absolute path either way. The option help and `docs/COMMANDS.md` say so.
- **F003 (duplicated id hashing): not changed.** The reviewer calls two uses tolerable; a shared helper waits for a third.
- **F004 (no pruning of deleted files): documented, not changed.** Slice design D5 keys a record on project and path and the architecture says one record per file. `docs/COMMANDS.md` states that a deleted or renamed review leaves its record behind.
- **F005 (test helper annotation): fixed.**

### Run Digest

- Response length: 3240 chars
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
- Tokens — prompt / cached / cache write / completion / reasoning: 63453 / 2921 / 60530 / 3108 / not computed
- Duration: 26.5 s
- Cost: $0.31 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 6
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 6
- Finding-shaped matches — surviving validation: 6
