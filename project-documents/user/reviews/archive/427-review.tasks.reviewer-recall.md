---
docType: review
layer: project
reviewType: tasks
slice: reviewer-recall
conventionsSource: AGENTS.md
projectRules: []
project: squadron
verdict: CONCERNS
verdictSource: derived
sourceDocument: project-documents/user/tasks/427-tasks.reviewer-recall.md
aiModel: claude-haiku-5-5
aiProfile: sdk
status: complete
dateCreated: 20261106
dateUpdated: 20261106
reviewedSha: 135b683e4d37d59620b8d094a370651ac1a8675b
revision_number: 1
toolsGiven: [read_file, list_files, grep]
toolCallsMade: 16
effort: xhigh
turns: 17
promptTokens: 1089481
cachedTokens: 916645
cacheWriteTokens: 172820
completionTokens: 75566
durationSeconds: 335.6
costUsd: 0.395449
costBasis: provider
runId: run-20261106-tasks-plan-9f00462c
squadronVersion: 0.24.23
findings:
  - id: F001
    severity: concern
    category: design-consistency
    summary: "Task 1 correction list omits sections that still contradict the tasks"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:68"
  - id: F002
    severity: concern
    category: correctness
    summary: "Spacing check uses original lines, so line-removing defects can break the success criterion"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:176"
  - id: F003
    severity: concern
    category: implementation-gap
    summary: "Operator-token location is not specified"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:102"
  - id: F004
    severity: concern
    category: test-coverage
    summary: "No fixture for a selected test that passes under the defect"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:160"
  - id: F005
    severity: concern
    category: test-design
    summary: "\"Fixture tree byte-identical\" conflicts with the flaky fixture and pytest caches"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:171"
  - id: F006
    severity: concern
    category: sequencing
    summary: "Walkthrough step 6 cannot produce its expected exit 2"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:313"
  - id: F007
    severity: concern
    category: dependencies
    summary: "No named parser for the `path#name` anchor name"
    location: "src/squadron/review/parsers.py:287"
  - id: F008
    severity: concern
    category: dependencies
    summary: "Dependency on 422 and 426 contradicts the design"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:6"
  - id: F009
    severity: concern
    category: scope
    summary: "Task 10 refactors sibling code and bundles it under `feat:`"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:132"
  - id: F010
    severity: concern
    category: design-consistency
    summary: "Recall identity fields do not match the schema"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:317"
  - id: F011
    severity: concern
    category: maintainability
    summary: "Source files will pass the ~300-line limit with splits deferred"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:324"
  - id: F012
    severity: concern
    category: proportionality
    summary: "Task file is overweight"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md"
  - id: F013
    severity: note
    category: test-verification
    summary: "Task 4's pyright check cannot run on a test"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:90"
  - id: F014
    severity: note
    category: correctness
    summary: "Root commit is rejected with a misleading reason"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:181"
  - id: F015
    severity: note
    category: clarity
    summary: "Several targets are not named"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:214"
  - id: F016
    severity: note
    category: clarity
    summary: "Misplaced and mislabeled references"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:124"
  - id: F017
    severity: note
    category: cross-slice
    summary: "425's design still defines `ReviewerRef` with `rules_hash`"
    location: "project-documents/user/slices/425-slice.grading-and-paired-report.md:384"
  - id: F018
    severity: pass
    category: coverage
    summary: "Success criteria are covered"
    location: "project-documents/user/slices/427-slice.reviewer-recall.md:389"
  - id: F019
    severity: pass
    category: sequencing
    summary: "Sequencing, test-with pattern and commit markers"
    location: "project-documents/user/tasks/427-tasks.reviewer-recall.md:40"
  - id: F020
    severity: pass
    category: dependencies
    summary: "Named helpers exist in the repo"
    location: "src/squadron/review/models.py:26"
---

# Review: tasks — slice 427

**Verdict:** CONCERNS
**Model:** claude-haiku-5-5

## Findings

### [CONCERN] Task 1 correction list omits sections that still contradict the tasks

Task 1 lists D8, D9, D1, D4, D11, the adapter contract, Technical Scope, API Contracts, Component Structure and Implementation Notes. It does not list three sections that will still conflict after Task 1 runs. Success Criteria (design line 395) says "within 2 × RECALL_LINE_WINDOW + 1 lines", which forbids the distance 2W+1 that Task 15 allows. Patterns and Conventions (design line 266) puts the enums in `benchmark_models.py`, but Task 11 puts them in `recall_models.py`. Database/Storage Schema (design line 375) says `BenchmarkRecordStore` gains the recall methods, but Task 12 puts them in `RecallRecordStore`. Context Summary line 51 says spacing is "(D4, Success Criteria)", so the intent is there; the list is incomplete.

### [CONCERN] Spacing check uses original lines, so line-removing defects can break the success criterion

Task 15 measures spacing between kept defects in original-tree lines. A kept deletion above a later defect moves that defect's defected-tree line up by the removed count. The success criterion uses stored (defected-tree) lines. Example with W=3: deleting lines 10–12 leaves a zero-width defect at 10. A defect originally at 17 is 7 lines away in original coordinates, so it is allowed. In the defected tree it sits at 14, which is 4 away, and a finding at line 12 reaches both. The check needs defected-tree lines that include the candidate's own net change, plus a test where the deletion is kept after the later defect.

### [CONCERN] Operator-token location is not specified

`ast` gives node spans, not operator spans. `compare-boundary`, `compare-negate` and `bool-swap` change one operator token inside a `Compare` or `BoolOp` node. "Replaces exactly the node's segment" cannot express that, and D4 forbids `ast.unparse`. The chained-comparison test on line 103 needs the same thing. The task should name how the token is found (for example, `tokenize` over the node's segment, or a scan between operand spans).

### [CONCERN] No fixture for a selected test that passes under the defect

The design's Technical Requirements (design line 405) lists "one rejected because no selected test fails". `recall_unselected` has no test that imports the module, so it exercises empty selection (`no_selected_tests`), not a selected test that passes under the mutant. Task 14 never runs real pytest on that path. Add a fixture where a test imports the module but does not reach the mutated line, and a Task 14 test that expects `NotProved`.

### [CONCERN] "Fixture tree byte-identical" conflicts with the flaky fixture and pytest caches

`recall_flaky` (line 161) increments a counter file, and Task 14 (line 171) requires the tree to be byte-identical after each call. pytest also writes `__pycache__` and `.pytest_cache` during runs. Put the counter outside the tree (for example, a path passed in from `tmp_path`), and define the identity check as "source and test files unchanged", or disable caches for these runs.

### [CONCERN] Walkthrough step 6 cannot produce its expected exit 2

`recall_run_id` is derived from set name, version, reviewer keys and K (design line 249), not from `--max-cost`. After step 3 completes, step 6 with `--max-cost 0.30` finds no planned reviews and exits 0 complete. The cap demonstration needs a fresh run id (a different K or set) or must run before step 3 finishes, then resume with `--max-cost 8`. Design walkthrough step 6 (design line 450) has the same problem.

### [CONCERN] No named parser for the `path#name` anchor name

D6 and Task 22 need the name in a `path#name` anchor. `location_path` returns the path before `#`, `location_span` returns None for anchors (per its docstring), and `location_line` gives no name. Nothing returns the anchor name, and Task 22 does not name a parser. Either add a helper in 917's module so findings are read the same way everywhere, or specify it in Task 22 with a test on the real anchor format.

### [CONCERN] Dependency on 422 and 426 contradicts the design

The design says "427 does not depend on 422 or 426" (design line 67), and the frontmatter lists no 422. But Task 10 requires `commands/sq/benchmark.md`, which 422 creates, Task 35 extends that file, and Task 20 follows "426's `build_deps()`" style. Either add 422 to the frontmatter and correct design line 67, or drop the 426 reference.

### [CONCERN] Task 10 refactors sibling code and bundles it under `feat:`

Task 10 may move 421's project-source rule and 424's lock helper into shared functions on this branch, and it says the change is a `refactor:`. The only marker (line 138) is `feat:`. The design's Integration Points (design line 385) limit 421 changes to the set write, and 424's lock is not a listed consumed interface. Record these sibling refactors in the design, and commit them separately with a `refactor:` prefix before the feature commit.

### [CONCERN] Recall identity fields do not match the schema

D5 hashes each defect's `edit_span` and `replacement`. `PlantedDefect` (design lines 317–328) has no `replacement` field, only `mutated`. Task 11 says "defects" and tests "one defect's replacement text", which would also hash `proving_tests` and `enclosing_symbols`. Name the hashed fields explicitly and make the field names agree. The rebuild-stability criterion depends on this.

### [CONCERN] Source files will pass the ~300-line limit with splits deferred

`python_recall.py` collects Tasks 6–10 (expression and statement finders, apply, symbols, import closure, `is_source_path`). `recall_runner.py` collects Tasks 27–29 (begin, loop, cap, retry, lock). `benchmark_recall.py` collects Tasks 20, 30 and 34. Only Task 7 offers a split, and Task 37 defers the check to the end. Name the split modules in the tasks that create the files.

### [CONCERN] Task file is overweight

The file has 37 tasks, about 330 lines and about 20 commit markers, and its Context Summary repeats Task 1's gap list. Possible cuts:
- Fold Task 4's constants-only test (line 91) into the Task 3 or Task 5 tests.
- Merge Task 35 (a single doc edit) into Task 34.
- Drop the grep-style test in Task 25 (line 236). A unit assertion on the model fields covers it.
- Condense Context Summary's gap bullets into pointers to Task 1.
- Keep walkthrough step 7 as the design defines it, but note that Tasks 22–23 already run that file.

### [NOTE] Task 4's pyright check cannot run on a test

Task 4 requires a stub in `tests/` that "type-checks as RecallAdapter (pyright)". The repo's `pyproject.toml:100` sets `include = ["src"]`, and the task file's own note (line 59) says tests are not pyright-checked. The Python rules file says tests should be included, so the repo and the rule disagree. Move the conformance check into a `src` module, or assert conformance at runtime, and note the config gap.

### [NOTE] Root commit is rejected with a misleading reason

A parentless root commit has no P..C diff, and Task 16 rejects it as `no_source_change`, which misreports it. Either skip root commits in discovery and document that in the design, or add a reason with a matching test.

### [NOTE] Several targets are not named

- Tasks 21, 36 and 37 say "DEVLOG" with no path. The only DEVLOG files found are archived quarterly logs under `project-documents/user/archive/devlog/`.
- Task 37 (line 326) says "its slice-plan entry" with no path. The parent is `user/architecture/420-slices.model-benchmark.md`.
- Task 2 (line 78) says "the existing keys test file". It is `tests/config/test_keys.py`.
- Task 36 step 5 (line 311) says "an alias with no recall run" and does not name one.

### [NOTE] Misplaced and mislabeled references

Task 9 carries the real-source operator-coverage test, which belongs with Tasks 6–7. Task 4 (line 89) says "exactly as D4's API Contracts block", but the block is in Implementation Details under API Contracts.

### [NOTE] 425's design still defines `ReviewerRef` with `rules_hash`

425's design defines `ReviewerRef` with `rules_hash` (line 384, also line 207). 425's task file (line 48) drops it, and 427's Task 1 relies on that drop. Confirm 425's Task 1 corrects its design before 427 imports the type.

### [PASS] Success criteria are covered

Every functional criterion (F1–F7), technical criterion (T1–T5), integration criterion (I1–I2) and walkthrough step (1–7) maps to at least one task. The matcher criteria map to named cases in Tasks 22–23. The failure-mode tests from the review rule are present (Tasks 12, 14, 16, 17, 19, 27, 29, and 28 for the review-failure double). The design restates no NFR, so no load-test task is required.

### [PASS] Sequencing, test-with pattern and commit markers

Dependencies run forward with no cycles. Task 15 needs Tasks 4, 5 and 9, and Task 32 precedes Task 33. Every implementation task carries its own tests. The roughly 20 `**Commit**:` markers sit at tested points, and none follows every task.

### [PASS] Named helpers exist in the repo

Verified in `src/`: `Severity` (PASS, NOTE, CONCERN, FAIL), `ReviewCategory` (`CORRECTNESS`, `ERROR_HANDLING_OBSERVABILITY`), `location_path`, `location_span`, `get_positive_int_config`, `derive_project_id`, `SourceLanguage`, and `MetrologyRecord` in `metrology/models.py`. Task 10's precondition list covers the 421–425 names.

### Run Digest

- Response length: 13346 chars
- Response is newline-free: no
- Tool calls made: 16
- Tool calls failed: 1
- Stop reason: end_turn
- Output budget: backend default
- System prompt: preset+append
- Settings sources: project
- Reasoning characters: 0
- Effort: xhigh
- Turns: 17
- Tokens — prompt / cached / cache write / completion / reasoning: 1089481 / 916645 / 172820 / 75566 / not computed
- Duration: 335.6 s
- Cost: $0.40 (provider)
- `## Summary` located: yes
- `## Findings` located: yes
- Finding-shaped matches — whole response: 20
- Finding-shaped matches — inside fences: 0
- Finding-shaped matches — in findings section: 20
- Finding-shaped matches — surviving validation: 20

### Raw Response

I've read both documents. Before scoring, I'll check the names and paths the tasks lean on that the preconditions in Task 10 don't cover.
Most named helpers exist. Next I'll check the enum members, the anchor parsing that D6 relies on, and whether the benchmark package and a current DEVLOG exist.
The Python rules file is project guidance and doesn't change the review. It does say pyright should include `tests`, while Task 37 and the task file's note say pyright covers `src` only, so I'll check the repo's `pyproject.toml` too. Retrying the enum-member grep as two separate calls, since the last one failed on a space-joined path.
Enum members and `Severity` values exist. The repo's pyright config is `include = ["src"]`, so test-level pyright claims aren't checked. `src/squadron/benchmark/` doesn't exist yet, which matches the project state. Last checks: whether the anchor-name parsing D6 needs has a helper, and whether the sibling designs (421, 425) name the symbols 427 imports.
No helper parses the `path#name` anchor name; `location_path` and `location_span` return nothing useful for anchors, so D6's anchor rule has no named parser. Now the 425 design's exact signatures for the symbols 427 imports, since D8 and D11 depend on them.
The 425 design still defines `ReviewerRef` with `rules_hash` (line 384), while 427's context says 425 Task 7 drops it. Checking the 425 task file to see whether the drop is actually written there.
## Summary

**Verdict: CONCERNS.** The 37 tasks cover every success criterion in the slice design, and the test-with pattern and commit markers are in the right places. The gaps are in the details. Task 1's correction list misses sections that still contradict the tasks. The spacing rule can be violated after line-removing defects. Two implementation points are unspecified (operator-token location and anchor-name parsing). Walkthrough step 6 cannot produce its expected exit code, and the 422 dependency is inconsistent. None of these is a FAIL.

Current state: `src/squadron/benchmark/` does not exist. Tasks 2–9 can start now, and Task 1 should land first. Task 10 will stop with `BLOCKED:` on 421–425, so Tasks 11–37 wait on those slices.

## Findings

### [CONCERN] Task 1 correction list omits sections that still contradict the tasks
category: design-consistency
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:68
Task 1 lists D8, D9, D1, D4, D11, the adapter contract, Technical Scope, API Contracts, Component Structure and Implementation Notes. It does not list three sections that will still conflict after Task 1 runs. Success Criteria (design line 395) says "within 2 × RECALL_LINE_WINDOW + 1 lines", which forbids the distance 2W+1 that Task 15 allows. Patterns and Conventions (design line 266) puts the enums in `benchmark_models.py`, but Task 11 puts them in `recall_models.py`. Database/Storage Schema (design line 375) says `BenchmarkRecordStore` gains the recall methods, but Task 12 puts them in `RecallRecordStore`. Context Summary line 51 says spacing is "(D4, Success Criteria)", so the intent is there; the list is incomplete.

### [CONCERN] Spacing check uses original lines, so line-removing defects can break the success criterion
category: correctness
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:176
Task 15 measures spacing between kept defects in original-tree lines. A kept deletion above a later defect moves that defect's defected-tree line up by the removed count. The success criterion uses stored (defected-tree) lines. Example with W=3: deleting lines 10–12 leaves a zero-width defect at 10. A defect originally at 17 is 7 lines away in original coordinates, so it is allowed. In the defected tree it sits at 14, which is 4 away, and a finding at line 12 reaches both. The check needs defected-tree lines that include the candidate's own net change, plus a test where the deletion is kept after the later defect.

### [CONCERN] Operator-token location is not specified
category: implementation-gap
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:102
`ast` gives node spans, not operator spans. `compare-boundary`, `compare-negate` and `bool-swap` change one operator token inside a `Compare` or `BoolOp` node. "Replaces exactly the node's segment" cannot express that, and D4 forbids `ast.unparse`. The chained-comparison test on line 103 needs the same thing. The task should name how the token is found (for example, `tokenize` over the node's segment, or a scan between operand spans).

### [CONCERN] No fixture for a selected test that passes under the defect
category: test-coverage
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:160
The design's Technical Requirements (design line 405) lists "one rejected because no selected test fails". `recall_unselected` has no test that imports the module, so it exercises empty selection (`no_selected_tests`), not a selected test that passes under the mutant. Task 14 never runs real pytest on that path. Add a fixture where a test imports the module but does not reach the mutated line, and a Task 14 test that expects `NotProved`.

### [CONCERN] "Fixture tree byte-identical" conflicts with the flaky fixture and pytest caches
category: test-design
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:171
`recall_flaky` (line 161) increments a counter file, and Task 14 (line 171) requires the tree to be byte-identical after each call. pytest also writes `__pycache__` and `.pytest_cache` during runs. Put the counter outside the tree (for example, a path passed in from `tmp_path`), and define the identity check as "source and test files unchanged", or disable caches for these runs.

### [CONCERN] Walkthrough step 6 cannot produce its expected exit 2
category: sequencing
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:313
`recall_run_id` is derived from set name, version, reviewer keys and K (design line 249), not from `--max-cost`. After step 3 completes, step 6 with `--max-cost 0.30` finds no planned reviews and exits 0 complete. The cap demonstration needs a fresh run id (a different K or set) or must run before step 3 finishes, then resume with `--max-cost 8`. Design walkthrough step 6 (design line 450) has the same problem.

### [CONCERN] No named parser for the `path#name` anchor name
category: dependencies
location: src/squadron/review/parsers.py:287
D6 and Task 22 need the name in a `path#name` anchor. `location_path` returns the path before `#`, `location_span` returns None for anchors (per its docstring), and `location_line` gives no name. Nothing returns the anchor name, and Task 22 does not name a parser. Either add a helper in 917's module so findings are read the same way everywhere, or specify it in Task 22 with a test on the real anchor format.

### [CONCERN] Dependency on 422 and 426 contradicts the design
category: dependencies
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:6
The design says "427 does not depend on 422 or 426" (design line 67), and the frontmatter lists no 422. But Task 10 requires `commands/sq/benchmark.md`, which 422 creates, Task 35 extends that file, and Task 20 follows "426's `build_deps()`" style. Either add 422 to the frontmatter and correct design line 67, or drop the 426 reference.

### [CONCERN] Task 10 refactors sibling code and bundles it under `feat:`
category: scope
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:132
Task 10 may move 421's project-source rule and 424's lock helper into shared functions on this branch, and it says the change is a `refactor:`. The only marker (line 138) is `feat:`. The design's Integration Points (design line 385) limit 421 changes to the set write, and 424's lock is not a listed consumed interface. Record these sibling refactors in the design, and commit them separately with a `refactor:` prefix before the feature commit.

### [CONCERN] Recall identity fields do not match the schema
category: design-consistency
location: project-documents/user/slices/427-slice.reviewer-recall.md:317
D5 hashes each defect's `edit_span` and `replacement`. `PlantedDefect` (design lines 317–328) has no `replacement` field, only `mutated`. Task 11 says "defects" and tests "one defect's replacement text", which would also hash `proving_tests` and `enclosing_symbols`. Name the hashed fields explicitly and make the field names agree. The rebuild-stability criterion depends on this.

### [CONCERN] Source files will pass the ~300-line limit with splits deferred
category: maintainability
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:324
`python_recall.py` collects Tasks 6–10 (expression and statement finders, apply, symbols, import closure, `is_source_path`). `recall_runner.py` collects Tasks 27–29 (begin, loop, cap, retry, lock). `benchmark_recall.py` collects Tasks 20, 30 and 34. Only Task 7 offers a split, and Task 37 defers the check to the end. Name the split modules in the tasks that create the files.

### [CONCERN] Task file is overweight
category: proportionality
location: project-documents/user/tasks/427-tasks.reviewer-recall.md
The file has 37 tasks, about 330 lines and about 20 commit markers, and its Context Summary repeats Task 1's gap list. Possible cuts:
- Fold Task 4's constants-only test (line 91) into the Task 3 or Task 5 tests.
- Merge Task 35 (a single doc edit) into Task 34.
- Drop the grep-style test in Task 25 (line 236). A unit assertion on the model fields covers it.
- Condense Context Summary's gap bullets into pointers to Task 1.
- Keep walkthrough step 7 as the design defines it, but note that Tasks 22–23 already run that file.

### [NOTE] Task 4's pyright check cannot run on a test
category: test-verification
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:90
Task 4 requires a stub in `tests/` that "type-checks as RecallAdapter (pyright)". The repo's `pyproject.toml:100` sets `include = ["src"]`, and the task file's own note (line 59) says tests are not pyright-checked. The Python rules file says tests should be included, so the repo and the rule disagree. Move the conformance check into a `src` module, or assert conformance at runtime, and note the config gap.

### [NOTE] Root commit is rejected with a misleading reason
category: correctness
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:181
A parentless root commit has no P..C diff, and Task 16 rejects it as `no_source_change`, which misreports it. Either skip root commits in discovery and document that in the design, or add a reason with a matching test.

### [NOTE] Several targets are not named
category: clarity
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:214
- Tasks 21, 36 and 37 say "DEVLOG" with no path. The only DEVLOG files found are archived quarterly logs under `project-documents/user/archive/devlog/`.
- Task 37 (line 326) says "its slice-plan entry" with no path. The parent is `user/architecture/420-slices.model-benchmark.md`.
- Task 2 (line 78) says "the existing keys test file". It is `tests/config/test_keys.py`.
- Task 36 step 5 (line 311) says "an alias with no recall run" and does not name one.

### [NOTE] Misplaced and mislabeled references
category: clarity
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:124
Task 9 carries the real-source operator-coverage test, which belongs with Tasks 6–7. Task 4 (line 89) says "exactly as D4's API Contracts block", but the block is in Implementation Details under API Contracts.

### [NOTE] 425's design still defines `ReviewerRef` with `rules_hash`
category: cross-slice
location: project-documents/user/slices/425-slice.grading-and-paired-report.md:384
425's design defines `ReviewerRef` with `rules_hash` (line 384, also line 207). 425's task file (line 48) drops it, and 427's Task 1 relies on that drop. Confirm 425's Task 1 corrects its design before 427 imports the type.

### [PASS] Success criteria are covered
category: coverage
location: project-documents/user/slices/427-slice.reviewer-recall.md:389
Every functional criterion (F1–F7), technical criterion (T1–T5), integration criterion (I1–I2) and walkthrough step (1–7) maps to at least one task. The matcher criteria map to named cases in Tasks 22–23. The failure-mode tests from the review rule are present (Tasks 12, 14, 16, 17, 19, 27, 29, and 28 for the review-failure double). The design restates no NFR, so no load-test task is required.

### [PASS] Sequencing, test-with pattern and commit markers
category: sequencing
location: project-documents/user/tasks/427-tasks.reviewer-recall.md:40
Dependencies run forward with no cycles. Task 15 needs Tasks 4, 5 and 9, and Task 32 precedes Task 33. Every implementation task carries its own tests. The roughly 20 `**Commit**:` markers sit at tested points, and none follows every task.

### [PASS] Named helpers exist in the repo
category: dependencies
location: src/squadron/review/models.py:26
Verified in `src/`: `Severity` (PASS, NOTE, CONCERN, FAIL), `ReviewCategory` (`CORRECTNESS`, `ERROR_HANDLING_OBSERVABILITY`), `location_path`, `location_span`, `get_positive_int_config`, `derive_project_id`, `SourceLanguage`, and `MetrologyRecord` in `metrology/models.py`. Task 10's precondition list covers the 421–425 names.
