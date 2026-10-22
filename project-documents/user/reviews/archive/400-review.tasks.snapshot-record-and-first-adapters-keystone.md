---
docType: review
layer: project
reviewType: tasks
slice: snapshot-record-and-first-adapters-keystone
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: stated
sourceDocument: project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md
aiModel: claude-sonnet-5-5
aiProfile: sdk
status: complete
dateCreated: 20261022
dateUpdated: 20261022
reviewedSha: d54ea98fbb7f98237c51281d7e976b3166a67f01
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 4
turns: 5
promptTokens: 198286
cachedTokens: 97931
cacheWriteTokens: 100349
completionTokens: 6353
durationSeconds: 52.1
costUsd: 0.475467
costBasis: provider
runId: run-20261022-p5-31b932ac
squadronVersion: 0.23.7
findings:
  - id: F001
    severity: concern
    category: sequencing
    summary: "TypeScript adapter work (Tasks 26–29) is committed as one batch"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:264-287"
  - id: F002
    severity: concern
    category: error-handling
    summary: "Tests assert ERROR logs that the implementation tasks never ask for"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:105-130"
  - id: F003
    severity: concern
    category: error-handling
    summary: "Store-write failure is handled in the CLI but has no log step and no test"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:295-300"
  - id: F004
    severity: note
    category: test-coverage
    summary: "TypeScript parse-failure coverage is thinner than the Python equivalent"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:272-274"
  - id: F005
    severity: note
    category: test-coverage
    summary: "Criterion 10 is only partly checked for `report baseline` and `audit delta`"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:91-97"
  - id: F006
    severity: note
    category: sequencing
    summary: "Several small tasks have no commit of their own"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md:45-130"
  - id: F007
    severity: pass
    category: coverage
    summary: "Success criteria 1–9 trace to implementation and test tasks"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md:307-324"
  - id: F008
    severity: pass
    category: scope
    summary: "Scope, sizing and proportionality fit the slice"
    location: "project-documents/user/tasks/400-tasks.snapshot-record-and-first-adapters-keystone.md"
  - id: F009
    severity: pass
    category: nfr
    summary: "No load-test requirement applies"
    location: "project-documents/user/slices/400-slice.snapshot-record-and-first-adapters-keystone.md:391"
---

# Review: tasks — slice 400

**Verdict:** CONCERNS
**Model:** claude-sonnet-5-5

## Findings

### [CONCERN] TypeScript adapter work (Tasks 26–29) is committed as one batch

The Python adapter commits after every implementation-plus-test pair (Tasks 21, 23 and 25). The TypeScript adapter does not. Tasks 26 and 27 (tree-sitter length) have no commit, and Task 28 (ESLint) has none either. Everything lands in the single commit at Task 29. That commit covers two implementation tasks and two test tasks. Project rules say to commit at least once per task. Add `feat(metrology): add TypeScript adapter with tree-sitter length` after Task 27, and narrow Task 29's commit to ESLint lint.

### [CONCERN] Tests assert ERROR logs that the implementation tasks never ask for

Task 10 asserts that a `run_git` result of `None` "logs ERROR" in both preflight and integrity. Task 9, which implements those paths, only says to raise and name the call; it never says to log at ERROR. The same goes for `resolve_files` in Task 12. Task 13's `None` test checks only the raised exception, not a log. The design's failure-mode table lists "ERROR log and the message on stderr" for these cases. The technical requirements want each failure mode tested for both its log signal and its outcome. Add the ERROR logging to Tasks 9 and 12, and an ERROR-log assertion to Task 13.

### [CONCERN] Store-write failure is handled in the CLI but has no log step and no test

Task 30 maps `MetrologyStoreError` to stderr and exit 1. The design's failure table also calls for an ERROR log, and the review rules require every failure mode to be observable. Task 31's cases (clean run, `--json`, dirty tree, `--cwd`, `list`) leave the store-write failure untested. Add one CLI test with a store that fails to write. It should assert exit 1, the path on stderr, and the ERROR log. Task 30 should say where that log is emitted.

### [NOTE] TypeScript parse-failure coverage is thinner than the Python equivalent

Task 26 sends both an error-root tree and an undecodable file to `unparsed_files`. Task 27 tests only a syntax-error file. Python (Task 21) tests all four failure types. The technical requirements list undecodable files as a required parse failure test. Add an undecodable-bytes case to Task 27.

### [NOTE] Criterion 10 is only partly checked for `report baseline` and `audit delta`

Success Criterion 10 names `sq metrology list`, `report baseline` and `audit delta`. Task 7 loads a store holding every existing record type plus a snapshot. Task 31 checks `list` output. Walkthrough step 10 covers `list` and `report baseline`. Nothing checks `audit delta`. Each of those commands reads the store with `_iter_records` and filters by `record_type` (`store.py:176` and the filters after it), so the risk is low. Add one assertion in Task 7 or Task 31 if you want the criterion fully covered.

### [NOTE] Several small tasks have no commit of their own

Tasks 2, 3, 4, 6, 8, 9, 11, 12, 16, 18, 20, 22, 24 and 28 share the commit of the test task that follows them. For Tasks 2–4, 6, 9, 11, 12, 16, 18, 20, 22 and 24 this fits the test-with pattern and is acceptable. Task 8 (config keys) is the exception. It sits between two commits and its only check is a manual `sq config set`. It stays uncommitted until Task 10, two tasks later. A line in Task 10 asserting the four keys' types and defaults would give it a real check.

### [PASS] Success criteria 1–9 trace to implementation and test tasks

- **Criterion 1** (one record per commit, rerun leaves one): Tasks 6, 7, 19 and 31.
- **Criterion 2** (dirty tree refused): Tasks 9, 10 and 31.
- **Criterion 3** (identity enforced by the model): Tasks 4 and 5.
- **Criterion 4** (identical JSON across runs): Tasks 19 and 33.
- **Criterion 5** (over-limit reporting): Task 14, including the derived `files_over_limit()`.
- **Criterion 6** (absence reasons): Tasks 19, 23, 25 and 29.
- **Criterion 7** (exclusions and `tool_ignored_files`): Tasks 13, 15, 28 and 29.
- **Criterion 8** (integrity check): Tasks 10 and 19.
- **Criterion 9** (untracked `.squadron.toml` exempt, INFO line on overwrite): Tasks 7 and 10.

### [PASS] Scope, sizing and proportionality fit the slice

Every task cites a decision or success criterion from the design. I found no scope creep. `resolve_files` and `files_over_limit()` are public because the design asks for them (404's scope report and the CLI summary). The slice has two adapters, a store extension and a CLI, and 34 tasks in one file is reasonable for that. The tests target specific criteria rather than adding extras. Tasks 4, 24 and the 300-line limit have explicit split fallbacks. Task 15 correctly captures real tool output before any parser (Tasks 17, 22, 25, 28) consumes it, and it stops with `BLOCKED:` rather than installing into `../context-forge`.

### [PASS] No load-test requirement applies

The slice restates no NFR. Performance is bounded by the configurable tool timeout, and the design already tests the timeout. A `tests/load/` task and a CI gating task are not needed.

### Run Digest

- Response length: 6486 chars
- Response is newline-free: no
- Tool calls made: 4
- Tool calls failed: 0
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: backend default
- Turns: 5
- Tokens — prompt / cached / cache write / completion / reasoning: 198286 / 97931 / 100349 / 6353 / not computed
- Duration: 52.1 s
- Cost: $0.48 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 9
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 9
- Finding-shaped matches — surviving validation: 9
